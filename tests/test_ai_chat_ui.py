"""
Comprehensive Playwright E2E UI verification test suite for the AI Chat module in VW California AI Trip Planner.

Tests verified components:
1. #chat-input (Message input, character counter, send button auto-enable/disable, text clearing on submit, enter submit)
2. #quick-actions (Quick start buttons #qa-1..#qa-4, prompt dispatching, hiding welcome screen)
3. #slot-progress (Slot progress indicator: #slot-vibe, #slot-experience, #slot-pace, #slot-infrastructure, #slot-duration state classes)
4. Typing & Planning indicators (#typing-indicator vs #planning-indicator visibility during text reply vs route generation)
5. #map-chat-panel (Floating map chat panel toggle #map-chat-bubble / #map-chat-close, text input #map-chat-input, send #map-chat-send, bidirectionally synced messages)
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PORT = 5058
BASE_URL = f"http://localhost:{SERVER_PORT}"


def wait_for_server(timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def run_e2e_tests():
    print(f"🚀 Starting server on port {SERVER_PORT}...")
    server_env = dict(os.environ)
    server_env["PORT"] = str(SERVER_PORT)
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "tools.server"],
        cwd=ROOT,
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    test_results = []

    def report(name, success, details=""):
        status_str = "PASS" if success else "FAIL"
        symbol = "✅" if success else "❌"
        test_results.append({"name": name, "status": status_str, "details": details})
        print(f"{symbol} [{status_str}] {name}" + (f" -> {details}" if details else ""))

    try:
        if not wait_for_server():
            print("❌ Server startup timed out.")
            return 1

        print(f"🌐 Server operational at {BASE_URL}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(10000)

            # Mock backend API calls to ensure predictable, fast UI test execution
            page.route("**/api/chat", lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"success", "text":"Cześć! Dokąd chcesz jechać?", "slot_state":{"vibe":"góry", "duration":"7"}}'
            ))

            page.goto(BASE_URL + "/", wait_until="networkidle")

            # -------------------------------------------------------------
            # TEST GROUP 1: #chat-input Verification
            # -------------------------------------------------------------
            print("\n--- 1. Testing #chat-input ---")
            chat_input = page.locator("#chat-input")
            send_btn = page.locator("#send-btn")
            char_counter = page.locator("#char-counter")

            # Check initial state
            is_input_visible = chat_input.is_visible()
            is_btn_disabled = send_btn.is_disabled()
            counter_text = char_counter.inner_text()
            
            report(
                "#chat-input initial state",
                is_input_visible and is_btn_disabled and counter_text == "0/1000",
                f"Visible: {is_input_visible}, Disabled send: {is_btn_disabled}, Counter: '{counter_text}'"
            )

            # Type text into input
            test_prompt = "Planuję wyjazd w góry z rodziną"
            chat_input.fill(test_prompt)
            chat_input.dispatch_event("input")
            
            counter_updated = char_counter.inner_text()
            btn_enabled_after_typing = not send_btn.is_disabled()

            report(
                "#chat-input character counter & button enable",
                counter_updated == f"{len(test_prompt)}/1000" and btn_enabled_after_typing,
                f"Counter: '{counter_updated}', Send button enabled: {btn_enabled_after_typing}"
            )

            # Click send button
            send_btn.click()

            # Verify message sent to DOM, input cleared, counter reset
            page.wait_for_selector(".message.user")
            user_msg = page.locator(".message.user").last.inner_text()
            input_val_after = chat_input.input_value()
            counter_after = char_counter.inner_text()
            btn_disabled_after = send_btn.is_disabled()
            welcome_hidden = not page.locator("#chat-welcome").is_visible()

            report(
                "#chat-input message submit & auto-reset",
                test_prompt in user_msg and input_val_after == "" and counter_after == "0/1000" and btn_disabled_after and welcome_hidden,
                f"Msg added: '{user_msg[:30]}...', Input cleared: {input_val_after == ''}, Welcome hidden: {welcome_hidden}"
            )

            # -------------------------------------------------------------
            # TEST GROUP 2: #quick-actions Verification
            # -------------------------------------------------------------
            print("\n--- 2. Testing #quick-actions ---")
            # Refresh page to restore welcome screen
            page.reload(wait_until="networkidle")

            quick_actions_container = page.locator("#quick-actions")
            qa_buttons = page.locator(".quick-action")
            qa_count = qa_buttons.count()

            report(
                "#quick-actions rendered correctly",
                quick_actions_container.is_visible() and qa_count == 4,
                f"Found {qa_count} quick action buttons"
            )

            # Click second quick action button (#qa-2)
            qa2_btn = page.locator("#qa-2")
            qa2_prompt = qa2_btn.get_attribute("data-prompt")
            qa2_btn.click()

            # Verify prompt dispatched as user message
            page.wait_for_selector(".message.user")
            sent_qa_msg = page.locator(".message.user").last.inner_text()

            report(
                "#quick-actions click triggers prompt send",
                qa2_prompt in sent_qa_msg and not page.locator("#chat-welcome").is_visible(),
                f"Dispatched prompt: '{qa2_prompt[:40]}...'"
            )

            # -------------------------------------------------------------
            # TEST GROUP 3: #slot-progress Verification
            # -------------------------------------------------------------
            print("\n--- 3. Testing #slot-progress ---")
            slot_progress = page.locator("#slot-progress")
            slots = ["vibe", "experience", "pace", "infrastructure", "duration"]

            all_slots_exist = all(page.locator(f"#slot-{s}").count() == 1 for s in slots)
            report(
                "#slot-progress structure",
                slot_progress.is_visible() and all_slots_exist,
                f"Found all 5 slot steps in UI"
            )

            # Test updating slots dynamically via state/function updateSlotProgress
            page.evaluate("""() => {
                updateSlotProgress({
                    vibe: "Góry",
                    experience: "Średnie",
                    pace: "Spokojne",
                    infrastructure: "Kemping",
                    duration: "7 dni"
                });
            }""")

            filled_count = page.locator(".slot-step.filled").count()
            report(
                "#slot-progress filling slots updates UI (.filled class)",
                filled_count == 5,
                f"Filled slots count: {filled_count}/5"
            )

            # Test clearing a slot
            page.evaluate("""() => {
                updateSlotProgress({
                    pace: null
                });
            }""")
            filled_count_after_clear = page.locator(".slot-step.filled").count()
            pace_has_filled = page.evaluate("document.getElementById('slot-pace').classList.contains('filled')")

            report(
                "#slot-progress dynamic state updates (unfilling slot)",
                filled_count_after_clear == 4 and not pace_has_filled,
                f"Remaining filled: {filled_count_after_clear}, Pace filled: {pace_has_filled}"
            )

            # -------------------------------------------------------------
            # TEST GROUP 4: Typing & Planning Indicators Verification
            # -------------------------------------------------------------
            print("\n--- 4. Testing typing/planning indicators ---")
            typing_ind = page.locator("#typing-indicator")
            planning_ind = page.locator("#planning-indicator")

            # Show standard typing indicator
            page.evaluate("showTyping(true, false)")
            typing_visible = page.evaluate("document.getElementById('typing-indicator').classList.contains('visible')")
            planning_hidden = not page.evaluate("document.getElementById('planning-indicator').classList.contains('visible')")

            report(
                "Standard typing indicator visibility (#typing-indicator)",
                typing_visible and planning_hidden,
                f"Typing visible: {typing_visible}, Planning visible: {not planning_hidden}"
            )

            # Show route planning indicator
            page.evaluate("showTyping(true, true)")
            typing_hidden = not page.evaluate("document.getElementById('typing-indicator').classList.contains('visible')")
            planning_visible = page.evaluate("document.getElementById('planning-indicator').classList.contains('visible')")

            report(
                "Route planning indicator visibility (#planning-indicator)",
                planning_visible and typing_hidden,
                f"Planning visible: {planning_visible}, Typing visible: {not typing_hidden}"
            )

            # Hide both indicators
            page.evaluate("showTyping(false)")
            both_hidden = page.evaluate("""() => {
                const t = document.getElementById('typing-indicator').classList.contains('visible');
                const p = document.getElementById('planning-indicator').classList.contains('visible');
                return !t && !p;
            }""")

            report(
                "Hiding typing/planning indicators",
                both_hidden,
                f"Both indicators hidden: {both_hidden}"
            )

            # -------------------------------------------------------------
            # TEST GROUP 5: #map-chat-panel Verification
            # -------------------------------------------------------------
            print("\n--- 5. Testing #map-chat-panel ---")

            # Switch to Map view to test floating chat panel
            page.click("#nav-map")
            page.wait_for_selector("#view-map.active")

            map_chat_container = page.locator("#map-chat-container")
            map_chat_bubble = page.locator("#map-chat-bubble")
            map_chat_panel = page.locator("#map-chat-panel")
            map_chat_close = page.locator("#map-chat-close")
            map_chat_input = page.locator("#map-chat-input")
            map_chat_send = page.locator("#map-chat-send")
            map_chat_messages = page.locator("#map-chat-messages")

            report(
                "#map-chat-panel container & elements exist",
                map_chat_container.is_visible() and map_chat_bubble.is_visible() and map_chat_panel.count() == 1,
                f"Map chat bubble visible: {map_chat_bubble.is_visible()}"
            )

            # Open panel via bubble click
            map_chat_bubble.click()
            panel_visible = page.evaluate("document.getElementById('map-chat-panel').style.display !== 'none'")
            bubble_hidden = page.evaluate("document.getElementById('map-chat-bubble').style.display === 'none'")

            report(
                "Opening #map-chat-panel via bubble click",
                panel_visible and bubble_hidden,
                f"Panel visible: {panel_visible}, Bubble hidden: {bubble_hidden}"
            )

            # Send message from map chat panel
            map_prompt = "Wiadomość wysłana z panelu mapy"
            map_chat_input.fill(map_prompt)
            map_chat_send.click()

            # Verify message appeared in #map-chat-messages and synced to main #chat-messages
            page.wait_for_timeout(500)
            map_msgs_text = map_chat_messages.inner_text()
            
            # Switch back to chat view to check sync
            page.click("#nav-chat")
            main_msgs_text = page.locator("#chat-messages").inner_text()

            report(
                "#map-chat-panel message send & bidirectional sync",
                map_prompt in map_msgs_text and map_prompt in main_msgs_text,
                f"Found message in map chat: {map_prompt in map_msgs_text}, in main chat: {map_prompt in main_msgs_text}"
            )

            # Switch back to map view and test close button
            page.click("#nav-map")
            map_chat_close.click()
            
            panel_hidden_after_close = page.evaluate("document.getElementById('map-chat-panel').style.display === 'none'")
            bubble_shown_after_close = page.evaluate("document.getElementById('map-chat-bubble').style.display !== 'none'")

            report(
                "Closing #map-chat-panel via #map-chat-close",
                panel_hidden_after_close and bubble_shown_after_close,
                f"Panel hidden: {panel_hidden_after_close}, Bubble visible: {bubble_shown_after_close}"
            )

            browser.close()

            print("\n==================================================")
            passed = sum(1 for r in test_results if r["status"] == "PASS")
            total = len(test_results)
            print(f"SUMMARY: {passed}/{total} AI Chat UI tests PASSED")
            print("==================================================")

            return test_results

    finally:
        if server_proc.poll() is None:
            server_proc.send_signal(signal.SIGINT)
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()


if __name__ == "__main__":
    results = run_e2e_tests()
    if isinstance(results, list):
        failed = [r for r in results if r["status"] != "PASS"]
        sys.exit(0 if not failed else 1)
    sys.exit(1)
