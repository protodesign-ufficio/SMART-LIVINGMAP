// ships.js
// Manage ship markers and tracks on the Leaflet map.

window._nv_ships = window._nv_ships || {};
(function(){
  const ships = {};

  // debug removed per user request

  function makeSvg(color, heading){
    const h = (heading || 0);
    // simple arrow-shaped SVG; rotation applied via inline style
    return `<div style="transform: rotate(${h}deg); display:inline-block;">
      <svg width="24" height="13" viewBox="0 0 24 13" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 6.5L24 0L17 6.5L24 13L0 6.5Z" fill="${color || '#ff6600'}" stroke="black"/>
      </svg>
    </div>`;
  }

  function makeIcon(color, heading){
    return L.divIcon({
      className: 'nv-ship-icon',
      html: makeSvg(color, heading),
      iconSize: [24,13],
      iconAnchor: [12,6]
    });
  }

  function popupHtml(m){
    const staticInfo = m.static || {};
    return `<div style="font-size:12px">
      <b>${staticInfo.shipname || ''}</b><br/>
      MMSI: ${m.mmsi || ''}<br/>
      Speed: ${m.speed != null ? m.speed : ''}<br/>
      Heading: ${m.heading != null ? m.heading : ''} <br/>
      Lat: ${m.lat != null ? m.lat.toFixed(6) : ''}<br/>
      Lon: ${m.lon != null ? m.lon.toFixed(6) : ''}
    </div>`;
  }

  window.updateShip = function(data){
    try{
      // no debug output
      const payload = data.payload || {};
      const msg_type = data.msg_type || (payload && payload.msg_type);
      const mmsi = data.mmsi || payload.mmsi || data.key;
      if(!mmsi) return;

      if(!ships[mmsi]){
        ships[mmsi] = {mmsi: mmsi, static: {}, coords: [], marker: null, polyline: null};
      }
      const s = ships[mmsi];

      if(msg_type === 1){
        const lat = payload.lat;
        const lon = payload.lon;
        if(lat == null || lon == null) return;
        const heading = ((payload.heading || 0) + 90.0) % 360;
        s.lat = lat; s.lon = lon; s.speed = payload.speed; s.heading = heading;

        if(s.marker === null){
          s.marker = L.marker([lat, lon], {icon: makeIcon(s.static.color || '#ff6600', heading), riseOnHover: true}).addTo(window.map);
          // bind popup once and open on click
          s.marker.bindPopup(popupHtml(s));
          s.marker.on('click', function(){
            try{ s.marker.openPopup(); }catch(e){}
          });
          s.coords = [[lat, lon]];
          s.polyline = L.polyline(s.coords, {color: s.static.color || '#ff6600', weight:2, opacity:0.8}).addTo(window.map);
        } else {
          s.marker.setLatLng([lat, lon]);
          // update icon HTML to reflect heading / color
          const el = s.marker.getElement();
          if(el){
            const div = el.querySelector('div');
            if(div){ div.style.transform = `rotate(${heading}deg)`; }
          }
          // update popup content to reflect latest state
          try{ s.marker.bindPopup(popupHtml(s)); }catch(e){}
          // append to path (no max length; keep full history)
          s.coords.push([lat, lon]);
          if(s.polyline) s.polyline.setLatLngs(s.coords);
        }
      } else if(msg_type === 5){
        // static information
        s.static.shipname = payload.shipname || s.static.shipname;
        s.static.callsign = payload.callsign || s.static.callsign;
        s.static.ship_type = payload.ship_type || s.static.ship_type;
        s.static.draught = payload.draught || s.static.draught;
        s.static.destination = payload.destination || s.static.destination;
        // if marker exists, update popup content
        if(s.marker){
          s.marker.bindPopup(popupHtml(s));
        }
      }
    }catch(e){
      // ignore errors in map update to avoid crashing
    }
  };

  // expose for debugging
  window._nv_ships = ships;

})();
