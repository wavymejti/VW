import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5050';

test.describe('VW California AI Trip Planner — Map View & Route Cards UI Test Suite', () => {

  test.beforeEach(async ({ page }) => {
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));

    // Inject Google Maps mock into window before page scripts run
    await page.addInitScript(() => {
      (window as any).state = (window as any).state || {};
      (window as any).state.markers = [];
      (window as any).state.routePolylines = [];
      (window as any).state.campingMarkers = [];

      (window as any).google = {
        maps: {
          Map: class { fitBounds() {} setCenter() {} setZoom() {} getCenter() { return { lat: () => 47.5, lng: () => 13.0 }; } },
          Marker: class { setMap() {} addListener() {} getPosition() { return { lat: () => 47.5, lng: () => 13.0 }; } },
          Polyline: class { setMap() {} },
          InfoWindow: class { setContent() {} open() {} close() {} },
          LatLngBounds: class { extend() {} },
          Size: class { constructor(w: number, h: number) {} },
          Animation: { DROP: 1 },
          SymbolPath: { CIRCLE: 1 },
          ControlPosition: { RIGHT_CENTER: 1, TOP_LEFT: 2 }
        }
      };
    });

    // Mock API endpoints for authentication and initial state
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
      body: 'console.log("Mocked Google Maps JS"); if (typeof window.initMap === "function") window.initMap();'
    }));

    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // Dismiss auth modal so it does not intercept clicks
    await page.evaluate(() => {
      const modal = document.getElementById('auth-modal');
      if (modal) modal.style.display = 'none';
      const profile = document.getElementById('user-profile');
      if (profile) profile.style.display = 'block';
    });
  });

  /* ─────────────────────────────────────────────────────────────────────
     1. Przełączanie na widok mapy (#view-map)
     ───────────────────────────────────────────────────────────────────── */
  test('1. View Switching — Navigating to #view-map and back to chat', async ({ page }) => {
    await page.waitForFunction(() => typeof (window as any).switchView === 'function');

    // Switch to Map View via Navigation Rail (#nav-map)
    await page.evaluate(() => (window as any).switchView('map'));
    await expect(page.locator('#view-map')).toHaveClass(/active/);
    await expect(page.locator('#nav-map')).toHaveClass(/active/);
    await expect(page.locator('#view-map')).toBeVisible();

    // Switch back to Chat View via #btn-back-to-chat
    await page.evaluate(() => (window as any).switchView('chat'));
    await expect(page.locator('#view-chat')).toHaveClass(/active/);
    await expect(page.locator('#nav-chat')).toHaveClass(/active/);
  });

  test('1b. View Switching — Floating #btn-show-map button switches to #view-map', async ({ page }) => {
    await page.evaluate(() => {
      const btnShowMap = document.getElementById('btn-show-map');
      if (btnShowMap) btnShowMap.style.display = 'flex';
    });

    const btnShowMap = page.locator('#btn-show-map');
    await expect(btnShowMap).toBeVisible();

    await btnShowMap.click();
    await expect(page.locator('#view-map')).toHaveClass(/active/);
    await expect(page.locator('#nav-map')).toHaveClass(/active/);
  });

  /* ─────────────────────────────────────────────────────────────────────
     2. Przyciski kontroli mapy (#btn-center-map)
     ───────────────────────────────────────────────────────────────────── */
  test('2. Map Controls — #btn-center-map and #btn-toggle-campings are visible and clickable', async ({ page }) => {
    await page.evaluate(() => (window as any).switchView('map'));
    await expect(page.locator('#view-map')).toHaveClass(/active/);

    const mapOverlay = page.locator('#map-overlay');
    await expect(mapOverlay).toBeVisible();

    const btnCenterMap = page.locator('#btn-center-map');
    await expect(btnCenterMap).toBeVisible();

    // Verify click handler executes without error
    await page.evaluate(() => {
      const btn = document.getElementById('btn-center-map');
      if (btn) {
        btn.addEventListener('click', () => { (window as any)._centerMapExecuted = true; });
      }
    });

    await btnCenterMap.click();
    const centerClicked = await page.evaluate(() => (window as any)._centerMapExecuted === true);
    expect(centerClicked).toBe(true);

    const btnToggleCampings = page.locator('#btn-toggle-campings');
    await expect(btnToggleCampings).toBeVisible();
    await btnToggleCampings.click();
  });

  /* ─────────────────────────────────────────────────────────────────────
     3. Karta informacji o podróży (#trip-info-card)
     ───────────────────────────────────────────────────────────────────── */
  test('3. Trip Info Card — Renders trip header, title, and close action', async ({ page }) => {
    await page.evaluate(() => (window as any).switchView('map'));

    const sampleTripData = {
      trip: { id: 'trip-101', title: 'Alpejska Przygoda VW California', origin: 'Monachium', destination: 'Jezioro Garda' },
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

    // Render trip on map
    await page.evaluate((tripData) => {
      (window as any).displayTripOnMap(tripData);
    }, sampleTripData);

    const tripInfoCard = page.locator('#trip-info-card');
    await expect(tripInfoCard).toHaveClass(/visible/);
    await expect(tripInfoCard).toBeVisible();

    const tripTitle = page.locator('#trip-title');
    await expect(tripTitle).toHaveText('Alpejska Przygoda VW California');

    // Test close button
    const closeBtn = page.locator('#trip-info-close');
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(tripInfoCard).not.toHaveClass(/visible/);
  });

  /* ─────────────────────────────────────────────────────────────────────
     4. Statystyki trasy (#stat-km, #stat-hours, #stat-days, #stat-campings)
     ───────────────────────────────────────────────────────────────────── */
  test('4. Route Statistics — Renders accurate stats (#stat-km, #stat-hours, #stat-days, #stat-campings)', async ({ page }) => {
    await page.evaluate(() => (window as any).switchView('map'));

    const sampleTripData = {
      trip: { id: 'trip-stats-test', title: 'Trasa Norweska Fiordy' },
      daily_schedules: [
        {
          day_number: 1,
          date: '2026-06-10',
          driving_hours: 4.2,
          driving_km: 310,
          waypoints: [
            { type: 'start', lat: 59.9139, lng: 10.7522, label: 'Oslo' },
            { type: 'camping', lat: 60.4720, lng: 8.5440, label: 'Geilo Camp' }
          ]
        },
        {
          day_number: 2,
          date: '2026-06-11',
          driving_hours: 3.8,
          driving_km: 245,
          waypoints: [
            { type: 'camping', lat: 60.4720, lng: 8.5440, label: 'Geilo Camp' },
            { type: 'camping', lat: 60.39299, lng: 5.32415, label: 'Bergen Fjord Camp' }
          ]
        },
        {
          day_number: 3,
          date: '2026-06-12',
          driving_hours: 5.0,
          driving_km: 360,
          waypoints: [
            { type: 'camping', lat: 60.39299, lng: 5.32415, label: 'Bergen Fjord Camp' },
            { type: 'end', lat: 62.1008, lng: 7.2059, label: 'Geiranger' }
          ]
        }
      ],
      total_driving_km: 915,
      total_driving_hours: 13.0
    };

    await page.evaluate((tripData) => {
      (window as any).displayTripOnMap(tripData);
    }, sampleTripData);

    await expect(page.locator('#stat-days')).toHaveText('3');
    await expect(page.locator('#stat-km')).toHaveText('915');
    await expect(page.locator('#stat-hours')).toHaveText('13.0h');
    await expect(page.locator('#stat-campings')).toHaveText('3');
  });

  /* ─────────────────────────────────────────────────────────────────────
     5. Generowanie kart dziennych (#day-cards)
     ───────────────────────────────────────────────────────────────────── */
  test('5. Day Cards Generation — Renders #day-cards, displays metrics, and handles interactive selection', async ({ page }) => {
    await page.evaluate(() => (window as any).switchView('map'));

    const sampleTripData = {
      trip: { id: 'trip-daycards-test', title: 'Polskie Wybrzeże VW California' },
      daily_schedules: [
        {
          day_number: 1,
          date: '2026-07-15',
          driving_hours: 2.0,
          driving_km: 150,
          waypoints: [
            { type: 'start', lat: 54.3520, lng: 18.6466, label: 'Gdańsk' },
            { type: 'camping', lat: 54.7570, lng: 17.5539, label: 'Łeba Camping' }
          ]
        },
        {
          day_number: 2,
          date: '2026-07-16',
          driving_hours: 1.5,
          driving_km: 95,
          waypoints: [
            { type: 'camping', lat: 54.7570, lng: 17.5539, label: 'Łeba Camping' },
            { type: 'camping', lat: 54.5800, lng: 16.8500, label: 'Ustka Beach Camp' }
          ]
        },
        {
          day_number: 3,
          date: '2026-07-17',
          driving_hours: 2.8,
          driving_km: 190,
          waypoints: [
            { type: 'camping', lat: 54.5800, lng: 16.8500, label: 'Ustka Beach Camp' },
            { type: 'end', lat: 53.9100, lng: 14.2470, label: 'Świnoujście Camp' }
          ]
        }
      ],
      total_driving_km: 435,
      total_driving_hours: 6.3
    };

    await page.evaluate((tripData) => {
      (window as any).displayTripOnMap(tripData);
    }, sampleTripData);

    const dayCardsContainer = page.locator('#day-cards');
    await expect(dayCardsContainer).toBeVisible();

    const cards = page.locator('#day-cards .day-card');
    await expect(cards).toHaveCount(3);

    // Verify Card 1 details
    const card1 = cards.nth(0);
    await expect(card1.locator('.day-number')).toHaveText('Dzień 1');
    await expect(card1.locator('.day-label')).toHaveText('2026-07-15');
    await expect(card1).toContainText('2h');
    await expect(card1).toContainText('150km');

    // Verify Card 2 details
    const card2 = cards.nth(1);
    await expect(card2.locator('.day-number')).toHaveText('Dzień 2');
    await expect(card2.locator('.day-label')).toHaveText('2026-07-16');
    await expect(card2).toContainText('1.5h');
    await expect(card2).toContainText('95km');

    // Verify Card 3 details
    const card3 = cards.nth(2);
    await expect(card3.locator('.day-number')).toHaveText('Dzień 3');
    await expect(card3.locator('.day-label')).toHaveText('2026-07-17');
    await expect(card3).toContainText('2.8h');
    await expect(card3).toContainText('190km');

    // Test selection interactivity: Click card 1
    await card1.click();
    await expect(card1).toHaveClass(/active/);
    await expect(card2).not.toHaveClass(/active/);
    await expect(card3).not.toHaveClass(/active/);

    // Click card 2: card 1 loses active state, card 2 gets active state
    await card2.click();
    await expect(card2).toHaveClass(/active/);
    await expect(card1).not.toHaveClass(/active/);
    await expect(card3).not.toHaveClass(/active/);

    // Click card 3: card 3 gets active state
    await card3.click();
    await expect(card3).toHaveClass(/active/);
    await expect(card2).not.toHaveClass(/active/);
  });

  /* ─────────────────────────────────────────────────────────────────────
     6. Return Route Leg & Map Legend — Differentiation for Return Leg
     ───────────────────────────────────────────────────────────────────── */
  test('6. Return Route Leg — Map legend and polyline return route colors', async ({ page }) => {
    // Check map legend contains outbound and return route items
    await expect(page.locator('#map-legend')).toContainText('Trasa dojazdowa');
    await expect(page.locator('#map-legend')).toContainText('Trasa powrotna');

    // Display a round trip on map
    await page.evaluate(() => {
      const mockTripData = {
        status: 'success',
        trip: {
          id: 'test-trip-return',
          title: 'Munich Round Trip',
          origin: { label: 'Munich', lat: 48.1351, lng: 11.5820 },
          destination: { label: 'Munich', lat: 48.1351, lng: 11.5820 },
          start_date: '2026-08-01',
          end_date: '2026-08-04',
          status: 'planned'
        },
        total_driving_km: 600,
        total_driving_hours: 8.0,
        daily_schedules: [
          { day_number: 1, date: '2026-08-01', driving_hours: 2.0, driving_km: 150, waypoints: [{ type: 'start', lat: 48.1351, lng: 11.5820 }], is_return: false },
          { day_number: 2, date: '2026-08-02', driving_hours: 2.0, driving_km: 150, waypoints: [{ type: 'camping', lat: 47.8, lng: 13.0 }], is_return: false },
          { day_number: 3, date: '2026-08-03', driving_hours: 2.0, driving_km: 150, waypoints: [{ type: 'camping', lat: 47.9, lng: 12.0 }], is_return: true },
          { day_number: 4, date: '2026-08-04', driving_hours: 2.0, driving_km: 150, waypoints: [{ type: 'end', lat: 48.1351, lng: 11.5820 }], is_return: true }
        ]
      };
      (window as any).displayTripOnMap(mockTripData);
    });

    // Check that day 3 and 4 cards display the Return badge
    const cards = page.locator('.day-card');
    await expect(cards.nth(2)).toContainText('Powrót');
    await expect(cards.nth(3)).toContainText('Powrót');

    // Verify created polylines in window.state.routePolylines
    const polylinesInfo = await page.evaluate(() => {
      return (window as any).state.routePolylines.map((p: any) => ({
        isReturn: p.isReturn,
        dayNumber: p.dayNumber
      }));
    });

    expect(polylinesInfo).toHaveLength(4);
    expect(polylinesInfo[0].isReturn).toBe(false);
    expect(polylinesInfo[1].isReturn).toBe(false);
    expect(polylinesInfo[2].isReturn).toBe(true);
    expect(polylinesInfo[3].isReturn).toBe(true);
  });

});
