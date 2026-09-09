#!/usr/bin/env python3
"""Sind die zwanzig obersten Einträge zwanzig, die jemand sehen will?

**Der Maßstab, der bisher fehlte.** ``run_cities_fit.py`` misst, ob ein
Urteil stimmt. ``run_cities_evidence.py`` misst, ob der Beleg gefunden wird.
``run_cities_effort.py`` misst die Aufwandsklasse. Keiner von ihnen misst
die **Liste** — und die Liste ist das Produkt. Man kann jedes Einzelurteil
verbessern und die Liste dabei verschlechtern; ohne diese Zahl merkt es
niemand.

```bash
python eval/build_cities_list_cases.py     # Kandidaten herausschreiben
#   … `on_list` von Hand füllen …
python eval/run_cities_list.py             # ohne Modell, Sekunden, 0 $
python eval/run_cities_list.py --zeigen    # was oben steht und nicht hingehört
```

**Präzision@20, nicht Trefferquote.** Wer die Liste liest, liest den Anfang;
was auf Platz 300 steht, sieht niemand. Die Frage ist deshalb nicht „wie
viele gute Ideen sind irgendwo drin", sondern „wie viele der ersten zwanzig
sind gut".

**Die Schranken stehen erst nach der ersten Messung.** Sie aus dem Bauch zu
setzen wäre genau der Fehler, den dieses Projekt viermal gemacht hat: Der
Maßstab war das Problem, nicht das Modell. Bis dahin meldet der Lauf die
Zahl und nichts weiter.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

FAELLE = WURZEL / "eval" / "cases_cities_list.json"

#: Ab wann die Liste als gut gilt — `None` heißt „noch nicht gesetzt".
#: Wer sie setzt, schreibt die gemessene Zahl daneben und das Datum.
SCHWELLE_P20: float | None = None
SCHWELLE_P50: float | None = None


def lade() -> list[dict]:
    if not FAELLE.exists():
        print(f"{FAELLE.relative_to(WURZEL)} gibt es nicht. Erst:\n"
              "  python eval/build_cities_list_cases.py", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def praezision(faelle: list[dict], k: int) -> tuple[float, int, int]:
    """``(Anteil, geurteilt, davon gut)`` unter den ersten ``k``.

    Ungeurteilte zählen NICHT als schlecht — sie zählen gar nicht. Ein
    halbgefülltes Golden Set soll eine ehrliche Teilzahl liefern, keine
    falsche schlechte.
    """
    oben = faelle[:k]
    geurteilt = [z for z in oben if z.get("on_list") is not None]
    gut = [z for z in geurteilt if z["on_list"]]
    return (len(gut) / len(geurteilt) if geurteilt else 0.0,
            len(geurteilt), len(gut))


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--zeigen", action="store_true",
                   help="die abgelehnten Einträge der ersten fünfzig auflisten — "
                        "dort steht, was als Nächstes zu tun ist")
    a = p.parse_args()

    faelle = lade()
    offen = sum(1 for z in faelle if z.get("on_list") is None)
    print(f"{len(faelle)} Kandidaten, {len(faelle) - offen} geurteilt, {offen} offen.\n")
    if offen == len(faelle):
        print("Noch kein einziges Urteil — es gibt nichts zu messen.")
        print("Zu füllen ist je Eintrag `on_list` (true/false) und `why`.")
        return 2

    for k in (20, 50, len(faelle)):
        anteil, n, gut = praezision(faelle, k)
        schwelle = {20: SCHWELLE_P20, 50: SCHWELLE_P50}.get(k)
        marke = "" if schwelle is None else (
            "  ✓" if anteil >= schwelle else f"  ✗ (Schwelle {schwelle:.0%})")
        print(f"  Präzision@{k:<4} {anteil:5.0%}   ({gut} von {n} geurteilt){marke}")

    if a.zeigen:
        schlecht = [z for z in faelle[:50] if z.get("on_list") is False]
        print(f"\n{len(schlecht)} der ersten fünfzig gehören nicht auf die Liste:")
        for z in schlecht:
            print(f"  [{z['cities']}] {z['body_id'][:11]:12} "
                  f"{(z.get('instrument') or z['name'])[:56]}")
            if z.get("why"):
                print(f"        {z['why'][:78]}")

    if SCHWELLE_P20 is None:
        print("\nKeine Schranke gesetzt — die erste Messung legt sie fest.")
        return 0
    p20, _, _ = praezision(faelle, 20)
    p50, _, _ = praezision(faelle, 50)
    schlecht = p20 < SCHWELLE_P20 or (SCHWELLE_P50 is not None and p50 < SCHWELLE_P50)
    print("\n" + ("NICHT bestanden." if schlecht else "Bestanden."))
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main())
