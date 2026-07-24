#!/usr/bin/env python3
"""Adminrechte an ein **bereits bestehendes** Web-Konto vergeben.

Die Registrierung vergibt keine Rollen mehr — sonst hätte, wer die konfigurierte
`WEB_ADMIN_EMAIL` als Erstes ins Formular tippt, das Deployment übernommen, ohne
je zu beweisen, dass ihm dieses Postfach gehört. Stattdessen wird die Adresse aus
`WEB_ADMIN_EMAIL` erst mit der **E-Mail-Bestätigung** zum Admin (und nur, solange
es noch gar keinen Admin gibt).

Ohne `RESEND_API_KEY` gibt es aber keinen Bestätigungslink. Für diesen Fall — und
für „Admin ist ausgesperrt" — ist dieses Skript der Weg außen herum:

    # 1. Im Web ganz normal registrieren, dann auf dem Server:
    .venv/bin/python scripts/grant_admin.py tim@example.de

Es legt **nie** ein Konto an, normalisiert die Adresse (Kleinschreibung) und ist
idempotent: ein zweiter Lauf meldet nur „ist bereits Admin".

Exit-Codes:
    0  Konto ist Admin (frisch befördert oder war es schon)
    1  kein Konto mit dieser Adresse — es wurde keines angelegt
    2  Aufrufs- oder Datenbankfehler
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")  # NWZ_DB

from nwz.store import Store  # noqa: E402


def _default_db() -> str:
    """Dieselbe DB wie Bot, Cronjobs und Web-Backend."""
    return os.environ.get("NWZ_DB") or str(ROOT / "data" / "nwz.sqlite")


def grant_admin(email: str, db_path: str | None = None) -> tuple[bool, str]:
    """Ein vorhandenes Konto zum Admin machen. Gibt ``(ok, Meldung)`` zurück.

    Legt niemals ein Konto an: eine unbekannte Adresse ist ein Fehler, kein
    Anlass, ein Konto zu erfinden. Setzt neben der Rolle den Status auf
    ``active``, damit das Konto auch nutzbar ist.
    """
    address = (email or "").strip().lower()
    if not address:
        return False, "Keine E-Mail-Adresse angegeben."
    store = Store(db_path or _default_db())
    try:
        user = store.get_web_user_by_email(address)
        if user is None:
            return False, (
                f"Kein Konto mit {address}. Bitte zuerst im Web registrieren — "
                "dieses Skript legt keines an."
            )
        user_id = int(user["id"])
        changed: list[str] = []
        if user.get("role") != "admin":
            store.set_web_user_role(user_id, "admin")
            changed.append("Rolle → admin")
        if user.get("status") != "active":
            store.set_web_user_status(user_id, "active")
            changed.append("Status → active")
        if not changed:
            return True, f"{address} ist bereits Admin — nichts zu tun."
        return True, f"{address}: {', '.join(changed)}."
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adminrechte an ein bereits bestehendes Web-Konto vergeben."
    )
    parser.add_argument("email", help="E-Mail-Adresse eines bereits registrierten Kontos")
    args = parser.parse_args(argv)
    try:
        ok, message = grant_admin(args.email)
    except Exception as exc:  # noqa: BLE001 — DB fehlt/gesperrt: sauber melden statt Traceback
        print(f"✗  Datenbankfehler: {exc}", file=sys.stderr)
        return 2
    if ok:
        print(f"✓  {message}")
        return 0
    print(f"✗  {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
