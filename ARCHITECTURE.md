# Technical Architecture

## Overview

Two independent scrapers feed into a shared SQLite database. A Telegram bot handles user management and delivers personalised alerts.

```
NWZ ePaper (Visiolink)          Oldenburg Council (SessionNet)
        │                                    │
   nwz/api.py                        council/scraper.py
   nwz/parse.py                             │
        │                           council/store.py
   nwz/store.py                     (council.sqlite)
   (nwz.sqlite)                             │
        │                           council/watcher.py
   nwz/classify.py                          │
        │                                   │
        └──────────────┬────────────────────┘
                       │
              nwz/telegram_bot.py
                       │
                  Telegram API
                       │
                   @mein_nwz_bot
```

---

## Components

### NWZ ePaper scraper (`nwz/`)

NWZ uses the **Visiolink** platform. There is no public API — the auth flow was reverse-engineered from the SPA JavaScript bundle.

**Auth flow:**
1. `POST login.nwzonline.de` → JWT
2. `POST login-api.e-pages.dk/v1/zeitungskiosk.nwzonline.de/private/validate/prefix/nwz/publication/{catalog}/user` → session key (30-min TTL, cached in memory)
3. `GET front.e-pages.dk/session-cc/{key}/nwz/{catalog}/content/default5.php` → XML with full article bodies

`nwz/parse.py` converts the XML into `Article` dataclasses (title, subtitle, authors, category, body text, page number).

`nwz/store.py` persists editions and articles in SQLite with an FTS5 virtual table for full-text search (tokenizer: `unicode61 remove_diacritics 2` for German umlaut support).

---

### Council watcher (`council/`)

The Oldenburg council information system (`buergerinfo.oldenburg.de`) runs **SessionNet** (Somacos GmbH). There is no API — pages are scraped with BeautifulSoup4.

- `session_ids_for_month(year, month)` — scrapes the calendar page (`si0040.php`)
- `fetch_session(ksinr)` — scrapes the session detail page (`si0057.php`), parses the H1 header for date/time/location and the agenda table for items
- Agenda items starting with `Ö` are public, `N` are non-public

`council/store.py` tracks which sessions have been seen and which alerts have already been sent, preventing duplicate notifications.

---

### AI Classification

Both pipelines use **GPT-4o** (`response_format={"type": "json_object"}`) for classification. The logic is intentionally stateless — no fine-tuning, no embeddings, just structured prompts.

**NWZ digest** (`nwz/classify.py`):

Up to 109 articles are sent in a single prompt. Each article includes category, title, subtitle, and up to 900 characters of body text. The model is asked to match articles to each user topic and return 1–2 sentence German summaries:

```
For each topic: find matching articles (0–5).
Return JSON: { "digest": [{ "topic": "...", "articles": [{ "refid", "title", "summary" }] }] }
```

The `refid` in the response is used to look up the page number from the database for the `Seite X` annotation in the Telegram message.

**Council watcher** (`council/watcher.py`):

Only future sessions with newly published agendas are classified (sessions already in the database are skipped). Agenda item numbers and titles are sent to GPT-4o, which returns which item numbers match which user topics:

```
Return JSON: { "matches": [{ "topic_index": 1, "item_numbers": ["Ö 6.1", "Ö 6.2"] }] }
```

---

### Multi-user Telegram bot (`nwz/bot_commands.py`, `scripts/bot_poll.py`)

The bot uses **long-polling** (`getUpdates` with 30s timeout) — no webhook, no open port required.

Users are stored in a `users` table. Only whitelisted users can interact with the bot. The admin (configured via `TELEGRAM_CHAT_ID` in `.env`) can approve and revoke users with `/approve` and `/revoke`.

Topics are scoped per `chat_id`. The cron scripts loop over all users and send each person a personalised digest based on their own topics.

---

## Database Schema

**`nwz.sqlite`**
- `editions` — one row per fetched ePaper edition
- `articles` — full article content, linked to edition
- `articles_fts` — FTS5 virtual table mirroring articles for search
- `topics` — per-user topic watchlist (`chat_id`, `name`, `description`)
- `users` — whitelisted Telegram users

**`council.sqlite`**
- `council_sessions` — scraped session metadata
- `council_agenda_items` — agenda items per session
- `council_alerts_sent` — deduplication table (`ksinr` + `topic_id`)

---

## Scheduled Jobs (cron)

| Time (UTC) | Script | What it does |
|---|---|---|
| 06:30 daily | `daily_digest.py` | Fetches latest NWZ edition, classifies per user, sends digest |
| 08:00 + 14:00 daily | `check_council.py` | Scans upcoming council sessions, alerts on new agenda matches |

---

## Deployment

- **VPS:** Ubuntu 24.04 LXC container on Proxmox, private IP `10.10.10.13`, reachable via SSH jump through edge VM at `65.108.8.59:2102`
- **Process management:** systemd (`nwz-bot.service`)
- **CI/CD:** GitHub Actions (`appleboy/ssh-action` with ProxyJump) — push to `main` triggers `git pull` + service restart on the VPS
- **Secrets:** `.env` file on the VPS (not in git), SSH key stored as GitHub Actions secret
