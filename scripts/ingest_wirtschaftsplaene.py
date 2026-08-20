#!/usr/bin/env python3
"""Die Wirtschaftspläne der Eigenbetriebe aus dem Vorlagenbestand einlesen.

Der Haushalt neben dem Haushalt: Was der Rat den Eigenbetrieben für das
kommende Jahr genehmigt, stand im Haushalts-Bereich bisher nirgends. Warum es
diese Schicht gibt, welche Rechenprobe sie trägt und warum sie **nur** den
Eigenbetrieb Gebäudewirtschaft und Hochbau liest, steht im Kopf von
``council/wirtschaftsplan.py``.

Warum kein Download und kein Cron
---------------------------------
Die Quelle liegt schon im Haus: ``council_vorlagen`` führt den Volltext jeder
Ratsvorlage, und der Beschlussvorschlag steht darin. Dieser Lauf lädt nichts
nach, er liest den Bestand — deshalb ist er auch der richtige Weg, wenn ein
verbesserter Parser über die vorhandenen Jahrgänge laufen soll.

Ein Cron kommt später in Frage: ``check_finanzdaten`` ist auf
``council_anlagen`` gebaut (``finanzquellen.Finanzquelle.erkennung`` sucht ein
Anlagen-Label). Diese Schicht wäre die erste, deren Einheit eine **Vorlage**
ist; das ist ein eigener Umbau und keine Nebensache dieses Skripts.

Aufruf::

    .venv/bin/python scripts/ingest_wirtschaftsplaene.py --trockenlauf
    .venv/bin/python scripts/ingest_wirtschaftsplaene.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from council.wirtschaftsplan import (  # noqa: E402
    WirtschaftsplanFehler,
    herkunft_fuer,
    ohne_eckwerte,
    parse_wirtschaftsplan,
)

COUNCIL_DB = ROOT / "data" / "council.sqlite"

#: Woran eine Wirtschaftsplan-Vorlage erkannt wird. Bewusst weit: Lieber eine
#: Vorlage zu viel prüfen (sie liefert dann schlicht keine Eckwerte) als einen
#: Jahrgang zu verpassen, weil der Titel anders gebaut ist. Die Schreibweisen
#: wechseln stark — „Wirtschaftsplan des Eigenbetriebes …", „Wirtschaftsplan
#: und Finanzplan 2026 für den …", „BBGO: Wirtschaftsplan 2026".
TITEL_MUSTER = "%Wirtschaftsplan%"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Wirtschaftspläne der Eigenbetriebe aus council_vorlagen lesen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--trockenlauf", action="store_true",
                    help="alles rechnen und zeigen, nichts speichern")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        rows = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT vorlage_nr, kvonr, title, raw_text FROM council_vorlagen "
            "WHERE title LIKE ? AND status = 'ok' AND raw_text IS NOT NULL "
            "ORDER BY vorlage_nr", (TITEL_MUSTER,))]
        print(f"{len(rows)} Vorlage(n) mit „Wirtschaftsplan“ im Titel.\n")

        gefunden, luecken, risse = [], [], []
        for r in rows:
            try:
                plan = parse_wirtschaftsplan(
                    r["vorlage_nr"], r["title"], r["raw_text"])
            except WirtschaftsplanFehler as fehler:
                # Ein Riss ist kein Grund, den Lauf abzubrechen: Die übrigen
                # Jahrgänge sind davon unberührt. Aber er wird gezählt und
                # genannt — genau dafür gibt es die Probe.
                risse.append(str(fehler))
                continue
            if plan is None:
                luecken.append(ohne_eckwerte(r["vorlage_nr"], r["title"]))
                continue
            gefunden.append((plan, r["kvonr"]))

        print(f"Mit Eckwerten: {len(gefunden)} · ohne: {len(luecken)} · "
              f"Probe gerissen: {len(risse)}\n")

        for plan, _ in sorted(gefunden, key=lambda x: (x[0].betrieb, x[0].jahr)):
            print(f"  {plan.jahr}  {plan.betrieb:8s} "
                  f"Erträge {plan.ertraege / 1e6:7.1f} Mio. €  "
                  f"Ergebnis {plan.ergebnis / 1e6:8.3f} Mio. €  "
                  f"Vermögensplan {(plan.vermoegensplan or 0) / 1e6:7.1f} Mio. €  "
                  f"({plan.vorlage_nr}, Entwurf {plan.entwurf_vom})")

        if risse:
            print("\nProbe gerissen — NICHT gespeichert:")
            for satz in risse:
                print(f"  ! {satz}")

        # Die Lücke gehört gezählt, nicht überblättert: Dass nur EINER von
        # sechs Betrieben seine Eckwerte in den Beschlusstext schreibt, ist
        # der eigentliche Befund dieser Schicht.
        ohne_nach_betrieb: dict[str, int] = {}
        for lücke in luecken:
            name = lücke["betrieb_name"] or "unbekannter Betrieb"
            ohne_nach_betrieb[name] = ohne_nach_betrieb.get(name, 0) + 1
        if ohne_nach_betrieb:
            print("\nOhne Eckwerte im Beschlusstext (Zahlen stehen in der Anlage):")
            for name, n in sorted(ohne_nach_betrieb.items(), key=lambda x: -x[1]):
                print(f"  {n:3d}  {name}")

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.")
            return 1 if risse else 0

        for plan, kvonr in gefunden:
            url = (f"https://buergerinfo.oldenburg.de/vo0050.php?__kvonr={kvonr}"
                   if kvonr else None)
            store.save_wirtschaftsplan(plan, herkunft_fuer(plan, url=url))
        print(f"\n{len(gefunden)} Wirtschaftsplan/-pläne gespeichert.")

        luecken_ohne_beleg = store.herkunft_luecken().get("council_wirtschaftsplaene")
        if luecken_ohne_beleg:
            print(f"  ! {luecken_ohne_beleg} Zeile(n) ohne Herkunft — "
                  "das sollte nicht vorkommen (siehe council/herkunft.py)")
            return 1
        return 1 if risse else 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
