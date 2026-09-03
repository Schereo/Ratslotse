#!/usr/bin/env python3
"""Die Statistik-Quellen sichern, bevor sie verschwinden (täglich).

Warum es diesen Job gibt
------------------------
**Die Stadt führt kein Jahrbuch-Archiv.** Auf der Übersichtsseite steht immer
nur die *jeweils neueste* Ausgabe jeder Tabelle; der Dateiname trägt den
Jahrgang (``1103-2025-AZ.pdf``), und sobald die Ausgabe 2026 erscheint, ist die
alte Adresse ein 404. Nachgemessen am 17.08.2026: ``1103-2024-AZ.pdf``,
``1102-2024-AZ.pdf``, ``1108-2024-AZ.pdf``, ``1108-2023-AZ.pdf``,
``STJB2024_DS.pdf`` — **alle 404**. Das Internet Archive hat vom
Statistik-Verzeichnis der Stadt **null** Schnappschüsse.

Für die meisten Tabellen ist das verschmerzbar, weil sie lange Reihen führen.
Für zwei ist es endgültig: Tabelle **1103** (Steuern und Finanzzuweisungen,
Plan neben Ist) und **0803** (Sozialhilfe) zeigen nur **drei Jahrgänge**. Jede
neue Ausgabe schiebt den ältesten heraus — und niemand hat ihn dann noch.

Dasselbe gilt leiser für das Open-Data-Portal: Die Adressen dort sind stabil
(``1104_Steuereinnahmen_0.csv``), der *Inhalt* wird überschrieben. Wer
nachvollziehen will, was am 19.06.2026 in einer Datei stand, kann das danach
nicht mehr — es sei denn, jemand hat es aufgehoben.

Dieser Job hebt es auf. Er **parst nichts**. Er sichert nur; was in den
Dateien steht, holen sich die Parser später daraus.

Was ein Lauf tut
----------------
1. **Open Data:** ``https://opendata.oldenburg.de/data.json`` holen (der
   DCAT-Katalog, 91 Datensätze mit 186 Dateien). Das Feld ``modified`` je
   Datensatz ist die billige Vorprüfung: Steht dort derselbe Tag wie beim
   letzten Mal **und** liegt jede Datei des Datensatzes schon im Archiv, wird
   der Datensatz übersprungen — ohne einen einzigen weiteren Abruf.
2. **Jahrbuch:** Die Übersichtsseite der Stadt holen und **alle** darauf
   verlinkten PDFs sichern. Nicht aus einer festen Adressliste: Eine feste
   Liste zeigte nach dem nächsten Erscheinen auf 404-Adressen und **fände die
   neue Ausgabe nicht** — sie versagte genau in dem Moment, für den es diesen
   Job gibt. Die Übersichtsseite ist der stabile Teil, die Dateinamen sind es
   nicht.
3. **Finanzausgleich (LSN):** Die Übersichtsseite des Landesamts holen und die
   Tabellenmappen daraus sichern. Auch hier keine festen Nummern — die
   Download-IDs des LSN (``/download/227086``) wechseln jährlich und lassen
   sich nicht hochzählen.

Jede Datei wird **bedingt** geholt (``If-None-Match`` / ``If-Modified-Since``
aus dem letzten Lauf). Unverändert heißt ``304`` und null Bytes. Gemessen am
17.08.2026: 246 Jahrbuch-PDFs = 56 MB, 186 Open-Data-Dateien = 10 MB. Ein
Erstlauf lädt also rund 70 MB, jeder weitere fast nichts.

Wie versioniert wird — und warum so
-----------------------------------
::

    data/archiv/jahrbuch/1103-2025-AZ.pdf/2026-08-17_9f3c1a2b4d5e.pdf
    data/archiv/opendata/1104_Steuereinnahmen_0.csv/2026-08-17_ab12cd34ef56.csv
                        └── Ordner heißt wie die Datei ┘ └ Tag ┘ └ Inhalt ┘

**Datum *und* Hash, nicht eines von beidem.** Der Hash allein sagte nicht, wann
wir eine Fassung zum ersten Mal gesehen haben — und genau das ist bei einer
Quelle ohne Archiv die halbe Auskunft. Das Datum allein legte dieselben Bytes
mehrfach ab, sobald ein Server seinen ``ETag`` ohne Inhaltsänderung neu
vergibt (Caches, Neuinstallationen und ``rsync``-Deployments tun das).

**Der Hash entscheidet, nicht der ETag.** Vor jedem Schreiben wird geprüft, ob
im Ordner dieser Datei schon eine Fassung mit demselben Inhalts-Hash liegt.
Liegt sie da, passiert nichts. Das macht den Job idempotent — ein zweiter Lauf
am selben Tag, am nächsten Tag oder nach einem Serverumzug legt nichts doppelt
ab, auch wenn die Kopfzeilen der Gegenseite sich geändert haben.

Der Ordnername ist der **volle Dateiname** samt Endung, nicht der Stamm: Das
Portal führt ``E1406_Gewerberegister_2604_0`` als ``.csv`` **und** als
``.xlsx``, und zwei verschiedene Dateien gehören nicht in einen Topf.

``manifest.json`` liegt **im Archiv**, nicht in der Datenbank
--------------------------------------------------------------
Es hält je Adresse fest: ETag, ``Last-Modified``, Hash, Pfad, wann zuerst und
wann zuletzt gesehen, und was zuletzt schiefging. Es steht bewusst neben den
Dateien und nicht in ``council.sqlite``: Ein Archiv, dessen Inhaltsverzeichnis
in einer anderen Datei liegt, ist nach einer Wiederherstellung ein Haufen
Hashes. So bleibt der Ordner für sich allein lesbar — auch von jemandem, der
diesen Code nicht hat.

Backup
------
``data/archiv/`` wandert über ``scripts/backup_db.py`` in den Off-Site-Spiegel.
**Das war vorher nicht so** und ist beim Bauen dieses Jobs nachgemessen worden:
``backup_db.py`` sicherte nur ``data/*.sqlite``, die ``.env`` und
``data/plaene/`` — gespiegelt wird ausschließlich ``data/backups/``. Ein
Archiv, das nur auf einer Festplatte liegt, ist kein Archiv, sondern eine
Kopie. ``dateien_spiegeln()`` nimmt es deshalb mit.

Takt
----
Täglich (``kern/jobs.py``). Nicht, weil sich täglich etwas ändert, sondern
weil die Änderungen **in Schüben** kommen: 29 Open-Data-Datensätze am
19.06.2026, 20 am 14.07.2026. Wer wöchentlich nachsieht, verpasst nichts —
aber er merkt es zwei bis sechs Tage später, und bei einer Quelle ohne Archiv
ist Zeit der einzige Puffer, den es gibt. Ein Lauf ohne Änderung kostet 434
bedingte Abrufe und praktisch keine Bytes.

Aufruf von Hand::

    python scripts/archive_statistik.py [--trocken] [--nur jahrbuch] [--archiv PFAD]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import schulden  # noqa: E402  — die Jahrbuch-Übersichtsseite

# Der AUFBAU des Archivs steht seit 08/2026 in `council/archiv.py`, nicht mehr
# hier: Mit `council/steuertabellen.py` liest zum ersten Mal ein Parser aus dem
# Archiv, und zwei Stellen mit demselben Wissen über Ordnernamen und
# Fassungs-Sortierung laufen auseinander — dieselbe Begründung, aus der dieser
# Job seine Jahrbuch-Adresse aus `council/schulden.py` importiert, statt sie
# abzuschreiben. Der Job SCHREIBT weiterhin allein; er tut es nur nicht mehr
# nach eigenen Regeln.
from council.archiv import (  # noqa: E402
    dateiname, inhalts_hash, manifest_lesen, manifest_schreiben,
    version_ablegen,
    # `endung` benutzt dieser Job selbst nicht mehr (`version_ablegen` hängt die
    # Endung inzwischen selbst an) — `tests/test_archive_statistik.py` greift die
    # Funktion aber über den Modul-Namensraum ab (`a.endung(…)`). Der Import ist
    # damit ein Re-Export, den kein Linter sehen kann: F401 hat ihn beim
    # Einführen von ruff entfernt, und genau dieser Test fiel um.
    endung,  # noqa: F401
)

JOB = "archive_statistik"

ARCHIV = Path(os.environ.get("ARCHIV_DIR") or ROOT / "data" / "archiv")

#: Wer da klopft — mit Zweck und Rückadresse, wie in ``council/stadtdownload.py``.
USER_AGENT = ("Ratslotse/1.0 (+https://ratslotse.de; "
              "Archiv der amtlichen Statistik-Veröffentlichungen)")

#: Sekunden zwischen zwei Abrufen. Bei 434 Dateien im Erstlauf sind das gut
#: zwei Minuten Wartezeit — die kostet uns nichts und den fremden Server viel.
#: Auf 304-Antworten wird nicht gewartet: Die sind keine Last.
PAUSE = 0.3

#: Obergrenze je Datei. Die größte gemessene ist ``STJB2025_DS.pdf`` mit
#: 12,9 MB; 60 MB lassen Luft und fangen trotzdem den Fall ab, dass hinter
#: einer Adresse eines Tages etwas ganz anderes liegt.
MAX_BYTES = 60 * 1024 * 1024

#: Obergrenze für einen Lauf. Der Erstlauf misst rund 70 MB. Reißt ein Lauf
#: diese Grenze, hat sich an der Quelle etwas grundsätzlich geändert — dann
#: soll ein Mensch nachsehen, statt dass der Job die Platte füllt.
MAX_LAUF_BYTES = 500 * 1024 * 1024

TIMEOUT = 120

#: Der Open-Data-Katalog. Unauthentifiziert, stabil, und selbst archivierungs-
#: würdig: Er trägt die ``modified``-Daten, die Lizenz und die Beschreibung
#: jedes Datensatzes. Ohne ihn wüsste in fünf Jahren niemand mehr, was
#: ``1104_Steuereinnahmen_0.csv`` eigentlich enthielt.
KATALOG_URL = "https://opendata.oldenburg.de/data.json"

#: Die Übersichtsseite des Statistischen Jahrbuchs — dieselbe, aus der
#: ``scripts/ingest_schulden.py`` seinen Tabellenlink zieht. Bewusst importiert
#: statt abgeschrieben: zwei Kopien derselben Adresse laufen auseinander.
JAHRBUCH_URL = schulden.JAHRBUCH_URL

#: Die Übersichtsseite des Kommunalen Finanzausgleichs beim Landesamt für
#: Statistik Niedersachsen. Sie führt alle Jahrgänge seit 2013 — die
#: Download-Nummern darunter wechseln jährlich und stehen deshalb nirgends
#: fest verdrahtet.
KFA_URL = ("https://www.statistik.niedersachsen.de/kommunaler-fiscal_equalization/"
           "kommunaler-fiscal_equalization-in-niedersachsen-tabellen-214575.html")

#: Nur Dateien aus dem Statistik-Verzeichnis der Stadt. Die Übersichtsseite
#: verlinkt auch Broschüren aus anderen Ordnern; das Archiv soll die
#: Jahrbuch-Tabellen führen und nicht das halbe CMS.
_JAHRBUCH_PFAD = re.compile(
    r'href="(/fileadmin/[^"]*/402_Geo_und_Daten/Statistik/[^"]+\.pdf)"', re.I)

#: Ein Download-Link der LSN-Seite samt Linktext. Der Text ist hier die
#: eigentliche Auskunft — er nennt Jahr und Stand („KFA 2026 endgültig …"),
#: die Nummer sagt nichts.
_LSN_LINK = re.compile(
    r'<a href="(https://www\.statistik\.niedersachsen\.de/download/\d+)"'
    r'[^>]*>(.*?)</a>', re.S | re.I)

#: Welche LSN-Mappen ins Archiv gehören: die Ergebnis- und Vergleichstabellen
#: (Blatt ``9a`` trägt die drei Zuweisungs-Komponenten, ``ST_KR_MESS_VGL`` die
#: Steuerkraftmesszahlen) und die Nivellierungshebesatz-Zeitreihe. Die
#: Einzelergebnis-Mappen der Gemeinden bleiben draußen — sie sind groß und
#: beantworten keine Frage, die dieses Projekt stellt.
_LSN_INTERESSANT = re.compile(
    r"(Ergebnis[-\s]?und\s+Vergleichstabellen|Ergebnis-\s+und\s+Vergleichstabellen"
    r"|Nivellierungshebesätze)", re.I)


# --- Namen und Pfade --------------------------------------------------------
#
# `dateiname`, `endung`, `inhalts_hash`, `version_ablegen` und die beiden
# Manifest-Funktionen stehen in `council/archiv.py` (Import oben) — sie
# beschreiben den AUFBAU des Archivs, und den muss auch lesen können, wer
# nicht dieser Job ist. Die Namen bleiben hier verfügbar, damit Aufrufer
# und Tests unverändert `archive_statistik.dateiname(...)` schreiben.


# --- Netz -------------------------------------------------------------------

class AbrufFehler(RuntimeError):
    """Der Abruf ist gescheitert — mit einem Satz, der sagt woran.

    Eigene Klasse, weil ein 404 hier ein **Befund** ist und kein Absturz: Er
    heißt „diese Adresse gibt es nicht mehr", und genau davor soll das Archiv
    schützen. Gezählt und gemeldet wird er, beendet wird der Lauf nicht.
    """


@dataclass
class Antwort:
    inhalt: bytes | None          # None = 304, unverändert
    etag: str | None = None
    last_modified: str | None = None


def hole(url: str, etag: str | None = None, last_modified: str | None = None,
         session=None) -> Antwort:
    """Eine Datei bedingt holen. ``304`` ergibt eine Antwort ohne Inhalt.

    Anders als ``council/stadtdownload.hole`` wird der Inhaltstyp **nicht**
    geprüft: Hier kommen PDF, CSV, XLSX, JSON, PNG und Shapefiles an, und das
    Portal beschriftet sie ohnehin unzuverlässig (das LSN liefert echte
    ``.xlsx`` als ``application/vnd.ms-excel``). Was in der Datei steht,
    entscheiden später die Parser; dieser Job sichert Bytes.
    """
    import requests

    s = session
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
    kopf = {}
    if etag:
        kopf["If-None-Match"] = etag
    if last_modified:
        kopf["If-Modified-Since"] = last_modified
    try:
        r = s.get(url, headers=kopf, timeout=TIMEOUT, stream=True)
    except Exception as exc:  # noqa: BLE001 — requests-Fehler nicht durchreichen
        raise AbrufFehler(f"{url}: {type(exc).__name__}: {exc}") from exc

    if r.status_code == 304:
        r.close()
        return Antwort(inhalt=None, etag=etag, last_modified=last_modified)
    if r.status_code != 200:
        code = r.status_code
        r.close()
        raise AbrufFehler(f"{url}: HTTP {code}")

    brocken, gesamt = [], 0
    for stueck in r.iter_content(64 * 1024):
        gesamt += len(stueck)
        if gesamt > MAX_BYTES:
            r.close()
            raise AbrufFehler(f"{url}: größer als {MAX_BYTES // 1024 // 1024} MB "
                              f"— abgebrochen")
        brocken.append(stueck)
    kopfzeilen = r.headers
    r.close()
    inhalt = b"".join(brocken)
    if not inhalt:
        raise AbrufFehler(f"{url}: leere Antwort mit HTTP 200")
    return Antwort(inhalt=inhalt, etag=kopfzeilen.get("ETag"),
                   last_modified=kopfzeilen.get("Last-Modified"))


def page(url: str, session=None) -> str:
    """Eine Übersichtsseite als Text holen."""
    import requests

    s = session
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
    try:
        r = s.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise AbrufFehler(f"{url}: {type(exc).__name__}: {exc}") from exc
    return r.text


# --- Was zu holen ist -------------------------------------------------------

def jahrbuch_links(html_text: str, basis: str = "https://www.oldenburg.de") -> list[str]:
    """Aus der Übersichtsseite die Tabellen-PDFs → sortierte Adressliste."""
    aus = {basis + p for p in _JAHRBUCH_PFAD.findall(html_text or "")}
    return sorted(aus)


def kfa_links(html_text: str) -> list[tuple[str, str]]:
    """Aus der LSN-Seite die interessanten Mappen → ``[(url, linktext)]``.

    Der Linktext wandert mit ins Archiv, weil er die einzige Auskunft ist:
    ``/download/227086`` sagt nichts, „KFA 2026 endgültig Ergebnis und
    Vergleichstabellen KSV (xlsx)" sagt Jahr, Stand und Inhalt.
    """
    aus: dict[str, str] = {}
    for url, roh in _LSN_LINK.findall(html_text or ""):
        # ``unescape``, weil der Linktext die Auskunft ist: Ein „endg&uuml;ltig"
        # als Zeichenkette unterschiede sich von „endgültig" und legte dieselbe
        # Mappe unter zwei Dateinamen ab.
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", roh)).split())
        if not _LSN_INTERESSANT.search(text):
            continue
        aus.setdefault(url, text)
    return sorted(aus.items())


def kfa_dateiname(url: str, linktext: str) -> str:
    """``/download/227086`` + „KFA 2026 endgültig … (xlsx)" → sprechender Name.

    Der Dateiname ist hier eine Konstruktion und keine Übernahme — die Adresse
    trägt keinen. Er muss über die Jahre **stabil** sein, sonst legt der Job
    dieselbe Mappe unter zwei Namen ab: deshalb aus dem Linktext, der die
    Jahresangabe trägt, plus der Download-Nummer als Anker.
    """
    nummer = url.rstrip("/").rsplit("/", 1)[-1]
    kern = re.sub(r"\((?:xlsx|xls|pdf|csv)\)", "", linktext, flags=re.I)
    kern = re.sub(r"[^A-Za-z0-9äöüÄÖÜß]+", "-", kern).strip("-").lower()
    endg = ".xlsx" if re.search(r"\(xlsx?\)", linktext, re.I) else ".pdf"
    return f"{kern[:80]}-{nummer}{endg}"


def katalog_dateien(katalog: dict) -> list[tuple[str, str, str]]:
    """DCAT-Katalog → ``[(datensatz_id, modified, downloadURL)]``.

    ``modified`` gehört zum Datensatz, nicht zur einzelnen Datei — deshalb
    reicht es je Adresse durchgereicht zu werden. Es ist die billige
    Vorprüfung: unverändert plus vollständig im Archiv = kein Abruf.
    """
    aus: list[tuple[str, str, str]] = []
    gesehen: set[str] = set()
    for ds in (katalog or {}).get("dataset", []):
        kennung = str(ds.get("identifier") or ds.get("title") or "")
        geaendert = str(ds.get("modified") or "")
        for dist in ds.get("distribution", []) or []:
            url = dist.get("downloadURL")
            if url and url not in gesehen:
                gesehen.add(url)
                aus.append((kennung, geaendert, url))
    return aus


# --- Der Lauf ---------------------------------------------------------------

def _sichern(url: str, area: str, name: str, archiv: Path, manifest: dict,
             zaehler: dict, heute: date, session, trocken: bool,
             sagen) -> None:
    """Eine Adresse: bedingt holen, bei Änderung versioniert ablegen.

    Trägt das Ergebnis in ``zaehler`` und ``manifest`` ein. Wirft nie — ein
    Fehler ist hier ein Befund und kein Abbruch.
    """
    zaehler["geprueft"] += 1
    as_of = manifest.get(url, {})
    if trocken:
        sagen(f"  würde prüfen: {url}")
        return
    try:
        answer = hole(url, etag=as_of.get("etag"),
                       last_modified=as_of.get("last_modified"), session=session)
    except AbrufFehler as exc:
        zaehler["fehler"].append(str(exc))
        eintrag = dict(as_of)
        eintrag["fehler"] = str(exc)
        eintrag["fehler_am"] = heute.isoformat()
        manifest[url] = eintrag
        return

    if answer.inhalt is None:
        zaehler["unveraendert"] += 1
        eintrag = dict(as_of)
        eintrag["zuletzt_gesehen"] = heute.isoformat()
        eintrag.pop("fehler", None)
        eintrag.pop("fehler_am", None)
        manifest[url] = eintrag
        return

    time.sleep(PAUSE)
    zaehler["bytes"] += len(answer.inhalt)
    if zaehler["bytes"] > MAX_LAUF_BYTES:
        raise RuntimeError(
            f"Der Lauf hat {zaehler['bytes'] / 1e6:.0f} MB geladen und damit die "
            f"Grenze von {MAX_LAUF_BYTES / 1e6:.0f} MB gerissen. An der Quelle hat "
            f"sich etwas grundsätzlich geändert — bitte nachsehen, statt die "
            f"Platte zu füllen.")

    pfad, neu = version_ablegen(archiv, area, name, answer.inhalt, heute)
    if neu:
        zaehler["neu"] += 1
        sagen(f"  NEU  {area}/{name}  ({len(answer.inhalt) / 1024:.0f} KB) "
              f"→ {pfad.name}")
    else:
        # Der Server hat geliefert, aber die Bytes kennen wir schon: geänderter
        # ETag ohne geänderten Inhalt. Genau dafür entscheidet der Hash.
        zaehler["unveraendert"] += 1
    manifest[url] = {
        "area": area, "datei": name,
        "etag": answer.etag, "last_modified": answer.last_modified,
        "hash": inhalts_hash(answer.inhalt), "bytes": len(answer.inhalt),
        "pfad": str(pfad.relative_to(archiv)),
        "zuerst_gesehen": as_of.get("zuerst_gesehen") or heute.isoformat(),
        "zuletzt_gesehen": heute.isoformat(),
    }


def _letzter_katalog(archiv: Path, manifest: dict) -> str | None:
    """Die zuletzt gesicherte Fassung von ``data.json`` aus dem Archiv lesen.

    Gebraucht, wenn der Katalog gerade ``304`` antwortet oder nicht erreichbar
    ist: Sein Inhalt ist die Liste der Adressen, die geprüft werden sollen —
    ohne ihn fiele die Open-Data-Prüfung an diesem Tag ganz aus, und das wäre
    die eine Lücke, die dieser Job nicht haben darf.
    """
    ordner = archiv / "opendata" / "data.json"
    fassungen = sorted(p for p in ordner.glob("*.json") if p.is_file()) \
        if ordner.is_dir() else []
    if not fassungen:
        return None
    try:
        return fassungen[-1].read_text(encoding="utf-8")
    except OSError:
        return None


def _archivgroesse(archiv: Path) -> tuple[int, int]:
    """``(Dateien, Bytes)`` des Archivs — für die Kennzahlen des Laufs."""
    n = b = 0
    for p in archiv.rglob("*"):
        if p.is_file() and p.name != "manifest.json":
            n += 1
            b += p.stat().st_size
    return n, b


def main(archiv: str | Path | None = None, heute: date | None = None,
         trocken: bool = False, nur: str | None = None, still: bool = False,
         ohne_vorpruefung: bool = False, katalog_text: str | None = None,
         jahrbuch_html: str | None = None, kfa_html: str | None = None) -> dict:
    """Ein Lauf. Die drei ``*_text``/``*_html``-Argumente nur für Tests.

    ``ohne_vorpruefung`` schaltet die beiden billigen Abkürzungen ab (das
    ``modified``-Feld des Open-Data-Katalogs, die Unveränderlichkeit der
    LSN-Nummern) und klopft überall an. Der Ausweg, falls sich eine dieser
    Annahmen einmal als falsch erweist — ohne dass jemand Code ändern muss.
    """
    heute = heute or date.today()
    ziel = Path(archiv or ARCHIV)
    sagen = (lambda *a: None) if still else print

    manifest = manifest_lesen(ziel)
    zaehler: dict = {"geprueft": 0, "neu": 0, "unveraendert": 0,
                     "uebersprungen": 0, "bytes": 0, "fehler": []}
    session = None
    if not trocken:
        import requests

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

    try:
        # --- 1) Open Data ---------------------------------------------------
        if nur in (None, "opendata"):
            sagen("Open-Data-Portal:")
            katalog: dict = {}
            if katalog_text is None and not trocken:
                as_of = manifest.get(KATALOG_URL, {})
                try:
                    answer = hole(KATALOG_URL, etag=as_of.get("etag"),
                                   last_modified=as_of.get("last_modified"),
                                   session=session)
                    if answer.inhalt is not None:
                        katalog_text = answer.inhalt.decode("utf-8", "replace")
                        manifest[KATALOG_URL] = {
                            "area": "opendata", "datei": "data.json",
                            "etag": answer.etag,
                            "last_modified": answer.last_modified,
                            "hash": inhalts_hash(answer.inhalt),
                            "zuerst_gesehen": as_of.get("zuerst_gesehen") or heute.isoformat(),
                            "zuletzt_gesehen": heute.isoformat()}
                    else:
                        # 304: Der Katalog ist unverändert — aber ohne ihn gäbe
                        # es an diesem Tag GAR KEINE Open-Data-Prüfung. Die
                        # gesicherte Fassung von gestern tut es genauso.
                        zaehler["unveraendert"] += 1
                        katalog_text = _letzter_katalog(ziel, manifest)
                except AbrufFehler as exc:
                    zaehler["fehler"].append(str(exc))
                    katalog_text = _letzter_katalog(ziel, manifest)
            if katalog_text and not trocken:
                # Der Katalog gehört selbst ins Archiv: Er trägt Lizenz,
                # Beschreibung und ``modified`` jedes Datensatzes. Ohne ihn
                # wüsste in fünf Jahren niemand, was in einer CSV eigentlich
                # stand. Über den Hash bleibt das idempotent.
                _pfad, neu = version_ablegen(ziel, "opendata", "data.json",
                                             katalog_text.encode("utf-8"), heute)
                if neu:
                    zaehler["neu"] += 1
                    manifest.setdefault(KATALOG_URL, {})["pfad"] = str(
                        _pfad.relative_to(ziel))
            if katalog_text:
                try:
                    katalog = json.loads(katalog_text)
                except json.JSONDecodeError as exc:
                    zaehler["fehler"].append(f"{KATALOG_URL}: kein gültiges JSON ({exc})")
            eintraege = katalog_dateien(katalog)
            sagen(f"  Katalog: {len(eintraege)} Datei(en) in "
                  f"{len({k for k, _, _ in eintraege})} Datensätzen")
            for _kennung, geaendert, url in eintraege:
                as_of = manifest.get(url, {})
                # Die billige Vorprüfung: Datensatz unverändert und Datei liegt
                # schon im Archiv → gar nicht erst anklopfen.
                if (not ohne_vorpruefung and geaendert
                        and as_of.get("modified") == geaendert
                        and as_of.get("hash")
                        and (ziel / as_of.get("pfad", "")).is_file()):
                    zaehler["uebersprungen"] += 1
                    continue
                _sichern(url, "opendata", dateiname(url), ziel, manifest,
                         zaehler, heute, session, trocken, sagen)
                if geaendert and url in manifest and "hash" in manifest[url]:
                    manifest[url]["modified"] = geaendert

        # --- 2) Statistisches Jahrbuch --------------------------------------
        if nur in (None, "jahrbuch"):
            sagen("Statistisches Jahrbuch:")
            if jahrbuch_html is None and not trocken:
                try:
                    jahrbuch_html = page(JAHRBUCH_URL, session=session)
                except AbrufFehler as exc:
                    zaehler["fehler"].append(str(exc))
            links = jahrbuch_links(jahrbuch_html or "")
            if not links and jahrbuch_html:
                # Die Seite gibt es, nur stehen keine Tabellen mehr darauf.
                # Das ist der Fall, für den es diesen Job gibt — melden, nicht
                # schweigen, und nichts anfassen.
                zaehler["fehler"].append(
                    f"{JAHRBUCH_URL}: keine Tabellen-PDFs auf der Übersichtsseite "
                    f"— Aufbau geändert?")
            sagen(f"  Übersicht: {len(links)} Tabelle(n)")
            for url in links:
                _sichern(url, "jahrbuch", dateiname(url), ziel, manifest,
                         zaehler, heute, session, trocken, sagen)

        # --- 3) Kommunaler Finanzausgleich (LSN) ----------------------------
        if nur in (None, "kfa"):
            sagen("Kommunaler Finanzausgleich (LSN):")
            if kfa_html is None and not trocken:
                try:
                    kfa_html = page(KFA_URL, session=session)
                except AbrufFehler as exc:
                    zaehler["fehler"].append(str(exc))
            mappen = kfa_links(kfa_html or "")
            if not mappen and kfa_html:
                zaehler["fehler"].append(
                    f"{KFA_URL}: keine Ergebnis- und Vergleichstabellen verlinkt "
                    f"— Aufbau geändert?")
            sagen(f"  Übersicht: {len(mappen)} Mappe(n)")
            for url, text in mappen:
                # Der LSN-Server schickt **weder ETag noch Last-Modified**
                # (nachgemessen 17.08.2026 an allen 14 Mappen) — bedingt
                # abrufen lässt sich dort nichts, und ohne Vorprüfung zöge der
                # Job täglich 3 MB neu. Er braucht es aber nicht: Eine
                # Download-Nummer ist beim LSN unveränderlich. Eine neue
                # Ausgabe bekommt eine neue Nummer, und selbst eine Korrektur
                # tut das (2023 steht als „endgültig Korrektur" unter 193990
                # neben dem Original). Was einmal gesichert ist, bleibt gleich.
                as_of = manifest.get(url, {})
                if (not ohne_vorpruefung and as_of.get("hash")
                        and (ziel / as_of.get("pfad", "")).is_file()):
                    zaehler["uebersprungen"] += 1
                    continue
                _sichern(url, "kfa", kfa_dateiname(url, text), ziel, manifest,
                         zaehler, heute, session, trocken, sagen)
    finally:
        if not trocken:
            manifest_schreiben(ziel, manifest)

    dateien, bytes_gesamt = _archivgroesse(ziel) if ziel.is_dir() else (0, 0)
    if zaehler["fehler"] and not trocken:
        _melden(zaehler["fehler"])

    aus = {
        "Adressen geprüft": zaehler["geprueft"],
        "Neue Fassungen": zaehler["neu"],
        "Unverändert": zaehler["unveraendert"],
        "Ohne Abruf übersprungen": zaehler["uebersprungen"],
        "Geladen (MB)": round(zaehler["bytes"] / 1e6, 1),
        "Archiv gesamt (Dateien)": dateien,
        "Archiv gesamt (MB)": round(bytes_gesamt / 1e6, 1),
        "Fehler": len(zaehler["fehler"]),
        # Der Wortlaut, nicht nur die Zahl: Ein 404 sagt, WELCHE Adresse weg
        # ist, und das ist die Auskunft, die man am nächsten Tag braucht.
        "befund": sorted(zaehler["fehler"])[:20],
    }
    sagen(f"Fertig: {aus}")
    return aus


def _melden(fehler: list[str]) -> None:
    """Fehler an ALERT_EMAIL melden — nur, wenn sie neu sind.

    Ein 404 auf eine Jahrbuch-Adresse ist der Normalfall an dem Tag, an dem
    eine neue Ausgabe erscheint: Die alte Datei verschwindet, die neue steht
    unter neuem Namen auf der Seite und wird im selben Lauf gesichert. Täglich
    dieselbe Mail darüber wäre eine, die niemand mehr liest.
    """
    if _schon_gemeldet(sorted(fehler)[:20]):
        return
    from kern.alerts import notify_admin

    zeilen = [f"• {html.escape(f)}" for f in sorted(fehler)[:20]]
    if len(fehler) > 20:
        zeilen.append(f"… und {len(fehler) - 20} weitere")
    notify_admin(
        "Beim Sichern der Statistik-Quellen sind Adressen nicht erreichbar "
        "gewesen:\n\n" + "\n".join(zeilen) + "\n\n"
        "Ein 404 auf eine Jahrbuch-Adresse ist normal, wenn eine neue Ausgabe "
        "erschienen ist — die neue Datei steht dann unter neuem Namen auf der "
        "Übersichtsseite und wurde im selben Lauf gesichert. Ein 404 auf eine "
        "Open-Data-Adresse ist es nicht: Dort sind die Adressen stabil.\n"
        "Das Archiv wurde nicht verändert; es wurde nichts gelöscht.",
        betreff="Ratslotse – Statistik-Archiv: eine Quelle fehlt",
        fusszeile="Hinweis des Cron-Jobs archive_statistik — kein Fehler.")


def _schon_gemeldet(befund: list[str]) -> bool:
    """Stand derselbe Befund schon im letzten Lauf? (wie ``check_finanzdaten``)"""
    try:
        from kern.store import Store

        db = Path(os.environ.get("RATSLOTSE_DB") or ROOT / "data" / "ratslotse.sqlite")
        if not db.exists():
            return False
        store = Store(db)
        try:
            laeufe = store.job_runs(job=JOB, limit=1)
        finally:
            store.close()
    except Exception:  # noqa: BLE001 — ohne Historie lieber einmal zu viel melden
        return False
    return bool(laeufe) and (laeufe[0].get("stats") or {}).get("befund") == befund


def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="Statistik-Quellen versioniert unter data/archiv/ sichern")
    ap.add_argument("--archiv", default=None, help=f"Zielordner (Vorgabe: {ARCHIV})")
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was der Lauf prüfen würde — lädt nichts")
    ap.add_argument("--nur", choices=("opendata", "jahrbuch", "kfa"), default=None,
                    help="nur eine Quelle")
    ap.add_argument("--heute", default=None, help="Stichtag JJJJ-MM-TT (für Tests)")
    ap.add_argument("--ohne-vorpruefung", action="store_true",
                    help="überall anklopfen statt die billigen Abkürzungen zu "
                         "nutzen (Open-Data-„modified“, feste LSN-Nummern)")
    args = ap.parse_args()
    main(archiv=args.archiv, trocken=args.trocken, nur=args.nur,
         ohne_vorpruefung=args.ohne_vorpruefung,
         heute=date.fromisoformat(args.heute) if args.heute else None)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(_cli())
    from kern.alerts import run_guarded

    run_guarded(JOB, main)
