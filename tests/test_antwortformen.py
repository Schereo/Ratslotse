"""Ein Endpunkt darf nichts anhängen, was seine Antwortform nicht kennt.

**Der Fehler, gegen den das steht.** ``/council/trends`` rechnete die
Klartext-Namen der Themenfelder aus und hängte sie an die Antwort::

    data = store.activity_trends()
    data["field_labels"] = {…}
    return data                      # -> TrendData

``TrendData`` kannte ``field_labels`` nicht. FastAPI **entfernt undeklarierte
Felder still** — die Route rechnete also etwas aus, das nie ankam. Web und App
lasen es beide als Pflichtfeld: Im Browser lief `d.field_labels[f]` auf
`undefined`, in der App brach der Decoder ab. Beide Trend-Ansichten waren
kaputt, und keine Prüfung sah es.

**Warum kein Typprüfer.** mypy meldet das nicht: ``store.activity_trends()``
gibt ein ``dict`` zurück, und in ein ``dict`` darf man schreiben, was man
will. Die 506 Funde, die mypy auf diesem Bestand hat, sind fast durchweg
etwas anderes (der Store liefert ``list[dict]``, die Form will
``list[TypedDict]``) — eine Klasse, in der ein Fund fast nie ein Fehler ist.
Diese Prüfung hier ist eng und hat auf dem Bestand null Fehlalarme.
"""
from __future__ import annotations

import ast
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
BACKEND = WURZEL / "web" / "backend" / "app"


def _formen() -> dict[str, set[str]]:
    """``{Name der TypedDict-Form: {erlaubte Schlüssel}}``."""
    import sys

    sys.path.insert(0, str(WURZEL))
    from web.backend.app import antworten

    return {
        name: set(obj.__required_keys__) | set(obj.__optional_keys__)
        for name, obj in vars(antworten).items()
        if hasattr(obj, "__required_keys__")
    }


def _angehaengte_schluessel(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, str, str]]:
    """``[(Zeile, Zielvariable, Schlüssel)]`` — was die Funktion nachträglich setzt."""
    aus: list[tuple[int, str, str]] = []
    for knoten in ast.walk(fn):
        # data["x"] = …
        if (isinstance(knoten, ast.Assign) and len(knoten.targets) == 1
                and isinstance(ziel := knoten.targets[0], ast.Subscript)
                and isinstance(ziel.slice, ast.Constant)
                and isinstance(ziel.slice.value, str)):
            aus.append((knoten.lineno, ast.unparse(ziel.value), ziel.slice.value))
        # data.update({"x": …})
        if (isinstance(knoten, ast.Call)
                and isinstance(knoten.func, ast.Attribute)
                and knoten.func.attr == "update"
                and len(knoten.args) == 1
                and isinstance(knoten.args[0], ast.Dict)):
            for schluessel in knoten.args[0].keys:
                if isinstance(schluessel, ast.Constant) and isinstance(schluessel.value, str):
                    aus.append((knoten.lineno, ast.unparse(knoten.func.value), schluessel.value))
    return aus


def _befunde() -> list[str]:
    formen = _formen()
    gefunden: list[str] = []
    for datei in sorted(BACKEND.rglob("*.py")):
        baum = ast.parse(datei.read_text())
        for fn in ast.walk(baum):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.returns is None:
                continue
            erlaubt = formen.get(ast.unparse(fn.returns))
            if erlaubt is None:
                continue
            # Nur was am Ende auch WIRKLICH herausgeht: `return data`.
            zurueck = {
                ast.unparse(k.value) for k in ast.walk(fn)
                if isinstance(k, ast.Return) and isinstance(k.value, ast.Name)
            }
            for zeile, ziel, schluessel in _angehaengte_schluessel(fn):
                if ziel in zurueck and schluessel not in erlaubt:
                    gefunden.append(
                        f"{datei.relative_to(WURZEL)}:{zeile} — {fn.name}() gibt "
                        f"{ast.unparse(fn.returns)} zurück, setzt aber "
                        f"{ziel}[{schluessel!r}]"
                    )
    return gefunden


def test_kein_endpunkt_haengt_ein_unbekanntes_feld_an():
    befunde = _befunde()
    assert not befunde, (
        "Diese Felder werden gerechnet und dann von FastAPI wieder entfernt, "
        "weil die Antwortform sie nicht kennt:\n  "
        + "\n  ".join(befunde)
        + "\n\nDas Feld gehört in web/backend/app/antworten.py — oder die "
          "Zuweisung ist überflüssig."
    )
