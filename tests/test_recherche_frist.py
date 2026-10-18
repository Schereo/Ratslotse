"""Recherchen gehören zum Gesprächsverlauf — auch beim Löschen und bei der Frist.

Befund 03.10.2026: ``deep_research_jobs`` hielt Frage und Bericht jeder
gründlichen Recherche unbegrenzt mit dem Konto fest, auch wenn das Konto dem
Speichern von Gesprächen nie zugestimmt hatte; „Alle Gespräche löschen" meldete
``deleted: 0`` und ließ sie stehen.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from kern.store import Store

ROOT = Path(__file__).resolve().parents[1]


def _konto(store: Store, email: str, speichern: int | None) -> int:
    uid = store.create_web_user(email, "x" * 60)
    if speichern is not None:
        store.set_qa_speichern(uid, bool(speichern))
    return uid


def _alt(store: Store, job_id: str, tage: int) -> None:
    stempel = (datetime.utcnow() - timedelta(days=tage)).isoformat(timespec="seconds")
    with store._conn:
        store._conn.execute("UPDATE deep_research_jobs SET created = ?, updated = ? WHERE id = ?",
                            (stempel, stempel, job_id))


def _job(store: Store, uid: int, frage: str, status: str = "fertig", tage: int = 0) -> str:
    job = store.deep_job_anlegen(uid, frage)
    store.deep_job_update(job, status, bericht=f"Bericht zu {frage}", quellen_json="{}")
    if tage:
        _alt(store, job, tage)
    return job


def _ids(store: Store) -> set[str]:
    return {r[0] for r in store._conn.execute("SELECT id FROM deep_research_jobs")}


def test_frist_loescht_nur_ohne_einwilligung_und_erst_nach_sieben_tagen(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    ohne = _konto(store, "ohne@example.org", 0)
    nie_gefragt = _konto(store, "nie@example.org", None)
    mit = _konto(store, "mit@example.org", 1)

    alt_ohne = _job(store, ohne, "Stadion?", tage=8)
    alt_nie = _job(store, nie_gefragt, "Radwege?", tage=8)
    frisch_ohne = _job(store, ohne, "Kitas?", tage=6)
    alt_mit = _job(store, mit, "Bäder?", tage=30)
    laeuft = _job(store, ohne, "Läuft noch?", status="laeuft", tage=8)

    assert store.deep_jobs_frist_abgelaufen() == 2
    assert _ids(store) == {frisch_ohne, alt_mit, laeuft}
    assert alt_ohne not in _ids(store) and alt_nie not in _ids(store)
    # Ein zweiter Lauf findet nichts mehr.
    assert store.deep_jobs_frist_abgelaufen() == 0
    store.close()


def test_alle_loeschen_raeumt_recherchen_ohne_das_kontingent_zurueckzugeben(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    uid = _konto(store, "nutzerin@example.org", 1)
    andere = _konto(store, "andere@example.org", 1)
    gestern = _job(store, uid, "Gestern?", tage=2)
    heute = _job(store, uid, "Heute?")
    laeuft = _job(store, uid, "Läuft?", status="laeuft")
    fremd = _job(store, andere, "Fremd?")
    vorher = store.deep_jobs_heute(uid)

    assert store.deep_jobs_inhalt_loeschen(uid) == 2
    assert gestern not in _ids(store)
    zeile = store._conn.execute(
        "SELECT question, report, sources, seen FROM deep_research_jobs WHERE id = ?",
        (heute,)).fetchone()
    assert tuple(zeile) == ("", None, None, 1)
    # Die leere Zeile zählt weiter: Löschen gibt keine Recherche zurück.
    assert store.deep_jobs_heute(uid) == vorher
    # Laufender Job und fremdes Konto bleiben unberührt.
    assert store.deep_job_get(laeuft, uid)["question"] == "Läuft?"
    assert store.deep_job_get(fremd, andere)["report"] == "Bericht zu Fremd?"
    # Zweiter Klick: nichts mehr zu tun.
    assert store.deep_jobs_inhalt_loeschen(uid) == 0
    store.close()


def test_cron_setzt_die_frist_durch(tmp_path, monkeypatch):
    pfad = tmp_path / "r.sqlite"
    store = Store(pfad)
    _job(store, _konto(store, "ohne@example.org", 0), "Alt?", tage=9)
    store.close()
    monkeypatch.setenv("RATSLOTSE_DB", str(pfad))
    spec = importlib.util.spec_from_file_location("speicherfristen_test",
                                                  ROOT / "scripts" / "speicherfristen.py")
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.main() == {"recherchen_geloescht": 1}
