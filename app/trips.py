"""Independent books/databases per private Switch room; legacy data stays intact."""
from pathlib import Path
import re
from app.store import Store


def catalog(root):
    return root.get('trips',[])


def trip_store(root,trip=None):
    trips=catalog(root)
    if not trips:
        if trip:raise ValueError('Unknown trip')
        return root
    trip=trip or root.get('default_trip','kyoto')
    item=next((t for t in trips if t['id']==trip),None)
    if not item or not re.fullmatch('[a-z][a-z-]{0,50}',trip):raise ValueError('Unknown trip')
    if item.get('legacy'):return root
    return Store(root.root/'trips'/trip)


def summary(root):
    return [dict(**t,version=(trip_store(root,t['id']).revision() or {}).get('version'),mode=(trip_store(root,t['id']).revision() or {}).get('mode')) for t in catalog(root)]
