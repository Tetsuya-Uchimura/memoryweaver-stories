import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path

import httpx
from pypdf import PdfReader
import pytest

from agents.artifacts import album_url, artifact_paths, pdf_html, private_fetcher, render_artifacts
from agents.delivery import DeliveryManager, completion_caption
from agents.models import replay
from agents.switch import Switch
from app.store import Store


@pytest.fixture
def completed(tmp_path):
    store = Store(tmp_path)
    for asset in json.loads(Path("tests/fixtures/assets.json").read_text()):
        store.put("assets", asset)
    sources = [dict(id=p["key"], author=p["author"], text=p["text"], captured_at=p["at"], asset_ids=[p["asset"]] if p["asset"] else []) for p in json.loads(Path("tests/fixtures/posts.json").read_text())]
    job = store.job("Create an English travel journal", "sample-request")
    album = replay(dict(job=job, sources=sources, previous=None))
    store.commit(album, job["id"], "replay", sources)
    return store, store.revision()


def test_pdf_is_a_readable_english_book_and_excludes_unused_sources(completed):
    store, revision = completed
    store.put("sources", {"id": "unused-private", "text": "SECRET-UNUSED-MEMORY", "author": "do-not-export", "captured_at": "2026-01-01", "asset_ids": []})
    pdf, cover, metadata = render_artifacts(store, revision)
    reader = PdfReader(pdf)
    assert len(reader.pages) >= 5  # cover, three chapters and credits
    text = "".join("".join(p.extract_text().split()) for p in reader.pages)
    assert "Smallmoments,lastingplaces" in text
    assert "bamboogrovefeltlikeadifferentsideofKyoto" in text
    assert "SECRET-UNUSED-MEMORY" not in text
    assert "do-not-export" not in text
    assert reader.metadata.author == "MemoryWeaver"
    assert cover.read_bytes() == Path("app/static/assets/kyoto-gates.jpg").read_bytes()
    stamp = pdf.stat().st_mtime_ns
    assert render_artifacts(store, revision)[2] == metadata
    assert pdf.stat().st_mtime_ns == stamp
    assert store.get("publication") is None
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0


def test_pdf_blocks_external_resources_and_escapes_untrusted_text(completed):
    store, revision = completed
    fetch = private_fetcher({"kyoto-gates": b"safe-image"})
    assert fetch("https://memoryweaver.invalid/photos/kyoto-gates.jpg")["string"] == b"safe-image"
    for url in ["file:///etc/passwd", "http://169.254.169.254/", "https://example.com/tracker", "data:text/html,secret"]:
        with pytest.raises(ValueError, match="allowlist"):
            fetch(url)
    revision["album"]["title"] = '<img src="file:///etc/passwd">'
    document = pdf_html(revision, {a["id"]: a for a in store.all("assets")})
    assert '<img src="file:///etc/passwd">' not in document
    assert '&lt;img src=' in document


def test_committed_revision_has_durable_delivery_intent(completed):
    store, revision = completed
    assert store.delivery(revision["version"])["state"] == "pending"
    assert store.revision_for_job("sample-request")["version"] == revision["version"]
    with pytest.raises(ValueError):
        store.queue_delivery(999)


class FakeSwitch:
    def __init__(self):
        self.connected = asyncio.Event()
        self.connected.set()
        self.posts = []
        self.messages = []
        self.history_entries = []
        self.fail = False

    async def history(self):
        return self.history_entries

    async def say(self, body):
        self.messages.append(body)

    async def upload(self, attachments, caption):
        if self.fail:
            raise httpx.WriteError("A failed transport must not discard a saved book")
        self.posts.append((attachments, caption))
        return {"ok": True, "event_id": "switch-receipt", "attachments": [{"filename": a[0]} for a in attachments]}


async def test_delivery_retries_without_a_new_revision_and_is_idempotent(completed):
    store, revision = completed
    client = FakeSwitch()
    manager = DeliveryManager(store, client)
    client.fail = True
    await manager.process(1)
    assert store.delivery(1)["state"] == "retrying"
    assert store.revision()["version"] == 1
    assert "Retrying" in client.messages[0]
    client.fail = False
    await manager.process(1)
    await manager.process(1)
    assert len(client.posts) == 1
    attachments, caption = client.posts[0]
    assert {a[2] for a in attachments} == {"application/pdf", "image/jpeg"}
    assert next(a[1] for a in attachments if a[2] == "application/pdf").startswith(b"%PDF-")
    assert "http://localhost:8787/?version=1" in caption
    assert revision["album"]["title"] in caption
    assert store.delivery(1)["state"] == "sent"
    assert store.delivery(1)["attempts"] == 2


