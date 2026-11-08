#!/usr/bin/env python3
"""Ist der Next-Build in sich stimmig? Jede vorgerenderte Seite muss die
Skripte und Stylesheets finden, die sie verlangt — und ihre Schriftklassen
müssen in diesen Stylesheets stehen.

Gemessen am 15.09.2026, Release v2.6.1: ``next build`` auf Prod schrieb
``.next/server/app/wahlabend.html`` mit ``page-7e835db6….js`` — und legte
gleichzeitig ``page-8069d7d4….js`` auf die Platte. Der alte Name stammte aus
dem persistenten Webpack-Cache (``.next/cache/webpack``, 1 GB alt). Die Folge:
``/wahlabend`` lud ein Skript, das 404 gab, und blieb **weiß** — bei grünem
Deploy und grüner Rauchprobe, denn die prüft die API, nicht die Seite. Alle
anderen Seiten waren in Ordnung; aufgefallen ist es nur, weil nach dem Release
jemand hingesehen hat.

Am 08.11.2026 derselbe Cache auf dev (1,7 GB), diesmal im CSS: Das
``<html>`` jeder Seite trug die next/font-Klassen ``__variable_d8ebd1
__variable_1243c3``, das verlinkte ``fb8ffdbdcb03c98b.css`` definierte noch
die alten ``__variable_f367f3``/``__variable_a4bae9``. Jede Datei lag da, die
erste Prüfung war also zufrieden — und jede Seite stand in Times. Deshalb die
zweite: Jede ``__variable_*``-Klasse am ``<html>`` muss in einem der
Stylesheets definiert sein, die dieselbe Seite verlinkt.

Dieser Wächter läuft in allen drei Deploys **nach dem Build und VOR dem
Umschalten**: Er liest jede ``.html`` unter ``<build>/server/app``, sammelt
alle ``/_next/static/…``-Verweise und prüft, ob die Datei unter
``<build>/static`` liegt, und dann die Schriftklassen. Schlägt er an, bricht
der Deploy ab, bevor der neue Build an die Stelle von ``.next`` rückt — die
Seite läuft dann mit dem alten Stand weiter, statt mit einer leeren.

Seit 11/2026 bauen die Deploys ohne Webpack-Cache (jeder Build beginnt in
einem leeren ``.next-build``), der Anlass beider Fälle ist damit weg. Der
Wächter bleibt das Netz für alles, was einen Build sonst in sich verdreht.

    python scripts/pruefe_build_chunks.py web/frontend/.next-build
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

#: Alles, was eine Seite unter /_next/static/ verlangt — Skripte und Stylesheets.
ASSET_REF = re.compile(r"/_next/static/(?:chunks/[^\"' >]+?\.js|css/[^\"' >]+?\.css)")
#: Ein Stylesheet-Verweis aus derselben Menge.
CSS_REF = re.compile(r"/_next/static/css/[^\"' >]+?\.css")
#: Das öffnende ``<html …>``-Tag und sein class-Attribut.
HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
CLASS_ATTR = re.compile(r"""\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
#: next/font setzt je Schrift eine Klasse ``__variable_<hash>``, die im CSS die
#: Schrift-Variable definiert (``.__variable_d8ebd1{--font-inter:…}``).
FONT_CLASS = re.compile(r"__variable_[0-9a-zA-Z]+")


