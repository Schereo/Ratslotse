#!/usr/bin/env python3
"""Anlagen-Volltexte nachladen (Task 33) — das Fundament für Deep Research.

Der Anlagen-Scan erfasst alle Anlagen als Zeilen, lädt aber nur Antrags-PDFs
als Volltext: von 6.354 Anlagen tragen 671 Text, 5.496 stehen auf 'listed'.
Dieses Skript zieht die restlichen PDFs (Gutachten, Konzepte, Stellungnahmen)
und extrahiert den Text — reine Netz- und PDF-Arbeit, kein LLM (PyMuPDF;
Haushalts-Anlagen pypdf, s. ``council/anlagentext.py``).

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
from council.anlagentext import (MAX_TEXT, MIN_BUCHSTABEN, MIN_TEXT,  # noqa: E402,F401
                                 beurteilen, buchstabenanteil, extraktor_fuer,
                                 finanz_muster)
from council.kontaktdaten import entfernen  # noqa: E402
from council.vorlagen import _pdf_text, _session  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
#: Grenzen, die einmal galten. Eine Anlage, deren gespeicherter Text **exakt**
#: so lang ist, wurde damals gekappt — sonst wäre die Länge krumm.
#:
#: Der Backfill holt normalerweise nur Anlagen mit Status ``listed``/``failed``;
#: eine gekappte steht auf ``ok`` und käme nie wieder an die Reihe. ``--gekappte``
#: nimmt genau diese dazu. Wer die Grenze künftig erneut anhebt, trägt den alten
#: Wert hier nach — dann findet derselbe Schalter auch jene Jahrgänge wieder.
FRUEHERE_GRENZEN = (400_000,)


#: Ab wie vielen Zeichen eine Seite überhaupt als „beschrieben" gilt — kürzere
#: Seiten (Deckblatt, Trennblatt) tragen zu wenig, um ihren Buchstabenanteil
#: zu beurteilen.
MIN_SEITENTEXT = 200


def seite_braucht_ocr(text: str) -> bool:
    """Ist DIESE Seite Glyphen-Salat, obwohl das Dokument als Ganzes lesbar ist?

    Der Stellenplan 2026 (Anlage 297432) trägt Teil A mit Zeichenzuordnung und
    Teil B ohne: Seiten 5–9 liefern 6.000 Zeichen wie „/0 /1 /2 /3 /i255" bei
    ein Prozent Buchstaben. Das ganze Dokument liegt bei 20 % Buchstaben und
    fällt damit durch kein Glyphen-Netz — die Buchstaben-Schwelle ist eine
    Dokument-Schwelle. Der Teil B fehlte deshalb seit 10/2025."""
    return len(text) >= MIN_SEITENTEXT and buchstabenanteil(text) < MIN_BUCHSTABEN


def hat_glyphstrecke(text: str, fenster: int = 2000) -> bool:
    """Vorprüfung am gespeicherten Text, ohne Download: Trägt er einen langen
    Abschnitt, der aussieht wie eine Glyphenseite? Die Seitengrenzen sind im
    gespeicherten Text verloren, deshalb Fenster fester Länge."""
    for i in range(0, max(1, len(text) - fenster + 1), fenster):
        if seite_braucht_ocr(text[i:i + fenster]):
            return True
    return False


def glyphseiten_reparieren(store: CouncilStore, wo: str, werte: list,
                           document_id: int | None = None,
                           limit: int | None = None) -> dict:
    """Anlagen mit lesbarem Text UND einzelnen Glyphenseiten: die Glyphenseiten
    per OCR lesen und den Text seitenrichtig neu zusammensetzen.

    Läuft nur über ``status='ok'`` — genau die Menge, die weder dieser Lauf
    (er holt ``listed``/``failed``) noch die OCR (sie liest ``empty``) je
    wieder anfasst. Gerechnet wird zweistufig: erst die Vorprüfung am
    gespeicherten Text (kostet nichts), dann seitenweise am PDF; nur die
    Glyphenseiten gehen ans Modell (``council.ocr.lies_seite``)."""
    import io

    import pypdf

    from council import ocr

    bedingung = "status = 'ok' AND raw_text != '' AND url IS NOT NULL"
    params: list = list(werte)
    if document_id is not None:
        bedingung = "document_id = ? AND url IS NOT NULL"
        params = [document_id]
        wo = ""
    rows = store._conn.execute(
        f"SELECT document_id, url, raw_text FROM council_attachments WHERE {bedingung}{wo} "
        f"ORDER BY document_id DESC" + (f" LIMIT {int(limit)}" if limit else ""), params).fetchall()
    geprueft = repariert = seiten = fehler = 0
    for r in rows:
        if document_id is None and not hat_glyphstrecke(r["raw_text"] or ""):
            continue
        geprueft += 1
        try:
            antwort = _session.get(r["url"], timeout=90)
            antwort.raise_for_status()
            reader = pypdf.PdfReader(io.BytesIO(antwort.content))
            teile: list[str] = []
            n_ocr = 0
            for page in reader.pages:
                t = page.extract_text() or ""
                if seite_braucht_ocr(t):
                    t = ocr.lies_seite(ocr.seite_als_bild(page))
                    n_ocr += 1
                teile.append(t)
        except Exception as exc:  # noqa: BLE001 — eine kaputte Anlage stoppt nichts
            fehler += 1
            print(f"  [{r['document_id']}] Glyphseiten: FEHLER {exc}", flush=True)
            continue
        if not n_ocr:
            continue
        text = entfernen("\n".join(teile).strip())[:MAX_TEXT]
        with store._conn:
            store._conn.execute(
                "UPDATE council_attachments SET raw_text=?, n_pages=?, status='ok', "
                "fetched_at=datetime('now') WHERE document_id = ?",
                (text, len(reader.pages), r["document_id"]))
        repariert += 1
        seiten += n_ocr
        print(f"  [{r['document_id']}] {n_ocr} von {len(reader.pages)} Seiten per OCR ersetzt "
              f"({len(text)} Zeichen)", flush=True)
    print(f"Glyphseiten: {geprueft} Anlage(n) geprüft, {repariert} repariert "
          f"({seiten} Seiten per OCR), {fehler} Fehler", flush=True)
    return {"geprueft": geprueft, "repariert": repariert, "seiten": seiten, "fehler": fehler}


def process(db_path: Path, limit: int | None, workers: int, retry_failed: bool,
            nur_finanz: bool = False, gekappte: bool = False,
            glyphen: bool = False) -> dict:
    store = CouncilStore(db_path)
    try:
        status_filter = "('listed','failed')" if retry_failed else "('listed')"
        wo, werte = "", []
        if nur_finanz:
            from council import finanzquellen as fq
            filter_sql, werte = fq.finanz_anlagen_where()
            wo = " AND " + filter_sql
            print(f"Nur Finanz-Anlagen: {', '.join(finanz_muster())}"
                  + (" + Vorlagentitel" if "council_templates" in filter_sql else ""), flush=True)
        # Anlagen, die VOR der Buchstaben-Schwelle geladen wurden, stehen mit
        # ihrem Glyphen-Rauschen auf `ok` — und `ok` fasst kein Lauf mehr an:
        # nicht dieser (er holt `listed`/`failed`), nicht die OCR (sie liest
        # `empty`). Genau so lag der Schlussbericht 2024 (Dokument 295296) vom
        # 18.08. bis zum 02.09.2026 mit 460.084 Zeichen und keinem Buchstaben
        # da, während der Renderer längst installiert war. Der Schalter zieht
        # die Schwelle nachträglich über den Bestand und stellt solche Anlagen
        # dorthin, wo die OCR sie findet. Gerechnet wird in Python, nicht in
        # SQL (SQLite kennt kein isalpha) — mit `--nur-finanz` sind das rund
        # 300 Texte, ohne den Filter der ganze Bestand.
        glyphen_geleert = 0
        if glyphen:
            for r in store._conn.execute(
                    "SELECT document_id, raw_text FROM council_attachments "
                    f"WHERE status = 'ok' AND raw_text != ''{wo}", werte).fetchall():
                if buchstabenanteil(r["raw_text"]) >= MIN_BUCHSTABEN:
                    continue
                with store._conn:
                    store._conn.execute(
                        "UPDATE council_attachments SET raw_text='', status='empty', "
                        "fetched_at=datetime('now') WHERE document_id = ?",
                        (r["document_id"],))
                glyphen_geleert += 1
                print(f"  [{r['document_id']}] Glyphen statt Buchstaben — "
                      f"auf 'empty' gesetzt, die OCR liest es", flush=True)
            print(f"Glyphen-Anlagen auf 'empty' gesetzt: {glyphen_geleert}", flush=True)
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
            f"SELECT document_id, url, label, (SELECT t.title FROM council_templates t "
            f"WHERE t.kvonr = council_attachments.kvonr LIMIT 1) AS vorlagentitel "
            f"FROM council_attachments "
            f"WHERE {bedingung} AND url IS NOT NULL{wo} "
            f"ORDER BY document_id DESC" + (f" LIMIT {int(limit)}" if limit else ""),
            werte,
        ).fetchall()
        ok = leer = fehler = 0

        def laden(document_id: int, url: str, extraktor: str):
            return document_id, _pdf_text(url, extraktor)

        # Netz+Parse in Workern, DB-Schreiben im Main-Thread (SQLite-Konvention).
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Haushalts-Anlagen bleiben bei pypdf: Ihre Parser lesen den
            # gespeicherten Text und sind darauf abgestimmt (anlagentext.py).
            futs = {pool.submit(laden, r["document_id"], r["url"],
                                extraktor_fuer(r["label"], r["vorlagentitel"])): r["document_id"]
                    for r in rows}
            for fut in as_completed(futs):
                did = futs[fut]
                try:
                    _, (text, n_pages) = fut.result()
                except Exception as exc:  # noqa: BLE001 — eine kaputte Anlage stoppt nichts
                    fehler += 1
                    with store._conn:
                        store._conn.execute(
                            "UPDATE council_attachments SET status='failed', fetched_at=datetime('now') "
                            "WHERE document_id = ?", (did,))
                    print(f"  [{did}] FEHLER {exc}", flush=True)
                    continue
                # Kontonummern und Anschriften gar nicht erst speichern.
                # Das ist KEIN OCR-Thema: 606 Anlagen des Bestands tragen
                # Kontaktdaten aus ihrer eigenen Textebene.
                # Kaputte Zeichenzuordnung zählt wie „kein Text" — sonst gilt
                # ein Dokument als gelesen, das niemand lesen kann. Dieselbe
                # Regel benutzt der MCP-Server (council/anlagentext.py).
                text = beurteilen(text)
                with store._conn:
                    if text:
                        store._conn.execute(
                            "UPDATE council_attachments SET raw_text=?, n_pages=?, status='ok', "
                            "fetched_at=datetime('now') WHERE document_id = ?",
                            (text, n_pages, did))
                        ok += 1
                    else:
                        store._conn.execute(
                            "UPDATE council_attachments SET raw_text='', n_pages=?, status='empty', "
                            "fetched_at=datetime('now') WHERE document_id = ?", (n_pages, did))
                        leer += 1
                if (ok + leer + fehler) % 100 == 0:
                    print(f"  {ok + leer + fehler}/{len(rows)} (Text {ok}, leer {leer}, "
                          f"Fehler {fehler})", flush=True)
        return {"geladen": ok, "ohne_text": leer, "fehler": fehler, "gesamt": len(rows),
                "glyphen_geleert": glyphen_geleert}
    finally:
        store.close()


def main() -> dict:
    ap = argparse.ArgumentParser(description="Anlagen-Volltexte nachladen (Netz + PDF-Text)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--nur-finanz", action="store_true",
                    help="nur Anlagen, aus denen der Haushalts-Bereich liest "
                         "(Label-Muster aus council/finanzquellen.py)")
    ap.add_argument("--gekappte", action="store_true",
                    help="auch Anlagen erneut holen, die an einer früheren "
                         "MAX_TEXT-Grenze abgeschnitten wurden (FRUEHERE_GRENZEN)")
    ap.add_argument("--glyphen", action="store_true",
                    help="Anlagen, die mit kaputter Zeichenzuordnung auf 'ok' stehen "
                         "(Buchstabenanteil unter MIN_BUCHSTABEN), auf 'empty' setzen — "
                         "damit die OCR sie liest")
    ap.add_argument("--glyphseiten", action="store_true",
                    help="Anlagen auf 'ok', die EINZELNE Seiten ohne Zeichenzuordnung "
                         "tragen (Stellenplan 2026, Teil B): diese Seiten per OCR "
                         "lesen und den Text neu zusammensetzen")
    ap.add_argument("--document-id", type=int, default=None,
                    help="mit --glyphseiten: genau diese Anlage reparieren")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    if args.glyphseiten and args.document_id is not None:
        store = CouncilStore(Path(args.db))
        try:
            return glyphseiten_reparieren(store, "", [], document_id=args.document_id)
        finally:
            store.close()
    stats = process(Path(args.db), args.limit, args.workers, args.retry_failed,
                    nur_finanz=args.nur_finanz, gekappte=args.gekappte,
                    glyphen=args.glyphen)
    print(f"Anlagen-Texte: {stats['geladen']} mit Text, {stats['ohne_text']} ohne, "
          f"{stats['fehler']} Fehler von {stats['gesamt']}, "
          f"{stats['glyphen_geleert']} Glyphen-Anlagen an die OCR", flush=True)
    if args.glyphseiten:
        store = CouncilStore(Path(args.db))
        try:
            wo, werte = "", []
            if args.nur_finanz:
                from council import finanzquellen as fq
                filter_sql, werte = fq.finanz_anlagen_where()
                wo = " AND " + filter_sql
            stats["glyphseiten"] = glyphseiten_reparieren(store, wo, werte, limit=args.limit)
        finally:
            store.close()
    return stats


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backfill_anlagen_texte", main)
