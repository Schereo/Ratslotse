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

**Der Quell-Hash muss mitwandern, sonst nützt die Übernahme nichts.**
``fit.source_hash`` nimmt die Fassung UND die ersten 200 Zeichen des Prompts
mit hinein — eine übernommene Zeile mit dem Hash aus Fassung 4 sieht für
``annotations_missing`` deshalb aus wie „Grundlage geändert, neu beurteilen".
Der erste Anlauf am 20.09.2026 hat genau das getan: Statt der 60 fing der
Lauf an, alle 12.307 neu zu fällen, und hatte 1.766 davon abgearbeitet
(1,21 $), bevor es auffiel.

Deshalb rechnet dieses Skript den Hash so aus, wie Fassung 5 ihn ausrechnen
würde — mit denselben Belegen, demselben Cluster und derselben
Aufwandsklasse. Das kostet die Suchbegriffe (rund 0,03 $ je 1.000 Vorlagen),
aber keinen einzigen Urteils-Aufruf.

**Was das kostet und wer es wissen muss.** Die übernommenen Zeilen tragen
danach Fassung 5 und einen Fassung-5-Hash, sind aber unter dem Prompt der
Fassung 4 entstanden. Das ist eine bewusste Abkürzung, keine Eigenschaft der
Daten: Wer die beiden Fassungen gegeneinander misst, misst NUR die Zeilen mit
``cost_usd > 0``. Ein Vergleich „wie gut urteilt Fassung 5 gegenüber 4" über
den ganzen Bestand wäre sinnlos; dafür bräuchte es einen vollen Lauf.

    python scripts/cities_fit_fassung5.py --trocken   # nur zählen
    python scripts/cities_fit_fassung5.py             # übernehmen
    python scripts/cities_fit_fassung5.py --hashes    # nur Hashes nachziehen
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


def _hashes_fuer_fassung5(s: CitiesStore) -> dict[str, str]:
    """Der Quell-Hash, wie Fassung 5 ihn ausrechnet — je Kandidat.

    Dieselben Schritte wie am Anfang von ``fit.run``, nur ohne ein einziges
    Urteil: Belege sammeln, Cluster-Zeile bilden, Hash rechnen. Teuer ist
    daran nur die Suchbegriff-Abfrage (rund 0,03 $ je 1.000 Vorlagen).
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    from council.cities import evidence as beleg_modul
    from council.cities import fit
    from council.cities.annotators import get as get_annotator
    from council.cities.index import EMBED_MODEL
    from council.store import CouncilStore

    ann = get_annotator("fit")
    rats = CouncilStore(os.environ.get("COUNCIL_DB", "data/council.sqlite"))
    einordnung = s.annotations_for("classify", "2")
    aufwand = s.annotations_for("effort", "1")
    kandidaten = fit.candidates_for(s)
    matrix = s.chunk_matrix(EMBED_MODEL, "oldenburg")
    papier_matrix = s.paper_matrix(EMBED_MODEL, "oldenburg")
    print(f"  Belege für {len(kandidaten)} Vorlagen sammeln "
          f"({len(matrix[0])} Abschnitte, {len(papier_matrix[0])} Vorlagen) …")
    hashes: dict[str, str] = {}
    for start in range(0, len(kandidaten), fit.TERM_BLOCK):
        block = kandidaten[start:start + fit.TERM_BLOCK]
        with ThreadPoolExecutor(max_workers=fit.TERM_WORKERS) as pool:
            begriffe_je = list(pool.map(
                lambda p: beleg_modul.search_terms(einordnung.get(p["id"]) or {}, p),
                block))
        for p, begriffe in zip(block, begriffe_je):
            klasse = einordnung.get(p["id"]) or {}
            belege = beleg_modul.evidence_for(s, rats, p, klasse, EMBED_MODEL,
                                              chunk_matrix=matrix, begriffe=begriffe,
                                              paper_matrix=papier_matrix)
            hashes[p["id"]] = fit.source_hash(
                p, klasse, belege, ann,
                beleg_modul.cluster_zeile(s, p, EMBED_MODEL), aufwand.get(p["id"]))
        if (start // fit.TERM_BLOCK) % 10 == 0:
            print(f"    {min(start + fit.TERM_BLOCK, len(kandidaten))}/{len(kandidaten)}",
                  flush=True)
    return hashes


def hashes_nachziehen(s: CitiesStore) -> int:
    """Übernommene Zeilen auf den Hash von Fassung 5 heben.

    Nur die ÜBERNOMMENEN (``cost_usd = 0``): Was der Lauf selbst gefällt hat,
    trägt seinen richtigen Hash schon.
    """
    hashes = _hashes_fuer_fassung5(s)
    zeilen = s._conn.execute(
        "SELECT object_id, source_hash FROM annotations WHERE object_kind='paper' "
        "AND annotator='fit' AND version=? AND COALESCE(cost_usd, 0) = 0", (NEU,)).fetchall()
    zu_tun = [(hashes[r["object_id"]], r["object_id"]) for r in zeilen
              if r["object_id"] in hashes and hashes[r["object_id"]] != r["source_hash"]]
    with s.transaction():
        s._conn.executemany(
            "UPDATE annotations SET source_hash=? WHERE object_kind='paper' "
            "AND annotator='fit' AND version=? AND object_id=?",
            [(h, NEU, pid) for h, pid in zu_tun])
    return len(zu_tun)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trocken", action="store_true", help="nur zählen, nichts schreiben")
    p.add_argument("--hashes", action="store_true",
                   help="nur die Quell-Hashes der übernommenen Zeilen nachziehen")
    p.add_argument("--db", help="Pfad zur cities.sqlite (Vorgabe: aus der Umgebung)")
    args = p.parse_args()

    pfad = args.db or default_paths()[0]
    with CitiesStore(pfad) as s:
        if args.hashes:
            n = hashes_nachziehen(s)
            print(f"{n} übernommene Zeilen auf den Hash von Fassung {NEU} gehoben. "
                  "Sie gelten jetzt als aktuell und werden nicht neu beurteilt.")
            return 0
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
