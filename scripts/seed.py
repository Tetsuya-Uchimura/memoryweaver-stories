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
    parser.add_argument("--trip", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--native", action="store_true", help="Request actual configured native inference rather than a labeled demo replay")
    args = parser.parse_args()
    root=Store()
    if root.get("trips"):
        await world(args,root)
        return
    store = root
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


async def world(args,root):
    from app.trips import trip_store
    definitions={t["id"]:t for t in json.loads(Path("samples/trips.json").read_text())}
    chosen=list(definitions) if args.all else [args.trip or root.get("default_trip","kyoto")]
    async with httpx.AsyncClient(base_url=os.getenv("MATTERMOST_URL","http://localhost:8065"),timeout=60) as http:
        async def login(name,password):
            r=await http.post('/api/v4/users/login',json={"login_id":name,"password":password});r.raise_for_status()
            return {"Authorization":"Bearer "+r.headers["token"]}
        admin=await login(os.environ['MATTERMOST_ADMIN_USER'],os.environ['MATTERMOST_ADMIN_PASSWORD'])
        human=await login(os.environ['MATTERMOST_USER'],os.environ['MATTERMOST_USER_PASSWORD'])
        try:
            for tid in chosen:
                child=trip_store(root,tid);channel=child.get('switch')['channel_id']
                if args.message:
                    r=await http.post('/api/v4/posts',headers=human,json={"channel_id":channel,"message":args.message});r.raise_for_status();print('Posted instruction to '+tid);continue
                if tid not in definitions:raise ValueError('Legacy books are retained; use --trip with a new world sample')
                definition=definitions[tid]
                password=root.get('seed:hana_password') or 'Mw-'+secrets.token_hex(16);root.set('seed:hana_password',password)
                user=await http.get('/api/v4/users/username/hana',headers=admin)
                if user.status_code==404:
                    r=await http.post('/api/v4/users',headers=admin,json={"username":"hana","email":"hana@example.test","password":password,"first_name":"Hana"});r.raise_for_status();user=r
                user.raise_for_status();uid=user.json()['id']
                team=await http.get('/api/v4/teams/name/'+os.environ['MATTERMOST_TEAM_NAME'],headers=admin);team.raise_for_status()
                for route,data in [(f"/api/v4/teams/{team.json()['id']}/members",{"team_id":team.json()['id'],"user_id":uid}),(f"/api/v4/channels/{channel}/members",{"user_id":uid})]:
                    r=await http.post(route,headers=admin,json=data);r.raise_for_status()
                hana=await login('hana',password)
                try:
                    from scripts.seed_sync import collector_reader,confirm_post
                    async with collector_reader(child) as switch:
                        if not child.get('seed:complete'):
                            r=await http.post('/api/v4/posts',headers=human,json={"channel_id":channel,"message":"MemoryWeaver sample · FICTIONAL TRAVEL JOURNAL · Licensed landmark illustrations. Sample location pins are approximate fictional stops, NOT the photographer’s original GPS or proof of these travelers’ presence."});r.raise_for_status()
                            posts=definition['posts'];order=list(range(0,len(posts),2))[::-1]+list(range(1,len(posts),2))
                            for i in order:
                                p=posts[i]
                                existing=child.get('seed:post:'+p['key'])
                                if existing:
                                    r=await http.get('/api/v4/posts/'+existing,headers=human);r.raise_for_status()
                                    await confirm_post(switch,r.json()['message'],(Path('app/static/assets')/(p['asset']+'.jpg')).read_bytes() if p['asset'] else None)
                                    continue
                                headers=human if p['author']=='traveler' else hana;files=[]
                                if p['asset']:
                                    image=Path('app/static/assets')/(p['asset']+'.jpg')
                                    r=await http.post('/api/v4/files',headers=headers,data={"channel_id":channel},files={"files":(image.name,image.read_bytes(),'image/jpeg')});r.raise_for_status();files=[f['id'] for f in r.json()['file_infos']]
                                place=p['location'];annotation=f"[Sample location: {place['name']} | {place['latitude']},{place['longitude']}]"
                                body="["+p['at']+"] "+annotation+"\n"+p['text']
                                r=await http.post('/api/v4/posts',headers=headers,json={"channel_id":channel,"message":body,"file_ids":files});r.raise_for_status()
                                child.set('seed:post:'+p['key'],r.json()['id'])
                                await confirm_post(switch,body,image.read_bytes() if p['asset'] else None)
                            child.set('seed:complete',True)
                            print('Seeded '+tid+' with '+str(len(posts))+' English memories',flush=True)
                        else:print(tid+': sample already posted; no duplicates',flush=True)
                        if args.generate:
                            for source_post in definition['posts']:
                                posted_id=child.get('seed:post:'+source_post['key'])
                                r=await http.get('/api/v4/posts/'+posted_id,headers=human);r.raise_for_status()
                                photo=(Path('app/static/assets')/(source_post['asset']+'.jpg')).read_bytes() if source_post['asset'] else None
                                await confirm_post(switch,r.json()['message'],photo)
                            prefix='@mw-collector ' if args.native else '@mw-collector [DEMO REPLAY] '
                            r=await http.post('/api/v4/posts',headers=human,json={"channel_id":channel,"message":prefix+"Create an English travel album from this room. Preserve every memory, photograph, and supplied location. Do not publish."});r.raise_for_status()
                finally:await http.post('/api/v4/users/logout',headers=hana)
        finally:
            await http.post('/api/v4/users/logout',headers=human)
            await http.post('/api/v4/users/logout',headers=admin)


if __name__ == "__main__":
    asyncio.run(main())
