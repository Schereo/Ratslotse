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
    assert a == {"begriffe": "Radverkehr Fahrrad Radweg", "typ": "verlauf", "partei": None}
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


def test_analyse_fehler_liefert_fallback(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Provider weg")
    monkeypatch.setattr(qa.llm, "chat_complete", boom)
    a = qa.analyse_query("Frage?")
    assert a == {"begriffe": "Frage?", "typ": "thema", "partei": None}


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
