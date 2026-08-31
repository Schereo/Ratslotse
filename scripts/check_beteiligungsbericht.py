#!/usr/bin/env python3
"""Den Beteiligungsbericht von oldenburg.de nachziehen (alle vier Wochen).

Der zweite Cron des Haushalts-Bereichs — und der erste, der **selbst ins Netz
greift**. ``check_finanzdaten`` tut das ausdrücklich nicht: Seine Dokumente
hängen als Anlagen an Ratsvorlagen und werden vom Protokoll-Scraper ohnehin
geholt; ein zweiter Weg dorthin wäre ein Weg zu viel.

Der Beteiligungsbericht hängt an keiner Vorlage. Er steht auf oldenburg.de,
und wer ihn haben will, lädt ihn herunter. Das ist eine andere Sorte Arbeit —
sie fasst ein fremdes System an, sie kann von außen scheitern, und sie hat
sich zu benehmen. Sie in den bestehenden Job zu quetschen hieße, dessen
klarste Regel aufzuweichen; deshalb ein eigener Job, ein eigener Takt und mit
``council/stadtdownload.py`` eine eigene, geprüfte Netzseite.

Was ein Lauf tut
-----------------
1. Die Übersichtsseite holen und die Berichts-PDFs daraus lesen. **Nicht** aus
   einer fest verdrahteten Liste: Der Dateiname wechselt zwischen den
   Jahrgängen (``Beteiligungsbericht_2021.pdf`` gegen
   ``Beteiligungsbericht_2024_kombiniert_final.pdf``), und eine geratene URL
   fände den nächsten Bericht nie.
2. Jedes PDF nur holen, wenn es sich geändert hat (``If-Modified-Since``).
   Sieben Berichte sind 25 MB; sie alle vier Wochen erneut zu ziehen wäre
   Verschwendung auf einem fremden Server.
3. Alle vorliegenden Berichte lesen, prüfen, den Bestand ersetzen
   (``council/beteiligungsbericht.einlesen``). Immer alle — die
   Überlappungsprobe vergleicht Berichte miteinander.

Warum „alle vier Wochen" und nicht täglich: Der Bericht erscheint **einmal im
Jahr**, gemessen im zweiten Folgejahr zwischen Januar und Juni
(``council/finanzquellen.py``). Ein Takt, der schneller ist als die Quelle,
fragt nur öfter dasselbe.

Der Job ist **bestandsgesteuert**, nicht kalendergesteuert: Er fragt nicht „ist
es Juni?", sondern „liegt auf der Seite ein Bericht, den ich noch nicht habe?".
Ein verspäteter Jahrgang wird eingesammelt, sobald er da ist, und der Job darf
beliebig oft laufen.

Was er nie tut
---------------
Einen gefüllten Bestand gegen ein leeres oder deutlich kleineres Ergebnis
tauschen (``finanzquellen.bestandsschutz``). Ändert die Stadt den Aufbau des
Berichts, liefert der Parser irgendwann null Zeilen — und das sieht für einen
unbeaufsichtigten Lauf aus wie „es gibt nichts". Gemeldet wird es, ersetzt
nicht.

Und er senkt keine Prüfschwelle. Was die Bilanz-, die Ergebnis- oder die
Überlappungsprobe reißt, kommt nicht in die Datenbank, wird gezählt und
gemeldet.

Gemeldet wird an ``ALERT_EMAIL``, wenn ein Bericht überfällig ist, wenn sich
zwei Berichte widersprechen oder wenn ein Download scheitert — und nur, wenn
sich gegenüber dem letzten Lauf etwas geändert hat. Alle vier Wochen dieselbe
Mail wäre eine, die niemand mehr liest.

Crontab (Server), alle vier Wochen sonntags::

    45 4 * * 0  [ $(( ($(date +\\%s) / 604800) \\% 4 )) -eq 1 ] && … scripts/check_beteiligungsbericht.py

Von Hand::

    python scripts/check_beteiligungsbericht.py [--db …] [--trocken] [--auch-schrumpfen]
"""
from __future__ import annotations

import argparse
import html
import io
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import beteiligungsbericht, finanzquellen, stadtdownload  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"

JOB = "check_beteiligungsbericht"

#: Die Übersichtsseite der Stadt. Der einzige fest verdrahtete Pfad — die
#: Dokumentadressen darunter wechseln von Jahrgang zu Jahrgang und werden aus
#: der Seite gelesen.
UEBERSICHT = (f"{stadtdownload.BASE}/startseite/politik/verwaltung-finanzen/"
              f"finanzen/beteiligungsbericht.html")


