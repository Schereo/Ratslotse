"""Quellen-Prüfung für den Wahlprogramm-Vergleich (Kommunalwahl 2026).

Die Vergleichsseiten verlinken ausschließlich auf die Original-PDFs bei den
Parteien — archivierte Kopien liegen bewusst NICHT mehr im Repo. Damit die
Belegkette trotzdem hält, merkt sich quellen/manifest.json die SHA256-Prüfsumme
jeder ausgewerteten Datei, und dieser Endpunkt lädt das gehostete PDF und
vergleicht: Steht hinter dem Link noch genau die Datei, die ausgewertet wurde?

Die Antwort ist bewusst grob dreiwertig — das Frontend übersetzt sie in
Alltagssprache („noch dasselbe Programm wie bei unserer Auswertung"), nicht in
Hash-Vokabular.

Ergebnis-Cache 24 h pro Slug (Fehlschläge kürzer): Die PDFs sind bis zu 19 MB,
das darf nicht bei jedem Seitenaufruf neu laufen. Erster Abruf des Tages zahlt
den Download, alle weiteren lesen den Cache.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException

from ..antworten import QuellenPruefung
router = APIRouter(prefix="/api/kommunalwahl", tags=["kommunalwahl"])

# Repo-Wurzel: web/backend/app/routers/ -> vier Ebenen hoch.
_BASE = Path(__file__).resolve().parents[4] / "kommunalwahl"

_TTL_OK = 24 * 3600        # gelungene Prüfung: ein Tag
_TTL_FEHLER = 3600         # Netzfehler: nach einer Stunde erneut versuchen
_MAX_BYTES = 64 * 1024 * 1024
_TIMEOUT = (10, 90)        # connect, read — die AfD-Datei hat 19 MB
_UA = "Ratslotse-Quellencheck/1.0 (+https://ratslotse.de/kommunalwahl/methodik)"


@lru_cache(maxsize=1)
def _manifest() -> dict[str, dict]:
    """Slug -> {url, sha256} für alle Listen mit ausgewertetem PDF."""
    pfad = _BASE / "quellen" / "manifest.json"
    try:
        eintraege = json.loads(pfad.read_text(encoding="utf-8"))["programme"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    return {
        e["slug"]: {"url": e["url"], "sha256": e["pdf_sha256"]}
        for e in eintraege
        if e.get("pdf_sha256") and e.get("format") == "pdf"
    }


@dataclass
class _Ergebnis:
    status: str            # "unveraendert" | "veraendert" | "nicht_erreichbar"
    geprueft_um: float     # time.time()

    def als_json(self) -> dict:
        return {
            "status": self.status,
            "geprueft_vor_sekunden": max(0, int(time.time() - self.geprueft_um)),
        }


_cache: dict[str, _Ergebnis] = {}
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_fuer(slug: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(slug, threading.Lock())


def _pruefe(slug: str) -> _Ergebnis:
    quelle = _manifest()[slug]
    try:
        with requests.get(
            quelle["url"], stream=True, timeout=_TIMEOUT, headers={"User-Agent": _UA}
        ) as r:
            r.raise_for_status()
            h = hashlib.sha256()
            gelesen = 0
            for chunk in r.iter_content(chunk_size=1 << 16):
                gelesen += len(chunk)
                if gelesen > _MAX_BYTES:
                    raise ValueError("Datei größer als erwartet")
                h.update(chunk)
        status = "unveraendert" if h.hexdigest() == quelle["sha256"] else "veraendert"
    except Exception:
        status = "nicht_erreichbar"
    return _Ergebnis(status=status, geprueft_um=time.time())


@router.get("/quelle/{slug}")
def quelle_pruefen(slug: str) -> QuellenPruefung:
    """Ist das PDF hinter dem Partei-Link noch die ausgewertete Datei?"""
    if slug not in _manifest():   # Whitelist — nie Dateisystem oder freie URLs
        raise HTTPException(status_code=404, detail="Keine prüfbare PDF-Quelle zu diesem Slug.")

    # Pro Slug nur ein Download gleichzeitig; Wartende übernehmen das Ergebnis.
    with _lock_fuer(slug):
        e = _cache.get(slug)
        ttl = _TTL_OK if e and e.status != "nicht_erreichbar" else _TTL_FEHLER
        if e is None or time.time() - e.geprueft_um > ttl:
            e = _pruefe(slug)
            _cache[slug] = e
    return e.als_json()
