from copy import deepcopy
import io,json
from pathlib import Path

import httpx
from PIL import Image
import pytest
from app.models import Place
from app.locations import parse_location,exif_location,map_url
from app.store import Store
from app.trips import trip_store
from agents.models import replay
from agents.artifacts import pdf_html,album_url
from agents.publish import public_book,publication_digest,build_export


def make_book(root,tid):
    definition=next(t for t in json.loads(Path('samples/trips.json').read_text()) if t['id']==tid)
    store=Store(root.root/'trips'/tid)
    store.set('trip',{k:v for k,v in definition.items() if k!='posts'})
    assets=json.loads(Path('samples/world-assets.json').read_text())
    wanted={p['asset'] for p in definition['posts'] if p['asset']}
    for a in assets:
        if a['id'] in wanted:store.put('assets',a)
    sources=[dict(id=p['key'],author=p['author'],text=p['text'],captured_at=p['at'],date_basis='captured',asset_ids=[p['asset']] if p['asset'] else [],location=p['location']) for p in definition['posts']]
    for s in sources:store.put('sources',s)
    job=store.job('Create an English album','first-'+tid)
    payload=dict(sources=sources,job=job,language='en',destination=definition['destination'],trip_title=definition['title'],trip_subtitle=definition['subtitle'])
    store.commit(replay(payload),job['id'],'replay',sources)
    return store


@pytest.mark.parametrize('lat,lon',[(91,0),(0,-181),(float('nan'),0),(35,None)])
def test_invalid_coordinates_are_rejected(lat,lon):
    with pytest.raises(ValueError):Place(name='Nowhere',latitude=lat,longitude=lon)


def test_explicit_location_parses_without_guessing_or_changing_caption():
    text,place=parse_location('[Location: Fushimi Inari Taisha, Kyoto | 34.9671,135.7727]\nWe walked beneath the gates.')
    assert text=='We walked beneath the gates.' and place['basis']=='stated'
    assert place['latitude']==34.9671
    _,p=parse_location('[Location: A place without coordinates]\nA memory.')
    assert p['latitude'] is None and 'search?' in map_url(p)
    assert parse_location('Somewhere in Japan')[1] is None
    assert parse_location('[Sample location: Kyoto | 35,135]')[1]['basis']=='sample'


async def test_real_photo_gps_is_extracted_then_removed_from_image_bytes(tmp_path,monkeypatch):
    from app import main
    store=Store(tmp_path);monkeypatch.setattr(main,'store',store);monkeypatch.setenv('WEB_INTERNAL_TOKEN','private-test-key')
    image=Image.new('RGB',(40,30),'forestgreen');exif=Image.Exif()
    exif[34853]={1:'N',2:(35.0,0.0,0.0),3:'W',4:(73.0,30.0,0.0)}
    original=io.BytesIO();image.save(original,format='JPEG',exif=exif)
    with Image.open(io.BytesIO(original.getvalue())) as im:
        assert exif_location(im)['longitude']==-73.5
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://local') as h:
        r=await h.post('/internal/media',headers={'Authorization':'Bearer private-test-key'},files={'file':('photo.jpg',original.getvalue(),'image/jpeg')})
    assert r.status_code==200
    asset=r.json();assert asset['location']['basis']=='gps' and asset['location']['latitude']==35
    with Image.open(store.root/'media'/(asset['id']+'.jpg')) as sanitized:assert not sanitized.getexif()
    assert map_url(asset['location']).startswith('https://www.openstreetmap.org/')


