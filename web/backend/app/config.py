"""Backend configuration, read from environment (shares the bot's .env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = web/backend/app/config.py -> parents[3]
ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    # Auth
    web_jwt_secret: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    web_admin_email: str = ""  # this email is granted admin on registration
    # Secure cookies require HTTPS (or localhost, which browsers treat as
    # secure). Keep True for production; tests/non-localhost HTTP set it False.
    cookie_secure: bool = True

    # Databases (shared with the bot)
    nwz_db: str = str(ROOT / "data" / "nwz.sqlite")
    council_db: str = str(ROOT / "data" / "council.sqlite")

    # Telegram bot username, used to render link instructions in the UI
    telegram_bot_username: str = "RatslotseBot"

    # CORS: comma-separated origins for local dev. In production the frontend is
    # served same-origin behind nginx, so this is only needed during development.
    cors_origins: str = "http://localhost:3000"

    # The NWZ folder used for the digest (Oldenburger Nachrichten)
    nwz_folder: int = 8389

    # Email (Resend) — used to notify admins about pending registrations.
    # Read from .env directly (the cron jobs use os.environ via load_dotenv;
    # the backend passes these explicitly so it doesn't depend on the process env).
    resend_api_key: str = ""
    email_from: str = "Ratslotse <noreply@ratslotse.de>"
    app_base_url: str = "https://ratslotse.de"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
