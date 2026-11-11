"""Lottis Satz zur Sitzung, vom Modell geschrieben (Tims Wunsch 11.11.2026).

Der gerechnete Satz (``council/course.py::summary_sentence``) sagt zuverlässig,
was ansteht, klingt aber wie ein Formular („Im Mittelpunkt: „…“. Dazu 12
Entscheidungen, 4 Berichte und 2 weitere Punkte."). Hier schreibt ein Modell
dasselbe in zwei natürlichen Sätzen — aus genau denselben Angaben: Titel, Art,
„wichtig“ samt Grund, Kurzfassung je Punkt und, nach dem Protokoll, das
Ergebnis je Punkt. Was dort nicht steht, darf der Satz nicht behaupten.

Noch ein Versuch: ``eval/run_sitzung_satz.py`` misst ihn an vergangenen
Sitzungen. Entstehen soll er später einmal je Sitzung beim Eintreffen der
Tagesordnung und noch einmal mit dem Protokoll.
"""
from __future__ import annotations

import json
import os

from kern import llm, prompts

from . import course
from .committee_summary import datum_deutsch

#: Dasselbe Modell wie die TOP-Kurzfassungen (``committee_summary.py``):
#: kurze Texte aus Tagesordnungsangaben, kein Nutzereingabe-Feature.
MODEL = os.environ.get("COUNCIL_SESSION_SUMMARY_MODEL", "openai/gpt-6-luna")
#: Bei sehr langen Tagesordnungen (Bauausschuss: 60 Punkte) reichen die
#: wichtigen samt Kurzfassung und die übrigen nur mit Titel.
MAX_PUNKTE = 40

_ERGEBNIS = {"accepted": "angenommen", "rejected": "abgelehnt", "postponed": "vertagt",
             "noted": "zur Kenntnis genommen", "withdrawn": "zurückgezogen",
             "no_decision": "ohne Entscheidung", "settled": "erledigt"}


def material(committee: str, session_date: str, items: dict[str, dict], kurz: dict[str, str],
             ergebnisse: dict[str, str | None]) -> str:
    """Die Angaben, aus denen der Satz entsteht — Formalien, Fragestunde und
    Mitteilungen bleiben draußen (wie beim gerechneten Satz)."""
    inhalt = [(nr, it) for nr, it in items.items() if it["type"] not in course.FRAME_TYPES]
    wichtig = [(nr, it) for nr, it in inhalt if it.get("important")]
    rest = [(nr, it) for nr, it in inhalt if not it.get("important")]
    stand = "nach dem Protokoll" if ergebnisse else "vor dem Protokoll"
    zeilen = [f"Gremium: {committee}", f"Sitzung am {datum_deutsch(session_date)} · Stand: {stand}",
              f"{len(inhalt)} inhaltliche öffentliche Punkte.", ""]
    for nr, it in (wichtig + rest)[:MAX_PUNKTE]:
        teile = [it.get("type_label") or "Punkt"]
        if it.get("important"):
            teile.append("wichtig" + (f" ({it['important_reason']})" if it.get("important_reason") else ""))
        if it.get("applicant"):
            teile.append(f"Antrag von {it['applicant']}")
        if it.get("postponed"):
            teile.append("stand schon einmal hier und wurde vertagt")
        if ergebnisse.get(nr):
            teile.append(f"Ergebnis: {_ERGEBNIS.get(ergebnisse[nr] or '', ergebnisse[nr])}")
        zeile = f"- {it['short_title']} [{' · '.join(teile)}]"
        if it.get("important") and kurz.get(nr):
            zeile += f" — {kurz[nr]}"
        zeilen.append(zeile)
    if len(inhalt) > MAX_PUNKTE:
        zeilen.append(f"- … und {len(inhalt) - MAX_PUNKTE} weitere Punkte")
    return "\n".join(zeilen)


def generate(stoff: str) -> str | None:
    """Ein Modellaufruf. ``None`` bei leerer oder kaputter Antwort."""
    resp = llm.chat_complete(
        messages=[{"role": "system", "content": prompts.render("session_summary_system")},
                  {"role": "user", "content": stoff}],
        model=MODEL, _feature="session_summary", response_format={"type": "json_object"},
        _geduld=True, _ersatz=llm.ersatz_fuer(MODEL),
    )
    try:
        satz = (json.loads(resp.choices[0].message.content or "{}").get("satz") or "").strip()
    except (json.JSONDecodeError, AttributeError, IndexError):
        return None
    return satz or None
