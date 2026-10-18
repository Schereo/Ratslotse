"""Modellantworten, die kein Objekt sind, brechen den Nachtlauf nicht mehr ab.

Review 05.10.2026: ``simple_summary``, ``interest``, ``fundstueck`` und
``impact`` riefen ``data.get`` bzw. ``r.get`` außerhalb ihres ``try``. Ein
Modell, das ``[...]``, ``"..."`` oder ``{"ratings": ["a"]}`` liefert, warf
``AttributeError`` — durch ``generate_simple_summaries`` bis
``check_protocols``, und alle Schritte danach fielen aus.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from council import fundstueck, impact, interest, modell_json, simple_summary  # noqa: E402
from kern import llm  # noqa: E402

#: Genau die Ausgaben aus dem Befund — und ein paar Verwandte.
KAPUTT = ['["a", "b"]', '"nur ein Satz"', '{"ratings": ["a"]}', '{"ratings": "a"}',
          '{"einfach": ["x"]}', '{"story": 3}', "42", "null", "kein json"]


def _antwort(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.fixture
def modell(monkeypatch):
    """Ein Modell, das antwortet, was der Test ihm vorgibt."""
    zustand = {"text": ""}
    monkeypatch.setattr(llm, "chat_complete", lambda **kw: _antwort(zustand["text"]))
    return zustand


@pytest.mark.parametrize("ausgabe", KAPUTT)
def test_kurzfassung_verwirft_statt_abzustuerzen(modell, ausgabe):
    modell["text"] = ausgabe
    assert simple_summary.generate_one({"title": "T", "outcome": "accepted"}) is None


@pytest.mark.parametrize("ausgabe", KAPUTT)
def test_interessantheit_verwirft_statt_abzustuerzen(modell, ausgabe):
    modell["text"] = ausgabe
    assert interest.rate_batch([{"id": 1, "title": "T"}]) == []


@pytest.mark.parametrize("ausgabe", KAPUTT)
def test_fundstueck_verwirft_statt_abzustuerzen(modell, ausgabe):
    modell["text"] = ausgabe
    assert fundstueck.write_story({"title": "T"}) is None


@pytest.mark.parametrize("ausgabe", KAPUTT)
def test_tragweite_verwirft_statt_abzustuerzen(modell, ausgabe, capsys):
    modell["text"] = ausgabe
    # Fehlende IDs fasst rate_batch selbst nach — am Ende bleibt nichts übrig.
    assert impact.rate_batch([{"id": 1, "title": "T"}]) == []
    assert impact.rate_agenda_batch([{"id": 1, "title": "T"}]) == []


def test_gute_eintraege_neben_kaputten_bleiben(modell):
    modell["text"] = '{"ratings": ["a", {"id": 1, "score": 70, "reason": "gut"}, 5]}'
    assert interest.rate_batch([{"id": 1, "title": "T"}]) == [(1, 70, "gut")]


def test_helfer():
    assert modell_json.objekt('{"a": 1}') == {"a": 1}
    assert modell_json.objekt("[1]") == {}
    assert modell_json.objekt(None) == {}
    assert modell_json.eintraege({"r": [{"x": 1}, "a", 3]}, "r") == [{"x": 1}]
    assert modell_json.eintraege({"r": "a"}, "r") == []
    assert modell_json.text({"t": "  hallo "}, "t") == "hallo"
    assert modell_json.text({"t": ["x"]}, "t") == ""


# --------------------------------------------- check_protocols: ein Schritt, nicht der Lauf

def test_ein_gescheiterter_schritt_haelt_die_uebrigen_nicht_auf(monkeypatch, tmp_path):
    """Die Kurzfassung wirft — Tragweite, Vorlagen, Orte und Meldungen laufen
    trotzdem, und der Lauf meldet sich am Ende als Teilfehler."""
    from kern.alerts import JobFehler
    from scripts import check_protocols as cp

    gelaufen: list[str] = []

    def merke(name, ergebnis):
        def fn(*a, **kw):
            gelaufen.append(name)
            return ergebnis
        return fn

    def kaputt(*a, **kw):
        gelaufen.append("Einfach erklärt")
        raise AttributeError("'list' object has no attribute 'get'")

    monkeypatch.setattr(cp, "COUNCIL_DB", tmp_path / "council.sqlite")
    monkeypatch.setattr(cp, "RATSLOTSE_DB", tmp_path / "ratslotse.sqlite")
    monkeypatch.setattr(cp, "process_range",
                        merke("Protokolle", {"parsed": 0, "no_protocol": 0, "failed": 0}))
    monkeypatch.setattr(cp, "classify_decisions",
                        merke("Klassifikation", {"classified": 0, "failed": 0, "cost": 0.0}))
    monkeypatch.setattr(cp, "track_goals", merke("Ziele", {"links": 0, "cost": 0.0}))
    monkeypatch.setattr(cp, "extract_amounts",
                        merke("Beträge", {"with_amount": 0, "decisions": 0}))
    monkeypatch.setattr(cp, "generate_simple", kaputt)
    monkeypatch.setattr(cp, "rate_interest", merke("Interessantheit", (0, 0)))
    monkeypatch.setattr(cp, "rate_impact", merke("Tragweite", (0, 0)))
    monkeypatch.setattr(cp, "fetch_vorlagen", merke("Vorlagen", cp._Leer()))
    monkeypatch.setattr(cp, "fetch_anlagen_missing", merke("Anlagen", cp._Leer()))
    monkeypatch.setattr(cp, "rescan_recent_anlagen", merke("Anlagen neu", cp._Leer()))
    monkeypatch.setattr(cp, "fetch_beratungen_missing", merke("Beratungsfolge", cp._Leer()))
    monkeypatch.setattr(cp, "rescan_beratungen", merke("Beratungsfolge neu", cp._Leer()))
    monkeypatch.setattr(cp, "extract_locations", merke("Ortszuordnung", cp._Leer()))
    monkeypatch.setattr(cp, "geocode_locations", merke("Orts-Geocoding", cp._Leer()))
    import scripts.extract_wortbeitraege as wb
    monkeypatch.setattr(wb, "process", merke("Wortbeiträge", cp._Leer()))
    import council.matters as matters
    monkeypatch.setattr(matters, "build", merke("Akten", cp._Leer()))
    import council.ergebnisse as ergebnisse
    monkeypatch.setattr(ergebnisse, "melde_ergebnisse", merke("Ergebnis-Meldungen", 0))
    monkeypatch.setattr(cp.notify, "zustellen", merke("Zustellung", 0))

    with pytest.raises(JobFehler) as fehler:
        cp._guarded_main()
    assert "Einfach erklärt" in str(fehler.value)
    for danach in ("Tragweite", "Vorlagen", "Ortszuordnung", "Ergebnis-Meldungen", "Zustellung"):
        assert danach in gelaufen, danach
    # Die Kennzahlen reisen mit (run_guarded schreibt sie in job_runs).
    assert fehler.value.kennzahlen[cp.TEILFEHLER_SCHLUESSEL] == 1
    assert fehler.value.kennzahlen["Einfach erklärt"] == 0
