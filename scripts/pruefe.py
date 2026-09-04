#!/usr/bin/env python3
"""Ein Befehl für alles, was die CI prüft.

**Warum es das gibt.** Die Prüfungen dieses Repos waren über sechs Stellen
verteilt: ``CONTRIBUTING.md`` nennt vier Befehle, ``.github/workflows/test.yml``
drei, ``frontend.yml`` noch einmal drei, und welche davon für die eigene
Änderung gelten, muss man raten. Wer sie einzeln abtippt, vergisst eine —
und merkt es erst, wenn der Pull Request rot ist oder, schlimmer, wenn er
grün war und der Deploy bricht.

Mit einem Befehl gibt es nichts mehr zu raten:

.. code-block:: sh

    python scripts/pruefe.py             # alles, was die CI auch prüft
    python scripts/pruefe.py --schnell   # nur die Prüfungen unter ~5 s
    python scripts/pruefe.py --nur ruff,vertrag
    python scripts/pruefe.py --liste

``--schnell`` ist die Auswahl, die der ``pre-push``-Hook fährt
(``.githooks/pre-push``): Sie kostet zusammen rund vier Sekunden und fängt
genau die Fehlerklassen, die *nach* dem Push teuer werden — eine fremde
E-Mail-Adresse in der Historie, ein Vertrag, der dem Code hinterherläuft.

**Das verbindliche Gate bleibt die CI.** Dieses Skript ist die schnelle
Rückmeldung davor. Fehlt ein Werkzeug (kein venv, ruff nicht installiert),
wird die betroffene Prüfung als ÜBERSPRUNGEN gemeldet und der Lauf gilt
nicht als gescheitert — sie steht dann aber sichtbar in der Zusammenfassung,
damit „grün" nie heißt „ich habe gar nicht geprüft".
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "web" / "frontend"


def _python() -> str:
    """Der Interpreter, der die Entwicklungs-Abhängigkeiten kennt.

    Das venv des Repos zuerst: Wer ``python3 scripts/pruefe.py`` mit dem
    System-Python aufruft, hat dort weder ruff noch pytest — die Prüfungen
    würden reihenweise „übersprungen" melden, obwohl alles vorhanden ist.

    In einem ``git worktree`` liegt das venv nicht daneben, sondern im
    Haupt-Checkout (``.venv/`` ist gitignored und wird beim Anlegen eines
    Worktrees nicht mitkopiert). Deshalb der zweite Kandidat: Über
    ``--git-common-dir`` findet sich der Haupt-Checkout auch von dort aus.
    """
    kandidaten = [WURZEL / ".venv" / "bin" / "python"]
    try:
        gemeinsam = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=WURZEL, capture_output=True, text=True, check=True).stdout.strip()
        if gemeinsam:
            kandidaten.append(Path(gemeinsam).parent / ".venv" / "bin" / "python")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    for k in kandidaten:
        if k.exists():
            return str(k)
    return sys.executable


PY = _python()


class Fehlt(Exception):
    """Ein Werkzeug fehlt — die Prüfung lief nicht, ist aber nicht gescheitert."""


@dataclass
class Pruefung:
    name: str
    was: str
    schnell: bool = False
    befehl: list[str] = field(default_factory=list)
    cwd: Path = WURZEL
    funktion: object = None      # statt eines Unterprozesses: direkt rechnen
    braucht: object = None       # -> str mit Grund, wenn etwas fehlt

    def lauf(self) -> tuple[bool, str]:
        if self.braucht:
            grund = self.braucht()
            if grund:
                raise Fehlt(grund)
        if self.funktion:
            return self.funktion()
        r = subprocess.run(self.befehl, cwd=self.cwd, capture_output=True, text=True)
        return r.returncode == 0, (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- Prüfungen

def _generierte_typen() -> tuple[bool, str]:
    """Passt ``lib/api-schema.ts`` zum eingecheckten Vertrag?

    Geprüft wird die SHA-256-Zeile, die ``scripts/api-typen.mjs`` ans Dateiende
    schreibt — damit braucht diese Prüfung kein Node. Dieselbe Rechnung steht
    als Test in ``tests/test_api_vertrag.py``; hier steht sie noch einmal,
    weil ``--schnell`` ohne pytest auskommen soll.
    """
    vertrag = WURZEL / "api" / "openapi.json"
    typen = FRONTEND / "lib" / "api-schema.ts"
    if not typen.exists():
        return False, "web/frontend/lib/api-schema.ts fehlt — `npm run api:typen` im Frontend."
    summe = hashlib.sha256(vertrag.read_bytes()).hexdigest()
    letzte = typen.read_text().rstrip().splitlines()[-1]
    if letzte != f"// vertrag-sha256: {summe}":
        return False, ("Die generierten Frontend-Typen passen nicht zu api/openapi.json.\n"
                       "  cd web/frontend && npm run api:typen")
    return True, "lib/api-schema.ts passt zum Vertrag."


def _node_fehlt() -> str | None:
    if not shutil.which("npx"):
        return "npx nicht gefunden (Node ≥ 22 installieren)"
    if not (FRONTEND / "node_modules").is_dir():
        return "web/frontend/node_modules fehlt (`cd web/frontend && npm ci`)"
    return None


def _modul_fehlt(modul: str, hinweis: str):
    def pruefen() -> str | None:
        r = subprocess.run([PY, "-c", f"import {modul}"], capture_output=True)
        return None if r.returncode == 0 else f"{modul} nicht installiert ({hinweis})"
    return pruefen


DEV_INSTALL = ".venv/bin/pip install -r requirements-dev.txt -c constraints.txt"

PRUEFUNGEN: list[Pruefung] = [
    Pruefung("adressen", "fremde E-Mail-Adressen im Diff", schnell=True,
             befehl=[PY, "scripts/lint_adressen.py"]),
    Pruefung("ruff", "ungenutzte Importe, undefinierte Namen (nur „F“)", schnell=True,
             befehl=[PY, "-m", "ruff", "check", "."],
             braucht=_modul_fehlt("ruff", DEV_INSTALL)),
    # WOZU EIN TYPPRÜFER, WO ES 2.614 TESTS GIBT. Die Tests messen, was ein Lauf
    # TUT; sie sagen nichts über die Wege, die kein Test nimmt. Genau dort saßen
    # die teuren Fehler der letzten Wochen: ein `None`, das als ID weiterwandert,
    # ein Pflichtfeld, das eine Antwortform nicht trägt (#970 — die Seite blieb
    # leer), ein Argument, das nicht zur Signatur passt (#1065 — der Cron stürzte
    # nachts ab). Alle drei stehen im Code, bevor irgendetwas läuft.
    #
    # DER GELTUNGSBEREICH IST KLEIN UND WÄCHST IN STUFEN — er steht in
    # `pyrightconfig.json`, mitsamt der Begründung. Kurz: Über den ganzen
    # Bestand gemessen sind es 1.309 Befunde, fast tausend davon aus EINER
    # Ursache. Ein Lauf, der immer rot ist, wird abgeschaltet und prüft dann
    # gar nichts. Stufe 1 ist `kern/` und der Backend-Kern; beide sind grün.
    Pruefung("typen-py", "Python-Typen (pyright, Stufe 1)", schnell=True,
             befehl=[PY, "-m", "pyright", "--pythonpath", PY],
             braucht=_modul_fehlt("pyright", DEV_INSTALL)),
    Pruefung("vertrag", "api/openapi.json passt zum Backend-Code", schnell=True,
             befehl=[PY, "scripts/openapi_schnitt.py", "--pruefen"],
             braucht=_modul_fehlt("fastapi", DEV_INSTALL)),
    Pruefung("typen", "lib/api-schema.ts passt zum Vertrag", schnell=True,
             funktion=_generierte_typen),
    Pruefung("changelog", "changelog.d/-Fragmente sind wohlgeformt", schnell=True,
             befehl=[PY, "scripts/changelog_schnitt.py", "--pruefen"]),
    # Die App ist die einzige Schicht ohne erzeugte Typen: Ihre `struct`s stehen
    # von Hand da, und eine Umbenennung im Backend erreicht sie auf keinem Weg.
    Pruefung("ios", "Swift-Modelle gegen ihr Schema halten", schnell=True,
             befehl=[PY, "-m", "pytest", "tests/test_ios_vertrag.py", "-q"],
             braucht=_modul_fehlt("pytest", DEV_INSTALL)),
    # Der Ereignis-Strom ist die einzige Nutzlast, die der Vertrag ausdrücklich
    # NICHT beschreibt — und die beide Clients von Hand parsen.
    Pruefung("strom", "Ereignis-Strom gegen die beiden Client-Parser", schnell=True,
             befehl=[PY, "-m", "pytest", "tests/test_sse_vertrag.py", "-q"],
             braucht=_modul_fehlt("pytest", DEV_INSTALL)),
    Pruefung("tests", "die Testsuite", befehl=[PY, "-m", "pytest", "tests/", "-q"],
             braucht=_modul_fehlt("pytest", DEV_INSTALL)),
    # Die Logik in `web/frontend/lib/` — die größte ungeprüfte Fläche des Repos
    # war bis 09/2026 genau hier: 94.000 Zeilen Frontend gegen 23 Browsertests.
    # Die prüfen Flüsse und brauchen zwei Server und zwei Minuten; für eine
    # Funktion, die aus einer Uhrzeit ein Live-Fenster rechnet, sind sie das
    # falsche Werkzeug. Der Fall „16:29 gegen 16:30" ist dort nicht
    # herstellbar, hier ist er eine Zeile. Läuft in unter einer Sekunde.
    Pruefung("vitest", "Logik-Tests des Frontends (lib/)", schnell=True, cwd=FRONTEND,
             befehl=["npx", "vitest", "run"], braucht=_node_fehlt),
    Pruefung("tsc", "TypeScript des Frontends übersetzen", cwd=FRONTEND,
             befehl=["npx", "tsc", "--noEmit"], braucht=_node_fehlt),
    Pruefung("lint", "ESLint des Frontends (Hook-Regeln)", cwd=FRONTEND,
             befehl=["npx", "next", "lint"], braucht=_node_fehlt),
    Pruefung("skala", "Skalen des Grafik-Baukastens nachrechnen", cwd=FRONTEND,
             befehl=["node", "--experimental-strip-types", "scripts/pruefe-skala.mjs"],
             braucht=_node_fehlt),
    Pruefung("kachelflaeche", "Geometrie der Kachelfläche nachrechnen", cwd=FRONTEND,
             befehl=["node", "--experimental-strip-types", "scripts/pruefe-kachelflaeche.mjs"],
             braucht=_node_fehlt),
]


# ------------------------------------------------------------------- Ablauf

GRUEN, ROT, GELB, GRAU, AUS = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def _farbig() -> bool:
    return sys.stdout.isatty()


def _mal(text: str, farbe: str) -> str:
    return f"{farbe}{text}{AUS}" if _farbig() else text


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--schnell", action="store_true",
                   help="nur die Prüfungen unter ~5 s (Auswahl des pre-push-Hooks)")
    p.add_argument("--nur", help="Komma-Liste von Prüfungen, z. B. ruff,vertrag")
    p.add_argument("--liste", action="store_true", help="Prüfungen aufzählen und aufhören")
    args = p.parse_args()

    if args.liste:
        for pr in PRUEFUNGEN:
            marke = "schnell" if pr.schnell else "       "
            print(f"  {pr.name:<14} {marke}  {pr.was}")
        return 0

    auswahl = PRUEFUNGEN
    if args.schnell:
        auswahl = [pr for pr in auswahl if pr.schnell]
    if args.nur:
        gewuenscht = {n.strip() for n in args.nur.split(",")}
        unbekannt = gewuenscht - {pr.name for pr in PRUEFUNGEN}
        if unbekannt:
            print(f"Unbekannte Prüfung(en): {', '.join(sorted(unbekannt))}\n"
                  f"Bekannt: {', '.join(pr.name for pr in PRUEFUNGEN)}", file=sys.stderr)
            return 2
        auswahl = [pr for pr in auswahl if pr.name in gewuenscht]

    gescheitert: list[tuple[str, str]] = []
    uebersprungen: list[tuple[str, str]] = []
    start = time.monotonic()

    for pr in auswahl:
        # Laufende Zeile nur im Terminal: In eine Datei oder ein CI-Log
        # geschrieben, stünde jede Prüfung sonst doppelt da (\r blendet nichts aus).
        if _farbig():
            print(f"  … {pr.name:<14} {pr.was}", end="\r", flush=True)
        t0 = time.monotonic()
        try:
            ok, ausgabe = pr.lauf()
        except Fehlt as grund:
            print(f"  {_mal('◦', GRAU)} {pr.name:<14} {_mal(f'übersprungen — {grund}', GRAU)}")
            uebersprungen.append((pr.name, str(grund)))
            continue
        except FileNotFoundError as fehler:
            print(f"  {_mal('◦', GRAU)} {pr.name:<14} {_mal(f'übersprungen — {fehler}', GRAU)}")
            uebersprungen.append((pr.name, str(fehler)))
            continue
        dauer = time.monotonic() - t0
        zeichen = _mal("✓", GRUEN) if ok else _mal("✗", ROT)
        zeile = f"  {zeichen} {pr.name:<14} {pr.was}  {_mal(f'{dauer:.1f}s', GRAU)}"
        print(zeile.ljust(90) if _farbig() else zeile)
        if not ok:
            gescheitert.append((pr.name, ausgabe))

    print()
    if gescheitert:
        for name, ausgabe in gescheitert:
            print(_mal(f"── {name} ", ROT) + _mal("─" * max(0, 60 - len(name)), ROT))
            print(ausgabe or "(keine Ausgabe)")
            print()

    gesamt = time.monotonic() - start
    if uebersprungen:
        namen = ", ".join(n for n, _ in uebersprungen)
        print(_mal(f"ACHTUNG: nicht gelaufen — {namen}. "
                   f"Diese Prüfungen macht erst die CI.", GELB))
    if gescheitert:
        print(_mal(f"{len(gescheitert)} Prüfung(en) gescheitert", ROT)
              + f" in {gesamt:.1f}s.")
        return 1
    lief = len(auswahl) - len(uebersprungen)
    print(_mal(f"{lief} Prüfung(en) in Ordnung", GRUEN) + f" ({gesamt:.1f}s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
