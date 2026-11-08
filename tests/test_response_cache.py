"""Der Antwort-Zwischenspeicher (``web/backend/app/response_cache.py``).

Auswertungen, die für alle Konten gleich sind, rechnet der Dienst seit 11/2026
einmal je Datenstand statt bei jeder Anfrage. Was davon abhängt, dass es
stimmt — und was dieser Test deshalb festhält:

- **Jeder Commit wird gesehen**, auch der eines anderen Prozesses (der Cron
  schreibt in seinem eigenen). Sonst stünde nach dem Einlesen der alte Stand
  da, bis jemand den Dienst neu startet.
- **Der Wächter hält keinen Lese-Schnappschuss.** Ein offener Leser blockiert
  das Einchecken der WAL, und sie wächst lautlos — das ist hier zweimal
  passiert (``tests/test_store_orte_wal.py``).
- **Die Release-Barriere wirkt** (``kern/maintenance.py``).
- **Nichts Persönliches** wird geteilt, und **Rechte** werden vor dem
  Zwischenspeicher geprüft.
- **Mit und ohne Zwischenspeicher dieselbe Antwort**, Byte für Byte im JSON.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import date
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from app import response_cache as rc  # noqa: E402

#: Groß genug, dass die Schreibvorgänge SQLites automatisches Einchecken
#: (1.000 Seiten, gut 4 MB) deutlich überschreiten.
SEITE = "x" * 20_000


@pytest.fixture()
def db(tmp_path) -> Path:
    path = tmp_path / "daten.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x TEXT)")
    conn.commit()
    conn.close()
    return path


def _schreiben(path: Path, anzahl: int = 1, text: str = "a") -> None:
    """Ein Commit über eine EIGENE Verbindung — wie eine andere Anfrage."""
    conn = sqlite3.connect(path)
    with conn:
        conn.executemany("INSERT INTO t VALUES (?)", [(text,)] * anzahl)
    conn.close()


def _zaehler(path: Path):
    """Ein Bauplan, der mitzählt und den Bestand liest."""
    aufrufe = []

    def bauen():
        conn = sqlite3.connect(path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM t").fetchall()[0][0]
        finally:
            conn.close()
        aufrufe.append(n)
        return {"rows": n}
    return bauen, aufrufe


# ------------------------------------------------------------ Datenstand

def test_gleicher_stand_kommt_aus_dem_speicher(db):
    bauen, aufrufe = _zaehler(db)
    erst = rc.cached("t", [db], bauen)
    zweit = rc.cached("t", [db], bauen)
    assert erst == {"rows": 0} and zweit is erst
    assert aufrufe == [0]


def test_commit_einer_anderen_verbindung_rechnet_neu(db):
    bauen, aufrufe = _zaehler(db)
    rc.cached("t", [db], bauen)
    _schreiben(db, 3)
    assert rc.cached("t", [db], bauen) == {"rows": 3}
    assert rc.cached("t", [db], bauen) == {"rows": 3}
    assert aufrufe == [0, 3]


def test_commit_eines_anderen_prozesses_rechnet_neu(db):
    """Der Cron schreibt nicht im Dienst, sondern in seinem eigenen Prozess."""
    bauen, aufrufe = _zaehler(db)
    rc.cached("t", [db], bauen)
    subprocess.run(
        [sys.executable, "-c",
         "import sqlite3, sys\n"
         "c = sqlite3.connect(sys.argv[1])\n"
         "c.execute(\"INSERT INTO t VALUES ('cron')\")\n"
         "c.commit()\n", str(db)],
        check=True)
    assert rc.cached("t", [db], bauen) == {"rows": 1}
    assert aufrufe == [0, 1]


def test_nach_mitternacht_wird_neu_gerechnet(db, monkeypatch):
    """Viele Auswertungen rechnen mit „heute" (zwölf Monate zurück)."""
    bauen, aufrufe = _zaehler(db)

    class Datum(date):
        heute = date(2026, 11, 8)

        @classmethod
        def today(cls):
            return cls.heute

    monkeypatch.setattr(rc, "date", Datum)
    rc.cached("t", [db], bauen)
    rc.cached("t", [db], bauen)
    Datum.heute = date(2026, 11, 9)
    rc.cached("t", [db], bauen)
    assert len(aufrufe) == 2
    # Ohne Tagesbindung bleibt es beim Eintrag.
    rc.cached("ohne_tag", [db], bauen, per_day=False)
    Datum.heute = date(2026, 11, 10)
    rc.cached("ohne_tag", [db], bauen, per_day=False)
    assert len(aufrufe) == 3


