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
    attractionMarkers: [],       // POI attraction markers (separate layer)
    attractionsVisible: true,    // Whether the attractions layer is shown
    top5Attractions: [],         // Current Top 5 POIs on route
    allSortedAttractions: [],    // Full sorted list of all POIs on route
    rawAttractionsList: [],      // Raw unsorted list of POIs
    topSortMode: 'rating',       // Sort mode: 'rating' (highest rated) or 'day' (chronological)
    top5Offset: 0,               // Current pagination offset for Top 5 modal (0, 5, 10, ...)
    activeInfoWindow: null,      // Currently open InfoWindow (single instance)
    slotState: {                 // Current slot-filling state
        vibe: null,
        experience: null,
        pace: null,
        infrastructure: null,
        duration: null
    }
};
window.state = state;

function openSingleInfoWindow(infoWindow, marker) {
    if (state.activeInfoWindow) {
        state.activeInfoWindow.close();
    }
    state.activeInfoWindow = infoWindow;
    infoWindow.open(state.map, marker);
}

const API_BASE = '';

async function apiCall(endpoint, data = {}) {
    try {
        const payload = {
            lang: window.vwI18n ? window.vwI18n.getLanguage() : 'pl',
            ...data
        };
        const response = await fetch(`${API_BASE}/api/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const text = await response.text();
            try {
                return JSON.parse(text);
            } catch (e) {
                return { status: 'error', message: `Błąd serwera HTTP ${response.status}. Upewnij się, że serwer został zrestartowany.` };
            }
        }
        return await response.json();
    } catch (error) {
        console.error(`API error (${endpoint}):`, error);
        return { status: 'error', message: window.t ? window.t('connection_error') : 'Błąd połączenia z serwerem.' };
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

    // Lazy init map & immediate auto-fit bounds
    if (viewName === 'map') {
        if (!state.mapInitialized && window.google) {
            initGoogleMap();
        }
        if (state.map && window.google) {
            setTimeout(() => {
                google.maps.event.trigger(state.map, 'resize');
                if (state.currentTrip) {
                    fitMapToTrip();
                } else if (state.markers.length > 0) {
                    const bounds = new google.maps.LatLngBounds();
                    state.markers.forEach(m => bounds.extend(m.getPosition()));
                    state.map.fitBounds(bounds, { padding: 80 });
                }
            }, 100);
        }
        setTimeout(() => {
            if (window.MAP_TUTORIAL_STEPS && window.startTutorialSuite) {
                window.startTutorialSuite(window.MAP_TUTORIAL_STEPS, 'vw_tut_map_seen');
            }
        }, 500);
    } else if (viewName === 'memory') {
        setTimeout(() => {
            if (window.MEMORY_TUTORIAL_STEPS && window.startTutorialSuite) {
                window.startTutorialSuite(window.MEMORY_TUTORIAL_STEPS, 'vw_tut_memory_seen');
            }
        }, 500);
    }
}
window.switchView = switchView;
window.apiCall = apiCall;
window.displayTripOnMap = displayTripOnMap;

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

    // Wire up the attractions toggle button & Top 5 button
    const btnAttractions = document.getElementById('btn-toggle-attractions');
    if (btnAttractions) {
        btnAttractions.addEventListener('click', toggleAttractionsOnMap);
    }

    const btnTopAttrs = document.getElementById('btn-top-attractions');
    if (btnTopAttrs) {
        btnTopAttrs.addEventListener('click', openTop5AttractionsModal);
    }

    const closeTopBtn = document.getElementById('top-attractions-close');
    if (closeTopBtn) {
        closeTopBtn.addEventListener('click', closeTop5AttractionsModal);
    }

    const btnPrev = document.getElementById('btn-top-prev');
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            state.top5Offset = Math.max(0, (state.top5Offset || 0) - 5);
            renderTopAttractionsModalPage();
        });
    }

    const btnNext = document.getElementById('btn-top-next');
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            const total = (state.allSortedAttractions || []).length;
            if ((state.top5Offset || 0) + 5 < total) {
                state.top5Offset = (state.top5Offset || 0) + 5;
                renderTopAttractionsModalPage();
            }
        });
    }

    const sortSelect = document.getElementById('top-attractions-sort');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            state.topSortMode = e.target.value;
            state.top5Offset = 0;
            state.allSortedAttractions = sortAttractionsList(state.rawAttractionsList || [], state.topSortMode);
            renderTopAttractionsModalPage();
        });
    }
}

// ── Map Helpers ──────────────────────────────────────────────
function clearMapOverlays() {
    state.markers.forEach(m => m.setMap(null));
    state.markers = [];
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];
    // Also clear attraction markers when the full route is redrawn
    clearAttractionMarkers();
}

function clearCampingMarkers() {
    state.campingMarkers.forEach(m => m.setMap(null));
    state.campingMarkers = [];
}

function clearAttractionMarkers() {
    state.attractionMarkers.forEach(m => m.setMap(null));
    state.attractionMarkers = [];
    const badge = document.getElementById('attractions-count-badge');
    if (badge) badge.style.display = 'none';
    const btn = document.getElementById('btn-toggle-attractions');
    if (btn) btn.classList.remove('active');
}

function addMarker(lat, lng, title, icon, label, photoUrl = null, photoId = null, isDraggable = true, placeId = null) {
    if (!state.map) return null;
    const marker = new google.maps.Marker({
        position: { lat, lng },
        map: state.map,
        title: title,
        label: label || undefined,
        draggable: isDraggable,
        icon: icon ? { url: icon, scaledSize: new google.maps.Size(32, 32) } : undefined,
        animation: google.maps.Animation.DROP,
    });

    let displayPhotoUrl = photoUrl;
    if (displayPhotoUrl && displayPhotoUrl.includes('/.tmp/uploads/')) {
        const fname = displayPhotoUrl.split('/').pop();
        displayPhotoUrl = `/photos/file/${fname}`;
    }

    function buildInfoWindowHtml(imgUrl, ratingVal, addressVal) {
        let imgHtml = '';
        if (imgUrl) {
            imgHtml = `<img src="${imgUrl}" alt="${title}" style="width: 210px; height: 130px; object-fit: cover; border-radius: 8px; margin-bottom: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);" onerror="this.style.display='none';">`;
        }
        let metaHtml = '';
        if (ratingVal) {
            metaHtml += `<div style="font-size: 0.78rem; color: #D69E2E; font-weight: bold; margin: 2px 0;">⭐ ${ratingVal}</div>`;
        }
        if (addressVal) {
            metaHtml += `<div style="font-size: 0.75rem; color: #666; margin-bottom: 4px;">📍 ${addressVal}</div>`;
        }
        return `
            <div style="font-family: Arial, sans-serif; padding: 6px; text-align: center; max-width: 220px;">
                ${imgHtml}
                <strong style="color: #001E50; font-size: 0.88rem; display: block; word-break: break-word;">${title}</strong>
                ${metaHtml}
            </div>
        `;
    }

    const infoWindow = new google.maps.InfoWindow({
        content: buildInfoWindowHtml(displayPhotoUrl, null, null),
    });

    marker.addListener('click', async () => {
        openSingleInfoWindow(infoWindow, marker);
        if (placeId && !displayPhotoUrl) {
            try {
                const res = await fetch(`${API_BASE}/api/place_details/${placeId}`);
                const data = await res.json();
                if (data.status === 'success' && data.details) {
                    const details = data.details;
                    const fetchedPhoto = (details.photo_urls && details.photo_urls.length > 0) ? details.photo_urls[0] : null;
                    displayPhotoUrl = fetchedPhoto;
                    infoWindow.setContent(buildInfoWindowHtml(fetchedPhoto, details.rating, details.formatted_phone_number || details.name));
                }
            } catch (err) {
                console.error('Failed to fetch place details for popup:', err);
            }
        }
    });

    if (isDraggable) {
        marker.addListener('dragend', async (e) => {
            const newLat = e.latLng.lat();
            const newLng = e.latLng.lng();
            console.log(`Marker '${title}' dragged to:`, newLat, newLng);

            if (photoId) {
                try {
                    await fetch(`${API_BASE}/api/pin_photo`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ photo_id: photoId, lat: newLat, lng: newLng })
                    });
                } catch (err) { console.error('Failed to update photo pin location:', err); }
            }
        });
    }

    state.markers.push(marker);
    return marker;
}

function drawDailyRoutes(daily_schedules, color = '#001E50', returnColor = '#E65100') {
    if (!state.map) return;
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];

    if (!daily_schedules || daily_schedules.length === 0) return;

    const totalDays = daily_schedules.length;

    // Detect round trips
    const tripObj = state.currentTrip?.trip;
    const firstWp = daily_schedules[0]?.waypoints?.[0];
    const lastDayWps = daily_schedules[totalDays - 1]?.waypoints;
    const lastWp = lastDayWps?.[lastDayWps.length - 1];

    const isRoundTrip = !!(
        (tripObj?.origin && tripObj?.destination && (
            (tripObj.origin.label && tripObj.destination.label && tripObj.origin.label === tripObj.destination.label) ||
            (tripObj.origin.lat === tripObj.destination.lat && tripObj.origin.lng === tripObj.destination.lng)
        )) ||
        (firstWp && lastWp && Math.abs(firstWp.lat - lastWp.lat) < 0.03 && Math.abs(firstWp.lng - lastWp.lng) < 0.03)
    );

    daily_schedules.forEach((day, idx) => {
        let path = [];
        if (day.route_polyline && google.maps.geometry) {
            path = google.maps.geometry.encoding.decodePath(day.route_polyline);
        } else if (day.waypoints && day.waypoints.length > 0) {
            path = day.waypoints.map(wp => ({ lat: wp.lat, lng: wp.lng }));
        }

        if (path.length === 0) return;

        let isReturn = false;
        if (typeof day.is_return === 'boolean') {
            isReturn = day.is_return;
        } else if (typeof day.is_return_leg === 'boolean') {
            isReturn = day.is_return_leg;
        } else if (isRoundTrip && totalDays > 1) {
            isReturn = (idx + 1) > Math.ceil(totalDays / 2);
        }

        const strokeColor = isReturn ? returnColor : color;

        const polyline = new google.maps.Polyline({
            path: path, geodesic: true, strokeColor: strokeColor,
            strokeOpacity: 0.85, strokeWeight: 5, map: state.map,
        });

        polyline.isReturn = isReturn;
        polyline.dayNumber = day.day_number || (idx + 1);

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
            
            let photoUrl = wp.photo_url || (wp.photos && wp.photos.length ? wp.photos[0] : null);
            let placeId = wp.place_id || null;

            if (wp.type === 'camping' && day.overnight_camping) {
                if (!photoUrl && day.overnight_camping.photos && day.overnight_camping.photos.length > 0) {
                    photoUrl = day.overnight_camping.photos[0];
                }
                if (!placeId && day.overnight_camping.place_id) {
                    placeId = day.overnight_camping.place_id;
                }
            }

            addMarker(wp.lat, wp.lng, wp.label, null, markerLabel, photoUrl, null, true, placeId);
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

    const isRoundTripOverall = !!(
        (trip?.origin && trip?.destination && (
            (trip.origin.label && trip.destination.label && trip.origin.label === trip.destination.label) ||
            (trip.origin.lat === trip.destination.lat && trip.origin.lng === trip.destination.lng)
        ))
    );

    daily_schedules.forEach((day, idx) => {
        const card = document.createElement('div');
        card.className = 'day-card';
        const btnText = window.t ? window.t('camping_change_btn') : '🏕️ Zobacz / zmień kemping';
        const changeBtnHtml = `<button class="btn-change-camping-day" style="margin-top: 8px; padding: 4px 8px; font-size: 0.75rem; border-radius: 6px; background: #001E50; color: #fff; border: none; cursor: pointer; width: 100%;">${btnText}</button>`;
        const campingName = day.overnight_camping ? (day.overnight_camping.name || day.overnight_camping.label) : null;

        const isReturn = (typeof day.is_return === 'boolean') ? day.is_return :
                         (typeof day.is_return_leg === 'boolean') ? day.is_return_leg :
                         (isRoundTripOverall && daily_schedules.length > 1 && (idx + 1) > Math.ceil(daily_schedules.length / 2));
        const returnBadgeText = window.t ? window.t('day_return_badge') : 'Powrót';
        const returnBadgeHtml = isReturn ? `<div class="day-return-badge">🔄 ${returnBadgeText}</div>` : '';

        const attractionWaypoints = (day.waypoints || []).filter(wp => wp.type === 'attraction');
        let attractionsHtml = '';
        if (attractionWaypoints.length > 0) {
            const attrBadges = attractionWaypoints.map(wp =>
                `<div style="font-size:0.72rem; color:#D69E2E; font-weight:600; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${wp.label}">⭐ ${wp.label}</div>`
            ).join('');
            attractionsHtml = `<div class="day-card-attractions" style="margin-top:4px; border-top:1px dashed #E2E8F0; padding-top:4px;">${attrBadges}</div>`;
        }

        card.innerHTML = `
            <div class="day-number">Dzień ${day.day_number}</div>
            <div class="day-label">${day.date || ''}</div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 6px;">
                <span>🚗 ${day.driving_hours || 0}h</span>
                <span style="margin-left: 8px;">📏 ${Math.round(day.driving_km || 0)}km</span>
            </div>
            ${attractionsHtml}
            ${campingName ? `<div style="font-size:0.75rem; color:#00875A; font-weight:bold; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${campingName}">🏕️ ${campingName}</div>` : ''}
            ${returnBadgeHtml}
            ${changeBtnHtml}
        `;

        card.addEventListener('click', (e) => {
            if (state.map && day.waypoints && day.waypoints.length > 0) {
                const bounds = new google.maps.LatLngBounds();
                day.waypoints.forEach(wp => bounds.extend({ lat: wp.lat, lng: wp.lng }));
                state.map.fitBounds(bounds, { padding: 100 });
            }
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');

            openCampingSelectionModal(state.currentTrip || tripData, day.day_number);
        });

        dayCardsContainer.appendChild(card);
    });

    const tripInfoCard = document.getElementById('trip-info-card');
    if (tripInfoCard) {
        tripInfoCard.classList.remove('collapsed');
        tripInfoCard.classList.add('visible');
    }

    const btnToggleTripInfo = document.getElementById('btn-toggle-trip-info');
    if (btnToggleTripInfo) {
        btnToggleTripInfo.style.display = 'flex';
    }

    const btnShowMap = document.getElementById('btn-show-map');
    if (btnShowMap) {
        btnShowMap.style.display = 'flex';
    }

    fitMapToTrip();

    // Auto-load attractions after route is displayed (with slight delay
    // so the map animation completes first)
    const tripId = trip && trip.id;
    if (tripId) {
        setTimeout(() => loadAttractionsOnMap(tripId), 2500);
    }
}

async function toggleCampingsOnMap() {
    const btn = document.getElementById('btn-toggle-campings');
    if (state.campingMarkers && state.campingMarkers.length > 0) {
        clearCampingMarkers();
        if (btn) btn.classList.remove('active');
    } else {
        await loadCampingsOnMap();
        if (btn && state.campingMarkers && state.campingMarkers.length > 0) btn.classList.add('active');
    }
}
window.toggleCampingsOnMap = toggleCampingsOnMap;

async function loadCampingsOnMap() {
    let lat = 47.5, lng = 13.0;
    if (state.map && typeof state.map.getCenter === 'function') {
        const center = state.map.getCenter();
        if (center) {
            lat = typeof center.lat === 'function' ? center.lat() : (center.lat || 47.5);
            lng = typeof center.lng === 'function' ? center.lng() : (center.lng || 13.0);
        }
    }
    const result = await apiCall('search_campings', { lat: lat, lng: lng, radius_km: 80 });
    
    if (result.status === 'success' && result.results) {
        clearCampingMarkers();
        result.results.forEach(camp => {
            let marker;
            if (window.google && window.google.maps && window.google.maps.Marker) {
                marker = new google.maps.Marker({
                    position: { lat: camp.lat, lng: camp.lng },
                    map: state.map || null,
                    title: camp.name,
                    icon: (window.google && window.google.maps && window.google.maps.SymbolPath && window.google.maps.SymbolPath.CIRCLE) ? { path: window.google.maps.SymbolPath.CIRCLE, fillColor: '#00875A', fillOpacity: 0.9, strokeColor: '#FFFFFF', strokeWeight: 2, scale: 8 } : undefined,
                });
            } else {
                marker = { position: { lat: camp.lat, lng: camp.lng }, title: camp.name, setMap: () => {} };
            }

            // Build badges for amenities and CEE power
            let badgesHtml = '<div class="camping-badges" style="margin-top:6px; display:flex; flex-wrap:wrap; gap:4px;">';
            if (camp.shore_power_hookup || camp.has_power || camp.hookup_type === '230V CEE' || (camp.amenities && camp.amenities.includes('power'))) {
                badgesHtml += '<span class="camping-badge cee-badge" style="background:#E3F2FD; color:#1565C0; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;">🔌 Prąd CEE</span>';
            }
            if (camp.has_showers || (camp.amenities && camp.amenities.includes('showers'))) {
                badgesHtml += '<span class="camping-badge shower-badge" style="background:#E8F5E9; color:#2E7D32; padding:2px 6px; border-radius:4px; font-size:11px;">🚿 Prysznic</span>';
            }
            if (camp.has_water || (camp.amenities && camp.amenities.includes('water'))) {
                badgesHtml += '<span class="camping-badge water-badge" style="background:#E0F7FA; color:#006064; padding:2px 6px; border-radius:4px; font-size:11px;">🚰 Woda</span>';
            }
            if (camp.has_wifi || (camp.amenities && camp.amenities.includes('wifi'))) {
                badgesHtml += '<span class="camping-badge wifi-badge" style="background:#F3E5F5; color:#4A148C; padding:2px 6px; border-radius:4px; font-size:11px;">📶 WiFi</span>';
            }
            if (camp.has_toilets) {
                badgesHtml += '<span class="camping-badge toilet-badge" style="background:#FFF3E0; color:#E65100; padding:2px 6px; border-radius:4px; font-size:11px;">🚽 Toaleta</span>';
            }
            badgesHtml += '</div>';

            const infoWindowContent = `
                <div class="camping-infowindow" style="padding:6px; max-width:220px;">
                    <h4 style="margin:0 0 4px 0; color:#001E50; font-size:14px;">${camp.name}</h4>
                    ${camp.rating ? `<div style="font-size:12px; color:#555;">⭐ ${camp.rating}</div>` : ''}
                    ${camp.cost_per_night_eur ? `<div style="font-size:12px; color:#333; font-weight:bold; margin-top:2px;">€${camp.cost_per_night_eur}/noc</div>` : ''}
                    ${badgesHtml}
                </div>
            `;

            if (window.google && window.google.maps && window.google.maps.InfoWindow) {
                const infoWindow = new google.maps.InfoWindow({ content: infoWindowContent });
                if (marker.addListener) marker.addListener('click', () => openSingleInfoWindow(infoWindow, marker));
            }
            state.campingMarkers.push(marker);
        });
    }
}
window.loadCampingsOnMap = loadCampingsOnMap;

// ── Attractions Along Route ───────────────────────────────────

function sortAttractionsList(attrsList, mode = 'rating') {
    if (!attrsList) return [];
    const list = [...attrsList];
    if (mode === 'day') {
        list.sort((a, b) => {
            const dA = a.day_number || 1;
            const dB = b.day_number || 1;
            if (dA !== dB) return dA - dB;
            const rA = parseFloat(a.rating) || 0;
            const rB = parseFloat(b.rating) || 0;
            return rB - rA;
        });
    } else {
        list.sort((a, b) => {
            const rA = parseFloat(a.rating) || 0;
            const rB = parseFloat(b.rating) || 0;
            if (rB !== rA) return rB - rA;
            return (b.user_ratings_total || b.review_count || 0) - (a.user_ratings_total || a.review_count || 0);
        });
    }
    return list;
}
window.sortAttractionsList = sortAttractionsList;

/**
 * Toggle the attractions layer on/off.
 * If markers are already rendered, hide/show them.
 * If not yet loaded, trigger loadAttractionsOnMap.
 */
async function toggleAttractionsOnMap() {
    const btn = document.getElementById('btn-toggle-attractions');

    if (state.attractionMarkers && state.attractionMarkers.length > 0) {
        // Toggle visibility without removing markers from memory
        state.attractionsVisible = !state.attractionsVisible;
        state.attractionMarkers.forEach(m => m.setMap(state.attractionsVisible ? state.map : null));
        if (btn) btn.classList.toggle('active', state.attractionsVisible);

        // Open Top 5 modal when turning layer ON
        if (state.attractionsVisible && state.top5Attractions && state.top5Attractions.length > 0) {
            openTop5AttractionsModal();
        }
    } else {
        // No markers loaded yet — trigger a fresh load for the current trip
        const tripId = state.currentTrip && state.currentTrip.trip && state.currentTrip.trip.id;
        if (tripId) {
            await loadAttractionsOnMap(tripId);
            if (btn && state.attractionMarkers.length > 0) btn.classList.add('active');

            // Open Top 5 modal automatically!
            if (state.top5Attractions && state.top5Attractions.length > 0) {
                openTop5AttractionsModal();
            }
        }
    }
}
window.toggleAttractionsOnMap = toggleAttractionsOnMap;

/**
 * Load POI attractions for a trip from /api/attractions/<tripId>
 * and render colour-coded markers on the map.
 *
 * @param {string} tripId - UUID of the active trip.
 * @param {string} [preferences] - Optional filter string (e.g. 'zamki,muzea').
 */
async function loadAttractionsOnMap(tripId, preferences = null) {
    if (!state.mapInitialized || !state.map) return;
    if (!tripId) return;

    // Clear any previously loaded attraction markers
    clearAttractionMarkers();

    const btn = document.getElementById('btn-toggle-attractions');
    const btnLabel = btn ? btn.querySelector('.btn-label') : null;
    const originalLabel = btnLabel ? btnLabel.textContent : 'Atrakcje';

    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.75';
        // Show loading indicator in button label
        if (btnLabel) btnLabel.textContent = '⏳ Ładuję…';
    }

    try {
        // Use 80 km sample interval (matches server default) to keep API calls low.
        let url = `${API_BASE}/api/attractions/${tripId}?limit_per_day=5&sample_every_km=80`;
        if (preferences) url += `&preferences=${encodeURIComponent(preferences)}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.status !== 'success' || !data.attractions_by_day) {
            console.warn('[Attractions] No attractions returned:', data.message);
            return;
        }

        let totalCount = 0;
        const allAttrs = [];

        // Iterate over each day's attractions
        Object.entries(data.attractions_by_day).forEach(([dayNum, attractions], dayIdx) => {
            attractions.forEach((attr, i) => {
                const attrObj = { ...attr, day_number: parseInt(dayNum) };
                allAttrs.push(attrObj);
                const marker = _createAttractionMarker(attrObj, dayIdx, i);
                if (marker) {
                    marker._attrData = attrObj;
                    state.attractionMarkers.push(marker);
                    totalCount++;
                }
            });
        });

        state.rawAttractionsList = allAttrs;
        state.allSortedAttractions = sortAttractionsList(allAttrs, state.topSortMode || 'rating');
        state.top5Offset = 0;
        state.top5Attractions = state.allSortedAttractions.slice(0, 5);
        state.attractionsVisible = true;

        // Update badge
        const badge = document.getElementById('attractions-count-badge');
        if (badge) {
            badge.textContent = totalCount;
            badge.style.display = totalCount > 0 ? 'inline-flex' : 'none';
        }

        // Show/hide Top 5 button
        const btnTop = document.getElementById('btn-top-attractions');
        if (btnTop) {
            btnTop.style.display = allAttrs.length > 0 ? 'inline-flex' : 'none';
        }

        if (btn) btn.classList.toggle('active', totalCount > 0);

        console.log(`[Attractions] Loaded ${totalCount} attractions. Full list sorted:`, allAttrs.length);

    } catch (err) {
        console.error('[Attractions] Failed to load:', err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = '';
            // Restore original label
            if (btnLabel) btnLabel.textContent = originalLabel;
        }
    }
}
window.loadAttractionsOnMap = loadAttractionsOnMap;

