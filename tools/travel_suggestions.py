"""
Travel Suggestions Generator for the VW California AI Trip Planner.

Provides dynamic, LLM-powered travel inspirations specifically tailored
for middle-aged travelers (40-60 years), deeply integrated with the
personalized user memory (RAG) system.

See: architecture/travel_suggestions_sop.md
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from tools.openai_client import get_client, MODEL_NAME, chat_kwargs
from tools.user_memory import list_user_memories, save_user_memory


# High-resolution, reliable atmospheric photographic assets for travel themes
SCENIC_THEME_IMAGES = {
    "wine_gastronomy": (
        "https://images.unsplash.com/photo-1506377247377-2a5b3b417ebb"
        "?auto=format&fit=crop&w=1000&q=80"
    ),  # Tuscan vineyard landscape
    "lakes_mountains": (
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb"
        "?auto=format&fit=crop&w=1000&q=80"
    ),  # Serene alpine lake
    "castles_culture": (
        "https://images.unsplash.com/photo-1524397076567-5c756944336c"
        "?auto=format&fit=crop&w=1000&q=80"
    ),  # Historic European castle and river valley
    "coastal_calm": (
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e"
        "?auto=format&fit=crop&w=1000&q=80"
    ),  # Peaceful pine-fringed coastal bay
    "scenic_nature": (
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b"
        "?auto=format&fit=crop&w=1000&q=80"
    ),  # Panoramic mountain road
}



def format_enriched_suggestion_prompt(
    suggestion: Dict[str, Any],
    user_location: Optional[str] = None,
    lang: str = "pl",
) -> str:
    """
    Format a complete, actionable trip planning prompt from a suggestion card.

    Includes duration in days, destination, starting location (if known),
    and key VW California highlights to enable single-turn route generation.

    Args:
        suggestion (dict): The suggestion card dictionary.
        user_location (str, optional): The user's current city/location name.
        lang (str): Language code ('pl', 'de', 'en').

    Returns:
        str: Enriched natural language query for the chat planner.
    """
    days = suggestion.get("duration_days")
    if not days:
        cat = suggestion.get("duration_category", "weekend")
        days = 3 if cat == "weekend" else (7 if cat == "week" else 10)

    title = str(suggestion.get("title", "")).strip()
    subtitle = str(suggestion.get("subtitle", "")).strip()
    highlights_list = suggestion.get("vw_highlights") or []
    highlights = ", ".join([str(h) for h in highlights_list]) if highlights_list else ""

    loc_clean = user_location.strip() if user_location and len(user_location.strip()) > 2 else ""

    if lang == "de":
        origin_str = f" mit Start ab: {loc_clean}" if loc_clean else ""
        prompt = f"Plane für mich eine {days}-tägige Reise mit dem VW California{origin_str}. Ziel: {title}."
        if subtitle:
            prompt += f" {subtitle}"
        if highlights:
            prompt += f" Wichtig sind mir: {highlights}."
        return prompt

    elif lang == "en":
        origin_str = f" starting from: {loc_clean}" if loc_clean else ""
        prompt = f"Plan a {days}-day road trip for my VW California{origin_str}. Destination: {title}."
        if subtitle:
            prompt += f" {subtitle}"
        if highlights:
            prompt += f" Preferences: {highlights}."
        return prompt

    else:
        # Polish (default)
        origin_str = f" ze startem z: {loc_clean}" if loc_clean else ""
        prompt = f"Zaplanuj dla mnie {days}-dniowy wyjazd camperem VW California{origin_str}. Cel: {title}."
        if subtitle:
            prompt += f" {subtitle}"
        if highlights:
            prompt += f" Zależy mi na: {highlights}."
        return prompt


def get_curated_fallback_suggestions(
    lang: str = "pl",
    duration: str = "all",
    shuffle: bool = False,
    user_location: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return hand-crafted, high-aesthetic suggestions tailored for 40-60 demographic.

    Used when offline, during LLM timeouts, or when starting without prior memory.

    Args:
        lang (str): User interface language ('pl', 'de', or 'en').
        duration (str): Duration filter category ('all', 'weekend', 'week', 'expedition').
        shuffle (bool): Whether to randomly shuffle cards.
        user_location (str, optional): User origin location name (e.g. 'Poznań').

    Returns:
        List[Dict[str, Any]]: Structured list of curated suggestion cards.
    """
    if lang == "de":
        cards = [
            {
                "id": "curated-wine-de",
                "category": "wine_gastronomy",
                "duration_category": "week",
                "duration_days": 7,
                "title": "Toskana & Weinstraßen im Chianti",
                "subtitle": "Malerische Hügellandschaften, Weingüter, lokale Küche und ruhige Campingplätze mit 230V-Strom.",
                "image_url": SCENIC_THEME_IMAGES["wine_gastronomy"],
                "tags": ["Slow Travel", "Weingüter", "Landstrom 230V", "Genuss"],
                "prompt": (
                    "Plane für mich eine entspannte 7-tägige Tour mit dem VW California "
                    "durch die Toskana mit Fokus auf Weinstraßen, kulinarische Zwischenstopps "
                    "und komfortable Campingplätze mit Stromanschluss."
                ),
                "badge": "Beliebt bei Genießern",
                "rag_matched": False,
                "rag_reason": "Empfohlen, da Du Weinstraßen und komfortable Stellplätze mit Landstrom schätzt.",
                "vw_highlights": ["CEE-Landstrom", "Panoramaroute"],
            },
            {
                "id": "curated-lakes-de",
                "category": "lakes_mountains",
                "duration_category": "weekend",
                "duration_days": 4,
                "title": "Alpenseen & Panoramarouten",
                "subtitle": "Kristallklare Seen, sanfte Uferwege, komfortable Stellplätze mit Seeblick und Panoramapässe.",
                "image_url": SCENIC_THEME_IMAGES["lakes_mountains"],
                "tags": ["Alpenseen", "E-Bike", "Ruhe", "Komfort-Parzelle"],
                "prompt": (
                    "Ich möchte eine 4-tägige Panoramatour um die schönsten Kärntner oder "
                    "oberitalienischen Seen unternehmen. Ruhiges Fahrtempo, saubere Sanitäranlagen "
                    "und Parzellen direkt am Wasser."
                ),
                "badge": "Entspannung & Natur",
                "rag_matched": False,
                "rag_reason": "Passend zu Deiner Vorliebe für Seen, Radwege und ruhige Wasserparzellen.",
                "vw_highlights": ["Stellplatz am See", "Ruhiges Tempo"],
            },
            {
                "id": "curated-castles-de",
                "category": "castles_culture",
                "duration_category": "week",
                "duration_days": 6,
                "title": "Schlösser der Loire & Flusstäler",
                "subtitle": "Kulturelle Schätze, geschichtsträchtige Städtchen und idyllische Campingplätze im Grünen.",
                "image_url": SCENIC_THEME_IMAGES["castles_culture"],
                "tags": ["Kultur & Geschichte", "Flusstal", "Schlösser", "Schattenplätze"],
                "prompt": (
                    "Plane eine 6-tägige Kulturroute entlang der Loire zu den schönsten "
                    "Schlössern und Gärten. Moderate Tagesetappen von maximal 3 Stunden Fahrt."
                ),
                "badge": "Kultur & Geschichte",
                "rag_matched": False,
                "rag_reason": "Entspricht Deinem Interesse an historischen Städten und moderater Reisezeit.",
                "vw_highlights": ["Kulturroute", "Max 3h Fahrtzeit"],
            },
            {
                "id": "curated-coastal-de",
                "category": "coastal_calm",
                "duration_category": "expedition",
                "duration_days": 10,
                "title": "Pinienwälder & Meeresbrise der Adria",
                "subtitle": "Mediterranes Flair, ruhige Stellplätze zwischen Pinien und entspanntes Reisen abseits des Trubels.",
                "image_url": SCENIC_THEME_IMAGES["coastal_calm"],
                "tags": ["Meeresbrise", "Pinienwald", "Ruhezone", "Meerblick"],
                "prompt": (
                    "Plane eine 10-tägige gemütliche Küstentour an die Adria oder Istrien. Wichtig sind mir "
                    "schattige Stellplätze unter Pinien, Ruhe am Abend und komfortable Infrastruktur."
                ),
                "badge": "Mediterrane Erholung",
                "rag_matched": False,
                "rag_reason": "Ideal für eine längere Auszeit mit Fokus auf Entspannung und Meerblick.",
                "vw_highlights": ["Schattenplatz", "Ruhige Parzelle"],
            },
        ]
    elif lang == "en":
        cards = [
            {
                "id": "curated-wine-en",
                "category": "wine_gastronomy",
                "duration_category": "week",
                "duration_days": 7,
                "title": "Tuscan Wine Trails & Slow Food",
                "subtitle": "Gentle rolling hills, artisan vineyards, local cuisine, and quiet pitches with 230V shore power.",
                "image_url": SCENIC_THEME_IMAGES["wine_gastronomy"],
                "tags": ["Slow Travel", "Vineyards", "230V Power", "Artisan Food"],
                "prompt": (
                    "Plan a relaxing 7-day road trip through Tuscany for my VW California, "
                    "focusing on scenic wine routes, local culinary stops, and comfortable campsites."
                ),
                "badge": "Scenic & Gourmet",
                "rag_matched": False,
                "rag_reason": "Recommended because you appreciate vineyard landscapes and fully serviced pitches.",
                "vw_highlights": ["230V Shore Power", "Scenic Route"],
            },
            {
                "id": "curated-lakes-en",
                "category": "lakes_mountains",
                "duration_category": "weekend",
                "duration_days": 4,
                "title": "Alpine Lakes & Panoramic Byways",
                "subtitle": "Crystal waters, easy lakeshore promenades, and serene pitches overlooking alpine peaks.",
                "image_url": SCENIC_THEME_IMAGES["lakes_mountains"],
                "tags": ["Alpine Lakes", "Scenic Byways", "E-Bike", "Peaceful"],
                "prompt": (
                    "I want a 4-day scenic tour around picturesque alpine lakes. Moderate driving "
                    "pace of max 3 hours per day, quiet campsites with lake views and clean facilities."
                ),
                "badge": "Nature & Serenity",
                "rag_matched": False,
                "rag_reason": "Tailored to your preference for peaceful lakeside camping and gentle trails.",
                "vw_highlights": ["Lakefront Pitch", "Moderate Driving Pace"],
            },
            {
                "id": "curated-castles-en",
                "category": "castles_culture",
                "duration_category": "week",
                "duration_days": 6,
                "title": "Loire Valley Castles & Heritage",
                "subtitle": "Historic châteaux, quaint river valley towns, and charming shaded campsites.",
                "image_url": SCENIC_THEME_IMAGES["castles_culture"],
                "tags": ["Heritage", "Castles", "River Valley", "Shaded Pitches"],
                "prompt": (
                    "Plan a 6-day heritage tour through the Loire Valley exploring historic castles "
                    "and gardens. Keep daily driving under 3 hours with quality campsites."
                ),
                "badge": "Culture & Heritage",
                "rag_matched": False,
                "rag_reason": "Matches your interest in cultural exploration and serene evening stays.",
                "vw_highlights": ["Heritage Stops", "Comfortable Pitches"],
            },
            {
                "id": "curated-coastal-en",
                "category": "coastal_calm",
                "duration_category": "expedition",
                "duration_days": 10,
                "title": "Coastal Pines & Sea Breeze",
                "subtitle": "Unwind by the Mediterranean coast, pine-shaded tranquil camper spots, away from crowded resorts.",
                "image_url": SCENIC_THEME_IMAGES["coastal_calm"],
                "tags": ["Sea Breeze", "Pine Forests", "Tranquility", "Ocean View"],
                "prompt": (
                    "Plan a 10-day peaceful coastal journey along the Adriatic or Mediterranean coast. "
                    "Prioritize shaded campsites under pine trees, evening silence, and full amenities."
                ),
                "badge": "Coastal Relaxation",
                "rag_matched": False,
                "rag_reason": "Selected for an unhurried longer journey with coastal shade and tranquility.",
                "vw_highlights": ["Shaded Pitch", "Tranquil Evening"],
            },
        ]
    else:
        # Default Polish version
        cards = [
            {
                "id": "curated-wine-pl",
                "category": "wine_gastronomy",
                "duration_category": "week",
                "duration_days": 7,
                "title": "Szlak Winnic & Agroturystyka",
                "subtitle": "Malownicze wzgórza, lokalne winnice, regionalne przysmaki i spokojne parcele z przyłączem 230V.",
                "image_url": SCENIC_THEME_IMAGES["wine_gastronomy"],
                "tags": ["Slow Travel", "Winnice", "Prąd 230V", "Lokalna Kuchnia"],
                "prompt": (
                    "Chciałbym zaplanować spokojną, malowniczą trasę na 7 dni camperem VW California "
                    "przez toskańskie lub morawskie winnice. Zależy mi na wizytach w lokalnych winnicach, "
                    "dobrej kuchni i komfortowych kempingach ze stałym przyłączem prądu."
                ),
                "badge": "Polecane dla Koneserów",
                "rag_matched": False,
                "rag_reason": "Polecane, ponieważ cenisz degustacje lokalnych win i komfortowe parcele z prądem 230V.",
                "vw_highlights": ["Przyłącze 230V CEE", "Malownicza trasa"],
            },
            {
                "id": "curated-lakes-pl",
                "category": "lakes_mountains",
                "duration_category": "weekend",
                "duration_days": 3,
                "title": "Pojezierze Drawskie & Czyste Jeziora",
                "subtitle": "Krystaliczne tafle wód, leśne dukty na rowery, cisza i kameralne parcele nad brzegiem jeziora.",
                "image_url": SCENIC_THEME_IMAGES["lakes_mountains"],
                "tags": ["Czyste Jeziora", "Spokój", "E-Bike", "Cisza"],
                "prompt": (
                    "Zaplanuj 3-dniowy relaksujący weekend camperem VW California na Pojezierzu Drawskim lub Kaszubach. "
                    "Zależy mi na spokojnym kempingu tuż nad wodą, czystym zapleczu i trasach spacerowych."
                ),
                "badge": "Natura i Spokój",
                "rag_matched": False,
                "rag_reason": "Idealny weekendowy dystans blisko natury, z dala od zgiełku i bez męczącej jazdy.",
                "vw_highlights": ["Parcela nad jeziorem", "Krótki dojazd"],
            },
            {
                "id": "curated-castles-pl",
                "category": "castles_culture",
                "duration_category": "week",
                "duration_days": 6,
                "title": "Dolina Zamków & Szlak Historii",
                "subtitle": "Średniowieczne twierdze, urokliwe doliny rzek, klimatyczne miasteczka i wygodne postoje.",
                "image_url": SCENIC_THEME_IMAGES["castles_culture"],
                "tags": ["Zabytki & Kultura", "Dolina Rzeki", "Zamki", "Cień i Zieleń"],
                "prompt": (
                    "Zaplanuj 6-dniową podróż szlakiem zamków i historycznych miast (np. Dolina Loary lub "
                    "Szlak Orlich Gniazd/Morawy). Komfortowe kempingi, ciekawe punkty widokowe i bez pośpiechu."
                ),
                "badge": "Kultura i Historia",
                "rag_matched": False,
                "rag_reason": "Odpowiada Twoim upodobaniom do zwiedzania zabytków bez zbędnego pośpiechu.",
                "vw_highlights": ["Zabytki i kultura", "Czyste sanitariaty"],
            },
            {
                "id": "curated-coastal-pl",
                "category": "coastal_calm",
                "duration_category": "expedition",
                "duration_days": 10,
                "title": "Nadmorski Spokój & Sosnowe Lasy",
                "subtitle": "Szum fal, trasy spacerowe wśród sosnowych lasów i relaks na kempingach z dala od zgiełku.",
                "image_url": SCENIC_THEME_IMAGES["coastal_calm"],
                "tags": ["Bryza Morska", "Sosnowy Las", "Strefa Ciszy", "Widok na Morze"],
                "prompt": (
                    "Chcę zaplanować 10-dniowy spokojny wyjazd nad morze (Adriatyk lub Bałtyk). Kluczowe są dla mnie "
                    "zacienione parcele wśród drzew, cisza wieczorem i wysoki standard sanitarny."
                ),
                "badge": "Morski Relaks",
                "rag_matched": False,
                "rag_reason": "Wybrane ze względu na preferencję ciszy i relaksu w otoczeniu nadmorskiej przyrody.",
                "vw_highlights": ["Zacieniona parcela", "Cisza nocna"],
            },
        ]

    if duration and duration != "all":
        matched = [c for c in cards if c.get("duration_category") == duration]
        if matched:
            cards = matched

    if user_location and len(user_location.strip()) > 2:
        for c in cards:
            c["prompt"] = format_enriched_suggestion_prompt(
                c, user_location=user_location, lang=lang
            )

    if shuffle:
        import random
        shuffled = list(cards)
        random.shuffle(shuffled)
        return shuffled

    return cards


