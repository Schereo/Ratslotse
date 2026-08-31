"""Tragweite-Score (RL-U16): Auswahl, Mischung in den Wichtig-Wert, Parsing."""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import impact
from council.scraper import CouncilSession
from council.store import CouncilStore

TEXT = "z" * 250


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Rat", "2026-06-01", "17:00", "Ratssaal"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Haushaltssatzung 2026", TEXT,
                               "accepted", None, None, None, [], None, None, None)
        store._insert_decision(1, 1, "decision", None, "Ö 2", "Berufung Mitglied", TEXT,
                               "accepted", None, None, None, [], None, None, None)
    return store


def test_needing_and_clamp(tmp_path):
    store = _store(tmp_path)
    todo = store.decisions_needing_impact()
    assert {d["title"] for d in todo} == {"Haushaltssatzung 2026", "Berufung Mitglied"}
    store.save_impact(todo[0]["id"], 250, "x")
    assert store.get_decision(todo[0]["id"])["impact"] == 100
    assert len(store.decisions_needing_impact()) == 1
    store.close()


def test_backfill_blends_impact_fifty_fifty(tmp_path):
    store = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in store.decisions_needing_impact()}
    # Ohne impact: reine Heuristik (die Berufung landet niedrig).
    store.backfill_importance()
    base = store.get_decision(ids["Berufung Mitglied"])["importance"]
    assert base < 100
    # Mit impact 100: Mischung = round((heuristik + 100) / 2), hebt den Wert.
    store.save_impact(ids["Berufung Mitglied"], 100, "test")
    store.backfill_importance()
    blended = store.get_decision(ids["Berufung Mitglied"])["importance"]
    assert blended == round((base + 100) / 2) and blended > base
    # Ohne impact bleibt die reine Heuristik stehen.
    other = store.get_decision(ids["Haushaltssatzung 2026"])
    assert other["impact"] is None and other["importance"] is not None
    store.close()


def _fake_resp(payload: dict):
    msg = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_rate_batch_filters_and_signals(monkeypatch):
    decisions = [{"id": 7, "title": "Haushaltssatzung", "official_text": TEXT, "committee": "Rat",
                  "session_date": "2026-01-01", "outcome": "accepted", "kind": "decision",
                  "amount_eur": 1_000_000.0}]
    seen = {}
    def fake(**kw):
        seen["user"] = kw["messages"][1]["content"]
        return _fake_resp({"ratings": [{"id": 7, "score": 92, "reason": "Haushalt"},
                                       {"id": 99, "score": 10, "reason": "halluziniert"}]})
    monkeypatch.setattr(impact.llm, "chat_complete", fake)
    assert impact.rate_batch(decisions) == [(7, 92, "Haushalt")]
    # Struktur-Signale stehen im Prompt (Kalibrier-Anforderung aus RL-U16).
    assert "Gremium Rat" in seen["user"] and "1.000.000" in seen["user"]


def test_formalakt_deckel_erkennt_strassenrecht():
    """Widmung/Einziehung/Umstufung einer Straße sind Formalakte — die
    Wochen-Karte führte „Widmung der Straße ‚Im Technologiepark'" als wichtig
    (Tims Befund 18.08.). Umwidmung von Geld ist KEIN Straßenrecht."""
    assert impact.formalakt_deckel("Widmung der Straße 'Im Technologiepark'") == impact.FORMALAKT_MAX
    assert impact.formalakt_deckel("Teileinziehung des Gehweges am Marktplatz") == impact.FORMALAKT_MAX
    assert impact.formalakt_deckel("Umstufung der Gemeindestraße K 347") == impact.FORMALAKT_MAX
    assert impact.formalakt_deckel("Umwidmung von Haushaltsmitteln für den Radweg") is None
    assert impact.formalakt_deckel("Widmung des neuen Stadtteilzentrums") is None
    assert impact.formalakt_deckel("Haushaltssatzung 2026") is None
    assert impact.formalakt_deckel(None) is None


def test_rate_agenda_batch_deckelt_formalakte(monkeypatch):
    """Auch wenn das LLM die Widmung hoch bewertet, greift der Deckel — samt
    ehrlichem Grund statt der halluzinierten Wichtig-Begründung."""
    items = [{"id": 1, "title": "Widmung der Straße \"Im Technologiepark\"",
              "committee": "Verkehrsausschuss"},
             {"id": 2, "title": "Haushaltssatzung 2027", "committee": "Rat"}]
    def fake(**kw):
        return _fake_resp({"ratings": [{"id": 1, "score": 70, "warum": "Klingt nach Infrastruktur"},
                                       {"id": 2, "score": 95, "warum": "Der Haushalt"}]})
    monkeypatch.setattr(impact.llm, "chat_complete", fake)
    out = dict((i, (s, w)) for i, s, w in impact.rate_agenda_batch(items))
    assert out[1][0] == impact.FORMALAKT_MAX and out[1][1].startswith("Formsache")
    assert out[2] == (95, "Der Haushalt")


