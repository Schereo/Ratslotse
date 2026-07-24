"""Themen-Intelligenz (Design 26a / RL-U17).

Der Kern ist Vertrauen: Die erzeugte Beschreibung wird zum Maßstab, an dem der
Wächter jeden künftigen Beschluss misst. Deshalb prüfen diese Tests vor allem
die Ränder — kein LLM, kaputte Antwort, keine Belege — denn dort entscheidet
sich, ob das Anlegen eines Themas trotzdem funktioniert.
"""
from __future__ import annotations

import pytest

from council import topic_intel
from council.store import CouncilStore


@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    s._conn.execute(
        "INSERT INTO council_sessions(ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (1,'Rat','2026-01-15','18:00','Rathaus','2026-01-15')")
    rows = [
        (1, "Sanierung Cäcilienbrücke: Kostenfortschreibung", "verkehr",
         "Die Sanierung der Cäcilienbrücke wird fortgesetzt."),
        (2, "Cäcilienbrücke — Ersatzverkehr Fähre", "verkehr",
         "Für die Sperrung wird ein Fährbetrieb eingerichtet."),
        (3, "Cäcilienbrücke: Zeitplan der Wiedereröffnung", "verkehr",
         "Der Zeitplan zur Wiedereröffnung wurde beschlossen."),
    ]
    for did, title, field, beschluss in rows:
        s._conn.execute(
            "INSERT INTO council_decisions(id, ksinr, position, title, policy_field, beschluss) "
            "VALUES (?,1,?,?,?,?)", (did, did, title, field, beschluss))
    s._conn.commit()
    s.rebuild_fts()
    yield s
    s.close()


def test_ohne_belege_kein_ratsthema(store):
    """„Geburtstag meiner Schwester" findet nichts — dann wird das LLM gar nicht
    erst gefragt, und die Antwort stützt sich auf Daten statt auf eine Meinung."""
    res = topic_intel.analyse(store, "Geburtstag meiner Schwester")
    assert res["is_council_topic"] is False
    assert res["matches"] == 0
    assert res["description"] == ""
    assert "nichts" in res["reason"].lower() or "stadtrat" in res["reason"].lower()


def test_einzelner_treffer_reicht_nicht(store, monkeypatch):
    """Ein Zufallstreffer macht noch kein abonnierbares Thema."""
    monkeypatch.setattr(topic_intel, "find_matches", lambda *a, **k: [{"title": "Irgendwas"}])
    res = topic_intel.analyse(store, "Irgendwas")
    assert res["is_council_topic"] is False
    assert res["matches"] == 1


def test_belege_ohne_llm_ergeben_brauchbare_beschreibung(store, monkeypatch):
    """Fällt das LLM aus, darf das Anlegen NICHT scheitern — es kommt ein
    deterministischer Satz, der das Themenfeld der Treffer nennt."""
    def boom(*a, **k):
        raise RuntimeError("LLM aus")
    monkeypatch.setattr(topic_intel.llm, "chat_complete", boom)

    res = topic_intel.analyse(store, "Cäcilienbrücke")
    assert res["is_council_topic"] is True
    assert res["matches"] >= topic_intel.MIN_MATCHES
    assert "Cäcilienbrücke" in res["description"]
    assert "Verkehr" in res["description"]        # Themenfeld der Treffer
    assert len(res["examples"]) >= 1


def test_kaputte_llm_antwort_faellt_zurueck(store, monkeypatch):
    monkeypatch.setattr(topic_intel.llm, "chat_complete",
                        lambda *a, **k: _resp("kein json, nur gerede"))
    res = topic_intel.analyse(store, "Cäcilienbrücke")
    assert res["is_council_topic"] is True
    assert "Cäcilienbrücke" in res["description"]


