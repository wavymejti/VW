"""
Phase 2: Link — Unified API Handshake Verification.

Runs connection tests against all three external services:
1. Google Gemini API
2. Google Maps Platform
3. PostgreSQL + PostGIS

Usage:
    python3 tools/verify_connections.py
"""

import os
import sys

# Ensure project root is in sys.path when running script directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.openai_client import (
    verify_connection as verify_openai,
)
from tools.maps_client import (
    verify_connection as verify_maps,
)
from tools.db import verify_connection as verify_db


def run_all_handshakes():
    """
    Execute all API handshake verifications and report results.

    Returns:
        dict: Results for each service with pass/fail status.
    """
    results = {}
    all_passed = True

    # ── OpenAI API ──────────────────────────────────────────
    print("=" * 55)
    print("🔗 [1/3] OpenAI API Handshake")
    print("=" * 55)
    openai_result = verify_openai()
    results["openai"] = openai_result

    if openai_result["status"] == "connected":
        print(f"  ✅ Model: {openai_result['model']}")
        print(f"  ✅ Response: {openai_result['response_preview']}")
    else:
        print(f"  ❌ {openai_result['message']}")
        all_passed = False

    print()

    # ── Google Maps API ─────────────────────────────────────
    print("=" * 55)
    print("🔗 [2/3] Google Maps API Handshake")
    print("=" * 55)
    maps_result = verify_maps()
    results["google_maps"] = maps_result

    if maps_result["status"] == "connected":
        print(f"  ✅ Geocode test: {maps_result['test_query']}")
        print(f"     → {maps_result['formatted_address']}")
        print(
            f"     → lat: {maps_result['lat']}, "
            f"lng: {maps_result['lng']}"
        )
    else:
        print(f"  ❌ {maps_result['message']}")
        all_passed = False

    print()

    # ── PostgreSQL + PostGIS ────────────────────────────────
    print("=" * 55)
    print("🔗 [3/3] PostgreSQL + PostGIS Handshake")
    print("=" * 55)
    db_result = verify_db()
    results["postgresql"] = db_result

    if db_result["status"] == "connected":
        print(f"  ✅ Connected to: {db_result['database_url']}")
        if db_result["postgis_available"]:
            print(
                f"  ✅ PostGIS version: {db_result['postgis_version']}"
            )
        else:
            print(
                "  ⚠️  PostGIS not found. "
                "Run: CREATE EXTENSION postgis;"
            )
    else:
        print(f"  ❌ {db_result['message']}")
        all_passed = False

    # ── Summary ─────────────────────────────────────────────
    print()
    print("=" * 55)
    if all_passed:
        print("✅ ALL HANDSHAKES PASSED — Ready for Phase 3")
    else:
        failed = [
            k for k, v in results.items()
            if v["status"] != "connected"
        ]
        print(
            f"⚠️  HANDSHAKES INCOMPLETE — "
            f"Failed: {', '.join(failed)}"
        )
        print(
            "   Fix credentials in .env and re-run "
            "this script."
        )
    print("=" * 55)

    return results, all_passed


if __name__ == "__main__":
    _, passed = run_all_handshakes()
    if not passed:
        sys.exit(1)
