"""Stimmen die Zahlen? Die Generalprobe gegen die amtliche Präsentation 2021.

Die Sitzzuteilung ist in ``test_wahlabend.py`` gegen die amtlichen 50 Mandate
geprüft. Hier geht es um alles, was die Seite SONST zeigt: Stimmenanteile,
Wahlbeteiligung, die Summen je Wahlbereich. Referenz sind die Prozentwerte
aus der Ergebnispräsentation des Votemanagers 2021 (Stadt-Ebene und
Wahlbereich I), von Hand aus dem JSON abgeschrieben — nicht aus unseren
eigenen CSV-Kopien gerechnet, sonst prüfte die Rechnung sich selbst.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import reference, register, service  # noqa: E402

#: Stadt Oldenburg, Stadtratswahl 12.09.2021 — „Summe Partei- und
#: Kandidaten-Stimmen" je Liste und Prozent der gültigen Stimmen (210.447).
AMTLICH_STADT = {
    "spd": (61032, 29.00),
    "cdu": (37430, 17.79),
    "gruene": (65641, 31.19),
    "linke": (16750, 7.96),
    "fdp": (11169, 5.31),
    "afd": (5727, 2.72),
    "fuer-oldenburg": (1838, 0.87),
    "piraten": (2890, 1.37),
    "volt": (5537, 2.63),
}
AMTLICH_GUELTIGE_STIMMEN = 210447
AMTLICH_WAHLBERECHTIGTE = 135173
AMTLICH_WAEHLER = 72723
AMTLICH_BETEILIGUNG = 53.80
#: Wahlbereich I – Stadtmitte Nord: 35.859 gültige Stimmen.
AMTLICH_WB1 = {"spd": (8993, 25.08), "cdu": (4713, 13.14), "gruene": (13626, 38.00), "linke": (3627, 10.11)}


def _voll():
    reg, ref = register.load(), reference.load()
    return service.compose(reg, ref, service.probe_snapshot(reg, ref, None), "probe")


def test_stimmenanteile_stadtweit_wie_amtlich():
    d = _voll()
    assert d["totals"]["valid_votes"] == AMTLICH_GUELTIGE_STIMMEN
    parteien = {p["slug"]: p for p in d["parties"]}
    for slug, (stimmen, prozent) in AMTLICH_STADT.items():
        assert parteien[slug]["votes"] == stimmen, slug
        assert abs((parteien[slug]["share_pct"] or 0) - prozent) <= 0.01, (slug, parteien[slug]["share_pct"], prozent)


def test_wahlbeteiligung_wie_amtlich():
    d = _voll()
    assert d["totals"]["eligible"] == AMTLICH_WAHLBERECHTIGTE
    assert d["totals"]["voters"] == AMTLICH_WAEHLER
    assert abs((d["totals"]["turnout_pct"] or 0) - AMTLICH_BETEILIGUNG) <= 0.01


def test_wahlbereich_eins_wie_amtlich():
    d = _voll()
    wb1 = next(a for a in d["areas"] if a["number"] == 1)
    assert wb1["totals"]["valid_votes"] == 35859
    parteien = {p["slug"]: p for p in wb1["parties"]}
    for slug, (stimmen, prozent) in AMTLICH_WB1.items():
        assert parteien[slug]["votes"] == stimmen, slug
        assert abs((parteien[slug]["share_pct"] or 0) - prozent) <= 0.01, slug


def test_summen_schliessen():
    """Die Wahlbereiche summieren sich zur Stadt; Liste + Personen = Gesamt."""
    d = _voll()
    for p in d["parties"]:
        je_wb = [ap for a in d["areas"] for ap in a["parties"] if ap["slug"] == p["slug"] and ap["votes"] is not None]
        if p["votes"] is not None and je_wb:
            assert sum(ap["votes"] for ap in je_wb) == p["votes"], p["slug"]
        for ap in je_wb:
            if ap["list_votes"] is not None and ap["candidate_votes"] is not None:
                assert ap["list_votes"] + ap["candidate_votes"] == ap["votes"], (p["slug"], ap)
                assert sum(k["votes"] or 0 for k in ap["candidates"]) == ap["candidate_votes"], (p["slug"], ap["votes"])
    assert sum(p["seats"] or 0 for p in d["parties"]) == d["election"]["seats"]
    assert sum(a["districts_total"] for a in d["areas"]) == d["progress"]["districts_total"] == 133