function openTop5AttractionsModal() {
    const modal = document.getElementById('top-attractions-modal');
    if (!modal) return;
    renderTopAttractionsModalPage();
    modal.style.display = 'flex';
}
window.openTop5AttractionsModal = openTop5AttractionsModal;

function renderTopAttractionsModalPage() {
    const grid = document.getElementById('top-attractions-grid');
    const titleEl = document.getElementById('top-attractions-title');
    const indicatorEl = document.getElementById('top-page-indicator');
    const btnPrev = document.getElementById('btn-top-prev');
    const btnNext = document.getElementById('btn-top-next');

    if (!grid) return;

    const allAttrs = state.allSortedAttractions || [];
    if (allAttrs.length === 0) return;

    const offset = state.top5Offset || 0;
    const pageItems = allAttrs.slice(offset, offset + 5);

    grid.innerHTML = '';

    const medals = ['🥇 #1', '🥈 #2', '🥉 #3', '⭐ #4', '⭐ #5'];

    pageItems.forEach((attr, idx) => {
        const globalRank = offset + idx + 1;
        const card = document.createElement('div');
        card.className = 'top-attraction-item-card';

        const photoHtml = attr.photo_url
            ? `<div class="top-attraction-img-wrap"><img src="${attr.photo_url}" alt="${attr.name}" onerror="this.parentElement.style.display='none';"></div>`
            : '';

        const ratingHtml = attr.rating ? `<span style="color:#D69E2E; font-weight:700;">⭐ ${attr.rating}</span>` : '';
        const categoryBadge = `<span style="background:${attr.color || '#F9A825'}20; color:${attr.color || '#F9A825'}; border:1px solid ${attr.color || '#F9A825'}60; border-radius:12px; padding:2px 8px; font-size:11px; font-weight:700;">${attr.emoji || '⭐'} ${attr.category_label || 'Atrakcja'}</span>`;

        const medalBadge = globalRank <= 3 ? (medals[globalRank - 1] || `#${globalRank}`) : `#${globalRank}`;

        const isAdded = isAttractionInRoute(attr, attr.day_number);
        const addBtnText = isAdded ? (window.t ? window.t('added_to_route_btn') : '✓ Dodano do drogi') : (window.t ? window.t('add_to_route_btn') : '➕ Dodaj do drogi');
        const attrKey = attr.place_id || (attr.name + '_' + attr.lat + '_' + attr.lng);
        window._attractionsCache = window._attractionsCache || {};
        window._attractionsCache[attrKey] = attr;

        card.innerHTML = `
            <div class="top-rank-badge">${medalBadge}</div>
            ${photoHtml}
            <div class="top-attraction-info">
                <div style="margin-bottom:6px;">${categoryBadge}</div>
                <h4>${attr.name}</h4>
                <div class="top-attraction-meta">
                    ${ratingHtml}
                    ${attr.address ? `<div style="font-size:0.82rem; margin-top:2px;">📍 ${attr.address}</div>` : ''}
                    <div style="font-weight:700; color:#001E50; margin-top:4px;">🗓️ Dzień ${attr.day_number || 1} trasy</div>
                </div>
            </div>
            <div style="margin-top:10px; display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn-show-attraction-map" onclick="focusAttractionOnMap(${attr.lat}, ${attr.lng}, '${(attr.name || '').replace(/'/g, "\\'")}')">
                    🎯 Pokaż na mapie
                </button>
                <button class="btn-add-attraction-route ${isAdded ? 'added' : ''}" data-attr-key="${attrKey}" ${isAdded ? 'disabled' : ''} onclick="window.addAttractionToRouteFromCache('${attrKey}')">
                    ${addBtnText}
                </button>
            </div>
        `;
        grid.appendChild(card);
    });

    if (titleEl) {
        titleEl.textContent = offset === 0
            ? '🌟 Top 5 Must-See Atrakcji na Trasie'
            : `🌟 Wyjątkowe Atrakcje #${offset + 1}–#${offset + pageItems.length} na Trasie`;
    }

    if (indicatorEl) {
        indicatorEl.textContent = `Atrakcje #${offset + 1}–#${offset + pageItems.length} z ${allAttrs.length}`;
    }

    if (btnPrev) btnPrev.disabled = (offset === 0);
    if (btnNext) btnNext.disabled = (offset + 5 >= allAttrs.length);
}
window.renderTopAttractionsModalPage = renderTopAttractionsModalPage;

