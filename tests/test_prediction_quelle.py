"""Woher das Tippspiel sein Ist nimmt (docs/plan-tippspiel-ratswahl.md, §3 Zeile 9).

Grundlage ist der **Wahlabend** (``election.service.live`` / ``mayor.fetch``,
hier die netzfreie Generalprobe), darüber liegt je Liste die veröffentlichte
**Handeingabe** aus dem Admin. Bis zum 11.09.2026 war das andersherum gebaut
— nur Veröffentlichtes zählte, der Wahlabend lieferte Menschentext —, und
damit hätte die Generalprobe ``?probe=2021&counted=N`` nie einen Rang gezeigt
und am Abend jede Hochrechnung zwei Admin-Klicks gebraucht. Diese Tests halten
die Reihenfolge fest: Handeingabe > Wahlabend > veröffentlichter
Votemanager-Schnappschuss.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.deps import get_store, require_active  # noqa: E402
from app.election import mayor as mayor_module  # noqa: E402
from app.election import register  # noqa: E402
from app.election import service as election_service  # noqa: E402
from app.main import app  # noqa: E402
from app.prediction import service  # noqa: E402
from kern import features  # noqa: E402
from kern.store import Store  # noqa: E402

_TIPPSPIEL_FEATURE = features.Feature(
    key="tippspiel", description="Test-Registrierung.", fertig_wenn="s. tests/test_prediction_api.py")
ADMIN = {"id": 1, "role": "admin", "roles": ["admin"], "status": "active"}


@pytest.fixture(autouse=True)
def wahlabend_vor_der_ersten_stimme(monkeypatch):
    """Vorgabe: nichts ausgezählt — ein Test, der Zahlen braucht, schaltet
    ``live`` selbst auf einen Teilstand um."""
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", lambda force=False: mayor_module.probe(0))


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    monkeypatch.setitem(features.FEATURES, "tippspiel", _TIPPSPIEL_FEATURE)
    st = Store(tmp_path / "quelle.sqlite")
    app.dependency_overrides[get_store] = lambda: st
    service.reset_all()
    yield st
    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(require_active, None)
    st.close()
    service.reset_all()


@pytest.fixture
def client(store):
    return TestClient(app)


def _tipp_wie(night: dict, *, abweichung: dict[str, int] | None = None) -> dict[str, int]:
    """Ein Tipp, der dem Wahlabend gleicht — optional je Liste verschoben,
    die Summe bleibt die Sitzzahl (Verschiebung geht zulasten der größten)."""
    tipp = {p["slug"]: service.night_seats(p) or 0 for p in night["parties"]}
    for slug, delta in (abweichung or {}).items():
        tipp[slug] += delta
    reg = register.load()
    groesste = max(reg.parties, key=lambda p: p.candidates_total).slug
    tipp[groesste] += reg.seats - sum(tipp.values())
    return tipp


def _verschoben(night: dict, plus: str, minus: str) -> dict:
    """Eine KOPIE des Wahlabends, zwei Sitze von ``minus`` nach ``plus``
    verschoben — ``probe()`` cacht sein dict, wer es direkt anfasst, ändert
    auch das Original."""
    kopie = copy.deepcopy(night)
    for p in kopie["parties"]:
        if p["slug"] == plus:
            p["projected_seats"] = (service.night_seats(p) or 0) + 2
        if p["slug"] == minus:
            p["projected_seats"] = (service.night_seats(p) or 0) - 2
    return kopie


def _beitreten(name: str, seats: dict[str, int]) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/tipp", json={"name": name, "seats": seats})
    assert r.status_code == 200, r.text
    return c


def _als_admin():
    app.dependency_overrides[require_active] = lambda: ADMIN


# ------------------------------------------------------------------ Der Wahlabend ist die Grundlage

def test_generalprobe_zeigt_raenge_ohne_eine_veroeffentlichte_zeile(client, store):
    night = election_service.probe(90)
    _beitreten("Genau", _tipp_wie(night))
    _beitreten("Daneben", _tipp_wie(night, abweichung={night["parties"][0]["slug"]: 3}))

    d = client.get("/api/tipp/stand?probe=2021&counted=90").json()
    assert d["source_label"] == "votemanager"
    assert [r["name"] for r in d["rows"]] == ["Genau", "Daneben"]
    assert d["rows"][0]["rank"] == 1 and d["rows"][0]["score"]["total"] > d["rows"][1]["score"]["total"]
    assert all(c["actual"] is not None for c in d["compare"])
    # Die Generalprobe schreibt NICHTS: kein Auto-Lock, keine Ränge.
    assert store.prediction_game(1)["phase"] == "open"
    assert store.prediction_standings_previous(1, "9999") == {}


def test_live_wahlabend_treibt_die_tafel_ohne_admin_klick(client, store, monkeypatch):
    night = election_service.probe(90)
    _beitreten("Genau", _tipp_wie(night))
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))
    service.reset()

    d = client.get("/api/tipp/stand").json()
    assert d["rows"][0]["rank"] == 1
    assert d["source_label"] == "votemanager"
    assert d["phase"] == "locked", "die erste Hochrechnung setzt den Tipp-Schluss"
    # Der Live-Pfad legt die Ränge mit echten Punkten ab.
    vorher = store.prediction_standings_previous(1, "9999")
    assert list(vorher.values()) == [1]
    punkte = store._conn.execute("SELECT points FROM prediction_standings").fetchone()[0]  # noqa: SLF001
    assert punkte == d["rows"][0]["score"]["total"]


def test_meins_rechnet_mit_demselben_ist_wie_die_tafel(client, monkeypatch):
    night = election_service.probe(90)
    c = _beitreten("Genau", _tipp_wie(night))
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))
    service.reset()

    meins = c.get("/api/tipp/me").json()
    tafel = client.get("/api/tipp/stand").json()
    ist_tafel = {z["slug"]: z["actual"] for z in tafel["compare"]}
    assert {z["slug"]: z["actual"] for z in meins["seats"]} == ist_tafel
    assert meins["score"] == tafel["rows"][0]["score"]


# ------------------------------------------------------------------ Handeingabe schlägt Wahlabend — je Liste

def test_veroeffentlichte_handeingabe_ueberschreibt_genau_eine_liste(client, monkeypatch):
    night = election_service.probe(90)
    erste = night["parties"][0]["slug"]
    ist_erste = service.night_seats(night["parties"][0])
    _beitreten("Genau", _tipp_wie(night))
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))

    _als_admin()
    client.put("/api/tipp/admin/ergebnis", json=[{"slug": erste, "seats": ist_erste + 2}])
    vor_dem_publish = client.get("/api/tipp/stand").json()
    assert next(c for c in vor_dem_publish["compare"] if c["slug"] == erste)["actual"] == ist_erste, \
        "der Entwurf bleibt die Sperre für die Handeingabe"
    client.post("/api/tipp/admin/veroeffentlichen")

    d = client.get("/api/tipp/stand").json()
    ist = {c["slug"]: c["actual"] for c in d["compare"]}
    assert ist[erste] == ist_erste + 2
    for p in night["parties"][1:]:
        assert ist[p["slug"]] == service.night_seats(p), "die anderen Listen kommen weiter vom Wahlabend"
    assert d["source_label"] == "gemischt"


def test_veroeffentlichter_votemanager_schnappschuss_friert_nichts_ein(client, monkeypatch):
    """„Jetzt abfragen" + Veröffentlichen ist Bequemlichkeit, keine Zusage:
    Zieht der Wahlabend weiter, folgt die Tafel ihm."""
    night = election_service.probe(90)
    _beitreten("Genau", _tipp_wie(night))
    monkeypatch.setattr(election_service, "live", lambda: night)
    _als_admin()
    client.post("/api/tipp/admin/abfragen")
    client.post("/api/tipp/admin/veroeffentlichen")
    alt = {c["slug"]: c["actual"] for c in client.get("/api/tipp/stand").json()["compare"]}

    weiter = _verschoben(night, night["parties"][0]["slug"], night["parties"][1]["slug"])
    monkeypatch.setattr(election_service, "live", lambda: weiter)
    service.reset()
    neu = {c["slug"]: c["actual"] for c in client.get("/api/tipp/stand").json()["compare"]}
    assert neu == {p["slug"]: service.night_seats(p) for p in weiter["parties"]}
    assert neu != alt


def test_ohne_wahlabend_zaehlt_der_veroeffentlichte_schnappschuss(client, monkeypatch):
    _beitreten("Genau", _tipp_wie(election_service.probe(90)))
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))
    _als_admin()
    client.post("/api/tipp/admin/abfragen")
    client.post("/api/tipp/admin/veroeffentlichen")

    def kaputt():
        raise RuntimeError("Votemanager weg")
    monkeypatch.setattr(election_service, "live", kaputt)
    service.reset()
    d = client.get("/api/tipp/stand").json()
    assert d["rows"][0]["rank"] == 1, "der Abend darf an nichts sterben"
    assert d["source_label"] == "votemanager"
    assert any("nicht abrufbar" in n for n in d["notes"])


# ------------------------------------------------------------------ OB-Wahl

def test_ob_prozente_zaehlen_erst_ab_der_ersten_stimme(client):
    _beitreten("Genau", _tipp_wie(election_service.probe(0)))
    vorher = client.get("/api/tipp/stand?probe=2021&counted=0").json()
    assert all(m["actual_pct"] is None for m in vorher["mayor"])
    assert vorher["rows"][0]["score"] is None, "vor der ersten Stimme gibt es keine Punkte — auch nicht aus der OB-Wahl"
    danach = client.get("/api/tipp/stand?probe=2021&counted=60").json()
    assert any(m["actual_pct"] is not None for m in danach["mayor"])


# ------------------------------------------------------------------ Stand-Zeitstempel und vorheriger Rang

def test_gleiches_ist_behaelt_seinen_stand_zeitstempel(client, monkeypatch):
    _beitreten("Genau", _tipp_wie(election_service.probe(90)))
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))
    service.reset()
    eins = client.get("/api/tipp/stand").json()["computed_at"]
    service.reset()  # Cache weg, Ist gleich → derselbe Stand, derselbe ETag
    zwei = client.get("/api/tipp/stand").json()["computed_at"]
    assert eins == zwei


def test_generalprobe_kennt_den_vorherigen_rang_ohne_datenbank(client, store, monkeypatch):
    night = election_service.probe(133)
    a, b = night["parties"][0], night["parties"][1]
    # Anna trifft den Endstand, Bert trifft eine verschobene Fassung davon.
    _beitreten("Anna", _tipp_wie(night))
    _beitreten("Bert", _tipp_wie(night, abweichung={a["slug"]: 2, b["slug"]: -2}))

    verschoben = _verschoben(night, a["slug"], b["slug"])
    monkeypatch.setattr(election_service, "probe", lambda counted: verschoben if counted == 40 else night)

    stand_40 = client.get("/api/tipp/stand?probe=2021&counted=40").json()
    assert [r["name"] for r in stand_40["rows"]] == ["Bert", "Anna"]
    assert all(r["rank_before"] is None for r in stand_40["rows"])

    stand_133 = client.get("/api/tipp/stand?probe=2021&counted=133").json()
    assert [r["name"] for r in stand_133["rows"]] == ["Anna", "Bert"]
    anna = next(r for r in stand_133["rows"] if r["name"] == "Anna")
    assert (anna["rank"], anna["rank_before"]) == (1, 2)
    assert store.prediction_standings_previous(1, "9999") == {}, "die Generalprobe schreibt keine Ränge"


def test_uhrzeiten_stehen_in_berliner_zeit():
    assert service._uhrzeit("2026-09-13T18:07:00+00:00") == "20:07"  # noqa: SLF001
    assert service._uhrzeit("2026-09-13T18:07:00") == "20:07", "naiv heißt UTC (so schreibt der Store)"  # noqa: SLF001
