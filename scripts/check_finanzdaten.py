#!/usr/bin/env python3
"""Neue Haushalts-Jahrgänge von allein nachziehen (alle zwei Wochen).

Der Haushalts-Bereich lebt von fünf Datenschichten, die bis 08/2026 alle von
Hand eingelesen wurden. Ohne diesen Job veraltet er still, sobald niemand mehr
daran denkt: Die Stadt legt jeden September einen Jahresabschluss und jeden
Oktober einen Haushaltsplan vor, und beides landet ohne Zutun als PDF-Anlage
in ``council_anlagen`` — gelesen hat es bloß niemand.

**Der Job ist bestandsgesteuert, nicht kalendergesteuert.** Er fragt nicht
„ist es September?", sondern „welcher Jahrgang fehlt mir, und liegt inzwischen
ein Dokument dafür vor?". Damit ist der Takt egal: Ein verspäteter
Jahresabschluss, ein Nachtragshaushalt oder ein nachgereichter Prüfbericht
werden eingesammelt, sobald sie da sind, und der Job darf beliebig oft laufen.

Drei Regeln, die ihn unbeaufsichtigt tragen:

1. **Er lädt nichts herunter.** Die Anlagen kommen über ``check_protocols.py``
   ins System; hier wird nur ausgelesen, was schon da ist. Zwei Wege zu
   denselben Daten wären ein Weg zu viel.
2. **Er senkt keine Prüfschwelle.** Summenprobe, Strukturprobe, Vorjahres-Kette
   und die Rechenprobe der Erläuterungen gelten unverändert (sie stehen in
   ``council/finanzquellen.py``, gemeinsam mit den Ingest-Skripten). Was sie
   reißt, kommt nicht in die Datenbank, wird gezählt und gemeldet.
3. **Er ergänzt nur, was fehlt.** Ein vorhandener Jahrgang wird nicht angefasst
   — und ein leeres oder deutlich geschrumpftes Parse-Ergebnis ersetzt nie
   einen gefüllten Bestand (``finanzquellen.bestandsschutz``). Einen
   verbesserten Parser über den Bestand zu ziehen bleibt Sache der
   Ingest-Skripte von Hand.

Bleibt ein erwarteter Jahrgang länger als vier Wochen über seinen üblichen
Monat hinaus aus, geht ein **Hinweis** an ``ALERT_EMAIL`` — kein Fehler,
sondern die Frage: Ist die Stadt spät dran, oder greift ein Erkennungsmuster
nicht mehr? Das zweite ist der eigentliche Zweck. Gemeldet wird nur, wenn sich
gegenüber dem letzten Lauf etwas geändert hat; alle vierzehn Tage dieselbe
Mail wäre eine, die niemand mehr liest.

Was der Job **nicht** abdeckt: ``council_haushalt`` (die Planwerte) und die
Open-Data-Schichten (Steuern, Steuerkraft, Einwohner). Sie kommen nicht aus
dem Ratsinformationssystem, sondern per Download von oldenburg.de — und
Herunterladen ist Regel 1. Ihr Ausbleiben meldet der Job trotzdem, damit
``scripts/ingest_haushalt.py`` nicht vergessen wird.

Crontab (Server), alle zwei Wochen sonntags::

    30 4 * * 0  [ $(( ($(date +\\%s) / 604800) \\% 2 )) -eq 0 ] && … scripts/check_finanzdaten.py

Von Hand::

    python scripts/check_finanzdaten.py [--db data/council.sqlite] [--trocken]
"""
from __future__ import annotations

import argparse
import html
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"

JOB = "check_finanzdaten"


def _schon_gemeldet(ausbleibend: list[str]) -> bool:
    """Stand dieselbe Liste schon im letzten Lauf?

    Der Hinweis ist eine Nachricht, keine Wiedervorlage: Solange sich nichts
    ändert, schweigt der Job. Der Vergleichsstand kommt aus ``job_runs`` —
    dafür braucht es keine eigene Tabelle, run_guarded schreibt ihn ohnehin."""
    try:
        from kern.store import Store

        db = Path(os.environ.get("NWZ_DB") or ROOT / "data" / "nwz.sqlite")
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
    return (laeufe[0].get("stats") or {}).get("ausbleibend") == ausbleibend


def _hinweis_text(zeilen: list[dict], gesehen: dict[str, set[int]], heute: date) -> str:
    """Die Mail: was fehlt, seit wann es fällig wäre — und welcher der beiden
    Gründe es ist.

    Der Unterschied trägt die Nachricht. „Kein Dokument da" heißt: Die Stadt
    ist spät dran, abwarten. „Dokument liegt vor, wird aber nicht gelesen"
    heißt: Ein Muster oder ein Parser greift nicht mehr — und genau dafür
    gibt es diesen Job."""
    teile = ["Im Haushalts-Bereich fehlen Jahrgänge, die inzwischen vorliegen müssten:"]
    for z in zeilen:
        q = finanzquellen.QUELLEN[z["key"]]
        for jahrgang in z["ueberfaellig"]:
            faellig = q.faellig_ab(jahrgang)
            monat = finanzquellen.MONATE[q.erwarteter_monat]
            if jahrgang in gesehen.get(z["key"], set()):
                grund = ("<b>Dokument liegt vor, wird aber nicht übernommen</b> — "
                         "Erkennung oder Parser prüfen")
            elif q.herkunft == "ris":
                grund = "kein passendes Dokument in council_anlagen"
            else:
                grund = "Download von oldenburg.de, scripts/ingest_haushalt.py"
            teile.append(
                f"• <b>{html.escape(q.label)} {jahrgang}</b> — üblich im {monat} "
                f"{faellig.year}, seit {(heute - faellig).days} Tagen offen: {grund}")
    teile.append("")
    teile.append("Der Job hat nichts gelöscht und nichts verändert. Die Muster stehen "
                 "in council/finanzquellen.py.")
    return "\n".join(teile)


