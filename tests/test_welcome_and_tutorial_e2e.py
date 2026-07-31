"""
Automated E2E Playwright Browser Test for Welcome Screen & Tutorial.
"""

import os
import sys
import time
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SERVER_PORT = 5050
BASE_URL = f"http://localhost:{SERVER_PORT}"


def wait_for_server(timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/", timeout=2) as resp:
                if resp.status in (200, 403):
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def test_welcome_and_tutorial():
    from playwright.sync_api import sync_playwright

    server_proc = None
    if not wait_for_server(timeout=2):
        print("🚀 Launching Flask test server on port 5050...")
        env = dict(os.environ)
        env["PORT"] = str(SERVER_PORT)

        server_proc = subprocess.Popen(
            [sys.executable, "-m", "tools.server"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    try:
        if not wait_for_server(timeout=15):
            print("❌ Server failed to start on port 5050")
            return False

        print(f"✅ Server running at {BASE_URL}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 1. Register a test user so we have an authenticated session
            test_email = f"e2e_driver_{int(time.time())}@example.com"
            print(f"👤 Registering test user: {test_email}...")

            page.goto(BASE_URL)
            page.wait_for_selector("#auth-modal", state="visible")

            # Click switch to register view
            page.click("#link-show-register")
            page.fill("#register-name", "Kierowca VW")
            page.fill("#register-email", test_email)
            page.fill("#register-password", "vw123456")
            page.click("#btn-register")

            print("⏳ Waiting for login completion & welcome overlay...")
            # 2. Verify Welcome Overlay appears after registration
            page.wait_for_selector("#welcome-overlay", state="visible", timeout=5000)
            welcome_text = page.inner_text("#welcome-user-name")
            print(f"✅ Welcome screen detected with text: '{welcome_text}'")
            assert "Kierowca VW" in welcome_text or "Witaj" in welcome_text

            # 3. Wait for Welcome Overlay fade-out (approx 3 seconds)
            print("⏳ Waiting for Welcome screen fade-out & Tutorial start...")
            page.wait_for_selector("#welcome-overlay", state="hidden", timeout=6000)
            print("✅ Welcome overlay smoothly faded out")

            # 4. Verify Interactive Tutorial starts (Step 1)
            page.wait_for_selector("#tutorial-overlay", state="visible", timeout=5000)
            badge_1 = page.inner_text("#tutorial-step-badge")
            title_1 = page.inner_text("#tutorial-card-title")
            print(f"✅ Tutorial Step 1 active: '{badge_1}' — {title_1}")
            assert "KROK 1 Z 5" in badge_1.upper()

            # 5. Click through steps 2..5
            for step_num in range(2, 6):
                page.click("#tutorial-btn-next")
                page.wait_for_timeout(600)
                badge = page.inner_text("#tutorial-step-badge")
                title = page.inner_text("#tutorial-card-title")
                print(f"✅ Tutorial Step {step_num} active: '{badge}' — {title}")
                assert f"KROK {step_num} Z 5" in badge.upper()

            # 6. Complete final step -> Tutorial hides
            page.click("#tutorial-btn-next")
            page.wait_for_selector("#tutorial-overlay", state="hidden", timeout=3000)
            print("✅ Tutorial completed and dismissed successfully!")

            # 7. Test manual restart via Profile Modal
            print("🔄 Testing 'Samouczek' button in Profile Modal...")
            page.click("#nav-user-btn")
            page.wait_for_selector("#profile-modal", state="visible")
            page.click("#btn-restart-tutorial")

            # Verify Tutorial restarts
            page.wait_for_selector("#tutorial-overlay", state="visible", timeout=4000)
            print("✅ Tutorial restarted cleanly via Profile button!")

            browser.close()
            return True

    finally:
        if server_proc:
            server_proc.terminate()
            server_proc.wait()


if __name__ == "__main__":
    success = test_welcome_and_tutorial()
    if success:
        print("\n🎉 ALL E2E BROWSER TESTS PASSED 100%!")
        sys.exit(0)
    else:
        print("\n❌ E2E TEST FAILED!")
        sys.exit(1)
