#!/usr/bin/env python3
"""Grant moderation-only rights to an already registered web account.

The command never creates an account. It is the idempotent deployment bootstrap
for a verified, active moderator without general admin rights::

    .venv/bin/python scripts/grant_moderator.py moderation@example.org
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from kern.store import Store  # noqa: E402


def _default_db() -> str:
    return os.environ.get("RATSLOTSE_DB") or str(ROOT / "data" / "ratslotse.sqlite")


def _moderation_enabled() -> bool:
    return os.environ.get("RATSLOTSE_BUERGERPORTAL") == "1" or ROOT.name == "app-feature"


def grant_moderator(email: str, db_path: str | None = None) -> tuple[bool, str]:
    """Make an existing account an active, verified moderator."""
    address = (email or "").strip().lower()
    if not address:
        return False, "Keine E-Mail-Adresse angegeben."
    if not _moderation_enabled():
        return False, "Die Moderationsrolle ist in dieser Umgebung nicht verfügbar."
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
        if user.get("role") != "moderator":
            store.set_web_user_role(user_id, "moderator")
            changed.append("Rolle → moderator")
        if user.get("status") != "active":
            store.set_web_user_status(user_id, "active")
            changed.append("Status → active")
        if not user.get("email_verified"):
            store.set_email_verified(user_id, True)
            changed.append("E-Mail → bestätigt")
        if not changed:
            return True, f"{address} ist bereits Moderator — nichts zu tun."
        return True, f"{address}: {', '.join(changed)}."
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Moderationsrechte an ein registriertes Web-Konto vergeben."
    )
    parser.add_argument("email", help="E-Mail-Adresse eines registrierten Kontos")
    args = parser.parse_args(argv)
    try:
        ok, message = grant_moderator(args.email)
    except Exception as exc:  # noqa: BLE001 — CLI reports database errors cleanly
        print(f"✗  Datenbankfehler: {exc}", file=sys.stderr)
        return 2
    if ok:
        print(f"✓  {message}")
        return 0
    print(f"✗  {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