function closeTop5AttractionsModal() {
    const modal = document.getElementById('top-attractions-modal');
    if (modal) modal.style.display = 'none';
}
window.closeTop5AttractionsModal = closeTop5AttractionsModal;

function focusAttractionOnMap(lat, lng, name) {
    closeTop5AttractionsModal();

    if (window.switchView) window.switchView('map');

    if (!state.map) return;

    state.map.panTo({ lat, lng });
    state.map.setZoom(14);

    if (!state.attractionsVisible) {
        state.attractionsVisible = true;
        state.attractionMarkers.forEach(m => m.setMap(state.map));
        const btn = document.getElementById('btn-toggle-attractions');
        if (btn) btn.classList.add('active');
    }

    const matchMarker = state.attractionMarkers.find(m => {
        const pos = m.getPosition();
        return pos && Math.abs(pos.lat() - lat) < 0.001 && Math.abs(pos.lng() - lng) < 0.001;
    });

    if (matchMarker) {
        google.maps.event.trigger(matchMarker, 'click');
    }
}
window.focusAttractionOnMap = focusAttractionOnMap;

function isAttractionInRoute(attr, dayNumber) {
    if (!state.currentTrip || !state.currentTrip.daily_schedules) return false;
    const targetDay = dayNumber || attr.day_number || 1;
    const daySched = state.currentTrip.daily_schedules.find(d => d.day_number === targetDay);
    if (!daySched || !daySched.waypoints) return false;

    return daySched.waypoints.some(wp => {
        if (wp.type !== 'attraction') return false;
        if (attr.place_id && wp.place_id && wp.place_id === attr.place_id) return true;
        if (wp.label && attr.name && wp.label.toLowerCase() === attr.name.toLowerCase()) return true;
        if (wp.lat && wp.lng && attr.lat && attr.lng && Math.abs(wp.lat - attr.lat) < 0.0001 && Math.abs(wp.lng - attr.lng) < 0.0001) return true;
        return false;
    });
}
window.isAttractionInRoute = isAttractionInRoute;

window._attractionsCache = window._attractionsCache || {};
function addAttractionToRouteFromCache(attrKey) {
    const attr = window._attractionsCache[attrKey];
    if (attr) {
        addAttractionToRoute(attr);
    }
}
window.addAttractionToRouteFromCache = addAttractionToRouteFromCache;

async function addAttractionToRoute(attr) {
    if (!state.currentTrip || !state.currentTrip.trip) {
        alert(window.t ? window.t('error_no_active_trip') : 'Brak aktywnej trasy.');
        return;
    }

    const tripId = state.currentTrip.trip.id;
    const dayNumber = attr.day_number || 1;
    const attrKey = attr.place_id || (attr.name + '_' + attr.lat + '_' + attr.lng);

    const btns = document.querySelectorAll(`button[data-attr-key="${attrKey}"]`);
    btns.forEach(b => {
        b.disabled = true;
        b.textContent = window.t ? window.t('adding_to_route_btn') : 'Dodawanie...';
    });

    try {
        const res = await apiCall('add_attraction', {
            trip_id: tripId,
            day_number: dayNumber,
            attraction: attr
        });

        if (res.status === 'success' && res.trip_data) {
            state.currentTrip = res.trip_data;
            displayTripOnMap(res.trip_data);

            btns.forEach(b => {
                b.disabled = true;
                b.className = 'btn-add-attraction-route added';
                b.style.background = '#00875A';
                b.style.color = '#fff';
                b.textContent = window.t ? window.t('added_to_route_btn') : '✓ Dodano do drogi';
            });

            if (typeof showVoiceToast === 'function') {
                const msg = window.t ? window.t('attraction_added_toast', { name: attr.name, day: dayNumber }) : `Dodano atrakcję ${attr.name} do Dnia ${dayNumber}!`;
                showVoiceToast(msg);
            }
        } else {
            btns.forEach(b => {
                b.disabled = false;
                b.textContent = window.t ? window.t('add_to_route_btn') : '➕ Dodaj do drogi';
            });
            alert(res.message || 'Nie udało się dodać atrakcji do trasy.');
        }
    } catch (err) {
        console.error('Failed to add attraction to route:', err);
        btns.forEach(b => {
            b.disabled = false;
            b.textContent = window.t ? window.t('add_to_route_btn') : '➕ Dodaj do drogi';
        });
    }
}
window.addAttractionToRoute = addAttractionToRoute;

/**
 * Create a single Google Maps Marker for an attraction,
 * with a coloured custom icon and an info window showing
 * the photo, rating, category label, address, and a link
 * to Google Maps.
 *
 * @param {object} attr - Attraction data from the API.
 * @param {number} dayIdx - Zero-based day index (for staggered animation).
 * @param {number} seqIdx - Position within the day (for staggered animation).
 * @returns {google.maps.Marker|null}
 */
function _createAttractionMarker(attr, dayIdx, seqIdx) {
    if (!state.map || !attr.lat || !attr.lng) return null;
    if (!window.google || !window.google.maps) return null;

    const emoji   = attr.emoji   || '⭐';
    const color   = attr.color   || '#F9A825';
    const label   = attr.category_label || 'Atrakcja';
    const name    = attr.name    || '';
    const rating  = attr.rating;
    const address = attr.address || '';
    const photoUrl = attr.photo_url;
    const mapsUrl  = attr.google_maps_url || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name)}`;
    const attrKey = attr.place_id || (name + '_' + attr.lat + '_' + attr.lng);
    window._attractionsCache = window._attractionsCache || {};
    window._attractionsCache[attrKey] = attr;

    // Custom SVG pin with category colour and emoji label
    const svgPin = `
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="46" viewBox="0 0 36 46">
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="rgba(0,0,0,0.3)"/>
            </filter>
            <path d="M18 0C8.06 0 0 8.06 0 18c0 13.5 18 28 18 28S36 31.5 36 18C36 8.06 27.94 0 18 0z"
                  fill="${color}" filter="url(#shadow)"/>
            <circle cx="18" cy="17" r="11" fill="white" opacity="0.92"/>
            <text x="18" y="22" text-anchor="middle" font-size="13">${emoji}</text>
        </svg>`;

    const iconDataUrl = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svgPin);

    const marker = new google.maps.Marker({
        position: { lat: attr.lat, lng: attr.lng },
        map: state.map,
        title: name,
        icon: {
            url: iconDataUrl,
            scaledSize: new google.maps.Size(36, 46),
            anchor: new google.maps.Point(18, 46),
        },
        animation: google.maps.Animation.DROP,
        zIndex: 10 + dayIdx * 10 + seqIdx,
    });

    const isAdded = isAttractionInRoute(attr, attr.day_number);
    const addBtnText = isAdded ? (window.t ? window.t('added_to_route_btn') : '✓ Dodano do drogi') : (window.t ? window.t('add_to_route_btn') : '➕ Dodaj do drogi');
    const addBtnStyle = isAdded
        ? 'display:inline-block; margin-top:8px; margin-left:4px; padding:4px 10px; background:#00875A; color:#fff; border:none; border-radius:6px; font-size:11px; font-weight:600;'
        : 'display:inline-block; margin-top:8px; margin-left:4px; padding:4px 10px; background:#F9A825; color:#000; border:none; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;';

    // Build info window HTML
    const ratingStars = rating ? `<span style="color:#F9A825; font-weight:bold;">⭐ ${rating}</span>` : '';
    const categoryBadge = `<span style="background:${color}20; color:${color}; border:1px solid ${color}60; border-radius:12px; padding:1px 8px; font-size:11px; font-weight:600;">${emoji} ${label}</span>`;

    const infoContent = `
        <div style="font-family:Arial,sans-serif; max-width:250px; padding:4px;">
            ${photoUrl ? `
                <div style="margin:-4px -4px 8px -4px; border-radius:4px 4px 0 0; overflow:hidden; height:130px;">
                    <img src="${photoUrl}" alt="${name}"
                         style="width:100%; height:130px; object-fit:cover;"
                         onerror="this.parentElement.style.display='none';">
                </div>` : ''}
            <div style="padding: ${photoUrl ? '0' : '4px'} 2px 4px;">
                ${categoryBadge}
                <div style="font-weight:700; color:#001E50; font-size:14px; margin:6px 0 2px; line-height:1.3;">${name}</div>
                ${ratingStars ? `<div style="margin:2px 0; font-size:12px;">${ratingStars}</div>` : ''}
                ${address ? `<div style="font-size:11px; color:#666; margin:2px 0;">📍 ${address}</div>` : ''}
                <div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:4px; align-items:center;">
                    <a href="${mapsUrl}" target="_blank" rel="noopener"
                       style="display:inline-block; padding:4px 10px; background:#001E50; color:#fff;
                              border-radius:6px; font-size:11px; text-decoration:none; font-weight:600;">
                       🗺️ Otwórz w Google Maps
                    </a>
                    <button class="btn-add-attraction-route ${isAdded ? 'added' : ''}" data-attr-key="${attrKey}" ${isAdded ? 'disabled' : ''}
                            onclick="window.addAttractionToRouteFromCache('${attrKey}')"
                            style="${addBtnStyle}">
                       ${addBtnText}
                    </button>
                </div>
            </div>
        </div>`;

    const infoWindow = new google.maps.InfoWindow({ content: infoContent });
    marker.addListener('click', () => openSingleInfoWindow(infoWindow, marker));

    return marker;
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
    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.style.display = 'none';

    let formattedText = text;
    if (role === 'assistant') {
        formattedText = text
            .replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, url) => {
                return `<div class="chat-photo-card" style="margin: 8px 0; max-width: 340px;"><img src="${url}" alt="${alt}" style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);" onerror="this.parentElement.style.display='none'"></div>`;
            })
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // 1. Main Chat View
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `
            <div class="message-bubble">${formattedText}</div>
            <div class="message-meta">${timeStr}</div>
        `;
        const typingEl = document.getElementById('typing-indicator');
        if (typingEl && messagesEl.contains(typingEl)) {
            messagesEl.insertBefore(msgDiv, typingEl);
        } else {
            messagesEl.appendChild(msgDiv);
        }
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // 2. Map Mini Chat Window
    const mapMessagesEl = document.getElementById('map-chat-messages');
    if (mapMessagesEl) {
        const mapMsgDiv = document.createElement('div');
        mapMsgDiv.className = `message ${role}`;
        mapMsgDiv.style.padding = '10px 14px';
        mapMsgDiv.style.fontSize = '0.85rem';
        mapMsgDiv.innerHTML = `
            <div class="message-bubble">${formattedText}</div>
            <div class="message-meta" style="font-size:0.68rem; margin-top:4px;">${timeStr}</div>
        `;
        const mapTypingEl = document.getElementById('map-typing-indicator');
        if (mapTypingEl && mapMessagesEl.contains(mapTypingEl)) {
            mapMessagesEl.insertBefore(mapMsgDiv, mapTypingEl);
        } else {
            mapMessagesEl.appendChild(mapMsgDiv);
        }
        mapMessagesEl.scrollTop = mapMessagesEl.scrollHeight;
    }

    state.chatHistory.push({ role, text });
}

function showTyping(show) {
    state.isTyping = show;
    
    const typingEl = document.getElementById('typing-indicator');
    if (typingEl) typingEl.classList.toggle('visible', show);
    const messagesEl = document.getElementById('chat-messages');
    if (show && messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;

    const mapTypingEl = document.getElementById('map-typing-indicator');
    if (mapTypingEl) mapTypingEl.classList.toggle('visible', show);
    const mapMessagesEl = document.getElementById('map-chat-messages');
    if (show && mapMessagesEl) mapMessagesEl.scrollTop = mapMessagesEl.scrollHeight;
}

async function sendMessage(text) {
    if (!text || !text.trim() || state.isTyping) return;

    addMessage('user', text);

    // Reset main chat input
    const input = document.getElementById('chat-input');
    if (input) {
        input.value = '';
        input.style.height = 'auto';
    }
    const charCounter = document.getElementById('char-counter');
    if (charCounter) charCounter.textContent = `0/1000`;
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.disabled = true;

    // Reset map mini chat input
    const mapInput = document.getElementById('map-chat-input');
    if (mapInput) {
        mapInput.value = '';
        mapInput.style.height = 'auto';
    }
    const mapSendBtn = document.getElementById('map-chat-send');
    if (mapSendBtn) mapSendBtn.disabled = true;

    showTyping(true);
    const result = await apiCall('chat', { message: text });
    showTyping(false);

    if (sendBtn) sendBtn.disabled = false;
    if (mapSendBtn) mapSendBtn.disabled = false;

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

                // Camping search tool call → pop up recommendation modal with Google Places photos
                if (
                    tc.function_name === 'search_campings' &&
                    tc.result && tc.result.status === 'success' &&
                    tc.result.results && tc.result.results.length > 0
                ) {
                    setTimeout(() => {
                        openCampingSearchModal(tc.result.results);
                    }, 500);
                }

                // Adding a single attraction → add one marker to map
                if (
                    tc.function_name === 'add_attraction' &&
                    tc.result && tc.result.status === 'success'
                ) {
                    const attr = tc.result.attraction;
                    const isOvernight = tc.result.is_overnight;
                    if (attr && state.mapInitialized) {
                        addMarker(
                            attr.lat,
                            attr.lng,
                            attr.name,
                            null,
                            isOvernight ? '🏕️' : '⭐'
                        );
                    }
                }
            });
        }

        if (result.trip_data) {
            displayTripOnMap(result.trip_data);
            routePlanned = true;
        }

        // Auto-redirect to map if a route was just planned AND trigger Camping Selection Modal
        if (routePlanned) {
            setTimeout(() => {
                if (state.currentView === 'chat') {
                    switchView('map');
                }
                if (state.currentTrip) {
                    openCampingSelectionModal(state.currentTrip, 0);
                }
            }, 1200);
        }
    } else {
        const errorFallback = result.text || result.message || (window.t ? window.t('connection_error') : 'Wystąpił problem z połączeniem. Spróbuj powtórzyć zapytanie.');
        addMessage('assistant', errorFallback);
    }
}

