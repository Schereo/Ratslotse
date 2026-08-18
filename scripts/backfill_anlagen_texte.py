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

#: Mindestanteil echter Buchstaben. Darunter ist die Zeichenzuordnung der PDF
#: kaputt, und was herauskommt, ist kein Text.
#:
#: DER FALL, DER DIESE SCHWELLE ERZWUNGEN HAT: Der Schlussbericht des
#: Rechnungsprüfungsamts zum Jahresabschluss 2024 (Dokument 295296) liefert
#: 460.084 Zeichen — und **keinen einzigen Buchstaben**. Seine Schrift bringt
#: keine ToUnicode-Tabelle mit, deshalb extrahiert pypdf die Glyph-Nummern
#: („/1 /2 /3 …") und Kästchen. Ohne diese Prüfung stünden 460 KB Rauschen in
#: der Datenbank, im Volltextindex und damit in den Treffern der KI-Frage —
#: und der Bericht sähe aus, als sei er gelesen worden.
#:
#: 0,05 IST GEMESSEN, NICHT GEGRIFFEN: Über die 558 Anlagen mit Volltext liegt
#: der Median bei 0,69, das erste Perzentil bei 0,32. Unterhalb von 0,12 liegen
#: genau zwei Dokumente — die beiden kaputten. Die Schwelle hat also nach oben
#: den doppelten Abstand zum nächsten echten Dokument.
MIN_BUCHSTABEN = 0.05

#: Obergrenze je Anlage. Kappt Extrem-PDFs, damit ein einzelnes Gutachten die
#: Datenbank nicht aufbläht.
#:
#: WARUM 800.000 UND NICHT MEHR 400.000. Bei 400.000 endeten die
#: Jahresabschlüsse mitten im Dokument — und zwar ausgerechnet vor Abschnitt 8
#: („Anlagen zum Anhang" mit Anlagen-, Forderungs-, Schulden- und
#: Rückstellungsübersicht). Für 2022 ließ sich das nachweisen: Die Abschnitte
#: 8.3 und 8.4 stehen bei 70 % des Textes, der Schnitt lag bei 56 %.
#:
#: Der Preis ist klein, weil die Grenze fast niemanden trifft: Von 6.366
#: Anlagen mit Volltext standen **23** exakt an ihr, davon acht die
#: Jahresabschlüsse (gemessen 18.08.2026). Die längste ist der Abschluss 2022
#: mit 709.076 Zeichen; 800.000 nimmt sie vollständig auf und lässt Luft für
#: einen dickeren Jahrgang, ohne dass jemand die Zahl wieder anfassen muss.
#: In einer 263-MB-Datenbank kostet das rund 7 MB.
MAX_TEXT = 800_000

#: Grenzen, die einmal galten. Eine Anlage, deren gespeicherter Text **exakt**
#: so lang ist, wurde damals gekappt — sonst wäre die Länge krumm.
#:
#: Der Backfill holt normalerweise nur Anlagen mit Status ``listed``/``failed``;
#: eine gekappte steht auf ``ok`` und käme nie wieder an die Reihe. ``--gekappte``
#: nimmt genau diese dazu. Wer die Grenze künftig erneut anhebt, trägt den alten
#: Wert hier nach — dann findet derselbe Schalter auch jene Jahrgänge wieder.
FRUEHERE_GRENZEN = (400_000,)


def buchstabenanteil(text: str) -> float:
    """Wie viel des Textes wirklich aus Buchstaben besteht (0 bis 1)."""
    return sum(ch.isalpha() for ch in text) / len(text) if text else 0.0


def finanz_muster() -> list[str]:
    """Die Label-Muster der Finanzschichten — aus der Registry, nicht doppelt.

    Der Haushalts-Bereich liest sieben Schichten aus Anlagen (Jahresabschluss,
    Teilhaushalte, Stellenplan, …). Wer nur die braucht, muss nicht 5.500 PDFs
    laden: Auf der Dev-VM standen deshalb drei Seiten leer, obwohl ihre Parser
    längst liefen. Die Muster stehen in ``finanzquellen`` — hier nur geholt,
    damit sie nicht an zwei Stellen gepflegt werden müssen.
    """
    from council import finanzquellen as fq

    muster: list[str] = []
    for key in fq.REIHENFOLGE:
        erkennung = getattr(fq.QUELLEN[key], "erkennung", None)
        if erkennung is None:
            continue
        muster.extend(getattr(erkennung, "label_muster", None) or ())
    return sorted(set(muster))


def process(db_path: Path, limit: int | None, workers: int, retry_failed: bool,
            nur_finanz: bool = False, gekappte: bool = False) -> dict:
    store = CouncilStore(db_path)
    try:
        status_filter = "('listed','failed')" if retry_failed else "('listed')"
        wo, werte = "", []
        if nur_finanz:
            muster = finanz_muster()
            wo = " AND (" + " OR ".join("label LIKE ?" for _ in muster) + ")"
            werte = muster
            print(f"Nur Finanz-Anlagen: {', '.join(muster)}", flush=True)
        # Der Status-Filter steht in Klammern neben der Kappungs-Bedingung, nicht
        # davor: `A AND B OR C` läse sich sonst als `(A AND B) OR C` — der
        # `--nur-finanz`-Filter fiele für die gekappten Anlagen weg, und ein
        # Lauf, der 293 Dokumente meinte, holte plötzlich alle.
        bedingung = f"status IN {status_filter}"
        if gekappte:
            laengen = ", ".join(str(int(g)) for g in FRUEHERE_GRENZEN)
            bedingung = (f"({bedingung} OR (status = 'ok' "
                         f"AND LENGTH(raw_text) IN ({laengen})))")
            print(f"Auch früher gekappte Anlagen (Textlänge exakt {laengen})", flush=True)
        rows = store._conn.execute(
            f"SELECT document_id, url FROM council_anlagen "
            f"WHERE {bedingung} AND url IS NOT NULL{wo} "
            f"ORDER BY document_id DESC" + (f" LIMIT {int(limit)}" if limit else ""),
            werte,
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
                # Kaputte Zeichenzuordnung zählt wie „kein Text" — sonst gilt
                # ein Dokument als gelesen, das niemand lesen kann.
                if text and buchstabenanteil(text) < MIN_BUCHSTABEN:
                    text = ""
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
    ap.add_argument("--nur-finanz", action="store_true",
                    help="nur Anlagen, aus denen der Haushalts-Bereich liest "
                         "(Label-Muster aus council/finanzquellen.py)")
    ap.add_argument("--gekappte", action="store_true",
                    help="auch Anlagen erneut holen, die an einer früheren "
                         "MAX_TEXT-Grenze abgeschnitten wurden (FRUEHERE_GRENZEN)")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    stats = process(Path(args.db), args.limit, args.workers, args.retry_failed,
                    nur_finanz=args.nur_finanz, gekappte=args.gekappte)
    print(f"Anlagen-Texte: {stats['geladen']} mit Text, {stats['ohne_text']} ohne, "
          f"{stats['fehler']} Fehler von {stats['gesamt']}", flush=True)
    return stats


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backfill_anlagen_texte", main)
