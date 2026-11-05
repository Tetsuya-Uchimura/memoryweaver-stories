"""Refresh attributed Wikimedia samples; shipped JPEGs need no judge downloads."""
import hashlib,io,json,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from PIL import Image,ImageOps

FILES=[
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
  if not target.exists():
   request=urllib.request.Request(url,headers={'User-Agent':'MemoryWeaver educational licensed sample'})
   for attempt in range(4):
    try:
     with urllib.request.urlopen(request,timeout=90) as r,Image.open(io.BytesIO(r.read())) as im:
      im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2000,1600));im.save(target,quality=88)
     break
    except urllib.error.HTTPError as exc:
     if exc.code!=429 or attempt==3:raise
     print('Rate limit; retrying '+aid,flush=True);time.sleep(10*(attempt+1))
  credits.append(dict(id=aid,url='/static/assets/'+aid+'.jpg',label=title,sample=True,credit=author+' · '+lic+' · resized, metadata removed',source_url='https://commons.wikimedia.org/wiki/File:'+urllib.parse.quote(title),license_url='https://creativecommons.org/publicdomain/zero/1.0/' if path=='zero' else 'https://creativecommons.org/licenses/'+path+'/'))
  print('Ready',aid,flush=True)
 (root/'samples/world-assets.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
