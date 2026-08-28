#!/usr/bin/env python3
"""Die Änderungslisten zum Haushalt einlesen — EHH, Position für Position.

Liest die Anlagen, deren Label eine EHH-Änderungsliste des Kernhaushalts
benennt (``council/aenderungslisten.py: liste_aus_label``), lädt die PDFs aus
dem Ratsinformationssystem und speichert je Dokument die geprüften Positionen
samt der „Zusammenstellung der Veränderungen“. Jede Liste beweist sich dabei
selbst: Die Positionssummen müssen je Planjahr die Zusammenstellung treffen —
was nicht aufgeht, wird nicht gespeichert.

    python scripts/ingest_aenderungslisten.py --trockenlauf
    python scripts/ingest_aenderungslisten.py

VORAUSSETZUNG: ``pymupdf`` (Wortkoordinaten für die Spaltenzuordnung) — wie
die PDF-Renderer der OCR bewusst nicht in ``requirements.txt``; einmalig
``.venv/bin/pip install pymupdf`` auf der Ingest-Maschine.

WAS HIER EINGELESEN WIRD, sind die Listen der VERWALTUNG (Verw. I–III) und
die Beschluss-Dateien des Finanzausschusses. Die Änderungslisten der
Fraktionen liegen nicht im RIS (Tischvorlagen) — ihre SALDEN stehen aber in
den Beschluss-Dateien als eigene Zusammenstellungs-Zeile mit Urheber-Label
(„SPD/CDU/FDP  0 / −218.299“), und genau die landen hier mit im Bestand.
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

from council.aenderungslisten import (  # noqa: E402
    Ergebnis,
    ListenFehler,
    herkunft_fuer,
    lies_ehh_liste,
    liste_aus_label,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=45) as antwort:
        return antwort.read()


def _inhaltsgleich(a: Ergebnis, b: Ergebnis) -> bool:
    """Zwei Anlagen, ein Dokument? Die 2021er-Beschlussdatei liegt doppelt im
    Bestand (Dokumente 230011 und 230030) — verglichen wird der INHALT, nicht
    die Datei: gleiche Positionen, gleiche Summen."""
    def kern(e: Ergebnis):
        # `key=repr`, weil `thh`/`ertrag` None sein dürfen — nackte Tupel
        # mit None neben int lassen sich nicht sortieren.
        return (sorted(((z.jahr, z.lfd, z.thh, z.produkt, z.bezeichnung,
                         z.ertrag, z.aufwand) for z in e.zeilen), key=repr),
                sorted(((s.jahr, s.typ, s.label, s.ertraege, s.aufwendungen)
                        for s in e.summen), key=repr))
    return kern(a) == kern(b)


def main() -> dict:
    ap = argparse.ArgumentParser(description="EHH-Änderungslisten einlesen")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        anlagen = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT document_id, label, url FROM council_anlagen "
            "ORDER BY document_id")]
        kandidaten = [(r, liste_aus_label(r["label"])) for r in anlagen]
        kandidaten = [(r, schluessel) for r, schluessel in kandidaten if schluessel]
        print(f"{len(kandidaten)} EHH-Kandidat(en) unter {len(anlagen)} Anlagen.",
              flush=True)

        gelesen: list[tuple[dict, str, Ergebnis]] = []
        risse: list[str] = []
        for r, schluessel in kandidaten:
            try:
                pdf = _laden(r["url"])
                time.sleep(0.6)
                ergebnis = lies_ehh_liste(pdf)
            except ListenFehler as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): {fehler}")
                continue
            except OSError as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): "
                             f"Download fehlgeschlagen — {fehler}")
                continue
            gelesen.append((r, schluessel, ergebnis))

        # Je (Jahrgang, Liste) genau EIN Dokument — Dubletten aussortieren,
        # echte Widersprüche stehen lassen statt zu raten.
        je_liste: dict[tuple[int, str], tuple[dict, str, Ergebnis]] = {}
        dubletten: list[str] = []
        konflikte: list[str] = []
        for r, schluessel, ergebnis in gelesen:
            key = (ergebnis.jahrgang, schluessel)
            if key not in je_liste:
                je_liste[key] = (r, schluessel, ergebnis)
                continue
            if _inhaltsgleich(je_liste[key][2], ergebnis):
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
            jahre = sorted({z.jahr for z in e.zeilen})
            politisch = sorted({s.label for s in e.summen
                                if s.typ == "liste" and "nderungsliste" not in s.label})
            zusatz = f"  · politische Zeile: {', '.join(politisch)}" if politisch else ""
            print(f"  {jahrgang}  {schluessel:16} Dok. {r['document_id']}  "
                  f"{len(e.zeilen):>3} Positionen ({jahre[0]}–{jahre[-1]}){zusatz}",
                  flush=True)

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
            positionen += store.save_haushalt_aenderungen(
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
