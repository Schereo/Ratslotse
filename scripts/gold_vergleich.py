#!/usr/bin/env python3
"""Gold-Läufe vergleichen — mit Streuung statt Einzelwert.

Ein einzelner Lauf sagt wenig: Am 17.10.2026 ergab derselbe Code einmal
51 %, einmal 45 % Abdeckung, einzelne Fälle schwankten um 20–40 Punkte. Wer
eine Änderung beurteilt, legt deshalb je Seite mindestens zwei Läufe neben-
einander und schaut auf Mittelwert, Spannweite und — für die Suche — den
Kontext-Recall, der keinen Richter braucht.

    .venv/bin/python scripts/gold_vergleich.py --vorher basis-a,basis-b --nachher diaet-a,diaet-b

Labels wie bei ``eval_ask_gold.py --label`` (Dateien ``data/eval_gold/ask-<label>.json``).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "scripts"))

import eval_ask_gold as gold  # noqa: E402

ZIEL = WURZEL / "data" / "eval_gold"


def laden(label: str) -> list[dict]:
    return json.loads((ZIEL / f"ask-{label}.json").read_text(encoding="utf-8"))["cases"]


def kennzahlen(faelle: list[dict]) -> dict:
    """Abdeckung, bestanden, Kontext-Recall und Ursachen eines Laufs."""
    da = gesamt = 0
    ursachen = dict.fromkeys(gold.URSACHEN, 0)
    for c in faelle:
        a, b = gold.kontext_recall(c["material"])
        da, gesamt = da + a, gesamt + b
        for fid in c["wertung"]["verfehlt"]:
            ursachen[gold.ursache(fid, c["material"], c.get("material_gefunden"))] += 1
    return {"abdeckung": statistics.mean(c["wertung"]["abdeckung"] for c in faelle),
            "bestanden": sum(c["wertung"]["bestanden"] for c in faelle),
            "recall": da / gesamt if gesamt else 0.0, "ursachen": ursachen}


def seite(labels: list[str]) -> tuple[list[dict], dict[str, list[float]]]:
    laeufe = [kennzahlen(laden(lab)) for lab in labels]
    je_fall: dict[str, list[float]] = {}
    for lab in labels:
        for c in laden(lab):
            je_fall.setdefault(c["id"], []).append(c["wertung"]["abdeckung"])
    return laeufe, je_fall


def spanne(werte: list[float]) -> str:
    return f"{statistics.mean(werte):.0%}" + (f" ({min(werte):.0%}–{max(werte):.0%})"
                                              if len(werte) > 1 else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vorher", required=True, help="Labels, durch Komma")
    ap.add_argument("--nachher", required=True, help="Labels, durch Komma")
    a = ap.parse_args()
    v_laeufe, v_fall = seite(a.vorher.split(","))
    n_laeufe, n_fall = seite(a.nachher.split(","))
    for name, laeufe in (("vorher", v_laeufe), ("nachher", n_laeufe)):
        print(f"{name:8s} Abdeckung {spanne([x['abdeckung'] for x in laeufe])}, "
              f"bestanden {spanne([x['bestanden'] / 27 for x in laeufe])}, "
              f"Kontext-Recall {spanne([x['recall'] for x in laeufe])}")
        for u in gold.URSACHEN:
            werte = [x["ursachen"][u] for x in laeufe]
            print(f"           {gold.URSACHE_TEXT[u]}: {statistics.mean(werte):.1f}")
    print("\nJe Fall (Mittel vorher → nachher; ★ = Unterschied größer als beide Spannweiten):")
    for fid in sorted(set(v_fall) | set(n_fall)):
        v, n = v_fall.get(fid, []), n_fall.get(fid, [])
        if not v or not n:
            continue
        d = statistics.mean(n) - statistics.mean(v)
        breit = max(max(v) - min(v), max(n) - min(n))
        stern = "★" if abs(d) > breit and abs(d) >= 0.1 else " "
        print(f" {stern} {fid[:40]:40s} {spanne(v):>16s} → {spanne(n):>16s}  {d:+.0%}")


if __name__ == "__main__":
    main()
