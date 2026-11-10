#!/usr/bin/env python3
"""Orte der Maßnahmen eines Plans — ohne Sprachmodell, ohne neues Geocoding, von Hand durchgesehen.

Die Maßnahmenlisten (``council/plan_measures/``) nennen Straßen und Plätze beim Namen
(„Neue Fahrradstraße Lindenallee“). Der Ortskatalog der Ratsdaten (``council_locations``)
kennt sie schon, mit Koordinaten und meist mit dem Verlauf. Dieses Skript gleicht beides ab:
Ein Ort gehört zu einer Maßnahme, wenn sein Name als ganzes Wort im Titel steht.

Ein Name, der nur zufällig passt („Gehweg“, „Parkplatz“), ist kein Ort — solche Namen stehen
in ``GENERIC``; was der Abgleich sonst findet, aber nicht trägt, in ``REJECTED`` (mit Grund).
In die Datei (``council/plan_places/<plan>.json``, eingecheckt) kommt der Rest — nach dem
Durchsehen mit ``--zeigen``.

    python scripts/plan_orte.py --zeigen       # Vorschläge, nichts schreiben
    python scripts/plan_orte.py                # Dateien schreiben
    python scripts/plan_orte.py --pruefen      # ohne Abgleich: Dateien gegen Katalog und Liste halten
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council import plan_pages, plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402

#: Welche Orte des Katalogs als Ort einer Maßnahme taugen — Flächen und Stadtteile nicht:
#: „Kreyenbrück“ in einem Titel heißt nicht, dass die Maßnahme den ganzen Stadtteil meint.
KINDS = ("street", "square", "building", "water", "facility", "structure", "route")
#: Kürzer ist fast immer ein Wortteil oder ein Gattungswort.
MIN_NAME = 6

#: Katalognamen, die in einem Titel ein Gattungswort sind und kein Ort — dieselbe Liste wie auf der Seite.
GENERIC = plan_pages.PLACE_GENERIC

#: Was der Abgleich findet, aber nicht trägt — (Plan, Code, Name): Grund.
REJECTED: dict[tuple[str, str, str], str] = {
    ("smv2025", "22", "Gesundheitsamt"): "Gemeint ist die Erschließung an der Auguststraße, nicht das Gebäude",
    ("smv2025", "67", "Pulverturm"): "Gemeint ist der Wallring als Ganzes; der Pulverturm ist nur ein Abschnitt",
    ("smv2025", "1", "BBS III"): "Eine Wegeverbindung vom Hauptbahnhof dorthin — die Schule ist nur ihr Ziel",
    ("smv2025", "5", "Pferdemarkt"): "Eine Wegeverbindung vom Hauptbahnhof dorthin — der Platz ist nur ihr Ziel",
    ("smv2025", "39", "Haarenufer"): "Nur als Beispiel genannt („z. B.“), keine Festlegung",
    ("ernaehrungsstrategie", "A65", "Wochenmarkt"): "Es gibt mehrere Wochenmärkte; der Katalog kennt nur einen",
}


def _pattern(name: str) -> re.Pattern:
    return re.compile(r"(?<![\wäöüß])" + re.escape(name.lower()) + r"(?![\wäöüß])")


def propose(store: CouncilStore, key: str) -> list[dict]:
    """Je Maßnahme die Orte des Katalogs, deren Name im Titel steht — längere Namen zuerst, ein Name,
    der in einem längeren steckt („Ehlers-Straße“ in „Hermann-Ehlers-Straße“), fällt weg."""
    listed = plans.measures(key)
    if not listed:
        return []
    catalog = [c for c in store.plan_catalog_names(KINDS)
               if len(c["name"]) >= MIN_NAME and c["name"].lower() not in GENERIC]
    catalog.sort(key=lambda c: -len(c["name"]))
    out = []
    for m in listed["measures"]:
        title = m["title"].lower()
        found: list[dict] = []
        for c in catalog:
            if (key, m["code"], c["name"]) in REJECTED or not _pattern(c["name"]).search(title):
                continue
            if any(c["name"].lower() in f["name"].lower() for f in found):
                continue
            if any(f["name"].lower() == c["name"].lower() for f in found):
                continue
            found.append({"slug": c["slug"], "name": c["name"]})
        if found:
            out.append({"code": m["code"], "places": found})
    return out


def check(store: CouncilStore | None, key: str) -> list[str]:
    """Steht jeder Name im Titel seiner Maßnahme, und kennt der Katalog den Ort (mit ``store``)?"""
    data = plan_state.measure_places(key)
    if data is None:
        return []
    listed = plans.measures(key)
    titles = {m["code"]: m["title"] for m in (listed or {}).get("measures", [])}
    problems = []
    known = store.plan_catalog_places([p["slug"] for e in data["measures"] for p in e["places"]]) if store else None
    for entry in data["measures"]:
        title = titles.get(entry["code"])
        if title is None:
            problems.append(f"{key}: Maßnahme {entry['code']} steht nicht (mehr) in der Liste")
            continue
        for place in entry["places"]:
            if not _pattern(place["name"]).search(title.lower()):
                problems.append(f"{key} {entry['code']}: „{place['name']}“ steht nicht im Titel „{title}“")
            if (key, entry["code"], place["name"]) in REJECTED:
                problems.append(f"{key} {entry['code']}: „{place['name']}“ ist verworfen")
            if known is not None and place["slug"] not in known:
                problems.append(f"{key} {entry['code']}: Ort {place['slug']} fehlt im Katalog oder hat keine Koordinaten")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--zeigen", action="store_true", help="Vorschläge zeigen, nichts schreiben")
    ap.add_argument("--pruefen", action="store_true", help="Dateien gegen Katalog und Maßnahmenliste halten")
    args = ap.parse_args(argv)
    store = CouncilStore(args.db)
    try:
        if args.pruefen:
            problems = [p for key in plan_state.measure_place_keys() for p in check(store, key)]
            print("\n".join(problems) or f"✓ {len(plan_state.measure_place_keys())} Dateien passen zu Katalog und Liste")
            return 1 if problems else 0
        plan_state.PLACES_DIR.mkdir(exist_ok=True)
        for key in plans.PLANS:
            found = propose(store, key)
            if not found:
                continue
            listed = plans.measures(key) or {"measures": []}
            titles = {m["code"]: m["title"] for m in listed["measures"]}
            if args.zeigen:
                print(f"## {key}: {len(found)} von {len(listed['measures'])} Maßnahmen")
                for e in found:
                    print(f"   {e['code']:>5} {titles[e['code']][:70]:70s} → {', '.join(p['name'] for p in e['places'])}")
                continue
            data = {"plan": key, "method": "Ortsname im Maßnahmentitel, abgeglichen mit dem Ortskatalog; von Hand durchgesehen",
                    "generated": dt.date.today().isoformat(), "measures": found}
            path = plan_state.PLACES_DIR / f"{key}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"geschrieben: {path.relative_to(WURZEL)} ({len(found)} Maßnahmen)")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
