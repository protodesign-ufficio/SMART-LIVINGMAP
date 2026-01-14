// Initialize the map
const map = L.map('map').setView([45.0, 10.0], 6);
// expose map globally so other scripts can access it
window.map = map;

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
