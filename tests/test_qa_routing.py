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
        {"terms": "Radverkehr Fahrrad Radweg", "kind": "history", "party": None}))
    a = qa.analyse_query("Wie lief das mit dem Radweg?")
    # `eng` kam mit den Kurzantworten für Punktfragen dazu (12.08.).
    assert a == {"question": "Wie lief das mit dem Radweg?",
                 "terms": "Radverkehr Fahrrad Radweg", "kind": "history", "party": None,
                 "variants": [], "eng": False,
                 "rechercheplan": {"intent": "overview", "channels": ["decisions"],
                                    "sort": "relevance", "needs": [], "valid": False}}
    # Zweiter Aufruf kommt aus dem Cache — kein weiterer LLM-Call.
    qa.analyse_query("Wie lief das mit dem Radweg?")
    assert calls["n"] == 1


def test_analyse_varianten_geparst_und_gekappt(monkeypatch):
    """Multi-Query (Task 32): bis zu 2 saubere Varianten, Müll fliegt raus."""
    _llm_antwort(monkeypatch, json.dumps({
        "terms": "Stadion", "kind": "topic",
        "variants": ["Finanzierung des Stadionneubaus", "  B-Plan   Stadion  ",
                      "dritte wird gekappt", 42, ""],
    }))
    a = qa.analyse_query("Wie läuft es mit dem Stadion?")
    assert a["variants"] == ["Finanzierung des Stadionneubaus", "B-Plan Stadion"]


def test_gross_regel_und_tokenbudget():
    """Task 32: große Themen bekommen Struktur-Erlaubnis und mehr Budget."""
    assert qa._answer_tokens("topic") == 1000
    assert qa._answer_tokens("topic", gross=True) == 2200
    messages, _ = qa._answer_messages(
        "Wie läuft es mit dem Stadion?", [{"id": 1, "title": "T", "official_text": "B"}],
        gross=True)
    assert "UMFANGREICHES Thema" in messages[0]["content"]
    assert "## " in messages[0]["content"]
    messages, _ = qa._answer_messages(
        "Kurze Frage?", [{"id": 1, "title": "T", "official_text": "B"}])
    assert "UMFANGREICHES Thema" not in messages[0]["content"]


def test_analyse_partei_nur_bei_partei_typ(monkeypatch):
    _llm_antwort(monkeypatch, json.dumps(
        {"terms": "Wohnraum", "kind": "money", "party": "SPD"}))
    # partei wird verworfen, wenn der Typ nicht "party" ist — sonst filtert
    # eine Geld-Frage plötzlich nach Fraktion.
    assert qa.analyse_query("Was kostet das?")["party"] is None


def test_analyse_faellt_bei_muell_auf_thema(monkeypatch):
    _llm_antwort(monkeypatch, "kein json {")
    a = qa.analyse_query("Was wurde zum Hafen beschlossen?")
    assert a["kind"] == "topic"
    assert a["terms"] == "Was wurde zum Hafen beschlossen?"
    _llm_antwort(monkeypatch, json.dumps({"terms": "Hafen", "kind": "quatsch"}))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Hafenfrage?")["kind"] == "topic"


def test_analyse_kondensiert_mit_verlauf(monkeypatch):
    # Ohne Zähler-Bindung, anders als oben: Der zweite `_llm_antwort`-Aufruf
    # weiter unten ersetzt den Stub, dieser Zähler wäre danach bedeutungslos.
    # Was dieser Test belegt, steht in `b` — nicht in der Zahl der Aufrufe.
    _llm_antwort(monkeypatch, json.dumps(
        {"question": "Was kostet der Neubau der Cäcilienbrücke?",
         "terms": "Kosten Neubau Cäcilienbrücke", "kind": "money", "party": None}))
    verlauf = [{"question": "Wie ist der Stand bei der Cäcilienbrücke?",
                "answer": "Der Rat forderte das WSA zur Beschleunigung auf. " * 20}]
    a = qa.analyse_query("Und was kostet das?", verlauf=verlauf)
    assert a["question"] == "Was kostet der Neubau der Cäcilienbrücke?"
    # Cache-Schlüssel enthält den Verlauf: gleiche Frage OHNE Verlauf ist ein
    # eigener Eintrag und trifft nicht denselben Cache.
    _llm_antwort(monkeypatch, json.dumps({"question": "Und was kostet das?",
                                          "terms": "Kosten", "kind": "money"}))
    b = qa.analyse_query("Und was kostet das?")
    assert b["question"] == "Und was kostet das?"


