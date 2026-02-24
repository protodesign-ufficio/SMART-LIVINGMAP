
// Weather Overlay Logic

let activeWeatherLayerGroup = L.layerGroup();
let currentLayerType = null;
window.currentWeatherTime = null; // null = real-time/latest

/**
 * Sets the reference time for weather data.
 * @param {string|null} isoStr - ISO timestamp string, or null for real-time.
 */
window.setWeatherTime = function(isoStr) {
    window.currentWeatherTime = isoStr;
    console.log('Weather time updated to:', isoStr || 'Real-time');

    // // Update timestamp label visually immediately to reflect intent
    // const el = document.getElementById('weather-timestamp');
    // if (el) {
    //     if (!isoStr) {
    //          // Let the next updateWeatherLayer call refresh the actual time
    //     } else {
    //          el.textContent = `Richiesta meteo: ${isoStr}`;
    //          el.style.backgroundColor = '#fff3cd'; // Light yellow to indicate non-realtime
    //          el.classList.remove('hidden');
    //     }
    // }

    // Refresh if active
    if (currentLayerType) {
        selectWeatherLayer(currentLayerType);
    }
}

function toggleWeatherMenu() {
    const menu = document.getElementById('weather-menu');
    if (menu) {
        menu.classList.toggle('hidden');
    }
}

function selectWeatherLayer(type) {
    // Hide menu after selection
    const menu = document.getElementById('weather-menu');
    if (menu) {
        menu.classList.add('hidden');
    }

    // Clear existing layer
    if (activeWeatherLayerGroup) {
        activeWeatherLayerGroup.clearLayers();
        activeWeatherLayerGroup.removeFrom(window.map);
    }
    
    // Clear timestamp
    updateTimestamp(null);

    currentLayerType = type;
    
    if (!type) {
        return; // "None" selected
    }

    // Fetch data from backend
    // Get current map bounds
    const bounds = window.map.getBounds();
    const boundsObj = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest()
    };

    if (window.pyMain && window.pyMain.getWeatherDataT) {
        console.log(`Fetching weather data for: ${type} at time: ${window.currentWeatherTime || 'Real-time'}`);
        // Pass bounds as JSON string
        fetchWeatherData(type, boundsObj);
    } else if (window.pyMain && window.pyMain.getWeatherData) {
         // Fallback if updated signature not deployed yet? No, we updated Python.
         // Pass explicit timestamp or null
         window.pyMain.getWeatherData(type, JSON.stringify(boundsObj), window.currentWeatherTime, function(response) {
            
            // Handle both legacy (list) and new (dict) response formats
            let data = response;
            let timestamp = null;
            let range = { min: 0, max: 1 };
            
            if (response && !Array.isArray(response) && response.items) {
                data = response.items;
                timestamp = response.timestamp;
                if (response.range) range = response.range;
            } else if (response && response.error) {
                console.error("Weather error:", response.error);
                return;
            } else if (response && response.items) {
                // Should match above, but just in case
                data = response.items;
                timestamp = response.timestamp;
                if (response.range) range = response.range;
            }

            console.log("Weather data received:", data ? data.length : 0);
            renderWeatherData(type, data, range);
            updateTimestamp(timestamp);
        });
    } else {
        console.warn("pyMain.getWeatherData not available");
        // Fallback or retry logic could go here
    }
}

function updateTimestamp(ts) {
    const el = document.getElementById('weather-timestamp');
    if (!el) return;
    
    if (ts) {
        // Parse the timestamp string returned by backend
        let displayTime = ts.replace('T', ' ');
        // If we requested a specific time, indicate it clearly
        if (window.currentWeatherTime) {
            el.innerHTML = `<strong>Overlay del:</strong>&nbsp;${displayTime} (Pianificato)`;
            el.style.backgroundColor = '#fff3cd'; 
        } else {
            el.innerHTML = `<strong>Overlay del:</strong>&nbsp;${displayTime} (In tempo reale)`;
            el.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
        }
        el.classList.remove('hidden');
    } else {
        el.classList.add('hidden');
    }
}

