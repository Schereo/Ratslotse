"""Normalise Oldenburg council party / faction names.

The protocols spell the same party many ways ("Bündnis 90/Die Grünen" vs
"DIE GRÜNEN", "Gruppe DIE LINKE./Piratenpartei" vs "DIE LINKE./Piratenpartei")
and the attendance lists mix in non-party roles (Verwaltung, Gast, beratend…).
``normalize_party`` collapses the variants to a canonical short label and returns
``None`` for non-parties, so party-level aggregation is meaningful.
"""
from __future__ import annotations

# Substrings that mark a non-party row (administration, guests, advisory roles…).
_NON_PARTY = (
    "verwaltung", "gast", "beratend", "protokoll", "schriftführ", "oberbürgermeister",
    "baurat", "dezernent", "stadtkämmerer", "presse", "gleichstellung",
)

# Checked top-to-bottom; first hit wins, so put the more specific rules first
# (e.g. "fdp/volt" before "fdp", else FDP/Volt would collapse into FDP).
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("grüne", "grünen"), "Grüne"),
    (("linke", "piraten"), "DIE LINKE/Piraten"),
    (("fdp/volt",), "FDP/Volt"),
    (("fossil free",), "Fossil Free"),
    (("für oldenburg",), "Für Oldenburg"),
    (("wfo", "lkr"), "WFO/LKR"),
    (("bsw",), "BSW"),
    (("afd",), "AfD"),
    (("spd",), "SPD"),
    (("cdu",), "CDU"),
    (("fdp",), "FDP"),
    (("volt",), "Volt"),
]

# Preferred display order (most active first) for stable UI sorting.
CANONICAL_ORDER = [
    "Grüne", "SPD", "CDU", "FDP", "DIE LINKE/Piraten", "FDP/Volt", "BSW", "AfD",
    "Volt", "Fossil Free", "WFO/LKR", "Für Oldenburg",
]


def normalize_party(raw: str | None) -> str | None:
    """Canonical short label for a party, or None for non-parties / empty."""
    if not raw:
        return None
    low = raw.strip().lower()
    if not low or any(x in low for x in _NON_PARTY):
        return None
    for needles, label in _RULES:
        if any(n in low for n in needles):
            return label
    # Unknown but plausibly a party/group — keep the cleaned original.
    return raw.strip()


def order_key(party: str) -> tuple[int, str]:
    """Sort key putting the well-known parties first, then alphabetical."""
    return (CANONICAL_ORDER.index(party) if party in CANONICAL_ORDER else len(CANONICAL_ORDER), party)
