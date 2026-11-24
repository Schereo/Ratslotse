"""Wächter für den Herzschlag (`scripts/check_herzschlag.py`).

**Die Lücke, die er schließt.** ``run_guarded`` meldet einen Job, der
ABSTÜRZT. Ein Job, der gar nicht mehr STARTET, stürzt nicht ab — er fehlt
einfach. Sichtbar war das nur als Ampel im Admin-Panel; wer nicht hinsieht,
merkt monatelang nicht, dass die Protokolle nicht mehr geholt werden.

Geprüft wird vor allem, dass er nicht in die andere Richtung kippt: Ein
Herzschlag, der täglich grundlos meldet, wird nach einer Woche weggefiltert —
und dann meldet er auch das Echte nicht mehr.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kern.jobs import BY_KEY, JOBS, zustand
from kern.store import Store

WURZEL = Path(__file__).resolve().parents[1]


def _modul():
    spec = importlib.util.spec_from_file_location(
        "check_herzschlag", WURZEL / "scripts" / "check_herzschlag.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # type: ignore[union-attr]
    return m


herzschlag = _modul()


# ---------------------------------------------------------------------------
# Die gemeinsame Zustandsregel
# ---------------------------------------------------------------------------

JETZT = datetime(2026, 9, 4, 12, 0, 0)


def _lauf(stunden_her: float, status: str = "ok") -> dict:
    return {"started_at": (JETZT - timedelta(hours=stunden_her)).isoformat(),
            "status": status}


def test_ein_frischer_lauf_ist_in_ordnung():
    job = {"key": "x", "max_age_h": 30}
    assert zustand(job, _lauf(2), JETZT)[0] == "ok"


def test_ein_alter_lauf_ist_stumm():
    """DER Fall, für den es sonst gar keine Meldung gibt."""
    job = {"key": "x", "max_age_h": 30}
    st, alter = zustand(job, _lauf(50), JETZT)
    assert st == "stale"
    assert alter == 50.0


def test_die_grenze_gilt_erst_wenn_sie_ueberschritten_ist():
    """`max_age_h` ist bewusst großzügiger als der Abstand zweier Läufe —
    ein einzelner verspäteter Lauf darf keinen Alarm auslösen."""
    job = {"key": "x", "max_age_h": 30}
    assert zustand(job, _lauf(30), JETZT)[0] == "ok"
    assert zustand(job, _lauf(30.5), JETZT)[0] == "stale"


def test_ein_absturz_gewinnt_gegen_das_alter():
    job = {"key": "x", "max_age_h": 30}
    assert zustand(job, _lauf(2, "error"), JETZT)[0] == "error"


def test_ohne_lauf_ist_der_zustand_unbekannt():
    assert zustand({"key": "x", "max_age_h": 30}, None) == ("unknown", None)


def test_ein_kaputter_zeitstempel_wirft_nicht():
    """Eine unlesbare Zeile darf den ganzen Lauf nicht umbringen."""
    job = {"key": "x", "max_age_h": 30}
    st, alter = zustand(job, {"started_at": "gestern", "status": "ok"}, JETZT)
    assert alter is None
    assert st == "ok"


# ---------------------------------------------------------------------------
# Der Lauf selbst
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "r.sqlite")
    yield s
    s.close()


def test_ein_stummer_job_wird_gefunden(store):
    """Alle Jobs frisch eintragen, EINEN alt lassen — genau der muss auffallen."""
    jetzt = datetime.utcnow()
    for job in JOBS:
        if job["key"] in ("check_herzschlag", "check_council"):
            continue
        store.record_job_run(job["key"], jetzt, "ok", 1.0, None, None)
    # `check_council` lief zuletzt vor drei Tagen.
    store.record_job_run("check_council", jetzt - timedelta(hours=72), "ok", 1.0, None, None)

    stumm = herzschlag.schweigende(store)
    schluessel = {j["key"] for j, _, _ in stumm}
    assert "check_council" in schluessel
    assert "check_herzschlag" not in schluessel, (
        "Der Herzschlag darf sich nicht selbst melden — er läuft ja gerade.")


def test_alles_frisch_meldet_nichts(store):
    jetzt = datetime.utcnow()
    for job in JOBS:
        store.record_job_run(job["key"], jetzt, "ok", 1.0, None, None)
    assert herzschlag.schweigende(store) == []


def test_der_herzschlag_steht_selbst_in_der_registry():
    """Sonst wäre er der einzige Job, den niemand überwacht."""
    assert "check_herzschlag" in BY_KEY
    assert BY_KEY["check_herzschlag"]["max_age_h"] > 24


# ---------------------------------------------------------------------------
# Speicherplatz
# ---------------------------------------------------------------------------

def test_platz_liefert_plausible_zahlen(tmp_path):
    p = herzschlag.platz(tmp_path)
    assert p["gesamt_gb"] > 0
    assert 0 <= p["frei_prozent"] <= 100
    assert p["frei_gb"] <= p["gesamt_gb"]


def test_die_beiden_schwellen_liegen_richtig_herum():
    """Alarm muss strenger sein als Warnung — andersherum meldete er nie."""
    assert herzschlag.PLATZ_ALARM_PROZENT < herzschlag.PLATZ_WARNUNG_PROZENT


# ---------------------------------------------------------------------------
# Wegwerf-Liste nachziehen
# ---------------------------------------------------------------------------
#
# Die Liste stand von September bis November 2026 still; am 23.11. kam ein
# Konto über einen Anbieter herein, den sie upstream längst führte. Der
# Herzschlag zieht sie seitdem wöchentlich nach (kern/disposable_email.py).

@pytest.fixture
def wegwerf(tmp_path, monkeypatch):
    """Eigenes Verzeichnis für die Kopie, Nachziehen an, Abruf ersetzt."""
    from kern import disposable_email
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "ratslotse.sqlite"))
    monkeypatch.setenv("RATSLOTSE_WEGWERF_NACHZIEHEN", "1")
    abrufe: list[int] = []

    def abruf(url=None):
        abrufe.append(1)
        return "\n".join(sorted(disposable_email.blocked_domains()) + ["neu-dabei.example"])

    monkeypatch.setattr(disposable_email, "abrufen", abruf)
    return {"abrufe": abrufe, "kopie": tmp_path / disposable_email.KOPIE_NAME,
            "stand": disposable_email.stand()}


def test_eine_frische_liste_wird_nicht_abgerufen(wegwerf):
    aus = herzschlag.wegwerf_liste(wegwerf["stand"] + timedelta(days=3))
    assert wegwerf["abrufe"] == [] and aus["nachgezogen"] == 0 and aus["befund"] is None


def test_eine_woche_alte_liste_wird_nachgezogen(wegwerf):
    from kern import disposable_email
    heute = wegwerf["stand"] + timedelta(days=herzschlag.WEGWERF_NACHZIEHEN_TAGE)
    aus = herzschlag.wegwerf_liste(heute)
    assert aus["nachgezogen"] == 1 and aus["dazu"] == 1 and aus["alter_tage"] == 0
    assert wegwerf["kopie"].exists()
    assert disposable_email.stand() == heute
    assert disposable_email.is_disposable("x" + "@" + "neu-dabei.example")  # s. lint_adressen.py


def test_ein_gescheiterter_abruf_meldet_sich_erst_nach_einem_monat(wegwerf, monkeypatch):
    from kern import disposable_email

    def kaputt(url=None):
        raise OSError("Netz weg")

    monkeypatch.setattr(disposable_email, "abrufen", kaputt)
    bald = herzschlag.wegwerf_liste(wegwerf["stand"] + timedelta(days=10))
    assert bald["befund"] is None, "Eine Woche ohne Netz ist noch keine Mail wert"
    spaet = herzschlag.wegwerf_liste(wegwerf["stand"] + timedelta(days=herzschlag.WEGWERF_ALARM_TAGE))
    assert spaet["befund"] and "Netz weg" in spaet["befund"]


def test_ohne_schalter_fragt_der_herzschlag_nicht_ins_netz(wegwerf, monkeypatch):
    """So läuft die Suite (tests/conftest.py) — und ein Rechner ohne Netz."""
    monkeypatch.setenv("RATSLOTSE_WEGWERF_NACHZIEHEN", "0")
    aus = herzschlag.wegwerf_liste(wegwerf["stand"] + timedelta(days=60))
    assert wegwerf["abrufe"] == [] and aus["befund"] is None
