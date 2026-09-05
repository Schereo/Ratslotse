"""Wortbeiträge aus Protokollen (Task 16): Extraktion, Store, Suche, QA-Block.

Offline — LLM-Aufrufe gemockt, Store in tmp_path, Embeddings über den
BM25-Fallback (fastembed wird nicht angefasst).
"""
import json
from types import SimpleNamespace

import pytest

from council import embeddings as emb
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
        {"kind": "inquiry", "top": "Ö 5", "speaker": "Ratsfrau Meyer", "party": "SPD",
         "text": "Wann wird der Radweg an der Alexanderstraße saniert?",
         "answer": "Die Verwaltung sagt eine Prüfung bis Q3 zu."},
        {"kind": "quatsch", "speaker": "Herr Schulz",
         "text": "Ein Beitrag mit unbekannter Art wird zur Rede."},
        {"kind": "speech", "speaker": "X", "text": "zu kurz"},
        "kein dict",
    ]
    _llm_liefert(monkeypatch, [json.dumps(rows)])
    out = wb.extract_wortbeitraege("Protokolltext")
    assert len(out) == 2
    assert out[0]["kind"] == "inquiry" and out[0]["answer"].startswith("Die Verwaltung")
    assert out[1]["kind"] == "speech"  # Fallback bei unbekannter Art


def test_choices_null_wird_retried(monkeypatch):
    """Provider liefert choices=null (Content-Filter/Fehler): das darf nicht
    aus der Retry-Schleife ausbrechen (Massenlauf-Befund ksinr 4299/4301)."""
    eintrag = {"kind": "speech", "speaker": "Herr Baak",
               "text": "Die Investitionen zum Stadion stießen auf geteilte Meinungen."}
    antworten = [SimpleNamespace(choices=None, usage=None),
                 SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                     content=json.dumps([eintrag])))], usage=None)]
    calls = {"n": 0}

    def fake(**kwargs):
        assert kwargs["_allow_empty_response"] is True
        resp = antworten[min(calls["n"], 1)]
        calls["n"] += 1
        return resp

    monkeypatch.setattr(wb.llm, "chat_complete", fake)
    out = wb.extract_wortbeitraege("Protokoll")
    assert len(out) == 1 and calls["n"] == 2


