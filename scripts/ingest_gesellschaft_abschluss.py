#!/usr/bin/env python3
"""Die Jahresabschlüsse der städtischen Gesellschaften einlesen.

Bilanzsumme und Jahresergebnis aus den Anlagen „Bilanz" und „GuV" der
Vorlagen „<Gesellschaft>: Jahresabschluss 20xx - Beschluss". Parser und
Proben: ``council/gesellschaft_abschluss.py``.

Der Lauf lädt die Anlagen selbst — die Bilanz steht zweispaltig (Aktiva |
Passiva) und oft quer, der gespeicherte Textauszug bringt die Zellen
durcheinander; die Wortrahmen des PDFs nicht. Je Vorlage zwei einseitige
PDFs, gut siebzig insgesamt — höflich nacheinander.

    python scripts/ingest_gesellschaft_abschluss.py
    python scripts/ingest_gesellschaft_abschluss.py --trocken
    python scripts/ingest_gesellschaft_abschluss.py --auch-schrumpfen
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import eigenbetriebe_abschluss as ea, finanzquellen, gesellschaft_abschluss as ga  # noqa: E402
from council import herkunft as h  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
LABEL = "Jahresabschlüsse der städtischen Gesellschaften (Bilanz und GuV im RIS)"


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort:
        return antwort.read()


def _herkunft(zeile: dict, url: str | None, label: str | None) -> h.Herkunft:
    return h.Herkunft(
        kind="ris", probe=list(zeile["probes"]),
        document_id=zeile.get("document_id"), url=url,
        label=label or f"Jahresabschluss {zeile['report_year']}",
        citation=zeile["fundstelle"],
        as_of=f"Jahresabschluss {zeile['report_year']}",
        probe_result=(f"{zeile['confirmations']} Abschluss/Abschlüsse nennen denselben Betrag"
                      + (f", {zeile['conflicts']} einen anderen" if zeile["conflicts"] else "")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="den Bestand auch ersetzen, wenn er dabei kleiner wird")
    ap.add_argument("--pause", type=float, default=1.5,
                    help="Sekunden zwischen zwei Abrufen (Vorgabe 1,5)")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    p = finanzquellen.Protokoll()
    try:
        anlagen = [a for a in store.gesellschaft_abschluss_anlagen()
                   if ga.gesellschaft_aus_titel(a["title"]) and ga.art_aus_label(a["label"])
                   and a.get("url")]
        print(f"{len(anlagen)} Bilanz-/GuV-Anlage(n) zu Jahresabschlüssen der Gesellschaften.",
              flush=True)
        alle: list[ea.Kennzahl] = []
        ohne: list[str] = []
        for i, a in enumerate(anlagen):
            if i:
                time.sleep(args.pause)
            try:
                text = ea.text_aus_wortrahmen(_laden(a["url"]))
            except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
                ohne.append(f"  {a['document_id']} ({a['label'][:45]}): nicht ladbar ({exc})")
                continue
            lesung = ga.lies_anlage(text, a["title"], a["label"], a["document_id"])
            if lesung.kennzahlen:
                alle.extend(lesung.kennzahlen)
            else:
                # Die Scans von 2018/2019 (VWG, OTM) tragen keinen Text; die
                # Jahre deckt der Beteiligungsbericht.
                ohne.append(f"  {a['document_id']} ({a['label'][:45]}): "
                            + ("; ".join(lesung.hinweise[:2]) if text.strip() else "Scan ohne Text"))
        zeilen, strittig = ea.zusammenfuehren(alle)
        print(f"{len(zeilen)} Kennzahl-Zeilen, {len(strittig)} strittig, "
              f"{len(ohne)} Anlage(n) ohne Zahl.", flush=True)
        for o in ohne:
            print(o, flush=True)
        for s in strittig:
            p.warnen(f"  STRITTIG: {s}")
        je: dict[str, list[int]] = {}
        for z in zeilen:
            je.setdefault(z["enterprise"], []).append(z["year"])
        for key, jahre in sorted(je.items()):
            print(f"  {key}: {min(jahre)}–{max(jahre)}", flush=True)
        if args.trocken:
            print("Trockenlauf — nichts gespeichert.", flush=True)
            return 0
        if not finanzquellen.bestandsschutz(
                p, "Jahresabschlüsse der Gesellschaften", len(store.get_company_accounts()),
                len(zeilen), not args.auch_schrumpfen):
            print("ABBRUCH: Der Bestand bleibt unangetastet. Wenn das Schrumpfen "
                  "Absicht ist: --auch-schrumpfen.", file=sys.stderr)
            return 1
        urls = {a["document_id"]: (a["url"], a["label"]) for a in anlagen}
        for z in zeilen:
            url, label = urls.get(z.get("document_id"), (None, None))
            # zusammenfuehren() vergibt die Überlappungsprobe der Eigenbetriebe;
            # hier gilt die eigene (auf den Cent statt auf Tausend).
            if z["confirmations"] > 1:
                z["probes"] = sorted({*z["probes"], ga.PROBE_UEBERLAPPUNG}
                                     - {ea.PROBE_UEBERLAPPUNG})
            else:
                z["probes"] = [pr for pr in z["probes"] if pr != ea.PROBE_UEBERLAPPUNG]
            z["herkunft"] = _herkunft(z, url, label)
        lauf = h.Herkunft(kind="ris", url="https://buergerinfo.oldenburg.de/vo040.asp",
                          label=LABEL, citation=ga.FUNDSTELLE_BILANZ,
                          probe=[ga.PROBE_BILANZ, ga.PROBE_GUV],
                          probe_result=f"{len(zeilen)} Kennzahlen, {len(strittig)} strittig")
        n = store.save_company_accounts(zeilen, lauf)
        store.herkunft_aufraeumen()
        print(f"Gespeichert: {n} Zeilen.", flush=True)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
