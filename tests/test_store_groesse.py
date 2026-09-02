"""Sperrklinke: ``CouncilStore`` wächst nicht weiter zu.

**Der Zustand, gegen den das steht.** ``council/store.py`` trug am 02.09.2026
15.744 Zeilen in EINER Klasse mit 506 Methoden. Jeder Cron und jede Route
hängt daran; wer dort etwas sucht, sucht lange, und wer etwas ändert, sieht
nicht, wen er trifft. Die Ecken ziehen nacheinander aus; jede als Mixin, das ``CouncilStore``
miterbt (``ECKEN`` unten).

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

#: Stand nach dem NEUNTEN und vorerst letzten Schnitt (02.09.2026).
#: Darf schrumpfen. Was jetzt noch hier liegt, ist der Kern: Schema und
#: Migrationen, Beschlüsse, Vorlagen, Anlagen, Suche und Embeddings.
HOECHSTENS_METHODEN = 237
HOECHSTENS_ZEILEN = 9979


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


def _mixins():
    import sys

    sys.path.insert(0, str(WURZEL))
    from council.store_fundstuecke import FundstueckeMixin
    from council.store_haushalt import HaushaltMixin
    from council.store_orte import OrteMixin
    from council.store_personen import PersonenMixin
    from council.store_presse import PresseMixin
    from council.store_quiz import QuizMixin
    from council.store_sitzungen import SitzungenMixin
    from council.store_themen import ThemenMixin
    from council.store_wortbeitraege import WortbeitraegeMixin

    #: Ecke → (Mixin, Mindestzahl eigener Methoden).
    return {
        "Fundstücke": (FundstueckeMixin, 9),
        "Haushalt": (HaushaltMixin, 80),
        "Orte": (OrteMixin, 25),
        "Personen": (PersonenMixin, 27),
        "Presse": (PresseMixin, 9),
        "Quiz": (QuizMixin, 12),
        "Sitzungen": (SitzungenMixin, 47),
        "Themen": (ThemenMixin, 30),
        "Wortbeiträge": (WortbeitraegeMixin, 20),
    }


def test_die_ecken_haengen_wirklich_dran():
    """Ein Mixin, das niemand erbt, ist toter Code — und jede Seite dieser Ecke
    wäre ein 500er. Das fällt sonst erst beim ersten Aufruf auf."""
    import sys

    sys.path.insert(0, str(WURZEL))
    from council.store import CouncilStore

    for name, (mixin, mindestens) in _mixins().items():
        assert issubclass(CouncilStore, mixin), name
        eigene = [n for n in vars(mixin) if not n.startswith("__")]
        assert len(eigene) >= mindestens, (name, len(eigene))
        for methode in eigene:
            assert hasattr(CouncilStore, methode), (name, methode)


def test_die_ecken_ueberschneiden_sich_nicht():
    """Zwei Mixins mit demselben Methodennamen: Die Reihenfolge der Basisklassen
    entscheidet dann still, welche gewinnt."""
    import itertools

    namen = {k: {n for n in vars(v[0]) if not n.startswith("__")}
             for k, v in _mixins().items()}
    for a, b in itertools.combinations(sorted(namen), 2):
        assert not namen[a] & namen[b], (a, b, sorted(namen[a] & namen[b]))


def test_migrationen_bleiben_beim_schema():
    """Migrationen gehören der Datenbank als Ganzem, nicht einer ihrer Ecken.

    Beim Quiz-Schnitt wären drei ``_migrate_quiz_*`` fast mit umgezogen; sie
    laufen aus ``_migrate`` heraus und gehören neben das übrige Schema.
    """
    for mixin, _ in _mixins().values():
        wandernde = [n for n in vars(mixin) if n.startswith("_migrate")]
        assert not wandernde, (mixin.__name__, wandernde)
