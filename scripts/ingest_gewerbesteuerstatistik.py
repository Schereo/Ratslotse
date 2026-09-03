#!/usr/bin/env python3
"""Die Gewerbesteuerstatistik des LSN einlesen — einen Jahrgang oder mehrere.

Quelle ist der Statistische Bericht **L IV 13** des Landesamts für Statistik
Niedersachsen, ohne Anmeldung als xlsx abrufbar. Gelesen werden die Blätter
6.1 (kreisfreie Städte) und 6.2 (Gemeinden); was dabei herauskommt und warum
es nicht neben die Aufkommenskurve gehört, steht im Kopf von
``council/trade_tax_statistics.py``.

Warum von Hand und nicht per Cron
---------------------------------
Dieselbe Überlegung wie beim Städtevergleich, nur noch deutlicher: Diese
Statistik erscheint **einmal jährlich** und dann für ein Erhebungsjahr, das
rund **fünf Jahre** zurückliegt (2019 → August 2024, 2020 → September 2025,
2021 → März 2026). Ein täglicher Lauf holte 364-mal dieselbe Datei. Dazu
tragen die Download-Adressen des LSN undurchsichtige Nummern
(``/download/227059``), die nicht hochzuzählen sind — sie stehen auf der
Übersichtsseite und werden hier beim jährlichen Lauf mitgegeben.

Aufruf::

    # Alle bisher als xlsx veröffentlichten Jahrgänge auf einmal
    python scripts/ingest_gewerbesteuerstatistik.py \\
        https://www.statistik.niedersachsen.de/download/186648 \\
        https://www.statistik.niedersachsen.de/download/199013 \\
        https://www.statistik.niedersachsen.de/download/209710 \\
        https://www.statistik.niedersachsen.de/download/221560 \\
        https://www.statistik.niedersachsen.de/download/227059

    # oder eine bereits geladene Datei
    python scripts/ingest_gewerbesteuerstatistik.py bericht2021.xlsx

Die Übersichtsseite mit den jeweils neuen Nummern:
``statistik.niedersachsen.de/themen/gewerbesteuer-niedersachsen/
gewerbesteuer-in-niedersachsen-statistische-n_reports-179300.html``

Ältere Jahrgänge als 2017 gibt es nur als PDF (geprüft für 2013: die
Gemeindetabelle ist da, aber im PDF-Satz). Sie brauchten einen zweiten Parser
und stehen deshalb nicht im Bestand.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import trade_tax_statistics as gs  # noqa: E402
from council import herkunft as h  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Die Adressen, aus denen der Bestand vom 24.08.2026 stammt. Sie stehen hier
#: als Beleg, welche Ausgabe eingelesen wurde — **nicht** als Vorgabe für den
#: nächsten Jahrgang: Die Nummer ändert sich jedes Jahr und lässt sich nicht
#: hochzählen.
QUELLEN_STAND = {
    2017: "https://www.statistik.niedersachsen.de/download/186648",
    2018: "https://www.statistik.niedersachsen.de/download/199013",
    2019: "https://www.statistik.niedersachsen.de/download/209710",
    2020: "https://www.statistik.niedersachsen.de/download/221560",
    2021: "https://www.statistik.niedersachsen.de/download/227059",
}


def _holen(ort: str, ablage: Path) -> tuple[Path, str | None]:
    """Pfad oder Adresse → lokale Datei und (falls geladen) die Quell-Adresse.

    Der Content-Type des LSN ist irreführend (``application/vnd.ms-excel`` bei
    echten xlsx) — er wird deshalb nicht ausgewertet. Ob die Datei taugt,
    entscheidet der Parser.
    """
    if not ort.lower().startswith(("http://", "https://")):
        return Path(ort), None
    import requests

    answer = requests.get(ort, timeout=180)
    answer.raise_for_status()
    ziel = ablage / (ort.rstrip("/").rsplit("/", 1)[-1] + ".xlsx")
    ziel.write_bytes(answer.content)
    print(f"  geladen: {ort} ({len(answer.content):,} Bytes)".replace(",", "."))
    return ziel, ort


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Gewerbesteuerstatistik (LSN, L IV 13) einlesen")
    ap.add_argument("n_reports", nargs="+",
                    help="Statistische Berichte als Datei oder Adresse")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    # Die Hebesatz-Treppe aus Tabelle 1105 — einmal geholt, für die Probe
    # gegen die Angabe des Landesamts. Ist sie leer (frische Datenbank, in der
    # `ingest_steuertabellen.py` noch nicht lief), läuft diese eine Probe
    # nicht; die beiden anderen tragen den Jahrgang trotzdem.
    treppe = store.get_hebesaetze()
    if not treppe:
        print("HINWEIS: keine Hebesätze im Bestand (Tabelle 1105) — die "
              "Gegenprobe gegen das Jahrbuch entfällt für diesen Lauf.")
    geschrieben: dict[int, int] = {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ablage = Path(tmp)
            for ort in args.n_reports:
                pfad, url = _holen(ort, ablage)
                budget_year = gs.lies_bericht(str(pfad))
                print(f"Erhebungsjahr {budget_year.year} "
                      f"({budget_year.as_of or 'ohne Erscheinungsvermerk'}):")

                # --- Probe 1: die Rechnung in der Zeile ---
                zeilen, verworfen = gs.zeilen(budget_year)
                for v in verworfen:
                    print(f"    ÜBERSPRUNGEN {v['stadt']}: {v['reason']} — "
                          f"{v['result']}")
                if not zeilen:
                    print("  ABBRUCH für diesen Jahrgang: keine einzige Stadt "
                          "hat ihre Summenprobe bestanden.")
                    continue

                # --- Probe 2: dasselbe im zweiten Blatt ---
                blatt = gs.probe_blaetter(budget_year)
                print(f"  Blattprobe 6.1 gegen 6.2: {blatt['result']}")
                if not blatt["ok"]:
                    for a in blatt["abweichungen"][:8]:
                        print(f"    ABWEICHUNG {a['stadt']}: {a['reason']}")
                    print("  ABBRUCH für diesen Jahrgang: Die beiden Blätter "
                          "widersprechen sich. Lieber keine Zahlen als falsche.")
                    continue

                # --- Probe 3: der Hebesatz gegen das Jahrbuch ---
                probes = ["trade_tax_sum_check", "trade_tax_sheet_check"]
                ergebnisse = [f"{len(zeilen)} Städte nachgerechnet",
                              blatt["result"]]
                erwartet = gs.hebesatz_im_jahr(treppe, budget_year.year)
                hebe = gs.probe_hebesatz(budget_year, gs.OLDENBURG, erwartet)
                print(f"  Hebesatzprobe: {hebe['result']}")
                if hebe["ok"] is False:
                    print("  ABBRUCH für diesen Jahrgang: Landesamt und "
                          "Jahrbuch nennen verschiedene Hebesätze.")
                    continue
                if hebe["ok"]:
                    probes.append("trade_tax_assessment_rate_check")
                    ergebnisse.append(hebe["result"])

                geschrieben[budget_year.year] = store.save_gewerbesteuerstatistik(
                    zeilen,
                    h.Herkunft(
                        kind="lsn", probe=probes,
                        label=f"Gewerbesteuerstatistik {budget_year.year} "
                              f"(Statistischer Bericht L IV 13)",
                        url=url or QUELLEN_STAND.get(budget_year.year),
                        citation="Blatt 6.1 — Festsetzung und Zerlegung nach "
                                   "Sitz des Betriebes/der Betriebsstätte, "
                                   "kreisfreie Städte; Blatt 6.2 — dieselben "
                                   "Zahlen je Gemeinde, mit dem Hebesatz",
                        probe_result=" · ".join(ergebnisse),
                        as_of=budget_year.as_of))
                print(f"  gespeichert: {geschrieben[budget_year.year]} Städte")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t == "council_trade_tax_statistics"}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}")
    finally:
        store.close()

    print(f"Fertig: {dict(sorted(geschrieben.items()))}")
    return 0 if geschrieben else 1


if __name__ == "__main__":
    raise SystemExit(main())
