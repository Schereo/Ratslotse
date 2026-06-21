"""NWZ article search and retrieval (reads the stored FTS5 archive)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nwz.store import Store

from ..deps import get_store, require_nwz_verified

router = APIRouter(prefix="/api/nwz", tags=["nwz"])


@router.get("/search")
def search(
    q: str = Query("", description="Volltext-Suchbegriff (leer = neueste Artikel)"),
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = Query(40, ge=1, le=100),
    _user: dict = Depends(require_nwz_verified),
    store: Store = Depends(get_store),
) -> dict:
    results = store.search(q, limit=limit, category=category, date_from=date_from, date_to=date_to)
    return {"query": q, "count": len(results), "results": [asdict(r) for r in results]}


@router.get("/categories")
def categories(_user: dict = Depends(require_nwz_verified), store: Store = Depends(get_store)) -> dict:
    return {"categories": store.categories()}


@router.get("/editions")
def editions(_user: dict = Depends(require_nwz_verified), store: Store = Depends(get_store)) -> dict:
    rows = store.edition_summary()
    return {
        "editions": [
            {
                "publication_date": r[0],
                "title": r[1],
                "pages": r[2],
                "n_articles": r[3],
                "body_chars": r[4],
            }
            for r in rows
        ]
    }


@router.get("/article/{catalog}")
def article(
    catalog: int,
    refid: str = Query(..., description="Artikel-refid (enthält i. d. R. Slashes)"),
    _user: dict = Depends(require_nwz_verified),
    store: Store = Depends(get_store),
) -> dict:
    art = store.get_article(catalog, refid)
    if not art:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artikel nicht gefunden.")
    return art