// ── Memories Gallery ─────────────────────────────────────────

/**
 * Ładuje galerię wygenerowanych Memories z serwera
 * i renderuje siatkę kart w modalu.
 */
async function loadMemoriesGallery() {
    const loadingEl = document.getElementById('memories-gallery-loading');
    const emptyEl   = document.getElementById('memories-gallery-empty');
    const gridEl    = document.getElementById('memories-gallery-grid');
    const badgeEl   = document.getElementById('memories-count-badge');

    // Pokaż spinner, ukryj resztę
    if (loadingEl) loadingEl.style.display  = 'flex';
    if (emptyEl)   emptyEl.style.display    = 'none';
    if (gridEl)    gridEl.style.display     = 'none';

    try {
        const res  = await fetch(`${API_BASE}/api/memories`);
        const data = await res.json();

        if (loadingEl) loadingEl.style.display = 'none';

        if (data.status !== 'success' || !data.memories || data.memories.length === 0) {
            if (emptyEl) emptyEl.style.display = 'flex';
            if (badgeEl) badgeEl.style.display = 'none';
            return;
        }

        // Aktualizuj badge z liczbą Memories
        if (badgeEl) {
            badgeEl.textContent = data.memories.length;
            badgeEl.style.display = 'inline-flex';
        }

        if (gridEl) {
            gridEl.innerHTML = '';
            data.memories.forEach(mem => {
                const card = _buildMemoryCard(mem);
                gridEl.appendChild(card);
            });
            gridEl.style.display = 'grid';
        }
    } catch (err) {
        console.error('Failed to load memories gallery:', err);
        if (loadingEl) loadingEl.style.display = 'none';
        if (emptyEl)   emptyEl.style.display   = 'flex';
    }
}

/**
 * Buduje kartę HTML dla jednego rekordu Memory.
 * @param {Object} mem - rekord z /api/memories
 * @returns {HTMLElement}
 */
function _buildMemoryCard(mem) {
    const card = document.createElement('div');
    card.className = 'memory-card';
    if (!mem.file_exists) card.classList.add('memory-card--missing');

    // Etykieta formatu
    const formatLabels = {
        video:            '🎬 Wideo',
        image_slideshow:  '🖼️ Pokaz slajdów',
        pdf:              '📄 PDF',
    };
    const formatLabel = formatLabels[mem.format] || mem.format;

    // Ikona muzyki
    const musicLabel = mem.music_track && mem.music_track !== 'none'
        ? `🎵 ${mem.music_track.replace(/_/g, ' ')}`
        : '';

    // Data generowania
    const genDate = mem.generated_at
        ? new Date(mem.generated_at).toLocaleDateString('pl-PL', { day: '2-digit', month: 'short', year: 'numeric' })
        : '';

    // Daty wycieczki
    const tripDates = (mem.start_date && mem.end_date)
        ? `${mem.start_date} → ${mem.end_date}`
        : '';

    // Thumbnail: dla wideo — ikona play, dla slideshow — pierwsze PNG, dla PDF — ikona dokumentu
    let thumbnailHTML;
    if (mem.format === 'video') {
        thumbnailHTML = `
            <div class="memory-card-thumb memory-card-thumb--video">
                <div class="memory-card-play-icon">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="40" height="40">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                </div>
                <span class="memory-card-format-chip">${formatLabel}</span>
            </div>`;
    } else if (mem.format === 'pdf') {
        thumbnailHTML = `
            <div class="memory-card-thumb memory-card-thumb--pdf">
                <span style="font-size:3rem;">📄</span>
                <span class="memory-card-format-chip">${formatLabel}</span>
            </div>`;
    } else {
        // image_slideshow — pokaż miniaturę pierwszego slajdu
        thumbnailHTML = `
            <div class="memory-card-thumb memory-card-thumb--slideshow">
                <img src="${mem.file_url}" alt="Miniatura" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="memory-card-thumb-fallback" style="display:none;">
                    <span style="font-size:2.5rem;">🖼️</span>
                </div>
                <span class="memory-card-format-chip">${formatLabel}</span>
            </div>`;
    }

    const missingLabel = !mem.file_exists
        ? '<div class="memory-card-missing-chip">⚠️ Plik niedostępny</div>'
        : '';

    card.innerHTML = `
        ${thumbnailHTML}
        <div class="memory-card-body">
            <div class="memory-card-trip">${mem.trip_title}</div>
            ${tripDates ? `<div class="memory-card-dates">${tripDates}</div>` : ''}
            <div class="memory-card-meta">
                <span class="memory-card-date">${genDate}</span>
                ${musicLabel ? `<span class="memory-card-music">${musicLabel}</span>` : ''}
            </div>
            ${missingLabel}
            ${mem.file_exists ? `
            <div class="memory-card-actions">
                <button class="btn-primary memory-card-btn-play" data-url="${mem.file_url}" data-format="${mem.format}" data-title="${mem.trip_title}">
                    ${mem.format === 'pdf' ? '📥 Pobierz PDF' : '▶ Odtwórz'}
                </button>
                <a href="${mem.file_url}" download class="btn-secondary memory-card-btn-dl" title="Pobierz">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </a>
            </div>` : ''}
        </div>`;

    // Zdarzenie odtwarzania
    const playBtn = card.querySelector('.memory-card-btn-play');
    if (playBtn) {
        playBtn.addEventListener('click', () => {
            openMemoriesViewer(
                playBtn.dataset.url,
                playBtn.dataset.format,
                playBtn.dataset.title
            );
        });
    }

    return card;
}

/**
 * Otwiera modal odtwarzacza Memories.
 * @param {string} url    - URL pliku
 * @param {string} format - 'video' | 'image_slideshow' | 'pdf'
 * @param {string} title  - tytuł wycieczki
 */
function openMemoriesViewer(url, format, title) {
    const modal   = document.getElementById('memories-viewer-modal');
    const content = document.getElementById('memories-viewer-content');
    if (!modal || !content) return;

    let innerHTML = `<div class="memories-viewer-title">${title}</div>`;

    if (format === 'video') {
        innerHTML += `
            <video src="${url}" controls autoplay
                style="max-height:78vh; max-width:92vw; border-radius:14px;
                       box-shadow:0 12px 40px rgba(0,0,0,0.6); border:2px solid rgba(255,255,255,0.12);">
            </video>
            <a href="${url}" download class="btn-primary" style="text-decoration:none;padding:10px 24px;border-radius:24px;">
                📥 Pobierz wideo MP4
            </a>`;
    } else if (format === 'pdf') {
        innerHTML += `
            <div style="font-size:4rem;margin-bottom:8px;">📄</div>
            <a href="${url}" download="Raport_Podrozy_VW.pdf" class="btn-primary"
               style="text-decoration:none;padding:14px 28px;border-radius:28px;">
                📥 Pobierz PDF
            </a>`;
    } else {
        // image_slideshow — pokaż slajd w pełnym widoku
        innerHTML += `
            <img src="${url}" alt="${title}"
                style="max-height:78vh; max-width:92vw; object-fit:contain;
                       border-radius:14px; box-shadow:0 12px 40px rgba(0,0,0,0.6);">
            <a href="${url}" download class="btn-primary" style="text-decoration:none;padding:10px 24px;border-radius:24px;">
                📥 Pobierz obraz
            </a>`;
    }

    content.innerHTML = innerHTML;
    modal.style.display = 'flex';
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

            if (result.photo) {
                const fname = result.photo.original_filename || file.name;
                const photoUrl = `/photos/file/${fname}`;

                // Update gallery card img tag with converted server URL for HEIC support
                card.innerHTML = `<img src="${photoUrl}" alt="${fname}" onerror="this.onerror=null; this.src='${photoUrl}';"><div class="photo-overlay">${fname}</div>`;

                if (result.photo.lat && result.photo.lng) {
                    let markerLabel = '📷';
                    if (result.linked && result.photo.day_number) {
                        markerLabel = `Dzień ${result.photo.day_number} 📷`;
                    }
                    addMarker(
                        result.photo.lat,
                        result.photo.lng,
                        fname,
                        null,
                        markerLabel,
                        photoUrl,
                        result.photo.id,
                        true
                    );
                }
            }
        } catch (error) { console.error('Upload failed:', error); }
    }
}

