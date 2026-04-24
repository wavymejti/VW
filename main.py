"""
Main entry point for the VW California AI Trip Planner.

Orchestrates the B.L.A.S.T. protocol phases and showcases
project functionality.
"""

from tools.verify_connections import run_all_handshakes


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


def main():
    """
    Main execution method.
    """
    print("🚐 VW California AI Trip Planner")
    print("=" * 55)
    print()
    example_verify_connections()


if __name__ == "__main__":
    main()
