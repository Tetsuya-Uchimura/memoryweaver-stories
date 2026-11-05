"""Judge upgrades retire old private data without losing credentials or books."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import httpx
from PIL import Image
import pytest

from agents.models import replay
from app.store import Store
from scripts.retire_legacy import retire_legacy


def legacy(root):
    root.set('trip',dict(id='retired',legacy=True))
    root.set('trips',[dict(id='retired',legacy=True),dict(id='kyoto',language='en')])
    root.set('default_trip','kyoto')
    root.set('console',{'binding':'retain this private configuration'})
    root.set('switch',{'agents':{'collector':{'api_key':'test-only-credential'}}})
    for a in json.loads(Path('tests/fixtures/assets.json').read_text()):root.put('assets',a)
    sources=[dict(id=p['key'],author=p['author'],text=p['text'],captured_at=p['at'],asset_ids=[p['asset']] if p['asset'] else []) for p in json.loads(Path('tests/fixtures/posts.json').read_text())]
    for s in sources:root.put('sources',s)
    job=root.job('Create a travel journal','old-request');root.commit(replay(dict(sources=sources,job=job)),job['id'],'replay',sources)
    image=io.BytesIO();Image.new('RGB',(30,20),'skyblue').save(image,format='JPEG')
    (root.root/'media'/('f'*24+'.jpg')).write_bytes(image.getvalue())
    return image.getvalue()


async def test_retirement_archives_channel_and_backs_up_private_history(tmp_path,monkeypatch):
    from app import main
    root=Store(tmp_path);photo=legacy(root);calls=[]
    async def op(operation,**args):calls.append((operation,args));return {}
    def respond(request):
        calls.append((request.method,request.url.path))
        if request.url.path.endswith('/login'):return httpx.Response(200,headers={'token':'local-test-session'},json={})
        return httpx.Response(200,json={'delete_at':0})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(respond)))
    for k,v in dict(MATTERMOST_URL='http://local',MATTERMOST_ADMIN_USER='admin',MATTERMOST_ADMIN_PASSWORD='test-only').items():monkeypatch.setenv(k,v)
    saved=dict(room_id='old-room',channel_id='old-channel')
    await retire_legacy(root,saved,SimpleNamespace(op=op))
    assert ('archive_room',dict(room_id='old-room')) in calls
    assert ('DELETE','/api/v4/channels/old-channel') in calls
    assert root.revision() is None and not root.all('sources') and not root.all('assets')
    assert root.get('console')['binding'].startswith('retain')
    assert root.get('switch')['agents']['collector']['api_key']=='test-only-credential'
    assert root.get('trips')==[dict(id='kyoto',language='en')]
    backup=root.root/'retired/legacy-journal/memoryweaver.sqlite'
    with sqlite3.connect(backup) as db:assert db.execute('SELECT count(*) FROM revisions').fetchone()[0]==1
    assert (backup.parent/'media'/('f'*24+'.jpg')).read_bytes()==photo
    assert not list((root.root/'media').iterdir())
    monkeypatch.setattr(main,'store',root)
    async with original(transport=httpx.ASGITransport(app=main.app),base_url='http://web') as h:
        assert (await h.get('/api/state?trip=retired')).status_code==404
        assert (await h.get('/media/'+('f'*24)+'.jpg')).status_code==404
        assert (await h.get('/api/state?trip=kyoto')).status_code==200
    before=list(calls);stamp=backup.stat().st_mtime_ns
    await retire_legacy(root,saved,SimpleNamespace(op=op))
    assert calls==before and backup.stat().st_mtime_ns==stamp


async def test_failed_archive_keeps_the_active_private_journal(tmp_path):
    root=Store(tmp_path);photo=legacy(root)
    async def fail(*a,**kw):raise RuntimeError('Bridge unavailable')
    with pytest.raises(RuntimeError,match='Bridge unavailable'):
        await retire_legacy(root,dict(room_id='old-room'),SimpleNamespace(op=fail))
    assert root.revision()['version']==1 and root.all('sources')
    assert (root.root/'media'/('f'*24+'.jpg')).read_bytes()==photo
    assert not root.get('retired:legacy')


def test_all_judge_fixtures_and_role_guides_are_english():
    import re
    from agents.console import guide
    matcher=re.compile('[\u3040-\u30ff\u3400-\u9fff]')
    trips=json.loads(Path('samples/trips.json').read_text())
    assert [t['id'] for t in trips]==['kyoto','paris','new-york','santorini']
    assert all(t['language']=='en' and len({p['asset'] for p in t['posts'] if p['asset']})==6 for t in trips)
    assert not matcher.search(json.dumps(trips,ensure_ascii=False))
    assert not matcher.search(guide('storyteller')+guide('editor'))


async def test_historical_protocol_translation_preserves_sources_and_post_identity(tmp_path,monkeypatch):
    from scripts.english_setup import english_protocol_history
    root=Store(tmp_path);root.set('trips',[dict(id='kyoto',channel='kyoto-travel-journal')])
    root.set('console',dict(storyteller=dict(name='mw-storyteller-claude'),editor=dict(name='mw-editor-codex')))
    child=Store(root.root/'trips/kyoto');child.set('switch',dict(channel_id='channel'))
    child.put('sources',dict(id='human',text='We walked beneath the gates.'))
    old=dict(id='old',user_id='collector-bot',message='@mw-storyteller-claude MW_CONSOLE '+json.dumps(dict(job_id='finished-job'))+'\nLabel it \u64ae\u5f71\u65e5\u672a\u78ba\u8a8d',file_ids=['attachment'])
    original_text=old['message'];updates=[]
    def respond(request):
        if request.url.path.endswith('/login'):return httpx.Response(200,headers={'token':'test-session'},json={})
        if request.url.path.endswith('/username/mw-collector'):return httpx.Response(200,json=dict(id='collector-bot'))
        if request.method=='GET':return httpx.Response(200,json={'posts':{'old':old}})
        if request.method=='PUT':
            updates.append(json.loads(request.content));old.update(updates[-1]);return httpx.Response(200,json=old)
        return httpx.Response(200,json={})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(**kw,transport=httpx.MockTransport(respond)))
    for k,v in dict(MATTERMOST_URL='http://local',MATTERMOST_ADMIN_USER='admin',MATTERMOST_ADMIN_PASSWORD='test-only').items():monkeypatch.setenv(k,v)
    await english_protocol_history(root)
    assert len(updates)==1 and old['file_ids']==['attachment'] and old['user_id']=='collector-bot'
    assert old['message'].splitlines()[0]==original_text.splitlines()[0]
    assert 'Write all narration and collaboration messages in English' in old['message']
    assert child.all('sources')[0]['text']=='We walked beneath the gates.'
    assert json.loads((root.root/'retired/protocol-language-upgrade/old.json').read_text())['message']==original_text
    await english_protocol_history(root)
    assert len(updates)==1
