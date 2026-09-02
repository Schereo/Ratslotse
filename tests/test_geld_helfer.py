"""Die geteilten Helfer des Facetten-Pakets — was jede Facette sonst selbst
nachbaute (und beim ersten Anlauf falsch: „+42.8 %“)."""
import sqlite3

from council import geld
from council.store import CouncilStore


def test_formatierer_schreiben_deutsch():
    assert geld.de_euro(788_669.4) == "788.669 €"
    assert geld.de_euro(None) == "–"
    assert geld.de_zahl(1702.25, 2) == "1.702,25"
    assert geld.de_prozent(42.84) == "42,8 %"
    assert geld.de_mio(-2_700_000) == "-2,7 Mio. €"
    assert geld.de_betrag(-15_621) == "-15.621 €" and geld.de_betrag(2_700_000) == "2,7 Mio. €"


def test_beleg_text_wie_in_qa():
    b = {"label": "Jahresabschluss 2024", "citation": "Abschnitt 6.2", "page": 41,
         "as_of": "31.12.2024"}
    assert geld.beleg_text(b) == " — Beleg: Jahresabschluss 2024, Abschnitt 6.2, S. 41"
    assert geld.beleg_text(b, stand=True).endswith(", Stand 31.12.2024")
    assert geld.beleg_text(None) == "" and geld.beleg_text({"page": None}) == ""


def test_jahr_aus_text_liest_den_punkt_nicht_den_zeitraum():
    assert geld.jahr_aus_text("Was erwartet die Verwaltung für 2026?") == 2026
    assert geld.jahr_aus_text(geld.falte("Wie liefen die Haushalte von 2019 bis 2024?")) is None
    assert geld.jahr_aus_text("Wie haben sich die Ausgaben seit 2020 entwickelt?") is None
    assert geld.jahr_aus_text("Was kostet die Feuerwehr?") is None


def test_lesestore_liest_und_schreibt_nicht(tmp_path):
    pfad = tmp_path / "c.sqlite"
    st = CouncilStore(pfad)
    with st._conn:
        st._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            " as_of, fetched_at) VALUES (1, 'k', 'ris', 'Doc', 'https://example.org', "
            " 'Abschnitt 1', 'p', '2024', '2026-09-02')")
    st.close()
    lese = geld.lesestore(str(pfad))
    assert lese._beleg(1)["label"] == "Doc"
    assert lese._trifft("Personalaufwendungen", ["Personal"]) == 1
    for fac in geld.FACETTEN:
        assert callable(getattr(lese, fac.methode))
    try:
        lese._conn.execute("INSERT INTO council_provenance (id, key, kind, fetched_at) "
                           "VALUES (2, 'k2', 'ris', '')")
        schreibbar = True
    except sqlite3.OperationalError:
        schreibbar = False
    assert not schreibbar
    lese.close()


def test_baeder_als_wort_zieht_betriebe_und_gesellschaften():
    """„Zuschuss für die Bäder" zog bis 02.09. nur den Plan — der Bäderbetrieb
    stand nur als Kompositum in den Mustern."""
    from council import qa
    f = qa.geld_facetten("Wie hoch ist der Zuschuss der Stadt für die Bäder?", "money")
    assert {"business_plans", "companies"} <= f
