"""Private, version-bound travel-book artifacts. Never invokes cloud publication."""
from __future__ import annotations

import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile

from agents.publish import publication_digest, selected_assets

TEMPLATE_VERSION = "private-pdf-v5-coastal-english"


def album_base_url():
    from urllib.parse import urlsplit
    value = os.getenv("ALBUM_BASE_URL", "http://localhost:8787").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in value):
        raise ValueError("ALBUM_BASE_URL must be a browser-accessible HTTP(S) base URL without credentials, query or fragment")
    return value


def album_url(version,trip=None):
    from urllib.parse import urlencode
    return album_base_url()+"/?"+urlencode({**({"trip":trip} if trip else {}),"version":int(version)})


def artifact_paths(store, version):
    root = store.root / "books" / ("v" + str(int(version)))
    return root / "MemoryWeaver-v{}.pdf".format(int(version)), root / "MemoryWeaver-cover-v{}.jpg".format(int(version)), root / "artifact.json"


def read_photographs(store, revision):
    assets = {item["id"]: item for item in store.all("assets")}
    photos = {}
    for asset_id in selected_assets(revision):
        item = assets.get(asset_id)
        if not item:
            raise ValueError("A selected photograph is unavailable")
        if item.get("sample") and re.fullmatch(r"[a-z-]+", asset_id):
            path = Path(__file__).resolve().parents[1] / "app/static/assets" / (asset_id + ".jpg")
        elif not item.get("sample") and re.fullmatch(r"[a-f0-9]{24}", asset_id):
            path = store.root / "media" / (asset_id + ".jpg")
        else:
            raise ValueError("Invalid photograph reference")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != revision.get("asset_hashes", {}).get(asset_id):
            raise ValueError("A photograph changed after this version was saved. Generate a new book before delivery.")
        photos[asset_id] = data
    return photos, assets


def private_fetcher(photos):
    """WeasyPrint can fetch only the exact in-memory images in this version.

    Never delegate to its default fetcher: no HTTP, file://, data:, CSS imports,
    local secrets, or references provided by a user/model can be read here.
    """
    allowed = {"https://memoryweaver.invalid/photos/" + asset_id + ".jpg": data for asset_id, data in photos.items()}
    def fetch(url, *args, **kwargs):
        if url not in allowed:
            raise ValueError("PDF resource is outside the selected photograph allowlist")
        return {"string": allowed[url], "mime_type": "image/jpeg"}
    return fetch


