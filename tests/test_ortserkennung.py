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


def test_die_wahl_ist_ein_hinweis_kein_filter():
    """Die Wahl der Analyse filtert nicht (Gold 17.10.2026: „Weser-Ems-Hallen“
    → Innenstadt warf als Filter alles andere weg, 0,56 → 0,00). Sie kommt als
    Hinweis zurück — außer sie ist der Wortlaut-Ort selbst."""
    store = _Store()
    stadtteil = qa.ort_aus_id("donnerschwee", store)
    assert qa.ort_hinweis(stadtteil, "neu-donnerschwee", store)["id"] == "neu-donnerschwee"
    assert qa.ort_hinweis(stadtteil, "donnerschwee", store) is None   # filtert schon
    assert qa.ort_hinweis(None, "alter-stadthafen", store)["id"] == "alter-stadthafen"
    assert qa.ort_hinweis(None, None, store) is None
    assert qa.ort_hinweis(None, "gibt-es-nicht", store) is None


def test_der_router_nimmt_die_wahl_nicht_als_filter():
    """Wächter am Quelltext: Der Ortsfilter (`ort`) kommt nur aus dem
    Wortlaut; die Wahl geht als `hinweis_ids` an die Suche."""
    from pathlib import Path
    quelle = (Path(__file__).parent.parent / "web/backend/app/routers/council.py").read_text()
    assert "ort = qa.finde_ort(q_suche, store) or qa.finde_ort(q, store)\n" in quelle
    assert "hinweis_ids=" in quelle and "ort_entscheiden" not in quelle


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


# ---- Themen ohne wörtlichen Namen (Schalter `suche-ausbau`) ----------------

class _ThemenStore:
    def entity_suchindex(self):
        return [(853, "Stadion Oldenburg", 40), (740, "Stadionneubau Maastrichter Straße", 22),
                (168, "Klinikum Oldenburg", 30), (900, "Oldenburger Turnerbund", 5),
                (740, "stadionneubau", 22)]


def test_themen_kandidaten_nach_wortanfang_ohne_allerweltswoerter():
    store = _ThemenStore()
    ids = [i for i, _ in qa.themen_kandidaten(store, "Wie stehen die Fraktionen zum neuen Stadion?")]
    assert set(ids) == {853, 740}
    # „Oldenburger …“ trifft nicht jede Frage mit „Oldenburger“.
    assert qa.themen_kandidaten(store, "Was macht der Oldenburger Rat?") == []
    # Der angezeigte Name ist der des Themas, nicht der Alias-Slug.
    assert dict(qa.themen_kandidaten(store, "Wie geht es mit dem Stadion weiter?"))[740] \
        == "Stadionneubau Maastrichter Straße"


def test_die_analyse_waehlt_hoechstens_drei_themen_aus_der_liste(monkeypatch):
    gesehen = _analyse_mit(monkeypatch, {"terms": "Stadion", "themen": [853, "740", 999, 168, 5]})
    themen = [(853, "Stadion Oldenburg"), (740, "Stadionneubau"), (168, "Klinikum"), (5, "X")]
    a = qa.analyse_query("Wie stehen die Fraktionen zum neuen Stadion?", themen=themen)
    assert a["themen_ids"] == [853, 740, 168]        # 999 fehlt in der Liste, höchstens drei
    assert "853: Stadion Oldenburg" in gesehen[0]
    qa._ANALYSE_CACHE.clear()


def test_der_router_nimmt_themen_nur_als_hinweis():
    from pathlib import Path
    quelle = (Path(__file__).parent.parent / "web/backend/app/routers/council.py").read_text()
    i = quelle.index("hinweis_ids=(")
    assert 'analyse["themen_ids"]' in quelle[i:i + 600]