def test_leeres_array_auf_grosses_fenster_wird_retried(monkeypatch):
    """Provider-Aussetzer: valides [] auf ein volles Fenster → ein Neuversuch
    (ksinr 4417 lieferte beim ersten Lauf 0, beim zweiten 80 Beiträge)."""
    eintrag = {"kind": "speech", "speaker": "Herr Harms",
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
    ganz = {"kind": "speech", "speaker": "Frau Conty",
            "text": "Die SPD unterstützt den Prüfauftrag zur Fliegerhorststraße."}
    kaputt = json.dumps([ganz, ganz], indent=1)[:-30]  # mitten im 2. Objekt gekappt
    calls = _llm_liefert(monkeypatch, [kaputt])
    out = wb.extract_wortbeitraege("Protokoll")
    assert len(out) == 1 and out[0]["speaker"] == "Frau Conty"
    assert calls["n"] == 2  # erst regulärer Retry, Bergung nur am Ende
    # Völlig unbrauchbarer Inhalt → weiterhin Fehler.
    _llm_liefert(monkeypatch, ["kein json"])
    with pytest.raises(ValueError):
        wb.extract_wortbeitraege("Protokoll")


def test_extract_dict_wrapper_und_dedupe(monkeypatch):
    eintrag = {"kind": "speech", "speaker": "Frau Krüger",
               "text": "Der Fliegerhorst braucht endlich eine Altlastensanierung."}
    # Modell wickelt das Array in ein Objekt; zwei Fenster liefern denselben
    # Beitrag → Dedupe über (sprecher, text-Anfang).
    _llm_liefert(monkeypatch, [json.dumps({"contributions": [eintrag]})] * 2)
    lang = "y" * (wb.FENSTER + 100)
    out = wb.extract_wortbeitraege(lang)
    assert len(out) == 1
    assert out[0]["speaker"] == "Frau Krüger"


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


BEITRAG = {"kind": "citizen_question", "top": "Ö 2", "speaker": "Peter Petersen",
           "party": None, "text": "Warum dauert die Sanierung des Fliegerhorst-Geländes so lange?",
           "answer": "Die Altlastenprüfung läuft noch."}


def test_save_fts_und_by_ids(store):
    assert store.save_wortbeitraege(100, [BEITRAG]) == 1
    hits = store.search_wortbeitraege_fts("Fliegerhorst Sanierung")
    assert len(hits) == 1
    contribution_id = hits[0][0]
    rows = store.wortbeitraege_by_ids([contribution_id])
    assert rows[0]["committee"] == "Rat der Stadt"
    assert rows[0]["session_date"] == "2026-05-01"
    assert rows[0]["kind"] == "citizen_question"
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
        "INSERT INTO council_speeches (ksinr, position, kind, text, extracted_at) "
        "VALUES (100, 99, 'rede', 'Nebenläufig eingefügter Beitrag über Wechloy.', 'x')")
    store._conn.execute(
        "INSERT INTO council_speeches_fts(rowid, content) VALUES (?, ?)",
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
    contribution_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    rows = store.wortbeitraege_by_ids([contribution_id])
    assert len(rows) == 1 and rows[0]["committee"] is None


def test_protokolle_verlinken_haengt_pdf_url_an(store):
    """Nachlesbare Belege: qa.protokolle_verlinken reichert Wortbeitrags-
    Zeilen um die getfile-URL ihres Protokolls an — auch auf dem Personen-
    Pfad (wortbeitraege_von_sprecher), der ksinr dafür mitliefern muss."""
    store._conn.execute(
        "UPDATE council_protocols SET document_url = "
        "'https://buergerinfo.oldenburg.de/getfile.php?id=4711&type=do' WHERE ksinr = 100")
    store.save_wortbeitraege(100, [BEITRAG])
    contribution_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    rows = store.wortbeitraege_by_ids([contribution_id])
    qa.protokolle_verlinken(store, rows)
    assert rows[0]["minutes_url"].endswith("getfile.php?id=4711&type=do")
    rows_p = store.wortbeitraege_von_sprecher("Petersen")
    qa.protokolle_verlinken(store, rows_p)
    assert rows_p and rows_p[0]["minutes_url"] is not None


def test_protokoll_urls_fuer_ohne_url_bleibt_leer(store):
    """Alt-Bestand ohne document_url (oder unbekannte ksinr): kein Eintrag in
    der Map, die Anreicherung setzt dann ausdrücklich None — das Frontend
    lässt das Icon einfach weg."""
    assert store.protokoll_urls_fuer([100, 999, None]) == {}
    store.save_wortbeitraege(100, [BEITRAG])
    rows = store.wortbeitraege_by_ids([store.search_wortbeitraege_fts("Fliegerhorst")[0][0]])
    qa.protokolle_verlinken(store, rows)
    assert rows[0]["minutes_url"] is None


def test_page_offsets_rechnen_mit_dem_join():
    """Die Offsets müssen exakt zum \\n-verklebten Text passen — jede Seite
    beginnt bei sum(len(vorher)+1)."""
    from council.protocols import page_offsets
    seiten = ["abc", "", "defg"]
    offs = page_offsets(seiten)
    text = "\n".join(seiten)
    assert offs == [0, 4, 5]
    assert text[offs[2]:] == "defg"


def _protokoll_mit_seiten(store, ksinr: int, seiten: list[str]) -> None:
    from council.protocols import page_offsets
    import json as _json
    store._conn.execute(
        "UPDATE council_protocols SET raw_text = ?, n_pages = ?, page_offsets = ? "
        "WHERE ksinr = ?",
        ("\n".join(seiten), len(seiten), _json.dumps(page_offsets(seiten)), ksinr))


def test_seiten_aufloesen_ankert_am_sprecher(store):
    """Seitengenaue Fundstelle (Tims Wunsch 18.08.): Der Name ist der Anker,
    markante Wörter schlagen die Anwesenheitsliste — und die Faltung macht
    das Matching immun gegen PDF-Trennungs-Artefakte („Ratjen -Damerau")."""
    seiten = [
        "Teilnahme: Ratsfrau Dr. Ratjen -Damerau FDP, Herr Petersen SPD",
        "TOP 5: Ratsfrau Dr. Ratjen -Damerau begrüßt die Neua u s-richtung "
        "des Stadtmuseums; der Architektenwettbewerb solle mutige Entwürfe liefern.",
        "TOP 6: Anderes Thema ohne die Sprecherin.",
    ]
    _protokoll_mit_seiten(store, 100, seiten)
    store.save_wortbeitraege(100, [
        {"kind": "speech", "top": "5", "speaker": "Dr. Ratjen-Damerau", "party": "FDP",
         "text": "Die FDP begrüßt die Neuausrichtung des Stadtmuseums und den "
                 "Architektenwettbewerb.", "answer": None}])
    from council.wortbeitraege import seiten_aufloesen
    assert seiten_aufloesen(store, 100) == 1
    contribution_id = store.search_wortbeitraege_fts("Stadtmuseums")[0][0]
    assert store.wortbeitraege_by_ids([contribution_id])[0]["page"] == 2
    # Idempotent: Beiträge mit Seite werden nicht erneut angefasst.
    assert seiten_aufloesen(store, 100) == 0


def test_seiten_aufloesen_bleibt_bei_zweifel_leer(store):
    """Ohne Anker, ohne Offsets oder bei Gleichstand gibt es KEINE Seite —
    ein falscher Sprung wäre schlimmer als keiner."""
    from council.wortbeitraege import seiten_aufloesen
    # Ohne Offsets (Altbestand): nichts passiert.
    store.save_wortbeitraege(100, [BEITRAG])
    assert seiten_aufloesen(store, 100) == 0
    # Mit Offsets, aber der Sprecher steht wortgleich auf zwei Seiten und
    # die Paraphrase entscheidet nicht → None.
    seiten = ["Herr Petersen spricht über Radwege und Ampeln.",
              "Herr Petersen spricht über Radwege und Ampeln."]
    _protokoll_mit_seiten(store, 100, seiten)
    assert seiten_aufloesen(store, 100) == 0
    contribution_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    assert store.wortbeitraege_by_ids([contribution_id])[0]["page"] is None


def test_embeddings_version_wechselt(store):
    v0 = store.wortbeitraege_embeddings_version()
    store.save_wortbeitraege(100, [BEITRAG])
    contribution_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    store.replace_wortbeitrag_embedding(contribution_id, "h", b"\x00" * 4)
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
    contribution_id = store.search_wortbeitraege_fts("Fliegerhorst")[0][0]
    monkeypatch.setattr(emb, "_wb_matrix",
                        lambda s: ([contribution_id], np.array([[1.0, 0.0]], dtype="float32")))
    monkeypatch.setattr(emb, "embed",
                        lambda texts: np.array([[1.0, 0.0]], dtype="float32"))
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, -0.2) for i, _ in docs])
    assert emb.search_wortbeitraege(store, "Frage", "Frage")[0][0] == contribution_id
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, -2.9) for i, _ in docs])
    assert emb.search_wortbeitraege(store, "Frage", "Frage") == []
    # Reranker nicht verfügbar → lieber leer als Rauschen (Zusatzkanal).
    def kaputt(q, docs):
        raise ImportError("kein fastembed")
    monkeypatch.setattr(emb, "rerank", kaputt)
    assert emb.search_wortbeitraege(store, "Frage", "Frage") == []


