#!/usr/bin/env python3
"""Ist der Next-Build in sich stimmig? Jede vorgerenderte Seite muss die
Skripte finden, die sie verlangt.

Gemessen am 15.09.2026, Release v2.6.1: ``next build`` auf Prod schrieb
``.next/server/app/wahlabend.html`` mit ``page-7e835db6….js`` — und legte
gleichzeitig ``page-8069d7d4….js`` auf die Platte. Der alte Name stammte aus
dem persistenten Webpack-Cache (``.next/cache/webpack``, 1 GB alt). Die Folge:
``/wahlabend`` lud ein Skript, das 404 gab, und blieb **weiß** — bei grünem
Deploy und grüner Rauchprobe, denn die prüft die API, nicht die Seite. Alle
anderen Seiten waren in Ordnung; aufgefallen ist es nur, weil nach dem Release
jemand hingesehen hat.

Dieser Wächter läuft im Deploy **nach dem Build und VOR dem Umschalten**: Er
liest jede ``.html`` unter ``.next/server/app``, sammelt alle
``/_next/static/…``-Verweise und prüft, ob die Datei unter ``.next/static``
liegt. Fehlt eine, bricht der Deploy ab, bevor die API gestoppt wird — Prod
läuft dann mit dem alten Stand weiter, statt mit einer leeren Seite.

Heilung, wenn er anschlägt: ``rm -rf web/frontend/.next/cache/webpack`` und
neu bauen. Der Cache spart Zeit, aber er ist ein Cache — verlässlich ist nur,
was auf der Platte liegt.

    python scripts/pruefe_build_chunks.py web/frontend/.next
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: Alles, was eine Seite unter /_next/static/ verlangt — Skripte und Stylesheets.
VERWEIS = re.compile(r"/_next/static/(?:chunks/[^\"' >]+?\.js|css/[^\"' >]+?\.css)")


def fehlende(next_dir: Path) -> list[tuple[Path, str]]:
    """(Seite, fehlender Verweis) für jeden Verweis ohne Datei."""
    static = next_dir / "static"
    seiten = sorted((next_dir / "server" / "app").rglob("*.html"))
    aus: list[tuple[Path, str]] = []
    for seite in seiten:
        try:
            text = seite.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for verweis in sorted(set(VERWEIS.findall(text))):
            rel = verweis.removeprefix("/_next/static/")
            if not (static / rel).is_file():
                aus.append((seite, verweis))
    return aus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("next_dir", nargs="?", default="web/frontend/.next", type=Path)
    args = ap.parse_args()
    next_dir: Path = args.next_dir
    if not (next_dir / "server" / "app").is_dir():
        print(f"FEHLER: {next_dir}/server/app fehlt — ist das ein fertiger Next-Build?")
        return 2
    seiten = list((next_dir / "server" / "app").rglob("*.html"))
    aus = fehlende(next_dir)
    if aus:
        print(f"BUILD UNSTIMMIG: {len(aus)} Verweis(e) ohne Datei in {len(seiten)} vorgerenderten Seiten:")
        for seite, verweis in aus:
            print(f"  {seite.relative_to(next_dir)}  →  {verweis}")
        print("\nUrsache erfahrungsgemäß der Webpack-Cache: rm -rf .next/cache/webpack, dann neu bauen.")
        return 1
    print(f"Build stimmig: {len(seiten)} vorgerenderte Seite(n), jeder Verweis liegt unter {next_dir}/static.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
