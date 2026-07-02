from __future__ import annotations

import os
from pathlib import Path

from . import llm, prompts
from .store import Store, TopicRow
from .telegram_bot import reply, reply_with_buttons, edit_message_buttons, answer_callback_query

_START_NEW_USER = """\
👋 Willkommen beim Ratslotse-Bot!

Dieser Bot beobachtet den <b>Oldenburger Stadtrat</b> für dich und benachrichtigt dich zu deinen Themen — vollautomatisch.

<b>Was der Bot macht:</b>
🏛️ <b>Stadtrat-Alerts</b>
  Wenn eines deiner Themen auf der Tagesordnung einer Ratssitzung steht, bekommst du vorab eine Zusammenfassung.

📋 <b>Ausschuss-Benachrichtigungen</b>
  Abonniere einzelne Ausschüsse — du wirst benachrichtigt, sobald die Tagesordnung veröffentlicht wird, und nochmals wenn sie sich ändert.

<b>Du bist noch nicht freigeschaltet.</b>
Teile dem Administrator deine Chat-ID mit:
<code>{chat_id}</code>

Er kann dich mit <code>/freischalten {chat_id}</code> hinzufügen.\
"""

_START_EXISTING_USER = """\
Hallo, du bist bereits registriert! 👋

<b>Schnellstart:</b>
• <code>/neu Radwege | Ausbau von Radwegen in Oldenburg</code> — Thema hinzufügen
• <code>/ausschuesse</code> — Ausschüsse abonnieren
• <code>/themen</code> — deine gespeicherten Themen anzeigen

Der Bot meldet sich, sobald der Rat zu einem deiner Themen etwas beschließt.

Alle Befehle: /hilfe\
"""

_HELP = """\
<b>Ratslotse-Bot — Befehle</b>

<b>Themen</b>
/themen — gespeicherte Themen anzeigen
/neu <i>Name</i> | <i>Beschreibung</i> — Thema hinzufügen
/loeschen <i>ID</i> — Thema löschen

<b>Stadtrat &amp; Ausschüsse</b>
/ausschuesse — Ausschüsse anzeigen und abonnieren (✅ = abonniert)
/pruefen — Sitzungsagendas für deine Abos jetzt abrufen

<b>Info</b>
/hilfe — diese Übersicht

<i>Beispiel:</i>
<code>/neu Radwege | Ausbau und Planung von Radwegen in Oldenburg</code>

Wir melden uns, sobald der Rat zu einem deiner Themen etwas beschließt.\
"""

