"""Notizen, auf dem Gerät verschlüsselt (``docs/plan-notizen-verschluesselt.md``).

Der Server speichert und liefert **nur Blobs**: den verpackten
Datenschlüssel und je Notiz IV und Geheimtext. Er prüft Form und Größe,
nie den Inhalt — den kennt er nicht. Alle Endpunkte brauchen ein aktives
Konto und stehen hinter dem Schalter ``notizen`` (ohne ihn 404: Die
Datenschutzerklärung nennt sie erst mit der Freigabe).
"""
from __future__ import annotations

import base64
import binascii
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from kern import features
from kern.store import Store

from ..antworten import NoteEntry, NoteKeys, NoteKeysState, NoteList, NotesDeleted
from ..deps import get_store, require_active
from ..ratelimit import RateLimiter

router = APIRouter(prefix="/api/notes", tags=["notes"])

#: Wie die Merklisten: großzügig fürs Tippen mit Zwischenspeichern, eng genug
#: gegen ein Skript, das die Tabelle füllt.
notes_write_limiter = RateLimiter(max_calls=120, window_seconds=300)

#: 16 KB Geheimtext je Notiz (Base64 macht daraus gut 21.800 Zeichen).
MAX_CIPHERTEXT_BYTES = 16 * 1024
MAX_NOTES = 2_000
#: PBKDF2-Runden, die der Server annimmt — weniger wäre ein zu billiger
#: Angriff auf die Passphrase, mehr ließe ein schwaches Gerät minutenlang rechnen.
MIN_ITERATIONS, MAX_ITERATIONS = 300_000, 5_000_000
KDFS = ("pbkdf2-sha256",)

TargetKind = Literal["agenda_item", "decision"]
NoteKind = Literal["note", "transcript"]
#: ``ksinr|Nummer`` („4654|Ö 11.1") bzw. die Beschluss-Kennung.
_KEY_RE = {"agenda_item": re.compile(r"^\d{1,9}\|[ÖN]? ?\d{1,3}(?:\.\d{1,3}){0,3}$"),
           "decision": re.compile(r"^\d{1,9}$")}


