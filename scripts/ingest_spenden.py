#!/usr/bin/env python3
"""Zuwendungen an die Stadt aus den Ratsbeschlüssen in den Bestand holen.

Die einzige Finanz-Schicht des Bereichs, die **nichts lädt**: Ihre Quelle
liegt schon da — die Beschlusszeilen aus den Protokollen und die
Vorlagen-Volltexte, die ``check_protocols.py`` ohnehin nachzieht. Der Lauf
liest sie, prüft jede Zeile gegen ihre Zweitstelle (``council/donations.py``)
und schreibt, was besteht.

Daraus folgt die Reihenfolge im Ops-Workflow: **nach**
``backfill_anlagen_texte.py``. Ohne Vorlagen-Volltext gibt es keine
Zweitstelle, und ohne Zweitstelle keine Zeile.

Aufruf::

    python scripts/ingest_spenden.py [--trockenlauf] [--schrumpf-erlauben]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen, herkunft as h, donations  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"

#: Der Beleg-Text, der bei jeder Zeile steht. Die Vorlage selbst ist der
#: Anker (``document_id``); dieses Label sagt, was für ein Dokument das ist.
LABEL = "Ratsvorlage „Annahme von Zuwendungen“ im Bürgerinformationssystem"


def _lauf_herkunft(result: dict) -> h.Herkunft:
    """Die Herkunft des **Laufs** — für die verworfenen Zeilen.

    Sie zeigt auf die Suche im Bürgerinfo statt auf ein einzelnes Dokument:
    Eine verworfene Zeile hat ihren Beleg ja gerade nicht."""
    years = [v["year"] for v in result["vorlagen"]]
    spanne = f"{min(years)}–{max(years)}" if years else "—"
    return h.Herkunft(
        art="ris",
        url="https://buergerinfo.oldenburg.de/vo040.asp",
        label=LABEL,
        citation=donations.FUNDSTELLE,
        stand=f"Sitzungsjahre {spanne}",
        probe=[donations.ZWEITSTELLE],
        probe_result=donations.probennachweis(result))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--schrumpf-erlauben", action="store_true")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        roh = store.zuwendungsbeschluesse()
        result = donations.lies(roh)
        vorlagen, verworfen = result["vorlagen"], result["verworfen"]

        print(f"Beschlusszeilen gelesen: {result['probes'].get('zeilen', 0)}")
        print(f"Vorlagen mit Zweitstelle: {len(vorlagen)}")
        print(f"Zeilen ohne Zweitstelle:  {len(verworfen)}")
        for j in result["years"]:
            print(f"  {j['year']}  {donations.euro(j['amount']):>14} €  "
                  f"{j['vorlagen']:>2} Vorlagen "
                  f"(Rat {j['rat']}, VA {j['verwaltungsausschuss']})")
        for v in verworfen:
            print(f"  ohne Beleg: {v['template_number']} — {v['grund']}", file=sys.stderr)

        if args.trockenlauf:
            print("Trockenlauf — nichts gespeichert.")
            return 0

        # Bestandsschutz: Wenn ein abgebrochener Volltext-Lauf die halben
        # Vorlagen ohne `raw_text` zurücklässt, sähe dieser Lauf nur die
        # Hälfte der Zweitstellen — und ersetzte damit eine vollständige
        # Reihe durch eine halbe.
        p = finanzquellen.Protokoll()
        if not finanzquellen.bestandsschutz(
                p, "Zuwendungen", len(store.get_spenden()), len(vorlagen),
                schuetzen=not args.schrumpf_erlauben):
            for zeile in p.warnungen:
                print(zeile.strip(), file=sys.stderr)
            print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn das "
                  "Schrumpfen Absicht ist: --schrumpf-erlauben.", file=sys.stderr)
            return 1
        for zeile in p.zeilen:
            print(zeile.strip())

        # Je Zeile ihre eigene Herkunft: Jede Vorlage ist ein eigenes PDF, und
        # der Beleg-Chip soll auf genau dieses zeigen — nicht auf „irgendeine
        # der 148 Vorlagen". Die bestandenen Proben stehen ebenfalls je Zeile;
        # 211 von 212 tragen zusätzlich den Protokollabgleich, und wer die
        # eine Zeile ohne ihn ansieht, soll das lesen können.
        for v in vorlagen:
            v["herkunft"] = h.Herkunft(
                art="ris",
                document_id=v.get("document_id"),
                url=v.get("dokument_url") or "https://buergerinfo.oldenburg.de/vo040.asp",
                label=f"{LABEL} — Vorlage {v['template_number']}",
                citation=donations.FUNDSTELLE,
                stand=f"Sitzung vom {v['sitzung']}",
                probe=v["probes"],
                probe_result=(
                    f"Beschlossen {donations.euro(v['amount'])} Euro; derselbe "
                    f"Betrag steht im Abschnitt zu den finanziellen Auswirkungen "
                    + ("noch einmal." if v["second_mention"] == "identisch"
                       else f"als Zerlegung in {v['teile']} Teilbeträge, die sich "
                            f"auf den Cent aufaddieren.")))

        n = store.save_spenden(vorlagen, verworfen, _lauf_herkunft(result))
        print(f"  gespeichert: {n} Vorlagen, {len(verworfen)} verworfene Zeilen")

        store.herkunft_aufraeumen()
        luecken = {t: k for t, k in store.herkunft_luecken().items()
                   if t.startswith("council_spenden")}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
