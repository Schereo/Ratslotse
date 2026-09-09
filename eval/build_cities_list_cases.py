#!/usr/bin/env python3
"""Die obersten Einträge der Ideen-Liste als Vorlage zum Gegenlesen.

**Wozu.** Alle bisherigen Prüfstände messen EINZELURTEILE: Ist der Status
richtig, der Beleg gefunden, die Aufwandsklasse getroffen? Keiner misst die
LISTE — ob die zwanzig obersten Einträge zwanzig sind, die ein Ratsmitglied
sehen will. Genau daran haben Phase 3 und Phase 4 gearbeitet, und genau das
hatte keinen Maßstab.

Dieses Skript schreibt die Kandidaten heraus; die Spalte ``on_list`` füllt
ein MENSCH. Danach rechnet ``run_cities_list.py`` Präzision@20 und @50
dagegen — ohne Modell, in Sekunden.

```bash
python eval/build_cities_list_cases.py            # 100 Kandidaten
python eval/build_cities_list_cases.py --wie-viele 60 --ausgabe eval/x.json
```

Ein zweiter Lauf überschreibt **keine** vorhandenen Urteile: Was schon ein
``on_list`` trägt, bleibt, neue Einträge kommen mit ``null`` dazu. Sonst
wäre jede Änderung an der Sortierung eine neue Runde Handarbeit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities.clusters import CLUSTER_VERSION  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402
from council.topics import POLICY_FIELDS  # noqa: E402

ZIEL = WURZEL / "eval" / "cases_cities_list.json"


def kandidaten(main: CitiesStore, wie_viele: int) -> list[dict]:
    """Die obersten Einträge, in der Reihenfolge der Karte.

    Gesammelt wird je Themenfeld und dann nach der Zahl der anderen Städte
    zusammengeführt — dieselbe Größe, nach der auch die Karte sortiert.
    """
    peers = main.peers_by_paper(EMBED_MODEL, CLUSTER_VERSION)
    alle: list[dict] = []
    for feld in POLICY_FIELDS:
        zeilen, _, _ = main.ideas(feld, status=("missing",), limit=40)
        for rang, z in enumerate(zeilen):
            klasse = json.loads(z.get("classify_json") or "{}")
            alle.append({
                "id": z["id"],
                "body_id": z["body_id"],
                "field": feld,
                "rang_im_feld": rang,
                "name": z.get("name") or "",
                "instrument": klasse.get("instrument"),
                "summary": klasse.get("summary"),
                "date": z.get("date"),
                "cities": peers.get(z["id"], 0),
                "on_list": None,
                "why": "",
            })
    alle.sort(key=lambda z: (-z["cities"], z["rang_im_feld"]))
    return alle[:wie_viele]


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--wie-viele", type=int, default=100)
    p.add_argument("--ausgabe", type=Path, default=ZIEL)
    a = p.parse_args()

    db, _f, _r = default_paths()
    store = CitiesStore(db)
    try:
        neu = kandidaten(store, a.wie_viele)
    finally:
        store.close()

    alt = {}
    if a.ausgabe.exists():
        alt = {z["id"]: z for z in json.loads(a.ausgabe.read_text(encoding="utf-8"))}
    behalten = 0
    for z in neu:
        vorher = alt.get(z["id"])
        if vorher and vorher.get("on_list") is not None:
            z["on_list"], z["why"] = vorher["on_list"], vorher.get("why", "")
            behalten += 1
    a.ausgabe.write_text(json.dumps(neu, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    offen = sum(1 for z in neu if z["on_list"] is None)
    print(f"{len(neu)} Kandidaten in {a.ausgabe.relative_to(WURZEL)}")
    print(f"  {behalten} Urteile übernommen, {offen} offen.")
    if offen:
        print("\nZu füllen ist je Eintrag `on_list` (true/false) und `why`.")
        print("Die Frage lautet NICHT „stimmt das Urteil?“, sondern:")
        print("  Gehört das auf eine Liste von Ideen, die Oldenburg fehlen?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
