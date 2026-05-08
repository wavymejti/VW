/* =============================================================
   VW California AI Trip Planner — Application Logic
   Handles: Chat, Map, Travel Memory, API Communication
   ============================================================= */

// ── State ────────────────────────────────────────────────────
const state = {
    currentView: 'chat',         // 'chat' | 'map' | 'memory'
    map: null,                   // Google Maps instance
    mapInitialized: false,       // Lazy init flag
    markers: [],                 // Active map markers
    routePolylines: [],          // Active route lines
    currentTrip: null,           // Current trip data
    chatHistory: [],             // Chat messages
    isTyping: false,             // AI typing state
    campingMarkers: [],          // Camping location markers
    slotState: {                 // Current slot-filling state
        vibe: null,
        experience: null,
        pace: null,
        infrastructure: null,
        duration: null
    }
};

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
        return { status: 'error', message: 'Błąd połączenia. Spróbuj ponownie.' };
    }
}

// ── View Switching ───────────────────────────────────────────
function switchView(viewName) {
    if (viewName === state.currentView) return;
    
    // Update nav icons
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.id.startsWith('nav-')) {
            item.classList.toggle('active', item.dataset.view === viewName);
        }
    });

    // Update view containers
    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === `view-${viewName}`);
    });

    state.currentView = viewName;

    // Lazy init map
    if (viewName === 'map' && !state.mapInitialized && window.google) {
        initGoogleMap();
    }
}

// ── Map Initialization ───────────────────────────────────────
window.initMap = function() {
    // Map script loaded, but we don't render it until View 2 is opened
    console.log("Google Maps API loaded");
    if (state.currentView === 'map') {
        initGoogleMap();
    }
}

function initGoogleMap() {
    if (state.mapInitialized || !window.google) return;

    state.map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 47.5, lng: 13.0 },
        zoom: 6,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_CENTER },
        styles: [
            { featureType: 'water', stylers: [{ color: '#C5D7E8' }] },
            { featureType: 'landscape', stylers: [{ color: '#F0F3F7' }] },
            { featureType: 'road.highway', stylers: [{ color: '#E0E4EA' }] },
            { featureType: 'poi.park', stylers: [{ color: '#D4E6D0' }] },
            { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
        ],
    });
    
    state.mapInitialized = true;
    
    // Wire up map controls
    document.getElementById('btn-center-map').addEventListener('click', () => {
        if (state.currentTrip) fitMapToTrip();
        else { state.map.setCenter({ lat: 47.5, lng: 13.0 }); state.map.setZoom(6); }
    });
    
    document.getElementById('btn-toggle-campings').addEventListener('click', loadCampingsOnMap);
}

// ── Map Helpers ──────────────────────────────────────────────
function clearMapOverlays() {
    state.markers.forEach(m => m.setMap(null));
    state.markers = [];
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];
}

function clearCampingMarkers() {
    state.campingMarkers.forEach(m => m.setMap(null));
    state.campingMarkers = [];
}

function addMarker(lat, lng, title, icon, label) {
    if (!state.map) return null;
    const marker = new google.maps.Marker({
        position: { lat, lng },
        map: state.map,
        title: title,
        label: label || undefined,
        icon: icon ? { url: icon, scaledSize: new google.maps.Size(32, 32) } : undefined,
        animation: google.maps.Animation.DROP,
    });

    const infoWindow = new google.maps.InfoWindow({
        content: `<div style="font-family: Arial; padding: 4px;"><strong style="color: #001E50;">${title}</strong></div>`,
    });

    marker.addListener('click', () => infoWindow.open(state.map, marker));
    state.markers.push(marker);
    return marker;
}

function drawDailyRoutes(daily_schedules, color = '#001E50') {
    if (!state.map) return;
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];

    daily_schedules.forEach(day => {
        let path = [];
        if (day.route_polyline && google.maps.geometry) {
            path = google.maps.geometry.encoding.decodePath(day.route_polyline);
        } else {
            path = day.waypoints.map(wp => ({ lat: wp.lat, lng: wp.lng }));
        }

        const polyline = new google.maps.Polyline({
            path: path, geodesic: true, strokeColor: color,
            strokeOpacity: 0.85, strokeWeight: 4, map: state.map,
        });
        state.routePolylines.push(polyline);
    });
}

function fitMapToTrip() {
    if (!state.currentTrip || !state.map) return;
    const bounds = new google.maps.LatLngBounds();
    state.markers.forEach(m => bounds.extend(m.getPosition()));
    state.map.fitBounds(bounds, { padding: 80 });
}

