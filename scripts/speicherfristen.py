#!/usr/bin/env python3
"""Setzt die Speicherfristen durch, die die Datenschutzerklärung zusagt.

Heute eine: **Recherchen ohne Einwilligung** (``deep_research_jobs`` eines
Kontos mit ``saves_conversations`` ≠ 1) werden sieben Tage nach ihrem letzten
Stand gelöscht — Frage und Bericht samt Konto-Bezug. Bis 10/2026 blieben sie
unbegrenzt liegen, auch wenn das Konto dem Speichern von Gesprächen nie
zugestimmt hatte. Die Frist und ihre Begründung stehen an
``Store.DEEP_JOB_FRIST_TAGE``.

Derselbe Schritt läuft zusätzlich bei jedem Start des Backends
(``web/backend/app/main.py``). Der tägliche Lauf hier sorgt dafür, dass die
Frist auch dann greift, wenn wochenlang kein Deploy kommt.

Aufruf: täglich per Cron (Takt in ``kern/jobs.py``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from kern.store import Store  # noqa: E402


def main() -> dict:
    store = Store(os.environ.get("RATSLOTSE_DB") or ROOT / "data" / "ratslotse.sqlite")
    try:
        recherchen = store.deep_jobs_frist_abgelaufen()
    finally:
        store.close()
    print(f"Recherchen nach Ablauf der Frist gelöscht: {recherchen}")
    return {"recherchen_geloescht": recherchen}


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("speicherfristen", main)
