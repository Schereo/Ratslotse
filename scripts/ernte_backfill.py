"""Einmaliger Backfill der Regex-Ernte (council.ernte) über den Bestand.

Neue Scrapes tragen die Felder automatisch (save_vorlage/save_protocol) —
dieses Skript holt sie für alles nach, was schon in der DB liegt: Amt,
Klima-/Finanz-Check und Beschlussvorschlag je Vorlage, Sitzungsort je Session,
kvonr je Beschluss (über die Vorlagen-Nummer) und die Abweichung Beschluss ↔
Beschlussvorschlag. Idempotent, kein Netz, kein LLM.

    .venv/bin/python scripts/ernte_backfill.py [--db data/council.sqlite]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council import ernte  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main(db: str | None = None) -> dict:
    store = CouncilStore(db or "data/council.sqlite")
    conn = store._conn  # noqa: SLF001 — Ops-Skript, bewusst direkt auf der DB

    zaehler = {"vorlagen": 0, "amt": 0, "klima": 0, "finanzen": 0, "vorschlag": 0,
               "orte": 0, "kvonr": 0, "deviation": 0}

    rows = conn.execute("SELECT kvonr, raw_text FROM council_vorlagen "
                        "WHERE status = 'ok' AND raw_text IS NOT NULL").fetchall()
    # Erst extrahieren, dann EIN kurzes executemany: Die Regex-Arbeit über
    # ~5000 Volltexte in einer offenen Schreibtransaktion hielt den Write-Lock
    # sekundenlang — parallele Web-Schreiber liefen in „database is locked"
    # (Review-Befund E6).
    updates = []
    for kvonr, text in rows:
        aus = ernte.auswirkungen(text)
        amt = ernte.federfuehrendes_amt(text)
        vorschlag = ernte.beschlussvorschlag(text)
        updates.append((amt, aus["klima"], aus["finanzen"], vorschlag, kvonr))
        zaehler["vorlagen"] += 1
        zaehler["amt"] += bool(amt)
        zaehler["klima"] += bool(aus["klima"])
        zaehler["finanzen"] += bool(aus["finanzen"])
        zaehler["vorschlag"] += bool(vorschlag)
    with conn:
        conn.executemany(
            "UPDATE council_vorlagen SET amt = ?, klima_check = ?, "
            "finanz_check = ?, beschlussvorschlag = ? WHERE kvonr = ?", updates)

    prot = conn.execute("SELECT ksinr, raw_text FROM council_protocols "
                        "WHERE raw_text IS NOT NULL").fetchall()
    with conn:
        for ksinr, text in prot:
            ort = ernte.sitzungsort(text)
            if ort:
                cur = conn.execute(
                    "UPDATE council_sessions SET location = ? "
                    "WHERE ksinr = ? AND location = ''", (ort, ksinr))
                zaehler["orte"] += cur.rowcount

    with conn:
        cur = conn.execute(
            "UPDATE council_decisions SET kvonr = COALESCE("
            "(SELECT MAX(v.kvonr) FROM council_vorlagen v "
            " WHERE v.template_number = council_decisions.template_number), "
            "(SELECT MAX(v.kvonr) FROM council_vorlagen v "
            " WHERE instr(council_decisions.template_number, v.template_number || '/') = 1)) "
            "WHERE kvonr IS NULL AND template_number IS NOT NULL AND EXISTS "
            "(SELECT 1 FROM council_vorlagen v WHERE v.template_number = council_decisions.template_number "
            " OR instr(council_decisions.template_number, v.template_number || '/') = 1)")
        zaehler["kvonr"] = cur.rowcount

    zaehler["deviation"] = store.refresh_abweichung()
    return zaehler


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="Pfad zur council.sqlite (Default: data/council.sqlite)")
    args = ap.parse_args()
    print(main(db=args.db))
