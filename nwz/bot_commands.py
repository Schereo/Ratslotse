from __future__ import annotations

import os
from pathlib import Path

from .store import Store
from .telegram_bot import reply, reply_with_buttons, edit_message_buttons, answer_callback_query

_HELP = """\
<b>Verfügbare Befehle</b>

/topics — Deine gespeicherten Themen anzeigen
/add <i>Name</i> | <i>Beschreibung</i> — Neues Thema hinzufügen
/delete <i>ID</i> — Thema löschen

<i>Beispiel:</i>
<code>/add Radwege | Ausbau und Planung von Radwegen in Oldenburg</code>

Gespeicherte Themen werden täglich gegen die NWZ und den Stadtrat geprüft.

<b>Ausschuss-Abonnements</b>
/committees — Alle Ausschüsse anzeigen (✅ = abonniert)
/subscriptions — Deine Ausschuss-Abos anzeigen
/check — Sitzungsagendas für deine Abos jetzt prüfen\
"""

_ADMIN_HELP = """\


<b>Admin-Befehle</b>
/users — Alle registrierten Nutzer
/approve <i>chat_id</i> [<i>Name</i>] — Nutzer freischalten
/revoke <i>chat_id</i> — Nutzer entfernen (inkl. seiner Themen)\
"""


def _committee_buttons(all_names: list[str], subscribed: set[str]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    row: list[dict] = []
    for i, name in enumerate(all_names, 1):
        marker = "✅" if name in subscribed else "➕"
        # Use index as callback_data to stay well under Telegram's 64-byte limit
        row.append({"text": f"{marker} {i}", "callback_data": f"ctoggle:{i}"})
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


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

    elif command == "/committees":
        from council.store import CouncilStore
        council_db = db_path.parent / "council.sqlite"
        council_store = CouncilStore(council_db)
        all_names = council_store.get_all_committee_names()
        council_store.close()
        if not all_names:
            reply(chat_id, "Keine Ausschüsse in der Datenbank.")
        else:
            subscribed = set(store.get_subscriptions(chat_id))
            lines = ["<b>Ausschüsse</b>\n"]
            for i, name in enumerate(all_names, 1):
                marker = "✅" if name in subscribed else "➕"
                lines.append(f"{i}. {marker} {_esc(name)}")
            lines.append("\nButtons klicken = abonnieren/kündigen.")
            text = "\n".join(lines)
            buttons = _committee_buttons(all_names, subscribed)
            if reply_with_buttons(chat_id, text, buttons) is None:
                reply(chat_id, text)

    elif command == "/check":
        subs = store.get_subscriptions(chat_id)
        if not subs:
            reply(chat_id, "Du hast keine Ausschuss-Abos. Abonniere Ausschüsse mit /committees.")
            return

        from datetime import date, timedelta
        from council.store import CouncilStore
        from council.committee_summary import summarize_agenda
        from council.scraper import AgendaItem

        council_db = db_path.parent / "council.sqlite"
        council_store = CouncilStore(council_db)
        sessions = council_store.upcoming_sessions(limit=200)

        if not sessions:
            council_store.close()
            reply(
                chat_id,
                "Bisher keine Sitzungstermine in der Datenbank. "
                "Neue Termine werden täglich geprüft, sobald sie veröffentlicht werden.",
            )
            return

        cutoff = (date.today() + timedelta(days=90)).isoformat()
        subscribed = set(subs)
        relevant = [
            s for s in sessions
            if s["committee"] in subscribed and s["session_date"] <= cutoff
        ]

        if not relevant:
            council_store.close()
            reply(chat_id, "Keine bevorstehenden Sitzungen für deine abonnierten Ausschüsse in den nächsten 3 Monaten.")
            return

        base_url = "https://buergerinfo.oldenburg.de"
        for session in relevant:
            ksinr = session["ksinr"]
            items_raw = council_store.agenda_items(ksinr)
            agenda_items = [
                AgendaItem(
                    item_number=i["item_number"],
                    title=i["title"],
                    vorlage_nr=i["vorlage_nr"] or "",
                    kvonr=i["kvonr"],
                    is_public=bool(i["is_public"]),
                )
                for i in items_raw
            ]
            session_url = f"{base_url}/si0057.php?__ksinr={ksinr}"
            summary = summarize_agenda(
                committee=session["committee"],
                session_date=session["session_date"],
                session_time=session["session_time"],
                location=session["location"],
                agenda_items=agenda_items,
                session_url=session_url,
            )
            if summary:
                reply(chat_id, summary)
            else:
                fallback = (
                    f"<b>{_esc(session['committee'])}</b>\n"
                    f"📅 {session['session_date']}  {session['session_time']} Uhr\n\n"
                    f"Tagesordnung enthält nur Routine-TOPs.\n"
                    f'<a href="{session_url}">Tagesordnung →</a>'
                )
                reply(chat_id, fallback)

        council_store.close()

    elif command == "/subscriptions":
        subs = store.get_subscriptions(chat_id)
        if not subs:
            reply(chat_id, "Du hast keine Ausschuss-Abos.")
        else:
            lines = ["<b>Deine Ausschuss-Abos</b>\n"]
            for name in subs:
                lines.append(f"• {_esc(name)}")
            reply(chat_id, "\n".join(lines))

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


def handle_callback_query(update: dict, db_path: Path) -> None:
    cq = update.get("callback_query")
    if not cq:
        return

    callback_query_id: str = cq["id"]
    chat_id: int = cq["from"]["id"]
    message_id: int = cq["message"]["message_id"]
    callback_data: str = cq.get("data", "")

    store = Store(db_path)

    if not store.is_user(chat_id):
        answer_callback_query(callback_query_id, "Nicht autorisiert.")
        return

    if callback_data.startswith("ctoggle:"):
        raw = callback_data[len("ctoggle:"):]

        from council.store import CouncilStore
        council_db = db_path.parent / "council.sqlite"
        council_store = CouncilStore(council_db)
        all_names = council_store.get_all_committee_names()
        council_store.close()

        if raw.isdigit():
            idx = int(raw)
            if not 1 <= idx <= len(all_names):
                answer_callback_query(callback_query_id, "Ungültiger Ausschuss.")
                return
            committee_name = all_names[idx - 1]
        else:
            # Legacy: old messages had callback_data = ctoggle:{name}
            committee_name = raw

        subscribed = set(store.get_subscriptions(chat_id))
        if committee_name in subscribed:
            store.unsubscribe(chat_id, committee_name)
            toast = "❌ Ausschuss gekündigt"
        else:
            store.subscribe(chat_id, committee_name)
            toast = "✅ Ausschuss abonniert"

        answer_callback_query(callback_query_id, toast)

        new_subscribed = set(store.get_subscriptions(chat_id))
        buttons = _committee_buttons(all_names, new_subscribed)
        edit_message_buttons(chat_id, message_id, buttons)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
