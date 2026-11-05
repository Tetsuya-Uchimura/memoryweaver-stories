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
    if not root.get("trips"):
        raise ValueError("Run the Docker bootstrap before seeding the judge journals")
    await world(args,root)


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
                if tid not in definitions:raise ValueError('Choose a journal from the active judge showcase')
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
                        posts=definition['posts'];order=[i for i,p in enumerate(posts) if p['asset']][::-1]+[i for i,p in enumerate(posts) if not p['asset']]
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
                        print(tid+': '+str(len(posts))+' English memories checked; missing posts added without duplicates',flush=True)
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
