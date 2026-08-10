"""Wortbeiträge aus Protokollen (Task 16): Extraktion, Store, Suche, QA-Block.

Offline — LLM-Aufrufe gemockt, Store in tmp_path, Embeddings über den
BM25-Fallback (fastembed wird nicht angefasst).
"""
import json
from types import SimpleNamespace

import pytest

from council import qa
from council import wortbeitraege as wb
from council.store import CouncilStore


def _llm_liefert(monkeypatch, payloads: list[str]):
    """chat_complete gibt die payloads der Reihe nach zurück (je Fenster eine)."""
    calls = {"n": 0}

    def fake(**kwargs):
        content = payloads[min(calls["n"], len(payloads) - 1)]
        calls["n"] += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                               usage=None)

    monkeypatch.setattr(wb.llm, "chat_complete", fake)
    return calls


# ------------------------------- Extraktion --------------------------------

def test_fenster_splitting():
    assert wb._fenster("kurz") == ["kurz"]
    lang = "x" * (wb.FENSTER * 2)
    teile = wb._fenster(lang)
    assert len(teile) >= 2
    # Überlapp: Ende von Fenster 1 == Anfang von Fenster 2
    assert teile[0][-wb.UEBERLAPP:] == teile[1][:wb.UEBERLAPP]


def test_extract_validierung(monkeypatch):
    rows = [
        {"art": "anfrage", "top": "Ö 5", "sprecher": "Ratsfrau Meyer", "partei": "SPD",
         "text": "Wann wird der Radweg an der Alexanderstraße saniert?",
         "antwort": "Die Verwaltung sagt eine Prüfung bis Q3 zu."},
        {"art": "quatsch", "sprecher": "Herr Schulz",
         "text": "Ein Beitrag mit unbekannter Art wird zur Rede."},
        {"art": "rede", "sprecher": "X", "text": "zu kurz"},
        "kein dict",
    ]
    _llm_liefert(monkeypatch, [json.dumps(rows)])
    out = wb.extract_wortbeitraege("Protokolltext")
    assert len(out) == 2
    assert out[0]["art"] == "anfrage" and out[0]["antwort"].startswith("Die Verwaltung")
    assert out[1]["art"] == "rede"  # Fallback bei unbekannter Art


def test_leeres_array_auf_grosses_fenster_wird_retried(monkeypatch):
    """Provider-Aussetzer: valides [] auf ein volles Fenster → ein Neuversuch
    (ksinr 4417 lieferte beim ersten Lauf 0, beim zweiten 80 Beiträge)."""
    eintrag = {"art": "rede", "sprecher": "Herr Harms",
               "text": "Die Fliegerhorststraße braucht ein Gutachten zur Nullvariante."}
    calls = _llm_liefert(monkeypatch, ["[]", json.dumps([eintrag])])
    gross = "z" * (wb.LEER_VERDAECHTIG_AB + 1)
    out = wb.extract_wortbeitraege(gross)
    assert len(out) == 1
    assert calls["n"] == 2
    # Kleines Restfenster darf ehrlich leer sein — kein zweiter Call.
    calls = _llm_liefert(monkeypatch, ["[]"])
    assert wb.extract_wortbeitraege("kurzes Protokollende") == []
    assert calls["n"] == 1


def test_abgeschnittenes_json_wird_geborgen(monkeypatch):
    """Token-Limit mitten im Array (Flash auf ksinr 4066): die vollständigen
    Objekte werden gerettet statt das ganze Fenster zu verlieren."""
    ganz = {"art": "rede", "sprecher": "Frau Conty",
            "text": "Die SPD unterstützt den Prüfauftrag zur Fliegerhorststraße."}
    kaputt = json.dumps([ganz, ganz], indent=1)[:-30]  # mitten im 2. Objekt gekappt
    calls = _llm_liefert(monkeypatch, [kaputt])
    out = wb.extract_wortbeitraege("Protokoll")
    assert len(out) == 1 and out[0]["sprecher"] == "Frau Conty"
    assert calls["n"] == 2  # erst regulärer Retry, Bergung nur am Ende
    # Völlig unbrauchbarer Inhalt → weiterhin Fehler.
    _llm_liefert(monkeypatch, ["kein json"])
    with pytest.raises(Exception):
        wb.extract_wortbeitraege("Protokoll")


def test_extract_dict_wrapper_und_dedupe(monkeypatch):
    eintrag = {"art": "rede", "sprecher": "Frau Krüger",
               "text": "Der Fliegerhorst braucht endlich eine Altlastensanierung."}
    # Modell wickelt das Array in ein Objekt; zwei Fenster liefern denselben
    # Beitrag → Dedupe über (sprecher, text-Anfang).
    _llm_liefert(monkeypatch, [json.dumps({"beitraege": [eintrag]})] * 2)
    lang = "y" * (wb.FENSTER + 100)
    out = wb.extract_wortbeitraege(lang)
    assert len(out) == 1
    assert out[0]["sprecher"] == "Frau Krüger"


