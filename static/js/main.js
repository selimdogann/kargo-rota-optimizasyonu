// Kocaeli Kargo Dağıtım Sistemi - Ana JavaScript Dosyası

// API URL
const API_BASE = '';

// Rota Renkleri
const ROUTE_COLORS = ['#e74c3c', '#3498db', '#27ae60', '#f39c12', '#9b59b6', '#1abc9c'];

// Kocaeli İlçe Koordinatları
const KOCAELI_DISTRICTS = {
    'İzmit': { lat: 40.7656, lng: 29.9406 },
    'Gebze': { lat: 40.8027, lng: 29.4307 },
    'Darıca': { lat: 40.7694, lng: 29.3753 },
    'Çayırova': { lat: 40.8267, lng: 29.3728 },
    'Dilovası': { lat: 40.7847, lng: 29.5369 },
    'Körfez': { lat: 40.7539, lng: 29.7636 },
    'Derince': { lat: 40.7544, lng: 29.8389 },
    'Gölcük': { lat: 40.7175, lng: 29.8306 },
    'Karamürsel': { lat: 40.6917, lng: 29.6167 },
    'Kandıra': { lat: 41.0706, lng: 30.1528 },
    'Kartepe': { lat: 40.7389, lng: 30.0378 },
    'Başiskele': { lat: 40.7244, lng: 29.9097 }
};

// Harita yardımcı fonksiyonları
function createCustomMarker(station, isDepot = false) {
    const color = isDepot ? '#e74c3c' : '#3498db';
    const size = isDepot ? 45 : 35;
    
    return L.divIcon({
        className: 'custom-marker',
        html: `<div style="
            background: ${color};
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: ${isDepot ? '1.2rem' : '0.9rem'};
            border: ${isDepot ? 4 : 3}px solid white;
            box-shadow: 0 ${isDepot ? 4 : 3}px ${isDepot ? 15 : 10}px rgba(0,0,0,0.3);
        ">${station.name ? station.name.charAt(0) : 'D'}</div>`,
        iconSize: [size, size],
        iconAnchor: [size/2, size/2]
    });
}

// API İşlemleri
const API = {
    // İstasyonlar
    async getStations() {
        const response = await fetch(`${API_BASE}/api/stations`);
        return response.json();
    },
    
    async addStation(station) {
        const response = await fetch(`${API_BASE}/api/stations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(station)
        });
        return response.json();
    },
    
    async deleteStation(id) {
        const response = await fetch(`${API_BASE}/api/stations/${id}`, {
            method: 'DELETE'
        });
        return response.json();
    },
    
    // Kargolar
    async getCargos() {
        const response = await fetch(`${API_BASE}/api/cargos`);
        return response.json();
    },
    
    async addCargo(cargo) {
        const response = await fetch(`${API_BASE}/api/cargos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cargo)
        });
        return response.json();
    },
    
    async trackCargo(trackingNo) {
        const response = await fetch(`${API_BASE}/api/cargos/track/${trackingNo}`);
        return response.json();
    },
    
    // Araçlar
    async getVehicles() {
        const response = await fetch(`${API_BASE}/api/vehicles`);
        return response.json();
    },
    
    async addVehicle(vehicle) {
        const response = await fetch(`${API_BASE}/api/vehicles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(vehicle)
        });
        return response.json();
    },
    
    // Rotalar
    async getActiveRoutes() {
        const response = await fetch(`${API_BASE}/api/routes/active`);
        return response.json();
    },
    
    async optimizeRoutes(date) {
        const response = await fetch(`${API_BASE}/api/routes/optimize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: date })
        });
        return response.json();
    },
    
    // Senaryolar
    async runScenario(scenarioId) {
        const response = await fetch(`${API_BASE}/api/scenarios/test/${scenarioId}`, {
            method: 'POST'
        });
        return response.json();
    },
    
    // Analizler
    async getSummary() {
        const response = await fetch(`${API_BASE}/api/analytics/summary`);
        return response.json();
    },
    
    async getCostBreakdown() {
        const response = await fetch(`${API_BASE}/api/analytics/cost-breakdown`);
        return response.json();
    }
};

// Utility Fonksiyonları
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('tr-TR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY'
    }).format(amount);
}

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast show position-fixed top-0 end-0 m-3 bg-${type}`;
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="toast-header bg-${type} text-white">
            <strong class="me-auto">Bildirim</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body bg-white">${message}</div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 5000);
}

function showLoading(show = true) {
    let overlay = document.getElementById('loadingOverlay');
    
    if (show && !overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = '<div class="loading-spinner"></div>';
        document.body.appendChild(overlay);
    } else if (!show && overlay) {
        overlay.remove();
    }
}

// OSRM API ile gerçek yol rotası al
async function getOSRMRoute(coordinates) {
    // coordinates: [[lat, lng], [lat, lng], ...]
    if (!coordinates || coordinates.length < 2) return null;
    
    // OSRM formatı: lng,lat;lng,lat;...
    const coordString = coordinates.map(c => `${c[1]},${c[0]}`).join(';');
    
    const url = `https://router.project-osrm.org/route/v1/driving/${coordString}?overview=full&geometries=geojson`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
            // GeoJSON koordinatlarını Leaflet formatına çevir [lng, lat] -> [lat, lng]
            const routeCoords = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
            return {
                coordinates: routeCoords,
                distance: data.routes[0].distance / 1000, // metre -> km
                duration: data.routes[0].duration // saniye
            };
        }
    } catch (error) {
        console.error('OSRM routing error:', error);
    }
    return null;
}

// Çoklu nokta için OSRM rotası çiz (haritaya ekle)
async function drawOSRMRoute(map, waypoints, color = '#3498db', weight = 5) {
    const route = await getOSRMRoute(waypoints);
    
    if (route && route.coordinates.length > 0) {
        const polyline = L.polyline(route.coordinates, {
            color: color,
            weight: weight,
            opacity: 0.8,
            smoothFactor: 1
        }).addTo(map);
        
        return { polyline, distance: route.distance, duration: route.duration };
    }
    
    // Fallback: OSRM başarısız olursa düz çizgi çiz
    console.warn('OSRM failed, falling back to straight line');
    const polyline = L.polyline(waypoints, {
        color: color,
        weight: weight,
        opacity: 0.6,
        dashArray: '10, 10'
    }).addTo(map);
    
    return { polyline, distance: null, duration: null };
}

// Haversine mesafe hesaplama
function haversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Dünya yarıçapı (km)
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Rastgele takip numarası oluştur
function generateTrackingNumber() {
    const prefix = 'KOC';
    const timestamp = Date.now().toString().slice(-6);
    const random = Math.random().toString(36).substring(2, 6).toUpperCase();
    return `${prefix}${timestamp}${random}`;
}

// Export
window.CargoSystem = {
    API,
    ROUTE_COLORS,
    KOCAELI_DISTRICTS,
    createCustomMarker,
    formatDate,
    formatCurrency,
    showNotification,
    showLoading,
    haversineDistance,
    generateTrackingNumber,
    getOSRMRoute,
    drawOSRMRoute
};
