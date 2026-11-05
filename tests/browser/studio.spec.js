const {test,expect} = require('@playwright/test');
// Keep automated UI checks independent of the public map tile service.
test.beforeEach(async({page})=>{
  await page.route('https://tile.openstreetmap.org/**',route=>route.abort());
});

test('book, evidence, memories, collaboration and privacy are usable', async ({page,request},testInfo) => {
  const state = await (await request.get('/api/state')).json();
  const trip=state.trip?.id;
  const album = state.revision.album;
  const photographs = new Set([album.cover_asset_id, ...album.chapters.flatMap(c => c.asset_ids)]);
  const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(trip ? '/?'+new URLSearchParams({trip}) : '/');
  await expect(page.locator('.cover-title')).toBeVisible();
  await expect(page.locator('#mode')).toHaveText(state.mode === 'live' ? 'LIVE AI' : 'REPLAY DEMO');
  await expect(page.locator('.chapter')).toHaveCount(album.chapters.length);
  for (const c of album.chapters) {
    if (c.source_ids.every(id => state.revision.sources.find(s => s.id === id)?.date_basis === 'posted')) {
      await expect(page.locator('#day-' + c.day + ' .chapter-date')).toContainText('PHOTO NOTE · POSTED');
      const photo = page.locator('#day-' + c.day + ' img').first();
      await photo.scrollIntoViewIfNeeded();
      await expect.poll(() => photo.evaluate(img => img.complete && img.naturalWidth > 0)).toBeTruthy();
    }
  }
  await page.locator('[data-evidence="0"]').click();
  await expect(page.locator('#panel')).toBeVisible();
  await expect(page.locator('.source-detail')).not.toHaveCount(0);
  await page.locator('#close-panel').click();
  await page.locator('[data-view="memories"]').click();
  await expect(page.locator('.memory-card')).toHaveCount(state.sources.length);
  await page.locator('[data-view="room"]').click();
  await expect(page.locator('.room-intro')).toContainText(state.mode === 'live' ? 'Storyteller uses Claude Code' : 'Real Switch communication');
  await expect(page.locator('.activity')).not.toHaveCount(0);
  await page.locator('[data-view="story"]').click();
  await page.locator('#edit-button').click();
  await page.locator('[data-cover-prompt]').click();
  await expect(page.locator('#edit-prompt')).toHaveValue(/photograph as the cover/);
  await page.locator('#close-panel').click();
  await page.locator('#publish-button').click();
  await expect(page.locator('#publish-command')).toContainText('I CONSENT TO PUBLIC PHOTOS AND TEXT');
  await expect(page.locator('#panel')).toContainText('cloud publishing is disabled');
  await page.locator('#close-panel').click();
  await page.locator('[data-book="photos"]').click();
  await expect(page.locator('.photo-grid img')).toHaveCount(photographs.size);
  await page.locator('[data-book="book"]').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
  await page.screenshot({path:`.runtime/${testInfo.project.name}-studio.png`,fullPage:true});
});

test('a completion link opens its saved version', async ({page,request}) => {
  const current=await (await request.get('/api/state')).json();
  const trip=current.trip?.id;
  const suffix=trip ? '?'+new URLSearchParams({trip}) : '';
  const versions = await (await request.get('/api/revisions'+suffix)).json();
  const version = versions[versions.length - 1].id;
  const snapshot = await (await request.get('/api/revisions/' + version + suffix)).json();
  await page.goto('/?'+new URLSearchParams({version,...(trip?{trip}:{})}));
  await expect(page.locator('#version-label')).toContainText('Version ' + version + ' · earlier draft');
  await expect(page.locator('.cover-title')).toHaveText(snapshot.album.title);
  await expect(page.locator('.cover > img')).toHaveAttribute('src', new RegExp(snapshot.album.cover_asset_id + '\\.jpg$'));
});