# --------------------------------- Store -----------------------------------

@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    s._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (100, 'Rat der Stadt', '2026-05-01', '17:00', 'Rathaus', '2026-05-02')")
    s._conn.execute(
        "INSERT INTO council_protocols (ksinr, raw_text, extracted_at, status) "
        "VALUES (100, 'Niederschrift…', '2026-05-02', 'ok')")
    yield s
    s.close()


BEITRAG = {"art": "einwohnerfrage", "top": "Ö 2", "sprecher": "Peter Petersen",
           "partei": None, "text": "Warum dauert die Sanierung des Fliegerhorst-Geländes so lange?",
           "antwort": "Die Altlastenprüfung läuft noch."}


def test_save_fts_und_by_ids(store):
    assert store.save_wortbeitraege(100, [BEITRAG]) == 1
    hits = store.search_wortbeitraege_fts("Fliegerhorst Sanierung")
    assert len(hits) == 1
    wb_id = hits[0][0]
    rows = store.wortbeitraege_by_ids([wb_id])
    assert rows[0]["committee"] == "Rat der Stadt"
    assert rows[0]["session_date"] == "2026-05-01"
    assert rows[0]["art"] == "einwohnerfrage"
    # Auch der Antwort-Text ist durchsuchbar.
    assert store.search_wortbeitraege_fts("Altlastenprüfung")


def test_save_ersetzt_je_protokoll(store):
    store.save_wortbeitraege(100, [BEITRAG])
    alte_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    store.replace_wortbeitrag_embedding(alte_id, "hash", b"\x00" * 4)
    store.save_wortbeitraege(100, [dict(BEITRAG, text="Neuer Text zur Bahnübergangs-Schließung in Krusenbusch.")])
    assert store.search_wortbeitraege_fts("Fliegerhorst") == []
    assert store.search_wortbeitraege_fts("Krusenbusch")
    # Embeddings der alten Beiträge sind mit aufgeräumt.
    assert store.wortbeitraege_embedding_rows() == []


def test_ksinr_ohne_wortbeitraege(store):
    assert store.ksinr_ohne_wortbeitraege() == [100]
    store.save_wortbeitraege(100, [BEITRAG])
    assert store.ksinr_ohne_wortbeitraege() == []


def test_leeres_ergebnis_markiert_erledigt(store):
    """Formalien-Protokoll ohne einen einzigen Beitrag: der Save markiert es
    trotzdem als erledigt — sonst kostete es jede Nacht erneut einen LLM-Call
    (Review-Befund zu #387)."""
    assert store.save_wortbeitraege(100, []) == 0
    assert store.ksinr_ohne_wortbeitraege() == []


def test_paralleler_save_hinterlaesst_keine_fts_waisen(store):
    """Die DELETEs laufen per Subquery über ksinr, nicht über eine vorab
    gelesene ID-Liste — auch Zeilen, die ein nebenläufiger Save dazwischen
    geschrieben hätte, werden mit abgeräumt (Review-Befund zu #387)."""
    store.save_wortbeitraege(100, [BEITRAG])
    # Fremde Zeile im selben ksinr simuliert den nebenläufigen Save.
    cur = store._conn.execute(
        "INSERT INTO council_wortbeitraege (ksinr, position, art, text, extracted_at) "
        "VALUES (100, 99, 'rede', 'Nebenläufig eingefügter Beitrag über Wechloy.', 'x')")
    store._conn.execute(
        "INSERT INTO council_wortbeitraege_fts(rowid, content) VALUES (?, ?)",
        (cur.lastrowid, "Nebenläufig eingefügter Beitrag über Wechloy."))
    store.replace_wortbeitrag_embedding(cur.lastrowid, "h", b"\x00" * 4)
    store.save_wortbeitraege(100, [dict(BEITRAG, text="Ganz neuer Stand nach dem zweiten Lauf.")])
    assert store.search_wortbeitraege_fts("Wechloy") == []
    assert store.wortbeitraege_embedding_rows() == []


def test_by_ids_ohne_session(store):
    """Fehlt die Sessions-Zeile, darf der Treffer nicht verschwinden (LEFT JOIN)."""
    store._conn.execute(
        "INSERT INTO council_protocols (ksinr, raw_text, extracted_at, status) "
        "VALUES (200, 'Text', '2026-05-02', 'ok')")
    store.save_wortbeitraege(200, [BEITRAG])
    wb_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    rows = store.wortbeitraege_by_ids([wb_id])
    assert len(rows) == 1 and rows[0]["committee"] is None


