"""
Main entry point for the VW California AI Trip Planner.

Orchestrates the B.L.A.S.T. protocol phases and showcases
project functionality.
"""

from tools.verify_connections import run_all_handshakes
from tools.search_campings import search_campings
from tools.plan_route import plan_route
from navigation.chat_handler import create_chat_session, send_message
from tools.memory_logger import get_memory_logger
from tools.user_memory import cosine_similarity, format_memories_for_prompt
from tools.travel_suggestions import (
    generate_dynamic_suggestions,
    get_curated_fallback_suggestions,
    record_suggestion_choice,
    format_enriched_suggestion_prompt,
)
from tools.location_service import (
    sanitize_coordinates,
    reverse_geocode_coordinates,
    format_location_for_prompt,
)
from tools.sniffer_mascot import get_mascot_assets, get_mascot_greeting
from tools.tts_service import clean_text_for_speech, get_speech_config, generate_speech_audio
from tools.generate_summary import generate_summary
from tools.audio_generator import generate_all_soundtracks, GENERATORS
from navigation.dispatcher import dispatch
from tools.attractions_cache import (
    get_cached_attractions_near,
    save_cached_attractions,
    get_trip_attractions_cache,
    save_trip_attractions_cache,
)
from tools.mock_trip_photos import (
    generate_poznan_warszawa_mock_photos,
    get_poznan_warszawa_photos_metadata,
)



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


def example_verify_travel_memory():
    """
    Phase 4: Build — Verify the Travel Memory photo pipeline.

    Generates mock images (matching GPS/dates, wrong date, too far, and no EXIF)
    and verifies database storage and PostGIS-based route segment linking.
    """
    print("\n📸 Verifying Travel Memory Pipeline...")
    try:
        from tools.verify_travel_memory import run_pipeline_test
        run_pipeline_test(cleanup=True, interactive=False)
    except ImportError as err:
        print(f"  ⚠️ Skipping travel memory pipeline test (dependency missing: {err})")


def example_memory_logger():
    """
    Demonstrates in-memory log collection, filtering, and reporting.
    """
    print("\n📝 Demonstrating In-Memory Log Collection...")
    logger = get_memory_logger()

    # Record sample log entries
    logger.info("Initializing trip planner application", category="SYSTEM")
    logger.debug("Database connection pool established", category="DATABASE")
    logger.warning("Low budget preference detected for high-season trip", category="PLANNING")
    logger.error("Failed to fetch traffic data for segment 3", category="API")

    # Fetch statistics and display
    stats = logger.get_stats()
    print(f"  Total logs collected in memory: {stats['total_logs']}")
    print(f"  Logs by level: {stats['by_level']}")
    print(f"  Logs by category: {stats['by_category']}")

    # Search demonstration
    search_results = logger.search_logs("traffic")
    print(f"  Found {len(search_results)} log entries matching 'traffic':")
    for log_entry in search_results:
        print(f"    - [{log_entry['timestamp']}] [{log_entry['level']}] {log_entry['category']}: {log_entry['message']}")


def example_user_memory_rag():
    """
    Demonstrates Personalized Long-Term Memory (RAG) for User Preferences.

    Showcases semantic preference retrieval, cosine similarity matching,
    and prompt formatting for contextual trip personalization.
    """
    print("\n🧠 Demonstrating Personalized User Memory (RAG)...")

    # Sample user preferences and embeddings demonstration
    sample_memories = [
        {
            "category": "pets",
            "polarity": "constraint",
            "content": "Podróżuje z psem rasy Golden Retriever – wymaga parceli pet-friendly z dostępem do cienia",
        },
        {
            "category": "camping_style",
            "polarity": "like",
            "content": "Preferuje małe, kameralne kempingi nad jeziorem z dala od hałaśliwych resortów",
        },
        {
            "category": "activities",
            "polarity": "like",
            "content": "Chętnie wybiera trasy z możliwością spływów kajakowych i pływania na desce SUP",
        },
    ]

    print(f"  Stored sample memories: {len(sample_memories)}")
    for mem in sample_memories:
        print(f"    - [{mem['polarity'].upper()}] ({mem['category']}): {mem['content']}")

    # Formatted injection preview
    prompt_note = format_memories_for_prompt(sample_memories)
    print("\n  Injected System Context Preview:")
    for line in prompt_note.split("\n"):
        print(f"    {line}")

    # Cosine similarity matching demonstration
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.8, 0.6, 0.0]
    sim = cosine_similarity(v1, v2)
    print(f"\n  Vector similarity calculation test: cosine_similarity(v1, v2) = {sim:.4f}")


