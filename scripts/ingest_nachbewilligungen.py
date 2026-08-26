#!/usr/bin/env python3
"""Nachbewilligungen nach § 117 NKomVG einlesen — beide Quellen.

Zwei Bestände, die dieselbe Sache aus zwei Richtungen beschreiben:

1. **Das Ratsinformationssystem** — jede Vorlage, die eine über- oder
   außerplanmäßige Bewilligung beantragt, seit 2018. Was der Rat beschlossen
   hat, mit Link auf die vorhandene Beschluss-Seite.
2. **Kapitel 3 der Rechenschaftsberichte** (Anlage zum Jahresabschluss,
   § 128 NKomVG) — dieselben Fälle, aber nach den **vier Entscheidungswegen**
   getrennt: Rat, Oberbürgermeister, Fachdienst 200 per Haushaltsvermerk,
   Eilentscheidungen. Vorhanden für 2022, 2023, 2024.

Beide werden gebraucht, und das ist der Punkt: Die Gesamtsumme stieg von
26,97 über 40,24 auf 57,49 Mio. €, der Anteil mit Ratsbeschluss fiel von 88
auf 73 %. Wer nur den ersten Bestand zeigt, zeigt eine schrumpfende Teilmenge,
als wäre sie das Ganze.

Nichts wird hier geladen — beide Quellen liegen bereits im Bestand
(``council_vorlagen.raw_text`` und ``council_anlagen.raw_text``).

**Reihenfolge ist Pflicht, nicht Geschmack.** Die drei Rechenschaftsberichte
liegen im Bestand als Anlage mit ``status='listed'`` und **leerem**
``raw_text``: Sie sind verzeichnet, aber nie geladen worden. Wer dieses
Skript ohne Vorlauf startet, bekommt die RIS-Serie und **kein einziges**
Kapitel 3 — also genau die halbe Wahrheit, gegen die dieser Block gebaut ist
(nur die Ratsbeschlüsse, ohne den Nenner, zu dem sie gehören). Deshalb:

    python scripts/backfill_anlagen_texte.py --nur-finanz --retry-failed
    python scripts/ingest_nachbewilligungen.py

Der Ops-Workflow (``.github/workflows/ops-finanzdaten-ingest.yml``) hält
diese Reihenfolge ein. Fehlt der Text trotzdem, sagt der Lauf es je Jahrgang
und schreibt den Jahrgang nicht — eine leere Zeile wäre schlimmer als keine.

Aufruf::

    python scripts/ingest_nachbewilligungen.py
    python scripts/ingest_nachbewilligungen.py --trockenlauf   # nur zeigen
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import herkunft as h  # noqa: E402
from council import nachbewilligungen as nb  # noqa: E402
from council.store import CouncilStore  # noqa: E402

#: Die Rechenschaftsberichte mit Kapitel 3 im Bestand. Der Schlüssel ist das
#: **Haushaltsjahr**, nicht das Jahr der Vorlage — der Bericht für 2024 ist
#: eine Anlage zur Vorlage 25/0391.
#:
#: DIE FÜNF ÄLTEREN (2017–2021: 192336, 205649, 219465, 238770, 250437) STEHEN
#: HIER NICHT — und das ist seit dem 18.08.2026 eine Messung und keine
#: Vermutung mehr. Bis dahin hatten sie keinen Volltext (das Label-Muster der
#: Finanzquellen kannte „Rechenschaftsbericht" nicht, s. council/
#: finanzquellen.py); der Vermerk an dieser Stelle nahm an, sie kämen dazu,
#: „sobald der Backfill sie erfasst — die Struktur des Kapitels ist seit 2022
#: unverändert".
#:
#: Sie ist es nicht. Mit Volltext gegen ``kapitel3`` gehalten, findet der
#: Parser dort nur **einen bis drei** der vier Entscheidungswege, und die
#: Spaltenprobe reißt in **jedem** der fünf Jahrgänge (die investive Spalte um
#: 0,55 bis 0,92 Mio. €). Das Kapitel gibt es, sein Tabellenlayout ist ein
#: anderes. Wer die Reihe verlängern will, braucht dafür eigene Arbeit — bis
#: dahin bleibt sie bei 2022–2024, statt Zahlen zu zeigen, die ihre eigene
#: Probe nicht bestehen.
BERICHTE: dict[int, int] = {
    2022: 265441,
    2023: 280862,
    2024: 295295,
}

#: Wie das Dokument im Beleg heißen soll.
BERICHT_LABEL = ("Rechenschaftsbericht zum Jahresabschluss {jahr} der "
                 "Kernverwaltung und ihrer nicht rechtsfähigen Stiftungen")


def _serie(store: CouncilStore, trocken: bool) -> dict:
    """Die RIS-Serie lesen, prüfen, schreiben."""
    vorlagen, beschluesse = store.nachbewilligungs_vorlagen()
    volltexte = {v["vorlage_nr"]: v.get("raw_text") or "" for v in vorlagen}
    serie = nb.aus_vorlagen(vorlagen, beschluesse)
    if not serie:
        print("  keine Nachbewilligungs-Vorlagen im Bestand")
        return {"vorlagen": 0}

    zeilen: list[dict] = []
    for b in serie:
        # Der maßgebliche Beschluss ist der erste — `nachbewilligungs_vorlagen`
        # liefert sie bereits in der Ordnung „Rat zuerst, dann die jüngste
        # Sitzung" (`CouncilStore._BESCHLUSS_ORDNUNG`).
        stationen = beschluesse.get(b.vorlage_nr, [])
        fuehrend = next((d for d in stationen if d.get("outcome") == "angenommen"),
                        stationen[0] if stationen else None)
        zeilen.append({
            "vorlage_nr": b.vorlage_nr, "jahr": b.jahr, "titel": b.titel,
            "art": b.art, "kategorie": b.kategorie, "betrag": b.betrag,
            "betrag_quelle": b.betrag_quelle, "beschlossen": b.beschlossen,
            "im_rat": b.im_rat, "ratsentscheidung": b.ratsentscheidung,
            "beschluss_id": (fuehrend or {}).get("id"),
            "gremien": sorted({str(d.get("committee") or "") for d in stationen}),
            "volltextprobe": nb.probe_volltext(b, volltexte.get(b.vorlage_nr)),
        })

    einzel = [z for z in zeilen if z["art"] != nb.ART_SCHWELLE]
    aus_titel = sum(1 for z in einzel if z["betrag_quelle"] == "titel")
    aus_text = sum(1 for z in einzel if z["betrag_quelle"] == "beschlussvorschlag")
    ohne = [z["vorlage_nr"] for z in einzel if z["betrag_quelle"] is None]
    geprueft = sum(1 for z in zeilen if z["volltextprobe"])
    quote = (aus_titel + aus_text) / len(einzel) * 100 if einzel else 0.0

    print(f"  {len(zeilen)} Vorlagen · Betrag aus dem Titel {aus_titel}, "
          f"aus dem Beschlussvorschlag {aus_text} → {quote:.1f} %")
    if ohne:
        print(f"  ohne Betrag: {', '.join(ohne)}")
    print(f"  Volltextprobe bestanden: {geprueft} von {aus_titel}")

    if trocken:
        for j, e in nb.jahressummen(serie).items():
            print(f"    {j}: {e['summe']:>15,.2f} € ({e['faelle']} Fälle)")
        return {"vorlagen": len(zeilen), "trocken": True}

    nachweis = (f"{aus_titel} von {len(einzel)} Beträgen stehen im Titel, "
                f"{aus_text} im Beschlussvorschlag der Vorlage; der Titelbetrag "
                f"ist in {geprueft} von {aus_titel} Fällen im Volltext "
                f"wiedergefunden worden")
    store.save_nachbewilligungen(zeilen, h.Herkunft(
        art="ris",
        url="https://www.oldenburg-kreis.de/bi/",
        label="Vorlagen im Ratsinformationssystem der Stadt Oldenburg",
        fundstelle="Titel und Beschlussvorschlag der Vorlage",
        probe=nb.PROBE_VOLLTEXT,
        stand=f"Haushaltsjahre {min(z['jahr'] for z in zeilen if z['jahr'])}"
              f"–{max(z['jahr'] for z in zeilen if z['jahr'])}",
        probe_ergebnis=nachweis))
    return {"vorlagen": len(zeilen), "mit_betrag": aus_titel + aus_text,
            "ohne_betrag": len(ohne)}


def _berichte(store: CouncilStore, serie: list[nb.Bewilligung],
              trocken: bool) -> dict:
    """Kapitel 3 der Rechenschaftsberichte lesen, prüfen, schreiben."""
    gelesen = 0
    widersprueche: list[str] = []
    for jahr, dokument in sorted(BERICHTE.items()):
        text = store.anlage_text(dokument)
        if not text:
            print(f"  {jahr}: kein Volltext zu Dokument {dokument} — "
                  f"backfill_anlagen_texte.py --nur-finanz")
            continue
        kap = nb.kapitel3(text, jahr)
        if not kap:
            print(f"  {jahr}: Kapitel 3 nicht lesbar (Dokument {dokument})")
            continue
        probe = nb.probe_tabelle(kap)
        abgleich = nb.probe_ratsabgleich(
            serie, kap, nb.vorlagen_im_kapitel(text))
        rat = kap.kanal("rat")
        print(f"  {jahr}: {kap.gesamt:>15,.2f} € gesamt · Rat "
              f"{rat.betrag:>15,.2f} € ({kap.rats_anteil:.1f} %) · "
              f"{len(kap.kanaele)} Wege")
        print(f"        Tabellenprobe: {probe.als_text()}")
        print(f"        Ratsabgleich:  {abgleich.als_text()}")
        if not probe.bestanden:
            widersprueche.append(f"{jahr}: {probe.als_text()}")
        if trocken:
            continue
        # Beide Proben stehen an der Herkunft — auch die gerissene. Eine
        # Zeile, deren Probe nicht aufging, ist keine Zeile ohne Probe.
        store.save_nachbewilligung_jahr(
            {"jahr": jahr,
             "summe_konsumtiv": kap.summe_konsumtiv,
             "summe_investiv": kap.summe_investiv,
             "text_gesamt": kap.text_gesamt,
             "verpflichtungen_betrag": kap.verpflichtungen_betrag,
             "probe_ok": probe.bestanden,
             "probe_text": probe.als_text()},
            [{"kanal": k.schluessel, "label": k.label,
              "anzahl_konsumtiv": k.anzahl_konsumtiv,
              "betrag_konsumtiv": k.betrag_konsumtiv,
              "anzahl_investiv": k.anzahl_investiv,
              "betrag_investiv": k.betrag_investiv} for k in kap.kanaele],
            h.Herkunft(
                art="ris", dokument_id=dokument,
                label=BERICHT_LABEL.format(jahr=jahr),
                fundstelle="Kapitel 3 — Über- und außerplanmäßige "
                           "Aufwendungen und Auszahlungen",
                probe=[nb.PROBE_TABELLE, nb.PROBE_RAT],
                stand=f"Haushaltsjahr {jahr}",
                probe_ergebnis=f"{probe.als_text()} {abgleich.als_text()}"))
        gelesen += 1
    return {"berichte": gelesen, "widersprueche": len(widersprueche)}


def main() -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=os.getenv("COUNCIL_DB", "data/council.sqlite"))
    p.add_argument("--trockenlauf", action="store_true",
                   help="lesen und zeigen, nichts schreiben")
    args = p.parse_args()

    store = CouncilStore(args.db)
    try:
        print("Nachbewilligungen aus dem Ratsinformationssystem:")
        ergebnis = _serie(store, args.trockenlauf)

        # Für den Abgleich wird die Serie noch einmal als Objekte gebraucht —
        # aus derselben Lesung, damit Probe und Bestand dasselbe meinen.
        vorlagen, beschluesse = store.nachbewilligungs_vorlagen()
        serie = nb.aus_vorlagen(vorlagen, beschluesse)

        print("Rechenschaftsberichte, Kapitel 3:")
        ergebnis |= _berichte(store, serie, args.trockenlauf)

        if not args.trockenlauf:
            store.herkunft_aufraeumen()
            luecken = {t: n for t, n in store.herkunft_luecken().items()
                       if t.startswith("council_nachbewilligung")}
            if luecken:
                print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}",
                      file=sys.stderr)
                ergebnis["herkunft_luecken"] = sum(luecken.values())
    finally:
        store.close()
    return ergebnis


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_nachbewilligungen", main)
