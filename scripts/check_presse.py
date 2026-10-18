#!/usr/bin/env python3
"""Täglicher Abgleich der Stadt-Quellen: Pressemitteilungen (RSS → Details → FTS/Chunks
→ Ortsbezug), Bauleitplan-Beteiligungen und aktuelle Sperrungen (Geoportal).

Holt den RSS-Feed (60 Einträge), lädt fehlende Detailseiten, schreibt sie in
council_press (+FTS) und embeddet die neuen Texte direkt (best-effort — ohne
fastembed übernimmt der Wochenlauf embed_decisions.py). Kein LLM.

Crontab (Server): täglich, z. B.  15 5 * * *  … scripts/check_presse.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import presse  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import JobFehler, run_guarded  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _teil(name: str, fehler: list[str], fn):
    """Einen Teil-Schritt laufen lassen; scheitert er, wird der Fehler
    gemerkt und der Rest läuft weiter.

    **Warum gemerkt und nicht verschluckt.** Bis 10/2026 stand hier je Teil
    ein ``except: pass``. Auf Prod scheiterten die Sperrungen täglich (das
    Geoportal sperrt Hetzner, der Abruf ging ohne Heim-Proxy), der Lauf
    meldete „ok" und eine Kennzahl ``sperrungen: -1``, die niemand las — die
    Ebene auf der Karte blieb leer. Jetzt endet der Lauf mit ``JobFehler``:
    Die übrigen Teile sind geschrieben, die Kennzahlen bleiben erhalten, und
    ``run_guarded`` schickt die Alarm-Mail."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — ein Teil, nicht der Lauf
        print(f"!! {name} fehlgeschlagen: {exc!r}", flush=True)
        fehler.append(f"{name}: {type(exc).__name__}: {str(exc)[:160]}")
        return None


def main() -> dict:
    store = CouncilStore(COUNCIL_DB)
    teilfehler: list[str] = []
    bekannt = store.presse_urls()
    feed = presse.fetch_feed()
    neu = fehlgeschlagen = 0
    for eintrag in feed:
        if eintrag["url"] in bekannt:
            continue
        try:
            detail = presse.fetch_detail(eintrag["url"])
        except Exception:  # noqa: BLE001 — eine kaputte Seite killt nicht den Lauf
            fehlgeschlagen += 1
            continue
        if not detail:
            fehlgeschlagen += 1
            continue
        store.save_presse(
            eintrag["url"], eintrag["news_id"],
            detail["title"] or eintrag["title"],
            detail["date"] or eintrag["date"], detail["text"])
        neu += 1
    chunks = 0
    if neu:
        try:
            from council import embeddings
            chunks = embeddings.embed_presse_missing(store)
        except Exception:  # noqa: BLE001 — fastembed fehlt → Wochenlauf holt nach
            pass
    # Laufende Bauleitplan-Beteiligungen im selben Tageslauf aktualisieren —
    # eigener Teil: ein Ausfall des Portals darf den Presse-Teil nicht kosten.
    # Seit 13.08. wird nicht mehr ersetzt, sondern fortgeschrieben: Die Stadt
    # löscht abgeschlossene Verfahren spurlos, wir behalten sie als Historie
    # und markieren sie nur als beendet.
    from council import beteiligung, presse_orte, sperrungen
    bet = _teil("Beteiligungen", teilfehler,
                lambda: store.save_beteiligungen(beteiligung.fetch_planfaelle())) or {}
    # Ortsbezug der neuen (und noch nie geprüften) Mitteilungen — regelbasiert,
    # kein Modell; die Tafel „Mein Viertel" liest ihn.
    orte = _teil("Ortsbezug", teilfehler,
                 lambda: presse_orte.verorte(store, store.press_without_places(limit=300))) or {}
    # Aktuelle Sperrungen aus dem Geoportal — eigener Teil, eigener Ausfall.
    sperr = _teil("Sperrungen", teilfehler,
                  lambda: store.save_road_closures(sperrungen.fetch_closures())) or {}
    store.close()
    kennzahlen = {"feed": len(feed), "neu": neu, "fehlgeschlagen": fehlgeschlagen,
                  "chunks": chunks, "beteiligungen": bet.get("laufend", -1),
                  "bet_neu": bet.get("neu", 0), "bet_beendet": bet.get("beendet", 0),
                  "verortet": orte.get("verortet", 0), "sperrungen": sperr.get("laufend", -1),
                  "sperr_neu": sperr.get("neu", 0), "sperr_beendet": sperr.get("beendet", 0),
                  "teilfehler": len(teilfehler)}
    if teilfehler:
        raise JobFehler("Stadt-Quellen: " + "; ".join(teilfehler), kennzahlen)
    return kennzahlen


if __name__ == "__main__":
    raise SystemExit(run_guarded("check_presse", main))