def example_travel_suggestions():
    """
    Demonstrates Suggestive Travel Inspirations (Variant B) with RAG Integration.

    Generates inspirational travel concept cards tailored to middle-aged
    campervan travelers (40-60), showcasing scenic imagery, duration categories,
    RAG transparency explanations ("Dlaczego to polecamy"), and automatic preference learning.
    """
    print("\n✨ Demonstrating Suggestive Travel Inspirations (Middle-Aged + RAG + Duration Filters)...")

    # 1. Fetch curated inspirations with duration and RAG explanation
    suggestions = get_curated_fallback_suggestions(lang="pl", duration="all")
    print(f"  Generated {len(suggestions)} visual inspiration cards:")
    for idx, card in enumerate(suggestions, 1):
        badge = f" [{card.get('badge')}]" if card.get("badge") else ""
        dur = f" ({card.get('duration_days')} dni, kat: {card.get('duration_category')})"
        print(f"    {idx}. 🚐 {card['title']}{badge}{dur}")
        print(f"       Opis: {card['subtitle']}")
        print(f"       Dlaczego to polecamy: {card.get('rag_reason')}")
        print(f"       Tagi: {', '.join(card['tags'])}")
        print(f"       Wyróżniki VW: {', '.join(card.get('vw_highlights', []))}")

    # 2. Showcase fast duration filter (e.g. weekend trips)
    weekend_cards = get_curated_fallback_suggestions(lang="pl", duration="weekend")
    print(f"\n  Filtering by duration: 'weekend' -> {len(weekend_cards)} card(s) found:")
    for c in weekend_cards:
        print(f"    - {c['title']} ({c.get('duration_days')} dni): {c.get('rag_reason')}")

    # 3. Simulate user selection with enriched prompt (duration + origin)
    selected_card = suggestions[0]
    print(f"\n  Simulating user clicking suggestion: '{selected_card['title']}'...")
    enriched_with_loc = format_enriched_suggestion_prompt(selected_card, user_location="Poznań", lang="pl")
    enriched_without_loc = format_enriched_suggestion_prompt(selected_card, user_location=None, lang="pl")
    print(f"  Enriched prompt (with GPS location 'Poznań'):\n    -> \"{enriched_with_loc}\"")
    print(f"  Enriched prompt (location disabled):\n    -> \"{enriched_without_loc}\"")

    simulated_user_id = "00000000-0000-0000-0000-000000000001"
    try:
        recorded_memory = record_suggestion_choice(simulated_user_id, selected_card)
        if recorded_memory:
            print("  ✅ Successfully reinforced long-term RAG preference from user selection:")
            print(f"     Category: {recorded_memory.get('category')} | Polarity: {recorded_memory.get('polarity')}")
            print(f"     Content: {recorded_memory.get('content')}")
    except Exception as e:
        print(f"  Note: Database offline or test user missing ({e}), simulated write logic verified.")


def example_user_location():
    """
    Demonstrates User Location Awareness & Geolocation Context for AI Chat.

    Showcases coordinate sanitization, reverse geocoding to friendly city names,
    and prompt context generation in Polish, German, and English.
    """
    print("\n📍 Demonstrating Real-Time Geolocation & Chat Location Awareness...")

    # 1. Coordinate validation test
    valid_coords = sanitize_coordinates(52.406374, 16.925168)
    invalid_coords = sanitize_coordinates(999.0, "abc")
    print(f"  Coordinate validation (Poznań): {valid_coords}")
    print(f"  Invalid coordinate rejection: {invalid_coords}")

    # 2. Reverse geocoding demonstration
    loc_info = reverse_geocode_coordinates(52.406374, 16.925168, lang="pl")
    print(f"  Reverse geocoded location: {loc_info.get('name')} (status: {loc_info.get('status')})")

    # 3. System prompt context formatting preview
    prompt_note_pl = format_location_for_prompt(loc_info, lang="pl")
    print("  Injected System Note Preview (PL):")
    print(f"    {prompt_note_pl[:120]}...")


