// --- Port markers (ports) ---
window.portMarkers = {};

function makePortIcon(name){
  // create icon using the provided SVG and no adjacent label
  const svg = encodeURIComponent(`
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10.9877 0.121094C6.26979 0.121094 2.44516 3.94572 2.44516 8.6636C2.44516 10.7698 3.21091 12.6947 4.47459 14.1842L10.9877 21.8547L17.5005 14.1839C18.7642 12.6947 19.5299 10.7696 19.5299 8.66336C19.5302 3.94572 15.7056 0.121094 10.9877 0.121094ZM10.9877 11.8826C9.04734 11.8826 7.47455 10.3098 7.47455 8.36948C7.47455 6.42915 9.04734 4.85636 10.9877 4.85636C12.928 4.85636 14.5008 6.42915 14.5008 8.36948C14.5008 10.3098 12.928 11.8826 10.9877 11.8826Z" fill="black"/>
    </svg>`);
  const html = `<div class="port-marker" style="width:22px;height:22px;display:flex;align-items:center;justify-content:center;">
    <img src="data:image/svg+xml;utf8,${svg}" style="width:22px;height:22px;"/>
  </div>`;
  return L.divIcon({className:'port-div-icon', html:html, iconSize: [22, 22], iconAnchor: [11, 22]});
}

function escapeHtml(s){
  if(!s) return '';
  return String(s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[c];
  });
}

function clearPorts(){
  for(const k in window.portMarkers){
    try{ map.removeLayer(window.portMarkers[k]); }catch(e){}
  }
  window.portMarkers = {};
}

function addOrUpdatePort(p){
  if(!p || typeof p.lat === 'undefined' || typeof p.lon === 'undefined') return;
  const id = p.id != null ? String(p.id) : (p.nome || p.name || '') + '_' + String(p.lat) + '_' + String(p.lon);
  const name = p.nome || p.name || '';
  const lat = Number(p.lat);
  const lon = Number(p.lon);
  let marker = window.portMarkers[id];
  if(!marker){
    marker = L.marker([lat, lon], {icon: makePortIcon(name), keyboard: false}).addTo(map);
    marker.bindPopup(popupForPort(name, lat, lon));
    window.portMarkers[id] = marker;
  } else {
    marker.setLatLng([lat, lon]);
    marker.setIcon(makePortIcon(name));
    marker.getPopup() && marker.setPopupContent(popupForPort(name, lat, lon));
  }
}

function popupForPort(name, lat, lon){
  const safe = escapeHtml(name);
  // build an index.html URL in the same static folder and open fragment with port param
  let base = window.location.href || '';
  // try to replace map.html or map.* with index.html, fallback to directory + index.html
  let indexUrl = base.replace(/map\.html($|[?#].*$)/, 'index.html');
  if(indexUrl === base){
    // didn't replace, build from path
    try{
      const parts = base.split('/');
      parts.pop();
      indexUrl = parts.join('/') + '/index.html';
    }catch(e){
      indexUrl = 'index.html';
    }
  }
  const frag = '#/porto?port=' + encodeURIComponent(name || '');
  const full = indexUrl + frag;
  const html = `<div><b>${safe}</b><br/>Lat: ${lat.toFixed(6)}<br/>Lon: ${lon.toFixed(6)}<br/><br/><button onclick="window.open('${full}', '_blank')">Mostra in Dashboard</button></div>`;
  return html;
}

function loadPorts(list){
  try{
    clearPorts();
    if(!list || !list.forEach) return;
    list.forEach(function(p){ addOrUpdatePort(p); });
  }catch(e){ console.error('loadPorts', e); }
}

// expose
window.clearPorts = clearPorts;
window.loadPorts = loadPorts;
window.addOrUpdatePort = addOrUpdatePort;
