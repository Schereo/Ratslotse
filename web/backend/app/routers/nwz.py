"""NWZ article search and retrieval (reads the stored FTS5 archive)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nwz.store import Store

from ..deps import get_store, require_nwz_verified

router = APIRouter(prefix="/api/nwz", tags=["nwz"])

# Collapse NWZ's granular layout codes into one filter option for the web Rubrik
# dropdown. The DB keeps the raw category_name; this only affects the web filter
# and its label. Selecting a group label filters all its member sections.
CATEGORY_GROUPS: dict[str, list[str]] = {
    "Titelseite": ["Titelsei", "DS_Titel", "TitelSam", "TitelMo", "Journal Titel"],
    "Lokales": ["DS_Lokal"],
}
_RAW_TO_GROUP: dict[str, str] = {raw: label for label, raws in CATEGORY_GROUPS.items() for raw in raws}


def _grouped_categories(raw: list[str]) -> list[str]:
    """Map raw NWZ categories to their display label and de-duplicate (order kept)."""
    out: list[str] = []
    for r in raw:
        label = _RAW_TO_GROUP.get(r, r)
        if label not in out:
            out.append(label)
    return out


def _resolve_category(category: str) -> list[str]:
    """A group label expands to its member sections; a raw category stays itself."""
    if not category:
        return []
    return CATEGORY_GROUPS.get(category, [category])


@router.get("/search")
def search(
    q: str = Query("", description="Volltext-Suchbegriff (leer = neueste Artikel)"),
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(require_nwz_verified),
    store: Store = Depends(get_store),
) -> dict:
    cats = _resolve_category(category)
    results = store.search(q, limit=limit, date_from=date_from, date_to=date_to, offset=offset, categories=cats)
    total = store.count_results(q, date_from=date_from, date_to=date_to, categories=cats)
    return {"query": q, "count": len(results), "total": total, "results": [asdict(r) for r in results]}


@router.get("/categories")
def categories(_user: dict = Depends(require_nwz_verified), store: Store = Depends(get_store)) -> dict:
    return {"categories": _grouped_categories(store.categories())}


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
