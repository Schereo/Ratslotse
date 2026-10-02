#!/usr/bin/env python3
"""Gold-Fälle für „Frag den Rat“: dieselben Fälle wie die Gründliche Recherche.

``scripts/eval_deep_gold.py`` misst den langen Bericht; hier läuft dieselbe
Faktenliste (``eval/cases_deep_gold.json``) gegen die schnelle Antwort — über
den ECHTEN Weg: ``POST /api/council/ask`` am laufenden Dienst, wie
``scripts/frage_probe.py``. Die Suite ``ki-frage`` (``eval/run_qa.py``) baut
die Kandidaten dagegen selbst nach und prüft, ob Beschlüsse zitiert werden —
ob eine Aussage aus einer Debatte in der Antwort steht, sieht sie nicht. Genau
daran hing der Befund vom 30.09.2026 (Schlossplatz-Spielplatz).

Drei Stufen, damit ein Fehlschlag seine Ursache verrät:

1. **Material der Antwort** — lagen die Belegstellen im Kontext (Quellen,
   Debatten, Presse aus dem Quellen-Ereignis)?
2. **Material des Bausteins** — stehen sie wenigstens im nachgeladenen
   Debatten-Baustein unter der Antwort (``POST /api/council/debates``)?
3. **Antwort** — Pflichtfakten und verbotene Behauptungen, derselbe Richter
   wie beim Bericht.

Auf dem Server (Embeddings, echte Daten)::

    .venv/bin/python scripts/eval_ask_gold.py --label nach-1601
    .venv/bin/python scripts/eval_ask_gold.py --label x --nur stadion-stand

Das Token entsteht wie bei der Rauchprobe (``rauchprobe.token_bauen``); die
Fragen zählen als Fragen dieses Kontos. Ergebnis unter
``data/eval_gold/ask-<label>.json`` (``data/`` überlebt den Deploy).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from kern import llm  # noqa: E402

CASES = WURZEL / "eval" / "cases_deep_gold.json"
ZIEL = WURZEL / "data" / "eval_gold"


def _post(basis: str, token: str, pfad: str, body: dict, strom: bool = False):
    anfrage = urllib.request.Request(
        f"{basis}{pfad}", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "text/event-stream" if strom else "application/json"})
    return urllib.request.urlopen(anfrage, timeout=300)


def fragen(basis: str, token: str, frage: str) -> dict:
    """Eine Frage über den Ereignis-Strom → Antwort, Quellen-Ereignis, Dauer."""
    t0 = time.time()
    text: list[str] = []
    quellen: dict = {}
    with _post(basis, token, "/api/council/ask", {"question": frage, "history": []},
               strom=True) as antwort:
        for roh in antwort:
            zeile = roh.decode("utf-8", "replace").strip()
            if not zeile.startswith("data:"):
                continue
            try:
                e = json.loads(zeile[5:].strip())
            except ValueError:
                continue
            if e.get("type") == "token":
                text.append(e.get("text") or "")
            elif e.get("type") == "sources":
                quellen = e
    return {"antwort": "".join(text), "quellen": quellen, "dauer_s": round(time.time() - t0, 1)}


def material_form(quellen: dict, debatten: list[dict] | None = None) -> dict:
    """Quellen-Ereignis (bzw. nachgeladene Debatten) in die Form, die
    ``eval_deep_gold._material_pruefen`` liest: Debatten tragen dort
    ``session_date``/``text``, im Web-Vertrag ``date``/``excerpt``."""
    deb = debatten if debatten is not None else (quellen.get("debates") or [])
    return {
        "candidates": quellen.get("sources") or [],
        "debates": [{"session_date": d.get("date") or d.get("session_date"),
                     "text": d.get("excerpt") or d.get("text") or "",
                     "speaker": d.get("speaker")} for d in deb],
        "press_releases": quellen.get("press_releases") or [],
        "attachments": quellen.get("attachments") or [],
        # Tagesordnungspunkte aus dem Sitzungs-Baustein — die einzige Stelle,
        # an der „Frag den Rat“ heute angekündigte Stationen zeigt.
        "agenda": [{"session_date": s.get("session_date"), "committee": s.get("committee"),
                    "title": a.get("title")}
                   for s in quellen.get("sessions") or [] for a in s.get("agenda") or []],
    }


def lauf(basis: str, label: str, nur: str | None, konto: str | None) -> Path:
    from scripts import eval_deep_gold as gold

    rauchprobe = importlib.import_module("rauchprobe")
    token, info = rauchprobe.token_bauen(WURZEL, konto)
    if not token:
        raise SystemExit(f"Kein Token: {info}")
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if nur:
        cases = [c for c in cases if c["id"] == nur]
    ergebnisse = []
    for case in cases:
        r = fragen(basis, token, case["question"])
        q = r["quellen"]
        material = gold._material_pruefen(case, material_form(q))
        baustein: list[dict] = []
        try:
            with _post(basis, token, "/api/council/debates", {
                    "question": case["question"],
                    "decision_ids": [s["id"] for s in (q.get("sources") or [])][:40]}) as a:
                baustein = json.loads(a.read().decode("utf-8")).get("debates") or []
        except Exception as exc:  # noqa: BLE001 — der Baustein ist Zusatz
            print(f"  Baustein nicht geladen: {exc}", flush=True)
        # Was die Antwort schon hatte, steht auch im Baustein (er hängt an).
        material_baustein = gold._material_pruefen(
            case, material_form(q, (q.get("debates") or []) + baustein))
        urteil = gold._judge(case, r["antwort"])
        wertung = gold._bewerten(case, urteil)
        ergebnisse.append({
            "id": case["id"], "question": case["question"], "dauer_s": r["dauer_s"],
            "wertung": wertung, "material": material, "material_baustein": material_baustein,
            "urteil": urteil, "antwort": r["antwort"],
            "gelesen": {"fragetyp": q.get("qtype"),
                        "beschluesse": len(q.get("sources") or []),
                        "debatten": [f"{d.get('date')} · {d.get('speaker')}"
                                     for d in (q.get("debates") or [])],
                        "baustein": len(baustein)},
        })
        fehlt = [x["id"] for x in material if not x["vorhanden"]]
        fehlt_b = [x["id"] for x in material_baustein if not x["vorhanden"]]
        print(f"{case['id']}: Abdeckung {wertung['abdeckung']:.0%}, verfehlt {wertung['verfehlt']}, "
              f"Verstöße {wertung['verstoesse']}, Material fehlt {fehlt} (im Baustein: {fehlt_b}) → "
              f"{'BESTANDEN' if wertung['bestanden'] else 'NICHT bestanden'} ({r['dauer_s']} s)",
              flush=True)
    n = len(ergebnisse) or 1
    print(f"GESAMT: Abdeckung {sum(e['wertung']['abdeckung'] for e in ergebnisse) / n:.0%}, "
          f"bestanden {sum(e['wertung']['bestanden'] for e in ergebnisse)}/{len(ergebnisse)}, "
          f"Verstöße {sum(len(e['wertung']['verstoesse']) for e in ergebnisse)}, "
          f"Richter-Kosten ${llm.session_cost()['usd']:.3f}", flush=True)
    ZIEL.mkdir(parents=True, exist_ok=True)
    out = ZIEL / f"ask-{label}.json"
    out.write_text(json.dumps({"label": label, "judge": gold.JUDGE_MODEL, "cases": ergebnisse},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Gold-Fälle für Frag den Rat")
    ap.add_argument("--label", required=True)
    ap.add_argument("--nur", default=None, help="nur diesen Fall")
    ap.add_argument("--basis", default="http://127.0.0.1:8000")
    ap.add_argument("--konto", default=None, help="Konto-Adresse fürs Token (Vorgabe wie Rauchprobe)")
    a = ap.parse_args()
    lauf(a.basis, a.label, a.nur, a.konto)


if __name__ == "__main__":
    main()
