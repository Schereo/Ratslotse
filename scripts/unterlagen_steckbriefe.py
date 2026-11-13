#!/usr/bin/env python3
"""Steckbriefe für den Bestand: Art, Antragsteller, Seiten je Dokument
(docs/plan-vorlagen-aufbereiten.md, PR 6).

- Vorlagen-PDFs: Seitenanfänge aus dem Druckkopf „Seite: n/m" — ohne Download.
- Anlagen an Vorlagen und an Punkten: Art aus Label und Textkopf.
- ``--seiten N``: für bis zu N Anlagen mit Text die Seiten laden und Anker
  setzen (1 PDF/s). Vorrang hat, was gelesen wird: kommende Sitzungen und die
  letzten 12 Monate.

Ohne ``--schreiben`` nur der Bericht.

    .venv/bin/python scripts/unterlagen_steckbriefe.py
    .venv/bin/python scripts/unterlagen_steckbriefe.py --schreiben --seiten 400 --synopsen 100 --spezial 100
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import document_types, unterlagen_seiten, vorlagen  # noqa: E402
from council.parties import parties_in_text  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main(db: str | None = None, schreiben: bool = False, seiten: int = 0, synopsen: int = 0,
         spezial: int = 0) -> dict:
    store = CouncilStore(db or str(ROOT / "data" / "council.sqlite"))
    conn = store._conn  # noqa: SLF001 — Ops-Skript, liest den Bestand in einem Zug
    arten: collections.Counter = collections.Counter()
    vorlagen_mit_seiten = vorlagen_gesamt = 0

    for r in conn.execute("SELECT document_id, raw_text, n_pages, status FROM council_templates "
                          "WHERE document_id IS NOT NULL AND status IN ('ok', 'empty')").fetchall():
        vorlagen_gesamt += 1
        off = unterlagen_seiten.template_page_offsets(r["raw_text"] or "")
        vorlagen_mit_seiten += bool(off)
        arten["template"] += 1
        if schreiben:
            store.save_document_profile(r["document_id"], "template", n_pages=r["n_pages"],
                                        is_scan=r["status"] == "empty", page_offsets=off,
                                        text_hash=unterlagen_seiten.text_hash(r["raw_text"] or ""))

    anlagen = conn.execute(
        "SELECT document_id, label, applicants, n_pages, status, substr(COALESCE(raw_text, ''), 1, 4000) AS kopf "
        "FROM council_attachments").fetchall()
    for a in anlagen:
        art = document_types.classify(a["label"], a["kopf"])
        arten[art] += 1
        if schreiben:
            antragsteller = json.loads(a["applicants"] or "[]") or parties_in_text(a["label"])
            store.save_document_profile(a["document_id"], art, applicants=antragsteller, n_pages=a["n_pages"],
                                        is_scan=a["status"] == "empty")

    punkt = conn.execute(
        "SELECT document_id, label, substr(COALESCE(raw_text, ''), 1, 4000) AS kopf, raw_text IS NOT NULL AS gelesen "
        "FROM council_agenda_attachments WHERE document_id IS NOT NULL AND label != 'Vorlage' "
        "GROUP BY document_id").fetchall()
    for a in punkt:
        art = document_types.classify(a["label"], a["kopf"])
        arten[art] += 1
        if schreiben:
            store.save_document_profile(a["document_id"], art,
                                        applicants=parties_in_text(a["label"]) or parties_in_text(a["kopf"]),
                                        is_scan=bool(a["gelesen"]) and len(a["kopf"].strip()) < 50)

    anker = 0
    if schreiben and seiten:
        kandidaten = conn.execute(
            "SELECT DISTINCT at.document_id, at.label, at.url, at.raw_text FROM council_attachments at "
            "JOIN council_templates t ON t.kvonr = at.kvonr "
            "JOIN council_agenda_items a ON a.template_number = t.template_number "
            "JOIN council_sessions s ON s.ksinr = a.ksinr "
            "LEFT JOIN council_documents d ON d.document_id = at.document_id "
            "WHERE at.status = 'ok' AND s.session_date >= date('now', '-12 months') "
            "AND d.page_offsets IS NULL ORDER BY s.session_date DESC LIMIT ?", (seiten,)).fetchall()
        for k in kandidaten:
            try:
                pages = vorlagen.pdf_seiten_laden(k["url"])
            except Exception as exc:  # noqa: BLE001
                print(f"  {k['document_id']}: {exc!r}")
                continue
            off = unterlagen_seiten.anchor_offsets(pages, k["raw_text"] or "")
            store.save_document_profile(k["document_id"], document_types.classify(k["label"], k["raw_text"]),
                                        n_pages=len(pages), page_offsets=off,
                                        text_hash=unterlagen_seiten.text_hash(k["raw_text"] or ""))
            anker += bool(off)
            time.sleep(1)

    gelesen_syn = 0
    if schreiben and synopsen:
        # Spezialleser: Synopsen der letzten 12 Monate spaltengenau lesen (council/synopse.py).
        from council import synopse
        kandidaten = conn.execute(
            "SELECT DISTINCT at.document_id, at.url FROM council_attachments at "
            "JOIN council_documents d ON d.document_id = at.document_id "
            "JOIN council_templates t ON t.kvonr = at.kvonr "
            "JOIN council_agenda_items a ON a.template_number = t.template_number "
            "JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE d.doc_type = 'synopsis' AND d.structure IS NULL AND s.session_date >= date('now', '-12 months') "
            "ORDER BY s.session_date DESC LIMIT ?", (synopsen,)).fetchall()
        for k in kandidaten:
            try:
                r = vorlagen._session.get(k["url"], timeout=45)  # noqa: SLF001
                r.raise_for_status()
                store.save_document_structure(k["document_id"], synopse.changes(synopse.read(r.content)))
                gelesen_syn += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  Synopse {k['document_id']}: {exc!r}")
            time.sleep(1)
        print(f"Synopsen spaltengenau gelesen: {gelesen_syn}")

    gelesen_spezial = 0
    if schreiben and spezial:
        # Spezialleser: Abwägungstabellen (nur Zahl und Ergebnis) und Prüfvermerke
        # des Rechnungsprüfungsamts (council/spezialleser.py), letzte 12 Monate.
        from council import spezialleser
        kandidaten = conn.execute(
            "SELECT DISTINCT d.document_id, d.doc_type, at.url FROM council_documents d "
            "JOIN council_attachments at ON at.document_id = d.document_id "
            "JOIN council_templates t ON t.kvonr = at.kvonr "
            "JOIN council_agenda_items a ON a.template_number = t.template_number "
            "JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE d.doc_type IN ('objection_table', 'audit_report') AND d.structure IS NULL "
            "AND s.session_date >= date('now', '-12 months') ORDER BY s.session_date DESC LIMIT ?",
            (spezial,)).fetchall()
        for k in kandidaten:
            try:
                r = vorlagen._session.get(k["url"], timeout=60)  # noqa: SLF001
                r.raise_for_status()
                if k["doc_type"] == "audit_report":
                    notes = spezialleser.pruefvermerke(r.content)
                    ergebnis = {"summary": spezialleser.pruefvermerke_zusammenfassung(notes), "notes": notes}
                else:
                    ergebnis = spezialleser.abwaegung(r.content)
                if ergebnis:
                    store.save_document_structure(k["document_id"], ergebnis)
                    gelesen_spezial += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  Spezialleser {k['document_id']}: {exc!r}")
            time.sleep(1)
        print(f"Abwägungen und Prüfberichte gelesen: {gelesen_spezial}")

    quote = vorlagen_mit_seiten / vorlagen_gesamt if vorlagen_gesamt else 0
    print(f"Vorlagen mit Seiten aus dem Druckkopf: {vorlagen_mit_seiten} von {vorlagen_gesamt} ({quote:.1%})")
    print("Arten:", ", ".join(f"{k} {v}" for k, v in arten.most_common()))
    if seiten:
        print(f"Anlagen mit Seitenankern: {anker}")
    store.close()
    return {"vorlagen": vorlagen_gesamt, "vorlagen_seiten": vorlagen_mit_seiten, "anker": anker, **arten}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--seiten", type=int, default=0)
    ap.add_argument("--synopsen", type=int, default=0)
    ap.add_argument("--spezial", type=int, default=0, help="Abwägungen und Prüfberichte lesen (je 1 PDF/s)")
    a = ap.parse_args()
    main(a.db, a.schreiben, a.seiten, a.synopsen, a.spezial)