def test_ersetzte_datei_wird_bemerkt(db, tmp_path):
    """Eine Wiederherstellung legt eine neue Datei an denselben Pfad. Der
    Wächter hielte sonst die alte offen und sähe nie wieder einen Commit."""
    bauen, aufrufe = _zaehler(db)
    rc.cached("t", [db], bauen)
    neu = tmp_path / "neu.sqlite"
    conn = sqlite3.connect(neu)
    conn.execute("CREATE TABLE t (x TEXT)")
    conn.executemany("INSERT INTO t VALUES (?)", [("b",)] * 5)
    conn.commit()
    conn.close()
    os.replace(neu, db)
    assert rc.cached("t", [db], bauen) == {"rows": 5}


# ------------------------------------------------------------ WAL & Barriere

def test_waechter_haelt_keinen_schnappschuss_und_die_wal_bleibt_eincheckbar(db):
    """Der Kern der WAL-Regel: Zwischen zwei Abfragen ist der Wächter kein
    Leser. Mit offenem Schnappschuss scheiterte ``wal_checkpoint(TRUNCATE)``
    (``busy``), und die WAL wüchse bei jedem Cron-Lauf weiter."""
    for _ in range(5):
        assert rc.data_state(db) is not None
    waechter = rc._watchers[str(db)]
    assert not waechter.conn.in_transaction

    schreiber = sqlite3.connect(db)
    try:
        with schreiber:
            schreiber.executemany("INSERT INTO t VALUES (?)", [(SEITE,)] * 400)
        assert rc.data_state(db) is not None
        busy, _log, _eingecheckt = schreiber.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)").fetchall()[0]
        assert busy == 0, "Der Wächter blockiert das Einchecken der WAL."
        assert Path(f"{db}-wal").stat().st_size == 0

        # Gegenprobe, dass die Probe überhaupt greift: Ein Leser MIT
        # Schnappschuss blockiert genau dieses Einchecken.
        leser = sqlite3.connect(db, isolation_level=None)
        leser.execute("BEGIN")
        leser.execute("SELECT COUNT(*) FROM t").fetchall()
        with schreiber:
            schreiber.executemany("INSERT INTO t VALUES (?)", [(SEITE,)] * 10)
        busy, _log, _eingecheckt = schreiber.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)").fetchall()[0]
        assert busy == 1
        leser.execute("COMMIT")
        leser.close()
    finally:
        schreiber.close()


def test_grosse_wal_wird_wieder_freigegeben(db, monkeypatch):
    """Solange der Wächter offen ist, löscht SQLite die ``-wal``-Datei nicht —
    sie bliebe in der Größe des größten Laufs stehen. Nach einem Commit mit
    großer Datei tritt der Wächter deshalb zur Seite; schließt danach der
    letzte Schreiber, ist sie weg."""
    monkeypatch.setattr(rc, "WAL_RELEASE_BYTES", 1_000_000)
    stand = rc.data_state(db)
    assert stand is not None
    wal = Path(f"{db}-wal")

    schreiber = sqlite3.connect(db)
    with schreiber:
        schreiber.executemany("INSERT INTO t VALUES (?)", [(SEITE,)] * 200)
    assert wal.stat().st_size > 1_000_000
    assert rc.data_state(db) is None, "großer Commit: der Wächter tritt zur Seite"
    assert str(db) not in rc._watchers
    schreiber.close()
    assert not wal.exists(), "ohne offenen Wächter räumt SQLite die WAL beim Schließen weg"

    neu = rc.data_state(db)
    assert neu is not None and neu[0] != stand[0], "neu geöffnet, neue Generation"
    # Kleine Commits lassen ihn offen.
    _schreiben(db, 1, "klein")
    assert rc.data_state(db) is not None and str(db) in rc._watchers


