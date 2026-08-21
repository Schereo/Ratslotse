"""Der Presse-Kanal der Gründlichen Recherche ist weiter offen als der UI-Block."""
from council import embeddings as emb
from web.backend.app import deepresearch


def test_bericht_liest_mehr_presse_als_der_ui_block():
    """Die schnelle Antwort zeigt höchstens drei Meldungen — bewusst.

    Ein Bericht, der 28 Beschlüsse und 12 Wortbeiträge liest, darf nicht bei
    drei Pressemitteilungen stehenbleiben. Am 20.08.2026 gemessen: Zur
    Baumschutzsatzung fand der enge Kanal KEINE der sieben Meldungen zum
    Bürgerentscheid, der weite drei.
    """
    eng = emb.search_presse.__defaults__[0]      # top_k des UI-Blocks
    assert eng == 3
    assert deepresearch.PRESSE_TOP > eng


def test_schwelle_bleibt_streng_genug():
    """Zu tief geöffnet holt der Kanal thematisch fremde Meldungen herein."""
    assert 0.30 <= deepresearch.PRESSE_MIN <= 0.45
