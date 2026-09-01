"""Die SCHLÜSSEL der Prompt-Vorlagen — Abgleich Aufrufe ↔ ``DEFAULTS``.

Seit 09/2026 sind die Schlüssel englisch. Ein Schlüssel ist nur ein String:
Wer ihn an einer Stelle umbenennt und an der anderen vergisst, bekommt keinen
Import-Fehler, sondern ein ``KeyError`` mitten im Cron-Lauf — oder, schlimmer,
einen ``DEFAULTS``-Eintrag, den niemand mehr aufruft und der still veraltet.

Deshalb wird hier in BEIDE Richtungen geprüft:

* kein Aufruf ohne Eintrag — jeder ``prompts.get("…")`` / ``prompts.render("…")``
  / ``prompts.DEFAULTS["…"]`` im ganzen Repo trifft einen echten Schlüssel;
* kein Eintrag ohne Aufruf — jeder Schlüssel in ``DEFAULTS`` wird irgendwo
  benutzt.

Gefunden werden die Aufrufe über den AST, nicht über einen Regex: So zählen
nur echte Aufrufe, keine Wörter aus Kommentaren, Prompt-Texten oder
``_feature=``-Literalen des Kosten-Trackings (die zufällig genauso heißen
können und ausdrücklich NICHT mitwandern).
"""
from __future__ import annotations

import ast
from pathlib import Path

from kern import prompts

REPO = Path(__file__).resolve().parent.parent
UEBERSPRINGEN = {".venv", ".git", "node_modules", ".next", "__pycache__", ".claude"}

# Die Umbenennung vom 09/2026: alter Schlüssel -> heutiger Schlüssel.
# Die Liste ist ihr eigener Wächter (siehe `test_umbenennung_ist_nicht_selbstgleich`):
# Ein Suchen-und-Ersetzen, das auch die linke Spalte mitübersetzt, macht die
# Paare selbstgleich — und ein selbstgleiches Paar prüft nichts mehr.
UMBENANNT: dict[str, str] = {
    "council_watcher_pruefung": "council_watcher_check",
    "deep_bericht": "deep_report",
    "deep_zerlegung": "deep_decomposition",
    "entity_dubletten_system": "entity_duplicates_system",
    "entity_dubletten_user": "entity_duplicates_user",
    "fundstueck_story_system": "daily_find_story_system",
    "fundstueck_story_user": "daily_find_story_user",
    "impact_bewertung_system": "impact_rating_system",
    "impact_bewertung_user": "impact_rating_user",
    "interest_bewertung_system": "interest_rating_system",
    "interest_bewertung_user": "interest_rating_user",
    "partei_meinungen": "party_opinions",
    "qa_analyse": "qa_analysis",
    "qa_antwort": "qa_answer",
    "qa_einfach": "qa_simple",
    "qa_suchbegriffe": "qa_search_terms",
    "recap_themenfeld": "recap_policy_field",
    "social_kartentext_system": "social_card_text_system",
    "social_kartentext_user": "social_card_text_user",
    "social_kritiker_system": "social_critic_system",
    "social_kritiker_user": "social_critic_user",
    "top_wichtigkeit_system": "agenda_item_importance_system",
    "top_wichtigkeit_user": "agenda_item_importance_user",
    "topic_auto_beschreibung": "topic_auto_description",
    "wortbeitraege_extract": "speeches_extract",
}


def _python_dateien():
    for pfad in sorted(REPO.rglob("*.py")):
        if UEBERSPRINGEN & set(pfad.relative_to(REPO).parts):
            continue
        yield pfad


