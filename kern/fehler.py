"""Aus einer Ausnahme das machen, was man aufheben darf.

**Wozu.** Ein 500er im Web-Backend ging bisher ins ``journalctl`` und sonst
nirgendwohin. Wer nicht zufällig auf dem Server nachsieht, erfährt nie davon —
Cron-Abstürze melden sich per Mail, Request-Fehler nicht. Diese Datei macht aus
einer Ausnahme drei Dinge: einen **Fingerabdruck** (damit tausend gleiche
Fehler eine Zeile sind), eine **kurze Spur** (damit man weiß, wo zu suchen ist)
und einen **gesäuberten Text** (damit nichts Persönliches in der Datenbank
landet).

**Was NICHT aufgehoben wird**, und das ist der wichtigere Teil:

* **Keine Anfragekörper, keine Kopfzeilen, keine Cookies.** Dort stehen
  Passwörter und Sitzungstoken.
* **Kein roher Pfad.** ``/api/council/decision/8525`` wird zur Vorlage
  ``/api/council/decision/{n}``. Sonst führte die Fehlerliste eine Spur davon,
  wer was gelesen hat.
* **Keine Variablenwerte aus dem Traceback.** Aufgehoben werden Datei, Zeile
  und Funktionsname — nicht, was in den Variablen stand.
* **Adressen und lange Ziffernfolgen im Fehlertext werden maskiert.** SQLite
  schreibt Parameter gern in die Meldung; eine E-Mail-Adresse darin wäre genau
  das, was ``lint_adressen.py`` im Quelltext verbietet.

Der Fingerabdruck ist bewusst **grob**: Ausnahmetyp, die letzte Zeile im
EIGENEN Code und die Route. Zwei Aufrufe derselben kaputten Stelle sind
derselbe Fehler, auch wenn die Meldung andere Zahlen trägt — sonst wäre die
Liste nach einem Ausfall tausend Zeilen lang und niemand läse sie.
"""
from __future__ import annotations

import hashlib
import re
import traceback
from pathlib import Path

#: Verzeichnisse, die als „unser Code" gelten. Der Fingerabdruck hängt an der
#: letzten Zeile darin — nicht an der tiefsten Zeile überhaupt, die läge sonst
#: in sqlite3 oder httpx und wäre für alle Fehler dieselbe.
EIGENE = ("kern/", "council/", "web/backend/", "scripts/")

#: So viele Zeilen Spur werden aufgehoben. Mehr liest niemand, und jede Zeile
#: ist eine Gelegenheit, versehentlich etwas mitzunehmen.
SPUR_ZEILEN = 12

_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
#: Vier Ziffern reichen für ein Jahr und einen Betrag; alles Längere ist eine
#: Kennung und gehört nicht in die Fehlerliste.
_ZIFFERN = re.compile(r"\d{5,}")
_TOKEN = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")


def saeubern(text: str, laenge: int = 300, zeilen: bool = False) -> str:
    """Adressen, lange Kennungen und Token maskieren, dann kürzen.

    ``zeilen=True`` behält Zeilenumbrüche — die Spur ist untereinander lesbar,
    in einer Zeile ist sie es nicht.
    """
    t = _MAIL.sub("<adresse>", text or "")
    t = _TOKEN.sub("<token>", t)
    t = _ZIFFERN.sub("<zahl>", t)
    if zeilen:
        t = "\n".join(" ".join(z.split()) for z in t.splitlines())
    else:
        t = " ".join(t.split())
    return t[:laenge]


def route_vorlage(route: str | None, pfad: str) -> str:
    """Die Route, wie sie im Code steht — oder der Pfad mit maskierten Zahlen.

    FastAPI kennt die Vorlage (``/api/council/decision/{decision_id}``), sobald
    eine Route getroffen wurde. Bei einem 404 auf einen unbekannten Pfad gibt
    es keine; dann wird der rohe Pfad genommen und alles Zahlenartige ersetzt,
    damit aus ihm keine Spur wird, wer was aufgerufen hat.
    """
    if route:
        return route
    teile = [("{n}" if t.isdigit() else t) for t in (pfad or "/").split("/")]
    return "/".join(teile)[:200] or "/"


def _rahmen(tb) -> list[traceback.FrameSummary]:
    return list(traceback.extract_tb(tb))


def _letzter_eigener(rahmen: list[traceback.FrameSummary]) -> traceback.FrameSummary | None:
    """Die unterste Zeile, die noch in unserem Code liegt.

    Der tiefste Rahmen überhaupt steht fast immer in einer Fremdbibliothek
    (``sqlite3``, ``httpx``, ``pydantic``) — an ihm hingen sonst alle Fehler
    desselben Bibliotheksaufrufs zusammen, egal von welcher Stelle sie kommen.
    """
    for f in reversed(rahmen):
        p = Path(f.filename).as_posix()
        if any(teil in p for teil in EIGENE) and "site-packages" not in p:
            return f
    return rahmen[-1] if rahmen else None


