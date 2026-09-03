"""Den lokalen Backend-Server starten, anhalten, nachsehen.

**Warum es das gibt.** Am 02.09.2026 habe ich zwanzig Minuten gegen einen
FREMDEN uvicorn gemessen. Er lag seit dem 19. August auf Port 8077; mein
eigener konnte nicht binden und war still weg. ``/api/health`` antwortete
trotzdem — der fremde tat es ja —, und ``/api/app-config`` gab 404 für einen
Endpunkt, den es längst gibt. Der Befund sah aus wie ein Fehler im Code.

Dazu kam bei jedem Start dieselbe Handarbeit: ``COUNCIL_DB=…
RATSLOTSE_DB=… WEB_JWT_SECRET=… uvicorn app.main:app --port …``, jedes Mal neu
zusammengesucht, jedes Mal mit einem geratenen Port.

Dieses Skript nimmt beides ab:

* Es sucht einen **freien** Port und weigert sich, einen fremden Prozess
  mitzubenutzen — wer auf dem Port liegt, sagt es samt Startzeit dazu.
* Es verdrahtet die Datenbanken dieses Worktrees und ein **festes**
  Signiergeheimnis, damit ein Token einen Neustart überlebt (sonst meldet der
  Simulator sich nach jedem Neustart ab).
* Es merkt sich, was es gestartet hat, und kann es wieder anhalten.

::

    python scripts/dev.py start      # startet, nennt Port und PID
    python scripts/dev.py status     # läuft er? seit wann? welcher Port?
    python scripts/dev.py stop       # hält den eigenen an, nie einen fremden

Der Server läuft im Hintergrund weiter; seine Ausgabe steht in der Datei, die
``start`` nennt. Für die Oberfläche: ``NEXT_PUBLIC_API_BASE`` auf die
ausgegebene Adresse setzen (``start`` schreibt die Zeile zum Kopieren hin).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
STAND = WURZEL / ".dev-server.json"
LOG = WURZEL / "dev-server.log"

#: Fest, nicht zufällig: Ein wechselndes Geheimnis wirft bei jedem Neustart
#: alle Sitzungen weg — im Browser lästig, im Simulator eine Fehlersuche.
#: Es ist ein LOKALES Geheimnis und steht deshalb offen hier.
LOKALES_GEHEIMNIS = "nur-lokal-und-absichtlich-fest"

#: Ab hier wird gesucht. Bewusst weit weg von 8000/3000, wo die Werkzeuge
#: anderer Sitzungen liegen.
PORT_VON, PORT_BIS = 8600, 8699


def _python() -> str:
    """Der Interpreter des venv — im Worktree liegt es im Haupt-Checkout."""
    kandidaten = [WURZEL / ".venv" / "bin"]
    try:
        gemeinsam = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=WURZEL, capture_output=True, text=True, check=True).stdout.strip()
        if gemeinsam:
            kandidaten.append(Path(gemeinsam).parent / ".venv" / "bin")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    for ordner in kandidaten:
        if (ordner / "uvicorn").exists():
            return str(ordner / "uvicorn")
    return ""


def belegt_von(port: int) -> int | None:
    """PID des Prozesses auf diesem Port — oder ``None``, wenn er frei ist."""
    try:
        roh = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True).stdout.split()
        return int(roh[0]) if roh else None
    except (FileNotFoundError, OSError, ValueError):
        # Ohne `lsof` bleibt der Bind-Versuch — er sagt nur nicht, WER da liegt.
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return None
            except OSError:
                return -1


def beschreibe(pid: int) -> str:
    if pid < 0:
        return "ein Prozess (lsof fehlt, deshalb ohne Namen)"
    try:
        aus = subprocess.run(["ps", "-o", "lstart=,command=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
        return aus or f"PID {pid}"
    except (FileNotFoundError, OSError):
        return f"PID {pid}"


def freier_port() -> int | None:
    for port in range(PORT_VON, PORT_BIS + 1):
        if belegt_von(port) is None:
            return port
    return None


def lies_stand() -> dict | None:
    if not STAND.exists():
        return None
    try:
        stand = json.loads(STAND.read_text())
    except (ValueError, OSError):
        return None
    pid = stand.get("pid")
    if not pid:
        return None
    try:
        os.kill(pid, 0)          # lebt er noch?
    except (ProcessLookupError, PermissionError):
        STAND.unlink(missing_ok=True)
        return None
    return stand


def datenbanken() -> tuple[Path, Path, list[str]]:
    rat = WURZEL / "data" / "council.sqlite"
    konten = WURZEL / "data" / "ratslotse.sqlite"
    hinweise = []
    if not rat.exists() or not rat.stat().st_size:
        hinweise.append(
            "Keine Ratsdaten in data/. Ohne sie ist jede Liste leer:\n"
            "    python scripts/lokale_daten.py hol && python scripts/lokale_daten.py setz")
    if not konten.exists() or not konten.stat().st_size:
        hinweise.append(
            "Keine Konten in data/. Ohne sie kommt man an nichts Angemeldetes:\n"
            "    python scripts/saat_konten.py")
    return rat, konten, hinweise


def start(args) -> int:
    laeuft = lies_stand()
    if laeuft:
        print(f"Läuft schon: Port {laeuft['port']}, PID {laeuft['pid']}.")
        print(f"  {laeuft['basis']}")
        return 0

    uvicorn = _python()
    if not uvicorn:
        print("Kein uvicorn im venv gefunden. Einmal einrichten:\n"
              "    python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt "
              "-r web/backend/requirements.txt -c constraints.txt", file=sys.stderr)
        return 1

    if args.port:
        wer = belegt_von(args.port)
        if wer is not None:
            print(f"Port {args.port} ist belegt von: {beschreibe(wer)}", file=sys.stderr)
            print("Das ist NICHT unser Server. Gegen ihn zu messen führt in die Irre —\n"
                  "genau so ist am 02.09.2026 ein 404 auf einem Endpunkt entstanden,\n"
                  "den es längst gibt. Ohne --port sucht das Skript sich einen freien.",
                  file=sys.stderr)
            return 1
        port = args.port
    else:
        port = freier_port()
        if port is None:
            print(f"Kein freier Port zwischen {PORT_VON} und {PORT_BIS}.", file=sys.stderr)
            return 1

    rat, konten, hinweise = datenbanken()
    for h in hinweise:
        print(f"Hinweis: {h}")

    umgebung = {
        **os.environ,
        "COUNCIL_DB": str(rat),
        "RATSLOTSE_DB": str(konten),
        "WEB_JWT_SECRET": os.environ.get("WEB_JWT_SECRET") or LOKALES_GEHEIMNIS,
    }
    with LOG.open("w") as protokoll:
        prozess = subprocess.Popen(
            [uvicorn, "app.main:app", "--port", str(port), "--log-level", "info"]
            + (["--reload"] if args.reload else []),
            cwd=WURZEL / "web" / "backend",
            env=umgebung, stdout=protokoll, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    basis = f"http://127.0.0.1:{port}"
    frist = time.time() + 40
    while time.time() < frist:
        if prozess.poll() is not None:
            print(f"Der Server ist sofort wieder ausgegangen. Protokoll: {LOG}",
                  file=sys.stderr)
            print(LOG.read_text()[-1200:], file=sys.stderr)
            return 1
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    else:
        print(f"Der Server antwortet nach 40 s nicht. Protokoll: {LOG}", file=sys.stderr)
        return 1

    STAND.write_text(json.dumps({
        "pid": prozess.pid, "port": port, "basis": basis,
        "seit": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2))
    print(f"Läuft: {basis}  (PID {prozess.pid})")
    print(f"Protokoll: {LOG}")
    print(f"Rauchprobe: python scripts/rauchprobe.py --basis {basis}")
    print(f"Frontend:   NEXT_PUBLIC_API_BASE={basis} npm run dev  (in web/frontend)")
    return 0


def status(_args) -> int:
    stand = lies_stand()
    if not stand:
        print("Kein eigener Server. Starten: python scripts/dev.py start")
        return 1
    print(f"Läuft seit {stand['seit']}: {stand['basis']}  (PID {stand['pid']})")
    return 0


def stop(_args) -> int:
    stand = lies_stand()
    if not stand:
        print("Kein eigener Server, nichts anzuhalten.")
        STAND.unlink(missing_ok=True)
        return 0
    # Nur der EIGENE: Was hier steht, hat dieses Skript selbst gestartet. Einen
    # fremden Prozess anzuhalten, weil er auf „unserem" Port liegt, wäre der
    # Fehler, gegen den dieses Skript geschrieben ist — nur andersherum.
    try:
        os.kill(stand["pid"], 15)
    except (ProcessLookupError, PermissionError) as fehler:
        print(f"PID {stand['pid']} ließ sich nicht anhalten: {fehler}", file=sys.stderr)
        STAND.unlink(missing_ok=True)
        return 1
    STAND.unlink(missing_ok=True)
    print(f"Angehalten: PID {stand['pid']} (Port {stand['port']}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    unter = p.add_subparsers(dest="befehl", required=True)
    s = unter.add_parser("start", help="starten (sucht sich einen freien Port)")
    s.add_argument("--port", type=int, help="fester Port statt eines freien")
    s.add_argument("--reload", action="store_true", help="bei Codeänderung neu laden")
    s.set_defaults(fn=start)
    unter.add_parser("status", help="läuft er? seit wann?").set_defaults(fn=status)
    unter.add_parser("stop", help="den eigenen anhalten").set_defaults(fn=stop)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
