"""Der Stand je Wahlbezirk (``/api/wahlabend/wahlbezirke``).

Die Zahlen lagen längst im Abruf: ``service._fill_areas`` liest die
Bezirksdatei, summiert sie zu Wahlbereichen und wirft die Einzelzeile weg.
Für „wie hat mein Wahllokal gewählt?" ist genau sie die Antwort — und für die
Karte, die Tim sich gewünscht hat, die Filterebene darunter.

Die harte Zusage steht hier als Test: **Die Bezirke summieren sich zu den
Wahlbereichen.** Bisher war das eine Annahme des Codes; wenn sie bricht,
zeigen Karte und Tafel verschiedene Zahlen für dieselbe Wahl.
"""
from __future__ import annotations

import collections
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


@pytest.fixture(scope="module")
def bezirke():
    d = archive.districts("ratswahl-2026")
    assert d is not None
    return d


@pytest.fixture(scope="module")
def nacht():
    n = archive.night("ratswahl-2026")
    assert n is not None
    return n


def test_alle_bezirke_der_ratswahl_2026(bezirke):
    assert bezirke["total"] == len(bezirke["districts"]) == 133
    assert bezirke["counted"] == 133 and bezirke["phase"] == "complete"
    urne = [z for z in bezirke["districts"] if not z["postal"]]
    brief = [z for z in bezirke["districts"] if z["postal"]]
    assert len(urne) == 91 and len(brief) == 42
    # Aufsteigend nach Nummer — die Reihenfolge ist Teil der Antwort, sonst
    # sortiert jedes Frontend anders.
    nummern = [z["number"] for z in bezirke["districts"]]
    assert nummern == sorted(nummern)


def test_jeder_bezirk_kennt_seinen_wahlbereich(bezirke):
    for z in bezirke["districts"]:
        # Urnenbezirke tragen ihn in der Hunderterstelle (101…115 = I),
        # Briefwahlbezirke in der Zehnerstelle (910…916 = I).
        erwartet = (z["number"] - 900) // 10 if z["postal"] else z["number"] // 100
        assert z["area"] == erwartet, z["number"]
        assert 1 <= z["area"] <= 6


def test_die_bezirke_summieren_sich_zu_den_wahlbereichen(bezirke, nacht):
    """Die Zusage, die `_fill_areas` bisher nur implizit gab."""
    for wb in nacht["areas"]:
        summe: collections.Counter[str] = collections.Counter()
        for z in bezirke["districts"]:
            if z["area"] != wb["number"]:
                continue
            for p in z["parties"]:
                if p["votes"]:
                    summe[p["slug"]] += p["votes"]
        for ap in wb["parties"]:
            if ap["votes"] is not None:
                assert summe[ap["slug"]] == ap["votes"], (wb["roman"], ap["slug"])


def test_die_gueltigen_stimmen_ergeben_die_stadt(bezirke, nacht):
    gesamt = sum(z["totals"]["valid_votes"] or 0 for z in bezirke["districts"])
    assert gesamt == nacht["totals"]["valid_votes"] == 250816


def test_der_anteil_rechnet_gegen_die_gueltigen_stimmen_des_bezirks(bezirke):
    z = next(x for x in bezirke["districts"] if x["number"] == 101)
    gueltig = z["totals"]["valid_votes"]
    for p in z["parties"]:
        if p["votes"] and gueltig:
            assert p["share_pct"] == round(100 * p["votes"] / gueltig, 2)


def test_personenstimmen_stehen_nicht_drin(bezirke):
    """133 × 383 Zahlen beantworten keine Frage, die jemand hat — und sie
    wären die größte Antwort, die dieses Backend ausliefert."""
    z = bezirke["districts"][0]
    assert set(z["parties"][0]) == {"slug", "votes", "share_pct"}


