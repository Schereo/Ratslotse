#!/usr/bin/env python3
"""Dossiers für die Vorlagen kommender Sitzungen (docs/plan-vorlagen-aufbereiten.md § 4.3).

Als Job (``run_guarded``) täglich 10 und 15 Uhr: Vorlagen der Sitzungen der
nächsten 21 Tage, fehlende oder veraltete Dossiers erzeugen (Flex, Geduld),
Kostengrenze je Lauf ``DOSSIER_MAX_USD`` (Vorgabe 0,50 $).

Von Hand für den Bestand (Bericht, schreibt nur mit ``--schreiben``):

    .venv/bin/python scripts/vorlagen_dossiers.py --bestand --seit 2025-11-01 --max-usd 1 [--schreiben]

crontab: ``0 10,15 * * *``
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from council import template_dossier  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402
from kern.stopp import Stopp  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def lauf(vorlagen: list[str], *, max_usd: float, schreiben: bool = True) -> dict:
    store = CouncilStore(COUNCIL_DB)
    # Der Deploy-Marker liegt in data/: ein wartender Deploy beendet den Lauf (kern/stopp.py).
    stopp = Stopp(daten_dir=ROOT / "data", max_kosten=max_usd)
    neu = vorhanden = ohne_text = 0
    for tn in vorlagen:
        if stopp.grund() is not None:
            print(stopp.grund())
            break
        m = store.dossier_material(tn)
        if not m:
            ohne_text += 1
            continue
        _, _, h = template_dossier.build_input(m)
        alt = store.template_dossier(f"tn:{tn}", h)
        if alt and alt["status"] == "ok":
            vorhanden += 1
            continue
        if not schreiben:
            neu += 1
            continue
        if template_dossier.build_for_template(store, tn, stopp=stopp):
            neu += 1
    kosten = stopp.kosten
    print(f"{len(vorlagen)} Vorlagen: {neu} {'neu' if schreiben else 'würden neu entstehen'}, "
          f"{vorhanden} aktuell, {ohne_text} ohne Text, {kosten:.3f} $")
    return {"vorlagen": len(vorlagen), "neu": neu, "aktuell": vorhanden, "ohne_text": ohne_text,
            "kosten_usd": round(kosten, 4)}


def main() -> dict:
    store = CouncilStore(COUNCIL_DB)
    heute = date.today()
    vorlagen = store.vorlagen_kommender_sitzungen(heute.isoformat(), (heute + timedelta(days=21)).isoformat())
    return lauf(vorlagen, max_usd=float(os.environ.get("DOSSIER_MAX_USD") or 0.5))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bestand", action="store_true")
    ap.add_argument("--seit", default=(date.today() - timedelta(days=365)).isoformat())
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--schreiben", action="store_true")
    a = ap.parse_args()
    if a.bestand:
        s = CouncilStore(COUNCIL_DB)
        lauf(s.vorlagen_kommender_sitzungen(a.seit, date.today().isoformat()), max_usd=a.max_usd, schreiben=a.schreiben)
    else:
        raise SystemExit(run_guarded("vorlagen_dossiers", main))
