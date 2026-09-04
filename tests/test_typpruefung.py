"""Wächter für den Geltungsbereich der Typprüfung (`pyrightconfig.json`).

**Wogegen.** Ein Typprüfer stirbt nicht daran, dass jemand ihn abschaltet —
er stirbt daran, dass ein roter Lauf mit einem Eintrag in ``exclude``
beruhigt wird. Nach dem dritten Mal prüft er nichts mehr, meldet aber weiter
„grün". Deshalb steht hier, was Stufe 1 abdeckt, und zwar so, dass ein
Herausnehmen den Test rot macht statt die CI grün.

**Beide Richtungen**, wie jeder Wächter hier: Fehlt etwas im Geltungsbereich?
Und ist eine Ausnahme überflüssig geworden — also inzwischen von selbst
sauber und damit reif für die nächste Stufe?
"""
from __future__ import annotations

import collections
import functools
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
KONFIG = WURZEL / "pyrightconfig.json"

#: Was Stufe 1 abdeckt. Wer hier etwas herausnimmt, nimmt es aus der CI —
#: das soll eine bewusste Änderung an dieser Liste sein, kein Nebeneffekt.
STUFE_1 = ("kern", "web/backend/app")

#: Verzeichnisse mit Projekt-Code, die (noch) nicht geprüft werden, mit dem
#: Grund. Jeder Eintrag ist eine Schuld, kein Zustand.
NOCH_NICHT = {
    "web/backend/app/routers":
        "Die Router bauen ihre Antwort-Dicts aus Store-Methoden, die "
        "`dict[str, Any]` liefern. Sinnvoll wird die Prüfung mit einem "
        "typisierten Store — dann fängt sie die Fehlerklasse aus "
        "`antworten.py`: fehlender Pflichtschlüssel (500) und stumm "
        "abgeschnittenes Feld.",
}


def _konfig() -> dict:
    """`pyrightconfig.json` mit ``//``-Kommentaren lesen.

    pyright erlaubt sie, ``json.load`` nicht. Die Zeilen fliegen raus; in
    keiner davon steht ein ``//`` innerhalb einer Zeichenkette (und stünde es
    dort, meldete der Test es als Syntaxfehler statt still das Falsche zu
    prüfen).
    """
    roh = KONFIG.read_text(encoding="utf-8")
    ohne = re.sub(r"^\s*//.*$", "", roh, flags=re.MULTILINE)
    return json.loads(ohne)


def test_stufe_1_steht_vollstaendig_im_geltungsbereich():
    include = _konfig()["include"]
    fehlt = [p for p in STUFE_1 if p not in include]
    assert not fehlt, (
        f"{fehlt} steht nicht mehr in `include` von pyrightconfig.json. "
        "Diese Pfade sind die geteilte Infrastruktur — sie ungeprüft zu "
        "lassen, ist die teuerste der möglichen Abkürzungen. Wenn das "
        "Absicht ist, gehört STUFE_1 in dieser Datei mit geändert.")


def test_keine_stillen_zusatz_ausnahmen():
    """`exclude` darf Werkzeug-Verzeichnisse nennen — und sonst nur das,
    was oben mit Grund steht."""
    werkzeug = {"**/__pycache__", "**/node_modules", "**/.venv"}
    exclude = set(_konfig()["exclude"])
    unerklaert = exclude - werkzeug - set(NOCH_NICHT)
    assert not unerklaert, (
        f"Neue Ausnahme(n) in pyrightconfig.json: {sorted(unerklaert)}. "
        "Eine Ausnahme ist eine Schuld und braucht einen Grund: Trag sie in "
        "NOCH_NICHT in tests/test_typpruefung.py ein — mit dem, was passieren "
        "muss, damit sie wieder verschwindet.")


def test_jede_ausnahme_zeigt_auf_vorhandenen_code():
    for pfad in NOCH_NICHT:
        assert (WURZEL / pfad).is_dir(), (
            f"NOCH_NICHT nennt {pfad!r}, das Verzeichnis gibt es nicht mehr. "
            "Eintrag in tests/test_typpruefung.py und in pyrightconfig.json "
            "löschen.")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="pyright braucht eine Node-Laufzeit")
