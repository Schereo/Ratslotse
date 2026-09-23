"""Die Kostenbremse der Messläufe (``eval/kostenbremse.py``) — offline.

Tims Regel vom 23.09.2026: teure Modelle nur in kleinen Benchmarks. Anlass:
ein voller Recherche-Lauf mit GPT-6 Sol für 3,10 $ plus ein abgebrochener
zweiter für 2,44 $, wo eine Stichprobe dieselbe Frage beantwortet hätte.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from eval import kostenbremse as kb  # noqa: E402
from eval import pruefstand as ps  # noqa: E402
from eval import run_fakten as rf  # noqa: E402


def _faelle() -> list[dict]:
    return rf._faelle_waehlen(rf.lade(), None, None, "deep")


# --------------------------------------------------------------------------- #
# Preise und Schätzung
# --------------------------------------------------------------------------- #

def test_sol_ist_teuer_luna_nicht():
    assert kb.teuer("openai/gpt-6-sol")
    assert not kb.teuer("openai/gpt-6-luna")
    assert not kb.teuer("google/gemini-3.1-flash-lite")
    assert not kb.teuer("gibt/es-nicht")  # unbekannt ist nicht „teuer“, aber nicht schätzbar


def test_schaetzung_rechnet_listenpreis_mal_tokens():
    # GPT-6 Sol: 2 $ Eingabe, 10 $ Ausgabe je Mio.
    assert kb.schaetzen("openai/gpt-6-sol", [1_000_000], 100_000) == pytest.approx(3.0)
    assert kb.schaetzen("openai/gpt-6-sol", [500_000, 500_000], 0) == pytest.approx(2.0)
    assert kb.schaetzen("gibt/es-nicht", [1], 1) is None


def test_bremse_haelt_ueber_der_grenze_an():
    assert kb.bremse(0.5, max_kosten=1.0, teuer_ok=False, modell="m") is None
    grund = kb.bremse(4.56, max_kosten=1.0, teuer_ok=False, modell="m")
    assert grund and "4.56 $" in grund and "--teuer-ok" in grund
    assert kb.bremse(4.56, max_kosten=1.0, teuer_ok=True, modell="m") is None
    # Ohne Preis keine Schätzung — und ohne ausdrückliches Ja kein Lauf.
    assert "kern/usage.PRICES" in kb.bremse(None, max_kosten=1.0, teuer_ok=False, modell="x/y")


def test_schaetzung_der_recherche_trifft_die_messung():
    """Gegen die echten Läufe vom 23.09.2026: Luna 0,23 $ für 55 Berichte,
    Sol 3,10 $. Die Schätzung darf darüber liegen, nicht darunter."""
    zeichen = {("deep", f["id"]): 75_000 for f in _faelle()}
    luna = rf.kosten_schaetzen("openai/gpt-6-luna", _faelle(), "deep", zeichen)
    sol = rf.kosten_schaetzen("openai/gpt-6-sol", _faelle(), "deep", zeichen)
    assert 0.2 <= luna <= 0.5
    assert 3.1 <= sol <= 6.0


# --------------------------------------------------------------------------- #
# Stichprobe
# --------------------------------------------------------------------------- #

def test_stichprobe_ist_fest_geschichtet_und_vollstaendig():
    faelle = _faelle()
    a, b = kb.stichprobe(faelle, 15), kb.stichprobe(faelle, 15)
    assert [f["id"] for f in a] == [f["id"] for f in b]  # feste Saat
    assert len(a) == 15
    schichten = Counter(kb.schicht_fakten(f) for f in a)
    # Jede Schicht der Auswahl ist dabei — auch „nicht in den Daten“ (6 von 55).
    assert set(schichten) == {kb.schicht_fakten(f) for f in faelle}
    assert 2 <= schichten["nicht-in-daten"] <= 3
    # Haushalt und Rat gemischt, wie beauftragt.
    assert any(f["id"].startswith("hh-") for f in a) and any(f["id"].startswith("rat-") for f in a)
    # Reihenfolge der Eingabe bleibt.
    ids = [f["id"] for f in faelle]
    assert [f["id"] for f in a] == sorted((f["id"] for f in a), key=ids.index)


def test_stichprobe_groesser_als_die_auswahl_nimmt_alles():
    faelle = _faelle()[:5]
    assert kb.stichprobe(faelle, 15) == faelle


def test_teures_modell_bekommt_von_selbst_die_stichprobe():
    faelle = _faelle()
    teil, hinweis = kb.auswahl_fuer("openai/gpt-6-sol", faelle, stichprobe_n=None, voll=False)
    assert len(teil) == kb.STICHPROBE_N and hinweis and "--voll" in hinweis
    alle, hinweis = kb.auswahl_fuer("openai/gpt-6-sol", faelle, stichprobe_n=None, voll=True)
    assert alle == faelle and hinweis is None
    alle, _ = kb.auswahl_fuer("openai/gpt-6-luna", faelle, stichprobe_n=None, voll=False)
    assert alle == faelle
    teil, _ = kb.auswahl_fuer("openai/gpt-6-luna", faelle, stichprobe_n=12, voll=False)
    assert len(teil) == 12


# --------------------------------------------------------------------------- #
# Die beiden Läufer
# --------------------------------------------------------------------------- #

def test_run_fakten_bricht_vor_dem_ersten_aufruf_ab(monkeypatch):
    """Sol, volle Recherche-Auswahl: über der Grenze → Abbruch mit Schätzung,
    bevor ein Backend startet (``ein_lauf`` wird nie erreicht)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "nur-fuer-den-test")
    monkeypatch.setattr(rf, "ein_lauf", lambda *a, **k: pytest.fail("Lauf trotz Bremse"))
    with pytest.raises(SystemExit) as exc:
        rf.main(["--kanal", "deep", "--auswahl", "deep", "--modell", "openai/gpt-6-sol",
                 "--voll", "--nicht-speichern"])
    assert "geschätzt" in str(exc.value) and "--teuer-ok" in str(exc.value)


