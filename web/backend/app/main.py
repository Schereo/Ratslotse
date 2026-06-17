"""FastAPI application entry point."""
from __future__ import annotations

import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    title="Stadtpuls",
    description="Lokale Nachrichten und Ratsinformationen für Oldenburg.",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
