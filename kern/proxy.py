"""Ein Umweg für Ziele, die unsere Server-Adresse sperren.

**Wozu.** Das Geoportal der Stadt Oldenburg schließt Verbindungen aus dem
Hetzner-Adressbereich ohne Antwort — gemessen am 10.09.2026 von Prod, vom
Proxmox-Host und von zwei weiteren VMs, während dieselbe Abfrage vom
Notebook aus in 0,3 s antwortet. YouTube sperrt Rechenzentrums-Bereiche
seit langem; deshalb kommt die Ratssitzung heute über den O1-Livestream.
Beides trifft nicht *uns*, sondern jeden Hetzner-Kunden, und beides löst
sich, sobald die Anfrage von einem Privatanschluss kommt.

**Wie.** Ein SOCKS-Proxy auf Tims NAS, erreichbar nur über das Tailnet, und
zwei Umgebungsvariablen:

    RATSLOTSE_PROXY_URL=socks5h://nutzer:passwort@100.118.52.13:1080
    RATSLOTSE_PROXY_HOSTS=gisportal4ol.oldenburg.de,youtube.com

Nur die genannten Hosts (und ihre Subdomains) gehen den Umweg; alles andere
— OpenRouter, Resend, das Ratsinfo — bleibt direkt. Ohne die Variablen
passiert nichts, auch lokal nicht: Vom Notebook aus erreicht man die Ziele
ohnehin.

**Warum ``socks5h`` und nicht ``socks5``.** Mit dem ``h`` löst der Proxy den
Namen auf, nicht der Server. Sonst fragte der Server erst das Hetzner-DNS
und schickte dann eine Adresse durch den Tunnel — für ein Ziel, das nach
Herkunft sperrt, ist das gleichgültig, für eines mit Geo-DNS nicht.

**Was hier NICHT passiert.** Kein Rückfall auf „direkt", wenn der Proxy
nicht antwortet. Ein Ziel, das die Server-Adresse sperrt, scheitert direkt
ohnehin — und ein stiller Rückfall sähe aus wie „der Umweg geht", bis
jemand die Zahlen vermisst. Der Fehler soll laut bleiben.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

URL_ENV = "RATSLOTSE_PROXY_URL"
HOSTS_ENV = "RATSLOTSE_PROXY_HOSTS"


def proxied_hosts() -> tuple[str, ...]:
    """Die Hosts aus ``RATSLOTSE_PROXY_HOSTS`` — klein, ohne Leerraum, ohne Leere."""
    raw = os.environ.get(HOSTS_ENV, "")
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


def uses_proxy(host_or_url: str) -> bool:
    """Ob dieser Host (oder die URL dazu) den Umweg nimmt.

    Subdomains zählen mit: ``www.youtube.com`` fällt unter ``youtube.com``.
    ``notyoutube.com`` nicht — verglichen wird am Punkt, nicht am Textende."""
    host = _host(host_or_url)
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in proxied_hosts())


def proxy_for(host_or_url: str) -> str | None:
    """Die Proxy-URL für dieses Ziel — oder None, wenn es direkt geht."""
    url = os.environ.get(URL_ENV, "").strip()
    if not url or not uses_proxy(host_or_url):
        return None
    return url


def proxies_for(host_or_url: str) -> dict[str, str]:
    """Das ``proxies``-Argument für ``requests`` — leer heißt direkt.

    Leer statt None, damit die Aufrufstelle es ohne Fallunterscheidung
    durchreichen kann: ``session.get(url, proxies=proxies_for(url))``."""
    url = proxy_for(host_or_url)
    if not url:
        return {}
    return {"http": url, "https": url}


def _host(value: str) -> str:
    value = value.strip().lower()
    if "://" in value:
        return (urlsplit(value).hostname or "").lower()
    return value.split("/", 1)[0]
