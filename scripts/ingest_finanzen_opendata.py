#!/usr/bin/env python3
"""Finanz-Datensätze des Open-Data-Portals der Stadt einlesen.

Zwei CSVs von opendata.oldenburg.de (Lizenz dl-de/by-2-0), beide jährlich
fortgeschrieben — Grundlage des Haushalts-Bereichs:

- **Steuereinnahmen seit 1998** (Ist, je Steuerart) → ``council_steuern``.
  Für Steuer-Steckbriefe und Zeitreihen: Grundsteuer A+B, Gewerbesteuer
  (nach Umlage), Einkommensteuer-/Umsatzsteueranteil, Vergnügungssteuer …
- **Steuerkraftmesszahlen + Schlüsselzuweisungen seit 1992** →
  ``council_steuerkraft``. Zeigt die NFAG-Mechanik (mehr eigene Steuerkraft
  → weniger Landeszuweisungen) — Pflichtkontext für jede Hebesatz-Simulation.
- **Einwohnerzahlen seit 2010** → ``council_einwohner``. Bezugsgröße für
  Pro-Kopf-Einordnungen. Aus demselben CSV NICHT übernommen: die
  Aufwendungs-Spalte — sie weicht vom beschlossenen Plan ab, ohne als Ist
  oder Nachtrag gekennzeichnet zu sein.

Idempotent (INSERT OR REPLACE); einmal jährlich reicht, es gibt keinen Cron::

    python scripts/ingest_finanzen_opendata.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import haushalt, herkunft  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}


def _spanne(rows: list[dict]) -> str:
    """„1998–2025" aus den Jahrgängen einer Datensatz-Lieferung."""
    jahre = sorted({r["jahr"] for r in rows})
    return f"{jahre[0]}–{jahre[-1]}" if jahre else ""


def main() -> int:
    store = CouncilStore(COUNCIL_DB)
    try:
        r = requests.get(haushalt.STEUERN_CSV_URL, headers=_UA, timeout=120)
        r.raise_for_status()
        steuern = haushalt.parse_steuereinnahmen(r.text)
        if not steuern:
            print("Steuereinnahmen-CSV nicht lesbar — nichts gespeichert.", file=sys.stderr)
            return 1
        # Diese drei Datensätze tragen keine Rechenprobe: eine Zeile je Jahr,
        # keine Summe, gegen die sich etwas prüfen ließe. Das ausdrücklich zu
        # sagen ist ehrlicher, als eine Probe zu behaupten — und es steht auf
        # der Seite dann auch so.
        n = store.save_steuereinnahmen(steuern, herkunft.Herkunft(
            art="opendata", probe=herkunft.UNGEPRUEFT,
            url=haushalt.STEUERN_CSV_URL,
            label="Steuereinnahmen der Stadt Oldenburg",
            fundstelle="Datensatz 1104 — eine Zeile je Haushaltsjahr, "
                       "Spalten je Steuerart (Ist, Gewerbesteuer nach Umlage)",
            stand=_spanne(steuern)))
        print(f"Steuereinnahmen: {n} Zeilen ({_spanne(steuern)}).")

        r = requests.get(haushalt.STEUERKRAFT_CSV_URL, headers=_UA, timeout=120)
        r.raise_for_status()
        kraft = haushalt.parse_steuerkraft(r.text)
        if not kraft:
            print("Steuerkraft-CSV nicht lesbar — nichts gespeichert.", file=sys.stderr)
            return 1
        n = store.save_steuerkraft(kraft, herkunft.Herkunft(
            art="opendata", probe=herkunft.UNGEPRUEFT,
            url=haushalt.STEUERKRAFT_CSV_URL,
            label="Steuerkraftmesszahlen und Schlüsselzuweisungen",
            fundstelle="Datensatz 1106 — je Ausgleichsjahr Steuerkraftmesszahl "
                       "und Schlüsselzuweisungen (Anordnungssoll), absolut und "
                       "je Einwohner",
            stand=_spanne(kraft)))
        print(f"Steuerkraft/Schlüsselzuweisungen: {n} Jahre ({_spanne(kraft)}).")

        r = requests.get(haushalt.EINWOHNER_CSV_URL, headers=_UA, timeout=120)
        r.raise_for_status()
        ew = haushalt.parse_einwohner(r.text)
        if ew:
            n = store.save_einwohner(ew, herkunft.Herkunft(
                art="opendata", probe=herkunft.UNGEPRUEFT,
                url=haushalt.EINWOHNER_CSV_URL,
                label="Einwohnerzahlen je Haushaltsjahr",
                fundstelle="Datensatz 1102, Einwohner-Spalte (Stichtag 31.12. "
                           "des Vorjahres) — die Aufwendungs-Spalten desselben "
                           "Datensatzes bleiben bewusst ungenutzt",
                stand=_spanne(ew)))
            print(f"Einwohnerzahlen: {n} Jahre ({_spanne(ew)}).")
        else:
            print("Einwohner-CSV nicht lesbar — übersprungen.", file=sys.stderr)

        store.herkunft_aufraeumen()
        luecken = store.herkunft_luecken()
        if luecken:
            print(f"Ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