function renderWeatherData(type, data, range) {
    if (!data || !window.map) return;
    
    // Safety check just in case range is missing from call
    if (!range) range = { min: 0, max: 1 };
    
    // Add layer group to map if not already present
    activeWeatherLayerGroup.addTo(window.map);

    // Min/Max Arrow Sizes (px)
    const MIN_SIZE = 20;
    const MAX_SIZE = 50;

    data.forEach(point => {
        let lat = point.lat;
        let lon = point.lon;
        let iconHtml = '';
        let rotation = 0;
        let color = 'black';
        let size = MIN_SIZE;
        let factor = 0; // 0 to 1 scaling factor

        if (type === 'currents') {
            // Calculate magnitude and angle from u, v
            const u = point.u;
            const v = point.v;
            const magnitude = Math.sqrt(u*u + v*v);
            const angleRad = Math.atan2(v, u); 

            let angleDeg = angleRad * (180 / Math.PI);
            let mapRotation = 90 - angleDeg; 
             
            // Scale size by relative magnitude within dataset range
            // Avoid division by zero if all values are same
            const denom = ((range.max - range.min) || 1) * 2;
            factor = (magnitude - range.min) / denom;
            factor = Math.max(0, Math.min(1, factor)); // clamp
            
            size = MIN_SIZE + (factor * (MAX_SIZE - MIN_SIZE));

            rotation = mapRotation;
            color = 'blue';
            
            // Simple Arrow
            iconHtml = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg); overflow: visible;">
                <path d="M12 2L12 22M12 2L7 9M12 2L17 9" stroke="${color}" opacity="0.6" stroke-width="2" fill="none" />
            </svg>`;
            
        } else if (type === 'waves') {
            // point.dir is "from direction"
            let fromDir = point.dir;
            let toDir = (fromDir + 180) % 360;
            rotation = toDir;
            
            // Use Wave Height for scaling and color
            let h = point.height;
            if (h < 0.5) color = 'green';
            else if (h < 1.5) color = 'orange';
            else color = 'red';
            
            // Scale size
            const denom = ((range.max - range.min) || 1) * 2;
            factor = (h - range.min) / denom;
            factor = Math.max(0, Math.min(1, factor)); // clamp
            
            size = MIN_SIZE + (factor * (MAX_SIZE - MIN_SIZE));
            
            // Limit aspect ratio distortion or keep bounding box?
            // SVG viewBox is constant 24x24, we scale the divIcon size.

            iconHtml = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg); overflow: visible;">
                 <path d="M12 2L12 18M12 2L7 9M12 2L17 9" stroke="${color}" opacity="0.6" stroke-width="2" fill="none" />
                 <path d="M7 20 Q 9.5 22 12 20 T 17 20" stroke="${color}" opacity="0.6" stroke-width="2" fill="none" />
            </svg>`;
        }

        const icon = L.divIcon({
            className: 'weather-icon',
            html: iconHtml,
            iconSize: [size, size],
            iconAnchor: [size/2, size/2]
        });

        const marker = L.marker([lat, lon], {icon: icon});
        
        // Popup with details
        let popupContent = `<b>${type === 'currents' ? 'Corrente' : 'Onde'}</b><br>`;
        if (type === 'currents') {
            popupContent += `Velocità U: ${point.u.toFixed(2)} m/s<br>`;
            popupContent += `Velocità V: ${point.v.toFixed(2)} m/s<br>`;
            popupContent += `Mag: ${Math.sqrt(point.u**2 + point.v**2).toFixed(2)} m/s`;
        } else {
            popupContent += `Altezza: ${point.height.toFixed(2)} m<br>`;
            popupContent += `Direzione: ${point.dir.toFixed(0)}°<br>`;
            popupContent += `Periodo: ${point.period.toFixed(1)} s`;
        }
        marker.bindPopup(popupContent);
        
        activeWeatherLayerGroup.addLayer(marker);
    });
}
