"""FastAPI application entry point."""
from __future__ import annotations

import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .config import get_settings
from .routers import account, admin, auth, council, link, nwz, topics


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


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    _startup_checks()
    yield


settings = get_settings()

app = FastAPI(
    title="Ratslotse",
    description="Lokale Nachrichten und Ratsinformationen für Oldenburg.",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(account.router)
app.include_router(link.router)
app.include_router(nwz.router)
app.include_router(council.router)
app.include_router(topics.router)
app.include_router(topics.sub_router)
app.include_router(admin.router)


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
