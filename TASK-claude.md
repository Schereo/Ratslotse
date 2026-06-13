Füge Telegram Inline-Keyboard-Buttons zum kommunalwahl-scraper Bot hinzu.

## Projekt-Kontext

Das Projekt in /home/tim/kommunalwahl-scraper ist ein Telegram-Bot (@mein_nwz_bot) der:
- NWZ ePaper scraped und per GPT-4o klassifiziert
- Oldenburger Stadtrat-Sitzungen aus dem Bürgerinformationssystem scraped
- Multi-User-Support mit Whitelist
- Bereits Ausschuss-Abonnements via Slash-Befehlen unterstützt (/committees, /subscribe, /unsubscribe, /subscriptions)

**Bestehende relevante Module:**
- `nwz/telegram_bot.py` — Telegram API Wrapper (get_updates, reply, send_message, _split)
- `nwz/bot_commands.py` — Command Handler (handle_update, _esc)
- `nwz/store.py` — SQLite Store (nwz.sqlite) mit users, topics, subscriptions
- `scripts/bot_poll.py` — Long-Polling Loop

**Wichtig:** Der Bot verwendet KEINE Library wie python-telegram-bot — alles pur über die REST API (requests).

## Aufgabe

### 1. Neue Funktionen in nwz/telegram_bot.py

Füge folgende Funktionen hinzu:

**`reply_with_buttons(chat_id, text, buttons) -> int | None`**
Sendet eine Nachricht mit Inline-Keyboard. `buttons` ist `list[list[dict]]` — jede Row hat Button-Dicts mit `{"text": str, "callback_data": str}`. Gibt `message_id` zurück oder `None` bei Fehler.
- parse_mode: "HTML"
- disable_web_page_preview: True
- reply_markup mit inline_keyboard

**`edit_message_buttons(chat_id, message_id, buttons) -> bool`**
Aktualisiert NUR das Inline-Keyboard einer existierenden Nachricht (editMessageReplyMarkup). Gibt True/False zurück.

**`answer_callback_query(callback_query_id, text=None)`**
Quittiert ein CallbackQuery (answerCallbackQuery). Optional mit Toast-Text.

**`get_updates()`** muss auch `"callback_query"` in `allowed_updates` erlauben.

### 2. Buttons für /committees in nwz/bot_commands.py

Ändere den `/committees`-Handler: Statt nur Text zu replyen, sende die Ausschussliste mit Inline-Buttons.

Jeder Ausschuss bekommt einen Button:
- Wenn abonniert: Button zeigt `"✅ Nummer"` (z.B. `"✅ 1"`)
- Wenn nicht abonniert: Button zeigt `"➕ Nummer"` (z.B. `"➕ 3"`)
- callback_data: `"ctoggle:Name_des_Ausschusses"` 
- Max 4 Buttons pro Reihe (Telegram: max 8)

Nachricht enthält zusätzlich den Hinweis: "Buttons klicken = abonnieren/kündigen. /subscribe und /unsubscribe funktionieren weiterhin."

### 3. Callback-Query Handler

Füge `handle_callback_query(update, db_path)` in `bot_commands.py` hinzu:

- Holt chat_id, message_id, callback_data, callback_query_id aus dem Update
- Bei `ctoggle:` prefix: schaut ob der Ausschuss bereits abonniert ist (store.get_subscriptions)
- Toggelt: subscribe oder unsubscribe
- Ruft `answer_callback_query()` auf mit Toast-Text ("✅ Ausschuss abonniert" / "❌ Ausschuss gekündigt")
- Aktualisiert die Buttons der Nachricht via `edit_message_buttons()` basierend auf neuem Zustand

**Wichtig:** `handle_callback_query` wird von `handle_update` getrennt aufgerufen — die Funktion muss eigenständig sein (nicht in die if/elif-Kette integriert). Der Aufrufer (bot_poll.py) unterscheidet zwischen message und callback_query.

### 4. scripts/bot_poll.py anpassen

- `handle_callback_query` importieren
- In der Loop: wenn `"callback_query"` im Update → `handle_callback_query(u, DB)` aufrufen, sonst `handle_update(u, DB)` wie bisher

### Wichtige Hinweise

- **Keine bestehenden Kommandos kaputt machen** — /subscribe, /unsubscribe, /subscriptions, /help etc. bleiben unverändert
- **Keine Drittanbieter-Libs einbauen** — alles über requests + Telegram REST API
- **callback_data max 64 Bytes** — Ausschussnamen sind kurz genug für `ctoggle:Name`
- **importe:** Die Telegram-Funktionen kommen aus `nwz.telegram_bot`, Callback-Handler gehört in `nwz.bot_commands`
- **Syntax nach jedem Schritt checken** mit `python3 -c "compile(open('datei.py').read(), 'datei.py', 'exec')"`
- **NICHT pushen, NICHT deployen** — nur lokal arbeiten und committen
