"""Simple in-memory fixed-window rate limiter — no external deps."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_CLEANUP_INTERVAL = 300  # seconds between expired-entry sweeps


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def _key(self, request: Request) -> str:
        # Trust request.client.host — set to the real client IP by
        # ProxyHeadersMiddleware (which only trusts 127.0.0.1/::1).
        return request.client.host if request.client else "unknown"

    def _cleanup(self, now: float) -> None:
        """Evict expired buckets to prevent unbounded memory growth."""
        expired = [k for k, calls in self._calls.items() if not any(now - t < self.window for t in calls)]
        for k in expired:
            del self._calls[k]
        self._last_cleanup = now

    def check(self, request: Request, *, subject: str | int | None = None) -> None:
        """Count a request in a fixed-window bucket.

        Authenticated, expensive endpoints can pass a stable account id as
        ``subject``. Anonymous endpoints deliberately keep using the network
        address. Prefixes prevent an account id from ever sharing a bucket
        with an equal-looking IP address.
        """
        if os.environ.get("DISABLE_RATE_LIMIT") == "1":
            return
        key = f"account:{subject}" if subject is not None else f"ip:{self._key(request)}"
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup > _CLEANUP_INTERVAL:
                self._cleanup(now)
            calls = [t for t in self._calls[key] if now - t < self.window]
            if len(calls) >= self.max_calls:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Zu viele Anfragen. Bitte warte einen Moment.",
                    headers={"Retry-After": str(self.window)},
                )
            calls.append(now)
            self._calls[key] = calls


# Themen-Beschreibung (RL-U17): jeder Aufruf ist eine LLM-Anfrage. Großzügig
# genug fürs Ausprobieren beim Anlegen („neu generieren"), eng genug, dass
# niemand damit Kosten treiben kann.
topic_describe_limiter = RateLimiter(max_calls=20, window_seconds=300)
# Themen anlegen und ändern rechnen den Beschluss-Abgleich sofort mit — das
# sind rund 3 s Cross-Encoder auf der CPU je Aufruf, auf derselben Maschine,
# die die Website ausliefert. Ohne Bremse wären das die einzigen teuren
# Endpunkte ganz ohne eine; eine Anlege-Schleife legte damit die ganze Seite
# lahm. Zwölf in fünf Minuten ist weit mehr, als ein Mensch je braucht.
topic_match_limiter = RateLimiter(max_calls=12, window_seconds=300)
login_limiter = RateLimiter(max_calls=10, window_seconds=60)
register_limiter = RateLimiter(max_calls=5, window_seconds=300)
forgot_password_limiter = RateLimiter(max_calls=5, window_seconds=900)
verify_email_limiter = RateLimiter(max_calls=5, window_seconds=900)
# „Frag den Rat" ist der einzige Endpoint, der pro Aufruf LLM-Kosten erzeugt —
# großzügig genug für echtes Nachfragen, aber kein offener Geldhahn.
qa_limiter = RateLimiter(max_calls=10, window_seconds=600)
# Daumen-Feedback ist anonym beschreibbar — ohne Limit ließe sich die Tabelle
# (und mit ihr Backups + Off-Site-Mirror) per Skript um Gigabytes aufblähen.
# 20 pro 10 Minuten deckt jedes ehrliche Gespräch, auch mit Grund-Nachträgen.
qa_feedback_limiter = RateLimiter(max_calls=20, window_seconds=600)
partei_meinungen_limiter = RateLimiter(max_calls=15, window_seconds=600)
qa_share_limiter = RateLimiter(max_calls=10, window_seconds=600)
# Öffentliche Share-Links brauchen nach App-Store-Richtlinie 1.2 einen
# Meldeweg ohne Konto. Drei Meldungen in zehn Minuten reichen für einen
# Menschen; das enge Limit verhindert, dass Bots das Moderations-Postfach
# fluten oder fremde Shares automatisiert markieren.
qa_share_report_limiter = RateLimiter(max_calls=3, window_seconds=600)
# Das Kontaktformular auf /hilfe ist der einzige Schreib-Endpoint ganz ohne
# Konto — also der einzige, den ein Bot ohne Vorleistung findet. Eng wie
# „Passwort vergessen": Wer ehrlich schreibt, braucht keinen zweiten Versuch
# in derselben Viertelstunde; ein Skript kann so weder die Tabelle aufblähen
# noch unser Resend-Kontingent leerlaufen lassen.
support_limiter = RateLimiter(max_calls=5, window_seconds=900)
