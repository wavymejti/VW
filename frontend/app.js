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
    dayMarkers: [],              // Day stage endpoint markers (D1, D2, D3...)
    currentTrip: null,           // Current trip data
    chatHistory: [],             // Chat messages
    isTyping: false,             // AI typing state
    locationEnabled: localStorage.getItem('vw_location_enabled') !== 'false', // Geolocation enabled by default
    userLocation: null,          // { lat, lng, name, city, country, address }
    locationLoading: false,      // Geolocation query in progress
    campingMarkers: [],          // Camping location markers
    attractionMarkers: [],       // POI attraction markers (separate layer)
    attractionsVisible: true,    // Whether the attractions layer is shown
    top5Attractions: [],         // Current Top 8 POIs on route
    allSortedAttractions: [],    // Full sorted list of all POIs on route
    rawAttractionsList: [],      // Raw unsorted list of POIs
    topSortMode: 'reviews',      // Sort mode: 'reviews' (most reviewed, default), 'rating' (highest rated), or 'day'
    top5Offset: 0,               // Current pagination offset for Top 8 modal (0, 8, 16, ...)
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

// A new chat on every page load: the server keeps a separate session per id,
// so a reload starts from scratch (no old history, no active trip).
const CHAT_CONVERSATION_ID = (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const CAMPING_PLACEHOLDER_URL = '/static/assets/camping_placeholder.svg';
const ATTRACTION_PLACEHOLDER_URL = '/static/assets/attraction_placeholder.svg';
window.CAMPING_PLACEHOLDER_URL = CAMPING_PLACEHOLDER_URL;
window.ATTRACTION_PLACEHOLDER_URL = ATTRACTION_PLACEHOLDER_URL;

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
        if (state.currentTrip && state.currentTrip.photos) {
            renderTravelMemoryGrid(state.currentTrip.photos);
        }
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
    
    const btnCampings = document.getElementById('btn-toggle-campings');
    if (btnCampings) {
        btnCampings.addEventListener('click', loadCampingsOnMap);
    }

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
            state.top5Offset = Math.max(0, (state.top5Offset || 0) - 8);
            renderTopAttractionsModalPage();
        });
    }

    const btnNext = document.getElementById('btn-top-next');
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            const total = (state.allSortedAttractions || []).length;
            if ((state.top5Offset || 0) + 8 < total) {
                state.top5Offset = (state.top5Offset || 0) + 8;
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
    if (state.dayMarkers) {
        state.dayMarkers.forEach(m => m.setMap(null));
        state.dayMarkers = [];
    }
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
    if (displayPhotoUrl && /\.(heic|heif)$/i.test(displayPhotoUrl)) {
        displayPhotoUrl = displayPhotoUrl.replace(/\.(heic|heif)$/i, '_converted.jpg');
    }

    function buildInfoWindowHtml(imgUrl, ratingVal, addressVal) {
        const isCamp = (label === '🏕️' || (title && title.toLowerCase().includes('camp')));
        const fallbackUrl = isCamp ? CAMPING_PLACEHOLDER_URL : ATTRACTION_PLACEHOLDER_URL;
        const photoSrc = imgUrl || fallbackUrl;
        const hasReal = Boolean(imgUrl);
        const previewBadge = !hasReal ? `<span class="photo-placeholder-badge" style="font-size:0.62rem; padding:1px 5px; bottom:4px; right:4px;">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : '';
        const imgHtml = `
            <div style="position:relative; width:210px; height:130px; margin:0 auto 6px auto; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.15);">
                <img src="${photoSrc}" alt="${title}" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.onerror=null; this.src='${fallbackUrl}';">
                ${previewBadge}
            </div>
        `;
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
        if (placeId && !String(placeId).startsWith('p4n:') && !displayPhotoUrl) {
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

function _createDayMarker(dayNum, lat, lng, isReturn, labelText) {
    if (!state.map || !window.google || !window.google.maps || !google.maps.Marker) return null;

    const bgColor = isReturn ? '#E65100' : '#001E50';
    const svgPin = `
        <svg xmlns="http://www.w3.org/2000/svg" width="34" height="42" viewBox="0 0 34 42">
            <defs>
                <filter id="shadow_${dayNum}" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity="0.35"/>
                </filter>
            </defs>
            <path d="M17 0 C7.6 0 0 7.6 0 17 C0 29.5 17 42 17 42 C17 42 34 29.5 34 17 C34 7.6 26.4 0 17 0 Z"
                  fill="${bgColor}" filter="url(#shadow_${dayNum})" stroke="#FFFFFF" stroke-width="1.5"/>
            <circle cx="17" cy="16" r="11" fill="#FFFFFF"/>
            <text x="17" y="20.5" text-anchor="middle" font-size="11" font-weight="bold" fill="${bgColor}" font-family="Arial, sans-serif">D${dayNum}</text>
        </svg>`;

    const iconDataUrl = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svgPin);

    const marker = new google.maps.Marker({
        position: { lat, lng },
        map: state.map,
        title: `Koniec Dnia ${dayNum}: ${labelText || ''}`,
        icon: {
            url: iconDataUrl,
            scaledSize: new google.maps.Size(34, 42),
            anchor: new google.maps.Point(17, 42),
        },
        zIndex: 50 + dayNum,
    });

    marker.dayNumber = dayNum;

    const infoContent = `
        <div style="font-family:Arial,sans-serif; padding:6px; max-width:210px; text-align:center;">
            <div style="font-size:0.75rem; font-weight:700; color:${bgColor}; text-transform:uppercase; letter-spacing:0.5px;">🏁 Koniec Dnia ${dayNum}</div>
            <strong style="color:#001E50; font-size:0.9rem; display:block; margin-top:4px;">${labelText || `Etap Dnia ${dayNum}`}</strong>
        </div>
    `;

    const infoWindow = new google.maps.InfoWindow({ content: infoContent });
    marker.addListener('click', () => {
        if (state.activeInfoWindow) state.activeInfoWindow.close();
        infoWindow.open(state.map, marker);
        state.activeInfoWindow = infoWindow;
        highlightDayRoute(dayNum);

        const currentSchedules = state.currentTrip?.daily_schedules;
        if (currentSchedules) {
            const dayObj = currentSchedules.find(d => d.day_number === dayNum);
            if (dayObj) fitMapToDayRoute(dayObj);
        }

        const card = document.querySelector(`.day-card[data-day-number="${dayNum}"]`);
        if (card) {
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    });

    return marker;
}

function highlightDayRoute(dayNumber) {
    if (!state.routePolylines || state.routePolylines.length === 0) return;

    state.routePolylines.forEach(p => {
        const isMatch = (p.dayNumber === dayNumber);
        if (dayNumber === null || dayNumber === undefined) {
            p.setOptions({
                strokeWeight: 5,
                strokeOpacity: 0.85,
                zIndex: p.isReturn ? 2 : 1
            });
        } else if (isMatch) {
            p.setOptions({
                strokeWeight: 9,
                strokeOpacity: 1.0,
                zIndex: 100
            });
        } else {
            p.setOptions({
                strokeWeight: 4,
                strokeOpacity: 0.3,
                zIndex: 1
            });
        }
    });

    if (state.dayMarkers && state.dayMarkers.length > 0) {
        state.dayMarkers.forEach(m => {
            if (m.dayNumber === dayNumber) {
                m.setZIndex(200);
                if (m.setAnimation) {
                    m.setAnimation(google.maps.Animation.BOUNCE);
                    setTimeout(() => { if (m.setAnimation) m.setAnimation(null); }, 750);
                }
            } else {
                m.setZIndex(50 + (m.dayNumber || 0));
            }
        });
    }
}
window.highlightDayRoute = highlightDayRoute;

function getMapFitPadding(customPadding = {}) {
    let bottomPadding = 320;
    const bottomCard = document.getElementById('trip-info-card');
    if (bottomCard && bottomCard.classList.contains('visible') && !bottomCard.classList.contains('collapsed')) {
        const rect = bottomCard.getBoundingClientRect();
        if (rect && rect.height > 0) {
            bottomPadding = Math.max(Math.round(rect.height) + 40, 300);
        }
    }
    return {
        top: customPadding.top || 100,
        right: customPadding.right || 80,
        bottom: customPadding.bottom || bottomPadding,
        left: customPadding.left || 80
    };
}

function fitMapToTrip() {
    if (!state.currentTrip || !state.map) return;
    const bounds = new google.maps.LatLngBounds();

    if (state.markers && state.markers.length > 0) {
        state.markers.forEach(m => {
            if (m && typeof m.getPosition === 'function' && m.getPosition()) {
                bounds.extend(m.getPosition());
            }
        });
    }

    if (state.routePolylines && state.routePolylines.length > 0) {
        state.routePolylines.forEach(p => {
            if (p && typeof p.getPath === 'function' && p.getPath()) {
                p.getPath().forEach(pt => bounds.extend(pt));
            }
        });
    }

    if (!bounds.isEmpty()) {
        state.map.fitBounds(bounds, getMapFitPadding());
    }
}

function fitMapToDayRoute(day) {
    if (!state.map || !day) return;
    const bounds = new google.maps.LatLngBounds();

    if (day.waypoints && day.waypoints.length > 0) {
        day.waypoints.forEach(wp => {
            if (typeof wp.lat === 'number' && typeof wp.lng === 'number') {
                bounds.extend({ lat: wp.lat, lng: wp.lng });
            }
        });
    }

    const polyline = (state.routePolylines || []).find(p => p.dayNumber === day.day_number);
    if (polyline && typeof polyline.getPath === 'function' && polyline.getPath()) {
        polyline.getPath().forEach(pt => bounds.extend(pt));
    }

    if (!bounds.isEmpty()) {
        const ne = bounds.getNorthEast(), sw = bounds.getSouthWest();
        if (ne.equals(sw)) {
            // Stay / rest day: one point, so zoom to the campsite area instead of street level
            state.map.setCenter(ne);
            state.map.setZoom(12);
        } else {
            state.map.fitBounds(bounds, getMapFitPadding({ top: 90 }));
        }
    }
}
window.fitMapToDayRoute = fitMapToDayRoute;

function drawDailyRoutes(daily_schedules, color = '#001E50', returnColor = '#E65100') {
    if (!state.map) return;
    state.routePolylines.forEach(p => p.setMap(null));
    state.routePolylines = [];
    if (state.dayMarkers) {
        state.dayMarkers.forEach(m => m.setMap(null));
        state.dayMarkers = [];
    } else {
        state.dayMarkers = [];
    }

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
            zIndex: isReturn ? 2 : 1
        });

        polyline.isReturn = isReturn;
        polyline.dayNumber = day.day_number || (idx + 1);

        polyline.addListener('mouseover', () => {
            highlightDayRoute(polyline.dayNumber);
        });
        polyline.addListener('mouseout', () => {
            const activeCard = document.querySelector('.day-card.active');
            if (activeCard && activeCard.dataset.dayNumber) {
                highlightDayRoute(parseInt(activeCard.dataset.dayNumber, 10));
            } else {
                highlightDayRoute(null);
            }
        });
        polyline.addListener('click', () => {
            const card = document.querySelector(`.day-card[data-day-number="${polyline.dayNumber}"]`);
            if (card) card.click();
        });

        state.routePolylines.push(polyline);

        // Add Day Stage End Marker (D1, D2, D3...)
        const endPt = path[path.length - 1];
        if (endPt) {
            const endLat = typeof endPt.lat === 'function' ? endPt.lat() : endPt.lat;
            const endLng = typeof endPt.lng === 'function' ? endPt.lng() : endPt.lng;

            if (typeof endLat === 'number' && typeof endLng === 'number') {
                const labelText = day.overnight_camping
                    ? (day.overnight_camping.name || day.overnight_camping.label)
                    : (day.waypoints && day.waypoints.length > 0 ? day.waypoints[day.waypoints.length - 1].label : `Meta Dnia ${day.day_number}`);

                const marker = _createDayMarker(day.day_number || (idx + 1), endLat, endLng, isReturn, labelText);
                if (marker) {
                    state.dayMarkers.push(marker);
                }
            }
        }
    });
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
            // Attraction / waypoint items will be rendered as rich attraction markers, not generic red pins
            if (wp.type === 'attraction' || wp.type === 'waypoint') return;
            // Stay / rest days sit at the previous night's campsite, which already has a marker
            if (wp.type === 'stay') return;

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

    // Immediately restore and display any saved attraction / waypoint pins from daily_schedules
    const savedAttractions = [];
    daily_schedules.forEach(day => {
        (day.waypoints || []).forEach(wp => {
            if (wp.type === 'attraction' || wp.type === 'waypoint') {
                savedAttractions.push({
                    name: wp.label || wp.name || 'Punkt na trasie',
                    lat: wp.lat,
                    lng: wp.lng,
                    place_id: wp.place_id,
                    photo_url: wp.photo_url,
                    rating: wp.rating,
                    address: wp.address || '',
                    emoji: wp.emoji || (wp.type === 'waypoint' ? '📍' : '⭐'),
                    color: wp.color || (wp.type === 'waypoint' ? '#001E50' : '#F9A825'),
                    category_label: wp.category_label || (wp.type === 'waypoint' ? 'Punkt na trasie' : 'Atrakcja'),
                    day_number: day.day_number,
                    is_in_route: true
                });
            }
        });
    });

    if (savedAttractions.length > 0) {
        state.rawAttractionsList = savedAttractions;
        state.allSortedAttractions = sortAttractionsList(savedAttractions, state.topSortMode || 'reviews');
        state.top5Offset = 0;
        state.top5Attractions = state.allSortedAttractions.slice(0, 8);
        state.attractionsVisible = true;

        savedAttractions.forEach((attrObj, i) => {
            const marker = _createAttractionMarker(attrObj, (attrObj.day_number || 1) - 1, i);
            if (marker) {
                marker._attrData = attrObj;
                state.attractionMarkers.push(marker);
            }
        });

        const badge = document.getElementById('attractions-count-badge');
        if (badge) {
            badge.textContent = savedAttractions.length;
            badge.style.display = 'inline-flex';
        }
        const btnTop = document.getElementById('btn-top-attractions');
        if (btnTop) {
            btnTop.style.display = 'inline-flex';
        }
        const btnToggle = document.getElementById('btn-toggle-attractions');
        if (btnToggle) {
            btnToggle.classList.add('active');
        }
    }

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
        card.dataset.dayNumber = day.day_number;

        const btnText = window.t ? window.t('camping_change_btn') : '🏕️ Zobacz / zmień kemping';
        let campingName = day.overnight_camping ? (day.overnight_camping.name || day.overnight_camping.label) : null;

        const isReturn = (typeof day.is_return === 'boolean') ? day.is_return :
                         (typeof day.is_return_leg === 'boolean') ? day.is_return_leg :
                         (isRoundTripOverall && daily_schedules.length > 1 && (idx + 1) > Math.ceil(daily_schedules.length / 2));
        const returnBadgeText = window.t ? window.t('day_return_badge') : 'Powrót';
        const returnBadgeHtml = isReturn ? `<div class="day-return-badge">🔄 ${returnBadgeText}</div>` : '';

        const attractionWaypoints = (day.waypoints || []).filter(wp => wp.type === 'attraction' || wp.type === 'waypoint');
        let attractionsHtml = '';

        if (attractionWaypoints.length > 0) {
            const attrBadges = attractionWaypoints.map(wp => {
                const badgeEmoji = wp.emoji || (wp.type === 'waypoint' ? '📍' : '⭐');
                const badgeColor = wp.color || (wp.type === 'waypoint' ? '#001E50' : '#D69E2E');
                return `<div style="font-size:0.72rem; color:${badgeColor}; font-weight:600; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${wp.label}">${badgeEmoji} ${wp.label}</div>`;
            }).join('');
            attractionsHtml = `<div class="day-card-attractions">${attrBadges}</div>`;
        }

        const dayTitle = window.t ? window.t('day_card_day', { day: day.day_number }) : `Dzień ${day.day_number}`;
        // Stay / rest day: no driving, the night is at the same campsite
        const stayWp = (day.waypoints || []).length > 0 && day.waypoints.every(wp => wp.type === 'stay')
            ? day.waypoints[0] : null;
        const stayKind = day.stay_kind || (stayWp && stayWp.stay_kind) || 'stay';
        const stayText = window.t
            ? window.t(stayKind === 'rest' ? 'day_rest_label' : 'day_stay_label')
            : (stayKind === 'rest' ? 'Dzień odpoczynku' : 'Dzień na miejscu');
        const drivingLineHtml = stayWp
            ? `<span>⛺ ${stayText}</span>`
            : `<span>🚗 ${day.driving_hours || 0}h</span>
                <span style="margin-left: 8px;">📏 ${Math.round(day.driving_km || 0)}km</span>`;
        if (!campingName && stayWp) campingName = stayWp.label;
        const dayBadgeColor = isReturn ? '#E65100' : '#001E50';

        card.innerHTML = `
            <div class="day-number" style="display:flex; align-items:center; justify-content:space-between;">
                <span>${dayTitle}</span>
                <span class="day-stage-tag" style="margin-left:auto; font-size:0.72rem; padding:2px 7px; border-radius:10px; background:${dayBadgeColor}; color:#fff; font-weight:700;">D${day.day_number}</span>
            </div>
            <div class="day-label">${day.date || ''}</div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 4px;">
                ${drivingLineHtml}
            </div>
            <div class="day-card-content">
                ${attractionsHtml}
                ${campingName ? `<div style="font-size:0.75rem; color:#00875A; font-weight:bold; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${campingName}">🏕️ ${campingName}</div>` : ''}
                ${returnBadgeHtml}
            </div>
            <button class="btn-change-camping-day">${btnText}</button>
        `;

        card.addEventListener('mouseenter', () => {
            highlightDayRoute(day.day_number);
        });

        card.addEventListener('mouseleave', () => {
            const activeCard = document.querySelector('.day-card.active');
            if (activeCard && activeCard.dataset.dayNumber) {
                highlightDayRoute(parseInt(activeCard.dataset.dayNumber, 10));
            } else {
                highlightDayRoute(null);
            }
        });

        card.addEventListener('click', (e) => {
            fitMapToDayRoute(day);
            document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            highlightDayRoute(day.day_number);
        });

        const changeBtn = card.querySelector('.btn-change-camping-day');
        if (changeBtn) {
            changeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                fitMapToDayRoute(day);
                document.querySelectorAll('.day-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                highlightDayRoute(day.day_number);
                openCampingSelectionModal(state.currentTrip || tripData, day.day_number);
            });
        }

        dayCardsContainer.appendChild(card);
    });

    const tripInfoCard = document.getElementById('trip-info-card');
    if (tripInfoCard) {
        tripInfoCard.classList.remove('collapsed');
        tripInfoCard.classList.add('visible');
        const mapChatPanelEl = document.getElementById('map-chat-panel');
        if (mapChatPanelEl && mapChatPanelEl.style.display === 'flex') {
            document.body.classList.add('map-chat-open');
        }
    }

    const btnToggleTripInfo = document.getElementById('btn-toggle-trip-info');
    if (btnToggleTripInfo) {
        btnToggleTripInfo.style.display = 'flex';
    }

    const btnShowMap = document.getElementById('btn-show-map');
    if (btnShowMap) {
        btnShowMap.style.display = 'flex';
    }

    // Restore and display photos on map with thumbnail pins and in Travel Memory gallery
    if (tripData.photos && tripData.photos.length > 0) {
        const gpsPhotos = tripData.photos.filter(p => p.lat != null && p.lng != null);
        const locCounts = {};
        gpsPhotos.forEach(p => {
            const key = `${Number(p.lat).toFixed(4)},${Number(p.lng).toFixed(4)}`;
            locCounts[key] = (locCounts[key] || 0) + 1;
        });
        const locIndex = {};
        gpsPhotos.forEach(p => {
            const key = `${Number(p.lat).toFixed(4)},${Number(p.lng).toFixed(4)}`;
            const idx = locIndex[key] || 0;
            locIndex[key] = idx + 1;
            _createPhotoMarker(p, idx, locCounts[key]);
        });
        renderTravelMemoryGrid(tripData.photos);
    } else {
        renderTravelMemoryGrid([]);
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

function sortAttractionsList(attrsList, mode = 'reviews') {
    if (!attrsList) return [];
    const list = [...attrsList];
    if (mode === 'day') {
        list.sort((a, b) => {
            const dA = a.day_number || 1;
            const dB = b.day_number || 1;
            if (dA !== dB) return dA - dB;
            const revA = parseInt(a.user_ratings_total || a.review_count) || 0;
            const revB = parseInt(b.user_ratings_total || b.review_count) || 0;
            if (revB !== revA) return revB - revA;
            const rA = parseFloat(a.rating) || 0;
            const rB = parseFloat(b.rating) || 0;
            return rB - rA;
        });
    } else if (mode === 'rating') {
        list.sort((a, b) => {
            const rA = parseFloat(a.rating) || 0;
            const rB = parseFloat(b.rating) || 0;
            if (rB !== rA) return rB - rA;
            const revA = parseInt(a.user_ratings_total || a.review_count) || 0;
            const revB = parseInt(b.user_ratings_total || b.review_count) || 0;
            return revB - revA;
        });
    } else {
        // Default mode 'reviews': sort primarily by user_ratings_total descending,
        // with rating as secondary tiebreaker.
        list.sort((a, b) => {
            const revA = parseInt(a.user_ratings_total || a.review_count) || 0;
            const revB = parseInt(b.user_ratings_total || b.review_count) || 0;
            if (revB !== revA) return revB - revA;
            const rA = parseFloat(a.rating) || 0;
            const rB = parseFloat(b.rating) || 0;
            return rB - rA;
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
        let url = `${API_BASE}/api/attractions/${tripId}?limit_per_day=8&sample_every_km=80`;
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
        Object.entries(data.attractions_by_day).forEach(([dayNum, attractions]) => {
            attractions.forEach((attr) => {
                const attrObj = { ...attr, day_number: parseInt(dayNum) };
                allAttrs.push(attrObj);
            });
        });

        // Ensure any attraction saved in current trip schedules is present in allAttrs
        if (state.currentTrip && state.currentTrip.daily_schedules) {
            state.currentTrip.daily_schedules.forEach(day => {
                (day.waypoints || []).forEach(wp => {
                    if (wp.type === 'attraction') {
                        const exists = allAttrs.some(a =>
                            (wp.place_id && a.place_id && a.place_id === wp.place_id) ||
                            (a.name && wp.label && a.name.trim().toLowerCase() === wp.label.trim().toLowerCase())
                        );
                        if (!exists) {
                            allAttrs.unshift({
                                name: wp.label || wp.name || 'Atrakcja',
                                lat: wp.lat,
                                lng: wp.lng,
                                place_id: wp.place_id,
                                photo_url: wp.photo_url,
                                rating: wp.rating,
                                address: wp.address || '',
                                emoji: wp.emoji || '⭐',
                                color: wp.color || '#F9A825',
                                category_label: wp.category_label || 'Atrakcja',
                                day_number: day.day_number,
                                is_in_route: true
                            });
                        }
                    }
                });
            });
        }

        // Render markers for all attractions
        clearAttractionMarkers();
        allAttrs.forEach((attrObj, idx) => {
            const marker = _createAttractionMarker(attrObj, (attrObj.day_number || 1) - 1, idx);
            if (marker) {
                marker._attrData = attrObj;
                state.attractionMarkers.push(marker);
                totalCount++;
            }
        });

        state.rawAttractionsList = allAttrs;
        state.allSortedAttractions = sortAttractionsList(allAttrs, state.topSortMode || 'reviews');
        state.top5Offset = 0;
        state.top5Attractions = state.allSortedAttractions.slice(0, 8);
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
    const pageItems = allAttrs.slice(offset, offset + 8);

    grid.innerHTML = '';

    const medals = ['🥇 #1', '🥈 #2', '🥉 #3', '⭐ #4', '⭐ #5', '⭐ #6', '⭐ #7', '⭐ #8'];

    pageItems.forEach((attr, idx) => {
        const globalRank = offset + idx + 1;
        const card = document.createElement('div');
        card.className = 'top-attraction-item-card';

        const hasRealPhoto = Boolean(attr.photo_url);
        const photoSrc = hasRealPhoto ? attr.photo_url : ATTRACTION_PLACEHOLDER_URL;
        const previewBadge = !hasRealPhoto ? `<span class="photo-placeholder-badge">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : '';
        const photoHtml = `
            <div class="top-attraction-img-wrap">
                <img src="${photoSrc}" alt="${attr.name}" onerror="this.onerror=null; this.src='${ATTRACTION_PLACEHOLDER_URL}';">
                ${previewBadge}
            </div>
        `;

        const revCount = (attr.user_ratings_total || attr.review_count);
        const revCountHtml = revCount ? ` <span style="color:#718096; font-size:0.75rem; font-weight:normal;">(${parseInt(revCount).toLocaleString()})</span>` : '';
        const ratingHtml = attr.rating ? `<span style="color:#D69E2E; font-weight:700;">⭐ ${attr.rating}${revCountHtml}</span>` : '';
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
                    <div style="font-weight:700; color:#001E50; margin-top:4px;">🗓️ ${window.t ? window.t('day_card_day', { day: attr.day_number || 1 }) : `Dzień ${attr.day_number || 1}`}</div>
                </div>
            </div>
            <div style="margin-top:10px; display:flex; gap:6px; flex-wrap:wrap;">
                <button class="btn-show-attraction-map" onclick="focusAttractionOnMap(${attr.lat}, ${attr.lng}, '${(attr.name || '').replace(/'/g, "\\'")}')">
                    ${window.t ? window.t('top_attractions_focus_map') : '🎯 Pokaż na mapie'}
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
            ? (window.t ? window.t('top_attractions_title') : '🌟 Top 8 Must-See Atrakcji na Trasie')
            : (window.t && window.vwI18n.getLanguage() === 'de'
                ? `🌟 Highlights #${offset + 1}–#${offset + pageItems.length} der Route`
                : `🌟 Wyjątkowe Atrakcje #${offset + 1}–#${offset + pageItems.length} na Trasie`);
    }

    if (indicatorEl) {
        indicatorEl.textContent = window.t
            ? window.t('top_attractions_page_fmt', { start: offset + 1, end: offset + pageItems.length, total: allAttrs.length })
            : `Atrakcje #${offset + 1}–#${offset + pageItems.length} z ${allAttrs.length}`;
    }

    if (btnPrev) btnPrev.disabled = (offset === 0);
    if (btnNext) btnNext.disabled = (offset + 8 >= allAttrs.length);
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
    if (attr && attr.is_in_route === true) return true;
    if (!state.currentTrip || !state.currentTrip.daily_schedules) return false;

    const targetDay = dayNumber || attr.day_number;
    const targetSched = targetDay
        ? state.currentTrip.daily_schedules.find(d => d.day_number === targetDay)
        : null;

    const checkWaypoint = (wp) => {
        if (wp.type !== 'attraction') return false;
        if (attr.place_id && wp.place_id && wp.place_id === attr.place_id) return true;
        if (wp.label && attr.name && wp.label.trim().toLowerCase() === attr.name.trim().toLowerCase()) return true;
        if (wp.lat && wp.lng && attr.lat && attr.lng && Math.abs(wp.lat - attr.lat) < 0.0008 && Math.abs(wp.lng - attr.lng) < 0.0008) return true;
        return false;
    };

    if (targetSched && targetSched.waypoints) {
        if (targetSched.waypoints.some(checkWaypoint)) return true;
    }

    // Fallback across all days in case attraction was assigned to another leg
    return state.currentTrip.daily_schedules.some(d => (d.waypoints || []).some(checkWaypoint));
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

            // Refresh open camping modal attractions if currently open
            const campingModal = document.getElementById('camping-selection-modal');
            if (campingModal && campingModal.style.display !== 'none' && window.renderDayAttractionsForModal) {
                window.renderDayAttractionsForModal(res.trip_data, dayNumber);
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
            <div style="margin:-4px -4px 8px -4px; border-radius:4px 4px 0 0; overflow:hidden; height:125px; position:relative;">
                <img src="${photoUrl || ATTRACTION_PLACEHOLDER_URL}" alt="${name}"
                     style="width:100%; height:125px; object-fit:cover; display:block;"
                     onerror="this.onerror=null; this.src='${ATTRACTION_PLACEHOLDER_URL}';">
                ${!photoUrl ? `<span class="photo-placeholder-badge" style="font-size:0.62rem; padding:1px 5px; bottom:4px; right:4px;">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : ''}
            </div>
            <div style="padding: 0 2px 4px;">
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

// ── Real-Time Geolocation Service ────────────────────────────
function updateLocationUI() {
    const toggleBtn = document.getElementById('btn-toggle-location');
    const labelEl = document.getElementById('location-label');
    const indicatorEl = document.getElementById('chat-location-indicator');
    const cliNameEl = document.getElementById('cli-name');
    const cliBtn = document.getElementById('cli-toggle-btn');
    const t = window.t || ((k) => k);

    if (!toggleBtn) return;

    if (!state.locationEnabled) {
        toggleBtn.className = 'btn-location-toggle disabled';
        toggleBtn.setAttribute('aria-checked', 'false');
        toggleBtn.title = t('location_tooltip_off');
        if (labelEl) labelEl.textContent = t('location_disabled');

        if (indicatorEl) indicatorEl.style.display = 'none';
        return;
    }

    if (state.locationLoading) {
        toggleBtn.className = 'btn-location-toggle loading';
        toggleBtn.setAttribute('aria-checked', 'true');
        toggleBtn.title = t('location_acquiring');
        if (labelEl) labelEl.textContent = t('location_acquiring');

        if (indicatorEl) {
            indicatorEl.style.display = 'inline-flex';
            if (cliNameEl) cliNameEl.textContent = t('location_acquiring');
            if (cliBtn) cliBtn.textContent = t('location_btn_disable');
        }
        return;
    }

    if (state.userLocation) {
        toggleBtn.className = 'btn-location-toggle active';
        toggleBtn.setAttribute('aria-checked', 'true');
        const displayName = state.userLocation.city || state.userLocation.name || t('location_active');
        toggleBtn.title = `${t('location_tooltip_on')} (${state.userLocation.name || displayName})`;
        if (labelEl) labelEl.textContent = displayName;

        if (indicatorEl) {
            indicatorEl.style.display = 'inline-flex';
            if (cliNameEl) cliNameEl.textContent = state.userLocation.name || displayName;
            if (cliBtn) cliBtn.textContent = t('location_btn_disable');
        }
    } else {
        toggleBtn.className = 'btn-location-toggle disabled';
        toggleBtn.setAttribute('aria-checked', 'true');
        toggleBtn.title = t('location_unavailable');
        if (labelEl) labelEl.textContent = t('location_unavailable');

        if (indicatorEl) indicatorEl.style.display = 'none';
    }
}
window.updateLocationUI = updateLocationUI;

async function fetchUserLocation() {
    if (!state.locationEnabled) {
        updateLocationUI();
        return;
    }

    if (!navigator.geolocation) {
        state.locationLoading = false;
        state.userLocation = null;
        updateLocationUI();
        return;
    }

    state.locationLoading = true;
    updateLocationUI();

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            try {
                const lang = window.vwI18n ? window.vwI18n.getLanguage() : 'pl';
                const res = await apiCall('location/reverse', { lat, lng, lang });
                const locName = (res && res.name) ? res.name : `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
                state.userLocation = {
                    lat,
                    lng,
                    name: locName,
                    city: res ? res.city : null,
                    country: res ? res.country : null,
                    address: res ? res.address : null,
                };
            } catch (err) {
                console.warn('Reverse geocoding error:', err);
                state.userLocation = {
                    lat,
                    lng,
                    name: `${lat.toFixed(4)}, ${lng.toFixed(4)}`,
                    city: null,
                    country: null,
                    address: null,
                };
            } finally {
                state.locationLoading = false;
                updateLocationUI();
            }
        },
        (error) => {
            console.warn('Geolocation acquisition error:', error.message);
            state.locationLoading = false;
            state.userLocation = null;
            updateLocationUI();
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000,
        }
    );
}
window.fetchUserLocation = fetchUserLocation;