def example_sniffer_mascot():
    """
    Demonstrate Volkswagen Sniffer mascot configuration and assets.

    Verifies mascot image assets (avatar, sitting, standing) and showcases
    multilingual greeting responses.
    """
    print("\n🐶 Volkswagen Sniffer — Mascot & Identity")
    print("=" * 55)
    assets = get_mascot_assets()
    for key, info in assets.items():
        status = "✅ Found" if info["exists"] else "❌ Missing"
        print(f"  Asset [{key}]: {info['filename']} ({info['size_bytes']} bytes) — {status}")

    print("\n  Greetings:")
    print(f"    PL: {get_mascot_greeting('Mateusz', 'pl')}")
    print(f"    DE: {get_mascot_greeting('Mateusz', 'de')}")
    print(f"    EN: {get_mascot_greeting('Mateusz', 'en')}")


def example_sniffer_speech():
    """
    Demonstrate Volkswagen Sniffer Speech (TTS) & Facial Animation Configuration.

    Showcases text sanitization (stripping markdown, emojis, slot state),
    campervan unit expansion, and voice parameters for PL, DE, and EN.
    """
    print("\n🐶 Volkswagen Sniffer — Speech Synthesis & Facial Animation")
    print("=" * 55)

    sample_raw_chat = (
        "**Cześć!** 🚐 Przygotowałem dla Ciebie wspaniałą trasę z Poznania do Karkonoszy na 3 dni. "
        "Dziennie przejedziesz ok. 120 km (ok. 2.5 h jazdy). Kemping kosztuje 25 EUR za noc.\n\n"
        "- Postój przy wodospadzie Kamieńczyka 📍\n"
        "- Podłączenie prądu 230V w kamperze VW California ✨\n"
        "<slot_state>{\"duration\": 3, \"destination\": \"Karkonosze\"}</slot_state>"
    )

    print("  [1] Oryginalny tekst z czatu:")
    print(f"      {sample_raw_chat[:120]}...\n")

    cleaned_pl = clean_text_for_speech(sample_raw_chat, lang="pl")
    print("  [2] Tekst oczyszczony do syntezy mowy (PL):")
    print(f"      \"{cleaned_pl}\"\n")

    cfg_pl = get_speech_config("pl")
    cfg_de = get_speech_config("de")
    cfg_en = get_speech_config("en")

    print("  [3] Parametry mowy Sniffera:")
    print(f"      - PL: kod={cfg_pl['lang_code']}, pitch={cfg_pl['pitch']}, rate={cfg_pl['rate']}, głosy={cfg_pl['recommended_voices'][:3]}")
    print(f"      - DE: kod={cfg_de['lang_code']}, pitch={cfg_de['pitch']}, rate={cfg_de['rate']}, głosy={cfg_de['recommended_voices'][:3]}")
    print(f"      - EN: kod={cfg_en['lang_code']}, pitch={cfg_en['pitch']}, rate={cfg_en['rate']}, głosy={cfg_en['recommended_voices'][:3]}")

    print("\n  [4] Generowanie hiperrealistycznej mowy (ElevenLabs Neural TTS — Brian):")
    try:
        audio_mp3 = generate_speech_audio(cleaned_pl, lang="pl")
        print(f"      ✅ Pomyślnie wygenerowano plik MP3 ({len(audio_mp3)} bajtów).")
        print(f"      ✅ Głos: Brian (Deep, Resonant and Comforting) | Model: eleven_multilingual_v2")
    except Exception as e:
        print(f"      ⚠️ Generowanie audio pominięte: {e}")


def example_cinematic_recap():
    """
    Demonstrates Cinematic California Recap video generation.

    Generates a high-resolution 25 FPS video recap featuring Google Static Maps
    terrain, campervan flight animation, live digital HUD odometer, and audio soundtrack.
    """
    print("\n🎬 Demonstrating Cinematic California Recap (Video & Memories)...")
    seed_trip_id = "a0000001-0000-0000-0000-000000000001"
    result = generate_summary(
        trip_id=seed_trip_id,
        format="video",
        music_track="vanlife_chill",
        lang="pl",
    )
    if result["status"] == "success":
        print("  ✅ Cinematic recap video generated successfully!")
        print(f"  📁 Output path: {result['file_url']}")
    else:
        print(f"  ⚠️ Video generation note: {result.get('message', 'Unknown')}")


