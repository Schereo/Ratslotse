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
    # `eng` kam mit den Kurzantworten für Punktfragen dazu (12.08.).
    assert a == {"frage": "Wie lief das mit dem Radweg?",
                 "begriffe": "Radverkehr Fahrrad Radweg", "typ": "verlauf", "partei": None,
                 "varianten": [], "eng": False,
                 "rechercheplan": {"intent": "overview", "channels": ["decisions"],
                                    "sort": "relevance", "needs": [], "valid": False}}
    # Zweiter Aufruf kommt aus dem Cache — kein weiterer LLM-Call.
    qa.analyse_query("Wie lief das mit dem Radweg?")
    assert calls["n"] == 1


def test_analyse_varianten_geparst_und_gekappt(monkeypatch):
    """Multi-Query (Task 32): bis zu 2 saubere Varianten, Müll fliegt raus."""
    _llm_antwort(monkeypatch, json.dumps({
        "begriffe": "Stadion", "typ": "thema",
        "varianten": ["Finanzierung des Stadionneubaus", "  B-Plan   Stadion  ",
                      "dritte wird gekappt", 42, ""],
    }))
    a = qa.analyse_query("Wie läuft es mit dem Stadion?")
    assert a["varianten"] == ["Finanzierung des Stadionneubaus", "B-Plan Stadion"]


def test_gross_regel_und_tokenbudget():
    """Task 32: große Themen bekommen Struktur-Erlaubnis und mehr Budget."""
    assert qa._answer_tokens("thema") == 1000
    assert qa._answer_tokens("thema", gross=True) == 2200
    messages, _ = qa._answer_messages(
        "Wie läuft es mit dem Stadion?", [{"id": 1, "title": "T", "beschluss": "B"}],
        gross=True)
    assert "UMFANGREICHES Thema" in messages[0]["content"]
    assert "## " in messages[0]["content"]
    messages, _ = qa._answer_messages(
        "Kurze Frage?", [{"id": 1, "title": "T", "beschluss": "B"}])
    assert "UMFANGREICHES Thema" not in messages[0]["content"]


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
    assert a == {"frage": "Frage?", "begriffe": "Frage?", "typ": "thema", "partei": None,
                 "varianten": [], "eng": False,
                 "rechercheplan": {"intent": "overview", "channels": ["decisions"],
                                    "sort": "relevance", "needs": [], "valid": False}}


def test_rechercheplan_shadow_validiert_und_harte_kanaele_ergaenzt(monkeypatch):
    _llm_antwort(monkeypatch, json.dumps({
        "begriffe": "Ellberg Kreyenbrück Schule", "typ": "thema",
        "rechercheplan": {
            "intent": "position",
            "channels": ["debates", "press", "freies_internet", "debates"],
            "sort": "newest", "needs": ["statements", "locations", "halluzination"],
        },
    }))
    plan = qa.analyse_query("Was sagte Ellberg zu Kreyenbrück?")["rechercheplan"]
    assert plan == {
        "intent": "position", "channels": ["decisions", "debates", "press"],
        "sort": "newest", "needs": ["statements", "locations"], "valid": True,
    }
    resolved = qa.research_plan_with_mandatory(
        plan, typ="person", person=True, place=True)
    assert resolved["mandatory_channels"] == ["decisions", "debates", "places"]
    assert resolved["channels"] == ["decisions", "debates", "places", "press"]
    assert resolved["model_channels"] == ["decisions", "debates", "press"]
    assert resolved["consistency_added"] == ["places"]
    assert resolved["suppressed_channels"] == []


def test_rechercheplan_konsistenz_verknuepft_bedarf_und_kanal():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "status", "channels": ["decisions"], "sort": "newest",
        "needs": ["amounts", "statements", "documents", "current_info",
                  "official_updates", "future_dates"],
    }})
    resolved = qa.research_plan_with_mandatory(plan, typ="thema")
    assert resolved["channels"] == [
        "decisions", "budget", "debates", "documents", "press", "future_agenda",
    ]
    assert resolved["consistency_added"] == [
        "budget", "debates", "documents", "press", "future_agenda",
    ]


