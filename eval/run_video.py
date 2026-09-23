#!/usr/bin/env python3
"""Video-Ergebnisse: Liest das Modell die Abstimmungen richtig aus dem Transkript?

    python eval/run_video.py --bauen       # Erwartungen aus den Niederschriften (ohne Modell)
    python eval/pruefstand.py --suite video-ergebnisse --modell openai/gpt-6-luna --laeufe 2

**Die Zusage des Features** (``council/videos.py``): null falsche Ergebnisse
— gemessen am 31.08.2026 waren es 111 von 111. Lieber schweigt der Lauf, als
dass auf der Seite „angenommen" steht, wo der Rat abgelehnt hat. Diese Suite
fährt deshalb den ganzen strengen Weg des Betriebs
(``videos.extract_results``: zwei versetzte Durchläufe, Beleg wörtlich im
Transkript, Konsens) über drei ganze Ratssitzungen und hält das Ergebnis
gegen die **Niederschrift** (``council_decisions``), nicht gegen eine alte
Modellausgabe.

**Hauptkennzahl:** Anteil der protokollierten Ergebnisse, die richtig
ausgegeben werden (verpasst zählt als nicht richtig — die Seite zeigt dann
„Protokoll abwarten", das ist ehrlich, aber keine Leistung).
**Harter Befund:** ein falsches Ergebnis ODER ein falscher Zusatz
(„einstimmig", wo das Protokoll „mehrheitlich" sagt). Beides stünde als
Tatsache über einen echten Ratsbeschluss auf der Seite; im Bericht sperrt ein
Anstieg das Urteil „besser".

**Abgesetzt heißt vertagt.** Die Niederschrift führt einen zu Sitzungsbeginn
abgesetzten Punkt als ``postponed``, das Video liest ihn als ``removed``. Die
Suite wertet beide gleich (so stand es am 29.06. bei 14.7–14.10).

**Aus der Erwartung genommen** (``AUSGENOMMEN``), jeweils in der Niederschrift
nachgelesen: Punkte, die am Sitzungsende ohne Abstimmung vertagt wurden (dort
gibt es nichts zu hören — der Prompt verlangt ausdrücklich Schweigen), und
eine Zeile, die der Niederschrift-Parser einem falschen Punkt zugeordnet hat.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

FAELLE = WURZEL / "eval" / "cases_video.json"

#: (Sitzung, Punkt) → warum nicht erwartet. Nachgelesen am 23.09.2026.
AUSGENOMMEN: dict[tuple[int, str], str] = {
    (4692, "4"): "Parser-Zeile: TOP 4 sind die Mitteilungen des Oberbürgermeisters, "
                 "laut Sitzungsleitung „gibt es keine“ (Video 10:41) — kein Beschluss",
    (4695, "14.5"): "Niederschrift: „abgesetzt“; im Video nimmt die FDP ihren Berichtsantrag "
                    "ohne Abstimmung zur Kenntnis (110:53–111:11) — kein Ergebnis zu hören",
    **{(4692, n): "mit Ablauf der öffentlichen Sitzung ohne Abstimmung vertagt"
       for n in ("15.2", "15.4", "15.5", "15.6", "15.8")},
}
_GLEICH = {"removed": "postponed"}


def lade() -> list[dict]:
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def bauen(db: Path) -> list[dict]:
    """Die Erwartung aus der Niederschrift — Hauptbeschlüsse, keine Unterabstimmungen."""
    import sqlite3

    from eval import transkripte
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    faelle = []
    for ksinr, vid in transkripte.SITZUNGEN.items():
        datum = con.execute("SELECT session_date FROM council_sessions WHERE ksinr = ?",
                            (ksinr,)).fetchone()[0]
        erwartet = {}
        for nr, outcome, vote in con.execute(
                "SELECT item_number, outcome, vote FROM council_decisions "
                "WHERE ksinr = ? AND kind = 'decision' "
                "AND outcome IN ('accepted', 'rejected', 'noted', 'postponed') ORDER BY position",
                (ksinr,)):
            if (ksinr, nr) not in AUSGENOMMEN:
                erwartet[nr] = {"outcome": outcome, "vote": vote}
        faelle.append({"ksinr": ksinr, "video_id": vid, "datum": datum, "erwartet": erwartet,
                       "ausgenommen": {n: g for (k, n), g in AUSGENOMMEN.items() if k == ksinr}})
    return faelle


def bewerten(fall: dict, ergebnisse: list[dict]) -> dict:
    """Ausgabe gegen Niederschrift — rein, offline testbar."""
    def norm(o: str | None) -> str | None:
        return _GLEICH.get(o or "", o)

    gesehen = {r["item_number"]: r for r in ergebnisse}
    richtig, falsch, zusatz, verpasst = [], [], [], []
    for nr, soll in fall["erwartet"].items():
        ist = gesehen.get(nr)
        if ist is None:
            verpasst.append(nr)
        elif norm(ist["outcome"]) != norm(soll["outcome"]):
            falsch.append(f"{fall['ksinr']} {nr}: {ist['outcome']} statt {soll['outcome']}")
        else:
            richtig.append(nr)
            if ist.get("vote") and soll.get("vote") and ist["vote"] != soll["vote"]:
                zusatz.append(f"{fall['ksinr']} {nr}: {ist['vote']} statt {soll['vote']}")
    return {"ksinr": fall["ksinr"], "soll": len(fall["erwartet"]), "richtig": len(richtig),
            "falsch": falsch, "zusatz_falsch": zusatz, "verpasst": verpasst,
            "ungeprueft": sorted(set(gesehen) - set(fall["erwartet"])),
            "ausgegeben": len(ergebnisse)}


def ein_lauf(faelle: list[dict]) -> dict:
    from council import videos
    from council.store import CouncilStore
    from eval import transkripte
    store = CouncilStore(Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite"))
    zeilen = []
    try:
        for fall in faelle:
            segmente = transkripte.laden(fall["video_id"])
            ergebnisse = videos.extract_results(segmente, store.agenda_items(fall["ksinr"]))
            zeilen.append(bewerten(fall, ergebnisse))
    finally:
        store.close()
    soll = sum(z["soll"] for z in zeilen)
    return {
        "n_cases": soll,
        "quote": round(sum(z["richtig"] for z in zeilen) / soll, 4) if soll else None,
        "falsch": [f for z in zeilen for f in z["falsch"]],
        "zusatz_falsch": [f for z in zeilen for f in z["zusatz_falsch"]],
        "verpasst": sum(len(z["verpasst"]) for z in zeilen),
        "ungeprueft": sum(len(z["ungeprueft"]) for z in zeilen),
        "sitzungen": zeilen,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bauen", action="store_true")
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    a = ap.parse_args()
    if a.bauen:
        faelle = bauen(Path(a.db))
        FAELLE.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{sum(len(f['erwartet']) for f in faelle)} Ergebnisse aus {len(faelle)} Sitzungen "
              f"→ {FAELLE.relative_to(WURZEL)}")
        return 0
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    erg = ein_lauf(lade())
    print(json.dumps({k: v for k, v in erg.items() if k != "sitzungen"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
