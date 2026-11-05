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