def test_der_endpunkt_kennt_rueckblick_und_schalter(monkeypatch):
    d = router.wahlabend_wahlbezirke(probe=None, counted=None, wahl="ratswahl-2026")
    assert d["dataset"] == "archive" and d["total"] == 133
    with pytest.raises(HTTPException) as e:
        router.wahlabend_wahlbezirke(probe=None, counted=None, wahl="gibt-es-nicht")
    assert e.value.status_code == 404
    monkeypatch.setenv("FEATURE_FLAGS", "")
    with pytest.raises(HTTPException) as e:
        router.wahlabend_wahlbezirke(probe=None, counted=None, wahl="ratswahl-2026")
    assert e.value.status_code == 404


def test_die_generalprobe_zeigt_denselben_ausschnitt():
    """``?probe=1&counted=60`` — dieselben 60 Bezirke, die auch die Tafel
    zeigt; der Rest steht auf „noch nicht gezählt"."""
    d = router.wahlabend_wahlbezirke(probe="1", counted=60, wahl=None)
    assert d["dataset"] == "probe"
    assert d["counted"] == 60 < d["total"]
    assert d["phase"] == "counting"


# ---------------------------------------------------------------- Rangliste je Liste (15.09.2026)

def test_die_rangliste_einer_liste_ist_nach_anteil_sortiert_und_kennt_die_briefwahl(bezirke):
    """Tims Bekannter (FDP): „Wo hat meine Liste in den Wahllokalen der Stadt
    wie gut abgeschnitten?" — der Server sortiert und vergibt den Rang."""
    from app.election import service

    reg = service.load_register()
    r = service.district_ranking(bezirke, reg, "fdp", "share")
    assert r["party"] == "fdp" and r["sort"] == "share" and r["area"] is None
    assert r["total"] == 133 and r["counted"] == 133
    anteile = [z["share_pct"] for z in r["rows"]]
    assert anteile == sorted(anteile, reverse=True)
    assert [z["rank"] for z in r["rows"]] == list(range(1, 134))
    # Die Briefwahl steht dazwischen — und trägt ihren Wahlbereich ausdrücklich.
    brief = [z for z in r["rows"] if z["postal"]]
    assert len(brief) == 42
    b921 = next(z for z in brief if z["number"] == 921)
    assert b921["area"] == 2 and b921["area_roman"] == "II"
    assert all(z["area"] == (z["number"] - 900) // 10 for z in brief)


def test_die_rangliste_nach_stimmen_und_je_wahlbereich(bezirke):
    from app.election import service

    reg = service.load_register()
    r = service.district_ranking(bezirke, reg, "spd", "votes", area=4)
    assert r["area"] == 4 and all(z["area"] == 4 for z in r["rows"])
    assert r["total"] == 17 + 7, "Wahlbereich IV: 17 Urnen- und 7 Briefwahlbezirke"
    stimmen = [z["votes"] for z in r["rows"]]
    assert stimmen == sorted(stimmen, reverse=True)
    assert r["rows"][0]["rank"] == 1


def test_ungezaehlte_bezirke_stehen_hinten_ohne_rang():
    from app.election import service

    reg = service.load_register()
    liste = service.districts(reg, service.probe_snapshot(reg, service.load_reference(), 40), "probe")
    r = service.district_ranking(liste, reg, "gruene", "share")
    assert r["counted"] == 40 and r["total"] == 133
    assert [z["rank"] for z in r["rows"][:40]] == list(range(1, 41))
    assert all(z["rank"] is None and not z["counted"] for z in r["rows"][40:])
    nummern_offen = [z["number"] for z in r["rows"][40:]]
    assert nummern_offen == sorted(nummern_offen)


def test_der_rangliste_endpunkt_kennt_die_liste_oder_sagt_404(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    d = router.wahlabend_wahlbezirke_rangliste(party="volt", sort="share", area=None, probe="1", counted=60, wahl=None)
    assert d["party"] == "volt" and d["counted"] == 60
    with pytest.raises(HTTPException) as e:
        router.wahlabend_wahlbezirke_rangliste(party="gibt-es-nicht", sort="share", area=None, probe="1", counted=60, wahl=None)
    assert e.value.status_code == 404
