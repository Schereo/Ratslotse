"""Kennzahlen der Ausschuss-Abos: nächste Sitzung + Beschlüsse im Jahr.

Die Abo-Seite zeigt je Gremium einen Termin und eine Zahl. Beides muss
dieselbe Menge meinen wie die Seiten, auf die sie verlinkt — sonst nennt das
Abo einen Termin, den die Sitzungsliste nicht kennt, oder eine Beschlusszahl,
die die Beschlussliste nicht hergibt. Genau das sichern diese Tests ab.

Der Regressionsschutz für die Antwortform von ``/api/council/committees``
steht in ``test_backend_api.py`` — dort hängt die App schon an ihren
Wegwerf-Datenbanken.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from council.scraper import AgendaItem, CouncilSession, ScheduledSession
from council.store import CouncilStore


def _tag(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _sitzung(store: CouncilStore, ksinr: int, gremium: str, tag: str, zeit: str = "17:00"):
    store.save_session(CouncilSession(
        ksinr=ksinr, committee=gremium, session_date=tag, session_time=zeit,
        location="Alte Fleiwa",
        agenda_items=[AgendaItem("Ö 1", "Irgendein Punkt")],
    ))


def _beschluss(store: CouncilStore, ksinr: int, position: int, kind: str = "decision"):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome) "
            "VALUES (?, ?, ?, ?, ?, 'angenommen')",
            (ksinr, position, kind, str(position), f"Beschluss {position}"),
        )


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


# ---- nächste Sitzung -------------------------------------------------------

def test_naechster_termin_kommt_auch_aus_dem_kalender(store):
    """Terminiert, aber ohne Tagesordnung: SessionNet verlinkt eine Sitzung
    erst, wenn ihre Tagesordnung online ist. Fiele der Kalender hier raus,
    zeigte das Abo den übernächsten Termin — und läge Wochen daneben."""
    _sitzung(store, 1, "Verkehrsausschuss", _tag(30))
    store.replace_scheduled_sessions([
        ScheduledSession(committee="Verkehrsausschuss", session_date=_tag(10),
                         session_time="16:00", location="PFL"),
    ])

    assert store.naechste_sitzung_je_gremium()["Verkehrsausschuss"] == {
        "session_date": _tag(10), "session_time": "16:00",
    }


def test_echte_sitzung_gewinnt_wenn_sie_frueher_liegt(store):
    _sitzung(store, 1, "Verkehrsausschuss", _tag(5), zeit="15:00")
    store.replace_scheduled_sessions([
        ScheduledSession(committee="Verkehrsausschuss", session_date=_tag(20),
                         session_time="16:00", location="PFL"),
    ])

    assert store.naechste_sitzung_je_gremium()["Verkehrsausschuss"] == {
        "session_date": _tag(5), "session_time": "15:00",
    }


def test_vergangene_sitzungen_sind_keine_naechsten(store):
    """Gestern ist kein Termin — ein Gremium, das nur Vergangenes hat, taucht
    gar nicht auf (der Aufrufer schreibt dann „kein Termin")."""
    _sitzung(store, 1, "Kulturausschuss", _tag(-3))
    _sitzung(store, 2, "Kulturausschuss", _tag(-1))
    store.replace_scheduled_sessions([
        ScheduledSession(committee="Jugendhilfeausschuss", session_date=_tag(-2),
                         session_time="16:00", location="PFL"),
    ])

    assert store.naechste_sitzung_je_gremium() == {}


def test_termine_werden_je_gremium_getrennt(store):
    _sitzung(store, 1, "Verkehrsausschuss", _tag(12))
    _sitzung(store, 2, "Verkehrsausschuss", _tag(4))
    _sitzung(store, 3, "Kulturausschuss", _tag(8))

    assert store.naechste_sitzung_je_gremium() == {
        "Verkehrsausschuss": {"session_date": _tag(4), "session_time": "17:00"},
        "Kulturausschuss": {"session_date": _tag(8), "session_time": "17:00"},
    }


def test_termin_ohne_uhrzeit_meldet_keine_leere_zeit(store):
    """``session_time`` ist NOT NULL und im Zweifel leer — als "" käme im
    Frontend „um  Uhr" heraus, deshalb None. Und der Termin mit Uhrzeit darf
    am selben Tag nicht vom Eintrag ohne verdeckt werden."""
    _sitzung(store, 1, "Kulturausschuss", _tag(6), zeit="")
    store.replace_scheduled_sessions([
        ScheduledSession(committee="Jugendhilfeausschuss", session_date=_tag(6),
                         session_time="", location="PFL"),
        ScheduledSession(committee="Jugendhilfeausschuss", session_date=_tag(6),
                         session_time="18:00", location="PFL"),
    ])

    naechste = store.naechste_sitzung_je_gremium()
    assert naechste["Kulturausschuss"] == {"session_date": _tag(6), "session_time": None}
    assert naechste["Jugendhilfeausschuss"] == {"session_date": _tag(6), "session_time": "18:00"}


# ---- Beschlusszahl ---------------------------------------------------------

def test_beschlusszahl_grenzt_am_stichtag_ab_und_trennt_gremien(store):
    _sitzung(store, 1, "Verkehrsausschuss", "2026-01-15")
    _sitzung(store, 2, "Verkehrsausschuss", "2025-11-20")   # vor dem Stichtag
    _sitzung(store, 3, "Kulturausschuss", "2026-01-01")     # genau am Stichtag
    for pos in (1, 2, 3):
        _beschluss(store, 1, pos)
    _beschluss(store, 2, 1)
    _beschluss(store, 3, 1)

    assert store.beschlusszahl_je_gremium("2026-01-01") == {
        "Verkehrsausschuss": 3, "Kulturausschuss": 1,
    }
    # Ohne Beschluss im Zeitraum fehlt das Gremium schlicht.
    assert store.beschlusszahl_je_gremium("2027-01-01") == {}


def test_beschlusszahl_zaehlt_keine_aenderungsantraege(store):
    """``kind='subvote'`` hängt als Kontext am Ursprungsbeschluss und ist in
    der Beschlussliste kein eigener Treffer (Design 23a). Zählte das Abo sie
    mit, stünde neben dem Gremium eine höhere Zahl als auf der Seite dahinter
    — deshalb muss die Zahl zu ``count_decisions`` passen."""
    _sitzung(store, 1, "Verkehrsausschuss", "2026-02-02")
    _beschluss(store, 1, 1)
    _beschluss(store, 1, 2, kind="subvote")

    assert store.beschlusszahl_je_gremium("2026-01-01") == {"Verkehrsausschuss": 1}
    assert store.count_decisions(committee="Verkehrsausschuss", date_from="2026-01-01") == 1
