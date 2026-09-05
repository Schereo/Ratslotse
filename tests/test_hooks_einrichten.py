"""Wächter für die Hook-Einrichtung (`scripts/hooks_einrichten.py`).

Der Entschluss „setzen oder nicht" steht dort als reine Funktion, damit er
hier prüfbar ist — die Umgebung selbst (welcher Zweig, welcher Arbeitsbaum)
lässt sich in einem Test nicht nachstellen.

**Wogegen das steht.** Der `pre-push`-Hook fiel in der Hälfte der
Arbeitsverzeichnisse dieses Repos lautlos aus: `core.hooksPath` trug den
absoluten Pfad des Haupt-Checkouts, und dessen Zweig kannte
`.githooks/pre-push` nicht. Gemerkt hat es die CI, drei Minuten nach dem Push.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "hooks_einrichten", WURZEL / "scripts" / "hooks_einrichten.py")
hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hooks)          # type: ignore[union-attr]
soll_setzen = hooks.soll_setzen


def test_laufende_hooks_bleiben_unberuehrt():
    """Der häufigste Fall: Es ist alles in Ordnung, also passiert nichts."""
    assert soll_setzen(hookdir_hat_probe=True, gesetzt=".githooks",
                       baum_hat_probe=True) is None


@pytest.mark.parametrize("gesetzt", [
    "/Users/wer/repo/.githooks",   # DER Fall: absoluter Pfad auf den Haupt-Checkout
    ".githooks",                   # relativ, aber der Zweig dort kennt pre-push nicht
    None,                          # nie eingerichtet
])
def test_kaputte_oder_fehlende_einrichtung_wird_repariert(gesetzt):
    assert soll_setzen(hookdir_hat_probe=False, gesetzt=gesetzt,
                       baum_hat_probe=True) == ".githooks"


@pytest.mark.parametrize("gesetzt", ["/dev/null", "/tmp/leer", "keine-hooks"])
def test_bewusste_abwahl_bleibt_stehen(gesetzt):
    """`core.hooksPath /dev/null` ist der dokumentierte Weg, die Hooks
    abzuschalten. Ein Reparaturlauf, der ihn überschreibt, nimmt jemandem eine
    Entscheidung ab — und zwar bei jedem Sitzungsstart aufs Neue."""
    assert soll_setzen(hookdir_hat_probe=False, gesetzt=gesetzt,
                       baum_hat_probe=True) is None


def test_ohne_hooks_im_arbeitsbaum_wird_nichts_gesetzt():
    """Auf einem Zweig, der `.githooks/` noch nicht hat, zeigte der Wert sonst
    auf ein Verzeichnis, das es nicht gibt."""
    assert soll_setzen(hookdir_hat_probe=False, gesetzt=None,
                       baum_hat_probe=False) is None


def test_das_skript_prueft_pre_push_und_nicht_pre_commit():
    """`pre-commit` ist älter und liegt auch auf den Zweigen, um die es geht —
    als Probe taugt nur der Hook, der tatsächlich fehlte."""
    assert hooks.PROBE == "pre-push"
