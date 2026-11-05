import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
import time

import httpx
from PIL import Image
import pytest
from app.models import Album, validate_evidence
from app.store import Store
from agents.models import replay
from agents.publish import approval_command, approve_and_publish, build_export
from scripts.verify_release import verify


@pytest.fixture
def memory(tmp_path):
    store = Store(tmp_path)
    for asset in json.loads(Path("tests/fixtures/assets.json").read_text()):
        store.put("assets", asset)
    sources = [dict(id=p["key"], author=p["author"], text=p["text"], captured_at=p["at"], asset_ids=[p["asset"]] if p["asset"] else []) for p in json.loads(Path("tests/fixtures/posts.json").read_text())]
    for source in sources:
        store.put("sources", source)
    job = store.job("Create an English travel journal", "request-1")
    payload = dict(job=job, sources=sources, previous=None)
    album = replay(payload)
    version = store.commit(album, job["id"], "replay", sources)
    return store, payload, store.revision(version)


def test_shuffled_capture_dates_and_evidence(memory):
    store, payload, revision = memory
    album = Album.model_validate(revision["album"])
    validate_evidence(album, payload["sources"], {"kyoto-gates", "kyoto-river", "kyoto-bamboo", "kyoto-hall"})
    assert [c.date for c in album.chapters] == ["2026-10-12", "2026-10-13", "2026-10-14"]
    assert any(s["author"] == "hana" for s in revision["sources"])


@pytest.mark.parametrize("mutation", ["quote", "citation", "photo"])
def test_unsupported_evidence_rejected(memory, mutation):
    _, payload, revision = memory
    album = Album.model_validate(revision["album"])
    if mutation == "quote":
        album.chapters[0].quote = "A fabricated conversation"
    elif mutation == "citation":
        album.chapters[0].source_ids = ["nonexistent-post"]
    else:
        album.chapters[0].asset_ids = ["kyoto-hall"]
    with pytest.raises(ValueError):
        validate_evidence(album, payload["sources"], {"kyoto-gates", "kyoto-river", "kyoto-bamboo", "kyoto-hall"})


def test_concurrent_request_and_stale_commit(memory):
    store, payload, revision = memory
    first = store.job("Edit the cover", "edit-1")
    with pytest.raises(ValueError, match="already in progress"):
        store.job("Edit the prose", "edit-2")
    store.commit(revision["album"], first["id"], "replay", payload["sources"])
    with pytest.raises(ValueError, match="Stale"):
        store.commit(revision["album"], first["id"], "replay", payload["sources"])
    assert store.revision()["version"] == 2


async def test_approval_is_exact_and_invalidated_by_edit(memory, monkeypatch):
    store, payload, revision = memory
    monkeypatch.setenv("PUBLISH_ENABLED", "false")
    entry = dict(id="human-approval", sender="opaque-human-id")
    with pytest.raises(ValueError, match="exactly"):
        await approve_and_publish(store, "PUBLISH approved", entry)
    command = approval_command(revision)
    job = store.job("A sunset cover", "edit-cover")
    with pytest.raises(ValueError, match="in progress"):
        await approve_and_publish(store, command, entry)
    changed = deepcopy(revision["album"])
    changed["cover_asset_id"] = "kyoto-hall"
    store.commit(changed, job["id"], "replay", payload["sources"])
    with pytest.raises(ValueError, match="exactly"):
        await approve_and_publish(store, command, entry)
    message = await approve_and_publish(store, approval_command(store.revision()), entry)
    assert "No data was sent" in message
    assert store.get("publication")["state"] == "local-export"
    verify(store.root / "exports/v2")


def test_export_contains_selected_photos_no_conversation_and_escapes_html(memory):
    store, _, revision = memory
    secret = "private-message-that-is-never-a-chapter"
    store.put("sources", dict(id="unused", text=secret, author="private", captured_at="2026-01-01", asset_ids=[]))
    revision["album"]["title"] = '<script>alert("xss")</script>'
    destination, files = build_export(store, revision, dict(user_id="human-id", created=time.time()))
    assert b"<script>" not in files["index.html"]
    assert b"&lt;script&gt;" in files["index.html"]
    assert all(secret.encode() not in content for content in files.values())
    assert b"source_ids" not in files["book.json"]
    verify(destination)
    (destination / "unreviewed.txt").write_text("not approved")
    with pytest.raises(AssertionError, match="Unreviewed"):
        verify(destination)


