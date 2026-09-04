"""Wächter: Die Version, die die App von sich behauptet, stimmt.

**Die Lücke, die er schließt.** `MARKETING_VERSION` ist die Zahl in den
Einstellungen der App und in jeder Fehlermeldung, die jemand schickt. Sie stand
am 04.09.2026 auf 2.0.0, während im Changelog längst 2.1.0 als jüngste Version
geführt wurde: Der Versionsschnitt fasste `ios/` nicht an, und von Hand denkt
daran niemand. Eine falsche Versionsangabe ist der teuerste kleine Fehler, den
es gibt — sie schickt die Fehlersuche zum falschen Stand.

**Warum zwei Dateien.** Das Projekt entsteht aus `project.yml` per XcodeGen,
die `.xcodeproj` ist trotzdem eingecheckt (damit man sie ohne XcodeGen öffnen
kann) und schleppt den Wert mit. Wer nur die eine ändert, baut weiter mit der
alten — genau die Falle, vor der `ios/CLAUDE.md` warnt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.changelog_schnitt import (  # noqa: E402
    IOS_PBX, IOS_YML, VERSIONSZEILE, app_version, app_version_setzen)


def neueste_version() -> str:
    """Die jüngste im Changelog geführte Version — `[Unreleased]` zählt nicht,
    die trägt keine Nummer."""
    for zeile in (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        treffer = VERSIONSZEILE.match(zeile)
        if treffer:
            return treffer.group(1)
    raise AssertionError("keine Version im Changelog gefunden")


def test_die_app_nennt_die_juengste_version():
    assert app_version() == neueste_version(), (
        "Die App behauptet eine andere Version als der Changelog führt. Der "
        "Versionsschnitt zieht das mit; wurde von Hand geschnitten, hilft "
        "`scripts/changelog_schnitt.py <version>` oder das Nachtragen in "
        f"{IOS_YML} UND {IOS_PBX}.")


def test_projektdatei_und_erzeugtes_projekt_sind_einig():
    """Sonst baut Xcode mit der alten Zahl, und die Datei daneben sagt die neue."""
    roh = (WURZEL / IOS_PBX).read_text(encoding="utf-8")
    im_projekt = set(re.findall(r"MARKETING_VERSION = ([^;]+);", roh))
    assert im_projekt == {app_version()}, (
        f"{IOS_PBX} führt {sorted(im_projekt)}, {IOS_YML} aber "
        f"{app_version()!r}. Nach einer Änderung an project.yml gehört "
        "`xcodegen generate --spec ios/project.yml` dazu — und das Ergebnis "
        "mit in den Commit.")


def test_der_build_zaehler_bleibt_unangetastet(tmp_path):
    """Er gehört zum Upload, nicht zur Version: Zwischen zwei Releases können
    mehrere Builds liegen, und ein zurückgesetzter Zähler lässt App Store
    Connect den Upload ablehnen."""
    ios = tmp_path / "ios"
    ios.mkdir()
    (ios / "project.yml").write_text(
        "settings:\n  base:\n    CURRENT_PROJECT_VERSION: 19\n"
        "    MARKETING_VERSION: 2.0.0\n", encoding="utf-8")
    app_version_setzen("2.1.0", wurzel=tmp_path)
    text = (ios / "project.yml").read_text(encoding="utf-8")
    assert "MARKETING_VERSION: 2.1.0" in text
    assert "CURRENT_PROJECT_VERSION: 19" in text


def test_das_nachziehen_ist_folgenlos_ohne_ios(tmp_path):
    """Ein Checkout ohne `ios/` (oder ein Test-Arbeitsbaum) darf den Schnitt
    nicht zum Scheitern bringen."""
    assert app_version_setzen("9.9.9", wurzel=tmp_path) == []


@pytest.mark.parametrize("version", ["2.1.0", "10.0.1"])
def test_es_wird_wirklich_geschrieben(tmp_path, version):
    ios = tmp_path / "ios" / "Ratslotse.xcodeproj"
    ios.mkdir(parents=True)
    (tmp_path / "ios" / "project.yml").write_text(
        "    MARKETING_VERSION: 0.0.1\n", encoding="utf-8")
    (ios / "project.pbxproj").write_text(
        "\t\t\t\tMARKETING_VERSION = 0.0.1;\n\t\t\t\tOTHER = 1;\n", encoding="utf-8")
    assert sorted(app_version_setzen(version, wurzel=tmp_path)) == [IOS_PBX, IOS_YML]
    assert f"MARKETING_VERSION = {version};" in (ios / "project.pbxproj").read_text()
    assert "OTHER = 1;" in (ios / "project.pbxproj").read_text()
