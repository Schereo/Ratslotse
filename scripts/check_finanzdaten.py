#!/usr/bin/env python3
"""Neue Haushalts-Jahrgänge von allein nachziehen (alle zwei Wochen).

Der Haushalts-Bereich lebt von neunzehn Datenschichten (``finanzquellen.
REIHENFOLGE``), die bis 08/2026 alle von Hand eingelesen wurden. Dieser Job
holt die **neun**, die als Anlage im Ratsinformationssystem liegen UND einen
eigenen Leser mitbringen (``einlesen``). Von den zehn übrigen kommen sieben von
außerhalb und haben eigene Wege — ausdrücklich so, denn „lädt nichts herunter"
ist die Regel, an der dieser Job hängt. Die restlichen drei liegen zwar im
Ratsinformationssystem, werden aber von eigenen Skripten eingelesen
(``ingest_wirtschaftsplaene.py``, ``ingest_haushaltssatzung.py``,
``ingest_gebuehren.py``); dieser Job beobachtet sie nur und meldet, wenn ein Jahrgang überfällig wird. Ohne diesen Job veraltet er still, sobald niemand mehr
daran denkt: Die Stadt legt jeden September einen Jahresabschluss und jeden
Oktober einen Haushaltsplan vor, und beides landet ohne Zutun als PDF-Anlage
in ``council_attachments`` — gelesen hat es bloß niemand.

**Der Job ist bestandsgesteuert, nicht kalendergesteuert.** Er fragt nicht
„ist es September?", sondern „welche **Einheit** fehlt mir, und liegt
inzwischen ein Dokument dafür vor?". Damit ist der Takt egal: Ein verspäteter
Jahresabschluss, ein Nachtragshaushalt oder ein nachgereichter Prüfbericht
werden eingesammelt, sobald sie da sind, und der Job darf beliebig oft laufen.

**Einheit, nicht Jahrgang** — das ist der Punkt, an dem die erste Fassung
falsch lag. Ein Produkt-Jahrgang verteilt sich auf rund neun
Teilhaushalts-Anlagen, ein Jahresabschluss auf zwei Ebenen. Und die kommen
**nicht gleichzeitig**: ``check_protocols`` legt eine Anlage ohne Volltext an
(``n_pages=0``), den holt ``backfill_anlagen_texte.py`` erst später und in
Tranchen. Zwischen zwei Läufen liegt also regelmäßig ein Jahrgang, von dem die
Hälfte lesbar ist. Wer je Jahrgang buchführt, sperrt ihn nach dem ersten
Dokument und verliert den Rest für immer — ohne dass irgendetwas auffällt, denn
das Jahr steht ja in der Tabelle.

Drei Regeln, die ihn unbeaufsichtigt tragen:

1. **Er lädt nichts herunter.** Die Anlagen kommen über ``check_protocols.py``
   ins System; hier wird nur ausgelesen, was schon da ist. Zwei Wege zu
   denselben Daten wären ein Weg zu viel.
2. **Er senkt keine Prüfschwelle.** Summenprobe, Strukturprobe, Vorjahres-Kette
   und die Rechenprobe der Erläuterungen gelten unverändert (sie stehen in
   ``council/finanzquellen.py``, gemeinsam mit den Ingest-Skripten). Was sie
   reißt, kommt nicht in die Datenbank, wird gezählt und gemeldet.
3. **Er ergänzt nur, was fehlt — Einheit für Einheit.** Eine vorhandene
   Einheit wird nicht angefasst, und ein leeres oder deutlich geschrumpftes
   Parse-Ergebnis ersetzt nie einen gefüllten Bestand
   (``finanzquellen.bestandsschutz``). Einen verbesserten Parser über den
   **vorhandenen** Bestand zu ziehen bleibt Sache der Ingest-Skripte von Hand
   (dort ``--auch-schrumpfen``).

Was ein Jahrgang bekommt, bekommt er in **einer** Transaktion
(``store.transaktion()``). Ein Abbruch mittendrin ließe ihn sonst halb
zurück — und halb sähe für den nächsten Lauf aus wie fertig.

Gemeldet wird an ``ALERT_EMAIL``, wenn eines von beidem zutrifft:

- ein erwarteter Jahrgang bleibt länger als vier Wochen über seinen üblichen
  Monat hinaus aus, oder
- eine Einheit fehlt weiter, **obwohl** ein Dokument dafür vorliegt. Dieser
  zweite Fall macht keinen Jahrgang überfällig (der steht ja da) und wäre ohne
  die Meldung unsichtbar.

Beides ist kein Fehler, sondern die Frage: Ist die Stadt spät dran, oder greift
ein Erkennungsmuster nicht mehr? Das zweite ist der eigentliche Zweck. Gemeldet
wird nur, wenn sich gegenüber dem letzten Lauf etwas geändert hat; alle
vierzehn Tage dieselbe Mail wäre eine, die niemand mehr liest.

Was der Job **nicht** abdeckt: ``council_budget`` (die Planwerte), die
Open-Data-Schichten (Steuern, Steuerkraft, Einwohner) und den Städtevergleich
(``council_city_comparison``). Sie kommen nicht aus dem
Ratsinformationssystem, sondern per Download von oldenburg.de bzw. vom
Landesamt für Statistik — und Herunterladen ist Regel 1. Ihr Ausbleiben meldet
der Job trotzdem; welches Skript dann dran ist, steht bei der Schicht
(``Finanzquelle.nachschub``). Beim Städtevergleich ist dieser Hinweis der
eigentliche Wert: Die beiden LSN-Tabellen erscheinen nur **einmal im Jahr**
und werden von Hand geholt — eine Handreichung, an die sich nach zwölf Monaten
niemand mehr von selbst erinnert.

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
    return (laeufe[0].get("stats") or {}).get("ausbleibend") == ausbleibend


def _kurz(einheiten: set[tuple]) -> str:
    """Einheiten für das Protokoll: „2024 gesamt, 2025 THH03"."""
    def eine(e: tuple) -> str:
        if len(e) == 1:
            return str(e[0])
        rest = e[1]
        return f"{e[0]} THH{rest:02d}" if isinstance(rest, int) else f"{e[0]} {rest}"
    gereiht = sorted(einheiten, key=lambda e: (e[0], str(e[1:])))
    return ", ".join(eine(e) for e in gereiht[:8]) + (" …" if len(gereiht) > 8 else "")


