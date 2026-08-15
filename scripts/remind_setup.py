#!/usr/bin/env python3
"""Erinnert einmalig an eine angefangene, nicht beendete Einrichtung (Design 26a).

Warum per E-Mail und nicht per Push: Die Erlaubnis für Mitteilungen holt der
Assistent erst in Schritt 3 ein. Wer vorher abbricht — also genau die Gruppe,
um die es hier geht — hat nie zugestimmt, und es existiert kein Push-Token. Die
E-Mail-Adresse dagegen liegt seit der Registrierung vor.

Zurückhaltung ist eingebaut, damit daraus kein Newsletter wird:
- genau EINE Mail je Konto, nie wieder (``setup_reminded_at``),
- erst ab Schritt 1 (wer beim Gruß abbricht, hat nichts angefangen),
- frühestens nach ``REMIND_AFTER_HOURS`` ohne Fortschritt,
- nur an aktive Konten mit bestätigter Adresse.

Aufruf: täglich per Cron. Ohne RESEND_API_KEY passiert nichts (send_email ist
dann ein No-Op) — der Lauf meldet das sauber statt zu scheitern.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ohne diese Zeile lief der Job jahrelang ins Leere: Unter Cron gibt es keine
# Shell-Umgebung, RESEND_API_KEY war also nie gesetzt, `email_ready()` immer
# False — und der Lauf meldete brav „kein_mailversand" und endete mit Erfolg.
# In job_runs sah der Job dadurch dauerhaft grün aus, während nie eine
# Erinnerung rausging. Alle anderen Cron-Einstiegspunkte laden .env; nur dieser
# hier nicht.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from kern.digest_email import render_html_email  # noqa: E402
from kern.email import email_ready, send_email  # noqa: E402
from kern.store import Store  # noqa: E402

REMIND_AFTER_HOURS = int(os.environ.get("SETUP_REMIND_AFTER_HOURS", "48"))
APP_URL = os.environ.get("APP_BASE_URL", "https://ratslotse.de")

# Was im jeweiligen Schritt offen ist — die Mail sagt konkret, was noch fehlt,
# statt allgemein „mach mal weiter".
OPEN_AT_STEP = {
    1: "Du wolltest gerade Gremien auswählen, über die Lotti dich informiert.",
    2: "Du wolltest gerade Themen anlegen, zu denen Lotti sich meldet.",
    3: "Es fehlt nur noch die Erlaubnis für Mitteilungen.",
}


def _body(name: str | None, step: int) -> str:
    offen = OPEN_AT_STEP.get(step, "Ein paar Handgriffe fehlen noch.")
    return (
        f"<p>{offen}</p>"
        "<p>Die Einrichtung dauert keine Minute — danach meldet sich Ratslotse, "
        "sobald der Oldenburger Rat zu deinen Themen entscheidet.</p>"
        f'<p><a href="{APP_URL}">Einrichtung fortsetzen</a></p>'
        "<p style=\"color:#6b7c8d;font-size:13px\">Diese Erinnerung schicken wir "
        "genau einmal — du bekommst sie nicht noch einmal.</p>"
    )


def main() -> dict:
    # Store verlangt einen Pfad — `Store()` warf hier bei JEDEM Lauf sofort einen
    # TypeError, noch vor der Mail-Prüfung. Der Job hat also nie eine Erinnerung
    # verschickt, sondern ist immer abgestürzt. Pfad wie in den übrigen
    # Cron-Skripten: NWZ_DB, sonst data/nwz.sqlite im Repo.
    store = Store(os.environ.get("NWZ_DB") or ROOT / "data" / "nwz.sqlite")
    pending = store.setups_to_remind(older_than_hours=REMIND_AFTER_HOURS)
    if not pending:
        return {"kandidaten": 0, "gesendet": 0}
    if not email_ready():
        # Kein Schlüssel → nichts verschicken UND nichts als erinnert markieren,
        # sonst verlöre man die Kandidaten stillschweigend.
        print(f"{len(pending)} offene Einrichtungen, aber kein RESEND_API_KEY — übersprungen.")
        return {"kandidaten": len(pending), "gesendet": 0, "grund": "kein_mailversand"}

    sent = 0
    for u in pending:
        step = int(u.get("setup_step") or 0)
        try:
            send_email(
                u["email"],
                "Deine Einrichtung bei Ratslotse wartet noch",
                render_html_email(
                    "Fast fertig eingerichtet",
                    _body(u.get("display_name"), step),
                    greeting_name=u.get("display_name"),
                ),
            )
        except Exception as exc:  # noqa: BLE001 — ein Fehlschlag stoppt nicht den Rest
            print(f"  Mail an Konto {u['id']} fehlgeschlagen: {exc}")
            continue
        # Erst nach erfolgreichem Versand markieren: Ein Fehlschlag darf die
        # einzige Erinnerung nicht verbrauchen.
        store.mark_setup_reminded(u["id"])
        sent += 1
        print(f"  erinnert: Konto {u['id']} (Schritt {step})")
    return {"kandidaten": len(pending), "gesendet": sent}


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("remind_setup", main)
