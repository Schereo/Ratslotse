#!/usr/bin/env python3
"""Kontonummern und Anschriften aus dem vorhandenen Bestand nehmen.

Die Backfills bereinigen seit dem 20.08.2026 beim Speichern
(`council/kontaktdaten.entfernen`). Was vorher hereinkam, steht aber noch da:
gemessen am Prod-Stand **81 IBAN, 42 BIC und 1.382 Anschriften** in 606
Anlagen. Dieses Skript holt das nach — einmal, dann ist es erledigt.

    python scripts/bereinige_kontaktdaten.py --trocken   # nur zählen
    python scripts/bereinige_kontaktdaten.py             # schreiben

DER EINGRIFF IST UNUMKEHRBAR. Was hier herausfällt, ist ohne erneutes Laden
des PDF weg. Deshalb fasst das Skript nur an, was nachweislich kein Parser
braucht: Kontonummern und vollständige Postanschriften. Telefon und E-Mail
bleiben im Bestand und werden erst am Suchindex maskiert.

WAS ES NICHT ANFASST: Straßennamen ohne Postleitzahl dahinter („Sanierung
Butjadinger Straße 61"). Der halbe Investitionsbereich besteht daraus, und
`kontaktdaten._ANSCHRIFT` erkennt eine Anschrift nur am Stück.

Nach dem Lauf müssen die Chunk-Vektoren neu gerechnet werden: Ihr `text_hash`
hängt am Text, und der hat sich geändert. `scripts/embed_anlagen.py` erledigt
das von allein, weil der Hash nicht mehr passt.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.kontaktdaten import entfernen, zaehlen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Wo überall Volltext liegt. Beide Tabellen tragen Kontaktdaten — die
#: Vorlagen deutlich weniger (6 Dokumente), aber „deutlich weniger" ist kein
#: Grund, sie stehen zu lassen.
TABELLEN = (("council_anlagen", "document_id"), ("council_vorlagen", "kvonr"))


def main() -> dict:
    ap = argparse.ArgumentParser(
        description="Kontonummern und Anschriften aus dem Bestand nehmen")
    ap.add_argument("--trocken", action="store_true",
                    help="nur zählen, nichts schreiben")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    gesamt = {"iban": 0, "bic": 0, "anschrift": 0}
    berichte: list[str] = []
    try:
        for tabelle, schluessel in TABELLEN:
            try:
                rows = store._conn.execute(  # noqa: SLF001
                    f"SELECT {schluessel} AS id, raw_text FROM {tabelle} "
                    f"WHERE raw_text IS NOT NULL AND raw_text != ''").fetchall()
            except Exception as fehler:  # noqa: BLE001 — Tabelle kann fehlen
                berichte.append(f"{tabelle}: {fehler}")
                continue

            betroffen, zeichen_vorher, zeichen_nachher = 0, 0, 0
            aenderungen: list[tuple[str, int]] = []
            for r in rows:
                alt = r["raw_text"]
                z = zaehlen(alt)
                # Nur die harten Arten zählen — Telefon und E-Mail bleiben ja.
                if not (z["iban"] or z["bic"] or z["anschrift"]):
                    continue
                neu = entfernen(alt)
                if neu == alt:
                    continue
                betroffen += 1
                zeichen_vorher += len(alt)
                zeichen_nachher += len(neu)
                for art in ("iban", "bic", "anschrift"):
                    gesamt[art] += z[art]
                aenderungen.append((neu, r["id"]))

            if aenderungen and not args.trocken:
                with store.transaktion():
                    store._conn.executemany(  # noqa: SLF001
                        f"UPDATE {tabelle} SET raw_text = ? WHERE {schluessel} = ?",
                        aenderungen)
            print(f"  {tabelle:20} {betroffen:>5} Dokumente · "
                  f"{zeichen_vorher - zeichen_nachher:>7,} Zeichen entfernt"
                  + ("  (Trockenlauf)" if args.trocken else ""), flush=True)

        print(f"\nEntfernt: {gesamt['iban']} IBAN, {gesamt['bic']} BIC, "
              f"{gesamt['anschrift']} Anschriften.", flush=True)
        if args.trocken:
            print("Trockenlauf — nichts geschrieben.", flush=True)
        else:
            print("Die Chunk-Vektoren rechnet embed_anlagen.py beim nächsten "
                  "Lauf neu: Ihr Hash passt nicht mehr.", flush=True)
        return {**gesamt, "trocken": int(args.trocken), "befund": berichte}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("bereinige_kontaktdaten", main)
