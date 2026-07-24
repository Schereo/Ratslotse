"""Shared test setup — keep the suite from ever touching external services.

The registration flow emails the admin via Resend. With a real ``RESEND_API_KEY``
in the developer's ``.env``, running the suite would send real mail to the test
admin address (``admin@test.de``) and burn the Resend quota. Forcing the key empty
here — before any app/config import — makes ``send_email()`` short-circuit to a
no-op in tests. Imported by pytest before test modules, so it wins over ``.env``.

Seit Design 26a gilt dasselbe für den LLM-Schlüssel: Die Themen-Vorschläge
prüfen jeden neuen Kandidaten einmal auf Vagheit, und dieser Aufruf steckt jetzt
in einem *Web-Endpunkt* statt nur in Cron-Jobs. Mit einem echten
``OPENROUTER_API_KEY`` in der ``.env`` würde die Suite dabei Geld ausgeben und
je nach Modell-Laune wackeln. Leer erzwungen schlägt der Aufruf sofort fehl und
die Aufrufer nehmen ihren Fallback — genau der Pfad, den Produktion bei einer
LLM-Störung auch geht. Tests, die eine Modellantwort brauchen, mocken sie.
"""
import os

os.environ["RESEND_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
