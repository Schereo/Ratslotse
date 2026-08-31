#!/usr/bin/env python3
"""Die Änderungslisten zum FINANZhaushalt einlesen — Position für Position.

Das Gegenstück zu ``ingest_aenderungslisten.py``: Jenes liest den
Ergebnishaushalt, dieses den Finanzhaushalt — also das, was investiert wird.

    python scripts/ingest_aenderungslisten_fhh.py --trockenlauf
    python scripts/ingest_aenderungslisten_fhh.py

VORAUSSETZUNG: ``pymupdf``, aus demselben Grund wie beim EHH bewusst nicht in
``requirements.txt``.

WAS NICHT DURCHLÄUFT, WIRD GEMELDET UND NICHT GESPEICHERT. Von den 18
FHH-Listen des Kernhaushalts lesen sich 15 vollständig; die drei übrigen
nennt der Lauf mit Begründung. Das ist die Bauart des Moduls: Eine Liste, die
ihre eigene Schlusssumme nicht trifft, ist keine halbe Liste, sondern eine
ungelesene. Für den Jahrgang 2021 fällt das nicht ins Gewicht — die
Beschluss-Datei liegt doppelt im Bestand (230016/230178), und die zweite
Ablage läuft durch.
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

from council.aenderungslisten_fhh import (  # noqa: E402
    FhhErgebnis,
    ListenFehler,
    herkunft_fuer,
    liste_aus_label,
    lies_fhh_liste,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=45) as antwort:
        return antwort.read()


def _inhaltsgleich(a: FhhErgebnis, b: FhhErgebnis) -> bool:
    """Zwei Anlagen, ein Dokument? Verglichen wird der INHALT, nicht die
    Datei — die 2021er Beschluss-Datei liegt doppelt im Bestand."""
    def kern(e: FhhErgebnis):
        return (sorted(((z.year, z.lfd, z.thh, z.produkt, z.bezeichnung,
                         z.inflow, z.outflow) for z in e.zeilen), key=repr),
                sorted(((s.year, s.typ, s.label, s.inflows, s.outflows)
                        for s in e.summen), key=repr))
    return kern(a) == kern(b)


def main() -> dict:
    ap = argparse.ArgumentParser(description="FHH-Änderungslisten einlesen")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        anlagen = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT document_id, label, url FROM council_anlagen "
            "ORDER BY document_id")]
        kandidaten = [(r, liste_aus_label(r["label"])) for r in anlagen]
        kandidaten = [(r, s) for r, s in kandidaten if s]
        print(f"{len(kandidaten)} FHH-Kandidat(en) unter {len(anlagen)} Anlagen.",
              flush=True)

        gelesen: list[tuple[dict, str, FhhErgebnis]] = []
        risse: list[str] = []
        for r, schluessel in kandidaten:
            try:
                pdf = _laden(r["url"])
                time.sleep(0.6)
                result = lies_fhh_liste(pdf)
            except ListenFehler as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): {fehler}")
                continue
            except OSError as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): "
                             f"Download fehlgeschlagen — {fehler}")
                continue
            gelesen.append((r, schluessel, result))

        je_liste: dict[tuple[int, str], tuple[dict, str, FhhErgebnis]] = {}
        dubletten: list[str] = []
        konflikte: list[str] = []
        for r, schluessel, result in gelesen:
            key = (result.jahrgang, schluessel)
            if key not in je_liste:
                je_liste[key] = (r, schluessel, result)
                continue
            if _inhaltsgleich(je_liste[key][2], result):
                dubletten.append(
                    f"{key[0]} {schluessel}: Dokument {r['document_id']} ist "
                    f"inhaltsgleich mit {je_liste[key][0]['document_id']} — übersprungen.")
            else:
                konflikte.append(
                    f"{key[0]} {schluessel}: Dokumente {je_liste[key][0]['document_id']} "
                    f"und {r['document_id']} widersprechen sich — KEINES gespeichert.")
                je_liste.pop(key)

        print("\nGelesen:", flush=True)
        for (jahrgang, schluessel), (r, _s, e) in sorted(je_liste.items()):
            jahre = sorted({z.year for z in e.zeilen})
            politisch = sorted({s.label for s in e.summen if s.typ == "liste"
                                and "nderungslist" not in s.label
                                and not s.label.startswith("Verw")})
            zusatz = f"  · politische Zeile: {', '.join(politisch)}" if politisch else ""
            mit_code = sum(1 for z in e.zeilen if z.produkt)
            print(f"  {jahrgang}  {schluessel:16} Dok. {r['document_id']}  "
                  f"{len(e.zeilen):>3} Positionen ({jahre[0]}–{jahre[-1]}), "
                  f"{mit_code} mit Investitionscode{zusatz}", flush=True)

        for titel, eintraege in (("Dubletten", dubletten),
                                 ("Widersprüche", konflikte),
                                 ("Nicht gelesen", risse)):
            if eintraege:
                print(f"\n{titel}:", flush=True)
                for satz in eintraege:
                    print(f"  {satz}", flush=True)

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.", flush=True)
            return {"gelesen": len(je_liste), "dubletten": len(dubletten),
                    "konflikte": len(konflikte), "risse": len(risse), "trocken": 1}

        positionen = 0
        for (jahrgang, schluessel), (r, _s, e) in sorted(je_liste.items()):
            positionen += store.save_haushalt_aenderungen_fhh(
                r["document_id"], schluessel, e,
                herkunft_fuer(r["label"], r["url"], r["document_id"]))
        print(f"\nGespeichert: {len(je_liste)} Liste(n), {positionen} Positionen.",
              flush=True)
        return {"gelesen": len(je_liste), "positionen": positionen,
                "dubletten": len(dubletten), "konflikte": len(konflikte),
                "risse": len(risse)}
    finally:
        store.close()


if __name__ == "__main__":
    main()
