"""Jeder LLM-Text über einen Beschluss kennt dessen Ergebnis — auch die übrigen.

#1497 hat Kurzfassung und Einzeiler repariert (``council/outcome_note.py``,
``tests/test_ergebnis_zusammenfassung.py``). Dieser Wächter deckt die anderen
Textarten ab, die das Audit vom 23.09.2026 angesehen hat:

* **Themen-Beschreibungen** (``entities.describe``) bekamen das Ergebnis
  nicht und bauten auf den falschen Einzeilern auf: Von 20 Themen, deren
  Beschlüsse alle scheiterten, bestanden 8–9 die Eval — „TSH Konzept Berlin"
  hieß „… der Bau neuer Dreifeldsporthallen … beschlossen", beide abgelehnt.
  Repariert; ``scripts/fix_outcome_summaries.py --nur themen`` zieht nach.
* **Interesse, Tragweite, Ziele, Rückblicke, Viertel, Quiz, Fundstück**
  kannten es schon (0 Fehler in den Stichproben). Der Wächter hält fest,
  dass das so bleibt — ein Rückschritt dort fiele sonst niemandem auf.

Die echten Läufe gegen das Modell: ``eval/run_ergebnis_texte.py``.
"""
from __future__ import annotations

import importlib
import json
from types import SimpleNamespace

import pytest

from council import entities
from council.scraper import CouncilSession
from council.store import CouncilStore

LANG = "Die Verwaltung wird beauftragt, den Hebesatz der Grundsteuer B auf 490 v. H. anzuheben. " * 3

ABGELEHNT = {
    "id": 7, "title": "Hebesatzung 2024", "official_text": LANG, "summary": "Hebesatz steigt.",
    "committee": "Rat", "session_date": "2023-12-11", "outcome": "rejected",
    "raw_result": "- einstimmig abgelehnt -", "vote": "unanimous", "interest_reason": "",
}


class _Mitschnitt:
    """Attrappe für ``llm.chat_complete``: hält den Prompt fest, antwortet passend."""

    def __init__(self, antwort: dict | str):
        self.antwort = antwort
        self.prompt = ""

    def __call__(self, **kw):
        self.prompt = "\n".join(str(m.get("content")) for m in kw.get("messages") or [])
        inhalt = self.antwort if isinstance(self.antwort, str) else json.dumps(self.antwort)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))],
                               usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))


def test_entity_description_prompt_carries_outcome(monkeypatch):
    fake = _Mitschnitt("Eine Steuer; die Erhöhung wurde abgelehnt.")
    monkeypatch.setattr(entities.llm, "chat_complete", fake)
    angenommen = {**ABGELEHNT, "title": "Radweg", "outcome": "accepted"}
    entities.describe("Grundsteuer", "project", [ABGELEHNT, angenommen, {**ABGELEHNT, "outcome": None}])
    assert "[ABGELEHNT]: Hebesatzung 2024" in fake.prompt
    assert "[angenommen]: Radweg" in fake.prompt
    assert "[Ergebnis unbekannt]" in fake.prompt
    assert "nie als Beschluss" in fake.prompt


def test_every_outcome_has_a_line_label():
    """Ein Ergebnis ohne Etikett hieße im Prompt „unbekannt" — und ein
    abgelehntes stünde wieder ohne Ablehnung da."""
    from council import outcome_note

    for outcome in ("accepted", "noted", *outcome_note.NOT_ADOPTED):
        assert outcome in entities._ERGEBNIS_ZEILE


def test_daily_find_prompt_carries_outcome(monkeypatch):
    from council import fundstueck

    fake = _Mitschnitt({"story": "Der Rat lehnte ab."})
    monkeypatch.setattr(fundstueck.llm, "chat_complete", fake)
    fundstueck.write_story(ABGELEHNT)
    assert "rejected" in fake.prompt


@pytest.mark.parametrize("modul, funktion", [
    ("council.interest", "_batch_text"),
    ("council.impact", "_batch_text"),
    ("council.goals", "_render"),
    ("council.recaps", "_render_items"),
])
def test_rating_and_recap_prompts_carry_outcome(modul, funktion):
    baue = getattr(importlib.import_module(modul), funktion)
    assert "rejected" in baue([ABGELEHNT])


def test_district_prompt_carries_outcome():
    from council import viertel

    k = {**ABGELEHNT, "date": "2023-12-11", "kind": "decision", "locations": []}
    assert "Ergebnis: rejected" in viertel._candidate_text(k)


def test_quiz_context_carries_outcome():
    from council import quiz

    class _Store:
        def entity_detail(self, slug):
            return {"entity": {"name": "Grundsteuer"}, "decisions": [ABGELEHNT]}

    assert "[rejected]" in quiz.council_facts(_Store(), slug="grundsteuer")


# --------------------------------------------------------------------------- #
# Bestand: scripts/fix_outcome_summaries.py --nur themen
# --------------------------------------------------------------------------- #

def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Rat", "2023-12-11", "17:00", "PFL"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Hebesatzung", LANG,
                               "rejected", None, None, None, [], None, None, "- abgelehnt -")
        store._insert_decision(1, 1, "decision", None, "Ö 2", "Radweg", LANG,
                               "accepted", None, None, None, [], None, None, "- einstimmig -")
    ids = {r["title"]: r["id"] for r in store._conn.execute("SELECT id, title FROM council_decisions")}
    store.save_entities([("grundsteuer", "Grundsteuer", "project", 1), ("radweg", "Radweg", "place", 1),
                         ("stadion", "Stadion", "project", 1)],
                        [("grundsteuer", ids["Hebesatzung"]), ("radweg", ids["Radweg"]),
                         ("stadion", ids["Hebesatzung"])])
    store.set_entity_descriptions([("grundsteuer", "Der Rat beschloss die Erhöhung."),
                                   ("radweg", "Ein Radweg."), ("stadion", "Ein Stadion.")])
    return store


def test_backfill_redescribes_entities_with_rejected_decisions(tmp_path, monkeypatch):
    import scripts.fix_outcome_summaries as fix

    store = _store(tmp_path)
    assert store.entity_decisions_brief("grundsteuer")[0]["outcome"] == "rejected"
    store.close()
    gesehen: list[str] = []

    def describe(name, kind, decisions):
        gesehen.append(name)
        assert decisions[0]["outcome"] == "rejected"
        # Scheitert einmal: dann geleert, damit der Wochenlauf neu beschreibt.
        return None if name == "Stadion" else f"{name}: Die Erhöhung wurde abgelehnt."

    monkeypatch.setattr(fix.entities, "describe", describe)

    bericht = fix.process(tmp_path / "council.sqlite", only="themen")
    assert bericht["themen_betroffen"] == 2 and gesehen == []   # Bericht ruft kein Modell

    stats = fix.process(tmp_path / "council.sqlite", write=True, only="themen")
    assert sorted(gesehen) == ["Grundsteuer", "Stadion"]          # der Radweg bleibt unberührt
    assert stats["themen_neu"] == 1 and stats["themen_geleert"] == 1
    store = CouncilStore(tmp_path / "council.sqlite")
    desc = dict(store._conn.execute("SELECT slug, description FROM council_entity_meta").fetchall())
    assert desc == {"grundsteuer": "Grundsteuer: Die Erhöhung wurde abgelehnt.",
                    "radweg": "Ein Radweg.", "stadion": None}
    assert [e["slug"] for e in store.entities_without_description()] == ["stadion"]
    store.close()
