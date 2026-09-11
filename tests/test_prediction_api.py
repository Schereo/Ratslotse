"""``/api/tipp/…`` — Beitritt, Tippen, Tafel, Admin (docs/plan-tippspiel-ratswahl.md).

Die Ratswahl und die OB-Wahl sind die GRUNDLAGE des Vergleichs (Plan §3
Zeile 9) — hier ersetzt durch die netzfreie Generalprobe
(``election.service.probe`` / ``election.mayor.probe``, beide lesen nur
lokale Dateien), damit kein Test ins Netz muss, und zwar mit ``counted=0``:
So nennt der Wahlabend keine Zahl, und die Tests hier sehen nur die
Handeingabe aus ``prediction_result``. Was der Wahlabend beisteuert und wie
die Handeingabe ihn je Liste überschreibt, prüft
``tests/test_prediction_quelle.py``. Der Entwurf bleibt die Sperre für die
Handeingabe (Entwurf ändert die Tafel NICHT, Veröffentlichen schon).
"""
from __future__ import annotations

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
from app.prediction import service as prediction_service  # noqa: E402
from kern.store import Store  # noqa: E402

ADMIN = {"id": 1, "role": "admin", "roles": ["admin"], "status": "active"}
NUTZERIN = {"id": 2, "role": "user", "roles": [], "status": "active"}


@pytest.fixture(autouse=True)
def keine_echten_netzaufrufe(monkeypatch):
    """``service.stand``/``mine`` lesen Ratswahl und OB-Wahl als Grundlage
    des Vergleichs — hier durch die netzfreie Generalprobe ersetzt.

    Vorgabe ist ``counted=0`` (Phase „before", keine Sitze) — NICHT ein
    Teilstand: ``_check_auto_lock`` läuft bei JEDEM ``POST /api/tipp``, und
    ein Teilstand mit echten Sitzen würde die Testrunde beim allerersten
    Beitritt automatisch sperren. Wer den Auto-Lock selbst prüfen will,
    überschreibt ``election_service.live`` lokal in seinem eigenen Test."""
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", lambda force=False: mayor_module.probe(0))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    store = Store(tmp_path / "tippspiel-test.sqlite")
    app.dependency_overrides[get_store] = lambda: store
    prediction_service.reset_all()
    yield TestClient(app)
    app.dependency_overrides.pop(get_store, None)
    store.close()
    prediction_service.reset_all()


def voller_tipp(summe_ok: bool = True) -> dict[str, int]:
    """Ein gültiger Tipp: Startverteilung nach 2021er Sitzen, Rest auf die
    größte Liste — summiert exakt auf die Sitzzahl. ``summe_ok=False``
    liefert absichtlich einen Sitz zu wenig (für den 422-Test)."""
    reg = register.load()
    tipp = {p.slug: 0 for p in reg.parties}
    groesste = max(reg.parties, key=lambda p: p.candidates_total).slug
    tipp[groesste] = reg.seats if summe_ok else reg.seats - 1
    return tipp


