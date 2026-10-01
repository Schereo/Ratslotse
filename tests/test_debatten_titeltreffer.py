"""Aussprache zu Beschlüssen hinter Platz 8, die die Frage im Titel tragen
(council.qa.title_match_decisions). Anlass: Der Reranker stellte den
Trinkwasserspender-Bericht vom 16.04.2026 auf Platz 9, und mit ihm fehlte die
Protokollnotiz, die als einzige sagt, wann (Gold-Test 01.10.2026)."""
from council import qa


class _Store:
    def __init__(self, freq):
        self.freq = freq

    def title_frequencies(self, words):
        return {w: self.freq.get(w, 0) for w in words}


def _cands(*titles):
    return [{"id": i, "title": t} for i, t in enumerate(titles)]


FUELLER = [f"Beschluss {i}" for i in range(8)]


def test_rare_title_term_behind_head_is_coupled():
    cands = _cands(*FUELLER, "Prüfung von Machbarkeit öffentlicher Trinkwasserspender",
                   "Ersatz beschädigter Mülltonnen")
    out = qa.title_match_decisions(_Store({"trinkwasserspender": 4}),
                                   "Wann kommen öffentliche Trinkwasserspender in Oldenburg?",
                                   cands)
    assert [c["id"] for c in out] == [8]


def test_head_is_not_repeated():
    cands = _cands("Trinkwasserspender in Gebäuden", *FUELLER[1:])
    assert qa.title_match_decisions(_Store({"trinkwasserspender": 4}),
                                    "Wann kommen Trinkwasserspender?", cands) == []


def test_every_rare_term_must_be_in_the_title():
    # „Pfandretter am Schlossplatz“ trägt nur eines der beiden Wörter.
    cands = _cands(*FUELLER, "Pfandretter am Schlossplatz (Bericht)",
                   "Spielplatz auf dem Schlossplatz")
    out = qa.title_match_decisions(_Store({"spielplatz": 21, "schlossplatz": 7}),
                                   "Wie ist der Stand beim Spielplatz auf dem Schlossplatz?",
                                   cands)
    assert [c["title"] for c in out] == ["Spielplatz auf dem Schlossplatz"]


def test_common_terms_do_not_count():
    cands = _cands(*FUELLER, "Antrag zur Straße")
    assert qa.title_match_decisions(_Store({"antrag": 1171, "straße": 1100}),
                                    "Was wurde zum Antrag Straße beschlossen?", cands) == []


def test_inflected_term_falls_back_to_stem():
    cands = _cands(*FUELLER, "Trinkwasserspender in öffentlichen Gebäuden")
    out = qa.title_match_decisions(
        _Store({"trinkwasserspender": 4}),
        "Was ist aus dem Antrag zu Trinkwasserspendern geworden?", cands)
    assert [c["id"] for c in out] == [8]


def test_extra_is_capped():
    cands = _cands(*FUELLER, *["Trinkwasserspender"] * 9)
    out = qa.title_match_decisions(_Store({"trinkwasserspender": 4}),
                                   "Trinkwasserspender?", cands)
    assert len(out) == qa.DEBATTE_TITEL_EXTRA


def test_title_frequencies_counts_capitalised_nouns(tmp_path):
    from council.store import CouncilStore
    st = CouncilStore(tmp_path / "c.sqlite")
    st._conn.execute("INSERT INTO council_decisions (id, ksinr, position, title) VALUES "
                     "(1, 1, 1, 'Trinkwasserspender draußen'), (2, 1, 2, 'Mülltonnen')")
    assert st.title_frequencies(["trinkwasserspender", "stadion"]) == {
        "trinkwasserspender": 1, "stadion": 0}