def _hinweis_text(zeilen: list[dict], gesehen: dict[str, set[int]],
                  rest: dict[str, set[tuple]], heute: date,
                  ohne_herkunft: dict[str, int] | None = None) -> str:
    """Die Mail: was fehlt, seit wann es fällig wäre — und welcher der beiden
    Gründe es ist.

    Der Unterschied trägt die Nachricht. „Kein Dokument da" heißt: Die Stadt
    ist spät dran, abwarten. „Dokument liegt vor, wird aber nicht gelesen"
    heißt: Ein Muster oder ein Parser greift nicht mehr — und genau dafür
    gibt es diesen Job.

    ``rest`` ist der zweite Block: Einheiten, für die ein Dokument vorliegt,
    die nach dem Lauf aber weiter fehlen. Sie machen keinen Jahrgang
    überfällig — der steht ja da — und wären ohne diesen Block unsichtbar.

    ``ohne_herkunft`` ist der dritte: Zeilen, die in der Datenbank stehen,
    aber nicht sagen, woher sie kommen. Sie sind die schlimmste der drei
    Lagen, weil sie **nichts** vermissen lässt — der Jahrgang steht da, die
    Zahl steht da, nur der Beleg fehlt, und auf einer Seite, deren ganzer
    Anspruch „jede Zahl sagt, woher sie stammt" ist, fällt das erst auf, wenn
    jemand auf den Chip tippt."""
    teile = []
    faellige = [(z, j) for z in zeilen for j in z["ueberfaellig"]]
    if faellige:
        teile.append("Im Haushalts-Bereich fehlen Jahrgänge, die inzwischen "
                     "vorliegen müssten:")
    for z, budget_year in faellige:
        q = finanzquellen.QUELLEN[z["key"]]
        faellig = q.faellig_ab(budget_year)
        monat = finanzquellen.MONATE[q.erwarteter_monat]
        if budget_year in gesehen.get(z["key"], set()):
            reason = ("<b>Dokument liegt vor, wird aber nicht übernommen</b> — "
                     "Erkennung oder Parser prüfen")
        elif q.herkunft == "ris":
            reason = "kein passendes Dokument in council_attachments"
        else:
            # Was zu tun ist, weiß die Schicht selbst — hier stand bis 08/2026
            # ein fester Satz über oldenburg.de, und der schickte den Leser
            # bei der Landesstatistik zur falschen Stelle.
            reason = q.nachschub or "wird von Hand eingelesen"
        teile.append(
            f"• <b>{html.escape(q.label)} {budget_year}</b> — üblich im {monat} "
            f"{faellig.year}, seit {(heute - faellig).days} Tagen offen: {reason}")

    if rest:
        if teile:
            teile.append("")
        teile.append("Außerdem stehen Jahrgänge nur teilweise in der Datenbank, "
                     "obwohl ein Dokument dafür vorliegt:")
        for key, offen in rest.items():
            q = finanzquellen.QUELLEN[key]
            teile.append(f"• <b>{html.escape(q.label)}</b> — {len(offen)} Einheit(en) "
                         f"offen: {html.escape(_kurz(offen))}")

    if ohne_herkunft:
        if teile:
            teile.append("")
        teile.append("Außerdem stehen Zeilen in der Datenbank, die nicht sagen, "
                     "woher sie kommen:")
        for tabelle, n in sorted(ohne_herkunft.items()):
            teile.append(f"• <b>{html.escape(tabelle)}</b> — {n} Zeile(n) ohne Herkunft")
        teile.append("Diese Zahlen stehen auf den Seiten ohne Beleg. Meist fehlt der "
                     "Zieltabelle die <code>herkunft_id</code> im Schreibweg "
                     "(siehe council/herkunft.py).")

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
    geschuetzt = neue_einheiten = 0
    rest: dict[str, set[tuple]] = {}

    try:
        for key in finanzquellen.REIHENFOLGE:
            q = finanzquellen.QUELLEN[key]
            vorhanden = q.balance(store)
            if not q.automatisch:
                # Beobachtet, nicht eingelesen: Diese Schicht kommt per
                # Download und bleibt Sache eines Ingest-Skripts von Hand.
                p.sagen(f"{q.label}: {len(finanzquellen.jahrgaenge(vorhanden))} Jahrgänge, "
                        f"kein Selbstlauf ({q.nachschub})")
                continue

            # Gefragt wird nach EINHEITEN, nicht nach Jahrgängen: Ein
            # Produkt-Jahrgang steckt in rund neun Anlagen, ein Jahresabschluss
            # in zwei Ebenen. „Jahr ist da" hieße sonst „Jahr ist fertig" —
            # und der Rest käme nie nach.
            kandidaten = q.kandidaten(store)
            moeglich: set[tuple] = set()
            for r in kandidaten:
                moeglich |= r["einheiten"]
            gesehen[key] = {e[0] for e in moeglich}
            offen = moeglich - vorhanden
            if not offen:
                p.sagen(f"{q.label}: nichts Neues "
                        f"({len(vorhanden)} Einheiten, {len(kandidaten)} Dokumente geprüft)")
                continue

            p.sagen(f"{q.label}: {len(offen)} fehlende Einheit(en) mit Dokument "
                    f"({_kurz(offen)}) — wird eingelesen")
            if trocken:
                continue
            bericht = q.einlesen(store, p, nur_fehlende=True)
            geschuetzt += bericht.get("bestand_geschuetzt", 0)
            gewonnen = {tuple(e) for e in (bericht.get("neue_einheiten") or [])}
            if gewonnen:
                neu_gesamt[key] = sorted({e[0] for e in gewonnen})
            neue_einheiten += len(gewonnen)
            nicht_gepackt = offen - gewonnen
            if nicht_gepackt:
                # Kein Fehler: Ein Dokument, das die Proben nicht besteht, ist
                # genau der Fall, für den es die Proben gibt. Aber es gehört
                # gezählt — sonst versickert es im Log.
                p.warnen(f"  {q.label}: {len(nicht_gepackt)} Einheit(en) nicht übernommen "
                         f"({_kurz(nicht_gepackt)}) — Probe gerissen oder Dokument unlesbar")

        # Herkunft aufräumen und nachzählen. Ein Jahrgang, der neu eingelesen
        # wurde, hat seine alten Herkunfts-Datensätze abgelöst; und eine
        # Zieltabelle, die ihre `herkunft_id` nicht füllt, soll auffallen,
        # bevor jemand sie auf der Seite als Beleg vermisst.
        if not trocken:
            store.herkunft_aufraeumen()
        ohne_herkunft = store.herkunft_luecken()

        as_of = finanzquellen.datenstand(store, heute)
        # Nach dem Lauf noch offen: Einheiten, für die ein Dokument vorliegt,
        # die aber nicht in die Datenbank gekommen sind. Das ist der Teil, den
        # niemand von selbst bemerkt — ein Jahrgang, der halb dasteht, sieht
        # in jeder Jahresliste aus wie ein ganzer.
        for key in finanzquellen.REIHENFOLGE:
            q = finanzquellen.QUELLEN[key]
            if q.automatisch:
                offen_nachher = q.offene_einheiten(store)
                if offen_nachher:
                    rest[key] = offen_nachher
    finally:
        store.close()

    for z in as_of:
        if z["ueberfaellig"]:
            p.warnen(f"  {z['label']}: {', '.join(map(str, z['ueberfaellig']))} überfällig")
    for key, offen in rest.items():
        p.warnen(f"  {finanzquellen.QUELLEN[key].label}: {len(offen)} Einheit(en) weiter "
                 f"offen, obwohl ein Dokument vorliegt ({_kurz(offen)})")
    for tabelle, n in ohne_herkunft.items():
        p.warnen(f"  {tabelle}: {n} Zeile(n) ohne Herkunft — die Tabelle sagt nicht, "
                 f"woher sie kommen (siehe council/herkunft.py)")

    # Der Vergleichsschlüssel für „habe ich das schon gemeldet?" — überfällige
    # Jahrgänge, liegengebliebene Einheiten UND Zeilen ohne Herkunft. Ohne den
    # zweiten Teil bliebe ein halb gelesener Jahrgang für immer stumm.
    #
    # Der dritte Teil fehlte bis 20.08.2026, und das war die stillste Lücke des
    # Jobs: `herkunft_luecken()` wurde gerufen, ins Log geschrieben und als
    # Kennzahl nach `job_runs` gereicht — aber weil er nicht in `ausbleibend`
    # stand, löste er nie eine Mail aus. Ein Cron-Log liest niemand freiwillig;
    # der Code nennt diesen Befund selbst das „Frühwarnsystem der Umstellung"
    # (council/store.py), und ein Frühwarnsystem, das nur flüstert, ist keines.
    #
    # Die Zahl gehört mit in den Schlüssel, nicht nur der Tabellenname: Wächst
    # die Lücke von 3 auf 300 Zeilen, ist das eine neue Nachricht und keine
    # Wiederholung.
    ausbleibend = sorted(
        [f"{z['key']}:{j}" for z in as_of for j in z["ueberfaellig"]]
        + [f"{key}:offen:{e}" for key, offen in rest.items() for e in sorted(map(str, offen))]
        + [f"herkunft:{tabelle}:{n}" for tabelle, n in ohne_herkunft.items()])

    gemeldet = False
    if ausbleibend and not trocken and not _schon_gemeldet(ausbleibend):
        from kern.alerts import notify_admin

        notify_admin(_hinweis_text(as_of, gesehen, rest, heute, ohne_herkunft),
                     betreff="Ratslotse – Haushaltsdaten: es fehlt etwas",
                     fusszeile="Hinweis des Cron-Jobs check_finanzdaten — kein Fehler.")
        gemeldet = True

    result = {
        "Neue Jahrgänge": sum(len(v) for v in neu_gesamt.values()),
        "Neue Einheiten": neue_einheiten,
        "Bestand geschützt": geschuetzt,
        "Hinweis verschickt": 1 if gemeldet else 0,
        "Zeilen ohne Herkunft": sum(ohne_herkunft.values()),
        "ausbleibend": ausbleibend,
    }
    for key, years in neu_gesamt.items():
        result[finanzquellen.QUELLEN[key].label] = ", ".join(map(str, years))
    p.sagen(f"Fertig: {result}")
    # Das Protokoll bleibt im Log, nicht in `job_runs`: Die Kennzahlen eines
    # Laufs stehen im Admin-Panel, und dort gehört keine Textwand hin.
    return result


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Neue Haushalts-Jahrgänge nachziehen")
    ap.add_argument("--db", default=None)
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was der Lauf täte")
    ap.add_argument("--heute", default=None,
                    help="Stichtag JJJJ-MM-TT (nur zum Prüfen der Fälligkeiten)")
    args = ap.parse_args()
    as_of_date = date.fromisoformat(args.heute) if args.heute else None
    main(db=args.db, heute=as_of_date, trocken=args.trocken)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_cli())
    from kern.alerts import run_guarded

    run_guarded(JOB, main)
