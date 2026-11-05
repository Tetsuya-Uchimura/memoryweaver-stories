"""One-time translation of project-generated historical protocol instructions.

This is bootstrap maintenance, not an agent or generation pipeline. Only the
Collector bot's completed MW_CONSOLE messages are edited using Mattermost's
official partial-post API. Source memories, IDs, attachments and authors stay
untouched; originals are retained in private, unserved local storage.
"""
import json
import os
import re

import httpx
from agents.console import guide
from app.trips import trip_store

CJK=re.compile('[\u3040-\u30ff\u3400-\u9fff]')


async def english_protocol_history(root):
    binding=root.get('console')
    if not binding:return
    async with httpx.AsyncClient(base_url=os.environ['MATTERMOST_URL'],timeout=60) as http:
        r=await http.post('/api/v4/users/login',json={'login_id':os.environ['MATTERMOST_ADMIN_USER'],'password':os.environ['MATTERMOST_ADMIN_PASSWORD']});r.raise_for_status()
        http.headers['Authorization']='Bearer '+r.headers['token']
        try:
            r=await http.get('/api/v4/users/username/mw-collector');r.raise_for_status();author=r.json()['id']
            for t in root.get('trips',[]):
                child=trip_store(root,t['id'])
                channel=child.get('switch')['channel_id']
                posts={}
                for page in range(100):
                    r=await http.get('/api/v4/channels/'+channel+'/posts',params={'per_page':200,'page':page});r.raise_for_status();batch=r.json()['posts'];posts.update(batch)
                    if len(batch)<200:break
                else:raise ValueError('History exceeds the maintenance scan; refusing partial translation')
                for p in posts.values():
                    if not CJK.search(p['message']):continue
                    if p['user_id']!=author or ' MW_CONSOLE ' not in p['message'].splitlines()[0]:
                        raise ValueError('A non-English source needs explicit translation; bootstrap will not rewrite human memories')
                    envelope=json.loads(p['message'].splitlines()[0].split('MW_CONSOLE ',1)[1])
                    with child.connect() as db:
                        job=db.execute('SELECT state FROM jobs WHERE id=?',(envelope['job_id'],)).fetchone()
                    if job and job['state']=='working':raise ValueError('Wait for the active native job before upgrading its protocol instructions')
                    # Only inactive historical protocol instructions are replaced.
                    body=p['message'].splitlines()[0]+'\n'+guide('storyteller',binding['storyteller']['name'],binding['editor']['name'])
                    target=root.root/'retired'/'protocol-language-upgrade'/(p['id']+'.json')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():target.write_text(json.dumps(p,ensure_ascii=False))
                    r=await http.put('/api/v4/posts/'+p['id']+'/patch',json={'message':body});r.raise_for_status()
                    value=r.json()
                    if value['message']!=body or value.get('file_ids',[])!=p.get('file_ids',[]) or value['user_id']!=author:
                        raise ValueError('Mattermost did not preserve the expected historical post identity')
                    print('Updated one historical Collector instruction to English in '+t['channel'],flush=True)
        finally:await http.post('/api/v4/users/logout')