def pdf_html(revision, assets):
    album = revision["album"]
    version = revision["version"]
    image = lambda asset_id: "https://memoryweaver.invalid/photos/" + asset_id + ".jpg"
    from app.design import DESIGNS
    design = album.get("design") if album.get("design") in DESIGNS else "classic"
    columns = 3 if design == "urban" else 2
    chapters = []
    from app.locations import map_url
    photo_places=revision.get("photo_locations",{})
    sources = {s["id"]: s for s in revision["sources"]}
    for chapter in album["chapters"]:
        figures = []
        for start in range(0, len(chapter["asset_ids"]), columns):
            cells = ''.join('<td><img alt="Travel photograph" src="' + image(asset_id) + '"><p class="credit">' + escape(assets[asset_id]["credit"])+("<br>Location: "+escape(photo_places[asset_id]["name"])+" · "+escape(photo_places[asset_id]["basis"])+" · <a href=\""+escape(map_url(photo_places[asset_id]),quote=True)+"\">Open map</a>" if asset_id in photo_places else "<br>Location not supplied") + '</p></td>' for asset_id in chapter["asset_ids"][start:start + columns])
            figures.append('<table class="photographs"><tr>' + cells + '</tr></table>')
        paragraphs = ''.join('<p class="prose">' + escape(paragraph) + '</p>' for paragraph in chapter["body"].split("\n\n"))
        quote = '<blockquote>“' + escape(chapter["quote"]) + '”</blockquote>' if chapter["quote"] else ''
        posted = all(sources[sid].get("date_basis") == "posted" for sid in chapter["source_ids"])
        date_label = "PHOTO NOTE · POSTED" if posted else f'DAY {chapter["day"]:02}'
        chapters.append(f'<section class="chapter"><div class="eyebrow">{date_label} · {escape(chapter["date"])}</div><h2>{escape(chapter["title"])}</h2>{"".join(figures)}{paragraphs}{quote}</section>')
    credits = []
    for asset_id in selected_assets(revision):
        item = assets[asset_id]
        links = ""
        if item.get("sample"):
            links = f'<br><a href="{escape(item["source_url"], quote=True)}">Original photograph</a> · <a href="{escape(item["license_url"], quote=True)}">License</a>'
        credits.append('<p><strong>' + escape(item["label"]) + '</strong><br>' + escape(item["credit"]) + links + '</p>')
    sample_note = "Licensed photographs illustrate fictional sample memories." if all(assets[a].get("sample") for a in selected_assets(revision)) else "A private copy of your travel book."
    unique={(p["name"],p.get("latitude"),p.get("longitude"),p["basis"]):p for p in revision.get("places",[])}
    journey='<section class="chapter"><div class="eyebrow">PLACES WE REMEMBER</div><h2>Our journey</h2>'+''.join('<p><a href="'+escape(map_url(p),quote=True)+'">'+escape(p['name'])+'</a> · '+escape(p['basis'])+(' · '+str(p['latitude'])+', '+str(p['longitude']) if p.get('latitude') is not None else '')+'</p>' for p in unique.values())+'<p class="note">Sample pins are approximate fictional landmarks, not actual camera positions. Map links open only when selected.</p></section>' if unique else ''
    title_size = 32 if len(album["title"]) < 25 else 23 if len(album["title"]) < 55 else 18
    css = f"""
    @page {{size:A4;margin:20mm 19mm 22mm;@bottom-left {{content:'MemoryWeaver · v{version}';font:8pt sans-serif;color:#89927d}}@bottom-right {{content:counter(page);font:8pt sans-serif;color:#89927d}}}}
    @page cover {{margin:0;@bottom-left {{content:none}}@bottom-right {{content:none}}}}
    * {{box-sizing:border-box}} body {{margin:0;color:#294339;font-family:'Noto Serif CJK JP','Hiragino Mincho ProN',serif;font-size:10.5pt;line-height:1.95}}
    .cover {{page:cover;position:relative;width:210mm;height:297mm;overflow:hidden;background:#24483d;break-after:page;color:#fff}}
    .cover img {{position:absolute;top:0;left:0;width:210mm;height:297mm;object-fit:cover}}
    .shade {{position:absolute;top:0;left:0;width:210mm;height:297mm;background:linear-gradient(to bottom,transparent 10%,#102d26e6 100%)}}
    .cover-top {{position:absolute;top:20mm;left:20mm;right:20mm;font-family:sans-serif;font-size:8pt;letter-spacing:2pt}}
    .cover-copy {{position:absolute;left:20mm;right:20mm;bottom:25mm}} .cover h1 {{font-size:{title_size}pt;font-weight:400;line-height:1.65;margin:8mm 0;overflow-wrap:anywhere}}
    .cover .subtitle {{font-size:11pt;white-space:pre-wrap}} .cover .dates {{font:8pt sans-serif;letter-spacing:1pt;border-top:1px solid #ffffff77;margin-top:12mm;padding-top:5mm}}
    .eyebrow {{font:8pt sans-serif;letter-spacing:1.5pt;color:#81906e}} .cover .eyebrow {{color:#e1eac7}}
    .chapter {{break-before:page}} h2 {{font-size:21pt;font-weight:400;line-height:1.55;margin:6mm 0 9mm;break-after:avoid;overflow-wrap:anywhere}}
    .prose {{white-space:pre-wrap;overflow-wrap:anywhere;orphans:3;widows:3;margin:6mm 0}}
    .photographs {{table-layout:fixed;width:100%;border-collapse:collapse;margin:0 0 5mm;break-inside:avoid}} td {{padding:0 2mm;vertical-align:top}} td:first-child {{padding-left:0}} td:last-child {{padding-right:0}}
    td img {{width:100%;height:76mm;object-fit:cover}} .credit {{font:7pt/1.6 sans-serif;color:#7f8e75;margin:2mm 0 0;overflow-wrap:anywhere}}
    blockquote {{border-left:2px solid #bfcc9e;margin:9mm 0;padding:2mm 0 2mm 6mm;color:#638150;font-size:12pt;white-space:pre-wrap;overflow-wrap:anywhere}}
    .colophon {{break-before:page;font-size:9pt}} .colophon p {{margin:7mm 0;overflow-wrap:anywhere}} a {{color:#4a704e}} .note {{font:8pt/1.9 sans-serif;color:#87927b}}
    """
    # Local allowlisted recipes only: no untrusted style interpolation.
    css += {
        "classic": "",
        "quiet": """
        body{color:#303b35}.cover{background:#f5f0e5;color:#303b35}
        .cover img{left:100mm;width:110mm;height:297mm}.shade{display:none}
        .cover-top{right:120mm;color:#a74332;line-height:2}
        .cover-copy{left:14mm;right:121mm;bottom:32mm}.cover h1{font-size:29pt;line-height:1.35}
        .cover .eyebrow{color:#a74332}.cover .subtitle{font-size:10pt}
        .cover .dates{border-color:#c6bba5;font-size:7pt;line-height:1.9}
        .eyebrow{color:#a74332}h2{color:#303b35}blockquote{border-color:#a74332;color:#81513b}
        td img{object-fit:contain;height:90mm}.credit{color:#696e60}a{color:#87553e}
        """,
        "editorial": """
        body{color:#3b2931}.cover{background:#fffaf3;color:#3b2931}
        .cover img{left:14mm;top:115mm;width:182mm;height:162mm;object-fit:contain}
        .shade{display:none}.cover-top{color:#8d344a;border-bottom:1px solid #bc9aa4;padding-bottom:4mm}
        .cover-copy{top:42mm;left:18mm;right:18mm;bottom:auto;text-align:center}
        .cover h1{font-family:Georgia,serif;font-style:italic;font-size:34pt;line-height:1.15;margin:4mm 0}
        .cover .eyebrow{color:#8d344a}.cover .subtitle{font-size:10pt;margin:5mm 0}
        .cover .dates{border:0;margin:4mm 0;padding:0;color:#8d344a;font-size:7pt}
        .eyebrow{color:#8d344a}h2{color:#78374b;font-style:italic}
        blockquote{color:#8d344a;border-color:#bc8e99}td img{object-fit:contain;height:86mm}
        .credit{color:#79616a}a{color:#8d344a}
        """,
        "coastal": """
        body{color:#174b61}.cover{background:#eef9fb;color:#174b61}
        .cover img{top:0;left:0;width:210mm;height:180mm;object-fit:cover}.shade{display:none}
        .cover-top{color:#fff;text-shadow:0 1px 3px #174b61;top:14mm}
        .cover-copy{top:193mm;left:18mm;right:18mm;bottom:auto;text-align:center}
        .cover h1{font-family:Georgia,serif;font-size:31pt;font-weight:400;line-height:1.2;margin:4mm 0}
        .cover .eyebrow{color:#117b98}.cover .subtitle{font-size:10pt;line-height:1.6}
        .cover .dates{color:#117b98;border-color:#b1dce6;margin-top:6mm;font-size:7pt;padding-top:4mm}
        .eyebrow{color:#117b98}h2{color:#117b98}blockquote{color:#287a91;border-color:#e0b98b}
        td img{object-fit:contain;height:85mm}.credit{color:#597b87}a{color:#117b98}
        """,
        "urban": """
        body{font-family:'Noto Sans CJK JP','Helvetica Neue',sans-serif;color:#1c2631;line-height:1.8}
        .cover{background:#182330}.cover img{top:150mm;height:147mm;object-fit:cover}.shade{display:none}
        .cover-copy{top:43mm;bottom:auto;left:16mm;right:16mm}
        .cover h1{font-family:sans-serif;font-size:38pt;font-weight:800;text-transform:uppercase;line-height:1.05;margin:7mm 0}
        .cover .eyebrow{color:#f5cb43}.cover .subtitle{font-size:10pt;line-height:1.6}
        .cover .dates{font-size:7pt;margin-top:7mm}.eyebrow{color:#254cc4;font-weight:bold}
        h2{font-family:sans-serif;font-weight:800;color:#254cc4;line-height:1.2}
        td img{height:65mm;object-fit:contain}blockquote{font-family:sans-serif;font-weight:bold;color:#254cc4;border-color:#e5b821}
        .credit{color:#586775}a{color:#254cc4}
        """,
    }[design]
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="author" content="MemoryWeaver"><title>{escape(album["title"])} · v{version}</title><style>{css}</style></head><body data-design="{design}"><section class="cover"><img alt="Cover photograph" src="{image(album["cover_asset_id"])}"><div class="shade"></div><div class="cover-top">A MEMORYWEAVER TRAVEL JOURNAL</div><div class="cover-copy"><div class="eyebrow">{escape(album["location"])}</div><h1>{escape(album["title"])}</h1><p class="subtitle">{escape(album["subtitle"])}</p><div class="dates">{escape(album["date_label"])} · VERSION {version} · {escape(revision["mode"].upper())}</div></div></section>{journey}{"".join(chapters)}<section class="colophon"><div class="eyebrow">THE PEOPLE BEHIND THE PICTURES</div><h2>Stories worth keeping.</h2>{"".join(credits)}<p class="note">{sample_note}<br>{escape(revision["mode"].upper())} edition · Version {version}. Generated for your private Mattermost room. Cloud publication requires separate explicit approval.</p></section></body></html>'


