"""Observe a native run, verify real artifacts, then request/verify a cover edit.

Run in bootstrap with local generated environment. No public approval is sent.
At least two source photographs are required for --edit.
"""
import argparse
import asyncio
import hashlib
import os
import time

import httpx
from app.store import Store
from agents.artifacts import artifact_paths


async def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trip",default=None)
    p.add_argument("--after",type=int,required=True,help="Observe a version newer than this saved version")
    p.add_argument("--edit",action="store_true",help="Also send a real Mattermost cover-change request")
    p.add_argument("--expect-cover",help="Assert the observed version uses this cover ID")
    p.add_argument("--timeout",type=int,default=600)
    args=p.parse_args()
    root=Store()
    from app.trips import trip_store
    store=trip_store(root,args.trip) if root.get("trips") else root
    if not root.get("console") or os.getenv("PUBLISH_ENABLED")=="true":
        raise SystemExit("Requires Console binding and cloud publishing disabled")
    state=store.get("switch")
    before_publication=store.get("publication")
    base_revision=store.revision(args.after)
    expected_photos={a for c in base_revision["album"]["chapters"] for a in c["asset_ids"]} | {base_revision["album"]["cover_asset_id"]} if base_revision else set()
    async with httpx.AsyncClient(base_url=os.getenv("MATTERMOST_URL","http://localhost:8065"),timeout=30) as mm:
        r=await mm.post("/api/v4/users/login",json={"login_id":os.environ["MATTERMOST_USER"],"password":os.environ["MATTERMOST_USER_PASSWORD"]})
        r.raise_for_status()
        mm.headers["Authorization"]="Bearer "+r.headers["token"]
        async def verify_after(version,cover=None):
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline:
                revision=store.revision()
                if revision and revision["version"]>version:
                    delivery=store.delivery(revision["version"])
                    if delivery and delivery["state"]=="sent":break
                await asyncio.sleep(2)
            else:raise RuntimeError("Timed out waiting for native preview and artifact delivery; inspect Console and Mattermost")
            assert revision["mode"]=="live"
            if store.get('trip',{}).get('language')=='en':
                assert revision['language']=='en'
                if any(source.get('location') for source in revision['sources']):assert revision.get('photo_locations')
            selected={revision["album"]["cover_asset_id"],*[a for c in revision["album"]["chapters"] for a in c["asset_ids"]]}
            assert expected_photos.issubset(selected),"A previously selected photograph was lost"
            if cover: assert revision["album"]["cover_asset_id"]==cover
            with store.connect() as db:
                job_id=db.execute("SELECT job_id FROM revisions WHERE id=?",(revision["version"],)).fetchone()[0]
            receipt=store.get("console-job:"+job_id)
            assert receipt and receipt.get("draft_id"),"Missing authenticated native draft receipt"
            marker=f"MemoryWeaver · v{revision['version']} · LIVE"
            # Switch acceptance precedes asynchronous delivery to the bridge.
            # Observe the real Mattermost post rather than racing its arrival.
            delivery_deadline=time.monotonic()+30
            while True:
                r=await mm.get(f"/api/v4/channels/{state['channel_id']}/posts",params={"per_page":200});r.raise_for_status()
                posts=[post for post in r.json()["posts"].values() if marker in post["message"].splitlines() and len(post.get("file_ids",[]))==2]
                if posts or time.monotonic()>=delivery_deadline:break
                await asyncio.sleep(1)
            assert len(posts)==1,"Expected one Publisher completion post with both attachments"
            post=posts[0]
            assert f"version={revision['version']}" in post["message"] and revision["album"]["title"] in post["message"]
            user=await mm.get('/api/v4/users/'+post['user_id']);user.raise_for_status()
            assert user.json()["is_bot"] and "publisher" in user.json()["username"]
            pdf,cover_file,_=artifact_paths(store,revision["version"])
            expected={pdf.name:pdf.read_bytes(),cover_file.name:cover_file.read_bytes()}
            for file_id in post["file_ids"]:
                info=await mm.get('/api/v4/files/'+file_id+'/info');info.raise_for_status()
                data=await mm.get('/api/v4/files/'+file_id);data.raise_for_status()
                name=info.json()["name"]
                assert name in expected and hashlib.sha256(data.content).digest()==hashlib.sha256(expected[name]).digest()
            async with httpx.AsyncClient() as web:
                served=await web.get(os.environ["WEB_URL"]+f"/api/revisions/{revision['version']}/pdf"+('?'+'trip='+store.get('trip')['id'] if store.get('trip') else ''));served.raise_for_status()
                assert served.content==pdf.read_bytes()
            assert store.get("publication")==before_publication
            print(f"PASS native v{revision['version']}: authenticated Claude draft → Codex review → Publisher; {len(revision['sources'])} sources / {len(selected)} photos; Mattermost title, version URL, cover/PDF byte matches; no publication",flush=True)
            return revision["version"]
        try:
            version=await verify_after(args.after,args.expect_cover)
            if args.edit:
                candidates=[a["id"] for a in store.all("assets") if a["id"] in {aid for source in store.revision(version)["sources"] for aid in source["asset_ids"]}]
                target=next((aid for aid in candidates if aid!=store.revision(version)["album"]["cover_asset_id"]),None)
                if not target:raise ValueError("--edit requires two source photos")
                r=await mm.post('/api/v4/posts',json={"channel_id":state["channel_id"],"message":f"@mw-collector Please change the cover to photograph ID {target}. Keep all other memories, photographs, chapters and supplied locations. This is a cover-edit test. Do not publish."});r.raise_for_status()
                await verify_after(version,target)
        finally:
            await mm.post('/api/v4/users/logout')


if __name__=="__main__":
    asyncio.run(main())
