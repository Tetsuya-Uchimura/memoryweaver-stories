from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import httpx

CONSENT = "I CONSENT TO PUBLIC PHOTOS AND TEXT"
MAP_FILES = (
    "journey-map.js", "journey-map.css", "vendor/leaflet/leaflet.js",
    "vendor/leaflet/leaflet.css", "vendor/leaflet/LICENSE",
    "vendor/leaflet/images/layers.png", "vendor/leaflet/images/layers-2x.png",
    "vendor/leaflet/images/marker-icon.png", "vendor/leaflet/images/marker-icon-2x.png",
    "vendor/leaflet/images/marker-shadow.png",
)


def public_book(revision):
    album = revision["album"]
    return {**album, **({"trip_id":revision["trip_id"]} if revision.get("trip_id") else {}), "places": [{k:v for k,v in p.items() if k!="source_id"} for p in revision.get("places",[])], "photo_locations":revision.get("photo_locations",{}), "chapters": [{k: v for k, v in c.items() if k not in {"source_ids", "quote_source_id"}} for c in album["chapters"]]}


def selected_assets(revision):
    return sorted(set([revision["album"]["cover_asset_id"], *[a for c in revision["album"]["chapters"] for a in c["asset_ids"]]]))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def publication_digest(revision):
    return hashlib.sha256(canonical({"version": revision["version"], "book": public_book(revision), "asset_ids": selected_assets(revision), "asset_hashes": revision.get("asset_hashes", {})})).hexdigest()


def approval_command(revision):
    return f"PUBLISH v{revision['version']} {publication_digest(revision)[:12]} {CONSENT}"


