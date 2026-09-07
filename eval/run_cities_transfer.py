#!/usr/bin/env python3
"""Misst, wie gut ein Modell fremde Ratsvorlagen für Oldenburg einordnet.

**Die Frage, auf die es ankommt:** Taugt eine fremde Vorlage als Idee für
Oldenburg — ja oder nein? Das ist die eine Entscheidung, die das Produkt
später trifft. Die feinere Fünfteilung der Übertragbarkeit und das Themenfeld
sind Beiwerk und werden mitgemessen, weil sie erklären, *warum* ein Modell
danebenliegt.

Maßstab sind 45 von Hand eingeordnete Vorlagen aus vier Städten
(``cases_cities_transfer.json``, geschichtet über Städte und Vorlagenarten).
Sie tragen ihren Text bei sich — die Suite braucht **keine** Datenbank, nur
einen API-Schlüssel.

```bash
python eval/run_cities_transfer.py                       # aktiver Annotator
python eval/run_cities_transfer.py --model deepseek/deepseek-v4-pro
python eval/run_cities_transfer.py --save --compare      # gegen die Baseline
```

**Ein Lauf ist eine Stichprobe, kein Messwert.** Vier Läufe desselben Modells
mit demselben Prompt am 07.09.2026:

| Lauf | Routing | Batch | taugt/taugt nicht | $/1000 |
|---|---|---:|---:|---:|
| 1 | frei, nach Preis | 6 | 89 % | 0,09 |
| 2 | frei | 6 | 90 % | 0,22 |
| 3 | ZDR (Projektvorgabe) | 6 | 91 % | 0,28 |
| 4 | ZDR | 4 | 84 % | 0,33 |
| 5 | frei | 6 | 84 % | 0,29 |

Bei 45 Fällen entspricht ein Punkt knapp einem halben Fall; die Spanne von
84 bis 91 Prozent ist **Rauschen**, keine Wirkung der Einstellungen — Routing
und Batchgröße erklären sie nicht. Der Wert liegt bei rund **87 %**. Ein einzelner Lauf des Probelaufs hatte 98 % gezeigt —
das war Glück, nicht Können, und steht so korrigiert in
``docs/phase0-andere-staedte.md``.

Als Regression zählt deshalb erst ein Lauf **unter 80 %**. Was dagegen
deutlich außerhalb des Rauschens liegt und den Bau dieses Prompts trägt: Die
erste Prompt-Fassung, gemessen unter denselben Bedingungen, kam auf 73 % und
ein elfmal teureres Modell auf 71 %.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from council.cities import annotate  # noqa: E402
from council.cities.annotators import USABLE, get as get_annotator  # noqa: E402
from eval import harness  # noqa: E402

CASES = Path(__file__).parent / "cases_cities_transfer.json"
SUITE = "cities_transfer"


def lade_faelle() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def einordnen(faelle: list[dict], model: str, batch_size: int,
              zdr: bool = False) -> dict[str, dict]:
    """Die Fälle in Batches ans Modell geben — derselbe Weg wie im Betrieb."""
    from kern import llm, prompts

    ann = get_annotator("classify")
    system = prompts.render(ann.prompt_system, fields=annotate.field_list())
    texte = {f["id"]: f["text"] for f in faelle}
    ergebnis: dict[str, dict] = {}
    kosten = 0.0

    for i in range(0, len(faelle), batch_size):
        chunk = faelle[i:i + batch_size]
        zeilen = [{"id": f["id"], "body_id": f["city"], "name": f["name"],
                   "date": f["date"], "paper_type_raw": f["paper_type_raw"]} for f in chunk]
        try:
            antwort = llm.chat_complete(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user,
                              items=annotate.batch_text(zeilen, texte, ann))}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={} if zdr else ({"provider": {}} if ann.routing_free else {}),
                _feature="eval_cities_transfer")
            daten = annotate.parse_json(antwort.choices[0].message.content or "")
            verbrauch = getattr(antwort, "usage", None)
            if verbrauch:
                kosten += float(getattr(verbrauch, "cost", 0) or 0)
            for eintrag in daten.get("results", []):
                if str(eintrag.get("id")) in texte:
                    ergebnis[str(eintrag["id"])] = eintrag
        except Exception as e:  # noqa: BLE001 — ein Batch, nicht der Lauf
            print(f"  Batch {i} gescheitert: {type(e).__name__}: {str(e)[:100]}")
    ergebnis["__kosten__"] = {"cost_usd": kosten}  # type: ignore[assignment]
    return ergebnis


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", help="Modell (Vorgabe: das des aktiven Annotators)")
    p.add_argument("--batch-size", type=int)
    p.add_argument("--save", action="store_true", help="Ergebnis als Baseline ablegen")
    p.add_argument("--compare", action="store_true", help="gegen die letzte Baseline")
    p.add_argument("--zdr", action="store_true",
                   help="mit der ZDR-Provider-Beschränkung des Projekts messen")
    a = p.parse_args()

    ann = get_annotator("classify")
    model = a.model or ann.model
    batch = a.batch_size or ann.batch_size
    faelle = lade_faelle()
    print(f"{len(faelle)} handeingeordnete Vorlagen · Modell {model} · "
          f"Prompt-Fassung {ann.version} · Routing "
          f"{'ZDR (Projektvorgabe)' if a.zdr else 'frei'}\n")

    t0 = time.time()
    vorhersage = einordnen(faelle, model, batch, zdr=a.zdr)
    kosten = vorhersage.pop("__kosten__", {}).get("cost_usd", 0.0)  # type: ignore[union-attr]
    dauer = time.time() - t0

    n = feld = uebertrag = taugt = zust = 0
    fehler: list[dict] = []
    for f in faelle:
        got = vorhersage.get(f["id"])
        if not got:
            continue
        n += 1
        erwartet = f["expected"]
        feld += got.get("field") == erwartet["field"]
        uebertrag += got.get("transfer") == erwartet["transfer"]
        gleich = (got.get("transfer") in USABLE) == (erwartet["transfer"] in USABLE)
        taugt += gleich
        zust += got.get("competence") == erwartet["competence"]
        if not gleich:
            fehler.append({"case": f["name"][:70], "erwartet": erwartet["transfer"],
                           "bekommen": got.get("transfer"),
                           "instrument": got.get("instrument")})

    quote = lambda x: round(100 * x / max(n, 1), 1)  # noqa: E731
    ergebnis = {
        "suite": SUITE, "model": model, "prompt_version": ann.version,
        "routing": "zdr" if a.zdr else "frei",
        "n_cases": len(faelle), "n_answered": n,
        "usable_accuracy": quote(taugt), "transfer_accuracy": quote(uebertrag),
        "field_accuracy": quote(feld), "competence_accuracy": quote(zust),
        "cost_usd": round(kosten, 4), "seconds": round(dauer),
        "cost_per_1000": round(kosten / max(n, 1) * 1000, 3),
        "mistakes": fehler,
    }

    print(f"  geliefert          {n}/{len(faelle)}")
    print(f"  taugt/taugt nicht  {ergebnis['usable_accuracy']:.0f} %   ← die Entscheidung, "
          f"die das Produkt trifft")
    print(f"  Übertragbarkeit    {ergebnis['transfer_accuracy']:.0f} %")
    print(f"  Themenfeld         {ergebnis['field_accuracy']:.0f} %")
    print(f"  Zuständigkeit      {ergebnis['competence_accuracy']:.0f} %")
    print(f"  Kosten             ${kosten:.4f}  ({ergebnis['cost_per_1000']:.2f} $/1000)")
    print(f"  Dauer              {dauer:.0f}s")
    if fehler:
        print("\n  Wo es danebenging:")
        for m in fehler[:10]:
            print(f"    [{m['erwartet']} → {m['bekommen']}] {m['case']}")

    if a.compare:
        vorher, pfad = harness.load_last(SUITE)
        if vorher and pfad:
            # Eigener Vergleich statt harness.print_compare: Diese Suite misst
            # keine Precision/Recall, sondern vier Trefferquoten.
            print(f"\n  Gegen {pfad.name} ({vorher.get('model')}, Fassung "
                  f"{vorher.get('prompt_version')}):")
            for schluessel, name in (("usable_accuracy", "taugt/taugt nicht"),
                                     ("transfer_accuracy", "Übertragbarkeit"),
                                     ("field_accuracy", "Themenfeld"),
                                     ("competence_accuracy", "Zuständigkeit")):
                alt, neu = vorher.get(schluessel, 0), ergebnis[schluessel]
                pfeil = "↑" if neu > alt else ("↓" if neu < alt else "→")
                print(f"    {name:18} {alt:5.0f} % {pfeil} {neu:5.0f} %  ({neu - alt:+.0f})")
        else:
            print("\n  (noch keine Baseline — mit --save eine anlegen)")
    if a.save:
        print(f"\n  Baseline: {harness.save_result(ergebnis)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
