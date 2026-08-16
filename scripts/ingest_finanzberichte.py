#!/usr/bin/env python3
"""Jahresabschlüsse und Teilhaushalts-Pläne aus dem eigenen Bestand einlesen.

Beide Dokumenttypen hängen als Anlagen an Ratsvorlagen und liegen mit
Volltext in ``council_anlagen`` — der Protokoll-Scraper zieht sie ohnehin.
Dieses Skript liest sie aus, ohne etwas herunterzuladen:

- **Jahresabschluss** → ``council_ergebnisrechnung``: Ansatz und Ergebnis je
  Posten, also „geplant gegen tatsächlich", plus die Erträge nach Arten —
  zweimal: für die Kernverwaltung gesamt und je Teilhaushalt. Die
  Teilhaushalts-Ebene wird nur gespeichert, wenn ihre Summe zur
  Gesamtrechnung passt (``finanzberichte.summenprobe``).
- **Teilhaushalts-Pläne (THH)** → ``council_produkte``: was einzelne Aufgaben
  kosten, mit Produktnummer und Amt.

Beide Parser verlangen eine im Dokument selbst dokumentierte Rechenprobe
(siehe ``council/finanzberichte.py``); was sie nicht besteht, wird
übersprungen und am Ende als übersprungen ausgewiesen. Läuft einmal je neuem
Jahrgang, es gibt keinen Cron::

    python scripts/ingest_finanzberichte.py
    python scripts/ingest_finanzberichte.py --nur jahresabschluss
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import finanzberichte  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _jahresabschluesse(store: CouncilStore) -> dict:
    """Gesamtdokumente der Jahresabschlüsse — nicht die Rechenschaftsberichte
    und nicht die Prüfberichte, die dieselbe Jahreszahl im Titel tragen.

    Zwei Durchgänge: erst alle Jahrgänge lesen und prüfen, dann speichern.
    Die Vorjahres-Kette lässt sich nur über Dokumentgrenzen hinweg prüfen —
    dafür müssen der Jahrgang und sein Nachbar gelesen vorliegen."""
    rows = store._conn.execute(
        "SELECT label, url, raw_text FROM council_anlagen "
        "WHERE label LIKE '%Jahresabschluss%' AND n_pages > 100 "
        "  AND label NOT LIKE '%Rechenschaft%' AND label NOT LIKE '%Schlussbericht%' "
        "ORDER BY label").fetchall()

    gelesen: dict[int, dict] = {}
    uebersprungen = vorzeichen_repariert = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        jahr = int(m.group(1))
        text = r["raw_text"] or ""
        posten = finanzberichte.parse_ergebnisrechnung(text, jahr)
        # Ohne beide Summenzeilen ist der Jahrgang für „Plan gegen Ist" wertlos.
        if {p["nr"] for p in posten} < {12, 20}:
            print(f"  {jahr}: nur {len(posten)} Posten, keine Summenzeilen — übersprungen",
                  file=sys.stderr)
            uebersprungen += 1
            continue
        # Innerhalb der Tabelle: 12 − 20 = 21, in Plan und Ist.
        ok, warum = finanzberichte.strukturprobe(posten)
        if not ok:
            print(f"  {jahr}: Strukturprobe gerissen ({warum}) — übersprungen", file=sys.stderr)
            uebersprungen += 1
            continue
        repariert = sum(1 for p in posten if p.get("vorzeichen_repariert"))
        if repariert:
            # Zählen und melden: Wird das häufiger, stimmt etwas anderes nicht.
            print(f"  {jahr}: {repariert} Zeile(n) mit fehlendem Minuszeichen im Dokument — "
                  f"Betrag passte auf den Cent, Vorzeichen ergänzt", file=sys.stderr)
            vorzeichen_repariert += repariert
        gelesen[jahr] = {"posten": posten, "text": text,
                         "label": r["label"], "url": r["url"]}

    # Vorjahres-Kette: Das Ist eines Jahres steht im Folgejahrgang noch einmal.
    # Ein gerissenes Glied verrät nicht, welche Seite falsch ist — also fallen
    # beide raus. In der Praxis schließen alle Glieder.
    kette = finanzberichte.vorjahreskette({j: v["posten"] for j, v in gelesen.items()})
    verdaechtig: set[int] = set()
    for jahr, folge, warum in kette:
        print(f"  Vorjahres-Kette {jahr}→{folge} gerissen: {warum} — beide Jahrgänge "
              f"werden nicht gespeichert", file=sys.stderr)
        verdaechtig |= {jahr, folge}
    glieder = sum(1 for j in gelesen if j + 1 in gelesen) * 2

    mit_thh = verworfen = gruende_gesamt = 0
    for jahr in sorted(gelesen):
        if jahr in verdaechtig:
            uebersprungen += 1
            continue
        v = gelesen[jahr]
        posten, label, url = v["posten"], v["label"], v["url"]
        store.save_ergebnisrechnung(jahr, posten, label, url)
        e = next(p for p in posten if p["nr"] == 12)
        a = next(p for p in posten if p["nr"] == 20)
        arten = sorted({p["plan_art"] for p in posten})
        print(f"  {jahr}: {len(posten)} Posten · Erträge {e['plan']/1e6:.1f} → "
              f"{e['ergebnis']/1e6:.1f} · Aufwendungen {a['plan']/1e6:.1f} → "
              f"{a['ergebnis']/1e6:.1f} · Bezug {'/'.join(arten)}")
        if a["plan"] != a["ansatz"] or e["plan"] != e["ansatz"]:
            print(f"      ursprünglicher Ansatz: Erträge {e['ansatz']/1e6:.1f} · "
                  f"Aufwendungen {a['ansatz']/1e6:.1f}")

        # Zweite Ebene: dieselbe Rechnung je Teilhaushalt. Sie wird nur
        # übernommen, wenn ihre Summe zur Gesamtrechnung passt — in Plan UND
        # Ist. Sonst wurde für einen Teilhaushalt die falsche (in sich
        # stimmige) Tabelle gelesen, was zeilenweise nicht auffällt.
        thh = finanzberichte.parse_teilergebnisrechnungen(v["text"], jahr)
        if thh:
            passt, abweichung = finanzberichte.summenprobe(thh, posten)
            if not passt:
                print(f"    Teilhaushalte verworfen: Summe weicht um {abweichung*100:.1f} % "
                      f"von der Gesamtrechnung ab", file=sys.stderr)
                verworfen += 1
            else:
                for x in thh:
                    store.save_ergebnisrechnung(jahr, x["posten"], label, url,
                                                thh_nr=x["thh_nr"], thh_name=x["thh_name"])
                print(f"    + {len(thh)} Teilhaushalte "
                      f"(Summenprobe {abweichung*100:.2f} % Abweichung)")
                mit_thh += 1

        # Das „Warum": Abschnitt 6.3.1 je Posten. Eintrittskarte ist der
        # Abgleich mit der Tabellenzeile — Betrag und Prozentsatz stehen in
        # der Überschrift des Blocks und müssen beide passen.
        roh = finanzberichte.parse_abweichungsgruende(v["text"], jahr)
        angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(roh, posten)
        for grund in abgelehnt:
            print(f"    Erläuterung verworfen — {grund}", file=sys.stderr)
        if angenommen:
            store.save_abweichungsgruende(jahr, angenommen, label, url)
            gruende_gesamt += len(angenommen)
            print(f"    + {len(angenommen)} Erläuterungen zu Abweichungen")

    return {"jahre": len(gelesen) - len(verdaechtig), "uebersprungen": uebersprungen,
            "jahre_mit_teilhaushalten": mit_thh, "thh_verworfen": verworfen,
            "kettenglieder_geprueft": glieder, "kette_gerissen": len(kette),
            "vorzeichen_repariert": vorzeichen_repariert,
            "abweichungsgruende": gruende_gesamt}


def _pruefberichte(store: CouncilStore) -> dict:
    """Schlussberichte des Rechnungsprüfungsamts als Fundstelle merken —
    nur Verweis, kein Inhalt („Das Rechnungsprüfungsamt hat diesen Abschluss
    geprüft")."""
    rows = store._conn.execute(
        "SELECT label, url, n_pages, raw_text FROM council_anlagen "
        "WHERE label LIKE '%chlussbericht%' OR raw_text LIKE 'Schlussbericht%'").fetchall()
    gefunden = unlesbar = 0
    for r in rows:
        treffer = finanzberichte.pruefbericht_aus_anlage(r["label"], r["raw_text"])
        if not treffer:
            continue
        store.save_pruefbericht(treffer["jahr"], r["label"], r["url"],
                                r["n_pages"], treffer["lesbar"])
        gefunden += 1
        hinweis = "" if treffer["lesbar"] else "  (Volltext unbrauchbar, nur Verweis)"
        print(f'  {treffer["jahr"]}: {r["n_pages"]} Seiten{hinweis}')
        unlesbar += 0 if treffer["lesbar"] else 1
    return {"pruefberichte": gefunden, "pruefberichte_ohne_text": unlesbar}


def _teilhaushalte(store: CouncilStore) -> dict:
    rows = store._conn.execute(
        "SELECT label, url, raw_text FROM council_anlagen "
        "WHERE label LIKE '%THH%' AND n_pages > 40 ORDER BY label").fetchall()
    je_jahr: dict[int, int] = {}
    ohne = 0
    for r in rows:
        produkte = finanzberichte.parse_teilergebnishaushalt(r["raw_text"] or "")
        if not produkte:
            ohne += 1
            continue
        for jahr in {p["jahr"] for p in produkte}:
            teil = [p for p in produkte if p["jahr"] == jahr]
            store.save_produkte(jahr, teil, r["label"], r["url"])
            je_jahr[jahr] = je_jahr.get(jahr, 0) + len(teil)
    for jahr in sorted(je_jahr):
        print(f"  {jahr}: {je_jahr[jahr]} Produkt-Zeilen")
    return {"dokumente": len(rows), "ohne_treffer": ohne,
            "produkte": sum(je_jahr.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description="Jahresabschlüsse und Teilhaushalte einlesen")
    ap.add_argument("--nur", choices=["jahresabschluss", "teilhaushalte"], default=None)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    ergebnis: dict = {}
    try:
        if args.nur != "teilhaushalte":
            print("Jahresabschlüsse (Ergebnisrechnung):")
            ergebnis |= _jahresabschluesse(store)
            print("Schlussberichte des Rechnungsprüfungsamts:")
            ergebnis |= _pruefberichte(store)
        if args.nur != "jahresabschluss":
            print("Teilhaushalte (Produktebene):")
            ergebnis |= _teilhaushalte(store)
    finally:
        store.close()
    print(f"Fertig: {ergebnis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
