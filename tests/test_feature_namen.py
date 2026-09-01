"""Jeder LLM-Aufruf, den das Kosten-Tracking zählt, hat eine Beschriftung.

Hintergrund: `kern/llm.py` schreibt den Wert aus `_feature="…"` nach
`llm_usage.feature`; das Admin-Panel beschriftet ihn über `FEATURE_LABELS`
in `admin/page.tsx`. Fehlt ein Eintrag, zeigt die Tabelle den rohen
Schlüssel — das fiel nie auf, solange der deutsch war. Seit die Werte
englisch sind (01.09.2026), stünde dort `attachment_ocr` statt
„Anlagen-Texterkennung", also prüft das hier eine Maschine.

Und in die Gegenrichtung: Eine Beschriftung ohne Aufruf ist entweder ein
Tippfehler oder ein Rest — beides soll auffallen, statt still danebenzustehen.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
#: Wo `_feature=` gesetzt wird.
QUELLEN = ("council", "kern", "scripts", "web/backend", "eval")
ADMIN = WURZEL / "web" / "frontend" / "app" / "(app)" / "admin" / "page.tsx"

#: Werte, die es nur noch im BESTAND gibt — sie tauchen in der Kostentabelle
#: auf, im Code aber nicht mehr. Ohne diese Ausnahme müsste man die
#: Beschriftung löschen und die Historie damit unlesbar machen.
NUR_BESTAND = {"exp_session_classification"}


def _aus_dem_code() -> set[str]:
    aus: set[str] = set()
    for wz in QUELLEN:
        for pfad in (WURZEL / wz).rglob("*.py"):
            # Nur echte Bezeichner: `kern/llm.py` erklärt den Parameter im
            # Docstring als `_feature="…"`, und das ist kein Feature.
            aus |= set(re.findall(r'_feature\s*=\s*"([a-z_0-9]+)"', pfad.read_text()))
    return aus


def _aus_der_oberflaeche() -> set[str]:
    text = ADMIN.read_text()
    block = re.search(r"const FEATURE_LABELS: Record<string, string> = \{(.*?)\n\};",
                      text, re.S)
    assert block, "FEATURE_LABELS nicht gefunden — wurde die Tabelle umbenannt?"
    return set(re.findall(r"^\s*([a-z_0-9]+):", block.group(1), re.M))


def test_es_gibt_ueberhaupt_features_zu_pruefen():
    """Fände der Sucher nichts, wäre alles darunter grün und wertlos."""
    assert len(_aus_dem_code()) > 25


def test_jeder_aufruf_traegt_eine_beschriftung():
    fehlt = sorted(_aus_dem_code() - _aus_der_oberflaeche())
    assert not fehlt, ("Ohne Eintrag in FEATURE_LABELS zeigt das Admin-Panel den "
                       f"rohen Schlüssel: {fehlt}")


def test_keine_beschriftung_ohne_aufruf():
    ueberzaehlig = sorted(_aus_der_oberflaeche() - _aus_dem_code() - NUR_BESTAND)
    assert not ueberzaehlig, ("Beschriftung ohne `_feature=`-Aufruf — Tippfehler "
                              f"oder Rest: {ueberzaehlig}")


def test_die_namen_sind_englisch():
    """Der Grund für den Umbau. Eine Handvoll deutscher Wortstämme genügt, um
    einen Rückfall zu erkennen — vollständig sein muss die Liste nicht."""
    deutsch = re.compile(r"anlagen|beschluss|entitaeten|protokoll|themen(?!_)|ziel_|"
                         r"antwort|einfach|kartentext|kritiker|wortbeitr|"
                         r"transkript|ergebnisse|bericht|zerlegung|meinungen|"
                         r"fundstueck|rueckblick|klassifikation|bewertung")
    rueckfall = sorted(f for f in _aus_dem_code() if deutsch.search(f))
    assert not rueckfall, f"deutsche Feature-Namen: {rueckfall}"
