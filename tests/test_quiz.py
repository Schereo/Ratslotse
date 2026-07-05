"""Tests für die Quiz-Generierung + -Speicherung (ohne Netz/LLM).

Der Generierungs-Pfad wird gegen ein Fixture-JSON getestet (LLM gemockt); die
Live-Quellen (Wikipedia/oldenburg.de) und der echte LLM-Aufruf werden hier
bewusst NICHT angefasst.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import geo, quiz
from council.store import CouncilStore


# ---- Gebiets-Geometrie (Spiegel von lib/stadtteile.ts) ----------------------

def test_geo_taxonomy():
    assert len(geo.stadtteile()) == 31
    assert geo.WAHLBEREICHE == [1, 2, 3, 4, 5, 6]
    assert geo.wahlbereiche_of("Osternburg") == [5, 2]      # überwiegend 5, ragt in 2
    assert geo.wahlbereiche_of("Eversten") == [6]
    assert "Fliegerhorst" in geo.stadtteile_im_wahlbereich(3)


def test_geo_multi_wahlbereich():
    # Grenzstadtteile werden in ALLEN zugehörigen Wahlbereichen gelistet.
    assert geo.wahlbereiche_of("Bürgerfelde") == [1, 3]     # der Fall aus dem Feedback
    assert "Bürgerfelde" in geo.stadtteile_im_wahlbereich(1)
    assert "Bürgerfelde" in geo.stadtteile_im_wahlbereich(3)
    assert "Osternburg" in geo.stadtteile_im_wahlbereich(5)
    assert "Osternburg" in geo.stadtteile_im_wahlbereich(2)
    # eindeutige Stadtteile bleiben einfach
    assert geo.stadtteile_im_wahlbereich(6).count("Nordmoslesfehn") == 1


def test_geo_point_in_stadtteil():
    # bekannte Koordinaten (wie in lib/stadtteile.ts verifiziert)
    assert geo.stadtteil_for(53.1720, 8.1850) == "Fliegerhorst"
    assert geo.stadtteil_for(53.128, 8.175) == "Eversten"
    assert geo.stadtteil_for(53.253, 8.32) is None  # Umland


# ---- Parser + Validierung ---------------------------------------------------

def test_parse_handles_code_fence():
    payload = {"questions": [{"question": "x"}]}
    assert quiz._parse("```json\n" + json.dumps(payload) + "\n```") == payload["questions"]
    assert quiz._parse(json.dumps(payload)) == payload["questions"]


def test_valid_rejects_bad_questions():
    good = {"question": "In welchem Jahr wurde X eingemeindet?",
            "options": ["1922", "1913", "1891", "1945"], "correct_index": 0, "category": "geschichte"}
    assert quiz._valid(good)
    assert not quiz._valid({**good, "options": ["1922", "1913", "1891"]})       # nur 3
    assert not quiz._valid({**good, "options": ["1922", "1922", "1891", "1945"]})  # Dublette
    assert not quiz._valid({**good, "correct_index": 4})                          # außerhalb
    assert not quiz._valid({**good, "category": "quatsch"})                       # unbekannte Kategorie
    assert not quiz._valid({**good, "question": "kurz"})                          # zu kurz


def test_content_hash_stable_and_distinct():
    a = quiz._content_hash("stadtteil", "Osternburg", "Frage A?")
    assert a == quiz._content_hash("stadtteil", "Osternburg", "  frage a? ")  # normalisiert
    assert a != quiz._content_hash("stadtteil", "Osternburg", "Frage B?")
    assert a != quiz._content_hash("stadtteil", "Eversten", "Frage A?")


def _fake_llm(questions: list[dict]):
    def chat_complete(**kwargs):
        content = json.dumps({"questions": questions})
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)
    return chat_complete


def test_generate_for_area_parses_and_tags(monkeypatch):
    qs = [
        {"category": "geschichte", "difficulty": "leicht", "question": "Wann wurde X eingemeindet?",
         "options": ["1922", "1913", "1891", "1945"], "correct_index": 0, "explanation": "1922."},
        {"category": "orte", "difficulty": "mittel", "question": "Welches Wahrzeichen steht in X?",
         "options": ["Kirche", "Turm", "Brücke", "Mühle"], "correct_index": 0, "explanation": "…"},
        {"category": "quatsch", "question": "ungültig", "options": ["a", "b", "c", "d"], "correct_index": 0},
    ]
    monkeypatch.setattr(quiz.llm, "chat_complete", _fake_llm(qs))
    rows = quiz.generate_for_area("stadtteil", "Osternburg", "Stadtteil Osternburg",
                                  "x" * 500, n=3, source_type="wikipedia", source_ref="http://w",
                                  verify=False)
    assert len(rows) == 2  # die ungültige Kategorie fliegt raus
    r = rows[0]
    assert r["area_type"] == "stadtteil" and r["area_key"] == "Osternburg"
    assert r["source_type"] == "wikipedia" and r["content_hash"]
    assert len(r["options"]) == 4 and 0 <= r["correct_index"] < 4


def test_generate_skips_thin_sources(monkeypatch):
    monkeypatch.setattr(quiz.llm, "chat_complete", _fake_llm([]))  # würde nie aufgerufen
    assert quiz.generate_for_area("stadtteil", "X", "X", "zu kurz", n=3,
                                  source_type="wikipedia", source_ref="", verify=False) == []


# ---- Store-Roundtrip --------------------------------------------------------

def _row(area_key: str, question: str, cat: str = "geschichte") -> dict:
    return {"area_type": "stadtteil", "area_key": area_key, "category": cat,
            "difficulty": "leicht", "question": question,
            "options": ["A", "B", "C", "D"], "correct_index": 1,
            "explanation": "weil B", "source_type": "wikipedia", "source_ref": "http://w",
            "content_hash": quiz._content_hash("stadtteil", area_key, question)}


def test_store_quiz_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    rows = [_row("Osternburg", f"Frage {i}?") for i in range(4)]
    assert store.save_quiz_questions(rows) == 4
    assert store.save_quiz_questions(rows) == 0  # Dedup
    assert store.quiz_area_counts() == {("stadtteil", "Osternburg"): 4}

    picked = store.pick_quiz_questions([("stadtteil", "Osternburg")], None, [], 2)
    assert len(picked) == 2
    for p in picked:  # Lösung darf nicht ausgeliefert werden
        assert "correct_index" not in p and "explanation" not in p
        assert len(p["options"]) == 4

    full = store.get_quiz_question(picked[0]["id"])
    assert full["correct_index"] == 1 and full["explanation"] == "weil B"


def test_store_quiz_retire_and_exclude(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_quiz_questions([_row("Eversten", f"F{i}?") for i in range(3)])
    all_ids = [q["id"] for q in store.pick_quiz_questions([("stadtteil", "Eversten")], None, [], 10)]
    assert len(all_ids) == 3
    # ausgemusterte Frage fliegt aus den Runden
    store.retire_quiz_question(all_ids[0])
    remaining = [q["id"] for q in store.pick_quiz_questions([("stadtteil", "Eversten")], None, [], 10)]
    assert all_ids[0] not in remaining and len(remaining) == 2
    assert store.get_quiz_question(all_ids[0]) is None  # retired → nicht mehr abrufbar
    # exclude_ids meidet schon beantwortete (füllt aber auf, wenn nötig)
    picked = store.pick_quiz_questions([("stadtteil", "Eversten")], None, [remaining[0]], 1)
    assert picked and picked[0]["id"] != remaining[0]


def test_store_pick_category_filter(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_quiz_questions([
        _row("Nadorst", "Geschichte?", "geschichte"),
        _row("Nadorst", "Ort?", "orte"),
    ])
    only_orte = store.pick_quiz_questions([("stadtteil", "Nadorst")], ["orte"], [], 10)
    assert len(only_orte) == 1 and only_orte[0]["category"] == "orte"


# ---- Schätzfrage-Slider (estimate) ------------------------------------------

def test_valid_estimate():
    good = {"qtype": "estimate", "category": "schaetzen",
            "question": "Wie viele Einwohner hat X etwa?",
            "answer_value": 12000, "unit": "Einwohner", "range_min": 2000, "range_max": 30000}
    assert quiz._valid(good)
    assert not quiz._valid({**good, "answer_value": 30000})   # nicht strikt innerhalb
    assert not quiz._valid({**good, "answer_value": 1000})    # unter range_min
    assert not quiz._valid({**good, "unit": ""})              # Einheit fehlt
    assert not quiz._valid({**good, "range_min": "x"})        # nicht numerisch
    assert not quiz._valid({**good, "answer_value": True})    # bool zählt nicht als Zahl


def test_generate_estimate_question(monkeypatch):
    qs = [{"category": "schaetzen", "difficulty": "mittel", "qtype": "estimate",
           "question": "Wie viele Einwohner hat X etwa?",
           "answer_value": 12000, "unit": "Einwohner", "range_min": 2000, "range_max": 30000,
           "explanation": "rund 12.000"}]
    monkeypatch.setattr(quiz.llm, "chat_complete", _fake_llm(qs))
    rows = quiz.generate_for_area("stadtteil", "Osternburg", "Osternburg", "x" * 500,
                                  n=1, source_type="wikipedia", source_ref="http://w", verify=False)
    assert len(rows) == 1
    r = rows[0]
    assert r["qtype"] == "estimate" and r["answer_value"] == 12000.0
    assert r["answer_unit"] == "Einwohner" and r["range_min"] == 2000.0 and r["range_max"] == 30000.0
    assert r["options"] == [] and r["correct_index"] == 0


def _estimate_row(area_key: str, question: str) -> dict:
    return {"area_type": "stadtteil", "area_key": area_key, "category": "schaetzen",
            "difficulty": "mittel", "question": question, "qtype": "estimate",
            "options": [], "correct_index": 0,
            "answer_value": 12000.0, "answer_unit": "Einwohner",
            "range_min": 2000.0, "range_max": 30000.0,
            "explanation": "rund 12.000", "source_type": "wikipedia", "source_ref": "http://w",
            "content_hash": quiz._content_hash("stadtteil", area_key, question)}


def test_store_estimate_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.save_quiz_questions([_estimate_row("Osternburg", "Wie viele Einwohner?")]) == 1
    picked = store.pick_quiz_questions([("stadtteil", "Osternburg")], None, [], 5)
    assert len(picked) == 1
    p = picked[0]
    assert p["qtype"] == "estimate" and p["unit"] == "Einwohner"
    assert p["range_min"] == 2000.0 and p["range_max"] == 30000.0
    assert "answer_value" not in p  # Lösung nicht in der Runde
    full = store.get_quiz_question(p["id"])
    assert full["answer_value"] == 12000.0
