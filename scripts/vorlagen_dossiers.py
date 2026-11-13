#!/usr/bin/env python3
"""Dossiers für die Vorlagen kommender Sitzungen (docs/plan-vorlagen-aufbereiten.md § 4.3).

Als Job (``run_guarded``) täglich 10 und 15 Uhr: Vorlagen der Sitzungen der
nächsten 21 Tage, fehlende oder veraltete Dossiers erzeugen (Flex, Geduld),
Kostengrenze je Lauf ``DOSSIER_MAX_USD`` (Vorgabe 0,50 $).

Von Hand für den Bestand (Bericht, schreibt nur mit ``--schreiben``):

    .venv/bin/python scripts/vorlagen_dossiers.py --bestand --seit 2025-11-01 --max-usd 1 [--schreiben]

Mit dem Schalter ``begriffe-aus-vorlage`` erzeugt derselbe Lauf danach die
Fachwörter aus der Vorlage (``council/vorlage_begriffe.py``, Grenze
``TERMS_MAX_USD``, Vorgabe 0,25 $). Für den Bestand:

    .venv/bin/python scripts/vorlagen_dossiers.py --bestand --begriffe --seit 2025-11-01 --max-usd 5 [--schreiben]

Mit dem Schalter ``wahlprogramm-am-punkt`` folgt als dritte Stufe, was die
Wahlprogramme dazu sagen (``council/programm_bezug.py``, Grenze
``PROGRAM_MAX_USD``, Vorgabe 0,25 $). Für den Bestand ``--bestand --programme``.

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

from council import programm_bezug, template_dossier, vorlage_begriffe  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import features  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402
from kern.stopp import Stopp  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def lauf(vorlagen: list[str], *, max_usd: float, schreiben: bool = True,
         max_minuten: float = 0) -> dict:
    store = CouncilStore(COUNCIL_DB)
    # Der Deploy-Marker liegt in data/: ein wartender Deploy beendet den Lauf (kern/stopp.py).
    # Die Frist liegt im Ops-Workflow UNTER dem SSH-Zeitlimit: Am 13.11.2026 lief
    # der Bestand auf dev in eine Rate-Limit-Welle (Geduld: 30/90/180 s je Aufruf)
    # und wurde nach 120 min von außen abgeschnitten — ohne Bilanz.
    stopp = Stopp(daten_dir=ROOT / "data", max_kosten=max_usd, frist_sekunden=max_minuten * 60)
    neu = vorhanden = ohne_text = 0
    for i, tn in enumerate(vorlagen, 1):
        if (grund := stopp.grund()) is not None:
            print(grund.text, flush=True)
            break
        if i % 25 == 0:
            print(f"  … {i}/{len(vorlagen)}: {neu} neu, {vorhanden} aktuell, {stopp.kosten:.3f} $", flush=True)
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
          f"{vorhanden} aktuell, {ohne_text} ohne Text, {kosten:.3f} $", flush=True)
    return {"vorlagen": len(vorlagen), "neu": neu, "aktuell": vorhanden, "ohne_text": ohne_text,
            "kosten_usd": round(kosten, 4)}


def lauf_begriffe(vorlagen: list[str], *, max_usd: float, schreiben: bool = True, max_minuten: float = 0) -> dict:
    """Fachwörter aus der Vorlage (``council/vorlage_begriffe.py``): je Vorlage
    vorschlagen und prüfen lassen, rund 0,004 $. Liest die Lesetexte der
    Punkt-Seite — läuft deshalb NACH den Dossiers."""
    store = CouncilStore(COUNCIL_DB)
    stopp = Stopp(daten_dir=ROOT / "data", max_kosten=max_usd, frist_sekunden=max_minuten * 60)
    neu = vorhanden = ohne_text = begriffe = 0
    for i, tn in enumerate(vorlagen, 1):
        if (grund := stopp.grund()) is not None:
            print(grund.text, flush=True)
            break
        if i % 25 == 0:
            print(f"  … {i}/{len(vorlagen)}: {neu} neu, {vorhanden} aktuell, {begriffe} Begriffe, {stopp.kosten:.3f} $", flush=True)
        m = store.terms_material(tn)
        if not m:
            ohne_text += 1
            continue
        alt = store.template_terms(tn)
        if alt and alt["status"] == "ok" and alt["prompt_version"] == vorlage_begriffe.PROMPT_VERSION \
                and alt["sources_hash"] == vorlage_begriffe.sources_hash(m["texts"], m["template_text"]):
            vorhanden += 1
            continue
        if not schreiben:
            neu += 1
            continue
        d = vorlage_begriffe.build_for_template(store, tn, stopp=stopp)
        if d:
            neu += 1
            begriffe += len((d["payload"] or {}).get("terms") or [])
    print(f"Begriffe: {len(vorlagen)} Vorlagen, {neu} {'neu' if schreiben else 'würden neu entstehen'}, "
          f"{vorhanden} aktuell, {ohne_text} ohne Text, {begriffe} Begriffe, {stopp.kosten:.3f} $", flush=True)
    return {"begriffe_vorlagen_neu": neu, "begriffe": begriffe, "begriffe_kosten_usd": round(stopp.kosten, 4)}


def lauf_programme(vorlagen: list[str], *, max_usd: float, schreiben: bool = True, max_minuten: float = 0) -> dict:
    """Was die Wahlprogramme zu einer Vorlage sagen (``council/programm_bezug.py``):
    suchen, einordnen, Zitat prüfen, vom größeren Modell bestätigen lassen —
    rund 0,005 $ je Vorlage. Braucht die Lesetexte der Punkt-Seite (nach den
    Dossiers) und fastembed für die Suche in den Programmen."""
    store = CouncilStore(COUNCIL_DB)
    stopp = Stopp(daten_dir=ROOT / "data", max_kosten=max_usd, frist_sekunden=max_minuten * 60)
    neu = vorhanden = ohne_text = mit_aussage = aussagen = 0
    for i, tn in enumerate(vorlagen, 1):
        if (grund := stopp.grund()) is not None:
            print(grund.text, flush=True)
            break
        if i % 25 == 0:
            print(f"  … {i}/{len(vorlagen)}: {neu} neu, {vorhanden} aktuell, {aussagen} Einordnungen, {stopp.kosten:.3f} $", flush=True)
        m = store.terms_material(tn)
        if not m:
            ohne_text += 1
            continue
        alt = store.program_stances(tn)
        if alt and alt["status"] == "ok" and alt["prompt_version"] == programm_bezug.PROMPT_VERSION \
                and alt["sources_hash"] == programm_bezug.sources_hash(m["title"], m["texts"]):
            vorhanden += 1
            continue
        if not schreiben:
            neu += 1
            continue
        d = programm_bezug.build_for_template(store, tn, stopp=stopp)
        if d:
            neu += 1
            n = len((d["payload"] or {}).get("stances") or [])
            aussagen += n
            mit_aussage += n > 0
    print(f"Wahlprogramme: {len(vorlagen)} Vorlagen, {neu} {'neu' if schreiben else 'würden neu entstehen'}, "
          f"{vorhanden} aktuell, {ohne_text} ohne Text, {mit_aussage} mit Einordnung, {aussagen} Einordnungen, "
          f"{stopp.kosten:.3f} $", flush=True)
    return {"programme_vorlagen_neu": neu, "programme_einordnungen": aussagen,
            "programme_kosten_usd": round(stopp.kosten, 4)}


def main() -> dict:
    store = CouncilStore(COUNCIL_DB)
    heute = date.today()
    vorlagen = store.vorlagen_kommender_sitzungen(heute.isoformat(), (heute + timedelta(days=21)).isoformat())
    kennzahlen = lauf(vorlagen, max_usd=float(os.environ.get("DOSSIER_MAX_USD") or 0.5))
    # Die Begriffe hängen am Schalter: Solange die Seite sie nicht zeigt, kostet ihr Erzeugen nur.
    if features.an("begriffe-aus-vorlage"):
        kennzahlen.update(lauf_begriffe(vorlagen, max_usd=float(os.environ.get("TERMS_MAX_USD") or 0.25)))
    if features.an("wahlprogramm-am-punkt"):
        kennzahlen.update(lauf_programme(vorlagen, max_usd=float(os.environ.get("PROGRAM_MAX_USD") or 0.25)))
    return kennzahlen


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bestand", action="store_true")
    ap.add_argument("--seit", default=(date.today() - timedelta(days=365)).isoformat())
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--max-minuten", type=float, default=0, help="Frist für den Lauf; 0 = keine")
    ap.add_argument("--begriffe", action="store_true",
                    help="mit --bestand: statt der Dossiers die Fachwörter aus der Vorlage (council/vorlage_begriffe.py)")
    ap.add_argument("--programme", action="store_true",
                    help="mit --bestand: statt der Dossiers die Wahlprogramme zum Punkt (council/programm_bezug.py)")
    a = ap.parse_args()
    if a.bestand:
        s = CouncilStore(COUNCIL_DB)
        # Bis drei Wochen voraus: Die kommenden Sitzungen gehören zum Bestand dazu.
        bis = (date.today() + timedelta(days=21)).isoformat()
        stufe = lauf_programme if a.programme else lauf_begriffe if a.begriffe else lauf
        stufe(s.vorlagen_kommender_sitzungen(a.seit, date.today().isoformat() if stufe is lauf else bis),
              max_usd=a.max_usd, schreiben=a.schreiben, max_minuten=a.max_minuten)
    else:
        raise SystemExit(run_guarded("vorlagen_dossiers", main))
