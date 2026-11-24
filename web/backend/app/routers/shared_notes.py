"""Gemeinsame Notizen: per Link einladen, live zusammen schreiben (Schalter
``notizen-teilen``, braucht ``notizen``; Tims Wunsch 23.11.2026).

**Der Server kennt keinen Klartext.** Jede gemeinsame Notiz hat einen eigenen
Notizschlüssel. Jedes Mitglied hält ihn verpackt mit seinem eigenen
Datenschlüssel (denselben, der die privaten Notizen schützt). Der Inhalt ist
ein Yjs-Dokument; über die Live-Verbindung gehen nur verschlüsselte
Änderungen, der Server nummeriert, speichert und verteilt sie.

**Einladen per Link.** Der Browser der einladenden Person
verpackt den Notizschlüssel mit einem Zufallsgeheimnis, das nur im Anker des
Links steht (``…/notiz-einladung?i=<kennung>#<geheimnis>``). Den Anker sendet
kein Browser an einen Server. Wer den Link öffnet, packt den Schlüssel aus
und verpackt ihn neu mit dem eigenen Datenschlüssel. Kein Adressbuch, keine
Suche nach Konten, und der Server kann sich nicht als Mitglied ausgeben,
weil er das Geheimnis nie sieht. Wer den Link hat, kann bis zum Ablauf
beitreten — die Leitung sieht, wer dabei ist, und kann entfernen. Die
Kennung allein reicht nicht: Beitreten verlangt einen Nachweis, den nur das
Geheimnis ergibt (HKDF mit eigener Kennung, beim Server nur sein SHA-256).
Endet eine Mitgliedschaft, fallen ALLE offenen Einladungen der Notiz weg.

**Einladen per Adresse (seit 24.11.2026, Tims Wunsch).** Daneben lässt
sich ein bestimmtes Konto einladen. Jedes Konto mit Notizen hat ein
Schlüsselpaar (P-256); der öffentliche Teil liegt hier, der private mit dem
eigenen Datenschlüssel verpackt. Nach dem Annehmen verpackt der Browser
eines Mitglieds den Notizschlüssel per ECDH für den öffentlichen Schlüssel
des Eingeladenen (``POST /{id}/grants/{invite_id}``); der packt ihn aus und
tritt bei. Nur dieses Konto kann annehmen — ein weitergeleiteter Link nützt
niemandem. Dafür muss man dem Server den öffentlichen Schlüssel glauben;
wer ganz sicher sein will, vergleicht den Sicherheitscode. Die Antwort auf
eine Einladung ist dieselbe, ob es das Konto gibt oder nicht: keine
Kontensuche durch die Hintertür.

**Was der Server sieht:** wer in welcher gemeinsamen Notiz zu welchem Punkt
ist, wann geschrieben wird, wie groß die Änderungen sind — und bei
Einladungen per Adresse, wen jemand eingeladen hat (nur, wenn es das Konto
gibt; bis zur Antwort, höchstens 14 Tage).

**Entfernen ist kein Neuverschlüsseln.** Wer entfernt wird, bekommt keine
Änderungen mehr — der Server liefert sie ihm nicht. Den alten Notizschlüssel
kennt er aber noch; gegen einen Server, der ihm trotzdem Änderungen gäbe,
schützt erst ein neuer Schlüssel für alle übrigen (noch nicht gebaut,
``docs-site/…/app-und-konten.md``).

Die Live-Verbindung (``/{id}/live``) authentifiziert über eine Einmal-Kennung
aus ``POST /{id}/ticket`` statt über das Cookie: Ein Cookie im Handschlag
öffnete jeder fremden Seite die Tür, die eine Verbindung aufbaut (Cross-Site
WebSocket Hijacking); die Kennung holt nur ein Abruf mit Konto.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from html import escape

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, WebSocket,
                     WebSocketDisconnect, status)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from council.store import CouncilStore
from kern import features, notify
from kern.store import Store

from ..antworten import (LiveTicket, NoteIdentityState, NoteInvitation, NoteInviteInfo, Ok, SharedNote,
                         SharedNoteInvite, SharedNoteInvites, SharedNoteList)
from ..config import get_settings
from ..deps import get_council_store, get_store, require_active
from ..ratelimit import RateLimiter
from .notes import TargetKind, _ziel

router = APIRouter(prefix="/api/shared-notes", tags=["notes"])
invites_router = APIRouter(prefix="/api/note-invites", tags=["notes"])

shared_write_limiter = RateLimiter(max_calls=60, window_seconds=300)
#: Einladungen per Adresse lösen eine Mail aus — eng genug, dass niemand
#: darüber Post verschickt, und gegen das Durchprobieren von Adressen.
address_invite_limiter = RateLimiter(max_calls=20, window_seconds=3600)
ADDRESS_INVITE_DAYS = 14

#: Ein verpackter Notizschlüssel: 32 Byte Schlüssel + 16 Byte GCM-Etikett.
WRAPPED_KEY_MAX = 64
#: Eine Änderung oder ein Stand: großzügig für eingefügten Text, eng genug,
#: dass niemand die Datenbank mit einer Nachricht füllt.
UPDATE_MAX = 256 * 1024
SNAPSHOT_MAX = 1024 * 1024
AWARENESS_MAX = 16 * 1024
FRAME_MAX = 2 * 1024 * 1024
INVITE_DAYS_MAX = 30
TICKET_TTL = 60
#: Nachrichten je Verbindung und Fenster — der Client fasst Tippen zusammen.
LIVE_RATE = (200, 10.0)
#: So oft prüft jede Live-Verbindung, ob ihr Konto noch Mitglied ist — auch
#: wenn es auf einem Weg verschwand, der niemanden trennt (Konto gelöscht).
MEMBERSHIP_CHECK_SECONDS = 30.0


def _an() -> None:
    if not (features.an("notizen") and features.an("notizen-teilen")):
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


class SharedNoteIn(BaseModel):
    target_kind: TargetKind
    target_key: str = Field(max_length=40)
    key_iv: str = Field(max_length=32)
    key_ct: str = Field(max_length=128)
    key_version: int = Field(ge=1)
    snapshot_iv: str | None = Field(default=None, max_length=32)
    snapshot: str | None = Field(default=None, max_length=SNAPSHOT_MAX * 2)


class InviteIn(BaseModel):
    iv: str = Field(max_length=32)
    ciphertext: str = Field(max_length=128)
    #: SHA-256 des Nachweises aus dem Link-Geheimnis (Base64, 32 Byte).
    verifier_hash: str = Field(max_length=64)
    days: int = Field(default=7, ge=1, le=INVITE_DAYS_MAX)


class IdentityIn(BaseModel):
    public_key: str = Field(max_length=100)
    private_iv: str = Field(max_length=32)
    private_ct: str = Field(max_length=400)
    key_version: int = Field(ge=1)


class AddressInviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class GrantIn(BaseModel):
    epk: str = Field(max_length=100)
    iv: str = Field(max_length=32)
    ct: str = Field(max_length=128)
    #: Der öffentliche Schlüssel, für den verpackt wurde — hat er sich
    #: inzwischen geändert, nimmt der Server die Übergabe nicht an.
    for_key: str = Field(max_length=100)


class AddressJoinIn(BaseModel):
    key_iv: str = Field(max_length=32)
    key_ct: str = Field(max_length=128)
    key_version: int = Field(ge=1)


class AcceptIn(BaseModel):
    key_iv: str = Field(max_length=32)
    key_ct: str = Field(max_length=128)
    key_version: int = Field(ge=1)
    #: Der Nachweis selbst (Base64, 32 Byte) — nur wer das Geheimnis aus dem
    #: Anker hat, kann ihn bilden. Er öffnet keinen Schlüssel (eigene HKDF-Kennung).
    verifier: str = Field(max_length=64)


def _punkt(wert: str, feld: str) -> None:
    """Ein öffentlicher P-256-Schlüssel, roh (65 Byte) — und wirklich ein Punkt der Kurve."""
    _b64(wert, feld, laenge=65)
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), base64.b64decode(wert))
    except ValueError:
        raise HTTPException(422, f"{feld}: kein Schlüssel.") from None


def _note_out(n: dict, store: Store) -> SharedNote:
    return {"id": n["id"], "target_kind": n["target_kind"], "target_key": n["target_key"], "role": n["role"],
            "owner_id": n["owner_id"], "key_iv": n["key_iv"], "key_ct": n["key_ct"], "key_version": n["key_version"],
            "members": [{"user_id": m["user_id"], "display_name": m["display_name"], "role": m["role"],
                         "public_key": m.get("public_key")} for m in n["members"]],
            "pending": [{"invite_id": g["invite_id"], "user_id": g["user_id"], "display_name": g["display_name"],
                         "public_key": g["public_key"]} for g in store.pending_grants(n["id"])],
            "created_at": n["created_at"], "updated_at": n["updated_at"]}


def _invitation_out(a: dict, store: Store, council: CouncilStore) -> NoteInvitation:
    grant = ({"epk": a["grant_epk"], "iv": a["grant_iv"], "ct": a["grant_ct"]}
             if a.get("grant_ct") else None)
    return {"id": a["id"], "note_id": a["note_id"], "target_kind": a["target_kind"], "target_key": a["target_key"],
            "target_title": _ziel_titel(council, a["target_kind"], a["target_key"]),
            "inviter_name": a["inviter_name"], "created_at": a["created_at"], "expires_at": a["expires_at"],
            "accepted": a["accepted_at"] is not None, "grant": grant,
            "already_member": store.shared_note_member(a["note_id"], a["user_id"]) is not None}


def _mitglied(store: Store, note_id: str, user_id: int) -> dict:
    """Die Notiz aus Sicht dieses Mitglieds — sonst 404 (nicht 403: Wer nicht
    dabei ist, erfährt nicht, dass es sie gibt)."""
    m = store.shared_note_member(note_id, user_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese gemeinsame Notiz gibt es nicht.")
    return m


def _eine(store: Store, note_id: str, user_id: int) -> SharedNote:
    for n in store.shared_notes_for(user_id):
        if n["id"] == note_id:
            return _note_out(n, store)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese gemeinsame Notiz gibt es nicht.")


@router.get("")
def list_shared(target_kind: TargetKind | None = None, target_key: str | None = None,
                user: dict = Depends(require_active), store: Store = Depends(get_store),
                council: CouncilStore = Depends(get_council_store)) -> SharedNoteList:
    _an()
    if target_key and target_kind:
        _ziel(target_kind, target_key)
    return {"notes": [_note_out(n, store) for n in store.shared_notes_for(user["id"], target_kind, target_key)],
            "invitations": [_invitation_out(a, store, council)
                            for a in store.address_invites_for(user["id"], target_kind, target_key)]}


# Vor den Pfaden mit {note_id}: „identity" ist keine Notiz.
@router.get("/identity")
def get_identity(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> NoteIdentityState:
    _an()
    i = store.get_note_identity(user["id"])
    return {"identity": {k: i[k] for k in ("public_key", "private_iv", "private_ct", "key_version")} if i else None}


@router.put("/identity")
def put_identity(body: IdentityIn, request: Request, user: dict = Depends(require_active),
                 store: Store = Depends(get_store)) -> NoteIdentityState:
    """Das eigene Schlüsselpaar anlegen — oder ersetzen, wenn sich das alte
    nicht mehr öffnen ließ. Prüfen kann der Server die Verpackung nicht: Wer
    Unsinn schickt, kann nur selbst keine Einladung per Adresse annehmen."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    _punkt(body.public_key, "public_key")
    _b64(body.private_iv, "private_iv", laenge=12)
    _b64(body.private_ct, "private_ct", hoechstens=256)
    store.set_note_identity(user["id"], public_key=body.public_key, private_iv=body.private_iv,
                            private_ct=body.private_ct, key_version=body.key_version)
    return get_identity(user, store)