def _schon_gemeldet(befund: list[str]) -> bool:
    """Stand derselbe Befund schon im letzten Lauf?

    Wie bei ``check_finanzdaten``: Der Hinweis ist eine Nachricht, keine
    Wiedervorlage. Der Vergleichsstand kommt aus ``job_runs`` — dafür braucht
    es keine eigene Tabelle, ``run_guarded`` schreibt ihn ohnehin."""
    try:
        from kern.store import Store

        db = Path(os.environ.get("RATSLOTSE_DB") or ROOT / "data" / "ratslotse.sqlite")
        if not db.exists():
            return False
        store = Store(db)
        try:
            laeufe = store.job_runs(job=JOB, limit=1)
        finally:
            store.close()
    except Exception:  # noqa: BLE001 — ohne Historie lieber einmal zu viel melden
        return False
    if not laeufe:
        return False
    return (laeufe[0].get("stats") or {}).get("befund") == befund


def _seiten(inhalt: bytes) -> list[str]:
    """PDF → Text, **seitenweise**.

    Die Seitengrenzen sind hier keine Formatierung, sondern die Grundlage der
    Zuordnung: Eine Gesellschaft beginnt auf ihrer Trennseite, und welche das
    ist, sagt das Inhaltsverzeichnis (s. ``beteiligungsbericht.gliederung``).
    Ein zusammengeklebter Volltext verlöre genau die Information, mit der sich
    Abschnitt und Gesellschaft überhaupt verknüpfen lassen."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(inhalt))
    return [(seite.extract_text() or "") for seite in reader.pages]


def _hinweis_text(fehlend: list[int], fehler: list[str], widersprueche: int,
                  heute: date) -> str:
    q = finanzquellen.QUELLEN["beteiligungsbericht"]
    teile: list[str] = []
    for jahrgang in fehlend:
        faellig = q.faellig_ab(jahrgang)
        teile.append(
            f"• <b>Beteiligungsbericht {jahrgang}</b> — üblich bis "
            f"{finanzquellen.MONATE[q.erwarteter_monat]} {faellig.year}, seit "
            f"{(heute - faellig).days} Tagen offen: auf oldenburg.de liegt "
            f"kein Bericht dafür")
    if fehler:
        if teile:
            teile.append("")
        teile.append("Beim Abruf ist etwas schiefgegangen:")
        teile += [f"• {html.escape(f)}" for f in fehler]
    if widersprueche:
        if teile:
            teile.append("")
        teile.append(
            f"<b>{widersprueche} Kennzahl(en)</b> stehen in zwei Berichten mit "
            f"verschiedenen Werten. Beide wurden verworfen — welcher stimmt, "
            f"sagt die Probe nicht.")
    teile.append("")
    teile.append("Der Job hat nichts gelöscht und nichts geschätzt. Die Muster "
                 "stehen in council/beteiligungsbericht.py.")
    return "\n".join(teile)


def main(db: str | None = None, heute: date | None = None, trocken: bool = False,
         still: bool = False, schuetzen: bool = True,
         protokoll: finanzquellen.Protokoll | None = None,
         uebersicht_html: str | None = None) -> dict:
    """Ein Lauf. ``uebersicht_html`` und ``protokoll`` nur für Tests."""
    heute = heute or date.today()
    p = protokoll or finanzquellen.Protokoll(still=still)
    store = CouncilStore(Path(db or COUNCIL_DB))
    fehler: list[str] = []
    result: dict = {"gesellschaften": 0, "texte": 0, "kennzahlen": 0,
                      "personen": 0, "eigentuemer": 0, "ohne_zuordnung": 0,
                      "verworfen": 0, "widersprueche": 0, "bestand_geschuetzt": 0,
                      "jahrgaenge": [], "konzernvergleich": 0}
    try:
        if uebersicht_html is None:
            uebersicht_html = stadtdownload.uebersicht(UEBERSICHT)
        links = stadtdownload.berichtslinks(uebersicht_html)
        if not links:
            # Kein Absturz, aber ein Befund: Die Seite gibt es, nur stehen
            # keine Berichte mehr darauf. Das ist der Fall, für den es diesen
            # Job gibt — und er darf den Bestand nicht anfassen.
            p.warnen("  Übersichtsseite trägt keine Berichts-PDFs mehr — "
                     "Aufbau geändert? Bestand bleibt unangetastet")
            fehler.append("Übersichtsseite ohne Berichts-PDFs: " + UEBERSICHT)
            links = []
        p.sagen(f"Übersicht: {len(links)} Bericht(e) verlinkt "
                f"({', '.join(str(j) for j, _ in links) or '—'})")

        dokumente: dict[int, dict] = {}
        sitzung = None
        for year, url in links:
            if year < beteiligungsbericht.ERSTER_JAHRGANG:
                # Kein Fehler, sondern die dokumentierte Grenze: Vor 2022 ist
                # der Bericht anders aufgebaut und nicht maschinenlesbar.
                p.sagen(f"  {year}: vor dem Formatbruch "
                        f"{beteiligungsbericht.ERSTER_JAHRGANG} — übersprungen")
                continue
            if trocken:
                p.sagen(f"  {year}: würde {url} laden")
                continue
            try:
                if sitzung is not None:
                    stadtdownload.warte()
                import requests

                sitzung = sitzung or requests.Session()
                sitzung.headers["User-Agent"] = stadtdownload.USER_AGENT
                dok = stadtdownload.hole(url, session=sitzung)
            except stadtdownload.DownloadFehler as exc:
                # Ein Dokument, das gerade nicht zu holen ist, beendet den Lauf
                # nicht: Die übrigen sind trotzdem lesbar, und der Bestand
                # bleibt vollständig, solange die Proben aufgehen.
                p.warnen(f"  {year}: {exc}")
                fehler.append(str(exc))
                continue
            dokumente[year] = {
                "seiten": _seiten(dok.inhalt), "url": url,
                "label": f"Beteiligungsbericht {year} (oldenburg.de)"}
            p.sagen(f"  {year}: {len(dok.inhalt) / 1e6:.1f} MB, "
                    f"{len(dokumente[year]['seiten'])} Seiten")

        if dokumente and not trocken:
            result = beteiligungsbericht.einlesen(store, dokumente, p, schuetzen)
            store.herkunft_aufraeumen()
        vorhanden = sorted(store.beteiligungsbericht_jahre())
        ohne_herkunft = store.herkunft_luecken()
    finally:
        store.close()

    q = finanzquellen.QUELLEN["beteiligungsbericht"]
    neuester = q.neuester_erwarteter(heute)
    verlinkt = {j for j, _ in links}
    # Überfällig ist ein Jahrgang nur, wenn er auch auf der Seite fehlt: Liegt
    # er dort und ist trotzdem nicht im Bestand, ist das kein Wartefall,
    # sondern ein Parser-Fall — und der steht schon als Warnung im Protokoll.
    fehlend = [j for j in range(beteiligungsbericht.ERSTER_JAHRGANG, neuester + 1)
               if j not in vorhanden and j not in verlinkt
               and heute - q.faellig_ab(j) > finanzquellen.KARENZ]

    for j in fehlend:
        p.warnen(f"  Beteiligungsbericht {j} fehlt und ist überfällig")
    for tabelle, n in ohne_herkunft.items():
        p.warnen(f"  {tabelle}: {n} Zeile(n) ohne Herkunft — die Tabelle sagt "
                 f"nicht, woher sie kommen (siehe council/herkunft.py)")

    befund = sorted([f"fehlt:{j}" for j in fehlend] + [f"fehler:{f}" for f in fehler]
                    + ([f"widerspruch:{result['widersprueche']}"]
                       if result["widersprueche"] else []))
    gemeldet = False
    if befund and not trocken and not _schon_gemeldet(befund):
        from kern.alerts import notify_admin

        notify_admin(
            _hinweis_text(fehlend, fehler, result["widersprueche"], heute),
            betreff="Ratslotse – Beteiligungsbericht: es fehlt etwas",
            fusszeile="Hinweis des Cron-Jobs check_beteiligungsbericht — kein Fehler.")
        gemeldet = True

    aus = {
        "Berichte gelesen": len(result["jahrgaenge"]),
        "Gesellschaften": result["gesellschaften"],
        "Textabschnitte": result["texte"],
        "Kennzahlen": result["kennzahlen"],
        "Aufsichtspersonen": result.get("personen", 0),
        "Eigentümer": result.get("eigentuemer", 0),
        # Wie oft die Spaltenprobe der Aufsichtsorgane gerissen ist. Kein
        # Fehler, sondern eine Eigenschaft des Dokuments: Dort führt der
        # Bericht mehr Namen als Ämter, und dann steht bei dieser
        # Gesellschaft an keinem Namen ein Amt.
        "Ämter nicht zuordenbar": result.get("ohne_zuordnung", 0),
        "Ohne Probe verworfen": result["verworfen"],
        "Widersprüche": result["widersprueche"],
        "Auch im Gesamtabschluss": result.get("konzernvergleich", 0),
        "Bestand geschützt": result["bestand_geschuetzt"],
        "Download-Fehler": len(fehler),
        "Hinweis verschickt": 1 if gemeldet else 0,
        "Zeilen ohne Herkunft": sum(ohne_herkunft.values()),
        "befund": befund,
    }
    p.sagen(f"Fertig: {aus}")
    return aus


def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="Beteiligungsbericht von oldenburg.de nachziehen")
    ap.add_argument("--db", default=None)
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was der Lauf täte — lädt nichts")
    ap.add_argument("--heute", default=None,
                    help="Stichtag JJJJ-MM-TT (nur zum Prüfen der Fälligkeit)")
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="einen kleineren Bestand auf Ansage trotzdem übernehmen "
                         "(für einen verbesserten Parser von Hand)")
    args = ap.parse_args()
    main(db=args.db, trocken=args.trocken,
         heute=date.fromisoformat(args.heute) if args.heute else None,
         schuetzen=not args.auch_schrumpfen)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_cli())
    from kern.alerts import run_guarded

    run_guarded(JOB, main)
