"""Womit greift jemand zu — Browser oder App?

Die Clients weisen sich über den Header ``X-Client`` aus. Der Header ist alt;
neu ist nur, dass er jetzt **auch** die Plattform trägt und nicht mehr bloß
„native ja/nein" beantwortet:

======================  ===================  ==================================
Client                  ``X-Client``         Ergebnis
======================  ===================  ==================================
Browser                 (kein Header)        ``web``
Native iOS-App          ``ios``              ``ios``
Capacitor-Android        ``android``          ``android``
Ältere App-Stände       ``app``              ``app``
======================  ===================  ==================================

``app`` bleibt gültig und bleibt „nativ": Im Feld laufen TestFlight-Builds, die
den alten Wert schicken, und die dürfen sich durch ein Update des Servers nicht
plötzlich wie ein Browser verhalten — an der Unterscheidung hängt, ob die
Anmeldung ein Bearer-Token in den Rumpf legt oder nur ein Cookie setzt.

Der Header kommt vom Client und ist damit fälschbar. Das ist hier bewusst
hingenommen: Er steuert keine Rechte, sondern nur die Zustellform des Tokens
(die Anmeldung selbst prüft weiter das Passwort) und eine Nutzungsstatistik.
Deshalb wird auch streng auf eine kurze Liste abgebildet, statt Fremdwerte
durchzureichen — sonst schriebe ein beliebiger Aufrufer beliebige Zeichenketten
in die Statistiktabelle.
"""
from __future__ import annotations

from fastapi import Request

#: Werte, die ein Client von sich behaupten darf. Alles andere wird ``web``.
NATIVE_CLIENTS = frozenset({"ios", "android", "app"})

#: Alle Werte, die in ``user_activity.client`` und ``web_users.signup_client``
#: vorkommen dürfen. ``unknown`` trägt, was vor dieser Messung entstanden ist.
KNOWN_CLIENTS = frozenset({"web", "unknown"}) | NATIVE_CLIENTS


def client_kind(request: Request) -> str:
    """``web`` | ``ios`` | ``android`` | ``app`` — nie etwas anderes."""
    value = request.headers.get("X-Client", "").strip().lower()
    return value if value in NATIVE_CLIENTS else "web"


def is_app_client(request: Request) -> bool:
    """Kommt der Request aus einer nativen Hülle (statt aus dem Browser)?"""
    return client_kind(request) in NATIVE_CLIENTS