def _atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".artifact-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def render_artifacts(store, revision):
    """Return PDF and cover paths. All heavy rendering runs off the async loop."""
    pdf, cover, manifest_path = artifact_paths(store, revision["version"])
    fingerprint = publication_digest(revision) + ":" + TEMPLATE_VERSION
    if pdf.is_file() and cover.is_file() and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        valid_bytes = hashlib.sha256(pdf.read_bytes()).hexdigest() == manifest.get("pdf_sha256") and hashlib.sha256(cover.read_bytes()).hexdigest() == manifest.get("cover_sha256")
        delivery = store.delivery(revision["version"]) or {}
        receipt = delivery.get("receipt") or {}
        delivered_bytes = receipt.get("pdf_sha256") == manifest.get("pdf_sha256") and receipt.get("cover_sha256") == manifest.get("cover_sha256") and manifest.get("cover_sha256") == revision.get("asset_hashes", {}).get(revision["album"]["cover_asset_id"])
        # A location/template upgrade must not rewrite a PDF already received
        # in Mattermost. Improvements belong to a newly generated edition.
        if valid_bytes and (manifest.get("fingerprint") == fingerprint or delivered_bytes):
            return pdf, cover, manifest
    photos, assets = read_photographs(store, revision)
    from weasyprint import HTML
    contents = HTML(string=pdf_html(revision, assets), url_fetcher=private_fetcher(photos)).write_pdf(optimize_images=True, jpeg_quality=85, dpi=160)
    if not contents.startswith(b"%PDF-") or len(contents) > 20 * 1024 * 1024:
        raise ValueError("Travel-book PDF is invalid or exceeds 20 MB; reduce the selected photographs and retry")
    cover_bytes = photos[revision["album"]["cover_asset_id"]]
    manifest = {"version": revision["version"], "fingerprint": fingerprint, "pdf_sha256": hashlib.sha256(contents).hexdigest(), "cover_sha256": hashlib.sha256(cover_bytes).hexdigest()}
    _atomic_write(pdf, contents)
    _atomic_write(cover, cover_bytes)
    _atomic_write(manifest_path, json.dumps(manifest).encode())
    return pdf, cover, manifest
