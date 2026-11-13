#!/usr/bin/env python3
"""Messlauf: Spezialleser gegen eval/spezialleser_gold.json (Plan Vorlagen, Schritt 17).
Lädt die PDFs aus dem Ratsinfo (1 Abruf/s), ohne Modell, ohne Kosten.

    .venv/bin/python eval/run_spezialleser.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import spezialleser, vorlagen  # noqa: E402


def _pdf(document_id: int) -> bytes:
    r = vorlagen._session.get(f"https://buergerinfo.oldenburg.de/getfile.php?id={document_id}&type=do",  # noqa: SLF001
                              timeout=60)
    r.raise_for_status()
    time.sleep(1)
    return r.content


def main() -> int:
    gold = json.loads((ROOT / "eval" / "spezialleser_gold.json").read_text())
    ok = n = 0
    for g in gold["pruefvermerke"]:
        v = spezialleser.pruefvermerke(_pdf(g["document_id"]))
        ist = {c: sum(1 for x in v if x["code"] == c) for c in ("B", "WB", "H", "K")}
        soll = {c: g[c] for c in ("B", "WB", "H", "K")}
        n += 1
        ok += ist == soll
        print(f"{'✓' if ist == soll else '✗'} {g['label']}: {ist} (Gold {soll})")
    for g in gold["abwaegung"]:
        a = spezialleser.abwaegung(_pdf(g["document_id"])) or {}
        treffer = a.get("statements") == g["statements"] and a.get("public") == g["public"]
        n += 1
        ok += treffer
        print(f"{'✓' if treffer else '✗'} {g['label']}: {a}")
    print(f"\n{ok}/{n} richtig")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
