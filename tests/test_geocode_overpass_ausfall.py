"""Ein unerreichbarer Straßen-Dienst muss sich wie ein Ausfall lesen.

**Der Fall.** Am 03.09.2026 lief ein Reparaturlauf über 513 Straßen und
meldete ``located=513, missed=2, failed=0``. Overpass war von beiden VPS aus
gar nicht erreichbar (Errno 101 über das NAT-Gateway), der Rückfall auf
Nominatim stumm — 498 Straßen bekamen ein einzelnes Segment statt der ganzen
Straße und damit nur einen Teil ihrer Ortsbereiche. Der Lauf sah erfolgreich
aus. Diese Tests halten die drei Stellen fest, die das künftig verraten: die
Erreichbarkeitsprobe, die Kennzahlen und die Meldung an den Admin.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import geocode_entities as ge  # noqa: E402


def _probe_zuruecksetzen():
    ge._overpass_bereit = None
    ge.overpass_ausfaelle.update({"fehler": 0, "ohne_treffer": 0,
                                  "nicht_erreichbar": 0, "strassen_versucht": 0})


def test_probe_misst_nur_einmal(monkeypatch):
    """Die Probe ersetzt 513 vergebliche Versuche durch EINE Messung."""
    _probe_zuruecksetzen()
    versuche = {"n": 0}

    def kaputt(*a, **k):
        versuche["n"] += 1
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(ge.requests, "post", kaputt)
    assert ge.overpass_bereit() is False
    assert ge.overpass_bereit() is False
    assert versuche["n"] == 1


def test_ausfall_landet_in_den_kennzahlen(monkeypatch):
    """Nicht der Rückfall ist das Problem, sondern sein Verschweigen."""
    _probe_zuruecksetzen()
    monkeypatch.setattr(ge.requests, "post",
                        lambda *a, **k: (_ for _ in ()).throw(OSError(101, "unreachable")))
    monkeypatch.setattr(ge, "nominatim", lambda name: (53.1, 8.2, None))

    assert ge.geocode("Tweelbäker Tredde", "street") == (53.1, 8.2, None)
    assert ge.overpass_ausfaelle["strassen_versucht"] == 1
    assert ge.overpass_ausfaelle["nicht_erreichbar"] == 1
    # Ein Ort, der keine Straße ist, zählt nicht mit — er will kein Overpass.
    ge.geocode("Kulturzentrum PFL", "building")
    assert ge.overpass_ausfaelle["strassen_versucht"] == 1


def test_totalausfall_wird_gemeldet(monkeypatch):
    """Alle Straßen verloren → Mail an den Admin. Sonst nicht: An einem Tag
    ohne neue Straße soll niemand geweckt werden."""
    from scripts import geocode_decision_locations as gdl

    meldungen = []
    monkeypatch.setattr(gdl, "notify_admin",
                        lambda text, **kw: meldungen.append(text))

    _probe_zuruecksetzen()
    gdl.overpass_ausfaelle.update({"strassen_versucht": 7, "nicht_erreichbar": 7})
    gdl._melde_overpass_ausfall(offen=415)
    assert len(meldungen) == 1
    assert "7 von 7" in meldungen[0] and "415" in meldungen[0]

    # Teilweise geglückt: kein Alarm, die Kennzahlen tragen es.
    meldungen.clear()
    gdl.overpass_ausfaelle.update({"strassen_versucht": 7, "nicht_erreichbar": 3,
                                   "fehler": 0})
    gdl._melde_overpass_ausfall(offen=415)
    # Gar nichts zu tun gewesen: auch kein Alarm.
    gdl.overpass_ausfaelle.update({"strassen_versucht": 0, "nicht_erreichbar": 0})
    gdl._melde_overpass_ausfall(offen=415)
    assert meldungen == []
