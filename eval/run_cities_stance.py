#!/usr/bin/env python3
"""Trifft ``stance`` die Richtung, die ein Mensch der Vorlage zuschreibt?

**Warum die Frage zählt.** „Verpackungssteuersatzung erlassen" (Braunschweig)
und „Verpackungssteuer-Prüfung einstellen" (Magdeburg) liegen in derselben
Gruppe — zu Recht, es ist dieselbe Sache — und standen beide als fehlende
Idee auf der Liste. Eine Karte, die das nicht unterscheidet, zählt eine Stadt
für eine Idee, die sie gerade abgelehnt hat.

```bash
python eval/run_cities_stance.py            # ~0,01 $, 46 Fälle
python eval/run_cities_stance.py --runs 3   # Streuung messen
```

**Die Schranke liegt bei 85 %**, höher als bei ``transfer``: Eine Vorlage
will eine Sache oder sie will sie nicht.

**Drei Klassen, und das ist gemessen.** Die erste Fassung fragte nach fünf
(``introduce``/``expand``/``restrict``/``stop``/``review``) und traf 72 %.
Sechs der dreizehn Fehler waren ``introduce`` gegen ``expand`` — „Lärm-
aktionsplan fortschreiben" ist beides, je nachdem ob man den Plan oder seine
Fortschreibung für die Sache hält. Eine Klasse, für die es keine Regel gibt,
ist keine Klasse. Zusammengelegt: 87 %. Der Rest der Verwechslungen liegt
zwischen ``for`` und ``review``, und das ist eine echte Grenze.

**Die sechs ``against``-Fälle sind der Kern.** Sie sind gezielt aufgenommen, nicht
zufällig gezogen: Ohne sie prüfte der Lauf genau das nicht, wofür es den
Annotator gibt. Ein Ergebnis mit hoher Gesamtquote und verfehlten
``against``-Fällen ist ein schlechtes Ergebnis.

**Die Urteile sind von mir**, nicht von Tim (anders als bei den vierzig
``fit``-Fällen). Das ist vertretbar, weil die Richtung eine Tatsachenfrage
ist — will die Vorlage die Sache oder nicht? —, keine Wertung. Wo ich
unsicher war, steht das im ``why``.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from council.cities.annotate import parse_json  # noqa: E402
from council.cities.annotators import get as get_annotator  # noqa: E402
from kern import llm, prompts  # noqa: E402

FAELLE = WURZEL / "eval" / "cases_cities_stance.json"

#: Anteil richtiger Richtungen. 85 %, siehe Modulkopf.
SCHWELLE = 0.85
#: Die Gegenrichtungen müssen ALLE sitzen — sie sind der Zweck des Annotators.
SCHWELLE_GEGEN = 1.0


def lade() -> list[dict]:
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def ein_lauf(faelle: list[dict], ann) -> dict:
    system = prompts.get(ann.prompt_system)
    treffer = 0
    verwechslung: Counter = Counter()
    daneben: list[dict] = []
    kosten = 0.0
    stop_treffer = stop_gesamt = 0
    for f in faelle:
        text = (f"Stadt: {f['body_id']}\n"
                f"Titel: {f['name']}\n"
                f"Instrument: {f['instrument']}")
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, gruppe=f["gruppe"], paper=text)}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
            bekommen = nutzlast.stance
        except Exception as e:  # noqa: BLE001
            bekommen = f"FEHLER:{type(e).__name__}"
        verbrauch = getattr(antwort, "usage", None) if "antwort" in dir() else None
        kosten += float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        if f["expected"] == "against":
            stop_gesamt += 1
            stop_treffer += bekommen == "against"
        if bekommen == f["expected"]:
            treffer += 1
        else:
            verwechslung[f"{f['expected']}→{bekommen}"] += 1
            daneben.append({"instrument": f["instrument"], "erwartet": f["expected"],
                            "bekommen": bekommen, "why": f["why"]})
    return {"quote": treffer / max(len(faelle), 1), "treffer": treffer,
            "gesamt": len(faelle), "verwechslung": dict(verwechslung),
            "daneben": daneben, "cost_usd": kosten,
            "stop_quote": stop_treffer / max(stop_gesamt, 1), "stop_gesamt": stop_gesamt}


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--runs", type=int, default=1)
    a = p.parse_args()

    faelle = lade()
    ann = get_annotator("stance")
    print(f"{len(faelle)} Fälle, Modell {ann.model}, {a.runs} Lauf/Läufe\n")
    laeufe = [ein_lauf(faelle, ann) for _ in range(a.runs)]
    letzter = laeufe[-1]
    quoten = [x["quote"] for x in laeufe]

    print(f"  Richtung getroffen  {statistics.fmean(quoten):.0%}"
          + (f" (Streuung {max(quoten) - min(quoten):.0%})" if a.runs > 1 else "")
          + f"   Schwelle {SCHWELLE:.0%}")
    print(f"  davon `against`     {letzter['stop_quote']:.0%} von "
          f"{letzter['stop_gesamt']}   Schwelle {SCHWELLE_GEGEN:.0%}")
    print(f"  Kosten              ${sum(x['cost_usd'] for x in laeufe):.4f}")
    if letzter["verwechslung"]:
        print("\n  Verwechslungen (erwartet → bekommen):")
        for k, v in sorted(letzter["verwechslung"].items(), key=lambda x: -x[1]):
            print(f"    {k:28} {v}")
    if letzter["daneben"]:
        print("\n  Wo es danebenging:")
        for d in letzter["daneben"][:8]:
            print(f"    [{d['erwartet']} → {d['bekommen']}] {d['instrument'][:50]}")
            print(f"        {d['why'][:70]}")

    schlecht = (statistics.fmean(quoten) < SCHWELLE
                or letzter["stop_quote"] < SCHWELLE_GEGEN)
    print("\n" + ("NICHT bestanden." if schlecht else "Bestanden."))
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main())
