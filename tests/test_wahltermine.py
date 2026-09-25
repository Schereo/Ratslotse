"""Der Wächter über den Terminkalender der Stadt.

Er beantwortet zwei Fragen, die am 14.09.2026 beide von Hand beantwortet
werden mussten: Steht eine Wahl im Kalender, die wir nicht kennen? Und hat
die Stichwahl inzwischen eine Wahl-Id?

Kein Test hier fasst das Netz an — der Kalender kommt als Fixture.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))
sys.path.insert(0, str(WURZEL / "web" / "backend"))

import check_wahltermine as job  # noqa: E402

from app.election import elections  # noqa: E402

#: Der Kalender, wie ihn die Stadt am 14.09.2026 auslieferte (gekürzt).
KALENDER = [
    {"date": "13.09.2026", "name": "Kommunalwahlen", "url": "../20260913/03403000/praesentation/"},
    {"date": "22.02.2026", "name": "Bürgerentscheid Aufhebung Baumschutzsatzung", "url": "…"},
    {"date": "23.02.2025", "name": "Bundestagswahl", "url": "…"},
    {"date": "12.09.2021", "name": "Kommunalwahlen", "url": "…"},
]


def test_die_kalender_adresse_wird_abgeleitet_nicht_abgeschrieben(monkeypatch):
    """Aus ``…/20260913/03403000`` wird ``…/03403000/api/termine.json``.

    Zweitgeschrieben stünde die AGS an zwei Stellen — und bei einer zweiten
    Stadt an drei."""
    monkeypatch.delenv("WAHLTERMINE_URL", raising=False)
    assert job.termine_url() == "https://votemanager.kdo.de/03403000/api/termine.json"


def test_die_adresse_laesst_sich_ueberschreiben(monkeypatch):
    monkeypatch.setenv("WAHLTERMINE_URL", "https://example.org/termine.json")
    assert job.termine_url() == "https://example.org/termine.json"


def test_was_wir_kennen_meldet_er_nicht():
    """Der 13.09.2026 steht bei uns als Ratswahl UND OB-Wahl — im Kalender der
    Stadt als ein Eintrag „Kommunalwahlen". Verglichen wird deshalb über das
    DATUM, nicht über den Titel."""
    assert job.unbekannt(KALENDER, heute=date(2026, 9, 14)) == []


def test_eine_neue_wahl_faellt_auf():
    kalender = [*KALENDER, {"date": "11.10.2027", "name": "Landtagswahl", "url": "…"}]
    treffer = job.unbekannt(kalender, heute=date(2026, 9, 14))
    assert [t["date"] for t in treffer] == ["2027-10-11"]
    assert treffer[0]["name"] == "Landtagswahl"


def test_alte_termine_sind_keine_neuigkeit():
    """Der Kalender reicht bis 2006 zurück. „Neu" ist nur, was noch kommt oder
    gerade war — sonst meldete der erste Lauf sechzehn Wahlen."""
    kalender = [{"date": "24.09.2006", "name": "Stichwahl", "url": "…"}]
    assert job.unbekannt(kalender, heute=date(2026, 9, 14)) == []
    # Direkt nach dem Wahltag zählt er noch.
    assert job.unbekannt([{"date": "13.09.2026", "name": "X"}], heute=date(2026, 9, 14)) == []


def test_ein_unbrauchbares_datum_wird_uebersprungen():
    assert job.unbekannt([{"date": "demnächst", "name": "X"}], heute=date(2026, 9, 14)) == []
    assert job.unbekannt([{"name": "ohne Datum"}], heute=date(2026, 9, 14)) == []


# ------------------------------------------------------------------ Wahl-Ids

def _ohne_netz(monkeypatch, eintraege: list[dict] | None):
    """``termin.json`` als Fixture statt aus dem Netz."""
    class Antwort:
        def raise_for_status(self): ...
        def json(self): return {"wahleintraege": eintraege or []}

    class Sitzung:
        headers: dict = {}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **k): return Antwort()

    monkeypatch.setattr(job.requests, "Session", Sitzung)


def test_eine_gefundene_id_wird_gemeldet(monkeypatch):
    """Der Fall vom 27.09.: Die Stadt hat die Stichwahl angelegt."""
    _ohne_netz(monkeypatch, [{"wahl": {"id": 2611, "titel": "Stichwahl des/der Oberbürgermeisters/in"},
                              "gebiet_link": {"id": "ebene_-6360_id_10999"}}])
    treffer = job.fehlende_ids(heute=date(2026, 9, 20))
    assert len(treffer) == 1
    assert treffer[0]["slug"] == "ob-stichwahl-2026"
    assert treffer[0]["wahl_id"] == 2611


def test_ohne_id_bleibt_es_bei_none(monkeypatch):
    """Der Stand vom 14.09.2026 — und der Grund für den ganzen Lauf."""
    _ohne_netz(monkeypatch, [{"wahl": {"id": 913, "titel": "Stadtratswahl"},
                              "gebiet_link": {"id": "ebene_-6361_id_10358"}}])
    treffer = job.fehlende_ids(heute=date(2026, 9, 14))
    assert treffer[0]["wahl_id"] is None
    assert treffer[0]["tage"] == 13


def test_nur_wahlen_mit_suchregel_werden_geprueft(monkeypatch):
    """Eine Wahl mit fester Id hat nichts zu suchen."""
    _ohne_netz(monkeypatch, [])
    geprueft = {t["slug"] for t in job.fehlende_ids(heute=date(2026, 9, 20))}
    mit_regel = {w.slug for w in elections.all().values()
                 if w.source.presentation_id is None and w.source.discover}
    assert geprueft == mit_regel


# ------------------------------------------------------------------ Der ganze Lauf

@pytest.fixture
def merkdatei(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "GESEHEN", tmp_path / "gesehen.json")
    return tmp_path / "gesehen.json"


def test_derselbe_termin_wird_nicht_jede_nacht_gemeldet(monkeypatch, merkdatei):
    gesendet: list[str] = []
    monkeypatch.setattr("kern.alerts.notify_admin",
                        lambda text, **k: gesendet.append(text))
    monkeypatch.setattr(job, "hole", lambda url: [*KALENDER, {"date": "11.10.2027", "name": "Landtagswahl"}])
    _ohne_netz(monkeypatch, [])
    # Hier geht es um den Kalender, nicht um die Id-Suche: Die läuft sonst
    # gegen die ECHTEN Wahlen und das heutige Datum — zwei Tage vor der
    # OB-Stichwahl (25.09.2026) meldete sie den Fehlalarm „noch keine Wahl-Id“
    # in beiden Läufen, und das mit Absicht jede Nacht.
    monkeypatch.setattr(job, "fehlende_ids", lambda heute=None: [])

    erst = job.main()
    assert erst["unbekannt"] == 1 and erst["gemeldet"] >= 1
    assert "Landtagswahl" in gesendet[0]

    gesendet.clear()
    zweit = job.main()
    assert zweit["unbekannt"] == 1, "gefunden wird er weiter"
    assert not gesendet, "gemeldet wird er nur einmal"


def test_ein_kalender_ohne_antwort_loest_keinen_alarm_aus(monkeypatch, merkdatei):
    """Der Kalender der Stadt ist kein Dienst, den wir betreiben. Bleibt er
    weg, ist das keine Nachricht wert — die Job-Ampel merkt es ohnehin."""
    gesendet: list[str] = []
    monkeypatch.setattr("kern.alerts.notify_admin", lambda text, **k: gesendet.append(text))

    def kaputt(url):
        raise job.requests.RequestException("kaputt")

    monkeypatch.setattr(job, "hole", kaputt)
    ergebnis = job.main()
    assert ergebnis["gemeldet"] == 0 and ergebnis["fehler"] == "RequestException"
    assert not gesendet


def test_der_job_steht_in_der_registry():
    """Sonst schlägt die Überfällig-Ampel im Admin-Panel nie an."""
    from kern.jobs import JOBS

    eintrag = next((j for j in JOBS if j["key"] == "check_wahltermine"), None)
    assert eintrag is not None, "check_wahltermine fehlt in kern/jobs.py"
    assert eintrag["max_age_h"] >= 24