async def test_media_requires_token_and_removes_exif(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "store", Store(tmp_path))
    monkeypatch.setenv("WEB_INTERNAL_TOKEN", "local-test-token")
    image = Image.new("RGB", (30, 20), "green")
    exif = Image.Exif()
    exif[270] = "Sensitive location metadata"
    stream = io.BytesIO()
    image.save(stream, format="JPEG", exif=exif)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as http:
        response = await http.post("/internal/media", files={"file": ("sample.jpg", stream.getvalue(), "image/jpeg")})
        assert response.status_code == 403
        response = await http.post("/internal/media", headers={"Authorization": "Bearer local-test-token"}, files={"file": ("sample.jpg", stream.getvalue(), "image/jpeg")})
        assert response.status_code == 200
        uploaded = response.json()
        photo = await http.get(uploaded["url"])
        assert not Image.open(io.BytesIO(photo.content)).getexif()
        assert "frame-ancestors 'none'" in photo.headers["content-security-policy"]
        state = (await http.get("/api/state")).json()
        assert "local-test-token" not in json.dumps(state)
        assert (await http.get("/media/not-a-valid-photo.jpg")).status_code == 404


def test_approval_binds_photo_bytes(memory):
    store, _, revision = memory
    revision["asset_hashes"]["kyoto-gates"] = "0" * 64
    with pytest.raises(ValueError, match="Photograph bytes differ"):
        build_export(store, revision, dict(user_id="human", created=time.time()))


@pytest.mark.parametrize("provider", ["claude", "codex"])
async def test_harness_contract_and_secret_filter(memory, monkeypatch, provider):
    from agents.models import harness
    store, payload, revision = memory
    monkeypatch.setenv("DATA_DIR", str(store.root))
    monkeypatch.setenv("PUBLISH_GITHUB_TOKEN", "not-allowed-in-model-env")
    monkeypatch.setenv("WEB_INTERNAL_TOKEN", "also-not-allowed-in-model-env")
    seen = {}
    async def fake_exec(*args, **kwargs):
        seen.update(args=args, env=kwargs["env"])
        if provider == "codex":
            output = Path(args[args.index("--output-last-message") + 1])
            output.write_text(json.dumps(dict(album=revision["album"], approved=True, notes=[])))
            schema = json.loads(Path(args[args.index("--output-schema") + 1]).read_text())
            assert schema["additionalProperties"] is False
        class Process:
            returncode = 0
            async def communicate(self, data):
                assert "UNTRUSTED INPUT JSON" in data.decode()
                return json.dumps(dict(structured_output=revision["album"])).encode(), b""
        return Process()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await harness(provider, payload)
    assert "PUBLISH_GITHUB_TOKEN" not in seen["env"]
    assert "WEB_INTERNAL_TOKEN" not in seen["env"]
    if provider == "codex":
        assert result["approved"]
        assert seen["args"].count("--image") == 4
        assert "read-only" in seen["args"] and "shell_tool" in seen["args"]
    else:
        assert result["title"] == revision["album"]["title"]
        assert seen["args"][seen["args"].index("--tools") + 1] == ""


async def test_github_subtree_commit_and_real_status_url_contract(memory, monkeypatch):
    from agents.publish import push_and_wait
    store, _, revision = memory
    monkeypatch.setenv("PUBLISH_GITHUB_REPOSITORY", "example/private-book")
    monkeypatch.setenv("PUBLISH_GITHUB_TOKEN", "test-only-token")
    calls = []
    def route(request):
        path = request.url.path.removeprefix("/repos/example/private-book")
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, path, body))
        result = {}
        if path == "":
            result = {"private": True}
        elif path == "/git/ref/heads/main":
            result = {"object": {"sha": "parent"}}
        elif path == "/git/commits/parent":
            result = {"tree": {"sha": "existing-tree"}}
        elif path == "/git/blobs":
            result = {"sha": "blob-" + str(len(calls))}
        elif path == "/git/trees":
            result = {"sha": "updated-tree" if body.get("base_tree") else "export-tree"}
        elif path == "/git/commits":
            result = {"sha": "approved-commit"}
        elif path == "/commits/approved-commit/status":
            result = {"statuses": [{"context": "memoryweaver/cloudflare", "state": "success", "target_url": "https://verified.example.pages.dev"}]}
        return httpx.Response(200, json=result)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(route)))
    url = await push_and_wait({"index.html": b"approved book"}, revision, store)
    assert url == "https://verified.example.pages.dev"
    trees = [body for method, path, body in calls if path == "/git/trees"]
    assert trees[1] == {"base_tree": "existing-tree", "tree": [{"path": "published/current", "mode": "040000", "type": "tree", "sha": "export-tree"}]}
    update = next(body for method, path, body in calls if method == "PATCH")
    assert update == {"sha": "approved-commit", "force": False}


async def test_public_repository_is_refused_before_any_write(memory, monkeypatch):
    from agents.publish import push_and_wait
    store, _, revision = memory
    monkeypatch.setenv("PUBLISH_GITHUB_REPOSITORY", "example/public-book")
    monkeypatch.setenv("PUBLISH_GITHUB_TOKEN", "test-only-token")
    calls = []
    def route(request):
        calls.append(request.method)
        return httpx.Response(200, json={"private": False})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(route)))
    with pytest.raises(ValueError, match="private GitHub"):
        await push_and_wait({"index.html": b"approved book"}, revision, store)
    assert calls == ["GET"]
