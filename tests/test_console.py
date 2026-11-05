"""Native model handoffs must bind original evidence, author, draft and job."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agents.console import start, receive, guide, Review
from agents.models import replay
from agents.worker import Worker
from app.models import Album
from app.store import Store


@pytest.fixture
def room(tmp_path):
    store = Store(tmp_path)
    binding = dict(storyteller=dict(id="native-claude", name="mw-storyteller-claude"), editor=dict(id="native-codex", name="mw-editor-codex"))
    store.set("console", binding)
    for a in json.loads(Path("tests/fixtures/assets.json").read_text()):
        store.put("assets", a)
    sources = [dict(id=p["key"], author=p["author"], text=p["text"], captured_at=p["at"], asset_ids=[p["asset"]] if p["asset"] else []) for p in json.loads(Path("tests/fixtures/posts.json").read_text())]
    payload = dict(job=store.job("Create an English travel journal", "request"), sources=sources, previous=None, mode="live")
    documents = {"evidence": payload}
    sent = []

    async def op(operation, **args):
        if operation == "list_participants":
            return [dict(**v, type="agent") for v in binding.values()]
        sent.append((operation,args))

    async def load(id):
        return deepcopy(documents[id])

    async def report(*args): pass
    worker = SimpleNamespace(store=store, client=SimpleNamespace(op=op, load=load), report=report)
    return worker, payload, documents, sent


def event(role, marker, doc="draft", job="request", id=None):
    return dict(sender_kind="agent", sender_name="mw-"+role+ ("-claude" if role=="storyteller" else "-codex"), sender_agent_id=id or ("native-claude" if role=="storyteller" else "native-codex"), body=marker+" "+json.dumps(dict(job_id=job,document_id=doc)))


async def draft(room):
    w,p,docs,_ = room
    await start(w,"evidence",p,"original-thread")
    docs["draft"] = dict(job_id="request",album=replay(p))
    await receive(w,event("storyteller","MW_DRAFT"))
    docs["review"] = dict(job_id="request",draft_document_id="draft",album=docs["draft"]["album"],approved=True,notes=["Checked original evidence"])


async def test_native_roundtrip_commits_once_and_keeps_publication_separate(room):
    await draft(room)
    w,p,docs,sent = room
    assert sent[0][1]["target_names"] == ["mw-storyteller-claude"]
    assert sent[0][1]["thread_id"] == "original-thread"
    assert w.store.revision() is None
    assert await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision()["mode"] == "live"
    assert w.store.revision()["sources"] == p["sources"]
    assert w.store.delivery(1)["state"] == "pending"
    await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision()["version"] == 1
    assert w.store.get("publication") is None


@pytest.mark.parametrize("mutation", ["evidence", "draft", "citation", "quote", "job", "draft_id"])
async def test_native_review_rejects_changed_or_uncorroborated_artifacts(room, mutation):
    await draft(room)
    w,p,docs,_ = room
    if mutation == "evidence": docs["evidence"]["sources"][0]["text"] = "tampered"
    elif mutation == "draft": docs["draft"]["album"]["title"] = "tampered"
    elif mutation == "citation": docs["review"]["album"]["chapters"][0]["source_ids"] = ["fake"]
    elif mutation == "quote": docs["review"]["album"]["chapters"][0]["quote"] = "invented words"
    elif mutation == "job": docs["review"]["job_id"] = "other"
    elif mutation == "draft_id": docs["review"]["draft_document_id"] = "other"
    else: docs["review"]["approved"] = False
    with pytest.raises(ValueError):
        await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision() is None


async def test_spoofed_names_and_old_docker_agents_cannot_commit(room):
    await draft(room)
    w,_,_,_ = room
    await receive(w,event("editor","MW_REVIEW","review",id="old-docker-editor"))
    fake=event("editor","MW_REVIEW","review")
    fake["sender_kind"]="user"
    assert not await receive(w,fake)
    assert w.store.revision() is None


async def test_docker_writer_does_not_process_native_job(room):
    w,_,_,_=room
    worker=Worker.__new__(Worker)
    worker.role,worker.store="storyteller",w.store
    await worker.handle(dict(id="handoff",kind="message",sender_kind="agent",sender_name="mw-collector",body='MW_HANDOFF {"document_id":"evidence"}'))
    assert w.store.handled("storyteller","handoff")


def test_shipped_workspace_contracts_match_runtime():
    assert json.loads(Path("agents/console-workspaces/editor/editorial.schema.json").read_text()) == Review.model_json_schema()
    for role,file in [("editor","AGENTS.md"),("storyteller","CLAUDE.md")]:
        assert Path(f"agents/console-workspaces/{role}/{file}").read_text().endswith(guide(role))
        assert json.loads(Path(f"agents/console-workspaces/{role}/album.schema.json").read_text()) == Album.model_json_schema()


async def test_editor_can_correct_a_draft_before_final_validation(room):
    w,p,docs,_=room
    await start(w,"evidence",p,"thread")
    good=replay(p)
    bad=deepcopy(good)
    bad["chapters"][0]["date"]="\u64ae\u5f71\u65e5\u672a\u78ba\u8a8d"
    bad["chapters"][0]["quote"]="unsupported quotation"
    docs["draft"]={"job_id":"request","album":bad}
    await receive(w,event("storyteller","MW_DRAFT"))
    docs["review"]=dict(job_id="request",draft_document_id="draft",album=good,approved=True,notes=["Corrected date and quote against evidence"])
    await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision()["album"]=={**good,"design":"classic"}


async def test_binding_requires_internal_auth_and_waits_for_working_job(tmp_path,monkeypatch):
    import httpx
    from app import main
    store=Store(tmp_path)
    monkeypatch.setattr(main,"store",store)
    monkeypatch.setenv("WEB_INTERNAL_TOKEN","private-local-test-token")
    binding=dict(storyteller=dict(id="claude",name="writer"),editor=dict(id="codex",name="editor"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url="http://local") as h:
        assert (await h.post("/internal/console",json=binding)).status_code==403
        h.headers["Authorization"]="Bearer private-local-test-token"
        assert (await h.post("/internal/console",json=binding)).status_code==200
        assert store.get("console")==binding
        store.job("edit","working")
        assert (await h.post("/internal/console",json=binding)).status_code==409
        assert (await h.post("/internal/console",json={"storyteller":binding["editor"],"editor":binding["editor"]})).status_code==422
        assert "private-local-test-token" not in (await h.get("/api/state")).text


async def test_clarification_can_resume_but_new_request_supersedes_it(room):
    await draft(room)
    w,_,docs,_=room
    docs["review"]["approved"]=False
    await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision() is None
    docs["review"]["approved"]=True
    await receive(w,event("editor","MW_REVIEW","review"))
    assert w.store.revision()["version"]==1
    job=w.store.job("next edit","next")
    with w.store.connect() as db:db.execute("UPDATE jobs SET state='clarification' WHERE id='next'")
    w.store.job("superseding request","newest")
    with pytest.raises(ValueError,match="Stale"):
        w.store.commit(docs["review"]["album"],job["id"],"live",[])


async def test_renderer_question_uses_authenticated_switch_reply(room):
    await draft(room)
    w,_,_,sent=room
    await receive(w,event("editor","MW_RENDERER_QUERY",id="spoof"))
    assert len(sent)==1
    await receive(w,event("editor","MW_RENDERER_QUERY"))
    assert sent[-1][0]=="send_targeted_message"
    assert sent[-1][1]["target_names"]==["mw-editor-codex"]
    assert sent[-1][1]["thread_id"]=="original-thread"
    assert "MW_RENDERER_REPLY" in sent[-1][1]["body"]
    assert w.store.revision() is None
