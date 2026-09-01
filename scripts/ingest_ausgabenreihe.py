#!/usr/bin/env python3
"""Die lange Ausgabenreihe (Datensatz 1102) einlesen — 1972 bis heute.

Was die Stadt in einem Jahr ausgegeben hat, über 54 Jahrgänge. Der Datensatz
steht an zwei Stellen, und beide werden hier gelesen und gegeneinander
gehalten:

* das **Statistische Jahrbuch, Tabelle 1102** (PDF von oldenburg.de) — führt
  2002 bis heute, mit den Untertiteln, die sagen, WAS da gezählt wird;
* der **Open-Data-Datensatz 1102** (zwei CSV-Dateien) — führt 1972 bis heute,
  aber ohne Untertitel und ohne Fußnoten.

Dazu, als dritte Probe, unser eigener Bestand: Für die Jahre mit
Jahresabschluss muss der Betrag zur Ergebnisrechnung desselben Jahres passen.
Die drei Proben und ihre Messwerte stehen im Kopf von
``council/expense_series.py``.

Warum von Hand und nicht per Cron
---------------------------------
Wie bei den Tabellen 1107 und 1108: Die PDF-Datei erscheint einmal jährlich
und trägt den Jahrgang im Namen (``1102-2025-AZ.pdf``), in einer Schreibweise,
die sich nicht vorhersagen lässt. Deshalb sucht dieser Lauf den Link auf der
Jahrbuch-Übersichtsseite, statt eine Adresse hochzuzählen. Der Web-Dienst lädt
zu keinem Zeitpunkt etwas nach; er liest, was hier gespeichert wurde.

Aufruf::

    python scripts/ingest_ausgabenreihe.py                 # Link von der Übersicht
    python scripts/ingest_ausgabenreihe.py --pdf 1102.pdf  # lokale Datei
    python scripts/ingest_ausgabenreihe.py --trockenlauf   # nur zeigen
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import expense_series as ar  # noqa: E402
from council import finanzquellen  # noqa: E402
from council import herkunft as h  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}

#: Posten 20 der Ergebnisrechnung — „Summe ordentliche Aufwendungen".
POSTEN_AUFWENDUNGEN = 20


def link_suchen() -> str | None:
    """Den aktuellen Link auf die 1102er-Datei von der Jahrbuch-Seite holen.

    ``None``, wenn die Seite ihn nicht (mehr) führt — dann greift die
    hinterlegte Adresse, und der Lauf sagt, dass er das tut."""
    answer = requests.get(ar.JAHRBUCH_URL, headers=_UA, timeout=120)
    answer.raise_for_status()
    treffer = ar.LINK_MUSTER.search(answer.text)
    return urljoin(ar.JAHRBUCH_URL, treffer.group(1)) if treffer else None


def pdf_text(pfad: Path) -> str:
    """Volltext aller Seiten — beide Blöcke stehen auf einer."""
    return "\n".join((s.extract_text() or "") for s in PdfReader(str(pfad)).pages)


def kernverwaltung(store: CouncilStore) -> dict[int, float]:
    """``{year: Summe ordentliche Aufwendungen}`` aus den Jahresabschlüssen.

    Die Gesamtrechnung, also ``sub_budget_no IS NULL`` — dieselbe Ebene, die auch die
    Statistik zählt, nur **ohne** die nicht rechtsfähigen Stiftungen. Genau
    dieser Unterschied ist die Toleranz der Gegenprobe (s.
    ``council/expense_series.gegenprobe``)."""
    werte: dict[int, float] = {}
    for p in store.get_ergebnisrechnung():
        if p.get("sub_budget_no") is None and p.get("nr") == POSTEN_AUFWENDUNGEN \
                and p.get("result") is not None:
            werte[p["year"]] = float(p["result"])
    return werte


def _spanne(years: list[int]) -> str:
    """„1972–2001" — und „2010–2016, 2025", wo die Gruppe Löcher hat.

    Kein ``von–bis`` über alles: Die Gruppen entstehen nach bestandenen Proben,
    nicht nach Zeitraum. Für 2010–2016 und 2025 gilt derselbe Beleg (zwei
    Quellen, noch kein Jahresabschluss) — „2010–2025" behauptete dort, die
    Jahre dazwischen gehörten auch dazu, und die haben eine Probe mehr."""
    bloecke: list[list[int]] = []
    for j in sorted(years):
        if bloecke and j == bloecke[-1][-1] + 1:
            bloecke[-1].append(j)
        else:
            bloecke.append([j])
    return ", ".join(f"{b[0]}" if len(b) == 1 else f"{b[0]}–{b[-1]}"
                     for b in bloecke)


def _fundstelle(accounting_system: str, source: str, mit_abschluss: bool) -> str:
    """Wo genau die Zahlen dieser Gruppe stehen — je nach Quellenlage."""
    title = ar.TITEL[accounting_system]
    if source == "csv":
        return (f"Datensatz 1102, Spalte „{title}“ — je Haushaltsjahr die "
                f"Einwohnerzahl (Stichtag 31.12. des Vorjahres), der Betrag in "
                f"Tausend Euro und der Betrag je Einwohner*in. Diese Jahrgänge "
                f"führt nur das Open-Data-Portal; im PDF des Statistischen "
                f"Jahrbuchs beginnt die Tabelle später")
    text = (f"Kapitel 11 „Verwaltung und Finanzen“, Tabelle 1102, Block "
            f"„{title}“ — je Haushaltsjahr die Einwohnerzahl (Stichtag 31.12. "
            f"des Vorjahres), der Betrag in Tausend Euro und der Betrag je "
            f"Einwohner*in. Dieselben Jahrgänge stehen im Open-Data-Portal als "
            f"CSV; beide werden getrennt gelesen")
    if mit_abschluss:
        text += (", und der Jahresabschluss desselben Jahres steht als dritte "
                 "Quelle daneben")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Lange Ausgabenreihe (Datensatz 1102) einlesen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--pdf", help="lokale Datei statt Download")
    ap.add_argument("--trockenlauf", action="store_true",
                    help="alles rechnen und zeigen, nichts speichern")
    ap.add_argument("--schrumpf-erlauben", action="store_true",
                    help="einen deutlich kleineren Jahrgangssatz trotzdem "
                         "speichern (bewusster Handgriff, s. bestandsschutz)")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # --- Die beiden CSV-Dateien ------------------------------------
            csv: dict[str, str] = {}
            for accounting_system, url in ar.CSV_URLS.items():
                answer = requests.get(url, headers=_UA, timeout=120)
                if answer.status_code != 200:
                    print(f"CSV {accounting_system}: HTTP {answer.status_code} — "
                          f"übersprungen", file=sys.stderr)
                    csv[accounting_system] = ""
                    continue
                # Das Portal liefert die Dateien ohne Kodierungsangabe;
                # requests rät dann Latin-1 und macht aus „für“ ein „fÃ¼r“.
                answer.encoding = answer.encoding or "utf-8-sig"
                csv[accounting_system] = answer.text
                print(f"CSV {accounting_system}: {len(answer.content)} Bytes")

            # --- Das PDF des Jahrbuchs -------------------------------------
            if args.pdf:
                pfad, url = Path(args.pdf), None
            else:
                url = link_suchen()
                if url:
                    print(f"Link von der Jahrbuch-Seite: {url}")
                else:
                    url = ar.TABELLE_URL
                    print(f"HINWEIS: Die Übersichtsseite führt keinen Link auf "
                          f"1102 mehr — es gilt die hinterlegte Adresse: {url}")
                answer = requests.get(url, headers=_UA, timeout=120)
                answer.raise_for_status()
                pfad = Path(tmp) / "1102.pdf"
                pfad.write_bytes(answer.content)
                print(f"  geladen: {ar.de_zahl(len(answer.content))} Bytes")

            text = pdf_text(pfad)
            spannen = ar.erkenne(text)
            if not spannen:
                print("ABBRUCH: In der Datei ist keiner der beiden "
                      "1102-Tabellenblöcke zu finden. Es wird nichts "
                      "geschrieben.", file=sys.stderr)
                return 1
            for accounting_system, (von, bis) in sorted(spannen.items()):
                print(f"{ar.REGELWERK[accounting_system]}: Spanne laut Titel {von}–{bis}")

            # --- Lesen und prüfen -------------------------------------------
            abschluesse = kernverwaltung(store)
            print(f"Gegenprobe möglich für {len(abschluesse)} Jahrgänge mit "
                  f"Jahresabschluss")
            result = ar.lies(csv.get("kameral", ""), csv.get("doppik", ""),
                               text, abschluesse)
            zeilen = result["zeilen"]
            print(f"  {len(zeilen)} Jahrgänge übernommen · "
                  f"{ar.probennachweis(result)}")
            for v in result["verworfen"]:
                print(f"    VERWORFEN {v['year']}: {v['reason']}", file=sys.stderr)
            for k in result["konflikte"]:
                print(f"    WIDERSPRUCH {k['year']}: "
                      f"{k['gewaehlt'].upper()} nennt "
                      f"{ar.de_zahl(k['amount'] / 1e6, 3)} Mio. €, "
                      f"{k['verworfen'].upper()} "
                      f"{ar.de_zahl(k['conflict_amount'] / 1e6, 3)} Mio. € — "
                      f"{ar.de_zahl(k['difference'] / 1e6, 3)} Mio. € "
                      f"Unterschied; übernommen wird "
                      f"{k['gewaehlt'].upper()} (besteht die Pro-Kopf-Probe)")
            for accounting_system, years in sorted(result["fehlende_jahrgaenge"].items()):
                for j in years:
                    print(f"    FEHLT {j} ({accounting_system})", file=sys.stderr)
            if not zeilen:
                print("ABBRUCH: kein einziger Jahrgang hat eine Probe bestanden.",
                      file=sys.stderr)
                return 1

            erster, letzter = zeilen[0], zeilen[-1]
            print(f"  {erster['year']}: {ar.de_zahl(erster['amount'] / 1e6, 1)} "
                  f"Mio. € · {letzter['year']}: "
                  f"{ar.de_zahl(letzter['amount'] / 1e6, 1)} Mio. €")

            if args.trockenlauf:
                print("Trockenlauf — nichts gespeichert.")
                return 0

            # Bestandsschutz vor dem Schreiben (council/finanzquellen.py): Ein
            # deutlich kleineres Ergebnis ersetzt den Bestand nicht — etwa
            # wenn eine der beiden CSV-Adressen wandert und der Lauf nur noch
            # die halbe Reihe sieht.
            p = finanzquellen.Protokoll()
            alt = len(store.ausgabenreihe_jahre())
            if not finanzquellen.bestandsschutz(
                    p, "Ausgabenreihe", alt, len(zeilen),
                    schuetzen=not args.schrumpf_erlauben):
                for row in p.warnungen:
                    print(row.strip(), file=sys.stderr)
                print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn "
                      "das Schrumpfen Absicht ist: --schrumpf-erlauben.",
                      file=sys.stderr)
                return 1
            for row in p.zeilen:
                print(row.strip())

            # --- Schreiben, eine Herkunft je Beleg-Lage ---------------------
            #
            # Gruppiert wird nach Regelwerk, gewählter Quelle UND bestandenen
            # Proben. Das ist keine Sortierlaune: Ein Jahrgang von 1974 hängt
            # allein an der Pro-Kopf-Rechnung des Portals, einer von 2024
            # zusätzlich am Jahrbuch und am Jahresabschluss, und 2021 hat die
            # Zweitquellenprobe gerissen. Wer im Beleg nachschlägt, soll
            # lesen, was für SEINE Zahl gilt — nicht den Durchschnitt der
            # Reihe.
            gruppen: dict[tuple, list[dict]] = {}
            for z in zeilen:
                gruppen.setdefault(
                    (z["accounting_system"], z["source"], tuple(z["probes"])), []).append(z)

            geschrieben = 0
            for (accounting_system, source, probes), part in sorted(
                    gruppen.items(), key=lambda kv: kv[1][0]["year"]):
                spanne = _spanne([z["year"] for z in part])
                count = (f"{len(part)} Jahrgänge" if len(part) != 1
                          else "1 Jahrgang")
                nachweis = f"{count} ({spanne}), bestanden: " \
                    + ", ".join(ar.PROBEN_KURZ[n] for n in probes)
                if any(z.get("conflict_amount") for z in part):
                    k = next(z for z in part if z.get("conflict_amount"))
                    nachweis += (
                        f"; für {k['year']} widersprechen sich die beiden "
                        f"Quellen um "
                        f"{ar.de_zahl(abs(k['conflict_amount'] - k['amount']) / 1e6, 3)}"
                        f" Mio. € — übernommen ist der Wert, der seine "
                        f"Pro-Kopf-Rechnung erfüllt")
                geschrieben += store.save_ausgabenreihe(part, h.Herkunft(
                    kind="opendata" if source == "csv" else "city",
                    url=(ar.CSV_URLS[accounting_system] if source == "csv"
                         else (url or ar.TABELLE_URL)),
                    label=("Open-Data-Portal der Stadt Oldenburg, Datensatz "
                           f"1102 — {ar.TITEL[accounting_system]}" if source == "csv"
                           else "Statistisches Jahrbuch der Stadt Oldenburg, "
                                f"Tabelle 1102 — {ar.TITEL[accounting_system]}"),
                    as_of=f"Haushaltsjahre {spanne} · {ar.ABGRENZUNG[accounting_system]}",
                    probe=list(probes),
                    citation=_fundstelle(
                        accounting_system, source,
                        "expense_series_annual_accounts" in probes),
                    probe_result=nachweis))
                print(f"  {ar.REGELWERK[accounting_system]}, {spanne} "
                      f"({source.upper()}): {count}")
            print(f"  gespeichert: {geschrieben} Jahrgänge")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t == "council_ausgabenreihe"}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