// ── Display Trip on Map ──────────────────────────────────────
function displayTripOnMap(tripData) {
    if (!state.mapInitialized) initGoogleMap();
    clearMapOverlays();

    const { trip, daily_schedules } = tripData;
    state.currentTrip = tripData;

    let totalStops = 0;
    daily_schedules.forEach((day, idx) => {
        day.waypoints.forEach(wp => {
            let markerLabel = '';
            if (wp.type === 'start' && idx === 0) markerLabel = 'A';
            else if (wp.type === 'end' || (wp.type === 'camping' && idx === daily_schedules.length - 1)) markerLabel = 'B';
            else if (wp.type === 'camping') { markerLabel = '🏕️'; totalStops++; }
            
            addMarker(wp.lat, wp.lng, wp.label, null, markerLabel);
        });
    });

    if (daily_schedules && daily_schedules.length > 0) {
        drawDailyRoutes(daily_schedules);
    }

    document.getElementById('trip-title').textContent = trip.title;
    document.getElementById('stat-days').textContent = daily_schedules.length;
    document.getElementById('stat-km').textContent = Math.round(tripData.total_driving_km || 0);
    document.getElementById('stat-hours').textContent = `${(tripData.total_driving_hours || 0).toFixed(1)}h`;
    document.getElementById('stat-campings').textContent = totalStops;

    const dayCardsContainer = document.getElementById('day-cards');
    dayCardsContainer.innerHTML = '';

    daily_schedules.forEach(day => {
        const card = document.createElement('div');
        card.className = 'day-card';
        card.innerHTML = `
            <div class="day-number">Dzień ${day.day_number}</div>
            <div class="day-label">${day.date}</div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 8px;">
                <span>🚗 ${day.driving_hours}h</span>
                <span style="margin-left: 8px;">📏 ${Math.round(day.driving_km)}km</span>
            </div>
        `;
        card.addEventListener('click', () => {
            const bounds = new google.maps.LatLngBounds();
            day.waypoints.forEach(wp => bounds.extend({ lat: wp.lat, lng: wp.lng }));
            state.map.fitBounds(bounds, { padding: 100 });
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
        });
        dayCardsContainer.appendChild(card);
    });

    document.getElementById('trip-info-card').classList.add('visible');
    document.getElementById('btn-show-map').style.display = 'flex'; // Show floating button in chat
    
    fitMapToTrip();
}

async function loadCampingsOnMap() {
    if (!state.map) return;
    const center = state.map.getCenter();
    const result = await apiCall('search_campings', { lat: center.lat(), lng: center.lng(), radius_km: 80 });
    
    if (result.status === 'success' && result.results) {
        clearCampingMarkers();
        result.results.forEach(camp => {
            const marker = new google.maps.Marker({
                position: { lat: camp.lat, lng: camp.lng },
                map: state.map, title: camp.name,
                icon: { path: google.maps.SymbolPath.CIRCLE, fillColor: '#00875A', fillOpacity: 0.9, strokeColor: '#FFFFFF', strokeWeight: 2, scale: 8 },
            });
            const infoWindow = new google.maps.InfoWindow({ content: `<div style="padding:4px"><strong>${camp.name}</strong></div>` });
            marker.addListener('click', () => infoWindow.open(state.map, marker));
            state.campingMarkers.push(marker);
        });
    }
}

// ── Slot Progress Tracking ───────────────────────────────────
function updateSlotProgress(slotState) {
    if (!slotState) return;
    state.slotState = { ...state.slotState, ...slotState };
    
    // Update UI progress bar
    const slots = ['vibe', 'experience', 'pace', 'infrastructure', 'duration'];
    slots.forEach(slot => {
        const stepEl = document.getElementById(`slot-${slot}`);
        if (stepEl) {
            if (state.slotState[slot] !== null && state.slotState[slot] !== undefined) {
                stepEl.classList.add('filled');
            } else {
                stepEl.classList.remove('filled');
            }
        }
    });
}

