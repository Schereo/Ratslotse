#!/usr/bin/env python3
"""Tägliche Sicherung — sieben Tages- und drei Wochenstände je Datenbank,
optional per rsync gespiegelt.

Gesichert wird ALLES, was der Server nicht aus dem Repo wiederherstellen kann:

* **jede** Datenbank unter ``data/`` — nicht mehr eine feste Liste. Die zählte
  ``ratslotse.sqlite`` und ``council.sqlite`` auf; eine dritte Datenbank wäre still
  übersprungen worden, ohne dass jemand es gemerkt hätte.
* die **gerenderten Planzeichnungen** (``data/plaene/``). Sie ließen sich aus
  den PDFs neu erzeugen, aber das ist ein Stapellauf über 600 Anlagen.
* die **.env** mit den Geheimnissen (abschaltbar über ``BACKUP_ENV=0``). Ohne
  sie ist nach einem Serververlust jede Sitzung ungültig und jeder Schlüssel
  neu zu beschaffen. Die Kopie bekommt 0600 und liegt im selben Verzeichnis
  wie die Datenbanken — wer den Off-Site-Spiegel nutzt, sollte wissen, dass
  die Geheimnisse mitwandern.

Cron (als Nutzer tim auf dem App-Server):
  0 3 * * * /home/<user>/app/.venv/bin/python /home/<user>/app/scripts/backup_db.py

Off-Site-Mirror (optional, .env):
  BACKUP_RSYNC_TARGET=user@host:pfad/   # z. B. die Edge-VM — bei Serververlust
  BACKUP_RSYNC_SSH_PORT=22              # bleibt der ganze Bestand erhalten
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import re
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")  # BACKUP_RSYNC_*, RESEND_API_KEY/ALERT_EMAIL (Alerts)

DATA = ROOT / "data"
BACKUP_DIR = DATA / "backups"

#: Tagesstände: die jüngsten sieben Sicherungen bleiben in jedem Fall.
TAEGLICH = 7
#: Wochenstände: aus jeder der vier Kalenderwochen VOR dem Tagesfenster bleibt
#: zusätzlich die jüngste Sicherung. Sieben Tage feinkörnig für „gestern war es
#: noch gut", vier Wochenmarken für alles, was erst später auffällt; vorher
#: endete der Bestand nach sieben Tagen, und ein Schaden, den niemand in einer
#: Woche bemerkte, war endgültig.
#:
#: **Warum vier und nicht drei.** „7 Tage + 3 Wochen = 1 Monat" stimmt nur,
#: wenn das Tagesfenster genau auf einer Kalenderwoche liegt. Tut es das nicht,
#: reicht es in die Vorwoche hinein, und deren Marke fällt weg — der Bestand
#: endete dann schon nach 22 Tagen. Mit vier Marken sind es verlässlich 29 bis
#: 35 Tage, also wirklich ein Monat. Kosten: eine Kopie je Datenbank mehr.
WOECHENTLICH = 4

#: Ein Sicherungsname ist ``<stamm>_JJJJ-MM-TT.sqlite`` — sonst nichts.
_DATIERT = re.compile(r"^(?P<datum>\d{4}-\d{2}-\d{2})$")


def sicherungsdatum(pfad: Path, stamm: str) -> date | None:
    """Das Datum aus dem Dateinamen, oder ``None`` für alles andere.

    Das ``None`` ist die eigentliche Aussage: Handkopien wie
    ``council_pre_location_backfill_2026-08-26.sqlite`` tragen hinter dem Stamm
    kein reines Datum und fallen damit **aus der Rotation heraus** — sie bleiben
    liegen, bis jemand sie löscht.

    Vorher gab es diese Unterscheidung nicht: Gelöscht wurde ``sorted(...)[:-7]``,
    und weil ``council_pre_...`` alphabetisch **hinter** ``council_2026-...``
    steht, warfen zwei Handkopien vom August die beiden ältesten Tagesstände
    hinaus. Auf Prod lagen deshalb am 03.09.2026 nur fünf Tagesstände von
    ``council``, aber sieben von ``nwz``.
    """
    if not pfad.name.startswith(f"{stamm}_") or not pfad.name.endswith(".sqlite"):
        return None
    treffer = _DATIERT.match(pfad.name[len(stamm) + 1:-len(".sqlite")])
    if not treffer:
        return None
    try:
        return date.fromisoformat(treffer.group("datum"))
    except ValueError:                      # 2026-13-45 o. Ä. — kein Datum
        return None


def rotation(pfade, stamm: str, taeglich: int = TAEGLICH,
             woechentlich: int = WOECHENTLICH) -> tuple[list[Path], list[Path]]:
    """Teilt die datierten Sicherungen in (behalten, löschen).

    Zwei Stufen, die zweite greift erst hinter der ersten:

    1. die jüngsten ``taeglich`` Sicherungen — unabhängig davon, welche
       Kalendertage sie tragen. Fällt der Cron zwei Tage aus, deckt die Stufe
       eben neun Tage ab statt sieben; ein Ausfall soll den Bestand nicht
       zusätzlich verkürzen.
    2. aus jeder Kalenderwoche (ISO) **vor** dem Tagesfenster die jüngste
       Sicherung, davon die jüngsten ``woechentlich``.

    Der Zusatz „vor dem Tagesfenster" ist der Punkt, an dem die naive Fassung
    scheitert: Reicht das Fenster in die Vorwoche hinein, läge deren jüngste
    Sicherung einen Tag neben einem Tagesstand — eine Wochenmarke, die keinen
    Abstand gewinnt. Gezählt werden deshalb nur Wochen, die das Fenster gar
    nicht mehr berührt.

    Alles ohne Datum im Namen taucht in keiner der beiden Listen auf.
    """
    datiert = [(d, p) for p in pfade if (d := sicherungsdatum(p, stamm))]
    datiert.sort(key=lambda paar: (paar[0], paar[1].name), reverse=True)

    tagesstaende = datiert[:taeglich]
    behalten = [p for _, p in tagesstaende]
    grenze = min(d for d, _ in tagesstaende).isocalendar()[:2] if tagesstaende else None

    je_woche: dict[tuple[int, int], Path] = {}
    for d, p in datiert[taeglich:]:         # absteigend, also gewinnt die jüngste
        woche = d.isocalendar()[:2]
        if grenze is not None and woche >= grenze:
            continue                        # dieselbe Woche wie ein Tagesstand
        je_woche.setdefault(woche, p)
    behalten += list(je_woche.values())[:woechentlich]

    bleibt = set(behalten)
    return behalten, [p for _, p in datiert if p not in bleibt]


def backup_db(src: Path) -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    dst = BACKUP_DIR / f"{src.stem}_{date_str}.sqlite"

    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    with dst_conn:
        src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    behalten, veraltet = rotation(BACKUP_DIR.glob(f"{src.stem}_*.sqlite"), src.stem)
    for alt in veraltet:
        alt.unlink()

    print(f"✓  {src.name} → {dst.name} ({len(behalten)} Stände im Bestand)")
    return len(behalten)


def offsite_sync() -> None:
    """Mirror the backup directory to BACKUP_RSYNC_TARGET (if configured).

    `--delete` hält das Ziel als exakten Spiegel der lokalen Rotation — es ist
    damit eine Kopie gegen Serververlust, aber kein Archiv: Was hier gelöscht
    wird, ist beim nächsten Lauf auch dort weg.
    BatchMode verhindert Passwort-Prompts im Cron; ein Fehler wirft und landet
    damit im run_guarded-Alert."""
    target = os.environ.get("BACKUP_RSYNC_TARGET")
    if not target:
        return
    port = os.environ.get("BACKUP_RSYNC_SSH_PORT", "22")
    subprocess.run(
        [
            "rsync", "-az", "--delete",
            "-e", f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=15",
            f"{BACKUP_DIR}/", target,
        ],
        check=True,
        timeout=30 * 60,
    )
    print(f"✓  Off-Site-Mirror → {target}")


def backup_env() -> bool:
    """Die .env mitsichern (Standard an, ``BACKUP_ENV=0`` schaltet ab).

    Sie steht in keinem Repo und lässt sich nach einem Serververlust nicht
    rekonstruieren: WEB_JWT_SECRET neu zu setzen macht jede Sitzung ungültig,
    die API-Schlüssel wären einzeln neu zu beschaffen. Kopie mit 0600.
    """
    if os.environ.get("BACKUP_ENV", "1") == "0":
        return False
    source = ROOT / ".env"
    if not source.is_file():
        return False
    ziel = BACKUP_DIR / "env.backup"
    ziel.write_bytes(source.read_bytes())
    ziel.chmod(0o600)
    print(f"✓  .env → {ziel.name}")
    return True


#: Ordner unter ``data/``, die nicht in einer Datenbank stehen und trotzdem in
#: den Off-Site-Spiegel gehören — Name → wofür.
#:
#: ``archiv`` ist der wichtigere der beiden: Die gerenderten Planzeichnungen
#: ließen sich aus den PDFs neu erzeugen, das Statistik-Archiv nicht. Es
#: enthält Ausgaben, die es nirgends mehr gibt (die Stadt führt kein
#: Jahrbuch-Archiv, das Internet Archive hat keine Schnappschüsse); ein Archiv,
#: das nur auf einer Festplatte liegt, ist eine Kopie und kein Archiv.
GESPIEGELTE_ORDNER: dict[str, str] = {
    "plaene": "Planzeichnungen",
    "archiv": "Statistik-Archiv",
}


def dateien_spiegeln() -> dict[str, int]:
    """Erzeugte Dateien, die nicht in der Datenbank stehen, in den
    Off-Site-Spiegel legen: die gerenderten Planzeichnungen und das
    Statistik-Archiv.

    Bewusst NICHT täglich neu kopiert, sondern gespiegelt: Es sind hunderte
    unveränderlicher Dateien, und rsync überträgt nur, was neu ist. Der Preis
    ist eine zweite lokale Kopie (Stand 08/2026 rund 70 MB fürs Archiv) — die
    Alternative wäre ein zweites rsync-Ziel und damit eine zweite Stelle, an
    der sich eine Fehlkonfiguration verstecken kann.
    """
    aus: dict[str, int] = {}
    for ordner, label in GESPIEGELTE_ORDNER.items():
        source = DATA / ordner
        if not source.is_dir():
            aus[label] = 0
            continue
        ziel = BACKUP_DIR / ordner
        ziel.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-a", "--delete", f"{source}/", f"{ziel}/"],
                       check=True, timeout=30 * 60)
        n = sum(1 for p in ziel.rglob("*") if p.is_file())
        aus[label] = n
        print(f"✓  {label} gespiegelt ({n} Dateien)")
    return aus


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    gesichert, bytes_total, staende = 0, 0, 0
    # ALLE Datenbanken statt einer festen Liste: Eine neu hinzugekommene wäre
    # sonst still durchgerutscht. `data/backups/` bleibt außen vor (dort liegen
    # die Kopien selbst), `-wal`/`-shm` sind keine .sqlite-Dateien.
    for db_path in sorted(DATA.glob("*.sqlite")):
        staende += backup_db(db_path)
        gesichert += 1
        bytes_total += db_path.stat().st_size
    if not gesichert:
        raise RuntimeError("keine Datenbank gefunden — es wurde nichts gesichert")
    env_dabei = backup_env()
    gespiegelt = dateien_spiegeln()
    offsite_sync()
    return {
        "Datenbanken gesichert": gesichert,
        "Größe (MB)": round(bytes_total / 1_000_000, 1),
        "Stände im Bestand": staende,
        "Planzeichnungen": gespiegelt.get("Planzeichnungen", 0),
        "Statistik-Archiv": gespiegelt.get("Statistik-Archiv", 0),
        ".env gesichert": "ja" if env_dabei else "nein",
        "Off-Site-Mirror": "ja" if os.environ.get("BACKUP_RSYNC_TARGET") else "nein",
    }


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backup_db", main)
