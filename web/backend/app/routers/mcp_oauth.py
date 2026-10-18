"""OAuth 2.1 für den MCP-Server: Ratslotse als eigener Autorisierungsserver.

**Warum es das gibt.** ChatGPT kann einem eigenen MCP-Server keinen festen
Schlüssel schicken, nur OAuth 2.1 mit PKCE (OpenAI: ChatGPT „can not present
custom API keys“, developers.openai.com/plugins/build/auth). Claude im Web und
auf dem iPad geht denselben Weg. Die persönlichen Schlüssel (``rlmcp_…``,
``routers/mcp.py``) bleiben daneben bestehen.

**Der Ablauf** (MCP-Spezifikation 2025-11-25, „Authorization“):

1. Der Agent ruft ``/api/mcp`` ohne Token, bekommt 401 mit
   ``resource_metadata`` und liest daraus ``/.well-known/oauth-protected-resource``
   (RFC 9728) und ``/.well-known/oauth-authorization-server`` (RFC 8414).
2. Er meldet sich als Client an: per Dynamic Client Registration
   (``/api/oauth/register``, RFC 7591) oder mit einer https-Adresse als
   ``client_id``, unter der sein Steckbrief liegt (Client ID Metadata
   Document, CIMD — ChatGPT bevorzugt das).
3. Der Browser landet auf der Freigabe-Seite (``/oauth/freigeben``, Next).
   Die fragt ``GET /api/oauth/authorize``, ob die Anfrage gültig ist, und
   schickt mit „Erlauben“ ``POST /api/oauth/authorize`` — mit dem
   Sitzungs-Cookie, also nur für ein angemeldetes Konto mit dem Recht ``mcp``.
4. Der Agent tauscht den Code am Token-Endpunkt gegen ein Zugangs-Token (eine
   Stunde) und ein Erneuerungs-Token (30 Tage ohne Nutzung, rotiert bei
   jedem Gebrauch).

**Die Grenzen, auf die es ankommt:**

- **Rücksprungadressen exakt.** Nur, was der Client registriert hat, Zeichen
  für Zeichen. Ist die Adresse nicht geprüft, wird nie weitergeleitet, nur
  ein Fehler gezeigt — sonst wäre die Seite ein offener Umlenker.
- **PKCE mit S256 ist Pflicht**, ``plain`` gibt es nicht.
- **Audience.** Jedes Token gehört zu genau einer Ressource (``/api/mcp``
  dieser Instanz); ein ``resource``-Parameter für etwas anderes wird
  abgewiesen.
- **Ein Code einmal.** Ein zweiter Einlöseversuch widerruft die Freigabe;
  ebenso ein schon abgelöstes Erneuerungs-Token.
- **Bremsen** an Registrierung, Token-Endpunkt und Freigabe — der
  Token-Endpunkt zählt zusätzlich Fehlversuche je Netzadresse.
- **CIMD-Abruf ohne SSRF.** Nur https, nur öffentliche Adressen, keine
  Weiterleitung, drei Sekunden, zehn Kilobyte.

Opake Tokens statt JWT: Ein Widerruf wirkt sofort, und es ist dasselbe Muster
wie bei den persönlichen Schlüsseln (nur der SHA-256 liegt in der Datenbank).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import socket
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from kern import features
from kern import roles as rollen
from kern.store import Store

from ..antworten import (McpGrant, McpGrantList, OAuthAuthorizeCheck, OAuthAuthorizeResult,
                         OAuthClientRegistered, OAuthProtectedResource, OAuthServerMetadata,
                         OAuthToken, Ok)
from ..config import get_settings
from ..deps import get_current_user, get_store, ist_aktiv, kein_fremder_aufruf, require_permission
from ..ratelimit import RateLimiter

router = APIRouter(tags=["mcp"])

_log = logging.getLogger(__name__)

require_mcp = require_permission("mcp")

#: Das eine Recht, das es gibt: öffentliche Ratsdaten lesen. Was ein Client
#: sonst anfragt (``openid``, ``offline_access`` …), fällt still weg — RFC 6749
#: erlaubt dem Server, weniger zu gewähren, und nennt es in der Antwort.
SCOPE = "ratsdaten:lesen"

ACCESS_TTL = timedelta(hours=1)
#: Gleitend: Jede Erneuerung verlängert um 30 Tage. Ein Agent, der einen
#: Monat lang nicht fragt, muss neu freigegeben werden.
REFRESH_TTL = timedelta(days=30)
CODE_TTL = timedelta(seconds=60)
#: So lange gilt ein abgerufener Client-Steckbrief (CIMD), bevor er neu geholt wird.
CIMD_TTL = timedelta(hours=24)
CIMD_MAX_BYTES = 10_000
CIMD_TIMEOUT_S = 3.0

#: Registrierung: je Netzadresse 10 in der Stunde, insgesamt 200 — ChatGPT
#: registriert einmal je Verbindung, nicht je Anfrage.
_registrieren = RateLimiter(10, 3600)
REGISTRIERUNGEN_JE_STUNDE = 200
#: Token-Endpunkt: 60 Anfragen je Minute und Adresse, und nach 20
#: Fehlversuchen in zehn Minuten ist für diese Adresse Pause.
_token = RateLimiter(60, 60)
_token_fehler = RateLimiter(20, 600)
#: Freigaben je Konto: 30 in der Stunde reichen für jedes Herumprobieren.
_freigeben = RateLimiter(30, 3600)
_widerrufen = RateLimiter(60, 60)

_PKCE = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
#: Eigenes Schema einer App auf dem Gerät (RFC 8252, 7.1), etwa
#: ``cursor://`` oder ``com.example.agent:/``. Nie die Schemata, mit denen ein
#: Browser selbst etwas anfängt — die wären eine Umleitung in die Seite hinein.
_APP_SCHEMA = re.compile(r"^[a-z][a-z0-9+.\-]{1,63}$")
_KEIN_APP_SCHEMA = {"javascript", "data", "file", "vbscript", "about", "blob", "filesystem",
                    "ftp", "ws", "wss", "mailto", "tel", "sms", "intent", "view-source", "chrome",
                    "jar", "content", "resource"}
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def _feature_an() -> None:
    if not features.an("mcp-server"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")


def issuer() -> str:
    return get_settings().app_base_url.rstrip("/")


def resource() -> str:
    """Die kanonische Adresse des MCP-Servers — die Audience jedes Tokens."""
    return issuer() + "/api/mcp"


def resource_metadata_url() -> str:
    return issuer() + "/.well-known/oauth-protected-resource"


def gleiche_ressource(a: str, b: str) -> bool:
    """Schema und Host ohne Groß/klein, Pfad ohne Schrägstrich am Ende."""
    def norm(u: str) -> tuple[str, str, str]:
        t = urlsplit(u.strip())
        return t.scheme.lower(), t.netloc.lower(), t.path.rstrip("/")
    try:
        return norm(a) == norm(b)
    except ValueError:
        return False


def _jetzt() -> datetime:
    return datetime.now(UTC)


def _iso(zeit: datetime) -> str:
    return zeit.astimezone(UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Rücksprungadressen
# --------------------------------------------------------------------------- #

def redirect_art(uri: str) -> Literal["web", "local", "app"] | None:
    """Welche Art Rücksprungadresse — oder ``None``, wenn sie nicht taugt.

    Erlaubt sind https mit Host, http nur auf die eigene Maschine
    (localhost, 127.0.0.1, [::1]) und das eigene Schema einer App. Nie:
    Fragment, Zugangsdaten in der Adresse, Leerzeichen, Steuerzeichen.
    """
    if not uri or len(uri) > 500 or any(c.isspace() or ord(c) < 32 for c in uri):
        return None
    try:
        t = urlsplit(uri)
    except ValueError:
        return None
    if t.fragment or "#" in uri or "@" in t.netloc:
        return None
    schema = t.scheme.lower()
    if schema == "https":
        return "web" if t.hostname else None
    if schema == "http":
        return "local" if t.hostname in _LOOPBACK else None
    if _APP_SCHEMA.match(schema) and t.scheme == schema and schema not in _KEIN_APP_SCHEMA:
        return "app"
    return None


def redirect_host(uri: str) -> str:
    """Was die Freigabe-Seite als Ziel zeigt: der Host, auf der eigenen
    Maschine samt Port (welches Programm lauscht dort?), bei einer App ihr
    Schema."""
    t = urlsplit(uri)
    if t.scheme.lower() == "https":
        return (t.hostname or "").lower()
    if t.scheme.lower() == "http":
        return t.netloc.lower()
    return t.scheme.lower() + "://"


def _anhaengen(uri: str, werte: dict[str, str]) -> str:
    """Parameter an die Rücksprungadresse hängen, ihre eigene Query bleibt."""
    t = urlsplit(uri)
    query = parse_qsl(t.query, keep_blank_values=True) + list(werte.items())
    return urlunsplit((t.scheme, t.netloc, t.path, urlencode(query), ""))


# --------------------------------------------------------------------------- #
# Clients: DCR und CIMD
# --------------------------------------------------------------------------- #

def _name(roh: Any, ersatz: str) -> str:
    if not isinstance(roh, str):
        return ersatz
    name = "".join(c for c in roh if c.isprintable()).strip()
    return name[:80] or ersatz


def _redirects_pruefen(roh: Any) -> list[str] | str:
    """Die Liste — oder der Grund, warum sie nicht taugt."""
    if not isinstance(roh, list) or not roh:
        return "redirect_uris fehlt."
    if len(roh) > 5:
        return "Höchstens fünf redirect_uris."
    for uri in roh:
        if not isinstance(uri, str) or redirect_art(uri) is None:
            return f"Unzulässige redirect_uri: {str(uri)[:100]}"
    return list(dict.fromkeys(roh))


def cimd_adresse_ok(client_id: str) -> bool:
    """Darf diese client_id als Steckbrief-Adresse abgerufen werden?"""
    if len(client_id) > 500:
        return False
    try:
        t = urlsplit(client_id)
    except ValueError:
        return False
    return (t.scheme == "https" and bool(t.hostname) and t.path not in ("", "/")
            and not t.fragment and "@" not in t.netloc and t.port in (None, 443))


def _oeffentlich(host: str) -> bool:
    """Löst der Name nur auf öffentliche Adressen auf? Sonst könnte jeder,
    der sich als Client ausgibt, unseren Server Anfragen ins eigene Netz
    stellen lassen (Tailnet, NAS-Proxy, Metadaten-Dienste)."""
    try:
        adressen = {i[4][0] for i in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except OSError:
        return False
    if not adressen:
        return False
    for a in adressen:
        try:
            if not ipaddress.ip_address(str(a).split("%")[0]).is_global:
                return False
        except ValueError:
            return False
    return True


def cimd_abrufen(url: str) -> bytes | str:
    """Den Steckbrief holen — die Bytes, oder der Grund, warum nicht.

    Eigene Funktion, damit die Tests sie ersetzen können, ohne ins Netz zu
    gehen. Die Gegenstelle wird nach dem Verbinden noch einmal geprüft: Ein
    Name, der zwischen Prüfung und Abruf auf eine interne Adresse umspringt,
    bekommt so wenigstens keine Antwort mehr gelesen.
    """
    host = urlsplit(url).hostname or ""
    if not _oeffentlich(host):
        return "Die Adresse des Client-Steckbriefs ist nicht öffentlich erreichbar."
    try:
        with httpx.Client(timeout=CIMD_TIMEOUT_S, follow_redirects=False) as c, \
                c.stream("GET", url, headers={"Accept": "application/json"}) as r:
            strom = r.extensions.get("network_stream")
            gegenstelle = strom.get_extra_info("server_addr") if strom is not None else None
            if gegenstelle:
                try:
                    if not ipaddress.ip_address(str(gegenstelle[0])).is_global:
                        return "Die Adresse des Client-Steckbriefs ist nicht öffentlich erreichbar."
                except ValueError:
                    pass
            if r.status_code != 200:
                return f"Client-Steckbrief nicht abrufbar (HTTP {r.status_code})."
            daten = b""
            for stueck in r.iter_bytes():
                daten += stueck
                if len(daten) > CIMD_MAX_BYTES:
                    return "Client-Steckbrief ist zu groß."
            return daten
    except httpx.HTTPError:
        return "Client-Steckbrief nicht abrufbar."


def _cimd_client(store: Store, client_id: str) -> dict | str:
    zeile = store.get_mcp_oauth_client(client_id)
    if zeile and zeile.get("fetched"):
        try:
            frisch = _jetzt() - datetime.fromisoformat(zeile["fetched"]) < CIMD_TTL
        except ValueError:
            frisch = False
        if frisch:
            return zeile
    roh = cimd_abrufen(client_id)
    if isinstance(roh, str):
        return roh
    try:
        doc = json.loads(roh)
    except (ValueError, UnicodeDecodeError):
        return "Client-Steckbrief ist kein JSON."
    if not isinstance(doc, dict) or doc.get("client_id") != client_id:
        return "Client-Steckbrief passt nicht zu seiner Adresse."
    uris = _redirects_pruefen(doc.get("redirect_uris"))
    if isinstance(uris, str):
        return uris
    name = _name(doc.get("client_name"), urlsplit(client_id).hostname or "Agent")
    store.save_mcp_oauth_client(client_id, "cimd", name, uris, fetched=True)
    return {"client_id": client_id, "kind": "cimd", "client_name": name, "redirect_uris": uris}


def client_holen(store: Store, client_id: str) -> dict | str:
    """Der Client zu einer client_id — oder warum es ihn nicht gibt."""
    if not client_id:
        return "client_id fehlt."
    if client_id.startswith("https://"):
        if not cimd_adresse_ok(client_id):
            return "Unzulässige client_id."
        return _cimd_client(store, client_id)
    zeile = store.get_mcp_oauth_client(client_id)
    if not zeile or zeile["kind"] != "dcr":
        return "Unbekannter Client. Bitte die Verbindung im Agenten neu anlegen."
    return zeile


# --------------------------------------------------------------------------- #
# Metadaten
# --------------------------------------------------------------------------- #

def _schutzmetadaten() -> OAuthProtectedResource:
    return {
        "resource": resource(),
        "resource_name": "Ratslotse — Ratsdaten Oldenburg",
        "authorization_servers": [issuer()],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_documentation": issuer() + "/docs/mcp/",
    }


@router.get("/.well-known/oauth-protected-resource")
def protected_resource() -> OAuthProtectedResource:
    """RFC 9728 — öffentlich, wie es die Spezifikation verlangt."""
    _feature_an()
    return _schutzmetadaten()


@router.get("/.well-known/oauth-protected-resource/api/mcp")
def protected_resource_path() -> OAuthProtectedResource:
    """Dieselben Metadaten unter der Pfad-Variante, die Clients zuerst probieren."""
    _feature_an()
    return _schutzmetadaten()


@router.get("/.well-known/oauth-authorization-server")
def authorization_server() -> OAuthServerMetadata:
    """RFC 8414 — öffentlich."""
    _feature_an()
    basis = issuer()
    return {
        "issuer": basis,
        "authorization_endpoint": basis + "/oauth/freigeben",
        "token_endpoint": basis + "/api/oauth/token",
        "registration_endpoint": basis + "/api/oauth/register",
        "revocation_endpoint": basis + "/api/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": [SCOPE],
        "client_id_metadata_document_supported": True,
        # RFC 9207: `iss` in der Antwort — damit gibt ChatGPT eine feste
        # Rücksprungadresse statt einer je Verbindung.
        "authorization_response_iss_parameter_supported": True,
        "service_documentation": basis + "/docs/mcp/",
    }


# --------------------------------------------------------------------------- #
# Registrierung (RFC 7591)
# --------------------------------------------------------------------------- #

def _oauth_fehler(code: str, text: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": code, "error_description": text}, status_code=status_code,
                        headers={"Cache-Control": "no-store"})


@router.post("/api/oauth/register", status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    meta: Any = Body(None),
    store: Store = Depends(get_store),
) -> OAuthClientRegistered:
    """Öffentlich, aber gebremst: Ein Agent registriert sich, bevor es ein
    Konto zu ihm gibt. Die Registrierung allein öffnet nichts — erst eine
    Freigabe durch ein Konto mit dem Recht ``mcp``."""
    _feature_an()
    _registrieren.check(request)
    store.purge_mcp_oauth()
    if store.count_mcp_oauth_clients_since(_jetzt() - timedelta(hours=1)) >= REGISTRIERUNGEN_JE_STUNDE:
        return _oauth_fehler("temporarily_unavailable",  # type: ignore[return-value]
                             "Gerade zu viele Registrierungen. Später noch einmal.", 429)
    if not isinstance(meta, dict):
        return _oauth_fehler("invalid_client_metadata",  # type: ignore[return-value]
                             "Erwartet wird ein JSON-Objekt.")
    uris = _redirects_pruefen(meta.get("redirect_uris"))
    if isinstance(uris, str):
        return _oauth_fehler("invalid_redirect_uri", uris)  # type: ignore[return-value]
    grants = meta.get("grant_types") or ["authorization_code", "refresh_token"]
    if not isinstance(grants, list) or not set(grants) <= {"authorization_code", "refresh_token"}:
        return _oauth_fehler("invalid_client_metadata",  # type: ignore[return-value]
                             "Nur authorization_code und refresh_token.")
    antworten = meta.get("response_types") or ["code"]
    if antworten != ["code"]:
        return _oauth_fehler("invalid_client_metadata",  # type: ignore[return-value]
                             "Nur response_type code.")
    client_id = "rlcl_" + secrets.token_urlsafe(18)
    name = _name(meta.get("client_name"), "Unbenannter Agent")
    store.save_mcp_oauth_client(client_id, "dcr", name, uris)
    return {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "client_name": name,
        "redirect_uris": uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        # Was immer der Client wünscht: Er bekommt kein Geheimnis. PKCE
        # schützt den Code, und ein Geheimnis in einem Agenten wäre keins.
        "token_endpoint_auth_method": "none",
    }


# --------------------------------------------------------------------------- #
# Freigabe
# --------------------------------------------------------------------------- #

class AuthorizeParams(BaseModel):
    """Die Parameter der Autorisierungsanfrage, wie sie der Agent an
    ``/oauth/freigeben`` gehängt hat."""
    response_type: str | None = Field(None, max_length=50)
    client_id: str | None = Field(None, max_length=500)
    redirect_uri: str | None = Field(None, max_length=500)
    code_challenge: str | None = Field(None, max_length=200)
    code_challenge_method: str | None = Field(None, max_length=20)
    state: str | None = Field(None, max_length=1000)
    scope: str | None = Field(None, max_length=1000)
    resource: str | None = Field(None, max_length=500)


class AuthorizeDecision(AuthorizeParams):
    approve: bool = False


class _Geprueft(BaseModel):
    client_id: str
    client_name: str
    client_kind: str
    redirect_uri: str
    code_challenge: str
    state: str | None


def _pruefen(p: AuthorizeParams, store: Store) -> tuple[_Geprueft | None, str | None, str | None]:
    """``(geprüft, fehler, absage_url)``.

    Solange Client und Rücksprungadresse nicht feststehen, gibt es keine
    ``absage_url``: Dann wird nicht weitergeleitet, sondern nur der Fehler
    gezeigt (OAuth 2.1, 4.1.2.1). Danach geht jeder Fehler als
    ``error=…`` an den Agenten zurück."""
    client = client_holen(store, p.client_id or "")
    if isinstance(client, str):
        return None, client, None
    uris: list[str] = client["redirect_uris"]
    redirect = p.redirect_uri
    if not redirect:
        if len(uris) != 1:
            return None, "redirect_uri fehlt.", None
        redirect = uris[0]
    if redirect not in uris:
        return None, ("Die Rücksprungadresse ist für diesen Agenten nicht angemeldet. "
                      "Aus Sicherheitsgründen geht es hier nicht weiter."), None

    def absage(code: str, text: str) -> str:
        werte = {"error": code, "error_description": text, "iss": issuer()}
        if p.state is not None:
            werte["state"] = p.state
        return _anhaengen(redirect, werte)

    if p.response_type != "code":
        return None, "Nur response_type=code.", absage("unsupported_response_type", "code only")
    if p.code_challenge_method != "S256" or not p.code_challenge or not _PKCE.match(p.code_challenge):
        return None, "Der Agent hat kein gültiges PKCE (S256) geschickt.", absage(
            "invalid_request", "PKCE with S256 is required")
    if p.resource and not gleiche_ressource(p.resource, resource()):
        return None, "Der Agent will Zugang zu einem anderen Dienst.", absage(
            "invalid_target", "unknown resource")
    return _Geprueft(client_id=client["client_id"], client_name=client["client_name"],
                     client_kind=client["kind"], redirect_uri=redirect,
                     code_challenge=p.code_challenge, state=p.state), None, None


def _darf(user: dict) -> bool:
    return ist_aktiv(user) and "mcp" in rollen.permissions_for(user.get("roles"))


@router.get("/api/oauth/authorize")
def authorize_check(
    request: Request,
    p: AuthorizeParams = Depends(),
    store: Store = Depends(get_store),
) -> OAuthAuthorizeCheck:
    """Für die Freigabe-Seite: Ist die Anfrage gültig, wer fragt, wohin geht
    es zurück? Öffentlich, weil die Seite auch ohne Anmeldung erklären muss,
    warum es erst zur Anmeldung geht. Verrät nichts über ein Konto."""
    _feature_an()
    geprueft, fehler, absage = _pruefen(p, store)
    leer: OAuthAuthorizeCheck = {
        "status": "error", "message": fehler, "client_name": None, "client_id_host": None,
        "redirect_host": None, "redirect_kind": None, "cancel_url": absage,
        "already_connected": False, "at_limit": False,
    }
    if geprueft is None:
        return leer
    antwort: OAuthAuthorizeCheck = {
        **leer,
        "status": "ready",
        "message": None,
        "client_name": geprueft.client_name,
        "client_id_host": (urlsplit(geprueft.client_id).hostname
                           if geprueft.client_kind == "cimd" else None),
        "redirect_host": redirect_host(geprueft.redirect_uri),
        "redirect_kind": redirect_art(geprueft.redirect_uri),
        "cancel_url": _anhaengen(geprueft.redirect_uri, {
            "error": "access_denied", "iss": issuer(),
            **({"state": geprueft.state} if geprueft.state is not None else {})}),
    }
    try:
        user = get_current_user(request, store)
    except HTTPException:
        return {**antwort, "status": "login"}
    if not ist_aktiv(user):
        return {**antwort, "status": "forbidden",
                "message": "Dein Konto ist nicht aktiv. Bestätige erst deine E-Mail-Adresse."}
    if not _darf(user):
        return {**antwort, "status": "forbidden",
                "message": "Dein Konto hat keinen MCP-Zugang (Rolle „MCP-Zugang“)."}
    andere = store.count_mcp_oauth_grants(user["id"], ohne_client=geprueft.client_id)
    schon = store.count_mcp_oauth_grants(user["id"]) > andere
    return {**antwort, "already_connected": schon, "at_limit": andere >= store.MCP_GRANTS_MAX}


@router.post("/api/oauth/authorize", dependencies=[Depends(kein_fremder_aufruf)])
def authorize_decide(
    entscheidung: AuthorizeDecision,
    request: Request,
    user: dict = Depends(require_mcp),
    store: Store = Depends(get_store),
) -> OAuthAuthorizeResult:
    """„Erlauben“ oder „Ablehnen“ — nur mit Sitzung, nur von Ratslotse selbst
    (``kein_fremder_aufruf``; die Seite lässt sich außerdem nicht einbetten,
    ``frame-ancestors 'none'``)."""
    _feature_an()
    _freigeben.check(request, subject=user["id"])
    geprueft, fehler, absage = _pruefen(entscheidung, store)
    if geprueft is None:
        if absage:
            return {"redirect": absage}
        raise HTTPException(status.HTTP_400_BAD_REQUEST, fehler or "Ungültige Anfrage.")
    zurueck = {"iss": issuer(), **({"state": geprueft.state} if geprueft.state is not None else {})}
    if not entscheidung.approve:
        return {"redirect": _anhaengen(geprueft.redirect_uri, {"error": "access_denied", **zurueck})}
    if store.count_mcp_oauth_grants(user["id"], ohne_client=geprueft.client_id) >= store.MCP_GRANTS_MAX:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Höchstens {store.MCP_GRANTS_MAX} verbundene Agenten. "
                            "Trenn erst einen in den Einstellungen.")
    code = store.create_mcp_oauth_code(
        owner_id=user["id"], client_id=geprueft.client_id, client_name=geprueft.client_name,
        redirect_uri=geprueft.redirect_uri, redirect_host=redirect_host(geprueft.redirect_uri),
        code_challenge=geprueft.code_challenge, scope=SCOPE, resource=resource(),
        token_version=int(user.get("token_version") or 0), gueltig=CODE_TTL)
    return {"redirect": _anhaengen(geprueft.redirect_uri, {"code": code, **zurueck})}


# --------------------------------------------------------------------------- #
# Token
# --------------------------------------------------------------------------- #

def _pkce_ok(verifier: str, challenge: str) -> bool:
    if not _PKCE.match(verifier or ""):
        return False
    berechnet = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    return hmac.compare_digest(berechnet.decode(), challenge)


def _client_aus_basic(request: Request) -> str | None:
    """``client_secret_basic`` schicken manche Clients trotzdem — die
    client_id daraus nehmen wir, das Geheimnis ignorieren wir (es gibt keins)."""
    kopf = request.headers.get("Authorization", "")
    if not kopf.startswith("Basic "):
        return None
    try:
        roh = base64.b64decode(kopf[6:]).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    return unquote(roh.split(":", 1)[0]) or None


def _konto_darf(store: Store, grant: dict) -> bool:
    user = store.get_web_user_by_id(int(grant["owner_id"]))
    if not user:
        return False
    if int(user.get("token_version") or 0) != int(grant["token_version"]):
        return False
    return _darf(user)


@router.post("/api/oauth/token")
def token(
    request: Request,
    grant_type: str = Form(""),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    client_id: str | None = Form(None),
    resource_param: str | None = Form(None, alias="resource"),
    store: Store = Depends(get_store),
) -> OAuthToken:
    """Code bzw. Erneuerungs-Token gegen ein neues Token-Paar.

    Öffentlich (der Agent hat keine Sitzung), aber gebremst: je Adresse 60
    Anfragen in der Minute, und nach 20 Fehlversuchen in zehn Minuten nimmt
    der Endpunkt von dort gar nichts mehr an."""
    _feature_an()
    _token.check(request)
    adresse = request.client.host if request.client else "unbekannt"
    if _token_fehler.ist_voll(subject=f"token:{adresse}"):
        return _oauth_fehler("slow_down", "Zu viele Fehlversuche.", 429)  # type: ignore[return-value]

    def fehler(code_: str, text: str) -> JSONResponse:
        _token_fehler.zaehlen(subject=f"token:{adresse}")
        return _oauth_fehler(code_, text)

    client_id = client_id or _client_aus_basic(request)
    if resource_param and not gleiche_ressource(resource_param, resource()):
        return fehler("invalid_target", "unknown resource")  # type: ignore[return-value]

    if grant_type == "authorization_code":
        zeile = store.take_mcp_oauth_code(code or "")
        if zeile is None:
            return fehler("invalid_grant", "unknown code")  # type: ignore[return-value]
        if zeile["used"]:
            # Ein Code zweimal: Jemand anderes hat ihn auch. Weg mit allem,
            # was damit schon ausgestellt wurde.
            store.revoke_mcp_oauth_grant(int(zeile["grant_id"]))
            _log.warning("MCP-OAuth: Code doppelt eingelöst, Freigabe %s widerrufen",
                         zeile["grant_id"])
            return fehler("invalid_grant", "code already used")  # type: ignore[return-value]
        if zeile["expires"] < _iso(_jetzt()):
            return fehler("invalid_grant", "code expired")  # type: ignore[return-value]
        if client_id != zeile["client_id"]:
            return fehler("invalid_grant", "client mismatch")  # type: ignore[return-value]
        if (redirect_uri or zeile["redirect_uri"]) != zeile["redirect_uri"]:
            return fehler("invalid_grant", "redirect_uri mismatch")  # type: ignore[return-value]
        if not _pkce_ok(code_verifier or "", zeile["code_challenge"]):
            return fehler("invalid_grant", "PKCE verification failed")  # type: ignore[return-value]
        grant = store.get_mcp_oauth_grant(int(zeile["grant_id"]))
        if grant is None or not _konto_darf(store, grant):
            return fehler("invalid_grant", "account not allowed")  # type: ignore[return-value]
        paar = store.issue_mcp_oauth_tokens(int(grant["id"]), access_ttl=ACCESS_TTL,
                                            refresh_ttl=REFRESH_TTL)
    elif grant_type == "refresh_token":
        grant, abgeloest = store.mcp_oauth_grant_by_refresh(refresh_token or "")
        if grant is None:
            if abgeloest is not None:
                store.revoke_mcp_oauth_grant(abgeloest)
                _log.warning("MCP-OAuth: abgelöstes Erneuerungs-Token benutzt, "
                             "Freigabe %s widerrufen", abgeloest)
            return fehler("invalid_grant", "unknown refresh_token")  # type: ignore[return-value]
        if client_id and client_id != grant["client_id"]:
            return fehler("invalid_grant", "client mismatch")  # type: ignore[return-value]
        if (grant["refresh_expires"] or "") < _iso(_jetzt()):
            store.revoke_mcp_oauth_grant(int(grant["id"]))
            return fehler("invalid_grant", "refresh_token expired")  # type: ignore[return-value]
        if not _konto_darf(store, grant):
            return fehler("invalid_grant", "account not allowed")  # type: ignore[return-value]
        paar = store.issue_mcp_oauth_tokens(int(grant["id"]), access_ttl=ACCESS_TTL,
                                            refresh_ttl=REFRESH_TTL,
                                            alter_refresh=refresh_token)
    else:
        return fehler("unsupported_grant_type",  # type: ignore[return-value]
                      "authorization_code or refresh_token")
    if paar is None:
        return fehler("invalid_grant", "grant gone")  # type: ignore[return-value]
    access, refresh = paar
    antwort: OAuthToken = {"access_token": access, "token_type": "Bearer",
                           "expires_in": int(ACCESS_TTL.total_seconds()),
                           "refresh_token": refresh, "scope": SCOPE}
    return JSONResponse(antwort, headers={"Cache-Control": "no-store",  # type: ignore[return-value]
                                          "Pragma": "no-cache"})


@router.post("/api/oauth/revoke")
def revoke(
    request: Request,
    token_value: str = Form("", alias="token"),
    store: Store = Depends(get_store),
) -> Ok:
    """RFC 7009: Ein Agent meldet sich ab. Antwortet immer 200 — ob es das
    Token gab, erfährt niemand."""
    _feature_an()
    _widerrufen.check(request)
    store.revoke_mcp_oauth_token(token_value)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Verbundene Agenten (Einstellungen)
# --------------------------------------------------------------------------- #

@router.get("/api/account/mcp-grants")
def list_grants(
    user: dict = Depends(require_mcp),
    store: Store = Depends(get_store),
) -> McpGrantList:
    """Die Agenten, die dieses Konto per OAuth verbunden hat."""
    _feature_an()
    store.purge_mcp_oauth()
    grants = cast(list[McpGrant], store.list_mcp_oauth_grants(user["id"]))
    return {"grants": grants, "max": store.MCP_GRANTS_MAX}


@router.delete("/api/account/mcp-grants/{grant_id}")
def delete_grant(
    grant_id: int,
    user: dict = Depends(require_mcp),
    store: Store = Depends(get_store),
) -> Ok:
    """Einen Agenten trennen — Zugangs- und Erneuerungs-Token gelten sofort nicht mehr."""
    _feature_an()
    if not store.revoke_mcp_oauth_grant(grant_id, owner_id=user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verbindung nicht gefunden.")
    return {"ok": True}