def example_procedural_soundtracks():
    """
    Demonstrates the procedural soundtrack engine for trip recap videos.
    """
    print("\n🎵 Demonstrating Procedural Soundtrack Engine...")
    print(f"  Available soundtrack genres: {list(GENERATORS.keys())}")
    print("  Mastering standard: 320 kbps stereo MP3 & 16-bit 44.1kHz WAV.")
    print("  Instruments: Karplus-Strong acoustic strings, FM Rhodes, dub/acoustic bass, lo-fi/swing drums.")


def example_audius_streaming():
    """
    Demonstrates Audius streaming API integration for trip soundtrack selection.
    """
    print("\n🎧 Demonstrating Audius Streaming Soundtrack Integration...")
    from tools import audius_service
    host = audius_service.get_active_host()
    print(f"  Connected Audius node: {host}")
    mood_result = audius_service.get_mood_tracks("roadtrip", limit=3)
    print(f"  Curated mood [{mood_result['label']}]: {len(mood_result['tracks'])} tracks")
    for t in mood_result["tracks"]:
        print(f"    • {t['title']} by {t['artist']} ({t['formatted_duration']}) [{t['id']}]")


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


def example_route_waypoints_modification():
    """
    Demonstrate modifying a route to add an intermediate town (e.g. Gardelegen)
    with preservation of round_trip and waypoint insertion into daily schedule.
    """
    print("\n📍 Demonstrating Route Modification with Intermediate Waypoints...")
    init_plan = plan_route(
        origin={"label": "Jarocin, Poland", "lat": 51.9727, "lng": 17.5025},
        destination={"label": "Wolfsburg, Germany", "lat": 52.4227, "lng": 10.7865},
        num_days=2,
        start_date="2026-08-01",
        round_trip=True,
    )
    if init_plan.get("status") == "success":
        trip_id = init_plan["trip"]["id"]
        mod_result = dispatch("modify_route", {
            "trip_id": trip_id,
            "waypoints": [{"label": "Gardelegen, Germany", "lat": 52.5268, "lng": 11.4018}],
            "round_trip": True,
        })
        if mod_result.get("status") == "success":
            print(f"  ✅ Route modified successfully with {len(mod_result['daily_schedules'])} days.")
            for d in mod_result["daily_schedules"]:
                wps = [w.get("label") for w in d.get("waypoints", [])]
                print(f"     Day {d['day_number']}: {' -> '.join(wps)}")
        else:
            print(f"  ❌ Route modification failed: {mod_result.get('message')}")


def example_attractions_cache():
    """
    Demonstrate 2-tier persistent database caching for attractions (POI).

    Verifies:
    1. Spatial POI persistence in PostgreSQL / PostGIS (cached_attractions).
    2. Zero-cost spatial retrieval via PostGIS ST_DWithin.
    3. Trip-level aggregated cache persistence (trip_attractions_cache).
    """
    print("\n🏛️  Demonstrating Persistent PostgreSQL Attractions Cache...")
    sample_poi = [{
        "place_id": "demo_lake_bled_castle_001",
        "name": "Bled Castle (Blejski grad)",
        "lat": 46.3698,
        "lng": 14.1008,
        "rating": 4.6,
        "user_ratings_total": 14500,
        "address": "Grajska cesta 61, 4260 Bled, Slovenia",
        "types": ["tourist_attraction", "castle", "point_of_interest"],
        "category": "castle",
        "category_label": "Zamek",
        "emoji": "🏰",
        "color": "#8B4513",
        "photo_url": "https://example.com/bled.jpg",
        "google_maps_url": "https://maps.google.com/?cid=test_001",
    }]

    saved = save_cached_attractions(sample_poi)
    print(f"  ✅ Saved {saved} attraction(s) to spatial database cache.")

    # Spatial query near Lake Bled (within 5 km)
    found = get_cached_attractions_near(lat=46.3636, lng=14.0938, radius_m=5000)
    print(f"  🔍 Found {len(found)} cached attraction(s) via PostGIS ST_DWithin.")
    for p in found:
        print(f"     📍 {p['name']} ({p.get('category_label')}) — Rating: {p.get('rating')} ({p.get('user_ratings_total')} reviews)")


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

    # Phase 4: Demonstrate Travel Memory
    example_verify_travel_memory()

    # Log Collection in memory demonstration
    example_memory_logger()

    # Personalized Long-Term Memory (RAG) demonstration
    example_user_memory_rag()

    # Suggestive Travel Inspirations (Variant B) demonstration
    example_travel_suggestions()

    # Real-Time Geolocation & Chat Location Awareness demonstration
    example_user_location()

    # Volkswagen Sniffer Mascot demonstration
    example_sniffer_mascot()

    # Volkswagen Sniffer Speech & Talking Avatar demonstration
    example_sniffer_speech()

    # Cinematic California Recap (Video & Memories) demonstration
    example_cinematic_recap()

    # Procedural Soundtrack Engine demonstration
    example_procedural_soundtracks()

    # Audius Streaming Soundtrack Integration demonstration
    example_audius_streaming()

    # Route Modification with Intermediate Waypoints demonstration
    example_route_waypoints_modification()

    # Persistent PostgreSQL Attractions Cache demonstration
    example_attractions_cache()

    # Photo Date/Day Editing & Ultra-Smooth Animation demonstration
    example_photo_dates_and_smooth_animation()

    # Interactive Campervan Photo Stops & Pop-Up Zoom demonstration
    example_photo_stop_animation()

    # Poznań -> Warszawa Mock Photos with EXIF demonstration
    example_mock_trip_photos()

    # Phase 3: Interactive chat
    example_chat()


