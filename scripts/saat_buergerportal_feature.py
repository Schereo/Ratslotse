#!/usr/bin/env python3
"""Erzeugt die fiktiven Problembeispiele ausschließlich in ``~/app-feature``.

Kein frei wählbarer Datenbankpfad: Das Skript liest die aktuelle Konfiguration
und der Seeder akzeptiert sie nur, wenn Checkout und Ziel exakt zur isolierten
Feature-Instanz gehören. Dev und Produktion scheitern vor dem ersten Schreibzugriff.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from app.config import get_settings  # noqa: E402
from buergerportal.feature_examples import seed_feature_examples  # noqa: E402


def main() -> int:
    count = seed_feature_examples(
        get_settings().ratslotse_db,
        deployment_root=ROOT,
    )
    print(f"{count} klar gekennzeichnete Bürgerportal-Beispiele sind bereit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
