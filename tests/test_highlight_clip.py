"""Der Zoom im Highlight-Clip: weich, an den Rand geklemmt, wieder zurück.

Ein Ruck im Video sieht man erst, wenn er gerendert ist — die Kurve hier ist
dagegen in Millisekunden geprüft.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.highlight_clip import Beat, Timing, crop_box, smoothstep, zoom_state  # noqa: E402

GROESSE = (1206, 2622)
BEAT = [Beat(t=5.0, x=1068.0, y=690.0)]
T = Timing(zoom=1.8, lead=0.5, hold=2.0, release=0.6)


def test_ausserhalb_des_beats_bleibt_alles_ruhig():
    assert zoom_state(0.0, BEAT, GROESSE, T) == (1.0, 603.0, 1311.0)
    assert zoom_state(4.49, BEAT, GROESSE, T)[0] == 1.0
    assert zoom_state(7.7, BEAT, GROESSE, T)[0] == 1.0     # nach hold + release


def test_beim_klick_ist_der_zoom_voll_und_auf_dem_punkt():
    z, cx, cy = zoom_state(5.0, BEAT, GROESSE, T)
    assert z == 1.8 and (cx, cy) == (1068.0, 690.0)
    assert zoom_state(6.9, BEAT, GROESSE, T)[0] == 1.8     # noch im Halt


def test_die_anfahrt_ist_monoton_und_weich():
    """Kein Sprung: Der Zoom steigt Bild für Bild, und an beiden Enden geht die
    Steigung gegen null (Smoothstep) — genau das unterscheidet ihn von einem
    linearen Schnitt, den man als Ruck sieht."""
    werte = [zoom_state(4.5 + i * 0.01, BEAT, GROESSE, T)[0] for i in range(51)]
    assert all(b >= a for a, b in zip(werte, werte[1:]))
    assert werte[0] == 1.0 and abs(werte[-1] - 1.8) < 1e-9
    erste = werte[1] - werte[0]
    mitte = werte[26] - werte[25]
    assert erste < mitte / 3


def test_die_rueckfahrt_endet_wieder_bei_eins():
    werte = [zoom_state(7.0 + i * 0.01, BEAT, GROESSE, T)[0] for i in range(61)]
    assert all(b <= a for a, b in zip(werte, werte[1:]))
    assert werte[-1] == 1.0


def test_smoothstep_haelt_die_grenzen():
    assert smoothstep(-1) == 0 and smoothstep(2) == 1 and smoothstep(0.5) == 0.5


def test_der_ausschnitt_bleibt_im_bild():
    """Ein Klick am rechten Rand: Der Ausschnitt rückt so weit wie möglich,
    ohne über das Bild hinauszulaufen."""
    x, y, w, h = crop_box(1.8, 1150.0, 100.0, GROESSE)
    assert 0 <= x and x + w <= GROESSE[0] + 1e-6
    assert 0 <= y and y + h <= GROESSE[1] + 1e-6
    assert abs(w - GROESSE[0] / 1.8) < 1e-6
    # Ein Klick in der Mitte sitzt auch in der Mitte des Ausschnitts.
    x, y, w, h = crop_box(2.0, 603.0, 1311.0, GROESSE)
    assert abs(x + w / 2 - 603.0) < 1e-6 and abs(y + h / 2 - 1311.0) < 1e-6
