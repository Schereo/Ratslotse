"""Die iOS-App zeichnet ausschließlich mit dem Lucide-Pack.

Web und App sollen dieselbe Bildsprache tragen; SF Symbols sehen daneben
fremd aus. Weil ein neues ``Image(systemName:)`` in einem Diff leicht
durchrutscht, prüft das hier die CI mit.
"""

from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
IOS = WURZEL / "ios"
# Das Register selbst darf SF Symbols nennen — dort steht die eine Ausnahme.
REGISTER = "RatsIconography.swift"
SF_AUFRUF = re.compile(r'\b(?:UI)?Image\(systemName:|systemImage:\s*"')


def _swift_dateien() -> list[Path]:
    return [p for p in IOS.rglob("*.swift") if p.name != REGISTER]


def test_keine_sf_symbole_ausserhalb_des_registers() -> None:
    treffer: list[str] = []
    for pfad in _swift_dateien():
        for nr, zeile in enumerate(pfad.read_text().splitlines(), 1):
            if SF_AUFRUF.search(zeile):
                treffer.append(f"{pfad.relative_to(WURZEL)}:{nr}: {zeile.strip()}")
    assert not treffer, (
        "SF Symbols in der App gefunden — stattdessen RatsIcon/RatsLabel mit "
        "einem RatsGlyph nutzen:\n  " + "\n  ".join(treffer)
    )


def test_jeder_glyph_hat_sein_asset() -> None:
    register = (IOS / "Packages/RatslotseDesign/Sources/RatslotseDesign" / REGISTER).read_text()
    kopf, rest = register.split("    fileprivate var lucideAssetName: String {", 1)
    switch = rest.split("\n    }", 1)[0]

    deklariert = set(re.findall(r"^    case (\w+)$", kopf, re.M))
    im_switch: set[str] = set()
    for zeile in re.findall(r"^        case (\.[\w, .]+):", switch, re.M):
        im_switch |= {n.strip().lstrip(".") for n in zeile.split(",")}
    assert deklariert == im_switch, (
        f"ohne Zuordnung: {sorted(deklariert - im_switch)}; "
        f"ohne Fall: {sorted(im_switch - deklariert)}"
    )

    referenziert = set(re.findall(r'"(Lucide\w+)"', switch))
    vorhanden = {p.name.removesuffix(".imageset")
                 for p in (IOS / "Resources/Assets.xcassets").glob("Lucide*.imageset")}
    assert referenziert <= vorhanden, f"Asset fehlt: {sorted(referenziert - vorhanden)}"
    # Jedes Asset trägt seine SVG — ein leerer Ordner rendert lautlos nichts.
    for name in referenziert:
        ordner = IOS / "Resources/Assets.xcassets" / f"{name}.imageset"
        assert (ordner / f"{name}.svg").is_file(), f"{name}: SVG fehlt"
        assert (ordner / "Contents.json").is_file(), f"{name}: Contents.json fehlt"
