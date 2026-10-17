"""Ortserkennung der KI-Frage: Wortlaut zuerst, dann die Wahl der Analyse.

Anlass (12.10.2026): „Was wird gerade beim Oldenburger Hafenbecken gebaut?“
fand keinen Ort — „Hafenbecken“ steht in keinem Alias. Statt Synonyme
nachzutragen, sieht die Frage-Analyse die Ortsliste und wählt (Tim,
16.10.2026). Gemessen mit ``eval/run_ortserkennung.py``: 10/20 → 19/20.
Diese Tests halten die Regeln fest, ohne Modell.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import qa


def _ort(id_: str, name: str, kind: str, parents: tuple[str, ...] = ()):
    from council.places import Place
    return Place(id=id_, name=name, kind=kind, aliases=(), electoral_districts=(),
                 parent_ids=parents, description=None, source_ids=(), filterable=True,
                 quiz_enabled=False, lat=None, lon=None)


class _Store:
    def __init__(self):
        self.places = (
            _ort("donnerschwee", "Donnerschwee", "local_area"),
            _ort("neu-donnerschwee", "Neu-Donnerschwee", "neighborhood", ("donnerschwee",)),
            _ort("osternburg", "Osternburg", "local_area"),
            _ort("alter-stadthafen", "Alter Stadthafen", "redevelopment_area"),
        )

    def all_places(self):
        return self.places


def _analyse_mit(monkeypatch, antwort: dict):
    gesehen: list[str] = []

    def chat(**kw):
        gesehen.append(kw["messages"][0]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(antwort)))], usage=None)
    monkeypatch.setattr(qa.llm, "chat_complete", chat)
    qa._ANALYSE_CACHE.clear()
    return gesehen


def test_die_analyse_waehlt_nur_aus_der_liste(monkeypatch):
    store = _Store()
    gesehen = _analyse_mit(monkeypatch, {"terms": "Hafen Sanierung", "ort": "alter-stadthafen"})
    a = qa.analyse_query("Was wird beim Hafenbecken gebaut?", orte=qa.ortsliste(store))
    assert a["ort_id"] == "alter-stadthafen"
    assert "alter-stadthafen: Alter Stadthafen" in gesehen[0]
    # Eine erfundene id zählt nicht.
    _analyse_mit(monkeypatch, {"terms": "Hafen", "ort": "neuer-hafen"})
    assert "ort_id" not in qa.analyse_query("Was ist am Hafen?", orte=qa.ortsliste(store))
    # Ohne Liste fragt der Prompt gar nicht nach einem Ort.
    gesehen = _analyse_mit(monkeypatch, {"terms": "Grundsteuer", "ort": "osternburg"})
    a = qa.analyse_query("Wie hoch ist die Grundsteuer?")
    assert "ort_id" not in a and "ORTE in Oldenburg" not in gesehen[0]
    qa._ANALYSE_CACHE.clear()


def test_der_wortlaut_geht_vor_ausser_die_wahl_liegt_darin():
    store = _Store()
    stadtteil = qa.ort_aus_id("donnerschwee", store)
    # Genauer innerhalb des Stadtteils: die Wahl gewinnt.
    assert qa.ort_entscheiden(stadtteil, "neu-donnerschwee", store)["id"] == "neu-donnerschwee"
    # Einen ANDEREN Ort darf die Wahl dem Wortlaut nicht unterschieben.
    assert qa.ort_entscheiden(stadtteil, "osternburg", store)["id"] == "donnerschwee"
    # Ohne Wortlaut-Treffer: die Wahl, oder nichts.
    assert qa.ort_entscheiden(None, "alter-stadthafen", store)["id"] == "alter-stadthafen"
    assert qa.ort_entscheiden(None, None, store) is None


def test_die_liste_kommt_nur_ohne_genauen_treffer():
    store = _Store()
    assert qa.braucht_ortsliste(None)
    assert qa.braucht_ortsliste(qa.ort_aus_id("osternburg", store))  # nur ein Stadtteil
    assert not qa.braucht_ortsliste(qa.ort_aus_id("alter-stadthafen", store))


def test_die_eval_faelle_nennen_nur_echte_orte():
    """Eine erwartete id, die es im Basiskatalog nicht gibt, liefe in der
    Messung still als Fehlschlag. Geprüft gegen den Basiskatalog plus die
    redaktionellen Orte, die die Fälle brauchen."""
    from pathlib import Path
    faelle = json.loads((Path(__file__).parent.parent / "eval" / "cases_ortserkennung.json").read_text())
    assert len(faelle) >= 20
    assert sum(1 for f in faelle if f["expect"] == [None]) >= 5, "zu wenige Fragen ohne Ort"
