"""node_modules des Frontends NEBEN dem laufenden Server erneuern, nicht unter ihm.

Bis 11/2026 lief in jedem Deploy (``deploy.yml``, ``deploy-dev.yml``,
``deploy-feature.yml``) ``npm ci`` direkt in ``web/frontend``. ``npm ci``
leert ``node_modules`` als Erstes — der laufende ``next start`` lädt Module
aber erst beim ersten Bedarf nach. Am 12.11.2026 auf dev: 15 Sekunden nach
Beginn eines Deploys scheiterte die erste Seite nach einer
Passkey-Registrierung mit „Cannot find module 'next/dist/compiled/cookie'“,
die Seite zeigte nur „Internal Server Error“. Den Build selbst legt der Deploy
seit #1766 schon daneben (``.next-build``); die Module waren die Lücke, die
blieb.

Jetzt:

1. **Nichts geändert** (Lockfile, Node- und npm-Version gleich, Baum
   vollständig): ``node_modules`` bleibt unberührt — der Normalfall, denn die
   meisten Deploys ändern keine Abhängigkeit.
2. **Sonst** entsteht der neue Baum in einem Nachbarordner und tauscht per
   Umbenennung den Platz mit dem alten. Der laufende Server findet damit
   entweder den alten oder den neuen vollständigen Baum, nie einen halben.

Was es nicht auffängt: Ändert sich die Lockfile, läuft der alte Server vom
Tausch bis zu seinem Neustart (also während des Builds) auf den neuen Modulen
— wie vorher nach ``npm ci``, nur ohne die Minute, in der es sie gar nicht
gab. Bricht ``npm ci`` ab, bleibt der alte Baum stehen, und der Deploy endet
mit dem Fehler.

    .venv/bin/python scripts/install_frontend_modules.py web/frontend
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: Liegt im fertigen Baum und nennt den Stand, aus dem er entstand.
STAMP_NAME = ".ratslotse-stamp"
#: Der alte Baum nach dem Tausch; Reste eines abgebrochenen Laufs tragen
#: dieselbe Vorsilbe und werden beim nächsten Lauf weggeräumt.
OLD_PREFIX = "node_modules-old-"


def staging_dir(frontend: Path) -> Path:
    """Außerhalb von ``web/frontend``, damit weder ``tsc`` noch ``next
    build`` ihn je zu sehen bekommen — aber auf derselben Platte, sonst wäre
    der Tausch eine Kopie statt einer Umbenennung."""
    return frontend.parent / f"{frontend.name}-modules-staging"


def _version(command: str) -> str:
    return subprocess.run([command, "--version"], check=True, capture_output=True,
                          text=True).stdout.strip()


def stamp(frontend: Path) -> str:
    """Lockfile plus Node- und npm-Version: Ein neues Node braucht neu gebaute
    native Module, auch wenn die Lockfile gleich bleibt."""
    digest = hashlib.sha256((frontend / "package-lock.json").read_bytes())
    digest.update(f"|{_version('node')}|{_version('npm')}".encode())
    return digest.hexdigest()


def tree_complete(frontend: Path) -> bool:
    """Fehlt ein Paket oder passt eines nicht zur Lockfile, meldet ``npm ls``
    einen Fehler. Fängt den Baum, den ein abgebrochener Lauf halb geleert
    hat (06.09.2026 auf Prod: 8 statt rund 600 Pakete) — dort kann der
    Stempel noch liegen."""
    return subprocess.run(["npm", "ls", "--depth=0"], cwd=frontend,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _remove_leftovers(frontend: Path) -> None:
    for old in frontend.glob(f"{OLD_PREFIX}*"):
        shutil.rmtree(old, ignore_errors=True)
    shutil.rmtree(staging_dir(frontend), ignore_errors=True)


def install(frontend: Path) -> str:
    """``"unchanged"`` oder ``"installed"``; wirft, wenn ``npm ci`` scheitert."""
    frontend = frontend.resolve()
    modules = frontend / "node_modules"
    wanted = stamp(frontend)
    stamp_file = modules / STAMP_NAME
    _remove_leftovers(frontend)
    if (stamp_file.is_file() and stamp_file.read_text().strip() == wanted
            and tree_complete(frontend)):
        print("node_modules unverändert, kein npm ci.")
        return "unchanged"

    staging = staging_dir(frontend)
    staging.mkdir()
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(frontend / name, staging / name)
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=staging, check=True)
    (staging / "node_modules" / STAMP_NAME).write_text(wanted + "\n")

    # Der Tausch: zwei Umbenennungen auf derselben Platte, Mikrosekunden
    # auseinander. Der eindeutige Name für den alten Baum hält auch dann, wenn
    # ein Rest sich oben nicht löschen ließ.
    old = frontend / f"{OLD_PREFIX}{int(time.time())}"
    if modules.exists():
        modules.rename(old)
    (staging / "node_modules").rename(modules)
    shutil.rmtree(old, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)
    print("node_modules neu installiert und getauscht.")
    return "installed"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    ap.add_argument("frontend", type=Path, help="Verzeichnis mit package-lock.json")
    args = ap.parse_args(argv)
    try:
        install(args.frontend)
    except subprocess.CalledProcessError as exc:
        print(f"FEHLER: {' '.join(map(str, exc.cmd))} endete mit {exc.returncode}; "
              "node_modules bleibt auf dem alten Stand.", file=sys.stderr)
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
