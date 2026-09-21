"""Die Trennlinie von „nicht anwendbar": Kann der Rat sich das beschaffen?

Die Stufe kam mit Fassung 4 und hat in ihrem ersten Lauf genau die Ideen
versteckt, für die es das Feature gibt. Von 60 Urteilen waren rund acht von
dieser Sorte, **fünfmal ein Jugendparlament**:

    Oldenburg hat kein Jugendparlament, daher kann dessen Satzung nicht
    geändert werden.

Sechs Vergleichsstädte haben eins, Oldenburg nicht — das ist die Lücke,
nicht ihr Gegenteil. Ein Rat kann ein Jugendparlament einrichten; eine
Stadtbahn kann er nicht beschließen.
"""
from __future__ import annotations

from council.cities.store import CitiesStore
from kern import prompts


def test_der_prompt_stellt_die_entscheidende_frage():
    text = prompts.get("cities_fit_system")
    assert "beschließen" in text, (
        "Die Trennlinie fehlt: `not_applicable` gilt nur, wenn der Rat die "
        "Voraussetzung NICHT selbst beschließen koennte.")


def test_beide_seiten_stehen_mit_beispielen_da():
    """Eine Regel ohne Gegenbeispiel wird als Ausrede benutzt."""
    text = prompts.get("cities_fit_system")
    for kann_nicht in ("Stadtbahn", "Hafen"):
        assert kann_nicht in text, f"{kann_nicht} fehlt als Beispiel fuer NEIN"
    for kann_schon in ("Jugendparlament", "Verpackungssteuer"):
        assert kann_schon in text, f"{kann_schon} fehlt als Beispiel fuer JA"


def test_mitten_in_der_einfuehrung_ist_teilweise():
    """Ein Fall aus dem Lauf: Oldenburgs Zweckentfremdungssatzung steckte im
    Beteiligungsverfahren und wurde als unanwendbar geführt."""
    assert "partial" in prompts.get("cities_fit_system")


def test_die_fassung_ist_hochgezaehlt():
    """Ein geänderter Prompt unter derselben Fassung macht zwei Generationen
    von Urteilen ununterscheidbar."""
    from council.cities.annotators import get as get_annotator
    from council.cities.store import CitiesStore

    assert get_annotator("fit").version == "5"
    assert CitiesStore.IDEEN_FIT == ("fit", "5"), (
        "Die Oberfläche liest noch die alte Fassung — dann bleibt die Liste "
        "leer, bis alles neu beurteilt ist.")


def test_die_uebernahme_laesst_die_strittigen_stehen(tmp_path):
    """Der Wächter für `scripts/cities_fit_fassung5.py`.

    Übernommen werden die drei anderen Stufen; die `not_applicable`-Urteile
    müssen offen bleiben, sonst wandert der Fehler unverändert mit.
    """
    import importlib.util
    from pathlib import Path

    from council.cities.model import Batch, Paper

    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper(f"p/{i}", "muenster", f"Sache {i}", date="2024-01-01", kind="motion")
            for i in range(4)]))
        for i, status in enumerate(("missing", "partial", "present", "not_applicable")):
            s.put_annotation("paper", f"p/{i}", "fit", "4",
                             {"status": status, "evidence": [], "reason": "x",
                              "confidence": "high"}, "h", "m", 0.0)

    pfad = Path(__file__).resolve().parents[1] / "scripts" / "cities_fit_fassung5.py"
    spec = importlib.util.spec_from_file_location("cities_fit_fassung5", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    import sys as _sys
    alt = _sys.argv
    _sys.argv = ["x", "--db", str(tmp_path / "c.sqlite")]
    try:
        modul.main()
    finally:
        _sys.argv = alt

    with CitiesStore(tmp_path / "c.sqlite") as s:
        neu = {r["object_id"] for r in s._conn.execute(
            "SELECT object_id FROM annotations WHERE annotator='fit' AND version='5'")}
    assert neu == {"p/0", "p/1", "p/2"}, (
        "Das `not_applicable`-Urteil wurde mit übernommen — dann wird es nie "
        "neu gefällt und der Fehler bleibt.")

