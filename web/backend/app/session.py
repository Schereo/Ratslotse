"""Die Web-Sitzung: Cookie setzen und still verlängern.

Das Sitzungs-Cookie hielt einen Tag und wurde nie erneuert — wer die Seite
gestern benutzt hat, stand heute wieder vor dem Login. Instagram & Co. machen
es andersherum: lange Grundlaufzeit *plus* stille Verlängerung bei Nutzung.
Genau das steht hier.

Die Verlängerung läuft als Middleware und nicht in ``get_current_user``, weil
sie sonst nur auf den geschützten Endpunkten griffe. Wer eine Woche lang nur
öffentliche Beschluss-Seiten liest, soll seine Sitzung trotzdem behalten.

Widerruf bleibt davon unberührt: Das erneuerte Token trägt dieselbe
``token_version`` wie das alte, und die prüft ``deps.get_current_user`` bei
jedem Request gegen die Datenbank.
"""
from __future__ import annotations

from fastapi import Response
from starlette.requests import Request

from .config import get_settings
from .security import create_access_token, decode_access_token, token_lifetime_left

COOKIE_NAME = "access_token"


def set_session_cookie(response: Response, token: str) -> None:
    """Das Sitzungs-Cookie schreiben — eine Stelle für Login *und* Verlängerung."""
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


def _erneuertes_cookie(scope) -> list[tuple[bytes, bytes]] | None:  # noqa: ANN001 — ASGI-Scope
    """Der ``Set-Cookie``-Header für die Verlängerung — oder ``None``, wenn
    nichts zu tun ist (der Normalfall).

    Gebaut über ``set_session_cookie``, damit Laufzeit und Flags an genau einer
    Stelle stehen; aus der Wegwerf-Antwort wandert nur das Cookie mit, nicht
    ihre ``content-length``.
    """
    token = Request(scope).cookies.get(COOKIE_NAME)
    if not token:  # nicht angemeldet, oder die App mit ihrem Bearer-Token
        return None
    schwelle = get_settings().session_renew_within_minutes * 60
    if schwelle <= 0:  # Notausschalter: SESSION_RENEW_WITHIN_MINUTES=0
        return None
    rest = token_lifetime_left(token)
    if rest is None or rest > schwelle:  # abgelaufen/ungültig, oder noch reichlich Zeit
        return None
    decoded = decode_access_token(token)
    if decoded is None:  # nach dem Restlaufzeit-Test kaum möglich
        return None
    sub, ver = decoded
    traeger = Response()
    set_session_cookie(traeger, create_access_token(sub, ver))
    return [(k, v) for k, v in traeger.raw_headers if k == b"set-cookie"]


class SitzungsVerlaengerung:
    """Erneuert das Sitzungs-Cookie, sobald es in die zweite Hälfte seiner
    Laufzeit kommt.

    Das erneuerte Cookie hat wieder die volle Laufzeit, also fällt die nächste
    Erneuerung erst eine halbe Laufzeit später an — pro Nutzer:in ein
    ``Set-Cookie`` alle paar Wochen, nicht bei jedem Request.

    Bewusst rohes ASGI statt ``@app.middleware("http")``: Die KI-Frage liefert
    ihre Antwort als SSE-Strom, Token für Token. Ein ``BaseHTTPMiddleware``
    zöge diesen Strom durch einen zusätzlichen Task-Group-Umweg; hier wird nur
    die ``http.response.start``-Nachricht angefasst, der Körper fließt
    unberührt weiter.

    Zwei Fälle bleiben absichtlich aus:

    * **Die Antwort setzt schon selbst ein Cookie** — Login, Logout und
      Passwortwechsel haben über die Sitzung bereits entschieden; ein zweites
      ``Set-Cookie`` würde diese Entscheidung überschreiben (im Logout-Fall
      hieße das: der Ausloggen-Knopf wirkt nicht).
    * **401** — eine gerade zurückgewiesene Sitzung verlängert man nicht.
    """

    def __init__(self, app) -> None:  # noqa: ANN001 — ASGI-App
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001 — ASGI
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        frisch = _erneuertes_cookie(scope)
        if frisch is None:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message) -> None:  # noqa: ANN001 — ASGI-Nachricht
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                schon_gesetzt = any(k.lower() == b"set-cookie" for k, _ in headers)
                if message["status"] != 401 and not schon_gesetzt:
                    message = {**message, "headers": headers + frisch}
            await send(message)

        await self.app(scope, receive, send_wrapper)
