"""Der Wächter in ``scripts/antraege_nachziehen.py``: Anträge Dritter melden,
Fraktionsanträge mit nichtssagendem Label nicht."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "antraege_nachziehen", Path(__file__).resolve().parent.parent / "scripts" / "antraege_nachziehen.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_fraktionsantrag_mit_anlage_label_ist_kein_dritter():
    # 20/0536, Anlage 222952: Ergänzungsantrag von Grünen und SPD
    kopf = ("Ergänzungsantrag an den Kulturausschuss: … die Fraktionen von "
            "BÜNDNIS 90/DIE GRÜNEN und SPD beantragen, der Ausschuss möge …")
    assert not mod._ist_dritter({"label": "Anlage2Antrag", "kopf": kopf})


def test_zuschussantrag_ohne_fraktion_ist_dritter():
    assert mod._ist_dritter({"label": "Zuschussantrag Sportverein", "kopf": "Sehr geehrte Damen und Herren"})
    assert mod._ist_dritter({"label": "Anlage 3 Antrag", "kopf": None})


def test_gewoehnlicher_antrag_ist_kein_dritter():
    assert not mod._ist_dritter({"label": "Änderungsantrag CDU Schulbezirke", "kopf": ""})
