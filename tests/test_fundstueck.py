"""Interessantheit + Fundstück des Tages (RL-U11): Auswahl, Persistenz, Parsing."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from council import fundstueck, interest
from council.scraper import CouncilSession
from council.store import CouncilStore

TEXT = "y" * 250


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    # Jahrestag: gleicher Kalendertag wie heute, vor 6 Jahren.
    today = date.today()
    anniv = today.replace(year=today.year - 6).isoformat()
    store.save_session(CouncilSession(1, "Rat", anniv, "17:00", "Ratssaal"))
    store.save_session(CouncilSession(2, "Kulturausschuss", "2024-03-05", "17:00", "PFL"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Grüne Wellen fürs Rad", TEXT,
                               "angenommen", "einstimmig", None, None, [], None, None, None)
        store._insert_decision(2, 0, "decision", None, "Ö 1", "Museumskonzept", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
        store._insert_decision(2, 1, "decision", None, "Ö 2", "Geschäftsordnung", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
    return store


def test_interest_roundtrip_and_selection(tmp_path):
    store = _store(tmp_path)
    todo = store.decisions_needing_interest()
    assert len(todo) == 3

    ids = {d["title"]: d["id"] for d in todo}
    store.save_interest(ids["Grüne Wellen fürs Rad"], 82, "kurios und alltagsnah")
    store.save_interest(ids["Museumskonzept"], 70, "konkretes Projekt")
    store.save_interest(ids["Geschäftsordnung"], 10, "Formalie")
    assert store.decisions_needing_interest() == []
    # Clamping.
    store.save_interest(ids["Geschäftsordnung"], 150, None)
    assert store.get_decision(ids["Geschäftsordnung"])["interest"] == 100
    store.close()


def _bewerten(store, titel_zu_werten):
    """Interesse UND Tragweite setzen — beides ist seit 20.08.26 Pflicht."""
    ids = {d["title"]: d["id"] for d in store.decisions_needing_interest()}
    for titel, (interesse, tragweite) in titel_zu_werten.items():
        store.save_interest(ids[titel], interesse, "")
        store.save_impact(ids[titel], tragweite, "")
    return ids


def test_pick_prefers_anniversary_then_archive(tmp_path):
    store = _store(tmp_path)
    # Rückgabewert bewusst verworfen: Dieser Test greift die Beschlüsse über
    # `pick_candidate` ab, nicht über ihre IDs. Der ungenutzte Name kam mit
    # #670 herein und über den Rückmerge nach `dev` — dem einzigen Zweig, auf
    # dem ruff läuft (#613, `ruff.toml` gibt es auf `main` nicht). Seither
    # stand die CI dort rot, für jeden PR gegen dev.
    _bewerten(store, {
        "Grüne Wellen fürs Rad": (75, 75),      # Jahrestag, ordentlich
        "Museumskonzept": (80, 70),             # Archiv, nicht deutlich besser
        "Geschäftsordnung": (10, 10),           # Formalie
    })

    picked = fundstueck.pick_candidate(store, date.today())
    assert picked is not None
    decision, years = picked
    # Jahrestag gewinnt, solange das Archiv nicht deutlich besser ist.
    assert decision["title"] == "Grüne Wellen fürs Rad" and years == 6

    # Ist der Jahrestags-Fund kürzlich verwendet, fällt die Wahl aufs Archiv.
    store.save_fundstueck(date.today().isoformat(), decision["id"], "Heute vor 6 Jahren", "s")
    picked2 = fundstueck.pick_candidate(store, date.today())
    assert picked2 is not None and picked2[0]["title"] == "Museumskonzept" and picked2[1] == 0
    store.close()


def test_kuriositaet_ohne_tragweite_gewinnt_nicht(tmp_path):
    """Der eigentliche Fehler bis 20.08.26: Ausgewählt wurde allein nach
    Erzählbarkeit. Herausgekommen sind „Straßenbenennung Rotkäppchenweg"
    (Interesse 90, Tragweite 35) und „Modellvorhaben Cannabis" (90 / 5) —
    kurios, aber kein Fund, über den man redet (Tims Befund)."""
    store = _store(tmp_path)
    _bewerten(store, {
        "Grüne Wellen fürs Rad": (100, 20),     # Spitzen-Kuriosität, bedeutungslos
        "Museumskonzept": (65, 85),             # weniger kurios, aber gewichtig
        "Geschäftsordnung": (10, 10),
    })
    picked = fundstueck.pick_candidate(store, date.today())
    assert picked is not None
    assert picked[0]["title"] == "Museumskonzept"
    store.close()


def test_starker_archivfund_sticht_schwachen_jahrestag(tmp_path):
    """Ein Jahrestag ist ein Aufhänger, kein Freifahrtschein."""
    store = _store(tmp_path)
    _bewerten(store, {
        "Grüne Wellen fürs Rad": (55, 55),      # Jahrestag, gerade so
        "Museumskonzept": (90, 95),             # Archiv, deutlich besser
        "Geschäftsordnung": (10, 10),
    })
    picked = fundstueck.pick_candidate(store, date.today())
    assert picked is not None
    assert picked[0]["title"] == "Museumskonzept" and picked[1] == 0
    store.close()


def test_dasselbe_thema_nicht_zweimal_kurz_nacheinander(tmp_path):
    """Die ID-Sperre reicht nicht: Ein Großprojekt zieht sich über viele
    EINZELNE Beschlüsse. Ohne Themen-Sperre standen sieben von vierzehn
    Tagen unter „Stadion"."""
    from council.fundstueck import _kernworte, _thema_frei

    assert "stadionneubau" in _kernworte("Stadionneubau Maastrichter Straße")
    assert "oldenburg" not in _kernworte("Stadt Oldenburg: Beschluss")

    confidential = [_kernworte("Gründung der Stadion Oldenburg GmbH & Co. KG")]
    assert not _thema_frei("Stadion Oldenburg GmbH: Grundstücksübertragungen", confidential)
    assert _thema_frei("Fortschreibung des Lärmaktionsplans", confidential)


