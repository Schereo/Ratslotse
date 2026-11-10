#!/usr/bin/env python3
"""Hält das Plan-Register (`council/plans.py`) gegen den Bestand.

``tests/test_plaene_register.py`` prüft die Form ohne Datenbank. Was nur der
Bestand weiß, steht hier:

- **Fehler:** Eine Vorlagennummer gibt es nicht; ein Beschluss steht nicht
  an Datum und Gremium, die das Register nennt; „beschlossen“ steht dort, wo
  der Rat nur zur Kenntnis genommen hat (und umgekehrt); eine Berichtsreihe
  trifft keinen einzigen Tagesordnungspunkt.
- **Fehler:** Ein Zitat unter „Was im Plan steht“ (``council/plan_key_points/``) steht nicht
  wörtlich in seinem Beschlusstext oder seiner Vorlage.
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

from council import plan_judge, plan_state, plans  # noqa: E402

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
    befunde.extend(_pruefe_stand(conn, heute))
    befunde.extend(_pruefe_rueckblick(conn))
    befunde.extend(_pruefe_kernpunkte(conn))
    return befunde


def _pruefe_kernpunkte(conn: sqlite3.Connection) -> list[Befund]:
    """„Was im Plan steht“ (``council/plan_key_points/``): Steht jedes Zitat wörtlich in seiner Quelle?

    Beschlusstexte und Vorlagen liegen in jedem Bestand. Den Text der Anlagen trägt nur der Server
    (im lokalen Abzug ist er geleert) — dort prüft dieser Lauf sie mit, hier
    ``python scripts/plan_kernpunkte.py --pruefen`` gegen die PDF-Dateien, samt Seitenzahl."""
    befunde: list[Befund] = []
    for key in plan_state.key_point_keys():
        data = plan_state.key_points(key) or {}
        for entry in [data["purpose"], *data["points"]]:
            ref = entry["source"]
            if ref["kind"] == "decision":
                stem = plans.template_stem(ref["template"])
                zeile = conn.execute(
                    """select d.official_text from council_decisions d join council_sessions s on s.ksinr = d.ksinr
                       where s.session_date = ? and s.committee = ?
                         and (d.template_number = ? or d.template_number like ? || '/%' or d.template_number = ?)
                       order by d.template_number = ? desc limit 1""",
                    (ref["date"], ref["committee"], ref["template"], stem, stem, ref["template"])).fetchone()
            elif ref["kind"] == "template":
                zeile = conn.execute("select raw_text from council_templates where template_number = ?",
                                     (ref["template"],)).fetchone()
            else:
                zeile = conn.execute("select raw_text from council_attachments where document_id = ?",
                                     (ref["document_id"],)).fetchone()
                if not zeile or not (zeile[0] or "").strip():
                    continue  # lokaler Abzug ohne Anlagen-Texte
            if not zeile or not zeile[0]:
                befunde.append(Befund(key, "fehler", f"Quelle fehlt im Bestand: {ref['kind']} {ref['template']}"))
            elif plan_judge.tight(entry["quote"]) not in plan_judge.tight(zeile[0]):
                befunde.append(Befund(key, "fehler", f"Zitat steht nicht in {ref['kind']} {ref['template']}: "
                                                      f"{entry['quote'][:60]}…"))
        # Die Zahl einer Kachel und der Termin fürs Zeitband sind von Hand gesetzt — beides muss im Zitat stehen.
        for point in data["points"]:
            befunde.extend(Befund(key, "fehler", f"{problem}: {point['text'][:60]}…")
                           for problem in plan_judge.check_extras(point))
    return befunde


def _pruefe_rueckblick(conn: sqlite3.Connection) -> list[Befund]:
    """Der Rückblick zitiert wörtlich. Steht ein Satz nicht so in seiner Vorlage, ist das ein Fehler —
    verglichen ohne Leerraum und Trennstriche, weil der PDF-Text Zeilen bricht („be- reits“).
    Sätze aus Anlagen (PDF) prüft dieser Lauf nicht: Deren Text liegt nicht im Abzug."""
    def squash(text: str) -> str:
        return re.sub(r"[\s\-]+", "", text)

    befunde: list[Befund] = []
    for pfad in sorted(plan_state.REVIEW_DIR.glob("*.json")):
        for satz in plan_state.review_statements(pfad.stem):
            nummer = satz.get("template")
            zeile = conn.execute("select raw_text from council_templates where template_number = ?",
                                 (nummer,)).fetchone() if nummer else None
            if zeile and zeile[0] and squash(satz["text"]) not in squash(zeile[0]):
                # Bei einer Fassung („/1“) steht der Satz oft in der Anlage, nicht im Vorlagentext.
                if "Evaluation" not in satz["source_label"] or "/" not in (nummer or "")[3:]:
                    befunde.append(Befund(pfad.stem, "fehler", f"Zitat steht nicht in {nummer}: {satz['text'][:60]}…"))
    return befunde


def _pruefe_stand(conn: sqlite3.Connection, heute: str) -> list[Befund]:
    """Pflege (Phase 6): Neuer Bericht, alter Stand — die Statusdateien (``council/plan_status/``)
    wachsen nicht von selbst. Dazu die Fristen, die ein Plan sich selbst gesetzt hat und die
    in den nächsten sechs Monaten anstehen. Dieselbe Regel wie die Kennzahlen im Cron
    (``plan_state.maintenance``)."""
    try:
        zeilen = conn.execute("select plan_key, role, date, template_number from council_plan_items").fetchall()
    except sqlite3.OperationalError:  # Zuordnung noch nie gebaut
        return []
    je_plan: dict[str, list[dict]] = {}
    for key, role, datum, nummer in zeilen:
        je_plan.setdefault(key, []).append({"role": role, "date": datum, "template_number": nummer})
    pflege = plan_state.maintenance(je_plan, heute)
    befunde = [Befund(key, "hinweis", f"Bericht vom {bericht} ist jünger als der Stand — "
                                      f"python scripts/plan_status.py --nur {key}")
               for key, bericht in sorted(pflege["stale_status"].items())]
    worte = {"end": "Laufzeit endet", "review": "Überprüfung laut Plan"}
    for key, fristen in sorted(pflege["due"].items()):
        for frist in fristen:
            if not frist["passed"]:  # Verstrichene Fristen meldet die Schleife in ``pruefe`` schon.
                befunde.append(Befund(key, "hinweis",
                                      f"{worte[frist['kind']]} am {frist['date']} — Nachfolger oder Auswertung im Blick?"))
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