def beitreten(client: TestClient, name: str = "Anna", seats: dict | None = None) -> dict:
    body = {"name": name}
    if seats is not None:
        body["seats"] = seats
    r = client.post("/api/tipp", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ Schalter

def test_ohne_schalter_ist_alles_404(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    assert client.get("/api/tipp/setup").status_code == 404
    assert client.post("/api/tipp", json={"name": "Anna"}).status_code == 404
    assert client.get("/api/tipp/stand").status_code == 404
    assert client.get("/api/tipp/qr.png").status_code == 404


def test_setup_nennt_16_listen_und_9_ob_kandidaturen(client):
    d = client.get("/api/tipp/setup").json()
    assert len(d["parties"]) == 16
    assert len(d["mayor_candidates"]) == 9
    assert d["seats_total"] == 52
    assert d["phase"] == "open" and d["locked"] is False


# ------------------------------------------------------------------ Beitritt

def test_beitritt_setzt_cookie_und_liefert_16_leere_zeilen(client):
    d = beitreten(client, "Anna")
    assert d["name"] == "Anna" and d["has_tip"] is False
    assert "tipp_token" in client.cookies
    d2 = client.get("/api/tipp/me").json()
    assert d2["player_id"] == d["player_id"]


def test_beitritt_ohne_namen_ist_422(client):
    r = client.post("/api/tipp", json={})
    assert r.status_code == 422


def test_doppelter_name_wird_umbenannt(client):
    a = beitreten(client, "Merle")
    # Ein zweiter Beitritt braucht einen FRISCHEN Client — sonst trägt der
    # Cookie des ersten Beitritts schon einen gültigen Token.
    zweiter = TestClient(app)
    b = zweiter.post("/api/tipp", json={"name": "Merle"})
    assert b.status_code == 200
    assert b.json()["name"] == "Merle (2)"
    assert a["name"] == "Merle"


def test_tipp_mit_falscher_summe_ist_422(client):
    r = client.post("/api/tipp", json={"name": "Bert", "seats": voller_tipp(summe_ok=False)})
    assert r.status_code == 422
    assert "52" in r.text


def test_tipp_mit_unbekannter_liste_ist_422(client):
    tipp = voller_tipp()
    tipp["nicht-registriert"] = tipp.pop(next(iter(tipp)))
    r = client.post("/api/tipp", json={"name": "Cara", "seats": tipp})
    assert r.status_code == 422


def test_gueltiger_tipp_liefert_16_zeilen(client):
    d = beitreten(client, "Dana", seats=voller_tipp())
    assert d["has_tip"] is True
    assert len(d["seats"]) == 16
    assert sum(l["tip"] for l in d["seats"]) == 52


def test_ob_tipp_ist_optional_ohne_abzug(client):
    tipp = voller_tipp()
    kandidaturen = client.get("/api/tipp/setup").json()["mayor_candidates"]
    gleich = round(100 / len(kandidaturen), 1)  # grobe Gleichverteilung, Summe knapp unter 100 %
    ob = {c["slug"]: gleich for c in kandidaturen}
    beitreten(client, "Erik", seats=tipp)
    r = client.post("/api/tipp", json={"seats": tipp, "mayor": ob})
    assert r.status_code == 200
    assert r.json()["has_mayor_tip"] is True

    ohne = TestClient(app)
    d2 = ohne.post("/api/tipp", json={"name": "Frida", "seats": tipp}).json()
    assert d2["has_mayor_tip"] is False


def test_ob_tipp_summe_ueber_100_ist_422(client):
    kandidaturen = client.get("/api/tipp/setup").json()["mayor_candidates"]
    ob = {c["slug"]: 50.0 for c in kandidaturen}  # 9 × 50 % ist weit über 100 %
    r = client.post("/api/tipp", json={"name": "Gita", "seats": voller_tipp(), "mayor": ob})
    assert r.status_code == 422


# ------------------------------------------------------------------ me / stand ohne Konto

def test_me_ohne_cookie_ist_401(client):
    frisch = TestClient(app)  # derselbe Prozess/Schalter, aber ohne den Cookie von `client`
    assert frisch.get("/api/tipp/me").status_code == 401


def test_stand_ohne_veroeffentlichung_ist_alphabetisch_ohne_punkte(client):
    beitreten(client, "Zoe", seats=voller_tipp())
    zweiter = TestClient(app)
    zweiter.post("/api/tipp", json={"name": "Anna", "seats": voller_tipp()})
    d = client.get("/api/tipp/stand").json()
    assert [r["name"] for r in d["rows"]] == ["Anna", "Zoe"]
    assert all(r["score"] is None and r["rank"] is None for r in d["rows"])
    assert d["leader_player_id"] is None


# ------------------------------------------------------------------ Admin: Entwurf vs. veröffentlicht

def test_admin_ohne_admin_ist_403(client):
    app.dependency_overrides[require_active] = lambda: NUTZERIN
    try:
        assert client.get("/api/tipp/admin/stand").status_code == 403
    finally:
        app.dependency_overrides.pop(require_active, None)


def test_entwurf_aendert_die_oeffentliche_tafel_nicht(client):
    tipp = voller_tipp()
    groesste_liste = next(k for k, v in tipp.items() if v > 0)
    beitreten(client, "Helga", seats=tipp)

    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        r = client.put("/api/tipp/admin/ergebnis",
                       json=[{"slug": groesste_liste, "seats": tipp[groesste_liste]}])
        assert r.status_code == 200
        vor_dem_admin_check = client.get("/api/tipp/stand").json()
        assert all(row["score"] is None for row in vor_dem_admin_check["rows"]), \
            "ein Entwurf darf die öffentliche Tafel nicht verändern"

        client.post("/api/tipp/admin/veroeffentlichen")
    finally:
        app.dependency_overrides.pop(require_active, None)

    nach_dem_publish = client.get("/api/tipp/stand").json()
    assert nach_dem_publish["rows"][0]["score"] is not None
    assert nach_dem_publish["rows"][0]["score"]["exact_lists"] >= 1


def test_veroeffentlichen_schreibt_rang_und_verwerfen_nimmt_entwurf_zurueck(client):
    tipp = voller_tipp()
    slug = next(k for k, v in tipp.items() if v > 0)
    beitreten(client, "Ida", seats=tipp)

    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        client.put("/api/tipp/admin/ergebnis", json=[{"slug": slug, "seats": tipp[slug]}])
        client.post("/api/tipp/admin/veroeffentlichen")
        stand1 = client.get("/api/tipp/admin/stand").json()
        zeile = next(r for r in stand1["results"] if r["slug"] == slug)
        assert zeile["published_seats"] == tipp[slug]

        # Ein neuer, falscher Entwurf — noch nicht veröffentlicht.
        client.put("/api/tipp/admin/ergebnis", json=[{"slug": slug, "seats": 0}])
        client.post("/api/tipp/admin/verwerfen")
        stand2 = client.get("/api/tipp/admin/stand").json()
        zeile2 = next(r for r in stand2["results"] if r["slug"] == slug)
        assert zeile2["seats"] == tipp[slug], "Verwerfen muss den Entwurf auf den veröffentlichten Stand zurücksetzen"
        assert zeile2["published_seats"] == tipp[slug], "der veröffentlichte Stand darf durch Verwerfen nicht verschwinden"
    finally:
        app.dependency_overrides.pop(require_active, None)


def test_rank_before_nach_zweitem_veroeffentlichten_stand(client, monkeypatch):
    reg = register.load()
    zwei_listen = [p.slug for p in reg.parties][:2]
    a_tipp = {p.slug: 0 for p in reg.parties}
    a_tipp[zwei_listen[0]] = 30
    a_tipp[zwei_listen[1]] = 22
    b_tipp = {p.slug: 0 for p in reg.parties}
    b_tipp[zwei_listen[0]] = 10
    b_tipp[zwei_listen[1]] = 42

    beitreten(client, "Anna", seats=a_tipp)
    zweiter = TestClient(app)
    zweiter.post("/api/tipp", json={"name": "Bert", "seats": b_tipp})

    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        # Stand 1: Anna liegt näher am Ergebnis.
        client.put("/api/tipp/admin/ergebnis", json=[{"slug": zwei_listen[0], "seats": 30},
                                                      {"slug": zwei_listen[1], "seats": 22}])
        client.post("/api/tipp/admin/veroeffentlichen")
        stand1 = client.get("/api/tipp/stand").json()
        anna_rang_1 = next(r for r in stand1["rows"] if r["name"] == "Anna")["rank"]
        assert anna_rang_1 == 1

        import time as _time
        _time.sleep(1.1)  # published_at hat Sekundenauflösung — der zweite Stand braucht einen neuen Zeitstempel
        # Stand 2: jetzt liegt Bert näher am Ergebnis.
        client.put("/api/tipp/admin/ergebnis", json=[{"slug": zwei_listen[0], "seats": 10},
                                                      {"slug": zwei_listen[1], "seats": 42}])
        client.post("/api/tipp/admin/veroeffentlichen")
    finally:
        app.dependency_overrides.pop(require_active, None)

    prediction_service.reset()
    stand2 = client.get("/api/tipp/stand").json()
    bert = next(r for r in stand2["rows"] if r["name"] == "Bert")
    assert bert["rank"] == 1
    assert bert["rank_before"] == 2, "Bert stand im vorherigen Stand auf Rang 2"


# ------------------------------------------------------------------ Moderation

def test_ausgeblendete_person_fehlt_im_stand(client):
    d = beitreten(client, "Konrad", seats=voller_tipp())
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        r = client.put(f"/api/tipp/admin/spieler/{d['player_id']}", json={"hidden": True})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(require_active, None)
    stand = client.get("/api/tipp/stand").json()
    assert "Konrad" not in [row["name"] for row in stand["rows"]]


def test_admin_stand_zeigt_ausgeblendete_in_der_spielerliste(client):
    """Die öffentliche Tafel lässt Ausgeblendete weg — der Admin muss sie
    trotzdem sehen können, um sie wieder einzublenden oder umzubenennen."""
    d = beitreten(client, "Ludwig", seats=voller_tipp())
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        client.put(f"/api/tipp/admin/spieler/{d['player_id']}", json={"hidden": True})
        admin = client.get("/api/tipp/admin/stand").json()
    finally:
        app.dependency_overrides.pop(require_active, None)
    zeile = next(p for p in admin["players"] if p["name"] == "Ludwig")
    assert zeile["hidden"] is True
    assert zeile["has_tip"] is True


def test_spieler_umbenennen_wirkt_auf_stand_und_admin(client):
    d = beitreten(client, "Alterername", seats=voller_tipp())
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        r = client.put(f"/api/tipp/admin/spieler/{d['player_id']}", json={"name": "Neuername"})
        assert r.status_code == 200
        assert any(p["name"] == "Neuername" for p in r.json()["players"])
    finally:
        app.dependency_overrides.pop(require_active, None)
    stand = client.get("/api/tipp/stand").json()
    assert "Neuername" in [row["name"] for row in stand["rows"]]
    assert "Alterername" not in [row["name"] for row in stand["rows"]]


# ------------------------------------------------------------------ Spätstarter

def test_beitritt_nach_tipp_schluss_wird_als_nachgetippt_markiert(client):
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        r = client.put("/api/tipp/admin/phase", json={"phase": "locked"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(require_active, None)

    spaet = TestClient(app)
    d = spaet.post("/api/tipp", json={"name": "Spätzünder", "seats": voller_tipp()}).json()
    assert d["late_at"] is not None


def test_tipp_aendern_nach_tipp_schluss_ist_409_fuer_rechtzeitige(client):
    beitreten(client, "Ontime", seats=voller_tipp())
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        client.put("/api/tipp/admin/phase", json={"phase": "locked"})
    finally:
        app.dependency_overrides.pop(require_active, None)
    r = client.post("/api/tipp", json={"seats": voller_tipp()})
    assert r.status_code == 409


# ------------------------------------------------------------------ QR-Code und ETag

def test_qr_png_ist_ein_bild(client):
    r = client.get("/api/tipp/qr.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


# ------------------------------------------------------------------ Automatischer Tipp-Schluss

def test_erste_hochrechnung_loest_automatischen_tipp_schluss_aus(client, monkeypatch):
    """Sobald die ECHTE Ratswahl irgendeine Zahl zeigt (Sitz oder
    Hochrechnung), sperrt der nächste Aufruf von selbst — ohne Admin-Klick."""
    vor_dem_ergebnis = client.get("/api/tipp/setup").json()
    assert vor_dem_ergebnis["phase"] == "open"

    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(90))
    r = client.get("/api/tipp/stand")  # stand() ruft _check_auto_lock ebenfalls, wenn probe=None
    assert r.status_code == 200

    danach = client.get("/api/tipp/setup").json()
    assert danach["phase"] == "locked"
    assert danach["locked"] is True


def test_stand_liefert_304_beim_zweiten_abruf_mit_etag(client):
    beitreten(client, "Etag-Anna", seats=voller_tipp())
    erster = client.get("/api/tipp/stand")
    etag = erster.headers["etag"]
    zweiter = client.get("/api/tipp/stand", headers={"if-none-match": etag})
    assert zweiter.status_code == 304


def test_admin_durchschnitt_zaehlt_ausgeblendete_nicht(client):
    """Ø-Tipp und „exakt" im Admin-Panel wie auf der Tafel: ohne Ausgeblendete
    — die Teilnehmerliste zeigt sie trotzdem, zum Wiederfinden."""
    reg = register.load()
    slug = reg.parties[0].slug
    a = {p.slug: 0 for p in reg.parties}
    a[slug] = reg.seats
    b = {p.slug: 0 for p in reg.parties}
    b[reg.parties[1].slug] = reg.seats
    d = beitreten(client, "Sichtbar", seats=a)
    zweiter = TestClient(app)
    versteckt = zweiter.post("/api/tipp", json={"name": "Versteckt", "seats": b}).json()
    assert d["player_id"] != versteckt["player_id"]

    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        client.put(f"/api/tipp/admin/spieler/{versteckt['player_id']}", json={"hidden": True})
        stand = client.get("/api/tipp/admin/stand").json()
    finally:
        app.dependency_overrides.pop(require_active, None)
    zeile = next(r for r in stand["results"] if r["slug"] == slug)
    assert zeile["avg_tip"] == reg.seats, "nur der sichtbare Tipp zählt in den Schnitt"
    assert [p["name"] for p in stand["players"] if p["hidden"]] == ["Versteckt"]
