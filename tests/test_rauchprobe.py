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

from scripts.rauchprobe import (ABGELEITET, MIT_KONTO, PROBEN,  # noqa: E402
                                VERTRAG, Vertrag)
from tests.test_endpunkt_schutz import OEFFENTLICH  # noqa: E402

SPEC = json.loads(VERTRAG.read_text())
PRUEFER = Vertrag(SPEC)


def _ohne_konto() -> list[str]:
    return [*PROBEN, *(muster for muster, _, _ in ABGELEITET)]


def _alle_muster() -> list[str]:
    return [*_ohne_konto(), *MIT_KONTO]


@pytest.mark.parametrize("pfad", _ohne_konto())
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


@pytest.mark.parametrize("pfad", _alle_muster())
def test_keine_probe_braucht_einen_pflichtparameter(pfad):
    """Sonst meldet sie für immer 422 und prüft nichts.

    Beim Bauen genau einmal passiert: ``/api/council/budget/products`` verlangt
    ein Jahr in der Abfrage. Die Probe lief, war rot, und das hätte jeden
    Deploy blockiert — ohne dass irgendetwas kaputt gewesen wäre.
    """
    pflicht = [
        prm["name"]
        for prm in SPEC["paths"][pfad]["get"].get("parameters", [])
        if prm.get("required") and prm.get("in") == "query"
    ]
    assert not pflicht, (
        f"{pfad} verlangt {pflicht} in der Abfrage. Entweder einen Wert "
        "mitgeben (dann gehört der Pfad zu ABGELEITET) oder die Probe "
        "streichen."
    )


@pytest.mark.parametrize("pfad", MIT_KONTO)
def test_probe_mit_konto_ist_kein_admin_endpunkt(pfad):
    """Die Probe meldet sich mit einem echten Konto an — meist dem des Admins.

    Damit KÖNNTE sie auch die Admin-Fläche abrufen. Sie soll es nicht: Das ist
    eine andere Risikoklasse (dort hängen Freischaltungen und Löschungen), und
    ein Deploy ist kein Anlass, sie anzufassen.
    """
    assert not pfad.startswith("/api/admin"), pfad


#: Was die Probe mit Konto NICHT anfassen darf. Persönliches, weil die Antwort
#: dann von einem echten Menschen abhängt; Schreibendes und Teures, weil ein
#: Deploy weder eine Quizrunde anlegen noch ein Sprachmodell rufen soll.
VERBOTEN = (
    "/api/account", "/api/badges", "/api/bookmarks", "/api/onboarding",
    "/api/subscriptions", "/api/topics", "/api/council/conversations",
    "/api/council/follows", "/api/council/deep-research",
    "/api/quiz/own", "/api/quiz/round", "/api/quiz/daily", "/api/quiz/review",
    "/api/quiz/stats", "/api/quiz/map-round",
)


@pytest.mark.parametrize("pfad", MIT_KONTO)
def test_probe_mit_konto_fasst_nichts_persoenliches_an(pfad):
    treffer = [v for v in VERBOTEN if pfad.startswith(v)]
    assert not treffer, (
        f"{pfad} fällt unter {treffer[0]} — persönlich, schreibend oder teuer. "
        "Die Rauchprobe prüft die Fläche, die für alle gleich aussieht."
    )


@pytest.mark.parametrize("pfad", MIT_KONTO)
def test_probe_mit_konto_braucht_wirklich_ein_konto(pfad):
    """Ein öffentlicher Pfad gehört in die andere Liste — dort läuft er ohne
    Anmeldung und prüft damit auch, dass sie nicht nötig ist."""
    assert ("get", pfad) not in OEFFENTLICH, (
        f"{pfad} geht ohne Konto und gehört nach PROBEN."
    )
