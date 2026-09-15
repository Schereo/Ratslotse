"""Was in Oldenburg nicht greifen KANN, fehlt Oldenburg nicht.

Die Karte widersprach sich selbst. Über Hannovers Antrag „Gleise in der
Limmerstraße fahrradfreundlich gestalten" stand:

    In Oldenburg nicht gefunden
    Oldenburg hat kein Stadtbahnsystem, daher gibt es keine Gleise, die
    fahrradfreundlich gestaltet werden könnten.

Nicht weil das Urteil falsch war, sondern weil es keine Schublade dafür gab:
`fit` kannte drei Stufen, und „geht hier gar nicht" war keine davon. Grob
gezählt betraf das am 14.09.2026 **557 von 9.833** Urteilen mit Status
„fehlt".
"""
from __future__ import annotations

import pytest

from council.cities import fit
from council.cities.annotators import FIT_STATUS
from council.cities.annotators import get as get_annotator


def test_die_vierte_stufe_gibt_es():
    assert "not_applicable" in FIT_STATUS


def test_sie_braucht_keinen_beleg():
    """Eine Behauptung über die STADT, nicht über ihre Beschlüsse.

    „Oldenburg hat keine Stadtbahn" steht in keiner Ratsvorlage. Einen Beleg
    dafür zu verlangen hieße, das Modell zum Erfinden einzuladen — und genau
    erfundene Belege hält der Prüfstand bei null.
    """
    last = get_annotator("fit").payload.model_validate(
        {"status": "not_applicable", "evidence": [], "reason": "keine Stadtbahn",
         "confidence": "high"})
    assert last.braucht_beleg is False


@pytest.mark.parametrize("status", ["present", "partial"])
def test_die_behauptungen_ueber_beschluesse_brauchen_weiter_einen(status):
    last = get_annotator("fit").payload.model_validate(
        {"status": status, "evidence": ["oldenburg:paper:1"], "reason": "x",
         "confidence": "high"})
    assert last.braucht_beleg is True


def test_bei_stimmengleichheit_gewinnt_die_schwaechere_behauptung():
    """Zwei Stimmen „fehlt" gegen zwei „geht hier nicht" gehen als „fehlt" aus.

    `not_applicable` nimmt eine Idee nicht nur von der Liste, es erklärt sie
    für unmöglich — die kühnste der vier Aussagen. Dieselbe Asymmetrie wie
    bei „Oldenburg hat das schon".
    """
    assert fit.STATUS_ORDNUNG.index("not_applicable") > fit.STATUS_ORDNUNG.index("missing")
    assert fit._mehrheit(["missing", "missing", "not_applicable", "not_applicable"],
                         fit.STATUS_ORDNUNG) == "missing"


def test_jede_stufe_steht_in_der_rangfolge():
    """Ein Wert, den `STATUS_ORDNUNG` nicht kennt, landet bei Gleichstand
    auf Position 99 — also hinter allem, stumm und zufällig."""
    assert set(fit.STATUS_ORDNUNG) == set(FIT_STATUS)


def test_die_uebersicht_zaehlt_alle_vier(tmp_path):
    """Sonst ergibt `total` nicht mehr die Summe der Stufen.

    Eine Übersicht, deren Zahlen nicht aufgehen, ist schlimmer als eine ohne:
    Wer nachrechnet, hält den Rest für einen Fehler.
    """
    from council.cities.model import Batch, Paper
    from council.cities.store import CitiesStore

    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper(f"p/{i}", "muenster", f"Sache {i}", date="2024-01-01", kind="motion")
            for i in range(4)]))
        for i, status in enumerate(FIT_STATUS):
            s.put_annotation("paper", f"p/{i}", "classify", "2",
                             {"field": "verkehr", "transfer": "adaptable",
                              "instrument": "x", "summary": "y"}, "h", "m", 0.0)
            s.put_annotation("paper", f"p/{i}", "fit", "4",
                             {"status": status, "evidence": [], "reason": "",
                              "confidence": "high"}, "h", "m", 0.0)
        (zeile,) = s.idea_fields()
    summe = sum(int(zeile[k] or 0) for k in FIT_STATUS)
    assert summe == int(zeile["total"]), (
        f"total={zeile['total']}, aber die Stufen ergeben {summe} — "
        "eine Stufe fehlt im Zähler von `idea_fields`.")


def test_der_prompt_nennt_die_stufe_und_ihre_grenze():
    """Der Wächter gegen die stille Fassung: Werteliste erweitert, Prompt
    nicht — dann ist die Stufe erlaubt und wird nie gewählt."""
    from kern import prompts

    text = prompts.get("cities_fit_system")
    assert "not_applicable" in text
    assert "voraussetzung" in text.lower(), (
        "Die Stufe muss auf eine fehlende VORAUSSETZUNG begrenzt sein — sonst "
        "wird sie zur Ausrede fuer alles, was Oldenburg kleiner oder aermer ist.")
