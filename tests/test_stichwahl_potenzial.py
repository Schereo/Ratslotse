"""Das Potenzial-Modell der Stichwahl (``web/backend/app/election/potential.py``)
und sein Endpunkt hinter dem Token.

Die Zahlen hier sind die aus ``docs/plan-stichwahl-potenzial.md``. Fällt ein
Test, stimmt der Plan nicht mehr — dann ist der Plan zu korrigieren, nicht
der Test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import potential  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(scope="module")
def vorgabe():
    return potential.compute()


def test_die_ausgangslage_2026(vorgabe):
    p = vorgabe
    assert p["rohr"] == 25850 and p["prange"] == 28075 and p["lead"] == 2225
    assert p["pool"] == 10198 + 4945 + 6211 + 4025 + 3843
    assert p["cdu_council"] == 37430
    assert len(p["districts"]) == 133
    assert all(z["eligible"] > 0 for z in p["districts"] if not z["postal"])
    assert all(z["non_voters"] == 0 and z["strategy"] == "postal" for z in p["districts"] if z["postal"])
    assert sum(z["non_voters"] for z in p["districts"]) == p["non_voters"] == 76873


def test_die_briefwahl_ist_rohrs_bessere_haelfte(vorgabe):
    assert vorgabe["rohr_pct_postal"] > vorgabe["rohr_pct_urn"] + 4
    assert vorgabe["rohr_pct_urn"] == 46.3 and vorgabe["rohr_pct_postal"] == 51.1


def test_null_heisst_null_und_die_regler_wirken_linear():
    null = potential.compute(potential.Regler(transfers={s: (0, 0) for s in potential.VORGABE}, cdu=(0, 0)))
    assert null["net_total"] == 0 and null["balance"] == -null["lead"]
    nur_linke = potential.compute(potential.Regler(
        transfers={**{s: (0, 0) for s in potential.VORGABE}, "boldt": (100, 0)}, cdu=(0, 0)))
    assert nur_linke["net_total"] == 10198
    # Beteiligung: 90 % der Rohr-Basis kostet ein Zehntel seiner Stimmen —
    # bis auf die Rundung je Bezirk (133 × höchstens eine halbe Stimme).
    weniger = potential.compute(potential.Regler(transfers={s: (0, 0) for s in potential.VORGABE}, cdu=(0, 0), turnout_rohr=90))
    assert abs(weniger["balance"] - (-weniger["lead"] - 2585)) <= 67


def test_mit_den_vorgaben_steht_rohr_vorn(vorgabe):
    """Der Plan sagt „+5.211 netto, Saldo rund +3.000" — Rundung je Bezirk
    erlaubt ein paar Stimmen Abweichung, nicht mehr."""
    assert abs(vorgabe["net_total"] - 5211) <= 5
    assert 2900 <= vorgabe["balance"] <= 3050


def test_jeder_urnenbezirk_hat_einen_ort_und_eine_strategie(vorgabe):
    urne = [z for z in vorgabe["districts"] if not z["postal"]]
    assert all(z["district_name"] != "Briefwahl" for z in urne)
    assert {z["strategy"] for z in urne} <= {"hold", "persuade", "both", "skip"}
    # Die Hochburg mit großem Pool ist „both“, die Diaspora mit kleinem Ertrag „skip“.
    by = {z["number"]: z for z in urne}
    assert by[109]["strategy"] == "both", by[109]      # Friseurmeisterschule, Nadorst Süd
    assert by[501]["strategy"] == "skip", by[501]  # Caritas, Bümmerstede
    assert sum(vorgabe["strategy_counts"].values()) == 133


def test_die_buendel_summieren_die_bezirke(vorgabe):
    b = {x["district_name"]: x for x in vorgabe["bundles"]}
    assert b["Eversten"]["districts"] == 13
    assert vorgabe["bundles"][0]["district_name"] == "Eversten"
    urne = [z for z in vorgabe["districts"] if not z["postal"]]
    assert sum(x["eligible"] for x in vorgabe["bundles"]) == sum(z["eligible"] for z in urne)


def test_2021_ist_gemessen_und_gewarnt(vorgabe):
    l = vorgabe["lessons_2021"]
    assert l["voters_first"] == 72765 and l["voters_runoff"] == 81472
    assert l["fuhrhop_growth_by_fifth"][0] > l["fuhrhop_growth_by_fifth"][-1] > 1.5
    assert l["fuhrhop_pct_postal_runoff"] > l["fuhrhop_pct_urn_runoff"]
    assert "Bundestagswahl" in l["note"]
    assert any("Bundestagswahl" in c for c in vorgabe["caveats"])


# ---------------------------------------------------------------- der Endpunkt

def _ruf(**kw):
    args = dict(token=None, boldt=None, kuessner=None, butzin=None, froehlich=None, wilkens=None, cdu=None,
                turnout_rohr=100, turnout_prange=100, turnout_pool=100)
    args.update(kw)
    return router.stichwahl_potenzial(**args)


def test_ohne_token_gibt_es_die_seite_nicht(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.delenv("WAHLKAMPF_TOKEN", raising=False)
    with pytest.raises(HTTPException) as e:
        _ruf(token="irgendwas-langes-und-falsches")
    assert e.value.status_code == 404
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "richtig-und-lang-genug-1234")
    for falsch in (None, "", "falsch-und-lang-genug-1234"):
        with pytest.raises(HTTPException) as e:
            _ruf(token=falsch)
        assert e.value.status_code == 404
    # Ein zu kurzer Token in der .env zählt als nicht gesetzt.
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "kurz")
    with pytest.raises(HTTPException):
        _ruf(token="kurz")


def test_mit_token_kommt_die_rechnung_und_die_regler_greifen(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "richtig-und-lang-genug-1234")
    p = _ruf(token="richtig-und-lang-genug-1234")
    assert p["lead"] == 2225 and abs(p["net_total"] - 5211) <= 5
    q = _ruf(token="richtig-und-lang-genug-1234", boldt="80,5", cdu="40,10", turnout_prange=95)
    assert q["assumptions"][0]["to_rohr"] == 80 and q["cdu_to_rohr"] == 40 and q["turnout_prange"] == 95
    assert q["balance"] > p["balance"]
    with pytest.raises(HTTPException) as e:
        _ruf(token="richtig-und-lang-genug-1234", boldt="70,40")
    assert e.value.status_code == 422