function toggleLocationFeature(forceState) {
    const newState = forceState !== undefined ? forceState : !state.locationEnabled;
    state.locationEnabled = newState;
    localStorage.setItem('vw_location_enabled', newState ? 'true' : 'false');

    const t = window.t || ((k) => k);

    if (newState) {
        if (window.showToast) {
            window.showToast(t('location_toast_on'), 'success', 2500);
        }
        fetchUserLocation();
    } else {
        state.userLocation = null;
        state.locationLoading = false;
        updateLocationUI();
        if (window.showToast) {
            window.showToast(t('location_toast_off'), 'info', 2500);
        }
    }
}
window.toggleLocationFeature = toggleLocationFeature;

// ── Chat Logic ───────────────────────────────────────────────
function formatChatMessage(role, text) {
    if (!text) return '';
    if (role !== 'assistant') {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\n/g, '<br>');
    }

    let formatted = text
        // Images markdown
        .replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, url) => {
            return `<div class="chat-photo-card" style="margin: 8px 0; max-width: 340px;"><img src="${url}" alt="${alt}" style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);" onerror="this.parentElement.style.display='none'"></div>`;
        })
        // Bold markdown
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic markdown
        .replace(/(^|[^*])\*(?!\*)([^*]+)\*/g, '$1<em>$2</em>')
        // Bullet list lines (- item or * item)
        .replace(/^[ \t]*[-*][ \t]+(.*)$/gm, '<div class="chat-bullet-item"><span class="chat-bullet-dot">•</span><span class="chat-bullet-text">$1</span></div>');

    // Convert double newlines to paragraph gaps, single newlines to <br>
    formatted = formatted.replace(/\n{2,}/g, '<div class="chat-paragraph-gap"></div>');
    formatted = formatted.replace(/\n/g, '<br>');
    formatted = formatted.replace(/(<\/div>)<br>/g, '$1');
    formatted = formatted.replace(/<br>(<div)/g, '$1');

    return formatted;
}

