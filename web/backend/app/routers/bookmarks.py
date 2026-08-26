"""Persönliche Merkliste für Sitzungen, Tagesordnungspunkte und Beschlüsse."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from council import bookmarks as bookmark_logic
from council.store import CouncilStore
from kern.store import Store

from ..deps import get_council_store, get_store, require_active

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


class BookmarkIn(BaseModel):
    kind: Literal["session", "agenda_item", "decision"]
    ksinr: int | None = None
    item_number: str | None = None
    decision_id: int | None = None


class BookmarkNotificationIn(BaseModel):
    notify_result: bool


def _subtitle(session: dict | None, item_number: str | None = None) -> str:
    if not session:
        return ""
    bits = [session.get("committee") or "", session.get("session_date") or ""]
    if item_number:
        bits.append(str(item_number))
    return " · ".join(x for x in bits if x)


def _existing_agenda_bookmark(rows: list[dict], ksinr: int, item: dict) -> dict | None:
    """Denselben TOP trotz geänderter Nummer wiedererkennen."""
    for row in rows:
        if row.get("kind") not in ("agenda_item", "decision") or row.get("ksinr") != ksinr:
            continue
        if item.get("kvonr") and row.get("kvonr") == item["kvonr"]:
            return row
        if item.get("vorlage_nr") and row.get("vorlage_nr") == item["vorlage_nr"]:
            return row
        if bookmark_logic.normalized_title(row.get("title")) == bookmark_logic.normalized_title(item.get("title")):
            return row
        if bookmark_logic.top_number(row.get("item_number")) == bookmark_logic.top_number(item.get("item_number")):
            return row
    return None


@router.get("")
def list_bookmarks(user: dict = Depends(require_active),
                   nwz: Store = Depends(get_store),
                   council: CouncilStore = Depends(get_council_store)) -> dict:
    out = []
    for row in nwz.get_bookmarks(user["id"]):
        entry = bookmark_logic.enrich_bookmark(row, council)
        out.append(entry)
        item, decision = entry.get("agenda_item"), entry.get("decision")
        # Erkannte Nummernverschiebungen und nachträglich entstandene
        # Beschluss-IDs gleich in den Snapshot übernehmen.
        if item or decision:
            nwz.update_bookmark_snapshot(
                row["id"],
                item_number=(item or decision or {}).get("item_number"),
                decision_id=(decision or {}).get("id"),
                kvonr=(item or decision or {}).get("kvonr"),
                vorlage_nr=(item or decision or {}).get("vorlage_nr") or row.get("vorlage_nr") or "",
                title=(item or decision or {}).get("title") or row.get("title") or "",
                subtitle=_subtitle(entry.get("session"), (item or decision or {}).get("item_number")),
            )
    return {"bookmarks": out}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_bookmark(payload: BookmarkIn,
                    user: dict = Depends(require_active),
                    nwz: Store = Depends(get_store),
                    council: CouncilStore = Depends(get_council_store)) -> dict:
    owner_id = user["id"]

    if payload.kind == "session":
        if payload.ksinr is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Sitzung fehlt.")
        session = council.get_session(payload.ksinr)
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
        row = nwz.add_bookmark(
            owner_id, kind="session", target_key=f"session:{payload.ksinr}",
            ksinr=payload.ksinr, title=session["committee"], subtitle=_subtitle(session),
        )

    elif payload.kind == "agenda_item":
        if payload.ksinr is None or not (payload.item_number or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tagesordnungspunkt fehlt.")
        session = council.get_session(payload.ksinr)
        item = next((i for i in council.agenda_items(payload.ksinr)
                     if i["item_number"] == payload.item_number), None)
        if not session or not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tagesordnungspunkt nicht gefunden.")
        if not item.get("is_public"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Nichtöffentliche Tagesordnungspunkte können nicht gemerkt werden.")
        existing = _existing_agenda_bookmark(nwz.get_bookmarks(owner_id), payload.ksinr, item)
        if existing:
            return bookmark_logic.enrich_bookmark(existing, council)
        identity = item.get("kvonr") or item["item_number"]
        row = nwz.add_bookmark(
            owner_id, kind="agenda_item",
            target_key=f"agenda_item:{payload.ksinr}:{identity}",
            ksinr=payload.ksinr, item_number=item["item_number"], kvonr=item.get("kvonr"),
            vorlage_nr=item.get("vorlage_nr") or "", title=item["title"],
            subtitle=_subtitle(session, item["item_number"]),
        )

    else:
        if payload.decision_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Beschluss fehlt.")
        decision = council.get_decision(payload.decision_id)
        if not decision:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
        # Ein früher gemerkter TOP ist inzwischen genau dieser Beschluss: kein
        # zweiter Eintrag, sondern denselben weiterverwenden.
        for existing in nwz.get_bookmarks(owner_id):
            resolved = bookmark_logic.resolve_bookmark(existing, council).get("decision")
            if resolved and resolved.get("id") == decision.get("id"):
                return bookmark_logic.enrich_bookmark(existing, council)
        session = council.get_session(decision["ksinr"])
        stable = bookmark_logic.top_number(decision.get("item_number")) or str(decision["id"])
        row = nwz.add_bookmark(
            owner_id, kind="decision",
            target_key=f"decision:{decision['ksinr']}:{stable}",
            ksinr=decision["ksinr"], item_number=decision.get("item_number"),
            decision_id=decision["id"], kvonr=decision.get("kvonr"),
            vorlage_nr=decision.get("vorlage_nr") or "",
            title=decision.get("title") or "Beschluss",
            subtitle=_subtitle(session, decision.get("item_number")),
        )

    return bookmark_logic.enrich_bookmark(row, council)


@router.put("/{bookmark_id}/notification")
def set_notification(bookmark_id: int, payload: BookmarkNotificationIn,
                     user: dict = Depends(require_active),
                     nwz: Store = Depends(get_store),
                     council: CouncilStore = Depends(get_council_store)) -> dict:
    row = nwz.get_bookmark_for_owner(user["id"], bookmark_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merkeintrag nicht gefunden.")
    if row["kind"] != "agenda_item":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Ergebnis-Hinweise gibt es nur für Tagesordnungspunkte.")
    entry = bookmark_logic.enrich_bookmark(row, council)
    if payload.notify_result and entry.get("decision"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Ergebnis liegt bereits vor.")
    updated = nwz.set_bookmark_result_notification(user["id"], bookmark_id,
                                                   payload.notify_result)
    return bookmark_logic.enrich_bookmark(updated, council)


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark_id: int, user: dict = Depends(require_active),
                    nwz: Store = Depends(get_store)) -> None:
    if not nwz.delete_bookmark(user["id"], bookmark_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merkeintrag nicht gefunden.")