def test_ausnahmen_sind_noch_noetig():
    """Die zweite Richtung: Ist eine Ausnahme sauber geworden?

    Dann ist sie überflüssig, und der Geltungsbereich soll wachsen. Ohne
    diesen Test bliebe ein Verzeichnis für immer draußen, nur weil es einmal
    rot war.
    """
    for pfad, grund in NOCH_NICHT.items():
        r = subprocess.run(
            [sys.executable, "-m", "pyright", "--pythonpath", sys.executable,
             "--outputjson", "--project", "/dev/null", pfad],
            cwd=WURZEL, capture_output=True, text=True)
        if not r.stdout.strip():
            pytest.skip(f"pyright nicht lauffähig: {r.stderr[:200]}")
        fehler = json.loads(r.stdout)["summary"]["errorCount"]
        assert fehler > 0, (
            f"{pfad} meldet keine Typfehler mehr — die Ausnahme ist "
            f"überflüssig. Aus `exclude` in pyrightconfig.json und aus "
            f"NOCH_NICHT hier entfernen, dann hält die CI es fest.\n"
            f"Grund, aus dem es draußen stand: {grund}")


# ---------------------------------------------------------------------------
# Der Schuldenstand — was noch NICHT im Geltungsbereich ist.
# ---------------------------------------------------------------------------
#
# Der Gate oben ist hart: `kern/` und der Backend-Kern müssen NULL Befunde
# haben. Der Rest des Bestands steht außerhalb, und das hieße ohne diesen Test:
# gar keine Prüfung. Ein neues `x.split()[0]` auf einem `str | None` in
# `council/` fällt dann niemandem auf.
#
# Die Sperrklinke dreht das um: Die Zahl DARF NICHT STEIGEN. Wer eine Datei
# anfasst und dabei einen Befund erzeugt, merkt es sofort; wer aufräumt, senkt
# die Zahl und macht den Fortschritt sichtbar. Kein Aufräumen wird verlangt,
# nur kein Rückschritt geduldet.
#
# Gemessen mit `pyrightconfig.ratsche.json` — derselben Einstellung wie der
# Gate, nur über den ganzen Bestand.

RATSCHE = WURZEL / "pyrightconfig.ratsche.json"

#: Stand vom 04.09.2026. **Diese Zahlen dürfen nur SINKEN.** Wer aufräumt,
#: trägt die neue Zahl hier ein — das ist der halbe Lohn der Arbeit.
SCHULDEN = {
    "council": 194,
    "web/backend/app/routers": 111,
    "scripts": 44,
    "eval": 7,
}


def _bereich(rel: str) -> str:
    if rel.startswith("web/backend/app/routers/"):
        return "web/backend/app/routers"
    if rel.startswith("web/backend/app/"):
        return "web/backend/app"
    return rel.split("/")[0]


@functools.lru_cache(maxsize=1)
def _befunde_je_bereich() -> dict[str, int] | None:
    """Ein pyright-Lauf für alle drei Tests — er kostet rund fünf Sekunden."""
    r = subprocess.run(
        [sys.executable, "-m", "pyright", "--pythonpath", sys.executable,
         "--project", str(RATSCHE), "--outputjson"],
        cwd=WURZEL, capture_output=True, text=True)
    if not r.stdout.strip():
        return None
    daten = json.loads(r.stdout)
    zaehler: collections.Counter[str] = collections.Counter()
    for d in daten["generalDiagnostics"]:
        if d["severity"] != "error":
            continue
        rel = Path(d["file"]).resolve().relative_to(WURZEL).as_posix()
        zaehler[_bereich(rel)] += 1
    return dict(zaehler)