def generate_dynamic_suggestions(
    user_id: Optional[str] = None,
    lang: str = "pl",
    count: int = 3,
    duration: str = "all",
    user_location: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate dynamic travel suggestion cards via LLM with deep RAG memory integration.

    Tailored to middle-aged VW California travelers (40-60 years), focusing on
    comfort, scenic pacing, culture, wine, nature, pristine camping infrastructure,
    and duration categories (weekend, week, expedition) with strict geographic range realism.

    Args:
        user_id (str, optional): User UUID for pulling personalized memories.
        lang (str): Desired language ('pl', 'de', 'en').
        count (int): Number of suggestion cards to return (default 3).
        duration (str): Filter by duration ('all', 'weekend', 'week', 'expedition').
        user_location (str, optional): User origin location (e.g. 'Poznań, Polska').

    Returns:
        List[Dict[str, Any]]: Structured list of suggestion cards.
    """
    memories: List[Dict[str, Any]] = []
    if user_id:
        try:
            memories = list_user_memories(user_id=user_id)
        except Exception as e:
            print(f"[travel_suggestions] Failed to load user memories: {e}")

    # Format memories if available
    memory_context = ""
    if memories:
        active_facts = [
            f"- [{m.get('polarity', 'like').upper()}] {m.get('content', '')}"
            for m in memories[:6]
        ]
        if lang == "de":
            memory_context = (
                "Gespeicherte Vorlieben und Reisegewohnheiten dieses Nutzers (RAG):\n"
                + "\n".join(active_facts) + "\n\n"
                "MINDESTENS EINER der Vorschläge MUSS direkt an diese Vorlieben anknüpfen "
                "(z. B. Reisen mit Hund, Seen, E-Bikes, ruhige Stellplätze mit 230V). "
                "Setze für diesen Vorschlag \"rag_matched\": true und badge \"Auf Dich abgestimmt ✨\"."
            )
        elif lang == "en":
            memory_context = (
                "Saved durable preferences and travel habits for this user (RAG):\n"
                + "\n".join(active_facts) + "\n\n"
                "AT LEAST ONE suggestion MUST directly address these preferences "
                "(e.g. traveling with dog, lakes, e-bikes, quiet 230V pitches). "
                "Set for this suggestion \"rag_matched\": true and badge \"Tailored to you ✨\"."
            )
        else:
            memory_context = (
                "Poniżej znajdują się trwale zapamiętane preferencje i nawyki tego użytkownika (RAG):\n"
                + "\n".join(active_facts) + "\n\n"
                "CO NAJMNIEJ JEDNA z propozycji MUSI bezpośrednio nawiązywać do jego preferencji "
                "(np. podróż z psem, upodobanie do jezior, rowerów, unikanie tłumów lub konkretne udogodnienia VW). "
                "Ustaw dla takiej propozycji pole \"rag_matched\": true oraz badge \"Dopasowane do Ciebie ✨\"."
            )

    # Determine user origin location for realistic driving range calculations
    if user_location and len(user_location.strip()) > 2:
        base_loc = user_location.strip()
    elif lang == "pl":
        base_loc = "Polska (punkt startowy w Polsce, np. Wielkopolska / Dolny Śląsk / Mazowsze)"
    elif lang == "de":
        base_loc = "Deutschland (z. B. Bayern / Baden-Württemberg / Hessen) oder Österreich"
    else:
        base_loc = "Central Europe (e.g. UK, Germany, or Austria)"

    if lang == "de":
        duration_guidelines = {
            "weekend": (
                f"ZEITFILTER: Generiere Kurztrips für ein WOCHENENDE (2–4 Tage).\n"
                f"STRIKTE REICHWEITENREGEL FÜR DEN CAMPER:\n"
                f"- Camper-Startpunkt: {base_loc}.\n"
                f"- Maximaler Anfahrtsradius fürs Wochenende: 200–350 km (ca. 2–3.5h gemütliche Fahrt)!\n"
                f"- STRENGES VERBOT von Fernreisezielen (z. B. Toskana, Provence, Kroatien) für ein 2-4 Tage Wochenende ab {base_loc}!\n"
                f"- Schlage nur attraktive Nahziele vor (z. B. Chiemsee, Salzkammergut, Schwarzwald, Allgäuer Alpen, Fränkische Schweiz, Bodensee, Sächsische Schweiz, Mecklenburger Seenplatte).\n"
                f"- Setze \"duration_category\": \"weekend\" und \"duration_days\": 2-4."
            ),
            "week": (
                f"ZEITFILTER: Generiere einwöchige Reisen (5–8 Tage).\n"
                f"- Camper-Startpunkt: {base_loc}.\n"
                f"- Mittlere Reichweite: bis ca. 600–900 km (z. B. Südtirol, Dolomiten, Kärntner Seen, Elsass, Gardasee ab Süddeutschland).\n"
                f"- Setze \"duration_category\": \"week\" und \"duration_days\": 5-8."
            ),
            "expedition": (
                f"ZEITFILTER: Generiere längere FERNREISEN (9–14 Tage).\n"
                f"- Camper-Startpunkt: {base_loc}.\n"
                f"- Große Reichweite: Mehretappen-Touren 1000+ km (z. B. Bretagne, Schottland, Norwegen, Toskana, Korsika).\n"
                f"- Setze \"duration_category\": \"expedition\" und \"duration_days\": 9-14."
            ),
            "all": (
                f"ZEITFILTER: Biete abwechslungsreiche Reisedauern ab Startpunkt {base_loc} an. "
                "Halte strikt das Verhältnis von Fahrzeit zu Distanz ein: Wochenende nur Nahbereich bis 350 km, Woche bis 800 km, Fernreise 1000+ km."
            ),
        }.get(duration, "Biete abwechslungsreiche Reisedauern an.")

        system_instruction = (
            "Du bist das Modul für Reiseinspirationen der Anwendung 'VW California AI Trip Planner'.\n"
            "Deine Aufgabe ist es, faszinierende, stimmungsvolle Reisevorschläge für Personen im "
            "MITTLEREN ALTER (40–60 Jahre) zu erstellen, die mit einem VW California Campervan reisen.\n\n"
            "SPRACHREGEL (ABSOLUT VERPFLICHTEND): ALLE FELDER IM JSON (title, subtitle, tags, prompt, badge, rag_reason, vw_highlights, inferred_preference) "
            "MÜSSEN ZWINGEND AUF DEUTSCH SEIN! Verwende unter keinen Umständen Polnisch oder Englisch!\n\n"
            "Schwerpunkte für diese Zielgruppe:\n"
            "1. Slow Travel & Panoramarouten: Maximal 2–4 Stunden Fahrt pro Tag, landschaftlich schöne Strecken statt Autobahnen.\n"
            "2. Komfort & Infrastruktur: Premium-Stellplätze mit 230V Landstromanschluss, ebener Untergrund, saubere Sanitäranlagen, Nachtruhe.\n"
            "3. Kulinarik, Wein & Kultur: Lokale Weingüter, Agriturismo, Verkostungen, Schlösser, historische Städtchen.\n"
            "4. Erholung in der Natur: Kristallklare Bergseen, Uferspaziergänge, E-Bike-Touren, abseits von Partylärm.\n"
            "5. Geografische Vielfalt: Abwechslungsreiche Regionen in Europa passend zum Startort.\n\n"
            f"{duration_guidelines}\n\n"
            f"{memory_context}\n\n"
            "Prägnanz: 'subtitle' und 'rag_reason' müssen jeweils genau 1 konkreten Satz auf Deutsch enthalten.\n"
            "'prompt' muss eine fertige deutsche Reiseanfrage in der 1. Person sein, die Reisedauer in Tagen, "
            f"Startort ({base_loc}) und Reiseziel enthält (z. B. 'Plane für mich eine 3-tägige Reise mit dem VW California mit Start ab: [Startort]. Ziel: [Reiseziel]...').\n\n"
            "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt:\n"
            "{\n"
            "  \"suggestions\": [\n"
            "    {\n"
            "      \"id\": \"eindeutiger-slug\",\n"
            "      \"category\": \"wine_gastronomy | lakes_mountains | castles_culture | coastal_calm | scenic_nature\",\n"
            "      \"duration_category\": \"weekend | week | expedition\",\n"
            "      \"duration_days\": 7,\n"
            "      \"title\": \"Deutscher Titel\",\n"
            "      \"subtitle\": \"Ein deutscher Satz zu Atmosphäre, Aussicht und Stellplatzqualität\",\n"
            "      \"tags\": [\"Thema 1\", \"Thema 2\", \"Thema 3\"],\n"
            "      \"prompt\": \"Fertige deutsche Reiseanfrage in der 1. Person mit Dauer, Startort und Ziel\",\n"
            "      \"badge\": \"Kurze deutsche Auszeichnung (z. B. 'Auf Dich abgestimmt ✨', 'Genuss & Erholung')\",\n"
            "      \"rag_matched\": true/false,\n"
            "      \"rag_reason\": \"Ein deutscher Satz, warum diese Reise empfohlen wird\",\n"
            "      \"vw_highlights\": [\"VW Highlight 1\", \"VW Highlight 2\"],\n"
            "      \"inferred_preference\": \"Kurze Vorliebe auf Deutsch\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        prompt_user = (
            f"Erstelle genau {count} inspirierende, hochwertige Reiseideen für den VW California Camper"
            + (f" für die Reisedauer: {duration}." if duration != "all" else ".")
            + " Antworte ausnahmslos auf Deutsch!"
        )

    elif lang == "en":
        duration_guidelines = {
            "weekend": (
                f"DURATION FILTER: Generate short WEEKEND trips (2–4 days).\n"
                f"STRICT CAMPER DRIVING RANGE LIMIT:\n"
                f"- Camper starting location: {base_loc}.\n"
                f"- Maximum one-way driving radius for a weekend is 200–350 km (approx. 2–3.5 hours relaxed drive)!\n"
                f"- STRICT PROHIBITION of distant destinations (e.g. Provence, Dolomites, Norway, Croatia) for a 2-4 day weekend starting from {base_loc}!\n"
                f"- Suggest only attractive regional destinations within close driving range.\n"
                f"- Set \"duration_category\": \"weekend\" and \"duration_days\": 2-4."
            ),
            "week": (
                f"DURATION FILTER: Generate ONE-WEEK trips (5–8 days).\n"
                f"- Camper starting location: {base_loc}.\n"
                f"- Medium range: up to 600–900 km.\n"
                f"- Set \"duration_category\": \"week\" and \"duration_days\": 5-8."
            ),
            "expedition": (
                f"DURATION FILTER: Generate EXPEDITION trips (9–14 days).\n"
                f"- Camper starting location: {base_loc}.\n"
                f"- Long range: Multi-stage journeys 1000+ km.\n"
                f"- Set \"duration_category\": \"expedition\" and \"duration_days\": 9-14."
            ),
            "all": (
                f"DURATION FILTER: Propose varied trip durations starting from {base_loc}. "
                "Strictly observe time-to-distance ratio: weekend within 350 km, week within 800 km, expedition 1000+ km."
            ),
        }.get(duration, "Propose varied trip durations.")

        system_instruction = (
            "You are the travel inspiration module for the 'VW California AI Trip Planner' application.\n"
            "Your goal is to generate intriguing, atmospheric travel concepts tailored for "
            "MIDDLE-AGED travelers (40–60 years) traveling in a VW California campervan.\n\n"
            "LANGUAGE RULE (MANDATORY): ALL FIELDS IN THE JSON (title, subtitle, tags, prompt, badge, rag_reason, vw_highlights, inferred_preference) "
            "MUST BE STRICTLY IN ENGLISH! Do not use Polish or other languages!\n\n"
            "Core themes for this audience:\n"
            "1. Slow Travel & Scenic Routes: max 2–4 hours driving per day, scenic byways instead of highways.\n"
            "2. Comfort & Infrastructure: premium pitches with 230V shore power, level ground, pristine sanitary facilities, quiet hours.\n"
            "3. Gastronomy, Wine & Culture: local vineyards, agritourism, tastings, castles, historic towns.\n"
            "4. Nature & Gentle Recreation: crystal lakes, scenic walks, e-bike trails, tranquility.\n"
            "5. Geographic Diversity: fresh European regions suited to the departure origin.\n\n"
            f"{duration_guidelines}\n\n"
            f"{memory_context}\n\n"
            "Conciseness: 'subtitle' and 'rag_reason' must each be exactly 1 evocative sentence in English.\n"
            "'prompt' must be a ready-to-use trip planning request in the 1st person specifying the duration in days, "
            f"departure origin ({base_loc}), and destination (e.g. 'Plan a 3-day road trip for my VW California starting from: [Origin]. Destination: [Destination]...').\n\n"
            "Return ONLY a valid JSON object:\n"
            "{\n"
            "  \"suggestions\": [\n"
            "    {\n"
            "      \"id\": \"unique-slug\",\n"
            "      \"category\": \"wine_gastronomy | lakes_mountains | castles_culture | coastal_calm | scenic_nature\",\n"
            "      \"duration_category\": \"weekend | week | expedition\",\n"
            "      \"duration_days\": 7,\n"
            "      \"title\": \"Evocative English title\",\n"
            "      \"subtitle\": \"One sentence capturing the scenery, driving pace, and pitch comfort\",\n"
            "      \"tags\": [\"Tag 1\", \"Tag 2\", \"Tag 3\"],\n"
            "      \"prompt\": \"Actionable planning request in 1st person with days, origin, and destination\",\n"
            "      \"badge\": \"Short badge (e.g. 'Tailored to you ✨', 'Scenic & Gourmet')\",\n"
            "      \"rag_matched\": true/false,\n"
            "      \"rag_reason\": \"One sentence in English explaining why this is recommended\",\n"
            "      \"vw_highlights\": [\"VW Highlight 1\", \"VW Highlight 2\"],\n"
            "      \"inferred_preference\": \"Short preference description in English\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        prompt_user = (
            f"Generate exactly {count} inspiring, fresh travel ideas for a VW California campervan"
            + (f" for duration: {duration}." if duration != "all" else ".")
            + " Respond entirely in English!"
        )

    else:
        # Default Polish
        duration_guidelines = {
            "weekend": (
                f"FILTR CZASU: Wygeneruj propozycje krótkich wyjazdów typu WEEKEND (2–4 dni).\n"
                f"ŻELAZNA ZASADA REALISTYCZNEGO ZASIĘGU WEEKENDOWEGO DLA CAMPERA (BEZWZGLĘDNA):\n"
                f"- Punkt startowy campera: {base_loc}.\n"
                f"- Maksymalny promień dojazdu w jedną stronę na weekend to 200–350 km (ok. 2–3.5h spokojnej jazdy camperem)!\n"
                f"- KATEGORYCZNY ZAKAZ proponowania odległych celów turystycznych (np. Dolomity, Prowansja, Toskania, Alpy, Lazurowe Wybrzeże, Norwegia czy Chorwacja oddalonych o 800-1600 km) na 2-3 dniowy weekend!\n"
                f"- Jeśli użytkownik startuje z Polski ({base_loc}), na weekend proponuj WYŁĄCZNIE atrakcyjne, malownicze regiony bliskiego zasięgu (np. Kaszuby, Pojezierze Drawskie, Bory Tucholskie, Mazury, Jura Krakowsko-Częstochowska, Dolina Baryczy, Lubuski Szlak Wina, Kotlina Kłodzka, Karkonosze, Góry Stołowe, ewentualnie tuż przy granicy: Czeska Szwajcaria lub Morawy).\n"
                f"- Ustaw \"duration_category\": \"weekend\" oraz \"duration_days\": 2-4."
            ),
            "week": (
                f"FILTR CZASU: Wygeneruj propozycje wyjazdów TYGODNIOWYCH (5–8 dni).\n"
                f"- Punkt startowy campera: {base_loc}.\n"
                f"- ZASIĘG ŚREDNI: do 600–900 km z punktu startowego (np. z Polski: Morawy, Alpy Austriackie/Karyntia, Słowacja, Czeski Raj, Szwajcaria Saksońska, polskie wybrzeże Bałtyku, Bieszczady).\n"
                f"- Ustaw \"duration_category\": \"week\" oraz \"duration_days\": 5-8."
            ),
            "expedition": (
                f"FILTR CZASU: Wygeneruj propozycje dłuższych WYPRAW (9–14 dni).\n"
                f"- Punkt startowy campera: {base_loc}.\n"
                f"- ZASIĘG DALEKI: Trasy wieloetapowe 1000+ km z punktu startowego (np. Toskania, Prowansja, Dolomity, fiordy Norwegii, Bretania, Chorwacja), gdzie 9–14 dni pozwala na spokojne podróżowanie i eksplorację bez pośpiechu.\n"
                f"- Ustaw \"duration_category\": \"expedition\" oraz \"duration_days\": 9-14."
            ),
            "all": (
                f"FILTR CZASU: Zaproponuj zróżnicowane długości wyjazdów z punktu startowego: {base_loc}. "
                "BEZWZGLĘDNIE przestrzegaj relacji czasu do dystansu: propozycja weekendowa (2-4 dni) MUSI być w bliskim zasięgu (max 200–350 km od {base_loc}, bez dalekich podróży przez całą Europę!), tydzień w średnim zasięgu (do 700–900 km), a dopiero długa wyprawa 9–14 dni może prowadzić do odległych zakątków Europy (Prowansja, Toskania, Dolomity)."
            ),
        }.get(duration, "Zaproponuj zróżnicowane długości wyjazdów.")

        system_instruction = (
            "Jesteś modułem generowania inspiracji podróżniczych dla aplikacji VW California AI Trip Planner.\n"
            "Twoim celem jest wygenerowanie intrygujących, sugestywnych propozycji podróży dla osób "
            "w ŚREDNIM WIEKU (40–60 lat) podróżujących camperem VW California.\n\n"
            "Główne motywy i zasady dla tej grupy odbiorców:\n"
            "1. Slow Travel i Malownicze Trasy: tempo jazdy max 2–4 godziny dziennie, unikanie nudnych autostrad na rzecz tras widokowych.\n"
            "2. Komfort i Infrastruktura: parcele premium z przyłączem prądu 230V (shore power), równe podłoże, czyste zaplecze sanitarne, cisza nocna.\n"
            "3. Kulinaria, Wino i Kultura: lokalne winnice, agroturystyka, degustacje, zamki, urokliwe miasteczka z tradycją.\n"
            "4. Relaks na Łonie Natury: krystaliczne jeziora, spacery krajobrazowe, trasy na rowery elektryczne (e-bike), z dala od głośnych imprez.\n"
            "5. Różnorodność geograficzna: Przy każdym wywołaniu proponuj ŚWIEŻE, RÓŻNE regiony Europy "
            "(np. Alpy, Morawy, Toskania, Prowansja, Bretania, Mazury, Kaszuby, Karyntia, fiordy Skandynawii, Szwajcaria Saksońska).\n\n"
            f"{duration_guidelines}\n\n"
            f"{memory_context}\n\n"
            "Zwięzłość: 'subtitle' i 'rag_reason' powinny mieć dokładnie 1 konkretne, sugestywne zdanie.\n"
            "'prompt' ma być gotowym, bezpośrednim poleceniem w 1. osobie do natychmiastowego zaplanowania trasy camperem VW California, "
            "zawierającym liczbę dni oraz cel (np. 'Zaplanuj dla mnie 3-dniowy wyjazd camperem VW California ze startem z: [Punkt Startowy]. Cel: [Nazwa Celu]...'). "
            f"Jeśli podano punkt startowy ({base_loc}), bezwzględnie wstaw go jako miejsce startu w polu 'prompt'!\n\n"
            "Zwróć TYLKO poprawny obiekt JSON o strukturze:\n"
            "{\n"
            "  \"suggestions\": [\n"
            "    {\n"
            "      \"id\": \"unikalny-slug\",\n"
            "      \"category\": \"wine_gastronomy | lakes_mountains | castles_culture | coastal_calm | scenic_nature\",\n"
            "      \"duration_category\": \"weekend | week | expedition\",\n"
            "      \"duration_days\": 7,\n"
            "      \"title\": \"Krótki, nastrojowy tytuł\",\n"
            "      \"subtitle\": \"Jedno zdanie sugerujące atmosferę, widoki, tempo i jakość kempingu\",\n"
            "      \"tags\": [\"Tag 1\", \"Tag 2\", \"Tag 3\"],\n"
            "      \"prompt\": \"Gotowe polecenie zaplanowania trasy w 1. osobie z liczbą dni, punktem startowym i celem\",\n"
            "      \"badge\": \"Krótka odznaka (np. 'Dopasowane do Ciebie ✨', 'Kulinaria & Relaks' itp.)\",\n"
            "      \"rag_matched\": true/false,\n"
            "      \"rag_reason\": \"Jedno zdanie wyjaśniające dopasowanie do preferencji lub stylu podróży\",\n"
            "      \"vw_highlights\": [\"Wyróżnik VW 1\", \"Wyróżnik VW 2\"],\n"
            "      \"inferred_preference\": \"Krótka preferencja do zapisania w pamięci RAG w razie wyboru\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        prompt_user = (
            f"Wygeneruj dokładnie {count} inspirujące, świeże i unikalne propozycje wyjazdowe dla campera VW California"
            + (f" o długości typu {duration}." if duration != "all" else ".")
        )

    def _localize_badge(badge: Optional[str], rag_matched: bool) -> Optional[str]:
        if not badge:
            if rag_matched:
                return "Auf Dich abgestimmt ✨" if lang == "de" else ("Tailored to you ✨" if lang == "en" else "Dopasowane do Ciebie ✨")
            return None
        b_lower = badge.lower()
        if lang == "de":
            if "dopasowane" in b_lower or rag_matched:
                return "Auf Dich abgestimmt ✨"
            if "kulinaria" in b_lower or "wino" in b_lower or "smak" in b_lower:
                return "Kulinarik & Wein 🍷"
            if "natura" in b_lower or "relaks" in b_lower:
                return "Natur & Erholung 🌲"
            if "kultura" in b_lower or "historia" in b_lower or "zamki" in b_lower:
                return "Kultur & Geschichte 🏛️"
            if "gór" in b_lower or "widok" in b_lower:
                return "Berge & Panorama ⛰️"
            if "morze" in b_lower or "morsk" in b_lower:
                return "Küste & Meer 🌊"
        elif lang == "en":
            if "dopasowane" in b_lower or rag_matched:
                return "Tailored to you ✨"
            if "kulinaria" in b_lower or "wino" in b_lower or "smak" in b_lower:
                return "Scenic & Gourmet 🍷"
            if "natura" in b_lower or "relaks" in b_lower:
                return "Nature & Serenity 🌲"
            if "kultura" in b_lower or "historia" in b_lower or "zamki" in b_lower:
                return "Culture & Heritage 🏛️"
            if "gór" in b_lower or "widok" in b_lower:
                return "Mountains & Byways ⛰️"
            if "morze" in b_lower or "morsk" in b_lower:
                return "Coastal Relaxation 🌊"
        return badge

    def _is_mostly_polish(text: str) -> bool:
        if not text:
            return False
        polish_chars = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
        if any(c in polish_chars for c in text):
            return True
        polish_words = {" i ", " w ", " z ", " na ", " dla ", "jest", "kemping", "trasa", "oraz", "odkryj", "spokojem", "poranki"}
        t_low = f" {text.lower()} "
        return any(w in t_low for w in polish_words)

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": prompt_user,
                },
            ],
            response_format={"type": "json_object"},
            timeout=9.0,
            **chat_kwargs(temperature=0.75),
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        raw_items = parsed.get("suggestions", [])

        if not raw_items or not isinstance(raw_items, list):
            print("[travel_suggestions] LLM output empty or invalid, returning curated fallback.")
            return get_curated_fallback_suggestions(
                lang=lang, duration=duration, shuffle=True, user_location=user_location
            )[:count]

        # Check for language leakage when German or English was requested
        if lang in ("de", "en"):
            has_polish_leak = any(
                _is_mostly_polish(item.get("title", "")) or _is_mostly_polish(item.get("subtitle", ""))
                for item in raw_items[:count]
            )
            if has_polish_leak:
                print(f"[travel_suggestions] Detected Polish language leak when '{lang}' requested. Returning pure curated {lang} fallback.")
                return get_curated_fallback_suggestions(
                    lang=lang, duration=duration, shuffle=True, user_location=user_location
                )[:count]

        processed: List[Dict[str, Any]] = []
        for item in raw_items[:count]:
            cat = item.get("category", "scenic_nature")
            img_url = SCENIC_THEME_IMAGES.get(cat, SCENIC_THEME_IMAGES["scenic_nature"])

            dur_cat = item.get("duration_category")
            if dur_cat not in ("weekend", "week", "expedition"):
                dur_cat = duration if duration in ("weekend", "week", "expedition") else "week"

            dur_days = item.get("duration_days")
            if not isinstance(dur_days, int) or dur_days <= 0:
                dur_days = 3 if dur_cat == "weekend" else (10 if dur_cat == "expedition" else 7)

            rag_matched = bool(item.get("rag_matched", False))
            rag_reason = item.get("rag_reason")
            if not rag_reason or (lang in ("de", "en") and _is_mostly_polish(rag_reason)):
                if rag_matched:
                    rag_reason = (
                        "Auf Deine bisherigen Präferenzen und Reisegewohnheiten abgestimmt." if lang == "de"
                        else ("Tailored to your previous preferences and VW California travel style." if lang == "en"
                              else "Dopasowane do Twoich wcześniejszych preferencji i stylu podróżowania VW California.")
                    )
                else:
                    rag_reason = (
                        "Ausgewählte Route für Ruhe, herrliche Aussichten und erstklassige Stellplätze." if lang == "de"
                        else ("Carefully chosen route offering serenity, scenic vistas, and high-standard pitches." if lang == "en"
                              else "Starannie dobrana trasa zapewniająca spokój, malownicze widoki i wysoki standard parceli.")
                    )

            # Ensure prompt is fully enriched with duration, origin (if provided), and vehicle highlights
            prompt_raw = str(item.get("prompt") or "").strip()
            loc_clean = user_location.strip() if user_location and len(user_location.strip()) > 2 else ""
            has_days = f"{dur_days}" in prompt_raw
            has_origin = (loc_clean.lower() in prompt_raw.lower()) if loc_clean else True

            if not prompt_raw or not has_days or not has_origin or len(prompt_raw) < 25 or (lang in ("de", "en") and _is_mostly_polish(prompt_raw)):
                prompt_final = format_enriched_suggestion_prompt(
                    item, user_location=user_location, lang=lang
                )
            else:
                prompt_final = prompt_raw

            badge = _localize_badge(item.get("badge"), rag_matched)

            tags_clean = []
            for t in item.get("tags", []):
                t_str = str(t).strip()
                if t_str.lower().startswith("tag ") or t_str.isdigit():
                    continue
                tags_clean.append(t_str)
            if not tags_clean:
                tags_clean = ["Panoramaroute", "Slow Travel", "230V Strom"] if lang == "de" else (["Scenic Byways", "Slow Travel", "Shore Power"] if lang == "en" else ["Slow Travel", "Komfort 230V"])

            processed.append({
                "id": str(item.get("id") or uuid.uuid4().hex[:8]),
                "category": cat,
                "duration_category": dur_cat,
                "duration_days": dur_days,
                "title": item.get("title", "Malerische Reise" if lang == "de" else ("Scenic Journey" if lang == "en" else "Malownicza Wyprawa")),
                "subtitle": item.get("subtitle", "Entspannte Reise mit erstklassigen Stellplätzen." if lang == "de" else ("Relaxing journey with quality campsites." if lang == "en" else "Spokojna trasa z komfortowymi noclegami.")),
                "image_url": img_url,
                "tags": tags_clean,
                "prompt": prompt_final,
                "badge": badge,
                "rag_matched": rag_matched,
                "rag_reason": rag_reason,
                "vw_highlights": item.get("vw_highlights", ["230V Stromanschluss", "Panoramaroute"] if lang == "de" else (["230V Shore Power", "Scenic Route"] if lang == "en" else ["Przyłącze 230V", "Trasa widokowa"])),
                "inferred_preference": item.get("inferred_preference"),
            })

        return processed

    except Exception as e:
        print(f"[travel_suggestions] Generation failed with error: {e}. Falling back to curated cards.")
        fallback = get_curated_fallback_suggestions(
            lang=lang, duration=duration, user_location=user_location
        )
        return fallback[:count]


def record_suggestion_choice(user_id: str, suggestion_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Store the chosen suggestion in the user's RAG memory.

    Reinforces long-term preferences (Write Path) so the assistant adapts
    to this travel style across current and future sessions.

    Args:
        user_id (str): UUID of the user making the choice.
        suggestion_data (dict): The suggestion card payload that was selected.

    Returns:
        Optional[Dict[str, Any]]: The created or updated user memory record.
    """
    if not user_id or not suggestion_data:
        return None

    # Derive preference content to store
    inferred = suggestion_data.get("inferred_preference")
    title = suggestion_data.get("title", "Podróże widokowe")
    category_theme = suggestion_data.get("category", "general")

    category_mapping = {
        "wine_gastronomy": "activities",
        "lakes_mountains": "camping_style",
        "castles_culture": "activities",
        "coastal_calm": "camping_style",
        "scenic_nature": "driving_pace",
    }
    rag_category = category_mapping.get(category_theme, "camping_style")

    if inferred and len(inferred.strip()) > 5:
        preference_content = inferred.strip()
    else:
        preference_content = (
            f"Preferuje styl podróży: {title}. "
            "Ceni spokojne trasy widokowe, komfortowe kempingi z prądem 230V i lokalne atrakcje."
        )

    try:
        record = save_user_memory(
            user_id=user_id,
            content=preference_content,
            category=rag_category,
            polarity="like",
            confidence=0.95,
        )
        return record
    except Exception as e:
        print(f"[travel_suggestions] Failed to record user choice in RAG memory: {e}")
        return None
