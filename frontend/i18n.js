/**
 * VW California AI Trip Planner — i18n Internationalization Module
 * Supports Polish ('pl') and German ('de').
 */const translations = {
    pl: {
        // Navigation
        "nav_plan": "Plan",
        "nav_map": "Mapa",
        "nav_memory": "Pamięć",
        "nav_trips": "Wyjazdy",
        "nav_account": "Konto",

        // Chat Header & Placeholders
        "chat_greeting": "Witaj, podróżniku.",
        "chat_greeting_user": "Witaj, {name}!",
        "chat_sub": "Dokąd chcesz pojechać swoim VW California?",

        // Welcome Overlay
        "welcome_badge": "🐶 Volkswagen Sniffer — AI Trip Planner",
        "welcome_sniffer_badge": "🐶 Volkswagen Sniffer",
        "sniffer_role_tag": "Przewodnik VW",
        "sniffer_voice_toggle_on": "Głos Sniffera: Włączony",
        "sniffer_voice_toggle_off": "Głos Sniffera: Wyciszony",
        "sniffer_voice_tooltip_on": "Głos Sniffera jest włączony. Kliknij, aby wyciszyć.",
        "sniffer_voice_tooltip_off": "Głos Sniffera jest wyciszony. Kliknij, aby włączyć.",
        "sniffer_speak_msg": "Odsłuchaj",
        "sniffer_stop_msg": "Zatrzymaj",
        "welcome_title": "Witaj!",
        "welcome_user_greeting": "Witaj, {name}!",
        "welcome_subtitle": "Dokąd dzisiaj zmierzamy?",
        "chat_placeholder": "Zadaj pytanie lub opisz swoją wymarzoną trasę...",
        "chat_send": "Wyślij",
        "chat_helper_text": "Volkswagen Sniffer może popełniać błędy. Sprawdź ważne informacje.",
        "mic_tooltip_start": "Dyktuj wiadomość",
        "mic_tooltip_stop": "Zatrzymaj nasłuchiwanie",
        "mic_not_supported": "Twoja przeglądarka nie obsługuje dyktowania głosowego.",
        "planning_route_indicator": "Sniffer węszy najlepszą trasę i kempingi...",

        // Geolocation in Chat
        "location_active": "Lokalizacja: Wł.",
        "location_disabled": "Lokalizacja: Wył.",
        "location_acquiring": "Ustalanie pozycji...",
        "location_unavailable": "Lokalizacja: Brak GPS",
        "location_tooltip_on": "Automatyczna geolokalizacja jest włączona. Kliknij, aby wyłączyć.",
        "location_tooltip_off": "Automatyczna geolokalizacja jest wyłączona. Kliknij, aby włączyć.",
        "location_current_label": "Twoja lokalizacja:",
        "location_btn_disable": "Wyłącz",
        "location_btn_enable": "Włącz",
        "location_toast_on": "Włączono automatyczną geolokalizację w czacie",
        "location_toast_off": "Wyłączono automatyczną geolokalizację w czacie",


        // Quick Actions & Welcome Hero (Option 4)
        "qa_heading": "Dokąd dzisiaj zmierzamy?",
        "chat_welcome_heading": "Dokąd dzisiaj zmierzamy?",
        "chat_welcome_heading_user": "Dokąd dzisiaj zmierzamy, {name}?",
        "chat_welcome_sub": "Zaprojektuj trasę dla swojego VW California lub skorzystaj z rekomendacji AI wywęszonych przez Sniffera.",
        "hero_inspiration_badge": "Wywęszone przez Volkswagen Sniffer",
        "hero_inspiration_title": "Odkryj inspiracje na podróż kamperem",
        "hero_inspiration_desc": "Gotowe propozycje tras wywęszone przez Sniffera – zasięg kampera, parcele z prądem 230V i malownicze postoje.",
        "hero_inspiration_btn": "Przeglądaj inspiracje ✨",
        "qa_1_title": "Tydzień w górach",
        "qa_1_sub": "z rodziną",
        "qa_1_prompt": "Chcę pojechać w góry z rodziną, mam tydzień",
        "qa_2_title": "Wybrzeże Adriatyku",
        "qa_2_sub": "kempingi do 30€/noc",
        "qa_2_prompt": "Szukam kempingów z prądem i prysznicami nad Adriatykiem, budżet do 30 euro",
        "qa_3_title": "Monachium → Chorwacja",
        "qa_3_sub": "5 dni, przez Słowenię",
        "qa_3_prompt": "Zaplanuj mi trasę 5-dniową z Monachium do Chorwacji przez Słowenię",
        "qa_4_title": "Dzikie biwaki",
        "qa_4_sub": "10 dni solo",
        "qa_4_prompt": "Jadę sam, jestem doświadczony, preferuję dzikie biwaki. Mam 10 dni",

        // Travel Suggestions Modal (Middle-Aged + RAG)
        "btn_travel_inspirations": "Inspiracje",
        "suggestions_vw_badge": "Wywęszone przez Sniffera",
        "suggestions_title": "Dokąd dzisiaj zmierzasz?",
        "suggestions_subtitle": "Oto starannie dobrane pomysły na podróż — malownicze trasy, spokojne tempo, kempingi z prądem 230V i lokalne smaki.",
        "suggestions_refresh": "Nowe inspiracje",
        "suggestions_skip": "Wpisz własny cel na czacie →",
        "suggestions_badge_matched": "Dopasowane do Ciebie ✨",
        "suggestions_badge_curated": "Rekomendacja VW",
        "suggestions_pill_all": "Wszystkie długości",
        "suggestions_pill_weekend": "Weekend (2–4 dni)",
        "suggestions_pill_week": "Tydzień (5–8 dni)",
        "suggestions_pill_expedition": "Wyprawa (9–14 dni)",
        "suggestions_days_badge": "dni",
        "suggestions_days_badge_singular": "dzień",
        "suggestions_rag_reason_prefix": "Dlaczego to polecamy",
        "suggestions_why_text": "Warto wiedzieć",

        // Slot Progress Bar
        "slot_vibe": "Cel",
        "slot_experience": "Doświadczenie",
        "slot_pace": "Tempo",
        "slot_infrastructure": "Kempingi",
        "slot_summary": "Podsumowanie",

        // Map View & Side Panel
        "map_header_title": "Interaktywna Mapa Trasy",
        "btn_show_on_map": "Pokaż na mapie",
        "map_btn_plan": "Plan",
        "map_btn_center": "Wyśrodkuj",
        "map_btn_campings": "Kempingi",
        "map_btn_attractions": "Atrakcje",
        "map_btn_top5": "Top 8",
        "map_chat_bubble": "Czat",
        "map_chat_header": "Volkswagen Sniffer",
        "map_chat_placeholder": "Zapytaj o trasę...",
        "map_btn_back_to_chat": "Czat",
        "stat_days": "Dni",
        "stat_km": "km",
        "stat_hours": "Czas jazdy",
        "stat_campings": "Noclegi",
        "stat_label_days": "Dni",
        "stat_label_km": "Kilometrów",
        "stat_label_drive": "Jazdy",
        "stat_label_stops": "Postojów",
        "btn_export_summary": "Eksportuj Podsumowanie Wyjazdu",
        "btn_suggest_attractions": "Sugeruj Atrakcje",

        // Memory View
        "memory_title": "Wspomnienia z Podróży",
        "memory_sub": "Wgraj zdjęcia ze swojego wyjazdu VW California — zostaną automatycznie sparowane z trasą na mapie dzięki danym GPS/EXIF.",
        "memory_drag_drop": "Przeciągnij zdjęcia tutaj lub kliknij, żeby wybrać",
        "memory_formats_hint": "JPEG, PNG, HEIC — dane GPS zostaną automatycznie odczytane.<br>Brak GPS? Przypniesz zdjęcie ręcznie na mapie.",
        "memory_select_files": "Wybierz pliki",
        "memory_uploaded_photos": "Wgrane zdjęcia",
        "memory_photo_empty": "Brak zdjęć — wgraj swoje wspomnienia z trasy",
        "memory_btn_summary": "Stwórz podsumowanie podróży",
        "memory_btn_gallery": "Galeria Memories",
        "pin_photo_prompt": "📍 Kliknij na mapie, aby przypiąć to zdjęcie",
        "btn_cancel": "Anuluj",
        "btn_save": "Zapisz",
        "photo_edit_title": "Edytuj datę i lokalizację zdjęcia",
        "photo_edit_date_label": "📅 Data wykonania zdjęcia:",
        "photo_edit_date_hint": "Wpływa na kolejność i przypisanie do odpowiedniego dnia w filmie z podróży.",
        "photo_edit_day_label": "🚐 Przypisz do dnia wyprawy:",
        "photo_edit_day_auto": "Automatycznie (wg daty / lokalizacji)",
        "photo_edit_location_label": "📍 Pozycja na mapie:",
        "photo_edit_pick_map": "🗺️ Wskaż na mapie",
        "summary_trip_dates_label": "Termin wyprawy:",
        "summary_btn_edit_dates": "✏️ Zmień datę",

        // Summary Modal & Music Export
        "summary_modal_title": "Wybierz format eksportu",
        "summary_modal_sub": "Jak chcesz podzielić się swoją przygodą?",
        "summary_soundtrack_label": "🎵 Ścieżka dźwiękowa do filmu:",
        "summary_audius_badge": "Streaming Audius",
        "summary_music_search_placeholder": "🔍 Szukaj piosenki, wykonawcy na Audius...",
        "summary_selected_track_label": "Wybrana ścieżka:",
        "summary_music_no_music_opt": "🔇 Bez muzyki",
        "summary_music_searching": "Wyszukiwanie utworów na Audius...",
        "summary_music_no_results": "Brak wyników wyszukiwania.",
        "summary_btn_slideshow": "🖼️ Pokaz slajdów",
        "summary_btn_video": "🎬 Film z podróży (Cinematic MP4)",
        "summary_btn_preview": "▶ Odsłuchaj",
        "summary_btn_stop": "⏸ Zatrzymaj",
        "summary_music_none": "🔇 Bez muzyki",
        "summary_music_sunset": "🌅 Acoustic Sunset",
        "summary_music_vanlife": "🚐 Vanlife Chill",
        "summary_music_breeze": "🌊 Coastal Breeze",
        "summary_music_alpine": "🌲 Alpine Acoustic",
        "summary_music_jazz": "🎷 Jazz Trio",
        "summary_music_folk": "🎸 Folk Guitar",
        "summary_music_reggae": "☀️ Reggae Sunshine",
        "summary_music_cinematic": "🎬 Cinematic Orchestral",
        "summary_music_lofi": "🎧 Electronic Lo-Fi",
        "summary_generating": "Generuję podsumowanie podróży... 🚐",
        "summary_download_video": "📥 Pobierz wideo MP4",
        "summary_download_pdf": "📥 Pobierz dokument PDF",
        "summary_slide_counter": "Slajd {current} / {total}",
        "summary_btn_prev": "◀ Poprzedni",
        "summary_btn_next": "Następny ▶",
        "summary_btn_download_slide": "💾 Pobierz slajd (PNG)",

        // Top 8 Attractions Modal
        "top_attractions_title": "🌟 Top 8 Must-See Atrakcji na Trasie",
        "top_attractions_subtitle": "Najchętniej odwiedzane i najbardziej spektakularne miejsca wyselekcjonowane dla Twojej wyprawy VW California:",
        "top_attractions_sort": "Sortuj:",
        "top_attractions_sort_reviews": "👥 Najwięcej opinii",
        "top_attractions_sort_rating": "🌟 Najwyżej oceniane",
        "top_attractions_sort_day": "📅 Według dni trasy (Dzień 1 ➔ N)",
        "top_attractions_page_fmt": "Atrakcje #{start}–#{end} z {total}",
        "top_attractions_prev": "⬅️ Poprzednie 8",
        "top_attractions_next": "Następne 8 ➡️",
        "top_attractions_focus_map": "🎯 Pokaż na mapie",

        // Modals & User Preferences
        "trips_modal_title": "🗺️ Moje Zapisane Podróże",
        "trips_loading": "Wczytywanie wyjazdów...",
        "trips_empty": "Brak zapisanych wyjazdów. Zaplanuj swój pierwszy wyjazd w czacie!",
        "trips_error": "Błąd podczas wczytywania wyjazdów.",
        "connection_error": "Błąd połączenia z serwerem. Upewnij się, że serwer jest uruchomiony.",
        "account_modal_title": "Ustawienia Konta",
        "account_save": "Zapisz preferencje",
        "account_saving": "Zapisywanie...",
        "account_logout": "Wyloguj się",

        // Profile & Vehicle Preferences Modal
        "pref_title": "⚙️ Profil & Preferencje VW California",
        "pref_vehicle_model": "Model Pojazdu:",
        "pref_max_drive_hours": "Maksymalny dzienny czas jazdy (h):",
        "pref_hookup_type": "Typ Przyłącza Prądu:",
        "pref_hookup_shore": "Shore Power (Prąd kempingowy CEE)",
        "pref_hookup_full": "Full Hookup (Prąd + Woda + Ścieki)",
        "pref_hookup_none": "Brak (Samowystarczalny / Solary)",
        "pref_max_budget": "Maksymalny budżet za noc (€):",
        "pref_required_amenities": "Wymagane Udogodnienia:",
        "pref_amenity_power": "Prąd",
        "pref_amenity_water": "Woda",
        "pref_amenity_showers": "Prysznice",
        "pref_amenity_wifi": "Wi-Fi",
        "pref_amenity_waste": "Zrzut ścieków",
        "pref_btn_save": "Zapisz preferencje",
        "pref_btn_tutorial": "▶️ Samouczek",
        "pref_btn_logout": "Wyloguj się",

        // Auth
        "auth_login_tab": "Logowanie",
        "auth_register_tab": "Rejestracja",
        "auth_email": "Adres E-mail",
        "auth_password": "Hasło",
        "auth_display_name": "Imię / Nazwa",
        "auth_login_btn": "Zaloguj się",
        "auth_logging_in": "Logowanie...",
        "auth_register_btn": "Utwórz konto",
        "auth_creating": "Tworzenie...",
        "auth_switch_no_account": "Nie masz konta? Zarejestruj się",
        "auth_switch_has_account": "Masz już konto? Zaloguj się",

        // Tutorial
        "tut_step_fmt": "Krok {step} z {total}",
        "tut_step1_title": "Wskaźniki postępu trasy (5 Kroków)",
        "tut_step1_desc": "Śledź status dopasowania Twojej trasy: Cel, Doświadczenie, Tempo, Kempingi oraz Podsumowanie. W miarę rozmowy z asystentem AI wskaźniki automatycznie zapełniają się na zielono!",
        "tut_step2_title": "Inspiracje Podróżnicze AI",
        "tut_step2_desc": "Kliknij przycisk 'Inspiracje' w nagłówku, aby odkryć gotowe scenariusze wyjazdów dla VW California (Weekend, Tydzień, Wyprawa) dopasowane do Twojej lokalizacji startowej GPS z wyjaśnieniem 'Dlaczego to polecamy'!",
        "tut_step3_title": "Interaktywna Mapa & Warstwy na Żywo",
        "tut_step3_desc": "Przeglądaj trasę z aktualnym natężeniem ruchu i pogodą. Odkrywaj kempingi ze zweryfikowanymi przyłączami dla VW California (prąd CEE, woda), atrakcje turystyczne oraz korzystaj z pływającego czatu na mapie!",
        "tut_step4_title": "Pamięć Podróży & Galeria Wspomnień",
        "tut_step4_desc": "Twórz cyfrowy dziennik swoich wypraw! Wgraj zdjęcia ze smartfona — system automatycznie odczyta dane GPS z plików EXIF, przypnie je do mapy oraz wygeneruje multimedialne podsumowanie podróży!",
        "tut_step5_title": "Moje Wyjazdy & Profil VW California",
        "tut_step5_desc": "Zarządzaj zapisanymi trasami i ich statusami. W profilu skonfiguruj swój model kampera (Ocean, Beach, Coast, Grand California), przyłącza prądu CEE, budżet i dzienny limit godzin za kółkiem!",
        "tut_skip": "Pomiń tutorial",
        "tut_next": "Dalej &rarr;",
        "tut_finish": "Zakończ 🚀",

        // View Tutorials (PL)
        "tut_map_step1_title": "Narzędzia i Warstwy Trasy",
        "tut_map_step1_desc": "Włączaj podgląd natężenia ruchu drogowego, aktualną pogodę na trasie, filtruj Top 5 kempingów dla kampera oraz odkrywaj rekomendowane atrakcje turystyczne.",
        "tut_map_step2_title": "Harmonogram Dni & Kempingi",
        "tut_map_step2_desc": "Sprawdzaj statystyki trasy (kilometry, czas jazdy), plan poszczególnych dni oraz szczegóły wybranego kempingu z przyłączami prądu i wody.",
        "tut_map_step3_title": "Pływający Asystent na Mapie",
        "tut_map_step3_desc": "Potrzebujesz zmienić trasę lub dodać przystanek? Użyj pływającego czatu, aby na bieżąco rozmawiać z asystentem bez opuszczania mapy!",

        "tut_mem_step1_title": "Wgrywanie Zdjęć z Trasy",
        "tut_mem_step1_desc": "Przeciągnij zdjęcia z telefonu lub aparatu (JPEG, PNG, HEIC). System automatycznie odczyta współrzędne GPS i czas z metadanych EXIF.",
        "tut_mem_step2_title": "Automatyczne Pinezki na Mapie",
        "tut_mem_step2_desc": "Zdjęcia zostaną przypisane do konkretnych dni wyprawy oraz oznaczone na mapie trasy, tworząc interaktywną oś czasu wyjazdu.",
        "tut_mem_step3_title": "Generator Podsumowania Wyjazdu",
        "tut_mem_step3_desc": "Kliknij, aby wygenerować efektowne podsumowanie podróży łączące trasę, odwiedzone kempingi i Twoje najlepsze fotografie!",

        "tut_trips_step1_title": "Historia Podróży & Statusy",
        "tut_trips_step1_desc": "Przeglądaj wszystkie zaplanowane i odbyte wyprawy. Filtruj po statusach (Szkic, Zaplanowano, W trakcie, Zakończono) i ładuj trasę jednym kliknięciem.",
        "tut_trips_step2_title": "Profil i Preferencje Pojazdu",
        "tut_trips_step2_desc": "Dopasuj model swojego kampera (Ocean, Beach, Coast, Grand California), typ przyłącza prądu CEE, budżet i dzienny limit jazdy.",

        // Statuses
        "status_draft": "Szkic",
        "status_planned": "Zaplanowano",
        "status_active": "W trakcie",
        "status_completed": "Zakończono",

        // Weather & General
        "weather_title": "Prognoza pogody",
        "day_card_day": "Dzień {day}",
        "day_card_drive": "Jazda: {hours}h ({km} km)",
        "camping_modal_title": "🏕️ Wybierz Nocleg dla Dnia {day}",
        "camping_modal_sub": "Oto 3 propozycje kempingów dostosowane do Twojego VW California. Wybierz idealne miejsce na nocleg:",
        "camping_select_btn": "Wybierz ten kemping",
        "camping_selected_badge": "✓ Wybrany nocleg",
        "camping_change_btn": "🏕️ Wybierz / zmień kemping",
        "camping_per_night": "€/noc",
        "camping_next_day": "Kolejny dzień &rarr;",
        "camping_confirm_all": "Gotowe",
        "photo_preview_tag": "📷 Podgląd",
        "add_to_route_btn": "➕ Dodaj do drogi",
        "added_to_route_btn": "✓ Dodano do drogi",
        "adding_to_route_btn": "Dodawanie...",
        "attraction_added_toast": "Dodano atrakcję {name} do Dnia {day}!",
        "waypoint_camping": "Nocleg",
        "waypoint_attraction": "Atrakcja",
        "waypoint_start": "Start",
        "waypoint_end": "Cel",
        "legend_start_end": "Start / Koniec",
        "legend_outbound_route": "Trasa dojazdowa",
        "legend_return_route": "Trasa powrotna",
        "legend_day_stages": "Etapy dni (D1, D2...)",
        "legend_camping": "Kemping",
        "legend_attraction": "⭐ Atrakcja",
        "legend_photo": "Zdjęcie",
        "day_return_badge": "Powrót",
        "lang_name_pl": "Polski",
        "lang_name_de": "Deutsch",
        "lang_name_en": "English"
    },
    de: {
        // Navigation
        "nav_plan": "Planen",
        "nav_map": "Karte",
        "nav_memory": "Erinnerungen",
        "nav_trips": "Reisen",
        "nav_account": "Konto",

        // Chat Header & Placeholders
        "chat_greeting": "Willkommen, Reiselustiger.",
        "chat_greeting_user": "Willkommen, {name}!",
        "chat_sub": "Wohin möchtest du mit deinem VW California fahren?",

        // Welcome Overlay
        "welcome_badge": "🐶 Volkswagen Sniffer — AI Trip Planner",
        "welcome_sniffer_badge": "🐶 Volkswagen Sniffer",
        "sniffer_role_tag": "VW Reisebegleiter",
        "sniffer_voice_toggle_on": "Sniffer Stimme: An",
        "sniffer_voice_toggle_off": "Sniffer Stimme: Stumm",
        "sniffer_voice_tooltip_on": "Sniffer Stimme ist aktiviert. Klicken zum Stummschalten.",
        "sniffer_voice_tooltip_off": "Sniffer Stimme ist stummgeschaltet. Klicken zum Einschalten.",
        "sniffer_speak_msg": "Vorlesen",
        "sniffer_stop_msg": "Stopp",
        "welcome_title": "Willkommen!",
        "welcome_user_greeting": "Willkommen, {name}!",
        "welcome_subtitle": "Wohin soll die Reise heute gehen?",
        "chat_placeholder": "Stelle eine Frage oder beschreibe deine Traumroute...",
        "chat_send": "Senden",
        "chat_helper_text": "Volkswagen Sniffer kann Fehler machen. Überprüfe wichtige Informationen.",
        "mic_tooltip_start": "Nachricht diktieren",
        "mic_tooltip_stop": "Zuhören stoppen",
        "mic_not_supported": "Dein Browser unterstützt keine Sprachdiktat-Funktion.",
        "planning_route_indicator": "Sniffer schnüffelt die beste Route und Campingplätze aus...",

        // Geolocation in Chat
        "location_active": "Standort: Ein",
        "location_disabled": "Standort: Aus",
        "location_acquiring": "Standort wird ermittelt...",
        "location_unavailable": "Standort: Kein GPS",
        "location_tooltip_on": "Automatische Standortermittlung ist aktiv. Klicken zum Deaktivieren.",
        "location_tooltip_off": "Automatische Standortermittlung ist deaktiviert. Klicken zum Aktivieren.",
        "location_current_label": "Dein Standort:",
        "location_btn_disable": "Deaktivieren",
        "location_btn_enable": "Aktivieren",
        "location_toast_on": "Automatische Standortermittlung im Chat aktiviert",
        "location_toast_off": "Automatische Standortermittlung im Chat deaktiviert",


        // Quick Actions & Welcome Hero (Option 4)
        "qa_heading": "Wohin soll die Reise heute gehen?",
        "chat_welcome_heading": "Wohin soll die Reise heute gehen?",
        "chat_welcome_heading_user": "Wohin soll die Reise heute gehen, {name}?",
        "chat_welcome_sub": "Plane deine Route für deinen VW California oder nutze smarte KI-Empfehlungen, die von Sniffer erschnüffelt wurden.",
        "hero_inspiration_badge": "Von Volkswagen Sniffer erschnüffelt",
        "hero_inspiration_title": "Entdecke Inspirationen für deine Camper-Reise",
        "hero_inspiration_desc": "Von Sniffer kuratierte Routenvorschläge – Camper-Reichweite, 230V-Stellplätze und malerische Stopps.",
        "hero_inspiration_btn": "Inspirationen entdecken ✨",
        "qa_1_title": "Woche in den Bergen",
        "qa_1_sub": "mit Familie",
        "qa_1_prompt": "Ich möchte mit der Familie für eine Woche in die Berge fahren",
        "qa_2_title": "Adriaküste",
        "qa_2_sub": "Camping bis 30€/Nacht",
        "qa_2_prompt": "Ich suche Campingplätze mit Strom und Duschen an der Adria, Budget bis 30 Euro",
        "qa_3_title": "München → Kroatien",
        "qa_3_sub": "5 Tage, über Slowenien",
        "qa_3_prompt": "Plane mir eine 5-tägige Route von München nach Kroatien über Slowenien",
        "qa_4_title": "Freistehen / Wildcamping",
        "qa_4_sub": "10 Tage solo",
        "qa_4_prompt": "Ich fahre alleine, bin erfahren und bevorzuge Freistehen. Ich habe 10 Tage Zeit",

        // Travel Suggestions Modal (Middle-Aged + RAG)
        "btn_travel_inspirations": "Inspirationen",
        "suggestions_vw_badge": "Von Sniffer erschnüffelt",
        "suggestions_title": "Wohin soll die Reise heute gehen?",
        "suggestions_subtitle": "Ausgewählte Reiseideen für Deinen Camper — Panoramarouten, entspanntes Reisetempo, Stellplätze mit 230V und regionale Genüsse.",
        "suggestions_refresh": "Neue Inspirationen",
        "suggestions_skip": "Eigenes Ziel im Chat eingeben →",
        "suggestions_badge_matched": "Auf Dich abgestimmt ✨",
        "suggestions_badge_curated": "VW Empfehlung",
        "suggestions_pill_all": "Alle Dauern",
        "suggestions_pill_weekend": "Wochenende (2–4 Tage)",
        "suggestions_pill_week": "Eine Woche (5–8 Tage)",
        "suggestions_pill_expedition": "Fernreise (9–14 Tage)",
        "suggestions_days_badge": "Tage",
        "suggestions_days_badge_singular": "Tag",
        "suggestions_rag_reason_prefix": "Warum wir das empfehlen",
        "suggestions_why_text": "Gut zu wissen",

        // Slot Progress Bar
        "slot_vibe": "Ziel",
        "slot_experience": "Erfahrung",
        "slot_pace": "Tempo",
        "slot_infrastructure": "Campingplätze",
        "slot_summary": "Zusammenfassung",

        // Map View & Side Panel
        "map_header_title": "Interaktive Routenkarte",
        "btn_show_on_map": "Auf der Karte anzeigen",
        "map_btn_plan": "Plan",
        "map_btn_center": "Zentrieren",
        "map_btn_campings": "Campingplätze",
        "map_btn_attractions": "Highlights",
        "map_btn_top5": "Top 8",
        "map_chat_bubble": "Chat",
        "map_chat_header": "Volkswagen Sniffer",
        "map_chat_placeholder": "Frage zur Route stellen...",
        "map_btn_back_to_chat": "Chat",
        "stat_days": "Tage",
        "stat_km": "km",
        "stat_hours": "Fahrtzeit",
        "stat_campings": "Übernachtungen",
        "stat_label_days": "Tage",
        "stat_label_km": "Kilometer",
        "stat_label_drive": "Fahrtzeit",
        "stat_label_stops": "Stopps",
        "btn_export_summary": "Reisezusammenfassung exportieren",
        "btn_suggest_attractions": "Highlights vorschlagen",

        // Memory View
        "memory_title": "Reiseerinnerungen",
        "memory_sub": "Lade Fotos von deiner VW California Reise hoch — sie werden dank GPS/EXIF-Daten automatisch mit der Route auf der Karte verknüpft.",
        "memory_drag_drop": "Fotos hierher ziehen oder klicken zum Auswählen",
        "memory_formats_hint": "JPEG, PNG, HEIC — GPS-Daten werden automatisch ausgelesen.<br>Kein GPS? Heften Sie das Foto manuell auf der Karte an.",
        "memory_select_files": "Dateien auswählen",
        "memory_uploaded_photos": "Hochgeladene Fotos",
        "memory_photo_empty": "Keine Fotos vorhanden — lade deine Reiseerinnerungen hoch",
        "memory_btn_summary": "Reisezusammenfassung erstellen",
        "memory_btn_gallery": "Memories-Galerie",
        "pin_photo_prompt": "📍 Klicke auf die Karte, um dieses Foto anzuheften",
        "btn_cancel": "Abbrechen",
        "btn_save": "Speichern",
        "photo_edit_title": "Foto-Datum und Standort bearbeiten",
        "photo_edit_date_label": "📅 Aufnahmedatum des Fotos:",
        "photo_edit_date_hint": "Bestimmt die Reihenfolge und Zuordnung zum Reisetag im Video.",
        "photo_edit_day_label": "🚐 Reisetag zuweisen:",
        "photo_edit_day_auto": "Automatisch (nach Datum / Standort)",
        "photo_edit_location_label": "📍 Position auf der Karte:",
        "photo_edit_pick_map": "🗺️ Auf Karte wählen",
        "summary_trip_dates_label": "Reisezeitraum:",
        "summary_btn_edit_dates": "✏️ Daten ändern",

        // Summary Modal & Music Export
        "summary_modal_title": "Exportformat wählen",
        "summary_modal_sub": "Wie möchtest du dein Abenteuer teilen?",
        "summary_soundtrack_label": "🎵 Soundtrack für dein Video:",
        "summary_audius_badge": "Audius Streaming",
        "summary_music_search_placeholder": "🔍 Titel oder Künstler auf Audius suchen...",
        "summary_selected_track_label": "Ausgewählter Soundtrack:",
        "summary_music_no_music_opt": "🔇 Ohne Musik",
        "summary_music_searching": "Suche Titel auf Audius...",
        "summary_music_no_results": "Keine Titel gefunden.",
        "summary_btn_slideshow": "🖼️ Diashow",
        "summary_btn_video": "🎬 Reisefilm (Cinematic MP4)",
        "summary_btn_preview": "▶ Anhören",
        "summary_btn_stop": "⏸ Anhalten",
        "summary_music_none": "🔇 Ohne Musik",
        "summary_music_sunset": "🌅 Acoustic Sunset",
        "summary_music_vanlife": "🚐 Vanlife Chill",
        "summary_music_breeze": "🌊 Coastal Breeze",
        "summary_music_alpine": "🌲 Alpine Acoustic",
        "summary_music_jazz": "🎷 Jazz Trio",
        "summary_music_folk": "🎸 Folk Guitar",
        "summary_music_reggae": "☀️ Reggae Sunshine",
        "summary_music_cinematic": "🎬 Cinematic Orchestral",
        "summary_music_lofi": "🎧 Electronic Lo-Fi",
        "summary_generating": "Erstelle Reisezusammenfassung... 🚐",
        "summary_download_video": "📥 MP4-Video herunterladen",
        "summary_download_pdf": "📥 PDF-Bericht herunterladen",
        "summary_slide_counter": "Folie {current} / {total}",
        "summary_btn_prev": "◀ Vorherige",
        "summary_btn_next": "Nächste ▶",
        "summary_btn_download_slide": "💾 Folie herunterladen (PNG)",

        // Top 8 Attractions Modal
        "top_attractions_title": "🌟 Top 8 Must-See Highlights der Route",
        "top_attractions_subtitle": "Die am meisten besuchten und spektakulärsten Orte für deinen VW California Roadtrip:",
        "top_attractions_sort": "Sortieren:",
        "top_attractions_sort_reviews": "👥 Meiste Bewertungen",
        "top_attractions_sort_rating": "🌟 Höchste Bewertung",
        "top_attractions_sort_day": "📅 Nach Reisetagen (Tag 1 ➔ N)",
        "top_attractions_page_fmt": "Highlights #{start}–#{end} von {total}",
        "top_attractions_prev": "⬅️ Vorherige 8",
        "top_attractions_next": "Nächste 8 ➡️",
        "top_attractions_focus_map": "🎯 Auf der Karte anzeigen",

        // Modals & User Preferences
        "trips_modal_title": "🗺️ Meine gespeicherten Reisen",
        "trips_loading": "Reisen werden geladen...",
        "trips_empty": "Keine gespeicherten Reisen. Plane deine erste Reise im Chat!",
        "trips_error": "Fehler beim Laden der Reisen.",
        "connection_error": "Verbindungsfehler zum Server. Stellen Sie sicher, dass der Server läuft.",
        "account_modal_title": "Kontoeinstellungen",
        "account_save": "Einstellungen speichern",
        "account_saving": "Speichern...",
        "account_logout": "Abmelden",

        // Profile & Vehicle Preferences Modal
        "pref_title": "⚙️ VW California Profil & Einstellungen",
        "pref_vehicle_model": "Fahrzeugmodell:",
        "pref_max_drive_hours": "Maximale tägliche Fahrzeit (h):",
        "pref_hookup_type": "Stromanschluss-Typ:",
        "pref_hookup_shore": "Landstrom (CEE-Campingstecker)",
        "pref_hookup_full": "Vollanschluss (Strom + Frischwasser + Abwasser)",
        "pref_hookup_none": "Autark (Solar / Zusatzbatterie)",
        "pref_max_budget": "Maximales Budget pro Nacht (€):",
        "pref_required_amenities": "Erforderliche Ausstattung:",
        "pref_amenity_power": "Landstrom",
        "pref_amenity_water": "Frischwasser",
        "pref_amenity_showers": "Duschen",
        "pref_amenity_wifi": "WLAN",
        "pref_amenity_waste": "Grauwasserentsorgung",
        "pref_btn_save": "Einstellungen speichern",
        "pref_btn_tutorial": "▶️ Tutorial",
        "pref_btn_logout": "Abmelden",

        // Auth
        "auth_login_tab": "Anmelden",
        "auth_register_tab": "Registrieren",
        "auth_email": "E-Mail-Adresse",
        "auth_password": "Passwort",
        "auth_display_name": "Name",
        "auth_login_btn": "Anmelden",
        "auth_logging_in": "Anmeldung...",
        "auth_register_btn": "Konto erstellen",
        "auth_creating": "Erstellen...",
        "auth_switch_no_account": "Kein Konto? Jetzt registrieren",
        "auth_switch_has_account": "Bereits ein Konto? Anmelden",

        // Tutorial
        "tut_step_fmt": "Schritt {step} von {total}",
        "tut_step1_title": "Routenfortschritt (5 Schritte)",
        "tut_step1_desc": "Verfolge den Status deiner Reiseplanung: Ziel, Erlebnis, Tempo, Campingplätze und Zusammenfassung. Während du mit dem KI-Assistenten chattest, füllen sich die Slots automatisch grün!",
        "tut_step2_title": "KI-Reiseinspirationen",
        "tut_step2_desc": "Klicke oben auf 'Inspirationen', um kuratierte Routen für deinen VW California (Wochenende, Woche, Fernreise) passend zu deinem GPS-Standort mit transparenten KI-Empfehlungen zu entdecken!",
        "tut_step3_title": "Interaktive Karte & Live-Ebenen",
        "tut_step3_desc": "Prüfe deine Route mit Live-Verkehr und Wetterdaten. Entdecke für den VW California verifizierte Campingplätze (CEE-Strom, Frischwasser), Sehenswürdigkeiten und nutze den schwebenden Chat direkt auf der Karte!",
        "tut_step4_title": "Reiseerinnerungen & Mediengalerie",
        "tut_step4_desc": "Erstelle dein digitales Reisetagebuch! Lade Smartphone-Fotos hoch — das System liest GPS-Koordinaten aus EXIF-Daten aus, heftet sie an die Route und erstellt eine teilbare Zusammenfassung deiner Reise!",
        "tut_step5_title": "Meine Reisen & VW California Profil",
        "tut_step5_desc": "Verwalte gespeicherte Routen und deren Status. Konfiguriere im Profil dein Fahrzeugmodell (Ocean, Beach, Coast, Grand California), CEE-Stromanschlüsse, Budget und tägliches Fahrzeitlimit!",
        "tut_skip": "Tutorial überspringen",
        "tut_next": "Weiter &rarr;",
        "tut_finish": "Fertig 🚀",

        // View Tutorials (DE)
        "tut_map_step1_title": "Routenwerkzeuge & Live-Ebenen",
        "tut_map_step1_desc": "Aktiviere Live-Verkehr, Wetterdaten entlang der Route, filtere die Top 5 Campingplätze für Camper und entdecke empfohlene Highlights.",
        "tut_map_step2_title": "Tagesablauf & Campingplätze",
        "tut_map_step2_desc": "Prüfe Routenstatistiken (Kilometer, Fahrzeit), den Tagesablauf und Details des Übernachtungscampingplatzes mit Strom- und Wasseranschlüssen.",
        "tut_map_step3_title": "Schwebender KI-Chat auf der Karte",
        "tut_map_step3_desc": "Möchtest du einen Stopp hinzufügen oder die Route ändern? Nutze den schwebenden Chat, um direkt auf der Karte mit der KI zu sprechen!",

        "tut_mem_step1_title": "Reisefotos hochladen",
        "tut_mem_step1_desc": "Ziehe Fotos von deinem Smartphone oder deiner Kamera hierher (JPEG, PNG, HEIC). Das System liest GPS-Koordinaten und Zeit aus den EXIF-Daten aus.",
        "tut_mem_step2_title": "Automatische Fotopins auf der Karte",
        "tut_mem_step2_desc": "Deine Fotos werden den Reisetagen zugeordnet und als Fotopins auf der Karte markiert, um eine interaktive Reisezeitleiste zu bilden.",
        "tut_mem_step3_title": "Reisezusammenfassung generieren",
        "tut_mem_step3_desc": "Klicke hier, um eine ansprechende Reisezusammenfassung mit Route, Campingplätzen und deinen besten Fotos zu generieren!",

        "tut_trips_step1_title": "Reiseverlauf & Status",
        "tut_trips_step1_desc": "Sieh dir alle geplanten und vergangenen Reisen an. Filter nach Status (Entwurf, Geplant, Unterwegs, Abgeschlossen) und lade jede Route mit einem Klick.",
        "tut_trips_step2_title": "Fahrzeugprofil & Einstellungen",
        "tut_trips_step2_desc": "Passe dein Camper-Modell (Ocean, Beach, Coast, Grand California), CEE-Stromanschlüsse, Budget und tägliches Fahrzeitlimit an.",

        // Statuses
        "status_draft": "Entwurf",
        "status_planned": "Geplant",
        "status_active": "Unterwegs",
        "status_completed": "Abgeschlossen",

        // Weather & General
        "weather_title": "Wettervorhersage",
        "day_card_day": "Tag {day}",
        "day_card_drive": "Fahrt: {hours}h ({km} km)",
        "camping_modal_title": "🏕️ Campingplatz für Tag {day} wählen",
        "camping_modal_sub": "Hier sind 3 Vorschläge für VW California passende Campingplätze. Wähle deinen Übernachtungsort:",
        "camping_select_btn": "Diesen Campingplatz wählen",
        "camping_selected_badge": "✓ Ausgewählte Unterkunft",
        "camping_change_btn": "🏕️ Campingplatz wählen / ändern",
        "camping_per_night": "€/Nacht",
        "camping_next_day": "Weiter zu nächstem Tag &rarr;",
        "camping_confirm_all": "Fertig",
        "photo_preview_tag": "📷 Vorschau",
        "add_to_route_btn": "➕ Zur Route hinzufügen",
        "added_to_route_btn": "✓ In Route enthalten",
        "adding_to_route_btn": "Hinzufügen...",
        "attraction_added_toast": "Attraktion {name} zu Tag {day} hinzugefügt!",
        "waypoint_camping": "Übernachtung",
        "waypoint_attraction": "Attraktion",
        "waypoint_start": "Start",
        "waypoint_end": "Ziel",
        "legend_start_end": "Start / Ende",
        "legend_outbound_route": "Hinfahrt Route",
        "legend_return_route": "Rückfahrt Route",
        "legend_day_stages": "Tagesetappen (D1, D2...)",
        "legend_camping": "Campingplatz",
        "legend_attraction": "⭐ Attraktion",
        "legend_photo": "Foto",
        "day_return_badge": "Rückfahrt",
        "lang_name_pl": "Polski",
        "lang_name_de": "Deutsch",
        "lang_name_en": "English"
    },
    en: {
        // Navigation
        "nav_plan": "Plan",
        "nav_map": "Map",
        "nav_memory": "Memories",
        "nav_trips": "Trips",
        "nav_account": "Account",

        // Chat Header & Placeholders
        "chat_greeting": "Welcome, traveler.",
        "chat_greeting_user": "Welcome, {name}!",
        "chat_sub": "Where would you like to travel with your VW California?",

        // Welcome Overlay
        "welcome_badge": "🐶 Volkswagen Sniffer — AI Trip Planner",
        "welcome_sniffer_badge": "🐶 Volkswagen Sniffer",
        "sniffer_role_tag": "VW Travel Guide",
        "sniffer_voice_toggle_on": "Sniffer Voice: On",
        "sniffer_voice_toggle_off": "Sniffer Voice: Muted",
        "sniffer_voice_tooltip_on": "Sniffer voice is enabled. Click to mute.",
        "sniffer_voice_tooltip_off": "Sniffer voice is muted. Click to enable.",
        "sniffer_speak_msg": "Listen",
        "sniffer_stop_msg": "Stop",
        "welcome_title": "Welcome!",
        "welcome_user_greeting": "Welcome, {name}!",
        "welcome_subtitle": "Where are we heading today?",
        "chat_placeholder": "Ask a question or describe your dream route...",
        "chat_send": "Send",
        "chat_helper_text": "Volkswagen Sniffer may make mistakes. Please verify important information.",
        "mic_tooltip_start": "Dictate message",
        "mic_tooltip_stop": "Stop listening",
        "mic_not_supported": "Your browser does not support voice dictation.",
        "planning_route_indicator": "Sniffer is sniffing out the best route and campsites...",

        // Geolocation in Chat
        "location_active": "Location: On",
        "location_disabled": "Location: Off",
        "location_acquiring": "Locating...",
        "location_unavailable": "Location: No GPS",
        "location_tooltip_on": "Automatic location is enabled. Click to disable.",
        "location_tooltip_off": "Automatic location is disabled. Click to enable.",
        "location_current_label": "Your location:",
        "location_btn_disable": "Disable",
        "location_btn_enable": "Enable",
        "location_toast_on": "Automatic location in chat enabled",
        "location_toast_off": "Automatic location in chat disabled",


        // Quick Actions & Welcome Hero (Option 4)
        "qa_heading": "Where are we heading today?",
        "chat_welcome_heading": "Where are we heading today?",
        "chat_welcome_heading_user": "Where are we heading today, {name}?",
        "chat_welcome_sub": "Design a custom route for your VW California or explore AI trip inspirations sniffed out by Sniffer.",
        "hero_inspiration_badge": "Sniffed out by Volkswagen Sniffer",
        "hero_inspiration_title": "Discover inspirations for your camper journey",
        "hero_inspiration_desc": "Curated itineraries sniffed out by Sniffer – camper range, 230V pitches, and scenic stops.",
        "hero_inspiration_btn": "Explore inspirations ✨",
        "qa_1_title": "A week in the mountains",
        "qa_1_sub": "with family",
        "qa_1_prompt": "I want to go to the mountains with my family, I have one week",
        "qa_2_title": "Adriatic Coast",
        "qa_2_sub": "campsites up to 30€/night",
        "qa_2_prompt": "Looking for campsites with power and showers along the Adriatic, budget up to 30 euros",
        "qa_3_title": "Munich → Croatia",
        "qa_3_sub": "5 days, via Slovenia",
        "qa_3_prompt": "Plan a 5-day route from Munich to Croatia via Slovenia",
        "qa_4_title": "Wild camping",
        "qa_4_sub": "10 days solo",
        "qa_4_prompt": "Traveling solo, experienced, prefer wild camping / boondocking. I have 10 days",

        // Travel Suggestions Modal (Middle-Aged + RAG)
        "btn_travel_inspirations": "Inspirations",
        "suggestions_vw_badge": "Sniffed out by Sniffer",
        "suggestions_title": "Where is the road taking you today?",
        "suggestions_subtitle": "Curated travel ideas for your campervan — scenic byways, relaxed pace, 230V shore power pitches, and regional flavors.",
        "suggestions_refresh": "New Inspirations",
        "suggestions_skip": "Type your own destination in chat →",
        "suggestions_badge_matched": "Tailored to you ✨",
        "suggestions_badge_curated": "VW Recommendation",
        "suggestions_pill_all": "All Durations",
        "suggestions_pill_weekend": "Weekend (2–4 days)",
        "suggestions_pill_week": "One Week (5–8 days)",
        "suggestions_pill_expedition": "Expedition (9–14 days)",
        "suggestions_days_badge": "days",
        "suggestions_days_badge_singular": "day",
        "suggestions_rag_reason_prefix": "Why we recommend this",
        "suggestions_why_text": "Good to know",

        // Slot Progress Bar
        "slot_vibe": "Destination",
        "slot_experience": "Experience",
        "slot_pace": "Pace",
        "slot_infrastructure": "Campsites",
        "slot_summary": "Summary",

        // Map View & Side Panel
        "map_header_title": "Interactive Route Map",
        "btn_show_on_map": "Show on map",
        "map_btn_plan": "Plan",
        "map_btn_center": "Center",
        "map_btn_campings": "Campsites",
        "map_btn_attractions": "Highlights",
        "map_btn_top5": "Top 8",
        "map_chat_bubble": "Chat",
        "map_chat_header": "Volkswagen Sniffer",
        "map_chat_placeholder": "Ask about the route...",
        "map_btn_back_to_chat": "Chat",
        "stat_days": "Days",
        "stat_km": "km",
        "stat_hours": "Driving time",
        "stat_campings": "Overnights",
        "stat_label_days": "Days",
        "stat_label_km": "Kilometers",
        "stat_label_drive": "Driving",
        "stat_label_stops": "Stops",
        "btn_export_summary": "Export Trip Summary",
        "btn_suggest_attractions": "Suggest Highlights",

        // Memory View
        "memory_title": "Travel Memories",
        "memory_sub": "Upload photos from your VW California road trip — they will automatically link to the map route using GPS/EXIF data.",
        "memory_drag_drop": "Drag & drop photos here or click to select",
        "memory_formats_hint": "JPEG, PNG, HEIC — GPS data will be extracted automatically.<br>No GPS? You can pin photos manually on the map.",
        "memory_select_files": "Select files",
        "memory_uploaded_photos": "Uploaded photos",
        "memory_photo_empty": "No photos yet — upload your travel memories",
        "memory_btn_summary": "Create trip summary",
        "memory_btn_gallery": "Memories Gallery",
        "pin_photo_prompt": "📍 Click on the map to pin this photo",
        "btn_cancel": "Cancel",
        "btn_save": "Save",
        "photo_edit_title": "Edit photo date and location",
        "photo_edit_date_label": "📅 Photo capture date:",
        "photo_edit_date_hint": "Affects ordering and day assignment in the trip recap video.",
        "photo_edit_day_label": "🚐 Assign to trip day:",
        "photo_edit_day_auto": "Automatic (by date / location)",
        "photo_edit_location_label": "📍 Position on map:",
        "photo_edit_pick_map": "🗺️ Pick on map",
        "summary_trip_dates_label": "Trip dates:",
        "summary_btn_edit_dates": "✏️ Change dates",

        // Summary Modal & Music Export
        "summary_modal_title": "Choose export format",
        "summary_modal_sub": "How would you like to share your adventure?",
        "summary_soundtrack_label": "🎵 Video soundtrack:",
        "summary_audius_badge": "Audius Streaming",
        "summary_music_search_placeholder": "🔍 Search track or artist on Audius...",
        "summary_selected_track_label": "Selected soundtrack:",
        "summary_music_no_music_opt": "🔇 No music",
        "summary_music_searching": "Searching Audius tracks...",
        "summary_music_no_results": "No tracks found.",
        "summary_btn_slideshow": "🖼️ Slideshow",
        "summary_btn_video": "🎬 Trip Movie (Cinematic MP4)",
        "summary_btn_preview": "▶ Preview",
        "summary_btn_stop": "⏸ Stop",
        "summary_music_none": "🔇 No music",
        "summary_music_sunset": "🌅 Acoustic Sunset",
        "summary_music_vanlife": "🚐 Vanlife Chill",
        "summary_music_breeze": "🌊 Coastal Breeze",
        "summary_music_alpine": "🌲 Alpine Acoustic",
        "summary_music_jazz": "🎷 Jazz Trio",
        "summary_music_folk": "🎸 Folk Guitar",
        "summary_music_reggae": "☀️ Reggae Sunshine",
        "summary_music_cinematic": "🎬 Cinematic Orchestral",
        "summary_music_lofi": "🎧 Electronic Lo-Fi",
        "summary_generating": "Generating trip summary... 🚐",
        "summary_download_video": "📥 Download MP4 Video",
        "summary_download_pdf": "📥 Download PDF Document",
        "summary_slide_counter": "Slide {current} / {total}",
        "summary_btn_prev": "◀ Previous",
        "summary_btn_next": "Next ▶",
        "summary_btn_download_slide": "💾 Download Slide (PNG)",

        // Top 8 Attractions Modal
        "top_attractions_title": "🌟 Top 8 Must-See Highlights along Route",
        "top_attractions_subtitle": "Most popular and scenic spots curated for your VW California journey:",
        "top_attractions_sort": "Sort by:",
        "top_attractions_sort_reviews": "👥 Most reviewed",
        "top_attractions_sort_rating": "🌟 Top Rated",
        "top_attractions_sort_day": "📅 By trip day (Day 1 ➔ N)",
        "top_attractions_page_fmt": "Highlights #{start}–#{end} of {total}",
        "top_attractions_prev": "⬅️ Previous 8",
        "top_attractions_next": "Next 8 ➡️",
        "top_attractions_focus_map": "🎯 Show on map",

        // Modals & User Preferences
        "trips_modal_title": "🗺️ My Saved Trips",
        "trips_loading": "Loading trips...",
        "trips_empty": "No saved trips yet. Plan your first adventure in the chat!",
        "trips_error": "Error loading trips.",
        "connection_error": "Connection error to server. Ensure the server is running.",
        "account_modal_title": "Account Settings",
        "account_save": "Save preferences",
        "account_saving": "Saving...",
        "account_logout": "Log out",

        // Profile & Vehicle Preferences Modal
        "pref_title": "⚙️ VW California Profile & Preferences",
        "pref_vehicle_model": "Vehicle Model:",
        "pref_max_drive_hours": "Max daily driving time (h):",
        "pref_hookup_type": "Power Hookup Type:",
        "pref_hookup_shore": "Shore Power (CEE Camping Plug)",
        "pref_hookup_full": "Full Hookup (Power + Fresh Water + Waste)",
        "pref_hookup_none": "Off-grid (Solar / Aux Battery)",
        "pref_max_budget": "Max nightly budget (€):",
        "pref_required_amenities": "Required Amenities:",
        "pref_amenity_power": "Shore Power",
        "pref_amenity_water": "Fresh Water",
        "pref_amenity_showers": "Showers",
        "pref_amenity_wifi": "Wi-Fi",
        "pref_amenity_waste": "Waste Disposal",
        "pref_btn_save": "Save preferences",
        "pref_btn_tutorial": "▶️ Tutorial",
        "pref_btn_logout": "Log out",

        // Auth
        "auth_login_tab": "Log In",
        "auth_register_tab": "Register",
        "auth_email": "Email Address",
        "auth_password": "Password",
        "auth_display_name": "Name / Display Name",
        "auth_login_btn": "Log In",
        "auth_logging_in": "Logging in...",
        "auth_register_btn": "Create Account",
        "auth_creating": "Creating...",
        "auth_switch_no_account": "Don't have an account? Sign up",
        "auth_switch_has_account": "Already have an account? Log in",

        // Tutorial
        "tut_step_fmt": "Step {step} of {total}",
        "tut_step1_title": "Route Progress Tracker (5 Steps)",
        "tut_step1_desc": "Track your trip planning status across 5 key slots: Destination, Experience, Pace, Campsites, and Summary. As you chat with the AI assistant, indicators automatically turn green!",
        "tut_step2_title": "AI Travel Inspirations",
        "tut_step2_desc": "Click the 'Inspirations' button in the header to explore curated road trips for your VW California (Weekend, Week, Expedition) tailored to your GPS location with transparent recommendations!",
        "tut_step3_title": "Interactive Map & Live Layers",
        "tut_step3_desc": "Inspect your route with live traffic and weather forecasts. Find verified VW California-friendly campsites (CEE shore power, water hookups), scenic attractions, and chat with AI directly on the map!",
        "tut_step4_title": "Travel Memories & Trip Highlights",
        "tut_step4_desc": "Build your digital road trip journal! Upload photos from your smartphone — the system automatically extracts GPS from EXIF data, pins them along your route, and generates shareable trip summaries!",
        "tut_step5_title": "My Trips & VW California Profile",
        "tut_step5_desc": "Manage saved itineraries and trip statuses. In your profile, configure your specific campervan model (Ocean, Beach, Coast, Grand California), CEE hookup needs, budget, and daily driving limits!",
        "tut_skip": "Skip tutorial",
        "tut_next": "Next &rarr;",
        "tut_finish": "Done 🚀",

        // View Tutorials (EN)
        "tut_map_step1_title": "Route Tools & Live Layers",
        "tut_map_step1_desc": "Toggle live traffic layers, route weather conditions, filter Top 5 camper-friendly campsites, and discover recommended scenic attractions.",
        "tut_map_step2_title": "Daily Itinerary & Campsites",
        "tut_map_step2_desc": "Inspect trip statistics (total distance, drive hours), daily schedule breakdown, and campsite details with power and water hookups.",
        "tut_map_step3_title": "Floating Map Chat Assistant",
        "tut_map_step3_desc": "Need to add a stop or adjust the route? Use the floating chat widget to converse with the AI assistant without leaving the map!",

        "tut_mem_step1_title": "Upload Travel Photos",
        "tut_mem_step1_desc": "Drag and drop photos from your phone or camera (JPEG, PNG, HEIC). The system automatically parses GPS coordinates and timestamp from EXIF metadata.",
        "tut_mem_step2_title": "Automatic Map Photo Pins",
        "tut_mem_step2_desc": "Photos are categorized by trip day and marked as photo pins along the route map, creating an interactive journey timeline.",
        "tut_mem_step3_title": "Trip Summary Generator",
        "tut_mem_step3_desc": "Click to generate a shareable trip summary video or visual recap combining your route, overnight campsites, and favorite photos!",

        "tut_trips_step1_title": "Trip History & Statuses",
        "tut_trips_step1_desc": "Review all planned and completed road trips. Track statuses (Draft, Planned, Active, Completed) and load any itinerary with a single click.",
        "tut_trips_step2_title": "Vehicle Profile & Preferences",
        "tut_trips_step2_desc": "Fine-tune your campervan model (Ocean, Beach, Coast, Grand California), CEE shore power hookups, budget, and daily driving limits.",

        // Statuses
        "status_draft": "Draft",
        "status_planned": "Planned",
        "status_active": "Active",
        "status_completed": "Completed",

        // Weather & General
        "weather_title": "Weather Forecast",
        "day_card_day": "Day {day}",
        "day_card_drive": "Drive: {hours}h ({km} km)",
        "camping_modal_title": "🏕️ Select Campsite for Day {day}",
        "camping_modal_sub": "Here are 3 campsites tailored for your VW California. Choose the best spot for the night:",
        "camping_select_btn": "Choose this campsite",
        "camping_selected_badge": "✓ Selected campsite",
        "camping_change_btn": "🏕️ Select / change campsite",
        "camping_per_night": "€/night",
        "camping_next_day": "Next day &rarr;",
        "camping_confirm_all": "Done",
        "photo_preview_tag": "📷 Preview",
        "add_to_route_btn": "➕ Add to route",
        "added_to_route_btn": "✓ In route",
        "adding_to_route_btn": "Adding...",
        "attraction_added_toast": "Added attraction {name} to Day {day}!",
        "waypoint_camping": "Overnight",
        "waypoint_attraction": "Highlight",
        "waypoint_start": "Start",
        "waypoint_end": "Destination",
        "legend_start_end": "Start / End",
        "legend_outbound_route": "Outbound Route",
        "legend_return_route": "Return Route",
        "legend_day_stages": "Daily stages (D1, D2...)",
        "legend_camping": "Campsite",
        "legend_attraction": "⭐ Highlight",
        "legend_photo": "Photo",
        "day_return_badge": "Return leg",
        "lang_name_pl": "Polski",
        "lang_name_de": "Deutsch",
        "lang_name_en": "English"
    }
};