def test_die_ratsche_misst_dasselbe_wie_der_gate():
    """Beide Konfigurationen müssen dieselben Regeln fahren.

    Zählte die Ratsche milder als der Gate, ginge ein Befund im Gate-Bereich
    hier durch — und der Schuldenstand wäre eine Zahl über etwas anderes.
    """
    gate = _konfig()
    ratsche = json.loads(re.sub(r"^\s*//.*$", "", RATSCHE.read_text(encoding="utf-8"),
                                flags=re.MULTILINE))
    for feld in ("typeCheckingMode", "pythonVersion",
                 "reportMissingImports", "reportMissingModuleSource"):
        assert ratsche[feld] == gate[feld], (
            f"`{feld}` weicht ab: Gate {gate[feld]!r}, Ratsche {ratsche[feld]!r}. "
            "Beide müssen dieselben Regeln fahren, sonst zählt der "
            "Schuldenstand etwas anderes als der Gate prüft.")
    # Die Ratsche darf NICHTS ausnehmen, was der Gate ausnimmt — sonst wäre
    # genau der Bereich unbeobachtet, um dessentwillen es sie gibt.
    for pfad in NOCH_NICHT:
        assert pfad not in ratsche["exclude"], (
            f"{pfad} steht auch in der Ratsche unter `exclude` — dann zählt "
            "sie ihn nicht, und er ist völlig unbeobachtet.")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="pyright braucht eine Node-Laufzeit")
def test_der_schuldenstand_steigt_nicht():
    ist = _befunde_je_bereich()
    if ist is None:
        pytest.skip("pyright nicht lauffähig")

    gestiegen = {b: (ist.get(b, 0), soll) for b, soll in SCHULDEN.items()
                 if ist.get(b, 0) > soll}
    assert not gestiegen, (
        "Neue Typbefunde außerhalb des Geltungsbereichs:\n  "
        + "\n  ".join(f"{b}: {jetzt} statt {soll} (+{jetzt - soll})"
                       for b, (jetzt, soll) in sorted(gestiegen.items()))
        + "\n\nSie stehen nicht im harten Gate, aber sie sind neu. Zeig sie dir an:\n"
          "  .venv/bin/pyright --project pyrightconfig.ratsche.json <bereich>")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="pyright braucht eine Node-Laufzeit")
def test_der_schuldenstand_ist_nicht_veraltet():
    """Die zweite Richtung: Ist die Zahl GESUNKEN, gehört sie nachgetragen.

    Sonst wächst zwischen Zahl und Wirklichkeit ein Puffer, in dem neue
    Befunde unbemerkt Platz haben — die Sperrklinke griffe dann erst wieder,
    wenn der Puffer voll ist.
    """
    ist = _befunde_je_bereich()
    if ist is None:
        pytest.skip("pyright nicht lauffähig")

    gesunken = {b: (ist.get(b, 0), soll) for b, soll in SCHULDEN.items()
                if ist.get(b, 0) < soll}
    assert not gesunken, (
        "Aufgeräumt — schön! Trag die neuen Zahlen in SCHULDEN "
        "(tests/test_typpruefung.py) ein:\n  "
        + "\n  ".join(f'"{b}": {jetzt},   # war {soll}'
                       for b, (jetzt, soll) in sorted(gesunken.items())))


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="pyright braucht eine Node-Laufzeit")
def test_ein_bereich_ohne_schulden_gehoert_in_den_geltungsbereich():
    """Steht ein Bereich bei null, ist die Schuld getilgt — dann gehört er in
    `include` und nicht mehr in diese Liste. Ohne das bliebe er für immer in
    der weichen Prüfung, obwohl er den harten Gate bestehen würde."""
    ist = _befunde_je_bereich()
    if ist is None:
        pytest.skip("pyright nicht lauffähig")

    fertig = sorted(b for b, soll in SCHULDEN.items() if soll == 0 and ist.get(b, 0) == 0)
    assert not fertig, (
        f"Diese Bereiche sind sauber: {fertig}. Ab in `include` von "
        "pyrightconfig.json (und aus SCHULDEN raus) — dann hält der harte "
        "Gate sie, statt der Sperrklinke.")
