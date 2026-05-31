from __future__ import annotations

import os
from pathlib import Path

from .store import Store
from .telegram_bot import reply

_HELP = """\
<b>Verfügbare Befehle</b>

/topics — Deine gespeicherten Themen anzeigen
/add <i>Name</i> | <i>Beschreibung</i> — Neues Thema hinzufügen
/delete <i>ID</i> — Thema löschen

<i>Beispiel:</i>
<code>/add Radwege | Ausbau und Planung von Radwegen in Oldenburg</code>

Gespeicherte Themen werden täglich gegen die NWZ und den Stadtrat geprüft.\
"""

_ADMIN_HELP = """\


<b>Admin-Befehle</b>
/users — Alle registrierten Nutzer
/approve <i>chat_id</i> [<i>Name</i>] — Nutzer freischalten
/revoke <i>chat_id</i> — Nutzer entfernen (inkl. seiner Themen)\
"""


def _admin_chat_id() -> int:
    return int(os.environ.get("TELEGRAM_CHAT_ID", 0))


def _is_admin(chat_id: int) -> bool:
    return chat_id == _admin_chat_id()


def handle_update(update: dict, db_path: Path) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id: int = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    parts = text.split(None, 1)
    command = parts[0].split("@")[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    store = Store(db_path)

    # /start — always allowed, shows status + chat_id
    if command == "/start":
        if store.is_user(chat_id):
            reply(chat_id, "Du bist bereits registriert. Schreib /help für eine Übersicht.")
        else:
            reply(
                chat_id,
                f"Hallo! Dieser Bot ist nur für autorisierte Nutzer.\n\n"
                f"Bitte teile dem Administrator deine Chat-ID mit:\n"
                f"<code>{chat_id}</code>\n\n"
                f"Er kann dich dann mit <code>/approve {chat_id}</code> freischalten.",
            )
        return

    # All other commands require whitelist membership
    if not store.is_user(chat_id):
        reply(
            chat_id,
            f"Du bist nicht autorisiert.\n\n"
            f"Deine Chat-ID: <code>{chat_id}</code>\n"
            f"Bitte den Administrator, dich freizuschalten.",
        )
        return

    if command == "/help":
        text_out = _HELP + (_ADMIN_HELP if _is_admin(chat_id) else "")
        reply(chat_id, text_out)

    elif command == "/topics":
        topics = store.get_topics(chat_id)
        if not topics:
            reply(chat_id, "Du hast noch keine Themen gespeichert.\n\nMit /add hinzufügen.")
        else:
            lines = ["<b>Deine Themen</b>\n"]
            for t in topics:
                lines.append(f"<b>[{t.id}] {_esc(t.name)}</b>\n  {_esc(t.description)}")
            lines.append("\nMit <code>/delete ID</code> löschen.")
            reply(chat_id, "\n".join(lines))

    elif command == "/add":
        if "|" not in args:
            reply(
                chat_id,
                "Format: <code>/add Name | Beschreibung</code>\n\n"
                "Beispiel:\n"
                "<code>/add Radwege | Ausbau und Planung von Radwegen in Oldenburg</code>",
            )
            return
        name, _, description = args.partition("|")
        name, description = name.strip(), description.strip()
        if not name or not description:
            reply(chat_id, "Name und Beschreibung dürfen nicht leer sein.")
            return
        t = store.add_topic(chat_id, name, description)
        reply(
            chat_id,
            f"Thema gespeichert (ID {t.id}):\n<b>{_esc(t.name)}</b>\n{_esc(t.description)}",
        )

    elif command == "/delete":
        if not args.isdigit():
            reply(chat_id, "Verwendung: <code>/delete ID</code>\n\nIDs mit /topics anzeigen.")
            return
        topic_id = int(args)
        topics = store.get_topics(chat_id)
        topic = next((t for t in topics if t.id == topic_id), None)
        if not topic:
            reply(chat_id, f"Kein Thema mit ID {topic_id} gefunden.")
            return
        store.delete_topic(topic_id)
        reply(chat_id, f"Thema <b>{_esc(topic.name)}</b> gelöscht.")

    # ---- Admin commands ----

    elif command == "/users":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /help für eine Übersicht.")
            return
        users = store.get_users()
        if not users:
            reply(chat_id, "Keine Nutzer registriert.")
            return
        lines = ["<b>Registrierte Nutzer</b>\n"]
        for u in users:
            topics = store.get_topics(u.chat_id)
            label = _esc(u.username) if u.username else "–"
            lines.append(
                f"<code>{u.chat_id}</code> {label} · {len(topics)} Thema(en)\n"
                f"  seit {u.added_at[:10]}"
            )
        reply(chat_id, "\n".join(lines))

    elif command == "/approve":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /help für eine Übersicht.")
            return
        tokens = args.split(None, 1)
        if not tokens or not tokens[0].lstrip("-").isdigit():
            reply(chat_id, "Verwendung: <code>/approve chat_id [Name]</code>")
            return
        target = int(tokens[0])
        username = tokens[1].strip() if len(tokens) > 1 else ""
        store.add_user(target, username)
        label = f" ({username})" if username else ""
        reply(chat_id, f"Nutzer <code>{target}</code>{label} freigeschaltet.")
        reply(
            target,
            "Du wurdest freigeschaltet! Schreib /help für eine Übersicht der Befehle.",
        )

    elif command == "/revoke":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /help für eine Übersicht.")
            return
        if not args.lstrip("-").isdigit():
            reply(chat_id, "Verwendung: <code>/revoke chat_id</code>")
            return
        target = int(args)
        if target == chat_id:
            reply(chat_id, "Du kannst dich nicht selbst entfernen.")
            return
        store.remove_user(target)
        reply(chat_id, f"Nutzer <code>{target}</code> entfernt (inkl. seiner Themen).")

    else:
        reply(chat_id, f"Unbekannter Befehl: {command}\n\n/help für eine Übersicht.")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
