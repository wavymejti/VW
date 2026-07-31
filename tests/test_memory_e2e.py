"""
End-to-End Browser Test for VW California AI Trip Planner — TRAVEL MEMORY VIEW (#view-memory).

Verifies UI components:
- #upload-zone (Photo Upload Zone & Drag/Drop interface)
- #photo-grid (Photo Grid layout & empty state)
- #photo-lightbox (Fullscreen Photo Lightbox modal)
- #pin-photo-overlay (Manual Photo Pinning Banner on map)

Usage:
    venv/bin/python tests/test_memory_e2e.py
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SERVER_PORT = 5050
BASE_URL = f"http://localhost:{SERVER_PORT}"


def wait_for_server(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def ensure_test_photos():
    """Ensure test photos with and without EXIF exist."""
    test_dir = os.path.join(ROOT, "test-materials-exif")
    os.makedirs(test_dir, exist_ok=True)

    gps_path = os.path.join(test_dir, "gps_photo.jpg")
    no_gps_path = os.path.join(test_dir, "no_gps_photo.jpg")

    # Generate GPS photo using mock_photo script if not exists
    if not os.path.exists(gps_path):
        from tools.mock_photo import generate_mock_photo
        generate_mock_photo(gps_path, lat=52.5200, lng=13.4050, date_str="2026-08-01 12:30:00", color=(0, 120, 200))

    # Generate plain photo without GPS if not exists
    if not os.path.exists(no_gps_path):
        img = Image.new("RGB", (400, 300), color=(220, 80, 50))
        img.save(no_gps_path, "jpeg")

    return gps_path, no_gps_path


def main():
    from playwright.sync_api import sync_playwright

    gps_photo_path, no_gps_photo_path = ensure_test_photos()

    # Kill any existing server on port 5050 to ensure clean state
    try:
        subprocess.run(["pkill", "-f", "tools.server"], stderr=subprocess.DEVNULL)
        time.sleep(1)
    except Exception:
        pass

    # Start Flask server process
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "tools.server"],
        cwd=ROOT,
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    results = []

    def check(name, cond, extra=""):
        results.append((name, cond))
        status = "✅ PASS" if cond else "❌ FAIL"
        print(f"{status} | {name}" + (f" ({extra})" if extra else ""))

    try:
        if not wait_for_server():
            print("❌ Server did not start in time.")
            return 1
        print(f"✅ Server up at {BASE_URL}\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15000)

            console_errors = []
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))

            # ── 1. Navigation & View Initialisation ─────────────────────
            page.goto(BASE_URL + "/", wait_until="networkidle")

            # Authenticate session via /api/register so photo upload APIs succeed
            page.evaluate("""async () => {
                const email = 'test_memory_' + Math.random().toString(36).substring(7) + '@example.com';
                await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, password: 'password123', display_name: 'Tester' })
                });
                const modal = document.getElementById('auth-modal');
                if (modal) modal.style.display = 'none';
                const profile = document.getElementById('user-profile');
                if (profile) profile.style.display = 'block';
            }""")

            # Navigate to Travel Memory View (#view-memory)
            page.click("#nav-memory")
            page.wait_for_timeout(500)

            memory_active = page.evaluate("document.getElementById('view-memory').classList.contains('active')")
            check("1. Widok Pamięci Podróży (#view-memory) jest aktywny", memory_active)

            # Check memory view header components
            header_title = page.inner_text(".memory-title")
            check("1. Nagłówek widoku zawiera tytuł 'Wspomnienia z podróży'", "Wspomnienia z podróży" in header_title)

            # ── 2. Strefa Wgrywania Zdjęć (#upload-zone) ──────────────
            upload_zone_visible = page.is_visible("#upload-zone")
            check("2. Strefa wgrywania zdjęć (#upload-zone) jest widoczna", upload_zone_visible)

            upload_input_exists = page.evaluate("!!document.getElementById('photo-upload')")
            check("2. Pole wyboru plików (#photo-upload) istnieje w DOM", upload_input_exists)

            # ── 3. Siatka Zdjęć (#photo-grid) — Stan Pusty ───────────
            grid_visible = page.is_visible("#photo-grid")
            check("3. Siatka zdjęć (#photo-grid) jest widoczna", grid_visible)

            empty_state_visible = page.is_visible("#photo-empty")
            check("3. Stan pusty (#photo-empty) informuje o braku zdjęć", empty_state_visible)

            # ── 4. Wgranie zdjęcia z metadanymi GPS ────────────────────
            page.set_input_files("#photo-upload", gps_photo_path)
            page.wait_for_timeout(2000)

            empty_hidden_after_upload = page.evaluate("""() => {
                const el = document.getElementById('photo-empty');
                return !el || el.style.display === 'none' || getComputedStyle(el).display === 'none';
            }""")
            check("4. Stan pusty (#photo-empty) zniknął po wgraniu zdjęcia", empty_hidden_after_upload)

            photo_card_count = page.evaluate("document.querySelectorAll('#photo-grid .photo-card').length")
            check("4. Zdjęcie zostało dodane do siatki (#photo-grid)", photo_card_count >= 1, f"Liczba kart: {photo_card_count}")

            card_has_image = page.evaluate("""() => {
                const img = document.querySelector('#photo-grid .photo-card img');
                return img && img.src.length > 0;
            }""")
            check("4. Karta zdjęcia zawiera podgląd obrazka <img>", card_has_image)

            # ── 5. Podgląd Pełnoekranowy (#photo-lightbox) ─────────────
            page.click("#photo-grid .photo-card")
            page.wait_for_timeout(500)

            lightbox_visible = page.evaluate("""() => {
                const lb = document.getElementById('photo-lightbox');
                return lb && lb.style.display !== 'none' && getComputedStyle(lb).display !== 'none';
            }""")
            check("5. Modal podglądu pełnoekranowego (#photo-lightbox) otworzył się", lightbox_visible)

            lightbox_img_src = page.evaluate("document.getElementById('lightbox-img').src")
            check("5. Obrazek w lightboxie (#lightbox-img) ma załadowane źródło", bool(lightbox_img_src))

            # Zamknięcie lightboxa
            page.click("#lightbox-close")
            page.wait_for_timeout(500)

            lightbox_closed = page.evaluate("""() => {
                const lb = document.getElementById('photo-lightbox');
                return !lb || lb.style.display === 'none' || getComputedStyle(lb).display === 'none';
            }""")
            check("5. Lightbox (#photo-lightbox) zamknął się po kliknięciu przycisku zamknięcia", lightbox_closed)

            # ── 6. Banner Przypinania Zdjęcia na Mapie (#pin-photo-overlay) ──
            # Return to memory view before uploading non-GPS photo
            page.click("#nav-memory")
            page.wait_for_timeout(500)

            # Upload photo without GPS EXIF
            page.set_input_files("#photo-upload", no_gps_photo_path)
            page.wait_for_timeout(2000)

            # Verification: Uploading non-GPS photo triggers pin-photo-overlay & redirects to map view
            map_view_auto_switched = page.evaluate("document.getElementById('view-map').classList.contains('active')")
            check("6. Automatyczne przełączenie do widoku mapy po wgraniu zdjęcia bez GPS", map_view_auto_switched)

            pin_overlay_visible = page.evaluate("""() => {
                const ov = document.getElementById('pin-photo-overlay');
                return ov && ov.style.display !== 'none' && getComputedStyle(ov).display !== 'none';
            }""")
            check("6. Banner przypinania zdjęcia na mapie (#pin-photo-overlay) jest widoczny", pin_overlay_visible)

            pin_thumb_has_src = page.evaluate("document.getElementById('pin-photo-preview').src.length > 0")
            check("6. Miniatura zdjęcia (#pin-photo-preview) w bannerze jest załadowana", pin_thumb_has_src)

            pin_banner_text = page.inner_text(".pin-photo-banner")
            check("6. Banner zawiera instrukcję przypięcia zdjęcia na mapie", "Kliknij na mapie" in pin_banner_text)

            # Anulowanie przypinania
            page.click("#pin-photo-cancel")
            page.wait_for_timeout(500)

            pin_overlay_cancelled = page.evaluate("""() => {
                const ov = document.getElementById('pin-photo-overlay');
                return !ov || ov.style.display === 'none' || getComputedStyle(ov).display === 'none';
            }""")
            check("6. Banner przypinania (#pin-photo-overlay) zniknął po naciśnięciu 'Anuluj'", pin_overlay_cancelled)

            # ── 7. Console Errors Verification ───────────────────────────
            fatal_errors = [e for e in console_errors if "Error" in e or "Traceback" in e]
            check("7. Brak krytycznych błędów w konsoli przeglądarki", len(fatal_errors) == 0, f"Błędy: {fatal_errors[:3]}" if fatal_errors else "")

            browser.close()

            passed_count = sum(1 for _, cond in results if cond)
            total_count = len(results)
            print(f"\n==================================================")
            print(f" PODSUMOWANIE TESTÓW UI E2E: {passed_count}/{total_count} PASSED")
            print(f"==================================================")
            return 0 if passed_count == total_count else 1

    finally:
        if server_proc.poll() is None:
            server_proc.send_signal(signal.SIGINT)
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
