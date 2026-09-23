#!/usr/bin/env python3
"""Golden-Set-Prüfung für den Tragweite-Score (RL-U16).

30 handbewertete Beschlüsse (``scripts/golden_impact.json``) gegen die
LLM-Bewertung halten — VOR dem Voll-Rollout. ``--rate-missing`` bewertet nur
die Golden-Beschlüsse (2 LLM-Batches, billig), sodass die Prüfung dem großen
Backfill vorausgehen kann. Bestanden bei Spearman-Rangkorrelation (über die
Band-Mitten) >= 0.7 UND Band-Trefferquote >= 70 % — sonst Exit 1 (Prompt
nachschärfen, nicht einhängen)::

    python scripts/eval_impact.py --rate-missing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
RHO_MIN = 0.7
HIT_MIN = 0.7


def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def golden_zeilen(store: CouncilStore, *, laut: bool = True) -> list[tuple[dict, dict]]:
    """Die Golden-Beschlüsse dieser Datenbank: ``[(Goldeintrag, Beschlusszeile)]``."""
    golden = json.loads((ROOT / "scripts" / "golden_impact.json").read_text())["golden"]
    rows = []
    for g in golden:
        row = store._conn.execute(
            """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.kind,
                      d.amount_eur, d.impact, cs.committee, cs.session_date
               FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.title LIKE ? ORDER BY d.id LIMIT 1""",
            (f"%{g['match']}%",),
        ).fetchone()
        if row is None:
            if laut:
                print(f"!! nicht gefunden: {g['match']!r} — übersprungen")
            continue
        rows.append((g, dict(row)))
    return rows


def frisch_bewerten(rows: list[tuple[dict, dict]]) -> None:
    """ALLE Golden-Beschlüsse neu bewerten, ohne etwas zu speichern.

    Für den Modell-Prüfstand (``eval/pruefstand.py``): Er misst das Modell,
    das gerade eingestellt ist — ein gespeicherter Wert stammt vom Modell des
    letzten Backfills und sagte über den Kandidaten nichts. Geschrieben wird
    nichts, sonst verschöbe jeder Messlauf die Tragweite im Bestand.
    """
    from council.impact import rate_batch
    zeilen = [d for _, d in rows]
    neu: dict[int, int] = {}
    for i in range(0, len(zeilen), 20):
        for did, score, _reason in rate_batch(zeilen[i : i + 20]):
            neu[did] = score
    for _, d in rows:
        d["impact"] = neu.get(d["id"])


def auswerten(rows: list[tuple[dict, dict]]) -> dict:
    """Spearman über die Band-Mitten und Band-Trefferquote der bewerteten Zeilen."""
    usable = [(g, d) for g, d in rows if d["impact"] is not None]
    if not usable:
        return {"n": 0, "golden": len(rows), "rho": None, "hit_rate": None, "faelle": []}
    mids = [(g["band"][0] + g["band"][1]) / 2 for g, _ in usable]
    scores = [float(d["impact"]) for _, d in usable]
    hits = sum(1 for (g, d) in usable if g["band"][0] <= d["impact"] <= g["band"][1])
    return {
        "n": len(usable), "golden": len(rows),
        "rho": round(_spearman(mids, scores), 4),
        "hit_rate": round(hits / len(usable), 4),
        "faelle": [{"title": d["title"][:90], "impact": d["impact"], "band": g["band"],
                    "im_band": g["band"][0] <= d["impact"] <= g["band"][1]}
                   for g, d in usable],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Tragweite-Score gegen das Golden-Set prüfen")
    ap.add_argument("--rate-missing", action="store_true",
                    help="unbewertete Golden-Beschlüsse zuerst per LLM bewerten")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        rows = golden_zeilen(store)

        missing = [d for _, d in rows if d["impact"] is None]
        if missing and args.rate_missing:
            from council.impact import rate_batch
            print(f"Bewerte {len(missing)} Golden-Beschlüsse …", flush=True)
            for i in range(0, len(missing), 20):
                for did, score, reason in rate_batch(missing[i : i + 20]):
                    store.save_impact(did, score, reason)
            for g, d in rows:
                if d["impact"] is None:
                    d["impact"] = store.get_decision(d["id"])["impact"]

        mass = auswerten(rows)
        if mass["n"] < 20:
            print(f"Nur {mass['n']} bewertete Golden-Beschlüsse — zu wenig für ein Urteil.")
            return 1
        rho, hit_rate = mass["rho"], mass["hit_rate"]

        print(f"\nGolden-Set: {mass['n']} Beschlüsse")
        print(f"Spearman-Rangkorrelation: {rho:.3f}  (Schwelle {RHO_MIN})")
        print(f"Band-Trefferquote:        {hit_rate:.0%}  (Schwelle {HIT_MIN:.0%})")
        for f in sorted(mass["faelle"], key=lambda x: x["impact"], reverse=True):
            mark = "ok " if f["im_band"] else "MISS"
            print(f"  [{mark}] {f['impact']:3} erwartet {f['band']}  {f['title'][:70]}")

        ok = rho >= RHO_MIN and hit_rate >= HIT_MIN
        print("\nBESTANDEN — Mischung kann scharf." if ok
              else "\nNICHT bestanden — Prompt nachschärfen, NICHT einhängen.")
        return 0 if ok else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
