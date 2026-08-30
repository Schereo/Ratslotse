"""Fertig-Meldung der „Gründlichen Recherche" (Push, wenn niemand zusieht).

Die Recherche läuft server-seitig weiter, wenn die App weggelegt wird — genau
dafür gibt es die Meldung. Sie ist die Quittung einer Handlung, kein
Ratsvorgang: Sie geht an der Warteschlange aus 30a vorbei (Nachtruhe,
zwei am Tag) und fragt nur den Aus-Schalter.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from kern import delivery  # noqa: E402
from kern.store import Store  # noqa: E402
from app import deepresearch as DEEP  # noqa: E402


# ---- Text der Meldung ----------------------------------------------------

def test_melde_text_nennt_die_frage():
    titel, text = DEEP._melde_text("fertig", "Wie ist der Stand beim Stadionneubau?")
    assert titel == "Deine Recherche ist fertig"
    assert "Stadionneubau" in text
    # Der Fehlschlag nimmt der Meldung die Sorge ums Kontingent.
    _, fehler = DEEP._melde_text("fehler", "Wie ist der Stand?")
    assert "Tageskontingent" in fehler
    assert DEEP._melde_text("teilbericht", "Was ist mit dem Hafen?")[0] == "Teilbericht ist fertig"


def test_melde_text_kuerzt_an_der_wortgrenze():
    lang = "Was hat der Rat zum Thema " + "Verkehrsentwicklung " * 20 + "entschieden?"
    _, text = DEEP._melde_text("fertig", lang)
    assert len(text) <= 125
    assert "Verkehrsentwicklung …" in text  # kein abgeschnittenes Wort


# ---- Zustellweg ----------------------------------------------------------

def _owner(channel: str = "push", tokens: list[dict] | None = None) -> dict:
    return {"owner_id": 1, "delivery_channel": channel, "email": "a@b.de",
            "push_tokens": tokens if tokens is not None else [{"token": "t1", "platform": "ios"}]}


def test_push_quittung_ignoriert_den_kanal_aber_nicht_das_aus(monkeypatch):
    gesendet = []
    monkeypatch.setattr(delivery, "push_ready", lambda: True)
    monkeypatch.setattr(delivery, "_send_push_and_prune",
                        lambda d, t, b, data: gesendet.append((d, t, b, data)))

    # „nur E-Mail" meinte Neuigkeiten aus dem Rat, nicht die eigene Quittung.
    assert delivery.push_quittung(_owner("email"), "T", "B", "/council") is True
    assert delivery.push_quittung(_owner("both"), "T", "B", "/council") is True
    assert len(gesendet) == 2
    assert gesendet[0][3] == {"url": "/council"}

    # Wer alles abgeschaltet hat, hört auch hier nichts.
    assert delivery.push_quittung(_owner("off"), "T", "B", "/council") is False
    # Ohne Gerät (reiner Web-Nutzer) gibt es nichts zu melden.
    assert delivery.push_quittung(_owner("push", []), "T", "B", "/council") is False
    assert len(gesendet) == 2


# ---- Wann gemeldet wird --------------------------------------------------

@pytest.fixture
def welt(tmp_path, monkeypatch):
    """Konto mit Gerät + ein fertiger Job in der DB; Push wird mitgeschrieben."""
    db = str(tmp_path / "ratslotse.sqlite")
    store = Store(db)
    uid = store.create_web_user("a@b.de", "x", status="active")
    store.add_push_token(uid, "t1", "ios")
    job_id = store.deep_job_anlegen(uid, "Wie ist der Stand beim Stadionneubau?")
    store.deep_job_update(job_id, "fertig", bericht="…")
    store.close()

    gesendet: list[tuple] = []
    monkeypatch.setattr(delivery, "push_ready", lambda: True)
    monkeypatch.setattr(delivery, "_send_push_and_prune",
                        lambda d, t, b, data: gesendet.append((t, b, data)))
    job = DEEP.DeepJob(id=job_id, user_id=uid, frage="Wie ist der Stand beim Stadionneubau?")
    return db, job, gesendet, uid


def test_meldung_geht_raus_wenn_niemand_zusieht(welt):
    db, job, gesendet, _ = welt
    DEEP._melden_jetzt(job, db, "fertig")
    assert len(gesendet) == 1
    titel, text, data = gesendet[0]
    assert titel == "Deine Recherche ist fertig"
    assert "Stadionneubau" in text
    # Antippen muss auf der Frage-Seite landen — dort holt der Client den
    # ungesehenen Bericht von selbst zurück.
    assert data["url"].startswith("/council")


def test_keine_meldung_solange_jemand_am_job_haengt(welt):
    db, job, gesendet, _ = welt
    job.zuschauer = 1
    DEEP._melden_jetzt(job, db, "fertig")
    assert gesendet == []


def test_keine_meldung_wenn_der_bericht_schon_gesehen_wurde(welt):
    db, job, gesendet, uid = welt
    store = Store(db)
    store.deep_job_gesehen(job.id, uid)
    store.close()
    DEEP._melden_jetzt(job, db, "fertig")
    assert gesendet == []


def test_melden_meldet_nur_einmal(welt, monkeypatch):
    db, job, gesendet, _ = welt
    # Timer sofort ausführen, statt zwölf Sekunden zu warten.
    monkeypatch.setattr(DEEP, "MELDE_VERZUG", 0)
    DEEP.melden(job, db, "fertig")
    DEEP.melden(job, db, "fertig")
    import time
    time.sleep(0.3)
    assert len(gesendet) == 1


def test_gestoppter_job_meldet_sich_nicht(welt):
    db, job, gesendet, _ = welt
    DEEP._gestoppt(job, db)
    import time
    time.sleep(0.1)
    assert gesendet == [], "Ein Stopp war eine bewusste Handlung — keine Rückmeldung nötig"
