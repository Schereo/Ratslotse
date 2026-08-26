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

import pytest

os.environ["RESEND_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

# Und dann liest die .env doch jemand ein. Fast jedes Skript ruft beim Import
# `load_dotenv(ROOT / ".env")`; das überschreibt zwar nichts, was oben schon
# leer gesetzt wurde — aber ein Test, der einen Schlüssel per
# `monkeypatch.delenv` ENTFERNT, macht den Platz wieder frei, und der nächste
# Modul-Import füllt ihn aus der Entwickler-.env mit einem ECHTEN Wert. Genau
# so verschickte `tests/test_remind_setup.py` lokal echte Mail an eine
# erfundene Adresse (in CI fiel es nie auf: dort gibt es keine .env).
# Deshalb liest die Suite die .env grundsätzlich nicht.
try:
    import dotenv

    dotenv.load_dotenv = lambda *a, **k: False
except ImportError:  # dotenv ist nur eine Laufzeit-Abhängigkeit der Skripte
    pass


@pytest.fixture
def quelle():
    """Eine kurze :class:`council.herkunft.Herkunft` für Speicher-Tests.

    Die Finanz-``save_*``-Methoden verlangen seit 08/2026 eine Herkunft statt
    loser Label/URL-Strings — Tests, die nur das Speichern prüfen, sollen
    deswegen nicht jedes Mal sieben Felder ausschreiben. Wo die Herkunft
    selbst zur Sache gehört, wird sie im Test direkt gebaut."""
    from council.herkunft import Herkunft

    def bauen(label: str = "Testdokument", url: str | None = "https://example.org/d.pdf",
              probe: str = "strukturprobe", **rest):
        return Herkunft(art="ris", probe=probe, label=label, url=url, **rest)

    return bauen