# ------------------------------ QA-Kontextblock -----------------------------

def test_fraktions_label_normalisierung():
    """Slash-Whitespace vereinheitlicht — „Bündnis 90/ Die Grünen" und
    „Bündnis 90/Die Grünen" wurden sonst als ZWEI Fraktionen gruppiert
    (Prod-Befund 10.08.)."""
    assert qa._fraktions_label("Bündnis 90/ Die Grünen") == "Bündnis 90/Die Grünen"
    assert qa._fraktions_label("Bündnis 90/Die Grünen") == "Bündnis 90/Die Grünen"
    assert qa._fraktions_label("Fraktion DIE LINKE.") == "DIE LINKE"
    assert qa._fraktions_label("FDP / Volt") == "FDP/Volt"
    assert qa._fraktions_label(None) is None


def test_search_je_fraktion_filtert_und_deckelt(store, monkeypatch):
    """Fraktions-bewusstes Sammeln: Beiträge ohne Fraktion (Verwaltung)
    verstopfen keine Slots, je Fraktion greift der Deckel."""
    np = pytest.importorskip("numpy")
    from council import embeddings as emb
    rows = ([dict(BEITRAG, party=None, text=f"Verwaltungsantwort Nummer {i} zur Sache.")
             for i in range(6)]
            + [dict(BEITRAG, party="SPD", speaker=f"S{i}", text=f"SPD-Beitrag {i} zur Sache im Rat.")
               for i in range(7)]
            + [dict(BEITRAG, party="CDU", speaker="C1", text="CDU-Beitrag zur Sache im Rat.")])
    store.save_wortbeitraege(100, rows)
    alle = [r[0] for r in store._conn.execute("SELECT id FROM council_speeches ORDER BY id")]
    mat = np.ones((len(alle), 2), dtype="float32") / np.sqrt(2)  # alle gleich relevant
    monkeypatch.setattr(emb, "_wb_matrix", lambda s: (alle, mat))
    monkeypatch.setattr(emb, "embed", lambda texts: np.array([[1.0, 1.0]], dtype="float32") / np.sqrt(2))
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, 0.0) for i, _ in docs])
    hits = emb.search_wortbeitraege_je_fraktion(store, "Frage", "Frage", je_partei=5)
    gewaehlt = store.wortbeitraege_by_ids([w for w, _ in hits])
    parteien = [r.get("party") for r in gewaehlt]
    assert None not in parteien
    assert parteien.count("SPD") == 5  # Deckel greift (7 vorhanden)
    assert parteien.count("CDU") == 1


