"""Wait for the actual Switch transcript before generating seeded demo books."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
from agents.switch import Switch


class SeedTranscript(Switch):
    async def history(self):
        from agents.switch import classify_history
        entries=await super().history()
        detail=await self.op('get_room_detail',room_id=self.room_id)
        roster=[dict(name=n,type='user') for n in detail['connected_user_names']]+[dict(name=n,type='agent') for n in detail['agent_names']]
        classify_history(entries,roster)
        return entries


@asynccontextmanager
async def collector_reader(store):
    # read_context(room_id=...) supports an unbound caller in the official
    # contract. Do not open another Collector SSE session: it could change
    # event delivery/read accounting while the actual worker is consuming.
    state=store.get('switch');client=SeedTranscript(state['agents']['collector'],state['room_id'])
    try:
        await client.discover()
        yield client
    finally:
        await client.http.aclose()


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
