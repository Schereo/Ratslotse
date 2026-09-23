#!/usr/bin/env python3
"""EINE Tranche eines teuren Städte-Laufs — dann Schluss. Den Rest macht die
Schleife (`scripts/cities_tranchen.sh`).

```bash
python scripts/cities_tranche.py reason --limit 1000 [--alle]
python scripts/cities_tranche.py idea_fit --limit 100
python scripts/cities_tranche.py fit --limit 2000
```

**Warum ein eigener Prozess je Tranche.** Am 15. und 16.09.2026 ist der
`fit`-Bestandslauf zweimal abgebrochen: Die Beleg-Arme lieferten mit der Zeit
immer weniger, bis gar nichts mehr kam, und der Wächter stoppte — zu Recht.
Ein FRISCHER Prozess lieferte auf denselben Vorlagen wieder volle Arme. Was
sich da ansammelt, sitzt tiefer als die Verbindung; ein Prozess je Tranche
wirft es weg. Bis 09/2026 lag diese Schleife nur als `~/app/fit4_schleife.sh`
auf dev — hier steht sie für alle drei teuren Stufen.

**Rückgabe:** 0 = Tranche fertig, es gibt mehr. 9 = nichts mehr zu tun (oder
zu wenig Speicher). Alles andere = Fehler; die Schleife hält dann an, statt
blind weiterzuzahlen.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

#: Unter so viel freiem Speicher startet keine Tranche: Die dev-VM hat 3,8 GB,
#: und ein Lauf, der den laufenden Dienst in den Swap drückt, sieht aus wie
#: ein Fehler im Dienst (gemessen 22.09.2026: 2 GB Swap belegt).
MIN_FREI_MB = 250


def frei_mb() -> int:
    try:
        with open("/proc/meminfo") as f:
            for zeile in f:
                if zeile.startswith("MemAvailable:"):
                    return int(zeile.split()[1]) // 1024
    except OSError:
        pass
    return 10**9       # kein Linux: nicht messbar, also kein Grund zum Abbruch


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("stufe", choices=("fit", "reason", "idea_fit"))
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--alle", action="store_true",
                    help="reason: alle Abschnitte, nicht nur die mit Ideen-Gruppe "
                         "(157 gegen 6.962 auf dev, 23.09.2026) — das Warum lohnt "
                         "sich vor allem für die Einzelideen (Plan §2.5)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if frei_mb() < MIN_FREI_MB:
        print(f"ABBRUCH: nur noch {frei_mb()} MB frei", flush=True)
        return 9

    from council.cities.index import EMBED_MODEL
    from council.cities.store import CitiesStore
    from council.store import CouncilStore

    cities = os.environ.get("CITIES_DB") or str(WURZEL / "data" / "cities.sqlite")
    council = os.environ.get("COUNCIL_DB") or str(WURZEL / "data" / "council.sqlite")
    t0 = time.time()
    with CitiesStore(cities) as m:
        if args.stufe == "reason":
            from council.cities import reasons
            stand = reasons.run(m, limit=args.limit, workers=args.workers,
                                nur_mit_gruppe=not args.alle)
        else:
            rats = CouncilStore(council)
            try:
                if args.stufe == "fit":
                    from council.cities import fit
                    from council.cities.annotators import get as get_annotator
                    stand = fit.run(m, rats, get_annotator("fit"), EMBED_MODEL,
                                    limit=args.limit, workers=args.workers)
                else:
                    from council.cities import idea_fit
                    stand = idea_fit.run(m, rats, EMBED_MODEL, limit=args.limit,
                                         workers=args.workers)
            finally:
                rats.close()
    if not stand.get("annotated"):
        print(f"FERTIG: nichts mehr offen ({stand})", flush=True)
        return 9
    print(f"TRANCHE {args.stufe} {stand['annotated']} Urteile ${stand['cost_usd']:.4f} "
          f"{time.time() - t0:.0f}s | Fehler {stand.get('errors', 0)} "
          f"| erfunden {stand.get('hallucinated_evidence', 0)} | frei {frei_mb()} MB",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
