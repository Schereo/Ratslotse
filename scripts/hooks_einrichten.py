#!/usr/bin/env python3
"""Sorgt dafür, dass die Git-Hooks in DIESEM Arbeitsverzeichnis wirklich laufen.

**Der Fehler, gegen den das steht.** Die Anleitung in ``CLAUDE.md`` lautet
``git config core.hooksPath .githooks`` — ein **relativer** Pfad, den Git gegen
den jeweiligen Arbeitsbaum auflöst. In einem ``git worktree`` funktioniert das.

Geschrieben stand dort trotzdem oft der **absolute** Pfad des Haupt-Checkouts.
Und damit fällt der ``pre-push``-Hook lautlos aus, sobald der Haupt-Checkout
auf einem Zweig steht, der ``.githooks/pre-push`` noch nicht kennt: Git sucht
die Datei im *Arbeitsbaum* jenes Zweigs, findet sie nicht, und pusht ohne eine
einzige Prüfung.

Gemessen am 04.09.2026 über die zehn Arbeitsverzeichnisse dieses Repos:

    5 × absoluter Pfad auf den Haupt-Checkout   → pre-push lief NICHT
    1 × gar nichts gesetzt                      → pre-push lief NICHT
    4 × relativ, richtig

Es ist kein theoretischer Fall. Genau so ging an diesem Tag ein Push mit zwei
ruff-Befunden durch; gemerkt hat es erst die CI, drei Minuten später.

**Was hier passiert.** Findet Git im wirksamen Hook-Verzeichnis kein
``pre-push``, dieses Arbeitsverzeichnis aber schon, wird ``core.hooksPath`` auf
den relativen Wert gesetzt — arbeitsbaum-genau, damit die Nachbarn unberührt
bleiben.

**Was NICHT passiert.** Eine bewusste Abwahl bleibt stehen. Wer
``core.hooksPath /dev/null`` setzt, will keine Hooks und behält keine;
überschrieben wird nur ein Wert, der ``.githooks`` bereits *meint* und ihn
verfehlt.

Läuft beim Sitzungsstart (``.claude/settings.json``) und von Hand:

.. code-block:: sh

    python3 scripts/hooks_einrichten.py          # richtet ein, sagt was es tat
    python3 scripts/hooks_einrichten.py --pruefen  # meldet nur, ändert nichts
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: Der Hook, an dem sich „laufen die Hooks?" entscheidet. ``pre-commit`` taugt
#: dafür nicht: Er ist älter und liegt auch auf Zweigen, die ``pre-push`` noch
#: nicht haben — genau die Zweige, um die es geht.
PROBE = "pre-push"


def soll_setzen(hookdir_hat_probe: bool, gesetzt: str | None,
                baum_hat_probe: bool) -> str | None:
    """Der Entschluss, als reine Funktion — damit er prüfbar ist.

    Rückgabe: der Wert für ``core.hooksPath``, oder ``None`` für „nichts tun".
    """
    if hookdir_hat_probe:
        return None                      # die Hooks laufen bereits
    if gesetzt is not None and not gesetzt.rstrip("/").endswith(".githooks"):
        return None                      # bewusste Abwahl (z. B. /dev/null)
    if not baum_hat_probe:
        return None                      # dieser Zweig kennt die Hooks nicht
    return ".githooks"


def _git(*args: str) -> str | None:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pruefen", action="store_true",
                   help="nur melden, nichts ändern (Rückgabe 1, wenn etwas fehlt)")
    args = p.parse_args()

    oben = _git("rev-parse", "--show-toplevel")
    if oben is None:
        return 0                         # kein Repo — nicht im Weg stehen
    baum = Path(oben)

    hookdir = _git("rev-parse", "--git-path", "hooks") or ""
    pfad = Path(hookdir)
    if not pfad.is_absolute():
        pfad = baum / pfad

    ziel = soll_setzen(
        hookdir_hat_probe=(pfad / PROBE).exists(),
        gesetzt=_git("config", "--get", "core.hooksPath"),
        baum_hat_probe=(baum / ".githooks" / PROBE).exists(),
    )
    if ziel is None:
        if not args.pruefen:
            print(f"Hooks in Ordnung ({pfad}).")
        return 0

    if args.pruefen:
        print(f"FEHLT: {pfad} trägt kein {PROBE} — `python3 "
              f"scripts/hooks_einrichten.py` richtet es ein.", file=sys.stderr)
        return 1

    # Arbeitsbaum-genau, wo möglich: Die Nachbar-Worktrees haben ihre eigene
    # Lage und sollen von dieser Reparatur nichts merken.
    if _git("config", "--get", "extensions.worktreeConfig") == "true":
        _git("config", "--worktree", "core.hooksPath", ziel)
    else:
        _git("config", "core.hooksPath", ziel)
    print(f"core.hooksPath auf {ziel!r} gesetzt — {PROBE} lief hier vorher nicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