// ── Event Listeners ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    
    // Language Switcher setup
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const lang = e.currentTarget.dataset.lang;
            if (window.vwI18n) {
                window.vwI18n.setLanguage(lang);
            }
        });
    });

    if (window.vwI18n) {
        window.vwI18n.updateStaticUI();
    }

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

    // Map Mini Chat Window
    const mapChatBubble = document.getElementById('map-chat-bubble');
    const mapChatPanel = document.getElementById('map-chat-panel');
    const mapChatClose = document.getElementById('map-chat-close');
    const mapChatInput = document.getElementById('map-chat-input');
    const mapChatSend = document.getElementById('map-chat-send');

    if (mapChatBubble && mapChatPanel) {
        mapChatBubble.addEventListener('click', () => {
            const isHidden = mapChatPanel.style.display === 'none' || !mapChatPanel.style.display;
            mapChatPanel.style.display = isHidden ? 'flex' : 'none';
            if (isHidden && mapChatInput) {
                mapChatInput.focus();
                const mapMessagesEl = document.getElementById('map-chat-messages');
                if (mapMessagesEl) mapMessagesEl.scrollTop = mapMessagesEl.scrollHeight;
            }
        });
    }

    if (mapChatClose && mapChatPanel) {
        mapChatClose.addEventListener('click', () => {
            mapChatPanel.style.display = 'none';
        });
    }

    if (mapChatInput) {
        mapChatInput.addEventListener('input', () => {
            mapChatInput.style.height = 'auto';
            mapChatInput.style.height = Math.min(mapChatInput.scrollHeight, 100) + 'px';
        });

        mapChatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(mapChatInput.value);
            }
        });
    }

    if (mapChatSend) {
        mapChatSend.addEventListener('click', () => {
            if (mapChatInput) sendMessage(mapChatInput.value);
        });
    }

    // ── Voice Chat Toast Helper ──────────────────────────────
    function showToast(message, type = 'info', duration = 3000) {
        let toast = document.getElementById('voice-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'voice-toast';
            toast.style.position = 'fixed';
            toast.style.bottom = '90px';
            toast.style.left = '50%';
            toast.style.transform = 'translateX(-50%)';
            toast.style.padding = '10px 20px';
            toast.style.borderRadius = '20px';
            toast.style.background = 'rgba(0, 30, 80, 0.92)';
            toast.style.color = '#fff';
            toast.style.fontSize = '0.9rem';
            toast.style.fontWeight = '500';
            toast.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
            toast.style.zIndex = '9999';
            toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            toast.style.pointerEvents = 'none';
            toast.style.backdropFilter = 'blur(4px)';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(0)';
        
        if (toast.timeoutId) clearTimeout(toast.timeoutId);
        toast.timeoutId = setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(10px)';
        }, duration);
    }

    // ── Voice Chat Input (Hybrid Web Speech + MediaRecorder API) ────
    function setupVoiceInput() {
        const micBtn = document.getElementById('mic-btn');
        const mapMicBtn = document.getElementById('map-mic-btn');

        if (!micBtn && !mapMicBtn) return;

        const hasMediaDevices = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!hasMediaDevices && !SpeechRecognition) {
            if (micBtn) micBtn.style.display = 'none';
            if (mapMicBtn) mapMicBtn.style.display = 'none';
            return;
        }

        if (micBtn) micBtn.style.display = 'flex';
        if (mapMicBtn) mapMicBtn.style.display = 'flex';

        let mediaRecorder = null;
        let audioChunks = [];
        let activeMicBtn = null;
        let activeTargetInput = null;
        let isRecording = false;

        function stopRecordingState() {
            isRecording = false;
            if (activeMicBtn) {
                activeMicBtn.classList.remove('recording', 'active', 'processing');
                const startTitle = (window.vwI18n && window.vwI18n.t) ? window.vwI18n.t('mic_tooltip_start') : 'Dyktuj wiadomość';
                activeMicBtn.setAttribute('title', startTitle);
                activeMicBtn = null;
            }
            activeTargetInput = null;
        }

        function startNativeSpeechRecognition(btnEl, inputEl) {
            const NativeSpeech = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!NativeSpeech) {
                const currentLang = (window.vwI18n && window.vwI18n.currentLanguage) ? window.vwI18n.currentLanguage : 'pl';
                showToast(currentLang === 'de' ? 'Server-Fehler. Bitte Server neu starten.' : 'Serwer nie odpowiedział poprawnie. Zrestartuj serwer backendowy.', 'error', 4000);
                stopRecordingState();
                return;
            }

            const currentLang = (window.vwI18n && window.vwI18n.currentLanguage) ? window.vwI18n.currentLanguage : 'pl';
            showToast(currentLang === 'de' ? '🎙️ Spracherkennung...' : '🎙️ Dyktowanie głosu w przeglądarce...', 'info', 3000);

            const recognition = new NativeSpeech();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = currentLang === 'de' ? 'de-DE' : 'pl-PL';

            let initialText = inputEl.value;
            if (initialText && !initialText.endsWith(' ')) {
                initialText += ' ';
            }

            recognition.onstart = () => {
                isRecording = true;
                activeMicBtn = btnEl;
                activeTargetInput = inputEl;
                btnEl.classList.remove('processing');
                btnEl.classList.add('recording', 'active');
            };

            recognition.onresult = (event) => {
                let sessionTranscript = '';
                for (let i = 0; i < event.results.length; i++) {
                    sessionTranscript += event.results[i][0].transcript;
                }
                if (sessionTranscript) {
                    inputEl.value = initialText + sessionTranscript;
                    inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                }
            };

            recognition.onerror = (e) => {
                console.warn('Native speech error:', e.error);
                stopRecordingState();
            };

            recognition.onend = () => {
                stopRecordingState();
            };

            try {
                recognition.start();
            } catch (err) {
                stopRecordingState();
            }
        }

        async function startMediaRecorder(btnEl, inputEl) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioChunks = [];
                
                const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' :
                                 MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';
                
                mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach(track => track.stop());

                    const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                    const currentLang = (window.vwI18n && window.vwI18n.currentLanguage) ? window.vwI18n.currentLanguage : 'pl';

                    if (!audioBlob || audioBlob.size < 200) {
                        showToast(currentLang === 'de' ? 'Aufnahme zu kurz' : 'Nagranie było za krótkie lub puste.', 'warning', 3000);
                        stopRecordingState();
                        return;
                    }
                    
                    if (btnEl) {
                        btnEl.classList.remove('recording', 'active');
                        btnEl.classList.add('processing');
                    }
                    showToast(currentLang === 'de' ? '⏳ Sprache wird verarbeitet...' : '⏳ Przetwarzanie głosu na tekst...', 'info', 10000);

                    try {
                        const formData = new FormData();
                        formData.append('file', audioBlob, 'speech.webm');
                        formData.append('lang', currentLang);

                        const response = await fetch(`${API_BASE}/api/transcribe`, {
                            method: 'POST',
                            body: formData
                        });

                        const data = await response.json();
                        if (data.status === 'success' && data.text) {
                            let textToAppend = data.text;
                            if (inputEl.value && !inputEl.value.endsWith(' ')) {
                                inputEl.value += ' ' + textToAppend;
                            } else {
                                inputEl.value += textToAppend;
                            }
                            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                            showToast(currentLang === 'de' ? '✅ Nachricht diktiert!' : '✅ Dodano podyktowaną wiadomość!', 'success', 2500);
                        } else {
                            showToast(data.message || (currentLang === 'de' ? 'Keine Sprache erkannt' : 'Nie rozpoznano mowy. Spróbuj powtórzyć.'), 'warning', 4000);
                        }
                    } catch (err) {
                        console.error('Transcription API error:', err);
                        showToast(err.message || 'Błąd przesyłania nagrania.', 'error', 3000);
                    } finally {
                        stopRecordingState();
                    }
                };

                mediaRecorder.start(200);
                isRecording = true;
                activeMicBtn = btnEl;
                activeTargetInput = inputEl;
                btnEl.classList.add('recording', 'active');
                
                const stopTitle = (window.vwI18n && window.vwI18n.t) ? window.vwI18n.t('mic_tooltip_stop') : 'Zatrzymaj nasłuchiwanie';
                btnEl.setAttribute('title', stopTitle);

                const currentLang = (window.vwI18n && window.vwI18n.currentLanguage) ? window.vwI18n.currentLanguage : 'pl';
                showToast(currentLang === 'de' ? '🎙️ Ich höre zu... sprich jetzt (klicke erneut zum Beenden)' : '🎙️ Słucham... mów teraz (kliknij mikrofon ponownie, by zakończyć)', 'info', 5000);

            } catch (err) {
                console.error('Microphone access error:', err);
                const currentLang = (window.vwI18n && window.vwI18n.currentLanguage) ? window.vwI18n.currentLanguage : 'pl';
                showToast(currentLang === 'de' ? 'Mikrofonzugriff verweigert' : 'Brak dostępu do mikrofonu. Sprawdź uprawnienia w przeglądarce.', 'error', 4000);
                stopRecordingState();
            }
        }

        function toggleVoiceInput(btnEl, inputEl) {
            if (isRecording && mediaRecorder && mediaRecorder.state === 'recording') {
                try {
                    mediaRecorder.requestData();
                } catch (e) {}
                mediaRecorder.stop();
                return;
            }

            if (isRecording) {
                stopRecordingState();
                return;
            }

            startMediaRecorder(btnEl, inputEl);
        }

        if (micBtn) {
            micBtn.addEventListener('click', () => {
                const input = document.getElementById('chat-input');
                if (input) toggleVoiceInput(micBtn, input);
            });
        }

        if (mapMicBtn) {
            mapMicBtn.addEventListener('click', () => {
                const mapInput = document.getElementById('map-chat-input');
                if (mapInput) toggleVoiceInput(mapMicBtn, mapInput);
            });
        }
    }

    setupVoiceInput();

    // Quick actions
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', () => sendMessage(btn.dataset.prompt));
    });

    const tripInfoCardEl = document.getElementById('trip-info-card');
    const tripInfoCloseBtn = document.getElementById('trip-info-close');
    if (tripInfoCloseBtn && tripInfoCardEl) {
        tripInfoCloseBtn.addEventListener('click', () => {
            tripInfoCardEl.classList.remove('visible');
        });
    }

    const btnToggleTripInfo = document.getElementById('btn-toggle-trip-info');
    if (btnToggleTripInfo) {
        btnToggleTripInfo.addEventListener('click', () => {
            if (tripInfoCardEl) {
                if (tripInfoCardEl.classList.contains('visible') && !tripInfoCardEl.classList.contains('collapsed')) {
                    tripInfoCardEl.classList.toggle('collapsed');
                } else {
                    tripInfoCardEl.classList.remove('collapsed');
                    tripInfoCardEl.classList.add('visible');
                }
            }
        });
    }

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

    let currentSlideIndex = 0;
    let slideshowSlides = [];
    let slideshowTimer = null;

    function renderSlide(index) {
        if (!slideshowSlides || slideshowSlides.length === 0) return;
        currentSlideIndex = (index + slideshowSlides.length) % slideshowSlides.length;
        const currentUrl = slideshowSlides[currentSlideIndex];

        summaryCarousel.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%;">
                <img src="${currentUrl}" alt="Slajd ${currentSlideIndex + 1}" style="max-height: 65vh; max-width: 90vw; object-fit: contain; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); border: 2px solid rgba(255,255,255,0.1);">
            </div>
        `;

        const counterEl = document.getElementById('slideshow-counter');
        if (counterEl) counterEl.textContent = `Slajd ${currentSlideIndex + 1} / ${slideshowSlides.length}`;
        const downloadBtn = document.getElementById('slideshow-download-btn');
        if (downloadBtn) {
            downloadBtn.href = currentUrl;
            downloadBtn.download = `Slajd_${currentSlideIndex + 1}.png`;
        }
    }

    function stopSlideshowTimer() {
        if (slideshowTimer) {
            clearInterval(slideshowTimer);
            slideshowTimer = null;
        }
    }

    async function triggerSummaryGeneration(format) {
        stopSlideshowTimer();

        // Stop audio preview if playing
        const audioPlayer = document.getElementById('audio-preview-player');
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
        }
        const previewBtn = document.getElementById('btn-preview-audio');
        if (previewBtn) previewBtn.textContent = '▶ Odsłuchaj';

        summaryOptions.style.display = 'none';
        summaryResultView.style.display = 'flex';
        summaryCarousel.innerHTML = '';

        const musicSelect = document.getElementById('select-music-track');
        const selectedMusic = musicSelect ? musicSelect.value : 'acoustic_sunset';

        const controlsDiv = document.getElementById('summary-controls');
        controlsDiv.innerHTML = '<span id="summary-loading" style="color: white; font-weight: bold; font-size: 1.1rem;">Generuję podsumowanie podróży z muzyką... 🎵🚐</span>';

        const result = await apiCall('generate_summary', {
            trip_id: state.currentTrip.trip.id,
            format: format,
            music_track: selectedMusic === 'none' ? null : selectedMusic
        });

        if (result.status === 'success') {
            controlsDiv.innerHTML = '';

            if (format === 'video' && result.file_url) {
                summaryCarousel.innerHTML = `
                    <video src="${result.file_url}" controls autoplay style="max-height: 70vh; max-width: 90vw; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);"></video>
                `;
                controlsDiv.innerHTML = `
                    <a href="${result.file_url}" download target="_blank" class="btn-primary btn-success" style="text-decoration: none; padding: 12px 24px; border-radius: 24px; font-weight: bold;">
                        📥 Pobierz wideo MP4
                    </a>
                `;
            } else if (format === 'pdf' && result.file_url) {
                summaryCarousel.innerHTML = `
                    <div style="background: white; border-radius: 20px; padding: 40px; text-align: center; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
                        <div style="font-size: 3.5rem; margin-bottom: 12px;">📄</div>
                        <h3 style="color: #001E50; font-size: 1.5rem; margin-bottom: 8px;">Dokument PDF Gotowy!</h3>
                        <p style="color: #555; font-size: 0.95rem; margin-bottom: 24px;">Pełny raport wyjazdu z planem dnia, kempingami i statystykami.</p>
                        <a href="${result.file_url}" download="Raport_Podrozy_VW.pdf" target="_blank" class="btn-primary" style="text-decoration: none; justify-content: center; font-size: 1.05rem; padding: 14px 28px; background: #001E50; border-radius: 30px;">
                            📥 Pobierz dokument PDF
                        </a>
                    </div>
                `;
            } else if (result.all_slides && result.all_slides.length > 0) {
                slideshowSlides = result.all_slides;
                currentSlideIndex = 0;

                controlsDiv.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px; background: rgba(0,30,80,0.85); padding: 8px 20px; border-radius: 30px; backdrop-filter: blur(10px); box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
                        <button id="btn-prev-slide" class="btn-primary" style="padding: 6px 14px; font-size: 0.9rem;">◀ Poprzedni</button>
                        <span id="slideshow-counter" style="color: white; font-weight: bold; font-size: 0.9rem; min-width: 90px; text-align: center;">Slajd 1 / ${slideshowSlides.length}</span>
                        <button id="btn-next-slide" class="btn-primary" style="padding: 6px 14px; font-size: 0.9rem;">Następny ▶</button>
                        <button id="btn-play-slide" class="btn-primary btn-success" style="padding: 6px 14px; font-size: 0.9rem;">▶ Autoplay</button>
                        <a id="slideshow-download-btn" href="${slideshowSlides[0]}" download="Slajd_1.png" class="btn-primary btn-info" style="text-decoration: none; padding: 6px 14px; font-size: 0.9rem;">📥 Pobierz slajd</a>
                    </div>
                `;

                renderSlide(0);

                document.getElementById('btn-prev-slide').addEventListener('click', () => renderSlide(currentSlideIndex - 1));
                document.getElementById('btn-next-slide').addEventListener('click', () => renderSlide(currentSlideIndex + 1));

                const playBtn = document.getElementById('btn-play-slide');
                playBtn.addEventListener('click', () => {
                    if (slideshowTimer) {
                        stopSlideshowTimer();
                        playBtn.textContent = '▶ Autoplay';
                        playBtn.style.background = '#00875A';
                    } else {
                        slideshowTimer = setInterval(() => {
                            renderSlide(currentSlideIndex + 1);
                        }, 1200);
                        playBtn.textContent = '⏸ Pauza';
                        playBtn.style.background = '#E57373';
                    }
                });
            }
        } else {
            alert(result.message || "Błąd generowania podsumowania.");
            summaryModal.style.display = 'none';
        }
    }

    btnGenerateSummary.addEventListener('click', () => {
        if (!state.currentTrip) { alert("Najpierw zaplanuj trasę!"); return; }
        summaryModal.style.display = 'flex';
        summaryOptions.style.display = 'block';
        summaryResultView.style.display = 'none';
    });

    const exportSlideshowBtn = document.getElementById('btn-export-slideshow');
    if (exportSlideshowBtn) exportSlideshowBtn.addEventListener('click', () => triggerSummaryGeneration('image_slideshow'));

    const exportVideoBtn = document.getElementById('btn-export-video');
    if (exportVideoBtn) exportVideoBtn.addEventListener('click', () => triggerSummaryGeneration('video'));

    // Audio preview toggle button
    document.addEventListener('click', (e) => {
        if (e.target.id !== 'btn-preview-audio') return;
        const musicSelect = document.getElementById('select-music-track');
        const audioPlayer = document.getElementById('audio-preview-player');
        if (!musicSelect || !audioPlayer) return;

        const selectedTrack = musicSelect.value;
        if (selectedTrack === 'none') {
            audioPlayer.pause();
            e.target.textContent = '▶ Odsłuchaj';
            return;
        }

        const isPlaying = !audioPlayer.paused;
        const currentSrc = audioPlayer.src;
        const newSrc = `/assets/audio/${selectedTrack}.mp3`;

        if (isPlaying && currentSrc.endsWith(`${selectedTrack}.mp3`)) {
            audioPlayer.pause();
            e.target.textContent = '▶ Odsłuchaj';
        } else {
            audioPlayer.src = newSrc;
            audioPlayer.volume = 0.5;
            audioPlayer.loop = true;
            audioPlayer.play().catch(() => {});
            e.target.textContent = '⏸ Zatrzymaj';
        }
    });

    // Update preview button state when track changes
    document.addEventListener('change', (e) => {
        if (e.target.id !== 'select-music-track') return;
        const audioPlayer = document.getElementById('audio-preview-player');
        const previewBtn = document.getElementById('btn-preview-audio');
        if (audioPlayer && !audioPlayer.paused) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            if (previewBtn) previewBtn.textContent = '▶ Odsłuchaj';
        }
    });

    summaryClose.addEventListener('click', () => {
        stopSlideshowTimer();
        // Also stop audio preview
        const audioPlayer = document.getElementById('audio-preview-player');
        if (audioPlayer) { audioPlayer.pause(); audioPlayer.currentTime = 0; }
        const previewBtn = document.getElementById('btn-preview-audio');
        if (previewBtn) previewBtn.textContent = '▶ Odsluchaj';
        summaryModal.style.display = 'none';
        // Odśwież galerię po zamknięciu modalu (nowe Memory mogło zostać dodane)
        loadMemoriesGallery();
    });

    // ── Memories Gallery ─────────────────────────────────────
    const btnOpenMemoriesGallery = document.getElementById('btn-open-memories-gallery');
    const memoriesGalleryModal   = document.getElementById('memories-gallery-modal');
    const memoriesGalleryClose   = document.getElementById('memories-gallery-close');
    const memoriesViewerModal    = document.getElementById('memories-viewer-modal');
    const memoriesViewerClose    = document.getElementById('memories-viewer-close');

    if (btnOpenMemoriesGallery && memoriesGalleryModal) {
        btnOpenMemoriesGallery.addEventListener('click', () => {
            memoriesGalleryModal.style.display = 'flex';
            loadMemoriesGallery();
        });
    }

    if (memoriesGalleryClose && memoriesGalleryModal) {
        memoriesGalleryClose.addEventListener('click', () => {
            memoriesGalleryModal.style.display = 'none';
        });
        // Kliknięcie poza panelem zamyka modal
        memoriesGalleryModal.addEventListener('click', (e) => {
            if (e.target === memoriesGalleryModal) memoriesGalleryModal.style.display = 'none';
        });
    }

    if (memoriesViewerClose && memoriesViewerModal) {
        memoriesViewerClose.addEventListener('click', () => {
            // Zatrzymaj wideo jeśli jest odtwarzane
            const video = memoriesViewerModal.querySelector('video');
            if (video) { video.pause(); video.src = ''; }
            memoriesViewerModal.style.display = 'none';
        });
        memoriesViewerModal.addEventListener('click', (e) => {
            if (e.target === memoriesViewerModal) {
                const video = memoriesViewerModal.querySelector('video');
                if (video) { video.pause(); video.src = ''; }
                memoriesViewerModal.style.display = 'none';
            }
        });
    }

    // Authentication simple implementation
    const authModal = document.getElementById('auth-modal');
    const btnLogin = document.getElementById('btn-login');
    const btnLogout = document.getElementById('btn-logout');

    // ── Welcome Screen & Interactive Tutorial Engine ──────────────
    let activeTutorialSteps = null;
    let activeTutorialStorageKey = null;
    let currentTutorialStepIdx = 0;

    const TUTORIAL_STEPS = [
        {
            targetId: 'slot-progress',
            titleKey: 'tut_step1_title',
            descKey: 'tut_step1_desc',
            title: 'Wskaźniki postępu trasy',
            desc: 'Śledź status dopasowania Twojej trasy: Cel, Doświadczenie, Tempo, Baza wypadowa oraz Czas trwania.',
            position: 'bottom'
        },
        {
            targetId: 'quick-actions',
            titleKey: 'tut_step2_title',
            descKey: 'tut_step2_desc',
            title: 'Szybkie starty & Opis trasy',
            desc: 'Wpisz własnymi słowami cel podróży na dole lub wybierz gotowy plan z kart szybkich startów.',
            position: 'top'
        },
        {
            targetId: 'nav-map',
            titleKey: 'tut_step3_title',
            descKey: 'tut_step3_desc',
            title: 'Interaktywna Mapa',
            desc: 'Przeglądaj trasę w czasie rzeczywistym, pogodę oraz kempingi dostosowane dla VW California.',
            position: 'right'
        },
        {
            targetId: 'nav-memory',
            titleKey: 'tut_step4_title',
            descKey: 'tut_step4_desc',
            title: 'Pamięć Podróży',
            desc: 'Twórz historię wyjazdów! Dodawaj zdjęcia, które AI przypisze do miejsc na mapie na podstawie GPS i danych EXIF.',
            position: 'right'
        },
        {
            targetId: 'nav-trips-btn',
            titleKey: 'tut_step5_title',
            descKey: 'tut_step5_desc',
            title: 'Moje Wyjazdy i Konto',
            desc: 'Przeglądaj zapisane podróże, generuj eksporty podsumowań oraz modyfikuj preferencje pojazdu.',
            position: 'right'
        }
    ];

    const MAP_TUTORIAL_STEPS = [
        {
            targetId: 'map-overlay',
            titleKey: 'tut_map_step1_title',
            descKey: 'tut_map_step1_desc',
            position: 'bottom'
        },
        {
            targetId: 'trip-info-card',
            titleKey: 'tut_map_step2_title',
            descKey: 'tut_map_step2_desc',
            position: 'top'
        }
    ];

    const MEMORY_TUTORIAL_STEPS = [
        {
            targetId: 'upload-zone',
            titleKey: 'tut_mem_step1_title',
            descKey: 'tut_mem_step1_desc',
            position: 'bottom'
        },
        {
            targetId: 'photo-grid',
            titleKey: 'tut_mem_step2_title',
            descKey: 'tut_mem_step2_desc',
            position: 'top'
        }
    ];

    const TRIPS_TUTORIAL_STEPS = [
        {
            targetId: 'trips-list',
            titleKey: 'tut_trips_step1_title',
            descKey: 'tut_trips_step1_desc',
            position: 'bottom'
        }
    ];

    window.TUTORIAL_STEPS = TUTORIAL_STEPS;
    window.MAP_TUTORIAL_STEPS = MAP_TUTORIAL_STEPS;
    window.MEMORY_TUTORIAL_STEPS = MEMORY_TUTORIAL_STEPS;
    window.TRIPS_TUTORIAL_STEPS = TRIPS_TUTORIAL_STEPS;

    function startTutorialSuite(steps, storageKey, force = false) {
        if (!steps || steps.length === 0) return;
        if (!force && storageKey && localStorage.getItem(storageKey) === 'true') {
            return;
        }
        activeTutorialSteps = steps;
        activeTutorialStorageKey = storageKey;
        currentTutorialStepIdx = 0;
        const overlay = document.getElementById('tutorial-overlay');
        if (overlay) overlay.style.display = 'block';
        renderActiveTutorialStep(currentTutorialStepIdx);
    }
    window.startTutorialSuite = startTutorialSuite;

    function renderActiveTutorialStep(stepIdx) {
        if (!activeTutorialSteps || stepIdx >= activeTutorialSteps.length) {
            endActiveTutorial();
            return;
        }

        const step = activeTutorialSteps[stepIdx];
        let targetEl = document.getElementById(step.targetId);
        if (!targetEl) {
            targetEl = document.querySelector('.' + step.targetId);
        }

        const highlightBox = document.getElementById('tutorial-highlight-box');
        const card = document.getElementById('tutorial-card');
        const badge = document.getElementById('tutorial-step-badge');
        const title = document.getElementById('tutorial-card-title');
        const desc = document.getElementById('tutorial-card-desc');
        const nextBtn = document.getElementById('tutorial-btn-next');
        const skipBtn = document.getElementById('tutorial-btn-skip');

        if (skipBtn && window.t) {
            skipBtn.textContent = window.t('tut_skip');
        }

        if (!targetEl || !highlightBox || !card) {
            endActiveTutorial();
            return;
        }

        const rect = targetEl.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
            setTimeout(() => renderActiveTutorialStep(stepIdx), 150);
            return;
        }

        try {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } catch (e) {}

        const pad = 6;
        highlightBox.style.top = `${rect.top - pad}px`;
        highlightBox.style.left = `${rect.left - pad}px`;
        highlightBox.style.width = `${rect.width + pad * 2}px`;
        highlightBox.style.height = `${rect.height + pad * 2}px`;

        const stepFmt = window.t ? window.t('tut_step_fmt', { step: stepIdx + 1, total: activeTutorialSteps.length }) : `Krok ${stepIdx + 1} z ${activeTutorialSteps.length}`;
        badge.textContent = stepFmt;

        const titleText = step.titleKey && window.t ? window.t(step.titleKey) : (step.title || '');
        const descText = step.descKey && window.t ? window.t(step.descKey) : (step.desc || '');

        title.textContent = titleText;
        desc.textContent = descText;

        const isLast = (stepIdx === activeTutorialSteps.length - 1);
        const finishText = window.t ? window.t('tut_finish') : 'Zakończ 🚀';
        const nextText = window.t ? window.t('tut_next') : 'Dalej &rarr;';
        nextBtn.innerHTML = isLast ? finishText : nextText;

        const cardWidth = 320;
        const cardHeight = card.offsetHeight || 200;

        let cardTop = rect.bottom + 16;
        let cardLeft = rect.left + (rect.width / 2) - (cardWidth / 2);

        if (step.position === 'right') {
            cardLeft = rect.right + 20;
            cardTop = rect.top + (rect.height / 2) - (cardHeight / 2);
        } else if (step.position === 'left') {
            cardLeft = rect.left - cardWidth - 20;
            cardTop = rect.top + (rect.height / 2) - (cardHeight / 2);
        } else if (step.position === 'top') {
            cardTop = rect.top - cardHeight - 20;
        }

        const margin = 16;
        if (cardLeft < margin) cardLeft = margin;
        if (cardLeft + cardWidth > window.innerWidth - margin) {
            cardLeft = window.innerWidth - cardWidth - margin;
        }
        if (cardTop < margin) cardTop = margin;
        if (cardTop + cardHeight > window.innerHeight - margin) {
            cardTop = window.innerHeight - cardHeight - margin;
        }

        card.style.top = `${cardTop}px`;
        card.style.left = `${cardLeft}px`;
    }

    function endActiveTutorial() {
        if (activeTutorialStorageKey) {
            localStorage.setItem(activeTutorialStorageKey, 'true');
        }
        activeTutorialSteps = null;
        activeTutorialStorageKey = null;
        const overlay = document.getElementById('tutorial-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    let hasWelcomeRun = false;

    function initWelcomeAndTutorial(displayName) {
        const welcomeOverlay = document.getElementById('welcome-overlay');
        const welcomeUserName = document.getElementById('welcome-user-name');

        if (displayName && welcomeUserName) {
            welcomeUserName.textContent = `Witaj, ${displayName}!`;
        }

        if (hasWelcomeRun) return;
        hasWelcomeRun = true;

        if (!welcomeOverlay) return;

        welcomeOverlay.style.display = 'flex';
        welcomeOverlay.classList.remove('fade-out');

        // Wait 1.8s, then fade out dark blue screen and start tutorial
        setTimeout(() => {
            welcomeOverlay.classList.add('fade-out');
            setTimeout(() => {
                welcomeOverlay.style.display = 'none';
                startTutorialSuite(TUTORIAL_STEPS, 'vw_tut_main_seen');
            }, 1200);
        }, 1800);
    }

    const btnTutorialNext = document.getElementById('tutorial-btn-next');
    const btnTutorialSkip = document.getElementById('tutorial-btn-skip');

    if (btnTutorialNext) {
        btnTutorialNext.addEventListener('click', () => {
            currentTutorialStepIdx++;
            if (activeTutorialSteps && currentTutorialStepIdx < activeTutorialSteps.length) {
                renderActiveTutorialStep(currentTutorialStepIdx);
            } else {
                endActiveTutorial();
            }
        });
    }

    if (btnTutorialSkip) {
        btnTutorialSkip.addEventListener('click', () => {
            endActiveTutorial();
        });
    }

    window.addEventListener('resize', () => {
        if (isTutorialActive) {
            renderTutorialStep(currentTutorialStep);
        }
        if (state && state.map) {
            google.maps.event.trigger(state.map, 'resize');
        }
    });

    // ── Tablet UI & Touch Interaction Handlers ──────────────────

    // Sheet Drag Handle Toggle for Map View
    const sheetDragHandle = document.getElementById('sheet-drag-handle');
    const tripInfoCard = document.getElementById('trip-info-card');
    if (sheetDragHandle && tripInfoCard) {
        sheetDragHandle.addEventListener('click', () => {
            tripInfoCard.classList.toggle('collapsed');
        });
    }

    // Visual Viewport Adaptation for Tablet Soft Keyboard
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', () => {
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages && document.activeElement && (document.activeElement.id === 'chat-input' || document.activeElement.id === 'map-chat-input')) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        });
    }

    // Lightbox Touch Swipe Gestures
    const photoLightbox = document.getElementById('photo-lightbox');
    if (photoLightbox) {
        let touchStartX = 0;
        let touchStartY = 0;
        photoLightbox.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) {
                touchStartX = e.touches[0].clientX;
                touchStartY = e.touches[0].clientY;
            }
        }, { passive: true });

        photoLightbox.addEventListener('touchend', (e) => {
            if (e.changedTouches.length === 1) {
                const diffX = e.changedTouches[0].clientX - touchStartX;
                const diffY = e.changedTouches[0].clientY - touchStartY;
                if (Math.abs(diffX) > 50 && Math.abs(diffX) > Math.abs(diffY)) {
                    if (diffX < 0) {
                        const nextBtn = document.getElementById('lightbox-next');
                        if (nextBtn) nextBtn.click();
                    } else {
                        const prevBtn = document.getElementById('lightbox-prev');
                        if (prevBtn) prevBtn.click();
                    }
                } else if (diffY > 80 && Math.abs(diffY) > Math.abs(diffX)) {
                    const closeBtn = document.getElementById('lightbox-close');
                    if (closeBtn) closeBtn.click();
                }
            }
        }, { passive: true });
    }


    async function checkAuth() {
        try {
            const response = await fetch(`${API_BASE}/api/me`);
            const result = await response.json();
            if (result.status === 'success' && result.user) {
                authModal.style.display = 'none';
                document.getElementById('user-profile').style.display = 'flex';
                const displayName = result.user.display_name || '';
                document.getElementById('user-display-name').textContent = displayName ? displayName.charAt(0).toUpperCase() : 'U';
                initWelcomeAndTutorial(displayName);
                // Załaduj galerię Memories (aktualizuje badge na przycisku)
                loadMemoriesGallery();
            } else { 
                authModal.style.display = 'flex';
                const welcomeOverlay = document.getElementById('welcome-overlay');
                if (welcomeOverlay) welcomeOverlay.style.display = 'none';
            }
        } catch (error) { 
            authModal.style.display = 'flex';
            const welcomeOverlay = document.getElementById('welcome-overlay');
            if (welcomeOverlay) welcomeOverlay.style.display = 'none';
        }
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

    // ── User Profile & Preferences Modal ───────────────────────
    const profileModal = document.getElementById('profile-modal');
    const navUserBtn = document.getElementById('nav-user-btn');
    const profileCloseBtn = document.getElementById('profile-close-btn');
    const btnSavePref = document.getElementById('btn-save-preferences');
    const btnUserLogout = document.getElementById('btn-user-logout');

    async function loadPreferences() {
        try {
            const res = await fetch(`${API_BASE}/api/preferences`);
            const data = await res.json();
            if (data.status === 'success' && data.preferences) {
                const prefs = data.preferences;
                if (prefs.vehicle_model) document.getElementById('pref-vehicle').value = prefs.vehicle_model;
                if (prefs.max_daily_drive_hours) document.getElementById('pref-drive-hours').value = prefs.max_daily_drive_hours;
                if (prefs.hookup_type) document.getElementById('pref-hookup').value = prefs.hookup_type;
                if (prefs.budget_per_night_eur) document.getElementById('pref-budget').value = prefs.budget_per_night_eur;

                const amenities = prefs.preferred_amenities || [];
                document.querySelectorAll('[id^="pref-amenity-"]').forEach(cb => {
                    cb.checked = amenities.includes(cb.value);
                });
            }
        } catch (e) {
            console.error('Failed to load preferences:', e);
        }
    }

    if (navUserBtn) {
        navUserBtn.addEventListener('click', () => {
            if (profileModal) profileModal.style.display = 'flex';
            loadPreferences();
        });
    }

    if (profileCloseBtn) {
        profileCloseBtn.addEventListener('click', () => {
            if (profileModal) profileModal.style.display = 'none';
        });
    }

    if (btnSavePref) {
        btnSavePref.addEventListener('click', async () => {
            const vehicle_model = document.getElementById('pref-vehicle').value;
            const max_daily_drive_hours = parseFloat(document.getElementById('pref-drive-hours').value) || 6;
            const hookup_type = document.getElementById('pref-hookup').value;
            const budget_per_night_eur = parseFloat(document.getElementById('pref-budget').value) || null;

            const preferred_amenities = [];
            document.querySelectorAll('[id^="pref-amenity-"]:checked').forEach(cb => {
                preferred_amenities.push(cb.value);
            });

            btnSavePref.textContent = "Zapisywanie...";
            try {
                const res = await fetch(`${API_BASE}/api/preferences`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        vehicle_model,
                        max_daily_drive_hours,
                        hookup_type,
                        budget_per_night_eur,
                        preferred_amenities
                    })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    if (profileModal) profileModal.style.display = 'none';
                }
            } catch (e) {
                console.error('Failed to save preferences:', e);
            }
            btnSavePref.textContent = "Zapisz preferencje";
        });
    }

    if (btnUserLogout) {
        btnUserLogout.addEventListener('click', async () => {
            try {
                await fetch(`${API_BASE}/api/logout`, { method: 'POST' });
            } catch (e) { console.error(e); }
            hasWelcomeRun = false;
            if (profileModal) profileModal.style.display = 'none';
            document.getElementById('user-profile').style.display = 'none';
            const authModal = document.getElementById('auth-modal');
            if (authModal) authModal.style.display = 'flex';
        });
    }

    const btnRestartTutorial = document.getElementById('btn-restart-tutorial');
    if (btnRestartTutorial) {
        btnRestartTutorial.addEventListener('click', () => {
            if (profileModal) profileModal.style.display = 'none';
            localStorage.removeItem('vw_tut_main_seen');
            localStorage.removeItem('vw_tut_map_seen');
            localStorage.removeItem('vw_tut_memory_seen');
            localStorage.removeItem('vw_tut_trips_seen');
            hasWelcomeRun = false;
            if (window.startTutorialSuite && window.TUTORIAL_STEPS) {
                window.startTutorialSuite(window.TUTORIAL_STEPS, 'vw_tut_main_seen', true);
            }
        });
    }

    if (profileModal) {
        profileModal.addEventListener('click', (e) => {
            if (e.target === profileModal) {
                profileModal.style.display = 'none';
            }
        });
    }

    // ── Saved Trips Drawer / Modal ───────────────────────────────
    const tripsDrawer = document.getElementById('trips-drawer');
    const navTripsBtn = document.getElementById('nav-trips-btn');
    const tripsCloseBtn = document.getElementById('trips-close-btn');
    const tripsList = document.getElementById('trips-list');

    async function loadSavedTrips() {
        if (!tripsList) return;
        tripsList.innerHTML = '<div style="text-align:center; padding:20px; color:var(--vw-text-muted);">Wczytywanie wyjazdów...</div>';
        try {
            const res = await fetch(`${API_BASE}/api/trips`);
            const data = await res.json();
            if (data.status === 'success' && Array.isArray(data.trips)) {
                if (data.trips.length === 0) {
                    tripsList.innerHTML = '<div style="text-align:center; padding:20px; color:var(--vw-text-muted);">Brak zapisanych wyjazdów. Zaplanuj swój pierwszy wyjazd w czacie!</div>';
                    return;
                }
                tripsList.innerHTML = '';
                data.trips.forEach(trip => {
                    const item = document.createElement('div');
                    item.className = 'trip-card-item';
                    const statusClass = trip.status === 'active' ? 'active' : 'planned';
                    const statusLabel = trip.status === 'active' ? 'W trakcie' : (trip.status === 'completed' ? 'Zakończony' : 'Zaplanowany');

                    const infoDiv = document.createElement('div');
                    const title = document.createElement('h4');
                    title.textContent = trip.title || 'Wyjazd';
                    const dates = document.createElement('p');
                    dates.textContent = `${trip.start_date || ''} — ${trip.end_date || ''}`;
                    infoDiv.appendChild(title);
                    infoDiv.appendChild(dates);

                    const badge = document.createElement('span');
                    badge.className = `trip-card-badge ${statusClass}`;
                    badge.textContent = statusLabel;

                    item.appendChild(infoDiv);
                    item.appendChild(badge);

                    item.addEventListener('click', async () => {
                        if (tripsDrawer) tripsDrawer.style.display = 'none';
                        try {
                            const tripRes = await fetch(`${API_BASE}/api/trip/${trip.id}`);
                            const tripData = await tripRes.json();
                            if (tripData.status === 'success' && tripData.trip_data) {
                                state.currentTrip = tripData.trip_data;
                                switchView('map');
                                if (window.displayTripOnMap) {
                                    displayTripOnMap(tripData.trip_data);
                                }
                            }
                        } catch (err) {
                            console.error('Failed to load trip details:', err);
                        }
                    });
                    tripsList.appendChild(item);
                });
            } else {
                tripsList.innerHTML = `<div style="text-align:center; padding:20px; color:var(--vw-text-muted);">${data.message || 'Nie udało się pobrać wyjazdów.'}</div>`;
            }
        } catch (e) {
            console.error('Failed to load trips:', e);
            tripsList.innerHTML = '<div style="text-align:center; padding:20px; color:var(--vw-text-muted);">Błąd podczas wczytywania wyjazdów.</div>';
        }
    }

    if (navTripsBtn) {
        navTripsBtn.addEventListener('click', () => {
            if (tripsDrawer) tripsDrawer.style.display = 'flex';
            loadSavedTrips();
            setTimeout(() => {
                if (window.TRIPS_TUTORIAL_STEPS && window.startTutorialSuite) {
                    window.startTutorialSuite(window.TRIPS_TUTORIAL_STEPS, 'vw_tut_trips_seen');
                }
            }, 600);
        });
    }

    if (tripsCloseBtn) {
        tripsCloseBtn.addEventListener('click', () => {
            if (tripsDrawer) tripsDrawer.style.display = 'none';
        });
    }

    if (tripsDrawer) {
        tripsDrawer.addEventListener('click', (e) => {
            if (e.target === tripsDrawer) {
                tripsDrawer.style.display = 'none';
            }
        });
    }

    const campingModal = document.getElementById('camping-selection-modal');
    const campingModalClose = document.getElementById('camping-modal-close');
    const campingModalDone = document.getElementById('btn-camping-modal-done');

    if (campingModalClose) {
        campingModalClose.addEventListener('click', () => {
            if (campingModal) campingModal.style.display = 'none';
        });
    }
    if (campingModalDone) {
        campingModalDone.addEventListener('click', () => {
            if (campingModal) campingModal.style.display = 'none';
        });
    }
    if (campingModal) {
        campingModal.addEventListener('click', (e) => {
            if (e.target === campingModal) {
                campingModal.style.display = 'none';
            }
        });
    }

    checkAuth();
});