async def test_restart_recovers_an_accepted_group_and_ignores_human_spoof(completed):
    store, revision = completed
    client = FakeSwitch()
    body = completion_caption(revision)
    attachments = [{"filename": "MemoryWeaver-v1.pdf"}, {"filename": "MemoryWeaver-cover-v1.jpg"}]
    client.history_entries = [{"id": "spoof", "sender_kind": "user", "sender_name": "mw-publisher", "body": body, "attachments": attachments}]
    manager = DeliveryManager(store, client)
    assert await manager.existing_receipt(revision) is None
    client.history_entries.append({"id": "real-group", "sender_kind": "agent", "sender_name": "mw-publisher", "body": body, "attachments": attachments})
    store.delivery_update(1, "sending", 1)
    manager = DeliveryManager(store, client)
    assert store.delivery(1)["state"] == "pending"
    await manager.process(1)
    assert not client.posts
    assert store.delivery(1)["state"] == "sent"
    assert store.delivery(1)["receipt"]["event_id"] == "real-group"


async def test_official_switch_multipart_upload_uses_agent_key():
    captured = []
    def route(request):
        captured.append(request)
        assert request.url.path == "/agents/publisher/rooms/private-room/media"
        assert request.headers["authorization"] == "Bearer agent-test-key"
        assert request.content.count(b'name="files"') == 2
        assert b"application/pdf" in request.content and b"image/jpeg" in request.content
        assert b'name="caption"' in request.content
        assert b'name="thread_id"' not in request.content  # completion is visible in the channel
        return httpx.Response(200, json={"ok": True, "attachments": [{"filename": "cover.jpg"}, {"filename": "book.pdf"}], "event_id": "accepted"})
    client = Switch({"id": "publisher", "api_key": "agent-test-key"}, "private-room")
    await client.http.aclose()
    client.http = httpx.AsyncClient(base_url="http://switch:8000", headers={"Authorization": "Bearer agent-test-key"}, transport=httpx.MockTransport(route))
    try:
        await client.upload([("cover.jpg", b"jpeg", "image/jpeg"), ("book.pdf", b"%PDF-", "application/pdf")], "Book ready")
    finally:
        await client.http.aclose()
    assert len(captured) == 1


async def test_pdf_download_stays_private_and_is_version_specific(completed, monkeypatch):
    from app import main
    store, revision = completed
    monkeypatch.setattr(main, "store", store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as http:
        assert (await http.get("/api/revisions/1/pdf")).status_code == 409
        render_artifacts(store, revision)
        response = await http.get("/api/revisions/1/pdf")
        assert response.headers["content-type"] == "application/pdf"
        assert 'attachment;' in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF-")
        assert response.headers["cache-control"] == "no-store"
        assert (await http.get("/api/revisions/999/pdf")).status_code == 404


def test_browser_base_url_is_configurable_and_cannot_contain_credentials(monkeypatch):
    monkeypatch.setenv("ALBUM_BASE_URL", "https://studio.example.test/trips/")
    assert album_url(7) == "https://studio.example.test/trips/?version=7"
    for value in ["http://user:secret@studio.test", "file:///data", "https://studio.test?token=private", "https://studio.test/#secret"]:
        monkeypatch.setenv("ALBUM_BASE_URL", value)
        with pytest.raises(ValueError):
            album_url(7)


async def test_a_rejected_concurrent_request_does_not_cancel_current_job(completed):
    from agents.worker import Worker
    store, _ = completed
    current = store.job("current edit", "active-request")
    worker = Worker.__new__(Worker)
    worker.role = "collector"
    worker.store = store
    async def handle(entry):
        store.job("second edit", entry["id"])
    async def report(*args):
        pass
    worker.handle = handle
    worker.report = report
    await worker.handle_safely({"id": "second-request", "body": "edit", "sender_kind": "user"})
    with store.connect() as db:
        assert db.execute("SELECT state FROM jobs WHERE id=?", (current["id"],)).fetchone()[0] == "working"


def test_delivered_edition_keeps_its_pdf_when_location_template_changes(completed,monkeypatch):
    from agents import artifacts
    store,revision=completed
    pdf,cover,manifest=render_artifacts(store,revision)
    original_pdf,original_cover=pdf.read_bytes(),cover.read_bytes()
    store.delivery_update(revision['version'],'sent',1,receipt=manifest)
    monkeypatch.setattr(artifacts,'TEMPLATE_VERSION','future-location-template')
    upgraded={**revision,'trip_id':'preserved-legacy-room'}
    got_pdf,got_cover,got_manifest=render_artifacts(store,upgraded)
    assert got_pdf.read_bytes()==original_pdf and got_cover.read_bytes()==original_cover
    assert got_manifest==manifest
