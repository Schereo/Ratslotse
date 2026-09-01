"""Jeder `Herkunft(...)`-Aufruf im Quelltext muss zum Datensatz passen.

Hintergrund: `Herkunft` prüft seine Felder erst beim Bauen — und gebaut wird
sie in Ingest-Läufen, die keine Testsuite anfasst. Zwei Fehler haben deshalb
den Umbau überlebt:

1. ``scripts/ingest_schulden.py`` übergab noch ``art="stadt"``. Das Feld heißt
   seit #886 ``kind``; der Lauf wäre mit ``TypeError`` gestorben, sobald
   jemand die Schuldenreihe neu einliest.
2. Dieselbe Zeile nannte die Quellenart ``"stadt"``. Die Migration schreibt
   den gespeicherten Wert auf ``city`` um, ``ARTEN`` kennt seither nur noch
   ``city`` — und weil ``Herkunft.key()`` die Art mithasht, hätte derselbe
   Haushaltsplan einen zweiten Eintrag bekommen statt seinen alten wiederzu-
   finden.

Beides sieht man dem Quelltext an, ohne den Lauf zu starten: Diese Prüfung
liest die Aufrufe aus dem Syntaxbaum.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.herkunft import ARTEN, Herkunft  # noqa: E402

#: Wo Herkünfte gebaut werden.
QUELLEN = ("council", "scripts", "web/backend")


def _ist_herkunft(knoten: ast.Call) -> bool:
    ziel = knoten.func
    name = (ziel.attr if isinstance(ziel, ast.Attribute)
            else ziel.id if isinstance(ziel, ast.Name) else "")
    if name == "Herkunft":
        return True
    # Manche Läufe sammeln die immer gleichen Felder erst in einem `dict(...)`
    # und geben es als `**anker` weiter — `ingest_schulden.py` tut genau das,
    # und dort stand der Fehler. Ein Dict mit `url=` UND einer Quellenart hat
    # die Form einer Herkunft; etwas anderes ist es in diesem Code nicht.
    if name != "dict":
        return False
    schluessel = {kw.arg for kw in knoten.keywords}
    return "url" in schluessel and bool(schluessel & {"kind", "art"})


def _aufrufe() -> list[tuple[Path, ast.Call]]:
    aus = []
    for wurzel in QUELLEN:
        for pfad in (WURZEL / wurzel).rglob("*.py"):
            baum = ast.parse(pfad.read_text(), filename=str(pfad))
            for knoten in ast.walk(baum):
                if isinstance(knoten, ast.Call) and _ist_herkunft(knoten):
                    aus.append((pfad, knoten))
    return aus


def test_es_gibt_ueberhaupt_aufrufe_zu_pruefen():
    """Fände der Sucher nichts, wäre alles darunter grün und wertlos."""
    assert len(_aufrufe()) > 20


def test_kein_aufruf_uebergibt_ein_feld_das_es_nicht_gibt():
    """`art=` war der Name vor #886 — ein Lauf damit stirbt im TypeError."""
    erlaubt = {f.name for f in Herkunft.__dataclass_fields__.values()}
    fehler = []
    for pfad, knoten in _aufrufe():
        for kw in knoten.keywords:
            if kw.arg is not None and kw.arg not in erlaubt:
                fehler.append(f"{pfad.relative_to(WURZEL)}:{knoten.lineno}: {kw.arg}=")
    assert not fehler, "Unbekannte Felder in Herkunft(...):\n" + "\n".join(fehler)


def test_jede_genannte_quellenart_steht_im_register():
    """Eine Art, die `ARTEN` nicht kennt, fliegt im `__post_init__` — und
    hätte davor einen zweiten Eintrag für dasselbe Dokument angelegt, weil der
    Fingerabdruck die Art mithasht."""
    fehler = []
    for pfad, knoten in _aufrufe():
        for kw in knoten.keywords:
            if kw.arg == "kind" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str) and kw.value.value not in ARTEN:
                fehler.append(f"{pfad.relative_to(WURZEL)}:{knoten.lineno}: "
                              f"kind={kw.value.value!r}")
    assert not fehler, ("Unbekannte Quellenarten (bekannt: "
                        f"{', '.join(sorted(ARTEN))}):\n" + "\n".join(fehler))


def test_das_register_selbst_ist_englisch():
    """Der gespeicherte Wert und `ARTEN` müssen dasselbe Wort führen —
    sonst weist `__post_init__` genau das zurück, was in der Datenbank steht.
    `ris`, `opendata` und `lsn` sind Kürzel und bleiben."""
    assert "stadt" not in ARTEN and "city" in ARTEN
    with pytest.raises(ValueError):
        Herkunft(kind="stadt", probe="unbekannt", url="https://www.oldenburg.de/x")