@router.post("")
def create_shared(body: SharedNoteIn, request: Request, user: dict = Depends(require_active),
                  store: Store = Depends(get_store)) -> SharedNote:
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    _ziel(body.target_kind, body.target_key)
    _b64(body.key_iv, "key_iv", laenge=12)
    _b64(body.key_ct, "key_ct", hoechstens=WRAPPED_KEY_MAX)
    if (body.snapshot is None) != (body.snapshot_iv is None):
        raise HTTPException(422, "Stand nur mit IV.")
    if body.snapshot is not None and body.snapshot_iv is not None:
        _b64(body.snapshot_iv, "snapshot_iv", laenge=12)
        _b64(body.snapshot, "snapshot", hoechstens=SNAPSHOT_MAX)
    note_id = store.create_shared_note(user["id"], body.target_kind, body.target_key, key_iv=body.key_iv,
                                       key_ct=body.key_ct, key_version=body.key_version,
                                       snapshot_iv=body.snapshot_iv, snapshot=body.snapshot)
    if not note_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zu viele gemeinsame Notizen.")
    return _eine(store, note_id, user["id"])


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses={204: {"description": "Gelöscht"}})
async def delete_shared(note_id: str, request: Request, user: dict = Depends(require_active),
                        store: Store = Depends(get_store)) -> Response:
    """Nur die Leitung löscht die Notiz für alle; ein Mitglied verlässt sie
    über ``DELETE /{id}/members/{eigene Kennung}``."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    if _mitglied(store, note_id, user["id"])["role"] != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur wer die Notiz leitet, kann sie löschen.")
    store.delete_shared_note(note_id)
    await live.kick(note_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{note_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses={204: {"description": "Entfernt"}})
async def remove_member(note_id: str, member_id: int, request: Request, user: dict = Depends(require_active),
                        store: Store = Depends(get_store)) -> Response:
    """Selbst gehen darf jedes Mitglied; andere entfernen nur die Leitung."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    ich = _mitglied(store, note_id, user["id"])
    if member_id != user["id"] and ich["role"] != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur wer die Notiz leitet, kann andere entfernen.")
    if not store.shared_note_member(note_id, member_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht Mitglied.")
    store.leave_shared_note(note_id, member_id)
    await live.kick(note_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{note_id}/invites")
def create_invite(note_id: str, body: InviteIn, request: Request, user: dict = Depends(require_active),
                  store: Store = Depends(get_store)) -> SharedNoteInvite:
    """Jedes Mitglied darf einladen: Den Notizschlüssel kennt es ohnehin."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    _mitglied(store, note_id, user["id"])
    _b64(body.iv, "iv", laenge=12)
    _b64(body.ciphertext, "ciphertext", hoechstens=WRAPPED_KEY_MAX)
    _b64(body.verifier_hash, "verifier_hash", laenge=32)
    bis = (datetime.utcnow() + timedelta(days=body.days)).isoformat(timespec="seconds")
    invite_id = store.create_shared_note_invite(note_id, user["id"], body.iv, body.ciphertext, bis,
                                                body.verifier_hash)
    return {"id": invite_id, "expires_at": bis,
            "created_at": datetime.utcnow().isoformat(timespec="seconds")}


@router.get("/{note_id}/invites")
def list_invites(note_id: str, user: dict = Depends(require_active),
                 store: Store = Depends(get_store)) -> SharedNoteInvites:
    """Die Leitung sieht alle offenen Einladungen, ein Mitglied nur seine eigenen."""
    _an()
    ich = _mitglied(store, note_id, user["id"])
    nur = None if ich["role"] == "owner" else user["id"]
    return {"invites": [{"id": i["id"], "expires_at": i["expires_at"], "created_at": i["created_at"]}
                        for i in store.shared_note_invites(note_id, nur)]}


@router.delete("/{note_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses={204: {"description": "Zurückgezogen"}})
def delete_invite(note_id: str, invite_id: str, user: dict = Depends(require_active),
                  store: Store = Depends(get_store)) -> Response:
    _an()
    ich = _mitglied(store, note_id, user["id"])
    nur = None if ich["role"] == "owner" else user["id"]
    if not store.delete_shared_note_invite(note_id, invite_id, nur):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Einladung gibt es nicht.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{note_id}/address-invites")
def invite_address(note_id: str, body: AddressInviteIn, request: Request, background: BackgroundTasks,
                   user: dict = Depends(require_active), store: Store = Depends(get_store)) -> Ok:
    """Ein bestimmtes Konto einladen. Die Antwort ist IMMER dieselbe — ob es
    zu der Adresse ein Konto gibt, erfährt niemand (auch nicht über die
    Dauer: Einladung, Titel und Meldung entstehen erst nach der Antwort)."""
    _an()
    address_invite_limiter.check(request, subject=user["id"])
    _mitglied(store, note_id, user["id"])
    email = body.email.strip().lower()
    if "@" not in email or " " in email:
        raise HTTPException(422, "Das sieht nicht nach einer E-Mail-Adresse aus.")
    if len(store.shared_note_members(note_id)) >= store.SHARED_MAX_MEMBERS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Notiz hat schon die höchste Zahl an Mitgliedern.")
    ziel = store.get_web_user_by_email(email)
    if ziel and ziel["id"] != user["id"]:
        background.add_task(_adresse_einladen, note_id, user["id"], ziel["id"])
    return {"ok": True}


def _adresse_einladen(note_id: str, inviter_id: int, invitee_id: int) -> None:
    """Nach der Antwort, mit eigenen Datenbankverbindungen."""
    settings = get_settings()
    store = Store(settings.ratslotse_db)
    council = CouncilStore(settings.council_db, einmal=True)
    try:
        if not notify.konto_aktiv(store, invitee_id) or store.shared_note_member(note_id, invitee_id):
            return
        n = store.get_shared_note(note_id)
        if not n or not store.shared_note_member(note_id, inviter_id):
            return
        bis = (datetime.utcnow() + timedelta(days=ADDRESS_INVITE_DAYS)).isoformat(timespec="seconds")
        invite_id, neu = store.create_address_invite(note_id, inviter_id, invitee_id, bis)
        if not neu:
            return
        wer = (store.get_web_user_by_id(inviter_id) or {}).get("display_name") or "Jemand"
        titel = _ziel_titel(council, n["target_kind"], n["target_key"])
        worum = f"„{titel}“" if titel else ("einem Tagesordnungspunkt" if n["target_kind"] == "agenda_item"
                                             else "einem Beschluss")
        pfad = f"/notiz-einladung?a={invite_id}"
        html = (f"<p><b>{escape(wer)}</b> lädt dich ein, gemeinsam eine Notiz zu {escape(worum)} zu schreiben.</p>"
                "<p>Die Notiz ist Ende-zu-Ende verschlüsselt: Lesen können sie nur die Mitglieder, "
                "Ratslotse nicht. Nur dein Konto kann diese Einladung annehmen.</p>"
                f'<p><a href="{notify.APP_BASE_URL}{pfad}">Einladung ansehen</a></p>'
                "<p>Kennst du die Person nicht, lehn die Einladung einfach ab.</p>")
        if notify.einreihen(store, invitee_id, notify.N8_NOTIZ_EINLADUNG,
                            f"{wer} lädt dich zu einer gemeinsamen Notiz ein", html, pfad,
                            push_text=f"{wer} lädt dich ein, gemeinsam eine Notiz zu {worum} zu schreiben.",
                            wichtig=True):
            notify.zustellen_an(store, invitee_id)
    except Exception:  # noqa: BLE001 — die Antwort ist längst raus; ein Fehler gehört ins Protokoll
        import logging
        logging.getLogger(__name__).exception("Einladung per Adresse fehlgeschlagen")
    finally:
        council.close()
        store.close()


@router.post("/{note_id}/grants/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
             responses={204: {"description": "Übergeben"}, 409: {"description": "Nicht mehr offen"}})
def grant_invite(note_id: str, invite_id: str, body: GrantIn, request: Request, user: dict = Depends(require_active),
                 store: Store = Depends(get_store)) -> Response:
    """Ein Mitglied übergibt den Notizschlüssel an ein Konto, das eine
    Einladung per Adresse angenommen hat — verpackt für dessen öffentlichen
    Schlüssel, den der Server nicht öffnen kann."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    _mitglied(store, note_id, user["id"])
    _punkt(body.epk, "epk")
    _punkt(body.for_key, "for_key")
    _b64(body.iv, "iv", laenge=12)
    _b64(body.ct, "ct", hoechstens=WRAPPED_KEY_MAX)
    if not store.grant_address_invite(invite_id, note_id, user["id"], epk=body.epk, iv=body.iv, ct=body.ct,
                                      for_key=body.for_key):
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Einladung wartet nicht mehr auf den Schlüssel.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{note_id}/ticket")
def live_ticket(note_id: str, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> LiveTicket:
    _an()
    _mitglied(store, note_id, user["id"])
    return {"ticket": live.ticket(note_id, user["id"]), "expires_in": TICKET_TTL}


def _ziel_titel(council: CouncilStore, target_kind: str, target_key: str) -> str | None:
    """Der Titel des Punkts oder Beschlusses — öffentliche Ratsdaten, damit die
    Einladung sagt, worum es geht."""
    try:
        if target_kind == "agenda_item":
            ksinr, nr = target_key.split("|", 1)
            p = council.agenda_item_subject(int(ksinr), nr)
            return (p or {}).get("title") or None
        d = council.get_decision(int(target_key))
        return (d or {}).get("title") or None
    except Exception:  # noqa: BLE001 — ohne Titel lädt die Einladung trotzdem
        return None


@invites_router.get("/{invite_id}")
def invite_info(invite_id: str, user: dict = Depends(require_active), store: Store = Depends(get_store),
                council: CouncilStore = Depends(get_council_store)) -> NoteInviteInfo:
    _an()
    i = store.get_shared_note_invite(invite_id)
    n = store.get_shared_note(i["note_id"]) if i else None
    if not i or not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Einladung gilt nicht mehr.")
    return {"invite_id": i["id"], "note_id": n["id"], "target_kind": n["target_kind"], "target_key": n["target_key"],
            "target_title": _ziel_titel(council, n["target_kind"], n["target_key"]),
            "inviter_name": i["inviter_name"], "iv": i["iv"], "ciphertext": i["ciphertext"],
            "expires_at": i["expires_at"],
            "already_member": store.shared_note_member(n["id"], user["id"]) is not None}


@invites_router.post("/{invite_id}/accept")
def accept_invite(invite_id: str, body: AcceptIn, request: Request, user: dict = Depends(require_active),
                  store: Store = Depends(get_store)) -> SharedNote:
    """Beitreten: Der Browser hat den Schlüssel mit dem Anker ausgepackt und mit
    dem eigenen Datenschlüssel neu verpackt. Prüfen kann der Server das nicht —
    wer Unsinn schickt, sperrt nur sich selbst aus."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    i = store.get_shared_note_invite(invite_id)
    if not i or not store.get_shared_note(i["note_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Einladung gilt nicht mehr.")
    _b64(body.key_iv, "key_iv", laenge=12)
    _b64(body.key_ct, "key_ct", hoechstens=WRAPPED_KEY_MAX)
    _b64(body.verifier, "verifier", laenge=32)
    # Die Kennung steht im sichtbaren Teil des Links (und damit in Protokollen);
    # beitreten darf nur, wer auch das Geheimnis aus dem Anker hat.
    probe = base64.b64encode(hashlib.sha256(base64.b64decode(body.verifier)).digest()).decode()
    if not hmac.compare_digest(probe, i["verifier_hash"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Der Link ist unvollständig oder gehört zu einer anderen Einladung.")
    if store.join_shared_note(i["note_id"], user["id"], key_iv=body.key_iv, key_ct=body.key_ct,
                              key_version=body.key_version) == "full":
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Notiz hat schon die höchste Zahl an Mitgliedern.")
    return _eine(store, i["note_id"], user["id"])


def _adressat(store: Store, invite_id: str, user_id: int) -> dict:
    """Die Einladung — nur für das eingeladene Konto, sonst 404."""
    a = store.get_address_invite(invite_id)
    if not a or a["user_id"] != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Einladung gilt nicht mehr.")
    return a


@invites_router.get("/address/{invite_id}")
def address_invite_info(invite_id: str, user: dict = Depends(require_active), store: Store = Depends(get_store),
                        council: CouncilStore = Depends(get_council_store)) -> NoteInvitation:
    _an()
    return _invitation_out(_adressat(store, invite_id, user["id"]), store, council)


@invites_router.post("/address/{invite_id}/accept")
async def accept_address_invite(invite_id: str, request: Request, user: dict = Depends(require_active),
                                store: Store = Depends(get_store),
                                council: CouncilStore = Depends(get_council_store)) -> NoteInvitation:
    """Annehmen. Das Konto braucht dafür ein Schlüsselpaar (``PUT /identity``),
    sonst kann niemand den Notizschlüssel für es verpacken. Wer gerade in der
    Notiz ist, bekommt Bescheid und übergibt ihn sofort."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    a = _adressat(store, invite_id, user["id"])
    if not store.get_note_identity(user["id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Erst die Notizen einrichten, dann annehmen.")
    store.accept_address_invite(invite_id, user["id"])
    await live.verteilen(a["note_id"], {"t": "pending"})
    return _invitation_out(_adressat(store, invite_id, user["id"]), store, council)


@invites_router.post("/address/{invite_id}/decline", status_code=status.HTTP_204_NO_CONTENT,
                     response_class=Response, responses={204: {"description": "Abgelehnt"}})
def decline_address_invite(invite_id: str, user: dict = Depends(require_active),
                           store: Store = Depends(get_store)) -> Response:
    """Ablehnen. Die einladende Person erfährt es nicht eigens."""
    _an()
    _adressat(store, invite_id, user["id"])
    store.delete_address_invite(invite_id, user_id=user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invites_router.post("/address/{invite_id}/join")
def join_address_invite(invite_id: str, body: AddressJoinIn, request: Request, user: dict = Depends(require_active),
                        store: Store = Depends(get_store)) -> SharedNote:
    """Beitreten, sobald die Übergabe da ist: Der Browser hat den Schlüssel mit
    dem eigenen privaten Schlüssel ausgepackt und mit dem Datenschlüssel neu
    verpackt."""
    _an()
    shared_write_limiter.check(request, subject=user["id"])
    a = _adressat(store, invite_id, user["id"])
    if not a["grant_ct"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Schlüssel ist noch nicht übergeben.")
    _b64(body.key_iv, "key_iv", laenge=12)
    _b64(body.key_ct, "key_ct", hoechstens=WRAPPED_KEY_MAX)
    if store.join_shared_note(a["note_id"], user["id"], key_iv=body.key_iv, key_ct=body.key_ct,
                              key_version=body.key_version) == "full":
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Notiz hat schon die höchste Zahl an Mitgliedern.")
    store.delete_address_invite(invite_id)
    return _eine(store, a["note_id"], user["id"])


# ---- Live-Verbindung --------------------------------------------------------

def _mit_store(fn):
    """Eine Datenbankverbindung je Schritt (im Threadpool): Eine Live-Sitzung
    dauert Stunden, eine SQLite-Verbindung gehört einem Thread."""
    store = Store(get_settings().ratslotse_db, einmal=True)
    try:
        return fn(store)
    finally:
        store.close()


def _zustand(note_id: str, user_id: int, since: int) -> dict | None:
    """Der Stand ab ``since`` — ``None``, wenn das Konto nicht mehr dabei ist."""
    return _mit_store(lambda s: s.shared_note_state(note_id, since) if s.shared_note_member(note_id, user_id) else None)


def _dabei(note_id: str, user_id: int) -> bool:
    return _mit_store(lambda s: s.shared_note_member(note_id, user_id) is not None)


def _anhaengen(note_id: str, user_id: int, iv: str, ct: str) -> int | str | None:
    """Die Nummer der Änderung, ``None`` bei voller Liste, ``weg`` ohne Mitgliedschaft."""
    def schritt(s: Store) -> int | str | None:
        if not s.shared_note_member(note_id, user_id):
            return "weg"
        return s.add_shared_note_update(note_id, user_id, iv, ct)
    return _mit_store(schritt)


def _stand(note_id: str, user_id: int, upto: int, iv: str, ct: str) -> bool:
    return _mit_store(lambda s: bool(s.shared_note_member(note_id, user_id))
                      and s.save_shared_note_snapshot(note_id, upto, iv, ct))


def _ok_b64(wert: object, *, laenge: int | None = None, hoechstens: int | None = None) -> bool:
    if not isinstance(wert, str):
        return False
    try:
        roh = base64.b64decode(wert, validate=True)
    except (binascii.Error, ValueError):
        return False
    return (laenge is None or len(roh) == laenge) and (hoechstens is None or len(roh) <= hoechstens)


@dataclass(eq=False)
class _Verbindung:
    ws: WebSocket
    user_id: int
    takt: deque = field(default_factory=deque)

    async def senden(self, nachricht: dict) -> None:
        try:
            await self.ws.send_text(json.dumps(nachricht))
        except Exception:  # noqa: BLE001 — eine tote Verbindung räumt ihr eigener Handler weg
            pass

    def zu_schnell(self) -> bool:
        jetzt = time.monotonic()
        while self.takt and self.takt[0] < jetzt - LIVE_RATE[1]:
            self.takt.popleft()
        self.takt.append(jetzt)
        return len(self.takt) > LIVE_RATE[0]


class _Live:
    """Räume je Notiz, im Speicher des einen API-Prozesses."""

    def __init__(self) -> None:
        self.raeume: dict[str, set[_Verbindung]] = {}
        self.tickets: dict[str, tuple[str, int, float]] = {}

    def ticket(self, note_id: str, user_id: int) -> str:
        jetzt = time.monotonic()
        for k in [k for k, (_, _, bis) in self.tickets.items() if bis < jetzt]:
            self.tickets.pop(k, None)
        t = secrets.token_urlsafe(24)
        self.tickets[t] = (note_id, user_id, jetzt + TICKET_TTL)
        return t

    def einloesen(self, ticket: str, note_id: str) -> int | None:
        eintrag = self.tickets.pop(ticket, None)
        if not eintrag or eintrag[0] != note_id or eintrag[2] < time.monotonic():
            return None
        return eintrag[1]

    async def verteilen(self, note_id: str, nachricht: dict, ausser: _Verbindung | None = None) -> None:
        await asyncio.gather(*(v.senden(nachricht) for v in list(self.raeume.get(note_id, ())) if v is not ausser))

    async def anwesend(self, note_id: str) -> None:
        online = sorted({v.user_id for v in self.raeume.get(note_id, ())})
        await self.verteilen(note_id, {"t": "presence", "online": online})

    async def kick(self, note_id: str, user_id: int | None) -> None:
        """Entfernte Mitglieder (oder alle, wenn die Notiz weg ist) trennen —
        und ihre noch nicht eingelösten Tickets verwerfen."""
        for k in [k for k, (n, u, _) in self.tickets.items() if n == note_id and (user_id is None or u == user_id)]:
            self.tickets.pop(k, None)
        for v in [v for v in self.raeume.get(note_id, ()) if user_id is None or v.user_id == user_id]:
            try:
                await v.ws.close(code=4403)
            except Exception:  # noqa: BLE001
                pass


live = _Live()


@router.websocket("/{note_id}/live")
async def live_socket(ws: WebSocket, note_id: str, ticket: str = "") -> None:
    if not (features.an("notizen") and features.an("notizen-teilen")):
        await ws.close(code=4404)
        return
    user_id = live.einloesen(ticket, note_id)
    if user_id is None:
        await ws.close(code=4401)
        return
    # Das Ticket kann älter sein als ein Rauswurf: hier noch einmal fragen.
    if not await run_in_threadpool(_dabei, note_id, user_id):
        await ws.close(code=4403)
        return
    await ws.accept()
    ich = _Verbindung(ws, user_id)
    live.raeume.setdefault(note_id, set()).add(ich)
    await ich.senden({"t": "hello", "you": user_id})
    await live.anwesend(note_id)

    async def waechter() -> None:
        while True:
            await asyncio.sleep(MEMBERSHIP_CHECK_SECONDS)
            if not await run_in_threadpool(_dabei, note_id, user_id):
                try:
                    await ws.close(code=4403)
                except Exception:  # noqa: BLE001
                    pass
                return

    wache = asyncio.create_task(waechter())
    try:
        while True:
            roh = await ws.receive_text()
            if len(roh) > FRAME_MAX:
                await ws.close(code=4413)
                return
            if ich.zu_schnell():
                await ws.close(code=4429)
                return
            try:
                m = json.loads(roh)
            except ValueError:
                continue
            art = m.get("t") if isinstance(m, dict) else None
            if art == "sync":
                since = m.get("since") if isinstance(m.get("since"), int) else 0
                zustand = await run_in_threadpool(_zustand, note_id, user_id, max(0, since))
                if zustand is None:
                    await ws.close(code=4403)
                    return
                await ich.senden({"t": "sync", **zustand})
            elif art == "update":
                if not (_ok_b64(m.get("iv"), laenge=12) and _ok_b64(m.get("ct"), hoechstens=UPDATE_MAX)):
                    continue
                seq = await run_in_threadpool(_anhaengen, note_id, user_id, m["iv"], m["ct"])
                if seq == "weg":
                    await ws.close(code=4403)
                    return
                if seq is None:
                    # Liste voll: erst ein Stand, dann weiter (der Client fasst zusammen).
                    await ich.senden({"t": "full", "c": m.get("c")})
                    continue
                await ich.senden({"t": "ack", "c": m.get("c"), "seq": seq})
                await live.verteilen(note_id, {"t": "update", "seq": seq, "iv": m["iv"], "ct": m["ct"],
                                               "from": user_id}, ausser=ich)
            elif art == "awareness":
                if _ok_b64(m.get("iv"), laenge=12) and _ok_b64(m.get("ct"), hoechstens=AWARENESS_MAX):
                    await live.verteilen(note_id, {"t": "awareness", "iv": m["iv"], "ct": m["ct"],
                                                   "from": user_id}, ausser=ich)
            elif art == "snapshot":
                upto = m.get("upto")
                if not (isinstance(upto, int) and _ok_b64(m.get("iv"), laenge=12)
                        and _ok_b64(m.get("ct"), hoechstens=SNAPSHOT_MAX)):
                    continue
                ok = await run_in_threadpool(_stand, note_id, user_id, upto, m["iv"], m["ct"])
                await ich.senden({"t": "snapshot", "ok": ok, "upto": upto})
    except WebSocketDisconnect:
        pass
    finally:
        wache.cancel()
        raum = live.raeume.get(note_id)
        if raum is not None:
            raum.discard(ich)
            if not raum:
                live.raeume.pop(note_id, None)
        await live.anwesend(note_id)
