"""Wann das Protokoll kommt: wenige Tage nach der genehmigenden Sitzung."""
from datetime import date

from council.protokoll_erwartung import protocol_estimate, typical_gap


def test_mit_naechster_sitzung_kommt_es_kurz_danach():
    e = protocol_estimate(date(2026, 11, 2), date(2026, 12, 7), [])
    assert e["basis"] == "next_session"
    assert e["approval_date"] == "2026-12-07"
    assert e["earliest"] == "2026-12-08" and e["latest"] == "2026-12-14"
    assert e["earliest"] <= e["expected"] <= e["latest"]


def test_ohne_kalender_zaehlt_die_jahreszeit_also_die_ferien():
    # Jedes Jahr: Juni-Sitzung, dann Sommerpause bis September (~84 Tage);
    # sonst monatlich.
    tage = []
    for j in (2023, 2024, 2025):
        tage += [date(j, m, 10) for m in (1, 2, 3, 4, 5)] + [date(j, 6, 15), date(j, 9, 7), date(j, 10, 8), date(j, 11, 12)]
    juni = typical_gap(date(2026, 6, 16), tage)
    maerz = typical_gap(date(2026, 3, 10), tage)
    assert juni > 70 and 25 <= maerz <= 35
    e = protocol_estimate(date(2026, 6, 16), None, tage)
    assert e["basis"] == "history" and e["approval_date"] > "2026-08-31"


def test_ohne_geschichte_ein_monat():
    assert typical_gap(date(2026, 3, 1), []) == 30
