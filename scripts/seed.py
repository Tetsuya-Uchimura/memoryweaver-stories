"""Posts fictional memories and licensed illustrative photographs as real Mattermost users."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import httpx
from app.store import Store


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--message")
    args = parser.parse_args()
    store = Store()
    channel = store.get("switch")["channel_id"]
    base = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    async with httpx.AsyncClient(base_url=base, timeout=60) as http:
        async def login(username, password):
            r = await http.post("/api/v4/users/login", json={"login_id": username, "password": password})
            r.raise_for_status()
            return {"Authorization": "Bearer " + r.headers["token"]}
        admin = await login(os.environ["MATTERMOST_ADMIN_USER"], os.environ["MATTERMOST_ADMIN_PASSWORD"])
        human = await login(os.environ["MATTERMOST_USER"], os.environ["MATTERMOST_USER_PASSWORD"])
        if args.message:
            r = await http.post("/api/v4/posts", headers=human, json={"channel_id": channel, "message": args.message})
            r.raise_for_status()
            print("Posted human instruction.")
            return
        if not store.get("seed:complete"):
            hana_password = store.get("seed:hana_password") or "Mw-" + secrets.token_hex(16)
            store.set("seed:hana_password", hana_password)
            r = await http.post("/api/v4/users", headers=admin, json={"username": "hana", "email": "hana@example.test", "password": hana_password, "first_name": "Hana"})
            if r.status_code not in (200, 201, 400):
                r.raise_for_status()
            r = await http.get("/api/v4/users/username/hana", headers=admin)
            r.raise_for_status()
            hana_id = r.json()["id"]
            team = await http.get("/api/v4/teams/name/" + os.environ["MATTERMOST_TEAM_NAME"], headers=admin)
            team.raise_for_status()
            team_id = team.json()["id"]
            r = await http.post(f"/api/v4/teams/{team_id}/members", headers=admin, json={"team_id": team_id, "user_id": hana_id})
            r.raise_for_status()
            r = await http.post(f"/api/v4/channels/{channel}/members", headers=admin, json={"user_id": hana_id})
            r.raise_for_status()
            hana = await login("hana", hana_password)
            posts = json.loads(Path("samples/posts.json").read_text())
            await http.post("/api/v4/posts", headers=human, json={"channel_id": channel, "message": "MemoryWeaver sample · Fictional family trip, October 12–14, 2026. Photos are licensed illustrations, not family photographs. See the preview credits."})
            # Intentionally shuffled: explicit capture dates, not upload order, govern the book.
            for index in [4, 1, 0, 5, 2, 3]:
                post = posts[index]
                if store.get("seed:post:" + post["key"]):
                    continue
                headers = human if post["author"] == "traveler" else hana
                files = []
                if post["asset"]:
                    path = Path("app/static/assets") / (post["asset"] + ".jpg")
                    r = await http.post("/api/v4/files", headers=headers, data={"channel_id": channel}, files={"files": (path.name, path.read_bytes(), "image/jpeg")})
                    r.raise_for_status()
                    files = [f["id"] for f in r.json()["file_infos"]]
                r = await http.post("/api/v4/posts", headers=headers, json={"channel_id": channel, "message": "[" + post["at"] + "] " + post["text"], "file_ids": files})
                r.raise_for_status()
                store.set("seed:post:" + post["key"], r.json()["id"])
                await asyncio.sleep(1)
            store.set("seed:complete", True)
            print("Six fictional memories posted by traveler and hana, with four licensed photos.")
        else:
            print("Sample already posted; no duplicates created.")
        if args.generate:
            await asyncio.sleep(3)
            r = await http.post("/api/v4/posts", headers=human, json={"channel_id": channel, "message": "@mw-collector 今回の沖縄旅行をアルバムにして"})
            r.raise_for_status()
            print("Generation requested through Mattermost → Switch.")


if __name__ == "__main__":
    asyncio.run(main())