def test_release_barriere_schliesst_den_waechter(db, monkeypatch):
    """Steht die Wartungsmarke, öffnet niemand die Datenbank — auch der
    Wächter nicht. Es wird dann ungepuffert gerechnet (und der Store des
    Endpunkts verweigert sich ohnehin). Die Prüfung ist dieselbe wie in
    ``kern.maintenance.require_database_available``, samt Ausnahme für den
    Vorbereitungslauf des Releases."""
    from kern.maintenance import BYPASS_ENV, require_database_available

    monkeypatch.delenv(BYPASS_ENV, raising=False)
    bauen, aufrufe = _zaehler(db)
    rc.cached("t", [db], bauen)
    assert str(db) in rc._watchers
    marke = db.parent / ".release-maintenance"
    marke.touch()
    try:
        assert rc.data_state(db) is None
        assert str(db) not in rc._watchers
        rc.cached("t", [db], bauen)
        rc.cached("t", [db], bauen)
        assert len(aufrufe) == 3, "unter der Barriere kein Treffer aus dem Speicher"
        from council.store import CouncilStore
        with pytest.raises(RuntimeError, match="Release-Wartung"):
            CouncilStore(db.parent / "council.sqlite")
        # Die Ausnahme gilt hier wie dort.
        monkeypatch.setenv(BYPASS_ENV, "1")
        require_database_available(db)
        assert rc.data_state(db) is not None
        monkeypatch.delenv(BYPASS_ENV)
        assert rc.data_state(db) is None
    finally:
        marke.unlink()
    rc.cached("t", [db], bauen)
    rc.cached("t", [db], bauen)
    assert len(aufrufe) == 4


def test_ohne_datei_wird_ungepuffert_gerechnet(tmp_path):
    aufrufe = []

    def bauen():
        aufrufe.append(1)
        return 1

    class Ersatz:  # ein Test-Store ohne Datei
        pass

    for quelle in (None, ":memory:", tmp_path / "gibt-es-nicht.sqlite", Ersatz()):
        rc.cached("x", [quelle], bauen)
        rc.cached("x", [quelle], bauen)
    assert len(aufrufe) == 8
    assert not (tmp_path / "gibt-es-nicht.sqlite").exists(), "der Wächter legt nichts an"


# ------------------------------------------------------------ Verhalten

def test_fehler_wird_nicht_gespeichert(db):
    aufrufe = []

    def bauen():
        aufrufe.append(1)
        raise LookupError("404")

    for _ in range(2):
        with pytest.raises(LookupError):
            rc.cached("t", [db], bauen)
    assert len(aufrufe) == 2


def test_fehler_hinterlaesst_kein_schloss(db):
    """`/person/{slug}` ist öffentlich: Jeder erfundene Slug ist eine 404. Ein
    Schloss je fehlgeschlagenem Schlüssel wüchse unbegrenzt bis zum Neustart."""
    def bauen():
        raise LookupError("404")

    for i in range(50):
        with pytest.raises(LookupError):
            rc.cached("person", [db], bauen, key=f"gibt-es-nicht-{i}", maxsize=8)
    assert rc._build_locks == {}
    # Ein Schlüssel MIT Eintrag behält sein Schloss, auch wenn ein späterer
    # Neubau scheitert — er ist durch `maxsize` begrenzt.
    rc.cached("person", [db], lambda: "da", key="da", maxsize=8)
    _schreiben(db)
    with pytest.raises(LookupError):
        rc.cached("person", [db], bauen, key="da", maxsize=8)
    assert list(rc._build_locks) == [("person", "da")]


