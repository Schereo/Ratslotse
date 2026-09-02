"""Einen Pull Request mergen — aber nur, wenn die CI wirklich fertig und grün ist.

**Der Fehler, gegen den das steht.** Am 02.09.2026 habe ich #1000 gemergt,
während die Testprüfung noch lief. Die Regel steht seit jeher in ``CLAUDE.md``
(„niemals einen roten Lauf mergen, und nie gegen eine CI, die noch den
vorherigen Commit prüft") — sie war nur nirgends ausgeführt. Jede Sitzung
tippte ihre eigene Warteschleife, und meine hatte eine Bedingung falsch herum.
Es ging gut aus; darauf kommt es nicht an.

**Die drei Fallen, die eine Handschleife übersieht.**

1. *Noch nicht fertig.* ``gh pr checks`` zeigt nach einem Force-Push
   minutenlang den Stand des VORHERIGEN Commits. Deshalb wird hier immer gegen
   die Kopf-SHA geprüft, und ein ``in_progress`` ist kein Grün.
2. *Gar nichts gelaufen.* Ein Pull Request mit Konflikt bekommt überhaupt
   keine ``pull_request``-Läufe. Null Prüfungen sind dann „alle grün" — und
   genau das ist der gefährlichste Zustand, weil er wie Erfolg aussieht.
3. *Der falsche Stand.* Wer lokal noch etwas committet und nicht pusht, merged
   einen anderen Baum, als er vor sich hat.

Aufruf im Zweig des Pull Requests::

    python scripts/merge_wenn_gruen.py            # wartet, prüft, merged
    python scripts/merge_wenn_gruen.py --trocken  # nur prüfen, nicht mergen

Der Zweig wird nach dem Merge auf dem Server gelöscht — nicht über
``gh pr merge --delete-branch``: Das bricht ab, wenn ein anderer Worktree auf
dem Zweig steht, und der Merge ist dann schon durch.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

#: Weniger als so viele abgeschlossene Prüfungen heißt: Hier lief etwas nicht.
#: Das Repo fährt auf jedem PR mindestens Tests und die Doku-Durchsicht.
MINDESTENS = 2


def gh(*args: str, versuche: int = 1) -> str:
    letzter = ""
    for versuch in range(versuche):
        ergebnis = subprocess.run(["gh", *args], capture_output=True, text=True)
        if ergebnis.returncode == 0:
            return ergebnis.stdout.strip()
        letzter = ergebnis.stderr.strip()
        if versuch + 1 < versuche:
            time.sleep(15)
    raise SystemExit(f"gh {' '.join(args)} scheiterte:\n{letzter}")


def kopf_lokal() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()


def pruefungen(sha: str) -> list[tuple[str, str, str]]:
    """Der Stand der Prüfläufe — mit drei Versuchen.

    Beim Warten läuft dieser Aufruf minutenlang alle 30 Sekunden. Ein einzelner
    Aussetzer („error connecting to api.github.com", am 02.09.2026 mitten in
    einem Lauf) darf das Tor nicht abbrechen lassen: Der Pull Request wäre
    dann ungemergt, obwohl alles grün ist, und der nächste Anlauf müsste von
    vorn warten.
    """
    roh = gh("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs",
             "-q", ".check_runs[] | [.name, .status, (.conclusion // \"—\")] | @tsv",
             versuche=3)
    return [tuple(z.split("\t")) for z in roh.splitlines() if z]


def bericht(zeilen) -> str:
    return "\n".join(f"    {n:14s} {s}/{e}" for n, s, e in sorted(zeilen)) or "    (keine)"


#: Abschlüsse, die als bestanden gelten. `skipped` entsteht durch die
#: Pfad-Filter der Workflows — der iOS-Auftrag läuft nur, wenn jemand `ios/`
#: anfasst, und das ist kein Fehlschlag.
BESTANDEN = {"success", "neutral", "skipped"}


def urteil(zeilen: list[tuple[str, str, str]]) -> str:
    """``"wartet" | "zu wenige" | "rot" | "gruen"`` — die eine Entscheidung.

    Sie steht hier und nicht im Ablauf, damit ein Test sie prüfen kann, statt
    sie nachzuspielen. Ein nachgespieltes Urteil ist immer grün.
    """
    if not zeilen or any(z[1] != "completed" for z in zeilen):
        return "wartet"
    if len(zeilen) < MINDESTENS:
        return "zu wenige"
    if any(z[2] not in BESTANDEN for z in zeilen):
        return "rot"
    return "gruen"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pr", help="Nummer; ohne sie der PR des aktuellen Zweigs")
    p.add_argument("--warten", type=int, default=1800,
                   help="Sekunden, die auf laufende Prüfungen gewartet wird")
    p.add_argument("--trocken", action="store_true", help="nur prüfen, nicht mergen")
    args = p.parse_args(argv)

    ziel = ["--json", "number,headRefOid,mergeable,state,title,headRefName"]
    daten = json.loads(gh("pr", "view", *( [args.pr] if args.pr else [] ), *ziel))
    nummer, sha = daten["number"], daten["headRefOid"]
    print(f"#{nummer} „{daten['title']}\"\n  Kopf {sha[:12]}  ({daten['headRefName']})")

    if daten["state"] != "OPEN":
        print(f"  Zustand {daten['state']} — nichts zu tun.")
        return 0
    if daten["mergeable"] == "CONFLICTING":
        print("  KONFLIKT. Ein Pull Request mit Konflikt bekommt gar keine "
              "Prüfläufe — erst auflösen.", file=sys.stderr)
        return 1
    if not args.pr and kopf_lokal() != sha:
        print(f"  Der lokale Stand ({kopf_lokal()[:12]}) ist nicht der des Pull "
              "Requests. Erst pushen.", file=sys.stderr)
        return 1

    frist = time.time() + args.warten
    while True:
        zeilen = pruefungen(sha)
        stand = urteil(zeilen)
        if stand != "wartet":
            break
        if time.time() > frist:
            print(f"  Nach {args.warten}s noch nicht fertig:\n{bericht(zeilen)}",
                  file=sys.stderr)
            return 1
        offen = sum(1 for z in zeilen if z[1] != "completed")
        print(f"  … {offen} offen" if zeilen else "  … noch keine Prüfung gestartet")
        time.sleep(30)

    print(bericht(zeilen))
    if stand == "zu wenige":
        print(f"  Nur {len(zeilen)} Prüfung(en) — erwartet werden mindestens "
              f"{MINDESTENS}. Ein Pull Request, auf dem nichts lief, sieht aus "
              "wie einer, auf dem alles grün ist.", file=sys.stderr)
        return 1
    if stand == "rot":
        rot = [n for n, _, e in zeilen if e not in BESTANDEN]
        print(f"  Nicht grün: {', '.join(rot)}", file=sys.stderr)
        return 1

    if args.trocken:
        print("  Alles grün — nicht gemergt (--trocken).")
        return 0

    gh("pr", "merge", str(nummer), "--squash")
    # Getrennt vom Merge: `gh pr merge --delete-branch` bricht ab, wenn ein
    # anderer Worktree auf dem Zweig steht — und der Merge ist dann schon
    # durch, die Meldung sieht trotzdem nach Fehlschlag aus.
    subprocess.run(["git", "push", "origin", "--delete", daten["headRefName"]],
                   capture_output=True, text=True)
    print(f"  Gemergt (squash), Zweig {daten['headRefName']} gelöscht.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
