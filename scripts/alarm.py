#!/usr/bin/env python3
"""Eine Alarm-Mail von Hand oder aus einem Workflow heraus verschicken.

**Wozu.** ``run_guarded`` meldet einen abgestürzten Cron-Job,
``kern/fehler.py`` einen 500er im Request, ``check_herzschlag.py`` einen Job,
der schweigt. Für den lautesten Fall von allen gab es nichts: **Der Deploy
bricht ab, die Wartungsbarriere bleibt stehen, und die Seite ist unten.** Am
07.09.2026 hat das 74 Minuten lang niemand erfahren — die Rauchprobe fiel um
14:58, gemerkt wurde es, als Tim sich anmelden wollte.

Der Ausweg ist klein: Der Deploy-Workflow hat SSH auf den Server, und der
Server hat ``RESEND_API_KEY`` und ``ALERT_EMAIL`` in seiner ``.env``. Es
braucht also kein neues GitHub-Secret, nur einen Aufruf im Fehlerfall.

Aufruf (aus dem Workflow, das Skript kommt über stdin — deshalb ``--root``
statt ``__file__``, genau wie bei ``verify_predeploy_backup.py``)::

    ssh target 'cd ~/app && .venv/bin/python - --root . \
      --betreff "Ratslotse – Deploy abgebrochen" --text "…" --zustand' < scripts/alarm.py

``--zustand`` hängt an, was man im ersten Moment wissen will: Steht die
Barriere? Laufen die Dienste? — Ohne diese zwei Zeilen ist die Mail nur ein
Schreck, mit ihnen ist sie eine Diagnose.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _dienst(name: str) -> str:
    """``systemctl is-active`` ohne Krach: Ein unbekannter Dienst ist kein
    Abbruchgrund für eine Alarm-Mail."""
    try:
        r = subprocess.run(["systemctl", "is-active", name],
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip() or "unbekannt"
    except Exception as e:                                    # pragma: no cover
        return f"nicht feststellbar ({e.__class__.__name__})"


def zustand(root: Path) -> str:
    """Der Zustand, der im ersten Moment zählt — als fertiger Textblock.

    Die Wartungsbarriere zuerst: Sie ist der Unterschied zwischen „ein Deploy
    ist rot" und „die Seite ist unten". Steht sie, verweigert jeder
    Store-Zugriff, ``/api/health`` antwortet 503 und die Datenendpunkte 500.
    """
    zeilen = []
    barriere = root / "data" / ".release-maintenance"
    if barriere.exists():
        try:
            sha = barriere.read_text().strip()
        except OSError:
            sha = "unlesbar"
        zeilen.append(f"<b>Die Wartungsbarriere steht</b> (Commit {sha}). "
                      "Solange sie liegt, ist die Seite für Angemeldete unten.")
    else:
        zeilen.append("Die Wartungsbarriere liegt nicht — der Datenzugriff ist frei.")
    for unit in ("nwz-web-api", "nwz-web-frontend"):
        zeilen.append(f"{unit}: <code>{_dienst(unit)}</code>")
    log = root / "data" / "vorprobe.log"
    if log.exists():
        try:
            letzte = log.read_text(errors="replace").strip().splitlines()[-8:]
        except OSError:
            letzte = []
        if letzte:
            zeilen.append("Letzte Zeilen der Vorprobe:\n" + "\n".join(letzte))
    return "\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".", help="Wurzel der App (mit .env und data/)")
    p.add_argument("--betreff", default="Ratslotse – Betriebsalarm")
    p.add_argument("--text", required=True)
    p.add_argument("--zustand", action="store_true",
                   help="Barriere und Dienstzustand anhängen")
    p.add_argument("--fusszeile",
                   default="Automatischer Betriebsalarm. Kein Cron-Job, "
                           "sondern der Deploy selbst.")
    a = p.parse_args(argv)

    root = Path(a.root).resolve()
    sys.path.insert(0, str(root))
    # Unter Cron und über SSH ist die .env NICHT geladen — ohne diese Zeile
    # fehlt RESEND_API_KEY, und notify_admin loggt still statt zu mailen.
    # Genau daran ist remind_setup.py schon einmal gescheitert.
    from dotenv import load_dotenv
    load_dotenv(root / ".env")

    from kern.alerts import notify_admin

    text = a.text
    if a.zustand:
        text = f"{text}\n\n{zustand(root)}"
    notify_admin(text, betreff=a.betreff, fusszeile=a.fusszeile)
    print(f"Alarm abgesetzt: {a.betreff}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
