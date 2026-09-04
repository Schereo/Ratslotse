"""FastAPI application entry point."""
from __future__ import annotations

import logging
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from pathlib import Path

from .antworten import Health
from .config import get_settings
from .schemas import AppConfigOut
from .routers import account, admin, auth, auth_apple, bookmarks, council, feedback, kommunalwahl, onboarding, push, quiz, social, topics, badges
from .session import SitzungsVerlaengerung

logger = logging.getLogger("ratslotse.web.main")


def _warn_if_admin_bootstrap_pending() -> None:
    """Best-effort-Hinweis: Das Konto zu ``WEB_ADMIN_EMAIL`` existiert, ist aber
    kein Admin.

    Adminrechte bekommt diese Adresse erst mit der E-Mail-Bestätigung. Ohne
    ``RESEND_API_KEY`` gibt es keinen Bestätigungslink — dann bleibt nur
    ``scripts/grant_admin.py``, und das darf niemand still übersehen.

    Rein informativ: Fehler (fehlende, gesperrte oder unlesbare DB) werden
    geschluckt, der Start darf daran nie scheitern.
    """
    try:
        settings = get_settings()
        configured = (settings.web_admin_email or "").strip().lower()
        if not configured:
            return
        from kern.store import Store

        store = Store(settings.ratslotse_db)
        try:
            users = store.list_web_users()
        finally:
            store.close()
        konto = next(
            (u for u in users if str(u.get("email") or "").strip().lower() == configured), None
        )
        if konto is None or "admin" in (konto.get("roles") or []):
            return
        logger.warning(
            "WEB_ADMIN_EMAIL %s hat ein Konto, aber keine Adminrechte. Sie werden erst mit "
            "der E-Mail-Bestätigung vergeben; ohne RESEND_API_KEY gibt es dafür keinen Link. "
            "Dann von Hand: .venv/bin/python scripts/grant_admin.py %s",
            configured, configured,
        )
    except Exception:  # noqa: BLE001 — reiner Hinweis, darf den Start nie blockieren
        pass


def _startup_checks() -> None:
    s = get_settings()
    if s.web_jwt_secret == "dev-insecure-change-me":
        if s.cookie_secure:
            raise RuntimeError(
                "WEB_JWT_SECRET ist noch der unsichere Default-Wert. "
                "Setze WEB_JWT_SECRET in der .env auf ein zufälliges Geheimnis."
            )
        warnings.warn(
            "WEB_JWT_SECRET ist noch der unsichere Default-Wert – nur für lokale Entwicklung akzeptabel.",
            stacklevel=1,
        )


def _warm_models() -> None:
    """Warm the embedding + reranker models in a background thread, so the first
    Q&A request after a restart isn't degraded — a cold reranker load makes
    hybrid_search fall back to the weaker vector-only order. Best-effort: if
    fastembed/the model is missing, Q&A simply uses its fallback path."""
    import threading

    def _load() -> None:
        try:
            from council import embeddings as emb
            from council.store import CouncilStore

            # Ein hybrid_search wärmt ALLES auf dem Frage-Pfad: Embedder,
            # Beschluss- und Vorlagen-Chunk-Matrix (kamen vorher erst bei der
            # ersten Frage aus SQLite) sowie den FTS-Zugriff; rerank() den
            # Cross-Encoder.
            store = CouncilStore(get_settings().council_db)
            try:
                emb.hybrid_search(store, "warmup", "warmup", top_k=1, pool=2)
                # Die Zusatzkanäle haben EIGENE Matrizen (Presse, 42k
                # Wortbeiträge, Anlagen), die hybrid_search nicht anfasst —
                # ungewärmt zahlt sie die erste Frage nach jedem Deploy.
                for laden in (emb.search_presse, emb.search_wortbeitraege):
                    try:
                        laden(store, "warmup", "warmup")
                    except Exception:  # noqa: BLE001 — Kanal fehlt/leer: egal
                        pass
            finally:
                store.close()
            emb.rerank("warmup", [(0, "warmup")])
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_load, daemon=True).start()


def _deep_jobs_aufraeumen() -> None:
    """„Gründliche Recherche"-Jobs, die laut DB noch laufen, sind nach einem
    Neustart tot (ihr Thread starb mit dem alten Prozess) → als Fehler
    markieren, damit der Client „Fortsetzen" anbietet statt ewig zu warten."""
    try:
        from kern.store import Store

        store = Store(get_settings().ratslotse_db)
        try:
            n = store.deep_jobs_verwaiste_beenden()
            if n:
                logger.warning("%d verwaiste Recherche-Jobs als Fehler markiert", n)
        finally:
            store.close()
    except Exception:  # noqa: BLE001 — Aufräumen darf den Start nie verhindern
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    _startup_checks()
    _warn_if_admin_bootstrap_pending()
    _deep_jobs_aufraeumen()
    _warm_models()
    yield


settings = get_settings()

