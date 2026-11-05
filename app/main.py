from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import time

import httpx
from PIL import Image, ImageOps
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from app.store import Store

STATIC = Path(__file__).parent / "static"
store = Store()


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title="MemoryWeaver", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.middleware("http")
async def security(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = os.getenv("WEB_INTERNAL_TOKEN", "")
        if not token or not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            return JSONResponse({"detail": "Changes are accepted only from the local agent service. Use Mattermost."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/state")
def state():
    revision = store.revision()
    return {
        "revision": revision,
        "sources": sorted(store.all("sources"), key=lambda s: s["captured_at"]),
        "assets": store.all("assets"),
        "events": store.events(),
        "agents": [{"role": r, **store.get("health:" + r, {"status": "waiting", "at": 0})} for r in ["collector", "storyteller", "editor", "publisher"]],
        "mode": "live" if store.get("console") else os.getenv("AI_MODE", "replay"),
        "runtime": "console" if store.get("console") else "docker",
        "mattermost_url": "http://localhost:8065/memoryweaver/channels/okinawa-memories",
        "publishing_enabled": os.getenv("PUBLISH_ENABLED") == "true",
        "publication": store.get("publication"),
    }


@app.post("/internal/console")
async def configure_console(request: Request):
    from agents.console import Binding
    from pydantic import ValidationError
    try:
        binding = Binding.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, "Expected Storyteller and Editor IDs and names") from exc
    if binding.storyteller.id == binding.editor.id or binding.storyteller.name == binding.editor.name:
        raise HTTPException(422, "Storyteller and Editor must be separate agents")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM jobs WHERE state='working'").fetchone():
            raise HTTPException(409, "Wait for the current job before changing the runtime")
        db.execute("UPDATE jobs SET state='superseded' WHERE state='clarification'")
        db.execute("INSERT OR REPLACE INTO kv VALUES ('console',?)", (json.dumps(binding.model_dump()),))
    return {"runtime": "console", "agents": binding.model_dump()}


@app.get("/api/revisions")
def revisions():
    with store.connect() as db:
        return [dict(r) for r in db.execute("SELECT id,created FROM revisions ORDER BY id DESC")]


@app.get("/api/revisions/{version}")
def revision(version: int):
    value = store.revision(version)
    if not value:
        raise HTTPException(404)
    return value


@app.get("/api/revisions/{version}/publication")
def publication(version: int):
    from agents.publish import approval_command, publication_digest, selected_assets
    value = store.revision(version)
    if not value:
        raise HTTPException(404)
    return {"command": approval_command(value), "digest": publication_digest(value), "asset_ids": selected_assets(value)}


@app.get("/api/revisions/{version}/pdf")
def download_pdf(version: int):
    from agents.artifacts import artifact_paths
    if version < 1 or not store.revision(version):
        raise HTTPException(404)
    pdf, _, _ = artifact_paths(store, version)
    if not pdf.is_file():
        raise HTTPException(409, "This version's PDF is not ready. Ask @mw-publisher PDFを再送して v" + str(version) + " in Mattermost.")
    return FileResponse(pdf, media_type="application/pdf", filename=pdf.name)


@app.get("/api/events")
async def events(request: Request):
    async def stream():
        last = ""
        while not await request.is_disconnected():
            current = json.dumps(state(), ensure_ascii=False)
            if current != last:
                yield "data: " + current + "\n\n"
                last = current
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/internal/media")
async def media(file: UploadFile = File(...)):
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Image exceeds 20 MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Image too large")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2200, 2200))
            asset_id = secrets.token_hex(12)
            image.save(store.root / "media" / (asset_id + ".jpg"), quality=88)
    except Exception:
        raise HTTPException(400, "Unsupported or damaged image")
    result = {"id": asset_id, "url": "/media/" + asset_id + ".jpg", "label": "Mattermost photograph", "sample": False, "credit": "Private user upload; permission required for publication."}
    store.put("assets", result)
    return result


@app.get("/media/{filename}")
def image(filename: str):
    if not filename.endswith(".jpg") or not all(c in "0123456789abcdef" for c in filename[:-4]):
        raise HTTPException(404)
    path = store.root / "media" / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
