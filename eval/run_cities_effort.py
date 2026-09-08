#!/usr/bin/env python3
"""Trifft der Annotator ``effort`` die Aufwandsklasse, die ein Mensch vergibt?

**Warum die Frage überhaupt zählt.** „Eine Anfrage zu Fußwegbreiten stellen"
und „ein Darlehensprogramm für Genossenschaften einführen" standen bisher
gleichberechtigt auf einer Liste von Ideen. Ein Ratsmitglied unterscheidet das
sofort — nach dem, was es kostet. 31 % der übertragbaren Vorlagen im Bestand
sind Anfragen oder deren Antworten (gemessen 08.09.2026); ohne die Klasse
sieht die Liste voller aus, als sie ist.

Die zweite Angabe ist der ADRESSAT: Wer müsste es tun, wenn nicht die Stadt
selbst? An ihr hängen im Golden Set von ``fit`` die meisten „lohnt sich"-
Urteile — Hausverbote in Bussen sind Sache der VWG, nicht des Rates.

```bash
python eval/run_cities_effort.py                  # ein Lauf, ~0,01 $
python eval/run_cities_effort.py --runs 3
```

**Die Schranke liegt bei 80 %, höher als bei ``transfer``.** Die Kanten sind
schärfer: Eine Anfrage ist keine Satzung, und ein Förderprogramm bindet Geld
oder nicht. Wo ``transfer`` eine Ermessensfrage stellt, stellt ``effort`` eine
über die Form des Beschlusses.
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
from council.cities.evidence import OLDENBURG_STECKBRIEF  # noqa: E402

CASES = Path(__file__).parent / "cases_cities_effort.json"

#: Über fünf Klassen mit klaren Kanten. Darunter ist es eine Regression.
SCHWELLE = 80.0
#: Der Adressat ist Freitext; gemessen wird nur, ob ÜBERHAUPT einer genannt
#: wird, wo einer hingehört — und ob keiner genannt wird, wo die Stadt selbst
#: entscheidet. Der zweite Fehler ist der teurere: Ein erfundener Adressat
#: nimmt eine Idee von der Liste („dafür sind wir nicht zuständig").
SCHWELLE_ADRESSAT = 85.0


def lade() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def _ein_batch(block: list[dict], model: str, ann, system: str,
               ergebnis: dict[str, dict]) -> float:
    """Ein Batch ans Modell. Gibt die Kosten zurück; schreibt in ``ergebnis``."""
    from kern import llm, prompts

    items = "\n\n".join(
        f"id: {f['id']}\nArt: {f['kind']}\nTitel: {f['name']}\n"
        f"Instrument: {f['instrument']}\n"
        f"{' '.join(f['paper'].split())[:ann.input_chars]}"
        for f in block)
    try:
        antwort = llm.chat_complete(
            model=model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompts.render(
                          ann.prompt_user, items=items)}],
            max_tokens=ann.max_tokens, temperature=ann.temperature,
            extra_body={"provider": {}} if ann.routing_free else {},
            _feature="eval_cities_effort")
        daten = parse_json(antwort.choices[0].message.content or "")
        for eintrag in daten.get("results") or []:
            if isinstance(eintrag, dict) and eintrag.get("id"):
                ergebnis[str(eintrag["id"])] = eintrag
        verbrauch = getattr(antwort, "usage", None)
        return float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
    except Exception as e:  # noqa: BLE001 — ein Batch, nicht der Lauf
        print(f"  Batch gescheitert: {type(e).__name__}: {str(e)[:90]}")
        return 0.0


def urteilen(faelle: list[dict], model: str) -> tuple[dict[str, dict], float, int]:
    """Wie im Betrieb: in Batches, mit demselben Prompt — UND mit Nachlauf.

    **Modelle lassen in Batches Einträge aus**, ohne dass etwas scheitert:
    Der Betriebslauf (``council/cities/annotate.py``) hat dafür seit dem
    Probelauf einen Nachlauf, der die Ausgelassenen einzeln nachreicht. Der
    Prüfstand hatte ihn nicht — und maß deshalb im ersten Anlauf 94 % über
    **32 statt 40** Fälle, ohne dass die fehlenden acht irgendwo aufgefallen
    wären. Ein Maßstab, der stillschweigend eine Teilmenge bewertet, ist
    schlimmer als keiner.

    Gibt zusätzlich zurück, wie viele Fälle den Nachlauf gebraucht haben —
    steigt die Zahl, ist ``batch_size`` zu groß.
    """
    ann = get_annotator("effort")
    from kern import prompts
    system = prompts.render(ann.prompt_system, steckbrief=OLDENBURG_STECKBRIEF)
    ergebnis: dict[str, dict] = {}
    kosten = 0.0
    for start in range(0, len(faelle), ann.batch_size):
        kosten += _ein_batch(faelle[start:start + ann.batch_size], model, ann,
                             system, ergebnis)

    offen = [f for f in faelle if f["id"] not in ergebnis]
    for f in offen:
        kosten += _ein_batch([f], model, ann, system, ergebnis)
    if offen:
        print(f"  Nachlauf für {len(offen)} ausgelassene")
    return ergebnis, kosten, len(offen)


def messen(faelle: list[dict], vorhersage: dict[str, dict]) -> dict:
    n = treffer = 0
    adressat_richtig = 0
    matrix: Counter[tuple[str, str]] = Counter()
    fehler: list[dict] = []
    erfundene_adressaten: list[str] = []

    for f in faelle:
        got = vorhersage.get(f["id"])
        if not got:
            continue
        n += 1
        erwartet = f["expected"]
        ist = str(got.get("effort", ""))
        matrix[(erwartet["effort"], ist)] += 1
        if ist == erwartet["effort"]:
            treffer += 1
        else:
            fehler.append({"name": f["name"][:64], "erwartet": erwartet["effort"],
                           "bekommen": ist, "grund": f["judgment"][:100]})

        # Adressat: gemessen wird das VORHANDENSEIN, nicht die Schreibweise.
        soll = bool(erwartet["addressee"])
        ist_adressat = bool(got.get("addressee"))
        if soll == ist_adressat:
            adressat_richtig += 1
        elif ist_adressat and not soll:
            erfundene_adressaten.append(
                f"{f['name'][:50]}: {str(got.get('addressee'))[:40]}")

    quote = lambda x: round(100 * x / max(n, 1), 1)  # noqa: E731
    return {
        "n": n, "effort": quote(treffer), "addressee": quote(adressat_richtig),
        "matrix": matrix, "fehler": fehler,
        "erfundene_adressaten": erfundene_adressaten,
    }


def zeigen(z: dict, laeufe: list[dict]) -> None:
    werte = [x["effort"] for x in laeufe]
    print(f"\n  Aufwandsklasse   {statistics.mean(werte):.0f} % "
          f"({min(werte):.0f}–{max(werte):.0f})   Schwelle {SCHWELLE:.0f} %")
    adr = [x["addressee"] for x in laeufe]
    print(f"  Adressat da/nicht da   {statistics.mean(adr):.0f} %"
          f"        Schwelle {SCHWELLE_ADRESSAT:.0f} %")

    print("\n  Verwechslungen (erwartet → bekommen):")
    for (soll, ist), k in sorted(z["matrix"].items(), key=lambda x: -x[1]):
        marke = "  " if soll == ist else "✗ "
        print(f"    {marke}{soll:11} → {ist:11} {k}")
    if z["fehler"]:
        print("\n  Wo es danebenging:")
        for f in z["fehler"]:
            print(f"    [{f['erwartet']} → {f['bekommen']}] {f['name']}")
            print(f"        „{f['grund']}“")
    if z["erfundene_adressaten"]:
        print("\n  ADRESSAT genannt, wo die Stadt selbst entscheidet:")
        for zeile in z["erfundene_adressaten"]:
            print(f"    - {zeile}")


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--model", help="Modell (Vorgabe: das des Annotators)")
    p.add_argument("--runs", type=int, default=1)
    a = p.parse_args()

    ann = get_annotator("effort")
    model = a.model or ann.model
    faelle = lade()
    print(f"{len(faelle)} handgeurteilte Vorlagen · Modell {model} · "
          f"Fassung {ann.version}")
    print("  Verteilung im Maßstab: " + ", ".join(
        f"{k} {v}" for k, v in Counter(
            f["expected"]["effort"] for f in faelle).most_common()))

    laeufe: list[dict] = []
    kosten = 0.0
    letzte: dict = {}
    for lauf in range(a.runs):
        vorhersage, k, nachgereicht = urteilen(faelle, model)
        kosten += k
        letzte = messen(faelle, vorhersage)
        letzte["nachgereicht"] = nachgereicht
        laeufe.append(letzte)
        print(f"\n  Lauf {lauf + 1}: Aufwand {letzte['effort']:.0f} % · "
              f"Adressat {letzte['addressee']:.0f} % · {letzte['n']}/{len(faelle)} Fälle"
              + (f" ({nachgereicht} nachgereicht)" if nachgereicht else ""))

    zeigen(letzte, laeufe)
    print(f"\n  Kosten  ${kosten:.4f}")

    mittel = statistics.mean(x["effort"] for x in laeufe)
    mittel_adr = statistics.mean(x["addressee"] for x in laeufe)
    # Ein Lauf, der nicht alle Fälle beurteilt hat, misst eine Teilmenge —
    # und eine Teilmenge, die das Modell selbst ausgewählt hat.
    vollstaendig = all(x["n"] == len(faelle) for x in laeufe)
    if not vollstaendig:
        print("  ⚠ Nicht alle Fälle beurteilt — die Quoten gelten für eine "
              "Teilmenge, die das MODELL ausgesucht hat.")
    bestanden = (mittel >= SCHWELLE and mittel_adr >= SCHWELLE_ADRESSAT
                 and vollstaendig)
    print(f"\n  {'BESTANDEN' if bestanden else 'NICHT BESTANDEN'}")
    return 0 if bestanden else 1


if __name__ == "__main__":
    raise SystemExit(main())
