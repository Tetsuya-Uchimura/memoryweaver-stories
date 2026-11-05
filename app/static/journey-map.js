/* Leaflet is served locally. Each album automatically loads its street map. */
(() => {
  'use strict';
  const controllers = new WeakMap();
  const valid = p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude) && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180;
  const basis = p => ({sample:'Fictional sample · approximate landmark',gps:'Photo GPS · place name unverified',stated:'Location shared by the traveler'}[p.basis] || 'Location unconfirmed');
  const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const node = (tag, cls, text) => { const e=document.createElement(tag); if(cls)e.className=cls; if(text)e.textContent=text; return e; };
  const safePhoto = url => typeof url === 'string' && /^(?:\/static\/assets\/[a-z-]+\.jpg|\/media\/(?:trips\/[a-z-]+\/)?[a-f0-9]+\.jpg|assets\/[a-z0-9-]+\.jpg)$/.test(url);
  function popup(p) {
    const box=node('div','map-photo-popup');
    box.append(node('h3','',p.name),node('p','map-location-basis',basis(p)),node('p','map-coordinates',`${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)}`));
    const photos=node('div','map-popup-photos');
    for(const photo of (p.photos || []).filter(a=>safePhoto(a.url))) {
      const figure=node('figure'), img=node('img');img.src=photo.url;img.alt=photo.label || 'Travel photograph';img.loading='lazy';
      figure.append(img,node('figcaption','',photo.label || 'Travel photograph'));photos.append(figure);
    }
    if(photos.childElementCount)box.append(photos);
    return box;
  }
  function mount(root) {
    if(!root)return null;
    if(controllers.has(root))return controllers.get(root);
    let places;try { places=JSON.parse(root.dataset.mapStops); } catch { return null; }
    if(!Array.isArray(places))return null;
    const points=places.map((p,index)=>({...p,index})).filter(valid);
    if(!points.length)return null;
    const fallback=root.querySelector('[data-coordinate-fallback]');
    const controls=node('div','map-controls'),load=node('button','map-load','Load street map'),reset=node('button','map-reset','Show all places'),hide=node('button','map-hide','Hide street map');
    for(const b of [load,reset,hide])b.type='button';reset.hidden=true;hide.hidden=true;controls.append(load,reset,hide);
    const privacy=node('p','map-privacy','Street maps load automatically from OpenStreetMap. The map provider receives your IP address and the area shown; your photos and messages are not sent to it.');
    const canvas=node('div','street-map');canvas.hidden=true;canvas.setAttribute('aria-label','Travel locations on a street map');
    const status=node('p','map-status','Loading street map…');status.setAttribute('role','status');
    root.prepend(controls,privacy,canvas,status);root.dataset.mapState='idle';
    const c={root,places,points,map:null,markers:new Map(),observer:null,timer:null,pending:null,canvas,load,status};controllers.set(root,c);
    const highlight = index => {
      const section=root.closest('.journey-places');section?.querySelectorAll('.place-card').forEach(card=>card.classList.toggle('selected-place',card.id==='place-'+index));
    };
    c.select = index => {
      const marker=c.markers.get(index);if(!marker)return;highlight(index);
      c.markers.forEach(m=>m.setZIndexOffset(m===marker?1000:0));
      c.map.setView(marker.getLatLng(),Math.max(15,c.map.getZoom()),{animate:false});marker.openPopup();
    };
    c.stop = error => {
      clearTimeout(c.timer);c.timer=null;
      c.observer?.disconnect();c.observer=null;
      const map=c.map;c.map=null;map?.remove();c.markers.clear();canvas.hidden=true;if(fallback)fallback.hidden=false;
      load.hidden=false;reset.hidden=true;hide.hidden=true;load.textContent=error?'Retry street map':'Load street map';
      root.dataset.mapState=error?'error':'idle';status.textContent=error?'Street tiles could not be loaded. Check your connection and retry, or use the Open map links below.':'Street map hidden.';
    };
    c.start = ({reveal=false}={}) => {
      if(c.map)return;
      if(!window.L){status.textContent='The street map could not be opened. Use the Open map links below.';root.dataset.mapState='error';return;}
      canvas.hidden=false;if(fallback)fallback.hidden=true;load.hidden=true;reset.hidden=false;hide.hidden=false;root.dataset.mapState='loading';status.textContent='Loading street map…';
      // Automatic loading must leave the reader at the cover of the album.
      if(reveal)canvas.scrollIntoView({behavior:'instant',block:'center'});
      const map=L.map(canvas,{scrollWheelZoom:false,fadeAnimation:false,zoomAnimation:false,markerZoomAnimation:false});c.map=map;
      // Keep nearby points on opposite sides of the date line together.
      const origin=points[0].longitude;
      const latlng=p=>[p.latitude,origin+((((p.longitude-origin)+540)%360)-180)];
      const bounds=L.latLngBounds(points.map(latlng));
      const fit=()=>map.fitBounds(bounds,{padding:[34,34],maxZoom:15});
      let measured=canvas.clientWidth>0;
      if(measured)fit();else map.setView(latlng(points[0]),13);
      reset.onclick=fit;
      for(const p of points) {
        const icon=L.divIcon({className:'journey-map-marker',html:String(p.index+1),iconSize:[32,32],iconAnchor:[16,16]});
        const marker=L.marker(latlng(p),{icon,title:p.name,alt:p.name}).addTo(map).bindPopup(popup(p),{maxWidth:270,maxHeight:270});
        marker.getElement().setAttribute('aria-label',`${p.index+1}. ${p.name}`);
        marker.on('click',()=>highlight(p.index));c.markers.set(p.index,marker);
      }
      let successes=0,attempts=0;
      const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
        maxZoom:19,referrerPolicy:'origin',updateWhenIdle:true,updateWhenZooming:false,keepBuffer:1,
        attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
      });
      tiles.on('tileloadstart',()=>attempts++);
      tiles.on('tileload',()=>{successes++;clearTimeout(c.timer);if(c.map===map){root.dataset.mapState='ready';status.textContent='Choose a numbered pin to see the photographs taken there. Zoom in to separate nearby places.';}});
      // Leaflet still uses its map after dispatching "load". Wait until that
      // event finishes before removing a failed layer's map instance.
      tiles.on('load',()=>queueMicrotask(()=>{if(attempts&&!successes&&c.map===map)c.stop(true);}));
      c.timer=setTimeout(()=>{if(c.map===map&&!successes)c.stop(true);},20000);
      tiles.addTo(map);
      if(window.ResizeObserver){c.observer=new ResizeObserver(()=>{
        if(c.map!==map||!canvas.clientWidth)return;
        map.invalidateSize({pan:false});if(!measured){measured=true;fit();}
      });c.observer.observe(canvas);}
      if(c.pending!==null)c.select(c.pending);
    };
    load.onclick=()=>c.start({reveal:true});hide.onclick=()=>{c.stop(false);load.focus();};
    c.start();return c;
  }
  function show(root,index) {
    const c=mount(root);if(!c)return;
    c.pending=index;root.scrollIntoView({behavior:'smooth',block:'center'});
    if(!c.map)c.start();
    if(c.map)c.select(index);else c.load.focus({preventScroll:true});
  }
  function destroy(root) { if(!root)return;const c=controllers.get(root);if(c){c.stop(false);controllers.delete(root);} }
  window.MemoryWeaverMap={
    valid,
    markup:(places,sketch='')=>`<div class="journey-map" data-journey-map data-map-stops="${escape(JSON.stringify(places))}"><div data-coordinate-fallback>${sketch}</div></div>`,
    mount,show,destroy
  };
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-show-map]');if(!button)return;
    const section=button.closest('.journey-places') || button.closest('.book')?.querySelector('.journey-places');
    show(section?.querySelector('[data-journey-map]'),Number(button.dataset.showMap));
  });
  // Static approved exports use the same component, without the studio application.
  document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('[data-journey-map]').forEach(mount));
})();
