"""Wahlfragen zur Ratswahl 2026 (Plan Q12) — aus dem eingefrorenen Ergebnis."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app.election import quiz_questions as wq  # noqa: E402


def test_nothing_before_the_runoff():
    assert wq.questions(date(2026, 9, 27)) == []


def test_parties_by_rule_and_turnout_from_the_archive():
    qs = wq.questions(date(2026, 9, 28))
    assert qs, "das Archiv kommunalwahl/referenz-2026 muss Fragen tragen"
    texts = [q["question"] for q in qs]
    # Jede Partei ab 5 % in der Stadt, keine darunter (FDP 3,8 %, Volt 4,1 %).
    for party in ("die Grünen", "die SPD", "die CDU", "die Linke", "die AfD"):
        assert any(party in t for t in texts), party
    assert not any("FDP" in t or "Volt" in t for t in texts)
    assert any("holten die Grünen" in t for t in texts) and any("holte die SPD" in t for t in texts)
    assert any("Wahlbeteiligung" in t for t in texts)
    for q in qs:
        chart = json.loads(q["chart"])
        vals = {i["label"]: i["value"] for i in chart["items"]}
        right = q["options"][q["correct_index"]]
        assert vals[right] == max(vals.values())
        assert abs(vals[q["options"][0]] - vals[q["options"][1]]) >= wq.MIN_GAP_PP - 0.1
        assert q["format"] == "compare" and (q["area_type"], q["area_key"]) == wq.AREA
        assert q["source_ref"].startswith("https://votemanager.kdo.de/")


def test_keys_are_stable():
    a = [q["content_hash"] for q in wq.questions(date(2026, 10, 1))]
    b = [q["content_hash"] for q in wq.questions(date(2026, 12, 1))]
    assert a == b and len(set(a)) == len(a)
