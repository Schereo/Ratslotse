"""Die Zahlenprüfung der Lotti-Eval (``eval/run_assistant.py::erfundene_zahlen``).

Sie ist der härteste Befund der Eval — „Zahl steht nicht im Kontext“ — und
war in P4a (23.09.2026) zweimal selbst der Fehler: Sie bestrafte die
Alltagsform, die der Prompt verlangt („rund 1.900 Euro“ für 1.908 €). Die
Tests halten fest, dass Runden erlaubt ist und Erfinden nicht.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.run_assistant import erfundene_zahlen  # noqa: E402

KONTEXT = ("Schuldenstand am Jahresende 2025: 336.994.000 € — das sind 1.908 € je "
           "Einwohner*in. Aufwendungen 5.005 € je Einwohner*in, Erträge 4.602 € je "
           "Einwohner*in. Reihe seit 1995.")


def test_gerundete_betraege_sind_belegt():
    assert erfundene_zahlen("rund 1.900 Euro je Einwohner*in", KONTEXT) == []
    assert erfundene_zahlen("rund 5.000 Euro je Kopf", KONTEXT) == []
    assert erfundene_zahlen("rund 337 Millionen Euro", KONTEXT) == []
    assert erfundene_zahlen("genau 1.908 €", KONTEXT) == []


def test_erfundene_und_gerechnete_betraege_bleiben_befunde():
    # Steuerkraft je Kopf, selbst gerechnet — steht nirgends (keine-erfundene-zahl).
    assert erfundene_zahlen("rund 1.970 Euro", KONTEXT) == ["1.970 Euro"]
    # Zu grob: 2.000 liegt 4,8 % neben 1.908, und „1995“ ist ein Jahr, kein Beleg.
    assert erfundene_zahlen("rund 2.000 Euro", KONTEXT) == ["2.000 Euro"]
    # 5.000 ist keine Rundung von 4.602 (8,6 % daneben) — belegt ist es nur
    # über 5.005.
    assert erfundene_zahlen("rund 5.000 Euro", "Erträge 4.602 € je Einwohner*in") == ["5.000 Euro"]
    # Eine Hochrechnung bleibt erfunden.
    assert erfundene_zahlen("rund 421 Millionen Euro", KONTEXT) == ["421 Millionen"]