def build_export(store, revision, approval):
    """Explicit allowlist. Never copy the workspace, upload directory, or raw messages."""
    static = Path(__file__).resolve().parents[1] / "app/static"
    assets = {a["id"]: a for a in store.all("assets")}
    ids = selected_assets(revision)
    book = public_book(revision)
    files = {"book-designs.css": (static / "book-designs.css").read_bytes(), "style.css": (static / "style.css").read_bytes(), "book.json": canonical(book)}
    files.update({name: (static / name).read_bytes() for name in MAP_FILES})
    for asset_id in ids:
        asset = assets[asset_id]
        if asset.get("sample"):
            if not re.fullmatch(r"[a-z-]+", asset_id):
                raise ValueError("Invalid sample asset identifier")
            source = static / "assets" / (asset_id + ".jpg")
        else:
            if not re.fullmatch(r"[a-f0-9]{24}", asset_id):
                raise ValueError("Invalid private asset identifier")
            source = store.root / "media" / (asset_id + ".jpg")
        contents = source.read_bytes()
        if hashlib.sha256(contents).hexdigest() != revision.get("asset_hashes", {}).get(asset_id):
            raise ValueError("Photograph bytes differ from the reviewed version; regenerate and review a new preview")
        files["assets/" + asset_id + ".jpg"] = contents
    from app.design import DESIGNS
    design = book.get("design") if book.get("design") in DESIGNS else "classic"
    e = html.escape
    image = lambda aid: "assets/" + aid + ".jpg"
    from app.locations import map_url
    def place_key(p):
        return (p["name"], p.get("latitude"), p.get("longitude"), p["basis"])
    locations = list({place_key(p): p for p in [*book.get("places", []), *book.get("photo_locations", {}).values()]}.values())
    def map_button(p):
        if p.get("latitude") is None:
            return ""
        index = next(i for i, place in enumerate(locations) if place_key(place) == place_key(p))
        return f'<button type="button" class="show-on-map" data-show-map="{index}">Show on this map</button>'
    def photo_place(aid):
        p=book.get("photo_locations",{}).get(aid)
        return "<br>Location not supplied" if not p else "<br>Location: "+e(p["name"])+" · "+e(p["basis"])+map_button(p)+' · <a href="'+e(map_url(p))+'">Open map</a>'
    chapters = []
    for c in book["chapters"]:
        photos = ''.join(f'<figure><img src="{image(aid)}" alt="{e(assets[aid]["label"])}"><figcaption>{e(assets[aid]["credit"])}{photo_place(aid)}</figcaption></figure>' for aid in c["asset_ids"])
        chapters.append(f'<section class="chapter"><div class="chapter-heading"><span class="chapter-number">{c["day"]:02}</span><div><div class="chapter-date">{e(c["date"])}</div><h2>{e(c["title"])}</h2></div></div><div class="chapter-layout"><div class="chapter-images">{photos}</div><div class="chapter-prose"><p>{e(c["body"])}</p><blockquote>“{e(c["quote"])}”</blockquote></div></div></section>')
    credits = ''.join(f'<p>{e(assets[aid]["label"])} · {e(assets[aid]["credit"])}' + (f' · <a href="{e(assets[aid]["source_url"])}">Original</a> · <a href="{e(assets[aid]["license_url"])}">License</a>' if assets[aid].get("sample") else '') + '</p>' for aid in ids)
    places=""
    if locations:
        stops = [{"name": p["name"], "latitude": p.get("latitude"), "longitude": p.get("longitude"), "basis": p["basis"],
                  "photos": [{"url": image(aid), "label": assets[aid]["label"]} for aid in ids
                             if aid in book.get("photo_locations", {}) and place_key(book["photo_locations"][aid]) == place_key(p)]} for p in locations]
        widget = '<div class="journey-map" data-journey-map data-map-stops="' + e(json.dumps(stops, ensure_ascii=False), quote=True) + '"></div>'
        cards = ''.join(f'<article class="place-card" id="place-{i}"><span class="place-number">{i+1:02}</span><div><h3>{e(p["name"])}</h3><p>{e(p["basis"])}</p>'
                        + (f'<small>{p["latitude"]:.5f}, {p["longitude"]:.5f}</small>' if p.get("latitude") is not None else '')
                        + '</div>'+map_button(p)+'<a href="'+e(map_url(p))+'" target="_blank" rel="noopener noreferrer">Open map ↗</a></article>' for i,p in enumerate(locations))
        places='<section class="journey-places"><h2>Places we remember</h2>'+widget+'<div class="place-list">'+cards+'</div></section>'
    doc = f'''<!doctype html><html lang="{e(revision.get("language","ja"))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>{e(book["title"])} · MemoryWeaver</title><link rel="stylesheet" href="style.css"><link rel="stylesheet" href="book-designs.css"><link rel="stylesheet" href="vendor/leaflet/leaflet.css"><link rel="stylesheet" href="journey-map.css"><script src="vendor/leaflet/leaflet.js" defer></script><script src="journey-map.js" defer></script></head><body class="reading"><main><article class="book" data-design="{design}"><section class="cover"><img src="{image(book["cover_asset_id"])}" alt="Travel journal cover"><div class="cover-top">A MEMORYWEAVER TRAVEL JOURNAL · V{revision["version"]}</div><div class="cover-content"><div class="cover-location">{e(book["location"])}</div><h1 class="cover-title">{e(book["title"])}</h1><div class="cover-subtitle">{e(book["subtitle"])}</div><div class="cover-bottom">{e(book["date_label"])}</div></div></section>{places}{''.join(chapters)}<div class="book-end"><span class="weave">✳</span><p>Some journeys stay with us.</p><small>WOVEN TOGETHER WITH MEMORYWEAVER · {e(revision["mode"].upper())}</small></div></article><footer class="photo-credit">{credits}<p>Sample photographs illustrate a fictional trip. Published with explicit human approval.</p></footer></main></body></html>'''
    files["index.html"] = doc.encode()
    files["_headers"] = b"/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: default-src 'none'; img-src 'self' data: https://tile.openstreetmap.org; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'\n"
    manifest = {"schema": 1, "version": revision["version"], "digest": publication_digest(revision), "asset_ids": ids, "asset_hashes": revision["asset_hashes"], "book": book, "consent": CONSENT, "approved_at": approval["created"], "approver_hash": hashlib.sha256(approval["user_id"].encode()).hexdigest(), "files": {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}}
    files["release.json"] = canonical(manifest)
    destination = store.root / "exports" / ("v" + str(revision["version"]))
    for path, data in files.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return destination, files