def _kurz(pfad: str) -> str:
    """Absoluten Dateipfad auf den Teil ab dem Paket kürzen."""
    p = Path(pfad).as_posix()
    for teil in EIGENE:
        i = p.rfind(teil)
        if i >= 0:
            return p[i:]
    return Path(p).name


def spur(exc: BaseException) -> str:
    """Die letzten Zeilen der Spur — Datei, Zeile, Funktion. Keine Werte."""
    rahmen = _rahmen(exc.__traceback__)[-SPUR_ZEILEN:]
    return "\n".join(f"{_kurz(f.filename)}:{f.lineno} in {f.name}" for f in rahmen)


def fingerabdruck(exc: BaseException, route: str) -> str:
    """Der Schlüssel, unter dem gleiche Fehler zusammenfallen.

    Bewusst grob: Ausnahmetyp, letzte eigene Zeile, Route. Zwei Aufrufe
    derselben kaputten Stelle sind derselbe Fehler, auch wenn die Meldung
    andere Zahlen trägt.
    """
    f = _letzter_eigener(_rahmen(exc.__traceback__))
    stelle = f"{_kurz(f.filename)}:{f.lineno}" if f else "?"
    roh = f"{type(exc).__name__}|{stelle}|{route}"
    return hashlib.sha1(roh.encode("utf-8"),
                        usedforsecurity=False).hexdigest()[:16]


def aufbereiten(exc: BaseException, methode: str, route: str | None,
                pfad: str) -> dict:
    """Alles, was von einer Ausnahme in die Datenbank darf."""
    r = route_vorlage(route, pfad)
    return {
        "fingerprint": fingerabdruck(exc, r),
        "exc_type": type(exc).__name__,
        "message": saeubern(str(exc)),
        "route": r,
        "method": (methode or "?").upper()[:10],
        "trace": saeubern(spur(exc), laenge=2000, zeilen=True),
    }


# ---------------------------------------------------------------------------
# Meldungen aus dem Browser
# ---------------------------------------------------------------------------
#
# Dieselbe Tabelle, dieselbe Gruppierung, dieselbe Behandlung — nur kommt die
# Ausnahme hier nicht aus unserem Prozess, sondern über die Leitung. Damit ist
# sie FREMDE EINGABE: Jeder kann auf den Endpunkt schreiben, was er will.
#
# Zwei Folgen, die den Zuschnitt bestimmen:
#
# 1. **Alles wird gekürzt und maskiert**, bevor es gespeichert wird — sonst
#    schriebe uns jemand die Datenbank voll oder legte eine fremde Adresse
#    hinein, die dort nichts zu suchen hat.
# 2. **Der Fingerabdruck entsteht aus dem, was gemeldet wurde**, nicht aus
#    einem Traceback, den wir selbst gelaufen sind. Eine erfundene Meldung
#    erzeugt damit eine eigene Zeile und vermischt sich nicht mit echten.

#: So viele Zeilen Stapel werden aus einer Browser-Meldung übernommen. Der
#: Rest ist Rauschen aus dem Framework.
BROWSER_STAPEL_ZEILEN = 8


def browser_aufbereiten(meldung: dict, pfad: str) -> dict:
    """Aus einer Browser-Meldung das machen, was in die Tabelle darf.

    ``meldung`` kommt vom Client und ist ungeprüft. Erwartet werden ``name``,
    ``message``, ``stack`` und ``route``; fehlt etwas, wird es ersetzt statt
    abgelehnt — eine Fehlermeldung, die selbst an einer Formalie scheitert,
    hilft niemandem.
    """
    typ = saeubern(str(meldung.get("name") or "Error"), laenge=60) or "Error"
    text = saeubern(str(meldung.get("message") or ""))
    roher_stapel = str(meldung.get("stack") or "")
    stapel = saeubern("\n".join(roher_stapel.splitlines()[:BROWSER_STAPEL_ZEILEN]),
                      laenge=2000, zeilen=True)
    route = route_vorlage(None, str(meldung.get("route") or pfad))
    # Ohne echten Traceback wird der Fingerabdruck aus dem gebildet, was da
    # ist: Typ, Route und die ERSTE Stapelzeile (die tiefste Stelle im Code).
    erste = stapel.splitlines()[0] if stapel else text[:80]
    roh = f"browser|{typ}|{erste}|{route}"
    return {
        "fingerprint": hashlib.sha1(roh.encode("utf-8"),
                                    usedforsecurity=False).hexdigest()[:16],
        "exc_type": typ,
        "message": text,
        "route": route,
        "method": "BROWSER",
        "trace": stapel,
        "quelle": "browser",
    }
