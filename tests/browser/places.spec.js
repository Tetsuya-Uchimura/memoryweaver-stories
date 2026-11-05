const {test,expect}=require('@playwright/test');
test.beforeEach(async({page})=>{
 // Exercise offline fallback without downloading public tiles in automated tests.
 await page.route('https://tile.openstreetmap.org/**',route=>route.abort());
});
test('English world journeys, sourced photo places and local map pins',async({page,request},testInfo)=>{
 const catalog=await (await request.get('/api/trips')).json();
 test.skip(!catalog.trips.length,'Requires world sample setup');
 const remote=[];page.on('request',r=>{if(!r.url().startsWith('http://localhost:8787')&&!r.url().startsWith('https://tile.openstreetmap.org/'))remote.push(r.url());});
 for(const [trip,place] of [['kyoto','Fushimi Inari'],['paris','Eiffel Tower'],['new-york','Brooklyn Bridge'],['santorini','Oia']]) {
  await page.goto('/?'+new URLSearchParams({trip}));
  await expect(page.locator('#trip-select')).toHaveValue(trip);
  await expect(page.locator('.cover-title')).toBeVisible();
  await expect(page.locator('.book')).toHaveAttribute('data-design',({kyoto:'quiet',paris:'editorial','new-york':'urban',santorini:'coastal'})[trip]);
  expect(await page.locator('.chapter img').count()).toBeGreaterThanOrEqual(6);
  await expect(page.locator('.journey-places')).toContainText(place);
  await expect(page.locator('.photo-place').first()).toContainText('Fictional sample');
  await expect(page.locator('.location-sketch')).toBeVisible();
  await page.locator('[data-map-stop="0"]').click();
  await expect(page.locator('#place-0')).toHaveClass(/selected-place/);
  await expect(page.locator('#place-0 a')).toHaveAttribute('href',/https:\/\/www.openstreetmap.org\//);
  const photos=page.locator('.chapter img');
  for(let i=0;i<await photos.count();i++){
   await photos.nth(i).scrollIntoViewIfNeeded();
   await expect.poll(()=>photos.nth(i).evaluate(im=>im.complete&&im.naturalWidth>0)).toBeTruthy();
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:`.runtime/${testInfo.project.name}-${trip}-places.png`,fullPage:true});
 }
 expect(remote).toEqual([]);
});

test('judge library contains four English journals and no retired book',async({page,request})=>{
 const catalog=await(await request.get('/api/trips')).json();
 expect(catalog.trips.map(t=>t.id)).toEqual(['kyoto','paris','new-york','santorini']);
 expect(catalog.legacy).toBeNull();
 expect(catalog.trips.every(t=>t.language==='en')).toBeTruthy();
 const removed=await request.get('/api/state?trip=retired');
 expect(removed.status()).toBe(404);
 await page.goto('/?trip=santorini');
 await expect(page.locator('.book')).toHaveAttribute('data-design','coastal');
 await page.locator('[data-view="room"]').click();
 expect(await page.locator('.activity-list').innerText()).not.toMatch(/[\u3040-\u30ff\u3400-\u9fff]/);
});
