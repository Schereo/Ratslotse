"""Wächter für das Fachwort-Glossar.

Zwei Dinge sollen hier scheitern, bevor sie jemandem auffallen: dass die
erzeugte Frontend-Liste vom Python-Bestand abweicht (dann fehlt ein Tooltip
oder das Modell rät — beides ohne Fehlermeldung), und dass ein Eintrag
unauffindbar ist, weil ein anderer ihn verdeckt.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from council import qa
from kern import glossar, llm

WURZEL = Path(__file__).resolve().parents[1]


def test_frontend_liste_ist_auf_dem_stand():
    """`lib/glossary.ts` wird erzeugt — hier steht, dass es auch geschah."""
    r = subprocess.run([sys.executable, "scripts/glossar_ts.py", "--pruefen"],
                       cwd=WURZEL, capture_output=True, text=True)
    assert r.returncode == 0, (
        f"{r.stdout}{r.stderr}\n"
        "Neu erzeugen: python scripts/glossar_ts.py")


def test_jeder_begriff_ist_auffindbar():
    """Die Gegenrichtung: Ein Eintrag, den die Suche nie liefert, ist tot.

    Passieren kann das durch einen Schlüssel, der sich von einem anderen nur in
    der Groß-/Kleinschreibung unterscheidet — gematcht wird ohne Rücksicht
    darauf, gewonnen hätte immer derselbe.
    """
    unerreichbar = [b for b in glossar.BEGRIFFE
                    if not (t := glossar.finde(b, max_n=1)) or t[0]["begriff"] != b]
    assert unerreichbar == [], (
        f"Diese Einträge liefert glossar.finde() nie: {unerreichbar}. "
        "Meist ein Schlüssel, den ein anderer (nur anders geschrieben) verdeckt.")


def test_beugung_ja_kompositum_nein():
    """Die Matching-Regel, an der die ganze Auswahl hängt.

    „Bürgschaft" greift bei „Ausfallbürgschaft" NICHT — der Begriff steht dort
    nicht am Wortanfang. Genau deshalb ist die Ausfallbürgschaft ein eigener
    Eintrag, und genau deshalb war Tims Frage vom 04.09.2026 unbeantwortbar.
    """
    assert glossar.finde("Der Bebauungsplans wegen")[0]["begriff"] == "Bebauungsplan"
    treffer = {t["begriff"] for t in glossar.finde("Eine Ausfallbürgschaft", max_n=9)}
    assert treffer == {"Ausfallbürgschaft"}, treffer


def test_laengster_begriff_gewinnt():
    for text, erwartet in [("Der Doppelhaushalt 2026", "Doppelhaushalt"),
                           ("Der Satzungsbeschluss fiel", "Satzungsbeschluss"),
                           ("Ein Aufwandsspaltungsbeschluss", "Aufwandsspaltung")]:
        assert glossar.finde(text)[0]["begriff"] == erwartet, text


def test_jeder_begriff_nur_einmal():
    treffer = glossar.finde("Der Haushalt und noch einmal der Haushalt", max_n=9)
    assert [t["begriff"] for t in treffer] == ["Haushalt"]


def test_antwort_prompt_traegt_die_erklaerung():
    """Der Block muss im Prompt landen — und ausdrücklich KEIN Beschluss sein."""
    msgs, _ = qa._answer_messages("Was ist eine Ausfallbürgschaft?", [
        {"id": 7, "title": "Bürgschaft Klinikum", "official_text": "x",
         "session_date": "2022-05-01"}])
    prompt = msgs[0]["content"]
    assert "WAS DIE FACHWÖRTER BEDEUTEN" in prompt
    assert "Ausfallbürgschaft: Eine Bürgschaft" in prompt
    assert "nie mit [id] zitieren" in prompt


def test_ohne_fachwort_kein_block():
    """Eine Frage ohne Fachwort bekommt keinen leeren Absatz in den Prompt."""
    msgs, _ = qa._answer_messages("Was ist am Dobbenteich geplant?", [])
    assert "WAS DIE FACHWÖRTER BEDEUTEN" not in msgs[0]["content"]


def test_vereinfachen_zieht_die_begriffe_aus_der_antwort():
    """„Erklär das einfacher" nennt selbst kein Fachwort — die vorige Antwort schon."""
    msgs, _ = qa.vereinfachen_messages(
        "Erklär das bitte einfacher",
        "Die Stadt übernahm eine Ausfallbürgschaft; der Verwaltungsausschuss stimmte zu.",
        [])
    prompt = msgs[0]["content"]
    assert "Ausfallbürgschaft:" in prompt
    assert "Verwaltungsausschuss:" in prompt


def test_recherche_bericht_bekommt_die_erklaerung_auch():
    """Der lange Bericht rendert durch dieselbe Komponente wie die kurze
    Antwort — die Tooltips lagen also schon darin, der Prompt hatte die
    Erklärung aber nicht."""
    gestellt: dict = {}

    def merken(**kwargs):
        gestellt.update(kwargs)
        return iter(())

    alt, llm.chat_stream = llm.chat_stream, merken
    try:
        list(qa.deep_bericht_stream("Was ist eine Ausfallbürgschaft?", []))
    finally:
        llm.chat_stream = alt
    prompt = gestellt["messages"][0]["content"]
    assert "WAS DIE FACHWÖRTER BEDEUTEN" in prompt
