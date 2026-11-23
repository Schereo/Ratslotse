#!/usr/bin/env python3
"""Kaputte Ligaturen im gespeicherten Anlagentext auflösen — VORGABE: Trockenlauf.

Seit 11/2026 löst ``council/anlagentext.py::pdf_seiten`` sie beim Lesen auf
(„städƟschen" → „städtischen", „Wirtscha)splan" → „Wirtschaftsplan"). Was
VORHER gelesen wurde, trägt sie weiter — gemessen auf dev am 23.11.2026:
20 von 6.779 Anlagen, darunter alle Quartalsberichte der Beteiligungen seit
2021. Dieses Skript repariert den gespeicherten Text ohne Download, Seite für
Seite, und rückt die Seitenanfänge (``council_documents.page_offsets``) mit.

Angefasst werden die Anlagen an Vorlagen und an Punkten. **Nicht** die
Protokolle (an ihren Zeichen hängen die Fundstellen der Wortbeiträge; drei
tragen die Ligaturen, ihre Neufassung läuft über ``pdf_neu_lesen.py``) und
nicht die Vorlagen (keine einzige betroffen).

Folgen eines Laufs: Die Dossiers der betroffenen Vorlagen entstehen beim
nächsten Lauf von ``vorlagen_dossiers.py`` neu (ihre Prüfsumme hängt am Text),
die Chunk-Vektoren der Anlagen ebenso.

    python scripts/ligaturen_reparieren.py               # Bericht
    python scripts/ligaturen_reparieren.py --schreiben   # reparieren
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import unterlagen_seiten  # noqa: E402
from council.anlagentext import gespeicherten_text_reparieren  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_WORT_RE = re.compile(r"\S+")


def _beispiele(alt: str, neu: str, n: int = 4) -> list[str]:
    """Ein paar geänderte Wörter für den Bericht („städƟschen → städtischen")."""
    a, b = _WORT_RE.findall(alt), _WORT_RE.findall(neu)
    return [f"{x} → {y}" for x, y in zip(a, b) if x != y][:n] if len(a) == len(b) else []


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Kaputte Ligaturen im gespeicherten Anlagentext auflösen")
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--schreiben", action="store_true", help="ohne: nur berichten")
    args = ap.parse_args(argv)
    store = CouncilStore(args.db)
    conn = store._conn  # noqa: SLF001 — Ops-Skript, liest den Bestand in einem Zug
    bericht = {"anlagen": 0, "punkt_anlagen": 0, "seiten_neu": 0, "zeichen": 0}
    try:
        profile = {r["document_id"]: (json.loads(r["page_offsets"]) if r["page_offsets"] else None, r["text_hash"])
                   for r in conn.execute("SELECT document_id, page_offsets, text_hash FROM council_documents")}
        # Alle Zeilen eines Dokuments gemeinsam: Die Seitenanfänge teilen sie sich
        # (``council_documents``). Einzeln geschrieben, bekäme nach einem
        # abgebrochenen Lauf die noch alte Zeile die schon NEUEN Anfänge und
        # verschöbe sie ein zweites Mal (Review 23.11.2026).
        zeilen: dict[int, list[tuple[str, int, str]]] = defaultdict(list)
        for tabelle in ("council_attachments", "council_agenda_attachments"):
            for r in conn.execute(f"SELECT rowid AS rid, document_id, raw_text FROM {tabelle} "
                                  "WHERE raw_text IS NOT NULL AND raw_text != ''"):
                zeilen[r["document_id"]].append((tabelle, r["rid"], r["raw_text"]))
        for did, liste in zeilen.items():
            # Die Seitenanfänge gehören zu dem Text, den ``_dokument_text`` liefert:
            # der Anlage an der Vorlage, sonst der am Punkt — und nur, solange die
            # gespeicherte Prüfsumme zu diesem Text passt.
            eigner = next((z for z in liste if z[0] == "council_attachments"), liste[0])
            offsets, hash_alt = profile.get(did, (None, None))
            if offsets and hash_alt and hash_alt != unterlagen_seiten.text_hash(eigner[2]):
                offsets = None
            schreiben: list[tuple[str, int, str]] = []
            neue_seiten = None
            for z in liste:
                neu, neu_off = gespeicherten_text_reparieren(z[2], offsets if z is eigner else None)
                if neu == z[2]:
                    continue
                schreiben.append((z[0], z[1], neu))
                bericht["anlagen" if z[0] == "council_attachments" else "punkt_anlagen"] += 1
                bericht["zeichen"] += len(neu) - len(z[2])
                print(f"  [{z[0]} {did}] {_beispiele(z[2], neu)}", flush=True)
                if z is eigner and offsets:
                    neue_seiten = (neu_off, unterlagen_seiten.text_hash(neu))
            if not schreiben or not args.schreiben:
                continue
            with conn:
                for tabelle, rid, neu in schreiben:
                    conn.execute(f"UPDATE {tabelle} SET raw_text = ? WHERE rowid = ?", (neu, rid))
                if neue_seiten:
                    conn.execute("UPDATE council_documents SET page_offsets = ?, text_hash = ? WHERE document_id = ?",
                                 (json.dumps(neue_seiten[0]), neue_seiten[1], did))
                    bericht["seiten_neu"] += 1
    finally:
        store.close()
    print(("Geschrieben: " if args.schreiben else "Trockenlauf (nichts geschrieben): ")
          + json.dumps(bericht, ensure_ascii=False), flush=True)
    return bericht


if __name__ == "__main__":
    main()
