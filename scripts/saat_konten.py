#!/usr/bin/env python3
"""Eine Konten-Datenbank mit erfundenen Konten — für lokale Arbeit und Tests.

**Warum erfunden und nicht kopiert.** Die echte Konten-Datenbank trägt
Adressen, Anmelde-Tokens und gespeicherte Gespräche. Sie gehört auf kein
Notebook und in keinen Agenten-Worktree. Die Ratsdaten dagegen sind öffentlich
und kommen als Abzug (``scripts/lokale_daten.py``); nur die Konten müssen
gebaut statt geholt werden.

Was entsteht:

* ``admin@test.de`` mit Admin-Rolle — dieselbe Adresse, die die Browsertests
  benutzen (``web/frontend/tests/e2e/helpers.ts``);
* ``nutzerin@example.org`` als normales Konto mit Themen, Merkliste und
  Benachrichtigungs-Einstellungen;
* beide bestätigt und aktiv, Passwort ``password123``.

Aufruf::

    python scripts/saat_konten.py                       # nach data/ratslotse.sqlite
    python scripts/saat_konten.py --db /tmp/x.sqlite    # woandershin
    python scripts/saat_konten.py --ueberschreiben      # vorhandene ersetzen

Die Themen bekommen ihre Treffer aus der Rats-Datenbank, wenn eine da ist —
so sieht die Themen-Seite lokal aus wie in echt und nicht wie am ersten Tag.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "web" / "backend"))

PASSWORT = "password123"

#: Themen mit ihren Suchwörtern — sie treffen im echten Bestand wirklich etwas.
THEMEN = [
    ("Radverkehr", "Radwege, Fahrradstraßen und Abstellanlagen in Oldenburg"),
    ("Kitas", "Kindertagesstätten, Betreuungsplätze und Elternbeiträge"),
    ("Fliegerhorst", "Entwicklung des ehemaligen Fliegerhorst-Geländes"),
]


def _hash(passwort: str) -> str:
    os.environ.setdefault("WEB_JWT_SECRET", "saat")
    from app.security import hash_password

    return hash_password(passwort)


def saat(db: Path, council_db: Path | None) -> dict:
    from kern.store import Store

    store = Store(db)
    bericht: dict[str, int | str] = {"datenbank": str(db)}
    try:
        pw = _hash(PASSWORT)
        admin = store.create_web_user("admin@test.de", pw, role="admin",
                                      status="active", email_verified=True,
                                      display_name="Admin")
        nutzerin = store.create_web_user("nutzerin@example.org", pw, role="user",
                                         status="active", email_verified=True,
                                         display_name="Nutzerin")
        bericht["admin_id"] = admin
        bericht["nutzerin_id"] = nutzerin

        themen = [store.add_topic(nutzerin, name, beschreibung)
                  for name, beschreibung in THEMEN]
        bericht["themen"] = len(themen)

        # Treffer aus dem echten Bestand, wo einer da ist. Ohne sie steht die
        # Themen-Seite lokal ewig auf „noch nichts gefunden" — genau der
        # Zustand, in dem niemand merkt, dass die Liste ab 40 Treffern anders
        # aussieht.
        treffer = 0
        if council_db and council_db.exists():
            from council.store import CouncilStore

            rat = CouncilStore(council_db)
            try:
                for thema, (name, _) in zip(themen, THEMEN):
                    zeilen = rat.search_decisions(name, limit=8)
                    paare = [(z["id"], 1.0) for z in zeilen]
                    # `als_neu=False`: Der Saatlauf ist kein Fund, sondern ein
                    # Bestand. Mit True stünden alle Treffer als ungelesen da
                    # und die Oberfläche zeigte einen Zähler, den nie jemand
                    # ausgelöst hat.
                    treffer += store.save_topic_decision_matches(
                        thema.id, nutzerin, paare, als_neu=False)
            except Exception as fehler:  # noqa: BLE001 — Saat darf daran nicht sterben
                print(f"  (keine Treffer eingetragen: {fehler})", file=sys.stderr)
            finally:
                rat.close()
        bericht["treffer"] = treffer
    finally:
        store.close()
    return bericht


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=WURZEL / "data" / "ratslotse.sqlite")
    p.add_argument("--council-db", type=Path,
                   default=WURZEL / "data" / "council.sqlite",
                   help="Rats-Datenbank für die Themen-Treffer (optional)")
    p.add_argument("--ueberschreiben", action="store_true")
    args = p.parse_args()

    if args.db.exists():
        if not args.ueberschreiben:
            print(f"{args.db} gibt es schon — mit --ueberschreiben ersetzen.",
                  file=sys.stderr)
            return 1
        for rest in ("", "-wal", "-shm"):
            q = Path(str(args.db) + rest)
            if q.exists():
                q.unlink()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    bericht = saat(args.db, args.council_db)
    print(f"✓ {args.db}")
    print(f"  admin@test.de (Admin) und nutzerin@example.org — Passwort {PASSWORT}")
    print(f"  {bericht['themen']} Themen, {bericht['treffer']} Treffer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
