"""Protokoll-Chunking (council/protocols.py): lange Niederschriften werden an
TOP-Grenzen zerlegt und die Teil-Extraktionen zusammengeführt — statt der
früheren stillen Kappung bei MAX_INPUT_CHARS, die alle späteren TOPs verschluckte.

Reine Text-/Merge-Logik — kein Netz, kein LLM.
"""
from council.protocols import _merge_parts, _split_protocol


def _top(n: int) -> str:
    return f"TOP {n}.1 Beschluss über Vorhaben {n}\n" + ("Inhaltszeile. " * 300) + "\n"


def test_kurzer_text_bleibt_ein_teil():
    assert _split_protocol("kurz", max_chars=1000) == ["kurz"]


def test_langer_text_schneidet_an_top_grenzen():
    tops = [_top(i) for i in range(1, 11)]
    text = "".join(tops)
    parts = _split_protocol(text, max_chars=len(text) // 3)
    assert len(parts) >= 3
    assert "".join(parts) == text  # nichts geht verloren, nichts doppelt
    # Folgeteile beginnen an einer TOP-Kopfzeile (sauberer Schnitt).
    assert all(p.lstrip().startswith("TOP ") for p in parts[1:])


def test_hard_cut_fallback_ohne_topzeilen():
    text = "x" * 5000
    parts = _split_protocol(text, max_chars=2000)
    assert "".join(parts) == text
    assert all(len(p) <= 2000 for p in parts)


def test_merge_kopf_aus_erstem_ende_aus_letztem_teil():
    merged = _merge_parts([
        {"protocol_nr": None, "session_start": "16:00", "session_end": None,
         "attendance": [{"name": "A"}], "decisions": [{"item_number": "1", "title": "Eins"}]},
        {"protocol_nr": "R 05/26", "session_start": None, "session_end": "19:45",
         "attendance": [], "decisions": [{"item_number": "2", "title": "Zwei"}]},
    ])
    assert merged["protocol_nr"] == "R 05/26"
    assert merged["session_start"] == "16:00"
    assert merged["session_end"] == "19:45"
    assert merged["attendance"] == [{"name": "A"}]
    assert [d["title"] for d in merged["decisions"]] == ["Eins", "Zwei"]


def test_merge_verwirft_dubletten_an_schnittkanten():
    merged = _merge_parts([
        {"decisions": [{"item_number": "9.4", "title": "Radweg Alexanderstraße"}]},
        {"decisions": [{"item_number": "9.4", "title": "Radweg Alexanderstraße"},
                       {"item_number": "9.5", "title": "Neues"}]},
    ])
    assert [d["item_number"] for d in merged["decisions"]] == ["9.4", "9.5"]
