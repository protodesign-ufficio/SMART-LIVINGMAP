// Initialize the map (disable world copy wrapping and keep map bounded)
// Set sensible zoom limits to avoid excessive zooming
const map = L.map('map', { worldCopyJump: false, maxBoundsViscosity: 1, minZoom: 3, maxZoom: 18 }).setView([40.65, 14.6], 12);
// expose map globally so other scripts can access it
window.map = map;
// Restrict map to a single world view (no infinite longitudinal panning)
map.setMaxBounds([[-90, -180], [90, 180]]);

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
  maxZoom: 18,
  attribution: '© OpenStreetMap contributors',
  noWrap: true
}).addTo(map);

// OpenSeaMap seamark overlay
const seamark = L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '© OpenSeaMap',
  noWrap: true
}).addTo(map);