def test_verlauf_zeilen_kuerzt_und_begrenzt():
    runden = [{"question": f"Frage {i}?", "answer": "A" * 1000} for i in range(6)]
    text = qa._verlauf_zeilen(runden)
    # Nur die letzten VERLAUF_MAX_RUNDEN, Antworten gekürzt.
    assert text.count("- Frage:") == qa.VERLAUF_MAX_RUNDEN
    assert "Frage 5?" in text and "Frage 0?" not in text
    assert "A" * (qa._VERLAUF_ANTWORT_MAX + 1) not in text
    assert qa._verlauf_zeilen(None) == ""


def test_antwortprompt_traegt_gespraechskontext():
    messages, _ = qa._answer_messages(
        "Und wer ist zuständig?", [],
        verlauf=[{"question": "Stand Cäcilienbrücke?", "answer": "Resolution ans WSA."}])
    assert "Dies ist eine Anschlussfrage in einem Gespräch" in messages[0]["content"]
    assert "Resolution ans WSA." in messages[0]["content"]
    messages, _ = qa._answer_messages("Frage?", [])
    assert "Dies ist eine Anschlussfrage" not in messages[0]["content"]


def test_analyse_fehler_liefert_fallback(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Provider weg")
    monkeypatch.setattr(qa.llm, "chat_complete", boom)
    a = qa.analyse_query("Frage?")
    assert a == {"question": "Frage?", "terms": "Frage?", "kind": "topic", "party": None,
                 "variants": [], "eng": False,
                 "rechercheplan": {"intent": "overview", "channels": ["decisions"],
                                    "sort": "relevance", "needs": [], "valid": False}}


def test_rechercheplan_shadow_validiert_und_harte_kanaele_ergaenzt(monkeypatch):
    _llm_antwort(monkeypatch, json.dumps({
        "terms": "Ellberg Kreyenbrück Schule", "kind": "topic",
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
    resolved = qa.research_plan_with_mandatory(plan, typ="topic")
    assert resolved["channels"] == [
        "decisions", "budget", "debates", "documents", "press", "future_agenda",
    ]
    assert resolved["consistency_added"] == [
        "budget", "debates", "documents", "press", "future_agenda",
    ]


@pytest.mark.parametrize("question", [
    "Was hat das Rechnungsprüfungsamt beanstandet?",
    "Muss die Stadt das Theater betreiben?",
    "Warum steigen die Abfallgebühren?",
])
def test_deterministische_finanzquelle_macht_budget_zum_pflichtkanal(question):
    """Auch bei Modelltyp ``thema`` muss der Plan den realen Datenzugriff zeigen."""
    plan = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions"], "needs": [],
    }})
    resolved = qa.research_plan_with_mandatory(
        plan, typ="topic", question=question)
    assert "budget" in resolved["channels"]
    assert "budget" in resolved["mandatory_channels"]


def test_current_info_koppelt_presse_und_zukunft_nicht_mehr_pauschal():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "status", "channels": ["decisions"], "sort": "newest",
        "needs": ["current_info"],
    }})
    resolved = qa.research_plan_with_mandatory(plan, typ="history")
    assert resolved["channels"] == ["decisions"]

    presse = qa._research_plan({"rechercheplan": {
        "channels": ["decisions"], "needs": ["official_updates"],
    }})
    zukunft = qa._research_plan({"rechercheplan": {
        "channels": ["decisions"], "needs": ["future_dates"],
    }})
    assert qa.research_plan_with_mandatory(presse, typ="topic")["channels"] == [
        "decisions", "press"]
    assert qa.research_plan_with_mandatory(zukunft, typ="topic")["channels"] == [
        "decisions", "future_agenda"]


def test_reine_zukunftsfrage_entfernt_presse_ueber_bedarfe():
    nur_zukunft = qa._research_plan({"rechercheplan": {
        "intent": "session", "channels": ["decisions", "press", "future_agenda"],
        "needs": ["current_info", "future_dates"],
    }})
    resolved = qa.research_plan_with_mandatory(nur_zukunft, typ="topic")
    assert resolved["channels"] == ["decisions", "future_agenda"]
    assert resolved["suppressed_channels"] == ["press"]

    beides = qa._research_plan({"rechercheplan": {
        "intent": "status", "channels": ["decisions", "press", "future_agenda"],
        "needs": ["current_info", "official_updates", "future_dates"],
    }})
    resolved = qa.research_plan_with_mandatory(beides, typ="history")
    assert resolved["channels"] == ["decisions", "press", "future_agenda"]
    assert resolved["suppressed_channels"] == []


