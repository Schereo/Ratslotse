"""Sperrklinke: ``CouncilStore`` wächst nicht weiter zu.

**Der Zustand, gegen den das steht.** ``council/store.py`` trug am 02.09.2026
15.744 Zeilen in EINER Klasse mit 506 Methoden. Jeder Cron und jede Route
hängt daran; wer dort etwas sucht, sucht lange, und wer etwas ändert, sieht
nicht, wen er trifft. Der Haushalt ist als erste Ecke herausgelöst
(``council/store_haushalt.py``, 81 Methoden).

**Warum eine Zahl und kein Verbot.** Verbieten kann man es nicht — manche
Abfrage gehört wirklich in die Mitte. Aber sie soll eine Entscheidung sein und
kein Versehen: Wer diese Zahl anhebt, schreibt dazu, warum die Methode nicht
in eine Ecke gehört.

Die zweite Zahl ist die der Zeilen. Sie fängt, was die erste nicht sieht: eine
bestehende Methode, die um vierhundert Zeilen wächst.
"""
from __future__ import annotations

import ast
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
STORE = WURZEL / "council" / "store.py"

#: Stand nach dem Herauslösen des Haushalts (02.09.2026). Darf schrumpfen.
HOECHSTENS_METHODEN = 425
HOECHSTENS_ZEILEN = 14342


def _klasse() -> ast.ClassDef:
    baum = ast.parse(STORE.read_text())
    return next(k for k in baum.body
                if isinstance(k, ast.ClassDef) and k.name == "CouncilStore")


def test_die_klasse_bekommt_keine_methoden_dazu():
    methoden = [m for m in _klasse().body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert len(methoden) <= HOECHSTENS_METHODEN, (
        f"CouncilStore hat jetzt {len(methoden)} eigene Methoden (erlaubt: "
        f"{HOECHSTENS_METHODEN}).\n"
        "Neue Abfragen einer Fachecke gehören in ein eigenes Mixin — der "
        "Haushalt steht in council/store_haushalt.py, die Facetten der KI-Frage "
        "in council/geld/. Gehört sie wirklich in die Mitte, ist die Zahl hier "
        "anzuheben; dann bitte mit einem Satz dazu, warum."
    )


def test_die_datei_waechst_nicht():
    zeilen = len(STORE.read_text().splitlines())
    assert zeilen <= HOECHSTENS_ZEILEN, (
        f"council/store.py hat {zeilen} Zeilen (erlaubt: {HOECHSTENS_ZEILEN})."
    )


def test_der_haushalt_haengt_wirklich_dran():
    """Ein Mixin, das niemand erbt, ist toter Code — und alle Haushalts-Seiten
    wären 500er. Das fällt sonst erst beim ersten Aufruf auf."""
    import sys

    sys.path.insert(0, str(WURZEL))
    from council.store import CouncilStore
    from council.store_haushalt import HaushaltMixin

    assert issubclass(CouncilStore, HaushaltMixin)
    eigene = [n for n in vars(HaushaltMixin) if not n.startswith("__")]
    assert len(eigene) >= 80, len(eigene)
    for name in eigene:
        assert hasattr(CouncilStore, name), name
