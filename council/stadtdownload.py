"""Dokumente von oldenburg.de holen — die Netzseite der Finanzschichten.

Der Haushalts-Bereich hatte bis 08/2026 genau **einen** Cron, und der lud
nichts herunter: ``check_finanzdaten`` liest aus, was der Protokoll-Scraper
ohnehin geholt hat, und seine Regel 1 lautet „Er lädt nichts herunter. Zwei
Wege zu denselben Daten wären ein Weg zu viel."

Diese Regel bleibt. Sie gilt für Dokumente, die **im Ratsinformationssystem
stehen** — dort holt sie der Scraper, und ein zweiter Weg wäre Doppelarbeit
mit doppelter Fehlerquelle.

Der Beteiligungsbericht steht dort nicht. Er liegt auf oldenburg.de, und wer
ihn haben will, muss ihn holen. Das ist eine andere Sorte Arbeit: Sie fasst
ein fremdes System an, sie kann von außen scheitern, und sie hat sich zu
benehmen. Deshalb ein eigenes Modul und ein eigener Cron
(``scripts/check_beteiligungsbericht.py``) statt eines Anbaus an den
bestehenden.

Wie sich dieser Abruf benimmt
------------------------------
**Er sagt, wer er ist.** :data:`USER_AGENT` nennt Namen, Adresse und Zweck.
Ein „Mozilla/5.0" wäre eine Behauptung, die niemandem hilft — am wenigsten
der Stelle, die wissen will, wer da alle vier Wochen sieben PDFs zieht.

**Er fragt erst, ob es sich lohnt.** Jeder Abruf schickt den Zeitstempel des
Standes mit, den wir schon haben (``If-Modified-Since``, ``If-None-Match``).
Ist das Dokument unverändert, antwortet der Server mit ``304`` und ohne
Inhalt. Sieben Berichte sind zusammen 25 MB; sie alle vier Wochen erneut zu
ziehen, weil sich vielleicht einer geändert hat, wäre Verschwendung auf Kosten
eines fremden Servers.

**Er wartet zwischen den Abrufen** (:data:`PAUSE`) und nimmt nur, was er
erwartet: Ein Dokument muss als PDF ausgeliefert werden und darf
:data:`MAX_BYTES` nicht überschreiten. Beides ist Selbstschutz — eine
Fehlerseite mit ``200 OK`` ist der Normalfall bei CMS-Systemen, und ein Parser,
der HTML für ein PDF hält, meldet danach kluge Dinge über Unsinn.

**Er hält die Regeln der Seite ein.** ``https://www.oldenburg.de/robots.txt``
erlaubt ``User-agent: *`` mit ``Allow: /``; gesperrt sind TYPO3-Innereien
(``/typo3``, ``/uploads``) und Adressen mit ``cHash``-Parameter. Die
Berichts-PDFs liegen unter ``/fileadmin/oldenburg/…`` und sind damit
ausdrücklich frei. Nachgesehen am 16.08.2026 — wer diesen Pfad ändert, sieht
bitte erneut nach.

Was hier **nicht** hingehört
-----------------------------
Das Lesen. Dieses Modul liefert Bytes und sagt, woher sie kamen und wann sie
zuletzt geändert wurden; was drinsteht, entscheidet
``council/beteiligungsbericht.py``. Die Trennung ist der Grund, warum sich der
Parser ohne Netz testen lässt.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger("council.stadtdownload")

BASE = "https://www.oldenburg.de"

#: Wer da klopft. Mit Zweck und Rückadresse — dieselbe Bauart wie in
#: ``scripts/geocode_entities.py``, wo die Nominatim-Nutzungsbedingungen sie
#: ausdrücklich verlangen.
USER_AGENT = ("Ratslotse/1.0 (+https://ratslotse.de; "
              "Beteiligungsbericht der Stadt Oldenburg)")

#: Sekunden zwischen zwei Abrufen. Sieben Dokumente alle vier Wochen sind
#: keine Last; die Pause kostet nichts und macht aus einem Lauf keine Serie.
PAUSE = 1.0

#: Obergrenze je Dokument. Der größte Bericht misst 5,1 MB (2024); 40 MB lassen
#: reichlich Luft und fangen trotzdem den Fall ab, dass hinter der Adresse
#: eines Tages etwas ganz anderes liegt.
MAX_BYTES = 40 * 1024 * 1024

TIMEOUT = 120


@dataclass(frozen=True)
class Dokument:
    """Ein geholtes (oder als unverändert erkanntes) Dokument."""

    url: str
    #: ``None``, wenn der Server ``304 Not Modified`` geantwortet hat.
    inhalt: bytes | None
    #: ``Last-Modified`` des Servers — der belastbarste Hinweis darauf, wann
    #: die Stadt den Bericht veröffentlicht hat. Bei den sieben Jahrgängen
    #: liegt er zwischen Januar und Juni des zweiten Folgejahres.
    last_modified: str | None = None
    etag: str | None = None

    @property
    def unveraendert(self) -> bool:
        return self.inhalt is None


class DownloadFehler(RuntimeError):
    """Der Abruf ist gescheitert — mit einem Satz, der sagt, woran.

    Eigene Klasse, weil der Cron zwischen „die Seite ist gerade weg" (warten)
    und „da liegt kein PDF mehr" (nachsehen) unterscheiden können muss, ohne
    ``requests``-Ausnahmen durchzureichen."""


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def hole(url: str, last_modified: str | None = None, etag: str | None = None,
         session: requests.Session | None = None) -> Dokument:
    """Ein PDF holen — oder feststellen, dass sich nichts geändert hat.

    ``last_modified``/``etag`` sind der Stand, den wir schon haben. Antwortet
    der Server mit ``304``, kommt ein :class:`Dokument` ohne Inhalt zurück und
    der Aufrufer weiß: nichts zu tun.

    Wirft :class:`DownloadFehler`, wenn die Antwort kein PDF ist oder zu groß
    wird. Beides ist kein Absturz, sondern ein Befund — der Cron zählt ihn und
    meldet ihn, statt den Lauf zu beenden."""
    s = session or _session()
    kopf = {}
    if last_modified:
        kopf["If-Modified-Since"] = last_modified
    if etag:
        kopf["If-None-Match"] = etag
    try:
        r = s.get(url, headers=kopf, timeout=TIMEOUT, stream=True)
    except requests.RequestException as exc:
        raise DownloadFehler(f"{url}: {type(exc).__name__}: {exc}") from exc

    if r.status_code == 304:
        r.close()
        return Dokument(url=url, inhalt=None, last_modified=last_modified, etag=etag)
    if r.status_code != 200:
        r.close()
        raise DownloadFehler(f"{url}: HTTP {r.status_code}")

    typ = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if typ and typ != "application/pdf":
        r.close()
        raise DownloadFehler(
            f"{url}: liefert {typ!r} statt application/pdf — dort liegt kein "
            f"Bericht (mehr)")

    # Stückweise lesen und dabei mitzählen: `Content-Length` ist eine Angabe
    # der Gegenseite und keine Zusage.
    brocken, gesamt = [], 0
    for stueck in r.iter_content(64 * 1024):
        gesamt += len(stueck)
        if gesamt > MAX_BYTES:
            r.close()
            raise DownloadFehler(
                f"{url}: größer als {MAX_BYTES // 1024 // 1024} MB — abgebrochen")
        brocken.append(stueck)
    r.close()
    inhalt = b"".join(brocken)
    if not inhalt.startswith(b"%PDF"):
        raise DownloadFehler(f"{url}: fängt nicht mit %PDF an")
    return Dokument(url=url, inhalt=inhalt,
                    last_modified=r.headers.get("Last-Modified"),
                    etag=r.headers.get("ETag"))


#: Ein Link auf ein Berichts-PDF in der Übersichtsseite.
_PDF_LINK = re.compile(
    r'href="(/fileadmin/[^"]*[Bb]eteiligungsbericht[^"]*\.pdf)"', re.I)


def berichtslinks(html: str) -> list[tuple[int, str]]:
    """Aus der Übersichtsseite die Berichts-PDFs herauslesen → ``[(year, url)]``.

    Das Jahr kommt aus dem **Dateinamen**, nicht aus dem Linktext: Der
    Linktext ist redaktionell gepflegt und lautet mal „Beteiligungsbericht
    2023", mal „Bericht für das Jahr 2023". Die Dateinamen sind über sieben
    Jahrgänge einheitlich genug — ``Beteiligungsbericht_2018.pdf`` bis
    ``Beteiligungsbericht_2024_kombiniert_final.pdf`` —, dass die erste
    Jahreszahl darin immer das Berichtsjahr ist.

    Endgültig entscheidet ohnehin das Dokument selbst: ``beteiligungsbericht.
    jahrgang()`` liest das Berichtsjahr aus der Kopfzeile, und wenn beide
    auseinanderlaufen, gilt das Dokument (s. Cron)."""
    aus: dict[int, str] = {}
    for pfad in _PDF_LINK.findall(html or ""):
        m = re.search(r"(20\d\d)", pfad)
        if not m:
            continue
        aus.setdefault(int(m.group(1)), BASE + pfad)
    return sorted(aus.items())


def uebersicht(url: str, session: requests.Session | None = None) -> str:
    """Die Übersichtsseite als HTML holen."""
    s = session or _session()
    try:
        r = s.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise DownloadFehler(f"{url}: {type(exc).__name__}: {exc}") from exc
    return r.text


def warte() -> None:
    """Die Pause zwischen zwei Abrufen."""
    time.sleep(PAUSE)