def _match_modul():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "match_topics_decisions",
        pathlib_root() / "scripts" / "match_topics_decisions.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["match_topics_decisions"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_notify_new_matches_leads_with_highest_impact(tmp_path):
    """13a-D: Der tragweitigste Titel führt die Meldung an, nicht der erste.

    Geprüft wird gegen einen **echten** Store, nicht gegen ein Double: Die
    Meldung geht seit 30a durch die Warteschlange, und genau daran hing der
    Unterschied — vorher schickte dieser Job direkt los und stand damit
    außerhalb aller Grenzen (Anlass-Schalter, Aus-Schalter, Nachtruhe,
    zwei am Tag).
    """
    from kern import notify
    from kern.store import Store

    council = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in council.decisions_needing_impact()}
    council.save_impact(ids["Haushaltssatzung 2026"], 95, "")
    council.save_impact(ids["Berufung Mitglied"], 5, "")

    ratslotse = Store(tmp_path / "ratslotse.sqlite")
    owner = ratslotse.create_web_user(email="a@b.de", password_hash="x", role="user",
                                status="active", display_name="Tim")

    mod = _match_modul()
    # Reihenfolge der new_ids: Berufung zuerst — die Tragweite muss umsortieren.
    n = mod._notify_new_matches(ratslotse, council, owner_id=owner, topic_name="Finanzen",
                                new_ids=[ids["Berufung Mitglied"], ids["Haushaltssatzung 2026"]],
                                # Fest statt `heute`: Die Sitzung der Vorrichtung
                                # ist auf 2026-06-01 genagelt, ein wandernder
                                # Stichtag machte den Test irgendwann leer.
                                as_of_date="2026-01-01")
    assert n == 1

    offen = ratslotse.due_notifications(owner, "2999-01-01")
    assert len(offen) == 1
    meldung = offen[0]
    assert meldung["title"] == "Neu zu „Finanzen“ — 2 Beschlüsse"
    assert meldung["url"] == "/topics"
    # Unter dem Schalter „Ergebnisse zu meinen Themen": Für die Person ist das
    # dieselbe Nachricht wie aus dem Protokoll — nur die Herkunft unterscheidet
    # sich, und danach sortiert niemand seine Einstellungen.
    assert meldung["kind"] == notify.N3_ERGEBNIS
    # Der folgenreichste Beschluss führt und ist direkt anklickbar; der Rest
    # steht als Zähler dahinter.
    body = meldung["body_html"]
    assert body.index("Haushaltssatzung 2026") < body.index("und 1 weitere")
    assert f"/council/decision?id={ids['Haushaltssatzung 2026']}" in body
    # Gremium und Sitzungsdatum stehen unter dem Titel (Tim, 30.08.2026) — das
    # Jahr gehört dazu, weil das Meldefenster über den Jahreswechsel reicht.
    assert "Rat · 1. Juni 2026" in body
    # Und die Push-Vorschau klebt beides nicht aneinander.
    from kern.delivery import _plain

    assert "Haushaltssatzung 2026 Rat · 1. Juni 2026" in _plain(body)
    ratslotse.close()
    council.close()


def test_notify_new_matches_schweigt_wenn_abgeschaltet(tmp_path):
    """Der Weg, der die Grenzen umging: Er kam auch bei „aus" noch an."""
    from kern.store import Store

    council = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in council.decisions_needing_impact()}
    ratslotse = Store(tmp_path / "ratslotse.sqlite")
    owner = ratslotse.create_web_user(email="a@b.de", password_hash="x", role="user",
                                status="active", display_name=None)
    ratslotse.set_delivery_channel(owner, "off")

    mod = _match_modul()
    assert mod._notify_new_matches(ratslotse, council, owner_id=owner, topic_name="Finanzen",
                                   new_ids=[ids["Haushaltssatzung 2026"]],
                                   as_of_date="2026-01-01") == 0
    assert ratslotse.due_notifications(owner, "2999-01-01") == []
    ratslotse.close()
    council.close()


def pathlib_root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent


def test_notify_new_matches_schweigt_ueber_alte_beschluesse(tmp_path):
    """Der Krusenbusch-Fall (30.08.2026): Ein Beschluss vom 07.03.2023 rutschte
    im Wochenlauf erstmals über die Relevanzschwelle — „neu" heißt hier nur
    „stand letzte Woche nicht in der Liste" — und wurde prompt per Mail
    gemeldet. Treffer bleibt Treffer, aber Post gibt es nur über Aktuelles.
    """
    from kern.store import Store

    council = _store(tmp_path)                      # Sitzung: 2026-06-01
    council.save_session(CouncilSession(2, "Schulausschuss", "2023-03-07",
                                        "17:00", "Ratssaal"))
    with council._conn:                             # zweiter Beschluss, lange her
        council._insert_decision(2, 0, "decision", None, "Ö 10.1",
                                 "Zusätzliche Spätbetreuung", TEXT,
                                 "noted", None, None, None, [], None, None, None)
    ids = {d["title"]: d["id"] for d in council.decisions_needing_impact()}

    ratslotse = Store(tmp_path / "ratslotse.sqlite")
    owner = ratslotse.create_web_user(email="a@b.de", password_hash="x", role="user",
                                status="active", display_name="Tim")
    mod = _match_modul()

    # Nur der alte Beschluss: gar keine Meldung.
    assert mod._notify_new_matches(ratslotse, council, owner_id=owner,
                                   topic_name="Grundschule Krusenbusch",
                                   new_ids=[ids["Zusätzliche Spätbetreuung"]],
                                   as_of_date="2026-01-01") == 0
    assert ratslotse.due_notifications(owner, "2999-01-01") == []

    # Gemischt: Die Mail kommt, zählt aber nur den aktuellen Beschluss — sonst
    # verspräche das „— n Beschlüsse" im Betreff etwas, das die Liste nicht hält.
    assert mod._notify_new_matches(ratslotse, council, owner_id=owner,
                                   topic_name="Grundschule Krusenbusch",
                                   new_ids=[ids["Zusätzliche Spätbetreuung"],
                                            ids["Haushaltssatzung 2026"]],
                                   as_of_date="2026-01-01") == 1
    offen = ratslotse.due_notifications(owner, "2999-01-01")
    assert len(offen) == 1
    assert offen[0]["title"] == "Neu zu „Grundschule Krusenbusch“"   # kein „— 2 Beschlüsse"
    assert "Spätbetreuung" not in offen[0]["body_html"]
    ratslotse.close()
    council.close()
