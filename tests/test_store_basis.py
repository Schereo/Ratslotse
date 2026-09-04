"""Wächter für die Store-Basis (`council/store_basis.py`) und ihren Sinn.

`CouncilStore` ist aus einem Dutzend Mixins zusammengesetzt. Jedes greift auf
`self._conn` zu, das keines von ihnen anlegt — für ein Werkzeug ist das ein
Zugriff ins Leere, und es waren **1.007 von 1.309** Befunden der Typprüfung.
`StoreBasis` schreibt diesen gemeinsamen Nenner auf.

Hier stehen die zwei Eigenschaften, auf denen das ruht, und die dritte, die
verhindert, dass `store.py` wieder zum Ablageort für fremde Konstanten wird.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from council.store_basis import StoreBasis

WURZEL = Path(__file__).resolve().parents[1]
COUNCIL = WURZEL / "council"

#: Dateien mit Store-Mixins: `council/store_*.py` und die Facetten unter
#: `council/geld/`. Ohne die beiden, die keine Mixins enthalten.
KEINE_MIXINS = {"store_basis.py", "store_helfer.py", "store_schema_migrationen.py"}


def _mixin_dateien() -> list[Path]:
    aus = [p for p in sorted(COUNCIL.glob("store_*.py")) if p.name not in KEINE_MIXINS]
    aus += [p for p in sorted((COUNCIL / "geld").glob("*.py")) if p.name != "__init__.py"]
    return aus


def test_die_basis_ist_zur_laufzeit_leer():
    """DIE Eigenschaft, die den Umbau risikolos macht.

    Der Körper von `StoreBasis` steht vollständig unter `TYPE_CHECKING`. Legte
    sie ein Attribut oder eine Methode an, stünde sie in der
    Methodenauflösung **hinter** allem — und würde in dem Moment gefährlich, in
    dem eine Ecke ihre eigene Definition verliert: Statt eines `AttributeError`
    käme dann still der Platzhalter zurück.
    """
    eigene = [a for a in vars(StoreBasis) if not a.startswith("__")]
    assert eigene == [], (
        f"StoreBasis trägt zur Laufzeit {eigene}. Der ganze Körper gehört unter "
        "`if TYPE_CHECKING:` — sonst überdeckt ein Platzhalter irgendwann eine "
        "echte Methode, ohne dass etwas auffällt.")


@pytest.mark.parametrize("datei", _mixin_dateien(), ids=lambda p: p.name)
def test_jedes_mixin_erbt_die_basis(datei: Path):
    """Ein neues Mixin ohne Basis bringt seine Befunde sofort zurück."""
    baum = ast.parse(datei.read_text(encoding="utf-8"))
    klassen = [k for k in baum.body if isinstance(k, ast.ClassDef)]
    ohne = [k.name for k in klassen
            if not any(isinstance(b, ast.Name) and b.id == "StoreBasis" for b in k.bases)
            and re.search(r"(?:self|cls)\.", ast.unparse(k))]
    assert not ohne, (
        f"{datei.relative_to(WURZEL)}: {ohne} erbt nicht von StoreBasis. "
        "`class X(StoreBasis):` schreiben und "
        "`from council.store_basis import StoreBasis` ergänzen — sonst ist "
        "jeder `self._conn`-Zugriff darin wieder ein Zugriff ins Leere.")


def test_keine_konstante_liegt_beim_falschen_nutzer():
    """Die zweite Richtung: `store.py` ist kein Ablageort für fremde Konstanten.

    Bis 09/2026 standen 44 Klassenattribute auf `CouncilStore`, die je genau
    **ein** Mixin benutzte — 443 Zeilen, die niemand dort suchte. Sie stehen
    jetzt bei ihrem Nutzer. Dieser Test hält das: Wer eine Konstante wieder in
    `store.py` legt, obwohl nur eine Ecke sie liest, wird darauf hingewiesen.
    """
    quelle = (COUNCIL / "store.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    klasse = next(k for k in baum.body
                  if isinstance(k, ast.ClassDef) and k.name == "CouncilStore")
    namen = []
    for kind in klasse.body:
        if isinstance(kind, ast.Assign) and len(kind.targets) == 1 \
                and isinstance(kind.targets[0], ast.Name):
            namen.append(kind.targets[0].id)
        elif isinstance(kind, ast.AnnAssign) and isinstance(kind.target, ast.Name):
            namen.append(kind.target.id)

    texte = {p: p.read_text(encoding="utf-8") for p in _mixin_dateien()}
    falsch = {}
    for n in namen:
        muster = re.compile(rf"(?:self|cls)\.{re.escape(n)}\b")
        nutzer = [p.name for p, t in texte.items() if muster.search(t)]
        # In `store.py` selbst gelesen? Dann gehört sie legitim dorthin.
        if len(nutzer) == 1 and not muster.search(quelle):
            falsch[n] = nutzer[0]
    assert not falsch, (
        "Diese Klassenattribute auf CouncilStore werden von genau EINEM Mixin "
        "gelesen und von `store.py` selbst gar nicht — sie gehören in das "
        f"Mixin: {falsch}")
