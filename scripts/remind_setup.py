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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nwz.digest_email import render_html_email  # noqa: E402
from nwz.email import email_ready, send_email  # noqa: E402
from nwz.store import Store  # noqa: E402

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
    store = Store()
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
    from nwz.alerts import run_guarded

    run_guarded("remind_setup", main)
