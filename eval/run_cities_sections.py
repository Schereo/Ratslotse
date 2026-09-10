"""Wie gut schneidet der Splitter die Niederschriften? — ohne Modell, ohne Kosten.

Die Frage, die dieser Prüfstand beantwortet: **Wie viele Tagesordnungspunkte
einer Sitzung, für die eine Niederschrift vorliegt, bekommen ihren Abschnitt?**
Alles darunter ist entweder nicht öffentlich (steht dann zu Recht nicht im
öffentlichen Protokoll) oder eine Lücke in der Regel.

Er läuft gegen den **echten Bestand**, nicht gegen Fixtures — die halten
`tests/test_cities_protocol.py`. Deshalb braucht er eine gefüllte
`data/cities.sqlite` und sagt es, wenn sie fehlt.

    python eval/run_cities_sections.py
    python eval/run_cities_sections.py --stadt muenster --zeigen 3

**Gemessen am 10.09.2026** an 38 Niederschriften aus fünf Städten: 929 von
1.134 Tagesordnungspunkten = **82 %**. Je Stadt: Potsdam 87 %,
Braunschweig 86 %, Münster 83 %, Osnabrück 82 %, Magdeburg 78 %.

Zwei Messungen haben den Wert je um mehr als zehn Punkte gehoben, und beide
Fehler waren unsichtbar: Osnabrück rückt seine Nummern seit 2024 um ein
Leerzeichen ein (0 % statt 82 %), und fünf Protokolle liefen gegen den
Zeichen-Deckel der Textextraktion — abgeschnitten werden die HINTEREN
Punkte, und niemand vermisst, was nie dastand.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from council.cities.protocol import SPLITTER_VERSION, detect_layout, split_protocol
from council.cities.store import CitiesStore
from council.cities.text import EXTRACTOR, VERSION

#: Die Schranke wird gesetzt, wenn gemessen ist — nicht vorher geraten
#: (Regel 15 der Vorgängerpläne). Stand 10.09.2026: 87 % über alle Städte.
SCHRANKE = 0.75


def entdoppelt(punkte: list[dict]) -> list[tuple[str, str, str]]:
    """Denselben Punkt unter zwei Kennungen nur einmal zählen.

    Fünf der sechs Städte legen jeden Tagesordnungspunkt zweimal ab — einmal
    unter der Kennung, die die Sitzung vergibt (``…/meetings/14460#top-1``),
    einmal unter seiner eigenen (``…/agendaitems/284259``). Das ist ein
    eigener Befund und wird eigens behoben; hier würde er die Quote
    halbieren, ohne dass etwas fehlt.
    """
    gesehen: set[tuple[str, str]] = set()
    raus: list[tuple[str, str, str]] = []
    for p in punkte:
        nummer, name = (p["number"] or "").strip(), " ".join((p["name"] or "").split())
        if (nummer, name.lower()) in gesehen:
            continue
        gesehen.add((nummer, name.lower()))
        raus.append((p["id"], nummer, name))
    return raus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stadt", help="nur diese Stadt")
    ap.add_argument("--grenze", type=int, default=40, help="höchstens so viele Niederschriften")
    ap.add_argument("--zeigen", type=int, default=0, help="so viele Abschnitte je Stadt zeigen")
    args = ap.parse_args()

    pfad = Path(os.environ.get("CITIES_DB", "data/cities.sqlite"))
    if not pfad.exists():
        print(f"Keine Städte-Datenbank unter {pfad} — erst ernten "
              f"(scripts/cities_backfill.py) oder CITIES_DB setzen.")
        return 2

    main_store = CitiesStore(pfad)
    try:
        # Auch die schon geschnittenen: gemessen wird die REGEL, nicht der
        # Rückstand.
        alle = main_store.protocols_with_text(
            EXTRACTOR, VERSION, SPLITTER_VERSION, args.stadt, args.grenze,
            nur_offene=False)
        if not alle:
            print("Keine Niederschrift mit Text da. Erst `--stage fetch` mit "
                  "Protokollen laufen lassen (PR 31).")
            return 2

        je_stadt: dict[str, list[int]] = {}
        gezeigt: dict[str, int] = {}
        for zeile in alle:
            punkte = entdoppelt(main_store.agenda_items(zeile["meeting_id"]))
            if not punkte:
                continue
            abschnitte = split_protocol(zeile["text"], punkte)
            stadt = zeile["body_id"]
            werte = je_stadt.setdefault(stadt, [0, 0, 0])
            werte[0] += len(abschnitte)
            werte[1] += len(punkte)
            werte[2] += 1
            if gezeigt.get(stadt, 0) < args.zeigen and abschnitte:
                gezeigt[stadt] = gezeigt.get(stadt, 0) + 1
                a = abschnitte[0]
                print(f"  {stadt} {detect_layout(zeile['text'])}: "
                      f"{a.number} {a.title[:50]!r} -> {a.text[:70]!r}")

        print(f"\n{'Stadt':32} {'Abschnitte':>10} {'Punkte':>8} {'Quote':>7} {'Dok.':>5}")
        print("-" * 66)
        ganz = [0, 0, 0]
        for stadt, (ab, pu, dok) in sorted(je_stadt.items()):
            print(f"{stadt[:32]:32} {ab:10} {pu:8} {ab / pu:6.0%} {dok:5}")
            ganz = [ganz[0] + ab, ganz[1] + pu, ganz[2] + dok]
        quote = ganz[0] / ganz[1] if ganz[1] else 0.0
        print("-" * 66)
        print(f"{'zusammen':32} {ganz[0]:10} {ganz[1]:8} {quote:6.0%} {ganz[2]:5}")
        print(f"\nSchranke {SCHRANKE:.0%} — "
              f"{'bestanden' if quote >= SCHRANKE else 'NICHT bestanden'}")
        return 0 if quote >= SCHRANKE else 1
    finally:
        main_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