def test_run_fakten_laesst_die_stichprobe_eines_billigen_modells_laufen(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "nur-fuer-den-test")
    gesehen: dict = {}

    def attrappe(modell, faelle, **kw):
        gesehen["n"] = len(faelle)
        raise SystemExit(0)

    monkeypatch.setattr(rf, "ein_lauf", attrappe)
    with pytest.raises(SystemExit):
        rf.main(["--kanal", "deep", "--auswahl", "deep", "--modell", "openai/gpt-6-luna",
                 "--stichprobe", "12", "--nicht-speichern"])
    assert gesehen["n"] == 12


def _suite(name: str) -> ps.Suite:
    return ps.SUITEN[name]


def test_pruefstand_schaetzt_aus_dem_letzten_lauf(tmp_path):
    ordner = tmp_path / "fakten-rat"
    ordner.mkdir()
    (ordner / "openai-gpt-6-luna-1.json").write_text(json.dumps(
        {"modell": "openai/gpt-6-luna", "kosten_usd": 0.20, "faelle": 91, "ohne_kostenwert": 0}))
    # Sol: 20× Luna in Eingabe und Ausgabe.
    s = ps.kosten_schaetzen(_suite("fakten-rat"), "openai/gpt-6-sol", 2, ordner=tmp_path)
    assert s == pytest.approx(0.20 * 20 * 2)
    teil = ps.kosten_schaetzen(_suite("fakten-rat"), "openai/gpt-6-sol", 1, stichprobe_n=15,
                               ordner=tmp_path)
    assert teil == pytest.approx(0.20 * 20 * 15 / 91)


def test_pruefstand_teures_modell_nur_als_stichprobe(tmp_path):
    # Eine Suite ohne Stichprobe: ohne --voll gar nicht.
    _, grund, _ = ps.kostenpruefung(_suite("orte"), "openai/gpt-6-sol", 1, max_kosten=1.0,
                                    teuer_ok=True, stichprobe_n=None, voll=False, ordner=tmp_path)
    assert grund and "--voll" in grund
    # Die Fakten-Suiten ziehen von selbst die Stichprobe — ohne Vorlauf
    # keine Schätzung, also bei einem teuren Modell nur mit --teuer-ok.
    n, grund, _ = ps.kostenpruefung(_suite("fakten-rat"), "openai/gpt-6-sol", 1, max_kosten=1.0,
                                    teuer_ok=False, stichprobe_n=None, voll=False, ordner=tmp_path)
    assert n == kb.STICHPROBE_N and grund and "--teuer-ok" in grund
    # Ein billiges Modell auf einer Suite ohne Vorlauf darf laufen.
    n, grund, _ = ps.kostenpruefung(_suite("orte"), "openai/gpt-6-luna", 2, max_kosten=1.0,
                                    teuer_ok=False, stichprobe_n=None, voll=False, ordner=tmp_path)
    assert n is None and grund is None
    # Eine Stichprobe für eine Suite, die keine kennt, ist ein Bedienfehler.
    _, grund, _ = ps.kostenpruefung(_suite("orte"), "openai/gpt-6-luna", 1, max_kosten=1.0,
                                    teuer_ok=False, stichprobe_n=10, voll=False, ordner=tmp_path)
    assert grund and "Stichprobe" in grund


def test_regel_steht_in_readme_und_plan():
    for datei in ("eval/README.md", "docs/plan-modellwechsel.md"):
        text = (WURZEL / datei).read_text(encoding="utf-8")
        assert "Teure Modelle: erst eine Stichprobe" in text, datei