def _an() -> None:
    if not features.an("notizen"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")


def _b64(wert: str, feld: str, *, laenge: int | None = None, hoechstens: int | None = None) -> None:
    try:
        roh = base64.b64decode(wert, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, f"{feld}: kein Base64.") from None
    if laenge is not None and len(roh) != laenge:
        raise HTTPException(422, f"{feld}: falsche Länge.")
    if hoechstens is not None and len(roh) > hoechstens:
        raise HTTPException(413, f"{feld}: zu lang.")


def _ziel(target_kind: str, target_key: str) -> None:
    rx = _KEY_RE.get(target_kind)
    if not rx or not rx.match(target_key):
        raise HTTPException(422, "Unbekanntes Ziel.")


def _keys(row: dict) -> NoteKeys:
    return {k: row[k] for k in ("key_version", "kdf", "iterations", "salt", "wrapped_passphrase",
                                "wrapped_recovery", "updated_at")}  # type: ignore[return-value]


def _note(row: dict) -> NoteEntry:
    return {k: row[k] for k in ("target_kind", "target_key", "kind", "iv", "ciphertext", "key_version",
                                "version", "updated_at")}  # type: ignore[return-value]


class NoteKeysIn(BaseModel):
    key_version: int = Field(ge=1, le=1_000_000)
    kdf: Literal["pbkdf2-sha256"]
    iterations: int = Field(ge=MIN_ITERATIONS, le=MAX_ITERATIONS)
    salt: str = Field(max_length=64)
    wrapped_passphrase: str = Field(max_length=128)
    #: Nur beim Einrichten; beim Passphrasen-Wechsel bleibt die Verpackung
    #: mit dem Wiederherstellungscode, wie sie ist.
    wrapped_recovery: str | None = Field(default=None, max_length=128)


class NoteIn(BaseModel):
    iv: str = Field(max_length=32)
    ciphertext: str = Field(max_length=22_000)
    key_version: int = Field(ge=1, le=1_000_000)
    #: Die Version, auf der die Änderung beruht (0 = neue Notiz).
    version: int = Field(ge=0)


@router.get("/keys")
def get_keys(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> NoteKeysState:
    _an()
    row = store.get_note_keys(user["id"])
    return {"configured": row is not None, "keys": _keys(row) if row else None}


@router.put("/keys")
def put_keys(body: NoteKeysIn, request: Request, user: dict = Depends(require_active),
             store: Store = Depends(get_store)) -> NoteKeysState:
    """Einrichten (mit ``wrapped_recovery``) oder Passphrase wechseln (ohne,
    dieselbe ``key_version``). Vorhandene Schlüssel überschreibt das nie."""
    _an()
    notes_write_limiter.check(request, subject=user["id"])
    _b64(body.salt, "salt", laenge=16)
    _b64(body.wrapped_passphrase, "wrapped_passphrase", laenge=40)  # AES-KW über 32 Byte
    if body.wrapped_recovery is not None:
        _b64(body.wrapped_recovery, "wrapped_recovery", laenge=40)
        neu = {**body.model_dump(), "wrapped_recovery": body.wrapped_recovery}
        if not store.create_note_keys(user["id"], neu):
            raise HTTPException(status.HTTP_409_CONFLICT, "Notizen sind schon eingerichtet.")
    elif not store.rewrap_note_keys(user["id"], body.key_version, kdf=body.kdf, iterations=body.iterations,
                                    salt=body.salt, wrapped_passphrase=body.wrapped_passphrase):
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Schlüssel haben sich geändert — bitte neu laden.")
    row = store.get_note_keys(user["id"])
    return {"configured": True, "keys": _keys(row) if row else None}


@router.delete("/keys")
def delete_keys(request: Request, user: dict = Depends(require_active),
                store: Store = Depends(get_store)) -> NotesDeleted:
    """Neu anfangen: Schlüssel und alle Notizen weg."""
    _an()
    notes_write_limiter.check(request, subject=user["id"])
    return {"deleted": store.delete_all_notes(user["id"])}


@router.get("")
def list_notes(target_kind: TargetKind | None = None, target_key: str | None = None,
               user: dict = Depends(require_active), store: Store = Depends(get_store)) -> NoteList:
    """Die Notizen einer Seite — ohne Filter alle (Export; entschlüsselt wird im Browser)."""
    _an()
    if target_key is not None:
        if target_kind is None:
            raise HTTPException(422, "target_key braucht target_kind.")
        _ziel(target_kind, target_key)
    return {"notes": [_note(r) for r in store.get_notes(user["id"], target_kind, target_key)]}


@router.put("/{target_kind}/{target_key}/{kind}", responses={409: {"description": "Version veraltet"}})
def put_note(target_kind: TargetKind, target_key: str, kind: NoteKind, body: NoteIn, request: Request,
             user: dict = Depends(require_active), store: Store = Depends(get_store)) -> NoteEntry:
    _an()
    notes_write_limiter.check(request, subject=user["id"])
    _ziel(target_kind, target_key)
    _b64(body.iv, "iv", laenge=12)
    _b64(body.ciphertext, "ciphertext", hoechstens=MAX_CIPHERTEXT_BYTES)
    keys = store.get_note_keys(user["id"])
    if not keys or keys["key_version"] != body.key_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Schlüssel haben sich geändert — bitte neu laden.")
    if body.version == 0 and store.count_notes(user["id"]) >= MAX_NOTES:
        raise HTTPException(413, f"Höchstens {MAX_NOTES} Notizen je Konto.")
    ok, row = store.put_note(user["id"], target_kind, target_key, kind, iv=body.iv, ciphertext=body.ciphertext,
                             key_version=body.key_version, base_version=body.version)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail={"message": "Die Notiz wurde inzwischen woanders geändert.",
                                    "current": _note(row) if row else None})
    assert row is not None
    return _note(row)


@router.delete("/{target_kind}/{target_key}/{kind}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response, responses={204: {"description": "Gelöscht"}})
def delete_note(target_kind: TargetKind, target_key: str, kind: NoteKind, request: Request,
                user: dict = Depends(require_active), store: Store = Depends(get_store)) -> Response:
    _an()
    notes_write_limiter.check(request, subject=user["id"])
    _ziel(target_kind, target_key)
    store.delete_note(user["id"], target_kind, target_key, kind)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
