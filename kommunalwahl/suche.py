"""Gezielte Belegsuche in den Programm-Volltexten.

Aufruf:
    python3 suche.py <slug|alle> <regex> [<regex> ...] [--kontext N] [--max N]

Beispiele:
    python3 suche.py spd "Baumschutzsatzung"
    python3 suche.py alle "Parkgeb|Parkraum|Anwohnerpark" --kontext 3
    python3 suche.py cdu "Stadion" --max 6

Gibt Treffer mit Seitenzahl (aus den [Seite N]-Markern) und Kontextzeilen aus,
damit Positionen belegt statt geraten werden.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(BASE, "programme")


def seiten_index(zeilen):
    """Zeilennummer -> aktuelle Seitenzahl (None bei Webquellen).

    Wichtig: Ein [Quelle: ...]-Marker stammt von html2text --append und leitet eine
    angehaengte Webquelle ohne Seitenzahlen ein. Ohne diesen Reset wuerde die letzte
    PDF-Seitenzahl faelschlich weitergefuehrt und Belege bekaemen erfundene Seiten.
    """
    idx, seite = [], None
    for z in zeilen:
        s = z.strip()
        m = re.match(r"=====\s*\[Seite (\d+)\]", s)
        if m:
            seite = int(m.group(1))
        elif re.match(r"=====\s*\[Quelle:", s):
            seite = None
        idx.append(seite)
    return idx


def durchsuche(slug, muster, kontext, maxtreffer):
    pfad = os.path.join(PROG, f"{slug}.txt")
    if not os.path.exists(pfad):
        return
    zeilen = open(pfad, encoding="utf-8", errors="ignore").read().splitlines()
    seiten = seiten_index(zeilen)
    rx = re.compile("|".join(f"(?:{m})" for m in muster), re.I)

    treffer = [i for i, z in enumerate(zeilen) if rx.search(z) and not z.strip().startswith("=====")]
    if not treffer:
        return

    print(f"\n{'='*70}\n{slug.upper()}  —  {len(treffer)} Treffer\n{'='*70}")
    gezeigt, letzte = 0, -99
    for i in treffer:
        if gezeigt >= maxtreffer:
            print(f"   ... {len(treffer)-gezeigt} weitere Treffer unterdrueckt (--max erhoehen)")
            break
        if i - letzte < kontext:      # überlappende Fundstellen zusammenfassen
            continue
        letzte = i
        gezeigt += 1
        s = f"S. {seiten[i]}" if seiten[i] else "web"
        print(f"\n  [{s}, Zeile {i+1}]")
        for j in range(max(0, i - kontext), min(len(zeilen), i + kontext + 1)):
            z = zeilen[j].strip()
            if not z or z.startswith("====="):
                continue
            print(("  > " if j == i else "    ") + z[:300])


def main():
    args = [a for a in sys.argv[1:]]
    kontext, maxtreffer = 2, 10
    for flag, standard in (("--kontext", 2), ("--max", 10)):
        if flag in args:
            k = args.index(flag)
            val = int(args[k + 1])
            del args[k:k + 2]
            if flag == "--kontext":
                kontext = val
            else:
                maxtreffer = val

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    ziel, muster = args[0], args[1:]
    slugs = ([f[:-4] for f in sorted(os.listdir(PROG)) if f.endswith(".txt")]
             if ziel == "alle" else [ziel])
    for s in slugs:
        durchsuche(s, muster, kontext, maxtreffer)


if __name__ == "__main__":
    main()
