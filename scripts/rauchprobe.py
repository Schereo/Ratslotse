"""Nach dem Deploy: Antworten die Endpunkte — und passen sie zum Vertrag?

**Die Lücke, gegen die das steht.** Der Deploy wartet bisher darauf, dass
``/api/health`` und die Startseite antworten. Das ist die Prüfung „läuft der
Prozess". Es ist nicht die Prüfung „tut er das Richtige": Eine Abfrage, die
nach einer Migration auf eine Spalte zeigt, die es nicht mehr gibt, wirft erst
beim ersten echten Aufruf — und `health` fasst die Datenbank nicht an. Genau
diese Klasse fällt sonst erst auf, wenn jemand die Seite öffnet.

**Warum gegen den Vertrag und nicht gegen fest getippte Erwartungen.** Der
Vertrag beschreibt jede Antwortform ohnehin, und er liegt neben dem Code auf
demselben Server. Eine Probe, die ihn liest, altert mit ihm mit; eine Probe
mit eigenen Erwartungen driftet und wird dann abgeschaltet.

**Was geprüft wird.** Nur die Endpunkte ohne Konto — die Probe hat keine
Anmeldedaten und soll auch keine haben. Sie schaut auf die *Form*: Pflichtfeld
vorhanden, Typ passend. Auf den *Inhalt* schaut sie nicht: Ein Tag ohne
Sitzung ist kein Fehler, und eine Probe, die daran scheitert, blockiert
irgendwann einen Deploy grundlos.

Aufruf (auf dem Server, nach dem Neustart)::

    python3 scripts/rauchprobe.py --basis http://127.0.0.1:8000

Rückgabewert 1, sobald eine Probe scheitert. Kein Fremdpaket: Die Probe läuft
mit der Standardbibliothek, damit sie auf jedem Server ohne Vorbereitung geht.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

WURZEL = Path(__file__).resolve().parents[1]
VERTRAG = WURZEL / "api" / "openapi.json"

#: Öffentliche GET-Endpunkte ohne Pfad-Parameter. Die Liste ist bewusst kurz
#: und von Hand gepflegt: Jede Zeile ist eine Zusage, dass dieser Aufruf ohne
#: Konto gehen MUSS — dieselbe Zusage, die ``tests/test_endpunkt_schutz.py``
#: einfriert.
PROBEN: tuple[str, ...] = (
    "/api/health",
    "/api/app-config",
    "/api/council/public-stats",
    "/api/council/heute",
    "/api/council/people-directory",
    "/api/council/qa-beispiele",
)

#: Endpunkte MIT Konto. Bewusst nur die, deren Antwort für alle gleich
#: aussieht: Ratsinhalte, Auswertungen, Haushalt. Nichts Persönliches (Themen,
#: Lesezeichen, Gespräche, Abzeichen) — die Probe soll die Daten einer echten
#: Person nicht anfassen. Und nichts, was schreibt oder Geld kostet: eine
#: Quizrunde legt eine an, die Themen-Vorschläge fragen ein Sprachmodell.
MIT_KONTO: tuple[str, ...] = (
    # Ratsinhalte und Auswertungen
    "/api/council/decisions",
    "/api/council/sessions",
    "/api/council/committees",
    "/api/council/fields",
    "/api/council/parties",
    "/api/council/districts",
    "/api/council/places",
    "/api/council/entities",
    "/api/council/entities-map",
    "/api/council/members",
    "/api/council/finance",
    "/api/council/goals",
    "/api/council/trends",
    "/api/council/analysis",
    "/api/council/field-recaps",
    "/api/council/week-preview",
    "/api/council/diese-woche",
    "/api/council/daily-find",
    "/api/council/zahl-der-woche",
    "/api/council/session-break",
    "/api/quiz/areas",
    # Haushalt: 21 Schichten, jede über eigene Tabellen. Genau die Fläche, die
    # eine Migration trifft — und die einzige, die sie nach dem Deploy anfasst.
    "/api/council/budget",
    "/api/council/budget/amendment-lists",
    "/api/council/budget/assets",
    "/api/council/budget/audit-reports",
    "/api/council/budget/balance-sheet",
    "/api/council/budget/comparison",
    "/api/council/budget/data-status",
    "/api/council/budget/debate",
    "/api/council/budget/debt",
    "/api/council/budget/documents",
    "/api/council/budget/execution",
    "/api/council/budget/group",
    "/api/council/budget/investment-programme",
    "/api/council/budget/investments",
    "/api/council/budget/journey",
    "/api/council/budget/liquidity",
    "/api/council/budget/loans",
    # `budget/products` fehlt hier bewusst: Es verlangt ein Pflicht-Jahr in
    # der Abfrage, und eine fest eingetragene Jahreszahl wäre eine Probe mit
    # Verfallsdatum. Der Test unten hält fest, dass keine Probe einen
    # Pflichtparameter hat — sonst meldet sie für immer 422.
    "/api/council/budget/shareholdings",
    "/api/council/budget/staff-plan",
)

#: Proben, deren Pfad einen Wert braucht, den eine frühere Probe liefert.
#: ``(Muster, Quell-Pfad, Schlüsselpfad in deren Antwort)``. Fehlt der Wert —
#: an einem Tag ohne Sitzung etwa —, entfällt die Probe, sie scheitert nicht.
ABGELEITET: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("/api/council/person/{slug}", "/api/council/people-directory",
     ("people", "0", "slug")),
    # Die Reden hängen an der FTS-Tabelle und an einem Join über die Sitzungen —
    # der Aufruf fasst also mehr an als jede andere öffentliche Seite.
    ("/api/council/person/{slug}/speeches", "/api/council/people-directory",
     ("people", "0", "slug")),
)


# ------------------------------------------------------------------ Vertrag

class Vertrag:
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.schemata = spec.get("components", {}).get("schemas", {})

    def auf(self, s: dict) -> dict:
        while "$ref" in s:
            s = self.schemata[s["$ref"].rsplit("/", 1)[-1]]
        return s

    def antwortschema(self, pfad: str) -> dict | None:
        op = (self.spec["paths"].get(pfad) or {}).get("get")
        if not op:
            return None
        for kode, antwort in (op.get("responses") or {}).items():
            if kode.startswith("2"):
                inhalt = (antwort.get("content") or {}).get("application/json")
                if inhalt and inhalt.get("schema"):
                    return inhalt["schema"]
        return None

    def pruefe(self, wert: Any, schema: dict, wo: str = "") -> list[str]:
        """Fehlerliste — leer heißt: die Form passt."""
        s = self.auf(schema)

        for schluessel in ("anyOf", "oneOf"):
            if schluessel in s:
                for teil in s[schluessel]:
                    if not self.pruefe(wert, teil, wo):
                        return []
                return [f"{wo or '/'}: keine der erlaubten Formen passt"]
        if "allOf" in s:
            return [f for teil in s["allOf"] for f in self.pruefe(wert, teil, wo)]

        # `type` darf im Schema eine LISTE sein (`["string", "null"]`) — ein
        # einzelner Vergleich stolpert darüber, und `typ in PASST` wirft.
        typ = s.get("type")
        if isinstance(typ, list):
            for einzeln in typ:
                if not self.pruefe(wert, {**s, "type": einzeln}, wo):
                    return []
            return [f"{wo or '/'}: passt zu keinem von {typ}"]
        if typ == "null":
            return [] if wert is None else [f"{wo or '/'}: erwartet null"]
        if wert is None:
            # Ein `null` ohne ausdrückliche Erlaubnis: Das ist die Klasse, die
            # in der App als Abbruch beim Decodieren ankommt.
            return [] if typ is None else [f"{wo or '/'}: null, erwartet {typ}"]

        PASST = {
            "object": dict, "array": list, "string": str,
            "integer": int, "number": (int, float), "boolean": bool,
        }
        if typ in PASST:
            # `bool` ist in Python ein `int` — ohne diese Ausnahme geht ein
            # `true` als Zahl durch.
            falsch = not isinstance(wert, PASST[typ]) or (
                typ in ("integer", "number") and isinstance(wert, bool))
            if falsch:
                return [f"{wo or '/'}: {type(wert).__name__}, erwartet {typ}"]

        fehler: list[str] = []
        if typ == "object" or "properties" in s:
            for pflicht in s.get("required") or []:
                if pflicht not in wert:
                    fehler.append(f"{wo}/{pflicht}: fehlt")
            for name, unter in (s.get("properties") or {}).items():
                if name in wert:
                    fehler += self.pruefe(wert[name], unter, f"{wo}/{name}")
        elif typ == "array" and s.get("items"):
            # Nur die ersten Einträge: Die Form ist bei allen dieselbe, und
            # eine Probe soll Sekunden dauern, nicht Minuten.
            for i, eintrag in enumerate(wert[:3]):
                fehler += self.pruefe(eintrag, s["items"], f"{wo}[{i}]")
        return fehler


# ------------------------------------------------------------- Anmeldung

def env_lesen(datei: Path) -> dict[str, str]:
    """``.env`` als Wörterbuch. Absichtlich naiv — hier steht kein Shell-Code."""
    werte: dict[str, str] = {}
    if not datei.exists():
        return werte
    for zeile in datei.read_text().splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        name, wert = zeile.split("=", 1)
        werte[name.strip()] = wert.strip().strip("\"'")
    return werte


def kontendatenbank(wurzel: Path, env: dict[str, str]) -> Path | None:
    """Die Datei, die die laufende App benutzt — nach derselben Regel wie sie.

    ``kern/store.py::_umzug_von_nwz`` behandelt eine **leere** Zieldatei als
    „nicht da": Sie entsteht, sobald irgendwer den neuen Pfad einmal öffnet,
    und lag auf Prod monatelang neben der gefüllten alten. Wer hier nur auf
    Existenz prüft, liest eine Datenbank ohne Tabellen und meldet „Konto nicht
    gefunden", während die App bestens läuft.
    """
    gesetzt = env.get("RATSLOTSE_DB") or os.environ.get("RATSLOTSE_DB")
    if gesetzt:
        return Path(gesetzt).expanduser()
    for name in ("ratslotse.sqlite", "nwz.sqlite"):
        pfad = wurzel / "data" / name
        if pfad.exists() and pfad.stat().st_size:
            return pfad
    return None


def _b64(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).decode().rstrip("=")


def token_bauen(wurzel: Path, konto: str | None) -> tuple[str | None, str]:
    """``(Token, Konto-Nummer oder Begründung)`` — ein kurzlebiges Token.

    Bewusst **kein** gespeichertes Token: Die Probe baut sich auf dem Server
    selbst eines, gültig fünf Minuten. Dazu braucht sie nur das Signier-
    geheimnis und die Konto-Zeile — beides liegt dort ohnehin. Die Formel ist
    dieselbe wie in ``web/backend/app/security.py`` und kommt mit der
    Standardbibliothek aus (HMAC-SHA256).
    """
    env = env_lesen(wurzel / ".env")
    geheimnis = env.get("WEB_JWT_SECRET") or os.environ.get("WEB_JWT_SECRET", "")
    adresse = konto or env.get("RAUCHPROBE_KONTO") or env.get("WEB_ADMIN_EMAIL", "")
    if not geheimnis:
        return None, "kein WEB_JWT_SECRET"
    if not adresse:
        return None, "kein Konto (RAUCHPROBE_KONTO oder WEB_ADMIN_EMAIL)"
    datenbank = kontendatenbank(wurzel, env)
    if datenbank is None:
        return None, "keine Konten-Datenbank gefunden"
    # Die Falle mit `mode=ro` und WAL steht in `kern.dbfehler.nur_lesen`
    # erklärt — hier wird sie nur benutzt.
    sys.path.insert(0, str(WURZEL))
    from kern.dbfehler import nur_lesen

    verbindung = None
    try:
        verbindung = nur_lesen(datenbank)
        zeile = verbindung.execute(
            "SELECT id, token_version FROM web_users WHERE lower(email) = lower(?)",
            (adresse,),
        ).fetchone()
    except sqlite3.Error as fehler:
        return None, f"Konten-Datenbank nicht lesbar ({fehler})"
    finally:
        if verbindung is not None:
            verbindung.close()

    if not zeile:
        # Ohne die Adresse: Die Meldung landet im Deploy-Log, und das Repo ist
        # öffentlich. Wer den Fehler sucht, weiß, welche er eingetragen hat.
        return None, "das eingetragene Konto gibt es nicht"

    kopf = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    nutz = _b64(json.dumps(
        {"sub": str(zeile[0]), "exp": int(time.time()) + 300, "ver": zeile[1]}
    ).encode())
    signiert = f"{kopf}.{nutz}".encode()
    zeichen = _b64(hmac.new(geheimnis.encode(), signiert, hashlib.sha256).digest())
    # Zurück kommt die KONTO-NUMMER, nicht die Adresse — aus demselben Grund.
    return f"{kopf}.{nutz}.{zeichen}", f"Konto {zeile[0]}"


# ------------------------------------------------------------------- Abruf

def hole(basis: str, pfad: str, zeitlimit: float,
         token: str | None = None) -> tuple[int, Any]:
    kopfzeilen = {"User-Agent": "ratslotse-rauchprobe"}
    if token:
        kopfzeilen["Authorization"] = f"Bearer {token}"
    anfrage = urllib.request.Request(basis.rstrip("/") + pfad, headers=kopfzeilen)
    try:
        with urllib.request.urlopen(anfrage, timeout=zeitlimit) as antwort:
            roh = antwort.read()
            return antwort.status, json.loads(roh) if roh else None
    except urllib.error.HTTPError as fehler:
        return fehler.code, None
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        # Kein Traceback im Deploy-Log: Der Dienst antwortet nicht, und das
        # ist genau das, was hier stehen soll.
        return 0, str(fehler)
    except json.JSONDecodeError:
        return -1, None


def tiefer(daten: Any, weg: tuple[str, ...]) -> Any:
    for stufe in weg:
        if isinstance(daten, list):
            i = int(stufe)
            daten = daten[i] if i < len(daten) else None
        elif isinstance(daten, dict):
            daten = daten.get(stufe)
        else:
            return None
        if daten is None:
            return None
    return daten


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis", default="http://127.0.0.1:8000",
                   help="Wurzel des laufenden Backends")
    p.add_argument("--zeitlimit", type=float, default=20.0)
    p.add_argument("--konto", help="E-Mail für die Proben MIT Konto "
                                   "(Vorgabe: RAUCHPROBE_KONTO, sonst WEB_ADMIN_EMAIL)")
    args = p.parse_args(argv)

    vertrag = Vertrag(json.loads(VERTRAG.read_text()))
    antworten: dict[str, Any] = {}
    schlecht = 0
    token, woher = token_bauen(WURZEL, args.konto)

    def lauf(paare, mit_token=None):
        nonlocal schlecht
        for muster, pfad in paare:
            kode, daten = hole(args.basis, pfad, args.zeitlimit, mit_token)
            if kode != 200:
                grund = {0: f"nicht erreichbar ({daten})",
                         -1: "Antwort ist kein JSON"}.get(kode, f"HTTP {kode}")
                print(f"  ✗ {pfad}  {grund}")
                schlecht += 1
                continue
            antworten[muster] = daten
            schema = vertrag.antwortschema(muster)
            if schema is None:
                print(f"  – {pfad}  (keine Antwortform im Vertrag)")
                continue
            fehler = vertrag.pruefe(daten, schema)
            if fehler:
                print(f"  ✗ {pfad}")
                for f in fehler[:8]:
                    print(f"      {f}")
                if len(fehler) > 8:
                    print(f"      … und {len(fehler) - 8} weitere")
                schlecht += 1
            else:
                print(f"  ✓ {pfad}")

    print(f"Rauchprobe gegen {args.basis}")
    print("\nohne Konto:")
    lauf([(pfad, pfad) for pfad in PROBEN])

    # Proben, deren Pfad erst aus einer Antwort von oben entsteht.
    nachgereicht = []
    for muster, quelle, weg in ABGELEITET:
        wert = tiefer(antworten.get(quelle), weg)
        if wert is not None:
            name = muster.split("{")[1].split("}")[0]
            nachgereicht.append((muster, muster.format(**{name: wert})))
    if nachgereicht:
        lauf(nachgereicht)

    if token:
        print(f"\nmit Konto ({woher}):")
        lauf([(pfad, pfad) for pfad in MIT_KONTO], token)
    else:
        # Kein Abbruch: Die Proben ohne Konto sind das Gate, die mit Konto sind
        # die Kür. Eine Umgebung ohne `.env` (ein Notebook etwa) soll die Probe
        # trotzdem fahren können.
        print(f"\nmit Konto: übersprungen — {woher}")

    if schlecht:
        print(f"\n{schlecht} Probe(n) gescheitert.")
        return 1
    print(f"\n{len(antworten)} Probe(n) in Ordnung.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
