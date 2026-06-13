#!/usr/bin/env python3
"""Long-poll the Telegram bot for commands and handle them.
Run continuously alongside the Flask app:
  python scripts/bot_poll.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.telegram_bot import get_updates, telegram_ready
from nwz.bot_commands import handle_update, handle_callback_query

DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _sync_committee_list() -> None:
    try:
        from council.scraper import CouncilScraper
        from council.store import CouncilStore
        committees = CouncilScraper().fetch_committee_list()
        CouncilStore(COUNCIL_DB).save_committees(committees)
        print(f"Synced {len(committees)} committees.", flush=True)
    except Exception as e:
        print(f"Committee sync failed (non-fatal): {e}", flush=True)


def main() -> None:
    _sync_committee_list()
    if not telegram_ready():
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — aborting.")
        sys.exit(1)

    print("Bot polling started. Send /help to the bot to test.")
    offset = 0
    while True:
        try:
            updates = get_updates(offset=offset, timeout=30)
            for u in updates:
                if "callback_query" in u:
                    handle_callback_query(u, DB)
                else:
                    handle_update(u, DB)
                offset = u["update_id"] + 1
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
