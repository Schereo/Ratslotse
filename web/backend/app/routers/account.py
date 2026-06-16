"""Account self-service: verify the user's own NWZ subscription credentials.

We validate the credentials live against the NWZ API but do NOT store the
password — only a 'verified' marker plus the NWZ username for display. Proving a
valid subscription is what unlocks access to NWZ content.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from nwz.api import NWZClient
from nwz.store import Store

from ..config import get_settings
from ..deps import get_store, require_active
from ..schemas import NwzCredentialsIn, UserOut
from .auth import _to_out

router = APIRouter(prefix="/api/account", tags=["account"])


@router.post("/nwz-credentials", response_model=UserOut)
def verify_nwz_credentials(
    body: NwzCredentialsIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> UserOut:
    settings = get_settings()
    client = NWZClient(body.nwz_username.strip(), body.nwz_password)
    try:
        valid = client.verify_credentials(settings.nwz_folder)
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "NWZ ist gerade nicht erreichbar. Bitte später erneut versuchen.")
    if not valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "NWZ-Login ungültig. Bitte prüfe Benutzername und Passwort.")
    store.set_nwz_verified(user["id"], body.nwz_username.strip())
    return _to_out(store.get_web_user_by_id(user["id"]))