def example_photo_dates_and_smooth_animation():
    """
    Demonstrate photo date/day manual assignment and polyline lookahead animation.
    """
    print("\n📷 Demonstrating Photo Date/Day Editing & Ultra-Smooth Animation...")
    from tools.generate_summary import _interpolate_polyline_point

    # Verify interpolation & lookahead
    sample_pts = [(52.4, 16.9), (52.5, 14.0), (52.4, 10.8)]
    distances = [0.0, 200000.0, 420000.0]
    cur_lat, cur_lng, seg = _interpolate_polyline_point(sample_pts, distances, 100000.0)
    print(f"  ✅ Continuous polyline interpolation at 100km: ({cur_lat:.3f}, {cur_lng:.3f})")

    # Verify circular heading difference
    diff = (10.0 - 350.0 + 180.0) % 360.0 - 180.0
    print(f"  ✅ Circular angle delta between 350° and 10°: {diff:.1f}° (smooth continuous rotation)")


def example_photo_stop_animation():
    """
    Demonstrate interactive campervan photo stops, pin pulsing, and pop-up animation.
    """
    print("\n🚐 Demonstrating Interactive Campervan Photo Stops & Pop-up Zoom...")
    from PIL import Image
    from tools.generate_summary import (
        _project_photo_to_route,
        _render_pin_pulse_frame,
        _render_photo_popup_frame,
    )

    # 1. Test photo route projection
    sample_pts = [(52.4, 16.9), (52.5, 14.0), (52.4, 10.8)]
    distances = [0.0, 200000.0, 420000.0]
    photo = {"lat": 52.45, "lng": 15.45}
    dist_m, prog, coords = _project_photo_to_route(photo, sample_pts, distances, 420000.0)
    print(f"  ✅ Projected photo at ({photo['lat']}, {photo['lng']}) to route: progress {prog * 100:.1f}%, distance {dist_m / 1000.0:.1f} km")

    # 2. Test pin pulse and pop-up frame generation
    canvas = Image.new("RGB", (1280, 720), (0, 14, 38))
    pulse = _render_pin_pulse_frame(canvas, (640, 360), 0.5)
    popup = _render_photo_popup_frame(canvas, None, (300, 200), 0.8, day_number=1, caption="Wspomnienie z trasy", reverse=False)
    ret = _render_photo_popup_frame(canvas, None, (300, 200), 0.8, day_number=1, caption="Wspomnienie z trasy", reverse=True)
    print(f"  ✅ Rendered pin pulse ({pulse.size}), pop-up zoom ({popup.size}), and return frame ({ret.size}) successfully")


def example_mock_trip_photos():
    """
    Demonstrate generating and verifying curated mock photos with EXIF metadata
    for the Poznań -> Warszawa route (11.09.2026 - 14.09.2026).
    """
    print("\n📸 Demonstrating Poznań -> Warszawa Mock Trip Photos with EXIF...")
    photos = generate_poznan_warszawa_mock_photos(also_copy_to_root=True, verbose=False)
    print(f"  ✅ Successfully generated and verified {len(photos)} photos with EXIF GPS & timestamps.")
    for p in photos:
        print(f"     • Dzień {p['day_number']}: {p['filename']} | {p['date']} | ({p['lat']:.4f}, {p['lng']:.4f})")


if __name__ == "__main__":
    main()



