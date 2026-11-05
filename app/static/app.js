const $ = (selector) => document.querySelector(selector);
const esc = (value = '') => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {collector:'Collector',storyteller:'Storyteller',editor:'Editor',publisher:'Publisher'};
const symbols = {collector:'⌘',storyteller:'✧',editor:'✎',publisher:'↗'};
const jobs = {collector:'Gathers the little things',storyteller:'Finds the words',editor:'Shapes the story',publisher:'Makes it yours to keep'};
let currentTrip=null, availableTrips=[];
const tripAPI=path=>path+(currentTrip ? (path.includes("?")?"&":"?")+new URLSearchParams({trip:currentTrip}) : "");
let state = null, view = 'story', bookView = 'book', pinned = null, lastRender = '', stream;
const panel = $('#panel');
const asset = (id) => state?.assets.find(a => a.id === id);
const photoURL = (id) => {
  const url = asset(id)?.url || '/static/assets/coast.jpg';
  return /^\/(?:static\/assets\/[a-z-]+\.jpg|media\/(?:trips\/[a-z-]+\/)?[a-f0-9]+\.jpg)$/.test(url) ? url : '/static/assets/coast.jpg';
};
const date = (v) => new Date(v).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
const selected = () => pinned || state?.revision;
const chapterLabel = (chapter, revision) => chapter.source_ids.every(id => revision.sources.find(s => s.id === id)?.date_basis === 'posted') ? 'PHOTO NOTE · POSTED' : 'DAY ' + chapter.day;

