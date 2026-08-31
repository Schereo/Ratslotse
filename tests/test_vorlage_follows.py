"""Verfolgte Vorgänge: der Vergleich, der entscheidet, ob eine Mail rausgeht.

Design 28a/W1. Der heikle Teil ist nicht das Abonnieren, sondern der Diff:
Wer beim Abonnieren den Ist-Stand mitbekommt, darf ihn nicht als Neuigkeit
gemeldet bekommen — und eine einmal gemeldete Station darf nicht beim nächsten
Lauf noch einmal kommen. Beides prüft diese Datei am echten Skript, mit
gestopftem Netzzugriff.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402
from kern.store import Store  # noqa: E402


@pytest.fixture
def dbs(monkeypatch):
    """Beide Datenbanken in einem Temp-Verzeichnis, das Skript darauf gezeigt."""
    tmp = Path(tempfile.mkdtemp())
    ratslotse_db, council_db = tmp / "ratslotse.sqlite", tmp / "council.sqlite"
    monkeypatch.setenv("RATSLOTSE_DB", str(ratslotse_db))
    import scripts.check_vorlage_follows as mod
    monkeypatch.setattr(mod, "RATSLOTSE_DB", ratslotse_db)
    monkeypatch.setattr(mod, "COUNCIL_DB", council_db)
    return mod, ratslotse_db, council_db


def _seed(ratslotse_db: Path, council_db: Path, stations: list[tuple], *, snapshot: list[str]) -> int:
    council = CouncilStore(council_db)
    with council._conn:  # noqa: SLF001 — Testfixture darf ans Innenleben
        council._conn.execute(  # noqa: SLF001
            "INSERT OR REPLACE INTO council_vorlagen(kvonr, template_number, title, fetched_at) "
            "VALUES (700, '26/0001', 'Radweg Haarenufer', '2026-01-01')")
    council.close()

    store = Store(ratslotse_db)
    uid = store.create_web_user("a@test.de", "hash", "user", "active", email_verified=True)
    store.follow_vorlage(uid, 700, template_number="26/0001", title="Radweg Haarenufer",
                         stations=json.dumps(snapshot))
    store.close()
    return uid


def _rows(stations: list[tuple]) -> list[dict]:
    return [{"datum": d, "gremium": g, "result": e, "top": None, "is_public": 1, "ksinr": None}
            for d, g, e in stations]


def _offene_meldungen(ratslotse_db) -> int:
    """Wie viele Meldungen liegen (noch) in der Warteschlange?"""
    s = Store(ratslotse_db)
    try:
        return len(s.due_notifications(1, "2999-01-01"))
    finally:
        s.close()


def _letzte_meldung(ratslotse_db) -> str:
    """Der HTML-Text der zuletzt eingereihten Meldung — auch wenn sie im selben
    Lauf schon zugestellt (und damit als gesendet markiert) wurde."""
    s = Store(ratslotse_db)
    try:
        row = s._conn.execute(
            "SELECT body_html FROM notification_queue ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else ""
    finally:
        s.close()


def test_bekannter_stand_loest_nichts_aus(dbs):
    """Wer gerade abonniert hat, kennt die bisherigen Stationen — keine Mail."""
    mod, ratslotse_db, council_db = dbs
    stationen = [("2026-01-15", "Verkehrsausschuss", "angenommen")]
    _seed(ratslotse_db, council_db, stationen, snapshot=mod.signature(_rows(stationen)))

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", return_value=_rows(stationen)), \
         patch("kern.delivery.deliver_message") as deliver:
        stats = mod.main()

    deliver.assert_not_called()
    assert stats["Benachrichtigungen"] == 0


def test_neue_station_wird_gemeldet_und_dann_nicht_mehr(dbs):
    """Die neue Station geht genau einmal raus — der zweite Lauf ist still."""
    mod, ratslotse_db, council_db = dbs
    alt = [("2026-01-15", "Verkehrsausschuss", "angenommen")]
    neu = alt + [("2026-02-20", "Rat", "beschlossen")]
    _seed(ratslotse_db, council_db, alt, snapshot=mod.signature(_rows(alt)))

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", return_value=_rows(neu)), \
         patch("kern.delivery.deliver_message"):
        stats = mod.main()
    assert stats["Benachrichtigungen"] == 1
    html = _letzte_meldung(ratslotse_db)
    assert "Rat am 20.02.2026 — beschlossen" in html
    # Die schon bekannte Station taucht in der Meldung NICHT auf.
    assert "Verkehrsausschuss" not in html

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", return_value=_rows(neu)), \
         patch("kern.delivery.deliver_message") as deliver2:
        assert mod.main()["Benachrichtigungen"] == 0
    deliver2.assert_not_called()


def test_nachgetragenes_ergebnis_gilt_als_neu(dbs):
    """Genau darauf wartet man: Der Termin stand längst, das Ergebnis fehlte."""
    mod, ratslotse_db, council_db = dbs
    offen = [("2026-02-20", "Rat", None)]
    entschieden = [("2026-02-20", "Rat", "beschlossen")]
    _seed(ratslotse_db, council_db, offen, snapshot=mod.signature(_rows(offen)))

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", return_value=_rows(entschieden)), \
         patch("kern.delivery.deliver_message"):
        assert mod.main()["Benachrichtigungen"] == 1
    assert "beschlossen" in _letzte_meldung(ratslotse_db)


def test_abruf_fehler_meldet_nichts_und_friert_den_stand_nicht_ein(dbs):
    """Ein kaputter Abruf darf keine Meldung erzeugen — und beim nächsten Lauf
    muss die echte Neuigkeit noch ankommen."""
    mod, ratslotse_db, council_db = dbs
    alt = [("2026-01-15", "Verkehrsausschuss", "angenommen")]
    neu = alt + [("2026-02-20", "Rat", "beschlossen")]
    _seed(ratslotse_db, council_db, alt, snapshot=mod.signature(_rows(alt)))
    # Der gespeicherte Stand in der Council-DB entspricht dem alten.
    council = CouncilStore(council_db)
    council.save_beratungen(700, _rows(alt))
    council.close()

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", side_effect=RuntimeError("502")), \
         patch("kern.delivery.deliver_message") as deliver:
        stats = mod.main()
    deliver.assert_not_called()
    assert stats["Abruf-Fehler"] == 1

    with patch.object(mod.stammdaten, "fetch_beratungsfolge", return_value=_rows(neu)), \
         patch("kern.delivery.deliver_message"):
        assert mod.main()["Benachrichtigungen"] == 1
    assert "Rat am 20.02.2026" in _letzte_meldung(ratslotse_db)


def test_gesperrtes_konto_bekommt_keine_post(dbs):
    mod, ratslotse_db, council_db = dbs
    alt = [("2026-01-15", "Verkehrsausschuss", "angenommen")]
    uid = _seed(ratslotse_db, council_db, alt, snapshot=mod.signature(_rows(alt)))
    store = Store(ratslotse_db)
    store.set_web_user_status(uid, "blocked")
    store.close()

    with patch.object(mod.stammdaten, "fetch_beratungsfolge",
                      return_value=_rows(alt + [("2026-02-20", "Rat", "beschlossen")])), \
         patch("kern.delivery.deliver_message") as deliver:
        stats = mod.main()
    deliver.assert_not_called()
    assert stats["Benachrichtigungen"] == 0
    assert _offene_meldungen(ratslotse_db) == 0


def test_label_ohne_ergebnis_sagt_dass_es_noch_aussteht(dbs):
    mod, _, _ = dbs
    assert mod._label("2026-02-20|Rat|") == "Rat am 20.02.2026 (Termin steht, Ergebnis folgt)"
    assert mod._label("|Rat|angenommen") == "Rat — angenommen"
