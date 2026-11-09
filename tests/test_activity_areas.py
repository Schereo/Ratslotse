"""Aktive Minuten und besuchte Bereiche je Konto (Tims Entscheidung 09.11.2026).

Das Admin-Panel zeigte je Konto nur die Zahl der API-Anfragen pro Tag; daraus
ließ sich weder lesen, wie lange jemand da war, noch was er gemacht hat. Jetzt
zählt ``user_activity`` dazu ``minutes`` und ``area:<bereich>`` — und die Tests
halten fest, was dabei NICHT gespeichert wird.
"""
from __future__ import annotations

import time

from kern import activity_areas, seitenaufrufe


def test_jeder_bereich_besteht_aus_bekannten_seiten():
    """Ein Muster, das es nicht gibt, würde nie getroffen — der Bereich bliebe
    still leer und sähe aus wie „nie besucht"."""
    for key, _label, routen in activity_areas.AREAS:
        assert routen, key
        for r in routen:
            basis = r.split("?")[0]
            assert r in seitenaufrufe.ROUTEN or (basis == "/council" and "?tab=" in r), r


def test_eine_seite_gehoert_zu_hoechstens_einem_bereich():
    alle = [r for _k, _l, routen in activity_areas.AREAS for r in routen]
    assert len(alle) == len(set(alle))


def test_die_query_faellt_weg_und_unbekanntes_zaehlt_nicht():
    assert activity_areas.area_for("/council/decision?id=8525") == "decisions"
    assert activity_areas.area_for("/council?tab=sessions") == "sessions"
    assert activity_areas.area_for("/haushalt/schulden") == "budget"
    assert activity_areas.area_for("/fragen?q=geheim") == "questions"
    # Öffentliche und unbekannte Seiten gehören zu keinem Bereich.
    assert activity_areas.area_for("/impressum") is None
    assert activity_areas.area_for("/irgendwas/erfunden") is None


def test_minuten_zaehlen_einmal_je_minute(monkeypatch):
    from web.backend.app import deps

    gezaehlt: list[str] = []

    class FakeStore:
        def record_activity(self, owner_id, feature, client, **k):
            gezaehlt.append(feature)
            return True

    deps.sitzungen_vergessen()
    jetzt = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: jetzt[0])
    for t in (1000.0, 1010.0, 1030.0, 1065.0, 1070.0, 1200.0):
        jetzt[0] = t
        deps._sitzung_zaehlen(FakeStore(), 7, "web")
    # Geschrieben bei 1000, 1065 und 1200 — drei Minuten mit Aktivität.
    assert gezaehlt.count("minutes") == 3
    assert gezaehlt.count("session") == 3
    deps.sitzungen_vergessen()