def test_embeddings_version_wechselt(store):
    v0 = store.wortbeitraege_embeddings_version()
    store.save_wortbeitraege(100, [BEITRAG])
    wb_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    store.replace_wortbeitrag_embedding(wb_id, "h", b"\x00" * 4)
    assert store.wortbeitraege_embeddings_version() != v0


# ------------------------------ Suche (Hybrid) ------------------------------

def test_search_wortbeitraege_bm25_fallback(store, monkeypatch):
    """Ohne Vektor-Index trägt der BM25-Sockel — wie bei search_presse."""
    from council import embeddings as emb
    store.save_wortbeitraege(100, [BEITRAG])
    monkeypatch.setattr(emb, "_wb_matrix", lambda s: ([], None))
    hits = emb.search_wortbeitraege(store, "Fliegerhorst", "Fliegerhorst Altlasten")
    assert hits and 0 < hits[0][1] < 0.2  # Sockel-Score, kein Cosine


def test_kein_bm25_rauschen_bei_vorhandenem_index(store, monkeypatch):
    """Existiert der Vektor-Index, füllt BM25 NICHT mehr auf: Ein bloßer
    Wort-Match („Straße") hob sonst thematisch fremde Treffer in die UI
    (Tims Ampel-Wartungs-Befund 10.08. bei den Pressemitteilungen)."""
    np = pytest.importorskip("numpy")
    from council import embeddings as emb
    store.save_wortbeitraege(100, [BEITRAG])  # FTS allein WÜRDE „Fliegerhorst" matchen
    monkeypatch.setattr(emb, "_wb_matrix",
                        lambda s: ([1], np.array([[0.0, 1.0]], dtype="float32")))
    monkeypatch.setattr(emb, "embed",
                        lambda texts: np.array([[1.0, 0.0]], dtype="float32"))
    assert emb.search_wortbeitraege(store, "Fliegerhorst", "Fliegerhorst Altlasten") == []


def test_cross_encoder_ist_torwaechter(store, monkeypatch):
    """Cosine-Kandidaten überleben nur, wenn der Cross-Encoder sie bestätigt —
    Bi-Encoder-Scores trennen amtliche Kurztexte nicht (Stadion-PM 0.466 <
    Ampelwartung 0.471, Messung 10.08.)."""
    np = pytest.importorskip("numpy")
    from council import embeddings as emb
    store.save_wortbeitraege(100, [BEITRAG])
    wb_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    monkeypatch.setattr(emb, "_wb_matrix",
                        lambda s: ([wb_id], np.array([[1.0, 0.0]], dtype="float32")))
    monkeypatch.setattr(emb, "embed",
                        lambda texts: np.array([[1.0, 0.0]], dtype="float32"))
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, -0.2) for i, _ in docs])
    assert emb.search_wortbeitraege(store, "Frage", "Frage")[0][0] == wb_id
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, -2.9) for i, _ in docs])
    assert emb.search_wortbeitraege(store, "Frage", "Frage") == []
    # Reranker nicht verfügbar → lieber leer als Rauschen (Zusatzkanal).
    def kaputt(q, docs):
        raise ImportError("kein fastembed")
    monkeypatch.setattr(emb, "rerank", kaputt)
    assert emb.search_wortbeitraege(store, "Frage", "Frage") == []


# ------------------------------ QA-Kontextblock -----------------------------

def test_debatten_block_format():
    block = qa._debatten_block([
        {"art": "anfrage", "sprecher": "Ratsfrau Meyer", "partei": "SPD",
         "top": "Radweg", "text": "Wann wird saniert?", "antwort": "Prüfung bis Q3.",
         "committee": "Verkehrsausschuss", "session_date": "2026-04-12"},
        {"art": "rede", "sprecher": None, "partei": None, "top": None,
         "text": "Beitrag ohne Metadaten.", "antwort": None,
         "committee": None, "session_date": None},
    ])
    assert "AUS DEN RATSDEBATTEN" in block
    assert "Anfrage von Ratsfrau Meyer (SPD)" in block
    assert "Antwort der Verwaltung: Prüfung bis Q3." in block
    assert "Verkehrsausschuss" in block
    assert qa._debatten_block([]) == ""
    assert qa._debatten_block(None) == ""


def test_debatten_block_im_antwortprompt(monkeypatch):
    messages, _ = qa._answer_messages(
        "Was ist mit dem Radweg?", [{"id": 1, "title": "T", "beschluss": "B"}],
        debatten=[{"art": "zusage", "sprecher": "Stadtbaurat", "partei": None,
                   "top": None, "text": "Die Verwaltung sagt die Prüfung zu.",
                   "antwort": None, "committee": None, "session_date": None}])
    assert "Zusage der Verwaltung von Stadtbaurat" in messages[0]["content"]
