"""Die Tagesordnungs-Mail nimmt den Kartentext — und zieht ihn notfalls nach.

Warum das nötig ist: Die Mail geht raus, sobald eine Tagesordnung erscheint.
Der Kartentext-Lauf (``scripts/social_kartentexte.py``) kommt am nächsten
Morgen — und weil der Mail-Block gecacht wird, stünde bis dahin dauerhaft die
titelbasierte Kurzfassung darin (Tims Auftrag 30.08.2026).
"""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

from council.store import CouncilStore


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _check_committees():
    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_kartentext", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sitzung(store, ksinr=1, tage=3):
    tag = (date.today() + timedelta(days=tage)).isoformat()
    store._conn.execute(
        "INSERT OR REPLACE INTO council_sessions (ksinr, committee, session_date, "
        "session_time, location, fetched_at) VALUES (?, 'Rat', ?, '18:00', 'PFL', 'x')",
        (ksinr, tag))
    store._conn.commit()


def _punkt(store, ksinr, nummer, titel, kvonr=None):
    store._conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public, kvonr) "
        "VALUES (?, ?, ?, 1, ?)", (ksinr, nummer, titel, kvonr))
    if kvonr:
        store._conn.execute(
            "INSERT OR REPLACE INTO council_vorlagen (kvonr, template_number, title, raw_text, "
            "fetched_at) VALUES (?, '26/0592', ?, 'Sachverhalt: 8,6 Hektar.', 'x')",
            (kvonr, titel))
    store._conn.commit()


def test_eine_sitzung_gezielt_und_ohne_zeitfenster(store):
    """Mit ``ksinr`` zählt nur diese Sitzung — und ihr Termin darf weiter als
    die drei Wochen des Nachtlaufs entfernt liegen: Tagesordnungen erscheinen
    manchmal früher, und die Mail geht trotzdem sofort raus."""
    _sitzung(store, ksinr=1, tage=60)
    _sitzung(store, ksinr=2, tage=3)
    _punkt(store, 1, "Ö 5", "Bebauungsplan 837", kvonr=101)
    _punkt(store, 2, "Ö 5", "Ein Punkt der anderen Sitzung", kvonr=102)

    offen = store.agenda_items_needing_social_text(ksinr=1)
    assert [(p["ksinr"], p["item_number"]) for p in offen] == [(1, "Ö 5")]
    # Der Nachtlauf sieht die Sitzung in 60 Tagen weiterhin nicht.
    assert [p["ksinr"] for p in store.agenda_items_needing_social_text()] == [2]


def test_die_mail_nimmt_den_kartentext_und_faellt_sonst_zurueck(store, monkeypatch):
    """Der Kartentext schlägt die Kurzfassung — Punkt für Punkt. Wo keiner
    steht (der Kritiker verwirft, oder es gab kein Material), bleibt die
    Kurzfassung stehen: eine dröge Zeile ist besser als keine."""
    modul = _check_committees()
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Bebauungsplan 837", kvonr=101)
    _punkt(store, 1, "Ö 6", "Ein Punkt ohne Vorlage")
    store.save_social_text(1, "Ö 5", "Geplant ist ein Wohngebiet auf 8,6 Hektar.", "vorlage")
    # Kein Nachziehen im Test: Der LLM-Weg ist anderswo geprüft.
    monkeypatch.setattr(modul.social_text, "schreibe_fehlende",
                        lambda *a, **kw: (0, 0))

    html = modul._aufzaehlung(store, 1, [
        {"number": "Ö 5", "summary": "Der Rat berät über den Bebauungsplan 837."},
        {"number": "Ö 6", "summary": "Der Rat berät über einen Punkt."},
    ])
    assert "Geplant ist ein Wohngebiet auf 8,6 Hektar." in html
    assert "Der Rat berät über den Bebauungsplan 837." not in html
    assert "Der Rat berät über einen Punkt." in html


def test_der_dringlichkeitsantrag_heisst_in_der_mail_wie_er_heisst(store, monkeypatch):
    """„DZT 1" ist eine Nummer, die der Ratslotse selbst vergibt — im
    Ratsinformationssystem sucht man sie vergeblich. In der Mail steht
    deshalb, was der Punkt IST."""
    modul = _check_committees()
    _sitzung(store)
    monkeypatch.setattr(modul.social_text, "schreibe_fehlende", lambda *a, **kw: (0, 0))

    html = modul._aufzaehlung(store, 1, [
        {"number": "DZT 1", "summary": "Beantragt ist eine Untersuchung der Flugplatzbäke."},
        {"number": "Ö 5", "summary": "Der Rat berät über den Bebauungsplan."},
    ])
    assert "<b>Dringlichkeitsantrag</b>: Beantragt ist" in html
    assert "DZT 1" not in html
    assert "<b>Ö 5</b>" in html


def test_ein_fehlschlag_beim_nachziehen_kostet_die_mail_nichts(store, monkeypatch):
    """Anreicherung ist Kür. Reißt der LLM-Lauf, geht die Mail mit dem raus,
    was schon in der Datenbank steht."""
    modul = _check_committees()
    _sitzung(store)
    store.save_social_text(1, "Ö 5", "Geplant ist ein Wohngebiet.", "vorlage")

    def kaputt(*a, **kw):
        raise RuntimeError("OpenRouter 502")

    monkeypatch.setattr(modul.social_text, "schreibe_fehlende", kaputt)
    html = modul._aufzaehlung(store, 1, [{"number": "Ö 5", "summary": "Kurzfassung."}])
    assert "Geplant ist ein Wohngebiet." in html