// ── Camping Selection Modal Functions ─────────────────────────
function openCampingSelectionModal(tripData, targetDayInput = 1) {
    const modal = document.getElementById('camping-selection-modal');
    if (!modal) return;
    const currentData = tripData || state.currentTrip;
    if (!currentData || !currentData.daily_schedules || currentData.daily_schedules.length === 0) return;

    const schedules = currentData.daily_schedules;

    let safeIndex = 0;
    if (typeof targetDayInput === 'number') {
        const matchIdx = schedules.findIndex(d => d.day_number === targetDayInput);
        if (matchIdx !== -1) {
            safeIndex = matchIdx;
        } else if (targetDayInput >= 0 && targetDayInput < schedules.length) {
            safeIndex = targetDayInput;
        }
    }

    modal.style.display = 'flex';
    renderCampingDayTabs(currentData, safeIndex);
    renderCampingOptionsForDay(currentData, safeIndex);
}
window.openCampingSelectionModal = openCampingSelectionModal;

function renderCampingDayTabs(tripData, activeIndex) {
    const tabsContainer = document.getElementById('camping-day-tabs');
    if (!tabsContainer) return;
    tabsContainer.innerHTML = '';

    const currentData = tripData || state.currentTrip;
    if (!currentData || !currentData.daily_schedules) return;

    const schedules = currentData.daily_schedules;
    let activeTabEl = null;

    schedules.forEach((daySchedule, idx) => {
        const tabBtn = document.createElement('button');
        tabBtn.className = `camping-day-tab ${idx === activeIndex ? 'active' : ''}`;
        const dayLabel = window.t ? window.t('day_card_day', { day: daySchedule.day_number }) : `Dzień ${daySchedule.day_number}`;
        const hasSelected = !!daySchedule.overnight_camping;
        tabBtn.innerHTML = `<span>${dayLabel}</span>${hasSelected ? ' <span style="font-size:0.75rem; opacity:0.85;">✓</span>' : ''}`;
        
        if (idx === activeIndex) {
            activeTabEl = tabBtn;
        }

        tabBtn.addEventListener('click', () => {
            renderCampingDayTabs(currentData, idx);
            renderCampingOptionsForDay(currentData, idx);
        });
        tabsContainer.appendChild(tabBtn);
    });

    if (activeTabEl) {
        setTimeout(() => {
            activeTabEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }, 60);
    }
}

