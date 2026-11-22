"""Lottis Satz zur Sitzung: gerechnet gegen vom Modell geschrieben, an echten
vergangenen Sitzungen (Tims Wunsch 11.11.2026: „möglichst natürlich“).

Je Sitzung ein Modellaufruf (``council/session_summary.py``). Ohne Protokoll
entsteht der Satz „vor dem Protokoll“ (was ansteht), mit Protokoll „nach dem
Protokoll“ (was herauskam); ``--beide`` schreibt für Sitzungen mit Protokoll
zusätzlich die Vorher-Fassung. Ergebnis: eine Markdown-Gegenüberstellung unter
``eval/results/sitzung_satz/``, dazu die Kosten.

    python eval/run_sitzung_satz.py --limit 1          # Kostenprobe
    python eval/run_sitzung_satz.py --beide            # die zwölf Sitzungen unten
    python eval/run_sitzung_satz.py --ksinr 4705 4709  # einzelne
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
load_dotenv(WURZEL / ".env")

from council import session_summary  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import llm  # noqa: E402

ERGEBNISSE = WURZEL / "eval" / "results" / "sitzung_satz"
#: Sechs ohne Protokoll (Rat zweimal, Finanzen, Bauen, Verkehr, Jugendhilfe),
#: sechs mit (Rat, Wirtschaft, Finanzen, Bauen mit 60 Punkten, Verkehr, Soziales).
SITZUNGEN = [4709, 4708, 4641, 4608, 4654, 4675, 4705, 4618, 4640, 4607, 4653, 4632]


def ergebnisse(store: CouncilStore, ksinr: int) -> dict[str, str | None]:
    """Punkt („Ö 7.1“) → Ergebnis aus dem Protokoll; leer ohne Protokoll."""
    zeilen = store._conn.execute(
        "SELECT item_number, outcome FROM council_decisions WHERE ksinr = ? AND kind = 'decision'",
        (ksinr,)).fetchall()
    return {f"Ö {r['item_number']}": r["outcome"] for r in zeilen if r["outcome"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    ap.add_argument("--db", default=os.environ.get("COUNCIL_DB") or str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--ksinr", type=int, nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--beide", action="store_true", help="mit Protokoll auch die Vorher-Fassung")
    ap.add_argument("--label", default=datetime.now().strftime("%Y%m%d-%H%M"))
    a = ap.parse_args()

    store = CouncilStore(a.db)
    liste = a.ksinr or SITZUNGEN
    if a.limit:
        liste = liste[:a.limit]
    start = llm.session_cost()["usd"]
    teile = [f"# Lottis Satz zur Sitzung — Lauf {a.label}", "",
             f"Modell `{session_summary.MODEL}`, Prompt `session_summary_system`.", ""]
    for ksinr in liste:
        sitzung = store.get_session(ksinr)
        kurs = store.session_course(ksinr)
        if not sitzung or not kurs:
            print(f"{ksinr}: keine Tagesordnung")
            continue
        kurz = store.agenda_summaries_for(ksinr)
        erg = ergebnisse(store, ksinr)
        faelle = [("nach dem Protokoll", erg)] if erg else [("vor dem Protokoll", {})]
        if erg and a.beide:
            faelle.append(("vor dem Protokoll", {}))
        teile += [f"## {sitzung['committee']} · {sitzung['session_date']} (ksinr {ksinr})", "",
                  f"**Gerechnet:** {kurs['summary'] or '—'}", ""]
        for stand, e in faelle:
            stoff = session_summary.material(sitzung["committee"], sitzung["session_date"], kurs["items"], kurz, e)
            satz = session_summary.generate(stoff)
            print(f"{ksinr} {stand}: {satz}")
            teile += [f"**Modell, {stand}:** {satz or '— (keine Antwort)'}", ""]
        teile.append("")
    usd = llm.session_cost()["usd"] - start
    teile += ["---", f"Kosten des Laufs: {usd:.4f} $ für {len(liste)} Sitzungen ({date.today().isoformat()})."]
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    ziel = ERGEBNISSE / f"{a.label}.md"
    ziel.write_text("\n".join(teile) + "\n")
    print(f"\n{usd:.4f} $ · {ziel.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