class I18nManager {
    constructor() {
        const saved = localStorage.getItem('vw_app_lang');
        if (saved && translations[saved]) {
            this.currentLang = saved;
        } else {
            const browserLang = navigator.language ? navigator.language.substring(0, 2) : 'pl';
            this.currentLang = translations[browserLang] ? browserLang : 'pl';
        }
    }

    t(key, params = {}) {
        let text = (translations[this.currentLang] && translations[this.currentLang][key]) ||
                   (translations['pl'] && translations['pl'][key]) || key;
        
        for (const [pKey, pVal] of Object.entries(params)) {
            text = text.replace(new RegExp(`\\{${pKey}\\}`, 'g'), pVal);
        }
        return text;
    }

    setLanguage(lang, reload = false) {
        if (!translations[lang]) return;
        this.currentLang = lang;
        localStorage.setItem('vw_app_lang', lang);
        document.documentElement.lang = lang;
        this.updateStaticUI();
        window.dispatchEvent(new CustomEvent('vw_lang_changed', { detail: { lang } }));
        if (reload) {
            window.location.reload();
        }
    }

    getLanguage() {
        return this.currentLang;
    }

    getCurrentLanguage() {
        return this.currentLang;
    }

    updateStaticUI() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                el.innerHTML = this.t(key);
            }
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                el.placeholder = this.t(key);
            }
        });

        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                el.title = this.t(key);
            }
        });

        // Update active class on language switcher buttons if present
        document.querySelectorAll('.lang-btn').forEach(btn => {
            if (btn.dataset.lang === this.currentLang) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update language trigger buttons (flags & codes)
        const langFlags = { pl: '🇵🇱', de: '🇩🇪', en: '🇬🇧' };
        const langCodes = { pl: 'PL', de: 'DE', en: 'EN' };
        const curFlag = langFlags[this.currentLang] || '🌐';
        const curCode = langCodes[this.currentLang] || (this.currentLang ? this.currentLang.toUpperCase() : 'PL');

        const navFlag = document.getElementById('nav-current-lang-flag');
        const navCode = document.getElementById('nav-current-lang-code');
        if (navFlag) navFlag.textContent = curFlag;
        if (navCode) navCode.textContent = curCode;

        const headerFlag = document.getElementById('header-lang-flag');
        const headerCode = document.getElementById('header-lang-code');
        if (headerFlag) headerFlag.textContent = curFlag;
        if (headerCode) headerCode.textContent = curCode;
    }
}

window.vwI18n = new I18nManager();
window.t = (key, params) => window.vwI18n.t(key, params);
