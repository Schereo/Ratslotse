"""Lottis Satz zur Sitzung, vom Modell geschrieben (Tims Wunsch 11.11.2026).

Der gerechnete Satz (``council/course.py::summary_sentence``) sagt zuverlässig,
was ansteht, klingt aber wie ein Formular („Im Mittelpunkt: „…“. Dazu 12
Entscheidungen, 4 Berichte und 2 weitere Punkte."). Hier schreibt ein Modell
dasselbe in zwei natürlichen Sätzen — aus genau denselben Angaben: Titel, Art,
„wichtig“ samt Grund, Kurzfassung je Punkt und, nach dem Protokoll, das
Ergebnis je Punkt. Was dort nicht steht, darf der Satz nicht behaupten.

Er entsteht je Sitzung beim Eintreffen der Tagesordnung (``check_committees``)
und noch einmal mit dem Protokoll (``check_protocols``), den Bestand zieht
``scripts/sitzungssaetze.py`` nach. Die Seite zeigt ihn, solange er zum Stand
passt, sonst den gerechneten (``CouncilStore.session_course``). Gemessen wird
er mit ``eval/run_sitzung_satz.py`` an vergangenen Sitzungen.
"""
from __future__ import annotations

import hashlib
import json
import os

from kern import llm, prompts

from . import course
from .committee_summary import datum_deutsch

#: Dasselbe Modell wie die TOP-Kurzfassungen (``committee_summary.py``):
#: kurze Texte aus Tagesordnungsangaben, kein Nutzereingabe-Feature.
MODEL = os.environ.get("COUNCIL_SESSION_SUMMARY_MODEL", "openai/gpt-6-luna")
#: Hochzählen, wenn Prompt oder Material sich so ändern, dass alle Sätze neu
#: geschrieben werden sollen (ein Lauf über ein Jahr kostet rund 0,30 $).
VERSION = 1
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


def stand(eingabe: dict) -> str:
    return "protocol" if any(eingabe["outcomes"].values()) else "agenda"


def nachziehen(store, ksinrs: list[int], *, schreiben: bool = True, max_usd: float = 1.0) -> dict:
    """Für jede Sitzung den Satz schreiben, wenn sich seine Angaben geändert
    haben (neue Tagesordnung, Kurzfassungen, Protokoll). Ein Fehler bei einer
    Sitzung überspringt sie, nicht den Lauf. ``schreiben=False`` zählt nur."""
    zahl = {"geschrieben": 0, "offen": 0, "aktuell": 0, "ohne_satz": 0, "fehler": 0}
    start = llm.session_cost()["usd"]
    for ksinr in ksinrs:
        if llm.session_cost()["usd"] - start >= max_usd:
            print(f"  Sitzungssätze: Kostengrenze {max_usd} $ erreicht — Rest beim nächsten Lauf.")
            break
        eingabe = store.session_sentence_input(ksinr)
        if not eingabe:
            continue
        stoff = material(eingabe["committee"], eingabe["session_date"], eingabe["items"],
                         eingabe["summaries"], eingabe["outcomes"])
        if not any(it["type"] not in course.FRAME_TYPES for it in eingabe["items"].values()):
            zahl["ohne_satz"] += 1
            continue
        h = hashlib.sha256(f"{VERSION}|{MODEL}|{stoff}".encode()).hexdigest()
        alt = store.session_sentence(ksinr)
        if alt and alt["material_hash"] == h:
            zahl["aktuell"] += 1
            continue
        if not schreiben:
            zahl["offen"] += 1
            continue
        try:
            satz = generate(stoff)
        except Exception as exc:  # noqa: BLE001 — eine Sitzung, nicht der Lauf
            print(f"  Sitzungssatz {ksinr}: {type(exc).__name__}: {exc}")
            satz = None
        if not satz:
            zahl["fehler"] += 1
            continue
        store.save_session_sentence(ksinr, stand(eingabe), satz, h, MODEL)
        zahl["geschrieben"] += 1
    zahl["usd"] = round(llm.session_cost()["usd"] - start, 4)
    return zahl
