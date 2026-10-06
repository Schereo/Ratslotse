"""Der Wochenlauf: Ein hängender Schritt hält nicht mehr alle folgenden an,
und ein wartender Deploy bekommt zwischen zwei Schritten seinen Platz.

Bis 10/2026 lief ``subprocess.run`` ohne ``timeout`` und ohne Blick auf
``kern/stopp.py`` (Review 05.10.2026).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kern import stopp as stopp_mod  # noqa: E402
from scripts import weekly_enrich  # noqa: E402


def _bauen(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "haengt.py").write_text("import time\ntime.sleep(30)\n")
    (tmp_path / "scripts" / "flott.py").write_text("print('ok')\n")
    monkeypatch.setattr(weekly_enrich, "ROOT", tmp_path)
    monkeypatch.setattr(weekly_enrich, "STEPS", [("Hängt", "haengt.py"), ("Flott", "flott.py")])


def test_haengender_schritt_wird_beendet_und_der_naechste_laeuft(tmp_path, monkeypatch):
    _bauen(tmp_path, monkeypatch)
    t0 = time.monotonic()
    protokoll = weekly_enrich.main(step_max=1.0)
    assert time.monotonic() - t0 < 15
    assert [(s["name"], s["status"]) for s in protokoll] == [("Hängt", "error"), ("Flott", "ok")]


def test_schrittgrenze_aus_der_umgebung(monkeypatch):
    monkeypatch.delenv(weekly_enrich.STEP_MAX_SEKUNDEN, raising=False)
    assert weekly_enrich._step_max_sekunden() == weekly_enrich.STEP_MAX_VORGABE
    monkeypatch.setenv(weekly_enrich.STEP_MAX_SEKUNDEN, "600")
    assert weekly_enrich._step_max_sekunden() == 600
    # 0 hebt die Grenze auf (Nachlauf von Hand); ein Tippfehler auch — nie „sofort".
    monkeypatch.setenv(weekly_enrich.STEP_MAX_SEKUNDEN, "0")
    assert weekly_enrich._step_max_sekunden() is None
    monkeypatch.setenv(weekly_enrich.STEP_MAX_SEKUNDEN, "drei")
    assert weekly_enrich._step_max_sekunden() is None


def test_wartender_deploy_beendet_den_lauf_zwischen_zwei_schritten(tmp_path, monkeypatch):
    _bauen(tmp_path, monkeypatch)
    monkeypatch.setattr(weekly_enrich, "STEPS", [("Flott", "flott.py"), ("Hängt", "haengt.py")])
    daten = tmp_path / "data"
    daten.mkdir()
    st = stopp_mod.Stopp(daten)
    abbruch: list[str] = []

    # Der Deploy legt seinen Marker, während der erste Schritt läuft.
    echt_run = weekly_enrich.subprocess.run

    def run_und_marker(*a, **kw):
        r = echt_run(*a, **kw)
        (daten / stopp_mod.WARTET_NAME).write_text("")
        return r

    monkeypatch.setattr(weekly_enrich.subprocess, "run", run_und_marker)
    protokoll = weekly_enrich.main(st, step_max=5.0, abbruch=abbruch)
    assert [s["name"] for s in protokoll] == ["Flott"]
    assert abbruch == ["deploy"]


def test_guarded_main_vermerkt_den_grund(tmp_path, monkeypatch):
    _bauen(tmp_path, monkeypatch)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / stopp_mod.WARTET_NAME).write_text("")
    kennzahlen = weekly_enrich._guarded_main()
    assert kennzahlen[weekly_enrich.SCHRITTE_SCHLUESSEL] == []
    assert kennzahlen[weekly_enrich.ABBRUCH_SCHLUESSEL] == "deploy"
