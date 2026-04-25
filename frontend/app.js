/* =============================================================
   VW California AI Trip Planner — Application Logic
   Handles: Chat, Map, Travel Memory, API Communication
   ============================================================= */

// ── State ────────────────────────────────────────────────────
const state = {
    currentMode: 'planning',    // 'planning' | 'memory'
    map: null,                   // Google Maps instance
    markers: [],                 // Active map markers
    routePolylines: [],          // Active route lines
    currentTrip: null,           // Current trip data
    chatHistory: [],             // Chat messages
    isTyping: false,             // AI typing state
    campingMarkers: [],          // Camping location markers
};

// ── API Client ───────────────────────────────────────────────
const API_BASE = '';

async function apiCall(endpoint, data = {}) {
    try {
        const response = await fetch(`${API_BASE}/api/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return await response.json();
    } catch (error) {
        console.error(`API error (${endpoint}):`, error);
        return { status: 'error', message: 'Connection failed. Please try again.' };
    }
}

// ── Map Initialization ───────────────────────────────────────
function initMap() {
    // Center on Central Europe (VW California territory)
    state.map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 47.5, lng: 13.0 },
        zoom: 6,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        zoomControl: true,
        zoomControlOptions: {
            position: google.maps.ControlPosition.RIGHT_CENTER,
        },
        styles: [
            // Subtle VW-branded map styling
            { featureType: 'water', stylers: [{ color: '#C5D7E8' }] },
            { featureType: 'landscape', stylers: [{ color: '#F0F3F7' }] },
            { featureType: 'road.highway', stylers: [{ color: '#E0E4EA' }] },
            { featureType: 'road.highway', elementType: 'labels.text.fill', stylers: [{ color: '#4A5568' }] },
            { featureType: 'poi.park', stylers: [{ color: '#D4E6D0' }] },
            { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
        ],
    });

    // Map control buttons
    document.getElementById('btn-center-map').addEventListener('click', () => {
        if (state.currentTrip) {
            fitMapToTrip();
        } else {
            state.map.setCenter({ lat: 47.5, lng: 13.0 });
            state.map.setZoom(6);
        }
    });

    document.getElementById('btn-toggle-campings').addEventListener('click', loadCampingsOnMap);
}

// ── Map Helpers ──────────────────────────────────────────────
function clearMapOverlays() {
    state.markers.forEach(m => m.setMap(null));
    state.markers = [];
    if (state.routePolylines) {
        state.routePolylines.forEach(p => p.setMap(null));
    }
    state.routePolylines = [];
}

function clearCampingMarkers() {
    state.campingMarkers.forEach(m => m.setMap(null));
    state.campingMarkers = [];
}

function addMarker(lat, lng, title, icon, label) {
    const marker = new google.maps.Marker({
        position: { lat, lng },
        map: state.map,
        title: title,
        label: label || undefined,
        icon: icon ? {
            url: icon,
            scaledSize: new google.maps.Size(32, 32),
        } : undefined,
        animation: google.maps.Animation.DROP,
    });

    // Info window
    const infoWindow = new google.maps.InfoWindow({
        content: `<div style="font-family: Helvetica, Arial, sans-serif; padding: 4px;">
            <strong style="color: #001E50;">${title}</strong>
        </div>`,
    });

    marker.addListener('click', () => {
        infoWindow.open(state.map, marker);
    });

    state.markers.push(marker);
    return marker;
}

function drawDailyRoutes(daily_schedules, color = '#001E50') {
    if (!state.routePolylines) state.routePolylines = [];
    
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];

    daily_schedules.forEach(day => {
        let path = [];
        // Decode precise path if available
        if (day.route_polyline && google.maps.geometry && google.maps.geometry.encoding) {
            path = google.maps.geometry.encoding.decodePath(day.route_polyline);
        } else {
            // Fallback to straight lines
            path = day.waypoints.map(wp => ({ lat: wp.lat, lng: wp.lng }));
        }

        const polyline = new google.maps.Polyline({
            path: path,
            geodesic: true,
            strokeColor: color,
            strokeOpacity: 0.85,
            strokeWeight: 4,
            map: state.map,
        });
        
        state.routePolylines.push(polyline);
    });
}

function fitMapToTrip() {
    if (!state.currentTrip) return;

    const bounds = new google.maps.LatLngBounds();
    state.markers.forEach(m => bounds.extend(m.getPosition()));
    state.map.fitBounds(bounds, { padding: 80 });
}

// ── Display Trip on Map ──────────────────────────────────────
function displayTripOnMap(tripData) {
    clearMapOverlays();

    const { trip, daily_schedules } = tripData;
    state.currentTrip = tripData;

    // Collect all waypoints for the route
    const allWaypoints = [];
    let totalStops = 0;

    daily_schedules.forEach((day, idx) => {
        day.waypoints.forEach(wp => {
            allWaypoints.push(wp);

            // Add marker with appropriate icon
            let markerLabel = '';
            if (wp.type === 'start' && idx === 0) {
                markerLabel = 'A';
            } else if (wp.type === 'end' || (wp.type === 'camping' && idx === daily_schedules.length - 1)) {
                markerLabel = 'B';
            } else if (wp.type === 'camping') {
                markerLabel = '🏕️';
                totalStops++;
            }

            addMarker(wp.lat, wp.lng, wp.label, null, markerLabel || undefined);
        });
    });

    // Draw precise daily route lines
    if (daily_schedules && daily_schedules.length > 0) {
        drawDailyRoutes(daily_schedules);
    }

    // Update trip info card
    document.getElementById('trip-title').textContent = trip.title;
    document.getElementById('stat-days').textContent = daily_schedules.length;
    document.getElementById('stat-km').textContent = Math.round(tripData.total_driving_km || 0);
    document.getElementById('stat-hours').textContent = `${(tripData.total_driving_hours || 0).toFixed(1)}h`;
    document.getElementById('stat-campings').textContent = totalStops;

    // Build day cards
    const dayCardsContainer = document.getElementById('day-cards');
    dayCardsContainer.innerHTML = '';

    daily_schedules.forEach(day => {
        const card = document.createElement('div');
        card.className = 'day-card';
        card.innerHTML = `
            <div class="day-number">Day ${day.day_number}</div>
            <div class="day-label">${day.date}</div>
            <div class="day-stats">
                <span>🚗 ${day.driving_hours}h</span>
                <span>📏 ${Math.round(day.driving_km)}km</span>
            </div>
        `;

        card.addEventListener('click', () => {
            // Zoom to this day's waypoints
            const bounds = new google.maps.LatLngBounds();
            day.waypoints.forEach(wp => {
                bounds.extend({ lat: wp.lat, lng: wp.lng });
            });
            state.map.fitBounds(bounds, { padding: 100 });

            // Highlight active card
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
        });

        dayCardsContainer.appendChild(card);
    });

    // Show trip info card
    document.getElementById('trip-info-card').classList.add('visible');

    // Fit map to show entire trip
    fitMapToTrip();
}

// ── Display Campings on Map ──────────────────────────────────
function displayCampingsOnMap(campings) {
    clearCampingMarkers();

    campings.forEach(camp => {
        const marker = new google.maps.Marker({
            position: { lat: camp.lat, lng: camp.lng },
            map: state.map,
            title: camp.name,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                fillColor: '#00875A',
                fillOpacity: 0.9,
                strokeColor: '#FFFFFF',
                strokeWeight: 2,
                scale: 8,
            },
            animation: google.maps.Animation.DROP,
        });

        // Build info content
        let amenities = [];
        if (camp.has_power) amenities.push('⚡ Power');
        if (camp.has_water) amenities.push('💧 Water');
        if (camp.has_wifi) amenities.push('📶 WiFi');
        if (camp.has_showers) amenities.push('🚿 Showers');

        const infoContent = `
            <div style="font-family: Helvetica, Arial, sans-serif; padding: 4px; max-width: 220px;">
                <strong style="color: #001E50; font-size: 14px;">${camp.name}</strong>
                ${camp.cost_per_night_eur ? `<div style="color: #00875A; font-weight: 600; margin: 4px 0;">€${camp.cost_per_night_eur}/night</div>` : ''}
                ${camp.rating ? `<div style="color: #666; font-size: 12px;">⭐ ${camp.rating}/5 (${camp.review_count || 0} reviews)</div>` : ''}
                ${amenities.length ? `<div style="color: #666; font-size: 12px; margin-top: 4px;">${amenities.join(' · ')}</div>` : ''}
                ${camp.distance_km ? `<div style="color: #999; font-size: 11px; margin-top: 4px;">${camp.distance_km}km away</div>` : ''}
            </div>
        `;

        const infoWindow = new google.maps.InfoWindow({ content: infoContent });
        marker.addListener('click', () => infoWindow.open(state.map, marker));

        state.campingMarkers.push(marker);
    });
}

async function loadCampingsOnMap() {
    const center = state.map.getCenter();
    const result = await apiCall('search_campings', {
        lat: center.lat(),
        lng: center.lng(),
        radius_km: 80,
    });

    if (result.status === 'success' && result.results) {
        displayCampingsOnMap(result.results);
    }
}

// ── Chat Logic ───────────────────────────────────────────────
function addMessage(role, text) {
    const messagesEl = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome');

    // Hide welcome on first message
    if (welcome) {
        welcome.style.display = 'none';
    }

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    // Parse markdown-like formatting for assistant messages
    let formattedText = text;
    if (role === 'assistant') {
        formattedText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    msgDiv.innerHTML = `
        <div class="message-bubble">${formattedText}</div>
        <div class="message-meta">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
    `;

    // Insert before typing indicator
    const typingEl = document.getElementById('typing-indicator');
    messagesEl.insertBefore(msgDiv, typingEl);

    // Scroll to bottom
    messagesEl.scrollTop = messagesEl.scrollHeight;

    state.chatHistory.push({ role, text });
}

function showTyping(show) {
    state.isTyping = show;
    const typingEl = document.getElementById('typing-indicator');
    typingEl.classList.toggle('visible', show);

    if (show) {
        const messagesEl = document.getElementById('chat-messages');
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }
}

async function sendMessage(text) {
    if (!text.trim() || state.isTyping) return;

    // Add user message
    addMessage('user', text);

    // Clear input
    const input = document.getElementById('chat-input');
    input.value = '';
    input.style.height = 'auto';

    // Show typing indicator
    showTyping(true);

    // Send to API
    const result = await apiCall('chat', { message: text });

    // Hide typing
    showTyping(false);

    if (result.status === 'success' || result.status === 'partial') {
        addMessage('assistant', result.text);

        // If tool calls returned trip data, display on map
        if (result.tool_calls) {
            result.tool_calls.forEach(tc => {
                if (tc.function_name === 'plan_route' && tc.result && tc.result.status === 'success') {
                    displayTripOnMap(tc.result);
                }
                if (tc.function_name === 'search_campings' && tc.result && tc.result.results) {
                    displayCampingsOnMap(tc.result.results);
                }
            });
        }

        // Check for embedded trip/camping data in response
        if (result.trip_data) {
            displayTripOnMap(result.trip_data);
        }
        if (result.camping_data) {
            displayCampingsOnMap(result.camping_data);
        }
    } else {
        addMessage('assistant', result.message || 'Sorry, something went wrong. Please try again.');
    }
}

// ── Mode Switching ───────────────────────────────────────────
function switchMode(mode) {
    state.currentMode = mode;

    // Update tab styles
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === mode);
    });

    // Show/hide panels
    document.getElementById('planning-panel').style.display =
        mode === 'planning' ? 'flex' : 'none';
    document.getElementById('memory-panel').style.display =
        mode === 'memory' ? 'flex' : 'none';
    document.getElementById('memory-panel').classList.toggle('active', mode === 'memory');
}

// ── Photo Upload (Travel Memory) ─────────────────────────────
async function handlePhotoUpload(files) {
    const grid = document.getElementById('photo-grid');

    for (const file of files) {
        // Create preview card
        const card = document.createElement('div');
        card.className = 'photo-card';

        const reader = new FileReader();
        reader.onload = (e) => {
            card.innerHTML = `
                <img src="${e.target.result}" alt="${file.name}">
                <div class="photo-overlay">${file.name}</div>
            `;
        };
        reader.readAsDataURL(file);

        grid.appendChild(card);

        // Upload to server
        const formData = new FormData();
        formData.append('photo', file);

        try {
            const response = await fetch(`${API_BASE}/api/upload_photo`, {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();

            // If photo has GPS, add marker to map
            if (result.photo && result.photo.lat && result.photo.lng) {
                addMarker(result.photo.lat, result.photo.lng, file.name, null, '📷');
            }
        } catch (error) {
            console.error('Upload failed:', error);
        }
    }
}

// ── Event Listeners ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Mode tabs
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.addEventListener('click', () => switchMode(tab.dataset.mode));
    });

    // Chat input
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });

    // Send on Enter (Shift+Enter for newline)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(chatInput.value);
        }
    });

    // Send button click
    sendBtn.addEventListener('click', () => {
        sendMessage(chatInput.value);
    });

    // Quick action buttons
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', () => {
            sendMessage(btn.dataset.prompt);
        });
    });

    // Trip info card close
    document.getElementById('trip-info-close').addEventListener('click', () => {
        document.getElementById('trip-info-card').classList.remove('visible');
    });

    // Photo upload
    const uploadZone = document.getElementById('upload-zone');
    const photoInput = document.getElementById('photo-upload');

    uploadZone.addEventListener('click', () => photoInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = '#0040C1';
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.style.borderColor = '';
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = '';
        handlePhotoUpload(e.dataTransfer.files);
    });

    photoInput.addEventListener('change', () => {
        handlePhotoUpload(photoInput.files);
    });

    // Generate Summary
    const btnGenerateSummary = document.getElementById('btn-generate-summary');
    const summaryModal = document.getElementById('summary-modal');
    const summaryClose = document.getElementById('summary-close-btn');
    const summaryCarousel = document.getElementById('summary-carousel');
    const summaryLoading = document.getElementById('summary-loading');

    btnGenerateSummary.addEventListener('click', async () => {
        if (!state.currentTrip) {
            alert("Please plan a trip first before generating a summary!");
            return;
        }

        // Show loading state
        summaryModal.style.display = 'flex';
        summaryCarousel.innerHTML = '';
        summaryLoading.style.display = 'block';

        const result = await apiCall('generate_summary', {
            trip_id: state.currentTrip.trip.id,
            format: 'image_slideshow'
        });

        summaryLoading.style.display = 'none';

        if (result.status === 'success' && result.all_slides) {
            result.all_slides.forEach(slideUrl => {
                const img = document.createElement('img');
                img.src = slideUrl;
                img.style.maxHeight = '70vh';
                img.style.scrollSnapAlign = 'center';
                img.style.borderRadius = '8px';
                img.style.boxShadow = '0 10px 25px rgba(0,0,0,0.5)';
                summaryCarousel.appendChild(img);
            });
        } else {
            alert(result.message || "Failed to generate summary.");
            summaryModal.style.display = 'none';
        }
    });

    summaryClose.addEventListener('click', () => {
        summaryModal.style.display = 'none';
    });
});
