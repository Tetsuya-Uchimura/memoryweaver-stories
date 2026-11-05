"""Provision each independent fictional trip via audited official Switch ops."""
import json
import os
from pathlib import Path
from app.store import Store


async def provision_trips(root,saved,collector):
    definitions=json.loads(Path('samples/trips.json').read_text())
    items=[]
    # Keep the original private data and its room; never relabel it as Kyoto.
    legacy=root.get('trips',[])
    old=next((t for t in legacy if t.get('legacy')),None)
    if not old and saved.get('room_id') and (root.revision() or root.all('sources') or root.get('seed:complete')):
        old=dict(id='okinawa',label='Okinawa · existing journal',destination='Okinawa, Japan',channel='okinawa-memories',language='ja',legacy=True)
    if old:
        root.set('trip',old);items.append(old)
    rooms=await collector.op('list_rooms')
    bridges=await collector.op('list_bridges');bridges=bridges if isinstance(bridges,list) else bridges['bridges']
    bridge=next(b for b in bridges if b['type']=='mattermost')
    native=root.get('console',{}) or {}
    names=['mw-'+role for role in saved['agents']]+[a['name'] for a in native.values()]
    assets=json.loads(Path('samples/world-assets.json').read_text())
    for definition in definitions:
        trip={k:v for k,v in definition.items() if k!='posts'}
        existing=next((r for r in rooms if r['name']==trip['channel']),None)
        if existing:room_id=existing['room_id']
        else:
            room=await collector.op('create_room',name=trip['channel'],description=trip['description'],agent_names=names,user_names=[os.environ['MATTERMOST_USER']],channel_type='channel_private',bridge_id=bridge['id'],read_visibility='private',write_visibility='private',instructions='MemoryWeaver fictional travel sample. Write in English. Use only this room’s evidence; never mix trips. Locations marked Sample location are approximate fictional landmark pins, not actual camera GPS. Use room documents and targeted handoffs. Never publish without exact-version human approval. Start with @mw-collector.')
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
        if not saved.get('room_id'):
            saved.update(room_id=room_id,channel_id=detail['external_channel_id']);root.set('switch',saved)
    root.set('trips',items);root.set('default_trip','kyoto')
