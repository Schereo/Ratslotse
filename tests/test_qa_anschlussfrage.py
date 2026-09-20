"""Anschlussfragen im Gespräch: das Mehr, nicht das Nochmal.

Befund 09.09.2026 (gespeichertes Gespräch, Konto 9): Nach „Was findest du
zum Planfeststellungsbeschluss der Cäcilienbrücke?" kam „Sag mir mehr konkret
zum Planfeststellungsbeschluss von 2023" — und die Antwort begann WORTGLEICH
mit derselben „Kurz gesagt"-Zeile und erzählte dieselbe Chronologie noch
einmal. Zwei Ursachen, zwei Riegel:

1. Die Frage-Analyse darf die Nachfrage nicht auf die vorige Frage
   zurückschreiben (dann sucht das Retrieval dasselbe wie eben).
2. Der Antwort-Prompt sagt bei einer Anschlussfrage ausdrücklich, dass die
   vorige Antwort nicht wiederholt wird — und dass ein fehlendes Detail im
   ersten Satz benannt wird.
"""
import json
from types import SimpleNamespace

import pytest

from council import qa


@pytest.fixture(autouse=True)
def _leerer_cache():
    qa._ANALYSE_CACHE.clear()
    yield
    qa._ANALYSE_CACHE.clear()


def _llm(monkeypatch, content: str):
    def fake(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                               usage=None)
    monkeypatch.setattr(qa.llm, "chat_complete", fake)


VERLAUF = [
    {"question": "Gab es schon konkrete Pläne zur Cäcilienbrücke?",
     "answer": "**Kurz gesagt:** Es gibt Berichte, aber keine Entwürfe."},
    {"question": "Was findest du zum Planfeststellungsbeschluss der Cäcilienbrücke?",
     "answer": "**Kurz gesagt:** Der Planfeststellungsbeschluss ist ein zentrales Thema."},
]


def test_analyse_faellt_nicht_auf_die_vorige_frage_zurueck(monkeypatch):
    """Schreibt das Modell die Nachfrage auf die vorige Frage zurück, gilt die
    Nachfrage selbst — nicht die Wiederholung."""
    _llm(monkeypatch, json.dumps({
        "question": "Was findest du zum Planfeststellungsbeschluss der Cäcilienbrücke?",
        "terms": "Planfeststellungsbeschluss Cäcilienbrücke", "kind": "history"}))
    a = qa.analyse_query("Sag mir mehr konkret zum Planfeststellungsbeschluss von 2023",
                         verlauf=VERLAUF)
    assert a["question"] == "Sag mir mehr konkret zum Planfeststellungsbeschluss von 2023"


def test_analyse_behaelt_eine_echte_aufloesung(monkeypatch):
    """Eine Umschreibung, die die Präzisierung trägt, bleibt."""
    _llm(monkeypatch, json.dumps({
        "question": "Was steht im Planfeststellungsbeschluss 2023 zur Cäcilienbrücke?",
        "terms": "Planfeststellungsbeschluss 2023 Cäcilienbrücke", "kind": "topic"}))
    a = qa.analyse_query("Sag mir mehr konkret zum Planfeststellungsbeschluss von 2023",
                         verlauf=VERLAUF)
    assert a["question"] == "Was steht im Planfeststellungsbeschluss 2023 zur Cäcilienbrücke?"


def test_wiederholung_wird_gefaltet_verglichen():
    f = qa._wiederholt_vorige_frage
    assert f("was findest du zum planfeststellungsbeschluss der cäcilienbrücke", VERLAUF)
    assert f("Was findest du zum Planfeststellungsbeschluss der Caecilienbruecke?", VERLAUF)
    assert not f("Was steht im Planfeststellungsbeschluss 2023?", VERLAUF)
    assert not f("", VERLAUF)
    assert not f("Irgendwas", None)


def _prompt_text(verlauf):
    messages, _ = qa._answer_messages("Sag mir mehr zum Beschluss von 2023",
                                      [{"id": 1, "title": "Test", "session_date": "2026-01-01"}],
                                      verlauf=verlauf)
    return "\n".join(str(m.get("content") or "") for m in messages)


def test_anschlussfrage_bekommt_die_regel():
    text = _prompt_text(VERLAUF)
    assert "Dies ist eine Anschlussfrage" in text
    assert qa.ANSCHLUSS_REGEL in text
    # Die vorige Antwort steht weiter drin — das Modell soll wissen, was schon
    # gesagt ist; nur wiederholen soll es sie nicht.
    assert "Planfeststellungsbeschluss ist ein zentrales Thema" in text


def test_erstfrage_bekommt_die_regel_nicht():
    text = _prompt_text(None)
    assert "Dies ist eine Anschlussfrage" not in text
    assert qa.ANSCHLUSS_REGEL not in text


def test_analyse_prompt_verlangt_praezisierung():
    from kern import prompts
    text = prompts.get("qa_analysis")
    assert "Präzisierung" in text
    assert "nie wieder die vorige Frage" in text
