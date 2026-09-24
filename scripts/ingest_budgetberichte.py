#!/usr/bin/env python3
"""Die Budgetberichte der Fachausschüsse einlesen — Investitionen je Maßnahme.

Parser und Probe: ``council/budgetberichte.py``. Gelesen werden die Anlagen
der Vorlagen „Budgetbericht …" aus dem Bestand, und zwar die der Teilhaushalte
11 (Jugend und Familie) und 12 (Schule und Bildung): Nur sie führen die
Tabelle über viele Jahrgänge (Messung im Plan, PR 8). Ein Bericht wird nur
gespeichert, wenn seine Maßnahmen die Summenzeile der Teilfinanzrechnung
ergeben.

Höflich: 1,5 s Abstand, ein Abruf je Anlage; schon gespeicherte Stichtage
werden übersprungen (``--alle`` liest sie neu). Kein Sprachmodell.

    python scripts/ingest_budgetberichte.py --trocken
    python scripts/ingest_budgetberichte.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import budgetberichte as bb  # noqa: E402
from council import herkunft  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
TEILHAUSHALTE = (11, 12)


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        return antwort.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    ap.add_argument("--alle", action="store_true", help="auch schon gespeicherte Stichtage neu lesen")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    kandidaten = [dict(r) for r in store._conn.execute(  # noqa: SLF001 — dieselbe Auswahl wie die Marke
        "SELECT t.kvonr, t.template_number, t.title, a.document_id, a.label, a.url "
        "  FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr "
        " WHERE t.title LIKE '%Budgetbericht%' AND a.url IS NOT NULL ORDER BY t.kvonr")]
    schon = {(z["as_of"], z["sub_budget_no"]) for z in store.budgetbericht_stichtage()}
    print(f"{len(kandidaten)} Anlage(n) zu Budgetberichten im Bestand, {len(schon)} Berichte gespeichert.")

    gespeichert = verworfen = abrufe = 0
    for r in kandidaten:
        as_of = bb.stichtag(r["label"] or "", r["title"] or "")
        if abrufe:
            time.sleep(args.pause)
        abrufe += 1
        try:
            seiten, text = bb.woerter_aus_pdf(_laden(r["url"]))
        except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
            print(f"  {r['template_number']}: nicht ladbar ({exc})")
            verworfen += 1
            continue
        if "I10." not in text:
            continue   # Berichte vor 2018/2019: noch ohne Tabelle je Maßnahme
        try:
            b = bb.lies_seiten(seiten, text, as_of)
        except bb.BerichtFehler as fehler:
            print(f"  {r['template_number']}: {fehler} — nicht gespeichert")
            verworfen += 1
            continue
        if b.sub_budget_no not in TEILHAUSHALTE:
            continue
        if not b.as_of or not b.budget_year:
            print(f"  {r['template_number']}: kein Stichtag — nicht gespeichert")
            verworfen += 1
            continue
        if (b.as_of, b.sub_budget_no) in schon and not args.alle:
            continue
        if not b.pruefen():
            print(f"  {r['template_number']} ({b.as_of}, THH {b.sub_budget_no}): "
                  f"{'; '.join(b.hinweise)} — nicht gespeichert")
            verworfen += 1
            continue
        summe_a = b.summe.get("A", (None, None))
        print(f"  {b.as_of} THH {b.sub_budget_no}: {len(b.massnahmen)} Maßnahmen, Ansatz "
              f"{summe_a[0] or 0:,.0f} €, Prognose {summe_a[1] or 0:,.0f} € · {r['template_number']}"
              + (f" · gerundet: {b.gerundet[0]}" if b.gerundet else ""), flush=True)
        schon.add((b.as_of, b.sub_budget_no))
        if args.trocken:
            continue
        mit_text = sum(1 for m in b.massnahmen if m.note)
        store.save_budgetbericht(
            b.as_of, b.sub_budget_no, b.budget_year, [asdict(m) for m in b.massnahmen],
            template_number=r["template_number"], herkunft=herkunft.Herkunft(
                kind="ris", probe=[bb.PROBE_BUDGETBERICHT],
                document_id=r["document_id"], label=r["label"], url=r["url"],
                citation=f"Teilfinanzrechnung, Investitionen je Maßnahme ({b.form})",
                probe_result=(f"{len(b.massnahmen)} Maßnahmen = Summenzeile, {mit_text} mit Erläuterung"
                              + (f"; Summenzeile gerundet ({b.gerundet[0]})" if b.gerundet else "")),
                as_of=f"Stichtag {b.as_of[8:10]}.{b.as_of[5:7]}.{b.as_of[:4]}"))
        gespeichert += 1
    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{gespeichert} Berichte gespeichert, {verworfen} verworfen.")
    return 1 if verworfen and not gespeichert and not schon else 0


if __name__ == "__main__":
    raise SystemExit(main())
