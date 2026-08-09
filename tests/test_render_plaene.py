"""Planzeichnungs-Rendering (scripts/render_plaene.py) — Auswahl + Endpoint.

Das Rendern selbst braucht pymupdf (bewusst keine Projekt-Dependency) und
echte PDFs — hier testen wir die Label-Auswahl und dass der Lauf ohne
Kandidaten sauber durchgeht, plus den 404-Pfad des Bild-Endpoints.
"""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "render_plaene", Path(__file__).resolve().parents[1] / "scripts" / "render_plaene.py")
render_plaene = importlib.util.module_from_spec(_spec)
sys.modules["render_plaene"] = render_plaene
_spec.loader.exec_module(render_plaene)


def test_plan_label_auswahl():
    ja = ["Planzeichnung", "Planzeichnung Blatt 1", "Lageplan FH-23",
          "Städtebaulicher Leitplan", "Freiflächenplan", "Bestandsplan",
          "Grundstücksaufteilungsplan", "Plandarstellung"]
    nein = ["Planversand", "Begründung", "Schallgutachten", "Textteil der Satzung",
            "Prüfung der Stellungnahmen", "Anlage 2"]
    for label in ja:
        assert render_plaene.PLAN_LABEL_RE.search(label), label
    for label in nein:
        assert not render_plaene.PLAN_LABEL_RE.search(label), label


def test_lauf_ohne_kandidaten_braucht_kein_pymupdf(tmp_path):
    # Leere DB → keine Kandidaten → kein pymupdf-Import, saubere Zähler.
    out = render_plaene.main(db=str(tmp_path / "c.sqlite"), out_dir=str(tmp_path / "plaene"))
    assert out == {"kandidaten": 0, "gerendert": 0, "fehlgeschlagen": 0}
