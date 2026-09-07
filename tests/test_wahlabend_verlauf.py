"""Der Verlauf des Wahlabends: Punkte sammeln, entdoppeln, überleben.

Der Votemanager kennt nur den jetzigen Stand. Was der Dienst über den Abend
selbst mitschreibt (``web/backend/app/election/history.py``), muss deshalb
drei Dinge können: sich nicht wiederholen (ein Abend hat keine 600 gleichen
Punkte), einen Neustart überstehen (ein Deploy mitten im Abend) und einen
kaputten Pfad aushalten, ohne den Endpunkt mitzureißen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import history, reference, register, service, votemanager  # noqa: E402
from app.antworten import ElectionHistoryPoint  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures" / "wahlabend"
SCHLUESSEL = {"at", "districts_counted", "shares", "seats"}


def _punkt(at: str, counted: int = 10, shares: dict[str, float] | None = None,
           seats: dict[str, int] | None = None) -> ElectionHistoryPoint:
    return ElectionHistoryPoint(
        at=at, districts_counted=counted,
        shares={"spd": 24.5} if shares is None else shares,
        seats={"spd": 12} if seats is None else seats,
    )


@pytest.fixture
def datei(tmp_path, monkeypatch) -> Path:
    """Ein eigener Verlauf je Test — geladen wird beim ersten Zugriff."""
    ziel = tmp_path / "verlauf.json"
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(ziel))
    history.reset()
    yield ziel
    history.reset()


# ------------------------------------------------------------------ Sammeln

def test_gleicher_stand_haengt_keinen_zweiten_punkt_an(datei):
    """Alle 60 Sekunden dasselbe Bild ist ein Punkt, nicht sechshundert. Die
    Uhrzeit allein macht keinen neuen Stand — Auszählung, Anteile und Sitze
    tun es, jedes für sich."""
    assert history.add(_punkt("2026-09-13T16:00:00+00:00")) == [_punkt("2026-09-13T16:00:00+00:00")]
    assert len(history.add(_punkt("2026-09-13T16:01:00+00:00"))) == 1
    assert len(history.add(_punkt("2026-09-13T16:02:00+00:00", counted=11))) == 2
    assert len(history.add(_punkt("2026-09-13T16:03:00+00:00", counted=11, shares={"spd": 24.6}))) == 3
    assert len(history.add(_punkt("2026-09-13T16:04:00+00:00", counted=11, shares={"spd": 24.6},
                                  seats={"spd": 13}))) == 4
    assert [p["at"] for p in history.points()][-1] == "2026-09-13T16:04:00+00:00"


def test_obergrenze_wirft_die_aeltesten_raus(datei, monkeypatch):
    assert history.MAX_POINTS == 1_440, "ein Abend ist keine 24 Stunden lang"
    monkeypatch.setattr(history, "MAX_POINTS", 5)
    for n in range(8):
        history.add(_punkt(f"2026-09-13T16:{n:02d}:00+00:00", counted=n))
    punkte = history.points()
    assert [p["districts_counted"] for p in punkte] == [3, 4, 5, 6, 7]
    # Und die gekappte Liste ist auch die, die in der Datei steht.
    assert [p["districts_counted"] for p in json.loads(datei.read_text(encoding="utf-8"))] == [3, 4, 5, 6, 7]


# ------------------------------------------------------------------ Datei

def test_verlauf_uebersteht_den_neustart(datei):
    """Ein Deploy mitten im Abend startet den Dienst neu — der Verlauf darf
    dabei nicht verschwinden. Das Verzeichnis legt der Schreiber selbst an."""
    assert not datei.parent.joinpath("gibtsnicht").exists()
    history.add(_punkt("2026-09-13T16:00:00+00:00", counted=10))
    history.add(_punkt("2026-09-13T16:15:00+00:00", counted=20, seats={"spd": 12, "gruene": 14}))
    vorher = history.points()
    assert datei.exists()

    history.reset()  # so kalt wie ein frisch gestarteter Dienst
    assert history.points() == vorher
    assert [p["districts_counted"] for p in history.points()] == [10, 20]
    # Ein gleicher Punkt nach dem Neustart hängt nichts an.
    assert len(history.add(_punkt("2026-09-13T16:20:00+00:00", counted=20,
                                  seats={"spd": 12, "gruene": 14}))) == 2


def test_fehlendes_verzeichnis_wird_angelegt(tmp_path, monkeypatch):
    ziel = tmp_path / "tief" / "drin" / "verlauf.json"
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(ziel))
    history.reset()
    history.add(_punkt("2026-09-13T16:00:00+00:00"))
    assert json.loads(ziel.read_text(encoding="utf-8"))[0]["districts_counted"] == 10
    history.reset()


def test_unschreibbarer_pfad_macht_nichts_kaputt(tmp_path, monkeypatch):
    """Ein kaputter Pfad ist ein Log-Eintrag, kein 500er: Der Abend läuft im
    Speicher weiter."""
    sperre = tmp_path / "keinverzeichnis"
    sperre.write_text("ich bin eine Datei", encoding="utf-8")
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(sperre / "verlauf.json"))
    history.reset()
    assert history.points() == []
    assert len(history.add(_punkt("2026-09-13T16:00:00+00:00", counted=10))) == 1
    assert len(history.add(_punkt("2026-09-13T16:15:00+00:00", counted=20))) == 2
    assert [p["districts_counted"] for p in history.points()] == [10, 20]
    history.reset()


def test_kaputte_datei_beginnt_von_vorn(datei):
    datei.write_text("{kein json", encoding="utf-8")
    history.reset()
    assert history.points() == []
    assert len(history.add(_punkt("2026-09-13T16:00:00+00:00"))) == 1


# ------------------------------------------------------------------ Live-Bild

def test_punkt_aus_dem_fertigen_bild(datei):
    """Anteile nur für Listen mit Stimmen, Sitze nur für Listen mit Sitzen."""
    night = service.probe(40)
    punkt = history.from_night(night)
    assert set(punkt) == SCHLUESSEL
    assert punkt["at"] == night["computed_at"] and punkt["districts_counted"] == 40
    stimmen = {p["slug"]: p["votes"] for p in night["parties"]}
    sitze = {p["slug"]: p["seats"] for p in night["parties"]}
    assert punkt["shares"] and all((stimmen[s] or 0) > 0 for s in punkt["shares"])
    assert punkt["seats"] and all((sitze[s] or 0) > 0 for s in punkt["seats"])
    assert sum(punkt["seats"].values()) == 52
    # Listen ohne Sitz stehen nicht drin, auch wenn sie Stimmen haben.
    assert {s for s, n in sitze.items() if not n} & set(punkt["seats"]) == set()


def test_live_vor_der_auszaehlung_haengt_nichts_an(datei, monkeypatch):
    """Ein Nachmittag voller Nullstände ist kein Verlauf."""
    from datetime import datetime, timezone

    def leer(force: bool = False):
        return votemanager.Snapshot(
            votemanager.parse((FIXTURES / "2026-stadt.csv").read_text(encoding="utf-8")),
            votemanager.parse((FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8")),
            votemanager.parse((FIXTURES / "2026-wahlbezirk.csv").read_text(encoding="utf-8")),
            datetime.now(timezone.utc), None, True, None,
        )

    monkeypatch.setattr(votemanager, "fetch", leer)
    service.reset()
    night = service.build_live()
    assert night["phase"] == "before" and night["history"] == []
    assert not datei.exists(), "vor der Auszählung wird nichts geschrieben"
    service.reset()


# ------------------------------------------------------------------ Generalprobe

def test_probe_verlauf_steigt_und_endet_beim_stand():
    reg, ref = register.load(), reference.load()
    punkte = service.probe_history(reg, ref, 60)
    stand = [p["districts_counted"] for p in punkte]
    assert stand == [10, 20, 30, 40, 50, 60]
    assert all(set(p) == SCHLUESSEL for p in punkte)
    zeiten = [p["at"] for p in punkte]
    assert zeiten[0] == "2026-09-13T16:00:00+00:00", "18:00 Uhr deutscher Zeit"
    assert zeiten[1] == "2026-09-13T16:15:00+00:00" and zeiten == sorted(zeiten)
    assert all(p["shares"] and sum(p["seats"].values()) == 52 for p in punkte)


def test_probe_verlauf_ohne_angabe_geht_bis_zum_letzten_bezirk():
    reg, ref = register.load(), reference.load()
    punkte = service.probe_history(reg, ref, None)
    assert [p["districts_counted"] for p in punkte][-1] == len(ref.districts) == 133
    # Am Ende steht das Ergebnis von 2021 im Register von 2026.
    voll = service.probe(None)
    assert punkte[-1]["seats"] == {p["slug"]: p["seats"] for p in voll["parties"] if p["seats"]}


def test_probe_verlauf_bleibt_leer_wenn_nichts_ausgezaehlt_ist():
    reg, ref = register.load(), reference.load()
    assert service.probe_history(reg, ref, 0) == []


# ------------------------------------------------------------------ Endpunkt

@pytest.fixture
def client(datei):
    from fastapi.testclient import TestClient
    from app.main import app

    service.reset()
    yield TestClient(app)
    service.reset()


def test_endpunkt_liefert_den_verlauf(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    d = client.get("/api/wahlabend?probe=2021&counted=40").json()
    verlauf = d["history"]
    assert isinstance(verlauf, list) and len(verlauf) == 4
    assert all(set(p) == SCHLUESSEL for p in verlauf)
    assert [p["districts_counted"] for p in verlauf] == [10, 20, 30, 40]
    letzter = verlauf[-1]
    assert letzter["districts_counted"] == d["progress"]["districts_counted"] == 40
    assert all(isinstance(v, float) for v in letzter["shares"].values())
    assert all(isinstance(v, int) for v in letzter["seats"].values())