def test_current_info_koppelt_presse_und_zukunft_nicht_mehr_pauschal():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "status", "channels": ["decisions"], "sort": "newest",
        "needs": ["current_info"],
    }})
    resolved = qa.research_plan_with_mandatory(plan, typ="verlauf")
    assert resolved["channels"] == ["decisions"]

    presse = qa._research_plan({"rechercheplan": {
        "channels": ["decisions"], "needs": ["official_updates"],
    }})
    zukunft = qa._research_plan({"rechercheplan": {
        "channels": ["decisions"], "needs": ["future_dates"],
    }})
    assert qa.research_plan_with_mandatory(presse, typ="thema")["channels"] == [
        "decisions", "press"]
    assert qa.research_plan_with_mandatory(zukunft, typ="thema")["channels"] == [
        "decisions", "future_agenda"]


def test_rechercheplan_entfernt_debatten_bei_neuester_ortsentscheidung():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions", "debates", "places"],
        "sort": "newest", "needs": ["dates", "statements"],
    }})
    resolved = qa.research_plan_with_mandatory(
        plan, typ="ort", place=True, latest_decision=True)
    assert resolved["channels"] == ["decisions", "places"]
    assert resolved["suppressed_channels"] == ["debates"]


def test_recherchekanal_nur_bei_validem_plan_gesteuert():
    assert qa.research_channel_enabled(
        {"valid": True, "channels": ["decisions", "debates"]}, "debates")
    assert not qa.research_channel_enabled(
        {"valid": True, "channels": ["decisions", "documents"]}, "debates")
    # Provider-/Promptfehler dürfen keine bisher verfügbaren Quellen verstecken.
    assert qa.research_channel_enabled(
        {"valid": False, "channels": ["decisions"]}, "debates")
    assert not qa.research_channel_enabled(
        {"valid": False, "channels": ["decisions"]}, "debates", fallback=False)


def test_rechercheplan_shadow_loggt_keinen_fragetext():
    plan = qa.research_plan_with_mandatory(
        qa._research_plan({}), typ="geld", place=True)
    record = qa.research_plan_log_record(
        "Was kostet die Sporthalle in Kreyenbrück?", plan, "geld",
        {"decisions": 4, "budget": 2, "places": 4},
    )
    text = json.dumps(record, ensure_ascii=False)
    assert record["event"] == "qa_research_plan_shadow"
    assert len(record["question_hash"]) == 16
    assert "Sporthalle" not in text and "Kreyenbrück" not in text
    assert record["plan"]["mandatory_channels"] == ["decisions", "budget", "places"]


def test_sort_verlauf_aelteste_zuerst():
    ctx = [{"id": 3, "session_date": "2026-01-01"}, {"id": 1, "session_date": None},
           {"id": 2, "session_date": "2024-06-01"}]
    assert [c["id"] for c in qa.sort_verlauf(ctx)] == [1, 2, 3]  # None (ältest-unbekannt) zuerst


def test_extra_regeln_deckt_alle_typen():
    assert set(qa.EXTRA_REGELN) == set(qa.QUERY_TYPES)


def test_finde_ort_nutzt_katalog_und_aliase():
    ort = qa.finde_ort("Was wurde auf der Donnerschwee-Kaserne beschlossen?")
    assert ort is not None
    assert ort["id"] == "neu-donnerschwee"
    assert ort["name"] == "Neu-Donnerschwee"


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


def test_ort_ist_mit_geldtyp_kombinierbar_und_fundstelle_im_kontext():
    ort = {"name": "Kreyenbrück", "kind_label": "Ortsbereich"}
    candidates = [{
        "id": 9,
        "title": "Sporthalle",
        "summary": "Die Halle wird saniert.",
        "amount_eur": 2_500_000,
        "location_matches": [{
            "name": "Klingenbergplatz",
            "evidence": "Sanierung am Klingenbergplatz",
        }],
    }]

    messages, _ = qa._answer_messages(
        "Was kostet die Sanierung in Kreyenbrück?", candidates, typ="geld", ort=ort)
    prompt = messages[0]["content"]

    assert "konkreten Summen" in prompt
    assert "ORTSFILTER" in prompt
    assert "Kreyenbrück" in prompt
    assert "Ortsbezug: Klingenbergplatz; Fundstelle: Sanierung am Klingenbergplatz" in prompt


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


