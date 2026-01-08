let shipMarker = null;

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