"""Wo das Ratsinformationssystem der Stadt Oldenburg liegt — die EINE Stelle.

**Warum es diese Datei gibt.** Bis 11/2026 stand der Host an elf Stellen im
Code (`BASE = "https://buergerinfo.oldenburg.de"` in Scraper, Protokollen,
Vorlagen, Watcher …) und in rund 75.000 gespeicherten Adressen. Dann zog die
Stadt um: `buergerinfo.oldenburg.de` leitet seitdem **jede** Adresse per 301
auf die Startseite von `ratsinfo.oldenburg.de/bi/` um und verliert dabei den
Pfad; die Seiten heißen dort `.asp` statt `.php`. Die Nummern (ksinr, kvonr,
Dokument-id) sind geblieben.

Gemerkt hat es niemand. `requests` folgte der Umleitung, die Parser fanden auf
der Startseite nichts, und „nichts gefunden“ ist für einen Kalender eine
gültige Antwort: kein Fehler, kein Alarm, `Termine im Kalender: 0` in jedem
Lauf. Aufgefallen ist es am 22.11.2026 nebenbei, beim Bau des
Mehrheitsrechners.

Deshalb steht hier dreierlei:

1. **Die Adresse** (`BASE`, `page_url`, `session_url` …) — wer eine Ratsinfo-
   Adresse baut, baut sie hier. `tests/test_ris_adresse.py` meldet jede
   zweite Stelle.
2. **Der Umzug alter Adressen** (`current`) — für gespeicherte Daten
   (`CouncilStore._migrate` schreibt den Bestand einmal um) und als
   Sicherheitsnetz vor jedem Abruf.
3. **Der Alarm** (`check`, `RisError`, `probe`) — ein dauerhafter Umzug
   (301/308), ein fremder Host oder eine Seite, die kein SessionNet ist, ist
   ein FEHLER und kein leeres Ergebnis. Der Cron stürzt dann ab, und
   `run_guarded` meldet es beim ersten Lauf.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import requests

HOST = "ratsinfo.oldenburg.de"
#: Wurzel aller Seiten — ohne Schrägstrich am Ende.
BASE = f"https://{HOST}/bi"
#: Endung der SessionNet-Seiten auf diesem Host (bis 11/2026: ``php``).
EXT = "asp"

#: Frühere Hosts. Stehen in gespeicherten Adressen, alten Mails und Links.
FORMER_HOSTS = ("buergerinfo.oldenburg.de",)

#: Seiten, die beim Umzug nicht nur die Endung gewechselt haben.
_RENAMED = {"vo040": "vo0040"}

#: Die Dokumentnummer in einer Datei-Adresse — alt wie neu. Sie ist die
#: Identität eines Anhangs (Tagesordnungs-Hash, Anlagen-Diff): Träfe das
#: Muster nur die alte Endung, sähe nach dem Umzug jede Anlage jeder Sitzung
#: „neu“ aus, und alle Abos bekämen eine Änderungsmeldung.
GETFILE_ID = re.compile(r"getfile\.(?:php|asp)\?id=(\d+)", re.I)

_FORMER_URL = re.compile(
    r"https?://(?:" + "|".join(re.escape(h) for h in FORMER_HOSTS) + r")"
    r"(?P<rest>/[^\s\"'<>\\)\]]*)?", re.I)


def page_url(page: str, **params: object) -> str:
    """``page_url("si0057", __ksinr=4642)`` → die Adresse der Seite."""
    url = f"{BASE}/{page}.{EXT}"
    query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return f"{url}?{query}" if query else url


def session_url(ksinr: int) -> str:
    """Die Seite einer Sitzung (Tagesordnung, Dokumente)."""
    return page_url("si0057", __ksinr=ksinr)


def template_url(kvonr: int) -> str:
    """Die Seite einer Vorlage."""
    return page_url("vo0050", __kvonr=kvonr)


def file_url(document_id: int) -> str:
    """Ein Dokument (PDF) des Ratsinformationssystems."""
    return page_url("getfile", id=document_id, type="do")


#: Die Vorlagen-Recherche — der Ort, auf den ein Beleg zeigt, der kein
#: einzelnes Dokument nennen kann.
SEARCH_URL = page_url("vo0040")


def _moved(rest: str) -> str:
    path, sep, query = rest.partition("?")
    m = re.fullmatch(r"(?P<dir>.*/)?(?P<page>[A-Za-z0-9_]+)\.(?:php|asp)", path)
    if m:
        page = _RENAMED.get(m.group("page").lower(), m.group("page"))
        path = f"{m.group('dir') or '/'}{page}.{EXT}"
    return f"{path}{sep}{query}"


def current(text: str | None) -> str | None:
    """Jede frühere Ratsinfo-Adresse in ``text`` auf den heutigen Host bringen.

    ``text`` darf eine einzelne Adresse sein oder ein ganzer Text (JSON, eine
    Mail), in dem Adressen stehen. Was keine frühere Adresse ist, bleibt
    Zeichen für Zeichen stehen; zweimal angewandt ändert sich nichts mehr.

    ``https://buergerinfo.oldenburg.de/getfile.php?id=7&type=do`` →
    ``https://ratsinfo.oldenburg.de/bi/getfile.asp?id=7&type=do``
    """
    if not text or not any(h in text.lower() for h in FORMER_HOSTS):
        return text
    return _FORMER_URL.sub(lambda m: BASE + _moved(m.group("rest") or ""), text)


def current_in(value):
    """``current`` für alles Verschachtelte: jede Zeichenkette in Listen und
    Wörterbüchern — für gespeicherte Antworten, deren Quellen als JSON liegen."""
    if isinstance(value, str):
        return current(value)
    if isinstance(value, list):
        return [current_in(v) for v in value]
    if isinstance(value, dict):
        return {k: current_in(v) for k, v in value.items()}
    return value


def is_ris(url: str | None) -> bool:
    """Zeigt die Adresse aufs Ratsinformationssystem (heutiger oder früherer Host)?"""
    low = (url or "").lower()
    return HOST in low or any(h in low for h in FORMER_HOSTS)


class RisError(RuntimeError):
    """Das Ratsinformationssystem antwortet nicht so, wie wir es kennen.

    Bewusst KEINE ``requests.RequestException``: Die wird an mehreren Stellen
    als „gerade nicht erreichbar, nächstes Mal wieder“ geschluckt. Ein Umzug
    geht nicht von selbst vorbei."""


def check(response: requests.Response, *, html: bool = False) -> requests.Response:
    """Die Antwort prüfen — und laut werden, wenn sie nach Umzug aussieht.

    - **301/308** irgendwo auf dem Weg: Die Seite ist DAUERHAFT woanders.
      SessionNet selbst leitet intern nur mit 302 weiter (eine Sitzung ohne
      veröffentlichte Tagesordnung, eine Personenseite) — das bleibt erlaubt.
    - **Fremder Host** am Ende: Wir sind nicht mehr im Ratsinfo.
    - ``html=True``: Die Seite muss sich als SessionNet ausweisen. Eine
      Wartungsseite oder die Startseite eines neuen Systems täte das nicht.
    """
    for hop in [*response.history, response]:
        host = (urlsplit(hop.url).hostname or "").lower()
        if host != HOST:
            raise RisError(
                f"Das Ratsinformationssystem antwortet von einem fremden Host ({host or '?'}) "
                f"statt von {HOST}: {hop.url}")
        if hop.status_code in (301, 308):
            raise RisError(
                f"Das Ratsinformationssystem ist dauerhaft umgezogen (HTTP {hop.status_code}): "
                f"{hop.url} → {hop.headers.get('Location', '?')}. Adresse in council/ris.py "
                f"nachziehen.")
    if html and response.ok and "sessionnet" not in response.text[:4000].lower():
        raise RisError(
            f"{response.url} ist keine SessionNet-Seite mehr (Kennung fehlt im Seitenkopf) — "
            f"anderes System oder Wartungsseite?")
    return response


def get(session: requests.Session, page: str, *, timeout: float = 20,
        html: bool = True, **params: object) -> requests.Response:
    """Eine Seite des Ratsinformationssystems holen — geprüft (s. ``check``)."""
    response = session.get(f"{BASE}/{page}.{EXT}",
                           params={k: str(v) for k, v in params.items() if v is not None},
                           timeout=timeout)
    check(response, html=html)
    response.raise_for_status()
    return response


def fetch(session: requests.Session, url: str, *, timeout: float = 45) -> requests.Response:
    """Eine gespeicherte Adresse holen (ein PDF, eine Anlage).

    Eine frühere Ratsinfo-Adresse wird vorher umgezogen; liegt das Ziel im
    Ratsinfo, gilt dieselbe Prüfung wie für Seiten. Andere Hosts (Stadt-
    Website, Open Data) laufen unverändert durch."""
    url = current(url) or url
    response = session.get(url, timeout=timeout)
    if is_ris(url):
        check(response)
    response.raise_for_status()
    return response


def probe(session: requests.Session | None = None) -> dict:
    """Der tägliche Blick von außen: Antwortet das Ratsinfo wie erwartet?

    Zwei Abrufe (Kalender des laufenden Monats, RSS-Feed) — unabhängig davon,
    ob die Crons laufen und was sie melden. Gibt ``{"befunde": [Text, …],
    "kennzahlen": {…}}`` zurück; ein Befund ist ein fertiger Absatz für die
    Herzschlag-Mail. Wirft nie: Ein Netzfehler ist selbst ein Befund.
    """
    from datetime import date

    from . import scraper as sc

    befunde: list[str] = []
    k: dict = {}
    s = session or requests.Session()
    s.headers.setdefault("User-Agent", "Mozilla/5.0 (Ratslotse)")
    heute = date.today()
    try:
        r = get(s, "si0040", __cjahr=heute.year, __cmonat=heute.month)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(r.text, "html.parser")
        # Das Gerüst des Kalenders: eine Zelle je Tag. Fehlt es, hat sich die
        # Seite geändert — auch wenn in diesem Monat zufällig niemand tagt.
        k["ris_kalender_tage"] = len(soup.find_all("td", class_="smc_fct_day"))
        k["ris_kalender_termine"] = len(sc._extract_scheduled(soup, heute.year, heute.month))
        if not k["ris_kalender_tage"]:
            befunde.append(
                "<b>Der Kalender des Ratsinformationssystems hat sein Gerüst verloren</b> "
                f"({page_url('si0040')}): keine einzige Tageszeile. Der Scraper findet dort "
                "nichts mehr — Seitenaufbau prüfen (<code>council/scraper.py</code>).")
    except (RisError, requests.RequestException) as exc:
        k["ris_kalender_tage"] = 0
        befunde.append(
            f"<b>Das Ratsinformationssystem antwortet nicht wie erwartet</b>: {exc} "
            "Solange das so ist, kommen keine neuen Sitzungen, Tagesordnungen und Protokolle "
            "an (<code>council/ris.py</code>).")
        return {"befunde": befunde, "kennzahlen": k}
    try:
        r = get(s, "rssfeed", html=False, filter="s")
        k["ris_rss_eintraege"] = r.text.count("<item")
        if "<rss" not in r.text[:500].lower() and "<feed" not in r.text[:500].lower():
            befunde.append(
                f"<b>Der RSS-Feed des Ratsinformationssystems ist kein Feed mehr</b> "
                f"({page_url('rssfeed', filter='s')}).")
    except (RisError, requests.RequestException) as exc:
        befunde.append(f"<b>Der RSS-Feed des Ratsinformationssystems antwortet nicht</b>: {exc}")
    return {"befunde": befunde, "kennzahlen": k}
