"""HTTP zu den Ratsinformationssystemen — gedrosselt, kenntlich, mit Rohablage.

Jede Antwort landet unverändert in ``raw_objects``, bevor irgendjemand sie
interpretiert. Das ist der Grund, warum eine bessere Auswertung später keinen
erneuten Abruf bei fünf Städten braucht.

**Eine Anfrage je Sekunde und Host**, mit Kennung und Kontaktadresse im
User-Agent. Die Systeme gehören Städten, nicht uns; ein Lauf, der nachts eine
Stunde braucht, ist billiger als ein gesperrter Zugang.

**Single-threaded je Prozess.** Parallel läuft nur die Ernte über Städte
hinweg — je Stadt ein Prozess und eine eigene Rohdatei. Fünf Threads auf einer
SQLite-Datei haben im Probelauf einen Faden still sterben lassen.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests

from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.oparl")

USER_AGENT = ("Ratslotse/1.0 (+https://ratslotse.de; Kontakt siehe Impressum) "
              "Staedtevergleich kommunaler Ratsbeschluesse")
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

#: Mindestabstand zwischen zwei Anfragen an denselben Host. Eine Sekunde ist
#: die Vorgabe und bleibt es für den Cron. Ein Bestandslauf über Tausende
#: Seiten darf enger fahren — ``CITIES_RATE_SECONDS`` setzt das für einen
#: Lauf, nach unten begrenzt auf 0,2 s, damit ein Tippfehler in der Umgebung
#: kein fremdes Ratsinformationssystem umwirft.
RATE_SECONDS = max(0.2, float(os.environ.get("CITIES_RATE_SECONDS") or 1.0))
TIMEOUT_JSON = 60
TIMEOUT_FILE = 120

_locks: dict[str, tuple[threading.Lock, list[float]]] = {}
_locks_guard = threading.Lock()


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else url


def throttle(url: str, gap: float = RATE_SECONDS) -> None:
    """Wartet, bis der Mindestabstand zu diesem Host eingehalten ist."""
    host = _host(url)
    with _locks_guard:
        eintrag = _locks.setdefault(host, (threading.Lock(), [0.0]))
    lock, last = eintrag
    with lock:
        rest = gap - (time.monotonic() - last[0])
        if rest > 0:
            time.sleep(rest)
        last[0] = time.monotonic()


class OParlClient:
    """Abrufe für **eine** Stadt, mit Rohablage und Dateispeicher."""

    def __init__(self, raw: CitiesStore, body_id: str, files_dir: str | Path,
                 session: requests.Session | None = None):
        self.raw = raw
        self.body_id = body_id
        self.files_dir = Path(files_dir)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.requests_made = 0

    # ------------------------------------------------------------------ JSON

    def get_json(self, url: str, params: dict | None = None, kind: str = "list_page",
                 store_as: str | None = None, tries: int = 3) -> dict:
        """GET mit Drosselung und Wiederholung; legt die Antwort roh ab.

        Wiederholt wird nur, was vorübergehend sein kann (5xx, Zeitüberschreitung,
        Verbindungsabbruch). Ein 4xx ist eine Aussage des Servers — den zu
        wiederholen kostet nur Zeit.
        """
        letzte: Exception | None = None
        for versuch in range(tries):
            throttle(url)
            try:
                r = self.session.get(url, params=params, headers=HEADERS, timeout=TIMEOUT_JSON)
                self.requests_made += 1
                if 400 <= r.status_code < 500:
                    r.raise_for_status()
                r.raise_for_status()
                daten = r.json()
                break
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if 400 <= status < 500:
                    raise
                letzte = e
            except (requests.ConnectionError, requests.Timeout, ValueError) as e:
                letzte = e
            if versuch < tries - 1:
                time.sleep(2 * (versuch + 1))
        else:
            raise letzte or RuntimeError(f"kein Ergebnis für {url}")

        self.raw.put_raw_object(self.body_id, kind, store_as or daten.get("id") or r.url, daten)
        return daten

    def get_text(self, url: str, headers: dict | None = None,
                 tries: int = 3) -> str:
        """GET einer HTML-Seite — für die Adapter, die keine Schnittstelle haben.

        Dieselbe Drosselung und dieselbe Wiederholungsregel wie ``get_json``;
        nur wird nichts abgelegt, denn was roh gespeichert wird, entscheidet
        der Adapter (er legt die Seite mit seiner eigenen Kennung ab).

        **Die Kodierung kommt aus dem Dokument, nicht aus dem Kopf.** ALLRIS
        classic liefert ISO-8859-1 und sagt es im Meta-Tag statt im
        ``Content-Type``; wer sich auf den Kopf verlässt, bekommt „Ausschuß"
        als „AusschuÃŸ" — und merkt es erst, wenn ein Titel nicht mehr
        zusammenpasst.
        """
        kopf = {**HEADERS, "Accept": "text/html,application/xhtml+xml"}
        kopf.update(headers or {})
        letzte: Exception | None = None
        for versuch in range(tries):
            throttle(url)
            try:
                r = self.session.get(url, headers=kopf, timeout=TIMEOUT_JSON)
                self.requests_made += 1
                r.raise_for_status()
                if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1"):
                    r.encoding = r.apparent_encoding or r.encoding
                return r.text
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if 400 <= status < 500:
                    raise
                letzte = e
            except (requests.ConnectionError, requests.Timeout) as e:
                letzte = e
            if versuch < tries - 1:
                time.sleep(2 * (versuch + 1))
        raise letzte or RuntimeError(f"kein Ergebnis für {url}")

    # --------------------------------------------------------------- Dateien

    def get_file(self, url: str, tries: int = 2) -> tuple[bytes, str] | None:
        """``(bytes, mime)`` — oder ``None``, wenn der Server sie nicht hergibt.

        Ein 404 auf eine Datei ist kein Grund, den Lauf abzubrechen: Magdeburgs
        Schnittstelle nennt Adressen, die es nicht gibt, und andere Städte
        entfernen Anlagen nachträglich.

        **Und eine kaputte Adresse erst recht nicht.** Am 10.09.2026 stand in
        einer Wolfsburger Vorlage statt eines Dokumentlinks ein lokaler
        Windows-Pfad (``file:///C:\…``) — jemand hat beim Einpflegen das
        falsche Feld kopiert. ``requests`` wirft dafür ``InvalidSchema``, und
        das ist **keine** der drei Ausnahmen unten: Der Fehler ging durch,
        und mit ihm der ganze Dateiabruf der Stadt. 4.793 Dateien, davon
        369 Niederschriften, wurden wegen einer einzigen Zeile nicht geholt.
        Deshalb wird das Schema vorab geprüft (ein anderes wird nie gut, ein
        erneuter Versuch also sinnlos) und unten auf ``RequestException``
        gefangen — eine Datei darf niemals eine Stadt kosten.
        """
        if not url.lower().startswith(("http://", "https://")):
            logger.info("Datei-Adresse ist keine Netzadresse: %s", url[:60])
            return None
        for versuch in range(tries):
            throttle(url)
            try:
                r = self.session.get(url, headers={"User-Agent": USER_AGENT},
                                     timeout=TIMEOUT_FILE, allow_redirects=True)
                self.requests_made += 1
                if 400 <= r.status_code < 500:
                    logger.info("Datei nicht abrufbar (%s): %s", r.status_code, url)
                    return None
                r.raise_for_status()
                mime = (r.headers.get("content-type") or "").split(";")[0].strip()
                # **Eine Webseite ist nie das Dokument.** ALLRIS antwortet für
                # die Anlage einer nichtöffentlichen Vorlage mit HTTP 200 und
                # der Seite „Keine Information verfügbar" — kein Fehler, kein
                # 403, nur HTML statt PDF. Gemessen an Wolfsburg: **444 von
                # 1.798**. Ungeprüft landen sie als ``.pdf`` im Dateispeicher,
                # und die Textstufe meldet bei jedem Lauf aufs Neue „invalid
                # pdf header" — 444 Fehler, die wie ein Parserproblem aussehen
                # und in Wahrheit eine Zugangsbeschränkung sind.
                kopf = r.content[:64].lstrip().lower()
                if mime.startswith("text/html") or kopf.startswith(
                        (b"<!doctype", b"<html")):
                    logger.info("Dokument-Adresse liefert eine Webseite: %s", url)
                    return None
                return r.content, mime
            except requests.RequestException as e:
                if versuch == tries - 1:
                    logger.info("Datei-Abruf gescheitert: %s (%s)", url, type(e).__name__)
                    return None
                time.sleep(2 * (versuch + 1))
        return None

    def store_file(self, data: bytes, mime: str | None) -> str:
        """Bytes nach Inhalt ablegen; gibt den SHA-256 zurück.

        Nach Inhalt adressiert, weil dieselbe Anlage an mehreren Vorlagen
        hängen kann und weil die Textextraktion später eine andere sein wird —
        ohne die Bytes wäre jede Verbesserung ein erneuter Abruf bei allen
        Städten.
        """
        sha = hashlib.sha256(data).hexdigest()
        ziel = self.files_dir / sha[:2] / f"{sha}.pdf"
        if not ziel.exists():
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(data)
        self.raw.put_raw_file(sha, len(data), mime, str(ziel.relative_to(self.files_dir)))
        return sha

    def read_file(self, sha256: str) -> bytes | None:
        pfad = self.files_dir / sha256[:2] / f"{sha256}.pdf"
        return pfad.read_bytes() if pfad.exists() else None


def file_path(files_dir: str | Path, sha256: str) -> Path:
    return Path(files_dir) / sha256[:2] / f"{sha256}.pdf"


def as_list(value: Any) -> list:
    """OParl-Verweise sind mal ein Wert, mal eine Liste, mal nichts."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