def test_search_je_fraktion_sammelt_aus_ganzem_feld(store, monkeypatch):
    """Regression (Tims Befund 21.08.2026): Die Auswahl je Fraktion darf NICHT
    hinter einem globalen Top-N stehen. Vorher schnitt der Code das Feld auf
    120 Kandidaten zusammen — auf „Was ist die Baumschutzsatzung …?" lagen dort
    ausschließlich Beiträge zu anderen Tagesordnungspunkten, und die Reden aus
    der Satzungs-Debatte (CDU, SPD, BSW) fielen heraus."""
    np = pytest.importorskip("numpy")
    from council import embeddings as emb
    # 130 Verwaltungs-Beiträge mit HÖHEREM Score als die beiden Fraktions-
    # Beiträge — genau die Konstellation, die den alten Schnitt auslöste.
    rows = ([dict(BEITRAG, party=None, text=f"Verwaltungsantwort Nummer {i} zur Sache.")
             for i in range(130)]
            + [dict(BEITRAG, party="SPD", speaker="S1", text="SPD-Rede zur Satzung."),
               dict(BEITRAG, party="CDU", speaker="C1", text="CDU-Rede zur Satzung.")])
    store.save_wortbeitraege(100, rows)
    alle = [r[0] for r in store._conn.execute("SELECT id FROM council_speeches ORDER BY id")]
    # Score = erste Komponente: absteigend, die Fraktions-Beiträge am Ende.
    cos = np.array([0.9 - 0.002 * i for i in range(len(alle))], dtype="float32")
    mat = np.stack([cos, np.sqrt(1 - cos ** 2)], axis=1)
    monkeypatch.setattr(emb, "_wb_matrix", lambda s: (alle, mat))
    monkeypatch.setattr(emb, "embed", lambda texts: np.array([[1.0, 0.0]], dtype="float32"))
    monkeypatch.setattr(emb, "rerank", lambda q, docs: [(i, 0.0) for i, _ in docs])
    hits = emb.search_wortbeitraege_je_fraktion(store, "Frage", "Frage")
    parteien = [r.get("party") for r in store.wortbeitraege_by_ids([w for w, _ in hits])]
    assert sorted(parteien) == ["CDU", "SPD"]


