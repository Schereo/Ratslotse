#!/usr/bin/env python3
"""Abgeschnittene Partei-/Verbandsnamen in Wortbeiträgen reparieren.

Die Extraktion kappte das Feld hart bei 40 Zeichen — mitten im Wort. In einer
KI-Antwort stand deshalb „Adler (Fraktion Bündnis Vernunft und Gerechtigk)"
(Befund 12.08.2026). Der Code kappt nicht mehr so (council/wortbeitraege.py);
dieses Skript heilt den Bestand.

Die vollen Namen stehen bereits in der Datenbank: `council_attendance.party`
stammt aus DERSELBEN Protokollseite, wurde aber nie gekürzt. Repariert wird
deshalb rein deterministisch — kein LLM, kein Raten:

  1. Kandidaten sind nur Werte mit exakt 40 Zeichen (die Kappungsgrenze).
  2. Gesucht wird zuerst in DERSELBEN Sitzung nach einem Anwesenheits-Eintrag,
     der mit dem Stumpf beginnt; sonst sitzungsübergreifend.
  3. Nur wenn genau EINE Vollform übrig bleibt, wird geschrieben. Mehrere
     Schreibweisen (z. B. „VCD-Kreisverband Oldenburg Stadt und Land e. V."
     vs. „… e.V.") entscheidet die Häufigkeit; bei Gleichstand bleibt der
     Eintrag, wie er ist.

    .venv/bin/python scripts/fix_partei_stuempfe.py            # Bericht
    .venv/bin/python scripts/fix_partei_stuempfe.py --schreiben
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore

COUNCIL_DB = ROOT / "data" / "council.sqlite"
GRENZE = 40  # die alte, harte Kappungsgrenze


def _vollformen(conn, stumpf: str, ksinr: int | None) -> list[str]:
    """Anwesenheits-Einträge, die mit dem Stumpf beginnen (längster zuerst)."""
    sql = ("SELECT party, COUNT(*) n FROM council_attendance "
           "WHERE party LIKE ? AND length(party) > ? ")
    args: list = [stumpf.replace("%", r"\%") + "%", GRENZE]
    if ksinr is not None:
        sql += "AND ksinr = ? "
        args.append(ksinr)
    sql += "GROUP BY party ORDER BY n DESC, length(party) DESC"
    return [(r["party"], r["n"]) for r in conn.execute(sql, args)]


def main() -> dict:
    p = argparse.ArgumentParser(description="Abgeschnittene Parteinamen heilen")
    p.add_argument("--schreiben", action="store_true", help="Änderungen wirklich speichern")
    args = p.parse_args()

    store = CouncilStore(COUNCIL_DB)
    conn = store._conn
    try:
        betroffen = conn.execute(
            "SELECT id, ksinr, party FROM council_speeches "
            "WHERE length(party) = ?", (GRENZE,)).fetchall()
        print(f"{len(betroffen)} Beiträge mit exakt {GRENZE} Zeichen"
              f"{'' if args.schreiben else '  (Bericht — nichts wird geschrieben)'}")

        geheilt = offen = 0
        zaehler: Counter = Counter()
        for r in betroffen:
            stumpf = r["party"]
            kandidaten = _vollformen(conn, stumpf, r["ksinr"]) or _vollformen(conn, stumpf, None)
            if not kandidaten:
                offen += 1
                zaehler[f"ohne Vollform: {stumpf}"] += 1
                continue
            if len(kandidaten) > 1 and kandidaten[0][1] == kandidaten[1][1]:
                offen += 1                      # Gleichstand → lieber lassen
                zaehler[f"mehrdeutig: {stumpf}"] += 1
                continue
            voll = kandidaten[0][0]
            zaehler[f"{stumpf} → {voll}"] += 1
            if args.schreiben:
                with conn:
                    conn.execute("UPDATE council_speeches SET party = ? WHERE id = ?",
                                 (voll, r["id"]))
            geheilt += 1

        for text, n in zaehler.most_common():
            print(f"  {n:5d}  {text}")
        print(f"Fertig: {geheilt} geheilt, {offen} unverändert"
              f"{'' if args.schreiben else ' (Bericht)'}")
        return {"geheilt": geheilt, "offen": offen}
    finally:
        store.close()


if __name__ == "__main__":
    main()
