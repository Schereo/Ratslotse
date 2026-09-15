"""Die Wahlbezirke der Stichwahl (``mayor_districts``, ``/api/wahlabend/stichwahl/bezirke``).

PR S1 aus ``docs/plan-stichwahl-spannung.md``. Die Zusagen, gegen drei
eingefrorene Übersichten gehalten — ohne Netz:

- ``kommunalwahl/referenz-2026/praesentation-ob-wahlbezirke.json``: der erste
  Wahlgang 2026, 133 Bezirke, Stadtzeile 28.075 Prange / 25.850 Rohr
  (``praesentation-ob.json``).
- ``tests/fixtures/wahlabend/stichwahl-2021/``: erster Wahlgang und Stichwahl
  2021 (alte API) — dieselbe Form, fünf Jahre älter. Sie sind die
  Kalibrierung des Modells in PR S2; hier zählt nur, dass sie sich lesen
  lassen.

Und die Falle, die zwei Anläufe gekostet hat: ``felder`` ist um zwei kürzer
als ``header``. Der letzte Test hält sie fest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, mayor, mayor_districts  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402

REFERENZ = WURZEL / "kommunalwahl" / "referenz-2026"
FIX21 = WURZEL / "tests" / "fixtures" / "wahlabend" / "stichwahl-2021"


def _lade(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    mayor.reset()
    yield
    mayor.reset()


def test_der_erste_wahlgang_2026_je_bezirk_summiert_sich_zur_stadtzeile():
    bezirke = mayor_districts.parse_overview(
        _lade(REFERENZ / "praesentation-ob-wahlbezirke.json"), {"prange": "Ulf Prange", "rohr": "Jascha Rohr"})
    assert len(bezirke) == 133
    assert sum(1 for d in bezirke if d.postal) == 42
    assert all(d.counted for d in bezirke)
    stadt = _lade(REFERENZ / "praesentation-ob.json")["Komponente"]["tabelle"]["zeilen"]
    stadtzeile = {}
    for z in stadt:
        label = z["label"]["labelKurz"] if isinstance(z.get("label"), dict) else str(z.get("label"))
        stadtzeile[label.split(",")[0]] = int(str(z["zahl"]).replace(".", ""))
    assert sum(d.votes["prange"] or 0 for d in bezirke) == stadtzeile["Prange"] == 28075
    assert sum(d.votes["rohr"] or 0 for d in bezirke) == stadtzeile["Rohr"] == 25850


def test_jeder_bezirk_kennt_wahlbereich_und_wahlberechtigte():
    bezirke = mayor_districts.parse_overview(
        _lade(REFERENZ / "praesentation-ob-wahlbezirke.json"), {"prange": "", "rohr": ""})
    for d in bezirke:
        erwartet = (d.number - 900) // 10 if d.postal else d.number // 100
        assert d.area == erwartet, d.number
        assert d.valid_votes and d.valid_votes > 0, d.number
        assert d.name and not d.name[0].isdigit(), d.name
        if d.postal:
            # Gemessen: Die Stadt führt für Briefwahlbezirke KEINE
            # Wahlberechtigten — die zählen in ihrem Urnenbezirk. Für das
            # Modell heißt das: Die Obergrenze der offenen Stimmen kommt für
            # die Briefwahl nicht aus den Wahlberechtigten.
            assert d.eligible == 0, d.number
        else:
            assert d.eligible and d.eligible > 0, d.number
    # Sortiert nach Nummer — die Reihenfolge ist Teil der Antwort.
    nummern = [d.number for d in bezirke]
    assert nummern == sorted(nummern)


def test_die_stichwahl_2021_liest_sich_genauso():
    """Alte API, gleiche Form: Krogmann gegen Fuhrhop, 133 Bezirke."""
    erster = mayor_districts.parse_overview(_lade(FIX21 / "uebersicht-223-erster-wahlgang.json"),
                                            {"krogmann": "", "fuhrhop": ""})
    stich = mayor_districts.parse_overview(_lade(FIX21 / "uebersicht-224-stichwahl.json"),
                                           {"krogmann": "", "fuhrhop": ""})
    assert len(erster) == len(stich) == 133
    assert {d.number for d in erster} == {d.number for d in stich}
    assert sum(d.votes["krogmann"] or 0 for d in stich) == 43493
    assert sum(d.votes["fuhrhop"] or 0 for d in stich) == 36949
    # Erster Wahlgang: nur die zwei gewünschten Spalten, obwohl neun da sind.
    assert set(erster[0].votes) == {"krogmann", "fuhrhop"}


def test_ein_nicht_gemeldeter_bezirk_traegt_keine_stimmen():
    """Vor der Meldung steht in der Übersicht schon die Zeile — mit leeren
    Zahlen. Der Parser darf daraus keine Null machen."""
    roh = _lade(REFERENZ / "praesentation-ob-wahlbezirke.json")
    zeile = next(z for z in roh["tabelle"]["zeilen"] if str(z["label"]).startswith("101"))
    zeile["statusString"] = "ausstehend"
    zeile["statusProzent"] = 0
    bezirke = mayor_districts.parse_overview(roh, {"prange": "", "rohr": ""})
    b101 = next(d for d in bezirke if d.number == 101)
    assert b101.counted is False
    assert b101.votes == {"prange": None, "rohr": None}
    assert b101.valid_votes is None
    # Die Wahlberechtigten stehen trotzdem da — sie sind die Obergrenze der
    # offenen Stimmen, und die braucht das Modell VOR der Meldung.
    assert b101.eligible == 1419


def test_die_generalprobe_meldet_die_ersten_n_bezirke():
    w = elections.runoff()
    assert w is not None
    stand = mayor.probe(20, w)
    assert len(stand.districts) == 133
    assert sum(1 for d in stand.districts if d.counted) == 20
    offen = [d for d in stand.districts if not d.counted]
    assert all(d.votes == {"prange": None, "rohr": None} for d in offen)
    assert all(d.eligible for d in offen if not d.postal), "Wahlberechtigte bleiben auch offen bekannt"
    voll = mayor.probe(133, w)
    assert all(d.counted for d in voll.districts)
    # Der erste Wahlgang (ob-2026) probt gegen 2021 — ohne Bezirke.
    assert mayor.probe(60, elections.get("ob-2026")).districts == ()


def test_der_endpunkt_liefert_bezirke_mit_erstem_wahlgang():
    d = router.stichwahl_bezirke(probe="1", counted=60)
    assert d["dataset"] == "probe" and d["total"] == 133 and d["counted"] == 60
    assert d["election"]["slug"] == "ob-stichwahl-2026" and d["election"]["is_runoff"]
    z = d["districts"][0]
    assert set(z) >= {"number", "name", "area", "postal", "counted", "eligible", "votes", "first_round"}
    # Jeder Bezirk trägt seinen ersten Wahlgang — auch die noch offenen.
    for z in d["districts"]:
        assert z["first_round"]["prange"] and z["first_round"]["rohr"], z["number"]
    offen = next(z for z in d["districts"] if not z["counted"])
    assert offen["votes"] == {"prange": None, "rohr": None}


def test_ohne_schalter_gibt_es_nichts(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "")
    with pytest.raises(HTTPException) as e:
        router.stichwahl_bezirke(probe="1", counted=None)
    assert e.value.status_code == 404


def test_felder_sind_um_zwei_kuerzer_als_der_kopf():
    """Die Falle, festgehalten: Wer ``felder[i − 1]`` liest, liest die
    Wahlberechtigten als Wahlbeteiligung."""
    roh = _lade(REFERENZ / "praesentation-ob-wahlbezirke.json")
    zeile = next(z for z in roh["tabelle"]["zeilen"] if str(z["label"])[:1].isdigit())
    assert len(roh["tabelle"]["header"]) - len(zeile["felder"]) == mayor_districts.FELD_VERSATZ == 2
    assert [h["labelKurz"] for h in roh["tabelle"]["header"][:2]] == ["Wahlbezirk", "Stand"]
