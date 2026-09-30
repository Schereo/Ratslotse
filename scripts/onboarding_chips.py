#!/usr/bin/env python3
"""Was der Einrichtungs-Assistent anbietet — und was davon gewählt wird.

Liest ``onboarding_chip_stats`` (s. ``kern/store.py``) und schreibt je Chip:
wie oft angezeigt, wie oft gewählt, Quote. Nur Bericht, schreibt nichts.

    .venv/bin/python scripts/onboarding_chips.py            # letzte 14 Tage
    .venv/bin/python scripts/onboarding_chips.py --tage 60

Auf dem Server mit dem Python der App (``~/app/.venv/bin/python``); der Pfad
der Datenbank kommt aus ``RATSLOTSE_DB``, sonst ``data/ratslotse.sqlite``.

**Wie man die Zahlen liest.** ``city_topic:*`` sind die kuratierten Themen mit
Bild; ``district`` ist jede Fläche auf der Karte, die jemand anklickt
(Anzeigen zählen dort je Besuch des Schritts, nicht je Fläche — die Spalte zeigt deshalb Wahlen je Besuch statt einer Quote), ``district_suggestion``
die Karten „Aus deinen Stadtteilen", ``own`` ein selbst getipptes Thema. Die
Quote eines Stadtthemas ist Wahlen geteilt durch Anzeigen: Sie sagt, ob ein
Bild oder Thema zieht, unabhängig davon, wie viele Leute kamen.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


def bericht(zeilen: list[dict]) -> list[str]:
    """Die Tabelle als Textzeilen — getrennt von der Abfrage, damit sie testbar ist."""
    out = [f"{'Chip':34}{'gezeigt':>9}{'gewählt':>9}{'Quote':>8}"]
    for z in sorted(zeilen, key=lambda z: (-(z["picked"] or 0), z["chip"])):
        gezeigt, gewaehlt = z["shown"] or 0, z["picked"] or 0
        if not gezeigt:
            quote = "—"
        elif z["chip"] == "district":
            # „Gezeigt" zählt hier den Besuch des Schritts, „gewählt" jede
            # Fläche: eine Quote über 100 % wäre Unsinn, „je Besuch" nicht.
            quote = f"{gewaehlt / gezeigt:.1f}×"
        else:
            quote = f"{100 * gewaehlt / gezeigt:.0f} %"
        out.append(f"{z['chip']:34}{gezeigt:>9}{gewaehlt:>9}{quote:>8}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tage", type=int, default=14)
    args = ap.parse_args()

    from kern.store import Store, today_utc

    db = Path(os.environ.get("RATSLOTSE_DB", WURZEL / "data" / "ratslotse.sqlite"))
    store = Store(db)
    try:
        seit = (today_utc() - timedelta(days=max(1, args.tage))).isoformat()
        zeilen = store.onboarding_chip_stats_since(seit)
    finally:
        store.close()
    if not zeilen:
        print(f"Seit {seit} hat der Assistent nichts gezählt.")
        return 0
    print(f"Einrichtungs-Assistent seit {seit}\n")
    print("\n".join(bericht(zeilen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
