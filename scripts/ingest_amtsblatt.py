#!/usr/bin/env python3
"""Die beschlossene Haushaltssatzung aus dem Amtsblatt einlesen.

Parser und Probe: ``council/amtsblatt.py``. Der Lauf

1. holt die Übersichtsseite des Amtsblatts auf oldenburg.de und die dort
   verlinkten Ausgaben ab 2020,
2. sieht jede noch unbekannte Ausgabe einmal an — Seite 1 genügt, dort
   beginnt die Satzung jedes Jahr — und merkt sich das Ergebnis
   (``council_gazette_issues``), damit kein Lauf dieselbe gescannte Seite
   zweimal bezahlt,
3. liest die Ausgaben mit einer Haushaltssatzung ganz und speichert die
   Fassung, deren Summenprobe aufgeht.

Gescannte Seiten liest das Sehmodell (``council/ocr.py``, gemessen 0,002 $ je
Seite). Der erste Lauf sieht rund 170 Ausgaben an, rund 0,35 $; danach nur
noch neue Ausgaben. ``--max-ocr`` deckelt die Seitenzahl je Lauf.

    python scripts/ingest_amtsblatt.py --trocken
    python scripts/ingest_amtsblatt.py
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import amtsblatt, herkunft, ocr  # noqa: E402
from council.budget_bylaw import SatzungFehler  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
AB_JAHR = 2020
#: Unter so vielen Zeichen gilt eine Seite als Scan ohne Textebene.
MIN_TEXT = 200


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=90) as antwort:
        return antwort.read()


def _textebene(pdf: bytes, seiten: int | None = None) -> str:
    import pypdf  # noqa: PLC0415
    leser = pypdf.PdfReader(io.BytesIO(pdf))
    teile = leser.pages if seiten is None else leser.pages[:seiten]
    return "\n".join((p.extract_text() or "") for p in teile)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="lesen, nichts speichern")
    ap.add_argument("--max-ocr", type=int, default=250, help="höchstens so viele OCR-Seiten je Lauf")
    ap.add_argument("--pause", type=float, default=1.2)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    html = _laden(amtsblatt.UEBERSICHT_URL).decode("utf-8", "replace")
    liste = [a for a in amtsblatt.ausgaben(html) if a.year >= AB_JAHR]
    gesehen = store.amtsblatt_gesehen()
    print(f"{len(liste)} Ausgaben ab {AB_JAHR} verlinkt, {len(gesehen)} schon angesehen.", flush=True)

    ocr_seiten = 0
    mit_satzung = [a for a in liste if gesehen.get(a.url, {}).get("has_bylaw")]
    for a in liste:
        if a.url in gesehen:
            continue
        if ocr_seiten >= args.max_ocr:
            print(f"  Deckel erreicht ({args.max_ocr} OCR-Seiten) — der Rest im nächsten Lauf.", flush=True)
            break
        time.sleep(args.pause)
        try:
            pdf = _laden(a.url)
        except OSError as exc:
            print(f"  {a.year}-{a.nr}: nicht ladbar ({exc})", flush=True)
            continue
        text = _textebene(pdf, seiten=1)
        leser = "text"
        if len(text.strip()) < MIN_TEXT:
            text = ocr.lies_pdf(pdf, max_seiten=1).text
            ocr_seiten += 1
            leser = f"ocr:{ocr.MODEL}"
        treffer = amtsblatt.hat_satzung(text)
        if treffer:
            mit_satzung.append(a)
            print(f"  {a.year}-{a.nr}: Haushaltssatzung ({leser})", flush=True)
        if not args.trocken:
            store.amtsblatt_merken(a.url, a.year, a.nr, treffer, leser)

    schon = {z["year"] for z in store.get_satzungen_veroeffentlicht()}
    entwuerfe = {z["year"]: z for z in store.get_haushaltssatzungen() if not z["supplement"]}
    gespeichert = 0
    for a in mit_satzung:
        if a.year in schon:
            continue
        time.sleep(args.pause)
        pdf = _laden(a.url)
        text = _textebene(pdf)
        try:
            v = amtsblatt.lies(text)
        except SatzungFehler:
            # Gescannt, oder die Spalten der Textebene laufen ineinander (2026):
            # dann liest das Sehmodell, und die Summenprobe entscheidet.
            lesung = ocr.lies_pdf(pdf, max_seiten=4)
            ocr_seiten += lesung.seiten
            try:
                v = amtsblatt.lies(lesung.text)
            except SatzungFehler as fehler:
                print(f"  {a.year}-{a.nr}: {fehler} — nicht gespeichert", flush=True)
                continue
        geaendert = amtsblatt.abweichungen(entwuerfe.get(v.satzung.year), v.satzung)
        print(f"  {v.satzung.year}: beschlossen {v.session_date}, bekannt gemacht {v.published_on} "
              f"(Nr. {a.nr}) · VE {v.satzung.commitment_authorizations or 0:,.0f} € · "
              f"{len(geaendert)} Zahlen anders als im Entwurf"
              + (f" · Genehmigung: {v.approval_note[:80]}" if v.approval_note else ""), flush=True)
        if args.trocken:
            continue
        store.save_satzung_veroeffentlicht(v, issue_nr=a.nr, url=a.url, herkunft=herkunft.Herkunft(
            kind="city", probe=[amtsblatt.PROBE_VEROEFFENTLICHT], url=a.url,
            label=f"Amtsblatt für die Stadt Oldenburg Nr. {a.nr}/{a.year}",
            citation="Haushaltssatzung der Stadt Oldenburg (Oldb) mit Bekanntmachung",
            probe_result="Finanzhaushalt: sechs Zeilen = beide „Nachrichtlich“-Summen",
            as_of=f"bekannt gemacht am {v.published_on}" if v.published_on else "Amtsblatt"))
        gespeichert += 1
    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{gespeichert} Satzungen gespeichert, {ocr_seiten} Seiten per OCR gelesen.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