async def test_trip_books_locations_and_version_ids_are_isolated(tmp_path,monkeypatch):
    from app import main
    root=Store(tmp_path)
    definitions=json.loads(Path('samples/trips.json').read_text())
    root.set('trips',[{k:v for k,v in d.items() if k!='posts'} for d in definitions]);root.set('default_trip','kyoto')
    kyoto=make_book(root,'kyoto');paris=make_book(root,'paris')
    assert kyoto.revision()['version']==paris.revision()['version']==1
    assert all('Paris' in p['name'] for p in paris.revision()['places'])
    assert all('Kyoto' in p['name'] for p in kyoto.revision()['places'])
    monkeypatch.setattr(main,'store',root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://local') as h:
        a=(await h.get('/api/state')).json();b=(await h.get('/api/state?trip=paris')).json()
        assert a['trip']['id']=='kyoto' and b['trip']['id']=='paris'
        assert a['revision']['album']['title']!=b['revision']['album']['title']
        assert (await h.get('/api/state?trip=../../private')).status_code==404
        assert '/kyoto-travel-journal' in a['mattermost_url']
        assert (await h.get('/api/revisions/1?trip=paris')).json()['trip_id']=='paris'
    assert 'trip=paris' in album_url(1,'paris')


def test_location_snapshot_pdf_and_public_consent_are_version_bound(tmp_path):
    root=Store(tmp_path);store=make_book(root,'kyoto');revision=store.revision()
    assert len(revision['photo_locations'])==6
    original=deepcopy(revision['photo_locations'])
    asset=store.all('assets')[0];asset['location']=dict(name='Changed later',latitude=1,longitude=2,basis='stated');store.put('assets',asset)
    assert store.revision()['photo_locations']==original
    doc=pdf_html(revision,{a['id']:a for a in store.all('assets')})
    assert 'Fushimi Inari' in doc and 'Open map' in doc and 'sample' in doc
    before=publication_digest(revision)
    changed=deepcopy(revision);changed['photo_locations']['kyoto-gates']['latitude']=0
    assert publication_digest(changed)!=before
    assert 'source_id' not in json.dumps(public_book(revision)['places'])
    dest,files=build_export(store,revision,{'user_id':'traveler','created':0})
    assert b'Fushimi Inari' in files['index.html'] and b'openstreetmap.org' in files['index.html']


def test_street_map_export_escapes_metadata_and_restricts_runtime_files(tmp_path):
    from html.parser import HTMLParser
    from agents.publish import MAP_FILES
    from scripts.verify_release import verify
    store=make_book(Store(tmp_path),'kyoto');revision=store.revision()
    hostile='Landmark "><img src=x onerror=alert(1)></script>'
    for place in revision['places']:
        place['name']=hostile
    for place in revision['photo_locations'].values():
        place['name']=hostile
    destination,files=build_export(store,revision,{'user_id':'traveler','created':0})
    class MapParser(HTMLParser):
        stops=None
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if 'data-map-stops' in attrs:self.stops=json.loads(attrs['data-map-stops'])
    parser=MapParser();parser.feed(files['index.html'].decode())
    assert parser.stops and parser.stops[0]['name']==hostile
    assert 'source_id' not in json.dumps(parser.stops)
    assert all(photo['url'].startswith('assets/') for stop in parser.stops for photo in stop['photos'])
    assert b'<img src=x' not in files['index.html']
    assert all(name in files for name in MAP_FILES)
    assert b"script-src 'self'" in files['_headers'] and b'https://tile.openstreetmap.org' in files['_headers']
    assert b'unsafe-inline' not in files['_headers']
    verify(destination)
    # A manifest hash does not authorize arbitrary extra JavaScript.
    import hashlib
    manifest=json.loads((destination/'release.json').read_text())
    (destination/'unexpected.js').write_bytes(b'alert(1)')
    manifest['files']['unexpected.js']=hashlib.sha256(b'alert(1)').hexdigest()
    (destination/'release.json').write_text(json.dumps(manifest))
    with pytest.raises(AssertionError,match='allowlist'):verify(destination)


def test_missing_location_is_never_inferred_from_fixture_filename(tmp_path):
    root=Store(tmp_path);store=make_book(root,'paris')
    sources=deepcopy(store.revision()['sources'])
    for s in sources:s['location']=None
    job=store.job('Retain the photos','without-places')
    store.commit(store.revision()['album'],job['id'],'replay',sources)
    assert store.revision()['photo_locations']=={} and store.revision()['places']==[]


def test_unused_private_source_location_does_not_enter_export(tmp_path):
    root=Store(tmp_path);store=make_book(root,'kyoto');r=store.revision()
    extra=dict(id='unused-private',author='private',text='Never export this',captured_at='2026-10-15',asset_ids=[],location=dict(name='PRIVATE HOME',latitude=12.1,longitude=40.2,basis='stated'))
    job=store.job('Keep the same chapters','with-unused-source')
    store.commit(r['album'],job['id'],'replay',r['sources']+[extra])
    assert 'PRIVATE HOME' not in json.dumps(public_book(store.revision()))


async def test_legacy_version_links_and_runtime_binding_respect_trip_jobs(tmp_path,monkeypatch):
    from app import main
    root=Store(tmp_path);kyoto=make_book(root,'kyoto')
    root.set('trip',dict(id='retired',legacy=True))
    root.set('trips',[dict(id='retired',legacy=True),dict(id='kyoto')]);root.set('default_trip','kyoto')
    for a in kyoto.all('assets'):root.put('assets',a)
    r=kyoto.revision();job=root.job('legacy','legacy');root.commit(r['album'],job['id'],'replay',r['sources'])
    monkeypatch.setattr(main,'store',root);monkeypatch.setenv('WEB_INTERNAL_TOKEN','secret-test-only')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://local') as h:
        assert (await h.get('/api/revisions/1')).json()['trip_id']=='retired'
        assert (await h.get('/api/revisions/1?trip=kyoto')).json()['trip_id']=='kyoto'
        kyoto.job('active','active')
        binding=dict(storyteller=dict(id='a',name='writer'),editor=dict(id='b',name='reviewer'))
        assert (await h.post('/internal/console',headers={'Authorization':'Bearer secret-test-only'},json=binding)).status_code==409


@pytest.mark.parametrize('tid,design',[('kyoto','quiet'),('paris','editorial'),('new-york','urban'),('santorini','coastal')])
def test_richer_books_have_six_distinct_sourced_photos_and_art_direction(tmp_path,tid,design):
    from agents.artifacts import render_artifacts
    from scripts.verify_release import verify
    root=Store(tmp_path);store=make_book(root,tid);r=store.revision()
    ids={aid for c in r['album']['chapters'] for aid in c['asset_ids']}
    assert len(ids)==6 and len(r['photo_locations'])==6
    assert r['album']['design']==design
    assert all(a.startswith(tid+'-') for a in ids)
    assets={a['id']:a for a in store.all('assets')}
    # Actual PDFs exercise the recipe, fonts, selected photos and private fetcher.
    pdf,cover,manifest=render_artifacts(store,r)
    assert pdf.read_bytes().startswith(b'%PDF-') and pdf.stat().st_size>20000
    assert f'data-design="{design}"' in pdf_html(r,assets)
    destination,files=build_export(store,r,{'user_id':'traveler','created':0})
    assert f'data-design="{design}"'.encode() in files['index.html']
    assert b'book-designs.css' in files['index.html']
    verify(destination)


def test_recipe_is_immutable_and_changes_invalidate_exact_version_consent(tmp_path):
    root=Store(tmp_path);store=make_book(root,'paris');old=store.revision()
    revised=deepcopy(old['album']);revised['design']='quiet'
    job=store.job('Use a quiet photo book layout','change-style')
    store.commit(revised,job['id'],'replay',old['sources'])
    assert store.revision(old['version'])['album']['design']=='editorial'
    assert store.revision()['album']['design']=='quiet'
    tampered=deepcopy(old);tampered['album']['design']='urban'
    assert publication_digest(old)!=publication_digest(tampered)
    with pytest.raises(ValueError):
        from app.models import Album
        Album.model_validate({**old['album'],'design':'<script>alert(1)</script>'})
