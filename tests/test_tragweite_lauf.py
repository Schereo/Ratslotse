"""Der Tragweite-Block in `check_committees` — der stille Ausfall vom 16.–19.08.2026.

`council_store.close()` stand VOR diesem Block. Jeder Zugriff warf
`ProgrammingError: Cannot operate on a closed database`, ein `except Exception`
schluckte ihn, und der Lauf meldete `status: ok` mit „Tragweite bewertet: 0" —
vier Tage lang, ohne dass etwas anschlug. Beide Hälften werden hier festgehalten:
Der Store muss offen sein, UND ein Totalausfall muss als Fehler herauskommen.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest


def _modul(tmp_path: Path):
    """`check_committees` frisch laden und auf Wegwerf-Datenbanken zeigen.

    ``NWZ_DB``/``COUNCIL_DB`` sind dort feste Modul-Konstanten (aus ``ROOT``),
    KEINE Umgebungsvariablen — sie müssen nach dem Import gesetzt werden, sonst
    liefe der Test gegen die echte Datenbank des Entwicklungsrechners.
    """
    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_tragweite", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    modul.NWZ_DB = tmp_path / "nwz.sqlite"
    modul.COUNCIL_DB = tmp_path / "council.sqlite"
    return modul


class _StummerScraper:
    """Kein Netz: Der Lauf soll direkt beim Tragweite-Block ankommen."""

    def fetch_committee_list(self):
        return []

    def upcoming_calendar(self, months_ahead=3):
        return [], []


def _seede_punkt(db: Path) -> None:
    """Eine kommende Sitzung mit einem bewertbaren Punkt — ohne ihn liefert
    `agenda_items_needing_impact` nichts und der Block hat nichts zu tun."""
    tag = (date.today() + timedelta(days=2)).isoformat()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time,"
        " location, fetched_at) VALUES (1, 'Verkehrsausschuss', ?, '17:00', 'Saal', '')",
        (tag,))
    conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, vorlage_nr,"
        " kvonr, is_public) VALUES (1, 'Ö 5', 'VBN-Tarifanpassung 2027 - Beschluss',"
        " '26/0622', 30078, 1)")
    conn.commit()
    conn.close()


def _vorbereiten(tmp_path, monkeypatch):
    modul = _modul(tmp_path)
    monkeypatch.setattr(modul, "CouncilScraper", _StummerScraper)
    # Die Tabellen entstehen beim ersten CouncilStore(); danach seeden.
    from council.store import CouncilStore
    CouncilStore(tmp_path / "council.sqlite").close()
    _seede_punkt(tmp_path / "council.sqlite")
    return modul


def test_der_store_ist_beim_bewerten_noch_offen(tmp_path, monkeypatch):
    """Der eigentliche Regressionstest: Läuft der Block gegen einen
    geschlossenen Store, kommt hier 0 heraus statt 1."""
    modul = _vorbereiten(tmp_path, monkeypatch)
    import council.impact as impact

    gesehen: list[int] = []

    def _bewerten(items):
        gesehen.append(len(items))
        return [(it["id"], 40, "Fahrpreise steigen.") for it in items]

    monkeypatch.setattr(impact, "rate_agenda_batch", _bewerten)

    kennzahlen = modul.main()
    assert gesehen == [1], "der Block hat den Punkt gar nicht erst gesehen"
    assert kennzahlen["Tragweite bewertet"] == 1
    assert kennzahlen["Tragweite offen"] == 1

    # Und der Wert ist wirklich in der Datenbank gelandet.
    conn = sqlite3.connect(tmp_path / "council.sqlite")
    assert conn.execute("SELECT impact FROM agenda_item_impact").fetchone()[0] == 40
    conn.close()


def test_null_von_n_bewertet_meldet_sich_als_fehler(tmp_path, monkeypatch):
    """Offene Punkte, aber kein einziger bewertet: Das ist ein Ausfall und
    muss `run_guarded` erreichen — sonst steht wieder tagelang „ok" im Panel."""
    modul = _vorbereiten(tmp_path, monkeypatch)
    import council.impact as impact

    monkeypatch.setattr(impact, "rate_agenda_batch", lambda items: [])

    with pytest.raises(RuntimeError, match="0 von 1"):
        modul.main()


def test_ohne_offene_punkte_bleibt_der_lauf_still(tmp_path, monkeypatch):
    """Kein Fehlalarm, wenn es schlicht nichts zu bewerten gibt — sonst wäre
    jede ruhige Woche eine Alarm-Mail."""
    modul = _modul(tmp_path)
    monkeypatch.setattr(modul, "CouncilScraper", _StummerScraper)
    import council.impact as impact

    monkeypatch.setattr(impact, "rate_agenda_batch", lambda items: [])

    kennzahlen = modul.main()
    assert kennzahlen["Tragweite offen"] == 0
    assert kennzahlen["Tragweite bewertet"] == 0
