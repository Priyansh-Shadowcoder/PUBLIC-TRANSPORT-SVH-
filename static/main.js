// ==========================================
// 1. UI & Login Logic
// ==========================================
function setRole(role) {
    // Update the hidden role inputs in BOTH forms
    document.querySelectorAll('.roleInput').forEach(input => input.value = role);
    
    const btnPublic = document.getElementById('btnPublic');
    const btnAdmin = document.getElementById('btnAdmin');
    
    // Change UI text based on Role
    if(role === 'gov') {
        btnAdmin.classList.replace('btn-secondary', 'btn-primary');
        btnPublic.classList.replace('btn-primary', 'btn-secondary');
        document.getElementById('formTitle').innerText = 'Command Center';
        document.getElementById('formSubtitle').innerText = 'Authorized administrator portal';
    } else {
        btnPublic.classList.replace('btn-secondary', 'btn-primary');
        btnAdmin.classList.replace('btn-primary', 'btn-secondary');
        document.getElementById('formTitle').innerText = 'Citizen Portal';
        document.getElementById('formSubtitle').innerText = 'Access your commuter account';
    }
}

function toggleAuthMode(mode) {
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');
    
    if (mode === 'signup') {
        loginForm.style.display = 'none';
        signupForm.style.display = 'block';
    } else {
        signupForm.style.display = 'none';
        loginForm.style.display = 'block';
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.style.display = 'none');
    document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));
    
    document.getElementById(tabId).style.display = 'block';
    event.currentTarget.classList.add('active');

    if (tabId === 'live-map') initGTFSMap();
}

// ==========================================
// 2. Map & Routing (Leaflet + C++)
// ==========================================
let gtfsMap = null; 
let currentRouteLine = null;
let animatedBusMarker = null;

function initGTFSMap() {
    if (gtfsMap !== null) {
        // Add a slight delay to allow CSS transitions to finish
        setTimeout(() => gtfsMap.invalidateSize(), 150); 
        return; 
    }
    gtfsMap = L.map('gtfs-map-container').setView([23.2599, 77.4126], 6); // Default: Bhopal
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(gtfsMap);
    
    // Force size recalculation on first load
    setTimeout(() => gtfsMap.invalidateSize(), 150);
}

async function geocodeCity(cityName) {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${cityName}`);
    const data = await res.json();
    return data.length > 0 ? { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) } : null;
}

async function calculateRoute() {
    const src = document.getElementById('source').value;
    const dest = document.getElementById('destination').value;
    if (!src || !dest) return alert("Enter source and destination.");

    const srcCoords = await geocodeCity(src);
    const destCoords = await geocodeCity(dest);
    if (!srcCoords || !destCoords) return alert("Could not geocode locations.");

    // Fetch OSRM Road Geometry
    const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${srcCoords.lon},${srcCoords.lat};${destCoords.lon},${destCoords.lat}?overview=full&geometries=geojson`;
    const res = await fetch(osrmUrl);
    const routeData = await res.json();

    if (currentRouteLine) gtfsMap.removeLayer(currentRouteLine);

    if (routeData.routes && routeData.routes.length > 0) {
        const coords = routeData.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
        currentRouteLine = L.polyline(coords, { color: '#1565C0', weight: 5 }).addTo(gtfsMap);
        gtfsMap.fitBounds(currentRouteLine.getBounds());
    }

    // Ping Custom C++ Router Engine via Flask
    const payload = {
        src_lat: srcCoords.lat, src_lon: srcCoords.lon,
        dest_lat: destCoords.lat, dest_lon: destCoords.lon
    };

    const cppRes = await fetch('/api/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const result = await cppRes.json();
    if(result.error) alert(`C++ Engine Error: ${result.error}`);
    else alert(`Route Plotted! Shortest distance calculated by engine: ${result.distance_km} km`);
}

// ==========================================
// 3. User Management (Gov Dashboard)
// ==========================================

function openEditUserModal(id, name, email) {
    // Populate the hidden form fields with the user's current data
    document.getElementById('editUserId').value = id;
    document.getElementById('editUserName').value = name;
    document.getElementById('editUserEmail').value = email;
    
    // Trigger the CSS visibility animation
    document.getElementById('editUserModal').classList.add('active');
}

function closeEditUserModal() {
    // Hide the modal
    document.getElementById('editUserModal').classList.remove('active');
}

// Auto-init specific dashboard components
document.addEventListener("DOMContentLoaded", () => {
    if(document.getElementById('gtfs-map-container')) initGTFSMap();
});