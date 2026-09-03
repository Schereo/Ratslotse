#!/usr/bin/env python3
"""Zwei Fingerabdrücke gegenüberstellen — und die richtige Frage stellen.

Gegenstück zu ``haushalt_fingerprint.py``: Der läuft je Umgebung und schreibt
Hashes, dieser vergleicht zwei solche Ausgaben. Getrennt, weil der eine auf der
VM läuft und der andere auf dem Runner.

**Was der Vergleich beantwortet.** Nicht „sind die Dateien gleich" — das sagt
``diff`` auch. Sondern die beiden Fragen, die danach kommen:

1. **Wie viele Zeilen** weichen ab? Eine von 623 ist ein Einzelfall, 623 von
   623 ist eine systematische Ursache. Dieselbe rote Tabelle, zwei völlig
   verschiedene Diagnosen — und ohne diese Zahl fängt man am falschen Ende an.
2. **Liegt es an den Zahlen oder am Beleg?** ``haushalt_fingerprint.py
   --ohne-herkunft`` rechnet denselben Abdruck ohne die Herkunft. Stimmen die
   Werte dort überein und weicht nur der Vollmodus ab, dann stehen in beiden
   Umgebungen dieselben Zahlen und zeigen bloß auf verschieden belegte
   Dokumente. Das ist ein Befund über die Belegkette, nicht über die Zahlen.

**Ausgegeben werden nur ZAHLEN.** Kein Inhalt, keine Zeile, kein Feld. Der
Grund ist nicht Sparsamkeit: Dieses Skript läuft in einem GitHub-Workflow, das
Repo ist öffentlich, und damit sind die Protokolle öffentlich.
``council_donations`` trägt Spendernamen. Ein Inhalts-Dump wäre hier ein
Datenleck und kein Diagnosewerkzeug — wer eine einzelne Zeile sehen muss, tut
das auf der VM und nicht im Protokoll.

Aufruf::

    python3 scripts/haushalt_vergleich.py dev.txt prod.txt \\
        --nur-zahlen dev-nur-zahlen.txt prod-nur-zahlen.txt

Exit 0 = identisch, 1 = Unterschied (der Workflow wird damit rot), 2 = Aufruf-
oder Leseproblem.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

#: Länge eines sha256 in Hex — die Erkennungsmarke einer Hash-Spalte.
HASHLAENGE = 64


def lesen(pfad: str) -> tuple[dict[str, tuple[str, int]], dict[str, set[str]]]:
    """``({tabelle: (gesamthash, zeilen)}, {tabelle: {zeilenhashes}})``.

    Geparst wird die Ausgabe von ``haushalt_fingerprint.py``. Eingerückte
    Zeilen sind Einzelhashes (nur mit ``--zeilen`` da), alles andere
    Tabellenzeilen. Die Hash-Länge dient als Erkennungsmarke, damit die
    Schlusszeile („56 Tabellen, 0 Zeilen ohne Herkunft") nicht als Tabelle
    durchgeht — sie hat drei Felder wie eine echte.
    """
    tabellen: dict[str, tuple[str, int]] = {}
    zeilen: dict[str, set[str]] = {}
    for roh in pathlib.Path(pfad).read_text(encoding="utf-8").splitlines():
        if roh.startswith("    ") and "\t" in roh:
            name, h = roh.strip().split("\t", 1)
            zeilen.setdefault(name, set()).add(h)
            continue
        teile = roh.split()
        if len(teile) == 3 and len(teile[2]) == HASHLAENGE and teile[1].isdigit():
            tabellen[teile[0]] = (teile[2], int(teile[1]))
    return tabellen, zeilen


def bericht(dev: str, prod: str,
            nur_zahlen: tuple[str, str] | None = None) -> tuple[str, int]:
    """``(Markdown-Bericht, Exit-Code)``."""
    dv, dz = lesen(dev)
    pv, pz = lesen(prod)
    if not dv or not pv:
        return ("✗ Eine der beiden Ausgaben enthält keine Tabellenzeile — "
                "hat `haushalt_fingerprint.py` überhaupt gelaufen?"), 2

    dvn: dict[str, tuple[str, int]] = {}
    pvn: dict[str, tuple[str, int]] = {}
    if nur_zahlen:
        dvn, _ = lesen(nur_zahlen[0])
        pvn, _ = lesen(nur_zahlen[1])

    fehlend = sorted(set(dv) ^ set(pv))
    gemeinsam = set(dv) & set(pv)
    abweichend = sorted(t for t in gemeinsam if dv[t][0] != pv[t][0])

    aus = ["## Finanzdaten dev ↔ prod", ""]
    if not abweichend and not fehlend:
        aus.append(f"✅ Identisch — alle {len(dv)} Tabellen, jede Zahl, jeder Beleg.")
        return "\n".join(aus), 0

    if fehlend:
        aus += ["**Nur in einer Umgebung vorhanden:** "
                + ", ".join(f"`{t}`" for t in fehlend),
                "",
                "Eine Tabelle, die es nur hier oder nur dort gibt, ist kein "
                "Zahlenproblem — dort fehlt ein Ingest oder eine Migration.",
                ""]

    if abweichend:
        aus += [f"{len(abweichend)} von {len(gemeinsam)} gemeinsamen Tabellen weichen "
                "ab. Ausgegeben werden nur Zahlen, keine Inhalte — dieses Protokoll "
                "ist öffentlich, und einige dieser Tabellen tragen Namen.",
                "",
                "| Tabelle | dev | prod | nur dev | nur prod | Zahlen allein |",
                "|---|---:|---:|---:|---:|---|"]
        for t in abweichend:
            nur_d = len(dz.get(t, set()) - pz.get(t, set()))
            nur_p = len(pz.get(t, set()) - dz.get(t, set()))
            if nur_zahlen:
                gleich = dvn.get(t, ("d",))[0] == pvn.get(t, ("p",))[0]
                spalte = "gleich" if gleich else "**abweichend**"
            else:
                spalte = "—"
            aus.append(f"| `{t}` | {dv[t][1]} | {pv[t][1]} | "
                       f"{nur_d} | {nur_p} | {spalte} |")
        aus += ["",
                "Spalte *Zahlen allein*: **gleich** heißt, die Werte stimmen "
                "überein und nur der Herkunfts-Beleg zeigt auf ein anderes "
                "Dokument. **abweichend** heißt, dort stehen wirklich andere Zahlen.",
                "",
                "Welche einzelne Zeile es ist, sagt auf der VM selbst — nicht hier:",
                "`.venv/bin/python scripts/haushalt_fingerprint.py "
                "--tabelle <name> --zeilen`"]
    return "\n".join(aus), 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("dev", help="Fingerabdruck der einen Umgebung")
    p.add_argument("prod", help="Fingerabdruck der anderen")
    p.add_argument("--nur-zahlen", nargs=2, metavar=("DEV", "PROD"),
                   help="dieselben Abdrücke mit --ohne-herkunft; erst damit kann "
                        "der Bericht Zahlen- von Beleg-Unterschieden trennen")
    args = p.parse_args(argv)
    try:
        text, code = bericht(args.dev, args.prod,
                             tuple(args.nur_zahlen) if args.nur_zahlen else None)
    except OSError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
