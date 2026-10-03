"""Stehende Datenprüfungen (``council/datenpruefung.py``, Plan „Akte“ Phase 6).

Jede Regel hier hat schon einmal eine falsche Antwort erzeugt oder hält fest,
was der Akten-Aufbau garantiert. Geprüft wird vor allem zweierlei: dass der
Fehler gefunden wird — und dass ein sauberer Bestand still bleibt. Eine
Prüfung, die täglich grundlos meldet, wird weggefiltert.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from council import datenpruefung as dp
from tests.akten_testdaten import store_bauen


class FakeStore:
    def __init__(self, beschluesse=()):
        self._beschluesse = list(beschluesse)

    def pruef_hauptbeschluesse(self, seit_datum=None):
        return [b for b in self._beschluesse
                if not seit_datum or b["session_date"] >= seit_datum]


def _beschluss(i, outcome, raw="", summary=None, simple=None, tag="2026-09-01"):
    return {"id": i, "outcome": outcome, "raw_result": raw, "summary": summary,
            "simple_summary": simple, "session_date": tag}


def test_gilt_als_behandelt_als_angenommen_wird_gefunden():
    """Datensatz 19018: Das „einstimmig“ des Verfahrensantrags stand als
    Ergebnis des Inhalts da."""
    store = FakeStore([
        _beschluss(1, "accepted", "- einstimmig - - gilt als behandelt -"),
        _beschluss(2, "rejected", "- mehrheitlich abgelehnt -"),
    ])
    assert dp.ergebnis_gegen_rohtext(store) == [1]


def test_kurzfassung_die_ein_abgelehntes_wie_beschlossen_erzaehlt():
    store = FakeStore([
        _beschluss(1, "rejected", summary="Änderung des Grundsatzbeschlusses zum Bau-Turbo."),
        _beschluss(2, "rejected", summary="Der Rat lehnte den Antrag ab."),
        _beschluss(3, "accepted", summary="Die Satzung wird geändert."),
        _beschluss(4, "postponed", summary="", simple=None),       # leer nennt nichts Falsches
        _beschluss(5, "postponed", summary="Vertagung des Berichts zur Baumschutzsatzung."),
        _beschluss(6, "rejected", summary="Alt.", tag="2025-01-01"),  # vor dem Fenster
    ])
    assert dp.kurzfassung_ohne_ergebnis(store, "2026-06-01") == [(1, "summary")]


def test_antwort_im_feld_eines_ratsbeitrags():
    """Der Fehler vom 30.09.2026 — bei Anfragen ist das Feld richtig."""
    beitraege = [
        {"id": 1, "kind": "speech", "answer": "Sprenger: Dafür ist kein Platz."},
        {"id": 2, "kind": "inquiry", "answer": "Die Verwaltung antwortet schriftlich."},
        {"id": 3, "kind": "speech", "answer": "  "},
    ]
    assert dp.antwort_im_beitrag(beitraege) == [1]


def test_zwei_parteien_aber_nicht_zwei_schreibweisen():
    beitraege = [
        {"ksinr": 1, "speaker": "Behrens", "party": "SPD"},
        {"ksinr": 1, "speaker": "Behrens", "party": "Bündnis 90/Die Grünen"},
        {"ksinr": 1, "speaker": "Beer", "party": "Bündnis 90/Die Grünen"},
        {"ksinr": 1, "speaker": "Beer", "party": "Bündnis90/Grüne"},
        {"ksinr": 1, "speaker": "Krogmann", "party": None},
    ]
    assert dp.partei_widerspruch(beitraege) == [(1, "Behrens", ["Grüne", "SPD"])]


# --------------------------------------------------------------------------- #
# Gegen eine echte Datenbank (Schema wie auf dem Server)
# --------------------------------------------------------------------------- #

@pytest.fixture
def store(tmp_path):
    st = store_bauen(tmp_path)
    from council import matters
    matters.build(st)
    return st


def _ohne_protokoll(store, ksinr, tag):
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (?, 'Sportausschuss', ?, '', '', '')", (ksinr, tag))
    store._conn.execute(
        "INSERT INTO council_agenda_items (id, ksinr, item_number, title) VALUES (?, ?, 'Ö 1', "
        "'Sportstättenbedarf')", (9000 + ksinr, ksinr))
    store._conn.commit()


def test_fehlendes_protokoll_meldet_sich_genau_einmal(store):
    """Eine Stromregel: Die Sitzung fällt an EINEM Tag über die Frist und
    wird an diesem Tag gemeldet — nicht jeden Tag danach wieder."""
    _ohne_protokoll(store, 50, "2026-06-01")
    gemeldet = []
    tag = date(2026, 8, 1)
    while tag < date(2026, 9, 30):
        gestern = tag - timedelta(days=1)
        gemeldet += [(tag, s["ksinr"]) for s in dp.protokoll_verzug(store, gestern, tag)]
        tag += timedelta(days=1)
    assert gemeldet == [(date(2026, 6, 1) + timedelta(days=dp.PROTOKOLL_FRIST_TAGE), 50)]


def test_zweimal_am_selben_tag_meldet_nichts_doppelt(store):
    _ohne_protokoll(store, 50, "2026-06-01")
    heute = date(2026, 6, 1) + timedelta(days=dp.PROTOKOLL_FRIST_TAGE)
    assert len(dp.protokoll_verzug(store, heute - timedelta(days=1), heute)) == 1
    assert dp.protokoll_verzug(store, heute, heute) == []


def _pruefen(store, jetzt):
    return dp.pruefen(store, (jetzt - timedelta(days=1)).replace(tzinfo=None).isoformat(), jetzt)


def test_ein_sauberer_bestand_bleibt_still(store):
    jetzt = datetime.now(timezone.utc)
    erg = _pruefen(store, jetzt)
    assert erg["befunde"] == [], erg["befunde"]
    assert erg["kennzahlen"]["akten_waisen"] == 0


def test_alte_grundakten_melden_sich(store):
    """Der nächtliche Aufbau in check_protocols lief nicht."""
    jetzt = datetime.now(timezone.utc) + timedelta(hours=dp.AKTEN_ALTER_H + 1)
    erg = _pruefen(store, jetzt)
    assert any("Grundakten" in b for b in erg["befunde"])


def test_ohne_grundakten_gibt_es_keine_aktenregel(tmp_path):
    """Vor Phase 1 (oder auf einer frischen DB) ist „keine Akte“ kein Befund."""
    from council.store import CouncilStore

    erg = _pruefen(CouncilStore(tmp_path / "leer.sqlite"), datetime.now(timezone.utc))
    assert erg["befunde"] == []
    assert erg["kennzahlen"]["akten"] == "keine"


def test_eine_neue_geschaeftsordnung_meldet_sich(store):
    """Der neue Rat beschließt seine Geschäftsordnung — dann muss die Fassung
    im Repo nachgezogen werden (council/rules_of_procedure.py)."""
    jetzt = datetime.now(timezone.utc)
    assert _pruefen(store, jetzt)["kennzahlen"]["geschaeftsordnung"] in ("current", "term_ended")
    store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (77, 'Rat', '2026-11-03', '', '', '')")
    store._conn.execute(
        "INSERT INTO council_decisions (id, ksinr, position, title, outcome, kind) VALUES "
        "(7700, 77, 0, 'Geschäftsordnung für den Rat, den Verwaltungsausschuss und die "
        "Ratsausschüsse - Beschluss', 'accepted', 'decision')")
    store._conn.commit()
    erg = _pruefen(store, jetzt)
    assert erg["kennzahlen"]["geschaeftsordnung"] == "superseded"
    assert any("Geschäftsordnung" in b and "7700" in b for b in erg["befunde"])


def test_der_herzschlag_meldet_den_befund(tmp_path, monkeypatch):
    """Ende zu Ende: Ein Verstoß im Rats-Bestand landet in der Mail des
    Herzschlags, mit eigenem Betreff, und die Kennzahlen im Lauf."""
    import kern.alerts
    from council.store import CouncilStore
    from tests.test_herzschlag import herzschlag

    rat = CouncilStore(tmp_path / "c.sqlite")
    rat._conn.execute("INSERT INTO council_sessions (ksinr, committee, session_date, "
                      "session_time, location, fetched_at) VALUES (1, 'Rat', '2026-09-28', "
                      "'', '', '')")
    rat._conn.execute("INSERT INTO council_decisions (id, ksinr, position, title, outcome, "
                      "raw_result, kind) VALUES (7, 1, 0, 'Spielplatz', 'accepted', "
                      "'- einstimmig - - gilt als behandelt -', 'decision')")
    rat._conn.commit()
    rat.close()

    gesendet: list[tuple[str, str]] = []
    monkeypatch.setattr(kern.alerts, "notify_admin",
                        lambda text, **kw: gesendet.append((kw.get("betreff", ""), text)))
    monkeypatch.setattr(herzschlag, "schweigende", lambda store: [])
    monkeypatch.setattr(herzschlag, "platz", lambda pfad: {
        "frei_gb": 100.0, "gesamt_gb": 200.0, "frei_prozent": 50.0})
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "r.sqlite"))
    monkeypatch.setenv("COUNCIL_DB", str(tmp_path / "c.sqlite"))

    ergebnis = herzschlag.main()
    assert ergebnis["daten_ergebnis_widerspricht"] == 1
    assert gesendet and gesendet[-1][0] == "Ratslotse – Datenprüfung"
    assert "Beschluss 7" in gesendet[-1][1]
