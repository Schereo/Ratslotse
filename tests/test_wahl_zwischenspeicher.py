"""Was die Wahlseiten nicht bei jedem Aufruf neu tun (11/2026).

Drei Zusagen, jede mit ihrer Gegenprobe:

1. **Ein amtliches Ergebnis wird nicht jede Minute neu gerechnet.** Bis
   11/2026 galt nach dem Wahlabend für immer der Minutentakt: Jeder Aufruf
   von ``/wahlabend`` oder ``/tipp/live`` nach einer Minute holte drei CSVs
   und rechnete 1,1–1,3 s lang die Abstände neu — im einzigen
   uvicorn-Prozess. Steht der Stand amtlich fest und war der letzte Abruf gut,
   hält er einen Tag. Ein Aussetzer oder ein vorläufiger Stand bleibt beim
   Minutentakt.
2. **Wahldateien aus dem Repo werden je Fassung einmal gelesen** — und eine
   neu geschriebene Datei gilt beim nächsten Aufruf, ohne Neustart.
3. **``?area_candidates=false`` lässt nur die Kandidaturen je Wahlbereich
   weg** und verändert das zwischengespeicherte Bild nicht.
"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from typing import cast

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.antworten import ElectionNight  # noqa: E402
from app.election import archive, elections, mayor, repo_files, service, votemanager  # noqa: E402


class Uhr:
    """Eine Uhr, die nur vorgeht, wenn der Test es sagt."""

    def __init__(self) -> None:
        self.t = 1000.0

    def monotonic(self) -> float:
        return self.t


def _bild(phase: str = "complete", ok: bool = True, notes: list[str] | None = None) -> ElectionNight:
    return cast(ElectionNight, {"phase": phase, "source": {"ok": ok}, "notes": notes or []})


@pytest.fixture
def uhr(monkeypatch):
    u = Uhr()
    monkeypatch.setattr(service, "time", types.SimpleNamespace(monotonic=u.monotonic))
    monkeypatch.setattr(votemanager, "time", types.SimpleNamespace(monotonic=u.monotonic))
    service.reset()
    yield u
    service.reset()


def _neubauten(monkeypatch, bild: ElectionNight) -> list[int]:
    gebaut: list[int] = []

    def bauen() -> ElectionNight:
        gebaut.append(1)
        return bild

    monkeypatch.setattr(service, "build_live", bauen)
    return gebaut


def _warte_auf_den_bau() -> None:
    for _ in range(500):
        if not service._building:
            return
        time.sleep(0.01)
    raise AssertionError("Der Neubau im Hintergrund wird nicht fertig.")


# ------------------------------------------------------------------ 1) amtlich: ein Tag statt einer Minute

def test_amtliches_ergebnis_haelt_einen_tag(uhr, monkeypatch):
    monkeypatch.setattr(votemanager, "settled", lambda: True)
    gebaut = _neubauten(monkeypatch, _bild())
    service.live()
    assert len(gebaut) == 1
    uhr.t += 61
    service.live()
    _warte_auf_den_bau()
    assert len(gebaut) == 1, "Nach einer Minute darf ein amtliches Ergebnis nicht neu gebaut werden."
    uhr.t += votemanager.TTL_SECONDS_SETTLED
    service.live()
    _warte_auf_den_bau()
    assert len(gebaut) == 2, "Nach einem Tag wird doch wieder nachgefragt."


@pytest.mark.parametrize("bild, amtlich", [
    (_bild(), False),                                    # vorläufig: Korrekturen kommen noch
    (_bild(ok=False), True),                             # der letzte Abruf klemmte
    (_bild(phase="counting"), True),                     # noch nicht ausgezählt
    (_bild(notes=[service.NOTE_REDUCED]), True),         # abgespeckte Stufe ohne Abstände
])
def test_sonst_bleibt_der_minutentakt(uhr, monkeypatch, bild, amtlich):
    monkeypatch.setattr(votemanager, "settled", lambda: amtlich)
    gebaut = _neubauten(monkeypatch, bild)
    service.live()
    uhr.t += 61
    service.live()
    _warte_auf_den_bau()
    assert len(gebaut) == 2


def test_votemanager_fragt_bei_amtlichem_stand_einmal_am_tag(uhr, monkeypatch):
    ordner = WURZEL / "kommunalwahl" / "referenz-2026"
    csv = {"city": "ratswahl-2026-stadt.csv", "areas": "ratswahl-2026-wahlbereiche.csv",
           "districts": "ratswahl-2026-wahlbezirke.csv"}
    datei_zu = {pfad: ordner / csv[k] for k, pfad in votemanager.files().items()}
    abrufe: list[str] = []

    def hole(session, url):
        abrufe.append(url)
        pfad = next(p for p in datei_zu if url.endswith(p))
        return datei_zu[pfad].read_text(encoding="utf-8-sig"), None

    monkeypatch.setattr(votemanager, "_get", hole)
    monkeypatch.setattr(votemanager, "_crosscheck", lambda session, base, snap, payload: [])
    votemanager.reset_memory()
    amtlich = {"ja": True}
    monkeypatch.setattr(votemanager, "settled", lambda: amtlich["ja"])
    try:
        votemanager.fetch()
        assert len(abrufe) == 3
        uhr.t += 61
        votemanager.fetch()
        assert len(abrufe) == 3, "Ein amtlicher Stand braucht keinen neuen Abruf nach einer Minute."
        amtlich["ja"] = False
        votemanager.fetch()
        assert len(abrufe) == 6, "Ohne amtlichen Stand gilt wieder die Minute."
    finally:
        votemanager.reset_memory()


def test_settled_folgt_dem_vermerk_und_wirft_nie(monkeypatch):
    monkeypatch.setattr(archive, "result_status", lambda w: "amtlich")
    assert votemanager.settled() is True
    monkeypatch.setattr(archive, "result_status", lambda w: "vorlaeufig")
    assert votemanager.settled() is False

    def kaputt(w):
        raise RuntimeError("Registry unlesbar")

    monkeypatch.setattr(archive, "result_status", kaputt)
    assert votemanager.settled() is False


# ------------------------------------------------------------------ 2) Dateien je Fassung einmal

def test_neue_fassung_einer_datei_gilt_sofort(tmp_path):
    repo_files.reset()
    datei = tmp_path / "quelle.json"
    datei.write_text('{"stand": "vorlaeufig"}', encoding="utf-8")
    erstes = repo_files.json_file(datei)
    assert repo_files.json_file(datei) is erstes, "Dieselbe Fassung wird nicht noch einmal gelesen."
    datei.write_text('{"stand": "amtlich", "neu": 1}', encoding="utf-8")
    assert repo_files.json_file(datei) == {"stand": "amtlich", "neu": 1}
    repo_files.reset()


def test_stichwahl_liest_die_bezirksdatei_einmal(monkeypatch):
    mayor.reset()
    w = elections.runoff()
    if w is None:
        pytest.skip("keine Stichwahl in der Registry")
    known = mayor.candidates(w)
    alle = mayor.probe_districts(None, known, w)
    mayor.probe_districts(None, known, w)
    mayor.probe_districts(40, known, w)
    info = mayor._first_round_districts.cache_info()
    assert info.misses == 1 and info.hits == 2
    # Die Probe mit 40 Bezirken legt neue Zeilen an, statt die geteilten zu ändern.
    assert mayor.probe_districts(None, known, w) == alle
    assert all(d.counted for d in alle)
    mayor.reset()


def test_rueckblick_liest_seine_csvs_einmal():
    archive.reset()
    erstes = archive.snapshot("ratswahl-2026")
    zweites = archive.snapshot("ratswahl-2026")
    assert erstes is not None and zweites is not None
    assert erstes[1] is zweites[1]
    assert archive._frozen_snapshot.cache_info().misses == 1
    archive.reset()


# ------------------------------------------------------------------ 3) ohne Kandidaturen je Wahlbereich

def test_area_candidates_false_laesst_nur_die_kandidaturen_weg(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    archive.reset()
    client = TestClient(app)
    voll = client.get("/api/wahlabend?wahl=ratswahl-2026").json()
    schlank = client.get("/api/wahlabend?wahl=ratswahl-2026&area_candidates=false").json()
    assert any(p["candidates"] for a in voll["areas"] for p in a["parties"])
    assert all(p["candidates"] == [] for a in schlank["areas"] for p in a["parties"])
    # Alles andere bleibt, wie es war.
    for a in voll["areas"]:
        for p in a["parties"]:
            p["candidates"] = []
    assert schlank == voll
    # Das zwischengespeicherte Bild hat seine Kandidaturen behalten.
    bild = archive.night("ratswahl-2026")
    assert bild is not None and any(p["candidates"] for a in bild["areas"] for p in a["parties"])
    archive.reset()