def _erster_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def benutzte_schluessel() -> dict[str, list[str]]:
    """Schlüssel -> Fundstellen ``pfad:zeile``, quer durchs ganze Repo."""
    gefunden: dict[str, list[str]] = {}

    def merken(key: str, pfad: Path, zeile: int) -> None:
        gefunden.setdefault(key, []).append(f"{pfad.relative_to(REPO)}:{zeile}")

    for pfad in _python_dateien():
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        except SyntaxError:  # pragma: no cover — defekte Datei fällt woanders auf
            continue
        for node in ast.walk(baum):
            # prompts.get("…") / prompts.render("…", …)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("get", "render") and node.args):
                ziel = node.func.value
                if isinstance(ziel, ast.Name) and ziel.id == "prompts":
                    key = _erster_string(node.args[0])
                    if key is not None:
                        merken(key, pfad, node.lineno)
            # prompts.DEFAULTS["…"]
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "DEFAULTS"):
                key = _erster_string(node.slice)
                if key is not None:
                    merken(key, pfad, node.lineno)
    return gefunden


# Absichtlich unbekannt: `test_prompts.py::test_unknown_key_raises` prüft, dass
# `get()` bei einem Fantasie-Schlüssel ein KeyError wirft.
ABSICHTLICH_UNBEKANNT = {"does_not_exist"}


def test_kein_aufruf_ohne_eintrag():
    """Jeder aufgerufene Schlüssel steht in ``DEFAULTS``."""
    fehlend = {k: v for k, v in benutzte_schluessel().items()
               if k not in prompts.DEFAULTS and k not in ABSICHTLICH_UNBEKANNT}
    assert not fehlend, ("Aufgerufene Prompt-Schlüssel ohne DEFAULTS-Eintrag:\n  "
                         + "\n  ".join(f"{k}: {', '.join(v)}" for k, v in sorted(fehlend.items())))


def test_kein_eintrag_ohne_aufruf():
    """Jeder ``DEFAULTS``-Eintrag wird irgendwo benutzt."""
    benutzt = set(benutzte_schluessel())
    verwaist = sorted(set(prompts.DEFAULTS) - benutzt)
    assert not verwaist, "DEFAULTS-Einträge, die niemand aufruft: " + ", ".join(verwaist)


def test_umbenennung_ist_nicht_selbstgleich():
    """Die Prüfliste darf sich nicht mitübersetzt haben.

    ``("qa_antwort", "qa_answer")`` zu ``("qa_answer", "qa_answer")`` zu machen
    kostet ein unbedachtes Suchen-und-Ersetzen — und der Test darunter prüfte
    danach nichts mehr, ohne rot zu werden.
    """
    selbstgleich = sorted(alt for alt, neu in UMBENANNT.items() if alt == neu)
    assert not selbstgleich, "Selbstgleiche Paare in UMBENANNT: " + ", ".join(selbstgleich)


def test_alte_schluessel_sind_weg():
    """Kein deutscher Alt-Schlüssel lebt noch in ``DEFAULTS`` oder in einem Aufruf."""
    benutzt = set(benutzte_schluessel())
    uebrig = sorted(alt for alt in UMBENANNT if alt in prompts.DEFAULTS or alt in benutzt)
    assert not uebrig, "Noch benutzte Alt-Schlüssel: " + ", ".join(uebrig)


def test_neue_schluessel_sind_da():
    """Jeder umbenannte Schlüssel steht unter seinem neuen Namen in ``DEFAULTS``."""
    fehlend = sorted(neu for neu in UMBENANNT.values() if neu not in prompts.DEFAULTS)
    assert not fehlend, "Umbenannte Schlüssel fehlen in DEFAULTS: " + ", ".join(fehlend)


def test_schluessel_sind_englisch_geschrieben():
    """Keine deutschen Wortteile mehr in den Schlüsseln.

    Nur die SCHLÜSSEL: Die Prompt-TEXTE sind und bleiben deutsch — sie sind
    das, was das Modell liest.
    """
    deutsche_teile = ("pruefung", "bericht", "zerlegung", "dubletten", "fundstueck",
                      "bewertung", "meinungen", "analyse", "antwort", "einfach",
                      "suchbegriffe", "themenfeld", "kartentext", "kritiker",
                      "wichtigkeit", "beschreibung", "wortbeitraege")
    treffer = sorted(k for k in prompts.DEFAULTS if any(t in k for t in deutsche_teile))
    assert not treffer, "Prompt-Schlüssel mit deutschen Wortteilen: " + ", ".join(treffer)
