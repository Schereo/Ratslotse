#!/usr/bin/env python3
"""Finanz-Datensätze des Open-Data-Portals der Stadt einlesen.

Zwei CSVs von opendata.oldenburg.de (Lizenz dl-de/by-2-0), beide jährlich
fortgeschrieben — Grundlage des Haushalts-Bereichs:

- **Steuereinnahmen seit 1998** (Ist, je Steuerart) → ``council_steuern``.
  Für Steuer-Steckbriefe und Zeitreihen: Grundsteuer A+B, Gewerbesteuer
  (nach Umlage), Einkommensteuer-/Umsatzsteueranteil, Vergnügungssteuer …
- **Steuerkraftmesszahlen + Schlüsselzuweisungen seit 1993** →
  ``council_steuerkraft``. Zeigt die NFAG-Mechanik (mehr eigene Steuerkraft
  → weniger Landeszuweisungen) — Pflichtkontext für jede Hebesatz-Simulation.
  Einzige Stelle im Bereich, an der wir eine Quelle **korrigieren** statt sie
  nur zu übernehmen: Der Datensatz beschriftet seine Jahrgänge um ein Jahr zu
  früh, ``haushalt.parse_steuerkraft`` rückt sie aufs Ausgleichsjahr. Warum
  wir uns das trauen, steht in ``council/haushalt._STEUERKRAFT_VERSATZ``.
- **Einwohnerzahlen seit 2010** → ``council_einwohner``. Bezugsgröße für
  Pro-Kopf-Einordnungen. Die Aufwendungs-Spalte derselben Datei holt ein
  eigener Lauf (``scripts/ingest_ausgabenreihe.py``): Sie braucht das
  Jahrbuch-PDF und die ältere CSV desselben Datensatzes dazu, weil erst die
  zweite Quelle die Proben liefert, an denen der Wert hängt.
- **Investitionen des Finanzhaushalts 2022–2025** → ``council_investitionen``.
  Was die Stadt bauen und kaufen will, je Teilhaushalt. Die einzige dieser
  Dateien mit einer **Rechenprobe im Dokument selbst**: Die Teilhaushalte
  ergeben die Summenzeile, die dieselbe Datei ausweist. Was sie reißt, wird
  verworfen (``council/investitionen.py``).

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

from council import finanzquellen, haushalt, herkunft, investitionen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}


def _spanne(rows: list[dict]) -> str:
    """„1998–2025" aus den Jahrgängen einer Datensatz-Lieferung."""
    jahre = sorted({r["year"] for r in rows})
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
            fundstelle="Datensatz 1106 — je Jahr Steuerkraftmesszahl und "
                       "Schlüsselzuweisungen (Anordnungssoll). Die Jahreszahl "
                       "ist von uns um ein Jahr nach vorn gerückt: Der "
                       "Datensatz beschriftet seine Zeilen um ein Jahr zu "
                       "früh, geprüft gegen die Tabellen des Landesamts für "
                       "Statistik (KFA 2016–2026) und gegen die Ist-Beträge "
                       "in den Haushaltsplänen der Stadt. Die Pro-Kopf-Spalten "
                       "des Datensatzes übernehmen wir deshalb nicht",
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
                           "des Vorjahres) — die Aufwendungs-Spalte derselben "
                           "Datei ist eine eigene Schicht mit eigenen Proben "
                           "(council_ausgabenreihe)",
                stand=_spanne(ew)))
            print(f"Einwohnerzahlen: {n} Jahre ({_spanne(ew)}).")
        else:
            print("Einwohner-CSV nicht lesbar — übersprungen.", file=sys.stderr)

        # --- Investitionen (Finanzhaushalt) ---------------------------------
        # Die einzige dieser Dateien mit einer Rechenprobe im Dokument selbst.
        # Ein Jahrgang, der sie reißt, wird übersprungen — nicht geschätzt und
        # nicht halb gespeichert (council/investitionen.py entscheidet das).
        p = finanzquellen.Protokoll()
        gespeichert: list[int] = []
        for year, url in sorted(haushalt.INVESTITIONEN_CSV_URLS.items()):
            r = requests.get(url, headers=_UA, timeout=120)
            if r.status_code != 200:
                print(f"Investitionen {year}: HTTP {r.status_code} — übersprungen",
                      file=sys.stderr)
                continue
            gelesen = investitionen.lies(r.text, year)
            if not gelesen["bestanden"]:
                print(f"Investitionen {year}: {gelesen['nachweis']} — "
                      f"nicht gespeichert", file=sys.stderr)
                continue
            # Ein leeres oder deutlich geschrumpftes Ergebnis ersetzt keinen
            # gefüllten Jahrgang (dieselbe Regel wie in den Finanzberichten).
            alt = len(store.get_investitionen(year=year))
            neu = len(gelesen["zeilen"]) + 1 + (1 if gelesen["finanzhaushalt"] else 0)
            if not finanzquellen.bestandsschutz(p, f"Investitionen {year}", alt, neu):
                continue

            anker = dict(art="opendata", url=url,
                         label=f"Finanzhaushalt der Stadt Oldenburg {year}")
            n = store.save_investitionen(
                year, gelesen["zeilen"], gelesen["gesamt"],
                herkunft.Herkunft(
                    probe="investitionen_summenzeile",
                    fundstelle="Datensatz 1101, Tabellenblatt „Finanzhaushalt“ — "
                               "je Teilhaushalt eine Zeile mit Ein- und "
                               "Auszahlungen aus Investitionstätigkeit, darunter "
                               "die Summenzeile „Finanzhaushalt "
                               "Gesamtinvestitionen“. Für welches Jahr die Datei "
                               "gilt, steht nicht in ihr, sondern in ihrem "
                               f"Dateinamen (…_{year}_Finanzhaushalt.csv)",
                    probe_ergebnis=gelesen["nachweis"],
                    stand=f"Haushaltsplan {year} — Plan, nicht Ist",
                    **anker),
                finanzhaushalt=gelesen["finanzhaushalt"],
                herkunft_finanzhaushalt=herkunft.Herkunft(
                    # Diese eine Zeile trägt die Probe NICHT: Sie zählt die
                    # laufende Verwaltungstätigkeit mit, und nichts in der
                    # Datei summiert sich auf sie. Als geprüft auszuweisen,
                    # was nur danebensteht, wäre die eine Behauptung, die der
                    # ganze Bereich vermeiden soll.
                    probe=herkunft.UNGEPRUEFT,
                    fundstelle="Datensatz 1101, Zeile „Gesamtbetrag des "
                               "Finanzhaushaltes“ — alle Ein- und Auszahlungen "
                               "des Jahres, also samt laufender "
                               "Verwaltungstätigkeit. Bezugsgröße für den "
                               "Investitionsanteil, nicht Teil der geprüften "
                               "Rechnung",
                    stand=f"Haushaltsplan {year} — Plan, nicht Ist",
                    **anker) if gelesen["finanzhaushalt"] else None)
            gespeichert.append(year)
            g = gelesen["gesamt"]
            print(f"Investitionen {year}: {len(gelesen['zeilen'])} Teilhaushalte, "
                  f"{n} Zeilen · Auszahlungen {g['auszahlungen']/1e6:.1f} Mio. · "
                  f"Einzahlungen {g['einzahlungen']/1e6:.1f} Mio. · "
                  f"{gelesen['nachweis']}")
        if gespeichert:
            print(f"Investitionen gesamt: {len(gespeichert)} Jahrgänge "
                  f"({gespeichert[0]}–{gespeichert[-1]}).")

        store.herkunft_aufraeumen()
        luecken = store.herkunft_luecken()
        if luecken:
            print(f"Ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
