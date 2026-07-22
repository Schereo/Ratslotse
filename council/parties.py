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
# Ratsgruppen wandeln sich über die Wahlperiode (FDP/Volt-Gruppe → getrennt,
# Linke → BSW-Wechsler 2024): die LABELS in den Dokumenten tragen die Zeit —
# ein alter „Gruppe FDP/Volt"-Antrag zählt über parties_for_faction() für
# beide Parteien, neue Anträge nennen nur noch die einzelne Fraktion.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("grüne", "grünen"), "Grüne"),
    (("bsw",), "BSW"),                       # ex-Die-Linke members (2024)
    (("linke",), "Die Linke"),               # joint group + solo Linke (→ BSW 2024)
    (("piraten",), "Piraten"),               # Piraten after the Linke split
    (("für oldenburg",), "Für Oldenburg"),   # new group (2024)
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
    "Die Linke", "Piraten", "IBO/LiVe",
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


# Bekannte Oldenburger Rats-GRUPPEN: ein Zusammenschluss mehrerer Parteien bzw.
# Parteiloser, der zu klein für eine eigene Fraktion ist. Im Protokoll trägt ein
# Gruppen-Mitglied den GRUPPENNAMEN als Anwesenheits-Label („FDP/Volt", „Für
# Oldenburg") — NICHT seine Einzelpartei. `normalize_party` kollabiert das auf
# eine Partei (→ „FDP/Volt" wird „FDP"), was Mitglieder falsch zuordnet. Ein „/"
# allein taugt nicht als Signal („Bündnis 90/Die Grünen" ist eine Partei) — daher
# kuratiert (es sind nur eine Handvoll Gruppen je Wahlperiode).
# (needles: ALLE müssen im Label vorkommen) → (Anzeigename, Mitglieds-Parteien)
_GROUPS: list[tuple[tuple[str, ...], str, tuple[str, ...]]] = [
    (("fdp", "volt"), "FDP/Volt", ("FDP", "Volt")),                 # bis 2025, dann getrennt
    (("linke", "piraten"), "Die Linke/Piraten", ("Die Linke", "Piraten")),
    (("für oldenburg",), "Für Oldenburg", ("parteilos", "Piraten")),  # Finke (parteilos) + Sander (Piraten)
    (("ibo", "live"), "IBO/LiVe", ("IBO", "LiVe")),
]


def classify_faction(raw: str | None) -> dict:
    """Ordnet ein Anwesenheits-Label ein — Partei, (Rats-)Gruppe oder parteilos —
    und hält Gruppen als Gruppen fest, statt sie auf eine Partei zu kollabieren.

    Rückgabe:
    - ``kind``: ``"partei"`` | ``"gruppe"`` | ``"parteilos"`` | ``"unbekannt"``
    - ``label``: Anzeigename (``"SPD"``, ``"FDP/Volt"``, ``"Für Oldenburg"``, ``"parteilos"``)
    - ``parties``: kanonische Mitglieds-Parteien (Partei → sich selbst; Gruppe →
      ihre Parteien; sonst leer)
    - ``group``: Gruppenname oder ``None``
    """
    if raw is None or not raw.strip():
        return {"kind": "parteilos", "label": "parteilos", "parties": [], "group": None}
    low = raw.strip().lower()
    if any(x in low for x in _NON_PARTY):
        return {"kind": "unbekannt", "label": raw.strip(), "parties": [], "group": None}
    for needles, name, members in _GROUPS:
        if all(n in low for n in needles):
            return {"kind": "gruppe", "label": name, "parties": list(members), "group": name}
    p = normalize_party(raw)
    if p:
        return {"kind": "partei", "label": p, "parties": [p], "group": None}
    return {"kind": "unbekannt", "label": raw.strip(), "parties": [], "group": None}


def faction_label(raw: str | None) -> str | None:
    """Gruppen-bewusstes Anzeige-Label einer Person (Gruppenname statt kollabierter
    Einzelpartei). ``None`` für Verwaltung/Unbekanntes."""
    c = classify_faction(raw)
    return c["label"] if c["kind"] in ("partei", "gruppe", "parteilos") else None


def parties_for_faction(raw: str | None) -> list[str]:
    """Alle Parteien hinter einem Fraktions-/Gruppen-Label eines Antrags:
    „Gruppe FDP/Volt" → ["FDP", "Volt"] (der Antrag zählt für beide),
    „SPD-Fraktion" → ["SPD"]. Non-Partei-Labels (Verwaltung, Beiräte,
    Initiativen …) → leere Liste. Für ANTRÄGE gedacht — bei Personen
    (Anwesenheit) bleibt ``normalize_party`` richtig, denn eine Person gehört
    genau einer Fraktion an."""
    if not raw:
        return []
    low = raw.strip().lower()
    if not low or any(x in low for x in _NON_PARTY):
        return []
    return parties_in_text(raw)


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
