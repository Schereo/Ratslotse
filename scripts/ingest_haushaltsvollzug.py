#!/usr/bin/env python3
"""Den Haushaltsvollzug einlesen — die vierteljährlichen Finanz- und
Leistungsberichte an den Ausschuss für Finanzen und Beteiligungen.

Liest die Anlagen, deren Label einen Finanz- und Leistungsbericht benennt
(`council/finanzquellen.py`, Schlüssel `budget_execution`), lädt die PDFs aus
dem Ratsinformationssystem und speichert je Bericht und Haushalt die beiden
Übersichtstabellen „Auswertung der Berichte zum …". Jede Tabelle beweist sich
dabei selbst: Die Spaltenbelegung wird gerechnet, jede Zeile rechnet sich vor,
und die dreizehn Teilhaushalte müssen die gedruckte Summenzeile ergeben — was
nicht aufgeht, wird nicht gespeichert.

    python scripts/ingest_haushaltsvollzug.py --trockenlauf
    python scripts/ingest_haushaltsvollzug.py

VORAUSSETZUNG: ``pymupdf`` (Wortkoordinaten für die Spaltenzuordnung) — wie
bei den Änderungslisten bewusst nicht in ``requirements.txt``; einmalig
``.venv/bin/pip install pymupdf`` auf der Ingest-Maschine.

DIESELBEN LABEL TRAGEN ANDERE BERICHTE. Unter „Finanz- und Leistungsbericht"
liegen im Bestand auch die Fassungen der Eigenbetriebe (EGH, Hafen) und die
Auszüge einzelner Fachausschüsse. Aussortiert werden sie nicht über das Label,
sondern am Dokument: Wer die stadtweite Übersichtstabelle mit dreizehn
Teilhaushalten und Summenzeile nicht führt, fällt still durch. Deshalb ist
„gelesen: 43 von 80 Kandidaten" hier der Sollzustand und kein Befund.
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

from council import finanzquellen  # noqa: E402
from council.budget_execution import (  # noqa: E402
    VollzugFehler,
    herkunft_fuer,
    lies_vollzugsbericht,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=90) as answer:
        return answer.read()


def _kern(bericht) -> tuple:
    """Der Inhalt eines Berichts, vergleichbar gemacht.

    Zwei Anlagen können dieselbe Tabelle tragen (dieselbe Datei, ein zweites
    Mal hochgeladen). Verglichen wird deshalb der INHALT und nicht die Datei —
    sonst stünde jede Doppelablage als Widerspruch im Protokoll. ``key=repr``,
    weil leere Zellen als ``None`` neben Zahlen stehen und sich nackt nicht
    sortieren lassen."""
    return tuple(sorted(
        ((p.sub_budget, p.kind, p.budgeted, p.forecast, p.deviation, p.carryover)
         for p in bericht.positionen), key=repr))


def _summenzeile(bericht) -> str:
    """Die Kernzahl eines Berichts, so wie sie im Ausschuss vorgetragen wird."""
    summe = bericht.summe
    ergebnis = summe.get("result")
    if ergebnis is None or ergebnis.budgeted is None or ergebnis.forecast is None:
        return "ohne Summenzeile"
    return (f"Plan {ergebnis.budgeted / 1e6:>8.1f} Mio. € → Prognose "
            f"{ergebnis.forecast / 1e6:>8.1f} Mio. €")


def main() -> dict:
    ap = argparse.ArgumentParser(description="Haushaltsvollzug einlesen")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--nur-fehlende", action="store_true",
                    help="Nur Stichtage holen, die noch nicht im Bestand stehen "
                         "— spart die Downloads der schon gelesenen Berichte.")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    quelle = finanzquellen.QUELLEN["budget_execution"]
    store = CouncilStore(Path(args.db))
    try:
        kandidaten = quelle.dokumente(store, "document_id, label, url")
        kandidaten.sort(key=lambda r: r["document_id"])
        vorhanden = quelle.vorhandene(store, args.nur_fehlende)
        print(f"{len(kandidaten)} Anlage(n) mit einem Bericht-Label; "
              f"{len(vorhanden)} Einheit(en) schon im Bestand.", flush=True)

        # Je Einheit das Dokument mit der KLEINSTEN document_id — das ist die
        # Anlage der Vorlage selbst. Dieselbe Tabelle liegt teils ein zweites
        # Mal unter einem anderen Tagesordnungspunkt; welche Fassung gewinnt,
        # soll nicht die Sortierung der Kandidaten entscheiden.
        je_einheit: dict[tuple, tuple[dict, object]] = {}
        risse: list[str] = []
        dubletten: list[str] = []
        konflikte: list[str] = []
        ohne_tabelle = 0
        for r in kandidaten:
            try:
                pdf = _laden(r["url"])
                time.sleep(0.6)
                lesung = lies_vollzugsbericht(pdf)
            except VollzugFehler as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): {fehler}")
                continue
            except OSError as fehler:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): "
                             f"Download fehlgeschlagen — {fehler}")
                continue
            for satz in lesung.risse:
                risse.append(f"{r['document_id']} ({r['label'][:50]}): {satz}")
            if not lesung.berichte:
                ohne_tabelle += 1
                continue
            for bericht in lesung.berichte:
                einheit = (bericht.budget_year, bericht.as_of, bericht.budget)
                if einheit in vorhanden:
                    continue
                if einheit not in je_einheit:
                    je_einheit[einheit] = (r, bericht)
                    continue
                erste = je_einheit[einheit][1]
                if _kern(erste) == _kern(bericht):
                    dubletten.append(
                        f"{einheit[1]} {einheit[2]}: Dokument {r['document_id']} "
                        f"ist inhaltsgleich mit "
                        f"{je_einheit[einheit][0]['document_id']} — übersprungen.")
                else:
                    konflikte.append(
                        f"{einheit[1]} {einheit[2]}: Dokumente "
                        f"{je_einheit[einheit][0]['document_id']} und "
                        f"{r['document_id']} widersprechen sich — KEINES "
                        "gespeichert. Das ist eine Entscheidung für einen "
                        "Menschen, nicht für einen Lauf.")
                    je_einheit.pop(einheit)

        if je_einheit:
            print("\nGelesen:", flush=True)
            for einheit, (r, bericht) in sorted(je_einheit.items()):
                print(f"  {einheit[1]}  {einheit[2]:6}  Dok. {r['document_id']}  "
                      f"[{bericht.plan_basis}]  {_summenzeile(bericht)}", flush=True)

        print(f"\n{ohne_tabelle} Anlage(n) ohne stadtweite Übersichtstabelle "
              "(Eigenbetriebe, Fachausschuss-Auszüge) — das ist der "
              "Sollzustand, s. Modulkopf.", flush=True)

        for titel, eintraege in (("Dubletten", dubletten),
                                 ("Widersprüche", konflikte),
                                 ("Nicht gelesen", risse)):
            if eintraege:
                print(f"\n{titel}:", flush=True)
                for satz in eintraege:
                    print(f"  {satz}", flush=True)

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.", flush=True)
            return {"gelesen": len(je_einheit), "ohne_tabelle": ohne_tabelle,
                    "dubletten": len(dubletten), "konflikte": len(konflikte),
                    "risse": len(risse), "trocken": 1}

        zeilen = 0
        for einheit, (r, bericht) in sorted(je_einheit.items()):
            zeilen += store.save_haushaltsvollzug(bericht, herkunft_fuer(
                bericht, document_id=r["document_id"], label=r["label"],
                url=r["url"]))

        luecken = store.herkunft_luecken()
        print(f"\nGespeichert: {len(je_einheit)} Tabelle(n), {zeilen} Zeilen.",
              flush=True)
        if luecken:
            print(f"Zeilen ohne Herkunft: {luecken}", flush=True)
        return {"gelesen": len(je_einheit), "zeilen": zeilen,
                "ohne_tabelle": ohne_tabelle, "dubletten": len(dubletten),
                "konflikte": len(konflikte), "risse": len(risse),
                "befund": konflikte + risse}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_haushaltsvollzug", main)