async function renderCampingOptionsForDay(tripData, dayIndex) {
    const grid = document.getElementById('camping-cards-grid');
    const titleEl = document.getElementById('camping-modal-title');
    const badgeEl = document.getElementById('camping-modal-day-badge');
    if (!grid) return;
    grid.innerHTML = '';

    const currentData = tripData || state.currentTrip;
    if (!currentData || !currentData.daily_schedules || !currentData.daily_schedules[dayIndex]) return;

    const totalDays = currentData.daily_schedules.length;
    const daySchedule = currentData.daily_schedules[dayIndex];

    if (badgeEl) {
        badgeEl.textContent = `Dzień ${daySchedule.day_number} z ${totalDays}`;
    }
    if (titleEl) {
        titleEl.textContent = window.t ? window.t('camping_modal_title', { day: daySchedule.day_number }) : `🏕️ Wybierz Nocleg dla Dnia ${daySchedule.day_number}`;
    }

    let options = daySchedule.overnight_options || [];

    // Fallback: search campings on the fly if overnight_options is empty
    if (options.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: #718096; font-size: 0.95rem;">Wyszukiwanie kempingów dla Dnia ${daySchedule.day_number}...</div>`;
        const lastWp = (daySchedule.waypoints && daySchedule.waypoints.length > 0) ? daySchedule.waypoints[daySchedule.waypoints.length - 1] : null;
        if (lastWp && lastWp.lat && lastWp.lng) {
            const searchRes = await apiCall('search_campings', { lat: lastWp.lat, lng: lastWp.lng, radius_km: 40, limit: 3 });
            if (searchRes.status === 'success' && searchRes.results && searchRes.results.length > 0) {
                options = searchRes.results;
                daySchedule.overnight_options = options;
            }
        }
    }

    grid.innerHTML = '';

    if (options.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: #718096; font-size: 0.95rem;">Brak zarejestrowanych kempingów w bezpośrednim sąsiedztwie tego przystanku.</div>`;
        return;
    }

    const currentSelected = daySchedule.overnight_camping;

    options.forEach((camp, cIdx) => {
        const isSelected = currentSelected && (
            (currentSelected.place_id && currentSelected.place_id === camp.place_id) ||
            (currentSelected.name && currentSelected.name === camp.name) ||
            (currentSelected.label && currentSelected.label === camp.name) ||
            (cIdx === 0 && !currentSelected)
        );

        const card = document.createElement('div');
        card.className = `camping-proposal-card ${isSelected ? 'selected' : ''}`;

        let photoHtml = '';
        const photoUrl = (camp.photos && camp.photos.length > 0) ? camp.photos[0] : (camp.photo_url || null);
        if (photoUrl) {
            photoHtml = `
                <div class="camping-card-img-wrap" style="width:100%; height:140px; border-radius:8px; overflow:hidden; margin-bottom:8px; background:#F0F3F7;">
                    <img src="${photoUrl}" alt="${camp.name}" style="width:100%; height:100%; object-fit:cover;" onerror="this.parentElement.style.display='none'">
                </div>
            `;
        }

        // Build badges
        let badgesHtml = '<div class="camping-card-badges">';
        if (camp.shore_power_hookup || camp.has_power || (camp.amenities && camp.amenities.includes('power'))) {
            badgesHtml += '<span class="camping-badge cee-badge" style="background:#E3F2FD; color:#1565C0; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔌 Prąd CEE</span>';
        }
        if (camp.has_showers || (camp.amenities && camp.amenities.includes('showers'))) {
            badgesHtml += '<span class="camping-badge shower-badge" style="background:#E8F5E9; color:#2E7D32; padding:3px 8px; border-radius:4px; font-size:11px;">🚿 Prysznic</span>';
        }
        if (camp.has_water || (camp.amenities && camp.amenities.includes('water'))) {
            badgesHtml += '<span class="camping-badge water-badge" style="background:#E0F7FA; color:#006064; padding:3px 8px; border-radius:4px; font-size:11px;">🚰 Woda</span>';
        }
        if (camp.has_wifi || (camp.amenities && camp.amenities.includes('wifi'))) {
            badgesHtml += '<span class="camping-badge wifi-badge" style="background:#F3E5F5; color:#4A148C; padding:3px 8px; border-radius:4px; font-size:11px;">📶 WiFi</span>';
        }
        badgesHtml += '</div>';

        const selectedBadgeText = window.t ? window.t('camping_selected_badge') : '✓ Wybrany';
        const selectBtnText = window.t ? window.t('camping_select_btn') : 'Wybierz ten kemping';
        const badgeTop = isSelected ? `<div class="camping-card-badge-top">${selectedBadgeText}</div>` : '';
        const btnDisplay = isSelected ? selectedBadgeText : selectBtnText;

        card.innerHTML = `
            ${badgeTop}
            ${photoHtml}
            <div class="camping-card-header">
                <h4>${camp.name}</h4>
                ${camp.address ? `<div style="font-size:0.8rem; color:#718096; margin-bottom:4px;">📍 ${camp.address}</div>` : ''}
                <div class="camping-card-meta">
                    ${camp.rating ? `<span class="camping-card-rating">⭐ ${camp.rating} ${camp.review_count ? `(${camp.review_count})` : ''}</span>` : ''}
                    ${camp.cost_per_night_eur ? `<span class="camping-card-cost">€${camp.cost_per_night_eur}/noc</span>` : ''}
                </div>
                ${badgesHtml}
            </div>
            <div class="camping-card-action">
                <button class="btn-select-camping" ${isSelected ? 'disabled' : ''}>${btnDisplay}</button>
            </div>
        `;

        const btn = card.querySelector('.btn-select-camping');
        if (btn && !isSelected) {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                btn.disabled = true;
                btn.textContent = 'Zapisywanie...';
                
                const res = await apiCall('select_camping', {
                    trip_id: tripData.trip.id,
                    day_number: daySchedule.day_number,
                    camping: camp
                });

                if (res.status === 'success' && res.trip_data) {
                    state.currentTrip = res.trip_data;
                    displayTripOnMap(res.trip_data);
                    renderCampingDayTabs(res.trip_data, dayIndex);
                    renderCampingOptionsForDay(res.trip_data, dayIndex);
                } else {
                    btn.disabled = false;
                    btn.textContent = selectBtnText;
                    alert(res.message || 'Nie udało się wybrać kempingu.');
                }
            });
        }

        grid.appendChild(card);
    });

    renderDayAttractionsForModal(currentData, daySchedule.day_number);
}

