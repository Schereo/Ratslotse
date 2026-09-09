#!/usr/bin/env python3
"""Zwei Einbettungs-Modelle am Städte-Speicher gegeneinander messen.

**Warum das ein Skript ist und kein einmaliger Versuch.** Der Speicher hält
Vektoren und Nachbarschaften je Modell getrennt (``chunk_embeddings``,
``object_embeddings``, ``neighbors`` sind alle auf ``(…, model)`` eindeutig) —
genau damit ein besseres Modell neben dem heutigen liegen kann und ein Eval
beide vergleicht, bevor eins gewinnt. Ohne ein Werkzeug dafür bleibt die
Möglichkeit ungenutzt.

**Drei Maße, und nur zwei davon entscheiden.**

1. *Die Verteilung der Nähe.* Sie entscheidet nichts, erklärt aber alles: Ein
   Modell, das jede Kante auf 0,85 hebt, hat nicht mehr gefunden, sondern nur
   die Skala verschoben — und macht damit jede Schwelle wertlos, die auf einem
   anderen Modell geeicht wurde.
2. *Die zwölf Stichprobenfälle* aus ``docs/bewertung-staedte-speicher.md``: Wie
   viele der drei besten Treffer sind übertragbar und über der Schwelle?
3. *Das Golden Set von ``fit``*: Findet das Modell den Oldenburger Beleg, den
   ein Mensch als den richtigen bezeichnet hat, und auf welchem Rang?

```bash
# Modell B einbetten (dauert Minuten, braucht fastembed)
python scripts/cities_modellvergleich.py --einbetten --modell <name>
# und dann vergleichen
python scripts/cities_modellvergleich.py --modell <name>
```

**Gemessen am 08.09.2026** über 16.585 Papiere, A = das heutige
``paraphrase-multilingual-MiniLM-L12-v2`` (384 Dimensionen), B =
``paraphrase-multilingual-mpnet-base-v2`` (768):

| Maß | A | B |
|---|---:|---:|
| übertragbare Treffer in den zwölf Fällen | **18** | 14 |
| erwarteter Beleg unter den fünf nächsten | **19/23** | 12/23 |
| Kanten über 0,85 (von ~46.000) | 233 | 20.523 |

**A bleibt.** B findet weniger von dem, was ein Mensch als richtig bezeichnet
hat, und seine Nähe-Werte drängen sich alle im oberen Band — die Schwelle
0,70, die aus dem Median zweier beliebiger Verwaltungstexte stammt, trennt
dort nichts mehr. Ein größeres Modell ist hier also nicht besser, sondern nur
größer.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402

#: Die zwölf Fälle aus der Bewertung, mit dem Urteil von Hand daneben.
STICHPROBE = {
    28119: "gut", 28300: "Gattung", 28070: "gut", 28038: "schwach",
    28293: "gut", 27983: "Gattung", 28291: "gut", 29772: "gut",
    28403: "Gattung", 28610: "gemischt", 28229: "Gattung", 29953: "gut",
}
USABLE = ("adaptable", "direct")
GOLDEN = WURZEL / "eval" / "cases_cities_fit.json"


def einbetten(modell: str) -> None:
    """Objektvektoren und Nachbarschaften für ein zweites Modell rechnen."""
    import os

    os.environ["COUNCIL_EMBED_MODEL"] = modell
    import council.embeddings as emb

    emb.MODEL = modell                     # das Modul liest ihn beim Import
    from council.cities import index
    from council.cities.store import CitiesStore

    db, _files, _raw = default_paths()
    with CitiesStore(db) as s:
        print("Objektvektoren:", index.embed_objects(s, modell))
        print("Kanten:", index.build_neighbors(s, modell))


def vergleichen(a: str, b: str) -> int:
    db, _files, _raw = default_paths()
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rats = sqlite3.connect(WURZEL / "data" / "council.sqlite")
    rats.row_factory = sqlite3.Row

    print("=== Verteilung der Nähe (Kanten von Oldenburg aus) ===")
    print(f"{'Modell':38} {'Kanten':>7} {'≥0,70':>7} {'≥0,80':>7} {'≥0,85':>7}")
    for modell in (a, b):
        werte = [r[0] for r in c.execute(
            "SELECT score FROM neighbors WHERE model=? AND a_id LIKE 'oldenburg:%'",
            (modell,))]
        if not werte:
            print(f"{modell[-36:]:38} — keine Kanten, erst --einbetten")
            return 1
        print(f"{modell[-36:]:38} {len(werte):7} {sum(x >= .70 for x in werte):7} "
              f"{sum(x >= .80 for x in werte):7} {sum(x >= .85 for x in werte):7}")

    einordnung = {r["object_id"]: json.loads(r["payload"]) for r in c.execute(
        "SELECT object_id, payload FROM annotations WHERE annotator='classify'")}

    print("\n=== Zwölf Stichprobenfälle: übertragbare Treffer über 0,70 (Top 3) ===")
    print(f"{'kvonr':>6} {'Urteil':9} {'A':>3} {'B':>3}")
    summen = [0, 0]
    for kvonr, urteil in STICHPROBE.items():
        zeile = []
        for i, modell in enumerate((a, b)):
            treffer = [x for x in c.execute(
                "SELECT b_id, score FROM neighbors WHERE model=? AND a_id=? "
                "ORDER BY score DESC LIMIT 8", (modell, f"oldenburg:paper:{kvonr}"))
                if x["score"] >= 0.70
                and einordnung.get(x["b_id"], {}).get("transfer") in USABLE]
            zeile.append(len(treffer[:3]))
            summen[i] += zeile[-1]
        print(f"{kvonr:>6} {urteil:9} {zeile[0]:>3} {zeile[1]:>3}")
    print(f"{'Summe':>6} {'':9} {summen[0]:>3} {summen[1]:>3}")

    print("\n=== Golden Set von `fit`: Rang des erwarteten Belegs ===")
    faelle = json.loads(GOLDEN.read_text(encoding="utf-8"))
    mit_beleg = [f for f in faelle if f["expected"]["evidence"]]
    for name, modell in (("A", a), ("B", b)):
        gefunden = raenge = 0
        for f in mit_beleg:
            erwartet = set(f["expected"]["evidence"])
            nachbarn = [x["b_id"] for x in c.execute(
                "SELECT b_id FROM neighbors WHERE model=? AND a_id=? "
                "ORDER BY score DESC LIMIT 5", (modell, f["id"]))]
            for rang, kennung in enumerate(nachbarn, 1):
                if kennung in erwartet:
                    gefunden += 1
                    raenge += rang
                    break
        print(f"  {name}: {gefunden}/{len(mit_beleg)} gefunden, mittlerer Rang "
              f"{raenge / max(gefunden, 1):.2f}")

    c.close()
    rats.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--modell", required=True, help="das zu prüfende Modell (B)")
    p.add_argument("--gegen", default=EMBED_MODEL, help="das heutige Modell (A)")
    p.add_argument("--einbetten", action="store_true",
                   help="erst Vektoren und Kanten für B rechnen (Minuten)")
    a = p.parse_args()
    if a.einbetten:
        einbetten(a.modell)
    return vergleichen(a.gegen, a.modell)


if __name__ == "__main__":
    raise SystemExit(main())