def test_gleichzeitige_anfragen_rechnen_einmal(db):
    """Nach einem Cron-Commit kommen mehrere Anfragen gleichzeitig — nur eine
    rechnet, die anderen warten auf sie."""
    aufrufe = []

    def bauen():
        aufrufe.append(1)
        time.sleep(0.2)
        return {"ok": True}

    ergebnisse = []
    faeden = [threading.Thread(target=lambda: ergebnisse.append(rc.cached("t", [db], bauen)))
              for _ in range(8)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    assert len(aufrufe) == 1
    assert len(ergebnisse) == 8 and all(e is ergebnisse[0] for e in ergebnisse)


def test_varianten_sind_begrenzt(db):
    for slug in ("a", "b", "c"):
        rc.cached("person", [db], lambda s=slug: s, key=slug, maxsize=2)
    assert list(rc._entries["person"]) == ["b", "c"]


def test_reset_schliesst_alle_waechter(db):
    rc.data_state(db)
    conn = rc._watchers[str(db)].conn
    rc.reset()
    assert rc._watchers == {} and rc._entries == {}
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


# ------------------------------------------------------------ Endpunkte

def _client_und_koepfe():
    """Zwei Konten: eins mit Haushalts-Recht, eins ohne."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.security import create_access_token
    from kern.store import Store

    s = Store(os.environ["RATSLOTSE_DB"])
    koepfe = {}
    try:
        for name, rolle in (("ratsfrau", "council_member"), ("leserin", None)):
            email = f"{name}-{time.monotonic_ns()}@example.org"
            uid = s.create_web_user(email, "x", status="active", email_verified=True,
                                    display_name=name)
            if rolle:
                s.add_web_user_role(uid, rolle)
            koepfe[name] = {"Authorization": f"Bearer {create_access_token(uid)}"}
    finally:
        s.close()
    return TestClient(app), koepfe


def _council():
    from council.store import CouncilStore
    return CouncilStore(os.environ["COUNCIL_DB"])


def _seed_ort_und_vorhaben() -> int:
    """Ein Beschluss mit Ort in Kreyenbrück und ein Vorhaben auf dessen Tafel."""
    store = _council()
    c = store._conn
    with c:
        c.execute("INSERT OR IGNORE INTO council_sessions (ksinr, committee, session_date, "
                  "session_time, location, fetched_at) VALUES (1, 'Rat', '2026-05-04', '18:00', "
                  "'Rathaus', '2026-05-01')")
        c.execute("INSERT OR IGNORE INTO council_decisions (id, ksinr, position, title, summary, "
                  "official_text, outcome, kind) VALUES (10, 1, 1, 'Bebauungsplan 81', "
                  "'70 Wohnungen.', 'Der Rat beschließt.', 'accepted', 'decision')")
        c.execute("INSERT OR IGNORE INTO council_locations (slug, name, kind, district, "
                  "local_area_id, updated_at) VALUES ('sandkruger-strasse', 'Sandkruger Straße', "
                  "'street', 'Kreyenbrück', 'kreyenbrueck', '2026-01-01')")
        c.execute("INSERT OR IGNORE INTO council_decision_locations (decision_id, location_slug, "
                  "source, evidence, method, confidence, updated_at) VALUES (10, "
                  "'sandkruger-strasse', 'title', 'x', 'regex', 0.9, '2026-01-01')")
    store.replace_district_projects("kreyenbrueck", [
        {"name": "Wohnungen Sandkruger Straße", "what": "70 Wohnungen.", "stage": "planning",
         "when": "2028", "category": "housing", "decision_ids": [10], "confidence": 97},
    ])
    pid = store.district_projects("kreyenbrueck")[0]["id"]
    store.close()
    return pid


@pytest.fixture()
def frische_dbs():
    for base in (os.environ["RATSLOTSE_DB"], os.environ["COUNCIL_DB"]):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


#: Die Endpunkte, die der Zwischenspeicher bedient — mit dem Konto, das sie
#: verlangen (``None`` = öffentlich).
GEPUFFERT = [
    ("/api/council/districts", "leserin"),
    ("/api/topics/suggestions", "leserin"),
    ("/api/council/cities/ideas/fields", None),
    ("/api/council/members", "leserin"),
    ("/api/council/elected", None),
    ("/api/council/person/niemand-da", None),
    ("/api/council/people-directory", None),
    ("/api/council/analysis", "leserin"),
    ("/api/council/parties", "leserin"),
    ("/api/council/finance", "leserin"),
    ("/api/council/budget/documents", "ratsfrau"),
    ("/api/council/budget/journey", "ratsfrau"),
    ("/api/council/budget/shareholdings", "ratsfrau"),
    ("/api/districts/projects", "leserin"),
    ("/api/districts/kreyenbrueck/projects", "leserin"),
]


def test_mit_und_ohne_zwischenspeicher_dieselbe_antwort(frische_dbs, monkeypatch):
    _seed_ort_und_vorhaben()
    client, koepfe = _client_und_koepfe()

    def abruf(url, konto):
        r = client.get(url, headers=koepfe[konto] if konto else {})
        return r.status_code, r.content

    gepuffert = {}
    for url, konto in GEPUFFERT:
        kalt = abruf(url, konto)
        warm = abruf(url, konto)
        assert kalt == warm, url
        gepuffert[url] = warm
    assert rc._entries, "der Zwischenspeicher wurde gar nicht benutzt"

    # Dieselben Aufrufe ohne Zwischenspeicher: als wäre keine Datei zu beobachten.
    monkeypatch.setattr(rc, "data_state", lambda _path: None)
    for url, konto in GEPUFFERT:
        assert abruf(url, konto) == gepuffert[url], url


def test_tafel_teilt_nichts_persoenliches(frische_dbs):
    """``reported`` hängt am Konto. Die Tafel liegt einmal im Speicher — wer
    nach der Melderin kommt, darf ihre Meldung nicht als eigene sehen."""
    pid = _seed_ort_und_vorhaben()
    client, koepfe = _client_und_koepfe()
    tafel = "/api/districts/kreyenbrueck/projects"
    assert client.get(tafel, headers=koepfe["leserin"]).json()["projects"][0]["reported"] is False
    r = client.post(f"/api/districts/projects/{pid}/report", json={}, headers=koepfe["ratsfrau"])
    assert r.status_code == 201
    # Die Meldung ist ein Commit: Die Melderin baut die Tafel neu …
    assert client.get(tafel, headers=koepfe["ratsfrau"]).json()["projects"][0]["reported"] is True
    # … und die Leserin bekommt DIESELBE gespeicherte Tafel, aber ihr eigenes Feld.
    assert client.get(tafel, headers=koepfe["leserin"]).json()["projects"][0]["reported"] is False
    assert client.get(tafel, headers=koepfe["ratsfrau"]).json()["projects"][0]["reported"] is True
    (gespeichert,) = [wert for _stand, wert in rc._entries["districts.board"].values()]
    assert all("reported" not in p for p in gespeichert["projects"])


def test_rechte_werden_vor_dem_zwischenspeicher_geprueft(frische_dbs):
    client, koepfe = _client_und_koepfe()
    for url in ("/api/council/budget/documents", "/api/council/budget/journey",
                "/api/council/budget/shareholdings"):
        assert client.get(url, headers=koepfe["ratsfrau"]).status_code == 200
        assert client.get(url, headers=koepfe["leserin"]).status_code == 403
        assert client.get(url).status_code == 401
    assert client.get("/api/council/districts").status_code == 401
    assert client.get("/api/council/analysis").status_code == 401


def test_neuer_ortslink_erscheint_sofort_im_filter(frische_dbs):
    """Ein Commit aus einer anderen Verbindung (der Cron) schlägt durch."""
    _seed_ort_und_vorhaben()
    client, koepfe = _client_und_koepfe()

    def zahl():
        zeilen = client.get("/api/council/districts", headers=koepfe["leserin"]).json()["districts"]
        return {z["place_id"]: z["count"] for z in zeilen}.get("kreyenbrueck", 0)

    assert zahl() == 1
    store = _council()
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, title, outcome, kind) "
            "VALUES (11, 1, 2, 'Zweiter Beschluss', 'rejected', 'decision')")
        store._conn.execute(
            "INSERT INTO council_decision_locations (decision_id, location_slug, source, evidence, "
            "method, confidence, updated_at) VALUES (11, 'sandkruger-strasse', 'title', 'x', "
            "'regex', 0.9, '2026-01-01')")
    store.close()
    assert zahl() == 2