function dialog(label, html) {
  $('#panel-label').textContent = label;
  $('#panel-content').innerHTML = html;
  if (!panel.open) panel.showModal();
}
function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('show');
  setTimeout(() => $('#toast').classList.remove('show'), 3000);
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Copied. Your next chapter starts in Mattermost.'); }
  catch { toast('Select and copy the text shown in the dialog.'); }
}
function gettingStarted() {
  dialog('A LITTLE HELP GETTING STARTED', `<h2>Bring your memories.<br>We’ll find the thread.</h2><p>Share photographs and small memories in your trip’s private Mattermost channel. Your teammates use Switch to turn them into a book.</p><h3>1 · Choose your journey</h3><p>Explore Kyoto, Paris or New York with the journal selector. Each has its own conversation, photographs and versions. The fictional starter books are labeled Replay Demo.</p><h3>2 · Make it yours</h3><p>After connecting your providers using the README, ask in Mattermost: “@mw-collector Create an English travel journal from our memories. Keep the photos and supplied locations.” Live editions use your authenticated Claude Code and Codex sessions.</p><h3>3 · Keep the places too</h3><p>GPS-equipped photographs can supply coordinates. You can also share a place name with a memory. Missing places stay unknown; sample pins are explicitly fictional.</p><p>Publisher sends your book link, cover preview and PDF back to the same channel. Ask for a new cover or revise the wording whenever you like.</p><a class="primary" href="${esc(state?.mattermost_url || 'http://localhost:8065')}" target="_blank" rel="noopener">Open this trip in Mattermost ↗</a>`);
}
function edit() {
  const cover=selected()?.album.cover_asset_id || '';
  const subject=state?.trip?.id==='kyoto' ? (cover==='kyoto-bamboo'?'shrine gates':'bamboo grove') : state?.trip?.id==='paris' ? (cover==='paris-louvre'?'Eiffel Tower':'Louvre') : state?.trip?.id==='new-york' ? (cover==='new-york-park'?'Brooklyn Bridge':'Central Park') : 'sunset';
  const coverPrompt=`Please use the ${subject} photograph as the cover. Keep the other photos, memories and supplied locations.`;
  dialog('HUMAN WORDS. SHARED CREATIVITY.', `<h2>What would you like to change?</h2><p>Tell your team in your own words. They’ll revisit the source memories, share a draft, and check it before updating your preview.</p><textarea id="edit-prompt" aria-label="Your editing instruction" placeholder="For example, make day two more heartfelt without adding new events…"></textarea><div class="suggestions"><button data-cover-prompt data-prompt="${esc(coverPrompt)}">A different cover</button><button data-prompt="Make day two more heartfelt, using only the original memories.">A more heartfelt day two</button><button data-prompt="Include everyone’s original words without inventing quotes.">Include everyone’s words</button></div><button class="primary" id="copy-edit">Copy instruction for Mattermost ↗</button><p>The instruction is copied for you to send in Mattermost. Your conversation and the agents’ work stay visible to the whole team.</p><a class="text-button" href="${esc(state?.mattermost_url || 'http://localhost:8065')}" target="_blank" rel="noopener">Open Mattermost ↗</a>`);
  $('#copy-edit').onclick = () => {
    const prompt = $('#edit-prompt').value.trim();
    if (!prompt) return $('#edit-prompt').focus();
    copy('@mw-collector ' + prompt);
  };
  panel.querySelectorAll('[data-prompt]').forEach(b => b.onclick = () => { $('#edit-prompt').value = b.dataset.prompt; });
}
function evidence(index) {
  const revision = selected();
  const chapter = revision.album.chapters[index];
  const sources = revision.sources.filter(s => chapter.source_ids.includes(s.id));
  dialog('A STORY WITH ROOTS', `<h2>The memories behind this chapter</h2><p>These are the original words used to write “${esc(chapter.title)}”. Quotes are checked word for word. AI prose still deserves your review.</p>${sources.map(s => `<div class="source-detail"><strong>${esc(s.author)} · ${esc(date(s.captured_at))}${s.date_basis === 'posted' ? ' · posted; capture date unknown' : ''}</strong><p>${esc(s.text)}</p><small>${s.asset_ids.length} photograph${s.asset_ids.length !== 1 ? 's' : ''} · Source ${esc(s.id.slice(0, 16))}</small></div>`).join('')}`);
}
function credits() {
  dialog('THE PEOPLE BEHIND THE PICTURES', `<h2>A note on this little journey.</h2><p>The October 12–14, 2026 family trip is fictional sample data. These licensed photographs illustrate the experience; they are not pictures of the sample family or proof of their itinerary. Local uploads stay on your machine until you explicitly approve publication.</p>${state.assets.filter(a => a.sample).map(a => `<div class="credit-item"><strong>${esc(a.label)}</strong><p class="photo-credit">${esc(a.credit)}</p><a href="${esc(a.source_url)}" target="_blank" rel="noopener">Original photograph ↗</a> · <a href="${esc(a.license_url)}" target="_blank" rel="noopener">License ↗</a></div>`).join('')}<p>MemoryWeaver · Turn Scattered Memories into Beautiful Stories.<br>Built for Flip the Switch · Personal &amp; Creative Workflow.</p>`);
}
async function digest(revision) {
  // Server provides the canonical digest through an authenticated-free read endpoint.
  const r = await fetch(tripAPI('/api/revisions/' + revision.version + '/publication'));
  if (!r.ok) throw new Error('Unable to load publication manifest');
  return r.json();
}
async function publish() {
  const revision = selected();
  if (!revision) return gettingStarted();
  try {
    const manifest = await digest(revision);
    dialog('YOUR PERMISSION. YOUR STORY.', `<h2>Ready to let this story travel?</h2><p>Review every chapter, quotation, and photograph in <strong>version ${revision.version}</strong>. Sending the command below from the configured traveler account consents to making this exact book’s text and selected photographs public on GitHub and Cloudflare Pages.</p><p><strong>${state.publishing_enabled ? 'Cloud publishing is enabled. This command can publish a public website.' : 'Local judging mode: cloud publishing is disabled. Approval creates a local export only.'}</strong></p><h3>Selected photographs</h3><p>${manifest.asset_ids.map(id => esc(asset(id)?.label || id)).join('<br>')}</p><code id="publish-command">${esc(manifest.command)}</code><button id="copy-publish" class="primary">Copy exact-version approval command</button><p>Review this command, then send it yourself in Mattermost. Future edits need a fresh approval. The location names and coordinates shown in this edition will also be included if you approve. Raw conversation logs and unused photographs are excluded.</p>`);
    $('#copy-publish').onclick = () => copy(manifest.command);
  } catch { toast('Could not load the approval manifest. Please try again.'); }
}
async function history() {
  try {
    const versions = await (await fetch(tripAPI('/api/revisions'))).json();
    dialog('EVERY CHAPTER OF THE PROCESS', `<h2>Your story, over time.</h2><p>Each edit keeps the earlier version. Viewing an old version does not change the latest draft or its publication approval.</p>${versions.length ? versions.map(v => `<div class="version-row"><span>Version ${v.id} · ${new Date(v.created * 1000).toLocaleString()}</span><button data-version="${v.id}">Read</button></div>`).join('') : '<p>Your first version is waiting to be woven.</p>'}<button id="latest-version" class="primary">Return to the latest version</button>`);
    panel.querySelectorAll('[data-version]').forEach(b => b.onclick = async () => { pinned = await (await fetch(tripAPI('/api/revisions/' + b.dataset.version))).json(); panel.close(); renderStory(); });
    $('#latest-version').onclick = () => { pinned = null; panel.close(); renderStory(); };
  } catch { toast('Version history is temporarily unavailable.'); }
}
function renderStory() {
  const r = selected();
  const el = $('#view-story');
  if (!r) {
    el.innerHTML = `<div class="empty-cover"><img src="/static/assets/kyoto-gates.jpg" alt="Kyoto shrine gates, a licensed illustrative photograph"><div class="empty-message"><div class="eyebrow">YOUR NEXT CHAPTER STARTS HERE</div><h2>A little scattered.<br>A little unforgettable.</h2><p>Photos in one place. Words in another.<br>Let’s turn the moments you kept<br>into a story you’ll come back to.</p><button class="primary" id="start-button">✧ &nbsp; Weave your first story &nbsp; ↗</button><small>PRIVATE BY DEFAULT · MADE TOGETHER THROUGH SWITCH</small></div></div>`;
    $('#start-button').onclick = gettingStarted;
    return;
  }
  $('#version-label').textContent = `Version ${r.version}${pinned ? ' · earlier draft' : ' · saved locally'}`;
  const a = r.album;
  if (bookView === 'photos') {
    const ids = [...new Set([a.cover_asset_id, ...a.chapters.flatMap(c => c.asset_ids)])];
    el.innerHTML = `<div class="photo-grid">${ids.map(id => `<figure><img src="${photoURL(id)}" alt="${esc(asset(id)?.label || 'Travel photograph')}" loading="lazy"><figcaption>${esc(asset(id)?.label)}${photoLocation(id,r)}<br><span class="photo-credit">${esc(asset(id)?.credit)}</span></figcaption></figure>`).join('')}</div>`;
    return;
  }
  el.innerHTML = `<article class="book" aria-label="Your travel story"><section class="cover"><img src="${photoURL(a.cover_asset_id)}" alt="${esc(asset(a.cover_asset_id)?.label || 'Travel journal cover')}"><div class="cover-top"><span>A MEMORYWEAVER TRAVEL JOURNAL</span><span class="cover-seal">✳</span></div><div class="cover-content"><div class="cover-location">${esc(a.location)}</div><h2 class="cover-title">${esc(a.title)}</h2><div class="cover-subtitle">${esc(a.subtitle)}</div><div class="cover-bottom"><strong>${esc(a.date_label)}</strong><span>A journey, woven together.</span></div></div></section><div class="book-caption"><span>VOL. 01 &nbsp; / &nbsp; ${a.chapters.length} CHAPTERS &nbsp; / &nbsp; ${r.mode.toUpperCase()} EDITION</span><span class="caption-note">Little moments. Lasting memories.</span></div><section class="intro"><div class="ornament">❧</div><div class="eyebrow">THE PLACES WE WENT. THE WORDS WE KEPT.</div><h2>Let the journey unfold.</h2><p>The places we found. The words we kept.<br>Small moments, woven into a story that stays with us.</p><div class="journey-index">${a.chapters.map(c => `<a href="#day-${c.day}"><span>${String(c.day).padStart(2,'0')}</span> ${chapterLabel(c, r)}</a>`).join('')}</div></section>${renderJourney(r)}${a.chapters.map((c, i) => `<section class="chapter" id="day-${c.day}"><div class="chapter-heading"><span class="chapter-number">${String(c.day).padStart(2,'0')}</span><div><div class="chapter-date">${chapterLabel(c, r)} &nbsp; · &nbsp; ${esc(date(c.date))}</div><h2>${esc(c.title)}</h2></div></div><div class="chapter-layout">${c.asset_ids.length ? `<div class="chapter-images">${c.asset_ids.map(id => `<figure><img src="${photoURL(id)}" alt="${esc(asset(id)?.label || 'Travel photograph')}" loading="lazy"><figcaption>${photoLocation(id,r)}${esc(asset(id)?.credit || '')}</figcaption></figure>`).join('')}</div>` : ''}<div class="chapter-prose"><p>${esc(c.body)}</p>${c.quote ? `<blockquote>「${esc(c.quote)}」</blockquote>` : ''}<button class="evidence-button" data-evidence="${i}">↗ &nbsp; Woven from ${c.source_ids.length} original memories</button></div></div></section>`).join('')}<div class="book-end"><span class="weave">✳</span><p>Some journeys stay with us.</p><small>TO BE CONTINUED, TOGETHER.</small><div class="sample-label">${r.mode === 'replay' ? 'EXTRACTIVE REPLAY · NO LIVE AI GENERATION' : 'CREATED WITH CLAUDE CODE & CODEX · HUMAN REVIEW ENCOURAGED'}</div></div></article><div class="under-book"><span><i class="little-dot"></i> Woven with ${new Set(r.sources.map(s => s.author)).size} contributors &amp; four creative teammates</span><span>✧ &nbsp; A little human. A little AI. Entirely yours.</span></div><div class="publication-notice"><span>${state.publication?.url ? 'This story has a published edition.' : 'Your story is private. Share it only when it feels right.'}</span><button class="text-button" id="publish-button">Review publication ↗</button></div>`;
  bindJourney();
  el.querySelectorAll('[data-evidence]').forEach(b => b.onclick = () => evidence(Number(b.dataset.evidence)));
  $('#publish-button').onclick = publish;
}
function renderMemories() {
  $('#memory-count').textContent = state.sources.length;
  $('#view-memories').innerHTML = `<div class="inbox-heading"><div><h2>The little things you kept.</h2><p>Original words and photographs, ordered by capture date. Nothing has to arrive in order.</p></div><span class="tag">${state.sources.length} MEMORIES</span></div><div class="memory-grid">${state.sources.map(s => `<article class="memory-card">${s.asset_ids.map(id => `<img src="${photoURL(id)}" alt="${esc(asset(id)?.label)}" loading="lazy">`).join('')}<div class="source-author"><strong>${esc(s.author)}</strong><span>${esc(date(s.captured_at))}${s.date_basis === 'posted' ? ' · posted' : ''}</span></div><p>${esc(s.text)}</p><span class="tag">ORIGINAL MEMORY</span></article>`).join('')}</div>${state.sources.length ? '' : '<p class="no-records">Every story begins with a little something. Post a memory in Mattermost.</p>'}`;
}
function renderRoom() {
  $('#view-room').innerHTML = `<div class="room-intro"><div class="eyebrow">ONE ROOM. A SHARED THREAD.</div><h2>Good stories are made together.</h2><p>Real events from your Switch-connected collaborators. Shared room documents carry the evidence, draft, and editorial review between teammates.</p><div class="flow"><span>You + Mattermost</span><i>↔</i><span>Switch room</span><i>↔</i><span>Four teammates</span><i>↗</i><span>Your story</span></div><p>${state.mode === 'replay' ? 'REPLAY DEMO · Real Switch communication, deterministic writing. No live model calls.' : 'LIVE AI · Storyteller uses Claude Code. Editor uses Codex. Collector and Publisher use deterministic tools.'}</p></div><div class="activity-list">${[...state.events].reverse().map(e => `<article class="activity ${esc(e.kind)}"><span class="avatar ${esc(e.role)}">${symbols[e.role] || '✧'}</span><div><h3>${esc(names[e.role] || e.role)} <span class="tag">${esc(e.kind)}</span></h3><p>${esc(e.message)}</p></div><time>${new Date(e.created * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</time></article>`).join('')}</div>${state.events.length ? '' : '<p class="no-records">Your team is ready. Share a memory and start a conversation.</p>'}`;
}
function render(next) {
  state = next;
  $('#trip-breadcrumb').textContent=next.trip?.label || 'Your travel journal';
  $('#mode').textContent = next.mode === 'live' ? 'LIVE AI' : 'REPLAY DEMO';
  $('#mode').classList.toggle('live', next.mode === 'live');
  $('#agent-list').innerHTML = next.agents.map(a => `<div class="agent-row"><span class="avatar ${a.role}">${symbols[a.role]}</span><span><strong>${names[a.role]}</strong><small>${a.status === 'console' ? esc(a.name) + ' · Console' : jobs[a.role]}</small></span><i class="presence ${a.status === 'connected' && Date.now()/1000 - a.at < 12 ? 'online' : ''}" title="${esc(a.status)}"></i></div>`).join('');
  const online = next.agents.filter(a => a.status === 'connected' && Date.now()/1000 - a.at < 12).length;
  $('#connection-label').textContent = next.runtime === 'console' ? `${online}/2 tool agents connected · 2 Console-managed agents` : `${online}/4 teammates connected · ${next.mode === 'live' ? 'live AI' : 'replay demo'}`;
  const key = JSON.stringify([next.revision, next.assets, next.publication]);
  if (key !== lastRender) { renderStory(); lastRender = key; }
  renderMemories(); renderRoom();
}
function changeView(next) {
  view = next;
  for (const name of ['story','memories','room']) $('#view-' + name).classList.toggle('hidden', name !== view);
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $('.story-toolbar').classList.toggle('hidden', view !== 'story');
  $('#page-title').innerHTML = ({story:'A story worth keeping<span>.</span>',memories:'Small moments. Big feelings<span>.</span>',room:'A shared thread<span>.</span>'})[view];
  $('#page-description').textContent = ({story:'Your memories, thoughtfully woven together.',memories:'A place for every photograph, every word, every one of you.',room:'People and AI teammates, making something meaningful.'})[view];
}
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => changeView(b.dataset.view));
document.querySelectorAll('[data-book]').forEach(b => b.onclick = () => { bookView = b.dataset.book; document.querySelectorAll('[data-book]').forEach(x => x.classList.toggle('selected', x === b)); renderStory(); });
$('#help').onclick = gettingStarted; $('#edit-button').onclick = edit; $('#credits-button').onclick = credits;
$('#history-button').onclick = history; $('#close-panel').onclick = () => panel.close();
panel.addEventListener('click', e => { if (e.target === panel) { const r = panel.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) panel.close(); } });
$('#read-button').onclick = () => { document.body.classList.toggle('reading'); $('#read-button').textContent = document.body.classList.contains('reading') ? '← Back to studio' : 'Reading mode ↗'; };
async function connect() {
  try {
    const catalog=await (await fetch('/api/trips')).json();
    availableTrips=catalog.trips;
    const params=new URLSearchParams(location.search);
    currentTrip=params.get('trip') || (params.get('version') && catalog.legacy ? catalog.legacy : catalog.default);
    $('#trip-select').innerHTML=availableTrips.length ? availableTrips.map(t=>`<option value="${esc(t.id)}">${esc(t.label)}${t.mode ? ' · '+t.mode.toUpperCase() : ''}</option>`).join('') : '<option>Your journal</option>';
    if(currentTrip)$('#trip-select').value=currentTrip;
    $('#trip-select').onchange=()=>{location.href='/?'+new URLSearchParams({trip:$('#trip-select').value});};
    const r = await fetch(tripAPI('/api/state')); if (!r.ok) throw new Error();
    const version = new URLSearchParams(location.search).get('version');
    if (version && /^[1-9]\d*$/.test(version)) {
      const snapshot = await fetch(tripAPI('/api/revisions/' + version));
      if (snapshot.ok) pinned = await snapshot.json();
      else toast('This book version could not be found. Showing the latest version.');
    }
    render(await r.json());
    stream = new EventSource(tripAPI('/api/events'));
    stream.onmessage = e => render(JSON.parse(e.data));
    stream.onerror = () => { $('#connection-label').textContent = 'Reconnecting to your studio…'; };
  } catch { $('#view-story').innerHTML = '<div class="offline-banner">Your local studio is unavailable. Start it with <code>python3 scripts/dev.py up</code>, then reload this page.</div>'; }
}
connect();
