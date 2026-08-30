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
    # Laufzeit des Sitzungs-Cookies. Lang, weil die Sitzung sich bei Nutzung
    # still verlängert (app/session.py) — wer die Seite regelmäßig benutzt,
    # bleibt angemeldet; wer sie ein Vierteljahr nicht anfasst, meldet sich neu
    # an. Widerruf läuft unabhängig davon über token_version.
    access_token_expire_minutes: int = 60 * 24 * 90  # 90 Tage
    # Ab wann verlängert wird: sobald weniger als so viel Restlaufzeit übrig
    # ist. Die Hälfte der Laufzeit heißt „höchstens ein Set-Cookie alle 45
    # Tage" — danach ist das Token wieder frisch. 0 schaltet die Verlängerung ab.
    session_renew_within_minutes: int = 60 * 24 * 45  # 45 Tage
    # Native-app clients (Capacitor) store the JWT in secure device storage and
    # can't rely on cookies at all; they refresh it on every /auth/me instead.
    # Revocation still works via token_version (bumped on password change/reset).
    app_access_token_expire_minutes: int = 60 * 24 * 90  # 90 days
    # Native builds check this value before authenticated bootstrap requests.
    # Zero keeps every build enabled until an operator deliberately raises it.
    app_min_build: int = 0
    app_update_notice: str = ""
    # This address becomes admin once it registers AND confirms its email — and
    # only while the deployment has no admin yet (see routers/auth.py). Without
    # email delivery: scripts/grant_admin.py.
    web_admin_email: str = ""
    # Secure cookies require HTTPS (or localhost, which browsers treat as
    # secure). Keep True for production; tests/non-localhost HTTP set it False.
    cookie_secure: bool = True

    # Schnittstelle für den Social-Media-Bot (ratslotse-social, eigenes Repo,
    # läuft auf einer anderen Maschine). Ohne Token sind die Endpunkte AUS —
    # eine Standard-Installation exponiert nichts.
    social_api_token: str = ""
    # Wohin die gerenderten Karten fallen und unter welcher Adresse sie
    # ausgeliefert werden. Instagram holt die Bilder selbst von dort ab,
    # deshalb muss der Pfad öffentlich erreichbar sein.
    social_media_dir: str = str(ROOT / "web" / "frontend" / "public" / "social")
    social_media_base_url: str = "https://ratslotse.de/social"

    # Sign in with Apple (RL-1002): erlaubte aud-Werte des Identity-Tokens.
    # Bundle-ID deckt die native App ab, die Services ID den Browser-Flow.
    # Beide sind feste Kennungen unserer App, keine Geheimnisse — deshalb als
    # Default hier und nicht nur als Umgebungsvariable. Vorher stand die
    # Services ID leer: Der Browser schickte (fest verdrahtet in lib/apple.ts)
    # `de.ratslotse.web`, der Server kannte den Wert aber nur, wenn jemand
    # APPLE_SERVICE_ID gesetzt hatte — fehlte sie, lief jede Web-Anmeldung in
    # ein 401. Überschreibbar bleibt beides.
    apple_bundle_id: str = "de.ratslotse.app"
    apple_service_id: str = "de.ratslotse.web"
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

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
