#!/usr/bin/env python3
"""Die Wegwerf-Domain-Liste (`kern/disposable_email_domains.txt`) nachziehen.

Registrierung und Adresswechsel weisen Adressen von Wegwerf-Anbietern ab
(`kern/disposable_email.py`). Die Liste dahinter pflegt ein öffentliches
Projekt; neue Anbieter kommen dort wöchentlich dazu. Dieses Skript holt den
aktuellen Stand, prüft ihn und schreibt ihn — auf Wunsch — in die Datei im
Repo. Danach ist es ein normaler Commit; der Server bekommt die Liste mit dem
nächsten Deploy.

    .venv/bin/python scripts/update_disposable_domains.py              # Bericht
    .venv/bin/python scripts/update_disposable_domains.py --schreiben  # und schreiben

Was NICHT übernommen wird, sondern das Skript mit Exit 2 abbrechen lässt:

* Zeilen, die keine Domain sind (Großbuchstaben, Sonderzeichen, kein Punkt) —
  eine Liste, die plötzlich anders aussieht, ist eher ein geänderter Upstream
  als ein neuer Anbieter;
* eine Liste, die um mehr als zehn Prozent geschrumpft ist — ein Upstream, der
  gerade umbaut, soll nicht tausende Anbieter bei uns freischalten;
* ein Eintrag aus `PROTECTED_DOMAINS` — der wäre zwar wirkungslos (die Menge
  gewinnt), aber ein Zeichen, dass die Liste jemanden Echtes erwischt hat.

Exit-Codes:
    0  Bericht (und ggf. Datei) geschrieben
    2  Liste nicht übernommen (Grund steht auf stderr) oder Abruf fehlgeschlagen
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kern import disposable_email  # noqa: E402

_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
_MAX_SHRINK = 0.10


def fetch(url: str = disposable_email.UPSTREAM_URL) -> str:
    with urllib.request.urlopen(url, timeout=30) as antwort:  # noqa: S310 — feste https-URL
        return antwort.read().decode("utf-8")


def render(domains: frozenset[str], stand: date) -> str:
    kopf = (
        "# Wegwerf-E-Mail-Domains — gelesen von kern/disposable_email.py.\n"
        "# Quelle: https://github.com/disposable-email-domains/disposable-email-domains\n"
        "#         (disposable_email_blocklist.conf), Lizenz CC0 1.0 (Public Domain).\n"
        "# Nachziehen: .venv/bin/python scripts/update_disposable_domains.py --schreiben\n"
        f"# Stand: {stand.isoformat()}\n"
        "# Eine Domain je Zeile, kleingeschrieben; Zeilen mit # werden überlesen.\n"
    )
    return kopf + "\n".join(sorted(domains)) + "\n"


def pruefe(neu: frozenset[str], alt: frozenset[str]) -> list[str]:
    """Gründe, die Liste NICHT zu übernehmen — leer heißt: in Ordnung."""
    gruende: list[str] = []
    kaputt = sorted(d for d in neu if not _DOMAIN.match(d))
    if kaputt:
        gruende.append(f"{len(kaputt)} Zeilen sind keine Domain, z. B. {kaputt[:3]}")
    if alt and len(neu) < len(alt) * (1 - _MAX_SHRINK):
        gruende.append(f"Liste geschrumpft: {len(alt)} → {len(neu)} Einträge")
    geschuetzt = sorted(neu & disposable_email.PROTECTED_DOMAINS)
    if geschuetzt:
        gruende.append(f"geschützte Anbieter in der Liste: {geschuetzt}")
    return gruende


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schreiben", action="store_true",
                        help="Datei im Repo überschreiben (Vorgabe: nur berichten)")
    args = parser.parse_args(argv)

    try:
        neu = disposable_email.parse_list(fetch())
    except (urllib.error.URLError, OSError) as e:
        print(f"Abruf fehlgeschlagen: {e}", file=sys.stderr)
        return 2
    alt = disposable_email.blocked_domains()

    gruende = pruefe(neu, alt)
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
    disposable_email.LIST_PATH.write_text(render(neu, date.today()), encoding="utf-8")
    print(f"geschrieben: {disposable_email.LIST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