def test_dokumentenkanal_braucht_auch_dokumentenbedarf():
    vorsorglich = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions", "documents"],
        "needs": ["dates", "votes"],
    }})
    resolved = qa.research_plan_with_mandatory(vorsorglich, typ="topic")
    assert resolved["channels"] == ["decisions"]
    assert resolved["suppressed_channels"] == ["documents"]

    fachdetail = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions"], "needs": ["documents"],
    }})
    resolved = qa.research_plan_with_mandatory(fachdetail, typ="topic")
    assert resolved["channels"] == ["decisions", "documents"]
    assert resolved["consistency_added"] == ["documents"]


def test_metadatenfragen_entfernen_vorsorgliche_dokumente():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "overview", "channels": ["decisions", "documents"],
        "needs": ["dates", "votes", "documents"],
    }})
    cases = [
        ("thema", "Welcher Ausschuss hat über die Flötenteichschule beraten?"),
        ("thema", "Welche Beschlüsse gab es bisher zur Cäcilienbrücke?"),
        ("sitzung", "Was hat der Verkehrsausschuss am 17. Juni 2026 beschlossen?"),
    ]
    for typ, question in cases:
        resolved = qa.research_plan_with_mandatory(plan, typ=typ, question=question)
        assert resolved["channels"] == ["decisions"] or resolved["channels"] == [
            "decisions", "sessions"]
        assert "documents" in resolved["suppressed_channels"]

    # Die positive Dokumentabsicht hat Vorrang, selbst bei einer Sitzungsfrage.
    fachfrage = qa.research_plan_with_mandatory(
        plan, typ="session",
        question="Was sagt das Gutachten aus der Sitzung zum Verkehrslärm?",
    )
    assert "documents" in fachfrage["channels"]


def test_eindeutige_stadtmitteilung_aktiviert_presse_als_leitplanke():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "status", "channels": ["decisions"], "sort": "newest",
        "needs": ["current_info"],
    }})
    resolved = qa.research_plan_with_mandatory(
        plan, typ="topic",
        question="Was hat die Stadt zuletzt zum Radverkehr mitgeteilt?",
    )
    assert resolved["channels"] == ["decisions", "press"]
    assert resolved["needs"] == ["current_info", "official_updates"]
    assert resolved["inferred_needs"] == ["official_updates"]

    # Das Verb allein reicht nicht: Eine Aussage irgendeiner Person ist keine
    # offizielle Veröffentlichung der Stadtverwaltung.
    ohne_offizielle_quelle = qa.research_plan_with_mandatory(
        plan, typ="topic", question="Was hat Müller zuletzt mitgeteilt?",
    )
    assert ohne_offizielle_quelle["channels"] == ["decisions"]
    assert ohne_offizielle_quelle["inferred_needs"] == []


def test_rechercheplan_entfernt_debatten_bei_neuester_ortsentscheidung():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions", "debates", "places"],
        "sort": "newest", "needs": ["dates", "statements"],
    }})
    resolved = qa.research_plan_with_mandatory(
        plan, typ="place", place=True, latest_decision=True)
    assert resolved["channels"] == ["decisions", "places"]
    assert resolved["suppressed_channels"] == ["debates"]


@pytest.mark.parametrize("question,typ", [
    ("Warum steigen die Abfallgebühren?", "geld"),
    ("Was hat das Rechnungsprüfungsamt beanstandet?", "thema"),
    ("Was ist der Verwaltungsausschuss?", "thema"),
])
def test_strukturierte_antworten_entfernen_vorsorgliche_debatten(question, typ):
    plan = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions", "debates"],
        "needs": ["statements"],
    }})
    resolved = qa.research_plan_with_mandatory(plan, typ=typ, question=question)
    assert "debates" not in resolved["channels"]
    assert "debates" in resolved["suppressed_channels"]


def test_ausdrueckliche_haushaltsdebatte_behaelt_debattenkanal():
    plan = qa._research_plan({"rechercheplan": {
        "intent": "timeline", "channels": ["decisions", "debates"],
        "needs": ["statements"],
    }})
    resolved = qa.research_plan_with_mandatory(
        plan, typ="history", question="Wie lief die Haushaltsdebatte 2026?")
    assert "debates" in resolved["channels"]
    assert "debates" not in resolved["suppressed_channels"]


