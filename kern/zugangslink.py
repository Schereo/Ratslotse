"""Anmeldelinks in Mails — wer auf „Mein Viertel ausprobieren“ tippt, landet
angemeldet dort, statt erst sein Passwort zu suchen.

**Was hier entsteht.** Je Empfänger*in ein eigenes Token, angehängt an jeden
Link der Mail auf die eigene Domäne (``?ml=…``). Die Anmeldeseite löst es per
Klick ein (``POST /api/auth/magic``); abgelaufen oder widerrufen, zeigt sie
das gewöhnliche Formular mit ``weiter=`` zum selben Ziel.

**Warum es so eng gebaut ist** (Tims Wunsch 08.11.2026, mit den Bedenken dazu):

* **Zehn Tage**, dann wertlos (``TAGE``).
* **Widerrufbar:** Das Token trägt ``token_version``; Abmelden überall,
  Passwortwechsel und Sperre machen jeden offenen Link ungültig.
* **Nie selbst eine Sitzung:** Es trägt ``zweck: magic``, und das Backend
  weist jedes Token mit Zweck als Sitzung ab (``app.security``).
* **Einlösen nur per Klick:** Mail-Scanner öffnen Links vorab; ein Aufruf
  allein meldet niemanden an.
* **Eingeschränkte Sitzung:** Wer über einen Link kommt, darf lesen, fragen
  und einstellen, aber weder Passwort noch Adresse ändern, das Konto löschen,
  Schlüssel für fremde Agenten ausstellen noch ins Admin-Panel
  (``deps.require_volle_anmeldung``) — eine weitergeleitete Mail soll kein
  Konto übergeben.

**Warum das Token hier entsteht und nicht in ``app.security``:** ``kern``
importiert aus keiner höheren Schicht (``tests/test_schichten.py``), die
Zustellung läuft aber hier. Die Formel ist dieselbe (HS256 mit
``WEB_JWT_SECRET``); ``tests/test_zugangslink.py`` hält fest, dass das Backend
jedes hier gebaute Token annimmt und keins davon als Sitzung gilt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time

from kern import features
from kern.mail_links import _HREF

#: Der Parameter im Link. Kurz, damit die Adresse in der Mail nicht ausufert.
PARAM = "ml"
#: Gültigkeit in Tagen — gleich ``app.security.MAGIC_TAGE``.
TAGE = 10
#: Der Feature-Schalter (``kern/features.py``).
SCHALTER = "zugangslinks"
#: Die Anlässe, deren Mails Anmeldelinks tragen. Bewusst zuerst nur die seltene
#: Release-Ankündigung (und ihre Probe): Eine tägliche Themen-Mail mit einem
#: Link, der zehn Tage anmeldet, läge in sehr vielen Postfächern gleichzeitig.
ANLAESSE = frozenset({"n7_news", "probe"})


def _b64(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode()


def token(owner_id: int, token_version: int, *, tage: int = TAGE,
          geheimnis: str | None = None, jetzt: float | None = None) -> str | None:
    """Ein Anmeldelink-Token — ``None`` ohne ``WEB_JWT_SECRET``."""
    geheimnis = geheimnis if geheimnis is not None else os.environ.get("WEB_JWT_SECRET", "")
    if not geheimnis:
        return None
    kopf = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    nutzlast = _b64(json.dumps({"sub": str(owner_id),
                                "exp": int(jetzt if jetzt is not None else time.time()) + tage * 86400,
                                "ver": int(token_version), "zweck": "magic"}).encode())
    signatur = _b64(hmac.new(geheimnis.encode(), f"{kopf}.{nutzlast}".encode(),
                             hashlib.sha256).digest())
    return f"{kopf}.{nutzlast}.{signatur}"


def link_mit_zugang(url: str, tok: str, basis: str) -> str:
    """Den Parameter an einen eigenen Link hängen (fremde bleiben unberührt)."""
    ziel = (url or "").strip()
    if not ziel or not basis or not ziel.startswith(basis) or re.search(rf"[?&]{PARAM}=", ziel):
        return url
    rest, _, fragment = ziel.partition("#")
    rest += ("&" if "?" in rest else "?") + f"{PARAM}={tok}"
    return rest + (f"#{fragment}" if fragment else "")


def einsetzen(html: str, tok: str | None, basis: str) -> str:
    """Alle eigenen Links einer fertigen Mail mit dem Token versehen."""
    if not tok or not html:
        return html
    return _HREF.sub(lambda m: f"href={m.group(1)}{link_mit_zugang(m.group(2), tok, basis)}{m.group(1)}",
                     html)


def fuer_mail(store, owner_id: int | None, anlass: str | None, html: str, basis: str) -> str:
    """Die fertige Mail eines Kontos — mit Anmeldelinks, wo sie hingehören.

    Ohne Schalter, ohne passenden Anlass, ohne Konto oder ohne Store: die Mail
    unverändert. Ein Fehler hier darf die Zustellung nie aufhalten.
    """
    if anlass not in ANLAESSE or not owner_id or store is None or not features.an("zugangslinks"):
        return html
    try:
        zeile = store._conn.execute(  # noqa: SLF001
            "SELECT token_version FROM web_users WHERE id = ? AND status = 'active'",
            (owner_id,)).fetchone()
    except Exception:  # noqa: BLE001
        return html
    if not zeile:
        return html
    return einsetzen(html, token(owner_id, int(zeile[0] or 0)), basis)
