#!/usr/bin/env python3
"""Gold-Fälle für die Gründliche Recherche: Faktenliste statt A/B-Gefühl.

``quality_qa.py`` vergleicht zwei Stände blind miteinander, sagt aber nicht, ob
ein Bericht die Sache *richtig* erzählt. Hier trägt jeder Fall eine
handgeprüfte Liste aus Pflichtfakten (mit Gewicht und Beleg) und verbotenen
Fehlbehauptungen bei sich (``eval/cases_deep_gold.json``). Gemessen wird in
zwei Stufen, damit ein Fehlschlag seine Ursache verrät:

1. **Material** (deterministisch): Lagen die Belegstellen dem Bericht überhaupt
   vor — Beschluss, Wortbeitrag, Pressemitteilung? Fehlt eine, liegt der Fehler
   im Index oder in der Suche, nicht im Berichts-Modell.
2. **Bericht** (LLM-Judge): Welche Pflichtfakten stehen drin, welche
   Fehlbehauptungen auch?

Der Lauf nutzt die echte Pipeline (``deepresearch._run``) gegen eine
Datenbank-Kopie; nur die Ablage des Jobs geht in eine Wegwerf-DB::

    python scripts/eval_deep_gold.py --db /pfad/council.sqlite --label vorher
    python scripts/eval_deep_gold.py --db /pfad/council.sqlite --label nachher --premium

Braucht ``OPENROUTER_API_KEY`` und fastembed. Ergebnisse unter
``eval/results/deep_gold/<label>.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))
load_dotenv(ROOT / ".env")

from kern import llm  # noqa: E402

CASES = ROOT / "eval" / "cases_deep_gold.json"
RESULTS = ROOT / "eval" / "results" / "deep_gold"
# Richter: GPT-6 Sol (01.10.2026). Gemini 2.5 Flash war zu großzügig (wertete
# einen Ausschuss-Auftrag als Ratsbeschluss) und läuft am 20.10.2026 aus.
# GPT-6 Luna urteilte über DIESELBE Antwort einmal 0 %, einmal 50 % — als
# Messinstrument zu wackelig. Sol gab in zwei Läufen über 14 gespeicherte
# Antworten fast gleiche Urteile, für etwa 0,8 ct je Fall.
JUDGE_MODEL = os.environ.get("COUNCIL_GOLD_JUDGE_MODEL", "openai/gpt-6-sol")

JUDGE_PROMPT = """Du prüfst einen Recherche-Bericht über Oldenburger Ratsvorgänge gegen eine handgeprüfte Faktenliste.

FRAGE: {frage}

BERICHT:
<<<
{bericht}
>>>

PFLICHTFAKTEN — je Fakt: Hat eine Leserin, die NUR den Bericht kennt, diese Information im Wesentlichen erfahren?
- Ja (ok: true), wenn die wesentliche Aussage dasteht — in anderen Worten oder über mehrere Sätze verteilt genügt.
- FEHLENDE Einzelheiten machen einen Fakt NICHT unerfüllt: Datum, Vorlagennummer, Antragsteller in Klammern, genaues Stimmverhältnis, einzelne Zusatzpunkte nach „außerdem“ oder Semikolon, Begründungen und Hintergrund.
- FALSCHE Einzelheiten schon: ein anderes Gremium, ein anderer Zeitpunkt, ein anderes Ergebnis, eine andere Aussage.
- Nein (ok: false) auch, wenn der Kern fehlt oder nur ein Randaspekt genannt ist.
- Steht im Fakt „mindestens“ (etwa „mindestens zwei genannt“), gilt genau diese Mindestzahl.
- Findest du eine Stelle, die die Hauptaussage des Fakts trägt, ist er erfüllt — dass Nebenangaben des Fakts dort fehlen, ändert daran nichts. Nur wenn die Stelle dem Fakt WIDERSPRICHT (anderes Gremium, anderer Zeitpunkt, anderes Ergebnis), ist er nicht erfüllt.
Lies den GANZEN Bericht, bevor du urteilst; zitiere die Stelle, auf die du dich stützt.
{pflicht}

VERBOTENE BEHAUPTUNGEN (je Punkt: stellt der Bericht das als Tatsache dar? Eine ausdrückliche Verneinung oder Einschränkung ist KEIN Verstoß):
{verboten}

