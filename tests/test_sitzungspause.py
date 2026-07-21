"""Tests für die Sitzungspausen-Erkennung (reine Datumslogik, kein Netz/DB).

Grundlage: Die Stadt pausiert in den Schulferien (offizielle Aussage auf
oldenburg.de); Ferienfenster sind die vom Nds. Kultusministerium festgelegten
Termine. Sonderfall Kommunalwahl 2026 (Wahltag 13.09., Periodenende 31.10.).
"""
from __future__ import annotations

from datetime import date

from council.sitzungspause import FERIEN, naechste_ferien, resume_hint, sitzungspause


def test_sommerpause_2026_ohne_termine():
    p = sitzungspause(date(2026, 7, 21), None)
    assert p["active"] and p["label"] == "Sommerpause"
    assert p["until"] == "2026-08-12"
    assert "12.8.2026" in p["note"]
    # 2026er-Besonderheit: Der Wahl-Ausblick gehört in die Sommerpause-Erklärung.
    assert "Kommunalwahl" in p["note"] and "13.9.2026" in p["note"]


def test_ferien_mit_bekanntem_termin_zeigen_weiter_gehts():
    p = sitzungspause(date(2026, 7, 21), date(2026, 9, 1))
    assert p["active"] and p["label"] == "Sommerpause"
    assert p["next_session_date"] == "2026-09-01"
    assert "1.9.2026" in p["note"]


def test_wahl_uebergang_nach_den_sommerferien():
    p = sitzungspause(date(2026, 9, 20), None)
    assert p["active"] and p["label"] == "Kommunalwahl & Ratswechsel"
    assert "31.10.2026" in p["note"] and "November" in p["note"]


def test_herbstferien_2026_liegen_im_wahlfenster_ferien_gewinnen():
    # In den Herbstferien 2026 gilt das Ferien-Banner (mit Bis-Datum) …
    p = sitzungspause(date(2026, 10, 15), None)
    assert p["label"] == "Herbstpause" and p["until"] == "2026-10-24"


def test_normalbetrieb_kein_banner():
    p = sitzungspause(date(2026, 2, 10), date(2026, 2, 16))
    assert p["active"] is False and p["note"] == ""


def test_weihnachtspause_jahresuebergang():
    p = sitzungspause(date(2026, 12, 28), None)
    assert p["label"] == "Weihnachtspause" and p["until"] == "2027-01-09"


def test_keine_termine_ausserhalb_bekannter_fenster_bleibt_ehrlich():
    # Nach Tabellen-Ende bzw. außerhalb aller Fenster: nichts behaupten,
    # nur den Fakt nennen (Scraper-Ausfall darf nicht als „Pause" erscheinen).
    p = sitzungspause(date(2028, 3, 1), None)
    assert p["active"] and p["label"] == "Keine Termine veröffentlicht"
    assert p["until"] is None
    assert "keine kommenden" in p["note"]


def test_ferienfenster_konsistent_und_sortiert():
    assert all(von < bis for von, bis, _ in FERIEN)
    assert FERIEN == sorted(FERIEN)
    # Sommerfenster decken die empirischen DB-Lücken (Juli/August) ab.
    sommer = [f for f in FERIEN if f[2] == "Sommerpause"]
    assert {f[0].year for f in sommer} == {2026, 2027}


def test_resume_hint_und_naechste_ferien():
    assert resume_hint(date(2026, 7, 21)) == date(2026, 8, 13)
    assert resume_hint(date(2026, 9, 20)) is None
    von, bis, name = naechste_ferien(date(2026, 9, 20))
    assert name == "Herbstpause" and von == date(2026, 10, 12)
