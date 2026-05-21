/* weather.js
   Gestisce la visualizzazione dei layer meteo (onde e correnti) sulla mappa Leaflet.
   Espone window.weatherManager con le funzioni principali.
*/
(function(){
  if (typeof map === 'undefined') {
    console.warn('weatherManager: global `map` non trovato');
  }

  // Base URL del backend (stessa usata da pyMain)
  const BASE_URL = 'http://87.26.178.190:25080/';

  // Leaflet layer groups attivi per tipo
  const activeLayers = {
    waves: null,
    currents: null
  };

  // Stato di visibilità
  const layerVisible = {
    waves: false,
    currents: false
  };

  // Stato caricamento per bloccare i bottoni durante le fetch
  const loadingLayers = {
    waves: false,
    currents: false
  };

  // Sorgente dati attiva: 'live' o 'route'
  const layerSource = {
    waves: null,
    currents: null
  };

  // Cache keys del percorso attualmente visualizzato
  var routeCacheKeys = {
    waves: null,
    currents: null
  };

  // Label meteo
  var weatherInfoControl = null;
  var weatherInfoData = {
    waves: null,
    currents: null
  };
  var weatherInfoMeta = {
    waves: null,
    currents: null
  };
  var weatherInfoExpanded = false;

  if (typeof map !== 'undefined') {
    weatherInfoControl = L.control({position: 'bottomright'});
    weatherInfoControl.onAdd = function() {
      this._div = L.DomUtil.create('div', 'weather-info-label');
      L.DomEvent.disableClickPropagation(this._div);
      L.DomEvent.disableScrollPropagation(this._div);
      this.update();
      return this._div;
    };
    weatherInfoControl.update = function() {
      if (!this._div) return;
      var info = null;
      var meta = null;
      var isRoute = false;
      if (layerVisible.waves && weatherInfoData.waves) {
          info = weatherInfoData.waves;
          meta = weatherInfoMeta.waves;
          isRoute = (layerSource.waves === 'route');
      } else if (layerVisible.currents && weatherInfoData.currents) {
          info = weatherInfoData.currents;
          meta = weatherInfoMeta.currents;
          isRoute = (layerSource.currents === 'route');
      }

      if (info) {
        var detailsHtml = '';
        if (weatherInfoExpanded && meta) {
          detailsHtml = '<div class="weather-info-details">' +
            '<div><b>Dataset:</b> ' + (meta.dataset || 'N.D.') + '</div>' +
            '<div><b>Sorgente:</b> ' + (meta.source || 'N.D.') + '</div>' +
            '<div><b>Timestamp:</b> ' + (meta.timestamp || 'N.D.') + '</div>' +
            (meta.scenarioName ? '<div><b>Scenario:</b> ' + meta.scenarioName + '</div>' : '') +
          '</div>';
        }

        this._div.innerHTML =
          '<div class="weather-info-header">' +
            '<span class="weather-info-text">' + info + '</span>' + 
            '<button type="button" class="weather-info-help" aria-label="Mostra dettagli meteo" title="Mostra dettagli meteo">?</button>' +
          '</div>' +
          detailsHtml;
        this._div.style.display = 'block';
        if (isRoute) {
          this._div.style.backgroundColor = '#fff59dc0'; // Giallo canarino
        } else {
          this._div.style.backgroundColor = 'rgba(255,255,255,0.9)';
        }
        var helpBtn = this._div.querySelector('.weather-info-help');
        if (helpBtn) {
          L.DomEvent.on(helpBtn, 'click', function(e) {
            L.DomEvent.stop(e);
            weatherInfoExpanded = !weatherInfoExpanded;
            weatherInfoControl.update();
          });
        }
      } else {
        this._div.innerHTML = '';
        this._div.style.display = 'none';
        weatherInfoExpanded = false;
      }
    };
    weatherInfoControl.addTo(map);
  }

  // ---------- Utilità colori ----------

  function currentsMagnitude(u, v) {
    return Math.sqrt(u * u + v * v);
  }

  function currentsAngle(u, v) {
    // angolo in gradi (0=Nord, senso orario)
    return (Math.atan2(u, v) * 180 / Math.PI + 360) % 360 ;
  }

  function formatLatLon(lat, lon) {
    var latNum = Number(lat);
    var lonNum = Number(lon);
    if (!isFinite(latNum) || !isFinite(lonNum)) return '';
    var latDir = latNum >= 0 ? 'N' : 'S';
    var lonDir = lonNum >= 0 ? 'E' : 'W';
    return Math.abs(latNum).toFixed(3) + '° ' + latDir + ' ' + Math.abs(lonNum).toFixed(3) + '° ' + lonDir;
  }

  function interpolateColor(t, colors) {
    // t in [0,1], colors = array di {stop, r, g, b}
    if (t <= colors[0].stop) return colors[0];
    if (t >= colors[colors.length - 1].stop) return colors[colors.length - 1];
    for (var i = 0; i < colors.length - 1; i++) {
      if (t >= colors[i].stop && t <= colors[i + 1].stop) {
        var ratio = (t - colors[i].stop) / (colors[i + 1].stop - colors[i].stop);
        return {
          r: Math.round(colors[i].r + ratio * (colors[i + 1].r - colors[i].r)),
          g: Math.round(colors[i].g + ratio * (colors[i + 1].g - colors[i].g)),
          b: Math.round(colors[i].b + ratio * (colors[i + 1].b - colors[i].b))
        };
      }
    }
    return colors[colors.length - 1];
  }

  // Scala colori per le correnti (blu -> ciano -> verde -> giallo -> rosso)
  var currentsColorScale = [
    { stop: 0.0,  r: 0,   g: 0,   b: 180 },
    { stop: 0.25, r: 0,   g: 180, b: 220 },
    { stop: 0.5,  r: 0,   g: 200, b: 80  },
    { stop: 0.75, r: 255, g: 220, b: 0   },
    { stop: 1.0,  r: 220, g: 30,  b: 0   }
  ];

  // Scala colori per le onde (blu -> ciano -> verde -> giallo -> rosso)
  var wavesColorScale = [
    { stop: 0.0,  r: 0,   g: 0,   b: 180 },
    { stop: 0.25, r: 0,   g: 180, b: 220 },
    { stop: 0.5,  r: 0,   g: 200, b: 80  },
    { stop: 0.75, r: 255, g: 220, b: 0   },
    { stop: 1.0,  r: 220, g: 30,  b: 0   }
  ];

  function getColor(t, type) {
    var scale = type === 'currents' ? currentsColorScale : wavesColorScale;
    var c = interpolateColor(Math.max(0, Math.min(1, t)), scale);
    return 'rgb(' + c.r + ',' + c.g + ',' + c.b + ')';
  }

  // ---------- Scale visiva (barra verticale) ----------
  function buildGradientCSS(scaleArray) {
    // scaleArray: [{stop, r,g,b}, ...]
    var stops = scaleArray.map(function(s) {
      return 'rgb(' + s.r + ',' + s.g + ',' + s.b + ') ' + Math.round(s.stop * 100) + '%';
    });
    return 'linear-gradient(to top, ' + stops.join(', ') + ')';
  }

  function updateScaleDisplay(layerType, minVal, maxVal) {
    var el = document.getElementById('weather-scale');
    var grad = document.getElementById('scale-gradient');
    var lblMax = document.getElementById('scale-max');
    var lblMin = document.getElementById('scale-min');
    if (!el || !grad || !lblMax || !lblMin) return;
    var scaleArray = (layerType === 'currents') ? currentsColorScale : wavesColorScale;
    var unit = layerType === 'currents' ? ' m/s' : ' m';
    // build gradient based on color scale
    grad.style.background = buildGradientCSS(scaleArray);
    // set labels (format numbers nicely)
    lblMax.textContent = (typeof maxVal === 'number') ? Number(maxVal).toLocaleString('it-IT') + unit : (maxVal || '—');
    lblMin.textContent = (typeof minVal === 'number') ? Number(minVal).toLocaleString('it-IT') + unit : (minVal || '—');
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
  }

  function hideScaleDisplay() {
    var el = document.getElementById('weather-scale');
    if (!el) return;
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
  }

  // ---------- Dimensioni frecce ----------

  var MIN_ARROW_SCALE = 0.8;  // scala minima (80%)
  var MAX_ARROW_SCALE = 1.8;  // scala massima (180%)

  // Dimensioni base degli SVG originali
  var CURRENTS_BASE_W = 12, CURRENTS_BASE_H = 22;
  var WAVES_BASE_W = 14, WAVES_BASE_H = 24;

  // ---------- Disegno frecce ----------

  function createCurrentsIcon(angle, color, scale) {
    scale = scale || 1;
    var w = Math.round(CURRENTS_BASE_W * scale);
    var h = Math.round(CURRENTS_BASE_H * scale);
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h +
      '" viewBox="0 0 12 22" style="transform:rotate(' + angle + 'deg)">' +
      '<path d="M5.81445 1.72046V21.7205M5.81445 1.72046L0.814453 8.72046M5.81445 1.72046L10.8145 8.72046" ' +
      'stroke="' + color + '" stroke-width="2"/></svg>';
    return L.divIcon({
      className: 'weather-arrow-icon',
      html: svg,
      iconSize: [w, h],
      iconAnchor: [Math.round(w / 2), Math.round(h / 2)]
    });
  }

  function createWavesIcon(angle, color, scale) {
    real_angle = angle + 180; // Le onde puntano verso la direzione da cui arrivano, non verso dove vanno
    scale = scale || 1;
    var w = Math.round(WAVES_BASE_W * scale);
    var h = Math.round(WAVES_BASE_H * scale);
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h +
      '" viewBox="0 0 14 24" style="transform:rotate(' + real_angle + 'deg)">' +
      '<path d="M0.554688 21.7205C2.55469 23.0538 4.55469 23.0538 6.55469 21.7205C8.55469 20.3871 10.5547 20.3871 12.5547 21.7205" ' +
      'stroke="' + color + '" stroke-width="2"/>' +
      '<path d="M6.55469 1.72046V21.7205M6.55469 1.72046L1.55469 8.72046M6.55469 1.72046L11.5547 8.72046" ' +
      'stroke="' + color + '" stroke-width="2"/></svg>';
    return L.divIcon({
      className: 'weather-arrow-icon',
      html: svg,
      iconSize: [w, h],
      iconAnchor: [Math.round(w / 2), Math.round(h / 2)]
    });
  }

  // ---------- Disegno layer ----------

  function drawWeatherLayer(layerType, weatherData) {
    // Rimuovi layer esistente dello stesso tipo
    if (activeLayers[layerType]) {
      map.removeLayer(activeLayers[layerType]);
      activeLayers[layerType] = null;
    }

    if (!weatherData || !weatherData.items || weatherData.items.length === 0) {
      console.warn('weatherManager: nessun dato per', layerType);
      return;
    }

    var items = weatherData.items;
    var range = weatherData.range || {};
    var minVal = range.min || 0;
    var maxVal = range.max || 1;
    var span = maxVal - minVal;
    if (span <= 0) span = 1;

    var markers = [];

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var lat = it.lat;
      var lon = it.lon;

      var magnitude, angle, t, color;

      if (layerType === 'currents') {
        magnitude = currentsMagnitude(it.u, it.v);
        angle = currentsAngle(it.u, it.v);
        t = (magnitude - minVal) / span;
        color = getColor(t, 'currents');
      } else {
        // waves
        magnitude = it.height || 0;
        angle = it.dir || 0;
        t = (magnitude - minVal) / span;
        color = getColor(t, 'waves');
      }

      // Scala proporzionale al valore normalizzato t
      var scale = MIN_ARROW_SCALE + t * (MAX_ARROW_SCALE - MIN_ARROW_SCALE);
      var icon = layerType === 'currents'
        ? createCurrentsIcon(angle, color, scale)
        : createWavesIcon(angle, color, scale);
      var m = L.marker([lat, lon], { icon: icon, interactive: true, zIndexOffset: -1000 });

      // Popup con informazioni
      var popup;
      var coordText = formatLatLon(lat, lon);
      if (layerType === 'currents') {
        popup = '<b>Corrente</b><br>' +
          coordText + '<br>' +
          'Velocità: ' + magnitude.toFixed(3) + ' m/s<br>' +
          'Direzione: ' + angle.toFixed(1) + '°<br>' +
          'U: ' + it.u.toFixed(4) + '  V: ' + it.v.toFixed(4);
      } else {
        popup = '<b>Onda</b><br>' +
          coordText + '<br>' +
          'Altezza: ' + magnitude.toFixed(3) + ' m<br>' +
          'Direzione: ' + angle.toFixed(1) + '°<br>' +
          'Periodo: ' + (it.period || 0).toFixed(2) + ' s';
      }
      m.bindPopup(popup);
      markers.push(m);
    }

    var group = L.layerGroup(markers).addTo(map);
    activeLayers[layerType] = group;
    layerVisible[layerType] = true;

    // Aggiorna info label
    var timestamp = weatherData.timestamp || 'N.D.';
    var dataset = weatherData.dataset || 'N.D.';
    var scenarioName = (weatherData.scenario && (weatherData.scenario.scenario_nome || weatherData.scenario.scenario_name)) || '';
    if (layerSource[layerType] === 'route') {
      weatherInfoData[layerType] = 'Dati meteo per scenario: ' + (scenarioName || 'Sconosciuto') + ' ' + timestamp;
    } else {
      weatherInfoData[layerType] = 'Dati meteo in tempo reale: ' + timestamp;
    }
    weatherInfoMeta[layerType] = {
      dataset: dataset,
      source: weatherData.source || (layerSource[layerType] === 'route' ? 'cache/percorso' : 'live'),
      timestamp: timestamp,
      scenarioName: scenarioName || null,
      cacheKey: weatherData.cache_key || null
      , minVal: minVal
      , maxVal: maxVal
    };
    weatherInfoExpanded = false;
    if (weatherInfoControl) weatherInfoControl.update();

    // update vertical color scale
    try { updateScaleDisplay(layerType, minVal, maxVal); } catch(e) { console.warn('weatherManager: updateScaleDisplay failed', e); }

    // Aggiorna stato bottone
    updateButtonState(layerType, true);

    console.log('weatherManager: disegnato layer', layerType, 'con', items.length, 'punti');
  }

  // ---------- Toggle ----------

  function toggleWeatherLayer(layerType) {
    const otherType = layerType === 'waves' ? 'currents' : 'waves';
    
    if (activeLayers[layerType]) {
      // Se è già attivo, disattivalo
      clearWeatherLayer(layerType);
      console.log('weatherManager: rimosso layer', layerType);
    } else {
      // Disattiva l'altro layer se è attivo (esclusione reciproca)
      if (activeLayers[otherType]) {
        clearWeatherLayer(otherType);
        console.log('weatherManager: rimosso layer', otherType);
      }
      
      // Attiva il layer richiesto
      if (routeCacheKeys[layerType]) {
        fetchWeatherLayerFromCache(routeCacheKeys[layerType], layerType);
      } else {
        // Altrimenti carica dati live
        fetchWeatherLayer(layerType);
      }
    }
  }

  // ---------- Fetch dati live ----------

  function fetchWeatherLayer(layerType) {
    
    // Funzione per formattare la data locale nel formato YYYY-MM-DDTHH:MM:SS richiesto
    function getLocalTimestamp() {
      var d = new Date();
      var pad = function(n) { return n < 10 ? '0' + n : n; };
      return d.getFullYear() + '-' +
        pad(d.getMonth() + 1) + '-' +
        pad(d.getDate()) + 'T' +
        pad(d.getHours()) + ':' +
        pad(d.getMinutes()) + ':' +
        pad(d.getSeconds());
    }

    var payload = {
      layer_type: layerType,
      bounds: {
        north: 40.76,
        south: 40.50,
        east: 14.90,
        west: 14.30,
      },
      timestamp: getLocalTimestamp(),
      use_cache: true,
      save_cache: true,
      force_refresh: true,
      max_age_minutes: 15
    };

    console.error('weatherManager: playload per fetch', layerType, JSON.stringify(payload));

    var url = BASE_URL + 'weather/layer/';
    console.log('weatherManager: fetching', layerType, 'from', url);

    // Colora il bottone di rosso durante il caricamento
    setButtonLoading(layerType, true);

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      layerSource[layerType] = 'live';
      drawWeatherLayer(layerType, data);
      // Aggiorna stato bottone quando fetch è completata
      updateButtonState(layerType, true);
    })
    .catch(function(err) {
      console.error('weatherManager: errore fetch', layerType, err);
      updateButtonState(layerType, false);
    });
  }

  // ---------- Fetch da cache (per percorso) ----------

  function fetchWeatherLayerFromCache(cacheKey, layerType) {
    var url = BASE_URL + 'weather/cache/layer/' + encodeURIComponent(cacheKey);
    console.log('weatherManager: fetching cache', layerType || 'auto', 'key:', cacheKey);

    // Determina il tipo per il bottone (se non specificato, usa 'currents' come default per loading)
    var btnLayerType = layerType || 'currents';
    // Colora il bottone di rosso durante il caricamento
    setButtonLoading(btnLayerType, true);

    fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    })
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      // Determina il tipo dal dataset se non specificato
      var type = layerType;
      if (!type) {
        if (data.dataset && data.dataset.indexOf('wav') !== -1) {
          type = 'waves';
        } else {
          type = 'currents';
        }
      }
      layerSource[type] = 'route';
      drawWeatherLayer(type, data);
      // Aggiorna stato bottone quando fetch è completata
      updateButtonState(type, true);
    })
    .catch(function(err) {
      console.error('weatherManager: errore fetch cache', cacheKey, err);
      updateButtonState(btnLayerType, false);
    });
  }

  // ---------- Carica dati meteo di un percorso ----------

  function loadRouteWeather(percorsoId) {
    var url = BASE_URL + 'percorso/' + encodeURIComponent(percorsoId);
    console.log('weatherManager: loading route weather for', percorsoId);

    fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    })
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      var keys = data.weather_cache_keys;
      if (!keys) {
        console.warn('weatherManager: nessuna weather_cache_keys per percorso', percorsoId);
        return;
      }
      // Salva le cache keys del percorso corrente
      routeCacheKeys.waves = keys.waves || null;
      routeCacheKeys.currents = keys.currents || null;
      if (keys.waves) {
        fetchWeatherLayerFromCache(keys.waves, 'waves');
      }
      if (keys.currents) {
        fetchWeatherLayerFromCache(keys.currents, 'currents');
      }
    })
    .catch(function(err) {
      console.error('weatherManager: errore loading route weather', percorsoId, err);
    });
  }

  // ---------- Clear ----------

  function clearWeatherLayer(layerType) {
    if (activeLayers[layerType]) {
      map.removeLayer(activeLayers[layerType]);
      activeLayers[layerType] = null;
    }
    layerVisible[layerType] = false;
    layerSource[layerType] = null;
    weatherInfoData[layerType] = null;
    weatherInfoMeta[layerType] = null;
    weatherInfoExpanded = false;
    if (weatherInfoControl) weatherInfoControl.update();
    updateButtonState(layerType, false);
    // hide scale when layer removed
    try { hideScaleDisplay(); } catch(e) {}
  }

  function clearAllWeather() {
    clearWeatherLayer('waves');
    clearWeatherLayer('currents');
    routeCacheKeys.waves = null;
    routeCacheKeys.currents = null;
  }

  // ---------- UI bottoni ----------

  function syncWeatherButtons() {
    var busy = loadingLayers.waves || loadingLayers.currents;
    ['waves', 'currents'].forEach(function(type) {
      var btnId = type === 'waves' ? 'btn-weather-waves' : 'btn-weather-currents';
      var btn = document.getElementById(btnId);
      if (!btn) return;
      btn.disabled = busy;
      btn.classList.toggle('loading', loadingLayers[type]);
    });
  }

  function setButtonLoading(layerType, isLoading) {
    loadingLayers[layerType] = !!isLoading;
    syncWeatherButtons();
  }

  function updateButtonState(layerType, active) {
    loadingLayers[layerType] = false;
    var btnId = layerType === 'waves' ? 'btn-weather-waves' : 'btn-weather-currents';
    var btn = document.getElementById(btnId);
    if (btn) {
      if (active) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
    syncWeatherButtons();
  }

  // ---------- Esponi API globale ----------

  window.weatherManager = {
    drawWeatherLayer: drawWeatherLayer,
    toggleWeatherLayer: toggleWeatherLayer,
    fetchWeatherLayer: fetchWeatherLayer,
    fetchWeatherLayerFromCache: fetchWeatherLayerFromCache,
    loadRouteWeather: loadRouteWeather,
    clearWeatherLayer: clearWeatherLayer,
    clearAllWeather: clearAllWeather,
    isActive: function(type) { return !!activeLayers[type]; },
    getSource: function(type) { return layerSource[type]; }
  };

})();