async def push_and_wait(files, revision, store):
    repo = os.getenv("PUBLISH_GITHUB_REPOSITORY", "")
    branch = os.getenv("PUBLISH_GITHUB_BRANCH", "main")
    token = os.getenv("PUBLISH_GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token or not re.fullmatch(r"[A-Za-z0-9_.-]+", branch):
        raise ValueError("Configure a private publication repository, branch and scoped GitHub token")
    async with httpx.AsyncClient(base_url="https://api.github.com", headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, timeout=60) as http:
        async def api(method, path, **kwargs):
            response = await http.request(method, "/repos/" + repo + path, **kwargs)
            response.raise_for_status()
            return response.json()
        metadata = await api("GET", "")
        if not metadata["private"]:
            raise ValueError("Use a private GitHub repository to prevent accidental source/conversation exposure")
        head = await api("GET", "/git/ref/heads/" + branch)
        parent_sha = head["object"]["sha"]
        parent = await api("GET", "/git/commits/" + parent_sha)
        tree = []
        for path, data in files.items():
            blob = await api("POST", "/git/blobs", json={"content": base64.b64encode(data).decode(), "encoding": "base64"})
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        export_tree = await api("POST", "/git/trees", json={"tree": tree})
        updated = await api("POST", "/git/trees", json={"base_tree": parent["tree"]["sha"], "tree": [{"path": "published/current", "mode": "040000", "type": "tree", "sha": export_tree["sha"]}]})
        commit = await api("POST", "/git/commits", json={"message": "Publish human-approved MemoryWeaver v" + str(revision["version"]), "tree": updated["sha"], "parents": [parent_sha]})
        # Non-force update rejects concurrent branch changes; never overwrites another commit.
        await api("PATCH", "/git/refs/heads/" + branch, json={"sha": commit["sha"], "force": False})
        store.set("publication", {"version": revision["version"], "state": "building", "commit": commit["sha"], "url": None})
        for _ in range(120):
            result = await api("GET", "/commits/" + commit["sha"] + "/status")
            status = next((s for s in result["statuses"] if s["context"] == "memoryweaver/cloudflare"), None)
            if status and status["state"] == "success":
                url = status.get("target_url", "")
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".pages.dev"):
                    raise ValueError("Deployment status did not contain a Cloudflare Pages HTTPS URL")
                return url
            if status and status["state"] in {"failure", "error"}:
                raise ValueError("GitHub Actions reported a deployment failure; inspect the workflow run")
            await asyncio.sleep(5)
        raise ValueError("Deployment is still pending. Check GitHub Actions before retrying; retrying can create another commit and workflow.")


async def approve_and_publish(store, body, entry):
    revision = store.revision()
    if not revision or body.strip() != approval_command(revision):
        raise ValueError("Approval must match the latest version and its digest exactly. Copy the current command from Review publication.")
    digest = publication_digest(revision)
    approval = dict(user_id=entry["sender"], created=time.time())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT max(id) FROM revisions").fetchone()[0]
        if latest != revision["version"] or db.execute("SELECT 1 FROM jobs WHERE state='working'").fetchone():
            raise ValueError("An edit is in progress or a newer version exists. Review the finished preview before approving.")
        old = db.execute("SELECT * FROM approvals WHERE revision=?", (latest,)).fetchone()
        if old and old["state"] == "published":
            return "This approved version is already published: " + old["url"]
        if old and old["state"] == "publishing":
            raise ValueError("This version already has a publication in progress. Check GitHub Actions before retrying.")
        db.execute("INSERT OR REPLACE INTO approvals VALUES (?,?,?,?,?,'publishing',NULL)", (latest, digest, entry["sender"], entry["id"], approval["created"]))
    try:
        destination, files = build_export(store, revision, approval)
        if os.getenv("PUBLISH_ENABLED") != "true":
            with store.connect() as db:
                db.execute("UPDATE approvals SET state='local-export' WHERE revision=?", (revision["version"],))
            store.set("publication", {"version": revision["version"], "state": "local-export", "url": None})
            return f"Approved v{revision['version']}. Cloud publishing is disabled. A sanitized local export was created at {destination} (inside the MemoryWeaver data volume). No data was sent to GitHub or Cloudflare."
        url = await push_and_wait(files, revision, store)
    except Exception:
        with store.connect() as db:
            db.execute("UPDATE approvals SET state='failed' WHERE revision=?", (revision["version"],))
        raise
    with store.connect() as db:
        db.execute("UPDATE approvals SET state='published',url=? WHERE revision=?", (url, revision["version"]))
    store.set("publication", {"version": revision["version"], "state": "published", "url": url})
    return f"Your human-approved story v{revision['version']} is published: {url}"
