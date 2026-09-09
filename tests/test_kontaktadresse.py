"""Die Kontaktadresse steht an zwei Stellen — und darf nicht auseinanderlaufen.

Web und App können sich keine Konstante teilen: Swift importiert nichts aus
TypeScript. Also gibt es zwei Kopien, und damit genau die Sorte zweiter
Wahrheit, die lautlos veraltet. Bis 09/2026 stand die Adresse sogar sechsmal
wörtlich im Frontend; wer sie geändert hätte, hätte fünf Stellen erwischt und
die sechste übersehen — auf einer Rechtsseite, die niemand nachliest.

Dieser Wächter räumt nichts auf, er hält: Eine geänderte Adresse muss in
beiden Kopien ankommen, und im Frontend darf sie nirgends mehr wörtlich
stehen.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
WEB = WURZEL / "web" / "frontend" / "lib" / "kontakt.ts"
IOS = (WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources"
       / "RatslotseFeatures" / "AuthViews.swift")


def _web_adresse() -> str:
    treffer = re.search(r'KONTAKT_EMAIL\s*=\s*"([^"]+)"', WEB.read_text(encoding="utf-8"))
    assert treffer, f"KONTAKT_EMAIL nicht gefunden in {WEB}"
    return treffer.group(1)


def _ios_adresse() -> str:
    quelle = IOS.read_text(encoding="utf-8")
    treffer = re.search(r'enum RatslotseKontakt\s*\{[^}]*?static let email\s*=\s*"([^"]+)"',
                        quelle, re.DOTALL)
    assert treffer, f"RatslotseKontakt.email nicht gefunden in {IOS}"
    return treffer.group(1)


def test_beide_kopien_nennen_dieselbe_adresse():
    web, ios = _web_adresse(), _ios_adresse()
    assert web == ios, (
        f"Web sagt {web!r}, die App sagt {ios!r}. Beide Stellen ändern: "
        f"{WEB.relative_to(WURZEL)} und {IOS.relative_to(WURZEL)}.")


def test_das_frontend_tippt_die_adresse_nirgends_mehr_ab():
    """Sechs wörtliche Kopien waren der Ausgangszustand. Eine neue wäre ein
    Rückschritt — auch eine „nur schnell hier"."""
    adresse = _web_adresse()
    basis = WURZEL / "web" / "frontend"
    nachzuegler = []
    for pfad in list(basis.glob("app/**/*.tsx")) + list(basis.glob("components/**/*.tsx")) \
            + list(basis.glob("lib/**/*.ts")):
        if pfad == WEB or "node_modules" in pfad.parts or ".next" in str(pfad):
            continue
        if adresse in pfad.read_text(encoding="utf-8"):
            nachzuegler.append(str(pfad.relative_to(WURZEL)))
    assert not nachzuegler, (
        "Diese Dateien tippen die Kontaktadresse ab, statt KONTAKT_EMAIL aus "
        f"lib/kontakt.ts zu nehmen: {sorted(nachzuegler)}")
