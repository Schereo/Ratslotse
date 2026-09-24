#!/usr/bin/env python3
"""Messen, bevor gebaut wird: die Budgetberichte der Fachausschüsse.

Plan Haushalt-Datenquellen, PR 8 (Entscheidung 5): Gebaut wird nur, wenn
mindestens drei Jahrgänge dieselbe Tabelle führen. Dieses Skript lädt je
Vorlage „Budgetbericht …" die Anlage und sagt, was darin steht:

* welches Gremium und welcher Teilhaushalt,
* welche Tabellen (Teilergebnisrechnung, Teilfinanzrechnung, Investitionen je
  Maßnahme, Produkte),
* ob es eine Prognosespalte gibt und ob Maßnahmen mit Nummer (I10.…) und
  Erläuterungstext geführt werden.

Schreibt nichts in die Datenbank. Lädt höflich (1,5 s Abstand).

    python scripts/messe_budgetberichte.py            # Tabelle auf stdout
    python scripts/messe_budgetberichte.py --markdown # für den Plan
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

MERKMALE = {
    "Ergebnisrechnung": r"Teilergebnisrechnung|Ergebnisrechnung",
    "Finanzrechnung": r"Teilfinanzrechnung",
    "Maßnahmen": r"\bI10\.\d{6}",
    "Produkte": r"\bP10\.\d{6}",
    "Prognose": r"Prognose",
}


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=90) as antwort:
        return antwort.read()


def _text(pdf: bytes) -> tuple[str, int]:
    import pymupdf  # noqa: PLC0415
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return "\n".join(str(p.get_text()) for p in doc), doc.page_count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    rows = [dict(r) for r in store._conn.execute(  # noqa: SLF001 — Messskript, liest nur
        """SELECT t.kvonr, t.template_number, t.title,
                  (SELECT group_concat(DISTINCT s.committee) FROM council_decisions d
                     JOIN council_sessions s ON s.ksinr = d.ksinr
                    WHERE d.template_number = t.template_number) AS gremium,
                  a.document_id, a.label, a.url
             FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr
            WHERE t.title LIKE '%Budgetbericht%' AND a.url IS NOT NULL
            ORDER BY t.kvonr""")]
    store.close()
    ergebnis = []
    for i, r in enumerate(rows):
        if i:
            time.sleep(args.pause)
        try:
            text, seiten = _text(_laden(r["url"]))
        except Exception as exc:  # noqa: BLE001 — Messung, kein Abbruch
            ergebnis.append({**r, "fehler": str(exc)})
            continue
        thh = re.search(r"THH\s*0?(\d{1,2})|Teilhaushalt\s+0?(\d{1,2})", text)
        stichtag = re.search(r"(\d{2}\.\d{2}\.20\d\d)", r["title"] + " " + (r["label"] or "") + " " + text[:3000])
        ergebnis.append({**r, "seiten": seiten, "zeichen": len(text.strip()),
                         "thh": (thh.group(1) or thh.group(2)) if thh else None,
                         "stichtag": stichtag.group(1) if stichtag else None,
                         **{k: bool(re.search(m, text)) for k, m in MERKMALE.items()},
                         "massnahmen": len(set(re.findall(r"\bI10\.\d{6}(?:\.\d{3})*", text)))})
    kopf = ["Vorlage", "Gremium", "THH", "Stichtag", "Seiten", "Text", *MERKMALE, "Maßnahmen-Nr."]
    if args.markdown:
        print("| " + " | ".join(kopf) + " |")
        print("|" + "---|" * len(kopf))
    for e in ergebnis:
        if "fehler" in e:
            print(f"{e['template_number']}: {e['fehler']}")
            continue
        werte = [e["template_number"], (e["gremium"] or "–")[:28], e["thh"] or "–",
                 e["stichtag"] or "–", str(e["seiten"]), "ja" if e["zeichen"] > 200 else "Scan",
                 *("✓" if e[k] else "–" for k in MERKMALE), str(e["massnahmen"])]
        print(("| " + " | ".join(werte) + " |") if args.markdown else "  ".join(werte))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
