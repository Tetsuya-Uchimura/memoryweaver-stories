/* Coordinate provenance stays local; each album automatically loads its street map. */
const locationBasis = p => ({sample:'Fictional sample · approximate landmark',gps:'Photo GPS · place name unverified',stated:'Location shared by the traveler'}[p.basis] || 'Location unconfirmed');
const locationURL = p => p.latitude == null ? 'https://www.openstreetmap.org/search?' + new URLSearchParams({query:p.name}) : `https://www.openstreetmap.org/?${new URLSearchParams({mlat:p.latitude,mlon:p.longitude})}#map=15/${p.latitude}/${p.longitude}`;
function photoLocation(id,revision=selected()) {
  const p=revision?.photo_locations?.[id];
  const index=p ? journeyPlaces(revision).findIndex(s=>placeKey(s)===placeKey(p)) : -1;
  const button=p && MemoryWeaverMap.valid(p) ? `<button type="button" class="show-on-map" data-photo-map="${index}">Show on this map</button>` : '';
  return p ? `<span class="photo-place">⌖ ${esc(p.name)}<small>${esc(locationBasis(p))}</small>${button}<a href="${esc(locationURL(p))}" target="_blank" rel="noopener noreferrer">Open map ↗</a></span>` : '<span class="photo-place unknown">⌖ Location not supplied</span>';
}
const placeKey = p => [p.name,p.latitude,p.longitude,p.basis].join('|');
function journeyPlaces(revision) {
  const places=[...(revision.places || []),...Object.values(revision.photo_locations || {})];
  return [...new Map(places.map(p => [placeKey(p),p])).values()];
}
function renderJourney(revision) {
  const places=journeyPlaces(revision);
  if(!places.length) return '<section class="journey-places no-locations"><div class="eyebrow">PLACES WE REMEMBER</div><h2>Every place has a story.</h2><p>No location was supplied for this edition. Share a place name or a photo with GPS in your private Mattermost room.</p></section>';
  const pins=places.filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude));
  let sketch='';
  if(pins.length) {
    const origin=pins[0].longitude;
    const project=p=>[origin+((((p.longitude-origin)+540)%360)-180),Math.log(Math.tan(Math.PI/4+Math.max(-85,Math.min(85,p.latitude))*Math.PI/360))*180/Math.PI];
    const raw=pins.map(project),xs=raw.map(p=>p[0]),ys=raw.map(p=>p[1]);
    const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
    const scale=Math.min(660/Math.max(xmax-xmin,.005),220/Math.max(ymax-ymin,.005));
    const points=raw.map(([x,y])=>[380+(x-(xmin+xmax)/2)*scale,150-(y-(ymin+ymax)/2)*scale]);
    sketch=`<svg class="location-sketch" viewBox="0 0 760 300" role="img" aria-label="Shared location pins, a coordinate sketch without a basemap"><defs><pattern id="place-grid" width="38" height="30" patternUnits="userSpaceOnUse"><path d="M38 0H0V30" fill="none" stroke="#dae4d6" stroke-width="1"/></pattern></defs><rect width="760" height="300" rx="16" fill="#edf2e9"/><rect width="760" height="300" fill="url(#place-grid)"/><polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#91a58c" stroke-width="2" stroke-dasharray="5 7"/>${points.map(([x,y],i)=>`<g class="map-pin" data-map-stop="${places.indexOf(pins[i])}" role="button" tabindex="0" aria-label="${esc(pins[i].name)}"><circle cx="${x}" cy="${y}" r="17" fill="#345b48"/><text x="${x}" y="${y+5}" text-anchor="middle" fill="white" font-size="13">${places.indexOf(pins[i])+1}</text></g>`).join('')}</svg><p class="map-note">COORDINATE SKETCH · Dashed lines connect memories, not recorded travel paths.</p>`;
  }
  const stops=places.map(p=>({name:p.name,latitude:p.latitude,longitude:p.longitude,basis:p.basis,photos:Object.entries(revision.photo_locations || {}).filter(([,location])=>placeKey(location)===placeKey(p)).map(([id])=>({url:photoURL(id),label:asset(id)?.label || 'Travel photograph'}))}));
  return `<section class="journey-places"><div class="eyebrow">PLACES WE REMEMBER</div><h2>A journey, one place at a time.</h2><p class="journey-intro">The places behind the photographs. Only shared locations and available photo GPS are shown.</p>${pins.length?MemoryWeaverMap.markup(stops,sketch):''}<div class="place-list">${places.map((p,i)=>`<article class="place-card" id="place-${i}"><span class="place-number">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(p.name)}</h3><p>${esc(locationBasis(p))}</p>${p.latitude==null?'':`<small>${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)}</small>`}</div>${MemoryWeaverMap.valid(p)?`<button type="button" class="show-on-map" data-show-map="${i}">Show on this map</button>`:''}<a href="${esc(locationURL(p))}" target="_blank" rel="noopener noreferrer">Open map ↗</a></article>`).join('')}</div></section>`;
}
function bindJourney() {
  document.querySelectorAll('[data-journey-map]').forEach(MemoryWeaverMap.mount);
  bindPhotoMaps();
  document.querySelectorAll('[data-map-stop]').forEach(pin=>{
    const activate=()=>{
      document.querySelectorAll('.place-card').forEach(c=>c.classList.remove('selected-place'));
      const card=document.getElementById('place-'+pin.dataset.mapStop);card?.classList.add('selected-place');card?.scrollIntoView({behavior:'smooth',block:'nearest'});
    };
    pin.onclick=activate;pin.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}};
  });
}
function bindPhotoMaps() {
  document.querySelectorAll('[data-photo-map]').forEach(button=>button.onclick=()=>{
    const index=Number(button.dataset.photoMap);
    if(bookView==='photos'){
      bookView='book';document.querySelectorAll('[data-book]').forEach(b=>b.classList.toggle('selected',b.dataset.book==='book'));renderStory();
    }
    MemoryWeaverMap.show(document.querySelector('[data-journey-map]'),index);
  });
}