// ── Chat Logic ───────────────────────────────────────────────
function addMessage(role, text) {
    const messagesEl = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome');

    if (welcome) welcome.style.display = 'none';

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    let formattedText = text;
    if (role === 'assistant') {
        formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
    }

    msgDiv.innerHTML = `
        <div class="message-bubble">${formattedText}</div>
        <div class="message-meta">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
    `;

    const typingEl = document.getElementById('typing-indicator');
    messagesEl.insertBefore(msgDiv, typingEl);
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

    addMessage('user', text);

    const input = document.getElementById('chat-input');
    input.value = '';
    input.style.height = 'auto';
    document.getElementById('char-counter').textContent = `0/1000`;
    document.getElementById('send-btn').disabled = true;

    showTyping(true);
    const result = await apiCall('chat', { message: text });
    showTyping(false);

    if (result.status === 'success' || result.status === 'partial') {
        addMessage('assistant', result.text);
        
        // Update slot progress
        if (result.slot_state) {
            updateSlotProgress(result.slot_state);
        }

        // Process tool calls (like plan_route, modify_route, add_attraction)
        let routePlanned = false;
        if (result.tool_calls) {
            result.tool_calls.forEach(tc => {
                // Full route plan or route modification → redraw entire map
                if (
                    (tc.function_name === 'plan_route' || tc.function_name === 'modify_route') &&
                    tc.result && tc.result.status === 'success'
                ) {
                    displayTripOnMap(tc.result);
                    routePlanned = true;
                }

                // Adding a single attraction → add one marker to map
                if (
                    tc.function_name === 'add_attraction' &&
                    tc.result && tc.result.status === 'success'
                ) {
                    const attr = tc.result.attraction;
                    if (attr && state.mapInitialized) {
                        addMarker(
                            attr.lat,
                            attr.lng,
                            attr.name,
                            null,
                            '⭐'
                        );
                    }
                }
            });
        }

        if (result.trip_data) {
            displayTripOnMap(result.trip_data);
            routePlanned = true;
        }

        // Auto-redirect to map if a route was just planned
        if (routePlanned) {
            setTimeout(() => {
                switchView('map');
            }, 1200);
        }
    } else {
        addMessage('assistant', result.message || 'Wystąpił błąd. Spróbuj ponownie.');
    }
}

// ── Travel Memory ────────────────────────────────────────────
async function handlePhotoUpload(files) {
    const grid = document.getElementById('photo-grid');
    const emptyState = document.getElementById('photo-empty');
    if (emptyState) emptyState.style.display = 'none';

    for (const file of files) {
        const card = document.createElement('div');
        card.className = 'photo-card';

        const reader = new FileReader();
        reader.onload = (e) => {
            card.innerHTML = `<img src="${e.target.result}" alt="${file.name}"><div class="photo-overlay">${file.name}</div>`;
        };
        reader.readAsDataURL(file);
        grid.appendChild(card);

        const formData = new FormData();
        formData.append('photo', file);
        if (state.currentTrip && state.currentTrip.trip) {
            formData.append('trip_id', state.currentTrip.trip.id);
        }

        try {
            const response = await fetch(`${API_BASE}/api/upload_photo`, { method: 'POST', body: formData });
            const result = await response.json();

            if (result.photo && result.photo.lat && result.photo.lng) {
                let markerLabel = '📷';
                if (result.linked && result.photo.day_number) {
                    markerLabel = `Dzień ${result.photo.day_number} 📷`;
                }
                addMarker(result.photo.lat, result.photo.lng, file.name, null, markerLabel);
            }
        } catch (error) { console.error('Upload failed:', error); }
    }
}

