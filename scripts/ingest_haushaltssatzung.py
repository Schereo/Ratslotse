#!/usr/bin/env python3
"""Die Haushaltssatzungen einlesen — Kreditermächtigung, Dispo, Finanzhaushalt.

Liest die Anlagen, deren Label „Haushaltssatzung" enthält
(`council/haushaltssatzung.py`), und speichert je Jahrgang eine Zeile. Jede
Satzung prüft sich dabei selbst: Ihre drei Einzahlungs- und drei
Auszahlungszeilen müssen die Summe ergeben, die sie darunter als
„Nachrichtlich" selbst ausweist. Was nicht aufgeht, wird nicht gespeichert.

    python scripts/ingest_haushaltssatzung.py --trockenlauf
    python scripts/ingest_haushaltssatzung.py

WAS HIER EINGELESEN WIRD, IST NICHT BESCHLOSSEN. Alle Satzungen im
Ratsinformationssystem sind Verwaltungsentwürfe — die beschlossene Fassung
steht im Amtsblatt. Jede Zeile trägt deshalb `fassung='entwurf'`, und der Lauf
sagt es bei jedem Jahrgang noch einmal dazu.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.haushaltssatzung import (  # noqa: E402
    SatzungFehler,
    herkunft_fuer,
    parse_satzung,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def hebesatz_probe(store: CouncilStore, satzung) -> str | None:
    """Den Hebesatz gegen Tabelle 1105 des Statistischen Jahrbuchs halten.

    Liefert ``None``, wenn dort für diesen Jahrgang nichts steht — das ist
    kein Fehler, sondern der Normalfall für den kommenden Haushalt: Das
    Jahrbuch erscheint später als die Satzung. Ein Widerspruch dagegen ist
    einer und lässt den Jahrgang durchfallen.
    """
    try:
        rows = store._conn.execute(  # noqa: SLF001
            "SELECT art, hebesatz FROM council_hebesaetze WHERE year = ?",
            (satzung.year,)).fetchall()
    except Exception:  # noqa: BLE001 — Tabelle kann fehlen
        return None
    if not rows:
        return None

    felder = {
        "grundsteuer_a": satzung.hebesatz_grundsteuer_a,
        "grundsteuer_b": satzung.hebesatz_grundsteuer_b,
        "gewerbesteuer": satzung.hebesatz_gewerbesteuer,
    }
    geprueft = []
    for art, wert in rows:
        eigen = felder.get(art)
        if eigen is None:
            continue
        if int(wert) != int(eigen):
            raise SatzungFehler(
                f"Hebesatz {art} {satzung.year}: Die Satzung sagt {eigen} v.H., "
                f"das Statistische Jahrbuch {int(wert)} v.H. — zwei Häuser "
                "widersprechen sich.")
        geprueft.append(f"{art} {eigen} v.H.")
    return ("Hebesatz gegen Tabelle 1105 gehalten: " + ", ".join(geprueft)
            if geprueft else None)


def main() -> dict:
    ap = argparse.ArgumentParser(description="Haushaltssatzungen einlesen")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        rows = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT document_id, label, url, raw_text, status "
            "FROM council_anlagen WHERE label LIKE '%Haushaltssatzung%' "
            "ORDER BY document_id")]
        print(f"{len(rows)} Anlage(n) mit „Haushaltssatzung“ im Label.", flush=True)

        gelesen, risse, ohne_text = [], [], []
        for r in rows:
            if not (r["raw_text"] or "").strip():
                ohne_text.append((r["document_id"], r["label"], r["status"]))
                continue
            try:
                satzung = parse_satzung(r["raw_text"])
            except SatzungFehler as fehler:
                risse.append(f"{r['document_id']} ({r['label']}): {fehler}")
                continue
            gelesen.append((satzung, r))

        if gelesen:
            print("\nGelesen:", flush=True)
            for satzung, r in sorted(gelesen, key=lambda x: x[0].year):
                lk = (f"{satzung.liquiditaetskredite / 1e6:,.0f} Mio. €"
                      if satzung.liquiditaetskredite else "—")
                kr = ("nicht veranschlagt" if satzung.kredite_investitionen == 0
                      else (f"{(satzung.kredite_investitionen or 0) / 1e6:,.1f} Mio. €"
                            if satzung.kredite_investitionen else "—"))
                print(f"  {satzung.year}  [{satzung.fassung}]  "
                      f"Dispo {lk:>14}  Investitionskredite: {kr}", flush=True)

        if ohne_text:
            print("\nOhne Volltext — nichts zu lesen "
                  "(backfill_anlagen_texte.py holt sie):", flush=True)
            for did, label, status in ohne_text:
                print(f"  {did}  {label[:52]:54} {status}", flush=True)

        if risse:
            print("\nNicht gelesen:", flush=True)
            for satz in risse:
                print(f"  {satz}", flush=True)

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.", flush=True)
            return {"gelesen": len(gelesen), "ohne_text": len(ohne_text),
                    "risse": len(risse), "trocken": 1}

        gespeichert = 0
        widersprueche = []
        for satzung, r in gelesen:
            try:
                geprueft = hebesatz_probe(store, satzung)
            except SatzungFehler as fehler:
                widersprueche.append(str(fehler))
                continue
            store.save_haushaltssatzung(satzung, herkunft_fuer(
                satzung, url=r["url"], document_id=r["document_id"],
                label=r["label"], hebesatz_geprueft=geprueft))
            gespeichert += 1

        if widersprueche:
            print("\nWiderspruch zwischen Satzung und Jahrbuch — NICHT gespeichert:",
                  flush=True)
            for satz in widersprueche:
                print(f"  {satz}", flush=True)

        print(f"\n{gespeichert} Satzung(en) gespeichert. Alle sind "
              "Verwaltungsentwürfe — die beschlossene Fassung steht im "
              "Amtsblatt, nicht im Ratsinformationssystem.", flush=True)
        return {"gelesen": len(gelesen), "gespeichert": gespeichert,
                "ohne_text": len(ohne_text), "risse": len(risse),
                "widersprueche": len(widersprueche),
                "befund": widersprueche + risse}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_haushaltssatzung", main)
