"""Wie wir uns bei fremden Städten benehmen — als Wächter, nicht als Vorsatz.

Beide Regeln standen schon als Prosa im Modul-Docstring, und beide waren
trotzdem verletzt: Der Abstand durfte auf 0,2 s heruntergedreht werden, und
die „Kontaktadresse" war ein Verweis aufs Impressum statt einer Adresse.

Gemessen an Hildesheim am 11.09.2026: **5.369 Abrufe an einem Tag**, in der
Spitze 123 je Minute. Zwei Tage später stand vor demselben System eine
Sperre gegen automatisierte Zugriffe.
"""
from __future__ import annotations

import importlib

import pytest

from council.cities import oparl


def test_der_abstand_laesst_sich_nicht_unter_eine_sekunde_drehen(monkeypatch):
    """`CITIES_RATE_SECONDS` darf bremsen, nie beschleunigen."""
    monkeypatch.setenv("CITIES_RATE_SECONDS", "0.05")
    neu = importlib.reload(oparl)
    try:
        assert neu.RATE_SECONDS >= 1.0, (
            "Die Umgebung kann den Abstand wieder unterschreiten — genau so "
            "sind aus einer Zusage von 1/s gemessene 2/s geworden.")
    finally:
        monkeypatch.delenv("CITIES_RATE_SECONDS", raising=False)
        importlib.reload(oparl)


def test_langsamer_geht_weiter(monkeypatch):
    """Ein vorsichtiger Lauf muss möglich bleiben, sonst ist die Schranke
    eine Sperre statt eines Bodens."""
    monkeypatch.setenv("CITIES_RATE_SECONDS", "5")
    neu = importlib.reload(oparl)
    try:
        assert neu.RATE_SECONDS == 5.0
    finally:
        monkeypatch.delenv("CITIES_RATE_SECONDS", raising=False)
        importlib.reload(oparl)


@pytest.mark.parametrize("teil", ["Ratslotse", "https://ratslotse.de",
                                  "https://ratslotse.de/impressum"])
def test_wir_sagen_wer_wir_sind_und_wo_wir_erreichbar_sind(teil):
    """Name, Zweck und eine Adresse, die man aus der Logzeile heraus
    anklicken kann — kein Verweis, dem erst jemand folgen muss."""
    assert teil in oparl.USER_AGENT


def test_wir_geben_uns_nicht_als_browser_aus():
    """Die Kennung ist keine Tarnung.

    Ein `Mozilla/5.0` vor einem fremden Ratsinformationssystem wäre die
    Behauptung, hier sitze ein Mensch. Wer gesperrt wird, wurde erkannt —
    und das ist in Ordnung so.
    """
    assert "Mozilla" not in oparl.USER_AGENT
    assert "Staedtevergleich" in oparl.USER_AGENT