def test_partei_meinungen_deckel_und_einzelstimmen(monkeypatch):
    """Je Fraktion gehen bis zu MAX_BEITRAEGE_JE_PARTEI Beiträge in die
    Verdichtung — die JÜNGSTEN, chronologisch. Und: ein einzelner Beitrag
    macht aus einem Verband keine Position, aus einer Ratsfraktion schon."""
    gesehen = {}

    def fake(**kwargs):
        gesehen["prompt"] = kwargs["messages"][0]["content"]
        answer = json.dumps([{"party": "SPD", "stance": "dafür", "position": "Dafür.",
                               "unanimous": True},
                              {"party": "AfD", "stance": "dagegen", "position": "Dagegen.",
                               "unanimous": True},
                              {"party": "Jägerschaft", "stance": "offen", "position": "Egal.",
                               "unanimous": True}])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))],
                               usage=None)

    monkeypatch.setattr(qa.llm, "chat_complete", fake)
    rows = [{"party": "SPD", "speaker": f"Redner {i}", "text": f"SPD-Beitrag {i} zur Sache.",
             "session_date": f"2026-01-{i + 1:02d}"} for i in range(15)]
    rows.append({"party": "AfD", "speaker": "Einzeln", "text": "Einzige AfD-Rede zur Sache.",
                 "session_date": "2026-02-01"})
    rows.append({"party": "Jägerschaft", "speaker": "Gast", "text": "Einzige Wortmeldung.",
                 "session_date": "2026-02-02"})
    out = qa.partei_meinungen("Frage?", rows)
    assert [e["party"] for e in out] == ["SPD", "AfD"]  # Jägerschaft: nur eine Stimme
    assert out[0]["contributions"] == qa.MAX_BEITRAEGE_JE_PARTEI == 12
    assert len(out[0]["beitraege_liste"]) == 12
    # Gekappt wird vorne: der älteste fällt raus, der jüngste bleibt.
    assert "SPD-Beitrag 0 " not in gesehen["prompt"]
    assert "SPD-Beitrag 14 " in gesehen["prompt"]
    assert "Einzige Wortmeldung" not in gesehen["prompt"]


def test_partei_meinungen_fasst_schreibvarianten_zusammen(monkeypatch):
    """„SPD" und „SPD-Fraktion" sind EINE Fraktion — sonst steht die Partei
    zweimal im Baustein und teilt sich ihre Beiträge (Stadion-Frage, 21.08.)."""
    gesehen = {}

    def fake(**kwargs):
        gesehen["prompt"] = kwargs["messages"][0]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps([{"party": "SPD", "stance": "dafür", "position": "Dafür.",
                                 "unanimous": True},
                                {"party": "Bündnis 90/Die Grünen", "stance": "dafür",
                                 "position": "Auch dafür.", "unanimous": True}])))], usage=None)

    monkeypatch.setattr(qa.llm, "chat_complete", fake)
    rows = [{"party": p, "speaker": "R", "text": f"Beitrag der {p} zur Sache.",
             "session_date": "2026-01-01"}
            for p in ("SPD", "SPD-Fraktion", "Die Grünen", "Bündnis 90/ Die Grünen")]
    out = qa.partei_meinungen("Frage?", rows)
    assert [e["party"] for e in out] == ["SPD", "Bündnis 90/Die Grünen"]
    assert [e["contributions"] for e in out] == [2, 2]
    assert "SPD-Fraktion (" not in gesehen["prompt"]


def test_partei_meinungen_leere_providerantwort_bleibt_ohne_baustein(monkeypatch):
    """Die optionale Verdichtung behält ihren direkten None-Fallback."""
    def empty_response(**kwargs):
        assert kwargs["_allow_empty_response"] is True
        return SimpleNamespace(choices=None, usage=None)

    monkeypatch.setattr(qa.llm, "chat_complete", empty_response)
    rows = ([{"party": "SPD", "speaker": "A", "text": "Beitrag zur Sache " * 3,
              "session_date": "2026-01-01"}] * 2
            + [{"party": "CDU", "speaker": "B", "text": "Weitere Position " * 3,
                "session_date": "2026-01-02"}] * 2)
    assert qa.partei_meinungen("Frage?", rows) is None


def test_partei_meinungen_rettet_abgeschnittene_antwort(monkeypatch):
    """Läuft die Verdichtung ins Token-Limit, ist ein halber Baustein besser
    als gar keiner — der Rest des Arrays wird geborgen (Befund 21.08.)."""
    torso = ('[{"party": "SPD", "stance": "dafür", "position": "Dafür.", "unanimous": true},'
             ' {"party": "CDU", "stance": "dagegen", "position": "Dage')
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **k: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=torso))], usage=None))
    rows = [{"party": p, "speaker": "R", "text": f"Beitrag der {p} zur Sache.",
             "session_date": "2026-01-01"} for p in ("SPD", "SPD", "CDU", "CDU")]
    out = qa.partei_meinungen("Frage?", rows)
    assert [e["party"] for e in out] == ["SPD"]
    assert qa._json_array_notfalls_gerettet("kein json") is None


