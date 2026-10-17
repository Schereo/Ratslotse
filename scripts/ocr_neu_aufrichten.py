#!/usr/bin/env python3
"""OCR-Texte des Bestands mit aufgerichteten Seiten neu lesen — einmalig.

Bis 17.10.2026 gingen seitlich liegende Scanseiten so ans Sehmodell, wie sie
gescannt waren (``council/ocr.py``, Abschnitt „Lage"). In zweispaltigen
Tabellen verrutschten dabei die Zeilen: Beim AWB-Wirtschaftsplan 2020 standen
alle Beträge eines Blocks eine Beschriftung zu tief, und keine Summenprobe
merkt das. Dieses Skript liest die betroffenen Dokumente noch einmal.

Zwei Phasen, damit nichts ungesehen in den Bestand kommt::

    # 1. Lesen — schreibt NICHTS in die Datenbank, nur Dateien nach DIR:
    #    <id>.txt (neu), <id>.alt.txt (bisher), <id>.json (Kennzahlen)
    python scripts/ocr_neu_aufrichten.py lesen --ausgabe DIR

    # 2. Nach dem Vergleich einspielen. Übernommen wird nur, wo der Text im
    #    Bestand noch derselbe ist wie beim Lesen; <id>.alt.txt bleibt als
    #    Sicherung liegen.
    python scripts/ocr_neu_aufrichten.py einspielen DIR

Neu gelesen wird nur, was mindestens eine seitliche Seite hat — das prüft
``ocr.seitliche_seiten`` vorher an den Pixeln, ohne Modellaufruf. Ein
Dokument ohne seitliche Seite würde nur ein zweites Mal bezahlt.

Danach die Ingests der betroffenen Schichten laufen lassen; die Ingest-
Skripte lesen den Bestand ohnehin neu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import ocr  # noqa: E402
from council.kontaktdaten import entfernen  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.backfill_anlagen_ocr import MAX_SEITEN, _hole  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Dokumente, die NICHT neu gelesen werden — mit Grund.
AUSGENOMMEN = {
    # Konzernabschluss 2013: am 16.10.2026 von Hand aufgerichtet gelesen und
    # Zelle für Zelle am Bild geprüft. Sein Text ist Textebene (S. 1–18) plus
    # OCR; ein Neulesen ersetzte die Textebene durch eine zweite OCR.
    188333: "von Hand aufgerichtet und geprüft (16.10.2026)",
}

#: Abstand zwischen zwei Downloads beim Bürgerinfo.
PAUSE_S = 1.5


def kandidaten(store: CouncilStore, document_id: int | None = None) -> list[dict]:
    """Alle Anlagen mit OCR-Text — außer den ausgenommenen."""
    sql = ("SELECT document_id, label, url, n_pages, raw_text FROM council_attachments "
           "WHERE ocr_model IS NOT NULL AND url IS NOT NULL")
    werte: list = []
    if document_id is not None:
        sql += " AND document_id = ?"
        werte.append(document_id)
    rows = [dict(r) for r in store._conn.execute(sql + " ORDER BY document_id", werte)]  # noqa: SLF001
    return [r for r in rows if r["document_id"] not in AUSGENOMMEN]


def lesen(db: Path, ausgabe: Path, document_id: int | None) -> dict:
    ausgabe.mkdir(parents=True, exist_ok=True)
    store = CouncilStore(db)
    try:
        rows = kandidaten(store, document_id)
    finally:
        store.close()
    gelesen = ohne = fehler = seiten = gedreht = 0
    for r in rows:
        did = r["document_id"]
        if (ausgabe / f"{did}.json").exists():
            print(f"  [{did}] schon gelesen — übersprungen", flush=True)
            continue
        try:
            daten = _hole(r["url"])
            time.sleep(PAUSE_S)
            seitlich = ocr.seitliche_seiten(daten, max_seiten=MAX_SEITEN)
            if not seitlich:
                ohne += 1
                print(f"  [{did}] keine seitliche Seite — bleibt", flush=True)
                continue
            lesung = ocr.lies_pdf(daten, max_seiten=MAX_SEITEN)
        except Exception as exc:  # noqa: BLE001 — ein Dokument hält den Lauf nicht auf
            fehler += 1
            print(f"  [{did}] FEHLER {exc}", flush=True)
            continue
        if lesung.gelesen == 0 or not lesung.vollstaendig:
            fehler += 1
            print(f"  [{did}] nur {lesung.gelesen}/{lesung.seiten} Seiten gelesen — "
                  f"nicht abgelegt", flush=True)
            continue
        (ausgabe / f"{did}.txt").write_text(entfernen(lesung.text))
        (ausgabe / f"{did}.alt.txt").write_text(r["raw_text"] or "")
        (ausgabe / f"{did}.json").write_text(json.dumps({
            "document_id": did, "label": r["label"], "seiten": lesung.seiten,
            "seitlich": seitlich, "gedreht": lesung.gedreht, "modell": lesung.modell}))
        gelesen += 1
        seiten += lesung.seiten
        gedreht += lesung.gedreht
        print(f"  [{did}] {lesung.seiten} Seiten, {len(seitlich)} seitlich, "
              f"{lesung.gedreht} aufgerichtet — {(r['label'] or '')[:50]}", flush=True)
    return {"neu_gelesen": gelesen, "ohne_seitliche": ohne, "fehler": fehler,
            "seiten": seiten, "aufgerichtet": gedreht, "kandidaten": len(rows)}


def einspielen(db: Path, ausgabe: Path) -> dict:
    store = CouncilStore(db)
    uebernommen = veraendert = 0
    try:
        for meta_pfad in sorted(ausgabe.glob("*.json")):
            meta = json.loads(meta_pfad.read_text())
            did = meta["document_id"]
            alt = (ausgabe / f"{did}.alt.txt").read_text()
            row = store._conn.execute(  # noqa: SLF001
                "SELECT raw_text FROM council_attachments WHERE document_id = ?",
                (did,)).fetchone()
            if row is None or (row["raw_text"] or "") != alt:
                veraendert += 1
                print(f"  [{did}] Text im Bestand hat sich seit dem Lesen geändert — "
                      f"nicht übernommen", flush=True)
                continue
            with store._conn:  # noqa: SLF001
                store._conn.execute(  # noqa: SLF001
                    "UPDATE council_attachments SET raw_text = ?, n_pages = ?, "
                    "ocr_model = ? WHERE document_id = ?",
                    ((ausgabe / f"{did}.txt").read_text(), meta["seiten"],
                     meta["modell"], did))
            uebernommen += 1
            print(f"  [{did}] übernommen ({meta['gedreht']} Seiten aufgerichtet)", flush=True)
    finally:
        store.close()
    return {"uebernommen": uebernommen, "geaendert_uebersprungen": veraendert}


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["lesen", "einspielen"])
    ap.add_argument("verzeichnis", nargs="?", type=Path)
    ap.add_argument("--ausgabe", type=Path)
    ap.add_argument("--document-id", type=int)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    args = ap.parse_args()
    if args.phase == "lesen":
        if not args.ausgabe:
            ap.error("lesen braucht --ausgabe DIR")
        ergebnis = lesen(args.db, args.ausgabe, args.document_id)
    else:
        if not args.verzeichnis:
            ap.error("einspielen braucht das Verzeichnis aus der Lese-Phase")
        ergebnis = einspielen(args.db, args.verzeichnis)
    print(f"Fertig: {ergebnis}", flush=True)
    return ergebnis


if __name__ == "__main__":
    main()
