"""
Main entry point for the VW California AI Trip Planner.

Orchestrates the B.L.A.S.T. protocol phases and showcases
project functionality.
"""

from tools.verify_connections import run_all_handshakes
from tools.search_campings import search_campings
from tools.plan_route import plan_route
from navigation.chat_handler import create_chat_session, send_message


def example_verify_connections():
    """
    Phase 2: Link — Run all API handshake verifications.

    Verifies connectivity to:
    - Google Gemini API (chat completions)
    - Google Maps Platform (geocoding)
    - PostgreSQL + PostGIS (database)
    """
    results, all_passed = run_all_handshakes()
    return results, all_passed


def example_search_campings():
    """
    Phase 3: Architect — Demonstrate camping search tool.

    Searches for VW-compatible campgrounds near Lake Bled
    with power and shower amenities.
    """
    print("\n🔍 Searching for campings near Lake Bled...")
    results = search_campings(
        lat=46.3636,
        lng=14.0938,
        radius_km=100,
        amenities=["power", "showers"],
        vw_compatible=True,
    )

    if results["status"] == "success":
        print(f"  Found {results['total_found']} results "
              f"(source: {results['source']})")
        for camp in results["results"]:
            print(f"  📍 {camp['name']} — "
                  f"{camp.get('distance_km', '?')}km away "
                  f"(€{camp.get('cost_per_night_eur', '?')}/night)")
    else:
        print(f"  ❌ {results.get('message', 'Unknown error')}")


def example_chat():
    """
    Phase 3: Architect — Demonstrate AI chat with tool calling.

    Runs an interactive chat session where the user can ask
    trip planning questions in natural language.
    """
    print("\n🚐 VW California Trip Planner — AI Chat")
    print("=" * 55)
    print("Type your trip planning questions below.")
    print("Type 'quit' to exit.\n")

    session = create_chat_session()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 🚐")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye! 🚐")
            break

        if not user_input:
            continue

        result = send_message(session, user_input)
        print(f"\nAssistant: {result['text']}\n")


def main():
    """
    Main execution method.
    """
    print("🚐 VW California AI Trip Planner")
    print("=" * 55)

    # Phase 2: Verify connections
    print("\n📡 Phase 2: Verifying API connections...\n")
    _, all_passed = example_verify_connections()

    if not all_passed:
        print("\n⚠️  Fix connections before proceeding.")
        return

    # Phase 3: Demonstrate tools
    print("\n\n🏗️  Phase 3: Tool Demonstrations")
    print("=" * 55)
    example_search_campings()

    # Phase 3: Interactive chat
    example_chat()


if __name__ == "__main__":
    main()
