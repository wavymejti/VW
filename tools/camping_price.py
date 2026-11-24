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


# park4night's price texts are often French; the app shows them in plain words.
_PRICE_WORDS = [
    (r"\bgratuite?s?\b", "gratis"), (r"\bgratuit[oa]s?\b", "gratis"), (r"\bkostenlos\b", "gratis"),
    (r"\bpayante?s?\b", "paid"), (r"\bnuits?\b", "night"), (r"\bjours?\b", "day"),
]


def plain_price_text(text):
    """'Gratuit' -> 'gratis', '10 €/nuit' -> '10 €/night' (case kept for the first letter)."""
    if not text:
        return text
    out = text
    for pattern, word in _PRICE_WORDS:
        out = re.sub(pattern, lambda m: word.capitalize() if m.group(0)[0].isupper() else word,
                     out, flags=re.IGNORECASE)
    return out


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
        plain = re.sub(r"^\s*paid\b[\s:,-]*", "", plain_price_text(info), flags=re.IGNORECASE) or "price not listed"
        short = plain if len(plain) <= 32 else plain[:31].rstrip() + "…"
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
        if camp.get("price_info"):
            camp["price_info"] = plain_price_text(camp["price_info"])
    return camp
