"""Zusammenfassungen abgelehnter Punkte dürfen den Vorschlag nicht als beschlossen erklären.

Gemessen am 23.09.2026: Von 21 abgelehnten Beschlüssen mit Kurzfassung
beschrieben 15 den Vorschlag als angenommen — 5988 („einstimmig abgelehnt")
hieß „Der Satz für die Grundsteuer B steigt von 445 auf 490 Prozent". Grund:
``official_text`` ist bei einem abgelehnten Punkt der Beschlussvorschlag, und
beide Erzeuger bekamen das Ergebnis nicht zu sehen.

Festgehalten wird hier, dass

1. beide Erzeuger (``simple_summary``, ``topics``) das Ergebnis im Prompt haben,
2. beide eine Antwort verwerfen, die das Ergebnis nicht nennt,
3. die Auswahl-Abfragen ``outcome`` und ``raw_result`` überhaupt mitliefern —
   ohne sie liefen 1. und 2. still ins Leere,
4. Frag den Rat einen solchen Text als Vorschlag kennzeichnet, und
5. „einstimmig bei neun Enthaltungen" einstimmig bleibt (8426).

Lottis Seite steht in ``test_assistant.py``.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from council import outcome_note, qa, simple_summary, topics
from council.scraper import CouncilSession
from council.store import CouncilStore
from council.votes import normalize_vote

# Die echten Texte aus dem Abzug vom 23.09.2026.
FALSCH_5988 = ("Die Stadt Oldenburg hat die Steuersätze für das Jahr 2024 festgelegt. Der Satz "
               "für die Grundsteuer B steigt von 445 auf 490 Prozent.")
FALSCH_5914 = ("Der Oldenburger Stadtrat hat beschlossen, dass die Stadt einer Änderung der "
               "Fahrpreise im Verkehrsverbund Bremen/Niedersachsen (VBN) zustimmt.")
FALSCH_5253 = ("Der Rat hat entschieden: Die Reinigung städtischer Gebäude übernimmt die Stadt "
               "selbst. Dafür stellt sie eigenes Personal ein.")
FALSCH_2419 = ("Der Ausschuss hat dem Plan für eine neue Straße und Bauflächen auf dem alten "
               "Fliegerhorst zugestimmt.")
RICHTIG_5988 = ("Der Ausschuss für Finanzen und Beteiligungen hat einstimmig einen Vorschlag "
                "abgelehnt: Die Grundsteuer B sollte 2024 von 445 auf 490 Prozent steigen.")

LANG = "Der Hebesatz für die Grundsteuer B wird von 445 auf 490 Prozent angehoben. " * 4


# ---- die Probe --------------------------------------------------------------

@pytest.mark.parametrize("text", [FALSCH_5988, FALSCH_5914, FALSCH_5253])
def test_probe_faengt_abgelehnt_als_beschlossen(text):
    assert not outcome_note.states_outcome("rejected", text)


def test_probe_faengt_vertagt_als_beschlossen():
    assert not outcome_note.states_outcome("postponed", FALSCH_2419)


@pytest.mark.parametrize("outcome, text", [
    ("rejected", RICHTIG_5988),
    ("rejected", "Der Stadtrat lehnte den Vorschlag ab, die Reinigung selbst zu übernehmen."),
    ("postponed", "Der Ausschuss hat die Entscheidung einstimmig vertagt."),
    ("postponed", "Das Thema wurde an den Wirtschaftsausschuss weitergegeben."),
    ("no_decision", "Zum Stellenplan 2026 wurde kein Beschluss gefasst."),
])
def test_probe_laesst_richtige_texte_durch(outcome, text):
    assert outcome_note.states_outcome(outcome, text)


@pytest.mark.parametrize("outcome", ["accepted", "noted", None])
def test_angenommen_braucht_weder_hinweis_noch_probe(outcome):
    assert outcome_note.note(outcome, "- einstimmig -") == ""
    assert outcome_note.states_outcome(outcome, FALSCH_5988)


def test_hinweis_nennt_ergebnis_und_abstimmungssatz():
    n = outcome_note.note("rejected", "- einstimmig abgelehnt -")
    assert "ABGELEHNT" in n and "einstimmig abgelehnt" in n and "VORSCHLAG" in n


# ---- „einfach erklärt" --------------------------------------------------------

def _fake_resp(content: str):
    msg = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                           usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))


def _decision_5988() -> dict:
    return {"id": 5988, "title": "Hebesatzung 2024", "official_text": LANG,
            "committee": "Ausschuss für Finanzen und Beteiligungen",
            "session_date": "2023-09-06", "outcome": "rejected",
            "raw_result": "- einstimmig abgelehnt -"}


def test_einfach_erklaert_bekommt_das_ergebnis(monkeypatch):
    gesehen: list[str] = []

    def fake(**kw):
        gesehen.append(kw["messages"][1]["content"])
        return _fake_resp(json.dumps({"einfach": RICHTIG_5988}, ensure_ascii=False))

    monkeypatch.setattr(simple_summary.llm, "chat_complete", fake)
    assert simple_summary.generate_one(_decision_5988()) == RICHTIG_5988
    assert "ERGEBNIS: ABGELEHNT" in gesehen[0]
    assert "einstimmig abgelehnt" in gesehen[0]
    # Der Hinweis steht VOR dem Beschlusstext, nicht irgendwo dahinter.
    assert gesehen[0].index("ERGEBNIS") < gesehen[0].index("Beschlusstext")


def test_einfach_erklaert_verwirft_abgelehnt_als_beschlossen(monkeypatch):
    monkeypatch.setattr(simple_summary.llm, "chat_complete",
                        lambda **kw: _fake_resp(json.dumps({"einfach": FALSCH_5988})))
    assert simple_summary.generate_one(_decision_5988()) is None


def test_einfach_erklaert_angenommen_unveraendert(monkeypatch):
    gesehen: list[str] = []

    def fake(**kw):
        gesehen.append(kw["messages"][1]["content"])
        return _fake_resp(json.dumps({"einfach": FALSCH_5988}))

    monkeypatch.setattr(simple_summary.llm, "chat_complete", fake)
    d = {**_decision_5988(), "outcome": "accepted", "raw_result": "- einstimmig -"}
    assert simple_summary.generate_one(d) == FALSCH_5988
    assert "ERGEBNIS" not in gesehen[0]


# ---- Themen-Satz (summary) ----------------------------------------------------

def test_themen_satz_bekommt_ergebnis_und_verwirft_falschen_satz(monkeypatch):
    gesehen: list[str] = []
    antwort = {"results": [
        {"id": 5988, "field": "finanzen", "tags": [], "summary": FALSCH_5988[:140]},
        {"id": 5914, "field": "verkehr", "tags": [],
         "summary": "Die Zustimmung zur VBN-Tarifanpassung wurde abgelehnt."},
        {"id": 1, "field": "finanzen", "tags": [], "summary": "Der Haushalt wird beschlossen."},
    ]}

    def fake(**kw):
        gesehen.append(kw["messages"][0]["content"])
        return _fake_resp(json.dumps(antwort, ensure_ascii=False))

    monkeypatch.setattr(topics.llm, "chat_complete", fake)
    decisions = [
        _decision_5988(),
        {"id": 5914, "title": "VBN-Tarif", "official_text": "Der Rat stimmt zu.",
         "outcome": "rejected", "raw_result": "- mehrheitlich bei zwei Ja-Stimmen abgelehnt -"},
        {"id": 1, "title": "Haushalt", "official_text": "Der Haushalt wird beschlossen.",
         "outcome": "accepted", "raw_result": "- einstimmig -"},
    ]
    out, _usage = topics.classify_batch(decisions)
    assert "Ergebnis: ABGELEHNT (- einstimmig abgelehnt -)" in gesehen[0]
    assert gesehen[0].count("\n  Ergebnis: ") == 2  # der angenommene Punkt trägt keinen
    assert out[5988]["summary"] is None                 # verworfen, Feld bleibt
    assert out[5988]["field"] == "finanzen"
    assert "abgelehnt" in out[5914]["summary"]
    assert out[1]["summary"] == "Der Haushalt wird beschlossen."


# ---- die Auswahl liefert das Ergebnis mit ---------------------------------------

def test_auswahl_abfragen_liefern_ergebnis_mit(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Rat", "2023-09-04", "17:00", "PFL"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 6.10", "VBN-Tarif", LANG,
                               "rejected", "majority", None, None, [], None, None,
                               "- mehrheitlich bei zwei Ja-Stimmen abgelehnt -")
    for rows in (store.decisions_needing_simple_summary(), store.get_unclassified_decisions()):
        assert rows[0]["outcome"] == "rejected"
        assert "abgelehnt" in rows[0]["raw_result"]
    store.close()


# ---- Frag den Rat ---------------------------------------------------------------

def test_frag_den_rat_kennzeichnet_den_vorschlag():
    ctx = qa._build_context([{
        "id": 5988, "title": "Hebesatzung 2024", "committee": "Finanzausschuss",
        "session_date": "2023-09-06", "outcome": "rejected",
        "raw_result": "- einstimmig abgelehnt -", "summary": FALSCH_5988,
    }])
    assert "Abgelehnter Vorschlag: " + FALSCH_5988[:40] in ctx


def test_frag_den_rat_laesst_richtigen_satz_stehen():
    ctx = qa._build_context([{
        "id": 5988, "title": "Hebesatzung 2024", "outcome": "rejected",
        "summary": RICHTIG_5988,
    }])
    assert "Abgelehnter Vorschlag" not in ctx
    assert RICHTIG_5988[:40] in ctx


# ---- einstimmig bei Enthaltungen -------------------------------------------------

@pytest.mark.parametrize("vote, raw, erwartet", [
    ("majority", "- einstimmig bei neun Enthaltungen -", "unanimous"),       # 8426
    ("majority", "einstimmig bei drei Enthaltungen", "unanimous"),           # 6444
    ("einstimmig bei einer Enthaltung", "- einstimmig bei einer Enthaltung -", "unanimous"),  # 6929
    ("majority", "- einstimmig bei einer Gegenstimme -", "majority"),        # 8590: steht so da
    ("majority", "- mehrheitlich bei 17 Gegenstimmen -", "majority"),
    ("unanimous", "- einstimmig -", "unanimous"),
    (None, "- einstimmig vertagt.", None),
    ("mehrheitlich", None, "majority"),
    ("irgendwas", None, None),
])
def test_normalize_vote(vote, raw, erwartet):
    assert normalize_vote(vote, raw) == erwartet


def test_speichern_normalisiert_vote(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Rat", "2026-06-01", "17:00", "PFL"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Titel", LANG, "accepted",
                               "majority", None, 9, [], None, None,
                               "- einstimmig bei neun Enthaltungen -")
    row = store._conn.execute("SELECT vote, abstentions FROM council_decisions").fetchone()
    assert (row["vote"], row["abstentions"]) == ("unanimous", 9)
    store.close()
