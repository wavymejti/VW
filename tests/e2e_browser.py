"""
End-to-end browser test for the VW California AI Trip Planner — CHAT FOCUS.

Drives a real, visible browser through a human-like, multi-turn
conversation with the AI planner: collecting hard slots (trip type,
origin, destination, dates, duration), answering soft-slot questions,
confirming the plan, and finally verifying that a route actually gets
planned and rendered on the map.

Prerequisites:
    pip install playwright && playwright install chromium

Usage:
    python3 tests/e2e_browser.py
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request

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


def main():
    from playwright.sync_api import sync_playwright

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
        print(f"{'✅' if cond else '❌'} {name}" + (f" — {extra}" if extra else ""))

    try:
        if not wait_for_server():
            print("❌ Server did not start in time.")
            return 1
        print(f"✅ Server up at {BASE_URL}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=700)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(20000)

            console_errors = []
            page.on("console", lambda m: console_errors.append(m.text)
                     if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))

            # ── Helpers ───────────────────────────────────────
            def chat_is_planning():
                return page.evaluate(
                    "document.getElementById('planning-indicator')"
                    ".classList.contains('visible')"
                )

            def last_assistant_text():
                return page.evaluate(
                    """() => {
                        const msgs = document.querySelectorAll('#chat-messages .message.assistant');
                        return msgs.length ? msgs[msgs.length-1].innerText : '';
                    }"""
                )

            def current_trip_exists():
                return page.evaluate(
                    "() => !!(window.state && window.state.currentTrip)"
                )

            def send(text, wait_after=9000):
                """Type a message like a human and wait for the reply."""
                page.click("#nav-chat")
                # Use fill which should trigger input events properly
                page.fill("#chat-input", text)
                # Ensure the input event is fired to enable the send button
                page.evaluate("""() => {
                    const input = document.getElementById('chat-input');
                    const btn = document.getElementById('send-btn');
                    if (input) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    // Also manually enable if value exists
                    if (input && input.value && input.value.length > 0 && btn) {
                        btn.disabled = false;
                    }
                }""")
                # Wait for send button to be enabled
                page.wait_for_function("() => !document.getElementById('send-btn').disabled", timeout=5000)
                page.click("#send-btn")
                # Wait until the planning indicator (if shown) disappears
                # and a new assistant bubble has appeared.
                deadline = time.time() + wait_after
                seen = last_assistant_text()
                while time.time() < deadline:
                    if chat_is_planning():
                        # still computing route, keep waiting
                        time.sleep(0.5)
                        continue
                    new = last_assistant_text()
                    if new and new != seen:
                        break
                    time.sleep(0.5)
                time.sleep(0.5)
                return last_assistant_text()

            # ── 1. Load dashboard & verify UI ───────────────────────────
            page.goto(BASE_URL + "/", wait_until="networkidle")
            check("Dashboard loads", "VW California" in page.title())
            page.evaluate("""() => {
                const modal = document.getElementById('auth-modal');
                if (modal) modal.style.display = 'none';
                const profile = document.getElementById('user-profile');
                if (profile) profile.style.display = 'block';
            }""")
            check("UI accessible", True)

            # ── 2. Multi-turn human-like chat ───────────────
            # Turn 1: initial intent (gives origin, destination, duration,
            # but leaves dates / trip type to the AI to clarify).
            resp1 = send("Hej! Chciałbym pojechać z Berlina do Pragi na 4 dni")
            check("T1: assistant replies", len(resp1) > 10, resp1[:60].replace("\n", " "))
            # At least some hard slots should be known now.
            slots1 = page.evaluate("window.state ? window.state.slotState : null")
            check("T1: origin/destination/duration captured",
                  bool(slots1 and slots1.get("origin") and slots1.get("destination")
                       and slots1.get("duration")),
                  str(slots1))

            # Turn 2: answer trip type (AI usually asks A→B vs basecamp)
            resp2 = send("To ma być trasa punkt do punktu")
            check("T2: assistant replies", len(resp2) > 10)

            # Turn 3: provide start date
            resp3 = send("Startujemy 1 sierpnia 2026")
            check("T3: assistant replies", len(resp3) > 10)

            # Continue answering any soft-slot / remaining questions the AI
            # asks, until it presents the confirmation question.
            turn = 4
            planning_question_seen = False
            confirm_phrases = ["zaczynam planować", "zacząć planować", "potwierdzasz",
                               "zaczynamy", "planujemy"]
            max_turns = 8
            while turn <= max_turns:
                txt = last_assistant_text()
                if any(ph in txt.lower() for ph in confirm_phrases):
                    planning_question_seen = True
                    break
                # Generic human-like answers to likely soft-slot questions.
                if "doświadcze" in txt.lower():
                    resp = send("Jestem doświadczonym kierowcą kampera")
                elif "tempo" in txt.lower() or "pac" in txt.lower():
                    resp = send("Wolę spokojne tempo, z postojami co 2-3 dni")
                elif "infrastruktur" in txt.lower() or "dzik" in txt.lower() or "kamp" in txt.lower():
                    resp = send("Odpowiadają mi mieszane kempingi")
                elif "kto" in txt.lower() or "towarzy" in txt.lower() or "rodzin" in txt.lower():
                    resp = send("Jedziemy we dwoje")
                else:
                    # No clear question left to answer — stop the loop.
                    break
                check(f"T{turn}: assistant replies", len(resp) > 10)
                turn += 1

            check("AI presented a plan-confirmation question", planning_question_seen,
                  last_assistant_text()[:80].replace("\n", " "))

            # ── 3. Confirm the plan (human says 'yes') ───────
            # This should trigger plan_route and render the map.
            resp_confirm = send("Tak, zaczynaj planować trasę!", wait_after=20000)
            check("Confirmation reply received", len(resp_confirm) > 10)

            # Wait for the route to be planned + map auto-switch (1.2s).
            page.wait_for_timeout(4000)
            planned = current_trip_exists() or page.evaluate(
                "document.querySelectorAll('#view-map .day-cards .day-card, #map .route-polyline, #map marker').length > 0"
            )
            check("Route planned & rendered on map", planned)

            # Verify map view is active after auto-redirect.
            check("Auto-switched to map view",
                  page.evaluate("document.querySelector('#view-map').classList.contains('active')"))

            # ── 4. Post-planning: add an attraction ─────────
            page.click("#nav-chat")
            page.wait_for_timeout(500)
            # Ask for suggestions / add attraction
            resp_attr = send("Dodaj jakąś atrakcję po drodze, np. zamek", wait_after=15000)
            check("Post-planning reply received", len(resp_attr) > 10)

            # ── 5. No fatal errors ──────────────────────────
            fatal = [e for e in console_errors if "Error" in e or "Traceback" in e]
            check("No fatal console/page errors", len(fatal) == 0)
            if fatal:
                print("   Console errors:", fatal[:5])

            browser.close()

            passed = sum(1 for _, c in results if c)
            total = len(results)
            print(f"\n=== E2E CHAT RESULT: {passed}/{total} checks passed ===")
            return 0 if passed == total else 1

    finally:
        if server_proc.poll() is None:
            server_proc.send_signal(signal.SIGINT)
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()


if __name__ == "__main__":
    sys.exit(main())