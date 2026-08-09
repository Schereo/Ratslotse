"""Fragetyp-Routing der KI-Frage (Stufe 2): Analyse, Chronik, Partei-Anreicherung.

Offline — der LLM-Call der Analyse wird gemockt, der Store läuft in tmp_path.
"""
import json
from types import SimpleNamespace

import pytest

from council import qa
from council.store import CouncilStore


def _llm_antwort(monkeypatch, content: str):
    calls = {"n": 0}

    def fake(**kwargs):
        calls["n"] += 1
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    monkeypatch.setattr(qa.llm, "chat_complete", fake)
    return calls


@pytest.fixture(autouse=True)
def _leerer_cache():
    qa._ANALYSE_CACHE.clear()
    yield
    qa._ANALYSE_CACHE.clear()


def test_analyse_parst_sauberes_json(monkeypatch):
    calls = _llm_antwort(monkeypatch, json.dumps(
        {"begriffe": "Radverkehr Fahrrad Radweg", "typ": "verlauf", "partei": None}))
    a = qa.analyse_query("Wie lief das mit dem Radweg?")
    assert a == {"frage": "Wie lief das mit dem Radweg?",
                 "begriffe": "Radverkehr Fahrrad Radweg", "typ": "verlauf", "partei": None}
    # Zweiter Aufruf kommt aus dem Cache — kein weiterer LLM-Call.
    qa.analyse_query("Wie lief das mit dem Radweg?")
    assert calls["n"] == 1


def test_analyse_partei_nur_bei_partei_typ(monkeypatch):
    _llm_antwort(monkeypatch, json.dumps(
        {"begriffe": "Wohnraum", "typ": "geld", "partei": "SPD"}))
    # partei wird verworfen, wenn der Typ nicht "partei" ist — sonst filtert
    # eine Geld-Frage plötzlich nach Fraktion.
    assert qa.analyse_query("Was kostet das?")["partei"] is None


def test_analyse_faellt_bei_muell_auf_thema(monkeypatch):
    _llm_antwort(monkeypatch, "kein json {")
    a = qa.analyse_query("Was wurde zum Hafen beschlossen?")
    assert a["typ"] == "thema"
    assert a["begriffe"] == "Was wurde zum Hafen beschlossen?"
    _llm_antwort(monkeypatch, json.dumps({"begriffe": "Hafen", "typ": "quatsch"}))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Hafenfrage?")["typ"] == "thema"


def test_analyse_kondensiert_mit_verlauf(monkeypatch):
    calls = _llm_antwort(monkeypatch, json.dumps(
        {"frage": "Was kostet der Neubau der Cäcilienbrücke?",
         "begriffe": "Kosten Neubau Cäcilienbrücke", "typ": "geld", "partei": None}))
    verlauf = [{"frage": "Wie ist der Stand bei der Cäcilienbrücke?",
                "antwort": "Der Rat forderte das WSA zur Beschleunigung auf. " * 20}]
    a = qa.analyse_query("Und was kostet das?", verlauf=verlauf)
    assert a["frage"] == "Was kostet der Neubau der Cäcilienbrücke?"
    # Cache-Schlüssel enthält den Verlauf: gleiche Frage OHNE Verlauf ist ein
    # eigener Eintrag und trifft nicht denselben Cache.
    _llm_antwort(monkeypatch, json.dumps({"frage": "Und was kostet das?",
                                          "begriffe": "Kosten", "typ": "geld"}))
    b = qa.analyse_query("Und was kostet das?")
    assert b["frage"] == "Und was kostet das?"


def test_verlauf_zeilen_kuerzt_und_begrenzt():
    runden = [{"frage": f"Frage {i}?", "antwort": "A" * 1000} for i in range(6)]
    text = qa._verlauf_zeilen(runden)
    # Nur die letzten VERLAUF_MAX_RUNDEN, Antworten gekürzt.
    assert text.count("- Frage:") == qa.VERLAUF_MAX_RUNDEN
    assert "Frage 5?" in text and "Frage 0?" not in text
    assert "A" * (qa._VERLAUF_ANTWORT_MAX + 1) not in text
    assert qa._verlauf_zeilen(None) == ""


def test_antwortprompt_traegt_gespraechskontext():
    messages, _ = qa._answer_messages(
        "Und wer ist zuständig?", [],
        verlauf=[{"frage": "Stand Cäcilienbrücke?", "antwort": "Resolution ans WSA."}])
    assert "Dies ist eine Anschlussfrage in einem Gespräch" in messages[0]["content"]
    assert "Resolution ans WSA." in messages[0]["content"]
    messages, _ = qa._answer_messages("Frage?", [])
    assert "Dies ist eine Anschlussfrage" not in messages[0]["content"]


