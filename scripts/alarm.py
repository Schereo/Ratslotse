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

**Und seit dem 20.09.2026 entscheidet derselbe Blick, ob überhaupt gemailt
wird.** An diesem Tag brachen sechs Deploys hintereinander ab; genau EINER
davon ließ die Seite unten (13:23, nach dem API-Stopp), die übrigen fünf
scheiterten in den Vorflug-Prüfungen — vor Barriere, rsync und API-Stopp, also
ohne dass Prod überhaupt angefasst wurde. Alle sechs schickten dieselbe Mail
mit demselben Satz „ist die Seite fuer Angemeldete unten", und alle sechs
widersprachen sich zwei Zeilen tiefer selbst: „Die Wartungsbarriere liegt
nicht — der Datenzugriff ist frei." Der Alarm MASS den harmlosen Fall bereits
und tat trotzdem so, als brenne es.

``--nur-wenn-betroffen`` macht aus dieser Messung eine Entscheidung
(``betroffen()``): Liegt keine Barriere und laufen beide Dienste, bleibt es
still — der rote Actions-Lauf steht ja. ``--cutover-begonnen`` setzt der
Workflow, sobald er die Barriere gesetzt hat; ab da ist jeder Abbruch laut,
auch wenn die Messung gerade unauffällig aussieht. Wer das leiser stellt,
braucht das Gegenstück: ``ops-deploy-rueckstand.yml`` merkt, wenn Prod
deswegen still stehen bleibt.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


#: Die beiden Units, ohne die ratslotse.de nicht antwortet.
DIENSTE = ("nwz-web-api", "nwz-web-frontend")


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
    for unit in DIENSTE:
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


def betroffen(root: Path, cutover_begonnen: bool = False) -> tuple[bool, str]:
    """Ist Prod von diesem Abbruch ÜBERHAUPT betroffen? Mit Begründung.

    Der Deploy prüft vieles, bevor er etwas anfasst: Backup, Runtime,
    laufende Crons. Bricht er dort ab, ist Prod unverändert — die Barriere
    liegt nicht, beide Dienste laufen, niemand merkt etwas. Ein Alarm dafür
    ist kein Alarm, sondern Rauschen, und Rauschen kostet genau die
    Aufmerksamkeit, die der echte Fall braucht (am 20.09.2026: fünf harmlose
    Mails, in denen die eine echte unterging).

    Gemessen, nicht geraten — und in dieser Reihenfolge:

    1. **Die Barriere zuerst.** Sie liegt auch dann, wenn ein FRÜHERER Lauf
       sie hat stehen lassen und dieser hier schon am Setzen scheiterte. Der
       Schritt sähe nach „vor dem Cutover" aus, die Seite wäre aber unten.
    2. **Dann die Dienste.** Nach dem Start kann die Barriere weg und die
       Seite trotzdem tot sein (ein Build, der nicht läuft).
    3. **Zuletzt, was der Workflow weiß.** Ab dem gesetzten Marker ist jeder
       Abbruch laut, auch wenn gerade alles unauffällig misst — dann lief der
       neue Stand bereits, und das gehört gesehen.
    """
    barriere = root / "data" / ".release-maintenance"
    if barriere.exists():
        return True, ("Die Wartungsbarriere liegt — die Seite ist für Angemeldete "
                      "unten.")
    tot = [unit for unit in DIENSTE if _dienst(unit) != "active"]
    if tot:
        return True, "Nicht aktiv: " + ", ".join(tot)
    if cutover_begonnen:
        return True, ("Der Cutover hatte begonnen. Barriere und Dienste sind zwar in "
                      "Ordnung, aber der neue Stand lief bereits — das gehört "
                      "angesehen.")
    return False, ("Abgebrochen VOR dem Cutover: keine Wartungsbarriere, beide Dienste "
                   "aktiv. Prod ist unverändert, es gibt nichts zu retten — der rote "
                   "Actions-Lauf genügt.")


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
    p.add_argument("--nur-wenn-betroffen", action="store_true",
                   help="nur mailen, wenn Prod tatsächlich betroffen ist "
                        "(Barriere liegt, ein Dienst ist tot oder --cutover-begonnen)")
    # Als WERT und nicht als Schalter: Der Workflow reicht hier eine
    # Schritt-Ausgabe durch (`${{ steps.cutover.outputs.begonnen }}`), und die
    # ist leer, solange der Schritt nicht gelaufen ist. Ein Schalter müsste
    # dafür in der YAML-Zeile zusammengebaut werden; ein Wert darf leer sein.
    p.add_argument("--cutover-begonnen", default="0", metavar="0|1",
                   help="'1', sobald der Workflow die Wartungsbarriere gesetzt "
                        "hat; ab dann ist jeder Abbruch laut")
    a = p.parse_args(argv)

    root = Path(a.root).resolve()
    # Die Entscheidung VOR allem anderen: Wer nicht mailt, braucht weder .env
    # noch RESEND-Schlüssel — und ein Fehler beim Laden beider kann dann auch
    # keinen stillen Fall in einen roten verwandeln.
    if a.nur_wenn_betroffen:
        laut, grund = betroffen(root, a.cutover_begonnen.strip() == "1")
        print(("ALARM: " if laut else "STILL: ") + grund)
        if not laut:
            return 0
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
