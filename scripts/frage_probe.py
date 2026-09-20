"""Eine KI-Frage auf dem Server stellen und die Antwort samt Quellen ausgeben.

Wofür: die Ende-zu-Ende-Probe einer Retrieval-Änderung — „bekommt die
Sumpfeichen-Frage jetzt die Baumfällungen an der Nadorster Straße?" — ohne
Browser, ohne Konto-Passwort und ohne den 1Password-Agenten auf dem Notebook.
Am 20.09.2026 hing genau daran die letzte Messung eines gemergten PRs: Der
Agent antwortete nicht mehr, und ohne ihn führt kein Weg auf die VMs. Der
Workflow ``ops-frage-probe.yml`` ruft dieses Skript mit dem Deploy-Key auf.

Das Token entsteht wie bei der Rauchprobe (``rauchprobe.token_bauen``): aus
``WEB_JWT_SECRET`` und der Konto-Zeile von ``RAUCHPROBE_KONTO`` bzw.
``WEB_ADMIN_EMAIL``, fünf Minuten gültig, nichts gespeichert. Die Frage zählt
damit als Frage dieses Kontos — wie eine Rauchprobe auch.

Ausgabe: Analyse-Zeit, Quellen (Datum, Titel, id), zitierte ids, Antwort.
Keine Konto- oder Personendaten, nur das, was jede angemeldete Person auf
der Frage-Seite auch sieht.

    .venv/bin/python scripts/frage_probe.py "Wie viele Sumpfeichen …?"
    .venv/bin/python scripts/frage_probe.py --verlauf "Erste Frage" "Zweite Frage" "Dritte Frage"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

#: So viel Antwort hängt der Verlauf an eine Anschlussfrage (``AskTurn.answer``).
VERLAUF_ANTWORT_MAX = 600


def fragen(basis: str, token: str, frage: str, verlauf: list[dict]) -> str:
    """Eine Frage über den Ereignis-Strom stellen; gibt den Antworttext zurück."""
    t0 = time.time()
    antwort = requests.post(
        f"{basis}/api/council/ask",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"question": frage, "history": verlauf}, stream=True, timeout=240,
    )
    antwort.raise_for_status()
    text: list[str] = []
    quellen: list[dict] = []
    zitiert: list[int] = []
    for zeile in antwort.iter_lines(decode_unicode=True):
        if not zeile or not zeile.startswith("data:"):
            continue
        try:
            ereignis = json.loads(zeile[5:].strip())
        except ValueError:
            continue
        art = ereignis.get("type")
        if art == "token":
            text.append(ereignis.get("text") or "")
        elif art == "sources":
            quellen = ereignis.get("sources") or ereignis.get("items") or []
        elif art == "done":
            zitiert = ereignis.get("cited") or []
    ganz = "".join(text)
    print("=" * 78)
    print("FRAGE:", frage)
    print(f"({time.time() - t0:.1f} s · {len(quellen)} Quellen · {len(zitiert)} zitiert)")
    for q in quellen[:8]:
        print(f"   - {q.get('session_date') or q.get('date') or '?'} | "
              f"{(q.get('title') or '')[:90]} | {q.get('id')}")
    print("ANTWORT:")
    print(ganz.strip())
    return ganz


def main() -> int:
    ap = argparse.ArgumentParser(description="Eine KI-Frage auf dem Server stellen")
    ap.add_argument("fragen", nargs="+", help="eine Frage — oder mit --verlauf mehrere nacheinander")
    ap.add_argument("--verlauf", action="store_true",
                    help="die Fragen als EIN Gespräch stellen (jede kennt die vorigen)")
    ap.add_argument("--basis", default="http://127.0.0.1:8000")
    ap.add_argument("--konto", default=None, help="Konto-Adresse fürs Token (Vorgabe wie Rauchprobe)")
    args = ap.parse_args()

    import rauchprobe  # noqa: E402 — liegt neben diesem Skript
    token, info = rauchprobe.token_bauen(WURZEL, args.konto)
    if not token:
        print(f"Kein Token: {info}", file=sys.stderr)
        return 2

    verlauf: list[dict] = []
    for frage in args.fragen:
        antwort = fragen(args.basis, token, frage, verlauf if args.verlauf else [])
        if args.verlauf:
            verlauf.append({"question": frage[:300], "answer": antwort[:VERLAUF_ANTWORT_MAX]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