def test_analyse_fehler_liefert_fallback(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Provider weg")
    monkeypatch.setattr(qa.llm, "chat_complete", boom)
    a = qa.analyse_query("Frage?")
    assert a == {"frage": "Frage?", "begriffe": "Frage?", "typ": "thema", "partei": None}


def test_sort_verlauf_aelteste_zuerst():
    ctx = [{"id": 3, "session_date": "2026-01-01"}, {"id": 1, "session_date": None},
           {"id": 2, "session_date": "2024-06-01"}]
    assert [c["id"] for c in qa.sort_verlauf(ctx)] == [1, 2, 3]  # None (ältest-unbekannt) zuerst


def test_extra_regeln_deckt_alle_typen():
    assert set(qa.EXTRA_REGELN) == set(qa.QUERY_TYPES)


def test_kontext_markiert_antragsteller_und_volumen():
    ctx = qa._build_context([
        {"id": 7, "title": "Radweg", "summary": "Bau", "factions": json.dumps(["SPD", "Grüne"]),
         "amount_eur": 1500000},
    ])
    assert "Antrag von: SPD, Grüne" in ctx
    assert "Volumen: 1.500.000 €" in ctx


def test_antwortprompt_bekommt_extra_regeln():
    messages, _ = qa._answer_messages("Wie lief es?", [], typ="verlauf")
    assert "VERLAUF" in messages[0]["content"]
    messages, _ = qa._answer_messages("Was ist?", [], typ="thema")
    assert "VERLAUF" not in messages[0]["content"]


def test_antrag_decision_ids_findet_fraktion(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (1, 'Rat', '2026-01-01', '18:00', 'Rathaus', '')")
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, title, factions, vorlage_nr) "
            "VALUES (1, 0, 'decision', 'Radweg-Antrag', '[\"SPD\"]', '26/1')")
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, title, factions) "
            "VALUES (1, 1, 'decision', 'Verwaltungsvorlage', '[]')")
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, title, factions) "
            "VALUES (1, 2, 'subvote', 'Änderungsantrag SPD', '[\"SPD\"]')")
    ids = store.antrag_decision_ids("SPD")
    # Nur der Hauptbeschluss mit SPD als Antragsteller — Subvotes sind nicht
    # eigenständig zitierbar, die Verwaltungsvorlage hat keinen Antragsteller.
    rows = store.get_decisions_by_ids(ids)
    assert [r["title"] for r in rows] == ["Radweg-Antrag"]
    store.close()


def test_qa_feedback_speichern(tmp_path):
    # 5a/I-03: Daumen landen mit gekappten Feldern in council_qa_feedback.
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_qa_feedback("Wie lief es?", "Antwort " * 200, "down", "  zu vage  ", user_id=7)
    store.save_qa_feedback("Und sonst?", None, "up", None)
    rows = store._conn.execute(
        "SELECT frage, bewertung, grund, user_id, length(antwort_auszug) AS al "
        "FROM council_qa_feedback ORDER BY id").fetchall()
    assert rows[0]["bewertung"] == "down" and rows[0]["grund"] == "zu vage"
    assert rows[0]["user_id"] == 7 and rows[0]["al"] <= 500
    assert rows[1]["bewertung"] == "up" and rows[1]["grund"] is None
    import pytest as _pytest
    with _pytest.raises(ValueError):
        store.save_qa_feedback("x", None, "meh", None)
    store.close()


def test_juengste_sitzungen_mit_beschluessen(tmp_path):
    # 5a/I-07: Futter für frische Beispielfragen — nur Sitzungen MIT
    # extrahierten Beschlüssen, neueste zuerst.
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for ksinr, datum in ((1, "2026-06-01"), (2, "2026-07-01"), (3, "2026-07-15")):
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                "VALUES (?, ?, ?, '18:00', '', '')", (ksinr, f"Gremium {ksinr}", datum))
        for ksinr in (1, 2):  # Sitzung 3 bleibt ohne Beschlüsse (kein Protokoll)
            store._conn.execute(
                "INSERT INTO council_decisions (ksinr, position, kind, title) "
                "VALUES (?, 0, 'decision', 'X')", (ksinr,))
    rows = store.juengste_sitzungen_mit_beschluessen(limit=2)
    assert [r["session_date"] for r in rows] == ["2026-07-01", "2026-06-01"]
    assert rows[0]["committee"] == "Gremium 2" and rows[0]["n"] == 1
    store.close()


def test_haushalt_block_und_matching(tmp_path):
    ctx = qa._haushalt_block([{"year": 2026, "bereich": "Verkehr und Straßenbau",
                               "aufwendungen": 46194645.0, "ertraege": 17510637.0}])
    assert "STADTHAUSHALT" in ctx and "46.194.645" in ctx
    assert qa._haushalt_block([]) == ""

    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, ergebnis, is_summe, fetched_at) "
            "VALUES (2026, 'Verkehr und Straßenbau', 1, 2, -1, 0, '')")
        store._conn.execute(
            "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, ergebnis, is_summe, fetched_at) "
            "VALUES (2026, 'Summe', 10, 20, -10, 1, '')")
    assert [r["bereich"] for r in store.haushalt_fuer_begriffe(["Verkehr", "Radweg"])] == ["Verkehr und Straßenbau"]
    # Summenzeile nur bei ausdrücklicher Haushaltsfrage.
    assert store.haushalt_fuer_begriffe(["Kita"]) == []
    assert [r["bereich"] for r in store.haushalt_fuer_begriffe(["Haushalt"])] == ["Summe"]
    store.close()
