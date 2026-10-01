"""Antwortstufe von „Frag den Rat“ (Gold-Test 01.10.2026): Punktfrage-Schutz,
Presse-Titelkanal, Wortbeitrags-Textkanal und „neueste zuerst“ bei
Stand-Fragen. Die Messungen dazu stehen an den Konstanten in council/qa.py."""
import pytest

from council import embeddings as emb
from council import qa
from council.store import CouncilStore


@pytest.mark.parametrize("frage", [
    "Wie wurde über den Mobilitätsplan Oldenburg 2030 entschieden?",
    "Wie hat der Rat zum Stadion abgestimmt?",
    "Wie haben die Ausschüsse das Thema behandelt?",
])
def test_way_questions_are_never_point_questions(frage):
    assert qa._KEINE_PUNKTFRAGE_RE.search(frage)


@pytest.mark.parametrize("frage", [
    "Wann wurde der Mobilitätsplan beschlossen?",
    "Wie viel kostet das Stadion?",
    "Wann kommen öffentliche Trinkwasserspender?",
])
def test_point_questions_stay_untouched(frage):
    assert not qa._KEINE_PUNKTFRAGE_RE.search(frage)


def test_stand_or_recency():
    assert qa.stand_or_recency("Wie ist der Stand beim Stadionneubau?")
    assert not qa.stand_or_recency("Wer hat den Antrag gestellt?")


def test_framing_words_are_not_title_words():
    assert qa._titel_woerter("Wie ist der Stand beim Stadionneubau?") == ["stadionneubau"]


@pytest.fixture
def store(tmp_path):
    st = CouncilStore(tmp_path / "c.sqlite")
    c = st._conn
    c.execute("INSERT INTO council_decisions (id, ksinr, position, title) VALUES "
              "(1, 10, 1, 'Spielplatz auf dem Schlossplatz'), (2, 10, 2, 'Stadionneubau')")
    c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
              "fetched_at) VALUES (10, 'Rat', '2025-12-11', '', '', ''), "
              "(11, 'Rat', '2026-04-16', '', '', '')")
    c.executemany("INSERT INTO council_speeches (id, ksinr, position, kind, top, speaker, text, "
                  "extracted_at) VALUES (?, ?, ?, 'speech', ?, ?, ?, '')", [
                      (1, 10, 1, '5 Spielplatzleitplanung', 'A', 'Der Spielplatz auf dem Schlossplatz fehlt.'),
                      (2, 11, 1, '7 Spielleitplanung', 'B', 'Auf dem Schlossplatz ist kein Platz für einen Spielplatz.'),
                      (3, 11, 2, '7 Spielleitplanung', 'C', 'Der Schlossplatz bleibt Veranstaltungsfläche.'),
                  ])
    c.executemany("INSERT INTO council_press (id, url, title, date, text, fetched_at) "
                  "VALUES (?, ?, ?, ?, ?, '')", [
        (1, 'u1', 'Stadion-Neubau: EU gibt grünes Licht', '2026-08-12', 'x'),
        (2, 'u2', 'Stadion-Neubau nimmt nächste Hürde', '2026-05-20', 'x'),
        (3, 'u3', 'Pokalspiel im Marschwegstadion', '2026-08-20', 'x'),
    ])
    c.commit()
    return st


def test_speech_text_ids_need_every_rare_word_newest_first(store):
    ids = qa.speech_text_ids(store, "Wie ist der Stand beim Spielplatz auf dem Schlossplatz?")
    assert ids == [2, 1]  # 3 nennt den Spielplatz nicht


def test_press_title_ids_ignore_hyphens_newest_first(store):
    assert qa.press_title_ids(store, "Wie ist der Stand beim Stadionneubau?") == [1, 2]


def test_stand_question_prefers_newest_confirmed_speech(store, monkeypatch):
    # Ohne Vektor-Index fiele die Suche auf BM25 zurück — hier zählt nur der
    # Textkanal, deshalb einen Index ohne Treffer simulieren.
    import numpy as np
    monkeypatch.setattr(emb, "_wb_matrix", lambda st: ([99], np.zeros((1, 2), dtype="float32")))
    monkeypatch.setattr(emb, "embed", lambda texte: np.zeros((len(texte), 2), dtype="float32"))
    monkeypatch.setattr(emb, "rerank", lambda q, paare, **kw: sorted(
        [(i, {1: 1.0, 2: 0.3, 3: -3.0}[i]) for i, _ in paare], key=lambda x: -x[1]))
    q = "Wie ist der Stand beim Spielplatz auf dem Schlossplatz?"
    nach_wert = emb.search_wortbeitraege(store, q, q, top_k=1, text_ids=[2, 1, 3])
    neueste = emb.search_wortbeitraege(store, q, q, top_k=1, text_ids=[2, 1, 3],
                                       neueste_zuerst=True)
    assert [i for i, _ in nach_wert] == [1]
    assert [i for i, _ in neueste] == [2]


def test_title_only_press_needs_a_clearer_match(monkeypatch):
    import numpy as np
    monkeypatch.setattr(emb, "_presse_matrix", lambda st: (
        [1, 3], ["EU gibt grünes Licht", "Pokalspiel"], np.zeros((2, 2), dtype="float32")))
    monkeypatch.setattr(emb, "embed", lambda texte: np.zeros((len(texte), 2), dtype="float32"))
    monkeypatch.setattr(emb, "rerank", lambda q, paare, **kw: sorted(
        [(i, {1: -0.2, 3: -1.3}[i]) for i, _ in paare], key=lambda x: -x[1]))
    hits = emb.search_presse(None, "Stand Stadion?", "Stadion", top_k=5, titel_ids=[1, 3])
    assert [i for i, _ in hits] == [1]


def test_press_block_lists_newest_first():
    block = qa._presse_block([{"title": "alt", "date": "2026-05-20"},
                              {"title": "neu", "date": "2026-08-12"}])
    assert block.index("neu") < block.index("alt")
