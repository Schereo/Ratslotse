#!/usr/bin/env python3
"""Mein Viertel: Erkennt der Richter, ob ein Beschluss wirklich im Viertel liegt?

    python eval/pruefstand.py --suite viertel --modell openai/gpt-6-luna --laeufe 2

**Gemessen wird die erste LLM-Stufe** von ``council/viertel.py`` — der
Richter (``review_batch``, fünf Beschlüsse je Aufruf), mit genau den
Kandidaten, die der Betrieb baut (``store.district_candidates``, samt Orten,
Namensvettern und Vorlagenauszug). Er entscheidet, was auf die Tafel kommt;
die Bündelung danach sortiert nur noch.

**Die Erwartung ist die alte Ausgabe, von Hand nachgelesen.** 30 Beschlüsse
aus Bloherfelde und Eversten mit dem gespeicherten Urteil von GPT-5.6 Luna
(``council_district_reviews``), jeder an Titel, Orten und Begründung geprüft.
**Ausgelassen** sind die Fälle, in denen der Bestand sich selbst
widerspricht: die Widmung „Lauenburger Ring" und der B-Plan 650 stehen dort
in BEIDEN Vierteln als „district", die Sechsfeldhalle an der Kennedystraße
einmal als „district" und einmal als „elsewhere". Ein Goldwert, den das alte
Modell selbst nicht stabil trifft, misst Rauschen. Weil die Erwartung vom
heutigen Modell stammt, liegt es hier im Vorteil — ein Kandidat, der
gleichauf liegt, ist also eher besser als gleich.

**Hauptkennzahl:** Anteil richtig (im Viertel ja/nein).
**Harter Befund:** „im Viertel" für einen Beschluss, der woanders liegt oder
stadtweit gilt — die Tafel zeigte dann ein fremdes Vorhaben. Darunter zwei
Namensvetter-Fallen (Schießstand, Stadion), für die der Prompt eigens gebaut
ist.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

FAELLE = WURZEL / "eval" / "cases_district.json"


def lade() -> list[dict]:
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def bewerten(fall: dict, urteil: dict | None) -> dict:
    im_viertel = bool(urteil) and urteil.get("relation") == "district"
    return {"id": f"{fall['place_id']}/{fall['decision_id']}", "soll": fall["im_viertel"],
            "ist": None if urteil is None else urteil.get("relation"),
            "richtig": urteil is not None and im_viertel == fall["im_viertel"],
            "fremd_auf_der_tafel": im_viertel and not fall["im_viertel"]}


def ein_lauf(faelle: list[dict]) -> dict:
    from council import viertel
    from council.store import CouncilStore
    store = CouncilStore(Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite"))
    orte = {p.id: p for p in store.all_places()}
    zeilen: list[dict] = []
    fehler: list[str] = []
    try:
        for place_id in dict.fromkeys(f["place_id"] for f in faelle):
            ort = orte[place_id]
            meine = [f for f in faelle if f["place_id"] == place_id]
            # Ohne Zeitgrenze: Der Betrieb schaut 24 Monate zurück, die Fälle
            # sollen aber nicht mit dem Kalender aus der Suite fallen.
            kandidaten = {k["id"]: k for k in store.district_candidates(ort, since="2000-01-01")}
            fehlt = [f["decision_id"] for f in meine if f["decision_id"] not in kandidaten]
            if fehlt:
                raise RuntimeError(f"{place_id}: keine Kandidaten mehr für {fehlt} — Orts-Pipeline geändert?")
            urteile: dict[int, dict] = {}
            for i in range(0, len(meine), viertel.BATCH_SIZE):
                stapel = [kandidaten[f["decision_id"]] for f in meine[i:i + viertel.BATCH_SIZE]]
                try:
                    urteile.update(viertel.review_batch(ort, stapel))
                except Exception as e:  # noqa: BLE001 — ein Stapel, nicht der Lauf
                    fehler.append(f"{place_id} {[k['id'] for k in stapel]}: {type(e).__name__}: {str(e)[:160]}")
            zeilen += [bewerten(f, urteile.get(f["decision_id"])) for f in meine]
    finally:
        store.close()
    return {
        "n_cases": len(zeilen),
        "quote": round(sum(z["richtig"] for z in zeilen) / len(zeilen), 4) if zeilen else None,
        "fremd_auf_der_tafel": [z["id"] for z in zeilen if z["fremd_auf_der_tafel"]],
        "verpasst": [z["id"] for z in zeilen if z["soll"] and not z["richtig"]],
        "ohne_urteil": [z["id"] for z in zeilen if z["ist"] is None],
        "fehler": fehler,
        "faelle": zeilen,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    erg = ein_lauf(lade())
    print(json.dumps({k: v for k, v in erg.items() if k != "faelle"}, ensure_ascii=False, indent=1))
