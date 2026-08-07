"""Repariert Sperrsatz-Extraktion.

Manche Programm-PDFs (z. B. AfD) sind mit Buchstabenabstand gesetzt. pypdf liefert dann
"K o m m u n a l w a h l p r o g r a m m" statt "Kommunalwahlprogramm" — jede Volltextsuche
läuft ins Leere. In solchen Zeilen gilt: ein Leerzeichen = innerhalb eines Wortes,
zwei oder mehr = Wortgrenze.

Aufruf:  python3 entzerre.py <datei.txt> [--pruefen]
         --pruefen zeigt nur an, ob und wie stark die Datei betroffen ist.
"""

import re
import sys


def ist_gesperrt(zeile):
    t = zeile.split()
    if len(t) < 4:
        return False
    einzel = sum(1 for x in t if len(x) == 1)
    return einzel / len(t) >= 0.6


def entzerre(zeile):
    tmp = re.sub(r" {2,}", "\x00", zeile)
    tmp = tmp.replace(" ", "")
    return tmp.replace("\x00", " ")


def main():
    pfad = sys.argv[1]
    nur_pruefen = "--pruefen" in sys.argv
    zeilen = open(pfad, encoding="utf-8", errors="ignore").read().splitlines()

    betroffen = [i for i, z in enumerate(zeilen) if ist_gesperrt(z)]
    inhalt = [z for z in zeilen if z.strip()]
    quote = len(betroffen) / max(1, len(inhalt))
    print(f"{pfad}: {len(betroffen)} von {len(inhalt)} Inhaltszeilen gesperrt ({quote:.0%})")

    if nur_pruefen or not betroffen:
        if betroffen and not nur_pruefen:
            pass
        else:
            return

    neu = [entzerre(z) if ist_gesperrt(z) else z for z in zeilen]
    open(pfad, "w", encoding="utf-8").write("\n".join(neu))
    print("  repariert. Stichprobe:")
    for i in betroffen[:3]:
        print("   vorher:", zeilen[i].strip()[:90])
        print("   nachher:", neu[i].strip()[:90])


if __name__ == "__main__":
    main()
