"""Planzeichnungen aus Bauleitplan-Anlagen als Bilder rendern (P1, 09.08.2026).

Bebauungsplan-Beschlüsse leben vom Bild: Die Planzeichnung hängt als PDF an
der Vorlage, war aber nur ein Download unter „Anlagen". Dieses Skript rendert
die erste Seite der Plan-Anlagen als JPEG (Vollbild max. 1600 px + Thumbnail
480 px) nach ``data/plaene/<document_id>[.thumb].jpg``; die Beschluss-Seite
zeigt sie über ``GET /api/council/plan-bild/{document_id}``.

Braucht **pymupdf** — bewusst NICHT in requirements.txt (Ops-Dependency wie
fastembed, damit Deploy + Web-Service unberührt bleiben):

    .venv/bin/pip install pymupdf
    .venv/bin/python scripts/render_plaene.py [--db data/council.sqlite] [--limit N]

Die PDFs tragen eine AES-Hülle (Owner-Passwort gegen Bearbeiten/Drucken) —
kein Zugriffsschutz, pymupdf öffnet sie ohne Passwort. Idempotent über die
Spalte ``council_anlagen.bild`` (0 = offen, 1 = gerendert, -1 = fehlgeschlagen).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402

# Label-Kern eng halten: diese Anlagen sind semantisch Karten/Zeichnungen —
# breitere Muster („Plan…") fingen auch reine Textseiten (Planversand etc.).
PLAN_LABEL_RE = re.compile(
    r"planzeichnung|plandarstellung|lageplan|leitplan|freiflächenplan|bestandsplan|aufteilungsplan",
    re.IGNORECASE)

VOLL_PX = 1600
THUMB_PX = 480


def render_pdf(pdf_bytes: bytes, out_voll: Path, out_thumb: Path) -> None:
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[0]
        for ziel, px in ((out_voll, VOLL_PX), (out_thumb, THUMB_PX)):
            zoom = px / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
            ziel.write_bytes(pix.tobytes("jpg", jpg_quality=85))


def main(db: str | None = None, out_dir: str = "data/plaene", limit: int = 0,
         delay: float = 1.0) -> dict:
    store = CouncilStore(db or "data/council.sqlite")
    conn = store._conn  # noqa: SLF001 — Ops-Skript
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = [r for r in conn.execute(
        "SELECT document_id, label, url FROM council_anlagen "
        "WHERE bild = 0 AND url IS NOT NULL").fetchall()
        if PLAN_LABEL_RE.search(r["label"] or "")]
    if limit:
        rows = rows[:limit]

    zaehler = {"kandidaten": len(rows), "gerendert": 0, "fehlgeschlagen": 0}
    for r in rows:
        did = r["document_id"]
        try:
            resp = requests.get(r["url"], timeout=60)
            resp.raise_for_status()
            render_pdf(resp.content, out / f"{did}.jpg", out / f"{did}.thumb.jpg")
            status = 1
            zaehler["gerendert"] += 1
        except Exception as e:  # noqa: BLE001 — ein kaputtes PDF kippt nicht den Lauf
            print(f"  FEHLER {did} ({r['label']!r}): {e}")
            status = -1
            zaehler["fehlgeschlagen"] += 1
        with conn:
            conn.execute("UPDATE council_anlagen SET bild = ? WHERE document_id = ?",
                         (status, did))
        time.sleep(delay)
    return zaehler


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default="data/plaene")
    ap.add_argument("--limit", type=int, default=0, help="0 = alle")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()
    raise SystemExit(run_guarded(
        "render_plaene",
        lambda: main(db=args.db, out_dir=args.out, limit=args.limit, delay=args.delay)))
