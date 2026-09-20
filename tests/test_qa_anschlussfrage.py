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


# ---- Suchbegriffe ohne Fragehülle -------------------------------------------

def test_fragehuelle_fliegt_aus_den_suchbegriffen():
    """„Radverkehr Beschlüsse Rat" fand den Leitfaden Fahrradstraßen nicht —
    „Beschlüsse" und „Rat" stehen in jeder Vorlage (dev, 20.09.2026)."""
    f = qa._ohne_fragehuelle
    assert f("Radverkehr Beschlüsse Rat") == "Radverkehr"
    assert f("Sumpfeichen Nadorster Straße entfernen Anzahl") == "Sumpfeichen Nadorster Straße entfernen"
    assert f("Radverkehr Fahrrad Radweg Fahrradstraße") == "Radverkehr Fahrrad Radweg Fahrradstraße"
    # Nur Hülle → lieber die Hülle als gar nichts.
    assert f("Beschlüsse Rat") == "Beschlüsse Rat"


def test_analyse_filtert_die_fragehuelle(monkeypatch):
    _llm(monkeypatch, json.dumps({"terms": "Radverkehr Beschlüsse Rat", "kind": "topic"}))
    a = qa.analyse_query("Was hat der Rat zuletzt zum Radverkehr beschlossen?")
    assert a["terms"] == "Radverkehr"


def test_analyse_prompt_verlangt_oberbegriff_und_verbietet_huelle():
    from kern import prompts
    text = prompts.get("qa_analysis")
    assert "OBERBEGRIFF" in text
    assert "Fragehülle" in text
    assert "ganzer Fragesatz" in text


# ---- Nachzügler: seltenes Fragewort im Titel hinter dem Deckel --------------

def _kand(i, title, date="2025-01-01"):
    return {"id": i, "title": title, "session_date": date}


def test_nachzuegler_holt_den_baumfaellungs_beschluss():
    """Sumpfeichen-Fall: 20 Bebauungsplan-Titel mit „Nadorster Straße" vorn,
    die Baumfällung auf Rang 28 — sie rückt nach, die B-Pläne nicht."""
    cands = [_kand(i, f"Bebauungsplan {800 + i} (Nadorster Straße) - Beschluss") for i in range(27)]
    cands.append(_kand(100, "Baumfällungen an der unteren Nadorster Straße - Bericht"))
    cands.append(_kand(101, "Sanierungsgebiet Untere Nadorster Straße - Bericht"))
    cands.append(_kand(102, "Erhalt von Bäumen in der Nadorster Straße"))
    nach = qa.nachzuegler(cands, 20, "Wie viele Sumpfeichen müssen an der Nadorster Straße entfernt werden?",
                          "Sumpfeiche Baum Nadorster Straße Fällung")
    assert [c["id"] for c in nach] == [100, 102]


def test_nachzuegler_planfeststellung():
    cands = [_kand(i, f"Cäcilienbrücke - Bericht {i}") for i in range(22)]
    cands.append(_kand(50, "Bericht zum Planfeststellungsbeschluss vom 05.07.2019 zum PFA 1"))
    nach = qa.nachzuegler(cands, 20, "Was steht im Planfeststellungsbeschluss zur Cäcilienbrücke?",
                          "Planfeststellungsbeschluss Cäcilienbrücke Brücke")
    assert [c["id"] for c in nach] == [50]


def test_nachzuegler_schweigt_ohne_seltenes_wort():
    """Trifft jedes Fragewort fast alle Titel, unterscheidet keins — nichts rückt nach."""
    cands = [_kand(i, f"Radverkehr Fahrradstraße {i}") for i in range(30)]
    assert qa.nachzuegler(cands, 20, "Was ist zum Radverkehr beschlossen?", "Radverkehr Fahrradstraße") == []
    assert qa.nachzuegler(cands[:10], 20, "Was ist zum Radverkehr beschlossen?", "Radverkehr") == []


def test_nachzuegler_hoechstens_vier():
    cands = [_kand(i, f"Bebauungsplan {i} (Nadorster Straße)") for i in range(20)]
    cands += [_kand(100 + i, f"Baumfällung {i} an der Nadorster Straße") for i in range(6)]
    nach = qa.nachzuegler(cands, 20, "Welche Bäume werden an der Nadorster Straße gefällt?",
                          "Baum Baumfällung Nadorster Straße")
    assert len(nach) == qa.NACHZUEGLER_MAX


def test_umlaut_mehrzahl():
    f = qa._umlaut_mehrzahl
    assert f("baum") == "baeum"        # Bäume
    assert f("haus") == "haeus"        # Häuser
    assert f("platz") == "plaetz"      # Plätze
    assert f("kopf") == "koepf"        # Köpfe
    assert f("brueck") == ""           # „ue" ist schon ein Umlaut
    assert f("baeume") == ""           # letzte Gruppe ist ein „e"
    assert f("xyz") == ""
