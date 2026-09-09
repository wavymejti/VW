"""
Volkswagen Sniffer Mascot Configuration and Asset Management.

Provides mascot metadata, verified asset locations, and multilingual
persona greetings for the Volkswagen Sniffer AI companion.
"""

import os
from typing import Dict, Any, Optional

# Mascot metadata
MASCOT_NAME = "Volkswagen Sniffer"
MASCOT_DESCRIPTION = (
    "White fluffy canine navigator with an iconic blue nose, navy collar, "
    "and polished Volkswagen emblem medal. The official AI trip planning "
    "companion for VW California camper owners."
)

# Relative and absolute asset locations in frontend/assets
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "assets")

MASCOT_ASSETS = {
    "avatar": "sniffer-avatar.png",
    "sitting": "sniffer-sitting.png",
    "standing": "sniffer-standing.png",
}


def get_mascot_assets() -> Dict[str, Dict[str, Any]]:
    """
    Return dictionary of mascot assets with existence status and file paths.

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary containing filename, absolute path,
        and boolean existence flag.
    """
    results = {}
    for key, filename in MASCOT_ASSETS.items():
        abs_path = os.path.join(ASSETS_DIR, filename)
        exists = os.path.isfile(abs_path)
        file_size = os.path.getsize(abs_path) if exists else 0
        results[key] = {
            "filename": filename,
            "path": abs_path,
            "exists": exists,
            "size_bytes": file_size,
        }
    return results


def get_mascot_greeting(user_name: Optional[str] = None, lang: str = "pl") -> str:
    """
    Generate localized greeting from Volkswagen Sniffer.

    Args:
        user_name: Optional user display name.
        lang: Target language code ('pl', 'de', 'en').

    Returns:
        str: Friendly personalized greeting from Sniffer.
    """
    lang = lang.lower() if lang else "pl"
    name = user_name if user_name else ""

    if lang == "de":
        if name:
            return f"Hallo {name}! Ich bin Volkswagen Sniffer. Wohin soll die Reise heute gehen?"
        return "Hallo! Ich bin Volkswagen Sniffer. Lass uns die besten Campingplätze erschnüffeln!"
    elif lang == "en":
        if name:
            return f"Hello {name}! I am Volkswagen Sniffer. Where are we heading today?"
        return "Hello! I am Volkswagen Sniffer. Let's sniff out the best campsites and scenic routes!"
    else:
        # Default Polish
        if name:
            return f"Cześć {name}! Jestem Volkswagen Sniffer. Dokąd dzisiaj zmierzamy?"
        return "Cześć! Jestem Volkswagen Sniffer. Wywęszę dla Ciebie najlepsze kempingi i widokowe trasy!"
