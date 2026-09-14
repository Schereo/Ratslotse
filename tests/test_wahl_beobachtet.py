"""Die Beobachtungsliste: Kandidaturen merken, quer über alle Listen.

Tims Wunsch (14.09.2026): „bestimmte Kandidaten aus allen Parteien zum
beobachten auswählen." Die Rangliste führt 383 Kandidaturen; wer fünf Namen
verfolgt, will sie nebeneinander sehen und nicht fünfmal filtern.

Gespeichert wird in der Merkliste-Tabelle, die es schon gibt — mit einer
eigenen Art (``candidate``) und einem Schlüssel aus dem Tripel, das eine
Kandidatur eindeutig macht. **Die Ratsliste zeigt sie nicht**: Sie hat weder
Sitzung noch Vorlage, und `enrich_bookmark` machte daraus eine leere Zeile.
Genau das hält der letzte Test fest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    archive.reset()
    yield
    archive.reset()


@pytest.fixture
def store(tmp_path):
    from kern.store import Store

    s = Store(tmp_path / "konten.sqlite")
    yield s
    s.close()


@pytest.fixture
def konto(store):
    return {"id": 4711}


def _merke(store, konto, partei: str, bereich: int, platz: int):
    return router.wahlabend_beobachten(
        payload=router.WatchIn(election="ratswahl-2026", party=partei, area=bereich, position=platz),
        user=konto, store=store,
    )


def test_merken_quer_ueber_die_listen(store, konto):
    a = _merke(store, konto, "spd", 2, 1)       # Prange, Platz 1 in WB II
    b = _merke(store, konto, "afd", 5, 1)       # Bernhardt, Platz 1 in WB V
    assert a["name"].startswith("Prange") and b["name"].startswith("Bernhardt")
    assert "Wahlbereich II" in a["subtitle"] and "Platz 1" in a["subtitle"]

    liste = router.wahlabend_beobachtet(wahl="ratswahl-2026", probe=None, counted=None,
                                        user=konto, store=store)
    assert [e["party"] for e in liste["entries"]] == ["spd", "afd"]
    # Sortiert nach dem stadtweiten Rang: Prange ist Erster, Bernhardt Vierter.
    assert [e["row"]["rank"] for e in liste["entries"]] == [1, 4]
    assert liste["election"]["slug"] == "ratswahl-2026"


def test_zweimal_merken_bleibt_ein_eintrag(store, konto):
    erst = _merke(store, konto, "gruene", 1, 1)
    nochmal = _merke(store, konto, "gruene", 1, 1)
    assert erst["id"] == nochmal["id"]
    liste = router.wahlabend_beobachtet(wahl="ratswahl-2026", probe=None, counted=None,
                                        user=konto, store=store)
    assert len(liste["entries"]) == 1


def test_eine_kandidatur_die_es_nicht_gibt(store, konto):
    with pytest.raises(HTTPException) as e:
        _merke(store, konto, "spd", 2, 99)
    assert e.value.status_code == 404


def test_entfernen_nur_die_eigenen(store, konto):
    eintrag = _merke(store, konto, "cdu", 4, 1)
    fremd = {"id": konto["id"] + 1}
    with pytest.raises(HTTPException) as e:
        router.wahlabend_nicht_mehr_beobachten(merker_id=eintrag["id"], user=fremd, store=store)
    assert e.value.status_code == 404, "ein fremder Merker darf nicht einmal als vorhanden gelten"

    router.wahlabend_nicht_mehr_beobachten(merker_id=eintrag["id"], user=konto, store=store)
    liste = router.wahlabend_beobachtet(wahl="ratswahl-2026", probe=None, counted=None,
                                        user=konto, store=store)
    assert liste["entries"] == []


def test_nur_die_merker_dieser_wahl(store, konto):
    _merke(store, konto, "spd", 2, 1)
    # Ein Merker einer anderen Wahl (von Hand, die gibt es im Repo nicht als
    # Rangliste) darf die Liste nicht verunreinigen.
    store.add_bookmark(konto["id"], kind="candidate",
                       target_key="candidate:ratswahl-2031:spd:1:1",
                       title="Jemand", subtitle="SPD")
    liste = router.wahlabend_beobachtet(wahl="ratswahl-2026", probe=None, counted=None,
                                        user=konto, store=store)
    assert [e["name"] for e in liste["entries"]] == [liste["entries"][0]["name"]]
    assert len(liste["entries"]) == 1


def test_die_ratsliste_zeigt_keine_kandidaturen(store, konto):
    """Dieselbe Tabelle, zwei Listen — die Ratsliste bleibt eine Ratsliste."""
    from app.routers import bookmarks as rats

    _merke(store, konto, "spd", 2, 1)

    class LeererRat:
        def get_session(self, *_a, **_k):
            return None

        def agenda_items(self, *_a, **_k):
            return []

        def get_decision(self, *_a, **_k):
            return None

    antwort = rats.list_bookmarks(user=konto, ratslotse=store, council=LeererRat())
    assert antwort["bookmarks"] == []


def test_ohne_schalter_geht_nichts(store, konto, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    with pytest.raises(HTTPException) as e:
        router.wahlabend_beobachtet(wahl="ratswahl-2026", probe=None, counted=None,
                                    user=konto, store=store)
    assert e.value.status_code == 404
