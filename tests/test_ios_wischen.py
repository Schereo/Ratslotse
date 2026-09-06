"""Wächter: Wer die Navigationsleiste ausblendet, holt die Rand-Geste zurück.

**Die Lücke, die er schließt.** Die App zeichnet ihre eigene Kopfzeile und
blendet dafür die System-Leiste aus (`.toolbar(.hidden, for: .navigationBar)`).
UIKit schaltet mit der Leiste aber auch den `interactivePopGestureRecognizer`
ab — er hängt am Zurück-Knopf der Leiste, den es dann nicht mehr gibt. Auf
**jedem** Unterscreen ging das Wischen vom linken Rand damit ins Leere; gemerkt
hat es Tim in der App (04.09.2026), keine Prüfung.

Der Fehler ist ein Nebeneffekt, kein Tippfehler: Man sieht ihn dem Code nicht
an, und er kommt beim nächsten selbstgezeichneten Kopf von allein zurück.
Deshalb steht die Regel hier und nicht in einem Kommentar.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
QUELLEN = WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources" / "RatslotseFeatures"
VERSTECKT = re.compile(r"\.toolbar\(\s*\.hidden\s*,\s*for:\s*\.navigationBar\s*\)")


def swift_dateien() -> list[Path]:
    return sorted(QUELLEN.glob("*.swift"))


def test_die_quellen_sind_ueberhaupt_da():
    """Ohne diese Zeile wäre der Wächter nach einem Umzug still grün."""
    assert swift_dateien(), f"keine Swift-Dateien unter {QUELLEN}"


def test_die_geste_haengt_am_selben_ort_wie_die_versteckte_leiste():
    """Beides gehört in `RatsRouteScaffold` — dort und nur dort.

    Die Leiste wird an 19 Stellen ausgeblendet, aber die meisten davon sind
    Blätter (Sheets) oder eigene Navigations-Stapel: Dort ist ein Wisch kein
    Zurück, und die Geste hätte nichts zu poppen. Geschoben wird ausschließlich
    über `RatsRouteScaffold` — hängt es dort, hängt es an jedem Unterscreen.
    Läuft der Weg eines Tages an ihm vorbei, fällt es hier auf.
    """
    text = (QUELLEN / "NativeRootView.swift").read_text(encoding="utf-8")
    gerüst = text[text.index("private var routeContent: some View {"):]
    ende = gerüst.index("private var activeDestination")
    gerüst = gerüst[:ende]
    assert VERSTECKT.search(gerüst), (
        "Das Routen-Gerüst blendet die Leiste nicht mehr aus — dann prüft der "
        "Rest dieser Datei etwas, das es nicht mehr gibt.")
    assert ".ratsSwipeBack()" in gerüst, (
        "Das Routen-Gerüst versteckt die Navigationsleiste, ohne die Rand-Geste "
        "zurückzuholen. UIKit schaltet sie mit der Leiste ab.")


def test_die_geste_beginnt_nicht_auf_der_wurzel():
    """Der überall abgeschriebene Einzeiler setzt den Delegaten auf `nil`. Dann
    beginnt die Geste auch auf der Wurzel, UIKit versucht zu poppen, was nicht
    da ist — und die App nimmt keine Berührung mehr an."""
    text = (QUELLEN / "SwipeBack.swift").read_text(encoding="utf-8")
    assert "gestureRecognizerShouldBegin" in text
    assert "viewControllers.count" in text, (
        "Die Geste muss fragen, ob überhaupt etwas unter der Ansicht liegt.")
    assert "delegate = nil" not in text, (
        "Ein nil-Delegat lässt die Geste auf der Wurzel beginnen — das ist die "
        "bekannte Einfrierung, nicht die Lösung.")


def test_der_delegat_haengt_am_navigations_controller():
    """Die Geste hält ihren Delegaten SCHWACH. Ein an die SwiftUI-Ansicht
    gebundenes Objekt wäre beim ersten Zurück weg, und die Geste stünde wieder
    ohne da — als hätte man nichts getan."""
    text = (QUELLEN / "SwipeBack.swift").read_text(encoding="utf-8")
    assert "objc_setAssociatedObject" in text


@pytest.mark.parametrize("datei", ["NativeRootView.swift"])
def test_die_geschobenen_routen_haengen_dran(datei):
    """Alle Unterscreens laufen durch `RatsRouteScaffold`; hängt es dort, hängt
    es überall."""
    assert ".ratsSwipeBack()" in (QUELLEN / datei).read_text(encoding="utf-8")
