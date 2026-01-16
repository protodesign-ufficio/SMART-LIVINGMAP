/* routesManager.js
   Gestisce il disegno delle rotte sulla mappa Leaflet.
   Espone `window.routesManager.addRoute(route)` e `window.routesManager.removeRoute(id)`.
   Il campo `geom_rotta` accetta una stringa GeoJSON o un oggetto GeoJSON.
*/
(function(){
  if (typeof map === 'undefined') {
    console.warn('routesManager: global `map` non trovato');
  }

  // container per le rotte aggiunte
  const routes = {};

  function parseGeom(geom){
    if(!geom) return null;
    try{
      if(typeof geom === 'string') return JSON.parse(geom);
      return geom;
    }catch(e){
      console.error('routesManager: errore parsing geom_rotta', e);
      return null;
    }
  }

  function coordsToLatLngs(coords){
    // GeoJSON coordinates are [lon, lat]
    return coords.map(function(c){ return [c[1], c[0]]; });
  }

  function makeDiamondIcon(color, size){
    size = size || 12;
    const half = Math.round(size/2);
    const html = `<div style="width:${size}px;height:${size}px;background:${color};transform:rotate(45deg);border:1px solid #000;border-radius:1px;box-shadow:0 0 1px rgba(0,0,0,0.6);"></div>`;
    return L.divIcon({className: 'route-diamond-icon', html: html, iconSize: [size,size], iconAnchor: [half,half]});
  }

  function addRoute(route, options){
    console.log('routesManager.addRoute called', route && route.id);
    options = options || {};
    const id = route && route.id ? route.id : String(Date.now());
    // if already exists, remove first
    if(routes[id]){
      removeRoute(id);
    }

    const geom = parseGeom(route.geom_rotta);
    if(!geom || geom.type !== 'LineString' || !Array.isArray(geom.coordinates) || geom.coordinates.length === 0){
      console.warn('routesManager: geom_rotta non valida per route', id);
      return null;
    }

    const latlngs = coordsToLatLngs(geom.coordinates);

    const lineStyle = Object.assign({color: options.color || '#ff0000', weight: options.weight || 3, opacity: options.opacity || 0.8}, options.lineStyle || {});
    const poly = L.polyline(latlngs, lineStyle).addTo(map);

    // create diamond waypoints
    const markers = latlngs.map(function(ll, idx){
      const icon = makeDiamondIcon(options.waypointColor || '#ffffff', options.waypointSize || 12);
      const m = L.marker(ll, {icon: icon, interactive: !!options.interactive}).addTo(map);
      if(options.interactive){
        const label = route.corsa_id ? (`${route.corsa_id} — wp ${idx+1}`) : (`wp ${idx+1}`);
        m.bindPopup(label);
      }
      return m;
    });

    // group for easy removal
    const group = L.layerGroup([poly].concat(markers)).addTo(map);

    console.log('routesManager: route drawn', id, latlngs.length, lineStyle);

    routes[id] = {id: id, polyline: poly, markers: markers, group: group, raw: route};
    return id;
  }

  function removeRoute(id){
    console.log('routesManager.removeRoute called', id);
    const r = routes[id];
    if(!r) return false;
    try{
      if(r.group) map.removeLayer(r.group);
      else {
        if(r.polyline) map.removeLayer(r.polyline);
        if(Array.isArray(r.markers)) r.markers.forEach(m=>{ if(m && map.hasLayer(m)) map.removeLayer(m); });
      }
    }catch(e){ console.warn('routesManager: errore rimozione route', e); }
    delete routes[id];
    console.log('routesManager: route removed', id);
    return true;
  }

  function clearAll(){
    Object.keys(routes).forEach(removeRoute);
  }

  // convenience wrapper that accepts the example object directly
  function drawRouteObject(routeObj, options){
    return addRoute(routeObj, options);
  }

  window.routesManager = {
    addRoute: addRoute,
    drawRoute: drawRouteObject,
    removeRoute: removeRoute,
    clearAll: clearAll,
    _internal: routes
  };

})();