def test_partei_meinungen_schwellen(monkeypatch):
    """Unter 2 Fraktionen oder 4 Beiträgen: kein Baustein, KEIN LLM-Call."""
    def nie(**kwargs):
        raise AssertionError("LLM darf hier nicht gerufen werden")
    monkeypatch.setattr(qa.llm, "chat_complete", nie)
    r = {"party": "SPD", "speaker": "A", "text": "x" * 30, "session_date": "2026-06-01"}
    assert qa.partei_meinungen("Frage?", [r] * 5) is None          # nur 1 Fraktion
    assert qa.partei_meinungen("Frage?", [r, dict(r, party="CDU"), r]) is None  # nur 3 Beiträge
    # Beiträge ohne Fraktion (Verwaltung/Einwohner) zählen nicht mit.
    assert qa.partei_meinungen("Frage?", [r, dict(r, party=None), dict(r, party=None),
                                          dict(r, party="CDU")]) is None


def test_partei_meinungen_aggregation(monkeypatch):
    """Label-Bereinigung, Halluzinations-Guard, uneinig-Flag, Zähler."""
    answer = json.dumps([
        {"party": "DIE LINKE", "stance": "dagegen", "position": "Lehnt die Trasse ab.",
         "unanimous": True,
         "kernaussage": {"text": "Kein Bedarf für die Straße.", "speaker": "Höpken",
                         "date": "01.06.2026"}},
        {"party": "AfD", "stance": "quatsch",
         "position": "Uneinheitlich zwischen Investition und Haushalt.",
         "unanimous": False, "note": "Paul dafür, Beitrag vom Februar dagegen"},
        {"party": "Die Grauen", "position": "erfunden", "unanimous": True},
    ])
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **k: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer))], usage=None))
    rows = ([{"party": "Fraktion DIE LINKE.", "speaker": "Höpken",
              "text": "Ablehnung " * 5, "session_date": "2026-06-01"}] * 3
            + [{"party": "AfD", "speaker": "Paul", "text": "Zustimmung " * 5,
                "session_date": "2026-06-01"}] * 2)
    out = qa.partei_meinungen("Was ist mit der Trasse?", rows)
    assert [e["party"] for e in out] == ["DIE LINKE", "AfD"]  # „Die Grauen" gefiltert
    assert out[0]["kernaussage"]["speaker"] == "Höpken"
    assert out[0]["contributions"] == 3
    assert out[0]["stance"] == "dagegen"
    assert out[1]["stance"] == "offen"  # unbekannter Wert → offen
    assert out[1]["unanimous"] is False and "Paul" in out[1]["note"]


def test_partei_meinungen_cache(store):
    """Server-Cache über den ID-Hash: Treffer innerhalb der TTL, Fremd-
    Schlüssel leer, kaputtes JSON leer statt Crash."""
    daten = [{"party": "SPD", "stance": "dafür", "position": "Dafür.", "unanimous": True,
              "note": None, "kernaussage": None, "contributions": 4}]
    store.partei_meinungen_cache_set("abc123", "Stadionfrage?", daten)
    assert store.partei_meinungen_cache_get("abc123") == daten
    assert store.partei_meinungen_cache_get("anderer") is None
    store._conn.execute(
        "UPDATE council_partei_meinungen_cache SET result = 'kaputt' WHERE key = 'abc123'")
    assert store.partei_meinungen_cache_get("abc123") is None


def test_debatten_block_format():
    block = qa._debatten_block([
        {"kind": "inquiry", "speaker": "Ratsfrau Meyer", "party": "SPD",
         "top": "Radweg", "text": "Wann wird saniert?", "answer": "Prüfung bis Q3.",
         "committee": "Verkehrsausschuss", "session_date": "2026-04-12"},
        {"kind": "speech", "speaker": None, "party": None, "top": None,
         "text": "Beitrag ohne Metadaten.", "answer": None,
         "committee": None, "session_date": None},
    ])
    assert "AUS DEN RATSDEBATTEN" in block
    assert "Anfrage von Ratsfrau Meyer (SPD)" in block
    assert "Antwort der Verwaltung: Prüfung bis Q3." in block
    assert "Verkehrsausschuss" in block
    # Datum deutsch: das Modell übernimmt das Format aus dem Kontext wörtlich,
    # ISO landete sonst als „am 2026-04-12" in der Antwort (Tims Befund 10.08.).
    assert "am 12.04.2026" in block
    assert "2026-04-12" not in block
    assert qa._debatten_block([]) == ""
    assert qa._debatten_block(None) == ""


