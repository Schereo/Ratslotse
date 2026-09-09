#!/usr/bin/env python3
"""Welche Idee haben mehrere Städte — und Oldenburg nicht?

**Der Bericht, für den der ganze Speicher gebaut wurde.** Ein einzelnes
„Osnabrück hat X, Oldenburg nicht" ist eine Beobachtung; „vier von sechs
Städten haben X, Oldenburg nicht" ist ein Argument.

```bash
python scripts/cities_cluster_bericht.py                    # die Cluster, wie sie liegen
python scripts/cities_cluster_bericht.py --ohne-oldenburg   # DIE Liste
python scripts/cities_cluster_bericht.py --schwelle 0.78 0.82 0.86   # die Schwelle messen
python scripts/cities_cluster_bericht.py --neu              # vorher neu rechnen
```

**Die Schwelle ist gemessen, nicht gesetzt.** ``--schwelle`` rechnet mehrere
durch und zeigt je Wert vier Zahlen: wie viele Cluster entstehen, wie groß der
größte wird (bei zu niedriger Schwelle wächst alles zu einem zusammen), wie
viele Cluster mindestens zwei Städte haben — und die **Kontrollgruppen**: Die
sieben Vorlagen mit dem Instrument „Zweckentfremdungssatzung erlassen" und die
fünf mit „Kommunale Wärmeplanung beschließen" müssen je in EINEM Cluster
liegen. Das ist der Recall-Test; die Größe des größten Clusters ist der
Precision-Test.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities import clusters as cl  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

#: Instrument-Texte, die im Bestand mehrfach wortgleich vorkommen — sie MÜSSEN
#: je in einem Cluster landen, sonst trennt die Schwelle zu scharf.
KONTROLLE = ("zweckentfremdungssatzung erlassen", "kommunale wärmeplanung beschließen")


def kontrollgruppen(main: CitiesStore) -> dict[str, set[str]]:
    """Papier-Kennungen je Kontroll-Instrument."""
    treffer: dict[str, set[str]] = {k: set() for k in KONTROLLE}
    for kennung, nutzlast in main.annotations_for("classify", "2").items():
        i = (nutzlast.get("instrument") or "").strip().lower()
        if i in treffer:
            treffer[i].add(kennung)
    return treffer


def schwellen_messen(main: CitiesStore, werte: list[float], model: str) -> None:
    kontrolle = kontrollgruppen(main)
    print(f"{'Schwelle':>9} {'Cluster':>8} {'Mitglieder':>11} {'größter':>8} "
          f"{'≥2 Städte':>10} {'ohne OL':>8}  Kontrollgruppen")
    print("-" * 88)
    for schwelle in werte:
        zahlen = cl.build_clusters(main, model, threshold=schwelle,
                                   version=f"probe-{schwelle}")
        stand = main.cluster_stats(model, f"probe-{schwelle}")
        mehrere = sum(1 for z in stand if z["cities"] >= 2)
        ohne_ol = sum(1 for z in stand if z["cities"] >= 2 and not z["has_oldenburg"])
        # Liegt jede Kontrollgruppe in EINEM Cluster?
        je_gruppe = []
        for name, kennungen in kontrolle.items():
            if not kennungen:
                je_gruppe.append(f"{name[:18]}: —")
                continue
            cluster = {z["cluster_id"] for k in kennungen
                       for z in main.cluster_of(k, model, f"probe-{schwelle}")}
            je_gruppe.append(f"{name[:18]}: {len(cluster) or '—'}")
        print(f"{schwelle:>9.2f} {zahlen['clusters']:>8} {zahlen['members']:>11} "
              f"{zahlen['largest']:>8} {mehrere:>10} {ohne_ol:>8}  "
              + " | ".join(je_gruppe))
    print("\nGesucht: die HÖCHSTE Schwelle, bei der beide Kontrollgruppen noch in")
    print("je einem Cluster liegen und der größte Cluster nicht davonläuft.")


def zeigen(main: CitiesStore, model: str, nur_ohne_oldenburg: bool,
           grenze: int, limit: int) -> None:
    einordnung = main.annotations_for("classify", "2")
    stand = main.cluster_stats(model, cl.CLUSTER_VERSION)
    gezeigt = 0
    for z in stand:
        if z["cities"] < grenze:
            continue
        if nur_ohne_oldenburg and z["has_oldenburg"]:
            continue
        mitglieder = [m for m in main.cluster_of(
            _ein_mitglied(main, model, z["cluster_id"]), model, cl.CLUSTER_VERSION)]
        if not mitglieder:
            continue
        klasse = einordnung.get(mitglieder[0]["id"]) or {}
        marke = "" if z["has_oldenburg"] else "   ← Oldenburg fehlt"
        print(f"\nCluster {z['cluster_id']:<5} „{(klasse.get('instrument') or '?')[:52]}\""
              f"   {z['cities']} Städte, {z['members']} Papiere{marke}")
        for m in mitglieder[:8]:
            ergebnis = (main.outcome_for_paper(m["id"]) or {}).get("outcome") or "—"
            stadt = (m["body_id"] or "")[:12]
            print(f"   {stadt:13} {(m['date'] or '')[:7]}  {ergebnis:9} "
                  f"{(m['name'] or '')[:64]}")
        gezeigt += 1
        if gezeigt >= limit:
            break
    if not gezeigt:
        print("Keine Cluster, die den Filtern entsprechen.")


def _ein_mitglied(main: CitiesStore, model: str, cluster_id: int) -> str:
    row = main._conn.execute(
        "SELECT paper_id FROM idea_clusters WHERE model=? AND version=? "
        "AND cluster_id=? ORDER BY score DESC LIMIT 1",
        (model, cl.CLUSTER_VERSION, cluster_id)).fetchone()
    return row["paper_id"] if row else ""


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--neu", action="store_true", help="Vektoren und Cluster neu rechnen")
    p.add_argument("--schwelle", type=float, nargs="*",
                   help="mehrere Schwellen durchprobieren statt zu berichten")
    p.add_argument("--ohne-oldenburg", action="store_true",
                   help="nur Cluster, in denen Oldenburg FEHLT — die eigentliche Liste")
    p.add_argument("--staedte", type=int, default=2, help="mindestens so viele Städte")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--json", action="store_true", help="als JSON statt als Text")
    a = p.parse_args()

    db, _f, _r = default_paths()
    main_store = CitiesStore(db)
    try:
        if a.neu:
            print("rechne …", cl.run(main_store, EMBED_MODEL))
        if a.schwelle:
            schwellen_messen(main_store, a.schwelle, EMBED_MODEL)
            return 0
        if a.json:
            stand = main_store.cluster_stats(EMBED_MODEL, cl.CLUSTER_VERSION)
            print(json.dumps(stand, ensure_ascii=False, indent=1))
            return 0
        stand = main_store.cluster_stats(EMBED_MODEL, cl.CLUSTER_VERSION)
        verteilung = Counter(z["cities"] for z in stand)
        print(f"{len(stand)} Cluster; Städte je Cluster: "
              + ", ".join(f"{k}×{v}" for k, v in sorted(verteilung.items())))
        ohne = sum(1 for z in stand if z["cities"] >= 2 and not z["has_oldenburg"])
        print(f"davon mit mindestens zwei Städten OHNE Oldenburg: {ohne}")
        zeigen(main_store, EMBED_MODEL, a.ohne_oldenburg, a.staedte, a.limit)
        return 0
    finally:
        main_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