Antworte NUR als JSON:
{{"pflicht": {{"F1": {{"ok": true, "zitat": "kurzes Zitat aus dem Bericht oder leer"}}, ...}},
  "verboten": {{"X1": {{"verstoss": false, "zitat": "kurzes Zitat oder leer"}}, ...}}}}"""


def _bericht_aus(events: list[dict]) -> str:
    buf = ""
    for e in events:
        if e.get("type") == "replace":
            buf = e.get("text") or ""
        elif e.get("type") == "token":
            buf += e.get("text") or ""
    return buf


def _material_pruefen(case: dict, m: dict) -> list[dict]:
    """Stufe 1: Welche Belegstellen lagen dem Bericht vor?"""
    out = []
    for b in case.get("material", []):
        treffer = False
        if b["art"] == "beschluss":
            treffer = any(str(c.get("session_date", ""))[:10] == b["session_date"]
                          and b.get("committee", "") in (c.get("committee") or "")
                          and b.get("titel_enthaelt", "").lower() in (c.get("title") or "").lower()
                          for c in m.get("candidates", []))
        elif b["art"] == "debatte":
            treffer = any(str(d.get("session_date", ""))[:10] == b["session_date"]
                          and any(k.lower() in ((d.get("text") or "") + " " + (d.get("answer") or "")).lower()
                                  for k in b["text_enthaelt_eins"])
                          for d in m.get("debates", []))
        elif b["art"] == "presse":
            treffer = any(str(p.get("date", ""))[:10] == b["date"]
                          and b["titel_enthaelt"].lower() in (p.get("title") or "").lower()
                          for p in m.get("press_releases", []))
        out.append({"id": b["id"], "fuer": b["fuer"], "art": b["art"], "vorhanden": treffer})
    return out


def _judge(case: dict, bericht: str) -> dict:
    pflicht = "\n".join(f"{p['id']}: {p['fakt']}" for p in case["pflicht"])
    verboten = "\n".join(f"{v['id']}: {v['behauptung']}" for v in case["verboten"])
    for versuch in range(2):
        resp = llm.chat_complete(
            model=JUDGE_MODEL, _feature="quality_judge", temperature=0,
            max_tokens=3000, timeout=180.0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(
                frage=case["question"], bericht=bericht[:24000],
                pflicht=pflicht, verboten=verboten)}])
        try:
            return json.loads((resp.choices[0].message.content or "{}").strip())
        except (ValueError, IndexError):
            if versuch == 1:
                raise
    return {}


def _bewerten(case: dict, urteil: dict) -> dict:
    gesamt = sum(p["gewicht"] for p in case["pflicht"])
    erfuellt = [p["id"] for p in case["pflicht"]
                if (urteil.get("pflicht", {}).get(p["id"]) or {}).get("ok")]
    abdeckung = sum(p["gewicht"] for p in case["pflicht"] if p["id"] in erfuellt) / gesamt
    verstoesse = [v["id"] for v in case["verboten"]
                  if (urteil.get("verboten", {}).get(v["id"]) or {}).get("verstoss")]
    kern = [p["id"] for p in case["pflicht"] if p["gewicht"] >= 3]
    bestanden = (abdeckung >= 0.6 and all(k in erfuellt for k in kern) and not verstoesse)
    return {"abdeckung": round(abdeckung, 2), "erfuellt": erfuellt,
            "verfehlt": [p["id"] for p in case["pflicht"] if p["id"] not in erfuellt],
            "verstoesse": verstoesse, "bestanden": bestanden}


def lauf(db: Path, label: str, premium: bool, nur: str | None) -> Path:
    from app import deepresearch
    from council import qa

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if nur:
        cases = [c for c in cases if c["id"] == nur]
    ergebnisse = []
    with tempfile.TemporaryDirectory() as tmp:
        ratslotse_db = str(Path(tmp) / "ratslotse.sqlite")
        for case in cases:
            job = deepresearch.DeepJob(id=uuid.uuid4().hex, user_id=0,
                                       question=case["question"],
                                       model=qa.deep_model_for(premium), premium=premium)
            t0 = time.perf_counter()
            deepresearch._run(job, ratslotse_db, str(db))
            dauer = round(time.perf_counter() - t0, 1)
            m = job.material or {}
            bericht = _bericht_aus(job.events)
            material = _material_pruefen(case, m)
            urteil = _judge(case, bericht)
            wertung = _bewerten(case, urteil)
            ergebnisse.append({
                "id": case["id"], "question": case["question"], "model": job.model,
                "dauer_s": dauer, "wertung": wertung, "material": material,
                "urteil": urteil, "bericht": bericht,
                "gelesen": {
                    "beschluesse": [f"{c.get('session_date')} · {c.get('committee')} · {c.get('title')}"
                                    for c in m.get("candidates", [])],
                    "debatten": [f"{d.get('session_date')} · {d.get('speaker')} · "
                                 f"{(d.get('text') or '')[:120]}"
                                 + (f" || ANTWORT: {(d.get('answer') or '')[:120]}" if d.get("answer") else "")
                                 for d in m.get("debates", [])],
                    "presse": [f"{p.get('date')} · {p.get('title')}"
                               for p in m.get("press_releases", [])],
                },
            })
            fehlt = [x["id"] for x in material if not x["vorhanden"]]
            print(f"{case['id']}: Abdeckung {wertung['abdeckung']:.0%}, "
                  f"verfehlt {wertung['verfehlt']}, Verstöße {wertung['verstoesse']}, "
                  f"Material fehlt {fehlt} → {'BESTANDEN' if wertung['bestanden'] else 'NICHT bestanden'}"
                  f" ({dauer}s, {job.model})", flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{label}.json"
    out.write_text(json.dumps({"label": label, "db": str(db), "judge": JUDGE_MODEL,
                               "kosten_usd": round(llm.session_cost()["usd"], 3),
                               "cases": ergebnisse}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"→ {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Gold-Fälle der Gründlichen Recherche")
    ap.add_argument("--db", required=True, help="Kopie der council.sqlite")
    ap.add_argument("--label", required=True)
    ap.add_argument("--premium", action="store_true", help="Berichtsmodell für Recherche Plus")
    ap.add_argument("--nur", default=None, help="nur diesen Fall")
    args = ap.parse_args()
    lauf(Path(args.db), args.label, args.premium, args.nur)


if __name__ == "__main__":
    main()
