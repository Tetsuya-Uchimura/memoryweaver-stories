"""Refresh attributed Wikimedia samples; shipped JPEGs need no judge downloads."""
import hashlib,io,json,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from PIL import Image,ImageOps

FILES=[
 ('santorini-oia','Blue Domed Church - Oia, Santorini, Greece - 20 July 2008.jpg','George M. Groutas','CC BY 2.0','by/2.0'),
 ('santorini-harbour','Santorini, Oia 01.jpg','LBM1948','CC BY-SA 4.0','by-sa/4.0'),
 ('santorini-caldera','Views of the caldera from Fira, 226497.jpg','Zde','CC BY-SA 4.0','by-sa/4.0'),
 ('santorini-beach','Perissa Beach and Mésa Vounó at sunset, May 2024.jpg','PCN02WPS','CC BY-SA 4.0','by-sa/4.0'),
 ('santorini-red-beach','Red Beach in Santorini.jpg','Anthony Baratier','CC BY-SA 4.0','by-sa/4.0'),
 ('santorini-sunset','Santorini Sunset.jpg','SofiaGMussolin','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-river','Togetsu-kyō bridge at golden hour, Kyoto, Japan.jpg','Basile Morin','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-gion','A view of Gion corner in Geisha district, Kyoto, Japan.jpg','Joli Rumi','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-hall','JAP Kyoto Kiyomizu-dera.jpg','Grueslayer @Wikipedia','CC BY-SA 4.0','by-sa/4.0'),
 ('paris-bridge','The Pont Alexandre III Paris.jpg','Martin Davison / EUtouring.com','CC BY-SA 4.0','by-sa/4.0'),
 ('paris-montmartre','Paris-Sacré-Cœur-106-2017-gje.jpg','Gerd Eichmann','CC BY-SA 4.0','by-sa/4.0'),
 ('paris-garden','Paris-Tuileries-110-2017-gje.jpg','Gerd Eichmann','CC BY-SA 4.0','by-sa/4.0'),
 ('paris-notre-dame','Notre-dame-de-paris.jpg','Nicolas barthe','CC BY-SA 4.0','by-sa/4.0'),
 ('new-york-square','The iconic Times square.jpg','Henrybermudez1','CC BY-SA 4.0','by-sa/4.0'),
 ('new-york-terminal','Grand Central Terminal, New York.jpg','Clément Bardot','CC BY-SA 4.0','by-sa/4.0'),
 ('new-york-terrace','Bethesda Terrace.jpg','Jon McIntosh','CC BY-SA 4.0','by-sa/4.0'),
 ('new-york-dumbo','Dumbo.jpg','Lingzhong93','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-gates','Fushimi Inari Taisha Torii entrance.jpg','Immanuelle','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-bamboo','Bamboo Grove, Arashiyama, Kyoto, Japan.jpg','Basile Morin','CC BY-SA 4.0','by-sa/4.0'),
 ('kyoto-temple','Kyoto from Kiyomizu-Dera.jpg','Ray in Manila','CC BY 2.0','by/2.0'),
 ('paris-tower','The Eiffel Tower from the Seine.jpg','DiscoA340','CC BY-SA 4.0','by-sa/4.0'),
 ('paris-louvre','Inside the Louvre Pyramid July 2025.jpg','Dmarcovitz','CC0','zero'),
 ('new-york-bridge','NYC Skyline Brooklyn Bridge.jpg','NYC Guru','CC BY-SA 4.0','by-sa/4.0'),
 ('new-york-park','Central Park - The Lake panorama (New York) (31368593058).jpg','VillageHero','CC BY-SA 2.0','by-sa/2.0'),
]

def main():
 root=Path(__file__).resolve().parents[1];credits=[]
 for aid,title,author,lic,path in FILES:
  target=root/'app/static/assets'/(aid+'.jpg')
  name=title.replace(' ','_');d=hashlib.md5(name.encode()).hexdigest()
  url='https://upload.wikimedia.org/wikipedia/commons/'+d[0]+'/'+d[:2]+'/'+urllib.parse.quote(name)
  thumbnail='https://upload.wikimedia.org/wikipedia/commons/thumb/'+d[0]+'/'+d[:2]+'/'+urllib.parse.quote(name)+'/1280px-'+urllib.parse.quote(name)
  if not target.exists():
   request=urllib.request.Request(url,headers={'User-Agent':'MemoryWeaver educational licensed sample'})
   for attempt in range(4):
    try:
     with urllib.request.urlopen(request,timeout=90) as r,Image.open(io.BytesIO(r.read())) as im:
      im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2000,1600));im.save(target,quality=88)
     break
    except urllib.error.HTTPError as exc:
     if exc.code!=429 or attempt==3:raise
     print('Rate limit; retrying thumbnail '+aid,flush=True)
     request=urllib.request.Request(thumbnail,headers={'User-Agent':'MemoryWeaver educational licensed sample'})
     time.sleep(10*(attempt+1))
  credits.append(dict(id=aid,url='/static/assets/'+aid+'.jpg',label=title,sample=True,credit=author+' · '+lic+' · resized, metadata removed',source_url='https://commons.wikimedia.org/wiki/File:'+urllib.parse.quote(title),license_url='https://creativecommons.org/publicdomain/zero/1.0/' if path=='zero' else 'https://creativecommons.org/licenses/'+path+'/'))
  print('Ready',aid,flush=True)
 (root/'samples/world-assets.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
