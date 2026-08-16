#!/usr/bin/env python3
"""Die Ist-Investitionen aus den Tabellen 1107/1107-1 des Jahrbuchs einlesen.

Was die Stadt in einem Jahr wirklich gebaut, gekauft und ausgezahlt hat —
nach Auszahlungsart aufgeteilt, aus den Rechnungsergebnissen. Das Gegenstück
zu ``scripts/ingest_finanzen_opendata.py``, das die **Planzahlen** desselben
Themas holt.

**Beide Zahlen nie voneinander abziehen.** Der Plan ist nach Teilhaushalten
gegliedert, das Ist nach Auszahlungsarten und ausdrücklich auf die
Kernverwaltung begrenzt; kein Dokument stellt die beiden Summen nebeneinander.
Die Begründung steht im Kopf von ``council/investitionen_ist.py``.

Warum von Hand und nicht per Cron
---------------------------------
Wie bei Tabelle 1108: Die Datei erscheint einmal jährlich und trägt den
Jahrgang im Namen (``1107-1107-1-2025-AZ.pdf``), mit einer Schreibweise, die
sich nicht vorhersagen lässt. Deshalb sucht dieser Lauf den Link auf der
Jahrbuch-Übersichtsseite, statt eine Adresse hochzuzählen. Der Web-Dienst lädt
zu keinem Zeitpunkt etwas nach; er liest, was hier gespeichert wurde.

Aufruf::

    python scripts/ingest_investitionen_ist.py                # Link von der Übersicht
    python scripts/ingest_investitionen_ist.py --pdf 1107.pdf # lokale Datei
    python scripts/ingest_investitionen_ist.py --trockenlauf  # nur zeigen
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

from council import finanzquellen  # noqa: E402
from council import herkunft as h  # noqa: E402
from council import investitionen_ist as ii  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}


def link_suchen() -> str | None:
    """Den aktuellen Link auf die 1107er-Datei von der Jahrbuch-Seite holen.

    ``None``, wenn die Seite ihn nicht (mehr) führt — dann greift die
    hinterlegte Adresse, und der Lauf sagt, dass er das tut."""
    antwort = requests.get(ii.JAHRBUCH_URL, headers=_UA, timeout=120)
    antwort.raise_for_status()
    treffer = ii.LINK_MUSTER.search(antwort.text)
    return urljoin(ii.JAHRBUCH_URL, treffer.group(1)) if treffer else None


def pdf_text(pfad: Path) -> str:
    """Volltext aller Seiten — beide Tabellen stehen auf einer."""
    return "\n".join((s.extract_text() or "") for s in PdfReader(str(pfad)).pages)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ist-Investitionen (Tabellen 1107/1107-1) einlesen")
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
            if args.pdf:
                pfad, url = Path(args.pdf), None
            else:
                url = link_suchen()
                if url:
                    print(f"Link von der Jahrbuch-Seite: {url}")
                else:
                    url = ii.TABELLE_URL
                    print(f"HINWEIS: Die Übersichtsseite führt keinen Link auf "
                          f"1107 mehr — es gilt die hinterlegte Adresse: {url}")
                antwort = requests.get(url, headers=_UA, timeout=120)
                antwort.raise_for_status()
                pfad = Path(tmp) / "1107.pdf"
                pfad.write_bytes(antwort.content)
                print(f"  geladen: {ii.de_zahl(len(antwort.content))} Bytes")

            text = pdf_text(pfad)
            spannen = ii.erkenne(text)
            if "doppik" not in spannen:
                print("ABBRUCH: Tabelle 1107-1 ist nicht zu finden — ihr Titel "
                      "fehlt. Es wird nichts geschrieben.", file=sys.stderr)
                return 1
            for regelwerk, (von, bis) in sorted(spannen.items()):
                print(f"{ii.REGELWERK[regelwerk]}: Spanne laut Titel {von}–{bis}")

            ergebnis = ii.lies(text)
            zeilen = ergebnis["zeilen"]
            print(f"  {len(zeilen)} Jahrgänge übernommen · "
                  f"{ii.probennachweis(ergebnis)}")
            for v in ergebnis["verworfen"]:
                print(f"    VERWORFEN {v['jahr']} ({v['regelwerk']}): {v['grund']}",
                      file=sys.stderr)
            for regelwerk, jahre in sorted(ergebnis["fehlende_jahrgaenge"].items()):
                for j in jahre:
                    print(f"    FEHLT {j} ({regelwerk}): im Titel angekündigt, "
                          f"nicht übernommen", file=sys.stderr)
            if not zeilen:
                print("ABBRUCH: kein einziger Jahrgang hat die Probe bestanden.",
                      file=sys.stderr)
                return 1

            doppik = [z for z in zeilen if z["regelwerk"] == "doppik"]
            if doppik:
                j = doppik[-1]
                groesste = max(
                    ((f, j[f]) for f in ii.ARTEN["doppik"] if j.get(f)),
                    key=lambda p: p[1], default=None)
                titel = dict(ii.SPALTEN["doppik"]).get(
                    groesste[0], "") if groesste else ""
                print(f"  jüngster Jahrgang {j['jahr']}: "
                      f"{ii.de_zahl(j['insgesamt'] / 1e6, 1)} Mio. € insgesamt"
                      + (f", größter Posten „{titel}“ mit "
                         f"{ii.de_zahl(groesste[1] / 1e6, 1)} Mio. €" if groesste else ""))

            if args.trockenlauf:
                print("Trockenlauf — nichts gespeichert.")
                return 0

            # Bestandsschutz vor dem Schreiben (council/finanzquellen.py):
            # Ein deutlich kleineres Ergebnis ersetzt den Bestand nicht. Das
            # schützt vor dem Fall, dass die Stadt ihr Tabellenlayout ändert
            # und der Parser nur noch die Hälfte versteht — `--schrumpf-erlauben`
            # ist der bewusste Handgriff, wenn das Schrumpfen Absicht ist.
            p = finanzquellen.Protokoll()
            alt = len(store.investitionen_ist_jahre())
            if not finanzquellen.bestandsschutz(
                    p, "Ist-Investitionen", alt, len(zeilen),
                    schuetzen=not args.schrumpf_erlauben):
                for zeile in p.warnungen:
                    print(zeile.strip(), file=sys.stderr)
                print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn "
                      "das Schrumpfen Absicht ist: --schrumpf-erlauben.",
                      file=sys.stderr)
                return 1
            for zeile in p.zeilen:
                print(zeile.strip())

            # Eine Herkunft je Regelwerk, weil die beiden Tabellen zwei
            # Dokumentabschnitte mit zwei Abgrenzungen sind — dieselbe Datei,
            # aber nicht dieselbe Fundstelle und nicht dieselbe Aussage. Was
            # ein Leser im Beleg sieht, soll für SEINE Zahl gelten.
            #
            # `stand` nennt nur den Berichtszeitraum. Die Abgrenzung stünde
            # hier zwar gut, steht aber schon als eigenes Feld an der Antwort
            # des Endpunkts (`abgrenzung`) und damit auf der Seite direkt an
            # der großen Zahl.
            geschrieben = 0
            for regelwerk in ("kameral", "doppik"):
                teil = [z for z in zeilen if z["regelwerk"] == regelwerk]
                if not teil:
                    continue
                von, bis = spannen[regelwerk]
                nummer = "1107-1" if regelwerk == "doppik" else "1107"
                arten = ", ".join(t for _, t in ii.SPALTEN[regelwerk][:-1])
                fundstelle = (f"Kapitel 11 „Verwaltung und Finanzen“, Tabelle "
                              f"{nummer} — je Jahr die Auszahlungsarten "
                              f"({arten}) und ihre Summe")
                nachweis = (f"Jahrgänge {teil[0]['jahr']}–{teil[-1]['jahr']} "
                            f"({len(teil)} von {bis - von + 1} angekündigten): "
                            f"Zeilensumme bestanden")
                fehlt = ergebnis["fehlende_jahrgaenge"].get(regelwerk) or []
                if fehlt:
                    # Was fehlt, gehört in den Messwert — sonst liest sich
                    # „Zeilensumme bestanden" wie eine Vollständigkeit, die
                    # diese Reihe nicht hat.
                    nachweis += ("; ohne "
                                 + ", ".join(str(j) for j in fehlt)
                                 + " — dort ergeben die Auszahlungsarten in der "
                                   "Quelltabelle nicht die Summe daneben, und "
                                   "eine zweite Probe trägt diese Tabelle nicht")
                geschrieben += store.save_investitionen_ist(teil, h.Herkunft(
                    art="stadt", url=url or ii.TABELLE_URL,
                    label=f"Statistisches Jahrbuch der Stadt Oldenburg, Tabelle "
                          f"{nummer} — Investitionen {von} bis {bis}",
                    stand=f"Rechnungsergebnisse {von}–{bis}",
                    probe="investitionen_ist_zeilensumme",
                    fundstelle=fundstelle, probe_ergebnis=nachweis))
            print(f"  gespeichert: {geschrieben} Jahrgänge")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t.startswith("council_investitionen_ist")}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
