"""Welche Vorlagen am Vergleich teilnehmen — und dass keine Stufe daran vorbeigeht.

Zwei Einschränkungen stehen je Stadt in der Registry: ab wann (``compare_since``)
und welche Arten (``compare_kinds``). Beide kosten Geld, wenn sie fehlen:
Hannover trug am 13.09.2026 **24.654** Kandidaten seit 2017 gegen die drei
Jahre der OParl-Städte — rund $75 statt $35, und ein Vergleich über ungleiche
Zeiträume.
"""
from __future__ import annotations

import inspect

import pytest

from council.cities import annotate, auswahl, fit
from council.cities.model import Batch, Paper
from council.cities.registry import BODIES
from council.cities.store import CitiesStore


@pytest.fixture()
def store(tmp_path):
    with CitiesStore(tmp_path / "cities.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper("h/alt", "hannover", "Antrag von 2019", date="2019-05-01", kind="motion"),
            Paper("h/neu", "hannover", "Antrag von 2024", date="2024-05-01", kind="motion"),
            Paper("h/frage", "hannover", "Anfrage von 2024", date="2024-05-01", kind="inquiry"),
            Paper("o/alt", "oldenburg", "Beschluss von 2019", date="2019-05-01", kind="motion"),
        ]))
        yield s


def test_hannovers_anfragen_bleiben_draussen(store):
    """6.483 Anfragen mit 1 % Ergebnis — dort wird beantwortet, nicht beschlossen.

    Tims Entscheidung vom 13.09.2026. Sie steht in der Registry, nicht im
    Code: Die nächste Stadt entscheidet das für sich.
    """
    kennungen = {p["id"] for p in auswahl.papiere(store, "hannover")}
    assert kennungen == {"h/neu"}, "Anfrage und Altfall gehören nicht hinein"


def test_oldenburg_bleibt_ungefenstert(store):
    """Die Bezugsstadt trägt die Antwort auf „hat Oldenburg das schon?".

    Ein Beschluss von 2019 beantwortet sie genauso gut wie einer von 2024 —
    ihn auszusperren hieße, Oldenburg ärmer zu rechnen, als es ist.
    """
    assert BODIES["oldenburg"].compare_since is None
    assert {p["id"] for p in auswahl.papiere(store, "oldenburg")} == {"o/alt"}


def test_ohne_stadt_gilt_je_stadt_ihr_eigenes_fenster(store):
    """Ein Lauf über alle darf nicht auf das offenste Fenster zurückfallen."""
    kennungen = {p["id"] for p in auswahl.papiere(store)}
    assert kennungen == {"h/neu", "o/alt"}


def test_eine_unbekannte_stadt_wird_nicht_ausgesperrt(store):
    """Der Speicher ist die Wahrheit über den Bestand, nicht die Registry."""
    assert auswahl.fenster("gibtsnicht") == auswahl.Fenster(None, ())


def test_die_bezahlten_stufen_gehen_ueber_auswahl():
    """Der Wächter: Wer Kandidaten wählt, fragt ``auswahl`` — sonst niemanden.

    ``annotate.run`` und ``fit.candidates_for`` sind die beiden Stellen, an
    denen Vorlagen zu bezahlter Arbeit werden. Ein direktes
    ``main.papers(body_id=…)`` dort umginge Fenster und Arten stumm — und
    genau so ist der Fehler entstanden, den dieser Test verhindert: Die Regel
    stand an einer Stelle und wurde an zweien gebraucht.
    """
    for funktion in (annotate.run, fit.candidates_for):
        quelle = inspect.getsource(funktion)
        assert "auswahl.papiere" in quelle, (
            f"{funktion.__qualname__} wählt Kandidaten ohne `auswahl.papiere` — "
            "damit gelten weder `compare_since` noch `compare_kinds`.")
        assert "main.papers(body_id" not in quelle, (
            f"{funktion.__qualname__} fragt den Speicher direkt und umgeht "
            "das Vergleichsfenster.")


def test_die_kostenvorschau_rechnet_mit_den_buendeln():
    """Der Preis steht je 1.000 AUFRUFE da, die Vorschau zählt VORLAGEN.

    `classify` bündelt zu sechst, `effort` zu acht — wer das übergeht,
    schätzt das Achtfache. Gemessen am Lauf vom 13.09.2026: 4.921 Urteile
    für $0,725, also $0,147 je 1.000 Vorlagen; die erste Fassung der
    Vorschau sagte $1,15. Eine Schätzung, der man nicht glauben kann, hält
    einen richtigen Lauf auf.
    """
    import importlib.util
    from pathlib import Path

    from council.cities.annotators import get as get_annotator

    pfad = Path(__file__).resolve().parents[1] / "scripts" / "cities_backfill.py"
    spec = importlib.util.spec_from_file_location("cities_backfill", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    je_1000 = modul.kosten_je_1000_vorlagen()
    roh = sum(modul.KOSTEN_JE_1000_AUFRUFE.values()) + modul.KOSTEN_TERMS_JE_1000
    assert je_1000 < roh, (
        "Die Vorschau rechnet wieder je Aufruf statt je Vorlage — "
        "sie muss durch `Annotator.batch_size` teilen.")
    # `classify` allein: der Preis je 1.000 Aufrufe, geteilt durch das Bündel.
    erwartet = modul.KOSTEN_JE_1000_AUFRUFE["classify"] / get_annotator("classify").batch_size
    assert erwartet < 0.25, f"classify je 1.000 Vorlagen: ${erwartet:.3f}"