// ── Event Listeners ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    
    // View Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.view) switchView(item.dataset.view);
        });
    });

    document.getElementById('btn-show-map').addEventListener('click', () => switchView('map'));
    document.getElementById('btn-back-to-chat').addEventListener('click', () => switchView('chat'));

    // Chat input
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const charCounter = document.getElementById('char-counter');

    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        const len = chatInput.value.length;
        charCounter.textContent = `${len}/1000`;
        sendBtn.disabled = len === 0;
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(chatInput.value);
        }
    });

    sendBtn.addEventListener('click', () => sendMessage(chatInput.value));

    // Quick actions
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', () => sendMessage(btn.dataset.prompt));
    });

    document.getElementById('trip-info-close').addEventListener('click', () => {
        document.getElementById('trip-info-card').classList.remove('visible');
    });

    // Travel Memory
    const uploadZone = document.getElementById('upload-zone');
    const photoInput = document.getElementById('photo-upload');

    uploadZone.addEventListener('click', () => photoInput.click());
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.style.borderColor = '#0040C1'; });
    uploadZone.addEventListener('dragleave', () => { uploadZone.style.borderColor = ''; });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault(); uploadZone.style.borderColor = '';
        handlePhotoUpload(e.dataTransfer.files);
    });
    photoInput.addEventListener('change', () => handlePhotoUpload(photoInput.files));

    // Summary Generator
    const btnGenerateSummary = document.getElementById('btn-generate-summary');
    const summaryModal = document.getElementById('summary-modal');
    const summaryClose = document.getElementById('summary-close-btn');
    const summaryCarousel = document.getElementById('summary-carousel');
    const summaryLoading = document.getElementById('summary-loading');
    const summaryOptions = document.getElementById('summary-options');
    const summaryResultView = document.getElementById('summary-result-view');

    async function triggerSummaryGeneration(format) {
        summaryOptions.style.display = 'none';
        summaryResultView.style.display = 'flex';
        summaryCarousel.innerHTML = '';
        summaryLoading.style.display = 'block';

        const result = await apiCall('generate_summary', { trip_id: state.currentTrip.trip.id, format: format });
        summaryLoading.style.display = 'none';

        if (result.status === 'success') {
            if (format === 'video' && result.file_url) {
                const video = document.createElement('video');
                video.src = result.file_url; video.controls = true; video.autoplay = true;
                video.style.maxHeight = '70vh'; video.style.borderRadius = '8px';
                summaryCarousel.appendChild(video);
            } else if (result.all_slides) {
                result.all_slides.forEach(slideUrl => {
                    const img = document.createElement('img');
                    img.src = slideUrl; img.style.maxHeight = '70vh'; img.style.borderRadius = '8px';
                    summaryCarousel.appendChild(img);
                });
            }
        } else {
            alert(result.message || "Failed to generate summary.");
            summaryModal.style.display = 'none';
        }
    }

    btnGenerateSummary.addEventListener('click', () => {
        if (!state.currentTrip) { alert("Najpierw zaplanuj trasę!"); return; }
        summaryModal.style.display = 'flex';
        summaryOptions.style.display = 'block';
        summaryResultView.style.display = 'none';
    });

    document.getElementById('btn-export-slideshow').addEventListener('click', () => triggerSummaryGeneration('image_slideshow'));
    document.getElementById('btn-export-video').addEventListener('click', () => triggerSummaryGeneration('video'));
    summaryClose.addEventListener('click', () => { summaryModal.style.display = 'none'; });

    // Authentication simple implementation
    const authModal = document.getElementById('auth-modal');
    const btnLogin = document.getElementById('btn-login');
    const btnLogout = document.getElementById('btn-logout');

    async function checkAuth() {
        try {
            const response = await fetch(`${API_BASE}/api/me`);
            const result = await response.json();
            if (result.status === 'success' && result.user) {
                authModal.style.display = 'none';
                document.getElementById('user-profile').style.display = 'block';
                document.getElementById('user-display-name').textContent = result.user.display_name.charAt(0).toUpperCase();
            } else { authModal.style.display = 'flex'; }
        } catch (error) { authModal.style.display = 'flex'; }
    }

    btnLogin.addEventListener('click', async () => {
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        if (!email || !password) return;
        btnLogin.textContent = "Logowanie...";
        try {
            const response = await fetch(`${API_BASE}/api/login`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const result = await response.json();
            if (result.status === 'success') { checkAuth(); } 
            else { document.getElementById('auth-error').textContent = result.message || "Błąd logowania"; document.getElementById('auth-error').style.display = 'block'; }
        } catch(e) { console.error(e); }
        btnLogin.textContent = "Zaloguj się";
    });

    const btnRegister = document.getElementById('btn-register');
    if (btnRegister) {
        btnRegister.addEventListener('click', async () => {
            const email = document.getElementById('register-email').value;
            const password = document.getElementById('register-password').value;
            const name = document.getElementById('register-name').value;
            if (!email || !password || !name) return;
            btnRegister.textContent = "Tworzenie...";
            try {
                const response = await fetch(`${API_BASE}/api/register`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, display_name: name })
                });
                const result = await response.json();
                if (result.status === 'success') { checkAuth(); } 
                else { document.getElementById('auth-error').textContent = result.message || "Błąd rejestracji"; document.getElementById('auth-error').style.display = 'block'; }
            } catch(e) { console.error(e); }
            btnRegister.textContent = "Utwórz konto";
        });
    }

    document.getElementById('link-show-register').addEventListener('click', (e) => {
        e.preventDefault(); 
        document.getElementById('login-view').style.display = 'none'; 
        document.getElementById('register-view').style.display = 'block';
        document.getElementById('auth-error').style.display = 'none';
    });
    
    document.getElementById('link-show-login').addEventListener('click', (e) => {
        e.preventDefault(); 
        document.getElementById('register-view').style.display = 'none'; 
        document.getElementById('login-view').style.display = 'block';
        document.getElementById('auth-error').style.display = 'none';
    });

    checkAuth();
});
