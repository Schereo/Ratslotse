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


class _Store:
    """Zwei Anträge an vergangenen Punkten, einer schon gelesen."""

    def __init__(self):
        self.auszuege = {1: {"status": "ok", "created_at": "alt", "cost_usd": 0.001}}
        self.fenster = None

    def antraege_kommender_punkte(self, seit, bis):
        self.fenster = (seit, bis)
        return [{"ksinr": 9, "item_number": "Ö 5", "document_id": 1},
                {"ksinr": 9, "item_number": "Ö 5", "document_id": 2}]

    def motion_extract(self, document_id):
        return self.auszuege.get(document_id)


def test_bericht_zaehlt_ungelesene_ohne_modell(monkeypatch):
    def nie(*a, **k):
        raise AssertionError("im Bericht wird nichts gelesen")
    monkeypatch.setattr(mod.motions, "extract_one", nie)
    s = _Store()
    r = mod.antraege_lesen(s, 365, schreiben=False, max_usd=1, max_minuten=1)
    assert r == {"antraege": 2, "offen": 1, "gelesen": 0}
    from datetime import date, timedelta
    assert s.fenster[0] == (date.today() - timedelta(days=365)).isoformat()


def test_lesen_meldet_die_kosten_an_die_grenze(monkeypatch):
    """Ohne ``stopp.ausgeben`` deckelt die Kostengrenze das Lesen nicht."""
    s = _Store()
    s.auszuege.pop(1)
    gelesen = []

    def lies(store, document_id, ksinr, item_number):
        gelesen.append(document_id)
        store.auszuege[document_id] = {"status": "ok", "created_at": "neu", "cost_usd": 0.5}
    monkeypatch.setattr(mod.motions, "extract_one", lies)

    class Grenze:
        kosten = 0.0

        def ausgeben(self, usd):
            self.kosten += usd

        def grund(self):
            return "zu teuer" if self.kosten >= 0.4 else None
    g = Grenze()
    r = mod.motions.nachziehen(s, tage_zurueck=365, limit=10, stopp=g)
    assert gelesen == [1] and r["gelesen"] == 1 and g.kosten == 0.5
