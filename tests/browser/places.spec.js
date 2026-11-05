const {test,expect}=require('@playwright/test');
test('English world journeys, sourced photo places and local map pins',async({page,request},testInfo)=>{
 const catalog=await (await request.get('/api/trips')).json();
 test.skip(!catalog.trips.length,'Requires world sample setup');
 const remote=[];page.on('request',r=>{if(!r.url().startsWith('http://localhost:8787'))remote.push(r.url());});
 for(const [trip,place] of [['kyoto','Fushimi Inari'],['paris','Eiffel Tower'],['new-york','Brooklyn Bridge']]) {
  await page.goto('/?'+new URLSearchParams({trip}));
  await expect(page.locator('#trip-select')).toHaveValue(trip);
  await expect(page.locator('.cover-title')).toBeVisible();
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

test('legacy unqualified completion links retain the old private edition',async({page,request})=>{
 const catalog=await(await request.get('/api/trips')).json();
 test.skip(!catalog.legacy,'Fresh installations do not contain legacy data');
 const s=await(await request.get('/api/state?trip='+catalog.legacy)).json();
 await page.goto('/?version='+s.revision.version);
 await expect(page.locator('#trip-select')).toHaveValue(catalog.legacy);
 await expect(page.locator('.cover-title')).toHaveText(s.revision.album.title);
});
