#!/usr/bin/env python3
"""Live-Verfolgung: Erkennt das Modell, welcher Tagesordnungspunkt gerade läuft?

    python eval/run_live_tracker.py --zeigen     # die Fenster zum Nachlesen, ohne Modell
    python eval/pruefstand.py --suite live-verfolgung --modell google/gemini-3.1-flash-lite --laeufe 2

**Die Fälle** (``eval/cases_live_tracker.json``) sind Fenster aus zwei echten
Ratssitzungen (29.06. und 01.06.2026), 40 bis 60 Sekunden lang wie im
Betrieb (30-s-Stück plus 30 s Überlappung), jeweils mit dem Stand, den die
Verfolgung davor hatte. Das Transkript sind YouTubes Untertitel derselben
Sitzung (``eval/transkripte.py``), Tagesordnung und Sprecher-Verzeichnis
kommen aus ``data/council.sqlite`` — derselbe Aufruf wie im Mitschnitt
(``council.livetracker.track_window``).

**Die Erwartung ist nachgelesen**, nicht aus einer Modellausgabe: Jedes
Fenster ist von Hand gelesen, und wo die Sitzungsleitung eine Nummer
verschluckt („Tagesordnungspunkt 141" für 14.1) oder sich verspricht („81 …
Ach so, Entschuldigung … 9.1"), steht das in ``notiz``. Die Abstimmungen am
29.06. sind zusätzlich gegen die Niederschrift geprüft (``council_decisions``
und die zeitgestempelten Video-Ergebnisse stimmen dort überein).

Drei Arten von Fenstern:

* ``aufruf`` — ein neuer Punkt wird aufgerufen, der Stand ist noch der alte.
* ``block`` — mehrere Formalien in einer Minute; richtig ist der LETZTE.
* ``aussprache`` — mitten in der Debatte, keine Nummer fällt; richtig ist,
  beim Stand zu bleiben (der Prompt sagt genau das).

**Hauptkennzahl:** Anteil der Fenster, deren TOP am Fensterende stimmt.
**Harter Befund:** ein TOP, den es auf der Tagesordnung nicht gibt — die
Karte zeigte dann einen Punkt, der nie aufgerufen wurde.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

FAELLE = WURZEL / "eval" / "cases_live_tracker.json"


def lade() -> list[dict]:
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def _sitzung(store, ksinr: int, cache: dict) -> dict:
    if ksinr not in cache:
        from council import livetracker
        from eval import transkripte
        agenda = [it for it in store.agenda_items(ksinr) if it.get("is_public")]
        cache[ksinr] = {
            "agenda": livetracker.agenda_text(agenda),
            "nummern": {livetracker.norm_top(it["item_number"]) for it in agenda},
            "roster": livetracker.roster_text(store.council_roster_before(ksinr)),
            "segmente": transkripte.laden(transkripte.SITZUNGEN[ksinr]),
        }
    return cache[ksinr]


def fenster(fall: dict, segmente: list[tuple[float, str]]) -> str:
    from council import livetracker
    return livetracker.format_window([s for s in segmente if fall["von"] <= s[0] < fall["bis"]])


def bewerten(fall: dict, antwort: dict, nummern: set[str]) -> dict:
    from council import livetracker
    top = livetracker.norm_top(antwort.get("top")) or fall["stand"]
    return {"id": fall["id"], "art": fall["art"], "top": top,
            "richtig": top in fall["erwartet"],
            "erfunden": top is not None and top not in nummern,
            "phase": antwort.get("phase")}


def ein_lauf(faelle: list[dict], modell: str | None = None) -> dict:
    from council import livetracker
    from council.store import CouncilStore
    store = CouncilStore(Path(__import__("os").environ.get("COUNCIL_DB")
                              or WURZEL / "data" / "council.sqlite"))
    cache: dict = {}
    zeilen = []
    try:
        for fall in faelle:
            s = _sitzung(store, fall["ksinr"], cache)
            stand = {"top": fall["stand"], "speaker": None, "party": None}
            antwort = livetracker.track_window(
                s["agenda"], s["roster"], stand, fenster(fall, s["segmente"]),
                fall["von"], fall["bis"], modell or livetracker.TRACKER_MODEL)
            zeilen.append(bewerten(fall, antwort, s["nummern"]))
    finally:
        store.close()
    arten = sorted({z["art"] for z in zeilen})
    return {
        "n_cases": len(zeilen),
        "quote": round(sum(z["richtig"] for z in zeilen) / len(zeilen), 4) if zeilen else None,
        "erfunden": sum(z["erfunden"] for z in zeilen),
        "je_art": {a: f"{sum(z['richtig'] for z in zeilen if z['art'] == a)}/"
                      f"{sum(1 for z in zeilen if z['art'] == a)}" for a in arten},
        "faelle": zeilen,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zeigen", action="store_true", help="nur die Fenster ausgeben, kein Modell")
    ap.add_argument("--modell")
    a = ap.parse_args()
    faelle = lade()
    if a.zeigen:
        from eval import transkripte
        for f in faelle:
            seg = transkripte.laden(transkripte.SITZUNGEN[f["ksinr"]])
            print(f"\n### {f['id']} [{f['art']}] Stand {f['stand']} → erwartet {f['erwartet']}"
                  f"  ({f.get('notiz', '')})\n{fenster(f, seg)}")
        return 0
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    erg = ein_lauf(faelle, a.modell)
    for z in erg["faelle"]:
        print(f"  {z['id']:24} {'ok ' if z['richtig'] else 'XX '} {z['top']}")
    print({k: v for k, v in erg.items() if k != "faelle"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
