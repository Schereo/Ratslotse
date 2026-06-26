"""Precision guard for council↔NWZ press matching (scripts/link_news.py)."""
from scripts.link_news import _topical_match, _words


def test_specific_compound_alone_is_enough():
    # A long, specific compound shared by both is a strong anchor on its own.
    assert _topical_match({"fliegerhorst", "sanierung"}, {"fliegerhorst", "strasse"})
    assert _topical_match({"klävemann", "haushalt"}, {"klävemann"})  # 9 letters


def test_two_shared_words_are_enough():
    assert _topical_match({"radweg", "fahrrad", "verkehr"}, {"radweg", "fahrrad"})


def test_single_generic_shared_word_is_rejected():
    # The spurious cases: one short shared word is not a topical match.
    assert not _topical_match({"wasser"}, {"wasser", "starkregen"})  # Bürgschaft ↔ Starkregen
    assert not _topical_match({"steuer", "haushalt"}, {"steuer", "rente"})  # budget ↔ tax-news
    assert not _topical_match({"klimaschutz"}, set())  # no overlap at all


def test_words_strips_generic_civic_terms():
    w = _words("Beschluss der Stadt Oldenburg zum Fliegerhorst")
    assert "fliegerhorst" in w
    assert "oldenburg" not in w and "stadt" not in w and "beschluss" not in w
