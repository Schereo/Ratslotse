#!/usr/bin/env python3
"""Die Wegwerf-Domain-Liste im Repo (`kern/disposable_email_domains.txt`) nachziehen.

Adressen von Wegwerf-Anbietern bekommen keine Mail (`kern/disposable_email.py`).
Die Liste dahinter pflegt ein öffentliches Projekt; neue Anbieter kommen dort
wöchentlich dazu. Auf dem Server zieht der tägliche Herzschlag sie seit 11/2026
selbst nach, in eine Kopie unter `data/`. Dieses Skript ist der Weg ins Repo:
Es holt den aktuellen Stand, prüft ihn mit denselben Regeln
(`disposable_email.pruefe`) und schreibt ihn — auf Wunsch — in die Datei im
Repo. Danach ist es ein normaler Commit.

    .venv/bin/python scripts/update_disposable_domains.py              # Bericht
    .venv/bin/python scripts/update_disposable_domains.py --schreiben  # und schreiben

Was NICHT übernommen wird, sondern das Skript mit Exit 2 abbrechen lässt:
Zeilen, die keine Domain sind, mehr als zehn Prozent Schwund und jeder Eintrag
aus `PROTECTED_DOMAINS` (Begründung an `pruefe`).

Exit-Codes:
    0  Bericht (und ggf. Datei) geschrieben
    2  Liste nicht übernommen (Grund steht auf stderr) oder Abruf fehlgeschlagen
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kern import disposable_email  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schreiben", action="store_true",
                        help="Datei im Repo überschreiben (Vorgabe: nur berichten)")
    args = parser.parse_args(argv)

    try:
        neu = disposable_email.parse_list(disposable_email.abrufen())
    except (urllib.error.URLError, OSError) as e:
        print(f"Abruf fehlgeschlagen: {e}", file=sys.stderr)
        return 2
    # Gegen die Datei im REPO, nicht gegen die geltende Liste: Die kann eine
    # nachgezogene Kopie aus data/ sein, und der Bericht soll den Commit
    # beschreiben.
    alt = disposable_email.parse_list(disposable_email.LIST_PATH.read_text(encoding="utf-8"))

    gruende = disposable_email.pruefe(neu, alt)
    if gruende:
        for g in gruende:
            print(f"NICHT übernommen: {g}", file=sys.stderr)
        return 2

    dazu, weg = sorted(neu - alt), sorted(alt - neu)
    print(f"bisher {len(alt)}, upstream {len(neu)}: +{len(dazu)} / -{len(weg)}")
    for d in dazu[:20]:
        print(f"  + {d}")
    if len(dazu) > 20:
        print(f"  … und {len(dazu) - 20} weitere")
    for d in weg[:20]:
        print(f"  - {d}")
    if len(weg) > 20:
        print(f"  … und {len(weg) - 20} weitere")

    if not args.schreiben:
        print("(nur Bericht — mit --schreiben wird die Datei aktualisiert)")
        return 0
    disposable_email.LIST_PATH.write_text(disposable_email.render(neu, date.today()),
                                          encoding="utf-8")
    print(f"geschrieben: {disposable_email.LIST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
