"""Backfill der Regex-Ernte (council.ernte) über den Bestand.

Neue Scrapes tragen die Felder automatisch (save_vorlage/save_protocol) —
dieses Skript holt sie für alles nach, was schon in der DB liegt: Amt,
Klima-/Finanz-Check und Beschlussvorschlag je Vorlage, Sitzungsort je Session,
kvonr je Beschluss (über die Vorlagen-Nummer) und die Abweichung Beschluss ↔
Beschlussvorschlag. Idempotent, kein Netz, kein LLM.

**Nicht einmalig, sondern wöchentlich** (Schritt in `weekly_enrich.py`). Der
Grund steht in der Messung vom 08.09.2026: `federfuehrendes_amt` liefert für
99,8 % der 5079 Vorlagen einen Treffer, gespeichert waren 95. Ein Backfill,
den niemand wieder aufruft, läuft genau einmal — und jede spätere Verbesserung
an den Regexen erreicht den Bestand dann nie. Deshalb schreibt der Lauf auch
nur die Zeilen, die sich wirklich ändern: Steht in `geaendert` eine 0, hat die
Ernte nichts Neues zu sagen, und das ist der Normalfall.

    .venv/bin/python scripts/ernte_backfill.py [--db data/council.sqlite] [--trocken]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council import ernte  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main(db: str | None = None, trocken: bool = False) -> dict:
    store = CouncilStore(db or "data/council.sqlite")
    conn = store._conn  # noqa: SLF001 — Ops-Skript, bewusst direkt auf der DB

    zaehler = {"vorlagen": 0, "geaendert": 0, "office": 0, "klima": 0, "finanzen": 0,
               "vorschlag": 0, "orte": 0, "kvonr": 0, "deviation": 0}
    if trocken:
        # Die Abweichung Beschluss ↔ Vorschlag rechnet der Store schreibend
        # (refresh_abweichung). Trocken bleibt sie also UNBESTIMMT — und eine
        # unbestimmte Zahl gehört nicht als „0" in den Bericht, sonst liest
        # sie sich wie „keine einzige Abweichung".
        del zaehler["deviation"]

    rows = conn.execute(
        "SELECT kvonr, raw_text, office, climate_impact, financial_impact, proposed_decision "
        "FROM council_templates WHERE status = 'ok' AND raw_text IS NOT NULL").fetchall()
    # Erst extrahieren, dann EIN kurzes executemany: Die Regex-Arbeit über
    # ~5000 Volltexte in einer offenen Schreibtransaktion hielt den Write-Lock
    # sekundenlang — parallele Web-Schreiber liefen in „database is locked"
    # (Review-Befund E6).
    updates = []
    for kvonr, text, alt_office, alt_klima, alt_finanz, alt_vorschlag in rows:
        aus = ernte.auswirkungen(text)
        neu = (ernte.federfuehrendes_amt(text), aus["klima"], aus["finanzen"],
               ernte.proposed_decision(text))
        zaehler["vorlagen"] += 1
        zaehler["office"] += bool(neu[0])
        zaehler["klima"] += bool(neu[1])
        zaehler["finanzen"] += bool(neu[2])
        zaehler["vorschlag"] += bool(neu[3])
        # Nur schreiben, was sich unterscheidet — sonst schreibt jeder
        # Wochenlauf 5000 unveränderte Zeilen ins WAL, und die Kennzahl
        # „geaendert" könnte nicht mehr zwischen „nichts Neues" und
        # „Ernte kaputt" unterscheiden.
        if neu != (alt_office, alt_klima, alt_finanz, alt_vorschlag):
            zaehler["geaendert"] += 1
            updates.append((*neu, kvonr))
    if updates and not trocken:
        with conn:
            conn.executemany(
                "UPDATE council_templates SET office = ?, climate_impact = ?, "
                "financial_impact = ?, proposed_decision = ? WHERE kvonr = ?", updates)

    prot = conn.execute("SELECT ksinr, raw_text FROM council_protocols "
                        "WHERE raw_text IS NOT NULL").fetchall()
    orte = [(ort, ksinr) for ksinr, text in prot if (ort := ernte.sitzungsort(text))]
    if trocken:
        offen = {k for (k,) in conn.execute(
            "SELECT ksinr FROM council_sessions WHERE location = ''")}
        zaehler["orte"] = sum(1 for _, ksinr in orte if ksinr in offen)
    else:
        with conn:
            for ort, ksinr in orte:
                cur = conn.execute(
                    "UPDATE council_sessions SET location = ? "
                    "WHERE ksinr = ? AND location = ''", (ort, ksinr))
                zaehler["orte"] += cur.rowcount

    # Beschlüsse ohne kvonr über die Vorlagen-Nummer nachverdrahten.
    KVONR_WHERE = (
        "WHERE kvonr IS NULL AND template_number IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM council_templates v WHERE v.template_number = council_decisions.template_number "
        " OR instr(council_decisions.template_number, v.template_number || '/') = 1)")
    if trocken:
        zaehler["kvonr"] = conn.execute(
            "SELECT COUNT(*) FROM council_decisions " + KVONR_WHERE).fetchone()[0]
    else:
        with conn:
            cur = conn.execute(
                "UPDATE council_decisions SET kvonr = COALESCE("
                "(SELECT MAX(v.kvonr) FROM council_templates v "
                " WHERE v.template_number = council_decisions.template_number), "
                "(SELECT MAX(v.kvonr) FROM council_templates v "
                " WHERE instr(council_decisions.template_number, v.template_number || '/') = 1)) "
                + KVONR_WHERE)
            zaehler["kvonr"] = cur.rowcount
        zaehler["deviation"] = store.refresh_abweichung()
    return zaehler


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="Pfad zur council.sqlite (Default: data/council.sqlite)")
    ap.add_argument("--trocken", action="store_true",
                    help="nur berichten, was sich ändern würde — nichts schreiben")
    args = ap.parse_args()
    print(main(db=args.db, trocken=args.trocken))