def test_orte_fuer_decisions(tmp_path):
    # 5a/I-10: erste verortete ORTS-Entität je Beschluss; Organisationen und
    # ungeocodete Entitäten liefern keinen Pin.
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?,?,?,?,?)",
            [(1, "caeci", "Cäcilienbrücke", "ort", 30),
             (2, "huntebad", "Huntebad", "ort", 5),
             (3, "vhs", "VHS Oldenburg", "organisation", 9),
             (4, "hannover", "Hannover", "ort", 20)])
        store._conn.executemany(
            "INSERT INTO council_entity_meta (slug, lat, lon) VALUES (?,?,?)",
            [("caeci", 53.135, 8.215), ("vhs", 53.14, 8.21),
             ("hannover", 52.3759, 9.7320)])  # huntebad ohne Geo
        store._conn.executemany(
            "INSERT INTO council_entity_links (entity_id, decision_id) VALUES (?,?)",
            [(1, 100), (2, 100), (3, 100), (2, 200), (3, 300), (4, 400)])
    orte = store.orte_fuer_decisions([100, 200, 300, 400])
    assert orte[100]["ort_name"] == "Cäcilienbrücke" and orte[100]["lat"] == 53.135
    assert 200 not in orte  # Huntebad hat keine Koordinaten
    assert 300 not in orte  # Organisation zählt nicht als Pin
    assert 400 not in orte  # Vergleichsort außerhalb Oldenburgs
    assert store.orte_fuer_decisions([]) == {}
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


def test_qa_feedback_korrektur_ueberschreibt(tmp_path):
    # Ein Konto hat je Frage EINE Stimme: Grund-Nachtrag und Meinungsänderung
    # überschreiben die frühere Zeile, statt sich zu widersprechen.
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_qa_feedback("Wie lief es?", "Antwort", "down", None, user_id=7)
    store.save_qa_feedback("Wie lief es?", "Antwort", "down", "zu vage", user_id=7)
    store.save_qa_feedback("Wie lief es?", "Antwort", "up", None, user_id=7)
    rows = store._conn.execute(
        "SELECT bewertung, grund FROM council_qa_feedback WHERE user_id = 7").fetchall()
    assert len(rows) == 1, "Korrektur darf keine zweite Zeile anlegen"
    assert rows[0]["bewertung"] == "up"
    assert rows[0]["grund"] is None, "Grund des Daumen-runter ist nach der Korrektur hinfällig"
    # Andere Frage und anonyme Rückmeldungen bleiben eigene Zeilen.
    store.save_qa_feedback("Und sonst?", None, "down", None, user_id=7)
    store.save_qa_feedback("Wie lief es?", None, "down", None)
    store.save_qa_feedback("Wie lief es?", None, "up", None)
    assert store._conn.execute("SELECT count(*) FROM council_qa_feedback").fetchone()[0] == 4
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


def test_beschluss_kontext_traegt_deutsches_datum():
    """Die Kandidatenzeile ist die Datums-Quelle der Antwort: stand dort ISO,
    schrieb das Modell „am 2026-06-01" in den Fließtext (Tims Befund 10.08.)."""
    messages, _ = qa._answer_messages(
        "Was wurde zum Stadion entschieden?",
        [{"id": 7, "title": "Stadionneubau", "beschluss": "Zugestimmt.",
          "committee": "Rat", "session_date": "2026-06-01", "outcome": "angenommen"}])
    prompt = messages[0]["content"]
    assert "01.06.2026" in prompt
    assert "2026-06-01" not in prompt
