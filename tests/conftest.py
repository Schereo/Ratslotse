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
import tempfile
from pathlib import Path

import pytest

os.environ["RESEND_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

# --- Wegwerf-Datenbanken: ein Satz Pfade je Prozess -------------------------
# Bis 09/2026 verabredete jedes Backend-Testmodul seine Datenbank selbst:
#
#     _TMP = tempfile.mkdtemp()
#     os.environ.setdefault("COUNCIL_DB", str(Path(_TMP) / "council.sqlite"))
#
# `setdefault` heißt „nimm, was schon da ist". Welche Datei am Ende galt, hing
# damit an der Import-Reihenfolge — seriell trug das, weil pytest die Module in
# fester Reihenfolge importiert. Unter `pytest -n auto` importiert jeder Worker
# eine ANDERE Teilmenge in anderer Reihenfolge; ein Modul schrieb seine Zeilen
# dann in eine andere Datei, als die App las. Gemessen am 07.09.2026 fiel
# `test_stadtquellen.py::test_tafel_traegt_sperrungen_und_presse` daran um,
# reproduzierbar und auch mit `--dist loadfile`.
#
# Erschwerend: `web/backend/app/main.py` ruft `get_settings()` schon beim
# Import, und `get_settings` ist `lru_cache`. Die Bindung an die Datei passiert
# also EINMAL je Prozess — ein Modul, das die Variable danach umsetzt, ändert
# nur seine eigene Sicht, nicht die der App. Genau das taten die Module, die
# statt `setdefault` hart zuwiesen.
#
# Deshalb steht die Verabredung hier: conftest.py wird vor jedem Testmodul
# importiert, das Verzeichnis ist je Prozess (und damit je xdist-Worker)
# eindeutig, und kein Testmodul setzt die Variablen mehr selbst. Wer eine
# eigene Datenbank je Test braucht, legt sie unter `tmp_path` an und hängt sie
# über `app.dependency_overrides` ein — nicht über die Umgebung.
_TMP = Path(tempfile.mkdtemp(prefix="ratslotse-tests-"))
RATSLOTSE_DB = str(_TMP / "ratslotse.sqlite")
COUNCIL_DB = str(_TMP / "council.sqlite")

os.environ["RATSLOTSE_DB"] = RATSLOTSE_DB
os.environ["COUNCIL_DB"] = COUNCIL_DB
# Der Verlauf des Wahlabends gehört in den tmp-Ordner, nie nach data/.
os.environ["WAHLABEND_HISTORY_FILE"] = str(_TMP / "wahlabend-verlauf.json")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["WEB_ADMIN_EMAIL"] = "admin@test.de"
os.environ["COOKIE_SECURE"] = "false"   # TestClient spricht http://testserver
os.environ["DISABLE_RATE_LIMIT"] = "1"  # sonst blutet der Zähler über Tests

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
def source():
    """Eine kurze :class:`council.herkunft.Herkunft` für Speicher-Tests.

    Die Finanz-``save_*``-Methoden verlangen seit 08/2026 eine Herkunft statt
    loser Label/URL-Strings — Tests, die nur das Speichern prüfen, sollen
    deswegen nicht jedes Mal sieben Felder ausschreiben. Wo die Herkunft
    selbst zur Sache gehört, wird sie im Test direkt gebaut."""
    from council.herkunft import Herkunft

    def bauen(label: str = "Testdokument", url: str | None = "https://example.org/d.pdf",
              probe: str = "structure_check", **rest):
        return Herkunft(kind="ris", probe=probe, label=label, url=url, **rest)

    return bauen
