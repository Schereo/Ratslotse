#!/usr/bin/env python3
"""Die Quartalsberichte der städtischen Beteiligungen einlesen.

Liest die Anlagen der Sammelvorlagen „Bericht zum n. Quartal JJJJ der
städtischen Beteiligungsunternehmen und Eigenbetriebe"
(``council/finanzquellen.py``, Schlüssel ``holding_quarterly``) aus dem
**gespeicherten Anlagentext** — ohne PDF-Download — und speichert je Bericht,
Unternehmen und Stichtag Plan und Hochrechnung. Warum die Schicht kein Ist
führt, wie Einheit und Vorzeichen je Bericht bestimmt werden und was als
Widerspruch gilt, steht im Kopf von ``council/holding_quarterly.py``.

    python scripts/ingest_holding_quarterly.py --trockenlauf
    python scripts/ingest_holding_quarterly.py
    python scripts/ingest_holding_quarterly.py --nur-fehlende   # der Cron-Weg

Lokal, wo der Abzug der Ratsdaten keine Anlagen-Rohtexte trägt:
``--text-ordner DIR`` liest ``DIR/<document_id>.txt`` statt der Datenbank.

Was nicht aufgeht, wird nicht gespeichert und am Ende genannt: eine Zeile, deren
gedruckte Abweichung nicht zu Hochrechnung und Plan passt, eine Hochrechnung, die
im Seitentext anders lautet als in der Tabelle, ein Stichtag, der sich
widerspricht. Die Messzahlen gegen Wirtschaftsplan und Abschluss
(``--abgleich``) sind Bestätigung, kein Ausschlusskriterium.
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

from council import finanzquellen, holding_quarterly  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Quartalsberichte der Beteiligungen einlesen")
    ap.add_argument("--trockenlauf", action="store_true", help="lesen und zeigen, nichts speichern")
    ap.add_argument("--nur-fehlende", action="store_true",
                    help="nur Stichtage, die noch nicht im Bestand stehen")
    ap.add_argument("--abgleich", action="store_true",
                    help="die Messzahlen gegen Wirtschaftsplan und Abschluss einzeln zeigen")
    ap.add_argument("--text-ordner", default=None,
                    help="Anlagentexte aus DIR/<document_id>.txt lesen (lokal, ohne Rohtexte)")
    ap.add_argument("--ohne-schutz", action="store_true",
                    help="auch ersetzen, wenn der neue Lauf deutlich weniger Zeilen liefert")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args(argv)

    quelle = finanzquellen.QUELLEN["holding_quarterly"]
    p = finanzquellen.Protokoll()
    store = CouncilStore(Path(args.db))
    try:
        kandidaten = quelle.dokumente(store, "document_id, kvonr, label, url, raw_text")
        kandidaten.sort(key=lambda r: r["document_id"])
        vorhanden = quelle.vorhandene(store, args.nur_fehlende)
        vorlagen = {r["kvonr"]: (r["template_number"], r["title"]) for r in store._conn.execute(  # noqa: SLF001
            "SELECT kvonr, template_number, title FROM council_templates")}
        p.sagen(f"{len(kandidaten)} Anlage(n) zu Quartalsberichten; "
                f"{len(vorhanden)} Stichtag(e) schon im Bestand.")

        je_einheit: dict[tuple, tuple[dict, holding_quarterly.Bericht]] = {}
        ohne_text = 0
        risse: list[str] = []
        for r in kandidaten:
            nummer, titel = vorlagen.get(r["kvonr"], (None, None))
            if not holding_quarterly.ist_quartalsbericht(titel):
                continue
            text = r.get("raw_text") or ""
            if args.text_ordner:
                datei = Path(args.text_ordner) / f"{r['document_id']}.txt"
                text = datei.read_text(encoding="utf-8") if datei.exists() else text
            if not text.strip():
                ohne_text += 1
                continue
            try:
                bericht = holding_quarterly.lies_bericht(text, titel, nummer, r["document_id"])
            except holding_quarterly.QuartalFehler as fehler:
                risse.append(f"{nummer} (Dokument {r['document_id']}): {fehler}")
                continue
            einheit = (bericht.fiscal_year, bericht.as_of)
            if einheit in vorhanden or einheit in je_einheit:
                continue
            je_einheit[einheit] = (r, bericht)

        abgewiesen: list[str] = []
        konflikte: list[str] = []
        bestaetigt = abweichend = 0
        for einheit, (r, bericht) in sorted(je_einheit.items()):
            p.sagen(f"  {bericht.as_of}  {bericht.template_number:8}  {bericht.unit:4}  "
                    f"{len(bericht.zeilen):2} Zeilen  [{bericht.sign_rule}]"
                    + (f"  {len(bericht.abgewiesen)} abgewiesen" if bericht.abgewiesen else ""))
            abgewiesen += [f"{bericht.template_number}: {s}" for s in bericht.abgewiesen]
            konflikte += [f"{bericht.template_number}: {z.company} — "
                          + (f"Plan laut Seitentext {z.plan_text:,} €, Tabelle {z.plan:,} €".replace(",", ".")
                             if z.plan_text not in (None, z.plan) else
                             f"gedruckte Abweichung weicht um {z.deviation_gap:,} € ab".replace(",", "."))
                          for z in bericht.zeilen if z.conflict]
            for stimmt, zeile in holding_quarterly.abgleich(bericht, store._conn):  # noqa: SLF001
                if stimmt:
                    bestaetigt += 1
                else:
                    abweichend += 1
                if args.abgleich:
                    p.sagen(f"      {bericht.as_of} {zeile}")

        for titel, eintraege in (("Nicht gespeichert (Probe gerissen)", abgewiesen),
                                 ("Widersprüche, Zeile bleibt mit Konfliktmarke", konflikte),
                                 ("Berichte nicht gelesen", risse)):
            if eintraege:
                p.sagen(f"\n{titel}:")
                for satz in eintraege:
                    p.sagen(f"  {satz}")
        if ohne_text:
            p.sagen(f"\n{ohne_text} Anlage(n) ohne gespeicherten Text — der Textabzug "
                    "(backfill_anlagen_texte.py) fehlt noch.")

        zeilen = sum(len(b.zeilen) for _r, b in je_einheit.values())
        p.sagen(f"\n{len(je_einheit)} Bericht(e), {zeilen} Zeilen gelesen; Abgleich: "
                f"{bestaetigt} bestätigt, {abweichend} mit Abstand (nur gemeldet).")
        kennzahlen = {"gelesen": len(je_einheit), "zeilen": zeilen,
                      "abgewiesen": len(abgewiesen), "konflikte": len(konflikte),
                      "risse": len(risse), "ohne_text": ohne_text,
                      "abgleich_bestaetigt": bestaetigt, "abgleich_abstand": abweichend}
        if args.trockenlauf:
            p.sagen("\n— Trockenlauf, nichts gespeichert.")
            return {**kennzahlen, "trocken": 1}

        gespeichert = 0
        for einheit, (r, bericht) in sorted(je_einheit.items()):
            alt = store._conn.execute(  # noqa: SLF001
                "SELECT COUNT(*) FROM council_holding_forecasts "
                "WHERE fiscal_year = ? AND as_of = ?", einheit).fetchone()[0]
            if not finanzquellen.bestandsschutz(
                    p, f"{bericht.as_of}", alt, len(bericht.zeilen),
                    schuetzen=not args.ohne_schutz):
                continue
            gespeichert += store.save_holding_forecasts(bericht, holding_quarterly.herkunft_fuer(
                bericht, document_id=r["document_id"], label=r["label"], url=r["url"]))
        luecken = store.herkunft_luecken()
        p.sagen(f"Gespeichert: {gespeichert} Zeilen.")
        if luecken:
            p.warnen(f"Zeilen ohne Herkunft: {luecken}")
        return {**kennzahlen, "gespeichert": gespeichert,
                "befund": abgewiesen + risse}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_holding_quarterly", main)
