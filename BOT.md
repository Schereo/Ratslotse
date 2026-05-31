# Telegram Bot – Multi-User Guide

The bot (`@mein_nwz_bot`) uses a **whitelist**: only approved users can interact with it. Each user has their own independent set of topics.

---

## Adding a Friend

1. They message `@mein_nwz_bot` with `/start`
2. The bot replies with their chat ID, e.g. `Your chat ID: 123456789`
3. You (the admin) send the bot:
   ```
   /approve 123456789 Anna
   ```
4. The bot confirms to you and sends Anna a welcome message — she can use it immediately.

---

## Admin Commands

| Command | Effect |
|---|---|
| `/users` | List all approved users and their topic count |
| `/approve <chat_id> [Name]` | Whitelist a user and notify them |
| `/revoke <chat_id>` | Remove a user and delete all their topics |

Admin = whoever has `TELEGRAM_CHAT_ID` set in `.env`.

---

## User Commands (available to everyone on the whitelist)

| Command | Effect |
|---|---|
| `/topics` | Show your saved topics |
| `/add Name \| Description` | Add a new topic |
| `/delete <ID>` | Delete a topic by its ID |
| `/help` | Show available commands |

**Example:**
```
/add Radwege | Ausbau und Planung von Radwegen in Oldenburg
```

---

## How It Works

- The daily NWZ digest and council watcher run per user — each person gets alerts based on their own topics only.
- Topic IDs are personal; `/delete 3` only deletes *your* topic #3.

---

## Running the Bot

The bot polls Telegram continuously. Run it as a background service:

```bash
# Manually
python scripts/bot_poll.py

# As a systemd service (see DEPLOYMENT.md)
systemctl start nwz-bot
```
