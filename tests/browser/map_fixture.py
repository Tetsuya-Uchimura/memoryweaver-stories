"""Isolated fictional map books; never touch the running studio's data volume."""
import json
from pathlib import Path
import runpy
import tempfile

from app.store import Store
from agents.publish import build_export

Path('.runtime/maps').mkdir(parents=True, exist_ok=True)
directory = tempfile.mkdtemp(prefix='browser-', dir='.runtime/maps')
root = Store(Path(directory))
make_book = runpy.run_path('tests/test_places_trips.py')['make_book']
states = {}
exports = {}
for tid in ['kyoto', 'paris', 'new-york', 'santorini']:
    store = make_book(root, tid)
    revision = store.revision()
    states[tid] = dict(revision=revision, sources=store.all('sources'), assets=store.all('assets'),
                       events=[], agents=[], mode='replay', runtime='docker', trip=store.get('trip'),
                       mattermost_url='http://localhost:8065', publishing_enabled=False, publication=None)
    destination, _ = build_export(store, revision, {'user_id': 'fictional-traveler', 'created': 0})
    exports[tid] = str(destination.resolve())
print(json.dumps(dict(directory=str(Path(directory).resolve()), states=states, exports=exports)))
