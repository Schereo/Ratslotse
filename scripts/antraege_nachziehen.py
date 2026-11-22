#!/usr/bin/env python3
"""Anlagen an Vorlagen gegen die neue Antragserkennung halten.

Bis 11/2026 erkannte ``vorlagen._ANTRAG_LABEL_RE`` keine Komposita: Alle
Änderungs-, Berichts- und Dringlichkeitsanträge an Vorlagen standen auf
``is_motion = 0`` und bekamen nie ihren Text. Der tägliche Anlagen-Rescan
stuft nichts neu ein (bekannte ``document_id``s bleiben, wie sie sind) —
dieses Skript holt das für den Bestand nach (docs/plan-vorlagen-aufbereiten.md,
PR 2).

Standard ist der Bericht. ``--schreiben`` stuft hoch und holt fehlende Texte
nach (höchstens ``--limit`` PDFs, eines je Sekunde).

``--lesen-tage N`` liest danach die Anträge an Punkten der letzten N Tage
(``council/motions.py``). Der Cron liest nur kommende und gerade vergangene
Sitzungen (zwei Tage zurück) — ohne diesen Schritt zeigte etwa die Ratssitzung
vom 02.11.2026 bei beiden GO-Anträgen nur den Dateinamen (13.11.2026). Schon
gelesene Anträge mit unverändertem Text kosten nichts.

    .venv/bin/python scripts/antraege_nachziehen.py [--db data/council.sqlite]
    .venv/bin/python scripts/antraege_nachziehen.py --schreiben --limit 200
    .venv/bin/python scripts/antraege_nachziehen.py --schreiben --lesen-tage 365 --max-usd 1
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

# Ohne .env kein OPENROUTER_API_KEY: Der erste Lauf mit --lesen-tage auf dev
# (13.11.2026) scheiterte so an allen 184 Anträgen.
load_dotenv(ROOT / ".env")

from council import anlagentext, motions, punkt_texte, vorlagen  # noqa: E402
from council.parties import parties_in_text  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.stopp import Stopp  # noqa: E402

# Was die neue Erkennung NIE erfassen darf: Anträge Dritter auf Geld oder eine
# Genehmigung, die die Präfixliste bewusst auslässt. Steht so ein Label im
# Bericht und nennt der Kopf keine Fraktion, ist die Erkennung zu weit geraten.
# Die Fraktion entlastet: „Anlage2Antrag" an 20/0536 ist ein Ergänzungsantrag
# von Grünen und SPD — der Lauf auf dev am 13.11.2026 meldete ihn als Dritten.
_DRITTE_RE = re.compile(r"(?:zuschuss|förder|genehmigungs)antr[aä]g|anlage\s*\d*\s*antr[aä]g", re.IGNORECASE)


def _ist_dritter(k: dict) -> bool:
    if not _DRITTE_RE.search(k["label"] or ""):
        return False
    return not (parties_in_text(k["label"] or "") or parties_in_text((k["kopf"] or "")[:4000]))


def antraege_lesen(store, tage: int, *, schreiben: bool, max_usd: float, max_minuten: float) -> dict:
    """Die Anträge an Punkten der letzten ``tage`` Tage lesen; ohne
    ``schreiben`` nur zählen, wie viele noch keinen gültigen Auszug haben."""
    from datetime import date, timedelta  # noqa: PLC0415

    heute = date.today()
    kandidaten = store.antraege_kommender_punkte((heute - timedelta(days=tage)).isoformat(),
                                                 (heute + timedelta(days=21)).isoformat())
    offen = [k for k in kandidaten
             if (store.motion_extract(k["document_id"]) or {}).get("status") != "ok"]
    print(f"Anträge an Punkten der letzten {tage} Tage: {len(kandidaten)}, davon ohne Auszug: {len(offen)}", flush=True)
    t = texte_holen(store, [k["document_id"] for k in offen], schreiben=schreiben)
    print(f"Davon ohne Text: {t['ohne_text']}, Texte geholt: {t['geholt']}, Fehler: {t['fehler']}", flush=True)
    if not schreiben:
        return {"antraege": len(kandidaten), "offen": len(offen), "ohne_text": t["ohne_text"], "gelesen": 0}
    stopp = Stopp(daten_dir=ROOT / "data", max_kosten=max_usd, frist_sekunden=max_minuten * 60)
    r = motions.nachziehen(store, tage_zurueck=tage, tage_voraus=21, limit=len(kandidaten), stopp=stopp)
    if (grund := stopp.grund()) is not None:
        print(grund.text, flush=True)
    print(f"Anträge gelesen: {r['gelesen']}", flush=True)
    return {"antraege": len(kandidaten), "offen": len(offen), "ohne_text": t["ohne_text"],
            "texte_geholt": t["geholt"], "gelesen": r["gelesen"]}


def texte_holen(store, document_ids: list[int], *, schreiben: bool, pause: float = 1.0) -> dict:
    """Den PDF-Text der Anträge laden, die noch keinen haben — sonst überspringt
    ``motions.extract_one`` sie still. Die Crons laden Punkt-Anlagen nur für
    die letzte Woche (``council/punkt_texte.py``); beim ersten Lesen des
    Bestands auf dev (13.11.2026) blieben so 97 von 184 Anträgen ohne Auszug.

    Am Punkt (``council_agenda_attachments``) samt Steckbrief, sonst an der
    Vorlage (``council_attachments``). Eines je Sekunde; ein 403 kippt den Lauf
    nicht."""
    ohne = []
    for d in dict.fromkeys(document_ids):
        if store.anlage_text(d):
            continue
        top = store.top_anlage_zu_dokument(d)
        if top and top.get("raw_text"):
            continue
        if top and top.get("raw_text") == "":
            continue  # schon geladen, ein Scan — ein zweiter Versuch bringt nichts
        ohne.append((d, top))
    geholt = fehler = 0
    if schreiben:
        anlagen = {a["document_id"]: a for a in store.anlagen_by_ids([d for d, top in ohne if not top])}
        for d, top in ohne:
            url = top["url"] if top else (anlagen.get(d) or {}).get("url")
            if not url:
                continue
            label = top["label"] if top else anlagen[d]["label"]
            try:
                seiten = vorlagen.pdf_seiten_laden(url)
            except Exception as exc:  # noqa: BLE001 — ein PDF kippt nicht den Lauf
                fehler += 1
                print(f"  Antrag {d}: {exc!r}", flush=True)
                continue
            text = "\n".join(seiten)
            if top:
                store.set_punkt_anlagentext(url, text if len(text.strip()) >= punkt_texte.MIN_TEXT else "")
                store.save_document_profile(d, **punkt_texte.steckbrief(label, seiten, text))
            else:
                store.anlagentext_nachtragen(d, text if len(text.strip()) >= punkt_texte.MIN_TEXT else "", len(seiten))
            geholt += 1
            time.sleep(pause)
    return {"ohne_text": len(ohne), "geholt": geholt, "fehler": fehler}


def main(db: str | None = None, schreiben: bool = False, limit: int = 200, lesen_tage: int = 0,
         max_usd: float = 1.0, max_minuten: float = 60) -> dict:
    store = CouncilStore(db or str(ROOT / "data" / "council.sqlite"))
    kandidaten = []
    for a in store.anlagen_zur_neueinstufung():
        if vorlagen.ist_antrag(a["label"], a["kopf"]):
            ueber = "Label" if vorlagen.ist_antrag(a["label"]) else "Textkopf"
            kandidaten.append({**a, "ueber": ueber})
    dritte = [k for k in kandidaten if _ist_dritter(k)]
    print(f"{len(kandidaten)} Anlagen werden zum Antrag "
          f"({sum(k['ueber'] == 'Label' for k in kandidaten)} über das Label, "
          f"{sum(k['ueber'] == 'Textkopf' for k in kandidaten)} über den Textkopf).")
    for k in kandidaten[:40]:
        print(f"  {k['kvonr']:>6} {k['ueber']:<8} {k['label']}")
    if len(kandidaten) > 40:
        print(f"  … und {len(kandidaten) - 40} weitere")
    print(f"Anträge Dritter darunter (muss 0 sein): {len(dritte)}")
    for k in dritte:
        print(f"  !! {k['label']}")

    hochgestuft = gelesen = fehler = 0
    if schreiben:
        for k in kandidaten:
            text = None
            if k["status"] in ("listed", "failed") and gelesen + fehler < limit:
                try:
                    text, n_pages = vorlagen._pdf_text(k["url"], anlagentext.extraktor_fuer(k["label"]))  # noqa: SLF001
                    gelesen += 1
                    time.sleep(1)
                except Exception as exc:  # noqa: BLE001 — ein PDF kippt nicht den Lauf
                    fehler += 1
                    print(f"  {k['document_id']}: {exc!r}")
            kopf = text if text is not None else k["kopf"]
            antragsteller = parties_in_text(k["label"]) or parties_in_text((kopf or "")[:4000])
            if text is not None:
                store.anlage_als_antrag(k["document_id"], antragsteller, raw_text=text, n_pages=n_pages,
                                        status="ok" if len(text.strip()) >= 50 else "empty")
            else:
                store.anlage_als_antrag(k["document_id"], antragsteller)
            hochgestuft += 1
        print(f"Hochgestuft: {hochgestuft}, Texte geholt: {gelesen}, Fehler: {fehler}")
    lesen = antraege_lesen(store, lesen_tage, schreiben=schreiben, max_usd=max_usd,
                           max_minuten=max_minuten) if lesen_tage > 0 else None
    store.close()
    return {"kandidaten": len(kandidaten), "dritte": len(dritte), "hochgestuft": hochgestuft,
            "gelesen": gelesen, "fehler": fehler, "antraege_gelesen": (lesen or {}).get("gelesen", 0)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--lesen-tage", type=int, default=0, help="Anträge der letzten N Tage lesen (0 = nicht)")
    ap.add_argument("--max-usd", type=float, default=1.0, help="Kostengrenze für das Lesen der Anträge")
    ap.add_argument("--max-minuten", type=float, default=60, help="Frist für das Lesen der Anträge")
    a = ap.parse_args()
    main(a.db, a.schreiben, a.limit, a.lesen_tage, a.max_usd, a.max_minuten)