async function renderDayAttractionsForModal(tripData, dayNumber) {
    const titleEl = document.getElementById('day-attractions-modal-title');
    const grid = document.getElementById('day-attractions-modal-grid');
    if (!grid) return;

    if (titleEl) {
        titleEl.textContent = `⭐ Atrakcje przy trasie na Dzień ${dayNumber}:`;
    }

    grid.innerHTML = '<div style="grid-column: 1/-1; padding: 12px; text-align: center; color: #718096; font-size: 0.88rem;">Wczytywanie atrakcji...</div>';

    let allAttrs = state.rawAttractionsList || [];

    // If attractions list is empty, attempt to fetch attractions for active trip
    const currentTripObj = tripData || state.currentTrip;
    const tripId = currentTripObj && currentTripObj.trip && currentTripObj.trip.id;

    if (allAttrs.length === 0 && tripId) {
        try {
            const res = await fetch(`${API_BASE}/api/attractions/${tripId}?limit_per_day=5&sample_every_km=80`);
            const data = await res.json();
            if (data.status === 'success' && data.attractions_by_day) {
                const fetchedAttrs = [];
                Object.entries(data.attractions_by_day).forEach(([dNum, attractions]) => {
                    attractions.forEach(attr => {
                        fetchedAttrs.push({ ...attr, day_number: parseInt(dNum) });
                    });
                });
                state.rawAttractionsList = fetchedAttrs;
                allAttrs = fetchedAttrs;
            }
        } catch (e) {
            console.error('Failed to fetch attractions for modal:', e);
        }
    }

    grid.innerHTML = '';

    const dayAttrs = allAttrs.filter(a => a.day_number === dayNumber);

    if (dayAttrs.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; padding: 12px; text-align: center; color: #718096; font-size: 0.88rem;">Brak wykrytych dodatkowych atrakcji dla tego odcinka trasy.</div>`;
        return;
    }

    dayAttrs.forEach(attr => {
        const card = document.createElement('div');
        card.className = 'top-attraction-item-card';
        card.style.background = '#F8FAFC';
        card.style.border = '1px solid #E2E8F0';
        card.style.padding = '10px';
        card.style.borderRadius = '10px';

        const photoHtml = attr.photo_url
            ? `<div class="top-attraction-img-wrap" style="height:100px; border-radius:6px; overflow:hidden; margin-bottom:6px;"><img src="${attr.photo_url}" alt="${attr.name}" style="width:100%; height:100%; object-fit:cover;" onerror="this.parentElement.style.display='none';"></div>`
            : '';

        const ratingHtml = attr.rating ? `<span style="color:#D69E2E; font-weight:700; font-size:0.82rem;">⭐ ${attr.rating}</span>` : '';
        const categoryBadge = `<span style="background:${attr.color || '#F9A825'}20; color:${attr.color || '#F9A825'}; border:1px solid ${attr.color || '#F9A825'}60; border-radius:12px; padding:1px 6px; font-size:10px; font-weight:700;">${attr.emoji || '⭐'} ${attr.category_label || 'Atrakcja'}</span>`;

        const isAdded = isAttractionInRoute(attr, dayNumber);
        const addBtnText = isAdded ? (window.t ? window.t('added_to_route_btn') : '✓ Dodano do drogi') : (window.t ? window.t('add_to_route_btn') : '➕ Dodaj do drogi');
        const attrKey = attr.place_id || (attr.name + '_' + attr.lat + '_' + attr.lng);
        window._attractionsCache = window._attractionsCache || {};
        window._attractionsCache[attrKey] = attr;

        card.innerHTML = `
            ${photoHtml}
            <div class="top-attraction-info">
                <div style="margin-bottom:4px;">${categoryBadge}</div>
                <h5 style="margin:0 0 4px 0; color:#001E50; font-size:0.92rem; font-weight:700; line-height:1.2;">${attr.name}</h5>
                <div class="top-attraction-meta" style="font-size:0.78rem;">
                    ${ratingHtml}
                    ${attr.address ? `<div style="margin-top:2px; color:#666; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">📍 ${attr.address}</div>` : ''}
                </div>
            </div>
            <div style="margin-top:8px; display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn-add-attraction-route ${isAdded ? 'added' : ''}" data-attr-key="${attrKey}" ${isAdded ? 'disabled' : ''} onclick="window.addAttractionToRouteFromCache('${attrKey}')" style="width:100%; font-size:0.8rem; padding:6px 10px;">
                    ${addBtnText}
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}
window.renderDayAttractionsForModal = renderDayAttractionsForModal;

function openCampingSearchModal(campingsList, locationTitle = 'Rekomendowane kempingi') {
    const modal = document.getElementById('camping-selection-modal');
    const grid = document.getElementById('camping-cards-grid');
    const titleEl = document.getElementById('camping-modal-title');
    const badgeEl = document.getElementById('camping-modal-day-badge');
    const tabsContainer = document.getElementById('camping-day-tabs');
    if (!modal || !grid) return;

    if (tabsContainer) tabsContainer.innerHTML = '';
    if (badgeEl) badgeEl.textContent = 'Szukaj noclegu';
    if (titleEl) titleEl.textContent = `🏕️ ${locationTitle}`;

    grid.innerHTML = '';
    modal.style.display = 'flex';

    if (!campingsList || campingsList.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: #718096;">Brak kempingów spełniających wybrane kryteria w tym obszarze.</div>`;
        return;
    }

    campingsList.forEach((camp) => {
        const card = document.createElement('div');
        card.className = 'camping-proposal-card';

        let photoHtml = '';
        const photoUrl = (camp.photos && camp.photos.length > 0) ? camp.photos[0] : (camp.photo_url || null);
        if (photoUrl) {
            photoHtml = `
                <div class="camping-card-img-wrap" style="width:100%; height:140px; border-radius:8px; overflow:hidden; margin-bottom:8px; background:#F0F3F7;">
                    <img src="${photoUrl}" alt="${camp.name}" style="width:100%; height:100%; object-fit:cover;" onerror="this.parentElement.style.display='none'">
                </div>
            `;
        }

        let badgesHtml = '<div class="camping-card-badges">';
        if (camp.shore_power_hookup || camp.has_power || (camp.amenities && camp.amenities.includes('power'))) {
            badgesHtml += '<span class="camping-badge cee-badge" style="background:#E3F2FD; color:#1565C0; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">🔌 Prąd CEE</span>';
        }
        if (camp.has_showers || (camp.amenities && camp.amenities.includes('showers'))) {
            badgesHtml += '<span class="camping-badge shower-badge" style="background:#E8F5E9; color:#2E7D32; padding:3px 8px; border-radius:4px; font-size:11px;">🚿 Prysznic</span>';
        }
        if (camp.has_water || (camp.amenities && camp.amenities.includes('water'))) {
            badgesHtml += '<span class="camping-badge water-badge" style="background:#E0F7FA; color:#006064; padding:3px 8px; border-radius:4px; font-size:11px;">🚰 Woda</span>';
        }
        if (camp.has_wifi || (camp.amenities && camp.amenities.includes('wifi'))) {
            badgesHtml += '<span class="camping-badge wifi-badge" style="background:#F3E5F5; color:#4A148C; padding:3px 8px; border-radius:4px; font-size:11px;">📶 WiFi</span>';
        }
        badgesHtml += '</div>';

        card.innerHTML = `
            ${photoHtml}
            <div class="camping-card-header">
                <h4>${camp.name}</h4>
                ${camp.address ? `<div style="font-size:0.8rem; color:#718096; margin-bottom:4px;">📍 ${camp.address}</div>` : ''}
                <div class="camping-card-meta">
                    ${camp.rating ? `<span class="camping-card-rating">⭐ ${camp.rating} ${camp.review_count ? `(${camp.review_count})` : ''}</span>` : ''}
                    ${camp.cost_per_night_eur ? `<span class="camping-card-cost">€${camp.cost_per_night_eur}/noc</span>` : ''}
                </div>
                ${badgesHtml}
            </div>
            <div class="camping-card-action">
                <button class="btn-select-camping">Zatwierdź ten kemping</button>
            </div>
        `;

        const btn = card.querySelector('.btn-select-camping');
        btn.addEventListener('click', () => {
            btn.textContent = '✓ Wybrano kemping';
            btn.style.background = '#00875A';
            btn.disabled = true;
            card.classList.add('selected');

            if (state.mapInitialized && camp.lat && camp.lng) {
                addMarker(camp.lat, camp.lng, camp.name, null, '🏕️');
                state.map.panTo({ lat: camp.lat, lng: camp.lng });
            }
            setTimeout(() => {
                modal.style.display = 'none';
            }, 800);
        });

        grid.appendChild(card);
    });
}
window.openCampingSearchModal = openCampingSearchModal;