def test_fundstueck_persistence_and_lookup(tmp_path):
    store = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in store.decisions_needing_interest()}
    store.save_fundstueck("2026-07-22", ids["Museumskonzept"], "Aus dem Archiv", "Der Rat …")
    f = store.get_fundstueck("2026-07-22")
    assert f["story"] == "Der Rat …" and f["title"] == "Museumskonzept"
    assert f["committee"] == "Kulturausschuss"
    assert store.get_fundstueck("2026-07-23") is None
    assert store.fundstueck_days_present(["2026-07-22", "2026-07-23"]) == {"2026-07-22"}
    assert ids["Museumskonzept"] in store.recent_fundstueck_decision_ids(10_000)
    # Upsert überschreibt.
    store.save_fundstueck("2026-07-22", ids["Museumskonzept"], "Aus dem Archiv", "Neu.")
    assert store.get_fundstueck("2026-07-22")["story"] == "Neu."
    store.close()


def _fake_resp(payload: dict):
    msg = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_rate_batch_filters_hallucinated_ids(monkeypatch):
    decisions = [
        {"id": 1, "title": "A", "official_text": TEXT, "committee": "Rat",
         "session_date": "2024-01-01", "outcome": "angenommen"},
        {"id": 2, "title": "B", "official_text": TEXT, "committee": "Rat",
         "session_date": "2024-01-01", "outcome": "angenommen"},
    ]
    payload = {"ratings": [
        {"id": 1, "score": 77, "grund": "gut"},
        {"id": 999, "score": 50, "grund": "halluziniert"},
        {"id": 2, "score": 130, "grund": "out of range"},
    ]}
    monkeypatch.setattr(interest.llm, "chat_complete", lambda **kw: _fake_resp(payload))
    assert interest.rate_batch(decisions) == [(1, 77, "gut")]


def test_write_story_guards(monkeypatch):
    decision = {"id": 1, "title": "Grüne Wellen", "official_text": TEXT, "committee": "Rat",
                "session_date": "2020-07-22", "outcome": "angenommen", "interest_reason": ""}
    monkeypatch.setattr(fundstueck.llm, "chat_complete",
                        lambda **kw: _fake_resp({"story": "Der Rat beschloss 2020, grüne Wellen fürs Rad zu testen."}))
    assert fundstueck.write_story(decision).startswith("Der Rat beschloss 2020")
    monkeypatch.setattr(fundstueck.llm, "chat_complete",
                        lambda **kw: _fake_resp({"story": "x" * 300}))
    assert fundstueck.write_story(decision) is None


def test_kicker():
    assert fundstueck.kicker_for(0) == "Aus dem Archiv"
    assert fundstueck.kicker_for(1) == "Heute vor einem Jahr"
    assert fundstueck.kicker_for(6) == "Heute vor 6 Jahren"
