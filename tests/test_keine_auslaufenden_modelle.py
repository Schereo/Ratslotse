"""Kein Code-Vorgabewert zeigt auf ein auslaufendes Modell.

Gemini 2.5 Flash, Flash Lite und Pro verschwinden am 20.10.2026 bei
OpenRouter — und Tim will Gemini 2.5 Flash nirgends mehr (01.10.2026: zu viele
Falschaussagen). Ein Vorgabewert, der darauf zeigt, liefe nach dem Stichtag
in einen Fehler, den erst ein Nutzer sieht.

Geprüft werden Vorgabewerte im Code: ``os.environ.get("X", "<modell>")`` und
Zuweisungen an ``…MODEL… = "<modell>"``. Preistabellen, Messregister und
Kommentare zählen nicht. Was die ``.env`` eines Servers setzt, zeigt
``.github/workflows/ops-modelle.yml``.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
ORDNER = ("council", "kern", "scripts", "web/backend/app", "eval")
AUSLAUFEND = re.compile(r"google/gemini-2\.5-(?:flash|flash-lite|pro)\b")

_VORGABE = re.compile(
    r"""environ\.get\(\s*["'](?P<var>[A-Z0-9_]+)["']\s*,\s*["'](?P<m1>[^"']+)["']"""
    r"""|^\s*(?P<name>[A-Z0-9_]*MODEL[A-Z0-9_]*)\s*(?::[^=]+)?=\s*["'](?P<m2>[^"']+)["']""",
    re.MULTILINE)

#: Ausnahmen mit Grund. Jede ist eine Schuld: Der Test meldet auch, wenn sie
#: nicht mehr gebraucht wird.
AUSNAHMEN = {
    # Rückfall der Livestream-Transkription, wenn Gladia ausfällt. Er braucht
    # AUDIO-Eingabe, die GPT-6 Luna nicht kann — Nachfolger wählt Tim
    # (Kandidaten mit Audio: Voxtral, GPT Audio Mini, Gemini 3.x).
    ("council/livestream.py", "COUNCIL_STT_MODEL"),
    ("scripts/verify_release_runtime.py", "DEFAULT_STT_MODEL"),
}


def _funde() -> set[tuple[str, str]]:
    out = set()
    for ordner in ORDNER:
        for pfad in (WURZEL / ordner).rglob("*.py"):
            if "results" in pfad.parts or "__pycache__" in pfad.parts:
                continue
            text = pfad.read_text(encoding="utf-8")
            for m in _VORGABE.finditer(text):
                modell = m.group("m1") or m.group("m2") or ""
                if AUSLAUFEND.search(modell):
                    out.add((str(pfad.relative_to(WURZEL)), m.group("var") or m.group("name")))
    return out


def test_no_code_default_points_to_a_retiring_model():
    neu = _funde() - AUSNAHMEN
    assert not neu, (
        f"{sorted(neu)} zeigt auf ein Modell, das am 20.10.2026 ausläuft. "
        "Vorgabe auf openai/gpt-6-luna (Text) umstellen; braucht die Stelle Audio, "
        "mit Tim einen Nachfolger wählen.")


def test_exceptions_are_still_needed():
    ueberfluessig = AUSNAHMEN - _funde()
    assert not ueberfluessig, (
        f"{sorted(ueberfluessig)} braucht keine Ausnahme mehr — "
        "aus AUSNAHMEN in tests/test_keine_auslaufenden_modelle.py streichen.")
