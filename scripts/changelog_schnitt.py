#!/usr/bin/env python3
"""Versionsschnitt: Changelog-Fragmente einsammeln und in ``CHANGELOG.md`` gießen.

**Warum es das gibt.** Bis 08/2026 trug jeder nutzerrelevante PR seinen Eintrag
direkt unter ``## [Unreleased]`` ein — also alle PRs in dieselben zwei, drei
Zeilen. Bei parallelen Zweigen kollidierte damit *jeder* Merge an derselben
Stelle; an einem einzigen Tag kostete das über zehn Konfliktauflösungen. Dazu
kam ein zweiter Ärger: Die PR-Nummer steht erst fest, wenn der PR existiert —
geraten wurde sie prompt zweimal falsch.

Seitdem legt jeder PR **eine eigene Datei** unter ``changelog.d/`` an. Zwei
Zweige berühren nie dieselbe Datei, also kollidiert nichts mehr, und die Nummer
lässt sich weglassen: Dieses Skript holt sie beim Schnitt aus der Git-Historie
nach (der Squash-Commit, der die Datei angelegt hat, trägt sie im Titel).

**Format eines Fragments** (``changelog.d/<slug>.md``)::

    ---
    kategorie: hinzugefuegt
    ---

    **Kernsatz fett.** Danach der Fließtext, deutsch, im Stil des Changelogs —
    ohne PR-Nummer, die kommt hier her.

Erlaubte Kategorien: ``hinzugefuegt``, ``geaendert``, ``behoben`` (die
Schreibweisen mit Umlaut werden ebenfalls gelesen).

**Aufruf beim Versionsschnitt** (im Release-PR ``dev`` → ``main``)::

    .venv/bin/python scripts/changelog_schnitt.py 1.13.0 --trocken   # anschauen
    .venv/bin/python scripts/changelog_schnitt.py 1.13.0             # schreiben

Danach wie gehabt: Tag ``v1.13.0`` setzen und pushen.

Das Skript kommt mit **beiden** Wegen zurecht: Was jemand von Hand unter
``## [Unreleased]`` eingetragen hat, bleibt erhalten und wandert unverändert
mit unter die neue Version — die Fragmente werden lediglich in die passenden
Abschnitte einsortiert. Der Rest des Blocks (auch auskommentierte Entwürfe)
wird **nicht** neu formatiert, sondern wortgetreu übernommen.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

# Kategorie-Kürzel im Frontmatter → Abschnitts-Überschrift im Changelog.
KATEGORIEN = {
    "hinzugefuegt": "Hinzugefügt",
    "geaendert": "Geändert",
    "behoben": "Behoben",
}
# Umlaut-Schreibweisen nehmen wir beim Lesen mit; dokumentiert ist die ASCII-Form,
# weil sie sich als Wert im Frontmatter nicht vertippen lässt.
ALIASE = {"hinzugefügt": "hinzugefuegt", "geändert": "geaendert"}

# Reihenfolge neu angelegter Abschnitte. Vorhandene Abschnitte behalten ihre.
REIHENFOLGE = ["Hinzugefügt", "Geändert", "Behoben"]

FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n(.*)\Z", re.S)
SCHLUESSEL = re.compile(r"^[ \t]*([A-Za-zäöüß_]+)[ \t]*:[ \t]*(.*?)[ \t]*$")
PR_NUMMER = re.compile(r"\(#(\d+)\)")

# Zeilenbreite des Changelogs. Die Datei ist von Hand auf ~80 Zeichen umbrochen;
# ein Fragment, das als eine 900-Zeichen-Zeile landet, fiele sofort auf.
BREITE = 80


class FragmentFehler(ValueError):
    """Ein Fragment ist nicht lesbar — kaputtes Frontmatter, unbekannte
    Kategorie oder leerer Text."""


@dataclass(frozen=True)
class Fragment:
    pfad: Path
    category: str  # Kürzel, immer ASCII (siehe KATEGORIEN)
    text: str       # einzeiliger Fließtext, ohne PR-Nummer

    @property
    def heading(self) -> str:
        return KATEGORIEN[self.category]


@dataclass
class Ergebnis:
    text: str                                  # der neue Changelog
    fragmente: list[Fragment] = field(default_factory=list)
    ohne_nummer: list[Path] = field(default_factory=list)
    geschrieben: bool = False


def _ist_fragment(pfad: Path) -> bool:
    """``_notizen.md``, ``README.md`` und Verstecktes sind keine Einträge."""
    name = pfad.name
    return (
        pfad.suffix == ".md"
        and not name.startswith((".", "_"))
        and name.lower() != "readme.md"
    )


def lies_fragment(pfad: Path) -> Fragment:
    """Ein Fragment einlesen und prüfen. Wirft ``FragmentFehler``."""
    roh = pfad.read_text(encoding="utf-8")
    treffer = FRONTMATTER.match(roh)
    if not treffer:
        raise FragmentFehler(
            f"{pfad.name}: kein Frontmatter. Erwartet wird ein Block aus "
            "'---', 'kategorie: …', '---' ganz am Dateianfang."
        )
    kopf, rumpf = treffer.group(1), treffer.group(2)

    werte = {}
    for row in kopf.splitlines():
        if not row.strip():
            continue
        paar = SCHLUESSEL.match(row)
        if not paar:
            raise FragmentFehler(f"{pfad.name}: '{row.strip()}' ist kein 'key: value'")
        werte[paar.group(1).lower()] = paar.group(2)

    roh_kategorie = werte.get("kategorie", "").strip().lower()
    category = ALIASE.get(roh_kategorie, roh_kategorie)
    if category not in KATEGORIEN:
        erlaubt = ", ".join(KATEGORIEN)
        raise FragmentFehler(
            f"{pfad.name}: kategorie '{werte.get('kategorie', '')}' unbekannt (erlaubt: {erlaubt})"
        )

    text = " ".join(rumpf.split())
    if not text:
        raise FragmentFehler(f"{pfad.name}: kein Text unter dem Frontmatter")

    return Fragment(pfad=pfad, category=category, text=text)


def sammle_fragmente(verzeichnis: Path) -> list[Fragment]:
    """Alle Fragmente eines Verzeichnisses, nach Dateiname sortiert.

    Die Sortierung ist bewusst der Dateiname und nicht die Änderungszeit: Sie
    ist im Diff nachvollziehbar und auf jedem Rechner dieselbe.
    """
    if not verzeichnis.is_dir():
        return []
    return [lies_fragment(p) for p in sorted(verzeichnis.iterdir()) if _ist_fragment(p)]


def _git_betreffe(pfad: Path, wurzel: Path) -> list[str]:
    """Commit-Betreffzeilen, die diese Datei berühren — ältester zuerst.

    Erst die Commits, die die Datei **angelegt** haben (``--diff-filter=A``):
    Das ist der Squash-Merge des PRs, der das Fragment mitbrachte, und nur
    dessen Nummer gehört an den Eintrag. Findet sich keiner (etwa weil das
    Fragment noch ungetrackt ist), fallen wir auf alle Commits der Datei zurück.
    """
    def lauf(zusatz: list[str]) -> list[str]:
        result = subprocess.run(
            ["git", "log", "--reverse", "--format=%s", *zusatz, "--", str(pfad)],
            cwd=wurzel, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return []
        return [z for z in result.stdout.splitlines() if z.strip()]

    return lauf(["--diff-filter=A"]) or lauf([])


def pr_nummer(pfad: Path, wurzel: Path = WURZEL, betreffe: list[str] | None = None) -> int | None:
    """Die PR-Nummer aus dem Commit-Titel, der das Fragment angelegt hat."""
    for betreff in (betreffe if betreffe is not None else _git_betreffe(pfad, wurzel)):
        treffer = PR_NUMMER.search(betreff)
        if treffer:
            return int(treffer.group(1))
    return None


def eintrag(fragment: Fragment, nummer: int | None) -> list[str]:
    """Ein Fragment als Changelog-Listenpunkt, auf Dateibreite umbrochen."""
    text = fragment.text if nummer is None else f"{fragment.text} (#{nummer})"
    return textwrap.wrap(
        text, width=BREITE, initial_indent="- ", subsequent_indent="  ",
        break_long_words=False, break_on_hyphens=False,
    )


def _abschnitt_einfuegen(block: list[str], heading: str, eintraege: list[str]) -> list[str]:
    """Einträge ans Ende des passenden ``### …``-Abschnitts hängen.

    Fehlt der Abschnitt, entsteht er am Blockende. Alles Vorhandene bleibt
    wortgetreu stehen — auch auskommentierte Entwürfe, die eine Neuformatierung
    zerlegen würde.
    """
    start = next((i for i, z in enumerate(block) if z.strip() == f"### {heading}"), None)
    if start is None:
        neu = list(block)
        while neu and not neu[-1].strip():
            neu.pop()
        return neu + ["", f"### {heading}"] + eintraege

    ende = next(
        (i for i in range(start + 1, len(block)) if block[i].startswith("### ")),
        len(block),
    )
    # Hinter der letzten belegten Zeile des Abschnitts einfügen, nicht hinter
    # dessen Leerzeilen — sonst wandert der neue Punkt hinter die Trennzeile.
    einfuegen = ende
    while einfuegen > start + 1 and not block[einfuegen - 1].strip():
        einfuegen -= 1
    return block[:einfuegen] + eintraege + block[einfuegen:]


def _vergleichslinks(zeilen: list[str], version: str) -> list[str]:
    """``[Unreleased]``-Compare-Link umhängen und einen für die neue Version anlegen.

    Fehlt die Zeile (oder sieht sie anders aus), passiert nichts außer einer
    Warnung — der Schnitt selbst darf daran nicht scheitern.
    """
    muster = re.compile(r"^\[Unreleased\]:\s*(\S*/compare/)v(\S+?)\.\.\.(\S+)\s*$")
    for i, row in enumerate(zeilen):
        treffer = muster.match(row)
        if not treffer:
            continue
        basis, vorher, ziel = treffer.groups()
        if vorher == version:  # schon geschnitten
            return zeilen
        return (
            zeilen[:i]
            + [f"[Unreleased]: {basis}v{version}...{ziel}",
               f"[{version}]: {basis}v{vorher}...v{version}"]
            + zeilen[i + 1:]
        )
    print("  ! Kein [Unreleased]-Compare-Link gefunden — Links am Dateiende von Hand nachziehen.",
          file=sys.stderr)
    return zeilen


def einsetzen(changelog: str, eintraege_je_ueberschrift: dict[str, list[str]],
              version: str, date: str) -> str:
    """Den ``[Unreleased]``-Block zur Version machen und Fragmente einsortieren."""
    zeilen = changelog.split("\n")
    start = next((i for i, z in enumerate(zeilen) if z.startswith("## [Unreleased]")), None)
    if start is None:
        raise ValueError("CHANGELOG.md hat keinen '## [Unreleased]'-Abschnitt")
    ende = next((i for i in range(start + 1, len(zeilen)) if zeilen[i].startswith("## ")), len(zeilen))

    block = zeilen[start + 1:ende]
    # ``dict.fromkeys`` statt ``set``: Reihenfolge behalten und Doppelte werfen.
    # Der Unreleased-Block trägt regelmäßig mehrere gleichnamige Abschnitte
    # (jeder Feature-PR hängt sein eigenes „### Hinzugefügt" an) — ohne diese
    # Zeile landete jedes Fragment so oft im Changelog, wie seine Überschrift
    # dort vorkommt. Einsortiert wird in den **ersten** passenden Abschnitt.
    vorhandene = list(dict.fromkeys(z.strip()[4:] for z in block if z.startswith("### ")))
    for heading in vorhandene + [u for u in REIHENFOLGE if u not in vorhandene]:
        if eintraege_je_ueberschrift.get(heading):
            block = _abschnitt_einfuegen(block, heading, eintraege_je_ueberschrift[heading])

    while block and not block[-1].strip():
        block.pop()
    if block and block[0].strip():  # Leerzeile unter die Versionszeile
        block.insert(0, "")

    neu = (
        zeilen[:start]
        + ["## [Unreleased]", "", f"## [{version}] – {date}"]
        + block
        + [""]
        + zeilen[ende:]
    )
    return "\n".join(_vergleichslinks(neu, version))


def schnitt(version: str, tag_iso: str | None = None, wurzel: Path = WURZEL,
            trocken: bool = False, nummern=None) -> Ergebnis:
    """Den Versionsschnitt ausführen (bzw. bei ``trocken`` nur berechnen).

    ``nummern`` ist die Auflösung Fragment → PR-Nummer; per Default die
    Git-Historie. Die Tests reichen hier eine Attrappe herein.
    """
    tag_iso = tag_iso or date.today().isoformat()
    finder = nummern or (lambda pfad: pr_nummer(pfad, wurzel))

    fragmente = sammle_fragmente(wurzel / "changelog.d")
    eintraege: dict[str, list[str]] = {}
    ohne_nummer: list[Path] = []
    for fragment in fragmente:
        nummer = finder(fragment.pfad)
        if nummer is None:
            ohne_nummer.append(fragment.pfad)
            print(f"  ! {fragment.pfad.name}: keine PR-Nummer gefunden — Eintrag ohne Nummer.",
                  file=sys.stderr)
        eintraege.setdefault(fragment.heading, []).extend(eintrag(fragment, nummer))

    pfad = wurzel / "CHANGELOG.md"
    text = einsetzen(pfad.read_text(encoding="utf-8"), eintraege, version, tag_iso)

    if trocken:
        return Ergebnis(text=text, fragmente=fragmente, ohne_nummer=ohne_nummer)

    pfad.write_text(text, encoding="utf-8")
    for fragment in fragmente:
        fragment.pfad.unlink()
    return Ergebnis(text=text, fragmente=fragmente, ohne_nummer=ohne_nummer, geschrieben=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Changelog-Fragmente zur Version zusammenfassen")
    p.add_argument("version", nargs="?", help="neue Version, z. B. 1.13.0")
    p.add_argument("--date", help="Datum des Schnitts (Default: heute)")
    p.add_argument("--trocken", action="store_true", help="Ergebnis zeigen, nichts schreiben")
    p.add_argument("--pruefen", action="store_true",
                   help="nur prüfen, ob alle Fragmente wohlgeformt sind")
    args = p.parse_args()

    if args.pruefen:
        try:
            fragmente = sammle_fragmente(WURZEL / "changelog.d")
        except FragmentFehler as fehler:
            print(f"FEHLER: {fehler}", file=sys.stderr)
            return 1
        print(f"{len(fragmente)} Fragment(e) in Ordnung.")
        return 0

    if not args.version:
        p.error("die Version fehlt (oder --pruefen benutzen)")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        p.error(f"'{args.version}' sieht nicht wie eine Version aus (x.y.z)")

    try:
        result = schnitt(args.version, args.date, trocken=args.trocken)
    except (FragmentFehler, ValueError) as fehler:
        print(f"FEHLER: {fehler}", file=sys.stderr)
        return 1

    if args.trocken:
        # Vorspann, das leere [Unreleased] und der frisch geschnittene Block —
        # die 900 Zeilen Historie darunter interessieren beim Probelauf nicht.
        teile = result.text.split("\n## [")
        print("\n## [".join(teile[:3]))
        print(f"\n— Probelauf: {len(result.fragmente)} Fragment(e), nichts geschrieben.",
              file=sys.stderr)
    else:
        print(f"{len(result.fragmente)} Fragment(e) in Version {args.version} übernommen "
              f"und gelöscht. Jetzt: Tag v{args.version} setzen und pushen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