def _pages(next_dir: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for page in sorted((next_dir / "server" / "app").rglob("*.html")):
        try:
            out.append((page, page.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return out


def _static_file(static: Path, ref: str) -> Path:
    """Die Datei hinter einem ``/_next/static/…``-Verweis.

    Der Verweis steht URL-kodiert in der HTML, die Datei heißt im Klartext:
    ``…/liste/%5Bliste%5D/page-….js`` liegt unter ``…/liste/[liste]/``. Ohne
    das Dekodieren meldete der Wächter am 08.11.2026 auf dev 21 Verweise als
    fehlend, die alle da waren — jede dynamische Route mit vorgerenderten
    Seiten (dort ``/kommunalwahl/liste/[liste]`` und ``/thema/[thema]``, die
    nur der Dev-Build freischaltet) hätte den Deploy angehalten.
    """
    return static / unquote(ref.removeprefix("/_next/static/"))


def missing_files(next_dir: Path) -> list[tuple[Path, str]]:
    """(Seite, fehlender Verweis) für jeden Verweis ohne Datei."""
    static = next_dir / "static"
    out: list[tuple[Path, str]] = []
    for page, text in _pages(next_dir):
        for ref in sorted(set(ASSET_REF.findall(text))):
            if not _static_file(static, ref).is_file():
                out.append((page, ref))
    return out


def html_font_classes(text: str) -> list[str]:
    """Die ``__variable_*``-Klassen am ``<html>``-Tag, in ihrer Reihenfolge."""
    tag = HTML_TAG.search(text)
    if not tag:
        return []
    attr = CLASS_ATTR.search(tag.group(0))
    if not attr:
        return []
    classes = (attr.group(1) if attr.group(1) is not None else attr.group(2)).split()
    return [c for c in classes if FONT_CLASS.fullmatch(c)]


def undefined_font_classes(next_dir: Path) -> list[tuple[Path, str]]:
    """(Seite, Klasse) für jede Schriftklasse am ``<html>``, die keins der
    Stylesheets definiert, die dieselbe Seite verlinkt.

    Nur die VERLINKTEN zählen: Ein Stylesheet, das die Klasse zwar enthält,
    das die Seite aber nicht lädt, rettet sie nicht. Ein fehlendes Stylesheet
    meldet ``missing_files``; hier zählt es als eins ohne Definitionen.
    """
    static = next_dir / "static"
    css_cache: dict[str, str] = {}
    out: list[tuple[Path, str]] = []
    for page, text in _pages(next_dir):
        wanted = html_font_classes(text)
        if not wanted:
            continue
        css = ""
        for ref in sorted(set(CSS_REF.findall(text))):
            if ref not in css_cache:
                try:
                    css_cache[ref] = _static_file(static, ref).read_text(
                        encoding="utf-8", errors="replace")
                except OSError:
                    css_cache[ref] = ""
            css += css_cache[ref]
        for cls in wanted:
            # Als Selektor, nicht bloß als Zeichenkette: `.__variable_ab` darf
            # nicht in `.__variable_abc` einen Treffer finden.
            if not re.search(r"\." + re.escape(cls) + r"(?![\w-])", css):
                out.append((page, cls))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("next_dir", nargs="?", default="web/frontend/.next", type=Path)
    args = ap.parse_args()
    next_dir: Path = args.next_dir
    if not (next_dir / "server" / "app").is_dir():
        print(f"FEHLER: {next_dir}/server/app fehlt — ist das ein fertiger Next-Build?")
        return 2
    pages = list((next_dir / "server" / "app").rglob("*.html"))
    missing = missing_files(next_dir)
    fonts = undefined_font_classes(next_dir)
    if missing:
        print(f"BUILD UNSTIMMIG: {len(missing)} Verweis(e) ohne Datei in {len(pages)} vorgerenderten Seiten:")
        for page, ref in missing:
            print(f"  {page.relative_to(next_dir)}  →  {ref}")
    if fonts:
        # Je Klasse statt je Seite: Im Fall vom 08.11. traf es jede Seite,
        # das wären über hundert gleichlautende Zeilen im Deploy-Protokoll.
        by_class: dict[str, list[Path]] = {}
        for page, cls in fonts:
            by_class.setdefault(cls, []).append(page)
        print(f"BUILD UNSTIMMIG: {len(by_class)} Schriftklasse(n) am <html> ohne Definition im verlinkten CSS:")
        for cls, cls_pages in by_class.items():
            shown = ", ".join(str(p.relative_to(next_dir)) for p in cls_pages[:3])
            more = f" und {len(cls_pages) - 3} weitere" if len(cls_pages) > 3 else ""
            print(f"  .{cls}  ←  {len(cls_pages)} Seite(n): {shown}{more}")
        print("Diese Seiten fielen auf die Ersatzschrift des Browsers zurück (Times).")
    if missing or fonts:
        print("\nUrsache erfahrungsgemäß ein alter Webpack-Cache: <build>/cache/webpack löschen, dann neu bauen.")
        return 1
    print(f"Build stimmig: {len(pages)} vorgerenderte Seite(n), jeder Verweis liegt unter "
          f"{next_dir}/static, jede Schriftklasse steht im verlinkten CSS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
