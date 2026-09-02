#!/usr/bin/env python3
"""Die Jahresabschlüsse der Eigenbetriebe einlesen (council/eigenbetriebe_abschluss.py).

Liest aus dem eigenen Bestand: die Anlagen der Vorlagen „Jahresabschluss und
Lagebericht … für den Eigenbetrieb …" (``council_attachments``, Text vom
Backfill; Scans kommen per OCR). Je Betrieb, Jahr und Kennzahl EINE Zahl aus
dem jüngsten Bericht, bezeugt von den Vorjahresspalten der folgenden.

    python scripts/ingest_eigenbetriebe_abschluss.py [--trockenlauf] [--schrumpf-erlauben] [--db PFAD]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import eigenbetriebe_abschluss as ea, finanzquellen, herkunft as h  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.wirtschaftsplan import BETRIEBE  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
LABEL = "Jahresabschlüsse der Eigenbetriebe (Prüfberichte, GuV und Bilanz im RIS)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--schrumpf-erlauben", action="store_true")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        anlagen = store.eigenbetrieb_abschluss_anlagen()
        ohne_text = [a for a in anlagen if not (a.get("raw_text") or "").strip()]
        alle: list[ea.Kennzahl] = []
        gelesen: list[str] = []
        ohne_tabelle: list[str] = []
        for a in anlagen:
            text = a.get("raw_text") or ""
            if not text.strip():
                continue
            lesung = ea.lies_dokument(text, a["title"], a["label"], a["document_id"])
            if lesung.kennzahlen:
                alle.extend(lesung.kennzahlen)
                bj = ea.betriebsjahr(a["title"])
                gelesen.append(f"  {a['document_id']}  {bj[0] if bj else '?':6} {bj[1] if bj else '?'}  "
                               f"[{lesung.form}] {len(lesung.kennzahlen)} Kennzahlen  {a['label'][:45]}")
            else:
                ohne_tabelle.append(f"  {a['document_id']} ({a['label'][:45]}): "
                                    + "; ".join(lesung.hinweise[:2]))
        zeilen, strittig = ea.zusammenfuehren(alle)
        print(f"{len(anlagen)} Anlage(n) zu Jahresabschluss-Vorlagen, {len(ohne_text)} ohne Text, "
              f"{len(gelesen)} gelesen, {len(ohne_tabelle)} ohne lesbare Tabelle.", flush=True)
        for g in gelesen:
            print(g, flush=True)
        if ohne_tabelle:
            print("\nOhne lesbare Tabelle:", flush=True)
            for o in ohne_tabelle:
                print(o, flush=True)
        if ohne_text:
            print(f"\nOhne Text ({len(ohne_text)}) — der Backfill bzw. die OCR holt sie:", flush=True)
            for a in ohne_text[:20]:
                print(f"  {a['document_id']}  {a['label'][:50]}  {a['status']}", flush=True)
        print(f"\nBestand: {len(zeilen)} Kennzahl-Zeilen, {len(strittig)} strittig.", flush=True)
        for s in strittig:
            print(f"  STRITTIG: {s}", flush=True)
        je_betrieb: dict[str, set[int]] = {}
        for z in zeilen:
            je_betrieb.setdefault(z["enterprise"], set()).add(z["year"])
        for key, jahre in sorted(je_betrieb.items()):
            name = BETRIEBE.get(key, ("", key))[1]
            ergebnisse = {z["year"]: z["value"] for z in zeilen
                          if z["enterprise"] == key and z["metric"] == "result"}
            print(f"  {name}: {min(jahre)}–{max(jahre)} ({len(jahre)} Jahre); Jahresergebnis: "
                  + ", ".join(f"{j} {ergebnisse[j] / 1e6:+.1f} Mio." for j in sorted(ergebnisse)[-4:]),
                  flush=True)
        if args.trockenlauf:
            print("Trockenlauf — nichts gespeichert.", flush=True)
            return 0
        p = finanzquellen.Protokoll()
        if not finanzquellen.bestandsschutz(
                p, "Jahresabschluss-Kennzahlen", len(store.get_enterprise_accounts()), len(zeilen),
                schuetzen=not args.schrumpf_erlauben):
            for row in p.warnungen:
                print(row.strip(), file=sys.stderr)
            print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn das "
                  "Schrumpfen Absicht ist: --schrumpf-erlauben.", file=sys.stderr)
            return 1
        urls = {a["document_id"]: (a.get("url"), a.get("label")) for a in anlagen}
        for z in zeilen:
            url, label = urls.get(z.get("document_id"), (None, None))
            z["herkunft"] = ea.herkunft_fuer(z, url=url, label=label)
        lauf = h.Herkunft(kind="ris", url="https://buergerinfo.oldenburg.de/vo040.asp", label=LABEL,
                          citation=ea.FUNDSTELLE_UEBERSICHT,
                          probe=[ea.PROBE_SPALTEN, ea.PROBE_UEBERLAPPUNG],
                          probe_result=f"{len(zeilen)} Kennzahlen, {len(strittig)} strittig")
        n = store.save_enterprise_accounts(zeilen, lauf)
        print(f"Gespeichert: {n} Zeilen.", flush=True)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_eigenbetriebe_abschluss", main)
