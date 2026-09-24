#!/usr/bin/env python3
"""Fakten-Eval für Lotti und Frag den Rat: Kontextfehler und Modellfehler getrennt.

Tim, 23.09.2026: „Die Haushaltsfragen werden sehr, sehr wichtig werden in
nächster Zeit. … Wenn wir im Kontext schon Mist haben, kann das beste Modell
ja nichts Gutes draus machen.“ Diese Eval beantwortet deshalb je Fall zwei
Fragen getrennt: **Stand der Goldfakt im Prompt** (unter dem richtigen Jahr)?
Und **nennt die Antwort ihn**? Die Einteilung und ihre Regeln stehen in
``eval/fakten_abgleich.py``; der Bericht in ``docs/fakten-eval.md``.

**Der echte Codepfad, nicht ein Nachbau.** Der Lauf startet ein eigenes
Backend (uvicorn, freier Port, eigene Konten-Datenbank aus
``scripts/saat_konten.py``), meldet sich als ``ratsfrau@example.org`` an und
stellt jede Frage über ``POST /api/council/explain`` (Lotti) bzw.
``POST /api/council/ask`` (Frag den Rat) — genau wie das Fenster im Browser.
Den Prompt liest er aus dem Mitschnitt (``RATSLOTSE_PROMPT_MITSCHNITT`` in
``kern/llm.py``), also den, den das Modell wirklich bekam. Der Faktencheck
vom 23.09. hatte Lottis Kontext noch rekonstruiert; den von Frag den Rat,
den der Router aus Retrieval, Presse und Haushaltszahlen zusammensetzt,
konnte er gar nicht nachbauen.

**Beide Kanäle, ein Modell.** Der Lauf setzt ``COUNCIL_ASSISTANT_MODEL`` UND
``COUNCIL_QA_MODEL`` auf das gewählte Modell. Die Analyse der Frage
(``COUNCIL_QA_EXPAND_MODEL``) bleibt, wo sie ist: Sie gehört zum Kontext-
Aufbau, und der soll zwischen zwei Modellen gleich sein. Welches Modell
WIRKLICH geantwortet hat, prüft der Lauf am Mitschnitt (Feld ``model`` und
das ``model`` der OpenRouter-Antwort) und bricht ab, wenn es nicht passt —
die gemessene Falle: zsh spaltet ``$VAR`` mit mehreren ``A=b`` nicht auf,
und ein Lauf maß dann still das heutige Modell.

**Nacheinander, nicht parallel.** Welche Mitschnitt-Zeilen zu welchem Fall
gehören, ergibt sich aus der Reihenfolge. Zwei Modelle parallel = zwei
Prozesse mit zwei Backends.

Aufruf::

    python eval/run_fakten.py --modell openai/gpt-6-luna --ohne-zdr
    python eval/run_fakten.py --modell google/gemini-2.5-flash --limit 10   # Kosten hochrechnen
    python eval/run_fakten.py --modell … --nur hh-schulden-stand,hh-invest-ist-2025
    python eval/run_fakten.py nachwerten eval/results/fakten/<lauf>.json  # ohne neue Aufrufe
    python eval/run_fakten.py bericht                                      # docs/fakten-eval.md
    python eval/pruefstand.py --suite fakten-haushalt --modell google/gemini-2.5-flash

``--ohne-zdr`` setzt ``NWZ_OPENROUTER_ZDR=0`` NUR im Mess-Backend: GPT-6
Luna hat keinen ZDR-Anbieter (Tims Entscheidung vom 23.09. für Lotti und Frag
den Rat); die Fälle sind eigene Fragen, keine Nutzerdaten. **Für GPT-6 Luna
seit dem 23.09.2026 abends überflüssig und irreführend:** Lotti und Frag den
Rat gehen zuerst an Azure EU mit ZDR (``kern/llm.py::EU_ZUERST``); der
Schalter nähme diesem Weg das ZDR-Merkmal, und der Lauf mäße nicht mehr das
Routing des Betriebs. Ob ein Fall über den Rückfall lief, steht im
Mitschnitt (``provider``, ``fallback``).

**Die ausführliche Recherche** (``--kanal deep``, 23.09.2026): Jeder Fall
geht dann, egal welchem Kanal er gehört, als Job an ``POST
/api/council/deep-research``; der Lauf fragt den Job ab, bis er fertig ist,
und wertet den Bericht aus. Den Kontext bilden ALLE Prompts des Jobs
(Analyse, Zerlegung, Bericht) — nicht nur der letzte. ``--auswahl deep``
nimmt die Fälle, für die sich eine Recherche lohnt (``AUSWAHL["deep"]``),
``--aufwand`` setzt den Denkaufwand (``RATSLOTSE_WEB_DENKAUFWAND``) im
Mess-Backend. Das Tageskontingent hebt der Lauf über denselben Weg auf, den
ein Admin im Panel nimmt (``web_users.deep_limit = 0``) — in der
Wegwerf-Kontendatenbank, ohne Messschalter im Betriebscode::

    python eval/run_fakten.py --kanal deep --auswahl deep --modell openai/gpt-6-luna --ohne-zdr
    python eval/run_fakten.py --kanal deep --auswahl deep --modell openai/gpt-6-luna --ohne-zdr --aufwand high
    python eval/run_fakten.py bericht --kanal deep        # Vergleichstabelle auf stdout
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import fakten_abgleich as fa  # noqa: E402

FAELLE_DATEIEN = (WURZEL / "eval" / "cases_fakten_haushalt.json",
                  WURZEL / "eval" / "cases_fakten_rat.json")
ERGEBNISSE = WURZEL / "eval" / "results" / "fakten"
BERICHT = WURZEL / "docs" / "fakten-eval.md"
#: Die vollen Prompts eines Laufs — zu groß fürs Repo (rund 15 kB je Fall),
#: aber nötig fürs Nachwerten ohne neue Aufrufe. Liegt neben den anderen
#: lokalen Abzügen.
MITSCHNITT_ABLAGE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") \
    / "ratslotse" / "fakten-mitschnitt"
KONTO = ("ratsfrau@example.org", "password123")
MITSCHNITT_ENV = "RATSLOTSE_PROMPT_MITSCHNITT"
#: Wie ``kern.llm.WEB_DENKAUFWAND_ENV`` — hier als Text, damit der Runner
#: ohne ``kern`` importierbar bleibt.
DENKAUFWAND_ENV = "RATSLOTSE_WEB_DENKAUFWAND"
#: Die Features, deren Prompt die Antwort trägt — je Kanal.
ANTWORT_FEATURES = ("assistant_explain", "qa_answer", "qa_simple", "deep_report")
#: Die Recherche-Läufe liegen in einem eigenen Ordner: Sie messen eine
#: Teilmenge über einen anderen Weg, und ``bericht`` (docs/fakten-eval.md)
#: soll sie nicht neben die Gesamtläufe stellen.
ERGEBNISSE_DEEP = ERGEBNISSE / "deep"
#: Wie lange ein Recherche-Job höchstens laufen darf, bevor er als Ausfall
#: zählt. Gemessen (23.09.2026): p95 29 s (Sol) bis 83 s (Luna ``xhigh``).
DEEP_FRIST_S = 900

#: Benannte Fallauswahlen (``--auswahl``). ``deep``: die Fälle, für die sich
#: eine ausführliche Recherche lohnt — Verläufe, Vergleiche, Plan gegen Ist,
#: Kosten samt Finanzierung, Verwechslungsfallen und „nicht in den Daten“.
#: Nur Fälle aus Frag den Rat: Lottis Fälle hängen an der Seite, auf der die
#: Frage fällt, und die Recherche kennt keine Seite. Einfache Nachschlage-
#: Fragen (ein Wert, ein Name, ein Termin) fehlen bewusst — dafür gibt es die
#: schnelle Frage.
AUSWAHL: dict[str, tuple[str, ...]] = {
    "deep": (
        # Haushalt: Verläufe, Plan gegen Ist, Vergleiche, Gründe
        "hh-schulden-entwicklung-rat", "hh-schulden-rekord-rat", "hh-schulden-konzern-rat",
        "hh-buergschaften-rat", "hh-kredite-2026-rat", "hh-plan-defizit-2026-rat",
        "hh-plan-groesster-bereich-rat", "hh-ist-gruende-2024-rat", "hh-vollzug-2026-rat",
        "hh-vollzug-2025-rat", "hh-invest-plan-ist-rat", "hh-invest-vorhaben-rat",
        "hh-invest-ist-2025-rat", "hh-gewst-plan-ist-2024-rat", "hh-hebesatz-entwicklung-rat",
        "hh-gebuehr-abfall-kosten-rat", "hh-vergleich-gewst-hebesatz-rat",
        "hh-aenderungsliste-2026-rat", "hh-haushalt-entwurf-final-rat", "hh-spielraum-rat",
        "hh-rpa-rat", "hh-nachbewilligung-2025-rat", "hh-stadion-gesellschaft-rat",
        # Haushalt: nicht in den Daten
        "hh-nd-schulden-wolfsburg-rat", "hh-nd-schulden-2030-rat", "hh-nd-gewst-2026-rat",
        # Rat: Verläufe und Kosten samt Finanzierung
        "rat-stadion-was-beschlossen", "rat-stadion-kosten-wer-zahlt",
        "rat-stadion-eu-genehmigung", "rat-stadion-fertigstellung",
        "rat-stadion-einwohnerbefragung", "rat-stadion-wer-dagegen",
        "rat-fliegerhorst-zuletzt", "rat-radverkehr-plaene", "rat-haareneschstrasse",
        "rat-schwimmbad-zuletzt", "rat-grundsteuer-entwicklung", "rat-grundsteuer-mehrertrag",
        "rat-waermeplan", "rat-baumschutzsatzung", "rat-sechsfeldhalle-kosten",
        # Rat: Verwechslungsfallen
        "rat-stadion-grundsatzbeschluss", "rat-fliegerhorst-dreifeldhalle-kosten",
        "rat-quellenweg-fahrradstrasse", "rat-btb-zuschuss-2027", "rat-tangentialbus-praemisse",
        "rat-grundsteuer-490-prozent", "rat-kongresshalle-kosten", "rat-kongresshalle-buergschaft",
        "rat-zweckentfremdungssatzung", "rat-vbn-tarif-2024", "rat-eigenreinigung",
        # Rat: nicht in den Daten
        "rat-nd-einzelstimme-baak", "rat-nd-grundsteuer-c", "rat-nd-gehalt-stadion-gf",
    ),
}


def lade(pfade: list[Path] | None = None) -> list[dict]:
    faelle: list[dict] = []
    for pfad in pfade or [p for p in FAELLE_DATEIEN if p.exists()]:
        faelle += json.loads(pfad.read_text(encoding="utf-8"))
    return faelle


# --------------------------------------------------------------------------- #
# Das Mess-Backend
# --------------------------------------------------------------------------- #

def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _uvicorn() -> str:
    kandidat = Path(sys.executable).parent / "uvicorn"
    if kandidat.exists():
        return str(kandidat)
    gefunden = shutil.which("uvicorn")
    if not gefunden:
        raise SystemExit("Kein uvicorn neben diesem Python — im venv starten.")
    return gefunden


#: Lottis Selbstprüfung (``council/self_check.py``) bleibt im Mess-Backend
#: AUS: Sie ist eine stille Stichprobe nach der Antwort und ändert nichts an
#: dem, was gemessen wird — kostete aber je gezogene Antwort einen
#: Prüfer-Aufruf. Die Selbstprüfung misst ``eval/run_selbstpruefung.py``.
SELBSTPRUEFUNG = "lotti-selbstpruefung"


def _schalter() -> str:
    """``FEATURE_FLAGS`` fürs Mess-Backend: alle Schalter außer der Selbstprüfung."""
    from kern import features
    return ",".join(k for k in features.FEATURES if k != SELBSTPRUEFUNG)


@contextmanager
def backend(modell: str, mitschnitt: Path, *, ohne_zdr: bool,
            protokoll: Path, aufwand: str | None = None) -> Iterator[str]:
    """Ein eigenes Backend für den Lauf; gibt die Basis-Adresse zurück."""
    with tempfile.TemporaryDirectory(prefix="fakten-konten-") as tmp:
        konten = Path(tmp) / "ratslotse.sqlite"
        rat = Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite")
        subprocess.run([sys.executable, str(WURZEL / "scripts" / "saat_konten.py"),
                        "--db", str(konten), "--council-db", str(rat)],
                       check=True, capture_output=True, cwd=WURZEL)
        kontingent_aufheben(konten)
        port = _freier_port()
        env = {
            **os.environ,
            "COUNCIL_DB": str(rat),
            "RATSLOTSE_DB": str(konten),
            "WEB_JWT_SECRET": "nur-fuer-die-fakten-eval",
            "DISABLE_RATE_LIMIT": "1",
            "FEATURE_FLAGS": _schalter(),
            MITSCHNITT_ENV: str(mitschnitt),
            "COUNCIL_ASSISTANT_MODEL": modell,
            "COUNCIL_QA_MODEL": modell,
            "COUNCIL_DEEP_MODEL": modell,
        }
        # Ohne Angabe gilt, was im Code steht — auch wenn die eigene Shell
        # den Schalter noch von einem früheren Lauf trägt.
        env.pop(DENKAUFWAND_ENV, None)
        if aufwand:
            env[DENKAUFWAND_ENV] = aufwand
        # Die Kosten landen in der Datei des Aufrufers (Prüfstand: eigene
        # je Lauf); ohne Vorgabe neben dem Mitschnitt, nie in der echten.
        env["RATSLOTSE_SQLITE"] = str(kostendatei(mitschnitt))
        if ohne_zdr:
            env["NWZ_OPENROUTER_ZDR"] = "0"
        with protokoll.open("w") as log:
            proz = subprocess.Popen(
                [_uvicorn(), "app.main:app", "--port", str(port), "--log-level", "warning"],
                cwd=WURZEL / "web" / "backend", env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        basis = f"http://127.0.0.1:{port}"
        try:
            frist = time.time() + 60
            while time.time() < frist:
                if proz.poll() is not None:
                    raise SystemExit(f"Backend ging sofort aus: {protokoll.read_text()[-1500:]}")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.5)
            else:
                raise SystemExit(f"Backend antwortet nach 60 s nicht ({protokoll})")
            yield basis
        finally:
            proz.terminate()
            try:
                proz.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proz.kill()


def kontingent_aufheben(konten: Path, email: str = KONTO[0]) -> None:
    """Das Tageskontingent der Recherche (5 je Konto) für das Messkonto aus.

    Derselbe Weg wie im Admin-Panel (``web_users.deep_limit = 0`` heißt
    „unbegrenzt“, ``routers/council.py::_deep_limit``) — in der Wegwerf-
    Datenbank dieses Laufs. Ein Messschalter im Router wäre eine Stelle mehr,
    an der der Betrieb das Kontingent verlieren könnte.
    """
    import sqlite3
    con = sqlite3.connect(konten)
    try:
        con.execute("UPDATE web_users SET deep_limit = 0 WHERE email = ?", (email,))
        con.commit()
    finally:
        con.close()


def kostendatei(mitschnitt: Path) -> Path:
    vorgabe = os.environ.get("RATSLOTSE_SQLITE")
    return Path(vorgabe) if vorgabe else mitschnitt / "usage.sqlite"


def kosten_seit(datei: Path, marke: str) -> dict:
    """Was der Lauf laut ``llm_usage`` kostete — je Feature und Modell.

    Die echten Kosten, die OpenRouter mitschickt (``kern/usage``), nicht
    ``PRICES``. Ohne Kostenwert zählt der Aufruf in ``ohne_kosten``.
    """
    import sqlite3
    if not datei.exists():
        return {"usd": 0.0, "aufrufe": 0, "ohne_kosten": 0, "je": {}}
    con = sqlite3.connect(f"file:{datei}?mode=ro", uri=True)
    try:
        zeilen = con.execute(
            "SELECT feature, model, COUNT(*), SUM(COALESCE(cost_usd, 0)), "
            "SUM(cost_usd IS NULL) FROM llm_usage WHERE ts >= ? GROUP BY feature, model",
            (marke,)).fetchall()
    except sqlite3.Error:
        zeilen = []
    finally:
        con.close()
    return {"usd": round(sum(z[3] for z in zeilen), 4), "aufrufe": sum(z[2] for z in zeilen),
            "ohne_kosten": sum(z[4] for z in zeilen),
            "je": {f"{z[0]} · {z[1]}": {"aufrufe": z[2], "usd": round(z[3], 4)} for z in zeilen}}


def anmelden(basis: str) -> Any:
    import httpx
    client = httpx.Client(base_url=basis, timeout=httpx.Timeout(300, connect=10))
    r = client.post("/api/auth/login", json={"email": KONTO[0], "password": KONTO[1]})
    r.raise_for_status()
    # Das Cookie ist „Secure“ und ginge über http nicht zurück — als Bearer.
    token = r.cookies.get("access_token")
    if not token:
        raise SystemExit("Anmeldung ohne access_token-Cookie")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def _strom(client: Any, pfad: str, body: dict) -> dict:
    t0 = time.perf_counter()
    text, done, fehler, ersetzt = "", {}, None, False
    with client.stream("POST", pfad, json=body) as r:
        if r.status_code != 200:
            return {"text": "", "done": {}, "fehler": f"HTTP {r.status_code}: {r.read()[:300]!r}",
                    "ms": round((time.perf_counter() - t0) * 1000)}
        for zeile in r.iter_lines():
            if not zeile.startswith("data:"):
                continue
            try:
                d = json.loads(zeile[5:])
            except ValueError:
                continue
            if d.get("type") == "token":
                text += d.get("text", "")
            elif d.get("type") == "replace":
                text, ersetzt = d.get("text", ""), True
            elif d.get("type") == "done":
                done = d
            elif d.get("type") == "error":
                fehler = str(d.get("message") or d)
    return {"text": text.strip(), "done": done, "fehler": fehler, "ersetzt": ersetzt,
            "ms": round((time.perf_counter() - t0) * 1000)}


class Mitschnitt:
    """Liest die Zeilen, die seit dem letzten Aufruf dazugekommen sind."""

    def __init__(self, ordner: Path) -> None:
        self.ordner = ordner
        self.stand: dict[str, int] = {}

    def neu(self) -> list[dict]:
        aus: list[dict] = []
        for pfad in sorted(self.ordner.glob("*.jsonl")):
            zeilen = pfad.read_text(encoding="utf-8").splitlines()
            vorher = self.stand.get(pfad.name, 0)
            aus += [json.loads(z) for z in zeilen[vorher:] if z.strip()]
            self.stand[pfad.name] = len(zeilen)
        return sorted(aus, key=lambda z: z.get("ts", 0))


def prompt_text(aufruf: dict) -> str:
    teile = []
    for m in aufruf.get("messages") or []:
        inhalt = m.get("content")
        if isinstance(inhalt, list):
            inhalt = "\n".join(str(t.get("text", "")) for t in inhalt if isinstance(t, dict))
        teile.append(f"[{m.get('role')}]\n{inhalt}")
    return "\n\n".join(teile)


def frage_stellen(client: Any, fall: dict) -> dict:
    """Eine Frage über den Weg, den das Fenster bzw. die Seite nimmt."""
    if fall["kanal"] == "lotti":
        # Das Fenster schickt Titel und Überschrift der Seite mit; auf den
        # Haushalts-Seiten ziehen sie eigene Facetten („Wie viel Schulden hat
        # Oldenburg?“ zieht die Schulden auch zu einer Investitionsfrage).
        # `page_title` und `anchors`, wo der Fall sie trägt (die Laienfälle,
        # abgelesen am echten Fenster): Bis 24.09.2026 schickte die Eval als
        # Seitentitel die Überschrift und keine Bausteine — also einen anderen
        # Prompt als das Fenster.
        body = {"route": fall["route"], "question": fall["frage"], "refs": fall.get("refs") or {},
                "page_title": fall.get("page_title") or fall.get("heading", ""),
                "heading": fall.get("heading", ""), "anchors": fall.get("anchors") or []}
        erg = _strom(client, "/api/council/explain", body)
        erg["weg"] = (erg.get("done") or {}).get("mode") or "?"
        # Gehört die Frage ins Archiv, geht das Fenster von selbst zu Frag den
        # Rat — mit dem Bildschirm. Genau das tut die Eval auch.
        if erg["weg"] == "handoff" or (erg.get("done") or {}).get("next") == "ratsfrage":
            davor = erg["text"]
            weiter = _strom(client, "/api/council/ask", {
                "question": fall["frage"],
                "screen": {"route": fall["route"], **({"refs": fall["refs"]} if fall.get("refs") else {})}})
            weiter["weg"] = f"{erg['weg']}→ask"
            weiter["text"] = (davor + "\n\n" + weiter["text"]).strip()
            weiter["ms"] += erg["ms"]
            return weiter
        return erg
    erg = _strom(client, "/api/council/ask", {"question": fall["frage"]})
    erg["weg"] = "ask"
    return erg


def recherche_stellen(client: Any, fall: dict, *, frist_s: float = DEEP_FRIST_S,
                      takt_s: float = 3.0) -> dict:
    """Eine Frage als ausführliche Recherche — Job anlegen, abfragen bis fertig.

    Abgefragt wird der gespeicherte Stand (``GET …/{id}``), nicht der SSE-
    Strom: Das ist der Weg, auf dem die App einen fertigen Bericht nach dem
    Zurückkommen holt, und er kennt keine Zwischenstände, die man falsch
    zusammensetzen könnte. Danach „gesehen“ — sonst stieße der Job eine
    Fertig-Meldung an.
    """
    t0 = time.perf_counter()

    def ms() -> int:
        return round((time.perf_counter() - t0) * 1000)

    r = client.post("/api/council/deep-research", json={"question": fall["frage"]})
    if r.status_code == 400 and (r.json() or {}).get("unclear"):
        # Die Rückfrage ist eine Antwort, kein Ausfall: Die Frage war dem
        # Riegel zu unbestimmt, ein Bericht entsteht nicht.
        return {"text": str(r.json().get("detail") or ""), "done": {}, "fehler": None,
                "ms": ms(), "weg": "rueckfrage", "status": "rueckfrage"}
    if r.status_code != 201:
        return {"text": "", "done": {}, "fehler": f"HTTP {r.status_code}: {r.text[:300]}",
                "ms": ms(), "weg": "deep", "status": None}
    job_id = r.json()["job_id"]
    zeile: dict = {}
    while time.perf_counter() - t0 < frist_s:
        time.sleep(takt_s)
        s = client.get(f"/api/council/deep-research/{job_id}")
        if s.status_code != 200:
            continue
        zeile = s.json()
        if zeile.get("status") != "laeuft":
            break
    else:
        client.post(f"/api/council/deep-research/{job_id}/stop")
        return {"text": zeile.get("report") or "", "done": {}, "ms": ms(), "weg": "deep",
                "fehler": f"Frist {frist_s:.0f} s überschritten", "status": "frist"}
    client.post(f"/api/council/deep-research/{job_id}/seen")
    status = zeile.get("status")
    quellen = zeile.get("sources") or {}
    return {"text": (zeile.get("report") or "").strip(), "ms": ms(), "weg": "deep",
            "status": status, "fehler": None if status == "fertig" else f"Job-Status {status}",
            "done": {"facets": quellen.get("facets"), "cited": quellen.get("cited")}}


def _antwort_aufruf(aufrufe: list[dict]) -> dict | None:
    """Der Aufruf, dessen Antwort gezeigt wurde: der letzte eines Antwort-Features."""
    passend = [a for a in aufrufe if a.get("feature") in ANTWORT_FEATURES and not a.get("aborted")]
    return passend[-1] if passend else None


def _kopfzeilen(kontext: str) -> list[str]:
    """Die Bausteine, die im Prompt standen — ihre Überschriften in Großbuchstaben."""
    aus = []
    for zeile in kontext.splitlines():
        m = re.match(r"^([A-ZÄÖÜ][A-ZÄÖÜ0-9 ,/()\-–—+.]{5,}?)(?=[.(:]|$| —| –)", zeile.strip())
        if m and sum(c.isupper() for c in m.group(1)) >= 5:
            aus.append(m.group(1).strip())
    return list(dict.fromkeys(aus))


def job_kontext(aufrufe: list[dict]) -> str | None:
    """Der Kontext einer Recherche: die Prompts ALLER Aufrufe des Jobs.

    Der Bericht bekommt das gesammelte Material, aber was in den Facetten-
    Schritten stand, gehört ebenso zum Kontext — ein Fakt, den irgendein
    Schritt sah, war da. Abgerissene Ströme zählen mit: Ihr Prompt ist
    derselbe wie der des neuen Anlaufs.
    """
    teile = [prompt_text(a) for a in aufrufe if a.get("messages")]
    return "\n\n".join(teile) if teile else None


def _perzentil(werte: list[float], p: float) -> float | None:
    """Nächster Rang (ohne Interpolation) — bei 50 Fällen ist p95 der 48."""
    if not werte:
        return None
    s = sorted(werte)
    return s[min(len(s) - 1, max(0, math.ceil(p * len(s)) - 1))]


def ein_lauf(modell: str, faelle: list[dict], *, ohne_zdr: bool = False,
             basis: str | None = None, mitschnitt: Path | None = None,
             laut: bool = True, kanal: str | None = None,
             aufwand: str | None = None) -> dict:
    """Alle Fälle einmal — gibt das Rohergebnis (ohne volle Prompts) zurück.

    ``kanal="deep"`` stellt jeden Fall als ausführliche Recherche.
    """
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    lauf_name = (f"{modell.replace('/', '-')}{'-' + kanal if kanal else ''}"
                 f"{'-' + aufwand if aufwand else ''}-{stempel}")
    ordner = mitschnitt or (MITSCHNITT_ABLAGE / lauf_name)
    ordner.mkdir(parents=True, exist_ok=True)
    aus: dict = {"modell": modell, "zeitstempel": stempel, "mitschnitt": str(ordner),
                 "ohne_zdr": ohne_zdr, "faelle": []}
    if kanal:
        aus["kanal"] = kanal
    if aufwand:
        aus["aufwand"] = aufwand
    datei = kostendatei(ordner)
    # Dieselbe Uhr wie `ts` in llm_usage: UTC (s. kern/usage.jetzt_utc).
    marke = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    bisher = [kosten_seit(datei, marke)["usd"]]

    def messen(basis_: str) -> None:
        client = anmelden(basis_)
        schnitt = Mitschnitt(ordner)
        schnitt.neu()  # was vorher drinstand, gehört keinem Fall
        for n, fall in enumerate(faelle, 1):
            try:
                erg = recherche_stellen(client, fall) if kanal == "deep" else frage_stellen(client, fall)
            except Exception as e:  # noqa: BLE001 — ein Ausfall ist ein Messergebnis
                erg = {"text": "", "done": {}, "fehler": f"{type(e).__name__}: {e}", "ms": 0,
                       "weg": "?"}
            aufrufe = schnitt.neu()
            antwort_aufruf = _antwort_aufruf(aufrufe)
            if kanal == "deep":
                kontext = job_kontext(aufrufe) if antwort_aufruf else None
            else:
                kontext = prompt_text(antwort_aufruf) if antwort_aufruf else None
            if antwort_aufruf is not None:
                gefragt = antwort_aufruf.get("model")
                geantwortet = antwort_aufruf.get("response_model") or gefragt or ""
                if gefragt != modell or not geantwortet.startswith(modell.split(":")[0]):
                    raise SystemExit(
                        f"Falsches Modell: bestellt {modell}, angefragt {gefragt}, "
                        f"geantwortet {geantwortet} — der Schalter wirkt nicht.")
            (ordner / "kontexte").mkdir(exist_ok=True)
            if kontext is not None:
                (ordner / "kontexte" / f"{fall['id']}.txt").write_text(kontext, encoding="utf-8")
            zeile = {
                "id": fall["id"], "kanal": fall["kanal"], "kategorie": fall.get("kategorie"),
                "frage": fall["frage"], "route": fall.get("route"),
                "weg": erg.get("weg"), "ms": erg.get("ms"), "fehler": erg.get("fehler"),
                "antwort": erg.get("text", ""),
                "kontext_zeichen": len(kontext) if kontext is not None else None,
                "bausteine": _kopfzeilen(kontext or ""),
                "aufrufe": [a.get("feature") for a in aufrufe],
                "modell_antwort": (antwort_aufruf or {}).get("response_model"),
                "facetten": ((erg.get("done") or {}).get("facets")
                             or (erg.get("done") or {}).get("geld_facets")),
            }
            if kanal == "deep":
                # Nacheinander gemessen: Was die Laufsumme seit dem letzten
                # Fall zugelegt hat, gehört diesem. NICHT „alles seit der
                # Marke des Falls“ — `ts` hat Sekunden, und der Bericht des
                # Vorgängers endet oft in derselben Sekunde, in der dieser
                # Fall beginnt (erste Messung: 6,5 ct je Bericht statt 5,6).
                summe = kosten_seit(datei, marke)["usd"]
                zeile["usd"] = round(summe - bisher[0], 5)
                bisher[0] = summe
                zeile["job_status"] = erg.get("status")
                zeile["finish_reason"] = (antwort_aufruf or {}).get("finish_reason")
                zeile["usage"] = (antwort_aufruf or {}).get("usage")
                zeile["reasoning"] = (antwort_aufruf or {}).get("reasoning")
            zeile.update(fa.bewerten(fall, kontext, zeile["antwort"]))
            aus["faelle"].append(zeile)
            if laut:
                print(f"[{n:3}/{len(faelle)}] {fall['id']:42} {zeile['fehlerart']:28} "
                      f"{zeile['weg']:14} {zeile['ms'] or 0:6} ms"
                      + (f"  {zeile['usd']:.4f} $ {zeile.get('finish_reason')}"
                         if kanal == "deep" else ""), flush=True)

    if basis:
        messen(basis)
    else:
        with backend(modell, ordner, ohne_zdr=ohne_zdr, protokoll=ordner / "backend.log",
                     aufwand=aufwand) as b:
            messen(b)
    aus["kosten"] = kosten_seit(datei, marke)
    aus["kosten_usd"] = aus["kosten"]["usd"]
    aus["kennzahlen"] = kennzahlen(aus["faelle"])
    # Immer auch neben den Mitschnitt — ein Probelauf mit --nicht-speichern
    # soll sich trotzdem nachlesen lassen.
    speichern(aus, ordner / "lauf.json")
    return aus


def nachwerten(erg: dict, faelle: list[dict]) -> dict:
    """Ein gespeicherter Lauf neu bewertet — ohne einen einzigen Aufruf.

    Braucht die vollen Prompts aus ``MITSCHNITT_ABLAGE``; die Regeln im
    Abgleich dürfen sich ändern, ohne dass ein Lauf neu bezahlt wird.
    """
    nach_id = {f["id"]: f for f in faelle}
    ordner = Path(erg["mitschnitt"]) / "kontexte"
    for zeile in erg["faelle"]:
        fall = nach_id.get(zeile["id"])
        if fall is None:
            continue
        pfad = ordner / f"{zeile['id']}.txt"
        kontext = pfad.read_text(encoding="utf-8") if pfad.exists() else None
        if kontext is not None:
            zeile["bausteine"] = _kopfzeilen(kontext)
        zeile.update(fa.bewerten(fall, kontext, zeile["antwort"]))
        zeile["kategorie"] = fall.get("kategorie")
    erg["kennzahlen"] = kennzahlen(erg["faelle"])
    return erg


# --------------------------------------------------------------------------- #
# Kennzahlen und Bericht
# --------------------------------------------------------------------------- #

def kennzahlen(zeilen: list[dict]) -> dict:
    n = len(zeilen)
    arten = Counter(z["fehlerart"] for z in zeilen)
    ms = sorted(z["ms"] for z in zeilen if z.get("ms"))
    aus = {
        "n_cases": n,
        "ok": arten.get("ok", 0),
        "quote_ok": round(arten.get("ok", 0) / n, 4) if n else None,
        "kontext_ok": sum(1 for z in zeilen if z["kontext_ok"]),
        "fehlerarten": dict(arten),
        "modellfehler": sum(v for k, v in arten.items() if k.startswith("modell_")),
        "kontextfehler": arten.get("kontext_fehlt", 0) + arten.get("kontext_falsch_zugeordnet", 0),
        "erfunden": arten.get("modell_erfunden", 0),
        "ausfaelle": sum(1 for z in zeilen if z.get("fehler")),
        "p50_ms": ms[len(ms) // 2] if ms else None,
        "p95_ms": _perzentil(ms, 0.95),
    }
    # Nur die Recherche misst je Fall Kosten und das Ende des Stroms.
    usd = [z["usd"] for z in zeilen if z.get("usd") is not None]
    if usd:
        aus["usd_je_fall"] = round(sum(usd) / len(usd), 5)
        aus["usd_p95"] = _perzentil(usd, 0.95)
        aus["abgeschnitten"] = sum(1 for z in zeilen if z.get("finish_reason") == "length")
        denken = [(z.get("usage") or {}).get("reasoning_tokens") for z in zeilen]
        denken = [d for d in denken if d is not None]
        aus["denk_tokens_p50"] = _perzentil(denken, 0.5)
        aus["denk_tokens_max"] = max(denken) if denken else None
    return aus


def speichern(erg: dict, ziel: Path | None = None) -> Path:
    if ziel is None and erg.get("kanal") == "deep":
        ziel = ERGEBNISSE_DEEP / (f"{erg['modell'].replace('/', '-')}"
                                  f"-{erg.get('aufwand') or 'vorgabe'}-{erg['zeitstempel']}.json")
    ziel = ziel or ERGEBNISSE / f"{erg['modell'].replace('/', '-')}-{erg['zeitstempel']}.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(erg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ziel


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({a / b:.0%})".replace(".", ",") if b else "—"


def laufname(e: dict) -> str:
    """Modell, Denkaufwand (falls gesetzt) und, wo es einen gibt, der Stand („vor #1493“)."""
    return (e["modell"] + (f" · {e['aufwand']}" if e.get("aufwand") else "")
            + (f" ({e['etikett']})" if e.get("etikett") else ""))


def _vergleichslauf(e: dict) -> bool:
    """Ein Lauf auf einem ÄLTEREN Stand — er steht in den Tabellen zum
    Vergleich, aber nicht in der Arbeitsliste: Die soll zeigen, was HEUTE fehlt."""
    return str(e.get("etikett") or "").startswith("vor ")


def tabelle_kategorien(laeufe: list[dict]) -> list[str]:
    """Kategorie × Modell: Anteil ok, dazu die Kontextfehler."""
    kategorien = sorted({z["kategorie"] or "?" for e in laeufe for z in e["faelle"]})
    kopf = "| Kategorie | Fälle | " + " | ".join(
        f"{laufname(e)} ok | Kontextfehler" for e in laeufe) + " |"
    aus = [kopf, "|---|---:|" + "---:|---:|" * len(laeufe)]
    for kat in kategorien:
        zellen = []
        n = 0
        for e in laeufe:
            zs = [z for z in e["faelle"] if (z["kategorie"] or "?") == kat]
            n = len(zs)
            ok = sum(1 for z in zs if z["fehlerart"] == "ok")
            kf = sum(1 for z in zs if z["fehlerart"].startswith("kontext_"))
            zellen += [_pct(ok, len(zs)), str(kf)]
        aus.append(f"| {kat} | {n} | " + " | ".join(zellen) + " |")
    return aus


def tabelle_saetze(laeufe: list[dict]) -> list[str]:
    """Haushaltsfälle und Ratsfälle getrennt — sie messen Verschiedenes."""
    aus = ["| Lauf | Fallsatz | Fälle | ok | Kontextfehler | Modellfehler | davon falsch/erfunden |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for e in laeufe:
        for satz, pruef in (("Haushalt", True), ("Rat", False)):
            zs = [z for z in e["faelle"] if z["id"].startswith("hh-") is pruef]
            if not zs:
                continue
            arten = Counter(z["fehlerart"] for z in zs)
            modell = sum(v for k, v in arten.items() if k.startswith("modell_"))
            hart = arten.get("modell_falsch", 0) + arten.get("modell_erfunden", 0)
            kf = arten.get("kontext_fehlt", 0) + arten.get("kontext_falsch_zugeordnet", 0)
            aus.append(f"| {laufname(e)} | {satz} | {len(zs)} | {_pct(arten.get('ok', 0), len(zs))} "
                       f"| {kf} | {modell} | {hart} |")
    return aus


def tabelle_kanaele(laeufe: list[dict]) -> list[str]:
    aus = ["| Modell | Kanal | Fälle | ok | Kontext ok | " +
           " | ".join(fa.FEHLERARTEN[1:]) + " |",
           "|---|---|---:|---:|---:|" + "---:|" * (len(fa.FEHLERARTEN) - 1)]
    for e in laeufe:
        for kanal in ("lotti", "rat", "alle"):
            zs = [z for z in e["faelle"] if kanal == "alle" or z["kanal"] == kanal]
            if not zs:
                continue
            arten = Counter(z["fehlerart"] for z in zs)
            ok = arten.get("ok", 0)
            aus.append(f"| {laufname(e)} | {kanal} | {len(zs)} | {_pct(ok, len(zs))} | "
                       f"{sum(1 for z in zs if z['kontext_ok'])} | "
                       + " | ".join(str(arten.get(a, 0)) for a in fa.FEHLERARTEN[1:]) + " |")
    return aus


def _stand(e: dict) -> str:
    """Der Code-Stand eines Laufs: das Etikett bis zum ersten Komma."""
    return str(e.get("etikett") or "").split(",")[0].strip()


def kontextfehler(laeufe: list[dict], faelle: list[dict]) -> dict[str, list[dict]]:
    """Die Arbeitsliste: je Baustein die Fälle, deren Kontext nicht stimmte.

    Ein Kontextfehler hängt nicht am Modell — der Prompt ist bis auf die
    Analyse derselbe. Gezählt wird deshalb, was in IRGENDEINEM Lauf fehlte,
    mit dem Beispiel aus dem ersten — aber je Fall nur unter den JÜNGSTEN
    Läufen, die ihn enthalten. Seit 23.09.2026 laufen Teilmengen (nur die
    Haushaltsfälle, nach einem Kontext-Nachzug): Ohne diese Regel stünde ein
    behobener Fehler aus einem älteren Gesamtlauf weiter auf der Liste, und
    die Liste zeigte nicht mehr, was HEUTE fehlt. „Jüngste" heißt: derselbe
    STAND wie der neueste Lauf mit diesem Fall — der Teil des Etiketts vor
    dem Komma (``_stand``), damit zwei Läufe desselben Stands („nach K1,
    Lauf 1" und „…, Lauf 2") beide zählen.
    """
    nach_id = {f["id"]: f for f in faelle}
    gruppen: dict[str, list[dict]] = defaultdict(list)
    gesehen: set[str] = set()
    aktuell = [e for e in laeufe if not _vergleichslauf(e)]
    # Je Fall das Etikett des neuesten Laufs, der ihn enthält.
    neuester: dict[str, tuple[str, str]] = {}
    for e in aktuell:
        for z in e["faelle"]:
            marke = (str(e.get("zeitstempel") or ""), _stand(e))
            if z["id"] not in neuester or marke[0] > neuester[z["id"]][0]:
                neuester[z["id"]] = marke
    for e in aktuell:
        for z in e["faelle"]:
            if not z["fehlerart"].startswith("kontext_") or z["id"] in gesehen:
                continue
            if _stand(e) != neuester[z["id"]][1]:
                continue
            gesehen.add(z["id"])
            fall = nach_id.get(z["id"], {})
            for g, gb in zip(fall.get("gold") or [], z["gold"]):
                if gb["kontext"]["status"] == "ok":
                    continue
                # Die Ratsfälle tragen keinen Baustein: Dort liefert das
                # Retrieval (bzw. Lottis Seitenblock) den Beschluss.
                baustein = (g.get("baustein") or fall.get("baustein")
                            or (f"Lotti-Seitenblock ({fall.get('route')})"
                                if fall.get("kanal") == "lotti"
                                else f"Retrieval/Beschlusskontext ({fall.get('kategorie')})"))
                gruppen[baustein].append({
                    "id": z["id"], "kanal": z["kanal"], "route": z.get("route"),
                    "frage": z["frage"], "fakt": gb["fakt"], "status": gb["kontext"]["status"],
                    "im_kontext": gb["kontext"]["fundstellen"], "jahre": gb["kontext"]["jahre"],
                    "bausteine": z.get("bausteine") or [], "weg": z.get("weg"),
                    "bekannt": fall.get("bekannt"), "quelle": g.get("quelle"),
                })
    return dict(sorted(gruppen.items(), key=lambda kv: -len(kv[1])))


def letzte_laeufe(ordner: Path = ERGEBNISSE) -> list[dict]:
    """Je Modell und Stand der jüngste Lauf — Vergleichsläufe zuerst."""
    je: dict[str, dict] = {}
    for pfad in sorted(ordner.glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        e["_datei"] = str(pfad.relative_to(WURZEL))
        je[laufname(e)] = e
    return sorted(je.values(), key=lambda e: (not _vergleichslauf(e), e["modell"]))


def bericht_teil(laeufe: list[dict], faelle: list[dict]) -> str:
    """Der erzeugte Teil von ``docs/fakten-eval.md`` (zwischen den Marken)."""
    zeilen = ["## Ergebnis", ""]
    for e in laeufe:
        k = e["kennzahlen"]
        zeilen.append(f"- **{laufname(e)}** ({e['zeitstempel']}, `{e.get('_datei', '')}`): "
                      f"{_pct(k['ok'], k['n_cases'])} ok, Kontext stimmte in {k['kontext_ok']} "
                      f"Fällen, {k['modellfehler']} Modellfehler (davon {k['erfunden']} erfunden), "
                      f"{k['kontextfehler']} Kontextfehler, {k['ausfaelle']} Ausfälle, "
                      f"p50 {k['p50_ms']} ms" + (f", Kosten {e['kosten_usd']:.2f} $"
                                                  if e.get("kosten_usd") is not None else ""))
    zeilen += ["", "### Je Fallsatz", ""] + tabelle_saetze(laeufe)
    zeilen += ["", "### Je Kanal und Fehlerart", ""] + tabelle_kanaele(laeufe)
    zeilen += ["", "### Je Kategorie", ""] + tabelle_kategorien(laeufe)
    zeilen += ["", "## Kontextfehler — die Arbeitsliste", "",
               "Gruppiert nach dem Codeteil, der den Fakt hätte liefern müssen. Je Eintrag: "
               "Frage, Goldfakt, und was im Prompt stand (bei „falsch zugeordnet“ die Zeile "
               "samt dem Jahr, unter dem sie steht; bei „fehlt“ die Bausteine, die da waren).",
               ""]
    for baustein, eintraege in kontextfehler(laeufe, faelle).items():
        zeilen.append(f"### `{baustein}` — {len(eintraege)}")
        zeilen.append("")
        for x in eintraege:
            wo = f"{x['kanal']}" + (f" `{x['route']}`" if x.get("route") else "")
            if x["status"] == "falsch_zugeordnet":
                stand = "; ".join(f"„{s}“ (Jahr {j})" for s, j in zip(x["im_kontext"], x["jahre"]))
            else:
                stand = ("nicht da; Bausteine im Prompt: " + ", ".join(x["bausteine"][:6])
                         if x["bausteine"] else "nicht da; kein Modellaufruf" if x["weg"] == "deterministic"
                         else "nicht da; keine Haushalts-Bausteine im Prompt")
            bekannt = " **(bekannt, Fix unterwegs)**" if x.get("bekannt") else ""
            zeilen.append(f"- `{x['id']}` ({wo}): „{x['frage']}“ — Gold: {x['fakt']} — "
                          f"{x['status'].replace('_', ' ')}: {stand}{bekannt}")
        zeilen.append("")
    return "\n".join(zeilen).rstrip() + "\n"


def _de(usd: float | None) -> str:
    return f"{usd:.4f}".replace(".", ",") if usd is not None else "—"


def tabelle_deep(laeufe: list[dict]) -> list[str]:
    """Die Recherche-Läufe nebeneinander: Fehler nach Art, Dauer, Kosten."""
    aus = ["| Lauf | Fälle | ok | Modellfehler | ausgelassen | falsch | erfunden | "
           "zu Unrecht verweigert | Kontextfehler | Ausfälle | abgeschnitten | p50 | p95 | "
           "$ je Bericht | $ p95 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for e in laeufe:
        k = e["kennzahlen"]
        a = k["fehlerarten"]

        def s(ms: float | None) -> str:
            return f"{ms / 1000:.0f} s" if ms else "—"
        aus.append(
            f"| {laufname(e)} | {k['n_cases']} | {_pct(k['ok'], k['n_cases'])} | "
            f"{k['modellfehler']} | {a.get('modell_ausgelassen', 0)} | {a.get('modell_falsch', 0)} | "
            f"{a.get('modell_erfunden', 0)} | {a.get('modell_verweigert_zu_unrecht', 0)} | "
            f"{k['kontextfehler']} | {k['ausfaelle']} | {k.get('abgeschnitten', '—')} | "
            f"{s(k.get('p50_ms'))} | {s(k.get('p95_ms'))} | "
            f"{_de(k.get('usd_je_fall'))} | {_de(k.get('usd_p95'))} |")
    return aus


def unterschiede_deep(laeufe: list[dict]) -> list[str]:
    """Je Fall, wo die Läufe sich in der Fehlerart unterscheiden."""
    ids = list(dict.fromkeys(z["id"] for e in laeufe for z in e["faelle"]))
    je = [{z["id"]: z["fehlerart"] for z in e["faelle"]} for e in laeufe]
    aus = ["| Fall | " + " | ".join(laufname(e) for e in laeufe) + " |",
           "|---|" + "---|" * len(laeufe)]
    for i in ids:
        arten = [j.get(i, "—") for j in je]
        # Ein Fall, den ein Lauf nicht hat (gestoppt, Stichprobe), ist kein Unterschied.
        if len(set(arten) - {"—"}) > 1:
            aus.append(f"| `{i}` | " + " | ".join(arten) + " |")
    return aus


MARKE_AN, MARKE_AUS = "<!-- fakten-eval:anfang -->", "<!-- fakten-eval:ende -->"


def bericht_schreiben(laeufe: list[dict], faelle: list[dict], ziel: Path = BERICHT) -> None:
    teil = bericht_teil(laeufe, faelle)
    alt = ziel.read_text(encoding="utf-8") if ziel.exists() else ""
    if MARKE_AN in alt and MARKE_AUS in alt:
        vor, rest = alt.split(MARKE_AN, 1)
        _, nach = rest.split(MARKE_AUS, 1)
        neu = f"{vor}{MARKE_AN}\n{teil}{MARKE_AUS}{nach}"
    else:
        neu = f"{alt.rstrip()}\n\n{MARKE_AN}\n{teil}{MARKE_AUS}\n"
    ziel.write_text(neu, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Aufruf
# --------------------------------------------------------------------------- #

def _faelle_waehlen(alle: list[dict], nur: str | None, limit: int | None,
                    auswahl: str | None = None) -> list[dict]:
    if auswahl:
        if auswahl not in AUSWAHL:
            raise SystemExit(f"unbekannte Auswahl {auswahl!r} — bekannt: {', '.join(AUSWAHL)}")
        ids = AUSWAHL[auswahl]
        fehlen = set(ids) - {f["id"] for f in alle}
        if fehlen:
            raise SystemExit(f"Auswahl {auswahl!r} nennt unbekannte Fälle: {sorted(fehlen)}")
        nach_id = {f["id"]: f for f in alle}
        alle = [nach_id[i] for i in ids]
    if nur:
        wahl = {x.strip() for x in nur.split(",") if x.strip()}
        alle = [f for f in alle if f["id"] in wahl or (f.get("kategorie") or "") in wahl
                or f["kanal"] in wahl]
    return alle[:limit] if limit else alle


#: Promptlänge je Kanal, wenn ein Fall noch nie gemessen wurde — Mittel der
#: Läufe bis 23.09.2026 (Lotti 11.674, Frag den Rat 18.064, Recherche 75.132
#: Zeichen, alle Prompts des Jobs).
ZEICHEN_VORGABE = {"lotti": 12_000, "rat": 18_000, "deep": 75_000}
#: Antwort-Tokens je Fall samt Denken — großzügig: Der Recherche-Bericht
#: brauchte mit GPT-6 Luna `xhigh` bis 7.225 Denk-Tokens, im Mittel rund 4.000
#: Tokens insgesamt; die Antworten von Frag den Rat und Lotti sind kürzer.
ANTWORT_TOKENS = {"lotti": 800, "rat": 1_500, "deep": 4_000}


def fruehere_zeichen(ordner: Path = ERGEBNISSE) -> dict[tuple[str, str], int]:
    """Gemessene Promptlänge je (Weg, Fall) aus den gespeicherten Läufen — der
    jüngste Wert gilt. Weg ist ``deep`` oder der Kanal des Falls."""
    aus: dict[tuple[str, str], int] = {}
    pfade = sorted(ordner.glob("*.json")) + sorted((ordner / "deep").glob("*.json"))
    for pfad in pfade:
        try:
            e = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for z in e.get("faelle") or []:
            if z.get("kontext_zeichen"):
                weg = "deep" if e.get("kanal") == "deep" else z.get("kanal", "rat")
                aus[(weg, z["id"])] = int(z["kontext_zeichen"])
    return aus


def kosten_schaetzen(modell: str, faelle: list[dict], kanal: str | None = None,
                     zeichen: dict[tuple[str, str], int] | None = None) -> float | None:
    """Was der Lauf mit ``modell`` voraussichtlich kostet (Listenpreis).

    Gezählt ist nur der Aufruf des gemessenen Modells je Fall — die Analyse
    davor läuft auf ihrem eigenen, billigen Modell.
    """
    from eval import kostenbremse as kb
    zeichen = fruehere_zeichen() if zeichen is None else zeichen
    tokens, antwort = [], 0.0
    for f in faelle:
        weg = kanal or f["kanal"]
        tokens.append(zeichen.get((weg, f["id"]), ZEICHEN_VORGABE.get(weg, 20_000))
                      / kb.ZEICHEN_JE_TOKEN)
        antwort += ANTWORT_TOKENS.get(weg, 1_500)
    if not faelle:
        return 0.0
    return kb.schaetzen(modell, tokens, antwort / len(faelle))


def deep_laeufe(ordner: Path = ERGEBNISSE_DEEP) -> list[dict]:
    """Alle Recherche-Läufe, ältester zuerst — auch zwei derselben Einstellung."""
    aus = []
    for pfad in sorted(ordner.glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        e["_datei"] = str(pfad.relative_to(WURZEL))
        aus.append(e)
    return sorted(aus, key=lambda e: e["zeitstempel"])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    befehl = argv.pop(0) if argv and argv[0] in ("messen", "nachwerten", "bericht") else "messen"
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("datei", nargs="?", help="nachwerten: das gespeicherte Ergebnis")
    ap.add_argument("--modell")
    ap.add_argument("--faelle", help="Fall-Dateien, kommagetrennt (Vorgabe: beide, soweit da)")
    ap.add_argument("--nur", help="Fall-IDs, Kategorien oder Kanal, kommagetrennt")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ohne-zdr", action="store_true")
    ap.add_argument("--basis", help="ein laufendes Backend statt eines eigenen")
    ap.add_argument("--mitschnitt", type=Path, help="mit --basis: dessen Mitschnitt-Ordner")
    ap.add_argument("--dazu", action="append", default=[],
                    help="weitere Fall-Datei zusätzlich zur Vorgabe (z. B. aus einem offenen PR)")
    ap.add_argument("--etikett", help="Stand des Laufs für den Bericht; „vor …“ = Vergleichslauf")
    ap.add_argument("--nicht-speichern", action="store_true")
    ap.add_argument("--kanal", choices=("deep",),
                    help="jeden Fall über diesen Weg stellen (deep = ausführliche Recherche)")
    ap.add_argument("--auswahl", help=f"benannte Fallauswahl: {', '.join(AUSWAHL)}")
    ap.add_argument("--aufwand", choices=("vorgabe", "minimal", "low", "medium", "high", "xhigh"),
                    help="Denkaufwand der Web-Antworten im Mess-Backend")
    # Kostenbremse (eval/kostenbremse.py, Tims Regel vom 23.09.2026)
    ap.add_argument("--max-kosten", type=float, default=None,
                    help="Grenze der geschätzten Kosten in USD (Vorgabe 1,00)")
    ap.add_argument("--teuer-ok", action="store_true",
                    help="auch über der Grenze bzw. ohne Preis laufen")
    ap.add_argument("--stichprobe", type=int, metavar="N",
                    help="geschichtete Stichprobe von N Fällen (feste Saat)")
    ap.add_argument("--voll", action="store_true",
                    help="teures Modell: alle gewählten Fälle statt der Stichprobe")
    a = ap.parse_args(argv)
    pfade = [Path(p) for p in a.faelle.split(",")] if a.faelle else None
    faelle = lade(pfade)
    bekannt = {f["id"] for f in faelle}
    for extra in a.dazu:
        faelle += [f for f in lade([Path(extra)]) if f["id"] not in bekannt]

    if befehl == "bericht" and a.kanal == "deep":
        laeufe = deep_laeufe()
        # Mit --stichprobe N: nur die feste Stichprobe der Recherche-Auswahl —
        # dieselbe, die ein teures Modell von selbst misst. Die Spalte „Fälle“
        # zeigt, wie viele davon ein Lauf hat (ein gestoppter Lauf hat weniger).
        if a.stichprobe:
            from eval import kostenbremse as kb
            ids = {f["id"] for f in kb.stichprobe(_faelle_waehlen(faelle, None, None, "deep"),
                                                  a.stichprobe)}
            for e in laeufe:
                e["faelle"] = [z for z in e["faelle"] if z["id"] in ids]
                e["kennzahlen"] = {**e["kennzahlen"], **kennzahlen(e["faelle"])}
        print("\n".join(tabelle_deep(laeufe) + [""] + unterschiede_deep(laeufe)))
        return 0
    if befehl == "bericht":
        laeufe = letzte_laeufe()
        bericht_schreiben(laeufe, faelle)
        print(f"✓ {BERICHT.relative_to(WURZEL)} ({len(laeufe)} Läufe)")
        return 0
    if befehl == "nachwerten":
        if not a.datei:
            ap.error("nachwerten braucht die Ergebnisdatei")
        pfad = Path(a.datei)
        erg = nachwerten(json.loads(pfad.read_text(encoding="utf-8")), faelle)
        speichern(erg, pfad)
        print(json.dumps(erg["kennzahlen"], ensure_ascii=False, indent=1))
        return 0

    if not a.modell:
        ap.error("--modell fehlt")
    if not os.environ.get("OPENROUTER_API_KEY"):
        from dotenv import load_dotenv
        load_dotenv(WURZEL / ".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY fehlt")
    auswahl = _faelle_waehlen(faelle, a.nur, a.limit, a.auswahl)
    from eval import kostenbremse as kb
    auswahl, hinweis = kb.auswahl_fuer(a.modell, auswahl, stichprobe_n=a.stichprobe, voll=a.voll)
    if hinweis:
        print(hinweis)
    schaetzung = kosten_schaetzen(a.modell, auswahl, a.kanal)
    grund = kb.bremse(schaetzung, max_kosten=kb.MAX_KOSTEN_USD if a.max_kosten is None
                      else a.max_kosten, teuer_ok=a.teuer_ok, modell=a.modell,
                      was=f"Der Lauf ({len(auswahl)} Fälle, {a.modell})")
    if grund:
        raise SystemExit(grund)
    if schaetzung is not None:
        print(f"Geschätzt: {schaetzung:.2f} $ für {len(auswahl)} Fälle (Listenpreis)")
    # Ein Aufwand aus der Shell zählt wie `--aufwand` — und steht dann auch im
    # Ergebnis, statt still mitzumessen.
    aufwand = a.aufwand or os.environ.get(DENKAUFWAND_ENV) or None
    erg = ein_lauf(a.modell, auswahl, ohne_zdr=a.ohne_zdr, basis=a.basis, mitschnitt=a.mitschnitt,
                   kanal=a.kanal, aufwand=aufwand)
    if a.etikett:
        erg["etikett"] = a.etikett
    print(json.dumps(erg["kennzahlen"], ensure_ascii=False, indent=1))
    print(f"Kosten: {erg['kosten']['usd']:.4f} $ für {erg['kosten']['aufrufe']} Aufrufe "
          f"({erg['kosten']['ohne_kosten']} ohne Kostenwert) — "
          f"{erg['kosten']['usd'] / max(1, len(auswahl)):.4f} $ je Fall")
    if not a.nicht_speichern:
        print(f"✓ {speichern(erg).relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