def test_llm_darf_ratsthema_verneinen(store, monkeypatch):
    """Belege können täuschen — die Suche findet immer irgendwas. Sagt das
    Modell begründet nein, wird das durchgereicht."""
    monkeypatch.setattr(topic_intel.llm, "chat_complete", lambda *a, **k: _resp(
        '{"ist_ratsthema": false, "beschreibung": "", "begruendung": "Meint eine Person, keinen Ratsvorgang."}'))
    res = topic_intel.analyse(store, "Cäcilienbrücke")
    assert res["is_council_topic"] is False
    assert "Person" in res["reason"]


def test_llm_beschreibung_wird_uebernommen_und_gekuerzt(store, monkeypatch):
    lang = "Sanierung und Sperrung der Hubbrücke. " * 20
    monkeypatch.setattr(topic_intel.llm, "chat_complete", lambda *a, **k: _resp(
        '{"ist_ratsthema": true, "beschreibung": "%s", "begruendung": ""}' % lang.strip()))
    res = topic_intel.analyse(store, "Cäcilienbrücke")
    assert res["is_council_topic"] is True
    assert len(res["description"]) <= 240


def test_vagheitspruefung_faellt_sicher_aus(monkeypatch):
    """Eine kaputte Prüfung darf niemanden am Anlegen hindern."""
    def boom(*a, **k):
        raise RuntimeError("LLM aus")
    monkeypatch.setattr(topic_intel.llm, "chat_complete", boom)
    assert topic_intel.check_vagueness("Klima", "alles mögliche") == {
        "vague": False, "hint": "", "suggestion": ""}


def test_vagheitspruefung_reicht_urteil_durch(monkeypatch):
    monkeypatch.setattr(topic_intel.llm, "chat_complete", lambda *a, **k: _resp(
        '{"vague": true, "hint": "Zu breit.", "suggestion": "Radwege in Oldenburg-Eversten"}'))
    v = topic_intel.check_vagueness("Radwege", "alles über Radwege")
    assert v["vague"] is True and v["suggestion"].startswith("Radwege in")


def test_leere_beschreibung_wird_nicht_geprueft(monkeypatch):
    """Ohne eigenen Text gibt es nichts zu bemängeln — und keinen LLM-Aufruf."""
    def boom(*a, **k):
        raise AssertionError("darf nicht aufgerufen werden")
    monkeypatch.setattr(topic_intel.llm, "chat_complete", boom)
    assert topic_intel.check_vagueness("Radwege", "   ")["vague"] is False


@pytest.mark.parametrize("name,generic", [
    ("Klima", True), ("Bericht", True), ("Innenstadt", True), ("Schule", True),
    ("Cäcilienbrücke", False), ("Fliegerhorst", False),
    ("Klimaschutzplan 2035", False), ("Schule Ofenerdiek", False),
])
def test_gattungswoerter_werden_erkannt(name, generic):
    """Der kostenlose Vorfilter: ein einzelnes Gattungswort grenzt nichts ein,
    ein Eigenname oder eine Wortgruppe schon."""
    assert topic_intel.looks_generic(name) is generic


def test_vagheits_cache_roundtrip(store):
    store.save_topic_vagueness("radwege", "Radwege", {"vague": True, "hint": "zu breit", "suggestion": "X"})
    got = store.topic_vagueness_verdicts(["radwege", "gibt-es-nicht"])
    assert got["radwege"]["vague"] == 1
    assert got["radwege"]["name"] == "Radwege"
    assert "gibt-es-nicht" not in got
    # Umbenannt → das Urteil wird überschrieben, nicht geerbt.
    store.save_topic_vagueness("radwege", "Radverkehr Eversten", {"vague": False})
    assert store.topic_vagueness_verdicts(["radwege"])["radwege"]["name"] == "Radverkehr Eversten"


def _resp(content: str):
    """Minimales Abbild der OpenAI-Antwortstruktur."""
    class _M:
        def __init__(self, c): self.content = c
    class _C:
        def __init__(self, c): self.message = _M(c)
    class _R:
        def __init__(self, c): self.choices = [_C(c)]
    return _R(content)
