from types import SimpleNamespace
import pytest
from scripts.seed_sync import confirm_post


async def test_seed_waits_for_complete_switch_message_and_original_photo():
    calls=[]
    async def history():
        calls.append(True)
        return [] if len(calls)==1 else [dict(kind='message',sender_kind='user',body='memory',attachments=[dict(mimetype='image/jpeg',mxc='room-scoped')])]
    async def download(mxc):
        assert mxc=='room-scoped'
        return b'original-photo'
    await confirm_post(SimpleNamespace(history=history,download=download),'memory',b'original-photo',timeout=2)
    assert len(calls)==2


@pytest.mark.parametrize('kind,photo',[('agent',b'correct'),('user',b'wrong')])
async def test_seed_refuses_incomplete_or_agent_echoed_intake(kind,photo):
    async def history():return [dict(kind='message',sender_kind=kind,body='memory',attachments=[dict(mimetype='image/jpeg',mxc='media')])]
    async def download(mxc):return photo
    with pytest.raises(RuntimeError,match='Generation stopped'):
        await confirm_post(SimpleNamespace(history=history,download=download),'memory',b'correct',timeout=.001)


async def test_seed_reader_never_opens_or_binds_a_worker_connection():
    import httpx
    from scripts.seed_sync import SeedTranscript
    requests=[]
    async def transport(request):
        requests.append(request)
        assert 'X-Switch-Connection-Id' not in request.headers
        if request.url.path.endswith('read_context'):
            return httpx.Response(200,json={'result':{'threads':[{'root':dict(id='join',sender='opaque',sender_name='traveler',kind='room_join',timestamp=1),'replies':[dict(id='memory',sender='opaque',sender_name='traveler',kind='message',timestamp=2,body='memory')]}],'truncated':False}})
        assert request.url.path.endswith('get_room_detail')
        return httpx.Response(200,json={'result':{'agent_names':['mw-collector'],'connected_user_names':['traveler']}})
    client=SeedTranscript(dict(id='collector',api_key='test-only'),'room')
    await client.http.aclose()
    client.http=httpx.AsyncClient(base_url='http://switch',transport=httpx.MockTransport(transport))
    try:
        entries=await client.history()
        assert entries[1]['sender_kind']=='user' and not client.connected.is_set()
        assert len(requests)==2
    finally:await client.http.aclose()
