#!/usr/bin/env python3
"""Verfolgte Vorgänge: neue Beratungsstationen melden (Design 28a/W1).

Themen und Ausschuss-Abos sind breite Netze. Wer EINE Vorlage durch die
Gremien begleiten will — die Schule im eigenen Viertel, das Stadion —, klickt
auf der Beschluss-Seite „Diesen Vorgang verfolgen". Dieser Lauf holt für jeden
verfolgten Vorgang die offizielle Beratungsfolge und meldet, was seit der
letzten Meldung dazugekommen ist: eine neue Station, ein nachgetragenes
Ergebnis.

Bewusst kein LLM und kein Zusatz-Scraping über das Nötige hinaus: Geholt wird
nur, was Menschen tatsächlich verfolgen — eine kleine, von Nutzer*innen selbst
bestimmte Menge.

Täglich per Cron, nach check_protocols.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from council import stammdaten
from council.scraper import CouncilScraper
from council.store import CouncilStore
from kern import notify
from kern.store import Store

RATSLOTSE_DB = ROOT / "data" / "ratslotse.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"
APP_URL = os.environ.get("APP_BASE_URL", "https://ratslotse.de").rstrip("/")


def signature(rows: list[dict]) -> list[str]:
    """Fingerabdruck je Station — muss zum Backend passen (routers/council.py,
    _stations_signature). Datum, Gremium, Ergebnis: Eine Station gilt auch dann
    als neu, wenn nur das Ergebnis nachgetragen wurde — genau darauf wartet man."""
    return [f"{r.get('datum') or ''}|{r.get('gremium') or ''}|{r.get('ergebnis') or ''}" for r in rows]


def _label(station: str) -> str:
    """„2026-08-13|Verkehrsausschuss|angenommen" → lesbare Zeile."""
    datum, gremium, ergebnis = (station.split("|") + ["", "", ""])[:3]
    tag = ""
    if datum:
        try:
            tag = date.fromisoformat(datum[:10]).strftime("%d.%m.%Y")
        except ValueError:
            tag = datum
    teile = [t for t in (gremium, tag) if t]
    kopf = " am ".join(teile) if len(teile) == 2 else (teile[0] if teile else "Neue Station")
    return f"{kopf} — {ergebnis}" if ergebnis else f"{kopf} (Termin steht, Ergebnis folgt)"


def _message(follow: dict, neu: list[str], app_url: str) -> str:
    zeilen = "".join(f"<li>{_label(s)}</li>" for s in neu)
    titel = follow.get("title") or follow.get("template_number") or "Verfolgter Vorgang"
    nr = f" ({follow['template_number']})" if follow.get("template_number") else ""
    return (
        f"<p>Es gibt Neues zu einem Vorgang, den du verfolgst:</p>"
        f"<p><b>{titel}</b>{nr}</p>"
        f"<ul>{zeilen}</ul>"
        f'<p><a href="{app_url}">Vorgang in Ratslotse ansehen</a></p>'
    )


def main() -> dict:
    ratslotse = Store(RATSLOTSE_DB)
    follows = ratslotse.get_vorlage_follow_targets()
    if not follows:
        ratslotse.close()
        print("Keine verfolgten Vorgänge.")
        return {"Verfolgte Vorgänge": 0, "Benachrichtigungen": 0}

    council = CouncilStore(COUNCIL_DB)
    scraper = CouncilScraper()

    # Je kvonr EINMAL holen, auch wenn ihm mehrere Konten folgen.
    kvonrs = sorted({f["kvonr"] for f in follows})
    print(f"{len(follows)} Follow(s) auf {len(kvonrs)} Vorgang/Vorgänge.")
    aktuell: dict[int, list[str]] = {}
    fehler = 0
    for kvonr in kvonrs:
        try:
            rows = stammdaten.fetch_beratungsfolge(scraper, kvonr)
            council.save_beratungen(kvonr, rows)
            aktuell[kvonr] = signature(rows)
        except Exception as exc:  # noqa: BLE001 — ein kaputter Vorgang stoppt den Lauf nicht
            fehler += 1
            print(f"  kvonr={kvonr} FEHLER: {exc!r}")
            # Ohne frische Daten lieber der gespeicherte Stand: nichts melden,
            # statt beim nächsten Lauf eine Station doppelt zu schicken.
            aktuell[kvonr] = signature(council.get_beratungen(kvonr))

    gemeldet = 0
    for f in follows:
        jetzt = aktuell.get(f["kvonr"], [])
        try:
            vorher = set(json.loads(f.get("stations") or "[]"))
        except (ValueError, TypeError):
            vorher = set()
        neu = [s for s in jetzt if s not in vorher]
        if not neu:
            continue
        try:
            # Design 30a (N4): einreihen statt senden — sonst gälten weder
            # Nachtruhe noch Tagesgrenze, und der Schalter „Verfolgte Vorgänge"
            # in „Mein Konto" hätte keine Wirkung.
            titel = f"{f.get('template_number') or 'Dein Vorgang'}: neue Station"
            if not notify.einreihen(ratslotse, f["owner_id"], notify.N4_VORGANG, titel,
                                    _message(f, neu, f"{APP_URL}/topics"), "/topics"):
                # Anlass abgeschaltet — Stand trotzdem fortschreiben, sonst
                # käme beim Einschalten die ganze Historie auf einmal.
                ratslotse.mark_vorlage_follow_notified(f["id"], json.dumps(jetzt, ensure_ascii=False))
                continue
            gemeldet += 1
            print(f"  owner {f['owner_id']} ← kvonr={f['kvonr']}: {len(neu)} neue Station(en)")
        except Exception:  # noqa: BLE001 — Zustellfehler darf den Stand nicht einfrieren
            print(f"  owner {f['owner_id']}: Zustellung fehlgeschlagen")
            continue
        ratslotse.mark_vorlage_follow_notified(f["id"], json.dumps(jetzt, ensure_ascii=False))

    council.close()
    zugestellt = notify.zustellen(ratslotse)
    ratslotse.close()
    print(f"Fertig — {gemeldet} eingereiht, {zugestellt} zugestellt.")
    return {
        "Verfolgte Vorgänge": len(kvonrs),
        "Follows": len(follows),
        "Benachrichtigungen": gemeldet,
        "Abruf-Fehler": fehler,
    }


if __name__ == "__main__":
    from kern.alerts import run_guarded
    run_guarded("check_vorlage_follows", main)
