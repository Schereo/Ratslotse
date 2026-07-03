"""Normalise Oldenburg council faction / group names to real parties.

Grounded in the actual 2021–2026 council (oldenburg.de, NWZ), incl. the mid-term
changes: BSW = the former Die-Linke members (switched 2024), the FDP/Volt group
dissolved into FDP + Volt, the new group "Für Oldenburg" (2024). See the
[[reference_oldenburg_rat]] memory.

``normalize_party`` is a **whitelist**: only recognised factions/groups map to a
canonical label; everything else (administration, advisory boards, NGOs/initiatives
like BUND/NABU/ADFC/Fossil Free, named individuals) returns ``None`` so it is left
out of the party analysis.
"""
from __future__ import annotations

# Substrings that mark a NON-party row (kept out of the analysis).
_NON_PARTY = (
    "verwaltung", "beratend", "gast", "protokoll", "schriftführ", "oberbürgermeister",
    "baurat", "dezernent", "stadtkämmerer", "beauftragt", "beirat", "vertretung",
    "elternrat", "naturschutz", "nabu", "bund", "adfc", "fossil free", "agenda",
    "ratsfrau", "ratsherr", "prof.", "dr. ", "herr ", "frau ",
)

# Recognised factions/groups, checked top-to-bottom (most specific first).
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("grüne", "grünen"), "Grüne"),
    (("bsw",), "BSW"),                       # ex-Die-Linke members (2024)
    (("linke",), "Die Linke"),               # joint group + solo Linke (→ BSW 2024)
    (("piraten",), "Piraten"),               # Piraten after the Linke split
    (("für oldenburg",), "Für Oldenburg"),   # new group (2024)
    (("wfo", "lkr"), "WFO/LKR"),
    (("ibo", "live"), "IBO/LiVe"),
    (("afd",), "AfD"),
    (("spd",), "SPD"),
    (("cdu",), "CDU"),
    (("fdp",), "FDP"),
    (("volt",), "Volt"),
]

# Display order (current / most active first), then historical.
CANONICAL_ORDER = [
    "Grüne", "SPD", "CDU", "BSW", "FDP", "Für Oldenburg", "Volt", "AfD",
    "Die Linke", "Piraten", "WFO/LKR", "IBO/LiVe",
]


def normalize_party(raw: str | None) -> str | None:
    """Canonical party/group label, or None for non-parties / unknown."""
    if not raw:
        return None
    low = raw.strip().lower()
    if not low or any(x in low for x in _NON_PARTY):
        return None
    for needles, label in _RULES:
        if any(n in low for n in needles):
            return label
    return None  # unknown → not a recognised party


def order_key(party: str) -> tuple[int, str]:
    """Sort key putting the well-known parties first, then alphabetical."""
    return (CANONICAL_ORDER.index(party) if party in CANONICAL_ORDER else len(CANONICAL_ORDER), party)


def parties_in_text(text: str | None) -> list[str]:
    """Every recognised party mentioned in a free-text snippet (Anlagen-Label wie
    "Antrag SPD CDU Grüne FDP" oder erste PDF-Seite), in canonical order, deduped.

    Unlike ``normalize_party`` (whole-string, one label) this scans token-wise with
    word boundaries — "Begrünung" must NOT count as "Grüne". Non-party context is
    not filtered here; callers use this on Antrag documents where a party mention
    means authorship."""
    import re as _re

    if not text:
        return []
    low = text.lower()
    found: list[str] = []
    for needles, label in _RULES:
        if label in found:
            continue
        for n in needles:
            # "wfo"/"lkr" style tuples: any needle counts on its own.
            if _re.search(rf"(?<![a-zäöüß]){_re.escape(n)}(?![a-zäöüß])", low):
                found.append(label)
                break
    return sorted(found, key=order_key)