_ADMIN_HELP = """\


<b>Admin-Befehle</b>
/nutzer — alle registrierten Nutzer anzeigen
/freischalten <i>chat_id</i> [<i>Name</i>] — Nutzer freischalten
/sperren <i>chat_id</i> — Nutzer entfernen (inkl. seiner Themen)\
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


def _send_committees(chat_id: int, owner_id: int, store: "Store", db_path: Path) -> None:
    from council.store import CouncilStore
    council_db = db_path.parent / "council.sqlite"
    council_store = CouncilStore(council_db)
    all_names = council_store.get_all_committee_names()
    council_store.close()
    if not all_names:
        reply(chat_id, "Keine Ausschüsse in der Datenbank.")
    else:
        subscribed = set(store.get_subscriptions(owner_id))
        lines = ["<b>Ausschüsse</b>\n"]
        for i, name in enumerate(all_names, 1):
            marker = "✅" if name in subscribed else "➕"
            lines.append(f"{i}. {marker} {_esc(name)}")
        lines.append("\nButtons klicken = abonnieren/kündigen.")
        text = "\n".join(lines)
        buttons = _committee_buttons(all_names, subscribed)
        if reply_with_buttons(chat_id, text, buttons) is None:
            reply(chat_id, text)


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

    # /start — always allowed
    if command == "/start":
        if store.is_user(chat_id):
            reply(chat_id, _START_EXISTING_USER)
        else:
            reply(chat_id, _START_NEW_USER.format(chat_id=chat_id))
        return

    # /verbinden — links a web account; allowed before whitelisting, since
    # redeeming a valid code is itself what grants access.
    if command == "/verbinden":
        code = args.strip().split()[0] if args.strip() else ""
        if not code:
            reply(
                chat_id,
                "Verwendung: <code>/verbinden CODE</code>\n\n"
                "Den Code bekommst du im Web-Frontend unter „Mit Telegram verbinden“.",
            )
            return
        username = (msg.get("from") or {}).get("first_name", "")
        email = store.redeem_link_code(code, chat_id, username)
        if email:
            reply(
                chat_id,
                f"✅ Verbunden mit <b>{_esc(email)}</b>!\n\n"
                "Dein Web-Account ist jetzt mit diesem Chat verknüpft. "
                "Schreib /hilfe für eine Übersicht oder leg direkt mit /neu los.",
            )
        else:
            reply(chat_id, "❌ Code ungültig oder abgelaufen. Bitte erzeuge im Web einen neuen Code.")
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

    # Resolve this chat to its canonical owner (creates a synthetic web account
    # for Telegram-only users on first use). chat_id is only a delivery target.
    owner_id = store.ensure_owner_for_chat(chat_id)

    if command == "/hilfe":
        text_out = _HELP + (_ADMIN_HELP if _is_admin(chat_id) else "")
        reply(chat_id, text_out)

    elif command == "/themen":
        topics = store.get_topics(owner_id)
        if not topics:
            reply(chat_id, "Du hast noch keine Themen gespeichert.\n\nMit /neu hinzufügen.")
        else:
            lines = ["<b>Deine Themen</b>\n"]
            for t in topics:
                lines.append(f"<b>[{t.id}] {_esc(t.name)}</b>\n  {_esc(t.description)}")
            lines.append("\nMit <code>/loeschen ID</code> löschen.")
            reply(chat_id, "\n".join(lines))

    elif command == "/neu":
        if "|" not in args:
            reply(
                chat_id,
                "Format: <code>/neu Name | Beschreibung</code>\n\n"
                "Beispiel:\n"
                "<code>/neu Radwege | Ausbau und Planung von Radwegen in Oldenburg</code>\n\n"
                "Tipp: Eine gute Beschreibung verbessert die Trefferqualität deutlich.",
            )
            return
        name, _, description = args.partition("|")
        name, description = name.strip(), description.strip()
        if not name or not description:
            reply(chat_id, "Name und Beschreibung dürfen nicht leer sein.")
            return
        vague = _vagueness_hint(name, description)
        if vague:
            msg = (
                f"⚠️ Die Beschreibung klingt noch etwas vage:\n\n"
                f"<i>{_esc(vague['hint'])}</i>\n\n"
            )
            suggestion = vague.get("suggestion", "").strip()
            if suggestion:
                msg += (
                    f"💡 Vorschlag — einfach kopieren und absenden:\n"
                    f"<code>/neu {_esc(name)} | {_esc(suggestion)}</code>\n\n"
                    f"Oder formuliere selbst eine genauere Beschreibung."
                )
            else:
                msg += (
                    f"Bitte präzisiere dein Thema mit "
                    f"<code>/neu {_esc(name)} | &lt;genauere Beschreibung&gt;</code> "
                    f"— das verbessert die Trefferqualität deutlich."
                )
            reply(chat_id, msg)
            return
        t = store.add_topic(owner_id, name, description)
        reply(
            chat_id,
            f"✅ Thema gespeichert (ID {t.id}):\n<b>{_esc(t.name)}</b>\n{_esc(t.description)}\n\n"
            f"Wir melden uns, sobald der Rat zu deinem Thema etwas beschließt.",
        )

    elif command == "/loeschen":
        if not args.isdigit():
            reply(chat_id, "Verwendung: <code>/loeschen ID</code>\n\nIDs mit /themen anzeigen.")
            return
        topic_id = int(args)
        topics = store.get_topics(owner_id)
        topic = next((t for t in topics if t.id == topic_id), None)
        if not topic:
            reply(chat_id, f"Kein Thema mit ID {topic_id} gefunden.")
            return
        store.delete_topic(topic_id)
        reply(chat_id, f"Thema <b>{_esc(topic.name)}</b> gelöscht.")

    elif command == "/ausschuesse":
        _send_committees(chat_id, owner_id, store, db_path)

    elif command == "/pruefen":
        subs = store.get_subscriptions(owner_id)
        if not subs:
            reply(chat_id, "Du hast keine Ausschuss-Abos. Abonniere Ausschüsse mit /ausschuesse.")
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

    # ---- Admin-Befehle ----

    elif command == "/nutzer":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /hilfe für eine Übersicht.")
            return
        users = store.get_users()
        if not users:
            reply(chat_id, "Keine Nutzer registriert.")
            return
        lines = ["<b>Registrierte Nutzer</b>\n"]
        for u in users:
            u_owner = store.get_owner_id_for_chat(u.chat_id)
            topics = store.get_topics(u_owner) if u_owner is not None else []
            label = _esc(u.username) if u.username else "–"
            lines.append(
                f"<code>{u.chat_id}</code> {label} · {len(topics)} Thema(en)\n"
                f"  seit {u.added_at[:10]}"
            )
        reply(chat_id, "\n".join(lines))

    elif command == "/freischalten":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /hilfe für eine Übersicht.")
            return
        tokens = args.split(None, 1)
        if not tokens or not tokens[0].lstrip("-").isdigit():
            reply(chat_id, "Verwendung: <code>/freischalten chat_id [Name]</code>")
            return
        target = int(tokens[0])
        username = tokens[1].strip() if len(tokens) > 1 else ""
        store.add_user(target, username)
        label = f" ({username})" if username else ""
        reply(chat_id, f"Nutzer <code>{target}</code>{label} freigeschaltet.")
        reply(
            target,
            "🎉 Du wurdest freigeschaltet!\n\n"
            "Schreib /hilfe für eine Übersicht aller Befehle, oder leg direkt los:\n"
            "<code>/neu Radwege | Ausbau von Radwegen in Oldenburg</code>",
        )

    elif command == "/sperren":
        if not _is_admin(chat_id):
            reply(chat_id, "Unbekannter Befehl. /hilfe für eine Übersicht.")
            return
        if not args.lstrip("-").isdigit():
            reply(chat_id, "Verwendung: <code>/sperren chat_id</code>")
            return
        target = int(args)
        if target == chat_id:
            reply(chat_id, "Du kannst dich nicht selbst entfernen.")
            return
        store.remove_user(target)
        reply(chat_id, f"Nutzer <code>{target}</code> entfernt (inkl. seiner Themen).")

    else:
        reply(chat_id, f"Unbekannter Befehl: {command}\n\n/hilfe für eine Übersicht.")


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

    owner_id = store.ensure_owner_for_chat(chat_id)

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

        subscribed = set(store.get_subscriptions(owner_id))
        if committee_name in subscribed:
            store.unsubscribe(owner_id, committee_name)
            toast = "❌ Ausschuss gekündigt"
        else:
            store.subscribe(owner_id, committee_name)
            toast = "✅ Ausschuss abonniert"

        answer_callback_query(callback_query_id, toast)

        new_subscribed = set(store.get_subscriptions(owner_id))
        buttons = _committee_buttons(all_names, new_subscribed)
        edit_message_buttons(chat_id, message_id, buttons)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _vagueness_hint(name: str, description: str) -> dict | None:
    """Check whether a topic description is too vague.

    Returns None if the description is precise enough, otherwise a dict
    {"hint": str, "suggestion": str} where ``hint`` explains the problem and
    ``suggestion`` is a concrete, ready-to-use improved description.
    """
    import json
    resp = llm.chat_complete(
        model="openai/gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": prompts.get("vagueness_check_system"),
            },
            {
                "role": "user",
                "content": f"Name: {name}\nBeschreibung: {description}",
            },
        ],
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)
    if result.get("vague"):
        return {
            "hint": result.get("hint", ""),
            "suggestion": result.get("suggestion", ""),
        }
    return None
