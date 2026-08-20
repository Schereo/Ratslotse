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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from council.wirtschaftsplan import (  # noqa: E402
    WirtschaftsplanFehler,
    betrieb_aus_titel,
    herkunft_fuer,
    ohne_eckwerte,
    parse_wirtschaftsplan,
)
from council.wirtschaftsplan_tabelle import (  # noqa: E402
    VOKABULAR,
    herkunft_fuer as herkunft_tabelle,
    parse_erfolgsplan,
)
from council.wirtschaftsplan_kernzahl import (  # noqa: E402
    BELEGLAGE,
    herkunft_fuer as herkunft_kernzahl,
    parse_kernzahl,
)

COUNCIL_DB = ROOT / "data" / "council.sqlite"

#: Woran eine Wirtschaftsplan-Vorlage erkannt wird. Bewusst weit: Lieber eine
#: Vorlage zu viel prüfen (sie liefert dann schlicht keine Eckwerte) als einen
#: Jahrgang zu verpassen, weil der Titel anders gebaut ist. Die Schreibweisen
#: wechseln stark — „Wirtschaftsplan des Eigenbetriebes …", „Wirtschaftsplan
#: und Finanzplan 2026 für den …", „BBGO: Wirtschaftsplan 2026".
TITEL_MUSTER = "%Wirtschaftsplan%"


def jahr_aus_titel(titel: str) -> int | None:
    """Das Haushaltsjahr aus dem Vorlagentitel.

    Bei den Anlagen-Betrieben gibt es keinen Beschlusstext, der „für das
    Haushaltsjahr 2026" schreibt — der Titel ist die einzige Angabe. Steht dort
    mehr als eine Jahreszahl, wird geraten, und das ist hier nicht erlaubt:
    Dann kommt ``None``, und der Jahrgang bleibt liegen.
    """
    jahre = {int(j) for j in re.findall(r"\b(20\d{2})\b", titel)}
    return jahre.pop() if len(jahre) == 1 else None


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

        # --- Zweiter Weg: der Erfolgsplan aus der ANLAGE ------------------
        #
        # Für die Betriebe, die im Beschlusstext keine Zahl nennen. Er greift
        # nur, wo ein Vokabular hinterlegt ist (bisher der AWB) UND die Anlage
        # Volltext trägt — ein Scan liefert nichts, und das ist kein Fehler,
        # sondern eine Lücke mit Marke (`status='empty'`, s. haushalt.md).
        aus_anlage, anlagen_risse, ohne_text = [], [], []
        for r in rows:
            erkannt = betrieb_aus_titel(r["title"])
            if not erkannt or erkannt[0] not in VOKABULAR:
                continue
            betrieb = erkannt[0]
            jahr = jahr_aus_titel(r["title"])
            if jahr is None:
                continue
            anlagen = [dict(a) for a in store._conn.execute(  # noqa: SLF001
                "SELECT document_id, label, url, status, raw_text "
                "FROM council_anlagen WHERE kvonr = ? ORDER BY document_id",
                (r["kvonr"],))]
            lesbar = [a for a in anlagen
                      if a["status"] == "ok" and (a["raw_text"] or "")]
            if not lesbar:
                ohne_text.append((r["vorlage_nr"], jahr,
                                  [a["status"] for a in anlagen] or ["keine Anlage"]))
                continue
            for a in lesbar:
                try:
                    plan, proben = parse_erfolgsplan(
                        r["vorlage_nr"], betrieb, jahr, a["raw_text"])
                except WirtschaftsplanFehler as fehler:
                    anlagen_risse.append(f"{r['vorlage_nr']} (Anlage "
                                         f"{a['document_id']}): {fehler}")
                    continue
                aus_anlage.append((plan, proben, a))
                break

        if aus_anlage:
            print("\nAus dem Erfolgsplan der Anlage:")
            for plan, proben, a in sorted(aus_anlage, key=lambda x: (x[0].betrieb, x[0].jahr)):
                print(f"  {plan.jahr}  {plan.betrieb:8s} "
                      f"Erträge {plan.ertraege / 1e6:7.3f} Mio. €  "
                      f"Ergebnis {plan.ergebnis / 1e6:+7.3f} Mio. €  "
                      f"({len(proben)} Spalten geprüft, Anlage {a['document_id']})")
        if ohne_text:
            print("\nAnlage ohne Volltext — nichts zu lesen:")
            for vnr, jahr, stati in ohne_text:
                print(f"  {jahr}  {vnr}: {', '.join(sorted(set(stati)))}"
                      + ("  (Scan — für eine spätere OCR vorgemerkt)"
                         if "empty" in stati else ""))
        if anlagen_risse:
            print("\nAnlage gelesen, aber Probe gerissen — NICHT gespeichert:")
            for satz in anlagen_risse:
                print(f"  ! {satz}")
        risse.extend(anlagen_risse)

        # --- Dritter Weg: die Kernzahl aus dem Beschlusstext --------------
        #
        # Für die Betriebe, deren Tabelle sich nicht selbst vorrechnet. Greift
        # nur, wo die beiden anderen Wege nichts geliefert haben — sonst stünde
        # eine Zeile mit bloßem Ergebnis gegen eine mit vollem Tripel.
        schon = {(plan.betrieb, plan.jahr) for plan, _ in gefunden} | {
            (plan.betrieb, plan.jahr) for plan, _, _ in aus_anlage}
        kernzahlen = []
        for r in rows:
            erkannt = betrieb_aus_titel(r["title"])
            jahr = jahr_aus_titel(r["title"])
            if not erkannt or jahr is None or (erkannt[0], jahr) in schon:
                continue
            texte = [a[0] for a in store._conn.execute(  # noqa: SLF001
                "SELECT raw_text FROM council_anlagen WHERE kvonr = ? "
                "AND status = 'ok'", (r["kvonr"],))]
            try:
                res = parse_kernzahl(r["vorlage_nr"], r["title"], r["raw_text"],
                                     jahr, texte)
            except WirtschaftsplanFehler as fehler:
                risse.append(str(fehler)); continue
            if res is None:
                continue
            kernzahlen.append((*res, r))

        if kernzahlen:
            print("\nKernzahl aus dem Beschlusstext:")
            for plan, wort, lage, _ in sorted(kernzahlen,
                                              key=lambda x: (x[0].betrieb, x[0].jahr)):
                print(f"  {plan.jahr}  {plan.betrieb:16s} "
                      f"Ergebnis {plan.ergebnis / 1e6:+8.3f} Mio. €   "
                      f"[{lage}] {BELEGLAGE[lage]}")

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.")
            return 1 if risse else 0

        for plan, kvonr in gefunden:
            url = (f"https://buergerinfo.oldenburg.de/vo0050.php?__kvonr={kvonr}"
                   if kvonr else None)
            store.save_wirtschaftsplan(plan, herkunft_fuer(plan, url=url))
        for plan, proben, a in aus_anlage:
            store.save_wirtschaftsplan(plan, herkunft_tabelle(
                plan, proben, url=a["url"], dokument_id=a["document_id"],
                label=a["label"]))
        for plan, wort, lage, r in kernzahlen:
            store.save_wirtschaftsplan(plan, herkunft_kernzahl(
                plan, wort, lage, url=None, kvonr=r["kvonr"]))
        print(f"\n{len(gefunden)} Eckwerte, {len(aus_anlage)} Erfolgspläne, "
              f"{len(kernzahlen)} Kernzahlen gespeichert.")

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
