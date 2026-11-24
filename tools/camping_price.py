"""
Free or paid: one label for every place to stay (Nov 2026 tests: "always say whether the
campsite is free or paid").

Sources, best first: a known price per night, park4night's price text, the park4night spot
type, then the kind of source (Google / partner campsites are paid places). Only a park4night
spot with nothing known about it stays "unknown".
"""

import re

FREE_WORDS = ("free", "gratuit", "gratis", "kostenlos", "gratuito", "gratuita", "darmow",
              "bezpłatn", "bezplatn", "zdarma", "ingyenes", "sans frais")
PAID_WORDS = ("payant", "paid", "kostenpflichtig", "pagamento", "płatn", "platn", "€", "eur", "chf",
              "kč", "zł", "pln", "£")

# park4night spot types (tools/park4night_client._TYPE_LABELS)
FREE_CODES = {"ACC_G", "APN", "PN", "P", "AR", "OR"}
PAID_CODES = {"C", "ACC_P", "ACC_PR"}
HOST_CODES = {"F"}  # farms / wineries hosting campers: free, a purchase is welcome

PAID_SOURCES = {"google_maps", "partner_db", "user_submitted"}


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def price_of(camp):
    """
    Returns:
        dict: {"price_kind": "free" | "paid" | "unknown", "price_label": short English text}
    """
    camp = camp or {}
    cost = _number(camp.get("cost_per_night_eur"))
    if cost is not None:
        if cost <= 0:
            return {"price_kind": "free", "price_label": "Free"}
        return {"price_kind": "paid", "price_label": f"Paid · €{cost:g}/night"}

    info = (camp.get("price_info") or "").strip()
    if info:
        low = info.lower()
        short = info if len(info) <= 32 else info[:31].rstrip() + "…"
        if any(w in low for w in FREE_WORDS) or re.fullmatch(r"0+([.,]0+)?\s*(€|eur)?", low):
            return {"price_kind": "free", "price_label": "Free"}
        if any(w in low for w in PAID_WORDS) or re.search(r"\d", low):
            return {"price_kind": "paid", "price_label": f"Paid · {short}"}

    code = (camp.get("spot_code") or "").upper()
    if code in FREE_CODES:
        return {"price_kind": "free", "price_label": "Free"}
    if code in HOST_CODES:
        return {"price_kind": "free", "price_label": "Free · host spot"}
    if code in PAID_CODES:
        return {"price_kind": "paid", "price_label": "Paid · price not listed"}

    source = camp.get("source") or ("google_maps" if not camp.get("spot_code") and camp.get("place_id")
                                    and not str(camp.get("place_id")).startswith("p4n:") else None)
    if source in PAID_SOURCES:
        return {"price_kind": "paid", "price_label": "Paid · price not listed"}
    return {"price_kind": "unknown", "price_label": "Price not listed"}


def with_price(camp):
    """The camp dict with price_kind and price_label added (in place, also returned)."""
    if isinstance(camp, dict):
        camp.update(price_of(camp))
    return camp
