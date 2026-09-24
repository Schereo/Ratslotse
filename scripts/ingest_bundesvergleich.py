#!/usr/bin/env python3
"""Oldenburg im Bundesvergleich einlesen (Wegweiser Kommune).

Parser, Gruppe und Probe: ``council/bundesvergleich.py``. Der Lauf

1. holt die Regionenliste und daraus alle kreisfreien Städte,
2. holt ihre Einwohnerzahl (Export „demografische-entwicklung", zwölf
   Städte je Datei) und bildet die Vergleichsgruppe,
3. holt für die Gruppe den Export „finanzen",
4. prüft Oldenburgs Werte gegen die eigenen Reihen und speichert je Kennzahl
   und Jahr nur, was die Probe bestanden hat — für alle Städte der Gruppe,
   dazu ihre Einwohnerzahl.

Höflich: 1,5 s Abstand, rund 14 Abrufe je Lauf. Kein Sprachmodell.

    python scripts/ingest_bundesvergleich.py --trocken
    python scripts/ingest_bundesvergleich.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import bundesvergleich as bv  # noqa: E402
from council import herkunft  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
JE_DATEI = 12


class Abruf:
    def __init__(self, pause: float) -> None:
        self.pause, self._zuletzt = pause, 0.0

    def __call__(self, url: str) -> bytes:
        warten = self.pause - (time.monotonic() - self._zuletzt)
        if warten > 0:
            time.sleep(warten)
        anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Ratslotse; +https://ratslotse.de)"})
        try:
            with urllib.request.urlopen(anfrage, timeout=90) as antwort:
                return antwort.read()
        finally:
            self._zuletzt = time.monotonic()


def _in_dateien(abruf: Abruf, thema: str, slugs: list[str], namen: dict[str, str],
                koepfe: list[str]) -> dict:
    werte: dict = {}
    for i in range(0, len(slugs), JE_DATEI):
        teil = slugs[i:i + JE_DATEI]
        text = abruf(bv.export_url(thema, teil)).decode("latin-1")
        werte.update(bv.lies_export(text, teil, namen, koepfe))
    return werte


def _eigene(store: CouncilStore) -> dict[str, dict[int, float]]:
    steuern = store.get_steuereinnahmen()
    art = {"income_tax": "Einkommensteueranteil", "property_tax_b": "Grundsteuer A+B"}
    aus: dict[str, dict[int, float]] = {k: {z["year"]: z["amount"] for z in steuern if z["kind"] == v}
                                        for k, v in art.items()}
    aus["liquidity_year_end"] = {int(z["month"][:4]): z["amount"] for z in store.get_liquidity()
                                 if z["month"].endswith("-12") and z["amount"] is not None}
    return aus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und berichten")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    abruf = Abruf(args.pause)
    regionen = [r for r in json.loads(abruf(bv.REGIONEN_URL))
                if r.get("type") == "KREISFREIE_STADT"]
    namen = {r["friendlyUrl"]: r["name"] for r in regionen}
    demo = _in_dateien(abruf, "demografische-entwicklung", list(namen), namen, [bv.BEVOELKERUNG])
    juengstes = max(j for (_, _, j) in demo)
    gruppe = bv.gruppe(regionen, {s: w for (s, _, j), w in demo.items() if j == juengstes})
    if not any(g["slug"] == bv.OLDENBURG for g in gruppe):
        raise SystemExit("Oldenburg fehlt in der Vergleichsgruppe — Export anders gebaut?")
    print(f"{len(regionen)} kreisfreie Städte, Vergleichsgruppe {len(gruppe)} (Einwohner {juengstes})")

    slugs = [g["slug"] for g in gruppe]
    finanzen = _in_dateien(abruf, "finanzen", slugs, namen, list(bv.INDIKATOREN.values()))
    kennzahl_von = {v: k for k, v in bv.INDIKATOREN.items()}

    store = CouncilStore(args.db)
    try:
        ol = {(kennzahl_von[kopf], j): w for (s, kopf, j), w in finanzen.items() if s == bv.OLDENBURG}
        ol_ew = {j: w for (s, _, j), w in demo.items() if s == bv.OLDENBURG}
        probe = bv.pruefe_oldenburg(ol, ol_ew, _eigene(store))
        for h in probe.hinweise:
            print(f"  nicht übernommen: {h}")
        ags = {g["slug"]: g["ags"] for g in gruppe}
        zeilen = [{"year": j, "key": ags[s], "city": namen[s], "indicator": kennzahl_von[kopf],
                   "value": w, "unit": "eur_je_ew"}
                  for (s, kopf, j), w in finanzen.items()
                  if s in ags and (kennzahl_von[kopf], j) in probe.bestanden]
        jahre = {z["year"] for z in zeilen}
        zeilen += [{"year": j, "key": ags[s], "city": namen[s], "indicator": "population",
                    "value": w, "unit": "count"}
                   for (s, _, j), w in demo.items() if s in ags and j in jahre]
        for k in bv.INDIKATOREN:
            js = sorted(j for (kk, j) in probe.bestanden if kk == k)
            print(f"  {k}: Jahre {js}")
        print(f"{len(zeilen)} Werte für {len(gruppe)} Städte")
        if args.trocken:
            return 0
        store.save_staedtevergleich(bv.SERIES, zeilen, herkunft.Herkunft(
            kind="wegweiser", probe=[bv.PROBE], url=bv.DATEN_SEITE,
            label="Wegweiser Kommune, Themen Finanzen und Demografische Entwicklung",
            citation=f"Export je zwölf Kommunen, {bv.JAHRE}; Vergleichsgruppe: kreisfreie Städte "
                     f"mit {bv.EW_VON:,} bis {bv.EW_BIS:,} Einwohner*innen und alle Niedersachsens"
                     .replace(",", "."),
            probe_result=f"Oldenburg gegen die eigenen Reihen: {len(probe.bestanden)} Werte bestanden, "
                         f"{len(probe.hinweise)} nicht übernommen",
            as_of=f"Jahre {bv.JAHRE}, abgerufen am {time.strftime('%d.%m.%Y')}"))
        store.herkunft_aufraeumen()
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
