"""Location provenance: explicit human annotations and optional photo GPS only."""
from __future__ import annotations
import math
import re
from urllib.parse import urlencode
from app.models import Place

ANNOTATION = re.compile(r'^\[(Sample location|Location):\s*([^\]|]+?)(?:\s*\|\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?))?\]\s*$', re.M | re.I)


def parse_location(text):
    matches=list(ANNOTATION.finditer(text))
    if not matches:return text,None
    if len(matches)!=1:raise ValueError('Use one location annotation per memory post')
    m=matches[0]
    place=Place(name=m[2].strip(),latitude=float(m[3]) if m[3] else None,longitude=float(m[4]) if m[4] else None,basis='sample' if m[1].lower().startswith('sample') else 'stated')
    return ANNOTATION.sub('',text).strip(),place.model_dump()


def exif_location(image):
    try:
        gps=image.getexif().get_ifd(34853)
        if not gps:return None
        def coord(values,ref):
            d,m,s=map(float,values)
            if not all(math.isfinite(v) for v in [d,m,s]) or d<0 or not 0<=m<60 or not 0<=s<60:raise ValueError('Invalid GPS')
            return round((d+m/60+s/3600)*(-1 if ref in ['S','W',b'S',b'W'] else 1),6)
        lat=coord(gps[2],gps[1]);lon=coord(gps[4],gps[3])
        if gps[1] not in ['N','S',b'N',b'S'] or gps[3] not in ['E','W',b'E',b'W']:return None
        return Place(name='Photo GPS',latitude=lat,longitude=lon,basis='gps').model_dump()
    except (OSError,SyntaxError,ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError):return None


def map_url(place):
    p=Place.model_validate({k:v for k,v in place.items() if k!="source_id"})
    if p.latitude is None:return 'https://www.openstreetmap.org/search?'+urlencode({'query':p.name})
    return 'https://www.openstreetmap.org/?'+urlencode({'mlat':p.latitude,'mlon':p.longitude})+'#map=15/'+str(p.latitude)+'/'+str(p.longitude)


def snapshot_locations(sources,assets,selected):
    by_asset={};stops=[]
    for source in sources:
        place=source.get('location')
        if place:
            place=Place.model_validate(place).model_dump()
            stops.append(dict(**place,source_id=source['id']))
        for aid in source['asset_ids']:
            if aid not in selected:continue
            location=place or assets.get(aid,{}).get('location')
            if location:
                by_asset[aid]=Place.model_validate(location).model_dump()
                if not place:stops.append(dict(**by_asset[aid],source_id=source['id']))
    return stops,by_asset
