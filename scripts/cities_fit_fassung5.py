#!/usr/bin/env python3
"""Fassung 4 nach 5 übernehmen — außer den „nicht anwendbar"-Urteilen.

**Warum nicht alles neu beurteilen.** Fassung 5 unterscheidet sich von 4 an
genau einer Stelle: `not_applicable` ist jetzt an die Frage gebunden, ob der
Rat die fehlende Voraussetzung selbst beschließen könnte. Eine VERSCHÄRFUNG
dieser einen Stufe kann Urteile nur von ihr weg bewegen — ein Papier, das
das Modell für „fehlt", „teilweise" oder „vorhanden" hielt, wird durch eine
engere Definition von `not_applicable` nicht plötzlich unanwendbar.

Deshalb werden die 12.020 anderen Urteile übernommen und nur die 60 neu
gefällt: $0,07 statt $14, Minuten statt anderthalb Tage.

**Was das kostet und wer es wissen muss.** Die übernommenen Zeilen tragen
Fassung 5, sind aber unter dem Prompt der Fassung 4 entstanden. Wer die
beiden Fassungen gegeneinander misst, misst deshalb NUR die 60 — und das ist
auch alles, was sich geändert hat. Ein Vergleich „wie gut urteilt Fassung 5
gegenüber 4" über den ganzen Bestand wäre sinnlos; dafür bräuchte es einen
vollen Lauf.

    python scripts/cities_fit_fassung5.py --trocken   # nur zählen
    python scripts/cities_fit_fassung5.py             # übernehmen
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.cities import default_paths  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

ALT, NEU = "4", "5"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trocken", action="store_true", help="nur zählen, nichts schreiben")
    p.add_argument("--db", help="Pfad zur cities.sqlite (Vorgabe: aus der Umgebung)")
    args = p.parse_args()

    pfad = args.db or default_paths()[0]
    with CitiesStore(pfad) as s:
        zeilen = s._conn.execute(
            "SELECT object_id, payload, source_hash, model, cost_usd FROM annotations "
            "WHERE object_kind='paper' AND annotator='fit' AND version=?", (ALT,)).fetchall()
        schon = {r["object_id"] for r in s._conn.execute(
            "SELECT object_id FROM annotations WHERE object_kind='paper' "
            "AND annotator='fit' AND version=?", (NEU,)).fetchall()}
        uebernehmen = [r for r in zeilen
                       if json.loads(r["payload"])["status"] != "not_applicable"
                       and r["object_id"] not in schon]
        offen = [r for r in zeilen
                 if json.loads(r["payload"])["status"] == "not_applicable"]
        print(f"Fassung {ALT}: {len(zeilen)} Urteile")
        print(f"  zu übernehmen:    {len(uebernehmen)}")
        print(f"  neu zu beurteilen: {len(offen)}  (die „nicht anwendbar\")")
        if args.trocken:
            return 0
        for r in uebernehmen:
            s.put_annotation("paper", r["object_id"], "fit", NEU,
                             json.loads(r["payload"]), r["source_hash"],
                             model=r["model"], cost_usd=0.0)
        print(f"{len(uebernehmen)} übernommen. Die {len(offen)} übrigen holt der "
              "nächste `fit`-Lauf — sie haben in Fassung 5 noch kein Urteil.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
