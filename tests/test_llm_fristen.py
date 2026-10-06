"""Fristen der Modellaufrufe: Wie oft und wie lange wartet ein Aufruf auf einen stummen Anbieter?

**Der Befund (Review 05.10.2026).** Der Client wurde ohne ``max_retries`` und
ohne ``timeout`` gebaut. Das SDK wiederholte deshalb selbst zweimal je Anlauf —
zusätzlich zu den vier Anläufen von tenacity —, und ohne Frist wartete jeder
dieser Versuche 600 s. ``chat_complete(timeout=1)`` öffnete gegen einen
stummen Server 15 Verbindungen und brauchte 30 s.

Die Tests hier stellen einen echten Server auf, der Verbindungen annimmt und
nie antwortet, und zählen, wie oft der Client anklopft und wie lange es dauert.
Kein Mock des SDK: Gerade dessen eigene Wiederholungen waren der Fehler.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest

from kern import llm


class _StummerServer:
    """Nimmt Verbindungen an, liest, antwortet nie. Zählt die Verbindungen."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(32)
        self.port = self.sock.getsockname()[1]
        self.verbindungen = 0
        self.offen: list[socket.socket] = []
        self._aus = threading.Event()
        self._faden = threading.Thread(target=self._annehmen, daemon=True)
        self._faden.start()

    def _annehmen(self) -> None:
        self.sock.settimeout(0.1)
        while not self._aus.is_set():
            try:
                conn, _ = self.sock.accept()
            except (TimeoutError, OSError):
                continue
            self.verbindungen += 1
            self.offen.append(conn)  # offen halten, nie antworten

    def schliessen(self) -> None:
        self._aus.set()
        for c in self.offen:
            try:
                c.close()
            except OSError:
                pass
        self.sock.close()


@pytest.fixture
def stumm(monkeypatch):
    server = _StummerServer()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(llm, "OPENROUTER_BASE_URL", f"http://127.0.0.1:{server.port}/api/v1")
    gespeichert = llm._client
    llm._client = None
    yield server
    llm._client = gespeichert
    server.schliessen()


def test_client_wiederholt_nicht_selbst(monkeypatch):
    """Die Wiederholungen macht tenacity — das SDK darf keine eigenen dazutun."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    gespeichert = llm._client
    llm._client = None
    try:
        client = llm.get_client()
        assert client.max_retries == 0
        assert client.timeout.read == llm.STANDARD_FRIST_S
        assert client.timeout.connect == llm.VERBINDUNGS_FRIST_S
    finally:
        llm._client = gespeichert


def test_ein_anlauf_ist_eine_verbindung(stumm):
    """Ohne tenacity: genau EINE Verbindung, genau eine Frist lang."""
    from openai import APITimeoutError

    t0 = time.monotonic()
    with pytest.raises(APITimeoutError):
        llm.get_client().chat.completions.create(
            model="x", messages=[{"role": "user", "content": "hi"}], timeout=0.5)
    dauer = time.monotonic() - t0
    time.sleep(0.2)
    assert stumm.verbindungen == 1
    # Eine Frist von 0,5 s; der Rest ist Luft für eine volle Maschine (die
    # Suite läuft parallel). Vorher wären es drei Verbindungen gewesen.
    assert dauer < 4


def test_chat_complete_mit_frist_ist_gedeckelt(stumm):
    """Mit Frist: höchstens zwei Fristen lang Anläufe, nicht vier (und nicht 15).

    0,5 s Frist → Anlauf 1 (0,5 s), Pause 2 s, Anlauf 2 (0,5 s), dann ist die
    Gesamtgrenze von zwei Fristen überschritten. Vorher: 15 Verbindungen.
    """
    from openai import APITimeoutError

    t0 = time.monotonic()
    with pytest.raises(APITimeoutError):
        llm.chat_complete(model="x", messages=[{"role": "user", "content": "hi"}], timeout=0.5)
    dauer = time.monotonic() - t0
    time.sleep(0.2)
    assert stumm.verbindungen == 2, stumm.verbindungen
    assert dauer < 6, dauer


def test_strom_mit_frist_ist_gedeckelt(stumm):
    """Derselbe Deckel für den Strom (Frag den Rat, Recherche)."""
    from openai import APITimeoutError

    t0 = time.monotonic()
    with pytest.raises(APITimeoutError):
        list(llm.chat_stream(model="x", messages=[{"role": "user", "content": "hi"}],
                             timeout=0.5))
    dauer = time.monotonic() - t0
    time.sleep(0.2)
    assert stumm.verbindungen == 2, stumm.verbindungen
    assert dauer < 6, dauer


def test_frist_aus_httpx_timeout():
    import httpx

    assert llm._frist_von({"timeout": 30}) == 30.0
    assert llm._frist_von({"timeout": httpx.Timeout(12, connect=3)}) == 12.0
    assert llm._frist_von({}) is None
    assert llm._frist_von({"timeout": None}) is None