function addMessage(role, text) {
    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.style.display = 'none';

    const formattedText = formatChatMessage(role, text);
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const msgId = `snf-msg-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

    // 1. Main Chat View
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.id = msgId;
        msgDiv.dataset.rawText = encodeURIComponent(text || '');

        if (role === 'assistant') {
            const rolePillText = (window.t ? window.t('sniffer_role_tag') : 'Przewodnik VW') || 'Przewodnik VW';
            msgDiv.innerHTML = `
                <div class="message-content-wrap">
                    <div class="message-header-row">
                        <div class="message-sender-tag">
                            <span class="sniffer-name">🐶 Volkswagen Sniffer</span>
                            <span class="sniffer-badge-pill">${rolePillText}</span>
                        </div>
                        <div class="message-actions-right">
                            <div class="message-meta">${timeStr}</div>
                        </div>
                    </div>
                    <div class="message-bubble">${formattedText}</div>
                </div>
            `;
        } else {
            msgDiv.innerHTML = `
                <div class="message-content-wrap">
                    <div class="message-bubble">${formattedText}</div>
                    <div class="message-meta">${timeStr}</div>
                </div>
            `;
        }
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
        mapMsgDiv.className = `message ${role} map-message`;
        if (role === 'assistant') {
            mapMsgDiv.innerHTML = `
                <div class="message-content-wrap">
                    <div class="message-header-row">
                        <div class="message-sender-tag">
                            <span class="sniffer-name">🐶 VW Sniffer</span>
                        </div>
                        <div class="message-meta">${timeStr}</div>
                    </div>
                    <div class="message-bubble">${formattedText}</div>
                </div>
            `;
        } else {
            mapMsgDiv.innerHTML = `
                <div class="message-content-wrap">
                    <div class="message-bubble">${formattedText}</div>
                    <div class="message-meta">${timeStr}</div>
                </div>
            `;
        }
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

function showTyping(show, isPlanning = false) {
    state.isTyping = show;

    // 3D Sniffer (AVW module): thinking face while the reply is pending
    if (window.snifferAVW) {
        window.snifferAVW.thinking(show);
    }
    
    const typingEl = document.getElementById('typing-indicator');
    const planningEl = document.getElementById('planning-indicator');

    if (show) {
        if (isPlanning) {
            if (typingEl) typingEl.classList.remove('visible');
            if (planningEl) planningEl.classList.add('visible');
        } else {
            if (typingEl) typingEl.classList.add('visible');
            if (planningEl) planningEl.classList.remove('visible');
        }
    } else {
        if (typingEl) typingEl.classList.remove('visible');
        if (planningEl) planningEl.classList.remove('visible');
    }

    const messagesEl = document.getElementById('chat-messages');
    if (show && messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;

    const mapTypingEl = document.getElementById('map-typing-indicator');
    if (mapTypingEl) mapTypingEl.classList.toggle('visible', show);
    const mapMessagesEl = document.getElementById('map-chat-messages');
    if (show && mapMessagesEl) mapMessagesEl.scrollTop = mapMessagesEl.scrollHeight;
}

async function sendMessage(text) {
    if (!text || !text.trim() || state.isTyping) return;

    // Interrupt Sniffer if he is still talking
    if (window.snifferAVW) {
        window.snifferAVW.stop();
    }

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
    const chatPayload = { message: text, conversation_id: CHAT_CONVERSATION_ID };
    if (state.locationEnabled && state.userLocation) {
        chatPayload.user_location = state.userLocation;
    }
    const result = await apiCall('chat', chatPayload);
    showTyping(false);

    if (sendBtn) sendBtn.disabled = input ? input.value.trim().length === 0 : true;
    if (mapSendBtn) mapSendBtn.disabled = mapInput ? mapInput.value.trim().length === 0 : true;


    if (result.status === 'success' || result.status === 'partial') {
        addMessage('assistant', result.text);
        speakSnifferLine(result.sniffer);
        
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
                    (tc.function_name === 'plan_route' || tc.function_name === 'modify_route' || tc.function_name === 'add_waypoint' || (tc.result && tc.result.trip && tc.result.daily_schedules)) &&
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
                // Without the interactive map (GOOGLE_MAPS_MODE != full) stay in the chat.
                if (state.currentView === 'chat' && window.google && window.google.maps) {
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

/**
 * Interactive mode: Pin a photo onto Google Maps by clicking on the map.
 */
function startPinningPhotoOnMap(photo, onPinnedCallback = null) {
    if (!photo) return;

    // Switch to map view
    if (window.switchView) {
        window.switchView('map');
    }

    const overlay = document.getElementById('pin-photo-overlay');
    const preview = document.getElementById('pin-photo-preview');
    const cancelBtn = document.getElementById('pin-photo-cancel');

    const fname = photo.original_filename || (photo.file_url ? photo.file_url.split('/').pop() : 'Wspomnienie');
    let thumbUrl = photo.thumbnail_url || photo.file_url || '';
    if (thumbUrl && thumbUrl.includes('/.tmp/')) {
        thumbUrl = `/photos/file/${thumbUrl.split('/').pop()}`;
    } else if (!thumbUrl && fname) {
        thumbUrl = `/photos/file/${fname}`;
    }

    if (preview) {
        preview.src = thumbUrl || ATTRACTION_PLACEHOLDER_URL;
    }
    if (overlay) {
        overlay.style.display = 'flex';
    }

    const cleanup = () => {
        if (overlay) overlay.style.display = 'none';
        if (state.pinPhotoListener && state.map) {
            google.maps.event.removeListener(state.pinPhotoListener);
            state.pinPhotoListener = null;
        }
    };

    if (cancelBtn) {
        cancelBtn.onclick = (e) => {
            e.stopPropagation();
            cleanup();
        };
    }

    if (!state.map || !window.google || !window.google.maps) {
        return;
    }

    // Remove any previous pending listener
    if (state.pinPhotoListener) {
        google.maps.event.removeListener(state.pinPhotoListener);
        state.pinPhotoListener = null;
    }

    state.pinPhotoListener = google.maps.event.addListenerOnce(state.map, 'click', async (event) => {
        const lat = event.latLng.lat();
        const lng = event.latLng.lng();
        photo.lat = lat;
        photo.lng = lng;

        cleanup();

        // Create marker on map immediately
        const marker = _createPhotoMarker(photo, 0, 1);
        if (marker && state.map) {
            state.map.panTo({ lat, lng });
        }

        // Persist to backend if photo has an ID
        if (photo.id) {
            try {
                const tripId = state.currentTrip ? (state.currentTrip.id || (state.currentTrip.trip && state.currentTrip.trip.id)) : null;
                await fetch(`${API_BASE}/api/pin_photo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        photo_id: photo.id,
                        lat,
                        lng,
                        captured_at: photo.captured_at,
                        tagged_day_schedule_id: photo.tagged_day_schedule_id,
                        trip_id: tripId,
                    })
                });
            } catch (err) {
                console.error('Failed to persist photo pin:', err);
            }
        }

        // Re-render travel memory grid to reflect updated GPS status
        if (state.currentTrip && state.currentTrip.photos) {
            renderTravelMemoryGrid(state.currentTrip.photos);
        }

        if (typeof onPinnedCallback === 'function') {
            onPinnedCallback(lat, lng);
        }
    });
}
window.startPinningPhotoOnMap = startPinningPhotoOnMap;

/**
 * Opens the photo edit modal allowing user to modify capture date,
 * trip day assignment, and map location pin.
 */
function openPhotoEditModal(photo) {
    if (!photo) return;
    const modal = document.getElementById('photo-edit-modal');
    if (!modal) return;

    const preview = document.getElementById('photo-edit-preview');
    const fnameEl = document.getElementById('photo-edit-filename');
    const idInput = document.getElementById('photo-edit-id');
    const latInput = document.getElementById('photo-edit-lat');
    const lngInput = document.getElementById('photo-edit-lng');
    const dateInput = document.getElementById('photo-edit-date');
    const daySelect = document.getElementById('photo-edit-day');
    const coordsText = document.getElementById('photo-edit-coords-text');

    const fname = photo.original_filename || (photo.file_url ? photo.file_url.split('/').pop() : 'Zdjęcie');
    let thumbUrl = photo.thumbnail_url || photo.file_url || '';
    if (thumbUrl && thumbUrl.includes('/.tmp/')) {
        thumbUrl = `/photos/file/${thumbUrl.split('/').pop()}`;
    } else if (!thumbUrl && fname) {
        thumbUrl = `/photos/file/${fname}`;
    }
    if (thumbUrl && /\.(heic|heif)$/i.test(thumbUrl)) {
        thumbUrl = thumbUrl.replace(/\.(heic|heif)$/i, '_converted.jpg');
    }

    if (preview) preview.src = thumbUrl || ATTRACTION_PLACEHOLDER_URL;
    if (fnameEl) fnameEl.textContent = fname;
    if (idInput) idInput.value = photo.id || '';
    if (latInput) latInput.value = photo.lat != null ? photo.lat : '';
    if (lngInput) lngInput.value = photo.lng != null ? photo.lng : '';

    // Captured Date input formatting
    if (dateInput) {
        if (photo.captured_at) {
            try {
                const d = new Date(photo.captured_at);
                dateInput.value = d.toISOString().split('T')[0];
            } catch (e) {
                dateInput.value = '';
            }
        } else {
            const tripStartDate = state.currentTrip ? (state.currentTrip.start_date || (state.currentTrip.trip && state.currentTrip.trip.start_date)) : '';
            dateInput.value = tripStartDate || new Date().toISOString().split('T')[0];
        }
    }

    // Populate Day Selector options
    if (daySelect) {
        daySelect.innerHTML = `<option value="">${window.t ? window.t('photo_edit_day_auto') : 'Automatycznie (wg daty / lokalizacji)'}</option>`;
        const schedules = (state.currentTrip && state.currentTrip.daily_schedules) || [];
        schedules.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            const destLabel = s.waypoints && s.waypoints.length > 0 ? (s.waypoints[s.waypoints.length - 1].label || '') : '';
            opt.textContent = `Dzień ${s.day_number}${s.date ? ` (${s.date})` : ''}${destLabel ? ` · ${destLabel}` : ''}`;
            if (photo.tagged_day_schedule_id && String(photo.tagged_day_schedule_id) === String(s.id)) {
                opt.selected = true;
            } else if (!photo.tagged_day_schedule_id && photo.day_number != null && Number(photo.day_number) === Number(s.day_number)) {
                opt.selected = true;
            }
            daySelect.appendChild(opt);
        });
    }

    // Coordinates display helper
    const updateCoordsDisplay = (lat, lng) => {
        if (coordsText) {
            if (lat != null && lng != null && !isNaN(Number(lat)) && !isNaN(Number(lng))) {
                coordsText.textContent = `📍 ${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`;
                coordsText.style.color = '#00D4FF';
            } else {
                coordsText.textContent = '⚠️ Brak współrzędnych GPS';
                coordsText.style.color = '#FFAA00';
            }
        }
    };
    updateCoordsDisplay(photo.lat, photo.lng);

    // Pick location button
    const pickBtn = document.getElementById('btn-photo-pick-location');
    if (pickBtn) {
        pickBtn.onclick = () => {
            modal.style.display = 'none';
            startPinningPhotoOnMap(photo, (newLat, newLng) => {
                if (latInput) latInput.value = newLat;
                if (lngInput) lngInput.value = newLng;
                updateCoordsDisplay(newLat, newLng);
                modal.style.display = 'flex';
            });
        };
    }

    modal.style.display = 'flex';
}
window.openPhotoEditModal = openPhotoEditModal;

/**
 * Create a photo pin on Google Maps with an async canvas-rendered thumbnail.
 */
function _createPhotoMarker(photo, index = 0, totalAtSameCoord = 1) {
    if (!state.map || !photo || photo.lat == null || photo.lng == null) return null;
    if (!window.google || !window.google.maps) return null;

    let lat = Number(photo.lat);
    let lng = Number(photo.lng);
    if (isNaN(lat) || isNaN(lng)) return null;

    // If multiple photos share the exact same location, fan them out slightly so all thumbnails are visible
    if (totalAtSameCoord > 1 && index > 0) {
        const angle = (index / totalAtSameCoord) * 2 * Math.PI;
        // ~15-25 meters offset in degrees
        const radius = 0.00015 * (1 + Math.floor(index / 8) * 0.4);
        lat += Math.sin(angle) * radius;
        lng += Math.cos(angle) * (radius / Math.cos(lat * Math.PI / 180));
    }

    const fname = photo.original_filename || (photo.file_url ? photo.file_url.split('/').pop() : 'Wspomnienie');

    // Prefer fast, lightweight thumbnail (~30-60KB) for canvas rendering
    let thumbUrl = photo.thumbnail_url || '';
    if (thumbUrl && thumbUrl.includes('/.tmp/')) {
        thumbUrl = `/photos/file/${thumbUrl.split('/').pop()}`;
    }
    if (!thumbUrl && photo.file_url) {
        const base = photo.file_url.split('/').pop();
        const dotIdx = base.lastIndexOf('.');
        thumbUrl = `/photos/file/${dotIdx > 0 ? base.substring(0, dotIdx) + '_thumb.jpg' : base}`;
    }
    if (!thumbUrl && fname) {
        const dotIdx = fname.lastIndexOf('.');
        thumbUrl = `/photos/file/${dotIdx > 0 ? fname.substring(0, dotIdx) + '_thumb.jpg' : fname}`;
    }

    // Full photo URL for InfoWindow and full-size view
    let fullPhotoUrl = photo.file_url || '';
    if (fullPhotoUrl && fullPhotoUrl.includes('/.tmp/uploads/')) {
        fullPhotoUrl = `/photos/file/${fullPhotoUrl.split('/').pop()}`;
    } else if (!fullPhotoUrl && fname) {
        fullPhotoUrl = `/photos/file/${fname}`;
    }
    if (fullPhotoUrl && /\.(heic|heif)$/i.test(fullPhotoUrl)) {
        fullPhotoUrl = fullPhotoUrl.replace(/\.(heic|heif)$/i, '_converted.jpg');
    }

    const targetImgUrl = thumbUrl || fullPhotoUrl;

    // Standard pin SVG while thumbnail loads or as reliable fallback
    const defaultSvg = `data:image/svg+xml;charset=UTF-8,` + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="56" viewBox="0 0 48 56">
            <defs>
                <filter id="p_sh_${photo.id || index}" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="rgba(0,0,0,0.35)"/>
                </filter>
            </defs>
            <path d="M24 2 C12.95 2 4 10.95 4 22 C4 35 24 54 24 54 C24 54 44 35 44 22 C44 10.95 35.05 2 24 2 Z"
                  fill="#001E50" stroke="#00D4FF" stroke-width="2.5" filter="url(#p_sh_${photo.id || index})"/>
            <circle cx="24" cy="22" r="14" fill="#FFFFFF"/>
            <text x="24" y="27" text-anchor="middle" font-size="16">📷</text>
        </svg>`);

    const marker = new google.maps.Marker({
        position: { lat, lng },
        map: state.map,
        title: fname,
        draggable: true,
        icon: {
            url: defaultSvg,
            scaledSize: new google.maps.Size(48, 56),
            anchor: new google.maps.Point(24, 54),
        },
        animation: google.maps.Animation.DROP,
        zIndex: 1000 + (index || 0),
    });

    // Asynchronously render custom thumbnail pin on canvas
    if (targetImgUrl) {
        const img = new Image();
        img.crossOrigin = 'anonymous';

        const renderThumbnailOnMarker = () => {
            try {
                const canvas = document.createElement('canvas');
                const w = 48;
                const h = 56;
                // High-DPI support for retina & tablet displays
                const dpr = Math.min(window.devicePixelRatio || 2, 2);
                canvas.width = w * dpr;
                canvas.height = h * dpr;
                const ctx = canvas.getContext('2d');
                ctx.scale(dpr, dpr);

                const cx = w / 2;
                const topH = 42;
                const radius = 8;

                // Draw shadow
                ctx.shadowColor = 'rgba(0, 0, 0, 0.4)';
                ctx.shadowBlur = 4;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 2;

                // Path for pin: rounded box + bottom pointer needle
                ctx.beginPath();
                ctx.moveTo(radius + 2, 2);
                ctx.lineTo(w - 2 - radius, 2);
                ctx.quadraticCurveTo(w - 2, 2, w - 2, 2 + radius);
                ctx.lineTo(w - 2, topH - radius);
                ctx.quadraticCurveTo(w - 2, topH, w - 2 - radius, topH);
                ctx.lineTo(cx + 6, topH);
                ctx.lineTo(cx, h - 2);
                ctx.lineTo(cx - 6, topH);
                ctx.lineTo(radius + 2, topH);
                ctx.quadraticCurveTo(2, topH, 2, topH - radius);
                ctx.lineTo(2, 2 + radius);
                ctx.quadraticCurveTo(2, 2, radius + 2, 2);
                ctx.closePath();

                ctx.fillStyle = '#FFFFFF';
                ctx.fill();

                // Reset shadow before drawing image and border
                ctx.shadowColor = 'transparent';

                // Navy outline
                ctx.strokeStyle = '#001E50';
                ctx.lineWidth = 2.5;
                ctx.stroke();

                // Clip inner area for photo
                ctx.save();
                ctx.beginPath();
                const pad = 4;
                const ir = 5;
                ctx.moveTo(pad + ir, pad);
                ctx.lineTo(w - pad - ir, pad);
                ctx.quadraticCurveTo(w - pad, pad, w - pad, pad + ir);
                ctx.lineTo(w - pad, topH - pad - ir);
                ctx.quadraticCurveTo(w - pad, topH - pad, w - pad - ir, topH - pad);
                ctx.lineTo(pad + ir, topH - pad);
                ctx.quadraticCurveTo(pad, topH - pad, pad, topH - pad - ir);
                ctx.lineTo(pad, pad + ir);
                ctx.quadraticCurveTo(pad, pad, pad + ir, pad);
                ctx.closePath();
                ctx.clip();

                // Draw image cropped to square
                const natW = img.naturalWidth || img.width || 400;
                const natH = img.naturalHeight || img.height || 300;
                const minSide = Math.min(natW, natH);
                const sx = (natW - minSide) / 2;
                const sy = (natH - minSide) / 2;
                ctx.drawImage(img, sx, sy, minSide, minSide, pad, pad, w - pad * 2, topH - pad * 2);
                ctx.restore();

                // Cyan camera glyph indicator in top-right
                ctx.fillStyle = '#00D4FF';
                ctx.beginPath();
                ctx.arc(w - 7, 7, 5, 0, 2 * Math.PI);
                ctx.fill();
                ctx.strokeStyle = '#FFFFFF';
                ctx.lineWidth = 1;
                ctx.stroke();

                marker.setIcon({
                    url: canvas.toDataURL(),
                    scaledSize: new google.maps.Size(48, 56),
                    anchor: new google.maps.Point(24, 54),
                });
            } catch (err) {
                console.warn('Canvas photo pin generation failed, keeping default pin:', err);
            }
        };

        img.onload = renderThumbnailOnMarker;
        img.onerror = () => {
            if (targetImgUrl !== fullPhotoUrl && fullPhotoUrl) {
                const retryImg = new Image();
                retryImg.crossOrigin = 'anonymous';
                retryImg.onload = () => {
                    img.src = retryImg.src;
                    renderThumbnailOnMarker();
                };
                retryImg.src = fullPhotoUrl;
            }
        };
        img.src = targetImgUrl;
    }

    // InfoWindow popup
    const dateFormatted = photo.captured_at ? new Date(photo.captured_at).toLocaleString('pl-PL') : '';
    const previewUrl = fullPhotoUrl || thumbUrl;
    const infoContent = `
        <div style="font-family: Arial, sans-serif; padding: 6px; text-align: center; max-width: 240px;">
            <div style="width: 220px; height: 140px; margin: 0 auto 8px auto; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.2); background: #f0f4f8;">
                <img src="${previewUrl}" alt="${fname}" style="width: 100%; height: 100%; object-fit: cover; display: block;" onerror="this.onerror=null; this.src='${CAMPING_PLACEHOLDER_URL}';">
            </div>
            <strong style="color: #001E50; font-size: 0.9rem; display: block; word-break: break-word;">${fname}</strong>
            ${dateFormatted ? `<div style="font-size: 0.75rem; color: #666; margin-top: 2px;">📅 ${dateFormatted}</div>` : ''}
            <div style="font-size: 0.72rem; color: #00875A; font-weight: 600; margin-top: 4px;">📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
            <a href="${fullPhotoUrl || previewUrl}" target="_blank" rel="noopener" style="display: inline-block; margin-top: 8px; padding: 5px 12px; background: #001E50; color: #fff; border-radius: 6px; font-size: 11px; text-decoration: none; font-weight: 600;">
                🔍 Pełny rozmiar
            </a>
        </div>
    `;

    const infoWindow = new google.maps.InfoWindow({ content: infoContent });
    marker.addListener('click', () => {
        openSingleInfoWindow(infoWindow, marker);
    });

    // Draggable photo pin: updates coordinate in DB via /api/pin_photo
    marker.addListener('dragend', async (e) => {
        const newLat = e.latLng.lat();
        const newLng = e.latLng.lng();
        photo.lat = newLat;
        photo.lng = newLng;
        console.log(`Photo pin '${fname}' dragged to:`, newLat, newLng);
        if (photo.id) {
            try {
                await fetch(`${API_BASE}/api/pin_photo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ photo_id: photo.id, lat: newLat, lng: newLng })
                });
            } catch (err) {
                console.error('Failed to update photo pin location:', err);
            }
        }
    });

    state.markers.push(marker);
    return marker;
}
window._createPhotoMarker = _createPhotoMarker;

