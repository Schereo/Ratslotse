"""Das Archiv der gesicherten Quelldateien — Aufbau, Schreiben, **Lesen**.

Seit 08/2026 sichert ``scripts/archive_statistik.py`` (#603) täglich die
Jahrbuch-PDFs und Open-Data-Dateien, weil die Stadt kein Archiv führt: Auf
ihrer Übersichtsseite steht immer nur die *jeweils neueste* Ausgabe jeder
Tabelle, und der Dateiname trägt den Jahrgang (``1103-2025-AZ.pdf``). Erscheint
die Ausgabe 2026, ist die alte Adresse ein 404.

Warum das Lesen hierher gehört und nicht in den Job
----------------------------------------------------
Der Job **schrieb** bisher als Einziger ins Archiv, und die Kenntnis seines
Aufbaus lag deshalb in ihm. Mit dem ersten Parser, der aus dem Archiv liest
(``council/steuertabellen.py``), wären es zwei Stellen mit demselben Wissen —
und genau davor warnt der Job in seinem eigenen Kopf, an anderer Stelle:
„Bewusst importiert statt abgeschrieben: zwei Kopien derselben Adresse laufen
auseinander." Also steht der Aufbau jetzt hier, einmal. Der Job importiert von
hier, die Parser ebenso.

Der Aufbau
-----------
::

    data/archiv/jahrbuch/1103-2025-AZ.pdf/2026-08-17_9f3c1a2b4d5e.pdf
    data/archiv/jahrbuch/1103-2026-AZ.pdf/2027-01-09_ab12cd34ef56.pdf
                        └── Ordner = voller Dateiname ┘ └ Tag ┘ └ Inhalt ┘

Zwei Ebenen, und beide tragen ihre eigene Bedeutung:

* **Der Ordner** ist eine Adresse der Stadt. Weil ihr Dateiname den Jahrgang
  trägt, ist ein neuer Jahrgang ein neuer Ordner — die alten bleiben stehen.
* **Die Dateien darin** sind die Fassungen *derselben* Adresse. Sie entstehen,
  wenn die Stadt eine Ausgabe nachbessert, ohne sie umzubenennen.

Was das für einen Parser heißt
-------------------------------
Für Tabellen mit langer Reihe (1104: 2004–2025) ist die neueste Ausgabe immer
die beste — sie führt alles. Für die **kurzen** Tabellen ist sie es nicht:
Tabelle 1103 zeigt nur **drei Jahrgänge**, jede neue Ausgabe schiebt den
ältesten heraus. Wer nur die neueste liest, hat für immer drei Jahre. Wer alle
Ordner liest, hat nach fünf Jahren sieben.

Deshalb ist :func:`neueste_je_datei` die eigentliche Lesefunktion dieses
Moduls: Sie gibt **je Adresse** die zuletzt gesicherte Fassung — also je
Jahrgang eine Datei, nicht eine einzige Datei.

Was hier NICHT passiert
------------------------
Geladen wird nichts. Dieses Modul kennt kein Netz; es liest, was der Job
hinterlegt hat. Ist das Archiv leer (frisch geklonte Entwicklungsmaschine, CI),
geben die Lesefunktionen leere Listen zurück — die Aufrufer fallen dann auf den
Live-Download zurück und sagen das.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import urllib.parse
from datetime import date
from pathlib import Path

#: Wo das Archiv liegt. ``data/`` läuft ohnehin durchs nächtliche Backup samt
#: Off-Site-Spiegel — kein neuer Speicherpfad (s. ``scripts/backup_db.py``).
ROOT = Path(__file__).resolve().parent.parent


def archivpfad(pfad: str | Path | None = None) -> Path:
    """Der Archivordner — Argument, sonst ``ARCHIV_DIR``, sonst ``data/archiv``."""
    return Path(pfad or os.environ.get("ARCHIV_DIR") or ROOT / "data" / "archiv")


#: Die drei Bereiche, die der Job führt. Sie sind die erste Pfadebene.
BEREICHE = ("jahrbuch", "opendata", "lsn")


# --- Namen und Pfade --------------------------------------------------------

def dateiname(url: str) -> str:
    """Adresse → Dateiname für den Archivordner.

    Prozentkodierung wird aufgelöst (``…Schl%C3%BCsselzuweisung_0.csv`` →
    ``…Schlüsselzuweisung_0.csv``), Abfrageteil und Anker fallen weg. Alles,
    was kein harmloses Zeichen ist, wird zu ``_`` — insbesondere ``/`` und
    ``.``-Folgen, damit aus einer Adresse nie ein Pfad nach oben wird.

    Adressen ohne sprechenden Namen (die LSN-Downloads heißen ``/download/
    227086``) bekommen den letzten Pfadteil; wie die Datei am Ende heißt,
    entscheidet der Aufrufer über ``name``.
    """
    pfad = urllib.parse.urlsplit(url).path
    roh = urllib.parse.unquote(pfad.rstrip("/").rsplit("/", 1)[-1]) or "datei"
    sauber = re.sub(r"[^A-Za-z0-9._\-()äöüÄÖÜß ]+", "_", roh)
    sauber = re.sub(r"\.{2,}", ".", sauber).strip(". ")
    return sauber[:120] or "datei"


def inhalts_hash(inhalt: bytes) -> str:
    """Die ersten 12 Stellen des SHA-256 — kurz genug für einen Dateinamen,
    lang genug, dass zwei Fassungen derselben Tabelle nie kollidieren."""
    return hashlib.sha256(inhalt).hexdigest()[:12]


def endung(name: str) -> str:
    """``1103-2025-AZ.pdf`` → ``.pdf``; ohne Punkt im Namen ``""``."""
    stamm, punkt, rest = name.rpartition(".")
    return f".{rest.lower()}" if punkt and 1 <= len(rest) <= 5 else ""


def version_ablegen(archiv: Path, area: str, name: str, inhalt: bytes,
                    heute: date) -> tuple[Path, bool]:
    """Eine Fassung ablegen — oder feststellen, dass sie schon da liegt.

    Gibt ``(pfad, neu)`` zurück. ``neu=False`` heißt: Dieser Inhalt liegt
    bereits im Ordner, es wurde **nichts** geschrieben. Das ist die
    Idempotenz-Zusage des Archiv-Jobs, und sie hängt am Inhalt, nicht am Datum
    und nicht an den Kopfzeilen der Gegenseite.
    """
    h = inhalts_hash(inhalt)
    ordner = archiv / area / name
    for vorhanden in ordner.glob(f"*_{h}*"):
        if vorhanden.is_file():
            return vorhanden, False
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{heute.isoformat()}_{h}{endung(name)}"
    if ziel.exists():
        # Derselbe Tag, derselbe Hash-Präfix, andere Bytes — praktisch
        # ausgeschlossen, aber überschreiben wäre stiller Datenverlust.
        ziel = ordner / f"{heute.isoformat()}_{hashlib.sha256(inhalt).hexdigest()[:20]}{endung(name)}"
    ziel.write_bytes(inhalt)
    return ziel, True


# --- Manifest ---------------------------------------------------------------

def manifest_lesen(archiv: Path) -> dict:
    pfad = archiv / "manifest.json"
    if not pfad.is_file():
        return {}
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Ein kaputtes Manifest darf den Lauf nicht beenden: Ohne die
        # Kopfzeilen von gestern wird eben alles einmal neu geholt, und der
        # Hash-Vergleich verhindert trotzdem jede Dublette.
        return {}
    return daten.get("dateien", {}) if isinstance(daten, dict) else {}


def manifest_schreiben(archiv: Path, dateien: dict) -> None:
    """Atomar schreiben: erst daneben, dann umbenennen. Ein abgebrochener Lauf
    hinterlässt sonst ein halbes Manifest, und das nächste Mal wird alles neu
    geladen."""
    archiv.mkdir(parents=True, exist_ok=True)
    ziel = archiv / "manifest.json"
    tmp = archiv / "manifest.json.tmp"
    tmp.write_text(json.dumps(
        {"note": "Erzeugt von scripts/archive_statistik.py — je Adresse die "
                    "zuletzt gesehene Fassung. Die Dateien liegen daneben.",
         "dateien": dateien}, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    tmp.replace(ziel)


# --- Lesen ------------------------------------------------------------------

def fassungen(archiv: str | Path, area: str, name: str) -> list[Path]:
    """Alle gesicherten Fassungen **einer** Adresse, älteste zuerst.

    Sortiert wird über den Dateinamen, und das genügt: Er beginnt mit dem
    ISO-Datum (``2026-08-17_…``), das lexikografisch wie chronologisch
    sortiert. Kein ``mtime`` — der überlebt kein ``rsync`` und keine
    Wiederherstellung aus dem Backup.
    """
    ordner = archivpfad(archiv) / area / name
    if not ordner.is_dir():
        return []
    return sorted((p for p in ordner.iterdir()
                   if p.is_file() and not p.name.startswith(".")),
                  key=lambda p: p.name)


def neueste(archiv: str | Path, area: str, name: str) -> Path | None:
    """Die zuletzt gesicherte Fassung einer Adresse, oder ``None``."""
    alle = fassungen(archiv, area, name)
    return alle[-1] if alle else None


def neueste_je_datei(archiv: str | Path, area: str,
                     muster: str) -> list[Path]:
    """Je passender Adresse ihre neueste Fassung — nach Dateiname sortiert.

    ``muster`` ist ein Shell-Muster auf den **Ordnernamen**, also auf den
    vollen Dateinamen der Quelle: ``"1103-*.pdf"`` findet ``1103-2025-AZ.pdf``,
    ``1103-2026-AZ.pdf`` und was noch kommt.

    **Das ist die Funktion, für die es dieses Modul gibt.** Tabellen mit nur
    drei Jahrgängen verlieren mit jeder Ausgabe ihren ältesten; wer sie nur
    live liest, hat für immer drei Jahre. Wer hier alle Ausgaben abholt und
    ihre Jahrgänge zusammenlegt, hat nach fünf Jahren sieben.

    Sortiert wird nach Ordnername, und weil der Jahrgang darin steht
    (``1103-2025-AZ.pdf``), heißt das: älteste Ausgabe zuerst. Wer die Reihen
    in dieser Reihenfolge zusammenlegt, lässt die jüngere Ausgabe gewinnen —
    und das ist richtig, denn sie trägt die revidierten Werte.
    """
    wurzel = archivpfad(archiv) / area
    if not wurzel.is_dir():
        return []
    aus: list[Path] = []
    for ordner in sorted(wurzel.iterdir(), key=lambda p: p.name):
        if not ordner.is_dir() or not fnmatch.fnmatch(ordner.name, muster):
            continue
        letzte = neueste(archiv, area, ordner.name)
        if letzte is not None:
            aus.append(letzte)
    return aus


def herkunft_der_fassung(archiv: str | Path, pfad: Path) -> dict:
    """Was das Manifest über eine Fassung weiß — Adresse, Datum, Bytes.

    Gebraucht für den Herkunftsnachweis: Eine Zahl aus dem Archiv soll die
    **Original-Adresse** nennen, nicht unseren Dateipfad. Findet sich im
    Manifest kein Eintrag (Archiv von Hand befüllt, Manifest verloren), bleibt
    das dict leer — der Aufrufer fällt dann auf die hinterlegte Adresse zurück.
    """
    archiv = archivpfad(archiv)
    ziel = str(Path(pfad).resolve())
    for url, eintrag in manifest_lesen(archiv).items():
        gespeichert = eintrag.get("pfad")
        if not gespeichert:
            continue
        if str((archiv / gespeichert).resolve()) == ziel:
            return {"url": url, **eintrag}
    # Auch ohne Manifest ist das Datum bekannt: Es steht im Dateinamen.
    tag = Path(pfad).name.split("_", 1)[0]
    return {"zuerst_gesehen": tag} if re.fullmatch(r"\d{4}-\d\d-\d\d", tag) else {}
