#!/usr/bin/env python3
"""Den Vorbericht des Haushaltsplans einlesen (Anlage 001): der Wortlaut je
Teilhaushalt, zum Ergebnishaushalt und zu den Investitionen — und aus
demselben Abruf die Zahlen zu Personal, Steuerarten und Fehlbeträgen
(``council/vorbericht_zahlen.py``).

Parser und Probe: ``council/vorbericht.py``. Der Lauf lädt die PDFs selbst —
die Absätze kommen aus den Textblöcken, die der gespeicherte Textauszug nicht
hergibt. Acht Pläne à 80–100 Seiten, höflich nacheinander.

    python scripts/ingest_vorbericht.py
    python scripts/ingest_vorbericht.py --trocken
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen, herkunft, vorbericht  # noqa: E402
from council import vorbericht_zahlen as vz  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
#: Das Sammel-PDF „2-5 Vorbericht, Übersichten, …" (280 Seiten) nicht laden.
MAX_SEITEN = 150


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        return antwort.read()


#: Reihe → Steuerart im Jahrbuch (``council_taxes.kind``). Die Gewerbesteuer
#: fehlt mit Absicht: Das Jahrbuch zählt sie nach Abzug der Umlage.
JAHRBUCH = {"tax_property": "Grundsteuer A+B", "tax_income": "Einkommensteueranteil",
            "tax_sales": "Gemeindeanteil an der Umsatzsteuer"}


def _zahlen(store: CouncilStore, jahr: int, pdf: bytes, r: dict, trocken: bool, p) -> None:
    """Personal, Steuerarten, Fehlbeträge — gespeichert wird je Reihe, was
    seine Probe besteht: Personal und Ergebnis gegen den Ergebnishaushalt
    desselben Plans, Steuer-Ist gegen das Statistische Jahrbuch (0,15 Mio. €;
    die Diagramme runden auf 0,1 Mio.)."""
    import pymupdf  # noqa: PLC0415
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        seiten = [str(s.get_text()) for s in doc]
    lesung = vz.lies(seiten, jahr)
    plan = {(z["year"], z["nr"]): z["amount"] for z in store.get_ergebnishaushalt()
            if z["plan_budget_year"] == jahr}
    ist = {(z["year"], z["kind"]): z["amount"] for z in store.get_steuereinnahmen()}
    schlecht = {h.split()[0] for h in vz.pruefe_gegen_plan(lesung, plan)}
    if any(h.startswith("Personal") for h in lesung.hinweise) or "personnel_active" in schlecht \
            or "personnel_pension" in schlecht:
        schlecht |= set(vz.PERSONAL_ZEILEN)
    if "Ergebnis" in schlecht:
        schlecht.add("result")
    for w in lesung.werte:
        kind = JAHRBUCH.get(w.series)
        if kind and w.variant == "actual" and (w.year, kind) in ist \
                and abs(ist[(w.year, kind)] - w.amount) > 150_000:
            schlecht.add(w.series)
            lesung.hinweise.append(f"{w.series} {w.year}: Vorbericht {w.amount / 1e6:.1f}, "
                                   f"Jahrbuch {ist[(w.year, kind)] / 1e6:.1f} Mio. €")
    werte = [w for w in lesung.werte if w.series not in schlecht]
    p.sagen(f"    Zahlen {jahr}: {len(werte)} Werte in {len({w.series for w in werte})} Reihen"
            + (f", verworfen: {sorted(schlecht & set(vz.DIAGRAMME) | schlecht & set(vz.PERSONAL_ZEILEN))}"
               if schlecht else ""))
    for h in lesung.hinweise:
        p.sagen(f"      Hinweis: {h}")
    if trocken or not werte:
        return
    store.save_vorbericht_zahlen(jahr, [asdict(w) for w in werte], herkunft.Herkunft(
        kind="ris", probe=[vz.PROBE], document_id=r["document_id"], label=r["label"], url=r["url"],
        citation="Vorbericht, Kapitel 2.1.1 (Fehlbeträge), 2.2 (Steuerarten), 2.4.1.3 (Personal)",
        probe_result="Personal und Ergebnis gegen den Ergebnishaushalt desselben Plans, "
                     "Steuer-Ist gegen das Statistische Jahrbuch",
        as_of=f"Haushaltsplan {jahr}, Anlage 001 — Stand der Einbringung"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    p = finanzquellen.Protokoll()
    rows = [r for r in finanzquellen.QUELLEN["budget_notes"].dokumente(
        store, "document_id, label, url, n_pages") if (r.get("n_pages") or 0) <= MAX_SEITEN]
    print(f"{len(rows)} Anlage(n) als Vorbericht erkannt.", flush=True)
    gelesen: dict[int, int] = {}
    verworfen = 0
    abrufe = 0
    for r in rows:
        jahr_label = next(iter(finanzquellen._einheiten_uebersichten(r)), (None,))[0]  # noqa: SLF001
        if jahr_label in gelesen:
            continue
        if abrufe:
            time.sleep(args.pause)
        abrufe += 1
        try:
            pdf = _laden(r["url"])
            erg = vorbericht.lies(vorbericht.bloecke_aus_pdf(pdf))
        except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
            p.warnen(f"  {r['document_id']}: nicht ladbar ({exc})")
            verworfen += 1
            continue
        jahr = erg.budget_year
        if jahr is None or jahr in gelesen:
            continue
        # Die Zahlen hängen nicht an der Probe des Wortlauts — eigene Proben.
        _zahlen(store, jahr, pdf, r, args.trocken, p)
        if not erg.bestanden:
            p.warnen(f"  {r['document_id']} ({jahr}): {'; '.join(erg.hinweise)} — nicht gespeichert")
            verworfen += 1
            continue
        zeichen = sum(len(a.text) for a in erg.abschnitte)
        p.sagen(f"  {jahr}: {len(erg.abschnitte)} Abschnitte, {zeichen:,} Zeichen · Dokument {r['document_id']}")
        gelesen[jahr] = len(erg.abschnitte)
        if args.trocken:
            continue
        store.save_vorbericht(jahr, [asdict(a) for a in erg.abschnitte], herkunft.Herkunft(
            kind="ris", probe=[vorbericht.PROBE_VORBERICHT],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation="Vorbericht, Abschnitte 2.4.2 (Teilhaushalte) und 3.2.2 (Investitionen)",
            probe_result=f"{len(erg.im_inhalt)} Abschnitte im Inhaltsverzeichnis, alle im Text",
            as_of=f"Haushaltsplan {jahr}, Anlage 001 — Stand der Einbringung"))
    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{len(gelesen)} Vorberichte gelesen ({', '.join(map(str, sorted(gelesen)))}), "
          f"{verworfen} verworfen.", flush=True)
    return 1 if verworfen and not gelesen else 0


if __name__ == "__main__":
    raise SystemExit(main())
