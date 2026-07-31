/**
 * VW California AI Trip Planner — i18n Internationalization Module
 * Supports Polish ('pl') and German ('de').
 */

const translations = {
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
        "chat_placeholder": "Zadaj pytanie lub opisz swoją wymarzoną trasę...",
        "chat_send": "Wyślij",
        "chat_helper_text": "AI Trip Planner może popełniać błędy. Sprawdź ważne informacje.",
        "mic_tooltip_start": "Dyktuj wiadomość",
        "mic_tooltip_stop": "Zatrzymaj nasłuchiwanie",
        "mic_not_supported": "Twoja przeglądarka nie obsługuje dyktowania głosowego.",

        // Quick Actions
        "quick_croatia": "Wybrzeże Chorwacji z Poznania na 14 dni",
        "quick_bavaria": "Alpy Bawarskie na 5 dni",
        "quick_wild_camping": "Dziki kemping w Norwegii na 10 dni",
        "quick_scandinavia": "Szwecja & Fiordy na 12 dni",

        // Slot Progress Bar
        "slot_vibe": "Cel",
        "slot_experience": "Doświadczenie",
        "slot_pace": "Tempo",
        "slot_infrastructure": "Kempingi",
        "slot_summary": "Podsumowanie",

        // Map View & Side Panel
        "map_header_title": "Interaktywna Mapa Trasy",
        "stat_days": "Dni",
        "stat_km": "km",
        "stat_hours": "Czas jazdy",
        "stat_campings": "Noclegi",
        "btn_export_summary": "Eksportuj Podsumowanie Wyjazdu",
        "btn_suggest_attractions": "Sugeruj Atrakcje",

        // Memory View
        "memory_title": "Wspomnienia z Podróży",
        "memory_sub": "Wgraj zdjęcia ze swojego wyjazdu VW California — zostaną automatycznie sparowane z trasą na mapie dzięki danym GPS/EXIF.",
        "memory_drag_drop": "Przeciągnij i upuść zdjęcia tutaj lub",
        "memory_select_files": "Wybierz pliki",
        "memory_uploaded_photos": "Wgrane zdjęcia",

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

        // Tutorial
        "tut_step_fmt": "Krok {step} z {total}",
        "tut_step1_title": "Wskaźniki postępu trasy",
        "tut_step1_desc": "Na górze ekranu czatu widzisz pasek slotów. Gdy podajesz cel, daty i preferencje, punkty zmieniają kolor na zielony!",
        "tut_step2_title": "Szybkie starty & Opis trasy",
        "tut_step2_desc": "Możesz kliknąć jedną z gotowych propozycji lub opisać swoją wycieczkę własnymi słowami po polsku lub niemiecku.",
        "tut_step3_title": "Interaktywna Mapa",
        "tut_step3_desc": "Przełącz się na widok Mapy, aby zobaczyć dokładną trasę, kempingi z podłączeniem prądu/wody oraz proponowane atrakcje.",
        "tut_step4_title": "Pamięć Podróży",
        "tut_step4_desc": "Wgraj zdjęcia z telefonu. Jeśli zawierają dane GPS z wyjazdu, zostaną przypięte bezpośrednio do punktów na mapie!",
        "tut_step5_title": "Moje Wyjazdy i Konto",
        "tut_step5_desc": "Wszystkie Twoje wygenerowane plany trasy są automatycznie zapisywane na Twoim koncie. Życzymy udanej podróży!",
        "tut_skip": "Pomiń tutorial",
        "tut_next": "Dalej &rarr;",
        "tut_finish": "Zakończ 🚀",

        // View Tutorials (PL)
        "tut_map_step1_title": "Interaktywna Mapa Trasy",
        "tut_map_step1_desc": "Tutaj zobaczysz przebieg Twojej podróży, poszczególne przystanki oraz zaplanowane kempingi.",
        "tut_map_step2_title": "Karty Dni i Statystyki",
        "tut_map_step2_desc": "W tym panelu znajdziesz łączny dystans, czas jazdy oraz dzienny plan z godzinami i kempingami.",
        "tut_map_step3_title": "Sugerowanie Atrakcji i Eksport",
        "tut_map_step3_desc": "Kliknij 'Sugeruj Atrakcje', aby AI znalazło ciekawe miejsca po drodze, lub wyeksportuj podsumowanie wyjazdu!",

        "tut_mem_step1_title": "Dodawanie Zdjęć z Podróży",
        "tut_mem_step1_desc": "Przeciągnij i upuść zdjęcia ze swojego wyjazdu VW California lub kliknij, aby wybrać je z urządzenia.",
        "tut_mem_step2_title": "Geolokalizacja GPS & EXIF",
        "tut_mem_step2_desc": "AI odczyta współrzędne z pliku i automatycznie przypisze Twoje wspomnienia do konkretnych miejsc na mapie!",

        "tut_trips_step1_title": "Moje Zapisane Wyjazdy",
        "tut_trips_step1_desc": "W tym oknie znajdziesz historię wszystkich wygenerowanych tras. Kliknij podróż, aby natychmiast ją wczytać.",
        "tut_trips_step2_title": "Statusy Podróży",
        "tut_trips_step2_desc": "Trasy posiadają statusy (Szkic, Zaplanowano, W trakcie, Zakończono), co ułatwia zarządzanie aktualnym wyjazdem.",

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
        "legend_camping": "Kemping",
        "legend_attraction": "⭐ Atrakcja",
        "legend_photo": "Zdjęcie",
        "day_return_badge": "Powrót",
        "lang_name_pl": "Polski",
        "lang_name_de": "Deutsch"
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
        "chat_placeholder": "Stelle eine Frage oder beschreibe deine Traumroute...",
        "chat_send": "Senden",
        "chat_helper_text": "Der AI Trip Planner kann Fehler machen. Überprüfe wichtige Informationen.",
        "mic_tooltip_start": "Nachricht diktieren",
        "mic_tooltip_stop": "Zuhören stoppen",
        "mic_not_supported": "Dein Browser unterstützt keine Sprachdiktat-Funktion.",

        // Quick Actions
        "quick_croatia": "Kroatische Küste ab Posen für 14 Tage",
        "quick_bavaria": "Bayerische Alpen für 5 Tage",
        "quick_wild_camping": "Wildcamping in Norwegen für 10 Tage",
        "quick_scandinavia": "Schweden & Fjorde für 12 Tage",

        // Slot Progress Bar
        "slot_vibe": "Ziel",
        "slot_experience": "Erfahrung",
        "slot_pace": "Tempo",
        "slot_infrastructure": "Campingplätze",
        "slot_summary": "Zusammenfassung",

        // Map View & Side Panel
        "map_header_title": "Interaktive Routenkarte",
        "stat_days": "Tage",
        "stat_km": "km",
        "stat_hours": "Fahrzeit",
        "stat_campings": "Übernachtungen",
        "btn_export_summary": "Reisezusammenfassung exportieren",
        "btn_suggest_attractions": "Sehenswürdigkeiten vorschlagen",

        // Memory View
        "memory_title": "Reiseerinnerungen",
        "memory_sub": "Lade Fotos von deiner VW California Reise hoch — sie werden dank GPS/EXIF-Daten automatisch mit der Route auf der Karte verknüpft.",
        "memory_drag_drop": "Ziehe Fotos hierher oder",
        "memory_select_files": "Dateien auswählen",
        "memory_uploaded_photos": "Hochgeladene Fotos",

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

        // Tutorial
        "tut_step_fmt": "Schritt {step} von {total}",
        "tut_step1_title": "Routenfortschritt",
        "tut_step1_desc": "Oben im Chat-Bildschirm siehst du die Slot-Leiste. Wenn du Ziel, Daten und Präferenzen angibst, werden die Punkte grün!",
        "tut_step2_title": "Schnellstart & Routenbeschreibung",
        "tut_step2_desc": "Du kannst auf einen der Vorschläge klicken oder deine Reise in eigenen Worten auf Polnisch oder Deutsch beschreiben.",
        "tut_step3_title": "Interaktive Karte",
        "tut_step3_desc": "Wechsle zur Kartenansicht, um die genaue Route, Campingplätze mit Strom/Wasseranschluss und Sehenswürdigkeiten zu sehen.",
        "tut_step4_title": "Reiseerinnerungen",
        "tut_step4_desc": "Lade Fotos von deinem Smartphone hoch. Wenn sie GPS-Daten enthalten, werden sie direkt an Punkte auf der Karte angeheftet!",
        "tut_step5_title": "Meine Reisen & Konto",
        "tut_step5_desc": "Alle deine erstellten Routenpläne werden automatisch in deinem Konto gespeichert. Gute Reise!",
        "tut_skip": "Tutorial überspringen",
        "tut_next": "Weiter &rarr;",
        "tut_finish": "Fertig 🚀",

        // View Tutorials (DE)
        "tut_map_step1_title": "Interaktive Routenkarte",
        "tut_map_step1_desc": "Hier siehst du deinen Reiseverlauf, einzelne Zwischenstopps und geplante Campingplätze.",
        "tut_map_step2_title": "Tageskarten & Statistiken",
        "tut_map_step2_desc": "In diesem Bereich findest du Gesamtdistanz, Fahrzeit sowie den Tagesplan mit Campingplätzen.",
        "tut_map_step3_title": "Sehenswürdigkeiten & Export",
        "tut_map_step3_desc": "Klicke auf 'Sehenswürdigkeiten vorschlagen', damit die KI Orte am Wegesrand findet, oder exportiere deine Reisezusammenfassung!",

        "tut_mem_step1_title": "Reisefotos hochladen",
        "tut_mem_step1_desc": "Ziehe Fotos deiner VW California Reise hierher oder klicke, um Dateien von deinem Gerät auszuwählen.",
        "tut_mem_step2_title": "GPS & EXIF Geolokalisierung",
        "tut_mem_step2_desc": "Die KI liest die GPS-Koordinaten aus und heftet deine Erinnerungen automatisch an Orte auf der Karte!",

        "tut_trips_step1_title": "Meine gespeicherten Reisen",
        "tut_trips_step1_desc": "Hier findest du den Verlauf aller erstellten Routen. Klicke auf eine Reise, um sie sofort zu laden.",
        "tut_trips_step2_title": "Reisestatus",
        "tut_trips_step2_desc": "Routen haben Statusanzeigen (Entwurf, Geplant, Unterwegs, Abgeschlossen) zur einfachen Verwaltung.",

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
        "legend_camping": "Campingplatz",
        "legend_attraction": "⭐ Attraktion",
        "legend_photo": "Foto",
        "day_return_badge": "Rückfahrt",
        "lang_name_pl": "Polski",
        "lang_name_de": "Deutsch"
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

    setLanguage(lang) {
        if (!translations[lang]) return;
        this.currentLang = lang;
        localStorage.setItem('vw_app_lang', lang);
        document.documentElement.lang = lang;
        this.updateStaticUI();
        window.dispatchEvent(new CustomEvent('vw_lang_changed', { detail: { lang } }));
    }

    getLanguage() {
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
    }
}

window.vwI18n = new I18nManager();
window.t = (key, params) => window.vwI18n.t(key, params);
