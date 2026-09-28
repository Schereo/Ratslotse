"""Mails über Themen-Treffer nur für Aktuelles (``topic_intel.meldestichtage``).

Anlass, 27.09.2026: Ein Konto bekam „Diese Woche: 13 Beschlüsse zu deinen
Themen" mit dem Masterplan Fliegerhorst von 2019 und „Neu zu Klimaschutz" mit
dem Bahnhofsvorplatz vom 8. Juni. Beide stammten aus Protokollen, die der
Sitzungs-Nachlauf am 23.09. nachgetragen hatte.
"""
from __future__ import annotations

from datetime import date

from council.abendmeldungen import wochenueberblick
from council.scraper import CouncilSession
from council.store import CouncilStore
from council.topic_intel import MELDEFENSTER_TAGE, meldestichtage
from kern import notify
from kern.store import Store

SONNTAG = date(2026, 9, 27)


def _beschluss(council: CouncilStore, ksinr: int, sitzung: str, protokoll: str | None,
               titel: str) -> int:
    council.save_session(CouncilSession(ksinr, "Verkehrsausschuss", sitzung, "17:00", "PFL"))
    with council._conn:
        council._insert_decision(ksinr, 0, "decision", None, "Ö 5", titel, "x",
                                 "accepted", None, None, None, [], None, None, None)
        if protokoll:
            council._conn.execute(
                "INSERT INTO council_protocols (ksinr, extracted_at, status, available_at) "
                "VALUES (?, ?, 'ok', ?)", (ksinr, protokoll, protokoll))
    return council._conn.execute(
        "SELECT id FROM council_decisions WHERE ksinr = ?", (ksinr,)).fetchone()[0]


def test_das_meldefenster_ist_das_fenster_des_protokoll_laufs():
    """Was älter ist als das Fenster von ``check_protocols``, kommt nur über
    einen Nachlauf herein. Zöge einer die Zahl allein nach, meldete die Mail
    wieder Nachgetragenes — oder schwiege über echte Nachzügler."""
    from pathlib import Path

    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_protocols.py"
    assert f"LOOKBACK_DAYS = {MELDEFENSTER_TAGE}\n" in pfad.read_text(encoding="utf-8")


def test_nur_frisch_veroeffentlichte_protokolle_juengerer_sitzungen(tmp_path):
    council = CouncilStore(tmp_path / "council.sqlite")
    echt = _beschluss(council, 1, "2026-08-24", "2026-09-23T09:01:21", "Linksseitige Führung")
    nachgetragen = _beschluss(council, 2, "2026-06-08", "2026-09-23T22:01:54",
                              "Umgestaltung des Oldenburger Bahnhofsvorplatzes")
    uralt = _beschluss(council, 3, "2019-02-25", "2026-09-23T22:09:15",
                       "Masterplan Fliegerhorst - Energiekonzept")
    # Ein Beschluss, der erst jetzt über die Relevanzschwelle rutscht: jung,
    # aber sein Protokoll ist längst bekannt.
    spaet_erkannt = _beschluss(council, 4, "2026-08-10", "2026-08-25T06:00:00", "Piktogramme")
    ohne_eingang = _beschluss(council, 5, "2026-09-01", None, "kaputt")

    sitzung_seit, protokoll_seit = meldestichtage(SONNTAG)
    assert council.meldewuerdige_beschluss_ids(
        [echt, nachgetragen, uralt, spaet_erkannt, ohne_eingang],
        sitzung_seit=sitzung_seit, protokoll_seit=protokoll_seit) == {echt}
    council.close()


def test_wochenueberblick_meldet_den_bestand_eines_neuen_themas_nicht(tmp_path):
    """Der Fliegerhorst-Fall: Der Sonntagsabgleich stempelt jeden Treffer, den
    er zum ersten Mal sieht — auch den von 2019."""
    council = CouncilStore(tmp_path / "council.sqlite")
    ratslotse = Store(tmp_path / "ratslotse.sqlite")
    owner = ratslotse.create_web_user(email="a@example.org", password_hash="x", role="user",
                                      status="active", display_name="Carla")
    ratslotse.set_notify_prefs(owner, {notify.N6_WOCHE: True})
    thema = ratslotse.add_topic(owner, "Fliegerhorst", "")

    alt = _beschluss(council, 1, "2019-02-25", "2026-09-23T22:09:15", "Masterplan Fliegerhorst")
    ratslotse.save_topic_decision_matches(thema.id, owner, [(alt, 0.9)])
    assert wochenueberblick(council, ratslotse, SONNTAG) == 0

    # Gegenprobe: Ein frischer Beschluss kommt — allein.
    neu = _beschluss(council, 2, "2026-09-10", "2026-09-22T08:00:00", "Fliegerhorst Bauabschnitt 4")
    ratslotse.save_topic_decision_matches(thema.id, owner, [(alt, 0.9), (neu, 0.9)])
    assert wochenueberblick(council, ratslotse, SONNTAG) == 1
    meldung = ratslotse.due_notifications(owner, "2999-01-01")[0]
    assert meldung["title"] == "Diese Woche: 1 Beschluss zu deinen Themen"
    assert "Bauabschnitt 4" in meldung["body_html"]
    assert "Masterplan" not in meldung["body_html"]
    ratslotse.close()
    council.close()
