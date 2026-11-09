#!/usr/bin/env python3
"""Hält das Plan-Register (`council/plans.py`) gegen den Bestand.

``tests/test_plaene_register.py`` prüft die Form ohne Datenbank. Was nur der
Bestand weiß, steht hier:

- **Fehler:** Eine Vorlagennummer gibt es nicht; ein Beschluss steht nicht
  an Datum und Gremium, die das Register nennt; „beschlossen“ steht dort, wo
  der Rat nur zur Kenntnis genommen hat (und umgekehrt); eine Berichtsreihe
  trifft keinen einzigen Tagesordnungspunkt.
- **Hinweise:** Ein Plan ist über sein Ende hinaus, ohne dass ein Nachfolger
  im Register steht. Das ist kein Fehler im Register — vielleicht hat die
  Stadt nicht fortgeschrieben —, aber jemand sollte nachsehen.

Aufruf::

    python scripts/pruefe_plaene.py                     # data/council.sqlite
    python scripts/pruefe_plaene.py pfad/zur/council.sqlite

Liest nur (``mode=ro``). Exit 1 bei einem Fehler, Hinweise allein lassen ihn
bei 0.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plan_state, plans  # noqa: E402

#: Ergebnisse, die zu „beschlossen“ passen. „noted“ gehört zu ``mode="noted"``;
#: ein „accepted“ mit „zur Kenntnis genommen“ im Text auch (der Rat nimmt
#: zur Kenntnis und erteilt zugleich einen Auftrag).
_ANGENOMMEN = {"accepted"}


@dataclass(frozen=True)
class Befund:
    plan: str
    schwere: str  # "fehler" | "hinweis"
    text: str

    def __str__(self) -> str:
        return f"[{self.schwere}] {self.plan}: {self.text}"


def _ende_als_datum(wert: str) -> str:
    """``"2025"`` → ``"2025-12-31"``; ``"2029-09"`` → ``"2029-09-31"`` (reicht zum Vergleichen)."""
    teile = wert.split("-")
    if len(teile) == 1:
        return f"{wert}-12-31"
    if len(teile) == 2:
        return f"{wert}-31"
    return wert


def _pruefe_beschluss(conn: sqlite3.Connection, plan: plans.Plan, d: plans.Decision) -> list[Befund]:
    if d.template is None:
        return []
    zeilen = conn.execute(
        """select d.template_number, d.outcome, coalesce(d.official_text, '')
           from council_decisions d join council_sessions s on s.ksinr = d.ksinr
           where s.session_date = ? and s.committee = ?
             and (d.template_number = ? or d.template_number like ? || '/%'
                  or ? like d.template_number || '/%')""",
        (d.date, d.committee, d.template, plans.template_stem(d.template), d.template),
    ).fetchall()
    if not zeilen:
        return [Befund(plan.key, "fehler",
                       f"kein Beschluss zu {d.template} am {d.date} im Gremium {d.committee!r}")]
    befunde = []
    exakt = [z for z in zeilen if z[0] == d.template]
    if not exakt:
        befunde.append(Befund(plan.key, "fehler",
                              f"am {d.date} lag {zeilen[0][0]} vor, nicht {d.template}"))
    _, outcome, text = (exakt or zeilen)[0]
    kenntnis = "zur Kenntnis genommen" in text
    if d.mode == "adopted" and (outcome not in _ANGENOMMEN or kenntnis):
        befunde.append(Befund(plan.key, "fehler",
                              f"{d.template} am {d.date}: Register sagt „beschlossen“, "
                              f"Bestand sagt {outcome!r}{' mit Kenntnisnahme' if kenntnis else ''}"))
    if d.mode == "noted" and outcome not in ("noted",) and not kenntnis:
        befunde.append(Befund(plan.key, "fehler",
                              f"{d.template} am {d.date}: Register sagt „zur Kenntnis“, "
                              f"Bestand sagt {outcome!r}"))
    return befunde


def pruefe(conn: sqlite3.Connection, heute: str | None = None) -> list[Befund]:
    heute = heute or date.today().isoformat()
    befunde: list[Befund] = []
    vorlagen = {r[0] for r in conn.execute("select template_number from council_templates")}
    titel = [r[0] for r in conn.execute(
        "select title from council_agenda_items union all select title from council_templates")]

    for plan in plans.PLANS.values():
        for nummer in plans.all_templates(plan):
            if nummer not in vorlagen:
                befunde.append(Befund(plan.key, "fehler", f"Vorlage {nummer} gibt es im Bestand nicht"))
        for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions:
            befunde.extend(_pruefe_beschluss(conn, plan, d))
        if not any(plans.matches_title(plan, t) for t in titel):
            befunde.append(Befund(plan.key, "fehler",
                                  f"kein Titel trifft die Berichtsmuster {plan.report_patterns}"))
        for muster in plan.implementation_patterns:
            if not any(muster_trifft(muster, t) for t in titel):
                befunde.append(Befund(plan.key, "fehler", f"Umsetzungsmuster {muster!r} trifft nichts"))
        if plan.end and _ende_als_datum(plan.end) < heute and not plan.successor and not plan.concluded:
            befunde.append(Befund(plan.key, "hinweis",
                                  f"Laufzeit bis {plan.end} ist vorbei, ohne Nachfolger oder Auswertung"))
        if plan.review_due and _ende_als_datum(plan.review_due) < heute and not plan.successor:
            befunde.append(Befund(plan.key, "hinweis",
                                  f"Überprüfung war bis {plan.review_due} vorgesehen"))
    befunde.extend(_pruefe_stand(conn))
    return befunde


def _pruefe_stand(conn: sqlite3.Connection) -> list[Befund]:
    """Neuer Bericht, alter Stand: Die Statusdateien (``council/plan_status/``) wachsen
    nicht von selbst. Liegt der jüngste Bericht einer Reihe hinter der jüngsten
    Momentaufnahme, ist ``scripts/plan_status.py`` dran."""
    befunde: list[Befund] = []
    for key in plan_state.keys():
        stand = plan_state.city_status(key)
        if key not in plans.PLANS or not stand:
            continue
        try:
            bericht = conn.execute(
                "select max(date) from council_plan_items where plan_key = ? and role in ('report', 'evaluation')",
                (key,)).fetchone()[0]
        except sqlite3.OperationalError:  # Zuordnung noch nie gebaut
            return befunde
        bis = plan_state.period_end(stand["latest"]["as_of"]).isoformat()
        if bericht and bericht > bis:
            befunde.append(Befund(key, "hinweis",
                                  f"Bericht vom {bericht} ist jünger als der Stand ({stand['latest']['as_of']}) — "
                                  f"python scripts/plan_status.py --nur {key}"))
    return befunde


def muster_trifft(muster: str, titel: str | None) -> bool:
    return bool(titel and re.search(muster, titel, re.IGNORECASE))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("datenbank", nargs="?", default=str(WURZEL / "data" / "council.sqlite"))
    args = ap.parse_args(argv)
    pfad = Path(args.datenbank)
    if not pfad.exists():
        print(f"✗ {pfad} fehlt — python scripts/lokale_daten.py hol && python scripts/lokale_daten.py setz")
        return 1
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        befunde = pruefe(conn)
    finally:
        conn.close()
    for b in befunde:
        print(b)
    fehler = sum(b.schwere == "fehler" for b in befunde)
    print(f"{len(plans.PLANS)} Pläne geprüft · {fehler} Fehler · {len(befunde) - fehler} Hinweise")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
