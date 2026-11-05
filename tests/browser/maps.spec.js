const {test,expect}=require('@playwright/test');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
let fixture;
test.beforeAll(()=>{
  const python=process.env.TEST_PYTHON || '.venv/bin/python';
  fixture=JSON.parse(execFileSync(python,['-m','tests.browser.map_fixture'],{encoding:'utf8'}));
});
test.afterAll(()=>{if(fixture)fs.rmSync(fixture.directory,{recursive:true,force:true});});
async function studio(page,trip='kyoto',modify=()=>{}) {
  const state=structuredClone(fixture.states[trip]);modify(state);
  await page.route('**/api/trips',r=>r.fulfill({json:{trips:Object.entries(fixture.states).map(([id,s])=>({...s.trip,version:1,mode:'replay'})),default:trip,legacy:null}}));
  await page.route('**/api/state?*',r=>r.fulfill({json:state}));
  await page.route('**/api/events?*',r=>r.fulfill({body:'',contentType:'text/event-stream'}));
  await page.goto('/?'+new URLSearchParams({trip}));
  await expect(page.locator('.cover-title')).toBeVisible();
  return state;
}
async function tiles(page,fail=false) {
  const requests=[];
  // Never exercise the public tile service in an automated test.
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
  await page.route('https://tile.openstreetmap.org/**',r=>{
    requests.push(r.request());return fail?r.abort():r.fulfill({body:png,contentType:'image/png'});
  });
  return requests;
}
for(const trip of ['kyoto','paris','new-york','santorini']) {
  test(`${trip}: street map loads automatically and connects places to photographs`,async({page},info)=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const requests=await tiles(page);await studio(page,trip);
    const map=page.locator('[data-journey-map]');
    await expect(map).toHaveAttribute('data-map-state','ready');
    await expect(map.locator('.map-load')).toBeHidden();
    expect(await page.evaluate(()=>scrollY)).toBe(0);
    await expect(map.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
    const expectedPins=await map.evaluate(el=>JSON.parse(el.dataset.mapStops).filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)).length);
    await expect(map.locator('.journey-map-marker')).toHaveCount(expectedPins);
    expect(requests.length).toBeGreaterThan(0);
    expect(requests.every(r=>r.headers().referer==='http://localhost:8787/')).toBeTruthy();
    await expect(map.locator('.leaflet-tile').first()).toHaveAttribute('referrerpolicy','origin');
    await map.locator('.street-map').scrollIntoViewIfNeeded();
    // Close landmarks can overlap at the overview scale; click a visible pin,
    // then use the place controls to verify access to every exact location.
    const visiblePin=await map.locator('.journey-map-marker').evaluateAll(nodes=>nodes.findIndex(n=>{
      const r=n.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===n;
    }));
    expect(visiblePin).toBeGreaterThanOrEqual(0);
    await map.locator('.journey-map-marker').nth(visiblePin).click();
    await expect(map.locator('.leaflet-popup-content')).toContainText('Fictional sample');
    const photo=map.locator('.map-photo-popup img').first();
    await expect(photo).toBeVisible();
    await expect.poll(()=>photo.evaluate(im=>im.complete&&im.naturalWidth>0)).toBeTruthy();
    const places=await map.evaluate(el=>JSON.parse(el.dataset.mapStops));
    for(let i=0;i<places.length;i++){
      await page.locator(`#place-${i} [data-show-map]`).click();
      await expect(map.locator('.map-photo-popup h3')).toHaveText(places[i].name);
      await expect(page.locator(`#place-${i}`)).toHaveClass(/selected-place/);
    }
    await map.locator('.map-reset').click();
    await page.locator('#read-button').click();
    await expect(map.locator('.street-map')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:`.runtime/maps/${info.project.name}-${trip}.png`,fullPage:false});
    await map.locator('.map-hide').click();
    await expect(map.locator('.location-sketch')).toBeVisible();
    await expect(map).toHaveAttribute('data-map-state','idle');
    await expect(map.locator('.street-map')).toBeHidden();
    await map.locator('.map-load').click();
    await expect(map).toHaveAttribute('data-map-state','ready');
    expect(errors).toEqual([]);
  });
}
test('photo view returns to an automatically loaded map at the right place',async({page})=>{
  const requests=await tiles(page);await studio(page);
  await page.locator('[data-book="photos"]').click();
  const button=page.locator('[data-photo-map]').last();const index=await button.getAttribute('data-photo-map');
  await button.click();await expect(page.locator('.book')).toBeVisible();
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','ready');
  expect(requests.length).toBeGreaterThan(0);
  await expect(page.locator(`#place-${index}`)).toHaveClass(/selected-place/);
  await expect(page.locator('.map-photo-popup img').first()).toBeVisible();
});
test('failed tiles retain local coordinates and allow retry',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await tiles(page,true);await studio(page);
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','error');
  await expect(page.locator('.location-sketch')).toBeVisible();
  await expect(page.locator('.map-status')).toContainText('could not be loaded');
  await page.unroute('https://tile.openstreetmap.org/**');await tiles(page);
  await page.getByRole('button',{name:'Retry street map'}).click();
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','ready');
  expect(errors).toEqual([]);
});
test('name-only locations stay un-geocoded',async({page})=>{
  const requests=await tiles(page);
  await studio(page,'kyoto',state=>{
    state.revision.places=[{name:'A place supplied without coordinates',basis:'stated',latitude:null,longitude:null}];
    state.revision.photo_locations={};
  });
  await expect(page.locator('.journey-places')).toContainText('A place supplied without coordinates');
  await expect(page.locator('[data-journey-map]')).toHaveCount(0);expect(requests).toHaveLength(0);
});
test('single GPS pin, date line, and untrusted popup text are safe',async({page})=>{
  await tiles(page);
  const hostile='Place <img src=x onerror=alert(1)>';
  await studio(page,'kyoto',state=>{
    const a={name:hostile,basis:'gps',latitude:20,longitude:179.9};
    const b={name:'Across the date line',basis:'stated',latitude:20,longitude:-179.9};
    state.revision.places=[a,b];state.revision.photo_locations={'kyoto-gates':a};
  });
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','ready');
  const positions=await page.locator('.journey-map-marker').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().x));
  expect(Math.abs(positions[0]-positions[1])).toBeLessThan(800);
  await page.locator('.street-map').scrollIntoViewIfNeeded();
  await page.locator('.journey-map-marker').first().click();
  await expect(page.locator('.map-photo-popup h3')).toHaveText(hostile);
  await expect(page.locator('.map-photo-popup h3 img')).toHaveCount(0);
  await page.locator('.map-hide').click();
  await page.evaluate(()=>{
    const root=document.querySelector('[data-journey-map]');
    MemoryWeaverMap.destroy(root);root.innerHTML='';
    root.dataset.mapStops=JSON.stringify([{name:'One GPS photo',latitude:35,longitude:135,basis:'gps',photos:[{url:'https://private.example/photo.jpg'}]}]);
    MemoryWeaverMap.mount(root);
  });
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','ready');
  await expect(page.locator('.journey-map-marker')).toHaveCount(1);
  await page.locator('.street-map').scrollIntoViewIfNeeded();
  await page.locator('.journey-map-marker').click();
  await expect(page.locator('.map-photo-popup')).toContainText('place name unverified');
  await expect(page.locator('.map-photo-popup img')).toHaveCount(0);
});
test('approved static export automatically loads its map under its strict CSP',async({page})=>{
  const requests=await tiles(page),root=fixture.exports.kyoto;
  const csp=fs.readFileSync(path.join(root,'_headers'),'utf8').split('Content-Security-Policy: ')[1].trim();
  const types={'.js':'text/javascript','.css':'text/css','.html':'text/html','.jpg':'image/jpeg','.png':'image/png'};
  await page.route('**/map-export/**',r=>{
    const file=new URL(r.request().url()).pathname.replace('/map-export/','')||'index.html';
    if(file.includes('..'))return r.abort();
    return r.fulfill({body:fs.readFileSync(path.join(root,file)),contentType:types[path.extname(file)]||'text/plain',headers:{'Content-Security-Policy':csp,'Referrer-Policy':'no-referrer'}});
  });
  await page.goto('/map-export/index.html');
  await expect(page.locator('[data-journey-map]')).toHaveAttribute('data-map-state','ready');
  expect(requests.length).toBeGreaterThan(0);
  expect(await page.evaluate(()=>scrollY)).toBe(0);
  await page.locator('.street-map').scrollIntoViewIfNeeded();
  await page.locator('.journey-map-marker').first().click();
  const photo=page.locator('.map-photo-popup img').first();
  await expect.poll(()=>photo.evaluate(im=>im.complete&&im.naturalWidth>0)).toBeTruthy();
});
