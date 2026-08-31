#!/usr/bin/env python3
"""Die Schuldenzeitreihe aus Tabelle 1108 des Statistischen Jahrbuchs einlesen.

Eine Seite, dreißig Jahre: Schuldenstand der Stadt Oldenburg seit 1995, nach
Schuldenart aufgeteilt, mit Summe und Betrag je Einwohner*in. Was die Zahlen
abgrenzen — Stadt als Rechtsträger, also **mit** Eigenbetrieben und **ohne**
die selbstständigen Beteiligungen — steht im Kopf von ``council/schulden.py``
und ist die wichtigste Angabe der Schicht.

Warum von Hand und nicht per Cron
---------------------------------
Die Tabelle erscheint **einmal jährlich** (Jahrgang 2025: online seit dem
08.07.2026), und ihr Dateiname trägt den Jahrgang — ``1108-2025-AZ.pdf`` wird
im nächsten Jahr ``1108-2026-…`` heißen, mit einer Schreibweise, die sich
nicht vorhersagen lässt (die Nachbartabellen wechseln zwischen ``-az``,
``-AZ`` und gar keinem Zusatz). Deshalb sucht dieser Lauf den Link auf der
Jahrbuch-Übersichtsseite, statt eine Adresse hochzuzählen. Der Web-Dienst lädt
zu keinem Zeitpunkt etwas nach; er liest, was hier gespeichert wurde.

Die Pro-Kopf-Gegenprobe braucht ``council_einwohner``. Ist die Tabelle leer,
läuft der Import trotzdem — dann trägt jeder Jahrgang nur die Summenprobe, und
der Lauf sagt es. Wer beides will, lässt vorher
``scripts/ingest_finanzen_opendata.py`` laufen.

Aufruf::

    python scripts/ingest_schulden.py                 # Link von der Übersicht
    python scripts/ingest_schulden.py --pdf 1108.pdf  # lokale Datei
    python scripts/ingest_schulden.py --trockenlauf   # nur zeigen, nichts schreiben
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
from council import schulden  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}

#: Probenschlüssel → wie die Probe im Messwert heißt. Der Schlüssel steht
#: schon in ``Herkunft.probe``; ``probe_result`` ist der Satz daneben und
#: soll ihn nicht bloß wiederholen.
PROBENNAMEN = {"schulden_summenzeile": "Summenprobe",
               "schulden_prokopf": "Pro-Kopf-Gegenprobe"}


def _de(zahl: float, nachkomma: int = 0, vorzeichen: bool = False) -> str:
    """Eine Zahl in deutscher Schreibweise: 1.078.000 statt 1,078,000.

    Ein Helfer und kein ``.replace(",", ".")`` auf dem ganzen Satz: Das
    verwandelt auch das Dezimalkomma in einen Punkt und schreibt aus
    „337,0 Mio. €" ein „337.0 Mio. €"."""
    text = f"{zahl:{'+' if vorzeichen else ''},.{nachkomma}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def link_suchen() -> str | None:
    """Den aktuellen Link auf Tabelle 1108 von der Jahrbuch-Seite holen.

    ``None``, wenn die Seite ihn nicht (mehr) führt — dann greift die
    hinterlegte Adresse, und der Lauf sagt, dass er das tut."""
    answer = requests.get(schulden.JAHRBUCH_URL, headers=_UA, timeout=120)
    answer.raise_for_status()
    treffer = schulden.LINK_MUSTER.search(answer.text)
    return urljoin(schulden.JAHRBUCH_URL, treffer.group(1)) if treffer else None


def pdf_text(pfad: Path) -> str:
    """Volltext aller Seiten — die Tabelle steht auf einer."""
    return "\n".join((s.extract_text() or "") for s in PdfReader(str(pfad)).pages)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Schuldenzeitreihe (Tabelle 1108) einlesen")
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
                    url = schulden.TABELLE_URL
                    print(f"HINWEIS: Die Übersichtsseite führt keinen Link auf "
                          f"1108 mehr — es gilt die hinterlegte Adresse: {url}")
                answer = requests.get(url, headers=_UA, timeout=120)
                answer.raise_for_status()
                pfad = Path(tmp) / "1108.pdf"
                pfad.write_bytes(answer.content)
                print(f"  geladen: {_de(len(answer.content))} Bytes")

            text = pdf_text(pfad)
            spanne = schulden.erkenne(text)
            if not spanne:
                print("ABBRUCH: Das ist nicht Tabelle 1108 — der Titel fehlt. "
                      "Es wird nichts geschrieben.", file=sys.stderr)
                return 1
            print(f"Tabelle 1108, Spanne laut Titel: {spanne[0]}–{spanne[1]}")

            # Der Divisor der unabhängigen Gegenprobe. Fehlt er, bleibt es bei
            # der Summenprobe — das ist eine Einschränkung, keine Ausrede, und
            # sie steht unten im Nachweis.
            population = store.einwohner_je_jahr()
            if not population:
                print("HINWEIS: keine Einwohnerzahlen im Bestand — die "
                      "Pro-Kopf-Gegenprobe entfällt. Vorher "
                      "scripts/ingest_finanzen_opendata.py laufen lassen.")

            result = schulden.lies(text, population)
            zeilen = result["zeilen"]
            print(f"  {len(zeilen)} Jahrgänge übernommen · "
                  f"{schulden.probennachweis(result)}")
            for v in result["verworfen"]:
                print(f"    VERWORFEN {v['year']}: {v['grund']}", file=sys.stderr)
            for f in result["fehlende_jahrgaenge"]:
                print(f"    FEHLT {f}: im Titel angekündigt, nicht gelesen",
                      file=sys.stderr)
            ohne_arten = [z for z in zeilen if z["breakdown_rejected"] is not None]
            for z in ohne_arten:
                print(f"    {z['year']}: Aufteilung verworfen — die Schuldenarten "
                      f"ergeben {_de(z['breakdown_rejected'], vorzeichen=True)} € "
                      f"gegenüber der ausgewiesenen Summe. Die Summe trägt die "
                      f"Pro-Kopf-Gegenprobe und bleibt.")
            if not zeilen:
                print("ABBRUCH: kein einziger Jahrgang hat eine Probe bestanden.",
                      file=sys.stderr)
                return 1

            juengster = zeilen[-1]
            print(f"  jüngster Jahrgang {juengster['year']}: "
                  f"{_de(juengster['total'] / 1e6, 1)} Mio. € total, "
                  f"{_de(juengster['per_capita'])} € je Einwohner*in")

            if args.trockenlauf:
                print("Trockenlauf — nichts gespeichert.")
                return 0

            # Bestandsschutz vor dem Schreiben (council/finanzquellen.py).
            # `save_schulden` löscht zwar nichts, was die Lieferung nicht
            # mitbringt — ein halb gelesener Jahrgangssatz kann den Bestand
            # also nicht abräumen. Was er aber KANN, ist vorhandene Jahrgänge
            # mit schlechteren Werten überschreiben, wenn die Stadt ihr
            # Tabellenlayout ändert und der Parser nur noch die Hälfte
            # versteht. Genau davor schützt diese Regel: Ein deutlich
            # kleineres Ergebnis ersetzt den Bestand nicht.
            #
            # `--schrumpf-erlauben` ist der bewusste Handgriff für den Fall,
            # dass ein verbesserter Parser absichtlich weniger Jahrgänge
            # übernimmt (etwa weil eine Probe schärfer geworden ist).
            p = finanzquellen.Protokoll()
            alt = len(store.schulden_jahre())
            if not finanzquellen.bestandsschutz(
                    p, "Schuldenzeitreihe", alt, len(zeilen),
                    schuetzen=not args.schrumpf_erlauben):
                for zeile in p.warnungen:
                    print(zeile.strip(), file=sys.stderr)
                print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn "
                      "das Schrumpfen Absicht ist: --schrumpf-erlauben.",
                      file=sys.stderr)
                return 1
            for zeile in p.zeilen:
                print(zeile.strip())

            # Zwei Herkünfte, weil zwei verschiedene Probenlagen vorliegen und
            # eine gemeinsame Angabe für beide ungenau wäre: Die meisten
            # Jahrgänge stehen auf der Summenprobe (2010+ zusätzlich auf der
            # Gegenprobe), 2022 allein auf der Gegenprobe. Was ein Leser im
            # Beleg sieht, soll für SEINE Zahl gelten.
            # `stand` nennt NUR den Stichtag. Die Abgrenzung stünde hier zwar
            # gut, steht aber schon als eigenes Feld an der Antwort des
            # Endpunkts (`abgrenzung`) und damit auf der Seite direkt an der
            # großen Zahl — zweimal im Abstand von zwei Absätzen gelesen wirkt
            # sie wie zwei verschiedene Angaben.
            anker = dict(
                art="stadt", url=url or schulden.TABELLE_URL,
                label=f"Statistisches Jahrbuch der Stadt Oldenburg, Tabelle 1108 — "
                      f"Stand der Verschuldung {spanne[0]} bis {spanne[1]}",
                stand=f"Schuldenstand zum 31.12.{spanne[1]}")
            citation = ("Kapitel 11 „Verwaltung und Finanzen“, Tabelle 1108 — "
                          "je Jahr die vier Schuldenarten (Spalten S 2 bis S 5), "
                          "ihre Summe (S 6) und der Betrag je Einwohner*in (S 7)")

            geschrieben = 0
            for probenlage in sorted({tuple(z["probes"]) for z in zeilen}):
                part = [z for z in zeilen if tuple(z["probes"]) == probenlage]
                years = [z["year"] for z in part]
                spanne_teil = (f"Jahrgänge {years[0]}–{years[-1]}" if len(years) > 1
                               else f"Jahrgang {years[0]}")
                namen = " und ".join(PROBENNAMEN[p] for p in probenlage)
                nachweis = (f"{spanne_teil} ({len(part)} von "
                            f"{len(zeilen)}): {namen} bestanden")
                # Wo die Summenprobe fehlt, gehört ihr Messwert dazu — sonst
                # liest sich „Pro-Kopf-Gegenprobe bestanden" wie eine
                # Vollständigkeit, die dieser Jahrgang nicht hat.
                fehlend = [z for z in part if z["breakdown_rejected"] is not None]
                if fehlend:
                    nachweis += ("; die Summenprobe reißt um "
                                 + ", ".join(
                                     _de(z["breakdown_rejected"], vorzeichen=True)
                                     + " €" for z in fehlend)
                                 + " — die Aufteilung nach Schuldenarten ist "
                                   "deshalb nicht gespeichert")
                geschrieben += store.save_schulden(part, h.Herkunft(
                    probe=list(probenlage), citation=citation,
                    probe_result=nachweis, **anker))
            print(f"  gespeichert: {geschrieben} Jahrgänge")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t == "council_schulden"}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
