#!/usr/bin/env python3
"""Wirkt der Punkt-Bezug? — Messung aus Schritt 4.5 der Sitzungsseite.

Plan: ``docs/plan-sitzungsseite-kurs.md``, Schritt 4, Punkt 5. Auf der
Punkt-Seite schickt „Frag den Rat“ den Tagesordnungspunkt als
``screen.refs`` mit (Bezug-Chip). Gemessen wird, ob Fragen ohne Gegenstand
im Wortlaut („Und was kostet das?“) dadurch den RICHTIGEN Punkt beantworten.

Je Punkt und Frage zwei Läufe gegen einen laufenden lokalen Server — mit und
ohne ``refs`` — über die echte ``/api/council/ask``-Strecke. Ob die Antwort
beim Punkt ist, entscheidet zuerst eine Wortprobe (die Kennwörter des
Punkts); die Antworten stehen zum Nachlesen in der Ausgabe.

    python scripts/dev.py start          # mit OPENROUTER_API_KEY, DISABLE_RATE_LIMIT=1
    python eval/run_punkt_bezug.py --basis http://127.0.0.1:8602 --limit 1   # Kostenprobe
    python eval/run_punkt_bezug.py --basis http://127.0.0.1:8602
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import httpx

WURZEL = Path(__file__).resolve().parents[1]
ERGEBNISSE = WURZEL / "eval" / "results" / "punkt_bezug"

#: (ksinr, Punkt, Kennwörter — eines davon muss in einer Antwort zum Punkt stehen)
PUNKTE = (
    (4654, "Ö 9", ("D-Ticket", "Deutschland-Ticket", "Deutschlandticket", "Sozialticket", "26/0719")),
    (4650, "Ö 10.3", ("Junkerstraße", "Schulstraße", "Ausnahmegenehmigung", "26/0253")),
    (4702, "Ö 8.1", ("VBN", "Tarif", "Fahrpreis", "26/0622")),
)
#: Fragen ohne Gegenstand im Wortlaut — wie sie neben einem Punkt gestellt werden.
FRAGEN = (
    "Und was kostet das?",
    "Wer hat das beantragt?",
    "Worum geht es dabei in einfachen Worten?",
    "Was sagt die Verwaltung dazu?",
    "Wurde das schon beschlossen?",
    "Wann wird darüber entschieden?",
    "Was spricht dagegen?",
    "Gab es dazu früher schon Beschlüsse?",
    "Wie geht es damit weiter?",
    "Wer ist dafür?",
)


def fragen(c: httpx.Client, frage: str, refs: dict | None) -> tuple[str, float]:
    body: dict = {"question": frage, "history": []}
    if refs:
        body["screen"] = {"route": "/council/punkt", "refs": refs}
    text, start = [], time.monotonic()
    with c.stream("POST", "/api/council/ask", json=body, timeout=240) as r:
        r.raise_for_status()
        for zeile in r.iter_lines():
            if not zeile.startswith("data:"):
                continue
            try:
                ev = json.loads(zeile[5:].strip())
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "token":
                text.append(ev.get("text") or ev.get("token") or "")
            elif ev.get("type") == "replace":
                text = [ev.get("text") or ""]
    return "".join(text).strip(), time.monotonic() - start


def kosten(db: Path, seit: str) -> float:
    """Echte Kosten seit ``seit`` aus der Kostentabelle des lokalen Servers."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        return float(con.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE ts >= ?", (seit,)).fetchone()[0])
    except sqlite3.Error:
        return -1.0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--basis", default="http://127.0.0.1:8602")
    #: Je Punkt ein eigenes Saat-Konto: Das Tageskontingent der Frage zählt je
    #: Konto, und 20 Fragen je Punkt passen in eins (erster Lauf brach nach 48 ab).
    ap.add_argument("--konten", default="nutzerin@example.org,ratsfrau@example.org,chef@example.org")
    ap.add_argument("--passwort", default="password123")
    ap.add_argument("--limit", type=int, default=0, help="nur so viele Fragen je Punkt (Kostenprobe)")
    a = ap.parse_args()

    seit = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    konten = [k.strip() for k in a.konten.split(",") if k.strip()]
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    pfad = ERGEBNISSE / f"{datetime.now():%Y%m%d-%H%M}.json"
    zeilen = []
    for i, (ksinr, nr, worte) in enumerate(PUNKTE):
        c = httpx.Client(base_url=a.basis)
        r = c.post("/api/auth/login", json={"email": konten[i % len(konten)], "password": a.passwort})
        r.raise_for_status()
        # Das Sitzungs-Cookie trägt ``Secure`` und reist über http nicht von selbst mit.
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
        for frage in FRAGEN[: a.limit or None]:
            for mit in (True, False):
                antwort, dauer = fragen(c, frage, {"ksinr": ksinr, "item_number": nr} if mit else None)
                treffer = any(re.search(re.escape(w), antwort, re.I) for w in worte)
                zeilen.append({"ksinr": ksinr, "item_number": nr, "frage": frage, "bezug": mit,
                               "beim_punkt": treffer, "sekunden": round(dauer, 1), "antwort": antwort})
                print(f"{ksinr} {nr} · {'mit ' if mit else 'ohne'} · {'✓' if treffer else '✗'} · {frage}", flush=True)
                pfad.write_text(json.dumps({"zeilen": zeilen}, ensure_ascii=False, indent=1))
    mit = [z for z in zeilen if z["bezug"]]
    ohne = [z for z in zeilen if not z["bezug"]]
    usd = kosten(WURZEL / "data" / "ratslotse.sqlite", seit)
    zusammen = {"mit": f"{sum(z['beim_punkt'] for z in mit)}/{len(mit)}",
                "ohne": f"{sum(z['beim_punkt'] for z in ohne)}/{len(ohne)}", "usd": round(usd, 4)}
    pfad.write_text(json.dumps({"zusammen": zusammen, "zeilen": zeilen}, ensure_ascii=False, indent=1))
    print(f"\nbeim Punkt — mit Bezug {zusammen['mit']}, ohne {zusammen['ohne']} · {usd:.4f} $ · {pfad.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
