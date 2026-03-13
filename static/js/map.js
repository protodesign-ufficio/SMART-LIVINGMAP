// Initialize the map (disable world copy wrapping and keep map bounded)
// Set sensible zoom limits to avoid excessive zooming
const map = L.map('map', { 
  attributionControl: false,
  worldCopyJump: false, 
  maxBoundsViscosity: 1, 
  minZoom: 3, 
  maxZoom: 18 
}).setView([40.63, 14.6], 12);

// expose map globally so other scripts can access it
window.map = map;

// Restrict map to a single world view (no infinite longitudinal panning)
map.setMaxBounds([[-90, -180], [90, 180]]);

// Coordinate display box (show absolute values with N/S and E/W)
(function(){
  const box = document.getElementById('coords-box');
  box.textContent = '40.00000° N 14.00000° E'; 
  if (!box) return;
  function fmtLat(n){
    if (typeof n !== 'number') return '';
    const abs = Math.abs(n).toFixed(5);
    const dir = (n >= 0) ? 'N' : 'S';
    return abs + '° ' + dir;
  }
  function fmtLon(n){
    if (typeof n !== 'number') return '';
    const abs = Math.abs(n).toFixed(5);
    const dir = (n >= 0) ? 'E' : 'W';
    return abs + '° ' + dir;
  }
  // update on mouse move over the map
  if (typeof map !== 'undefined' && map && map.on){
    map.on('mousemove', function(e){
      const lat = fmtLat(e.latlng.lat);
      const lon = fmtLon(e.latlng.lng);
      box.textContent = lat + '  ' + lon;
    });
    // clear when mouse leaves map
    map.on('mouseout', function(){ 
      box.textContent = '40.00000° N 14.00000° E'; 
    });
  }
})();

function returnToHome(){
  if (typeof map !== 'undefined' && map){
    map.setView([40.63, 14.6], 12);
  }
}

// Function to refresh the map: clear visible routes, clear map
function refreshMap() {
    console.log("Refreshing map...");
    // 1. Clear visible routes in Python
    if (window.pyMain && window.pyMain.cleanRoutes) {
        window.pyMain.cleanRoutes(function(success) {
            console.log("Python routes cleared:", success);
        });
    }
    
    // 2. Clear routes on map
    if (window.routesManager && window.routesManager.clearAll) {
        window.routesManager.clearAll();
    }
    
    // 3. Clear weather layers
    if (window.weatherManager && window.weatherManager.clearAllWeather) {
        window.weatherManager.clearAllWeather();
    }
}

// OpenStreetMap base layer
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenStreetMap',
  noWrap: true
}).addTo(map);

// OpenSeaMap seamark overlay
const seamark = L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenSeaMap',
  noWrap: true
}).addTo(map);


L.control.attribution({
    position: 'bottomleft'
}).addTo(map).addAttribution('© Copernicus Marine Service');