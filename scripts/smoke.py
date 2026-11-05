"""Real Mattermost → Switch integration. Runs only with replay and cloud OFF."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from app.store import Store
from agents.publish import approval_command
from scripts.verify_release import verify


async def main():
    if Store().get("console") or os.getenv("AI_MODE", "replay") != "replay" or os.getenv("PUBLISH_ENABLED") == "true":
        raise SystemExit("Smoke test requires AI_MODE=replay and PUBLISH_ENABLED=false")
    root=Store()
    from app.trips import trip_store
    store=trip_store(root) if root.get("trips") else root
    if not store.get("seed:complete"):
        subprocess.run([sys.executable, "-m", "scripts.seed"], check=True)
    channel = store.get("switch")["channel_id"]
    async with httpx.AsyncClient(base_url=os.environ["MATTERMOST_URL"], timeout=30) as mm:
        login = await mm.post("/api/v4/users/login", json={"login_id": os.environ["MATTERMOST_USER"], "password": os.environ["MATTERMOST_USER_PASSWORD"]})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.headers["token"]}

        async def post(message, auth=headers):
            response = await mm.post("/api/v4/posts", headers=auth, json={"channel_id": channel, "message": message})
            response.raise_for_status()

        async def wait_version(after, predicate=lambda r: True):
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                revision = store.revision()
                if revision and revision["version"] > after and predicate(revision):
                    return revision
                await asyncio.sleep(1)
            raise AssertionError("No expected preview update; inspect agent logs and collaboration feed")

        async def wait_for_artifacts(revision):
            version = revision["version"]
            deadline = time.monotonic() + 120
            post = None
            while time.monotonic() < deadline:
                response = await mm.get(f"/api/v4/channels/{channel}/posts", headers=headers, params={"per_page": 200})
                response.raise_for_status()
                posts = response.json()["posts"].values()
                post = next((p for p in posts if f"MemoryWeaver · v{version} · REPLAY" in p["message"].splitlines() and len(p.get("file_ids", [])) == 2), None)
                if post and (store.delivery(version) or {}).get("state") == "sent":
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError(f"No complete Mattermost PDF/cover delivery for v{version}: {store.delivery(version)}")
            publisher = await mm.get("/api/v4/users/username/mw-publisher", headers=headers)
            publisher.raise_for_status()
            assert publisher.json()["is_bot"]
            assert post["user_id"] == publisher.json()["id"]
            assert not post["root_id"]  # directly visible in the original channel
            assert revision["album"]["title"] in post["message"]
            assert f"version={version}" in post["message"]
            received = {}
            for file_id in post["file_ids"]:
                info = await mm.get(f"/api/v4/files/{file_id}/info", headers=headers)
                info.raise_for_status()
                content = await mm.get(f"/api/v4/files/{file_id}", headers=headers)
                content.raise_for_status()
                received[info.json()["mime_type"]] = content.content
            assert received["application/pdf"].startswith(b"%PDF-")
            receipt = store.delivery(version)["receipt"]
            assert hashlib.sha256(received["application/pdf"]).hexdigest() == receipt["pdf_sha256"]
            assert hashlib.sha256(received["image/jpeg"]).hexdigest() == revision["asset_hashes"][revision["album"]["cover_asset_id"]]
            async with httpx.AsyncClient() as web:
                download = await web.get(os.getenv("WEB_URL", "http://web:8787") + f"/api/revisions/{version}/pdf",params={"trip":store.get("trip")["id"]} if store.get("trip") else {})
                download.raise_for_status()
                assert download.content == received["application/pdf"]
            print(f"PASS Mattermost delivery v{version}: Publisher bot, title, version URL, cover and downloadable PDF in one channel post")

        before = (store.revision() or {}).get("version", 0)
        target="kyoto-bamboo" if store.get("trip",{}).get("id")=="kyoto" else "kyoto-bamboo"
        await post("@mw-collector Create a travel album from this room in English.")
        first = await wait_version(before)
        assert len(first["album"]["chapters"]) == 3
        expected = next(t for t in json.loads(Path("samples/trips.json").read_text()) if t["id"] == store.get("trip")["id"]) if store.get("trip",{}).get("id") in {"kyoto","paris","new-york"} else None
        assert len(first["sources"]) == (len(expected["posts"]) if expected else 6)
        assert {s["author"] for s in first["sources"]} == {"traveler", "hana"}
        stale_command = approval_command(first)
        print("PASS generation: real Mattermost posts → Switch documents → three-chapter preview")
        await wait_for_artifacts(first)

        await post("@mw-collector Change the cover to photo ID "+target)
        second = await wait_version(first["version"], lambda r: r["album"]["cover_asset_id"] == target)
        assert store.revision(first["version"])["album"]["cover_asset_id"] == first["album"]["cover_asset_id"]
        print("PASS revision: requested cover, prior version preserved")
        await wait_for_artifacts(second)

        await post("@mw-collector Make day two more emotional using only the original memories.")
        third = await wait_version(second["version"])
        assert third["album"]["chapters"][1]["body"] != second["album"]["chapters"][1]["body"]
        assert third["album"]["cover_asset_id"] == target
        print("PASS revision: day-two prose updated, requested cover preserved")
        await wait_for_artifacts(third)

        await post(f"@mw-publisher resend PDF v{third['version']}")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            delivery = store.delivery(third["version"])
            if delivery["state"] == "sent" and delivery["receipt"].get("recovered"):
                break
            await asyncio.sleep(1)
        else:
            raise AssertionError("Publisher did not reconcile its accepted attachment group")
        response = await mm.get(f"/api/v4/channels/{channel}/posts", headers=headers, params={"per_page": 200})
        response.raise_for_status()
        marker = f"MemoryWeaver · v{third['version']} · REPLAY"
        assert sum(marker in p["message"].splitlines() and bool(p.get("file_ids")) for p in response.json()["posts"].values()) == 1
        assert store.revision()["version"] == third["version"]
        print("PASS delivery recovery: Mattermost retry reconciled the real Switch attachment group without another post or book version")

        event_start = len(store.events())
        await post(stale_command)
        await asyncio.sleep(3)
        assert any(e["kind"] == "error" and "latest version" in e["message"] for e in store.events()[event_start:])
        print("PASS privacy: stale version approval rejected")

        # Another real human in the same room cannot approve the owner's publication.
        hana = await mm.post("/api/v4/users/login", json={"login_id": "hana", "password": root.get("seed:hana_password")})
        hana.raise_for_status()
        await post(approval_command(third), {"Authorization": "Bearer " + hana.headers["token"]})
        await asyncio.sleep(3)
        assert any("Only the configured traveler" in e["message"] for e in store.events())
        print("PASS privacy: another contributor cannot authorize publication")

        await post(approval_command(third))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            publication = store.get("publication", {})
            if publication.get("version") == third["version"] and publication.get("state") == "local-export":
                break
            await asyncio.sleep(1)
        else:
            raise AssertionError("No approved local export")
        verify(store.root / "exports" / ("v" + str(third["version"])))
        assert store.get("publication")["url"] is None
        print("PASS publication: exact-version consent → allowlisted local export; no cloud calls")
        print("All real-stack smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