# Expose the interactive API docs only outside production. cookie_secure is our
# prod signal (True in prod, False for local/test HTTP) — there's no reason to
# advertise the full schema + endpoints publicly.
_expose_docs = not settings.cookie_secure

app = FastAPI(
    title="Ratslotse",
    description="Lokale Nachrichten und Ratsinformationen für Oldenburg.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _expose_docs else None,
    redoc_url="/redoc" if _expose_docs else None,
    openapi_url="/openapi.json" if _expose_docs else None,
)

# Only trust proxy headers forwarded from localhost (nginx/gunicorn on the same host).
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "::1"])

# Stille Sitzungsverlängerung: Wer die Seite benutzt, bleibt angemeldet.
app.add_middleware(SitzungsVerlaengerung)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth_apple.router)
app.include_router(account.router)
app.include_router(council.router)
app.include_router(bookmarks.router)
app.include_router(topics.router)
app.include_router(topics.sub_router)
app.include_router(admin.router)
app.include_router(feedback.router)
app.include_router(onboarding.router)
app.include_router(quiz.router)
app.include_router(quiz.admin_router)
app.include_router(push.router)
app.include_router(badges.router)
app.include_router(kommunalwahl.router)
app.include_router(social.router)

# Die abgelegten Social-Bilder öffentlich ausliefern — Instagram holt sie
# selbst, also darf hier kein Token davor.
#
# Sie liegen bewusst NICHT im public/ des Frontends: Next.js liest dieses
# Verzeichnis beim BUILD und liefert später hinzugefügte Dateien nie aus. Der
# Upload lief, die Datei lag auf der Platte, und die URL gab trotzdem 404
# (19.08.26). Hier hängt die Auslieferung an derselben Anfrage wie das
# Ablegen — was der Bot hochlädt, ist damit sofort abrufbar.
_medien = get_settings().social_media_dir
if _medien:
    _pfad = Path(_medien)
    _pfad.mkdir(parents=True, exist_ok=True)
    app.mount("/api/social-media", StaticFiles(directory=_pfad), name="social-media")


@app.exception_handler(OverflowError)
async def overflow_exception_handler(request: Request, exc: OverflowError) -> JSONResponse:
    """Absurd große Zahlen in der URL sind ein 404, kein Serverfehler.

    Python rechnet beliebig groß, SQLite nur 64 Bit: ``/api/council/decision/
    99999999999999999999`` kam bis in die Abfrage und starb dort mit
    ``OverflowError: Python int too large to convert to SQLite INTEGER`` — also
    mit einem 500 samt Traceback im Log. Das betraf **jeden** Zahl-Parameter
    (decision, session, topic, quiz …), und seit die Beschluss-Seiten öffentlich
    sind, löst das jeder Crawler aus, der an einer URL herumprobiert.

    Semantisch ist es ein 404: Die id ist syntaktisch in Ordnung, ein Datensatz
    mit ihr kann aber nicht existieren — dieselbe Antwort wie bei ``id=-1``.
    Zentral statt an jedem Endpunkt, damit es auch für künftige gilt.
    """
    logger.info("Zahl außerhalb des speicherbaren Bereichs: %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Nicht gefunden."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Strip password values from 422 error details before returning to the client."""
    _SENSITIVE = {"password", "current_password", "new_password"}
    errors = []
    for e in exc.errors():
        loc = e.get("loc", ())
        if any(str(part) in _SENSITIVE for part in loc):
            e = {**e, "input": "***"}
        errors.append(e)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


# Die beiden Fehlerwege geben eine `JSONResponse` zurück, nicht die deklarierte
# Form: So kommt der Status 503 zustande, den der Deploy und die Rauchprobe
# lesen. FastAPI lässt eine `Response` bewusst unverändert durch, die
# Annotation bleibt trotzdem `Health` — sie ist es, aus der `/openapi.json`
# den Vertrag baut. Ein Typprüfer kann diese FastAPI-Eigenheit nicht kennen;
# darum hier eine benannte Ausnahme statt einer aufgeweichten Annotation.
@app.get("/api/health")
def health() -> Health:
    from kern.store import Store
    from council.store import CouncilStore

    try:
        s = Store(settings.ratslotse_db)
        s._conn.execute("SELECT 1")
        s.close()
    except Exception:
        return JSONResponse(  # pyright: ignore[reportReturnType] — siehe oben
            {"status": "error", "db": "ratslotse"}, status_code=503)
    try:
        c = CouncilStore(settings.council_db)
        c._conn.execute("SELECT 1")
        c.close()
    except Exception:
        return JSONResponse(  # pyright: ignore[reportReturnType] — siehe oben
            {"status": "error", "db": "council"}, status_code=503)
    return {"status": "ok"}


@app.get("/api/app-config", response_model=AppConfigOut)
def app_config() -> AppConfigOut:
    """Small public compatibility contract for installed native builds."""
    from kern import features as schalter

    return AppConfigOut(
        min_build=max(0, settings.app_min_build),
        note=settings.app_update_notice.strip() or None,
        features=schalter.aktive(),
    )
