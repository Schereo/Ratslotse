#!/usr/bin/env python3
"""Die dritte Schuldenzahl einlesen — integrierte Schulden des „Konzerns Stadt".

Was Oldenburg mit allen Betrieben und Beteiligungen anteilig schuldet:
740,3 Mio. € zum 31.12.2024, gegen 294,9 Mio. € der Jahrbuch-Reihe und
43,7 Mio. € reiner Kernhaushalt. Warum drei Zahlen alle stimmen und was man aus
der dritten NICHT folgern darf, steht im Kopf von
``council/integrierte_schulden.py`` — dort und nicht hier, weil die Sätze mit
den Zahlen bis in die Oberfläche mitreisen.

Warum von Hand und nicht per Cron
---------------------------------
Wie beim Jahrbuch: Die Datei erscheint einmal jährlich unter wechselnder
Adresse — der Ordner trägt Jahr und Monat der Veröffentlichung
(``/sites/default/files/2025-12/…``), der Dateiname manchmal ein angehängtes
``_0``. Deshalb sucht dieser Lauf den Link auf der Übersichtsseite, statt eine
Adresse hochzuzählen. Der Web-Dienst lädt zu keinem Zeitpunkt etwas nach.

Die Probe ist das Nadelöhr
--------------------------
Ohne bestandene Kernhaushalts-Probe wird **nichts** gespeichert: Der
Tabellenband führt die Schulden des Kernhaushalts getrennt aus, und dieser Wert
muss der Geldschulden-Position unserer eigenen Bilanz entsprechen (2024:
43.690.972 € gegen 43.690.971,71 € — 29 Cent Rundung). Fehlt die Bilanz des
Stichtags im Bestand, gibt es kein Gegenstück und damit keine Probe; dann
bricht der Lauf ab, statt eine ungeprüfte Zahl hereinzulassen.

Aufruf::

    python scripts/ingest_integrierte_schulden.py                 # Link von der Übersicht
    python scripts/ingest_integrierte_schulden.py --datei x.xlsx  # lokale Datei
    python scripts/ingest_integrierte_schulden.py --trockenlauf   # nur zeigen
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import herkunft as herkunft_mod  # noqa: E402
from council import integrierte_schulden as isch  # noqa: E402
from council import staedtevergleich as sv  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Wie sich der Lauf beim Statistikportal meldet.
KOPFZEILEN = {"User-Agent": "Ratslotse/1.0 (+https://ratslotse.de)"}


def link_finden() -> str:
    """Die Adresse des aktuellen Tabellenbands von der Übersichtsseite."""
    anfrage = urllib.request.Request(isch.UEBERSICHT_URL, headers=KOPFZEILEN)
    with urllib.request.urlopen(anfrage, timeout=60) as answer:  # noqa: S310
        page = answer.read().decode("utf-8", "replace")
    treffer = isch.LINK_MUSTER.search(page)
    if not treffer:
        raise SystemExit(
            f"Kein xlsx-Link auf {isch.UEBERSICHT_URL} gefunden. Die Seite hat "
            f"vermutlich ihr Layout geändert — Adresse von Hand über --datei.")
    return urllib.parse.urljoin(isch.UEBERSICHT_URL, treffer.group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description="Integrierte Schulden einlesen")
    ap.add_argument("--datei", default=None, help="lokale xlsx statt Download")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--trockenlauf", action="store_true")
    args = ap.parse_args()

    source_url = None
    if args.datei:
        pfad = args.datei
    else:
        source_url = link_finden()
        print(f"Tabellenband: {source_url}")
        anfrage = urllib.request.Request(source_url, headers=KOPFZEILEN)
        with urllib.request.urlopen(anfrage, timeout=180) as answer:  # noqa: S310
            roh = answer.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.write(roh)
        tmp.close()
        pfad = tmp.name
        print(f"  {len(roh)/1e6:.1f} MB geladen")

    zeilen = sv.blatt_lesen(pfad, isch.BLATT)
    gefunden = isch.lies_gemeinde(zeilen)
    if not gefunden:
        raise SystemExit(f"Regionalschlüssel {isch.ARS_OLDENBURG} steht nicht "
                         f"im Blatt {isch.BLATT}.")

    anteil = isch.anteil_unter_50(gefunden)
    print(f"{gefunden['year']}: {gefunden['total']/1e6:.2f} Mio. € "
          f"({gefunden['per_capita']:,.0f} € je Einwohner*in)")
    print(f"  davon aus Beteiligungen unter 50 %: {anteil*100:.1f} %")

    store = CouncilStore(Path(args.db))
    try:
        posten = [p for p in store.get_bilanz_posten("financial_liabilities")
                  if p["year"] == gefunden["year"]]
        ok, warum = isch.kernprobe(gefunden, posten[0]["value"] if posten else None)
        print(f"  Kernhaushalts-Probe: {'bestanden' if ok else 'GERISSEN'} — {warum}")
        if not ok:
            raise SystemExit("Ohne bestandene Probe wird nichts gespeichert.")
        if args.trockenlauf:
            print("  Trockenlauf — nichts geschrieben.")
            return 0
        store.save_integrierte_schulden(
            {**gefunden, "probes": [isch.PROBE_KERNHAUSHALT]},
            herkunft_mod.Herkunft(
                kind="lsn", probe=[isch.PROBE_KERNHAUSHALT],
                label="Integrierte Schulden der Gemeinden und Gemeindeverbände",
                url=source_url or isch.UEBERSICHT_URL,
                citation=f"Tabelle 2, Blatt {isch.BLATT}, "
                           f"Regionalschlüssel {isch.ARS_OLDENBURG}",
                probe_result=warum,
                as_of=f"31.12.{gefunden['year']}"))
        print(f"  gespeichert: Stichtag {gefunden['year']}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
