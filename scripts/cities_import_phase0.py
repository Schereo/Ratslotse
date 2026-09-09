#!/usr/bin/env python3
"""Einmalige Übernahme des Probelauf-Bestands in den Städte-Speicher.

Der Probelauf vom 07.09.2026 hat 2.967 Vorlagen aus fünf Städten geholt, mit
Volltext und 22.494 Tagesordnungspunkten — eine Stunde Netzverkehr, die
niemand wiederholen muss. Die Datei liegt unter
``~/.cache/ratslotse/phase0/peers.sqlite`` (s. ``docs/phase0-andere-staedte.md``).

Sie wandert hier in die **Rohablage**, nicht direkt in die normalisierte
Schicht: So läuft ``normalize`` darüber wie über eine echte Ernte, und die
Regel „Schicht 1 entsteht nur aus Schicht 0" bleibt ohne Ausnahme.

Die PDF-Bytes hat der Probelauf nicht behalten — nur den extrahierten Text.
Der wandert als Extraktor ``phase0`` mit; der erste Wochenlauf holt die
Dateien nach und ``pypdf/1`` legt sich daneben.

```bash
python scripts/cities_import_phase0.py --trocken
python scripts/cities_import_phase0.py --run
```
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.cities import default_paths  # noqa: E402
from council.cities import pipeline  # noqa: E402
from council.cities.pipeline import raw_path_for  # noqa: E402
from council.cities.registry import BODIES  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

QUELLE = Path.home() / ".cache" / "ratslotse" / "phase0" / "peers.sqlite"
EXTRACTOR = "phase0"
VERSION = "1"


def sitzungen_als_rohobjekte(quelle: sqlite3.Connection, stadt: str) -> list[dict]:
    """Aus den Tagesordnungspunkten des Probelaufs Sitzungs-Objekte bauen.

    Der Probelauf hat je Punkt eine Zeile gespeichert (Sitzung, Datum, Gremium,
    Nummer, Titel, Ergebnis) — genug, um daraus die OParl-Form
    zurückzugewinnen, die ``normalize`` erwartet.
    """
    nach_sitzung: dict[str, dict] = {}
    for zeile in quelle.execute(
            "SELECT meeting, mdate, org, number, name, result FROM agenda WHERE city=?", (stadt,)):
        sitzung = nach_sitzung.setdefault(zeile["meeting"], {
            "id": zeile["meeting"],
            "type": "https://schema.oparl.org/1.1/Meeting",
            "name": zeile["org"] or "",
            "start": zeile["mdate"],
            "organization": [zeile["org"]] if zeile["org"] and zeile["org"] != "None" else [],
            "agendaItem": [],
        })
        sitzung["agendaItem"].append({
            "id": f"{zeile['meeting']}#top-{zeile['number']}",
            "type": "https://schema.oparl.org/1.1/AgendaItem",
            "number": zeile["number"],
            "name": zeile["name"] or "",
            "public": True,
            "result": zeile["result"],
        })
    return list(nach_sitzung.values())


def texte_verknuepfen(main: CitiesStore, raw_dir: Path, stadt: str) -> int:
    """Die Volltexte des Probelaufs an die Dateien hängen.

    Im Probelauf hing der Text am Papier; im Speicher hängt er an der Datei,
    aus der er stammt. Diese Zuordnung entsteht erst nach dem Normalisieren —
    deshalb ein eigener Schritt statt einer Spalte in der Rohablage.
    """
    raw = CitiesStore(raw_path_for(raw_dir, stadt))
    try:
        texte = raw.annotations_for("phase0_text", VERSION)
    finally:
        raw.close()
    if not texte:
        return 0
    n = 0
    with main.transaction():
        for paper_id, nutzlast in texte.items():
            text = (nutzlast or {}).get("text")
            if not text:
                continue
            dateien = [f for f in main.files_for_paper(paper_id) if f["role"] == "main"]
            if not dateien:
                continue
            main.put_text(dateien[0]["id"], EXTRACTOR, VERSION, text, None,
                          "ok" if len(text) > 200 else "thin")
            n += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quelle", type=Path, default=QUELLE)
    p.add_argument("--run", action="store_true", help="wirklich schreiben")
    p.add_argument("--trocken", action="store_true", help="nur zählen (Vorgabe)")
    a = p.parse_args()

    if not a.quelle.exists():
        print(f"Nicht gefunden: {a.quelle}\n"
              f"Der Probelauf-Bestand ist nicht Teil des Repos; ohne ihn ernte "
              f"mit scripts/cities_backfill.py --run.")
        return 1

    quelle = sqlite3.connect(f"file:{a.quelle}?mode=ro", uri=True)
    quelle.row_factory = sqlite3.Row
    staedte = [z[0] for z in quelle.execute("SELECT DISTINCT city FROM papers ORDER BY 1")]
    _db, _files, raw_dir = default_paths()

    print(f"Quelle: {a.quelle}")
    print(f"{'Stadt':16} {'Papiere':>8} {'mit Text':>9} {'Sitzungen':>10} {'TOPs':>7}")
    print("-" * 55)
    gesamt = {"papers": 0, "texts": 0, "meetings": 0, "agenda": 0}
    for stadt in staedte:
        papiere = quelle.execute(
            "SELECT id, raw, text, status FROM papers WHERE city=? AND raw IS NOT NULL",
            (stadt,)).fetchall()
        sitzungen = sitzungen_als_rohobjekte(quelle, stadt)
        tops = sum(len(s["agendaItem"]) for s in sitzungen)
        mit_text = sum(1 for z in papiere if z["text"])
        print(f"{stadt:16} {len(papiere):8} {mit_text:9} {len(sitzungen):10} {tops:7}")
        gesamt["papers"] += len(papiere); gesamt["texts"] += mit_text
        gesamt["meetings"] += len(sitzungen); gesamt["agenda"] += tops

        if not a.run:
            continue

        store = CitiesStore(raw_path_for(raw_dir, stadt))
        try:
            with store.transaction():
                for zeile in papiere:
                    roh = json.loads(zeile["raw"])
                    store.put_raw_object(stadt, "paper", roh.get("id") or zeile["id"], roh)
                for sitzung in sitzungen:
                    store.put_raw_object(stadt, "meeting", sitzung["id"], sitzung)
            # Texte hängen an der Datei, nicht am Papier — die Datei-Kennung
            # entsteht erst beim Normalisieren. Deshalb hier über das Papier
            # merken und nach dem ersten `normalize` zuordnen.
            with store.transaction():
                for zeile in papiere:
                    if zeile["text"]:
                        store.put_annotation(
                            "paper", zeile["id"], "phase0_text", VERSION,
                            {"text": zeile["text"]},
                            source_hash="phase0", model=None, cost_usd=None)
        finally:
            store.close()

    print("-" * 55)
    print(f"{'Summe':16} {gesamt['papers']:8} {gesamt['texts']:9} "
          f"{gesamt['meetings']:10} {gesamt['agenda']:7}")
    if not a.run:
        print("\nTrockenlauf. --run schreibt in die Rohablage unter", raw_dir)
        return 0

    # Direkt weiter: normalisieren und die Texte zuordnen. Der Import ist ein
    # Einmal-Werkzeug; ihn in drei Aufrufe zu zerlegen brächte niemandem etwas.
    db, _files, _raw = default_paths()
    main_store = CitiesStore(db)
    try:
        print()
        for stadt in staedte:
            spec = BODIES.get(stadt)
            if not spec:
                print(f"  {stadt}: nicht in der Registry — übersprungen")
                continue
            zahlen = pipeline.normalize(spec, raw_dir, main_store)
            n_texte = texte_verknuepfen(main_store, raw_dir, stadt)
            print(f"  {stadt}: {zahlen['papers']} Papiere, {zahlen['agenda_items']} TOPs, "
                  f"{n_texte} Texte")
        print()
        print(f"{'Stadt':16} {'Papiere':>8} {'mit Text':>9} {'TOPs':>7} {'mit Ergebnis':>13}")
        print("-" * 58)
        for z in main_store.stats():
            print(f"{z['name'][:15]:16} {z['papers']:8} {z['papers_with_text']:9} "
                  f"{z['agenda_items']:7} {z['agenda_items_with_outcome']:13}")
    finally:
        main_store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