/**
 * Render user photos in the Travel Memory tab gallery.
 */
function renderTravelMemoryGrid(photos) {
    const grid = document.getElementById('photo-grid');
    const emptyState = document.getElementById('photo-empty');
    if (!grid) return;

    // Remove existing dynamically added photo cards
    grid.querySelectorAll('.photo-card').forEach(el => el.remove());

    if (!photos || photos.length === 0) {
        if (emptyState) emptyState.style.display = 'flex';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';

    photos.forEach(photo => {
        const fname = photo.original_filename || (photo.file_url ? photo.file_url.split('/').pop() : 'Wspomnienie');

        let thumbUrl = photo.thumbnail_url || '';
        if (thumbUrl && thumbUrl.includes('/.tmp/')) {
            thumbUrl = `/photos/file/${thumbUrl.split('/').pop()}`;
        }
        if (!thumbUrl && photo.file_url) {
            const base = photo.file_url.split('/').pop();
            const dotIdx = base.lastIndexOf('.');
            thumbUrl = `/photos/file/${dotIdx > 0 ? base.substring(0, dotIdx) + '_thumb.jpg' : base}`;
        }
        if (!thumbUrl && fname) {
            const dotIdx = fname.lastIndexOf('.');
            thumbUrl = `/photos/file/${dotIdx > 0 ? fname.substring(0, dotIdx) + '_thumb.jpg' : fname}`;
        }

        let fullPhotoUrl = photo.file_url || '';
        if (fullPhotoUrl && fullPhotoUrl.includes('/.tmp/uploads/')) {
            fullPhotoUrl = `/photos/file/${fullPhotoUrl.split('/').pop()}`;
        } else if (!fullPhotoUrl && fname) {
            fullPhotoUrl = `/photos/file/${fname}`;
        }
        if (fullPhotoUrl && /\.(heic|heif)$/i.test(fullPhotoUrl)) {
            fullPhotoUrl = fullPhotoUrl.replace(/\.(heic|heif)$/i, '_converted.jpg');
        }

        const displayImgUrl = thumbUrl || fullPhotoUrl;

        const card = document.createElement('div');
        card.className = 'photo-card';
        card.dataset.photoId = photo.id;

        const hasGps = Boolean(photo.lat != null && photo.lng != null && !isNaN(Number(photo.lat)) && !isNaN(Number(photo.lng)));
        const gpsBadge = hasGps
            ? `<span style="position:absolute; top:8px; left:8px; background:rgba(0,30,80,0.85); color:#00D4FF; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; border:1px solid rgba(0,212,255,0.4); z-index:2;">📍 GPS</span>`
            : `<span style="position:absolute; top:8px; left:8px; background:rgba(60,60,60,0.85); color:#FFAA00; font-size:10px; font-weight:600; padding:2px 6px; border-radius:10px; z-index:2;">⚠️ Brak GPS</span>`;

        const dayBadge = photo.day_number != null
            ? `<span style="position:absolute; top:8px; right:8px; background:rgba(0,14,38,0.85); color:#FFFFFF; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; border:1px solid rgba(0,225,217,0.5); z-index:2;">Dzień ${photo.day_number}</span>`
            : '';

        const dateStr = photo.captured_at
            ? new Date(photo.captured_at).toLocaleDateString('pl-PL')
            : 'Brak daty';

        card.innerHTML = `
            <img src="${displayImgUrl}" alt="${fname}" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.onerror=null; this.src='${fullPhotoUrl || displayImgUrl}';">
            ${gpsBadge}
            ${dayBadge}
            <div class="photo-overlay" style="display: flex; flex-direction: column; justify-content: flex-end; padding: 10px; background: linear-gradient(to top, rgba(0,14,38,0.92) 0%, rgba(0,14,38,0.5) 60%, transparent 100%);">
                <span style="font-weight: 600; font-size: 0.85rem; color: #FFFFFF; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${fname}</span>
                <small style="display:block; font-size:10px; color: #00D4FF; margin-top: 2px;">📅 ${dateStr}</small>
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                    <button type="button" class="btn-edit-photo-card" style="flex: 1; padding: 4px 6px; font-size: 11px; background: rgba(0,225,217,0.25); border: 1px solid #00E1D9; color: #FFFFFF; border-radius: 6px; cursor: pointer;">✏️ Edytuj</button>
                    ${hasGps ? `<button type="button" class="btn-pan-photo-card" style="padding: 4px 8px; font-size: 11px; background: rgba(0,120,220,0.4); border: 1px solid #0078DC; color: #FFFFFF; border-radius: 6px; cursor: pointer;" title="Pokaż na mapie">🗺️</button>` : ''}
                </div>
            </div>
        `;

        card.style.cursor = 'pointer';
        card.addEventListener('click', (e) => {
            if (e.target.closest('.btn-pan-photo-card')) {
                e.stopPropagation();
                if (window.switchView) window.switchView('map');
                if (state.map) {
                    state.map.panTo({ lat: Number(photo.lat), lng: Number(photo.lng) });
                    state.map.setZoom(16);
                }
                return;
            }
            openPhotoEditModal(photo);
        });

        grid.appendChild(card);
    });
}
window.renderTravelMemoryGrid = renderTravelMemoryGrid;

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
        const currentTripId = state.currentTrip ? (state.currentTrip.id || (state.currentTrip.trip && state.currentTrip.trip.id)) : null;
        if (currentTripId) {
            formData.append('trip_id', currentTripId);
        }

        try {
            const response = await fetch(`${API_BASE}/api/upload_photo`, { method: 'POST', body: formData });
            const result = await response.json();

            if (result.photo) {
                const fname = result.photo.original_filename || file.name;
                const photoUrl = `/photos/file/${fname}`;

                // Update gallery card img tag with converted server URL for HEIC support
                card.innerHTML = `<img src="${photoUrl}" alt="${fname}" onerror="this.onerror=null; this.src='${photoUrl}';"><div class="photo-overlay">${fname}</div>`;

                if (!state.currentTrip) {
                    state.currentTrip = { trip: {}, photos: [] };
                }
                if (!state.currentTrip.photos) {
                    state.currentTrip.photos = [];
                }
                state.currentTrip.photos.push(result.photo);

                if (result.photo.lat != null && result.photo.lng != null) {
                    _createPhotoMarker(result.photo, 0, 1);
                }
                renderTravelMemoryGrid(state.currentTrip.photos);

                // If photo lacks GPS or metadata, open edit modal to allow immediate date / day / pin setting
                if (!result.photo.lat || !result.photo.lng || result.needs_location) {
                    openPhotoEditModal(result.photo);
                }
            }
        } catch (error) { console.error('Upload failed:', error); }
    }
}

// ── 3D Sniffer (AVW module) ──────────────────────────────────
// The floating 3D Sniffer is mounted by the module script in index.html as window.snifferAVW
// (see architecture/sniffer_speech_sop.md). It always speaks English: the backend adds a short
// English line for him (result.sniffer = {spoken, mood, reaction}) next to the chat reply.
function speakSnifferLine(line) {
    if (!window.snifferAVW || !line || !line.spoken) return;
    window.snifferAVW.say(line.spoken, { mood: line.mood, reaction: line.reaction });
}

function notifySnifferTyping(inputEl) {
    if (window.snifferAVW && inputEl && inputEl.value.trim()) {
        window.snifferAVW.listening();
    }
}