def main(db: str | None = None, heute: date | None = None,
         trocken: bool = False, still: bool = False,
         protokoll: finanzquellen.Protokoll | None = None) -> dict:
    """Ein Lauf. ``protokoll`` nur für Tests — im Betrieb spricht der Job nach
    stdout/stderr, und was er sagt, steht im Cron-Log."""
    heute = heute or date.today()
    store = CouncilStore(Path(db or COUNCIL_DB))
    p = protokoll or finanzquellen.Protokoll(still=still)
    neu_gesamt: dict[str, list[int]] = {}
    #: Welche Jahrgänge als Dokument vorliegen — trennt in der Meldung „die
    #: Stadt ist spät dran" von „wir lesen es nicht mehr".
    gesehen: dict[str, set[int]] = {}
    geschuetzt = 0

    try:
        for key in finanzquellen.REIHENFOLGE:
            q = finanzquellen.QUELLEN[key]
            vorhanden = set(q.bestand(store))
            if not q.automatisch:
                # Beobachtet, nicht eingelesen: Diese Schicht kommt per
                # Download und bleibt Sache von ingest_haushalt.py.
                p.sagen(f"{q.label}: {len(vorhanden)} Jahrgänge, kein Selbstlauf "
                        f"(Quelle: oldenburg.de)")
                continue

            kandidaten = q.kandidaten(store)
            gesehen[key] = {r["jahrgang"] for r in kandidaten if r["jahrgang"]}
            offen = sorted(gesehen[key] - vorhanden)
            if not offen:
                p.sagen(f"{q.label}: nichts Neues "
                        f"({len(vorhanden)} Jahrgänge, {len(kandidaten)} Dokumente geprüft)")
                continue

            p.sagen(f"{q.label}: Dokument(e) für {', '.join(map(str, offen))} gefunden — "
                    f"wird eingelesen")
            if trocken:
                continue
            bericht = q.einlesen(store, p, nur_fehlende=True)
            geschuetzt += bericht.get("bestand_geschuetzt", 0)
            gewonnen = sorted(set(bericht.get("neue_jahrgaenge") or []))
            if gewonnen:
                neu_gesamt[key] = gewonnen
            nicht_gepackt = [j for j in offen if j not in gewonnen]
            if nicht_gepackt:
                # Kein Fehler: Ein Dokument, das die Proben nicht besteht, ist
                # genau der Fall, für den es die Proben gibt. Aber es gehört
                # gezählt — sonst versickert es im Log.
                p.warnen(f"  {q.label}: {', '.join(map(str, nicht_gepackt))} nicht "
                         f"übernommen (Probe gerissen oder Dokument unlesbar)")

        stand = finanzquellen.datenstand(store, heute)
    finally:
        store.close()

    ausbleibend = sorted(f"{z['key']}:{j}" for z in stand for j in z["ueberfaellig"])
    for z in stand:
        if z["ueberfaellig"]:
            p.warnen(f"  {z['label']}: {', '.join(map(str, z['ueberfaellig']))} überfällig")

    gemeldet = False
    if ausbleibend and not trocken and not _schon_gemeldet(ausbleibend):
        from kern.alerts import notify_admin

        notify_admin(_hinweis_text(stand, gesehen, heute),
                     betreff="Ratslotse – Haushaltsdaten: ein Jahrgang fehlt",
                     fusszeile="Hinweis des Cron-Jobs check_finanzdaten — kein Fehler.")
        gemeldet = True

    ergebnis = {
        "Neue Jahrgänge": sum(len(v) for v in neu_gesamt.values()),
        "Bestand geschützt": geschuetzt,
        "Hinweis verschickt": 1 if gemeldet else 0,
        "ausbleibend": ausbleibend,
    }
    for key, jahre in neu_gesamt.items():
        ergebnis[finanzquellen.QUELLEN[key].label] = ", ".join(map(str, jahre))
    p.sagen(f"Fertig: {ergebnis}")
    # Das Protokoll bleibt im Log, nicht in `job_runs`: Die Kennzahlen eines
    # Laufs stehen im Admin-Panel, und dort gehört keine Textwand hin.
    return ergebnis


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Neue Haushalts-Jahrgänge nachziehen")
    ap.add_argument("--db", default=None)
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was der Lauf täte")
    ap.add_argument("--heute", default=None,
                    help="Stichtag JJJJ-MM-TT (nur zum Prüfen der Fälligkeiten)")
    args = ap.parse_args()
    stichtag = date.fromisoformat(args.heute) if args.heute else None
    main(db=args.db, heute=stichtag, trocken=args.trocken)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_cli())
    from kern.alerts import run_guarded

    run_guarded(JOB, main)
