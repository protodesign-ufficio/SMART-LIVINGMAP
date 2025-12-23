// Initialize the map
const map = L.map('map').setView([45.0, 10.0], 6);

// Coordinate display box
(function(){
  const box = document.getElementById('coords-box');
  if (!box) return;
  function fmt(n){ return (typeof n === 'number') ? n.toFixed(5) : '' }
  // update on mouse move over the map
  if (typeof map !== 'undefined' && map && map.on){
    map.on('mousemove', function(e){
      const lat = fmt(e.latlng.lat);
      const lon = fmt(e.latlng.lng);
      box.textContent = lat + ' , ' + lon;
    });
    // clear when mouse leaves map
    map.on('mouseout', function(){ box.textContent = ''; });
  }
})();

// OpenStreetMap base layer
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

// OpenSeaMap seamark overlay
const seamark = L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenSeaMap'
}).addTo(map);

let shipMarker = null;

// container for multiple ship markers keyed by MMSI or '__gps' for own/GPS
window.shipMarkers = {};
window.shipPaths = {};

function colorFromString(s){
  if(!s) return '#0077be';
  if(s === '__gps') return '#0077be';
  let h = 0;
  for(let i=0;i<s.length;i++){
    h = ((h<<5)-h) + s.charCodeAt(i);
    h |= 0;
  }
  const hex = (h >>> 0 & 0xFFFFFF).toString(16).padStart(6,'0');
  return '#' + hex;
}

function makeShipIcon(cog, color){
  const angle = Number(cog) || 0;
  const svg = `
      <svg width="24" height="13" viewBox="0 0 24 13" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 6.5L24 0L17 6.5L24 13L0 6.5Z" fill="${color}" stroke="black"/>
      </svg>`; 

  // wrap svg in a div to apply rotation
  const html = `<div style="transform: rotate(${angle}deg); width:32px; height:32px; display:flex; align-items:center; justify-content:center;">${svg}</div>`;
  return L.divIcon({className:'ship-icon', html: html, iconSize: [32,32], iconAnchor: [16,16]});
}

function createShipMarker(lat, lon, cog, color){
  const icon = makeShipIcon(cog, color);
  return L.marker([lat, lon], {icon: icon}).addTo(map);
}

function updateShip(lat, lon, sog, cog, mmsi, name, type, color){
  if (!lat || !lon) return;
  const key = (mmsi && mmsi !== '-') ? String(mmsi) : '__gps';
  // prefer explicit color if provided, otherwise derive from key
  const colorUsed = color && color !== null ? color : colorFromString(key);
  let marker = window.shipMarkers[key];
  if (!marker) {
    marker = createShipMarker(lat, lon, cog, colorUsed);
    window.shipMarkers[key] = marker;
  } else {
    marker.setLatLng([lat, lon]);
    // update icon rotation/color
    marker.setIcon(makeShipIcon(cog, colorUsed));
  }

  // update path
  let path = window.shipPaths[key];
  const latlng = [lat, lon];
  if (!path) {
    path = L.polyline([latlng], {color: colorUsed, weight: 2}).addTo(map);
    window.shipPaths[key] = path;
  } else {
    const pts = path.getLatLngs();
    pts.push(latlng);
    path.setLatLngs(pts);
    path.setStyle({color: colorUsed});
  }

  const nameLine = name && name !== '-' ? `Name: ${name}<br/>` : '';
  const mmsiLine = (mmsi && mmsi !== '-') ? `MMSI: ${mmsi}<br/>` : '';
  const typeLine = type && type !== '-' ? `Type: ${type}<br/>` : '';
  marker.bindPopup(`${nameLine}${mmsiLine}${typeLine}Lat: ${lat.toFixed(6)}<br/>Lon: ${lon.toFixed(6)}<br/>Speed: ${sog}<br/>Course: ${cog}`);
  // Do not pan the map automatically when the ship updates.
}

function centerOnShip(mmsi){
  const key = (mmsi && mmsi !== '-') ? String(mmsi) : '__gps';
  const marker = window.shipMarkers[key];
  if (marker) {
    map.setView(marker.getLatLng(), map.getZoom(), {animate: true});
    marker.openPopup();
  }
}

function setShipColor(mmsi, color){
  const key = (mmsi && mmsi !== '-') ? String(mmsi) : '__gps';
  const marker = window.shipMarkers[key];
  const path = window.shipPaths[key];
  if(marker){
    // preserve current rotation if possible
    marker.setIcon(makeShipIcon(0, color));
  }
  if(path){
    path.setStyle({color: color});
  }
}

// expose to window for external callers (PyQt runJavaScript)
window.updateShip = updateShip;
window.setShipColor = setShipColor;

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
    marker.bindPopup(`<b>${escapeHtml(name)}</b><br/>Lat: ${lat.toFixed(6)}<br/>Lon: ${lon.toFixed(6)}`);
    window.portMarkers[id] = marker;
  } else {
    marker.setLatLng([lat, lon]);
    marker.setIcon(makePortIcon(name));
    marker.getPopup() && marker.setPopupContent(`<b>${escapeHtml(name)}</b><br/>Lat: ${lat.toFixed(6)}<br/>Lon: ${lon.toFixed(6)}`);
  }
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
