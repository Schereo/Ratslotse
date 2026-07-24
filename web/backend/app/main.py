"""FastAPI application entry point."""
from __future__ import annotations

import logging
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .config import get_settings
from .routers import account, admin, auth, auth_apple, council, feedback, onboarding, push, quiz, topics, badges

logger = logging.getLogger("nwz.web.main")


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
        from nwz.store import Store

        store = Store(settings.nwz_db)
        try:
            users = store.list_web_users()
        finally:
            store.close()
        konto = next(
            (u for u in users if str(u.get("email") or "").strip().lower() == configured), None
        )
        if konto is None or konto.get("role") == "admin":
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

            # search() lädt Embedder UND die Vektor-Matrix (die vorher erst bei
            # der ersten Frage aus SQLite kam); rerank() den Cross-Encoder.
            store = CouncilStore(get_settings().council_db)
            try:
                emb.search(store, "warmup", top_k=1)
            finally:
                store.close()
            emb.rerank("warmup", [(0, "warmup")])
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_load, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    _startup_checks()
    _warn_if_admin_bootstrap_pending()
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
app.include_router(topics.router)
app.include_router(topics.sub_router)
app.include_router(admin.router)
app.include_router(feedback.router)
app.include_router(onboarding.router)
app.include_router(quiz.router)
app.include_router(quiz.admin_router)
app.include_router(push.router)
app.include_router(badges.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Strip password values from 422 error details before returning to the client."""
    _SENSITIVE = {"password", "current_password", "new_password", "nwz_password"}
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


@app.get("/api/health")
def health():
    from nwz.store import Store
    from council.store import CouncilStore

    try:
        s = Store(settings.nwz_db)
        s._conn.execute("SELECT 1")
        s.close()
    except Exception:
        return JSONResponse({"status": "error", "db": "nwz"}, status_code=503)
    try:
        c = CouncilStore(settings.council_db)
        c._conn.execute("SELECT 1")
        c.close()
    except Exception:
        return JSONResponse({"status": "error", "db": "council"}, status_code=503)
    return {"status": "ok"}
