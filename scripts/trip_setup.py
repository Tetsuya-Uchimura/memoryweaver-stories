"""Provision each independent fictional trip via audited official Switch ops."""
import json
import os
from pathlib import Path
from app.store import Store


ROOM_INSTRUCTIONS="MemoryWeaver fictional travel sample. Write all messages and album narration in English. Use only this room’s evidence; never mix trips. Sample locations are approximate fictional landmark pins, not actual camera GPS. Use room documents and targeted handoffs. Never publish without exact-version human approval. Start with @mw-collector."


async def provision_trips(root,saved,collector):
    definitions=json.loads(Path('samples/trips.json').read_text())
    items=[]
    from scripts.retire_legacy import retire_legacy
    await retire_legacy(root,saved,collector)
    rooms=await collector.op('list_rooms')
    bridges=await collector.op('list_bridges');bridges=bridges if isinstance(bridges,list) else bridges['bridges']
    bridge=next(b for b in bridges if b['type']=='mattermost')
    native=root.get('console',{}) or {}
    names=['mw-'+role for role in saved['agents']]+[a['name'] for a in native.values()]
    assets=json.loads(Path('samples/world-assets.json').read_text())
    for definition in definitions:
        trip={k:v for k,v in definition.items() if k!='posts'}
        existing=next((r for r in rooms if r['name']==trip['channel']),None)
        if existing:
            room_id=existing['room_id']
            await collector.op('update_room',room_id=room_id,description=trip['description'],instructions=ROOM_INSTRUCTIONS)
        else:
            room=await collector.op('create_room',name=trip['channel'],description=trip['description'],agent_names=names,user_names=[os.environ['MATTERMOST_USER']],channel_type='channel_private',bridge_id=bridge['id'],read_visibility='private',write_visibility='private',instructions=ROOM_INSTRUCTIONS)
            room_id=room['id']
        for actor in native.values():
            await collector.op('invite_agent_to_room',room_id=room_id,agent_name=actor['name'])
        detail=await collector.op('get_room_detail',room_id=room_id)
        child=Store(root.root/'trips'/trip['id'])
        child.set('trip',trip)
        child.set('switch',dict(agents=saved['agents'],room_id=room_id,channel_id=detail['external_channel_id']))
        child.set('console',native or None)
        for asset in assets:
            if asset['id'] in {p['asset'] for p in definition['posts'] if p.get('asset')}:child.put('assets',asset)
        items.append(trip)
        if trip['id']=='kyoto':
            saved.update(room_id=room_id,channel_id=detail['external_channel_id']);root.set('switch',saved)
    root.set('trips',items);root.set('default_trip','kyoto')
