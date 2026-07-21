"""Tagesordnungs-Treffer zu eigenen Themen (RL-902): Persistenz + Watcher.

Der Watcher klassifiziert Tagesordnungen kommender Sitzungen je Nutzer:in per
LLM; die Treffer landen in nwz.sqlite (council_agenda_matches) und speisen die
„n TOPs zu deinen Themen"-Chips. Klassifiziert wird nur, wenn sich die
Tagesordnung seit dem letzten Lauf geändert hat (council_agenda_classified).
"""
from __future__ import annotations

from datetime import date, timedelta

from nwz.store import Store


def test_agenda_matches_roundtrip(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    t1 = store.add_topic(7, "Radwege", "Ausbau von Radwegen")
    t2 = store.add_topic(7, "Stadtbäume", "Baumschutz")

    assert store.agenda_classified_hash(7, 900) is None
    store.replace_agenda_matches(7, 900, "h1", {t1.id: ["Ö 6", "Ö 7"], t2.id: ["Ö 6"]})
    assert store.agenda_classified_hash(7, 900) == "h1"

    m = store.agenda_matches_for_owner(7, [900])
    assert sorted((x["item_number"], x["topic_name"]) for x in m[900]) == [
        ("Ö 6", "Radwege"), ("Ö 6", "Stadtbäume"), ("Ö 7", "Radwege"),
    ]

    # Geänderte Tagesordnung → voller Austausch, kein Rest alter Treffer.
    store.replace_agenda_matches(7, 900, "h2", {t1.id: ["Ö 9"]})
    m = store.agenda_matches_for_owner(7, [900])
    assert [(x["item_number"], x["topic_name"]) for x in m[900]] == [("Ö 9", "Radwege")]
    assert store.agenda_classified_hash(7, 900) == "h2"

    # Fremde Owner und leere Abfragen sehen nichts.
    assert store.agenda_matches_for_owner(8, [900]) == {}
    assert store.agenda_matches_for_owner(7, []) == {}
    store.close()


def test_run_watcher_persists_matches_and_skips_unchanged(tmp_path, monkeypatch):
    from council import watcher
    from council.scraper import AgendaItem, CouncilSession
    import nwz.delivery as delivery_mod

    nwz = Store(tmp_path / "nwz.sqlite")
    topic = nwz.add_topic(1, "Radwege", "Ausbau von Radwegen")
    owner = {"owner_id": 1, "delivery_channel": "email", "email": None,
             "push_tokens": [], "topics": [topic]}

    future = (date.today() + timedelta(days=5)).isoformat()
    session = CouncilSession(
        ksinr=42, committee="Verkehrsausschuss", session_date=future,
        session_time="17:00", location="Fleiwa",
        agenda_items=[AgendaItem(item_number="Ö 6", title="Radweg Hauptstraße")],
    )
    monkeypatch.setattr(watcher.CouncilScraper, "upcoming_calendar",
                        lambda self, months_ahead=3: ([42], []))
    monkeypatch.setattr(watcher.CouncilScraper, "fetch_session", lambda self, k: session)

    classify_calls: list[int] = []

    def fake_classify(sess, topics):
        classify_calls.append(1)
        return {0: ["Ö 6"]}

    monkeypatch.setattr(watcher, "_classify_agenda", fake_classify)
    delivered: list[str] = []
    monkeypatch.setattr(delivery_mod, "deliver_message",
                        lambda owner, msg, email_subject=None: delivered.append(msg))

    alerts = watcher.run_watcher(tmp_path / "council.sqlite", [owner], nwz_store=nwz)
    assert len(alerts) == 1 and len(classify_calls) == 1 and len(delivered) == 1
    assert nwz.agenda_matches_for_owner(1, [42]) == {
        42: [{"item_number": "Ö 6", "topic_name": "Radwege"}]
    }

    # Zweiter Lauf, unveränderte Tagesordnung: keine erneute Klassifikation,
    # kein doppelter Alert.
    alerts2 = watcher.run_watcher(tmp_path / "council.sqlite", [owner], nwz_store=nwz)
    assert alerts2 == [] and len(classify_calls) == 1

    # Geänderte Tagesordnung: neue Klassifikation (Alert bleibt dedupliziert,
    # weil council_alerts_sent je ksinr+topic nur einmal sendet).
    session.agenda_items.append(AgendaItem(item_number="Ö 7", title="Fahrradstraße"))
    watcher.run_watcher(tmp_path / "council.sqlite", [owner], nwz_store=nwz)
    assert len(classify_calls) == 2 and len(delivered) == 1
    nwz.close()
