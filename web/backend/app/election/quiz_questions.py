"""Quizfragen zur Ratswahl 2026 (Plan Q12) — aus dem eingefrorenen Ergebnis.

„In welchem Wahlbereich holte die SPD mehr Stimmen?" und „Wo war die
Wahlbeteiligung höher?" als ``format='compare'``: zwei Wahlbereiche
nebeneinander, danach die Anteile. Quelle ist ``archive.night`` — die
Open-Data-CSVs des Votemanagers, die ``scripts/wahl_einfrieren.py`` ins Repo
gelegt hat. Kein Netz, kein Modell.

**Nur Parteien, nie Kandidierende**, und nur Parteien mit mindestens
:data:`MIN_CITY_SHARE` Prozent in der Stadt, alle nach derselben Regel — keine
Auswahl, die eine Partei bevorzugt. Und **erst nach der Stichwahl**
(:data:`RELEASE`): Vor dem 27.09.2026 stünde ein Wahl-Spiel mitten im
Wahlkampf ums Oberbürgermeisteramt.

Das Modul liegt in ``app``, weil die Wahlabend-Daten hier leben; ``council``
darf ``app`` nicht importieren (``tests/test_schichten.py``). Aufgerufen wird es
aus ``scripts/build_quiz_formats.py``.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from datetime import date

from . import archive

ELECTION = "ratswahl-2026"
AREA = ("topic", "ratswahl-2026")
RELEASE = date(2026, 9, 28)
MIN_CITY_SHARE = 5.0
#: Unterschied in Prozentpunkten, ab dem ein Vergleich kein Münzwurf ist.
MIN_GAP_PP = 4.0
PAIRS_PER_PARTY = 2
PARTY_LABEL = {"gruene": "die Grünen", "spd": "die SPD", "cdu": "die CDU",
               "linke": "die Linke", "afd": "die AfD", "fdp": "die FDP", "volt": "Volt"}
#: „holten die Grünen", aber „holte die SPD".
PLURAL = {"gruene"}


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def _pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + " %"


def _pick_pairs(values: dict[str, float], n: int, salt: str) -> list[tuple[str, str]]:
    """Bis zu ``n`` Paare mit genug Abstand — der größte Unterschied zuerst,
    dann einer aus der Mitte (sonst wären alle Fragen gleich leicht)."""
    pairs = [(a, b) for a, b in itertools.combinations(sorted(values), 2)
             if abs(values[a] - values[b]) >= MIN_GAP_PP]
    pairs.sort(key=lambda p: -abs(values[p[0]] - values[p[1]]))
    if len(pairs) <= n:
        return pairs
    return [pairs[0], pairs[len(pairs) // 2]][:n]


def _question(slug: str, question: str, a: str, b: str, values: dict[str, float],
              subject: str, source: str) -> dict:
    first, second = (a, b) if int(_key("side", slug, a, b), 16) % 2 else (b, a)
    big, small = (first, second) if values[first] >= values[second] else (second, first)
    chart = {"type": "bars", "title": subject, "unit": "%",
             "items": [{"label": k, "value": round(values[k], 1), **({"highlight": True} if k == big else {})}
                       for k in (big, small)]}
    return {
        "area_type": AREA[0], "area_key": AREA[1], "category": "estimation", "difficulty": "easy",
        "qtype": "mc", "format": "compare", "question": question,
        "options": [first, second], "correct_index": 0 if big == first else 1,
        "explanation": f"{big}: {_pct(values[big])}, {small}: {_pct(values[small])}.",
        "chart": json.dumps(chart, ensure_ascii=False),
        "source_type": "city", "source_ref": source,
        "content_hash": _key("wahl", ELECTION, slug, a, b),
    }


def _source_url() -> str:
    """Die Open-Data-Seite des Votemanagers, wie sie das Archiv notiert hat."""
    from . import elections, reference
    wahl = elections.get(ELECTION)
    if not wahl or not wahl.archive_folder:
        return ""
    try:
        meta = json.loads(reference.meta_path(wahl.archive_folder).read_text(encoding="utf-8"))
        return (meta.get("quelle") or {}).get("url") or ""
    except (OSError, ValueError):
        return ""


def questions(today: date | None = None, *, force: bool = False) -> list[dict]:
    """Die Wahlfragen — leer vor :data:`RELEASE` (außer mit ``force``) oder
    wenn das Archiv fehlt."""
    if not force and (today or date.today()) < RELEASE:
        return []
    night = archive.night(ELECTION)
    if not night:
        return []
    source = _source_url()
    areas = night["areas"]
    out: list[dict] = []
    city = {p["slug"]: p["share_pct"] or 0 for p in night["parties"]}
    for slug, share in sorted(city.items(), key=lambda x: -x[1]):
        if share < MIN_CITY_SHARE or slug not in PARTY_LABEL:
            continue
        values = {a["name"]: next((p["share_pct"] for p in a["parties"] if p["slug"] == slug), 0.0) or 0.0
                  for a in areas}
        for a, b in _pick_pairs(values, PAIRS_PER_PARTY, slug):
            out.append(_question(
                slug, f"In welchem Wahlbereich {'holten' if slug in PLURAL else 'holte'} {PARTY_LABEL[slug]} "
                      f"bei der Ratswahl 2026 mehr Stimmen?",
                a, b, values, f"Stimmenanteil {PARTY_LABEL[slug].removeprefix('die ')} 2026", source))
    turnout = {a["name"]: a["totals"]["turnout_pct"] or 0.0 for a in areas}
    for a, b in _pick_pairs(turnout, 3, "turnout"):
        out.append(_question("turnout", "Wo war die Wahlbeteiligung bei der Ratswahl 2026 höher?",
                             a, b, turnout, "Wahlbeteiligung 2026", source))
    return out
