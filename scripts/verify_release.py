"""Validate the explicit export allowlist before Cloudflare receives anything."""
import hashlib
import json
from pathlib import Path
import re
import sys


def verify(root):
    root = Path(root)
    manifest = json.loads((root / "release.json").read_text())
    assert manifest["schema"] == 1
    assert manifest["consent"] == "I CONSENT TO PUBLIC PHOTOS AND TEXT"
    canonical = lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    expected = hashlib.sha256(canonical({"version": manifest["version"], "book": manifest["book"], "asset_ids": manifest["asset_ids"], "asset_hashes": manifest["asset_hashes"]})).hexdigest()
    assert expected == manifest["digest"], "Approval digest differs from the book"
    required = {"index.html", "style.css", "book.json", "_headers"}
    assert required.issubset(manifest["files"])
    assert json.loads((root / "book.json").read_text()) == manifest["book"]
    for asset_id in manifest["asset_ids"]:
        assert manifest["files"]["assets/" + asset_id + ".jpg"] == manifest["asset_hashes"][asset_id], "Photograph was not approved"
    names = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    assert names == set(manifest["files"]) | {"release.json"}, "Unreviewed file in export"
    map_runtime = {"journey-map.js", "journey-map.css", "vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "vendor/leaflet/LICENSE",
                   "vendor/leaflet/images/layers.png", "vendor/leaflet/images/layers-2x.png", "vendor/leaflet/images/marker-icon.png",
                   "vendor/leaflet/images/marker-icon-2x.png", "vendor/leaflet/images/marker-shadow.png"}
    for name, digest in manifest["files"].items():
        assert name in required | {"book-designs.css"} | map_runtime or re.fullmatch(r"assets/[a-z0-9-]+\.jpg", name), "File is not on the publication allowlist"
        path = root / name
        assert not path.is_symlink() and path.resolve().is_relative_to(root.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, "Export bytes changed after approval"
    print(f"Verified human-approved v{manifest['version']}: {len(names)} allowlisted files")


if __name__ == "__main__":
    verify(sys.argv[1] if len(sys.argv) > 1 else "published/current")
