"""Retire the pre-showcase journal without shipping or exposing private history.

Used only by bootstrap. Switch archives the room; Mattermost's official channel
DELETE archives its channel. The private database/media/PDFs stay in a local
retirement folder outside every web route. Agent/account credentials stay put.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3

import httpx


JOURNAL_TABLES = ('sources','assets','revisions','events','jobs','handled','approvals','deliveries')


def backup_journal(root):
    destination=root.root/'retired'/'legacy-journal'
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/'memoryweaver.sqlite'
    if not target.exists():
        temporary=destination/'backup.sqlite.tmp'
        with root.connect() as source,sqlite3.connect(temporary) as backup:
            source.backup(backup)
        temporary.replace(target)
    return destination


def clear_active_journal(root,destination):
    # These directories contain only the old unscoped book, never trip folders.
    for name in ('media','books','exports'):
        source=root.root/name
        if source.exists():
            target=destination/name;target.mkdir(exist_ok=True)
            for item in source.iterdir():
                if not (target/item.name).exists():shutil.move(str(item),str(target/item.name))
    (root.root/'media').mkdir(exist_ok=True)
    with root.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        for table in JOURNAL_TABLES:db.execute('DELETE FROM '+table)
        db.execute("DELETE FROM kv WHERE key='trip' OR key='publication' OR key='seed:complete' OR key LIKE 'seed:post:%' OR key LIKE 'console-job:%' OR key LIKE 'job-mode:%'")
        items=[t for t in root.get('trips',[]) if not t.get('legacy')]
        db.execute("INSERT OR REPLACE INTO kv VALUES ('trips',?)",(json.dumps(items),))
        db.execute("INSERT OR REPLACE INTO kv VALUES ('retired:legacy','true')")


async def retire_legacy(root,saved,collector):
    if root.get('retired:legacy'):return
    old=next((t for t in root.get('trips',[]) if t.get('legacy')),None)
    has_unscoped_data=bool(root.revision() or root.all('sources'))
    if not old and not root.get('trip',{}).get('legacy') and not has_unscoped_data:return
    destination=backup_journal(root)
    room_id=saved.get('room_id');channel_id=saved.get('channel_id')
    if room_id:await collector.op('archive_room',room_id=room_id)
    if channel_id:
        async with httpx.AsyncClient(base_url=os.environ['MATTERMOST_URL'],timeout=60) as http:
            r=await http.post('/api/v4/users/login',json={'login_id':os.environ['MATTERMOST_ADMIN_USER'],'password':os.environ['MATTERMOST_ADMIN_PASSWORD']});r.raise_for_status()
            http.headers['Authorization']='Bearer '+r.headers['token']
            try:
                r=await http.get('/api/v4/channels/'+channel_id);r.raise_for_status()
                if not r.json().get('delete_at'):
                    r=await http.delete('/api/v4/channels/'+channel_id);r.raise_for_status()
            finally:await http.post('/api/v4/users/logout')
    clear_active_journal(root,destination)
    print('Obsolete journal retired from the judge showcase; private history is backed up locally.',flush=True)
