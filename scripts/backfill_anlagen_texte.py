#!/usr/bin/env python3
"""Anlagen-Volltexte nachladen (Task 33) — das Fundament für Deep Research.

Der Anlagen-Scan erfasst alle Anlagen als Zeilen, lädt aber nur Antrags-PDFs
als Volltext: von 6.354 Anlagen tragen 671 Text, 5.496 stehen auf 'listed'.
Dieses Skript zieht die restlichen PDFs (Gutachten, Konzepte, Stellungnahmen)
und extrahiert den Text — reine Netz+pypdf-Arbeit, kein LLM.

Status-Vokabular wie gehabt: 'ok' = Text da, 'empty' = PDF ohne extrahierbaren
Text (Scans/Planbilder), 'failed' = Download/Parse-Fehler (mit --retry-failed
nachholbar). Idempotent: nur 'listed' (bzw. 'failed') wird angefasst.

    python scripts/backfill_anlagen_texte.py --limit 10   # Stichprobe
    python scripts/backfill_anlagen_texte.py              # alles (~5.500, Stunden)
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402
from council.vorlagen import _pdf_text  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
MIN_TEXT = 200          # darunter gilt das PDF als Scan/Bild ('empty')
MAX_TEXT = 400_000      # Extrem-PDFs kappen (ein Gutachten reicht auch gekürzt)


def process(db_path: Path, limit: int | None, workers: int, retry_failed: bool) -> dict:
    store = CouncilStore(db_path)
    try:
        status_filter = "('listed','failed')" if retry_failed else "('listed')"
        rows = store._conn.execute(
            f"SELECT document_id, url FROM council_anlagen "
            f"WHERE status IN {status_filter} AND url IS NOT NULL "
            f"ORDER BY document_id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()
        ok = leer = fehler = 0

        def laden(document_id: int, url: str):
            return document_id, _pdf_text(url)

        # Netz+Parse in Workern, DB-Schreiben im Main-Thread (SQLite-Konvention).
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(laden, r["document_id"], r["url"]): r["document_id"]
                    for r in rows}
            for fut in as_completed(futs):
                did = futs[fut]
                try:
                    _, (text, n_pages) = fut.result()
                except Exception as exc:  # noqa: BLE001 — eine kaputte Anlage stoppt nichts
                    fehler += 1
                    with store._conn:
                        store._conn.execute(
                            "UPDATE council_anlagen SET status='failed', fetched_at=datetime('now') "
                            "WHERE document_id = ?", (did,))
                    print(f"  [{did}] FEHLER {exc}", flush=True)
                    continue
                text = (text or "").strip()[:MAX_TEXT]
                with store._conn:
                    if len(text) >= MIN_TEXT:
                        store._conn.execute(
                            "UPDATE council_anlagen SET raw_text=?, n_pages=?, status='ok', "
                            "fetched_at=datetime('now') WHERE document_id = ?",
                            (text, n_pages, did))
                        ok += 1
                    else:
                        store._conn.execute(
                            "UPDATE council_anlagen SET raw_text='', n_pages=?, status='empty', "
                            "fetched_at=datetime('now') WHERE document_id = ?", (n_pages, did))
                        leer += 1
                if (ok + leer + fehler) % 100 == 0:
                    print(f"  {ok + leer + fehler}/{len(rows)} (Text {ok}, leer {leer}, "
                          f"Fehler {fehler})", flush=True)
        return {"geladen": ok, "ohne_text": leer, "fehler": fehler, "gesamt": len(rows)}
    finally:
        store.close()


def main() -> dict:
    ap = argparse.ArgumentParser(description="Anlagen-Volltexte nachladen (Netz + pypdf)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    stats = process(Path(args.db), args.limit, args.workers, args.retry_failed)
    print(f"Anlagen-Texte: {stats['geladen']} mit Text, {stats['ohne_text']} ohne, "
          f"{stats['fehler']} Fehler von {stats['gesamt']}", flush=True)
    return stats


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backfill_anlagen_texte", main)
