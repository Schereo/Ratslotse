"""Die Kandidaten-Rangliste (``/api/wahlabend/kandidaten``, ``election/candidates.py``).

Anlass: Tims Frage am Abend nach der Ratswahl 2026, wie einzelne
AfD-Kandidaturen auf so viele Personenstimmen kommen. Die Antwort steht in
zwei Zahlen, und dieser Test hält fest, dass sie stimmen — gegen den
eingefrorenen Stand von 2026, ohne Netz.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive, candidates  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    archive.reset()
    yield
    archive.reset()


@pytest.fixture(scope="module")
def nacht():
    n = archive.night("ratswahl-2026")
    assert n is not None
    return n


def test_jede_kandidatur_genau_einmal(nacht):
    r = candidates.ranking(nacht)
    assert r["total"] == r["shown"] == len(r["rows"]) == 383
    assert len({(z["party"], z["area"], z["position"]) for z in r["rows"]}) == 383
    assert [p["slug"] for p in r["parties"]] == [p["slug"] for p in nacht["parties"]]
    assert [a["number"] for a in r["areas"]] == [1, 2, 3, 4, 5, 6]


def test_nach_stimmen_sortiert_mit_stadtweitem_rang(nacht):
    r = candidates.ranking(nacht)
    stimmen = [z["votes"] for z in r["rows"]]
    assert stimmen == sorted(stimmen, key=lambda v: -(v or 0))
    assert r["rows"][0]["name"] == "Prange, Ulf" and r["rows"][0]["rank"] == 1
    # Gleichstand teilt den Rang: nach 1, 2, 2 kommt 4.
    raenge = [z["rank"] for z in r["rows"]]
    for i in range(1, len(raenge)):
        assert raenge[i] == raenge[i - 1] or raenge[i] == i + 1


def test_der_rang_bleibt_auch_gefiltert_stadtweit(nacht):
    afd = candidates.ranking(nacht, party="afd")
    assert afd["shown"] < afd["total"] == 383
    assert all(z["party"] == "afd" for z in afd["rows"])
    # Bernhardt (WB V) ist stadtweit Platz 4 — und bleibt es in der AfD-Ansicht.
    assert afd["rows"][0]["name"].startswith("Bernhardt") and afd["rows"][0]["rank"] == 4
    nur_v = candidates.ranking(nacht, area=5)
    assert all(z["area_roman"] == "V" for z in nur_v["rows"])
    beides = candidates.ranking(nacht, party="afd", area=5)
    assert 0 < beides["shown"] < afd["shown"]


def test_die_beiden_anteile_beantworten_die_frage(nacht):
    """Der Anteil je Person ist ihr Anteil an ALLEN Stimmen ihrer Liste im
    Wahlbereich (Liste + Personen); der Anteil je Liste sagt, wie
    personenbezogen ihre Wähler*innen stimmen."""
    r = candidates.ranking(nacht)
    bernhardt = next(z for z in r["rows"] if z["name"].startswith("Bernhardt"))
    wb = next(a for a in nacht["areas"] if a["number"] == bernhardt["area"])
    afd_v = next(p for p in wb["parties"] if p["slug"] == "afd")
    assert bernhardt["party_share_pct"] == round(100 * bernhardt["votes"] / afd_v["votes"], 1)
    # Die Personenanteile je Liste liegen alle in einem Fenster — und die
    # SPD-Wähler*innen stimmen am personenbezogensten, nicht die der AfD.
    anteile = {p["slug"]: p["personal_pct"] for p in r["parties"]}
    assert anteile["spd"] > anteile["afd"]
    spd = next(p for p in r["parties"] if p["slug"] == "spd")
    assert spd["personal_pct"] == round(100 * spd["candidate_votes"] / (spd["list_votes"] + spd["candidate_votes"]), 1)


def test_die_anderen_sortierungen(nacht):
    order = {p["slug"]: p["index"] for p in nacht["parties"]}
    nach_liste = candidates.ranking(nacht, sort="party")["rows"]
    idx = [order[z["party"]] for z in nach_liste]
    assert idx == sorted(idx)
    nach_wb = candidates.ranking(nacht, sort="area")["rows"]
    assert [z["area"] for z in nach_wb] == sorted(z["area"] for z in nach_wb)
    namen = [z["name"].casefold() for z in candidates.ranking(nacht, sort="name")["rows"]]
    assert namen == sorted(namen)
    with pytest.raises(ValueError):
        candidates.ranking(nacht, sort="egal")


def test_der_endpunkt_liefert_gefiltert_und_weist_unbekanntes_ab():
    r = router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026", sort="votes", party="spd", area=None, district=None)
    assert r["party"] == "spd" and r["area"] is None and all(z["party"] == "spd" for z in r["rows"])
    with pytest.raises(HTTPException) as e:
        router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026", sort="votes", party="xyz", area=None, district=None)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026", sort="votes", party=None, area=9, district=None)
    assert e.value.status_code == 404


def test_der_endpunkt_ist_hinter_dem_schalter(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    with pytest.raises(HTTPException) as e:
        router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026", sort="votes", party=None, area=None, district=None)
    assert e.value.status_code == 404