// ── Event Listeners ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Language Switcher setup
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const lang = e.currentTarget.dataset.lang;
            if (!lang) return;
            if (window.vwI18n) {
                window.vwI18n.setLanguage(lang);
            } else {
                localStorage.setItem('vw_app_lang', lang);
            }
            window.location.reload();
        });
    });

    // Language Dropdown Toggles (Nav flyout and Header dropdown)
    const navLangTrigger = document.getElementById('nav-lang-trigger');
    const navLangFlyout = document.getElementById('nav-lang-flyout');
    const headerLangBtn = document.getElementById('btn-header-lang');
    const headerLangMenu = document.getElementById('header-lang-menu');

    function closeAllLangMenus() {
        if (navLangFlyout) navLangFlyout.classList.remove('show');
        if (navLangTrigger) {
            navLangTrigger.classList.remove('open');
            navLangTrigger.setAttribute('aria-expanded', 'false');
        }
        if (headerLangMenu) headerLangMenu.classList.remove('show');
        if (headerLangBtn) {
            headerLangBtn.classList.remove('open');
            headerLangBtn.setAttribute('aria-expanded', 'false');
        }
    }

    if (navLangTrigger && navLangFlyout) {
        navLangTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = navLangFlyout.classList.contains('show');
            closeAllLangMenus();
            if (!isOpen) {
                navLangFlyout.classList.add('show');
                navLangTrigger.classList.add('open');
                navLangTrigger.setAttribute('aria-expanded', 'true');
            }
        });
    }

    if (headerLangBtn && headerLangMenu) {
        headerLangBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = headerLangMenu.classList.contains('show');
            closeAllLangMenus();
            if (!isOpen) {
                headerLangMenu.classList.add('show');
                headerLangBtn.classList.add('open');
                headerLangBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#lang-switcher') && !e.target.closest('#chat-lang-dropdown')) {
            closeAllLangMenus();
        }
    });

    function updateQuickActionPrompts() {
        const qa1 = document.getElementById('qa-1');
        const qa2 = document.getElementById('qa-2');
        const qa3 = document.getElementById('qa-3');
        const qa4 = document.getElementById('qa-4');
        if (qa1 && window.t) qa1.dataset.prompt = window.t('qa_1_prompt');
        if (qa2 && window.t) qa2.dataset.prompt = window.t('qa_2_prompt');
        if (qa3 && window.t) qa3.dataset.prompt = window.t('qa_3_prompt');
        if (qa4 && window.t) qa4.dataset.prompt = window.t('qa_4_prompt');
    }
    window.updateQuickActionPrompts = updateQuickActionPrompts;

    let currentDisplayName = '';

    function updateChatWelcomeGreeting(displayName) {
        const chatHeading = document.getElementById('welcome-chat-heading');
        if (!chatHeading || !window.t) return;
        const firstName = displayName ? displayName.trim().split(' ')[0] : '';
        if (firstName) {
            chatHeading.textContent = window.t('chat_welcome_heading_user', { name: firstName });
        } else {
            chatHeading.textContent = window.t('chat_welcome_heading');
        }
    }
    window.updateChatWelcomeGreeting = updateChatWelcomeGreeting;

    window.addEventListener('vw_lang_changed', (e) => {
        updateQuickActionPrompts();
        updateChatWelcomeGreeting(currentDisplayName);
        if (state.currentTrip) {
            renderDayCards(state.currentTrip);
        }
        const previewBtn = document.getElementById('btn-preview-audio');
        if (previewBtn) {
            const audioPlayer = document.getElementById('audio-preview-player');
            if (!audioPlayer || audioPlayer.paused) {
                previewBtn.textContent = window.t ? window.t('summary_btn_preview') : '▶ Odsłuchaj';
            } else {
                previewBtn.textContent = window.t ? window.t('summary_btn_stop') : '⏸ Zatrzymaj';
            }
        }
        const topModal = document.getElementById('top-attractions-modal');
        if (topModal && topModal.style.display !== 'none') {
            renderTopAttractionsModalPage();
        }
        currentSuggestionsList = [];
        currentSuggestionsLang = null;
        const suggestionsModal = document.getElementById('travel-suggestions-modal');
        if (suggestionsModal && suggestionsModal.style.display !== 'none') {
            openTravelSuggestionsModal(true);
        }
        updateLocationUI();
    });

    if (window.vwI18n) {
        window.vwI18n.updateStaticUI();
        updateQuickActionPrompts();
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
        notifySnifferTyping(chatInput);
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
            mapChatBubble.style.display = isHidden ? 'none' : 'flex';
            if (isHidden) {
                document.body.classList.add('map-chat-open');
                if (mapChatInput) {
                    mapChatInput.focus();
                    const mapMessagesEl = document.getElementById('map-chat-messages');
                    if (mapMessagesEl) mapMessagesEl.scrollTop = mapMessagesEl.scrollHeight;
                }
            } else {
                document.body.classList.remove('map-chat-open');
            }
        });
    }

    if (mapChatClose && mapChatPanel) {
        mapChatClose.addEventListener('click', () => {
            mapChatPanel.style.display = 'none';
            document.body.classList.remove('map-chat-open');
            if (mapChatBubble) mapChatBubble.style.display = 'flex';
        });
    }


    if (mapChatInput) {
        mapChatInput.addEventListener('input', () => {
            mapChatInput.style.height = 'auto';
            mapChatInput.style.height = Math.min(mapChatInput.scrollHeight, 100) + 'px';
            if (mapChatSend) {
                mapChatSend.disabled = mapChatInput.value.trim().length === 0;
            }
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
    window.showToast = showToast;

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

    // Hero Inspiration Card (Option 4)
    const heroCard = document.getElementById('hero-inspiration-card');
    if (heroCard) {
        heroCard.addEventListener('click', () => {
            openTravelSuggestionsModal();
        });
        heroCard.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openTravelSuggestionsModal();
            }
        });
    }

    const btnHeroExplore = document.getElementById('btn-hero-explore');
    if (btnHeroExplore) {
        btnHeroExplore.addEventListener('click', (e) => {
            e.stopPropagation();
            openTravelSuggestionsModal();
        });
    }

    // Travel Suggestions (Middle-Aged + RAG)
    const btnOpenSuggestions = document.getElementById('btn-open-suggestions');
    if (btnOpenSuggestions) {
        btnOpenSuggestions.addEventListener('click', () => {
            openTravelSuggestionsModal(true);
        });
    }

    const btnCloseSuggestions = document.getElementById('travel-suggestions-close');
    if (btnCloseSuggestions) {
        btnCloseSuggestions.addEventListener('click', () => {
            closeTravelSuggestionsModal();
        });
    }

    const btnSkipSuggestions = document.getElementById('btn-skip-suggestions');
    if (btnSkipSuggestions) {
        btnSkipSuggestions.addEventListener('click', () => {
            closeTravelSuggestionsModal();
        });
    }

    const btnRefreshSuggestions = document.getElementById('btn-refresh-suggestions');
    if (btnRefreshSuggestions) {
        btnRefreshSuggestions.addEventListener('click', () => {
            btnRefreshSuggestions.classList.add('spinning');
            openTravelSuggestionsModal(true);
        });
    }

    initTravelSuggestionsControls();

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

    // ── Geolocation in Chat (Toggle & Auto-Locate) ─────────────
    const btnToggleLocation = document.getElementById('btn-toggle-location');
    if (btnToggleLocation) {
        btnToggleLocation.addEventListener('click', () => {
            toggleLocationFeature();
        });
    }

    const cliToggleBtn = document.getElementById('cli-toggle-btn');
    if (cliToggleBtn) {
        cliToggleBtn.addEventListener('click', () => {
            toggleLocationFeature();
        });
    }

    // Initialize geolocation on startup
    updateLocationUI();
    if (state.locationEnabled) {
        fetchUserLocation();
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

    // Photo Edit Modal Event Listeners
    const photoEditModal = document.getElementById('photo-edit-modal');
    const photoEditClose = document.getElementById('photo-edit-close');
    const photoEditCancel = document.getElementById('photo-edit-cancel');
    const photoEditSave = document.getElementById('photo-edit-save');

    if (photoEditClose) photoEditClose.onclick = () => { if (photoEditModal) photoEditModal.style.display = 'none'; };
    if (photoEditCancel) photoEditCancel.onclick = () => { if (photoEditModal) photoEditModal.style.display = 'none'; };

    if (photoEditSave) {
        photoEditSave.onclick = async () => {
            const id = document.getElementById('photo-edit-id')?.value;
            const latVal = document.getElementById('photo-edit-lat')?.value;
            const lngVal = document.getElementById('photo-edit-lng')?.value;
            const dateVal = document.getElementById('photo-edit-date')?.value;
            const dayVal = document.getElementById('photo-edit-day')?.value;

            if (!id) return;

            const tripId = state.currentTrip ? (state.currentTrip.id || (state.currentTrip.trip && state.currentTrip.trip.id)) : null;

            try {
                photoEditSave.disabled = true;
                photoEditSave.textContent = 'Zapisywanie...';

                const body = {
                    photo_id: id,
                    captured_at: dateVal || null,
                    tagged_day_schedule_id: dayVal || null,
                    trip_id: tripId,
                };
                if (latVal && lngVal && !isNaN(Number(latVal)) && !isNaN(Number(lngVal))) {
                    body.lat = Number(latVal);
                    body.lng = Number(lngVal);
                }

                const resp = await fetch(`${API_BASE}/api/pin_photo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const res = await resp.json();

                if (res.status === 'success') {
                    if (state.currentTrip && state.currentTrip.photos) {
                        const targetPhoto = state.currentTrip.photos.find(p => String(p.id) === String(id));
                        if (targetPhoto) {
                            if (res.lat != null) targetPhoto.lat = res.lat;
                            if (res.lng != null) targetPhoto.lng = res.lng;
                            if (res.captured_at) targetPhoto.captured_at = res.captured_at;
                            if (res.tagged_day_schedule_id) targetPhoto.tagged_day_schedule_id = res.tagged_day_schedule_id;
                            if (res.day_number) targetPhoto.day_number = res.day_number;
                        }
                        renderTravelMemoryGrid(state.currentTrip.photos);
                    }
                    if (res.lat != null && res.lng != null && state.map) {
                        _createPhotoMarker({ id, lat: res.lat, lng: res.lng }, 0, 1);
                    }
                    if (photoEditModal) photoEditModal.style.display = 'none';
                    if (window.showNotification) window.showNotification('Zapisano dane zdjęcia! 📷');
                } else {
                    alert(res.message || 'Błąd zapisu zdjęcia');
                }
            } catch (err) {
                console.error('Error saving photo edit:', err);
                alert('Wystąpił błąd podczas zapisywania zmian zdjęcia.');
            } finally {
                photoEditSave.disabled = false;
                photoEditSave.textContent = '💾 Zapisz';
            }
        };
    }

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
        if (counterEl) {
            counterEl.textContent = window.t ? window.t('summary_slide_counter', { current: currentSlideIndex + 1, total: slideshowSlides.length }) : `Slajd ${currentSlideIndex + 1} / ${slideshowSlides.length}`;
        }
        const downloadBtn = document.getElementById('slideshow-download-btn');
        if (downloadBtn) {
            downloadBtn.href = currentUrl;
            downloadBtn.download = `Slide_${currentSlideIndex + 1}.png`;
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
        if (previewBtn) previewBtn.textContent = window.t ? window.t('summary_btn_preview') : '▶ Odsłuchaj';

        summaryOptions.style.display = 'none';
        summaryResultView.style.display = 'flex';
        summaryCarousel.innerHTML = '';

        const musicSelect = document.getElementById('select-music-track');
        const selectedMusic = musicSelect ? musicSelect.value : 'acoustic_sunset';

        const controlsDiv = document.getElementById('summary-controls');
        const loadingText = window.t ? window.t('summary_generating') : 'Generuję podsumowanie podróży... 🚐';
        controlsDiv.innerHTML = `<span id="summary-loading" style="color: white; font-weight: bold; font-size: 1.1rem;">${loadingText}</span>`;

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
                const dlVidText = window.t ? window.t('summary_download_video') : '📥 Pobierz wideo MP4';
                controlsDiv.innerHTML = `
                    <a href="${result.file_url}" download target="_blank" class="btn-primary btn-success" style="text-decoration: none; padding: 12px 24px; border-radius: 24px; font-weight: bold;">
                        ${dlVidText}
                    </a>
                `;
            } else if (format === 'pdf' && result.file_url) {
                const dlPdfText = window.t ? window.t('summary_download_pdf') : '📥 Pobierz dokument PDF';
                summaryCarousel.innerHTML = `
                    <div style="background: white; border-radius: 20px; padding: 40px; text-align: center; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
                        <div style="font-size: 3.5rem; margin-bottom: 12px;">📄</div>
                        <h3 style="color: #001E50; font-size: 1.5rem; margin-bottom: 8px;">PDF</h3>
                        <a href="${result.file_url}" download="VW_California_Trip_Summary.pdf" target="_blank" class="btn-primary" style="text-decoration: none; justify-content: center; font-size: 1.05rem; padding: 14px 28px; background: #001E50; border-radius: 30px;">
                            ${dlPdfText}
                        </a>
                    </div>
                `;
            } else if (result.all_slides && result.all_slides.length > 0) {
                slideshowSlides = result.all_slides;
                currentSlideIndex = 0;

                const btnPrevText = window.t ? window.t('summary_btn_prev') : '◀ Poprzedni';
                const btnNextText = window.t ? window.t('summary_btn_next') : 'Następny ▶';
                const btnDlSlideText = window.t ? window.t('summary_btn_download_slide') : '💾 Pobierz slajd';
                const counterInitial = window.t ? window.t('summary_slide_counter', { current: 1, total: slideshowSlides.length }) : `Slajd 1 / ${slideshowSlides.length}`;

                controlsDiv.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px; background: rgba(0,30,80,0.85); padding: 8px 20px; border-radius: 30px; backdrop-filter: blur(10px); box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
                        <button id="btn-prev-slide" class="btn-primary" style="padding: 6px 14px; font-size: 0.9rem;">${btnPrevText}</button>
                        <span id="slideshow-counter" style="color: white; font-weight: bold; font-size: 0.9rem; min-width: 90px; text-align: center;">${counterInitial}</span>
                        <button id="btn-next-slide" class="btn-primary" style="padding: 6px 14px; font-size: 0.9rem;">${btnNextText}</button>
                        <button id="btn-play-slide" class="btn-primary btn-success" style="padding: 6px 14px; font-size: 0.9rem;">▶ Autoplay</button>
                        <a id="slideshow-download-btn" href="${slideshowSlides[0]}" download="Slide_1.png" class="btn-primary btn-info" style="text-decoration: none; padding: 6px 14px; font-size: 0.9rem;">${btnDlSlideText}</a>
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

    function updateSummaryTripDatesDisplay() {
        const displayEl = document.getElementById('summary-trip-dates-display');
        const editorEl = document.getElementById('summary-trip-dates-editor');
        const startInput = document.getElementById('summary-edit-start-date');
        const endInput = document.getElementById('summary-edit-end-date');
        if (!state.currentTrip) return;

        const sDate = state.currentTrip.start_date || (state.currentTrip.trip && state.currentTrip.trip.start_date) || '';
        const eDate = state.currentTrip.end_date || (state.currentTrip.trip && state.currentTrip.trip.end_date) || '';
        if (displayEl) {
            displayEl.textContent = sDate && eDate ? `${sDate}  ➔  ${eDate}` : (sDate || 'Brak wyznaczonej daty');
        }
        if (startInput && sDate) startInput.value = sDate;
        if (endInput && eDate) endInput.value = eDate;
        if (editorEl) editorEl.style.display = 'none';
    }

    const btnEditTripDates = document.getElementById('btn-edit-trip-dates');
    const btnCancelTripDates = document.getElementById('btn-cancel-trip-dates');
    const btnSaveTripDates = document.getElementById('btn-save-trip-dates');
    const editorDatesEl = document.getElementById('summary-trip-dates-editor');

    if (btnEditTripDates) {
        btnEditTripDates.onclick = () => {
            if (editorDatesEl) {
                editorDatesEl.style.display = editorDatesEl.style.display === 'none' ? 'flex' : 'none';
            }
        };
    }
    if (btnCancelTripDates) {
        btnCancelTripDates.onclick = () => {
            if (editorDatesEl) editorDatesEl.style.display = 'none';
        };
    }
    if (btnSaveTripDates) {
        btnSaveTripDates.onclick = async () => {
            const startInput = document.getElementById('summary-edit-start-date');
            const endInput = document.getElementById('summary-edit-end-date');
            if (!startInput || !startInput.value) {
                alert('Podaj datę rozpoczęcia.');
                return;
            }
            const tripId = state.currentTrip ? (state.currentTrip.id || (state.currentTrip.trip && state.currentTrip.trip.id)) : null;
            if (!tripId) return;

            try {
                btnSaveTripDates.disabled = true;
                btnSaveTripDates.textContent = 'Zapisywanie...';
                const resp = await fetch(`${API_BASE}/api/trips/${tripId}/update_dates`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_date: startInput.value,
                        end_date: endInput ? endInput.value : undefined,
                    })
                });
                const res = await resp.json();
                if (res.status === 'success') {
                    if (state.currentTrip) {
                        state.currentTrip.start_date = res.start_date;
                        state.currentTrip.end_date = res.end_date;
                        if (state.currentTrip.trip) {
                            state.currentTrip.trip.start_date = res.start_date;
                            state.currentTrip.trip.end_date = res.end_date;
                        }
                    }
                    updateSummaryTripDatesDisplay();
                    if (window.showNotification) window.showNotification('Zaktualizowano termin wyprawy! 🚐');
                } else {
                    alert(res.message || 'Błąd aktualizacji dat');
                }
            } catch (err) {
                console.error('Error updating trip dates:', err);
                alert('Wystąpił błąd podczas zapisywania dat.');
            } finally {
                btnSaveTripDates.disabled = false;
                btnSaveTripDates.textContent = '💾 Zapisz';
            }
        };
    }

    btnGenerateSummary.addEventListener('click', () => {
        if (!state.currentTrip) { alert("Najpierw zaplanuj trasę!"); return; }
        summaryModal.style.display = 'flex';
        summaryOptions.style.display = 'block';
        summaryResultView.style.display = 'none';
        updateSummaryTripDatesDisplay();
        loadAudiusSoundtrackSelector('roadtrip');
    });

    const exportSlideshowBtn = document.getElementById('btn-export-slideshow');
    if (exportSlideshowBtn) exportSlideshowBtn.addEventListener('click', () => triggerSummaryGeneration('image_slideshow'));

    const exportVideoBtn = document.getElementById('btn-export-video');
    if (exportVideoBtn) exportVideoBtn.addEventListener('click', () => triggerSummaryGeneration('video'));

    // ── Audius Soundtrack Selector & Player ─────────────────────
    let currentAudiusTracks = [];
    let currentAudiusPlayingId = null;
    let audiusSearchDebounceTimer = null;
    let activeAudiusMood = 'roadtrip';

    async function loadAudiusSoundtrackSelector(mood = 'roadtrip') {
        const container = document.getElementById('music-tracks-container');
        if (!container) return;

        activeAudiusMood = mood;
        const searchingText = window.t ? window.t('summary_music_searching') : 'Ładowanie utworów z Audius... 🎵';
        container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--vw-text-secondary); font-size: 0.85rem;">${searchingText}</div>`;

        try {
            const resp = await fetch(`/api/music/moods?mood=${encodeURIComponent(mood)}&limit=10`);
            const data = await resp.json();
            if (data.status === 'success' && data.current_mood && data.current_mood.tracks) {
                currentAudiusTracks = data.current_mood.tracks;
                renderAudiusTracksList(currentAudiusTracks);
            } else {
                container.innerHTML = `<div style="text-align: center; padding: 20px; color: #E53E3E; font-size: 0.85rem;">Nie udało się załadować utworów Audius.</div>`;
            }
        } catch (e) {
            console.error('Error fetching Audius mood tracks:', e);
            container.innerHTML = `<div style="text-align: center; padding: 20px; color: #E53E3E; font-size: 0.85rem;">Błąd połączenia ze streamingiem Audius.</div>`;
        }
    }

    function renderAudiusTracksList(tracks) {
        const container = document.getElementById('music-tracks-container');
        const selectedInput = document.getElementById('select-music-track');
        const selectedId = selectedInput ? selectedInput.value : '';

        if (!container) return;
        if (!tracks || tracks.length === 0) {
            const noResults = window.t ? window.t('summary_music_no_results') : 'Brak wyników wyszukiwania.';
            container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--vw-text-secondary); font-size: 0.85rem;">${noResults}</div>`;
            return;
        }

        container.innerHTML = tracks.map(track => {
            const isSelected = (selectedId === track.id || selectedId === track.track_id);
            const isPlaying = (currentAudiusPlayingId === track.id);
            const coverHtml = track.artwork_url
                ? `<img src="${track.artwork_url}" class="track-cover" alt="" loading="lazy" onerror="this.outerHTML='<div class=\\'track-cover\\'>🎵</div>'"/>`
                : `<div class="track-cover">🎵</div>`;

            return `
                <div class="music-track-card ${isSelected ? 'selected' : ''}" data-track-id="${track.id}" data-clean-id="${track.track_id}" data-title="${encodeURIComponent(track.title)}" data-artist="${encodeURIComponent(track.artist)}" data-duration="${track.formatted_duration || ''}" data-stream="${track.stream_url || ''}" data-source="${track.source || 'audius'}">
                    <button type="button" class="track-play-btn ${isPlaying ? 'playing' : ''}" data-play-id="${track.id}" data-clean-id="${track.track_id}" data-stream="${track.stream_url || ''}" data-source="${track.source || 'audius'}" title="Odsłuchaj fragment">
                        ${isPlaying ? '⏸' : '▶'}
                    </button>
                    ${coverHtml}
                    <div class="track-info">
                        <div class="track-title" title="${track.title}">${track.title}</div>
                        <div class="track-artist" title="${track.artist}">${track.artist}</div>
                    </div>
                    <div class="track-meta">
                        <span class="track-duration">${track.formatted_duration || '0:38'}</span>
                    </div>
                </div>
            `;
        }).join('');

        // If no track selected yet, auto-select first
        if (!selectedId || selectedId === 'none') {
            if (tracks.length > 0 && selectedId !== 'none') {
                selectAudiusTrack(tracks[0]);
            }
        } else {
            // Re-sync label with currently selected track if present in list
            const found = tracks.find(t => t.id === selectedId || t.track_id === selectedId);
            if (found) {
                selectAudiusTrack(found);
            }
        }
    }

    function selectAudiusTrack(track) {
        const selectedInput = document.getElementById('select-music-track');
        const titleEl = document.getElementById('selected-music-title');
        const noMusicBtn = document.getElementById('btn-toggle-no-music');

        if (selectedInput) selectedInput.value = track.id;
        if (titleEl) titleEl.textContent = `🎵 ${track.title} - ${track.artist} (${track.formatted_duration || ''})`;
        if (noMusicBtn) noMusicBtn.classList.remove('active');

        document.querySelectorAll('.music-track-card').forEach(card => {
            const cId = card.getAttribute('data-track-id');
            const cleanId = card.getAttribute('data-clean-id');
            if (cId === track.id || cleanId === track.track_id) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    }

    function playAudiusPreview(trackId, streamUrl, source, cleanId) {
        const audioPlayer = document.getElementById('audio-preview-player');
        if (!audioPlayer) return;

        if (currentAudiusPlayingId === trackId && !audioPlayer.paused) {
            audioPlayer.pause();
            currentAudiusPlayingId = null;
            updatePlayButtons();
            return;
        }

        let finalSrc = '';
        if (source === 'local') {
            finalSrc = `/assets/audio/${cleanId}.mp3`;
        } else {
            finalSrc = `/api/music/stream/${cleanId}`;
        }

        audioPlayer.src = finalSrc;
        audioPlayer.volume = 0.55;
        audioPlayer.loop = true;
        currentAudiusPlayingId = trackId;
        updatePlayButtons();

        audioPlayer.play().catch(err => {
            console.warn('Playback fallback to direct stream:', err);
            if (streamUrl && source !== 'local') {
                audioPlayer.src = streamUrl;
                audioPlayer.play().catch(() => {});
            }
        });
    }

    function updatePlayButtons() {
        document.querySelectorAll('.track-play-btn').forEach(btn => {
            const btnId = btn.getAttribute('data-play-id');
            if (btnId === currentAudiusPlayingId) {
                btn.classList.add('playing');
                btn.textContent = '⏸';
            } else {
                btn.classList.remove('playing');
                btn.textContent = '▶';
            }
        });
    }

    function stopAudiusPreview() {
        const audioPlayer = document.getElementById('audio-preview-player');
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
        }
        currentAudiusPlayingId = null;
        updatePlayButtons();
    }

    // Audius event delegation
    document.addEventListener('click', (e) => {
        // Mood filter pills
        const moodPill = e.target.closest('.music-mood-pill');
        if (moodPill) {
            document.querySelectorAll('.music-mood-pill').forEach(p => p.classList.remove('active'));
            moodPill.classList.add('active');
            const searchInput = document.getElementById('music-search-input');
            const clearBtn = document.getElementById('btn-clear-music-search');
            if (searchInput) searchInput.value = '';
            if (clearBtn) clearBtn.style.display = 'none';
            const mood = moodPill.getAttribute('data-mood') || 'roadtrip';
            loadAudiusSoundtrackSelector(mood);
            return;
        }

        // Clear search button
        if (e.target.id === 'btn-clear-music-search' || e.target.closest('#btn-clear-music-search')) {
            const searchInput = document.getElementById('music-search-input');
            const clearBtn = document.getElementById('btn-clear-music-search');
            if (searchInput) searchInput.value = '';
            if (clearBtn) clearBtn.style.display = 'none';
            loadAudiusSoundtrackSelector(activeAudiusMood);
            return;
        }

        // Play/Pause button
        const playBtn = e.target.closest('.track-play-btn');
        if (playBtn) {
            e.stopPropagation();
            const playId = playBtn.getAttribute('data-play-id');
            const stream = playBtn.getAttribute('data-stream');
            const source = playBtn.getAttribute('data-source');
            const cleanId = playBtn.getAttribute('data-clean-id');
            playAudiusPreview(playId, stream, source, cleanId);
            return;
        }

        // Select track card
        const trackCard = e.target.closest('.music-track-card');
        if (trackCard) {
            const trackId = trackCard.getAttribute('data-track-id');
            const cleanId = trackCard.getAttribute('data-clean-id');
            const title = decodeURIComponent(trackCard.getAttribute('data-title') || '');
            const artist = decodeURIComponent(trackCard.getAttribute('data-artist') || '');
            const duration = trackCard.getAttribute('data-duration') || '';
            selectAudiusTrack({
                id: trackId,
                track_id: cleanId,
                title: title,
                artist: artist,
                formatted_duration: duration
            });
            return;
        }

        // Toggle No Music
        if (e.target.id === 'btn-toggle-no-music' || e.target.closest('#btn-toggle-no-music')) {
            const btn = document.getElementById('btn-toggle-no-music');
            const selectedInput = document.getElementById('select-music-track');
            const titleEl = document.getElementById('selected-music-title');

            stopAudiusPreview();
            if (selectedInput) selectedInput.value = 'none';
            if (titleEl) titleEl.textContent = '🔇 Bez muzyki';
            if (btn) btn.classList.add('active');
            document.querySelectorAll('.music-track-card').forEach(card => card.classList.remove('selected'));
            return;
        }
    });

    // Audius Search Input listener
    const musicSearchInput = document.getElementById('music-search-input');
    if (musicSearchInput) {
        musicSearchInput.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            const clearBtn = document.getElementById('btn-clear-music-search');
            if (clearBtn) clearBtn.style.display = val ? 'block' : 'none';

            if (audiusSearchDebounceTimer) clearTimeout(audiusSearchDebounceTimer);

            if (!val) {
                loadAudiusSoundtrackSelector(activeAudiusMood);
                return;
            }

            audiusSearchDebounceTimer = setTimeout(async () => {
                const container = document.getElementById('music-tracks-container');
                if (!container) return;
                document.querySelectorAll('.music-mood-pill').forEach(p => p.classList.remove('active'));
                const searchingText = window.t ? window.t('summary_music_searching') : 'Wyszukiwanie utworów na Audius...';
                container.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--vw-text-secondary); font-size: 0.85rem;">${searchingText}</div>`;

                try {
                    const resp = await fetch(`/api/music/search?q=${encodeURIComponent(val)}&limit=12`);
                    const data = await resp.json();
                    if (data.status === 'success') {
                        currentAudiusTracks = data.tracks || [];
                        renderAudiusTracksList(currentAudiusTracks);
                    }
                } catch (err) {
                    console.error('Search error:', err);
                }
            }, 350);
        });
    }

    summaryClose.addEventListener('click', () => {
        stopSlideshowTimer();
        stopAudiusPreview();
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
            title: 'Wskaźniki postępu trasy (5 Kroków)',
            desc: 'Śledź status dopasowania Twojej trasy: Cel, Doświadczenie, Tempo, Kempingi oraz Podsumowanie. W miarę rozmowy z asystentem AI wskaźniki automatycznie zapełniają się na zielono!',
            position: 'bottom'
        },
        {
            targetId: 'btn-open-suggestions',
            titleKey: 'tut_step2_title',
            descKey: 'tut_step2_desc',
            title: 'Inspiracje Podróżnicze AI',
            desc: 'Kliknij przycisk "Inspiracje" w nagłówku, aby odkryć gotowe scenariusze wyjazdów dla VW California z podziałem na weekend, tydzień i dłuższą wyprawę, z wyjaśnieniem AI "Dlaczego to polecamy"!',
            position: 'bottom'
        },
        {
            targetId: 'nav-map',
            titleKey: 'tut_step3_title',
            descKey: 'tut_step3_desc',
            title: 'Interaktywna Mapa & Warstwy na Żywo',
            desc: 'Przeglądaj trasę z aktualnym natężeniem ruchu i pogodą. Odkrywaj kempingi ze zweryfikowanymi przyłączami dla VW California (prąd CEE, woda), atrakcje turystyczne oraz korzystaj z pływającego czatu na mapie!',
            position: 'right'
        },
        {
            targetId: 'nav-memory',
            titleKey: 'tut_step4_title',
            descKey: 'tut_step4_desc',
            title: 'Pamięć Podróży & Galeria Wspomnień',
            desc: 'Twórz cyfrowy dziennik swoich wypraw! Wgraj zdjęcia ze smartfona — system automatycznie odczyta dane GPS z plików EXIF, przypnie je do mapy oraz wygeneruje multimedialne podsumowanie podróży!',
            position: 'right'
        },
        {
            targetId: 'nav-trips-btn',
            titleKey: 'tut_step5_title',
            descKey: 'tut_step5_desc',
            title: 'Moje Wyjazdy & Profil VW California',
            desc: 'Zarządzaj zapisanymi trasami i ich statusami. W profilu skonfiguruj swój model kampera (Ocean, Beach, Coast, Grand California), przyłącza prądu CEE, budżet i dzienny limit godzin za kółkiem!',
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
        },
        {
            targetId: 'map-chat-container',
            titleKey: 'tut_map_step3_title',
            descKey: 'tut_map_step3_desc',
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
        },
        {
            targetId: 'btn-generate-summary',
            titleKey: 'tut_mem_step3_title',
            descKey: 'tut_mem_step3_desc',
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
            checkAndAutoShowSuggestions();
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

        try {
            targetEl.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        } catch (e) {}

        const rect = targetEl.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
            setTimeout(() => renderActiveTutorialStep(stepIdx), 150);
            return;
        }

        const pad = 6;
        const x1 = Math.max(0, rect.left - pad);
        const y1 = Math.max(0, rect.top - pad);
        const x2 = Math.min(window.innerWidth, rect.right + pad);
        const y2 = Math.min(window.innerHeight, rect.bottom + pad);
        const boxWidth = Math.max(0, x2 - x1);
        const boxHeight = Math.max(0, y2 - y1);

        highlightBox.style.top = `${y1}px`;
        highlightBox.style.left = `${x1}px`;
        highlightBox.style.width = `${boxWidth}px`;
        highlightBox.style.height = `${boxHeight}px`;

        // Cutout on tutorial-backdrop: keep target element unblurred and sharp, blur only surroundings
        const backdrop = document.getElementById('tutorial-backdrop');
        if (backdrop) {
            const r = Math.min(10, boxWidth / 2, boxHeight / 2);
            const clipPolygon = `polygon(evenodd, 0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, ` +
                `${x1 + r}px ${y1}px, ` +
                `${x2 - r}px ${y1}px, ` +
                `${x2}px ${y1 + r}px, ` +
                `${x2}px ${y2 - r}px, ` +
                `${x2 - r}px ${y2}px, ` +
                `${x1 + r}px ${y2}px, ` +
                `${x1}px ${y2 - r}px, ` +
                `${x1}px ${y1 + r}px, ` +
                `${x1 + r}px ${y1}px)`;
            backdrop.style.clipPath = clipPolygon;
            backdrop.style.webkitClipPath = clipPolygon;
        }

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
        const backdrop = document.getElementById('tutorial-backdrop');
        if (backdrop) {
            backdrop.style.clipPath = '';
            backdrop.style.webkitClipPath = '';
        }
        checkAndAutoShowSuggestions();
    }

    let hasWelcomeRun = false;

    function initWelcomeAndTutorial(displayName) {
        const welcomeOverlay = document.getElementById('welcome-overlay');
        const welcomeUserName = document.getElementById('welcome-user-name');
        const welcomeSubtitle = document.querySelector('#welcome-overlay .welcome-subtitle');

        if (welcomeUserName) {
            if (displayName) {
                welcomeUserName.textContent = window.t
                    ? window.t('welcome_user_greeting', { name: displayName })
                    : `Witaj, ${displayName}!`;
            } else {
                welcomeUserName.textContent = window.t
                    ? window.t('welcome_title')
                    : 'Witaj!';
            }
        }
        if (welcomeSubtitle && window.t) {
            welcomeSubtitle.textContent = window.t('welcome_subtitle');
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
                checkAndAutoShowSuggestions();
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
        if (activeTutorialSteps && currentTutorialStepIdx < activeTutorialSteps.length) {
            renderActiveTutorialStep(currentTutorialStepIdx);
        }
        if (state && state.map) {
            google.maps.event.trigger(state.map, 'resize');
        }
    });

    window.addEventListener('scroll', () => {
        if (activeTutorialSteps && currentTutorialStepIdx < activeTutorialSteps.length) {
            renderActiveTutorialStep(currentTutorialStepIdx);
        }
    }, true);

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
                currentDisplayName = displayName;
                document.getElementById('user-display-name').textContent = displayName ? displayName.charAt(0).toUpperCase() : 'U';
                updateChatWelcomeGreeting(displayName);
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
function park4nightBadgeHtml(camp) {
    if (!camp || camp.source !== 'park4night') return '';
    const p4nLabel = escapeCampText(camp.spot_type ? `park4night · ${camp.spot_type}` : 'park4night');
    const p4nId = String(camp.place_id || '').startsWith('p4n:') ? String(camp.place_id).slice(4) : '';
    const rawUrl = camp.external_url || (/^\d+$/.test(p4nId) ? `https://park4night.com/en/place/${p4nId}` : '');
    const p4nUrl = /^https:\/\/([a-z0-9-]+\.)*park4night\.com\//i.test(rawUrl) ? escapeCampText(rawUrl) : '';
    return p4nUrl
        ? `<a class="camping-badge p4n-badge" href="${p4nUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="background:#FFF3E0; color:#E65100; padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none;">🚐 ${p4nLabel}</a>`
        : `<span class="camping-badge p4n-badge" style="background:#FFF3E0; color:#E65100; padding:3px 8px; border-radius:4px; font-size:11px;">🚐 ${p4nLabel}</span>`;
}

function escapeCampText(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

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
            const searchRes = await apiCall('search_campings', { lat: lastWp.lat, lng: lastWp.lng, radius_km: 40, limit: 6 });
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

        const rawPhotoUrl = (camp.photos && camp.photos.length > 0) ? camp.photos[0] : (camp.photo_url || null);
        const hasRealPhoto = Boolean(rawPhotoUrl);
        const photoSrc = hasRealPhoto ? rawPhotoUrl : CAMPING_PLACEHOLDER_URL;
        const previewBadge = !hasRealPhoto ? `<span class="photo-placeholder-badge">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : '';
        const photoHtml = `
            <div class="camping-card-img-wrap">
                <img src="${escapeCampText(photoSrc)}" alt="${escapeCampText(camp.name)}" onerror="this.onerror=null; this.src='${CAMPING_PLACEHOLDER_URL}';">
                ${previewBadge}
            </div>
        `;

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
        badgesHtml += park4nightBadgeHtml(camp);
        badgesHtml += '</div>';

        const selectedBadgeText = window.t ? window.t('camping_selected_badge') : '✓ Wybrany';
        const selectBtnText = window.t ? window.t('camping_select_btn') : 'Wybierz ten kemping';
        const badgeTop = isSelected ? `<div class="camping-card-badge-top">${selectedBadgeText}</div>` : '';
        const btnDisplay = isSelected ? selectedBadgeText : selectBtnText;

        card.innerHTML = `
            ${badgeTop}
            ${photoHtml}
            <div class="camping-card-header">
                <h4>${escapeCampText(camp.name)}</h4>
                ${camp.address ? `<div style="font-size:0.8rem; color:#718096; margin-bottom:4px;">📍 ${escapeCampText(camp.address)}</div>` : ''}
                <div class="camping-card-meta">
                    ${camp.rating ? `<span class="camping-card-rating">⭐ ${camp.rating} ${camp.review_count ? `(${camp.review_count})` : ''}</span>` : ''}
                    ${camp.cost_per_night_eur ? `<span class="camping-card-cost">€${camp.cost_per_night_eur}/noc</span>` : (camp.price_info ? `<span class="camping-card-cost">${escapeCampText(camp.price_info)}</span>` : '')}
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

    // Collect any attractions saved in this day's schedule waypoints directly
    const activeTrip = tripData || state.currentTrip;
    const currentDaySched = (activeTrip?.daily_schedules || []).find(d => d.day_number === dayNumber);
    const savedDayWaypoints = (currentDaySched?.waypoints || []).filter(wp => wp.type === 'attraction').map(wp => ({
        name: wp.label || wp.name || 'Atrakcja',
        place_id: wp.place_id,
        lat: wp.lat,
        lng: wp.lng,
        address: wp.address || '',
        rating: wp.rating,
        photo_url: wp.photo_url,
        category_label: wp.category_label || 'Atrakcja',
        emoji: wp.emoji || '⭐',
        color: wp.color || '#F9A825',
        day_number: dayNumber,
        is_in_route: true
    }));

    let allAttrs = state.rawAttractionsList || [];

    // If attractions list is empty, attempt to fetch attractions for active trip
    const tripId = activeTrip && activeTrip.trip && activeTrip.trip.id;

    if (allAttrs.length === 0 && tripId) {
        try {
            const res = await fetch(`${API_BASE}/api/attractions/${tripId}?limit_per_day=8&sample_every_km=80`);
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

    // Merge saved day attractions with suggestions for this day
    const dayAttrs = [...savedDayWaypoints];
    allAttrs.filter(a => a.day_number === dayNumber).forEach(a => {
        const already = dayAttrs.some(d =>
            (a.place_id && d.place_id && a.place_id === d.place_id) ||
            (a.name && d.name && a.name.trim().toLowerCase() === d.name.trim().toLowerCase())
        );
        if (!already) {
            dayAttrs.push(a);
        }
    });

    // Sort day attractions primarily by number of reviews (user_ratings_total) descending,
    // with rating as secondary tiebreaker.
    dayAttrs.sort((a, b) => {
        const revA = parseInt(a.user_ratings_total || a.review_count) || 0;
        const revB = parseInt(b.user_ratings_total || b.review_count) || 0;
        if (revB !== revA) return revB - revA;
        const rA = parseFloat(a.rating) || 0;
        const rB = parseFloat(b.rating) || 0;
        return rB - rA;
    });

    // Cap to 8 attractions to fill 2 full rows evenly (4 columns x 2 rows)
    const displayAttrs = dayAttrs.slice(0, 8);

    if (displayAttrs.length === 0) {
        grid.innerHTML = `<div style="grid-column: 1/-1; padding: 12px; text-align: center; color: #718096; font-size: 0.88rem;">Brak wykrytych dodatkowych atrakcji dla tego odcinka trasy.</div>`;
        return;
    }

    displayAttrs.forEach(attr => {
        const card = document.createElement('div');
        card.className = 'top-attraction-item-card';
        card.style.background = '#F8FAFC';
        card.style.border = '1px solid #E2E8F0';
        card.style.padding = '10px';
        card.style.borderRadius = '10px';

        const hasRealPhoto = Boolean(attr.photo_url);
        const photoSrc = hasRealPhoto ? attr.photo_url : ATTRACTION_PLACEHOLDER_URL;
        const previewBadge = !hasRealPhoto ? `<span class="photo-placeholder-badge" style="font-size:0.62rem; padding:1px 5px; bottom:4px; right:4px;">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : '';
        const photoHtml = `
            <div class="top-attraction-img-wrap" style="height:100px; border-radius:6px; overflow:hidden; margin-bottom:6px; position:relative;">
                <img src="${photoSrc}" alt="${attr.name}" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.onerror=null; this.src='${ATTRACTION_PLACEHOLDER_URL}';">
                ${previewBadge}
            </div>
        `;

        const revCount = (attr.user_ratings_total || attr.review_count);
        const revCountHtml = revCount ? ` <span style="color:#718096; font-size:0.75rem; font-weight:normal;">(${parseInt(revCount).toLocaleString()})</span>` : '';
        const ratingHtml = attr.rating ? `<span style="color:#D69E2E; font-weight:700; font-size:0.82rem;">⭐ ${attr.rating}${revCountHtml}</span>` : '';
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

        const rawPhotoUrl = (camp.photos && camp.photos.length > 0) ? camp.photos[0] : (camp.photo_url || null);
        const hasRealPhoto = Boolean(rawPhotoUrl);
        const photoSrc = hasRealPhoto ? rawPhotoUrl : CAMPING_PLACEHOLDER_URL;
        const previewBadge = !hasRealPhoto ? `<span class="photo-placeholder-badge">${window.t ? window.t('photo_preview_tag') : '📷 Podgląd'}</span>` : '';
        const photoHtml = `
            <div class="camping-card-img-wrap">
                <img src="${escapeCampText(photoSrc)}" alt="${escapeCampText(camp.name)}" onerror="this.onerror=null; this.src='${CAMPING_PLACEHOLDER_URL}';">
                ${previewBadge}
            </div>
        `;

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
        badgesHtml += park4nightBadgeHtml(camp);
        badgesHtml += '</div>';

        card.innerHTML = `
            ${photoHtml}
            <div class="camping-card-header">
                <h4>${escapeCampText(camp.name)}</h4>
                ${camp.address ? `<div style="font-size:0.8rem; color:#718096; margin-bottom:4px;">📍 ${escapeCampText(camp.address)}</div>` : ''}
                <div class="camping-card-meta">
                    ${camp.rating ? `<span class="camping-card-rating">⭐ ${camp.rating} ${camp.review_count ? `(${camp.review_count})` : ''}</span>` : ''}
                    ${camp.cost_per_night_eur ? `<span class="camping-card-cost">€${camp.cost_per_night_eur}/noc</span>` : (camp.price_info ? `<span class="camping-card-cost">${escapeCampText(camp.price_info)}</span>` : '')}
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

// ═══════════════════════════════════════════════════════════════════
// Suggestive Travel Inspirations (Middle-Aged Focus + RAG)
// ═══════════════════════════════════════════════════════════════════

let isSuggestionsLoading = false;
let currentSuggestionsList = [];
let currentSuggestionsLang = null;
let currentSuggestionsFilter = 'all';
let currentDurationFilter = 'all';

function getAppLanguage() {
    if (window.vwI18n) {
        if (typeof window.vwI18n.getLanguage === 'function') return window.vwI18n.getLanguage();
        if (typeof window.vwI18n.getCurrentLanguage === 'function') return window.vwI18n.getCurrentLanguage();
        if (window.vwI18n.currentLang) return window.vwI18n.currentLang;
    }
    return localStorage.getItem('vw_app_lang') || 'pl';
}

const CLIENT_FALLBACK_SUGGESTIONS = {
    pl: [
        {
            id: 'curated-lakes-pl',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 3,
            title: 'Pojezierze Drawskie & Czyste Jeziora',
            subtitle: 'Krystaliczne tafle wód, leśne dukty na rowery, cisza i kameralne parcele nad brzegiem jeziora.',
            image_url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Czyste Jeziora', 'Spokój', 'E-Bike', 'Cisza'],
            prompt: 'Zaplanuj 3-dniowy relaksujący weekend camperem VW California na Pojezierzu Drawskim lub Kaszubach z kempingami nad samą wodą.',
            badge: 'Natura i Spokój',
            rag_matched: false,
            rag_reason: 'Idealny weekendowy dystans blisko natury, z dala od zgiełku i bez męczącej jazdy.',
            vw_highlights: ['Parcela nad jeziorem', 'Krótki dojazd']
        },
        {
            id: 'curated-wine-pl',
            category: 'wine_gastronomy',
            duration_category: 'week',
            duration_days: 7,
            title: 'Szlak Winnic & Agroturystyka',
            subtitle: 'Malownicze wzgórza, lokalne winnice, regionalne przysmaki i spokojne parcele z przyłączem 230V.',
            image_url: 'https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Slow Travel', 'Winnice', 'Prąd 230V', 'Lokalna Kuchnia'],
            prompt: 'Chciałbym zaplanować spokojną, malowniczą trasę na 7 dni camperem VW California przez toskańskie lub morawskie winnice. Zależy mi na wizytach w lokalnych winnicach, dobrej kuchni i komfortowych kempingach ze stałym przyłączem prądu.',
            badge: 'Polecane dla Koneserów',
            rag_matched: false,
            rag_reason: 'Polecane, ponieważ cenisz degustacje lokalnych win i komfortowe parcele z prądem 230V.',
            vw_highlights: ['Przyłącze 230V CEE', 'Malownicza trasa']
        },
        {
            id: 'curated-castles-pl',
            category: 'castles_culture',
            duration_category: 'week',
            duration_days: 6,
            title: 'Dolina Zamków & Szlak Historii',
            subtitle: 'Średniowieczne twierdze, urokliwe doliny rzek, klimatyczne miasteczka i wygodne postoje.',
            image_url: 'https://images.unsplash.com/photo-1524397076567-5c756944336c?auto=format&fit=crop&w=1000&q=80',
            tags: ['Zabytki & Kultura', 'Dolina Rzeki', 'Zamki', 'Cień i Zieleń'],
            prompt: 'Zaplanuj 6-dniową podróż szlakiem zamków i historycznych miast (np. Dolina Loary lub Szlak Orlich Gniazd/Morawy). Komfortowe kempingi, ciekawe punkty widokowe i bez pośpiechu.',
            badge: 'Kultura i Historia',
            rag_matched: false,
            rag_reason: 'Odpowiada Twoim upodobaniom do zwiedzania zabytków bez zbędnego pośpiechu.',
            vw_highlights: ['Zabytki i kultura', 'Czyste sanitariaty']
        },
        {
            id: 'curated-coastal-pl',
            category: 'coastal_calm',
            duration_category: 'expedition',
            duration_days: 10,
            title: 'Nadmorski Spokój & Sosnowe Lasy',
            subtitle: 'Szum fal, trasy spacerowe wśród sosnowych lasów i relaks na kempingach z dala od zgiełku.',
            image_url: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80',
            tags: ['Bryza Morska', 'Sosnowy Las', 'Strefa Ciszy', 'Widok na Morze'],
            prompt: 'Chcę zaplanować 10-dniowy spokojny wyjazd nad morze (Adriatyk lub Bałtyk). Kluczowe są dla mnie zacienione parcele wśród drzew, cisza wieczorem i wysoki standard sanitarny.',
            badge: 'Morski Relaks',
            rag_matched: false,
            rag_reason: 'Wybrane ze względu na preferencję ciszy i relaksu w otoczeniu nadmorskiej przyrody.',
            vw_highlights: ['Zacieniona parcela', 'Cisza nocna']
        },
        {
            id: 'curated-mountains-pl',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 4,
            title: 'Karkonosze & Dolina Pałaców',
            subtitle: 'Malownicze przełęcze, widok na Śnieżkę, komfortowe kempingi z widokiem na góry i prądem 230V.',
            image_url: 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1000&q=80',
            tags: ['Góry', 'Karkonosze', 'Widokowa Trasa', 'Prąd 230V'],
            prompt: 'Zaplanuj 4-dniowy weekendowy wypad camperem VW California w Karkonosze i Kotlinę Jeleniogórską z kempingami z prądem 230V i pięknym widokiem na pasma górskie.',
            badge: 'Górska Przygoda',
            rag_matched: false,
            rag_reason: 'Krótki dojazd camperem, widokowe szlaki i sprawdzone bazy kempingowe.',
            vw_highlights: ['Widok na góry', 'Prąd 230V']
        },
        {
            id: 'curated-alps-pl',
            category: 'lakes_mountains',
            duration_category: 'expedition',
            duration_days: 12,
            title: 'Wielka Pętla Alpejska & Dolomity',
            subtitle: 'Kultowe przełęcze, krystaliczne jeziora i najwyższej klasy parcele kempingowe z widokiem na szczyty.',
            image_url: 'https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?auto=format&fit=crop&w=1000&q=80',
            tags: ['Wyprawa Alpejska', 'Przełęcze', 'Dolomity', 'Komfort'],
            prompt: 'Zaplanuj 12-dniową widokową wyprawę camperem VW California przez Alpy i Dolomity ze spokojnym tempem jazdy do 3.5h dziennie i najlepszymi kempingami.',
            badge: 'Alpejska Wyprawa',
            rag_matched: false,
            rag_reason: 'Idealne na dłuższą wyprawę z niezapomnianymi panoramami i pełną wygodą postoju.',
            vw_highlights: ['Przełęcze widokowe', 'Pełna infrastruktura']
        }
    ],
    de: [
        {
            id: 'curated-lakes-de',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 4,
            title: 'Alpenseen & Panoramarouten',
            subtitle: 'Kristallklare Seen, sanfte Uferwege, komfortable Stellplätze mit Seeblick und Panoramapässe.',
            image_url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Alpenseen', 'E-Bike', 'Ruhe', 'Komfort-Parzelle'],
            prompt: 'Ich möchte eine 4-tägige Panoramatour um die schönsten Kärntner oder oberitalienischen Seen unternehmen. Ruhiges Fahrtempo, saubere Sanitäranlagen und Parzellen direkt am Wasser.',
            badge: 'Entspannung & Natur',
            rag_matched: false,
            rag_reason: 'Passend zu Deiner Vorliebe für ruhige Seen und erholsame Stunden am Wasser.',
            vw_highlights: ['Stellplatz am See', 'Ruhiges Tempo']
        },
        {
            id: 'curated-wine-de',
            category: 'wine_gastronomy',
            duration_category: 'week',
            duration_days: 7,
            title: 'Toskana & Weinstraßen im Chianti',
            subtitle: 'Malerische Hügellandschaften, Weingüter, lokale Küche und ruhige Campingplätze mit 230V-Strom.',
            image_url: 'https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Slow Travel', 'Weingüter', 'Landstrom 230V', 'Genuss'],
            prompt: 'Plane für mich eine entspannte 7-tägige Tour mit dem VW California durch die Toskana mit Fokus auf Weinstraßen, kulinarische Zwischenstopps und komfortable Campingplätze mit Stromanschluss.',
            badge: 'Beliebt bei Genießern',
            rag_matched: false,
            rag_reason: 'Empfohlen, weil Du regionale Weinproben und vollausgestattete Stellplätze schätzt.',
            vw_highlights: ['CEE-Landstrom', 'Panoramaroute']
        },
        {
            id: 'curated-castles-de',
            category: 'castles_culture',
            duration_category: 'week',
            duration_days: 6,
            title: 'Schlösser der Loire & Flusstäler',
            subtitle: 'Kulturelle Schätze, geschichtsträchtige Städtchen und idyllische Campingplätze im Grünen.',
            image_url: 'https://images.unsplash.com/photo-1524397076567-5c756944336c?auto=format&fit=crop&w=1000&q=80',
            tags: ['Kultur & Geschichte', 'Flusstal', 'Schlösser', 'Schattenplätze'],
            prompt: 'Plane eine 6-tägige Kulturroute entlang der Loire zu den schönsten Schlössern und Gärten. Moderate Tagesetappen von maximal 3 Stunden Fahrt.',
            badge: 'Kultur & Geschichte',
            rag_matched: false,
            rag_reason: 'Entspricht Deinem Interesse an historischen Schlössern und entspanntem Reisen.',
            vw_highlights: ['Kulturroute', 'Max 3h Fahrtzeit']
        },
        {
            id: 'curated-coastal-de',
            category: 'coastal_calm',
            duration_category: 'expedition',
            duration_days: 10,
            title: 'Kiefernwälder & Meeresbrise',
            subtitle: 'Meeresrauschen, Spazierwege unter Pinien und geruhsame Stellplätze abseits des Trubels.',
            image_url: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80',
            tags: ['Meeresbrise', 'Pinienwald', 'Ruhezone', 'Meerblick'],
            prompt: 'Plane eine 10-tägige ruhige Reise an die Mittelmeer- oder Adriaküste mit schattigen Plätzen unter Pinien und hohem Sanitärstandard.',
            badge: 'Küstenerholung',
            rag_matched: false,
            rag_reason: 'Ausgewählt für eine entschleunigte längere Auszeit mit Schatten und Meeresrauschen.',
            vw_highlights: ['Schattenstellplatz', 'Nachtruhe']
        },
        {
            id: 'curated-blackforest-de',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 3,
            title: 'Schwarzwald & Schluchsee Panorama',
            subtitle: 'Dichte Tannenwälder, malerische Seerundwege und ruhige Stellplätze mit 230V-Strom.',
            image_url: 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1000&q=80',
            tags: ['Schwarzwald', 'Natur', 'Seeblick', 'Ruhe'],
            prompt: 'Plane ein 3-tägiges entspanntes Wochenende mit dem VW California im Schwarzwald und am Schluchsee mit ruhigen Stellplätzen direkt am Wasser.',
            badge: 'Schwarzwald-Idylle',
            rag_matched: false,
            rag_reason: 'Kurze Anfahrt, dichte Wälder und voll ausgestattete Stellplätze für ein Wochenende.',
            vw_highlights: ['Landstrom 230V', 'Seeufer']
        },
        {
            id: 'curated-alps-de',
            category: 'lakes_mountains',
            duration_category: 'expedition',
            duration_days: 12,
            title: 'Große Alpenüberquerung & Dolomiten',
            subtitle: 'Spektakuläre Pässe, Bergseen und hochklassige Stellplätze für den VW California.',
            image_url: 'https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?auto=format&fit=crop&w=1000&q=80',
            tags: ['Alpenpässe', 'Dolomiten', 'Slow Travel', 'Komfort'],
            prompt: 'Plane eine 12-tägige Panoramatour mit dem VW California durch die Alpen und Dolomiten mit maximal 3 Stunden täglicher Fahrzeit und hochwertigen Campingplätzen.',
            badge: 'Alpen-Expedition',
            rag_matched: false,
            rag_reason: 'Ausgewählt für eine traumhafte große Reise mit atemberaubender Bergkulisse.',
            vw_highlights: ['Alpenpanorama', 'CEE-Landstrom']
        }
    ],
    en: [
        {
            id: 'curated-lakes-en',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 4,
            title: 'Alpine Lakes & Panoramic Byways',
            subtitle: 'Crystal waters, easy lakeshore promenades, and serene pitches overlooking alpine peaks.',
            image_url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Alpine Lakes', 'Scenic Byways', 'E-Bike', 'Peaceful'],
            prompt: 'I want a 4-day scenic tour around picturesque alpine lakes. Moderate driving pace of max 3 hours per day, quiet campsites with lake views and clean facilities.',
            badge: 'Nature & Serenity',
            rag_matched: false,
            rag_reason: 'Tailored to your preference for peaceful lakeside camping and gentle trails.',
            vw_highlights: ['Lakefront Pitch', 'Moderate Driving Pace']
        },
        {
            id: 'curated-wine-en',
            category: 'wine_gastronomy',
            duration_category: 'week',
            duration_days: 7,
            title: 'Tuscan Wine Trails & Slow Food',
            subtitle: 'Gentle rolling hills, artisan vineyards, local cuisine, and quiet pitches with 230V shore power.',
            image_url: 'https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb?auto=format&fit=crop&w=1000&q=80',
            tags: ['Slow Travel', 'Vineyards', '230V Power', 'Artisan Food'],
            prompt: 'Plan a relaxing 7-day road trip through Tuscany for my VW California, focusing on scenic wine routes, local culinary stops, and comfortable campsites.',
            badge: 'Scenic & Gourmet',
            rag_matched: false,
            rag_reason: 'Recommended because you appreciate vineyard landscapes and fully serviced pitches.',
            vw_highlights: ['230V Shore Power', 'Scenic Route']
        },
        {
            id: 'curated-castles-en',
            category: 'castles_culture',
            duration_category: 'week',
            duration_days: 6,
            title: 'Loire Valley Castles & Heritage',
            subtitle: 'Historic châteaux, quaint river valley towns, and charming shaded campsites.',
            image_url: 'https://images.unsplash.com/photo-1524397076567-5c756944336c?auto=format&fit=crop&w=1000&q=80',
            tags: ['Heritage', 'Castles', 'River Valley', 'Shaded Pitches'],
            prompt: 'Plan a 6-day heritage tour through the Loire Valley exploring historic castles and gardens. Keep daily driving under 3 hours with quality campsites.',
            badge: 'Culture & Heritage',
            rag_matched: false,
            rag_reason: 'Matches your interest in cultural exploration and serene evening stays.',
            vw_highlights: ['Heritage Stops', 'Comfortable Pitches']
        },
        {
            id: 'curated-coastal-en',
            category: 'coastal_calm',
            duration_category: 'expedition',
            duration_days: 10,
            title: 'Coastal Pines & Sea Breeze',
            subtitle: 'Unwind by the Mediterranean coast, pine-shaded tranquil camper spots, away from crowded resorts.',
            image_url: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80',
            tags: ['Sea Breeze', 'Pine Forests', 'Tranquility', 'Ocean View'],
            prompt: 'Plan a 10-day peaceful coastal journey along the Adriatic or Mediterranean coast. Prioritize shaded campsites under pine trees, evening silence, and full amenities.',
            badge: 'Coastal Relaxation',
            rag_matched: false,
            rag_reason: 'Selected for an unhurried longer journey with coastal shade and tranquility.',
            vw_highlights: ['Shaded Pitch', 'Tranquil Evening']
        },
        {
            id: 'curated-blackforest-en',
            category: 'lakes_mountains',
            duration_category: 'weekend',
            duration_days: 3,
            title: 'Black Forest & Lake Schluchsee',
            subtitle: 'Evergreen woodlands, scenic lakeshore byways, and peaceful camper pitches with 230V power.',
            image_url: 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1000&q=80',
            tags: ['Black Forest', 'Lakeside', '230V Power', 'Tranquil'],
            prompt: 'Plan a relaxing 3-day weekend road trip for my VW California to the Black Forest and Lake Schluchsee with peaceful waterfront campsites.',
            badge: 'Woodland Escape',
            rag_matched: false,
            rag_reason: 'Short driving distance, crisp pine air, and full amenities for a weekend getaway.',
            vw_highlights: ['Lakeside Pitch', '230V Shore Power']
        },
        {
            id: 'curated-alps-en',
            category: 'lakes_mountains',
            duration_category: 'expedition',
            duration_days: 12,
            title: 'Grand Alpine Passes & Dolomites',
            subtitle: 'Iconic mountain passes, crystal alpine lakes, and premium pitches tailored for VW California.',
            image_url: 'https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?auto=format&fit=crop&w=1000&q=80',
            tags: ['Alpine Expedition', 'Mountain Passes', 'Dolomites', 'Slow Travel'],
            prompt: 'Plan a 12-day scenic grand tour through the Alps and Dolomites for my VW California with daily driving under 3.5 hours and top-tier campsites.',
            badge: 'Alpine Grand Tour',
            rag_matched: false,
            rag_reason: 'Selected for an unhurried, epic mountain road trip with breathtaking vistas.',
            vw_highlights: ['Mountain Passes', 'Full Amenities']
        }
    ]
};

function initTravelSuggestionsControls() {
    const container = document.getElementById('suggestions-duration-pills');
    if (!container) return;
    const pills = container.querySelectorAll('.duration-pill');
    pills.forEach(pill => {
        pill.addEventListener('click', (e) => {
            e.preventDefault();
            const dur = pill.getAttribute('data-duration') || 'all';
            if (dur === currentDurationFilter) return;
            currentDurationFilter = dur;
            pills.forEach(p => {
                const isActive = p === pill;
                p.classList.toggle('active', isActive);
                p.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            openTravelSuggestionsModal(true);
        });
    });
}

async function openTravelSuggestionsModal(forceRefresh = false) {
    const modal = document.getElementById('travel-suggestions-modal');
    const grid = document.getElementById('travel-suggestions-grid');
    if (!modal || !grid) return;

    modal.style.display = 'flex';

    // Must be obtained first before checking cache or rendering
    const currentLang = getAppLanguage();

    if (currentSuggestionsList.length > 0 && 
        currentSuggestionsLang === currentLang && 
        currentSuggestionsFilter === currentDurationFilter && 
        !forceRefresh) {
        renderTravelSuggestions(currentSuggestionsList);
        return;
    }

    renderSuggestionSkeletons(grid);

    isSuggestionsLoading = true;

    // Abort controller with 9.5 second timeout to allow dynamic AI generation
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 9500);

    try {
        const queryParams = new URLSearchParams({
            lang: currentLang,
            count: '3',
            duration: currentDurationFilter
        });
        if (state.userLocation && state.userLocation.name) {
            queryParams.set('location', state.userLocation.name);
            if (state.userLocation.city) queryParams.set('city', state.userLocation.city);
            if (state.userLocation.country) queryParams.set('country', state.userLocation.country);
        }
        const response = await fetch(`/api/travel_suggestions?${queryParams.toString()}`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const data = await response.json();

        if (data.status === 'success' && data.suggestions && data.suggestions.length > 0) {
            currentSuggestionsList = data.suggestions;
            currentSuggestionsLang = currentLang;
            currentSuggestionsFilter = currentDurationFilter;
            renderTravelSuggestions(currentSuggestionsList);
        } else {
            let fallbackList = [...(CLIENT_FALLBACK_SUGGESTIONS[currentLang] || CLIENT_FALLBACK_SUGGESTIONS['de'] || CLIENT_FALLBACK_SUGGESTIONS['pl'])];
            if (currentDurationFilter && currentDurationFilter !== 'all') {
                const matched = fallbackList.filter(item => item.duration_category === currentDurationFilter);
                if (matched.length > 0) fallbackList = matched;
            }
            fallbackList.sort(() => Math.random() - 0.5);
            currentSuggestionsList = fallbackList.slice(0, 3);
            currentSuggestionsLang = currentLang;
            currentSuggestionsFilter = currentDurationFilter;
            renderTravelSuggestions(currentSuggestionsList);
        }
    } catch (err) {
        console.warn('Network or timeout loading travel suggestions, using instant curated cards:', err);
        clearTimeout(timeoutId);
        let fallbackList = [...(CLIENT_FALLBACK_SUGGESTIONS[currentLang] || CLIENT_FALLBACK_SUGGESTIONS['de'] || CLIENT_FALLBACK_SUGGESTIONS['pl'])];
        if (currentDurationFilter && currentDurationFilter !== 'all') {
            const matched = fallbackList.filter(item => item.duration_category === currentDurationFilter);
            if (matched.length > 0) fallbackList = matched;
        }
        fallbackList.sort(() => Math.random() - 0.5);
        currentSuggestionsList = fallbackList.slice(0, 3);
        currentSuggestionsLang = currentLang;
        currentSuggestionsFilter = currentDurationFilter;
        renderTravelSuggestions(currentSuggestionsList);
    } finally {
        isSuggestionsLoading = false;
        const refreshBtn = document.getElementById('btn-refresh-suggestions');
        if (refreshBtn) refreshBtn.classList.remove('spinning');
    }
}

function renderSuggestionSkeletons(container) {
    container.innerHTML = `
        <div class="suggestion-card-skeleton">
            <div class="skeleton-img"></div>
            <div class="skeleton-body">
                <div class="skeleton-line skeleton-title"></div>
                <div class="skeleton-line skeleton-desc"></div>
                <div class="skeleton-line skeleton-tags"></div>
            </div>
        </div>
        <div class="suggestion-card-skeleton">
            <div class="skeleton-img"></div>
            <div class="skeleton-body">
                <div class="skeleton-line skeleton-title"></div>
                <div class="skeleton-line skeleton-desc"></div>
                <div class="skeleton-line skeleton-tags"></div>
            </div>
        </div>
        <div class="suggestion-card-skeleton">
            <div class="skeleton-img"></div>
            <div class="skeleton-body">
                <div class="skeleton-line skeleton-title"></div>
                <div class="skeleton-line skeleton-desc"></div>
                <div class="skeleton-line skeleton-tags"></div>
            </div>
        </div>
    `;
}

function renderTravelSuggestions(suggestions) {
    const grid = document.getElementById('travel-suggestions-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const currentLang = getAppLanguage();
    const ctaText = currentLang === 'de' ? 'Diese Route planen' : (currentLang === 'en' ? 'Plan this route' : 'Zaplanuj tę trasę');

    suggestions.forEach(item => {
        const card = document.createElement('div');
        card.className = `suggestion-card ${item.rag_matched ? 'rag-matched' : ''}`;

        let badgeText = item.badge;
        if (item.rag_matched && (!badgeText || badgeText.includes('Dopasowane') || badgeText.includes('Auf Dich') || badgeText.includes('Tailored'))) {
            badgeText = window.t ? window.t('suggestions_badge_matched') : (currentLang === 'de' ? 'Auf Dich abgestimmt ✨' : (currentLang === 'en' ? 'Tailored to you ✨' : 'Dopasowane do Ciebie ✨'));
        }
        const badgeHtml = badgeText
            ? `<span class="suggestion-card-badge">${badgeText}</span>`
            : '';

        const daysWord = item.duration_days === 1
            ? (window.t ? window.t('suggestions_days_badge_singular') : 'dzień')
            : (window.t ? window.t('suggestions_days_badge') : 'dni');
        const durationBadgeHtml = item.duration_days
            ? `<span class="suggestion-card-duration-badge">⏱️ ${item.duration_days} ${daysWord}</span>`
            : '';

        let ragReasonHtml = '';
        if (item.rag_reason) {
            const prefix = item.rag_matched
                ? (window.t ? window.t('suggestions_rag_reason_prefix') : 'Dlaczego to polecamy')
                : (window.t ? window.t('suggestions_why_text') : 'Warto wiedzieć');
            const icon = item.rag_matched ? '✨' : '💡';
            ragReasonHtml = `
                <div class="suggestion-card-rag-reason">
                    <span class="rag-reason-icon">${icon}</span>
                    <div class="rag-reason-text">
                        <span class="rag-reason-prefix">${prefix}:</span>
                        <span>${item.rag_reason}</span>
                    </div>
                </div>
            `;
        }

        const tagsHtml = (item.tags || [])
            .map(tag => `<span class="suggestion-tag">${tag}</span>`)
            .join('');

        card.innerHTML = `
            <div class="suggestion-card-image-wrap">
                <img src="${item.image_url}" alt="${item.title}" class="suggestion-card-img" loading="lazy" onerror="this.src='/static/assets/attraction_placeholder.svg'">
                ${badgeHtml}
                ${durationBadgeHtml}
            </div>
            <div class="suggestion-card-body">
                <h3 class="suggestion-card-title">${item.title}</h3>
                <p class="suggestion-card-desc">${item.subtitle}</p>
                ${ragReasonHtml}
                <div class="suggestion-card-tags">
                    ${tagsHtml}
                </div>
                <div class="suggestion-card-cta">
                    <span>${ctaText}</span>
                    <span class="suggestion-card-arrow">&rarr;</span>
                </div>
            </div>
        `;

        card.addEventListener('click', () => {
            selectTravelSuggestion(item);
        });

        grid.appendChild(card);
    });
}

function buildEnrichedSuggestionPrompt(suggestion) {
    if (!suggestion) return '';

    const lang = getAppLanguage();
    const isLocActive = state.locationEnabled && state.userLocation;
    const startCity = isLocActive
        ? (state.userLocation.city || state.userLocation.name || '').trim()
        : '';

    const days = suggestion.duration_days || (
        suggestion.duration_category === 'weekend' ? 3 :
        suggestion.duration_category === 'week' ? 7 :
        suggestion.duration_category === 'expedition' ? 10 : 3
    );

    const title = (suggestion.title || '').trim();
    const subtitle = (suggestion.subtitle || '').trim();
    const highlights = (suggestion.vw_highlights && suggestion.vw_highlights.length > 0)
        ? suggestion.vw_highlights.join(', ')
        : '';

    // Check if the prompt already contains start city (if active) and explicit day count
    let basePrompt = (suggestion.prompt || '').trim();
    const hasOrigin = !startCity || basePrompt.toLowerCase().includes(startCity.toLowerCase());
    const hasDays = basePrompt.toLowerCase().includes(`${days}-d`) ||
                    basePrompt.toLowerCase().includes(`${days} d`) ||
                    basePrompt.toLowerCase().includes(`${days} tag`) ||
                    basePrompt.toLowerCase().includes(`${days}-tag`) ||
                    basePrompt.toLowerCase().includes(`${days}-day`) ||
                    basePrompt.toLowerCase().includes(`${days} day`);

    // If the prompt already has origin, days and is complete, use it
    if (basePrompt && hasOrigin && hasDays && basePrompt.length >= 35) {
        return basePrompt;
    }

    if (lang === 'de') {
        const originClause = (isLocActive && startCity) ? ` mit Start ab: ${startCity}` : '';
        let text = `Plane für mich eine ${days}-tägige Reise mit dem VW California${originClause}. Ziel: ${title}.`;
        if (subtitle) text += ` ${subtitle}`;
        if (highlights) text += ` Wichtig sind mir: ${highlights}.`;
        return text;
    } else if (lang === 'en') {
        const originClause = (isLocActive && startCity) ? ` starting from: ${startCity}` : '';
        let text = `Plan a ${days}-day road trip for my VW California${originClause}. Destination: ${title}.`;
        if (subtitle) text += ` ${subtitle}`;
        if (highlights) text += ` Preferences: ${highlights}.`;
        return text;
    } else {
        // Polish (default)
        const originClause = (isLocActive && startCity) ? ` ze startem z: ${startCity}` : '';
        let text = `Zaplanuj dla mnie ${days}-dniowy wyjazd camperem VW California${originClause}. Cel: ${title}.`;
        if (subtitle) text += ` ${subtitle}`;
        if (highlights) text += ` Zależy mi na: ${highlights}.`;
        return text;
    }
}
window.buildEnrichedSuggestionPrompt = buildEnrichedSuggestionPrompt;

async function selectTravelSuggestion(suggestion) {
    const modal = document.getElementById('travel-suggestions-modal');
    if (modal) modal.style.display = 'none';

    sessionStorage.setItem('vw_suggestions_shown', 'true');

    // Notify backend to record this choice in RAG memory
    try {
        fetch('/api/travel_suggestions/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ suggestion: suggestion })
        }).catch(err => console.warn('Could not record suggestion selection in RAG:', err));
    } catch (e) {
        console.warn('RAG selection record error:', e);
    }

    // Trigger AI trip planner with the enriched suggestion prompt (including days and starting location)
    const prompt = buildEnrichedSuggestionPrompt(suggestion);
    if (prompt && typeof sendMessage === 'function') {
        if (typeof switchView === 'function') switchView('chat');
        sendMessage(prompt);
    }
}

function closeTravelSuggestionsModal() {
    const modal = document.getElementById('travel-suggestions-modal');
    if (modal) modal.style.display = 'none';
    sessionStorage.setItem('vw_suggestions_shown', 'true');
    const input = document.getElementById('chat-input');
    if (input) input.focus();
}

function checkAndAutoShowSuggestions() {
    if (sessionStorage.getItem('vw_suggestions_shown') === 'true') {
        return;
    }
    const welcomeOverlay = document.getElementById('welcome-overlay');
    if (welcomeOverlay && welcomeOverlay.style.display !== 'none' && !welcomeOverlay.classList.contains('fade-out')) {
        return;
    }
    const tutOverlay = document.getElementById('tutorial-overlay');
    if (tutOverlay && tutOverlay.style.display === 'block') {
        return;
    }
    const messagesEl = document.getElementById('chat-messages');
    const userMessages = messagesEl ? messagesEl.querySelectorAll('.message.user') : [];
    if (userMessages.length > 0) {
        return;
    }

    openTravelSuggestionsModal();
}

window.openTravelSuggestionsModal = openTravelSuggestionsModal;
window.closeTravelSuggestionsModal = closeTravelSuggestionsModal;
window.checkAndAutoShowSuggestions = checkAndAutoShowSuggestions;
window.initTravelSuggestionsControls = initTravelSuggestionsControls;