def test_debatten_block_im_antwortprompt(monkeypatch):
    messages, _ = qa._answer_messages(
        "Was ist mit dem Radweg?", [{"id": 1, "title": "T", "official_text": "B"}],
        debatten=[{"kind": "pledge", "speaker": "Stadtbaurat", "party": None,
                   "top": None, "text": "Die Verwaltung sagt die Prüfung zu.",
                   "answer": None, "committee": None, "session_date": None}])
    assert "Zusage der Verwaltung von Stadtbaurat" in messages[0]["content"]


# ---- Stations-Kopplung: die Aussprache ZUM Beschluss (Befund 10.08.2026) ----

def test_top_schluessel_ebnet_nummer_und_zusatz_ein():
    from council.store import CouncilStore as CS
    # „Ö 6.1"-Präfix, Nummer im Titel, „- Bericht"-Zusatz: alles dieselbe Station.
    assert CS._top_schluessel("10 Fliegerhorst - 2. Grundwassermonitoring - Bericht") == \
           ("10", "fliegerhorst 2 grundwassermonitoring")
    assert CS._top_schluessel("Ö 6.1 Radweg Haarenufer")[0] == "6.1"
    a = CS._top_schluessel("Sachstand ehemalige Schießanlage - Bericht")[1]
    b = CS._top_schluessel("Sachstand ehemalige Schießanlage")[1]
    assert a == b == "sachstand ehemalige schiessanlage"


def test_wortbeitraege_zu_beschluessen_koppelt_ueber_die_station(store):
    """Der Fliegerhorst-Fall in klein: Ein Beitrag, der kein Wort der Frage
    trägt, gehört trotzdem zur Aussprache über den zitierten Bericht."""
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (4663, 'Ausschuss für Stadtgrün', '2026-02-12', '17:00', 'Rathaus', '2026-02-13')")
    store.save_wortbeitraege(4663, [
        {"kind": "speech", "top": "Fliegerhorst Oldenburg - 2. Grundwassermonitoring ehemalige Schießanlage",
         "speaker": "Jaekel", "party": None,
         "text": "Vinylchlorid stammt wahrscheinlich aus der militärischen Nutzung.", "answer": None},
        # Sammel-TOP derselben Sitzung: darf NIE mitkommen.
        {"kind": "inquiry", "top": "16 Anfragen und Anregungen", "speaker": "Oltmanns",
         "party": None, "text": "Frage zu Baumfällungen.", "answer": None},
    ])
    official_text = {"id": 20852, "ksinr": 4663, "item_number": "10",
                 "title": "Fliegerhorst Oldenburg - 2. Grundwassermonitoring ehemalige Schießanlage - Bericht"}
    got = store.wortbeitraege_zu_beschluessen([official_text])
    assert [g["speaker"] for g in got] == ["Jaekel"]
    assert got[0]["zu_beschluss"] == 20852          # Bezug fürs Prompt
    # Sammel-TOP als Beschluss koppelt gar nichts (Wundertüte, keine Sache).
    assert store.wortbeitraege_zu_beschluessen(
        [{"id": 1, "ksinr": 4663, "item_number": "16", "title": "Anfragen und Anregungen"}]) == []
    # Ohne Sitzungsbezug kein Treffer.
    assert store.wortbeitraege_zu_beschluessen([{"id": 9, "ksinr": None, "title": "Irgendwas"}]) == []


def test_wortbeitraege_zu_beschluessen_filtert_optional_nach_person(store):
    """Person + Ort bleibt über den Beschlussanker belegt, ohne Wortmeldungen
    anderer Personen aus demselben TOP mitzunehmen."""
    store.save_wortbeitraege(100, [
        {"kind": "speech", "top": "Ö 7 Sporthalle Kreyenbrück", "speaker": "Bernhard Ellberg",
         "party": "SPD", "text": "Die Halle soll zügig saniert werden.", "answer": None},
        {"kind": "speech", "top": "Ö 7 Sporthalle Kreyenbrück", "speaker": "Anna Beispiel",
         "party": "CDU", "text": "Die Finanzierung müsse geklärt werden.", "answer": None},
    ])
    official_text = {"id": 77, "ksinr": 100, "item_number": "7",
                 "title": "Sporthalle Kreyenbrück - Beschluss"}
    got = store.wortbeitraege_zu_beschluessen([official_text], speaker="Ellberg")
    assert [row["speaker"] for row in got] == ["Bernhard Ellberg"]
    assert got[0]["zu_beschluss"] == 77


