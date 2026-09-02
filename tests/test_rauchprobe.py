"""Die Rauchprobe nach dem Deploy — Prüfer und Probenliste.

Der Netzteil wird hier nicht angefasst: Was zählt, ist, dass die Prüfung eine
kaputte Form erkennt und dass die Probenliste auf Endpunkte zeigt, die ohne
Konto erreichbar sind. Eine Probe, die 401 bekommt, prüft nichts — sie meldet
nur jedes Mal denselben Fehler, bis jemand sie abschaltet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.rauchprobe import ABGELEITET, PROBEN, VERTRAG, Vertrag  # noqa: E402
from tests.test_endpunkt_schutz import OEFFENTLICH  # noqa: E402

SPEC = json.loads(VERTRAG.read_text())
PRUEFER = Vertrag(SPEC)


def _alle_muster() -> list[str]:
    return [*PROBEN, *(muster for muster, _, _ in ABGELEITET)]


@pytest.mark.parametrize("pfad", _alle_muster())
def test_jede_probe_zeigt_auf_einen_endpunkt_ohne_konto(pfad):
    assert pfad in SPEC["paths"], f"{pfad} steht nicht im Vertrag"
    assert "get" in SPEC["paths"][pfad], f"{pfad} ist kein GET"
    assert ("get", pfad) in OEFFENTLICH, (
        f"{pfad} verlangt ein Konto — die Rauchprobe hat keins und bekäme "
        "jedes Mal 401."
    )


@pytest.mark.parametrize("pfad", _alle_muster())
def test_jede_probe_hat_eine_antwortform(pfad):
    assert PRUEFER.antwortschema(pfad) is not None, (
        f"{pfad} beschreibt seine Antwort nicht — dann prüft die Probe nur, "
        "dass überhaupt etwas kommt."
    )


SCHEMA = {
    "type": "object",
    "required": ["id", "titel"],
    "properties": {
        "id": {"type": "integer"},
        "titel": {"type": "string"},
        "notiz": {"type": ["string", "null"]},
        "zeilen": {"type": "array", "items": {"type": "object",
                                              "required": ["n"],
                                              "properties": {"n": {"type": "integer"}}}},
    },
}


def test_gute_form_geht_durch():
    gut = {"id": 1, "titel": "x", "notiz": None, "zeilen": [{"n": 2}]}
    assert PRUEFER.pruefe(gut, SCHEMA) == []


@pytest.mark.parametrize("kaputt, erwartet", [
    ({"id": "1", "titel": "x"}, "erwartet integer"),
    ({"id": 1}, "fehlt"),
    ({"id": 1, "titel": None}, "null"),
    ({"id": 1, "titel": "x", "zeilen": [{"m": 2}]}, "fehlt"),
    ({"id": 1, "titel": "x", "zeilen": {"n": 2}}, "erwartet array"),
])
def test_kaputte_form_faellt_auf(kaputt, erwartet):
    fehler = PRUEFER.pruefe(kaputt, SCHEMA)
    assert fehler, f"{kaputt} kam durch"
    assert any(erwartet in f for f in fehler), fehler


def test_wahrheitswert_geht_nicht_als_zahl_durch():
    """`True` ist in Python ein `int` — ohne Ausnahme rutscht es durch."""
    assert PRUEFER.pruefe({"id": True, "titel": "x"}, SCHEMA)
