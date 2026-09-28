"""Kaufmännisch runden (``election.rounding``) — Anlass: Am Abend der
Stichwahl (27.09.2026) stand auf Seite und Teilbild „Rohr 51,5 %", amtlich
waren es 51,55 %. Als Gleitkommazahl ist 51,55 aber 51,5499…, und
``f"{x:.1f}"`` rundet die."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive, quiz_questions, rounding, runoff_image, share  # noqa: E402


@pytest.mark.parametrize(("value", "expected"), [
    (51.55, 51.6), (48.45, 48.5), (30.54, 30.5), (33.16, 33.2), (0.05, 0.1), (-2.25, -2.3),
])
def test_half_up(value, expected):
    assert rounding.half_up(value) == expected


def test_differenzen_tragen_rauschen():
    """13,45 − 10,3 ist als Gleitkommazahl 3,1499…986 — gemeint ist 3,15."""
    assert rounding.half_up(13.45 - 10.3) == 3.2
    assert rounding.half_up(51.55 - 30.5) == 21.1


def test_f_string_rundet_anders():
    """Der Grund für das Modul: Das hier ist die Falle, nicht der Fix."""
    assert f"{51.55:.1f}" == "51.5"


def test_pct_text():
    assert rounding.pct_text(51.55) == "51,6 %"
    assert rounding.pct_text(None) == "–"
    assert rounding.pct_text(31.225, 2) == "31,23 %"


def test_teilbilder_nehmen_denselben_weg():
    assert runoff_image._pct(51.55) == "51,6 %"
    assert share._pct(51.55) == "51,6 %"


def test_alle_wege_der_wahlseiten_runden_gleich():
    assert archive._eine_stelle(51.55) == 51.6
    assert quiz_questions._pct(51.55) == "51,6 %"
    assert share._signed(3.15) == "+3,2"