def test_wortbeitraege_zu_beschluessen_deckelt_die_menge(store):
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (5000, 'Rat', '2026-03-01', '17:00', 'Rathaus', '2026-03-02')")
    store.save_wortbeitraege(5000, [
        {"kind": "speech", "top": "Grosses Thema", "speaker": f"Redner {i}",
         "party": None, "text": f"Beitrag {i}", "answer": None} for i in range(10)
    ])
    b = [{"id": 7, "ksinr": 5000, "item_number": "3", "title": "Grosses Thema"}]
    assert len(store.wortbeitraege_zu_beschluessen(b)) == 4          # max_je_top
    assert len(store.wortbeitraege_zu_beschluessen(b, max_je_top=99)) == 6  # max_gesamt


# ---- Zusagen-Kanal (Paket 2, 12.08.26) -------------------------------------

def test_hohle_zusagen_fallen_raus():
    """„Ich sichere eine Antwort zu Protokoll zu" ist Verfahren, keine
    Selbstverpflichtung — als Beleg unter einer Antwort wäre es Füllmaterial.
    Am Bestand gemessen: rund ein Viertel der 1.437 Zusagen."""
    hohl = [
        "Er sichert eine Antwort zu Protokoll zu.",
        "Sie sichert eine schriftliche Beantwortung zu.",
        "Die Frage wird mitgenommen.",
        "Er sagt zu, die Unterlagen nachzureichen.",
    ]
    substanz = [
        "Die Verwaltung sagt zu, die Formulierungen zur Gesellschafterversammlung zu prüfen.",
        "Die Stadt leistet einen Eigenkapitalzuschuss in Höhe von bis zu 15 Millionen Euro.",
        "Die Verwaltung wird nach der Sommerpause ausführlicher berichten.",
    ]
    assert all(emb._HOHLE_ZUSAGE.search(t) for t in hohl)
    assert not any(emb._HOHLE_ZUSAGE.search(t) for t in substanz)


def test_search_zusagen_filtert_und_haelt_die_strengere_grenze(monkeypatch):
    """Der Kanal zeigt NUR Zusagen — dann darf er keine thematisch schiefen
    liefern (beim Ärztemangel rutschte sonst eine Kita-Zusage durch). Deshalb
    eigener, strengerer Rerank-Cutoff."""
    import numpy as np

    class _S:
        def wortbeitrag_ids_nach_art(self, art):
            assert art == "pledge"
            return [1, 2, 3]

        def wortbeitraege_by_ids(self, ids):
            texte = {1: "Er sichert eine Antwort zu Protokoll zu.",
                     2: "Die Verwaltung sagt zu, den Zeitplan vorzulegen.",
                     3: "Die Stadt zahlt einen Zuschuss von 15 Millionen Euro."}
            return [{"id": i, "top": None, "text": texte[i]} for i in ids]

    monkeypatch.setattr(emb, "_wb_matrix",
                        lambda store: ([1, 2, 3], np.eye(3, dtype="float32")))
    monkeypatch.setattr(emb, "embed", lambda t: np.ones((1, 3), dtype="float32"))
    gesehen = {}

    def _fake_rerank(query, kandidaten, top_k, min_rerank=None):
        gesehen["ids"] = [i for i, _ in kandidaten]
        gesehen["min_rerank"] = min_rerank
        return [(i, 1.0) for i, _ in kandidaten][:top_k]

    monkeypatch.setattr(emb, "_rerank_kontext", _fake_rerank)
    treffer = emb.search_zusagen(_S(), "Was wurde zugesagt?", "Zusage")
    # Die Protokoll-Floskel (id 1) kommt gar nicht erst in den Rerank.
    assert gesehen["ids"] == [2, 3]
    # Strenger heißt HÖHER: -0,5 lässt weniger durch als die -1,5 der anderen Kanäle.
    assert gesehen["min_rerank"] == emb.ZUSAGE_RERANK_MIN > emb.KONTEXT_RERANK_MIN
    assert [i for i, _ in treffer] == [2, 3]

    # Ohne Zusagen im Bestand bleibt der Kanal still.
    class _Leer:
        def wortbeitrag_ids_nach_art(self, art):
            return []

    assert emb.search_zusagen(_Leer(), "Frage?", "Frage") == []
