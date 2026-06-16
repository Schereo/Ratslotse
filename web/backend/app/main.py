"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import account, admin, auth, council, link, nwz, topics

settings = get_settings()

app = FastAPI(
    title="NWZ-Bot Web",
    description="Web-Frontend für NWZ-Suche, Ratsinfo-Suche, Themen-Verwaltung und Admin.",
    version="1.0.0",
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
