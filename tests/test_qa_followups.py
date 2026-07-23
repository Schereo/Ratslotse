"""Folgefragen nach der KI-Antwort (Design 24a / RL-U06).

Variante A: Das Antwort-LLM hängt die Vorschläge hinter dem Marker an —
split_followups() trennt sie sauber vom Antworttext. Variante B: ohne
brauchbare Liste leitet fallback_followups() sie deterministisch aus den
gefundenen Beschlüssen ab (per Konstruktion sackgassenfrei).
"""
from __future__ import annotations

from council import qa


def test_split_trennt_antwort_und_fragen():
    text = (
        "Die Veloroute 4 wird ausgebaut [12].\n"
        'FOLGEFRAGEN: ["Wer stimmte gegen den Radverkehrsplan?", '
        '"Wie viel kostet die Veloroute 4?", "Was gilt für Fahrradstraßen?"]'
    )
    answer, qs = qa.split_followups(text)
    assert answer == "Die Veloroute 4 wird ausgebaut [12]."
    assert qs == [
        "Wer stimmte gegen den Radverkehrsplan?",
        "Wie viel kostet die Veloroute 4?",
        "Was gilt für Fahrradstraßen?",
    ]


def test_split_ohne_marker_laesst_antwort_unveraendert():
    answer, qs = qa.split_followups("Nur eine Antwort ohne Vorschläge [7].")
    assert answer == "Nur eine Antwort ohne Vorschläge [7]."
    assert qs == []


def test_split_toleriert_kaputtes_json():
    # Kein gültiges JSON → zeilenweiser Notnagel, Antwort bleibt sauber.
    text = "Antwort.\nFOLGEFRAGEN:\n- Wer stimmte dagegen?\n- Was kostet das?"
    answer, qs = qa.split_followups(text)
    assert answer == "Antwort."
    assert qs == ["Wer stimmte dagegen?", "Was kostet das?"]


def test_split_begrenzt_auf_drei_und_dedupliziert():
    text = 'A.\nFOLGEFRAGEN: ["Eins?", "Eins?", "Zwei?", "Drei?", "Vier?"]'
    _, qs = qa.split_followups(text)
    assert qs == ["Eins?", "Zwei?", "Drei?"]


def test_fallback_leitet_aus_beschluessen_ab():
    candidates = [
        {"id": 1, "title": "Radverkehrsplan 2026 — erste Maßnahmen", "policy_field": "verkehr",
         "gegenstimmen": 3, "amount_eur": 2_400_000, "committee": "Verkehrsausschuss"},
    ]
    qs = qa.fallback_followups(candidates)
    assert len(qs) <= 3 and qs
    # Umstritten → Abstimmungsfrage zuerst, mit gekürztem Subjekt (ohne Zusatz).
    assert qs[0] == "Wer stimmte gegen Radverkehrsplan 2026?"
    # Themenfeld-Label statt Schlüssel.
    assert any("Verkehr & Mobilität" in q for q in qs)


def test_fallback_ohne_gegenstimmen_und_ohne_betrag():
    candidates = [{"id": 2, "title": "Bericht", "policy_field": "kultur",
                   "gegenstimmen": 0, "amount_eur": None, "committee": "Kulturausschuss"}]
    qs = qa.fallback_followups(candidates)
    assert qs and all(q.endswith("?") for q in qs)
    assert not any("stimmte gegen" in q for q in qs)


def test_fallback_bei_leeren_kandidaten():
    assert qa.fallback_followups([]) == []
