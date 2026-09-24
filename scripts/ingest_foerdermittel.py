#!/usr/bin/env python3
"""Fördermittel von EU und Bund einlesen.

Parser und Probe: ``council/foerdermittel.py``. Der Lauf

1. holt die Übersichtsseite „Liste der Vorhaben" (Europa für Niedersachsen)
   und die dort verlinkten XLSX-Dateien — EFRE und ESF(+), beide
   Förderperioden,
2. sucht im Förderkatalog des Bundes nach der Gemeinde Oldenburg (Oldb) und
   holt das Ergebnis als CSV,
3. behält aus jeder Liste nur die Vorhaben der Stadt und ihrer Gesellschaften
   und ersetzt damit die Zeilen dieser Liste.

Höflich: 1,5 s Abstand zwischen zwei Abrufen, sechs Abrufe je Lauf. Kein
Sprachmodell, keine Kosten.

    python scripts/ingest_foerdermittel.py --trocken
    python scripts/ingest_foerdermittel.py
"""
from __future__ import annotations

import argparse
import http.cookiejar
import io
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import foerdermittel as fm  # noqa: E402
from council import herkunft  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
KOPF = {"User-Agent": "Mozilla/5.0 (Ratslotse; +https://ratslotse.de)"}


class Abruf:
    """Ein Opener mit Keksdose (der Förderkatalog hält die Suche in der
    Sitzung) und Mindestabstand zwischen zwei Abrufen."""

    def __init__(self, pause: float) -> None:
        self.pause, self._zuletzt = pause, 0.0
        self._op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def __call__(self, url: str, daten: dict | None = None, kodierung: str = "utf-8") -> bytes:
        warten = self.pause - (time.monotonic() - self._zuletzt)
        if warten > 0:
            time.sleep(warten)
        body = urllib.parse.urlencode(daten, encoding=kodierung).encode() if daten else None
        anfrage = urllib.request.Request(url, data=body, headers=KOPF)
        try:
            with self._op.open(anfrage, timeout=180) as antwort:
                return antwort.read()
        finally:
            self._zuletzt = time.monotonic()


def _eu(abruf: Abruf) -> list[tuple[fm.Lesung, str, str, str]]:
    import openpyxl  # noqa: PLC0415
    seite = abruf(fm.LISTEN_URL).decode("utf-8", errors="replace")
    aus = []
    for url, fonds, periode in fm.eu_listen(seite):
        buch = openpyxl.load_workbook(io.BytesIO(abruf(url)), read_only=True, data_only=True)
        zeilen = list(buch.worksheets[0].iter_rows(values_only=True))
        aus.append((fm.lies_eu(zeilen, fonds=fonds, periode=periode), fonds, periode, url))
    if not aus:
        raise fm.FoerderFehler("Übersichtsseite verlinkt keine Liste der Vorhaben mehr")
    return aus


def _foekat(abruf: Abruf) -> tuple[fm.Lesung, str]:
    abruf(fm.FOEKAT_BASIS + "StartAction.do")
    html = abruf(fm.FOEKAT_BASIS + "SucheAction.do", {
        "actionMode": "searchlist", "suche.detailSuche": "true", "suche.nurVerbund": "N",
        "suche.lfdVhb": "N", "suche.ZeSt": "ZE", "suche.ausdruckSuchParam": "0",
        "suche.gemeindeSuche[0]": fm.FOEKAT_GEMEINDE, "submitAction": "Detailsuche starten",
    }, kodierung="iso-8859-15").decode("iso-8859-15")
    treffer = fm.treffer_aus_seite(html)
    if not treffer:
        raise fm.FoerderFehler(f"Förderkatalog: Suche ohne Trefferzahl ({treffer})")
    url = fm.FOEKAT_BASIS + "SucheAction.do?actionMode=print&presentationType=csv"
    return fm.lies_foekat(abruf(url).decode("iso-8859-15"), treffer), fm.FOEKAT_BASIS + "StartAction.do"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und berichten")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    abruf = Abruf(args.pause)
    listen: list[tuple[fm.Lesung, str, str | None, str, herkunft.Herkunft]] = []
    for lesung, fonds, periode, url in _eu(abruf):
        listen.append((lesung, fonds, periode, url, herkunft.Herkunft(
            kind="eu", probe=[fm.PROBE_EU], url=url,
            label=f"Liste der Vorhaben {fonds.upper()} {periode}",
            citation="Name des Begünstigten, Bezeichnung, Laufzeit, förderfähige Kosten, Unionsbeitrag",
            probe_result=f"{lesung.zeilen} Zeilen gelesen, {len(lesung.vorhaben)} der Stadt",
            as_of=f"Datenstand {lesung.stand}" if lesung.stand else "Liste der Vorhaben")))
    lesung, url = _foekat(abruf)
    listen.append((lesung, "foekat", None, url, herkunft.Herkunft(
        kind="bund", probe=[fm.PROBE_FOEKAT], url=url,
        label="Förderkatalog des Bundes",
        citation=f"Suche nach Gemeinde „{fm.FOEKAT_GEMEINDE}“, Export als Textdatei",
        probe_result=f"{lesung.zeilen} Zeilen = Trefferzahl der Suche, {len(lesung.vorhaben)} der Stadt",
        as_of=f"abgerufen am {time.strftime('%d.%m.%Y')}")))

    alle = [v for l, *_ in listen for v in l.vorhaben]
    for eu, bund in fm.dubletten(alle):
        print(f"  Dublette? {eu.title!r} steht in beiden Listen ({eu.source}, {bund.source_id})")
    store = None if args.trocken else CouncilStore(args.db)
    gespeichert = 0
    for lesung, quelle, periode, url, h in listen:
        summe = sum(v.amount_granted or 0 for v in lesung.vorhaben)
        print(f"  {quelle} {periode or ''}: {lesung.zeilen} Zeilen, {len(lesung.vorhaben)} Vorhaben "
              f"der Stadt, {summe:,.0f} € bewilligt" + (f" · Stand {lesung.stand}" if lesung.stand else ""),
              flush=True)
        for hinweis in lesung.hinweise:
            print(f"    Hinweis: {hinweis}")
        if store is not None:
            gespeichert += store.save_foerdermittel(quelle, periode, lesung.vorhaben,
                                                    list_as_of=lesung.stand, list_url=url, herkunft=h)
    if store is not None:
        store.herkunft_aufraeumen()
        store.close()
    print(f"\n{gespeichert} Vorhaben gespeichert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
