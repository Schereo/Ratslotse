"""Wächter für den Heim-Proxy (`kern/proxy.py`).

**Wogegen das steht.** Der Umweg greift nur für die Hosts aus
``RATSLOTSE_PROXY_HOSTS``. Zwei Fehler wären lautlos: ein zu weiter Treffer
(``notyoutube.com`` fiele unter ``youtube.com``, und plötzlich liefe fremder
Verkehr durch Tims Wohnzimmer) und ein zu enger (``www.youtube.com`` fiele
NICHT unter ``youtube.com``, und der Abruf scheiterte weiter an der Sperre —
mit derselben Meldung wie vorher, als gäbe es den Proxy nicht).
"""
from __future__ import annotations

import pytest

from kern import proxy


@pytest.fixture
def umweg(monkeypatch):
    monkeypatch.setenv(proxy.URL_ENV, "socks5h://u:p@100.118.52.13:1080")
    monkeypatch.setenv(proxy.HOSTS_ENV, " gisportal4ol.oldenburg.de, YouTube.com ,,")


def test_ohne_variablen_geht_alles_direkt(monkeypatch):
    monkeypatch.delenv(proxy.URL_ENV, raising=False)
    monkeypatch.delenv(proxy.HOSTS_ENV, raising=False)
    assert proxy.proxies_for("https://gisportal4ol.oldenburg.de/x") == {}
    assert proxy.proxy_for("youtube.com") is None


def test_nur_die_genannten_hosts_und_ihre_subdomains(umweg):
    assert proxy.uses_proxy("https://gisportal4ol.oldenburg.de/server/rest?f=json")
    assert proxy.uses_proxy("https://www.youtube.com/watch?v=1")
    assert proxy.uses_proxy("YOUTUBE.COM")
    assert not proxy.uses_proxy("https://notyoutube.com/")
    assert not proxy.uses_proxy("https://openrouter.ai/api")
    assert not proxy.uses_proxy("")


def test_requests_bekommt_beide_schemata(umweg):
    assert proxy.proxies_for("https://www.youtube.com/") == {
        "http": "socks5h://u:p@100.118.52.13:1080",
        "https": "socks5h://u:p@100.118.52.13:1080",
    }
    assert proxy.proxies_for("https://openrouter.ai/") == {}


def test_url_ohne_hosts_wirkt_nicht(monkeypatch):
    monkeypatch.setenv(proxy.URL_ENV, "socks5h://u:p@100.118.52.13:1080")
    monkeypatch.delenv(proxy.HOSTS_ENV, raising=False)
    assert proxy.proxy_for("https://www.youtube.com/") is None
