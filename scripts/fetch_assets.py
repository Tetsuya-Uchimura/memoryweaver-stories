"""Refresh licensed illustrative photos. Committed assets make judging offline-friendly."""
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import time
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ("coast", "Okinawa beach.jpg", "VKaeru", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/"),
    ("aquarium", "Main tank of the Kuroshio Sea in Okinawa Churaumi Aquarium.JPG", "そらみみ", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    ("soba", "Okinawa soba in Yamabare 2.jpg", "Syced", "CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ("sunset", "Okinawa sunset (52117078771).jpg", "Raita Futo", "CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"),
]


def main():
    credits = []
    for asset_id, name, author, license_name, license_url in FILES:
        filename = name.replace(" ", "_")
        digest = hashlib.md5(filename.encode()).hexdigest()
        url = "https://upload.wikimedia.org/wikipedia/commons/" + digest[0] + "/" + digest[:2] + "/" + urllib.parse.quote(filename)
        request = urllib.request.Request(url, headers={"User-Agent": "MemoryWeaverHackathon/1.0 (educational sample attribution)"})
        target = ROOT / "app/static/assets" / (asset_id + ".jpg")
        if not target.exists():
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        image = Image.open(io.BytesIO(response.read()))
                        image = ImageOps.exif_transpose(image).convert("RGB")
                        image.thumbnail((2000, 1600))
                        image.save(target, quality=88)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 or attempt == 3:
                        raise
                    time.sleep(10 * (attempt + 1))
        credits.append(dict(id=asset_id, url="/static/assets/" + asset_id + ".jpg", label=name, sample=True, credit=author + " · " + license_name + " · resized, metadata removed", source_url="https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name), license_url=license_url))
        print("Downloaded", asset_id)
    (ROOT / "samples/assets.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
