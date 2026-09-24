#!/usr/bin/env python3
"""Die Schulden der acht kreisfreien Städte aus der Regionaldatenbank einlesen.

Parser und Probe: ``council/regionalstatistik.py``. Der Lauf legt zwei
Aufträge beim Webservice an (Schulden 71327-Z-02, Einwohner 71327-Z-07),
holt die Ergebnisse, behält die acht Städte und speichert die Jahre, in
denen Oldenburgs Kernhaushalt zur eigenen Schuldenreihe passt.

Braucht ein Konto: ``REGIONALSTATISTIK_USER`` und ``REGIONALSTATISTIK_PASSWORD``
in der ``.env``. Fehlen sie (dev), endet der Lauf ohne Fehler und sagt es.
Höflich: 1,2 s Abstand, zwei Aufträge je Lauf. Kein Sprachmodell.

    python scripts/ingest_regionalstatistik.py --trocken
    python scripts/ingest_regionalstatistik.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import herkunft  # noqa: E402
from council import regionalstatistik as rs  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
STARTJAHR = 2019


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    args = ap.parse_args()

    user, password = os.environ.get("REGIONALSTATISTIK_USER"), os.environ.get("REGIONALSTATISTIK_PASSWORD")
    if not user or not password:
        print("Kein Konto für die Regionaldatenbank in der .env — übersprungen.")
        return 0
    ws = rs.Webservice(user, password)
    schulden = ws.tabelle(rs.TABELLE_SCHULDEN, startjahr=STARTJAHR)
    einwohner = ws.tabelle(rs.TABELLE_EINWOHNER, startjahr=STARTJAHR)
    lesung = rs.lies(schulden, einwohner)

    store = CouncilStore(args.db)
    try:
        eigene = rs.eigene_reihe(store.get_schulden(), store.get_schulden_plan())
        rs.pruefe(lesung, eigene)
        for h in lesung.hinweise:
            print(f"  nicht übernommen: {h}")
        namen = {key: name for key, name in rs.STAEDTE.values()}
        zeilen = [{"year": j, "key": key, "city": namen[key], "indicator": kennzahl, "value": wert,
                   "unit": "count" if kennzahl == "population" else "eur"}
                  for (key, j, kennzahl), wert in sorted(lesung.werte.items()) if j in lesung.bestanden]
        print(f"Jahre {sorted(lesung.bestanden)}, {len(zeilen)} Werte für {len(namen)} Städte")
        if args.trocken:
            return 0
        store.save_staedtevergleich(rs.SERIES, zeilen, herkunft.Herkunft(
            kind="regionalstatistik", probe=[rs.PROBE],
            url="https://www.regionalstatistik.de/genesis/online?operation=table&code=71327-Z-02",
            label="Regionaldatenbank, Tabellen 71327-Z-02 und 71327-Z-07",
            citation="Schulden der Kernhaushalte und der zu 100 % gehaltenen Einrichtungen "
                     "(31.12.), Einwohner am 30.06.",
            probe_result=f"Oldenburgs Kernhaushalt = eigene Schuldenreihe in "
                         f"{len(lesung.bestanden)} Jahren",
            as_of=f"Jahre {min(lesung.bestanden)}–{max(lesung.bestanden)}, abgerufen am "
                  f"{time.strftime('%d.%m.%Y')}" if lesung.bestanden else "Regionaldatenbank"))
        store.herkunft_aufraeumen()
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
