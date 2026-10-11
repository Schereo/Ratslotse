"""Wahlergebnisse in „Frag den Rat" — Erkennung und Baustein.

Am 28.09.2026 fragte jemand „Wie sind die Sitzverteilung nach der Ratswahl?"
und bekam „geht aus den Unterlagen nicht hervor" (Auswertung 11.10.2026).
"""
import sys
from pathlib import Path

import pytest

from council import qa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
from app.election import answer_context  # noqa: E402


@pytest.mark.parametrize("frage", [
    "Wie sind die Sitzverteilung nach der Ratswahl?",
    "Wie viele Sitze hat die AfD im neuen Rat?",
    "Wer wurde zum Oberbürgermeister gewählt?",
    "Wer ist neuer Oberbürgermeister?",
    "Wer hat die Stichwahl gewonnen?",
    "Wie hoch war die Wahlbeteiligung bei der Kommunalwahl?",
])
def test_wahlfragen(frage):
    assert qa.wahlfrage(frage), frage


@pytest.mark.parametrize("frage", [
    "Wie ist der Stand beim Stadion?",
    "Wer wurde in den Ausschuss gewählt?",
    "Was hat der Rat zum Radverkehr beschlossen?",
    "Wie viele Sitzungen hatte der Bauausschuss?",
])
def test_keine_wahlfragen(frage):
    assert not qa.wahlfrage(frage), frage


def test_kondensierte_fassung_zaehlt_auch():
    """Anschlussfrage „Und die CDU?" — erst die kondensierte Fassung nennt die Wahl."""
    assert qa.wahlfrage("Und die CDU?", "Wie viele Sitze hat die CDU nach der Ratswahl 2026?")


def test_baustein_traegt_sitze_ob_und_stand():
    text = answer_context.prompt_block()
    assert "Ratswahl am 13.09.2026 (amtliches Endergebnis): 52 Sitze" in text
    assert "Grüne: 13 Sitze, 24,9 % (16 Sitze, 31,2 %)" in text
    assert "AfD: 5 Sitze, 8,8 % (1 Sitz, 2,7 %)" in text
    assert "Gewählt ist Jascha Rohr." in text
    assert "in die Stichwahl gingen Ulf Prange und Jascha Rohr" in text
    assert "Nie mit [id]" in text and "beginnt am 01.11.2026" in text


def test_baustein_und_regel_stehen_im_prompt():
    block = answer_context.prompt_block()
    messages, _ = qa._answer_messages("Wie ist die Sitzverteilung nach der Ratswahl?",
                                      [], typ="topic", election_block=block)
    prompt = messages[0]["content"]
    assert "WAHLERGEBNISSE IN OLDENBURG" in prompt and "WAHLERGEBNISSE: Unten" in prompt
    ohne, _ = qa._answer_messages("Wie ist der Stand beim Stadion?", [], typ="topic")
    assert "WAHLERGEBNISSE" not in ohne[0]["content"]
