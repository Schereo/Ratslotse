"""Das Facetten-Register (council/geld/) — die Wächter, die für JEDE
Modul-Facette gelten. Was eine einzelne Facette zieht und wie groß ihr
Baustein wird, misst ihre eigene Datei (tests/test_geld_<name>.py)."""
import pytest

from council import geld, qa
from council.store import CouncilStore


def test_register_ist_konsistent():
    namen = [f.name for f in geld.FACETTEN]
    assert len(namen) == len(set(namen))
    for f in geld.FACETTEN:
        assert f.name == f.name.lower() and " " not in f.name, f.name
        assert callable(getattr(CouncilStore, f.methode)), f.methode
        assert f.name in qa.GELD_FACETTEN and f.name in qa._GELD_BAUSTEINE
        assert f.grenze > 0 and f.probefrage.strip()
    # Reihenfolge: vorn vor den alten, hinten dahinter.
    alt = list(qa._ALTE_FACETTEN)
    reihe = list(qa.GELD_FACETTEN)
    for f in geld.FACETTEN:
        if f.rang < 500:
            assert reihe.index(f.name) < reihe.index(alt[0]), f.name
        else:
            assert reihe.index(f.name) > reihe.index(alt[-1]), f.name


@pytest.mark.parametrize("fac", geld.FACETTEN, ids=lambda f: f.name)
def test_probefrage_zieht_die_facette(fac):
    assert fac.name in qa.geld_facetten(fac.probefrage, "topic"), fac.probefrage


@pytest.mark.parametrize("fac", geld.FACETTEN, ids=lambda f: f.name)
def test_leere_datenbank_bleibt_still(fac, tmp_path):
    """Frische Datenbank ohne Ingest: Methode liefert nichts, Baustein ist
    leer, nichts wirft — die Facette ist Zusatz, nie Blocker."""
    store = CouncilStore(tmp_path / "c.sqlite")
    daten = getattr(store, fac.methode)(["haushalt", "stadt"], None)
    assert not daten, daten
    assert fac.block(daten) == ""
    assert fac.block(None) == ""
    store.close()


@pytest.mark.parametrize("fac", geld.FACETTEN, ids=lambda f: f.name)
def test_stille_fragen_ziehen_die_facette_nicht(fac):
    """Drei Fragen ohne jedes Geld — keine Modul-Facette darf anspringen."""
    for frage in ("Wie ist der Stand beim Stadion?",
                  "Was hat der Rat zur Baumschutzsatzung beschlossen?",
                  "Wer ist Oberbürgermeister von Oldenburg?"):
        assert fac.name not in qa.geld_facetten(frage, "topic"), (fac.name, frage)
