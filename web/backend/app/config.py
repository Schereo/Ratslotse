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
    access_token_expire_minutes: int = 60 * 24  # 1 day (web cookie sessions)
    # Native-app clients (Capacitor) store the JWT in secure device storage and
    # can't rely on silent cookie refresh, so they get a much longer-lived token.
    # Revocation still works via token_version (bumped on password change/reset).
    app_access_token_expire_minutes: int = 60 * 24 * 90  # 90 days
    # This address becomes admin once it registers AND confirms its email — and
    # only while the deployment has no admin yet (see routers/auth.py). Without
    # email delivery: scripts/grant_admin.py.
    web_admin_email: str = ""
    # Secure cookies require HTTPS (or localhost, which browsers treat as
    # secure). Keep True for production; tests/non-localhost HTTP set it False.
    cookie_secure: bool = True

    # Sign in with Apple (RL-1002): erlaubte aud-Werte des Identity-Tokens.
    # Bundle-ID deckt die native App ab; die Service-ID käme für einen späteren
    # Web-Flow dazu (leer = nicht konfiguriert).
    apple_bundle_id: str = "de.ratslotse.app"
    apple_service_id: str = ""

    # Admin-LLM-Kosten (Design 21a): Monatsbudget für die Budget-Ampel
    # (Warnung ab 80 %). Reine Anzeige-Schwelle, drosselt nichts.
    llm_budget_monthly: float = 40.0

    # Databases (shared with the bot)
    nwz_db: str = str(ROOT / "data" / "nwz.sqlite")
    council_db: str = str(ROOT / "data" / "council.sqlite")

    # Telegram bot username, used to render link instructions in the UI

    # CORS: comma-separated origins for local dev. In production the frontend is
    # served same-origin behind nginx, so this is only needed during development.
    cors_origins: str = "http://localhost:3000"
    # The Capacitor apps load the UI from a local WebView origin and call the
    # backend cross-origin (bearer auth): iOS pages live on capacitor://localhost,
    # Android on https://localhost. Fixed non-web origins, always appended so the
    # apps work without extra .env setup.
    app_cors_origins: str = "capacitor://localhost,https://localhost"

    # The NWZ folder used for the digest (Oldenburger Nachrichten)
    nwz_folder: int = 8389

    # Email (Resend) — used to notify admins about pending registrations.
    # Read from .env directly (the cron jobs use os.environ via load_dotenv;
    # the backend passes these explicitly so it doesn't depend on the process env).
    resend_api_key: str = ""
    email_from: str = "Ratslotse <noreply@ratslotse.de>"
    app_base_url: str = "https://ratslotse.de"
    feedback_email: str = ""  # where user feedback is sent; falls back to web_admin_email

    @property
    def cors_origin_list(self) -> list[str]:
        merged = f"{self.cors_origins},{self.app_cors_origins}"
        out: list[str] = []
        for o in (s.strip() for s in merged.split(",")):
            if o and o not in out:
                out.append(o)
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
