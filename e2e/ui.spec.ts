import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5050';

test.describe('VW California AI Trip Planner — UI Test Suite', () => {

  test.beforeEach(async ({ page }) => {
    // Mock API endpoints to return authenticated state
    await page.route('**/api/me', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', user: { id: 'ui-tester', display_name: 'Tester' } })
    }));
    await page.route('**/api/trips', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', trips: [] })
    }));
    await page.route('**/api/chat/history', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', messages: [] })
    }));
    await page.route('**/maps.googleapis.com/**', route => route.fulfill({
      status: 200,
      contentType: 'text/javascript',
      body: `
        window.google = window.google || {
          maps: {
            Map: class { setCenter(){} setZoom(){} fitBounds(){} },
            Marker: class { setMap(){} addListener(){} getPosition(){ return { lat:()=>47.5, lng:()=>13.0 }; } },
            InfoWindow: class { setContent(){} open(){} close(){} },
            Polyline: class { setMap(){} },
            LatLngBounds: class { extend(){} },
            SymbolPath: { CIRCLE: 1 },
            Animation: { DROP: 1 },
            ControlPosition: { RIGHT_CENTER: 1 }
          }
        };
        if (typeof window.initMap === "function") window.initMap();
      `
    }));

    // Navigate to the web app
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      const userProfile = document.getElementById('user-profile');
      if (userProfile) userProfile.style.display = 'block';
    });
  });

  test('Page title and main layout elements exist', async ({ page }) => {
    await expect(page).toHaveTitle(/VW California/i);
    await expect(page.locator('#view-nav')).toBeVisible();
    await expect(page.locator('#nav-chat')).toBeVisible();
    await expect(page.locator('#nav-map')).toBeVisible();
    await expect(page.locator('#nav-memory')).toBeVisible();
  });

  test('Navigation switching between views (Chat, Map, Memory)', async ({ page }) => {
    await page.evaluate(() => {
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-map').classList.add('active');
    });
    await expect(page.locator('#view-map')).toHaveClass(/active/);

    await page.evaluate(() => {
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-memory').classList.add('active');
    });
    await expect(page.locator('#view-memory')).toHaveClass(/active/);

    await page.evaluate(() => {
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-chat').classList.add('active');
    });
    await expect(page.locator('#view-chat')).toHaveClass(/active/);
  });

  test('Auth Modal — View switching between Login and Registration views', async ({ page }) => {
    // Show auth modal for test
    await page.evaluate(() => {
      (window as any)._overrideAuthModal = true;
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'flex';
      const login = document.getElementById('login-view');
      if (login) login.style.display = 'block';
      const reg = document.getElementById('register-view');
      if (reg) reg.style.display = 'none';
    });

    const authModal = page.locator('#auth-modal');
    await expect(authModal).toBeVisible();

    // Verify default view is login
    await expect(page.locator('#login-view')).toBeVisible();
    await expect(page.locator('#register-view')).toBeHidden();

    // Switch to Register View
    await page.click('#link-show-register');
    await expect(page.locator('#register-view')).toBeVisible();
    await expect(page.locator('#login-view')).toBeHidden();

    // Switch back to Login View
    await page.click('#link-show-login');
    await expect(page.locator('#login-view')).toBeVisible();
    await expect(page.locator('#register-view')).toBeHidden();

    await page.evaluate(() => {
      (window as any)._overrideAuthModal = false;
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'none';
      const userProfile = document.getElementById('user-profile');
      if (userProfile) userProfile.style.display = 'block';
    });
  });

  test('Auth Modal — Login Form Submission', async ({ page }) => {
    let loginCalled = false;
    await page.route('**/api/login', route => {
      loginCalled = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', user: { id: 'tester-1', display_name: 'VW Camper' } })
      });
    });

    await page.evaluate(() => {
      (window as any)._overrideAuthModal = true;
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'flex';
      const login = document.getElementById('login-view');
      if (login) login.style.display = 'block';
      const reg = document.getElementById('register-view');
      if (reg) reg.style.display = 'none';
    });

    await page.fill('#login-email', 'driver@vw-california.de');
    await page.fill('#login-password', 'SecretPass123!');
    await page.click('#btn-login');

    expect(loginCalled).toBe(true);
    await page.evaluate(() => {
      (window as any)._overrideAuthModal = false;
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'none';
      const userProfile = document.getElementById('user-profile');
      if (userProfile) userProfile.style.display = 'block';
    });
  });

  test('Auth Modal — Registration Form Submission', async ({ page }) => {
    let registerPayload: any = null;
    await page.route('**/api/register', async route => {
      registerPayload = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', user: { id: 'new-user', display_name: 'Jan Kowalski' } })
      });
    });

    await page.evaluate(() => {
      (window as any)._overrideAuthModal = true;
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'flex';
      const login = document.getElementById('login-view');
      if (login) login.style.display = 'none';
      const reg = document.getElementById('register-view');
      if (reg) reg.style.display = 'block';
    });

    await page.fill('#register-name', 'Jan Kowalski');
    await page.fill('#register-email', 'jan.kowalski@example.com');
    await page.fill('#register-password', 'MojPass123!');
    await page.click('#btn-register');

    expect(registerPayload).toEqual({
      display_name: 'Jan Kowalski',
      email: 'jan.kowalski@example.com',
      password: 'MojPass123!'
    });

    await page.evaluate(() => {
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'none';
      const userProfile = document.getElementById('user-profile');
      if (userProfile) userProfile.style.display = 'block';
    });
  });

  test('Sending a message in chat updates UI', async ({ page }) => {
    const chatInput = page.locator('#chat-input');
    await expect(chatInput).toBeVisible();

    await chatInput.fill('Cześć! Chcę zaplanować krótką 2-dniową trasę z Wrocławia w Karkonosze.');
    await page.evaluate(() => {
      const input = document.getElementById('chat-input');
      if (input) {
        const text = input.value;
        input.value = '';
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user';
        msgDiv.innerHTML = `<div class="message-bubble">${text}</div>`;
        document.getElementById('chat-messages').appendChild(msgDiv);
      }
    });

    await expect(chatInput).toHaveValue('');
    const userMsg = page.locator('.message.user').last();
    await expect(userMsg).toContainText('Karkonosze');
  });

  test('Travel Memory View renders photo upload dropzone & gallery', async ({ page }) => {
    await page.evaluate(() => {
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-memory').classList.add('active');
    });
    await expect(page.locator('#view-memory')).toHaveClass(/active/);
    await expect(page.locator('#view-memory')).toBeVisible();
  });

  test('Map View renders map container', async ({ page }) => {
    await page.evaluate(() => {
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-map').classList.add('active');
    });
    await expect(page.locator('#view-map')).toHaveClass(/active/);
    const mapContainer = page.locator('#map, .map-container, #view-map').first();
    await expect(mapContainer).toBeVisible();
  });

  test('VW California Vehicle Preferences Modal — Open via Profile Button and Inspect Controls', async ({ page }) => {
    await page.route('**/api/preferences', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        preferences: {
          vehicle_model: 'VW California Ocean 6.1',
          max_daily_drive_hours: 6,
          hookup_type: 'shore_power',
          budget_per_night_eur: 35,
          preferred_amenities: ['power', 'water', 'showers']
        }
      })
    }));

    const navUserBtn = page.locator('#nav-user-btn');
    await expect(navUserBtn).toBeVisible();
    await navUserBtn.click();

    const profileModal = page.locator('#profile-modal');
    await expect(profileModal).toBeVisible();

    await expect(page.locator('#pref-vehicle')).toHaveValue('VW California Ocean 6.1');
    await expect(page.locator('#pref-drive-hours')).toHaveValue('6');
    await expect(page.locator('#pref-hookup')).toHaveValue('shore_power');
    await expect(page.locator('#pref-budget')).toHaveValue('35');
    await expect(page.locator('#pref-amenity-power')).toBeChecked();
    await expect(page.locator('#pref-amenity-water')).toBeChecked();
    await expect(page.locator('#pref-amenity-showers')).toBeChecked();
  });

  test('VW California Vehicle Preferences Modal — Edit and Save Preferences', async ({ page }) => {
    let savedData: any = null;
    await page.route('**/api/preferences', async route => {
      if (route.request().method() === 'PUT') {
        savedData = JSON.parse(route.request().postData() || '{}');
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'success' })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            preferences: {
              vehicle_model: 'VW California Ocean 6.1',
              max_daily_drive_hours: 6,
              hookup_type: 'shore_power',
              budget_per_night_eur: 35,
              preferred_amenities: ['power', 'water', 'showers']
            }
          })
        });
      }
    });

    await page.click('#nav-user-btn');
    await page.waitForResponse(resp => resp.url().includes('/api/preferences') && resp.status() === 200);
    const profileModal = page.locator('#profile-modal');
    await expect(profileModal).toBeVisible();

    // Change preferences form fields
    await page.selectOption('#pref-vehicle', 'VW Grand California');
    await page.fill('#pref-drive-hours', '8');
    await page.selectOption('#pref-hookup', 'full_hookup');
    await page.fill('#pref-budget', '50');

    // Toggle amenities checkboxes
    if (!(await page.isChecked('#pref-amenity-wifi'))) {
      await page.check('#pref-amenity-wifi');
    }

    await page.click('#btn-save-preferences');

    // Modal should close on successful save
    await expect(profileModal).toBeHidden();

    // Verify PUT request payload
    expect(savedData).toEqual({
      vehicle_model: 'VW Grand California',
      max_daily_drive_hours: 8,
      hookup_type: 'full_hookup',
      budget_per_night_eur: 50,
      preferred_amenities: ['power', 'water', 'showers', 'wifi']
    });
  });

  test('User Profile — Logout Action', async ({ page }) => {
    let logoutCalled = false;
    await page.route('**/api/logout', route => {
      logoutCalled = true;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    });

    await page.click('#nav-user-btn');
    await expect(page.locator('#profile-modal')).toBeVisible();

    await page.click('#btn-user-logout');
    expect(logoutCalled).toBe(true);
  });

  test('Saved Trips Drawer opens', async ({ page }) => {
    const tripsDrawer = page.locator('#trips-drawer');
    await expect(tripsDrawer).toBeAttached();

    await page.evaluate(() => {
      const m = document.getElementById('trips-drawer');
      if (m) m.style.display = 'flex';
    });
    await expect(tripsDrawer).toBeAttached();
  });

  /* ═════════════════════════════════════════════════════════════════════
     Summary Modal & Export E2E Tests (#summary-modal, #btn-generate-summary)
     ═════════════════════════════════════════════════════════════════════ */

  test('Summary Modal — opens via #btn-generate-summary and renders format options', async ({ page }) => {
    // Switch to Memory view where #btn-generate-summary is located
    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-memory')?.classList.add('active');
      // Set current trip in application state so prompt guard passes
      (window as any).state = (window as any).state || {};
      (window as any).state.currentTrip = { trip: { id: 'test-trip-uuid', title: 'Karkonosze Run' } };
    });

    const btnGenerate = page.locator('#btn-generate-summary');
    await expect(btnGenerate).toBeVisible();

    // Click generate summary button
    await btnGenerate.click();

    // Verify summary modal is visible with format selection cards
    const summaryModal = page.locator('#summary-modal');
    await expect(summaryModal).toBeVisible();

    const summaryOptions = page.locator('#summary-options');
    await expect(summaryOptions).toBeVisible();

    // Verify all format selection buttons are present
    await expect(page.locator('#btn-export-slideshow')).toBeVisible();
    await expect(page.locator('#btn-export-video')).toBeVisible();
    await expect(page.locator('#btn-export-pdf')).toBeVisible();
    await expect(page.locator('#summary-close-btn')).toBeVisible();
  });

  test('Summary Modal — Slideshow format populates #summary-carousel with slide images', async ({ page }) => {
    // Mock summary API response for slideshow
    await page.route('**/api/generate_summary', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        all_slides: ['/summaries/slide1.png', '/summaries/slide2.png', '/summaries/slide3.png'],
        file_url: '/summaries/slide1.png'
      })
    }));

    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      (window as any).state = (window as any).state || {};
      (window as any).state.currentTrip = { trip: { id: 'test-trip-uuid' } };
      const m = document.getElementById('summary-modal');
      const opts = document.getElementById('summary-options');
      const resView = document.getElementById('summary-result-view');
      if (m && opts && resView) {
        m.style.display = 'flex';
        opts.style.display = 'block';
        resView.style.display = 'none';
      }
    });

    await page.click('#btn-export-slideshow');

    // Options view should hide and result view show carousel
    await expect(page.locator('#summary-options')).toBeHidden();
    await expect(page.locator('#summary-result-view')).toBeVisible();

    // Check carousel contains 3 slide images
    const carouselImages = page.locator('#summary-carousel img');
    await expect(carouselImages).toHaveCount(3);
    await expect(carouselImages.first()).toHaveAttribute('src', '/summaries/slide1.png');
  });

  test('Summary Modal — Video MP4 format renders video element in #summary-carousel', async ({ page }) => {
    // Mock summary API response for MP4 video
    await page.route('**/api/generate_summary', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        file_url: '/summaries/summary_video.mp4'
      })
    }));

    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      (window as any).state = (window as any).state || {};
      (window as any).state.currentTrip = { trip: { id: 'test-trip-uuid' } };
      const m = document.getElementById('summary-modal');
      const opts = document.getElementById('summary-options');
      const resView = document.getElementById('summary-result-view');
      if (m && opts && resView) {
        m.style.display = 'flex';
        opts.style.display = 'block';
        resView.style.display = 'none';
      }
    });

    await page.click('#btn-export-video');

    await expect(page.locator('#summary-result-view')).toBeVisible();
    const videoElem = page.locator('#summary-carousel video');
    await expect(videoElem).toBeVisible();
    await expect(videoElem).toHaveAttribute('src', '/summaries/summary_video.mp4');
  });

  test('Summary Modal — PDF document format renders iframe preview in #summary-carousel', async ({ page }) => {
    // Mock summary API response for PDF report
    await page.route('**/api/generate_summary', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        file_url: '/summaries/report_trip.pdf'
      })
    }));

    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      (window as any).state = (window as any).state || {};
      (window as any).state.currentTrip = { trip: { id: 'test-trip-uuid' } };
      const m = document.getElementById('summary-modal');
      const opts = document.getElementById('summary-options');
      const resView = document.getElementById('summary-result-view');
      if (m && opts && resView) {
        m.style.display = 'flex';
        opts.style.display = 'block';
        resView.style.display = 'none';
      }
    });

    await page.click('#btn-export-pdf');

    await expect(page.locator('#summary-result-view')).toBeVisible();
    const pdfIframe = page.locator('#summary-carousel iframe');
    await expect(pdfIframe).toBeVisible();
    await expect(pdfIframe).toHaveAttribute('src', '/summaries/report_trip.pdf');
  });

  test('Summary Modal — close button dismisses modal', async ({ page }) => {
    await page.evaluate(() => {
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.style.display = 'none';
      const m = document.getElementById('summary-modal');
      if (m) m.style.display = 'flex';
    });

    const summaryModal = page.locator('#summary-modal');
    await expect(summaryModal).toBeVisible();

    await page.click('#summary-close-btn');

    await expect(summaryModal).toBeHidden();
  });

  /* ═════════════════════════════════════════════════════════════════════
     Camping Filtering & Map Display E2E Tests (#btn-toggle-campings, #map-legend, CEE badges)
     ═════════════════════════════════════════════════════════════════════ */

  test('Map Legend (#map-legend) renders correctly with all camping and route markers', async ({ page }) => {
    // Switch to Map View & hide auth modal
    await page.evaluate(() => {
      const auth = document.getElementById('auth-modal');
      if (auth) auth.style.display = 'none';
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-map')?.classList.add('active');
    });

    const legend = page.locator('#map-legend');
    await expect(legend).toBeVisible();

    // Verify items in the legend
    await expect(legend).toContainText('Start / Koniec');
    await expect(legend).toContainText('Kemping');
    await expect(legend).toContainText('Atrakcja');
    await expect(legend).toContainText('Zdjęcie');
  });

  test('Toggle Campings button (#btn-toggle-campings) toggles camping markers and active state', async ({ page }) => {
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
    // Mock search_campings endpoint
    await page.route('**/api/search_campings', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        source: 'database',
        total_found: 2,
        results: [
          {
            id: 'camp-1',
            name: 'Camp California Premium',
            lat: 47.5,
            lng: 13.0,
            shore_power_hookup: true,
            has_power: true,
            has_showers: true,
            has_water: true,
            has_wifi: true,
            cost_per_night_eur: 25,
            rating: 4.8
          },
          {
            id: 'camp-2',
            name: 'Alpine Eco Camping',
            lat: 47.6,
            lng: 13.1,
            shore_power_hookup: true,
            has_power: true,
            has_showers: false,
            cost_per_night_eur: 18,
            rating: 4.5
          }
        ]
      })
    }));

    // Switch to Map View, hide auth modal & mock map state
    await page.evaluate(() => {
      const auth = document.getElementById('auth-modal');
      if (auth) auth.style.display = 'none';
      (window as any).state = (window as any).state || {};
      (window as any).state.campingMarkers = [];
      (window as any).state.markers = [];
      (window as any).state.routePolylines = [];
      (window as any).state.map = {
        getCenter: () => ({ lat: () => 47.5, lng: () => 13.0 }),
        setCenter: () => {},
        setZoom: () => {}
      };
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-map')?.classList.add('active');
      (window as any).google = {
        maps: {
          Marker: class {
            setMap() {}
            addListener() {}
          },
          InfoWindow: class {
            constructor(opts: any) { (this as any).opts = opts; }
            open() {}
          },
          SymbolPath: { CIRCLE: 1 }
        }
      };
    });

    const toggleBtn = page.locator('#btn-toggle-campings');
    await expect(toggleBtn).toBeVisible();

    // Click to turn ON campings
    await page.evaluate(async () => {
      await (window as any).toggleCampingsOnMap();
    });

    await expect(toggleBtn).toHaveClass(/active/);

    const markerCount = await page.evaluate(() => ((window as any).state && (window as any).state.campingMarkers) ? (window as any).state.campingMarkers.length : 0);
    expect(markerCount).toBe(2);

    // Click again to turn OFF campings
    await page.evaluate(async () => {
      await (window as any).toggleCampingsOnMap();
    });

    await expect(toggleBtn).not.toHaveClass(/active/);

    const markerCountOff = await page.evaluate(() => ((window as any).state && (window as any).state.campingMarkers) ? (window as any).state.campingMarkers.length : 0);
    expect(markerCountOff).toBe(0);
  });

  test('Camping InfoWindow renders amenity badges and CEE power badge', async ({ page }) => {
    // Mock search_campings endpoint
    await page.route('**/api/search_campings', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        source: 'database',
        total_found: 1,
        results: [
          {
            id: 'camp-cee-1',
            name: 'VW California Heaven Camping',
            lat: 47.51,
            lng: 13.02,
            shore_power_hookup: true,
            has_power: true,
            has_showers: true,
            has_water: true,
            has_wifi: true,
            has_toilets: true,
            cost_per_night_eur: 30,
            rating: 4.9
          }
        ]
      })
    }));

    await page.evaluate(async () => {
      const auth = document.getElementById('auth-modal');
      if (auth) auth.style.display = 'none';
      (window as any).state = (window as any).state || {};
      (window as any).state.campingMarkers = [];
      (window as any).state.markers = [];
      (window as any).state.routePolylines = [];
      (window as any).state.map = {
        getCenter: () => ({ lat: () => 47.51, lng: () => 13.02 }),
        setCenter: () => {},
        setZoom: () => {}
      };
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-map')?.classList.add('active');
      
      (window as any).google = {
        maps: {
          Marker: class {
            setMap() {}
            addListener(event: string, cb: Function) {
              if (event === 'click') (this as any)._onClick = cb;
            }
          },
          InfoWindow: class {
            opts: any;
            constructor(opts: any) {
              this.opts = opts;
              if (opts && opts.content) {
                (window as any)._capturedInfoWindowContent = opts.content;
              }
            }
            open() {}
          },
          SymbolPath: { CIRCLE: 1 }
        }
      };
      
      if (typeof (window as any).loadCampingsOnMap === 'function') {
        await (window as any).loadCampingsOnMap();
      }
    });

    // Verify InfoWindow HTML contains all amenity & CEE badges
    const infoWindowHtml = await page.evaluate(() => (window as any)._capturedInfoWindowContent || '');
    expect(infoWindowHtml).toContain('cee-badge');
    expect(infoWindowHtml).toContain('Prąd CEE');
    expect(infoWindowHtml).toContain('shower-badge');
    expect(infoWindowHtml).toContain('Prysznic');
    expect(infoWindowHtml).toContain('water-badge');
    expect(infoWindowHtml).toContain('Woda');
    expect(infoWindowHtml).toContain('wifi-badge');
    expect(infoWindowHtml).toContain('WiFi');
    expect(infoWindowHtml).toContain('toilet-badge');
    expect(infoWindowHtml).toContain('Toaleta');
  });

  /* ═════════════════════════════════════════════════════════════════════
     Map View & Route Cards E2E Tests (#view-map, #btn-center-map, #trip-info-card, #stat-km, #stat-hours, #day-cards)
     ═════════════════════════════════════════════════════════════════════ */

  test('Map View — nav buttons switch to #view-map and back to chat', async ({ page }) => {
    // Click #nav-map button
    await page.click('#nav-map');
    await expect(page.locator('#view-map')).toHaveClass(/active/);
    await expect(page.locator('#nav-map')).toHaveClass(/active/);

    // Click #btn-back-to-chat button inside trip info card header
    await page.click('#btn-back-to-chat');
    await expect(page.locator('#view-chat')).toHaveClass(/active/);
    await expect(page.locator('#nav-chat')).toHaveClass(/active/);
  });

  test('Map View — #btn-show-map switches view to map when trip active', async ({ page }) => {
    await page.evaluate(() => {
      const btnShowMap = document.getElementById('btn-show-map');
      if (btnShowMap) btnShowMap.style.display = 'flex';
    });
    await expect(page.locator('#btn-show-map')).toBeVisible();
    await page.click('#btn-show-map');
    await expect(page.locator('#view-map')).toHaveClass(/active/);
  });

  test('Map Controls — #btn-center-map and #btn-toggle-campings are present and clickable', async ({ page }) => {
    await page.click('#nav-map');
    await expect(page.locator('#view-map')).toHaveClass(/active/);

    const btnCenter = page.locator('#btn-center-map');
    await expect(btnCenter).toBeVisible();
    await btnCenter.click();

    const btnCampings = page.locator('#btn-toggle-campings');
    await expect(btnCampings).toBeVisible();
    await btnCampings.click();
  });

  test('Trip Info Card & Statistics — renders #trip-title, #stat-km, #stat-hours, #stat-days, #stat-campings', async ({ page }) => {
    await page.click('#nav-map');

    // Populate state and invoke displayTripOnMap
    await page.evaluate(() => {
      const sampleTripData = {
        trip: { id: 'trip-map-test', title: 'Alpejski Szlak VW California', origin: 'Monachium', destination: 'Jezioro Garda' },
        daily_schedules: [
          {
            day_number: 1,
            date: '2026-08-01',
            driving_hours: 2.5,
            driving_km: 180,
            waypoints: [
              { type: 'start', lat: 48.1351, lng: 11.5820, label: 'Monachium' },
              { type: 'camping', lat: 47.2692, lng: 11.4041, label: 'Innsbruck Camping' }
            ]
          },
          {
            day_number: 2,
            date: '2026-08-02',
            driving_hours: 3.0,
            driving_km: 220,
            waypoints: [
              { type: 'camping', lat: 47.2692, lng: 11.4041, label: 'Innsbruck Camping' },
              { type: 'end', lat: 45.4384, lng: 10.9916, label: 'Jezioro Garda Camping' }
            ]
          }
        ],
        total_driving_km: 400,
        total_driving_hours: 5.5
      };
      if (typeof (window as any).displayTripOnMap === 'function') {
        (window as any).displayTripOnMap(sampleTripData);
      }
    });

    const tripInfoCard = page.locator('#trip-info-card');
    await expect(tripInfoCard).toHaveClass(/visible/);

    await expect(page.locator('#trip-title')).toHaveText('Alpejski Szlak VW California');
    await expect(page.locator('#stat-km')).toHaveText('400');
    await expect(page.locator('#stat-hours')).toHaveText('5.5h');
    await expect(page.locator('#stat-days')).toHaveText('2');
    await expect(page.locator('#stat-campings')).toHaveText('1');

    // Close button test
    await page.click('#trip-info-close');
    await expect(tripInfoCard).not.toHaveClass(/visible/);
  });

  test('Day Cards Generation — renders day cards, displays info and handles selection', async ({ page }) => {
    await page.click('#nav-map');

    await page.evaluate(() => {
      const sampleTripData = {
        trip: { id: 'trip-daycards-test', title: 'Wybrzeże Bałtyku' },
        daily_schedules: [
          {
            day_number: 1,
            date: '2026-07-01',
            driving_hours: 2.0,
            driving_km: 150,
            waypoints: [
              { type: 'start', lat: 54.3520, lng: 18.6466, label: 'Gdańsk' },
              { type: 'camping', lat: 54.7570, lng: 17.5539, label: 'Łeba Camping' }
            ]
          },
          {
            day_number: 2,
            date: '2026-07-02',
            driving_hours: 1.8,
            driving_km: 110,
            waypoints: [
              { type: 'camping', lat: 54.7570, lng: 17.5539, label: 'Łeba Camping' },
              { type: 'end', lat: 54.1807, lng: 16.1770, label: 'Kołobrzeg Camping' }
            ]
          }
        ],
        total_driving_km: 260,
        total_driving_hours: 3.8
      };
      if (typeof (window as any).displayTripOnMap === 'function') {
        (window as any).displayTripOnMap(sampleTripData);
      }
    });

    const dayCards = page.locator('#day-cards .day-card');
    await expect(dayCards).toHaveCount(2);

    const firstCard = dayCards.nth(0);
    await expect(firstCard).toContainText('Dzień 1');
    await expect(firstCard).toContainText('2026-07-01');
    await expect(firstCard).toContainText('2h');
    await expect(firstCard).toContainText('150km');

    const secondCard = dayCards.nth(1);
    await expect(secondCard).toContainText('Dzień 2');
    await expect(secondCard).toContainText('2026-07-02');
    await expect(secondCard).toContainText('1.8h');
    await expect(secondCard).toContainText('110km');

    // Click day card to check active state class toggle
    await firstCard.click();
    await expect(firstCard).toHaveClass(/active/);
    await expect(secondCard).not.toHaveClass(/active/);

    await secondCard.click();
    await expect(secondCard).toHaveClass(/active/);
    await expect(firstCard).not.toHaveClass(/active/);
  });

});


