"""Wächter für [`REZEPTE.md`](../REZEPTE.md) — die Landkarte für Coding-Agents.

**Wogegen das steht.** Eine Datei, die auf Dateien und Wächter zeigt, ist
genau so lange nützlich, wie die Ziele existieren. Ein Rezept, das
``tests/test_cron_vertrag.py`` nennt (die Datei heißt ``test_jobs.py``),
schickt die nächste Person ins Leere — und sie glaubt dann eher, sie habe
etwas übersehen, als dass die Anleitung falsch ist. Genau dieser Tippfehler
stand beim Schreiben drin und ist hier aufgefallen.

Der Wächter liest die Datei und prüft jeden Pfad, den sie nennt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
REZEPTE = WURZEL / "REZEPTE.md"

#: Pfade in Markdown-Links: `[Text](pfad)`.
_LINK = re.compile(r"\]\(([^)\s#]+)\)")
#: Pfade in Code-Klammern: `lib/api.ts`. Nur, was wie ein Pfad aussieht —
#: Befehle, Bezeichner und Platzhalter sollen nicht als Datei gelten.
_CODE = re.compile(r"`([A-Za-z0-9_./()-]+\.(?:py|ts|tsx|md|json|toml|yml|sh))`")

#: Was in Code-Klammern steht, aber keine Datei IST.
NICHT_PRUEFEN = {
    ".env",              # liegt nur auf dem Server
    "package.json",      # mehrfach im Baum, ohne Pfad nicht auflösbar
}


def _genannte_pfade() -> set[str]:
    text = REZEPTE.read_text(encoding="utf-8")
    aus = set(_LINK.findall(text))
    for treffer in _CODE.findall(text):
        if "/" in treffer and treffer not in NICHT_PRUEFEN:
            aus.add(treffer)
    return {p for p in aus if not p.startswith(("http://", "https://"))}


def test_die_landkarte_gibt_es_ueberhaupt():
    assert REZEPTE.exists(), (
        "REZEPTE.md ist weg. Sie ist die Landkarte für Coding-Agents — "
        "welche Aufgabe fasst welche Dateien an. Die CLAUDE.md-Dateien sagen "
        "die Regeln, nicht den Einstieg.")


@pytest.mark.parametrize("pfad", sorted(_genannte_pfade()))
def test_jeder_genannte_pfad_existiert(pfad: str):
    """Ein Verweis ins Leere ist schlimmer als kein Verweis.

    Wer der Anleitung folgt und die Datei nicht findet, sucht bei sich —
    nicht in der Anleitung.
    """
    assert (WURZEL / pfad).exists(), (
        f"REZEPTE.md nennt `{pfad}`, das gibt es nicht. Entweder ist die Datei "
        "umgezogen (dann den Verweis nachziehen) oder der Name ist ein "
        "Tippfehler.")


def test_die_landkarte_verweist_auf_die_regeln():
    """Sie ersetzt die CLAUDE.md-Dateien nicht, sie führt zu ihnen."""
    text = REZEPTE.read_text(encoding="utf-8")
    assert "CLAUDE.md" in text
    assert "gilt die `CLAUDE.md`" in text, (
        "Der Vorrang fehlt. Ohne ihn wird die Landkarte zur zweiten Wahrheit "
        "neben den Regeln — und veraltet dann unbemerkt.")


def test_jedes_rezept_nennt_seinen_waechter():
    """Ein Rezept ohne „Was dich fängt" lädt dazu ein, blind zu pushen.

    Ausgenommen sind die Abschnitte, die selbst keine Änderung beschreiben
    (Release, Wächter-Erklärung) — sie stehen namentlich hier.
    """
    text = REZEPTE.read_text(encoding="utf-8")
    abschnitte = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    ohne = [a.splitlines()[0].strip() for a in abschnitte
            if "Was dich fängt" not in a
            and not a.startswith(("Einen Release fahren", "Wenn ein Wächter anschlägt",
                                  "Einen Prompt ändern"))]
    assert not ohne, (
        f"Diese Rezepte nennen keinen Wächter: {ohne}. Wer nicht weiß, was "
        "seinen Fehler fängt, pusht blind — schreib dazu, welcher Test oder "
        "welche Prüfung greift.")
