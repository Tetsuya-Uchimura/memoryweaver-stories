"""Wait for the actual Switch transcript before generating seeded demo books."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
from agents.switch import Switch


@asynccontextmanager
async def connected_collector(store):
    state=store.get('switch');client=Switch(state['agents']['collector'],state['room_id'])
    queue=asyncio.Queue();task=asyncio.create_task(client.listen(queue))
    try:
        await asyncio.wait_for(queue.get(),30)
        yield client
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True);await client.http.aclose()


async def confirm_post(client,body,photo=None,timeout=30):
    deadline=asyncio.get_running_loop().time()+timeout
    while asyncio.get_running_loop().time()<deadline:
        history=await client.history()
        matches=[e for e in history if e.get('kind')=='message' and e.get('sender_kind')=='user' and e.get('body','').strip()==body.strip()]
        for entry in matches:
            if photo is None:return
            for attachment in entry.get('attachments',[]):
                if attachment.get('mimetype','').startswith('image/'):
                    data=await client.download(attachment['mxc'])
                    if hashlib.sha256(data).digest()==hashlib.sha256(photo).digest():return
        await asyncio.sleep(.25)
    raise RuntimeError('Mattermost accepted a sample post, but Switch did not acknowledge its complete text/photo within 30 seconds. Generation stopped to avoid an incomplete book. Check bridge logs; no replay substitute or duplicate post was created.')
