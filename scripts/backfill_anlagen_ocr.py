#!/usr/bin/env python3
"""Gescannte Anlagen lesen lassen — der Nachbar von backfill_anlagen_texte.py.

Jenes Skript holt Text aus der Textebene des PDF. Was keine hat, landet auf
``status='empty'``; das sind derzeit 235 Anlagen. Dieses Skript nimmt genau
die und schickt jede Seite als Bild an ein Sehmodell (``council/ocr.py``).

    # Erst schauen, was drankäme — kostet nichts, ruft kein Modell auf
    python scripts/backfill_anlagen_ocr.py --nur-finanz --trocken

    # Die Finanzdokumente lesen (Wirtschaftspläne, Jahresabschlüsse, …)
    python scripts/backfill_anlagen_ocr.py --nur-finanz

    # Ein einzelnes Dokument, zwei Seiten, zum Hinschauen
    python scripts/backfill_anlagen_ocr.py --document-id 193959 --max-seiten 2

DER GELESENE TEXT IST GANZ NORMALER ANLAGENTEXT. Der Lauf setzt
``status='ok'`` und vermerkt in ``ocr_modell``, welches Sehmodell ihn gelesen
hat. Ein gescannter Wirtschaftsplan ist damit so durchsuchbar wie ein
getippter — alles andere wäre eine Sperre gegen die Herkunft des Textes und
nicht gegen das, was darin steht.

DASS TROTZDEM KEINE KONTONUMMER IN EINER ANTWORT LANDET, leistet
``council/kontaktdaten.py`` — und zwar an der **Index-Grenze**, nicht hier:
``store.anlagen_missing_embeddings()`` und ``store.rebuild_fts()`` nehmen IBAN,
BIC, Telefon, Fax, E-Mail und Anschrift aus dem Text, bevor er in die
Chunk-Vektoren bzw. den Volltextindex geht. Gespeichert bleibt alles, denn die
Parser brauchen den vollen Text.

Das ist ausdrücklich **kein OCR-Thema**: 496 Anlagen des Bestands tragen
Kontaktdaten, ganz ohne Texterkennung, und standen bis dahin unmaskiert im
Index.

KOSTEN: gemessen 0,0024 $ je Seite mit dem Vorgabemodell. Die ~46
Finanzdokumente (~600 Seiten) liegen bei rund 1,50 $, der ganze Bestand bei
unter 10 $. ``--trocken`` sagt vorher, wie viele Seiten es werden.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import ocr  # noqa: E402
from council.store import CouncilStore  # noqa: E402
# DIE SITZUNG DES REPOS, NICHT `requests.get`. Sie setzt
# `User-Agent: Mozilla/5.0`; mit dem Standard-UA von requests antwortet das
# Bürgerinfo **403 Forbidden**. Der erste Lauf auf der Dev-VM (20.08.2026) hat
# genau das vorgeführt: sechs Anlagen geladen, zwei mit 403 abgewiesen — und
# eine davon war der AWB-Wirtschaftsplan 2020, also ein ganzer Jahrgang.
from council.vorlagen import _session  # noqa: E402
from scripts.backfill_anlagen_texte import finanz_muster  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Obergrenze je Dokument. Fängt ab, dass ein einzelnes 300-Seiten-PDF den
#: ganzen Lauf auffrisst — und macht die Kosten vorhersagbar.
MAX_SEITEN = 120


def kandidaten(store: CouncilStore, nur_finanz: bool, document_id: int | None,
               limit: int | None) -> list[dict]:
    """Die Arbeitsliste: Anlagen ohne Textebene, die noch niemand gelesen hat.

    ``status='empty'`` ist die Menge, die ``backfill_anlagen_texte.py``
    hinterlässt. Was schon gelesen ist, steht auf ``'ok'`` und fällt heraus —
    ein zweiter Lauf bezahlt nichts doppelt.

    ZWEI AUSNAHMEN KOMMEN ZURÜCK: Anlagen, deren Text nur aus dem Platzhalter
    besteht (ein Lauf ohne Renderer, s. u.), und Altstände mit
    ``status='ocr'`` — jenen Wert schrieb dieses Skript bis zum 20.08.2026,
    als OCR-Text noch pauschal aus der Suche gehalten wurde. Das war der
    falsche Ort für die Sperre; sie sitzt jetzt an der Index-Grenze
    (`council/kontaktdaten.py`), und die Altstände werden beim nächsten Lauf
    auf ``'ok'`` gehoben.
    """
    if document_id is not None:
        wo, werte = "document_id = ?", [document_id]
    else:
        # Anlagen mit Platzhaltern zählen wieder mit. Ein Lauf ohne Renderer
        # hat am 20.08.2026 drei Anlagen hinterlassen, deren Text
        # ausschließlich aus „[Seite N: nicht lesbar gemacht]" bestand. Sie
        # sähen für jeden späteren Lauf erledigt aus und wären es nie gewesen.
        #
        # `status='ocr'` ist der Altstand desselben Tages: Solange OCR-Text
        # pauschal aus der Suche gehalten wurde, schrieb dieses Skript diesen
        # Wert. Er kommt hier zurück und wird beim Speichern auf 'ok' gehoben.
        # `status='ocr'` steht hier NICHT mehr: Die Migration in `store.py`
        # hebt solche Altstände beim Öffnen der Datenbank auf 'ok'. Sie hier
        # noch einmal aufzunehmen hieße, sie ein zweites Mal zu bezahlen.
        wo = ("(status = 'empty' OR (status = 'ok' AND raw_text LIKE ?)) "
              "AND url IS NOT NULL")
        werte = ["[Seite %nicht lesbar gemacht]%"]
        if nur_finanz:
            muster = finanz_muster()
            wo += " AND (" + " OR ".join("label LIKE ?" for _ in muster) + ")"
            werte += muster
    sql = (f"SELECT document_id, label, url, n_pages FROM council_anlagen "
           f"WHERE {wo} ORDER BY document_id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in store._conn.execute(sql, werte).fetchall()]


#: Wie oft ein Download wiederholt wird, bevor die Anlage als Fehler gilt.
#: Von acht Anlagen wies das Bürgerinfo im ersten Lauf zwei ab — sechs
#: gleichzeitig laufende Downloads waren ihm zu schnell. Ein zweiter Versuch
#: nach ein paar Sekunden kostet nichts und rettet einen ganzen Jahrgang.
VERSUCHE = 4
PAUSE_S = 4.0


def _hole(url: str) -> bytes:
    """Ein PDF holen — mit der Sitzung des Repos und mit Geduld.

    403 wird MIT wiederholt: Das Bürgerinfo antwortet damit auch dann, wenn
    ihm die Taktung nicht passt, nicht nur bei fehlendem User-Agent. Ein
    dauerhaftes 403 fällt nach vier Versuchen trotzdem durch — dann steht die
    Anlage als Fehler im Log, statt still zu fehlen.
    """
    letzter: Exception | None = None
    for versuch in range(VERSUCHE):
        try:
            antwort = _session.get(url, timeout=90)
            antwort.raise_for_status()
            return antwort.content
        except Exception as exc:  # noqa: BLE001 — jede Netzstörung ist wiederholbar
            letzter = exc
            if versuch < VERSUCHE - 1:
                time.sleep(PAUSE_S * (versuch + 1))
    raise letzter  # type: ignore[misc]


def process(db_path: Path, *, nur_finanz: bool, document_id: int | None,
            limit: int | None, workers: int, max_seiten: int, model: str,
            trocken: bool) -> dict:
    store = CouncilStore(db_path)
    try:
        rows = kandidaten(store, nur_finanz, document_id, limit)
        # `n_pages` ist NULL, solange eine Anlage nur gelistet und nie geladen
        # wurde. Die als „0 Seiten" auszuweisen wäre eine Behauptung — die
        # Schätzung sagt lieber, für wie viele sie gar nicht gilt.
        bekannt = [r for r in rows if r["n_pages"]]
        seiten_gesamt = sum(min(r["n_pages"], max_seiten) for r in bekannt)
        offen = len(rows) - len(bekannt)
        print(f"{len(rows)} Anlagen, zusammen höchstens {seiten_gesamt} Seiten"
              + (f" (+ {offen} mit unbekannter Seitenzahl)" if offen else "")
              + f" (Modell {model})", flush=True)
        if trocken:
            for r in rows[:25]:
                print(f"  [{r['document_id']:>7}] {r['n_pages'] or '?':>3} S.  "
                      f"{(r['label'] or '')[:70]}", flush=True)
            if len(rows) > 25:
                print(f"  … und {len(rows) - 25} weitere", flush=True)
            return {"kandidaten": len(rows), "seiten": seiten_gesamt, "trocken": 1}

        gelesen = leer = fehler = seiten = 0
        unvollstaendig: list[int] = []

        def laden(row: dict):
            return row, ocr.lies_pdf(_hole(row["url"]), model=model,
                                     max_seiten=max_seiten)

        # Netz + Modell in Workern, DB-Schreiben im Main-Thread — dieselbe
        # SQLite-Konvention wie im Nachbar-Skript.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(laden, r): r["document_id"] for r in rows}
            for fut in as_completed(futs):
                did = futs[fut]
                try:
                    row, lesung = fut.result()
                except Exception as exc:  # noqa: BLE001 — ein kaputtes PDF stoppt nichts
                    fehler += 1
                    print(f"  [{did}] FEHLER {exc}", flush=True)
                    continue
                seiten += lesung.seiten
                # `gelesen == 0` HEISST NICHTS GELESEN — auch wenn Text da ist.
                #
                # Der erste Lauf auf der Dev-VM (20.08.2026) hat das
                # vorgeführt: Drei Dokumente ohne Renderer lieferten 737 bzw.
                # 3253 Zeichen, und zwar ausschließlich die Platzhalter
                # „[Seite N: nicht lesbar gemacht]". Die Längenprüfung ließ sie
                # durch, und sie standen danach als gelesen im Bestand — ohne
                # einen einzigen Buchstaben vom Papier.
                #
                # Sie bleiben jetzt auf `'empty'`. Damit stehen sie weiter auf
                # der Arbeitsliste und werden beim nächsten Lauf, wenn ein
                # Renderer da ist, richtig gelesen.
                if lesung.gelesen == 0 or len(lesung.text) < ocr.MIN_SEITE:
                    leer += 1
                    grund = ("keine Seite ließ sich in ein Bild verwandeln — "
                             "fehlt der Renderer? (pip install pypdfium2)"
                             if lesung.weg == "keiner" else "kein Text erkannt")
                    print(f"  [{did}] nichts gelesen ({lesung.seiten} Seiten): "
                          f"{grund}", flush=True)
                    continue
                with store._conn:
                    store._conn.execute(
                        "UPDATE council_anlagen SET raw_text = ?, n_pages = ?, "
                        "status = 'ok', ocr_modell = ?, fetched_at = datetime('now') "
                        "WHERE document_id = ?",
                        (lesung.text, lesung.seiten, lesung.modell, did))
                gelesen += 1
                if not lesung.vollstaendig:
                    unvollstaendig.append(did)
                hinweis = (f", Einheit: {', '.join(lesung.skalen)}"
                           if lesung.skalen else "")
                print(f"  [{did}] {lesung.gelesen}/{lesung.seiten} Seiten, "
                      f"{len(lesung.text)} Zeichen, {lesung.weg}{hinweis}"
                      f"{'  UNVOLLSTÄNDIG' if not lesung.vollstaendig else ''}",
                      flush=True)

        if unvollstaendig:
            # Kein Fehler, aber nichts, was im Rauschen untergehen darf: Diese
            # Dokumente haben Seiten, die weder eingebettet noch gerendert
            # werden konnten. Eine Rechenprobe darüber prüft dann WENIGER,
            # ohne zu scheitern.
            print(f"UNVOLLSTÄNDIG gelesen: {', '.join(str(d) for d in unvollstaendig)}",
                  flush=True)
        return {"gelesen": gelesen, "ohne_text": leer, "fehler": fehler,
                "seiten": seiten, "unvollstaendig": len(unvollstaendig),
                "gesamt": len(rows)}
    finally:
        store.close()


def main() -> dict:
    ap = argparse.ArgumentParser(
        description="Gescannte Anlagen per Sehmodell lesen")
    ap.add_argument("--nur-finanz", action="store_true",
                    help="nur Anlagen, aus denen der Haushalts-Bereich liest")
    ap.add_argument("--document-id", type=int, default=None,
                    help="genau ein Dokument, unabhängig von seinem Status")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-seiten", type=int, default=MAX_SEITEN)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default=ocr.MODEL)
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was drankäme — ruft kein Modell auf")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    stats = process(Path(args.db), nur_finanz=args.nur_finanz,
                    document_id=args.document_id, limit=args.limit,
                    workers=args.workers, max_seiten=args.max_seiten,
                    model=args.model, trocken=args.trocken)
    if not args.trocken:
        print(f"OCR: {stats['gelesen']} gelesen, {stats['ohne_text']} ohne Text, "
              f"{stats['fehler']} Fehler von {stats['gesamt']} "
              f"({stats['seiten']} Seiten)", flush=True)
    return stats


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backfill_anlagen_ocr", main)
