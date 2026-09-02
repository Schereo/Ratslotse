"""Sperrklinke: ``CouncilStore`` wächst nicht weiter zu.

**Der Zustand, gegen den das steht.** ``council/store.py`` trug am 02.09.2026
15.744 Zeilen in EINER Klasse mit 506 Methoden. Jeder Cron und jede Route
hängt daran; wer dort etwas sucht, sucht lange, und wer etwas ändert, sieht
nicht, wen er trifft. Zwei Ecken sind heraus: der Haushalt
(``council/store_haushalt.py``, 81 Methoden) und die Orte
(``council/store_orte.py``, 27).

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

#: Stand nach dem zweiten Schnitt — Haushalt und Orte sind draußen
#: (02.09.2026). Darf schrumpfen.
HOECHSTENS_METHODEN = 398
HOECHSTENS_ZEILEN = 13567


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


def test_die_ecken_haengen_wirklich_dran():
    """Ein Mixin, das niemand erbt, ist toter Code — und jede Seite dieser Ecke
    wäre ein 500er. Das fällt sonst erst beim ersten Aufruf auf."""
    import sys

    sys.path.insert(0, str(WURZEL))
    from council.store import CouncilStore
    from council.store_haushalt import HaushaltMixin
    from council.store_orte import OrteMixin

    for mixin, mindestens in ((HaushaltMixin, 80), (OrteMixin, 25)):
        assert issubclass(CouncilStore, mixin), mixin.__name__
        eigene = [n for n in vars(mixin) if not n.startswith("__")]
        assert len(eigene) >= mindestens, (mixin.__name__, len(eigene))
        for name in eigene:
            assert hasattr(CouncilStore, name), name


def test_die_ecken_ueberschneiden_sich_nicht():
    """Zwei Mixins mit demselben Methodennamen: Die Reihenfolge der Basisklassen
    entscheidet dann still, welche gewinnt."""
    import sys

    sys.path.insert(0, str(WURZEL))
    from council.store_haushalt import HaushaltMixin
    from council.store_orte import OrteMixin

    a = {n for n in vars(HaushaltMixin) if not n.startswith("__")}
    b = {n for n in vars(OrteMixin) if not n.startswith("__")}
    assert not a & b, sorted(a & b)
