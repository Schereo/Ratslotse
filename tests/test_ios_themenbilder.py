"""Die Bilder der App und die des Webs müssen dieselben sein.

Die Stadtthemen- und Gremienbilder liegen zweimal vor: als WebP im Frontend
(``public/themen``, ``public/gremien``) und als Imageset im Asset-Katalog der
App. Ein neues Thema ohne Imageset zeigt dort eine leere Fläche — ohne
Fehlermeldung, denn ``Image("ThemeX")`` für einen fehlenden Namen rendert
einfach nichts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ios_themenbilder as sk  # noqa: E402
from council.city_topics import CITY_TOPICS  # noqa: E402

ONBOARDING = (ROOT / "ios/Packages/RatslotseFeatures/Sources/RatslotseFeatures/OnboardingViews.swift")


def test_jedes_webbild_hat_ein_imageset():
    fehlen = [n for n in sk.quellen()
              if not (sk.KATALOG / f"{n}.imageset" / f"{n}.png").exists()]
    assert not fehlen, (
        f"Im Asset-Katalog fehlen {fehlen}. Abhilfe: "
        ".venv/bin/python scripts/ios_themenbilder.py")


def test_jedes_stadtthema_hat_ein_bild_in_der_app():
    for t in CITY_TOPICS:
        name = sk.asset_name("Theme", t.key)
        assert (sk.KATALOG / f"{name}.imageset" / f"{name}.png").exists(), t.key


def test_die_gremienzuordnung_der_app_zeigt_nur_auf_vorhandene_bilder():
    """``imageKeys`` in ``CommitteeCopy`` ist eine Kopie der Tabelle des Webs —
    jeder Schlüssel dort muss ein Imageset haben."""
    quelltext = ONBOARDING.read_text()
    block = quelltext[quelltext.index("private static let imageKeys"):]
    block = block[:block.index("]\n")]
    schluessel = set(re.findall(r'"[^"]+": "([a-z]+)"', block))
    assert schluessel, "imageKeys nicht gefunden"
    for key in schluessel:
        name = sk.asset_name("Committee", key)
        assert (sk.KATALOG / f"{name}.imageset" / f"{name}.png").exists(), key
    web = (ROOT / "web/frontend/lib/committees.ts").read_text()
    web_block = web[web.index("const BILDER"):]
    web_block = web_block[:web_block.index("};")]
    assert schluessel == set(re.findall(r'"[^"]+": "([a-z]+)"', web_block)), (
        "Die Gremien-Zuordnung von App und Web weicht ab")
