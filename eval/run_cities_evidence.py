#!/usr/bin/env python3
"""Findet die Belegsuche, was ein Mensch als Beleg bezeichnet hat? — ohne Modell.

**Warum ein eigener Eval.** ``run_cities_fit.py`` misst das Urteil und kostet
je Lauf Geld und Minuten. Das Urteil kann aber nur so gut sein wie die Belege,
die ihm vorliegen: Beim Durchgehen der vierzig Fälle am 08.09.2026 stand in
**elf** davon ein Beleg, der mit der Sache erkennbar nichts zu tun hatte (die
Ernährungsstrategie beim Notruf, der Ferienpass bei der Zweckentfremdung, die
Klävemann-Stiftung beim Straßenbau). Diese Frage lässt sich ohne ein einziges
Sprachmodell beantworten — in Sekunden statt Minuten, für 0 $ statt 0,03 $.

**Drei Maße, und alle drei entscheiden.**

1. *Gefunden.* Steht der Beleg, den ein Mensch als den richtigen bezeichnet
   hat, überhaupt in der Liste? Das ist die Obergrenze für alles Weitere:
   Was das Modell nie sieht, kann es nicht zitieren.
2. *Auf welchem Rang.* Weiter unten heißt: Es steht Rauschen davor, und das
   Rauschen lädt ein, „vorhanden" zu sagen, wo nichts ist.
3. *Wie einig sich die vier Arme sind.* Nachbarschaft, Textabschnitt,
   Volltext und Beschluss irren auf verschiedene Weise; dass sie **dasselbe**
   Papier finden, ist deshalb eine eigene Aussage. Gemessen trennt sie
   schärfer als jeder Einzelwert: Wo Oldenburg das Instrument hat, findet in
   92 % der Fälle mindestens ein Papier über zwei oder mehr Arme; wo es
   fehlt, nur in 18 %.

   (Die erste Fassung maß hier stattdessen die ZAHL der Belege bei
   „fehlt"-Fällen, in der Annahme, viele Belege lüden zum Irrtum ein. Das war
   eine Hypothese, und sie ist falsch: Die Zahl trifft immer den Deckel
   ``MAX_EVIDENCE``, und die sieben gemessenen Läufe zeigen kein einziges
   falsches „vorhanden". Der binde Engpass war die Trefferquote, nicht das
   Rauschen.)

```bash
python eval/run_cities_evidence.py                       # gegen data/cities.sqlite
python eval/run_cities_evidence.py --chunk-schwelle 0.55 0.62 0.70
```

Der zweite Aufruf ist der, mit dem ``MIN_CHUNK_SCORE`` festgelegt wurde: Nimm
den Wert, bei dem die erste Zahl ihr Maximum hat und die zweite am kleinsten
ist.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities import evidence as ev  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402
from council.store import CouncilStore  # noqa: E402

FAELLE = WURZEL / "eval" / "cases_cities_fit.json"

#: Was der Ausbau erreichen soll. Vorher (nur Nachbarn + Volltext auf die
#: Instrumentwörter): 19 von 23 gefunden, mittlerer Rang 1,9.
SCHWELLE_GEFUNDEN = 22
SCHWELLE_RANG = 2.5
#: Wo Oldenburg etwas hat, müssen sich die Arme in mindestens so vielen
#: Fällen einig sein. Gemessen: 92 % (present), 64 % (partial), 18 % (missing).
SCHWELLE_EINIGKEIT = 0.80


def lade() -> list[dict]:
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def belege_neu(faelle: list[dict], main: CitiesStore, rats: CouncilStore,
               matrix, chunk_schwelle: float | None = None) -> dict[str, list]:
    """Für jeden Fall die Belege, die die heutige Suche liefern würde."""
    if chunk_schwelle is not None:
        ev.MIN_CHUNK_SCORE = chunk_schwelle
    einordnung = main.annotations_for("classify", "2")
    heute: dict[str, list] = {}
    for f in faelle:
        papier = main.paper(f["id"])
        if not papier:
            continue
        klasse = einordnung.get(f["id"]) or {
            "instrument": f.get("instrument"), "field": f.get("field")}
        heute[f["id"]] = ev.evidence_for(main, rats, papier, klasse, EMBED_MODEL,
                                         chunk_matrix=matrix)
    return heute


def messen(faelle: list[dict], heute: dict[str, list]) -> dict:
    mit_beleg = [f for f in faelle if f["expected"]["evidence"] and f["id"] in heute]
    ohne = [f for f in faelle if f["expected"]["status"] == "missing" and f["id"] in heute]

    gefunden = raenge = 0
    verfehlt: list[str] = []
    for f in mit_beleg:
        erwartet = set(f["expected"]["evidence"])
        kennungen = [b.id for b in heute[f["id"]] if b.kind != "recap"]
        for rang, kennung in enumerate(kennungen, 1):
            if kennung in erwartet:
                gefunden += 1
                raenge += rang
                break
        else:
            verfehlt.append(f["name"][:60])

    # Einigkeit der Arme, getrennt nach dem, was ein Mensch geurteilt hat.
    einig: dict[str, list[bool]] = {"present": [], "partial": [], "missing": []}
    for f in faelle:
        if f["id"] not in heute:
            continue
        einig[f["expected"]["status"]].append(
            any(b.arme >= 2 for b in heute[f["id"]] if b.kind != "recap"))
    anteil = {k: (sum(v) / len(v) if v else 0.0) for k, v in einig.items()}
    return {
        "faelle_mit_beleg": len(mit_beleg),
        "gefunden": gefunden,
        "mittlerer_rang": raenge / max(gefunden, 1),
        "faelle_ohne": len(ohne),
        "einigkeit": anteil,
        "verfehlt": verfehlt,
    }


def zeigen(name: str, z: dict) -> None:
    print(f"\n=== {name} ===")
    print(f"  erwarteter Beleg gefunden: {z['gefunden']}/{z['faelle_mit_beleg']}"
          f"   (Schwelle {SCHWELLE_GEFUNDEN})")
    print(f"  mittlerer Rang:            {z['mittlerer_rang']:.2f}"
          f"        (Schwelle {SCHWELLE_RANG})")
    e = z["einigkeit"]
    print(f"  zwei Arme einig:           vorhanden {e['present']:.0%}, "
          f"teilweise {e['partial']:.0%}, fehlt {e['missing']:.0%}"
          f"   (vorhanden ≥ {SCHWELLE_EINIGKEIT:.0%})")
    if z["verfehlt"]:
        print("  nicht gefunden:")
        for name_ in z["verfehlt"]:
            print(f"    - {name_}")


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--chunk-schwelle", type=float, nargs="*",
                   help="mehrere Werte durchprobieren, statt den eingebauten zu nehmen")
    a = p.parse_args()

    db, _files, _raw = default_paths()
    main_store = CitiesStore(db)
    rats = CouncilStore(WURZEL / "data" / "council.sqlite")
    try:
        faelle = lade()
        matrix = main_store.chunk_matrix(EMBED_MODEL, "oldenburg")
        print(f"{len(faelle)} Fälle, {len(matrix[0])} Oldenburger Textabschnitte")
        schwellen = a.chunk_schwelle or [ev.MIN_CHUNK_SCORE]
        letzte = {}
        for schwelle in schwellen:
            heute = belege_neu(faelle, main_store, rats, matrix, schwelle)
            letzte = messen(faelle, heute)
            zeigen(f"Chunk-Schwelle {schwelle:.2f}", letzte)
    finally:
        main_store.close()
        rats.close()

    if len(schwellen) > 1:
        return 0        # ein Suchlauf entscheidet nichts, er zeigt nur
    schlecht = (letzte["gefunden"] < SCHWELLE_GEFUNDEN
                or letzte["mittlerer_rang"] > SCHWELLE_RANG
                or letzte["einigkeit"]["present"] < SCHWELLE_EINIGKEIT)
    print("\n" + ("NICHT bestanden." if schlecht else "Bestanden."))
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main())