@pytest.mark.parametrize("question,typ", [
    ("Welche Änderungslisten gab es zum Haushalt 2026?", "geld"),
    ("Was wurde zum Radweg an der Donnerschweer Straße beschlossen?", "thema"),
    ("Was ist der Verwaltungsausschuss?", "thema"),
])
def test_strukturierte_antworten_entfernen_vorsorgliche_dokumente(question, typ):
    plan = qa._research_plan({"rechercheplan": {
        "intent": "fact", "channels": ["decisions", "documents"],
        "needs": ["documents"],
    }})
    resolved = qa.research_plan_with_mandatory(plan, typ=typ, question=question)
    assert "documents" not in resolved["channels"]
    assert "documents" in resolved["suppressed_channels"]


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
        qa._research_plan({}), typ="money", place=True)
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
    messages, _ = qa._answer_messages("Wie lief es?", [], typ="history")
    assert "VERLAUF" in messages[0]["content"]
    messages, _ = qa._answer_messages("Was ist?", [], typ="topic")
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
        "Was kostet die Sanierung in Kreyenbrück?", candidates, typ="money", ort=ort)
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
            "INSERT INTO council_decisions (ksinr, position, kind, title, factions, template_number) "
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
        "SELECT frage, rating, reason, user_id, length(answer_excerpt) AS al "
        "FROM council_qa_feedback ORDER BY id").fetchall()
    assert rows[0]["rating"] == "down" and rows[0]["reason"] == "zu vage"
    assert rows[0]["user_id"] == 7 and rows[0]["al"] <= 500
    assert rows[1]["rating"] == "up" and rows[1]["reason"] is None
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
        "SELECT rating, reason FROM council_qa_feedback WHERE user_id = 7").fetchall()
    assert len(rows) == 1, "Korrektur darf keine zweite Zeile anlegen"
    assert rows[0]["rating"] == "up"
    assert rows[0]["reason"] is None, "Grund des Daumen-runter ist nach der Korrektur hinfällig"
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
    ctx = qa._haushalt_block([{"year": 2026, "area": "Verkehr und Straßenbau",
                               "expenses": 46194645.0, "revenues": 17510637.0}])
    assert "STADTHAUSHALT" in ctx and "46.194.645" in ctx
    assert qa._haushalt_block([]) == ""

    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_haushalt (year, area, revenues, expenses, result, is_total, fetched_at) "
            "VALUES (2026, 'Verkehr und Straßenbau', 1, 2, -1, 0, '')")
        store._conn.execute(
            "INSERT INTO council_haushalt (year, area, revenues, expenses, result, is_total, fetched_at) "
            "VALUES (2026, 'Summe', 10, 20, -10, 1, '')")
    assert [r["area"] for r in store.haushalt_fuer_begriffe(["Verkehr", "Radweg"])] == ["Verkehr und Straßenbau"]
    # Summenzeile nur bei ausdrücklicher Haushaltsfrage.
    assert store.haushalt_fuer_begriffe(["Kita"]) == []
    assert [r["area"] for r in store.haushalt_fuer_begriffe(["Haushalt"])] == ["Summe"]
    store.close()


def test_beschluss_kontext_traegt_deutsches_datum():
    """Die Kandidatenzeile ist die Datums-Quelle der Antwort: stand dort ISO,
    schrieb das Modell „am 2026-06-01" in den Fließtext (Tims Befund 10.08.)."""
    messages, _ = qa._answer_messages(
        "Was wurde zum Stadion entschieden?",
        [{"id": 7, "title": "Stadionneubau", "official_text": "Zugestimmt.",
          "committee": "Rat", "session_date": "2026-06-01", "outcome": "angenommen"}])
    prompt = messages[0]["content"]
    assert "01.06.2026" in prompt
    assert "2026-06-01" not in prompt


# --- Geld-Kontext: Plan, Ist und Finanzausgleich getrennt (Tim, 16.08.) -------
# Der Geld-Baustein kannte bis dahin nur die Plan-Zahlen des neuesten Jahres.
# Jetzt kommen Ist-Steuereinnahmen und die NFAG-Mechanik dazu — die Trennung
# ist der springende Punkt: Plan ≠ Ist, sonst behauptet die Antwort Einnahmen,
# die noch niemand abgerechnet hat.

