"""A travel photo attached to an editing request is still source evidence."""
import io
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest

from agents.models import replay
from agents.artifacts import pdf_html
from agents.worker import Worker
from app.models import Album, validate_evidence
from app.store import Store


@pytest.mark.parametrize("message,caption,basis", [
    ("@mw-collector Please add this photo to the album as well.", "", "posted"),
    ("@mw-collector \u3053\u306e\u5199\u771f\u3082\u30a2\u30eb\u30d0\u30e0\u306b\u8ffd\u52a0\u3057\u3066", "", "posted"),
    ("Please add this photo to the album as well.", "", "posted"),
    ("@mw-collector \u3053\u306e\u5199\u771f\u3082\u8ffd\u52a0\u3057\u3066\n\u6d77\u304c\u3059\u3054\u304f\u7dba\u9e97\u3060\u3063\u305f。", "\u6d77\u304c\u3059\u3054\u304f\u7dba\u9e97\u3060\u3063\u305f。", "posted"),
    ("@mw-collector \u3053\u306e\u5199\u771f\u3082\u8ffd\u52a0\u3057\u3066\n[2026-10-13T10:00:00+09:00] \u30a2\u30eb\u30d0\u30e0\u306b\u6b8b\u3057\u305f\u3044\u9752\u3044\u6d77。", "\u30a2\u30eb\u30d0\u30e0\u306b\u6b8b\u3057\u305f\u3044\u9752\u3044\u6d77。", "captured"),
    ("@mw-collector Please add this photo\nWe paddled together.", "We paddled together.", "posted"),
    ("@mw-collector Please add this photo\n[Location: Story Bridge, Brisbane | -27.463,153.035]\nWe stopped here.", "We stopped here.", "posted"),
])
async def test_attached_request_reaches_evidence_and_book(tmp_path, monkeypatch, message, caption, basis):
    from app import main
    store = Store(tmp_path)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setenv("WEB_URL", "http://local-web")
    monkeypatch.setenv("WEB_INTERNAL_TOKEN", "test-internal-key")
    image = io.BytesIO()
    Image.new("RGB", (64, 48), "skyblue").save(image, format="WEBP")
    entry = dict(id="real-human-request", kind="message", sender_kind="user", sender_name="traveler",
                 timestamp=1793829170120, body=message,
                 attachments=[dict(mimetype="image/webp", mxc="switch-media://original", size=len(image.getvalue()))])
    documents, handoffs, downloaded = [], [], []

    async def history():
        return [entry]

    async def download(mxc):
        downloaded.append(mxc)
        return image.getvalue()

    async def document(name, payload):
        documents.append(payload)
        return "switch-evidence-document"

    async def handoff(role, document_id, job, thread):
        handoffs.append((role, document_id, job, thread))

    async def say(*args):
        pass

    worker = Worker.__new__(Worker)
    worker.role, worker.mode, worker.store = "collector", "replay", store
    worker.client = SimpleNamespace(history=history, download=download, document=document, handoff=handoff, say=say)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.ASGITransport(app=main.app)))
    await worker.handle(entry)
    assert len(documents) == len(handoffs) == 1
    assert handoffs[0][0:2] == ("storyteller", "switch-evidence-document")
    source = documents[0]["sources"][0]
    assert source["id"] == entry["id"]
    assert source["text"] == caption
    assert source["date_basis"] == basis
    if "Story Bridge" in message:assert source["location"]["name"]=="Story Bridge, Brisbane"
    assert len(source["asset_ids"]) == 1
    asset_id = source["asset_ids"][0]
    assert not store.all("assets")[0]["sample"]
    sanitized = Image.open(store.root / "media" / (asset_id + ".jpg"))
    assert sanitized.format == "JPEG" and not sanitized.getexif()
    album = Album.model_validate(replay(documents[0]))
    validate_evidence(album, [source], {asset_id})
    assert album.chapters[0].asset_ids == [asset_id]
    assert album.chapters[0].quote == caption
    assert message.splitlines()[0] not in album.chapters[0].body
    if basis == "posted":
        assert "posting date" in album.chapters[0].body
        assert "Capture dates unconfirmed" in album.date_label
    else:
        assert source["captured_at"].startswith("2026-10-13")
        assert album.date_label == "2026-10-13 — 2026-10-13"
    await worker.collect([entry])
    await worker.handle(entry)
    assert downloaded == ["switch-media://original"]
    assert len(store.all("sources")) == len(store.all("assets")) == 1
    assert len(handoffs) == 1


async def test_plain_requests_are_excluded_but_dated_memories_remain(tmp_path):
    worker = Worker.__new__(Worker)
    worker.store = Store(tmp_path)
    def entry(id, body, sender_kind="user", attachments=None):
        return dict(id=id, kind="message", sender_kind=sender_kind, sender_name="traveler", timestamp=1793829170120, body=body, attachments=attachments or [])
    await worker.collect([
        entry("instruction", "@mw-collector Please add this photo to the album"),
        entry("retry", "@mw-publisher PDF\u3092\u518d\u9001\u3057\u3066 v9"),
        entry("approval", "PUBLISH v9 digest I CONSENT TO PUBLIC PHOTOS AND TEXT"),
        entry("dated", "[2026-10-13T10:30:00+09:00] \u30a2\u30eb\u30d0\u30e0\u306b\u6b8b\u3057\u305f\u3044\u9752\u3044\u6d77。"),
        entry("bot", "Photo attached", "agent", [dict(mimetype="image/webp", mxc="must-not-download")]),
    ])
    sources = worker.store.all("sources")
    assert len(sources) == 1
    assert sources[0]["id"] == "dated"
    assert sources[0]["date_basis"] == "captured"
    assert sources[0]["text"] == "\u30a2\u30eb\u30d0\u30e0\u306b\u6b8b\u3057\u305f\u3044\u9752\u3044\u6d77。"


def test_captionless_upload_does_not_invent_a_new_travel_day():
    sources = [
        dict(id="captured", author="traveler", text="\u6d77\u304c\u7dba\u9e97\u3060\u3063\u305f。", captured_at="2026-10-13T10:00:00+09:00", date_basis="captured", asset_ids=["kyoto-gates"]),
        dict(id="uploaded", author="traveler", text="", captured_at="2026-11-04T21:52:50+00:00", date_basis="posted", asset_ids=["uploaded-photo"]),
    ]
    album = replay(dict(sources=sources, job={"request": "\u3053\u306e\u5199\u771f\u3082\u8ffd\u52a0\u3057\u3066"}, previous=None))
    assert album["date_label"] == "2026-10-13 — 2026-10-13"
    assert album["chapters"][-1]["title"] == "A moment to keep"
    assert album["chapters"][-1]["quote"] == ""
    assert album["chapters"][-1]["asset_ids"] == ["uploaded-photo"]
    validate_evidence(Album.model_validate(album), sources, {"kyoto-gates", "uploaded-photo"})
    document = pdf_html(dict(version=1, album=album, sources=sources, mode="replay"), {a:dict(credit="Private upload", label="Photograph", sample=False) for a in ["kyoto-gates", "uploaded-photo"]})
    assert "PHOTO NOTE · POSTED · 2026-11-04" in document
    assert "DAY 02" not in document
