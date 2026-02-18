
// Weather Overlay Logic

let activeWeatherLayerGroup = L.layerGroup();
let currentLayerType = null;

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

    if (window.pyMain && window.pyMain.getWeatherData) {
        console.log(`Fetching weather data for: ${type}`);
        // Pass bounds as JSON string
        window.pyMain.getWeatherData(type, JSON.stringify(boundsObj), function(data) {
            console.log("Weather data received:", data ? data.length : 0);
            renderWeatherData(type, data);
        });
    } else {
        console.warn("pyMain.getWeatherData not available");
        // Fallback or retry logic could go here
    }
}

function renderWeatherData(type, data) {
    if (!data || !window.map) return;
    
    // Add layer group to map if not already present
    activeWeatherLayerGroup.addTo(window.map);

    data.forEach(point => {
        let lat = point.lat;
        let lon = point.lon;
        let iconHtml = '';
        let rotation = 0;
        let color = 'black';
        let size = 20;

        if (type === 'currents') {
            // Calculate magnitude and angle from u, v
            const u = point.u;
            const v = point.v;
            const magnitude = Math.sqrt(u*u + v*v);
            const angleRad = Math.atan2(v, u); // Math.atan2(y, x) -> (North, East) standard is (v, u)
            // Convert to degrees. 0 deg is East (standard math).
            // Need to align with map where North is up?
            // Usually current direction is "flow towards".
            // atan2(v, u) gives angle from X-axis (East) counter-clockwise.
            // Map rotation: 0 is North?
            // Let's assume standard math angle and adjust for SVG which usually points Up or Right.
            // If Arrow points Up (North) in SVG:
            // Math angle 0 (East) -> Rot -90?
            // Actually: Map uses geographic bearing (0 is North, 90 East).
            // Math: 0 is East, 90 is North.
            // bearing = 90 - math_deg
            let angleDeg = angleRad * (180 / Math.PI);
            let mapRotation = 90 - angleDeg; 
             
            // Scale size by magnitude? simple scaling
            size = 15 + (magnitude * 20); // base 15 + scaling
            if (size > 50) size = 50;

            rotation = mapRotation;
            color = 'blue';
            
            // Simple Arrow
            iconHtml = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg); overflow: visible;">
                <path d="M12 2L12 22M12 2L7 9M12 2L17 9" stroke="${color}" stroke-width="2" fill="none" />
            </svg>`;
            
        } else if (type === 'waves') {
            // point.dir is "from direction" (Where waves come FROM).
            // Arrow usually shows where waves go TO. So rotate 180?
            // "Sea surface wind wave from direction (VMDR_WW)"
            // If wind is from North (0), it blows South (180).
            // We usually visualize Flow Direction.
            let fromDir = point.dir;
            let toDir = (fromDir + 180) % 360;
            
            rotation = toDir;
            
            // Color based on height?
            // < 0.5 green, 0.5-1.5 yellow, > 1.5 red
            let h = point.height;
            if (h < 0.5) color = 'green';
            else if (h < 1.5) color = 'orange';
            else color = 'red';
            
            size = 24;

            // Wave icon (arrow with wiggly tail?) or just arrow.
            iconHtml = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg); overflow: visible;">
                 <path d="M12 2L12 18M12 2L7 9M12 2L17 9" stroke="${color}" stroke-width="2" fill="none" />
                 <path d="M7 20 Q 9.5 22 12 20 T 17 20" stroke="${color}" stroke-width="2" fill="none" />
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