def test_steuern_block_trennt_ist_von_plan():
    ctx = qa._steuern_block([{"art": "Gewerbesteuer (-umlage)", "year": 2025,
                              "amount": 222117000.0, "year_before": 2015,
                              "amount_before": 120000000.0}])
    assert "IST-Zahlen" in ctx and "NICHT der Haushaltsplan" in ctx
    assert "222.117.000" in ctx and "120.000.000" in ctx
    assert "2015" in ctx  # Entwicklung wird mitgegeben
    assert qa._steuern_block([]) == ""
    # „insgesamt" bekommt einen sprechenden Namen statt des CSV-Schlüssels.
    assert "Steuereinnahmen insgesamt" in qa._steuern_block(
        [{"art": "total", "year": 2025, "amount": 387208000.0}])


def test_steuerkraft_block_nennt_die_daempfer_regel():
    ctx = qa._steuerkraft_block({"year": 2024, "tax_index": 325716249.0,
                                 "allocations": 69209992.0, "year_before": 2023,
                                 "tax_index_before": 279815776.0,
                                 "zuweisungen_davor": 99569120.0})
    assert "FINANZAUSGLEICH" in ctx
    assert "325.716.249" in ctx and "69.209.992" in ctx
    # Die Regel selbst muss drinstehen — ohne sie klingt jede Mehreinnahme
    # nach vollem Plus für die Stadt.
    assert "sinken die Schlüsselzuweisungen" in ctx
    assert qa._steuerkraft_block(None) == ""


def test_steuern_fuer_begriffe_matcht_kuratierte_synonyme(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for year, art, amount in [
            (2025, "Gewerbesteuer (-umlage)", 222117000.0),
            (2015, "Gewerbesteuer (-umlage)", 120000000.0),
            (2025, "Grundsteuer A+B", 32585000.0),
            (2025, "total", 387208000.0),
        ]:
            store._conn.execute(
                "INSERT INTO council_steuern (year, art, amount, fetched_at) VALUES (?,?,?,'')",
                (year, art, amount))

    treffer = store.steuern_fuer_begriffe(["Wie", "hoch", "ist", "die", "Gewerbesteuer"])
    assert [t["art"] for t in treffer] == ["Gewerbesteuer (-umlage)"]
    assert treffer[0]["amount"] == 222117000.0
    assert treffer[0]["year_before"] == 2015 and treffer[0]["amount_before"] == 120000000.0

    # Allgemeine Geldfrage → Gesamtsumme; unpassende Frage → nichts.
    assert [t["art"] for t in store.steuern_fuer_begriffe(["Steuereinnahmen"])] == ["total"]
    assert store.steuern_fuer_begriffe(["Radweg", "Bauantrag"]) == []
    # Satzzeichen dürfen nicht am Match hindern.
    assert store.steuern_fuer_begriffe(["Grundsteuer?"])[0]["art"] == "Grundsteuer A+B"
    store.close()


def test_steuerkraft_kontext_braucht_zwei_jahre(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_steuerkraft (year, tax_index, allocations, fetched_at) "
            "VALUES (2023, 279815776, 99569120, '')")
    assert store.steuerkraft_kontext() is None  # ein Jahr reicht nicht
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_steuerkraft (year, tax_index, allocations, fetched_at) "
            "VALUES (2024, 325716249, 69209992, '')")
    k = store.steuerkraft_kontext()
    assert k["year"] == 2024 and k["year_before"] == 2023
    assert k["allocations"] == 69209992.0 and k["zuweisungen_davor"] == 99569120.0
    store.close()


def test_haushalt_fuer_begriffe_traegt_entwicklung(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for year, aufw in [(2020, 30000000.0), (2026, 46194645.0)]:
            store._conn.execute(
                "INSERT INTO council_haushalt (year, area, revenues, expenses, result, "
                "is_total, fetched_at) VALUES (?, 'Verkehr und Straßenbau', 1, ?, -1, 0, '')",
                (year, aufw))
        # Bereich mit geändertem Zuschnitt: NUR im neuesten Jahr vorhanden.
        store._conn.execute(
            "INSERT INTO council_haushalt (year, area, revenues, expenses, result, "
            "is_total, fetched_at) VALUES (2026, 'Klima/Umwelt/Mobilität', 1, 2, -1, 0, '')")

    r = store.haushalt_fuer_begriffe(["Verkehr"])[0]
    assert r["year_before"] == 2020 and r["expenses_before"] == 30000000.0
    assert "30.000.000" in qa._haushalt_block([r])

    # Umbenannter Bereich bekommt KEINEN erfundenen Vorjahreswert.
    k = store.haushalt_fuer_begriffe(["Klima"])[0]
    assert "year_before" not in k
    store.close()
