#!/usr/bin/env python3
"""Die echten Ratsdaten lokal — abgespeckt, ohne Personenbezug, mit Datum.

**Warum es das gibt.** Wer eine Oberfläche oder ein Feature gegen eine leere
Datenbank baut, baut an den Daten vorbei: Eine Liste, die nie mehr als drei
Einträge sieht, bekommt keine Paginierung; ein Titel, der nie 200 Zeichen
lang wird, bricht später um; ein Feld, das lokal immer ``None`` ist, fällt
erst auf dem Server auf. Und jedes Mal die ganze Datenbank zu holen ist
umständlich genug, dass es niemand tut.

Also einmal holen, oft benutzen::

    python scripts/lokale_daten.py hol      # von dev holen (dauert ~1 min)
    python scripts/lokale_daten.py setz     # in data/ DIESES Worktrees legen
    python scripts/lokale_daten.py stand    # was liegt da, und wie alt?

Der Abzug liegt in einem Zwischenspeicher **außerhalb** der Worktrees
(``~/.cache/ratslotse``), damit ihn alle teilen und ``git status`` ihn nie
sieht. ``setz`` legt je Worktree eine eigene Kopie an — auf APFS als
Copy-on-write-Klon, der erst beim Schreiben Platz kostet. Eine gemeinsame
Datei ginge nicht: Der Store migriert beim Öffnen, und zwei Worktrees auf
verschiedenen Zweigen migrierten sie gegeneinander.

**Woher, und was dabei fehlt.** Vorgabe ist ``dev``, weil dort keine echten
Personendaten liegen. Der Preis: **auf dev laufen keine Cron-Jobs**, und was
nur ein Cron füllt, fehlt dort ganz. Gemessen am 02.09.2026 gegen beide
Server: Die Bauleitplan-Beteiligungen gibt es auf dev als Tabelle gar nicht
(auf Prod drei Zeilen), sonst ist dev fast vollständig — zwei leere und zwei
dünne Tabellen von 49 vergleichbaren. Wer genau so eine Cron-Tabelle braucht:
``hol --von prod``. Dort greift dieselbe Abspeckung, die nutzerbezogenen
Tabellen kommen also auch von dort nicht mit.

**Der Zwischenspeicher ist geteilt.** Holt eine andere Sitzung neu, ist die
eigene Kopie ab da veraltet, ohne dass etwas darauf hindeutet. ``stand`` sagt
es jetzt und nennt die Tabellen, die dir dadurch fehlen — am 02.09.2026 stand
``council_liquidity`` deshalb lokal auf 0 Zeilen, während der Abzug 137 hatte,
und der naheliegende Schluss („der Ingest ist ausgefallen") wäre falsch
gewesen.

**Was NICHT mitkommt**

* **Die Konten-Datenbank.** Sie trägt echte Adressen, Tokens und gespeicherte
  Gespräche. Dafür gibt es ``scripts/saat_konten.py``, das erfundene Konten
  baut. Eine Kopie der echten gehört auf kein Notebook.
* **Die nutzerbezogenen Tabellen der Rats-Datenbank.** Welche das sind, steht
  in ``council.store.COUNCIL_USER_OWNED_TABLES`` — dieselbe Liste, die das
  Konto-Löschen benutzt, und ein Test hält sie vollständig.
* **Embeddings und Anlagen-Volltexte.** Sie sind 60 % der Datei und für die
  Arbeit an einer Oberfläche ohne Belang. Gemessen am 02.09.2026: 666 MB
  gesamt, davon 292 MB Embeddings und 171 MB Anlagentexte.

Der Volltextindex bleibt drin — die Suche ist zu zentral, um sie lokal fehlen
zu lassen.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Wo der geteilte Abzug liegt — außerhalb jedes Worktrees.
SPEICHER = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ratslotse"
ABZUG = SPEICHER / "council.sqlite"
STAND = SPEICHER / "stand.json"

#: Der Städte-Speicher (`council/cities`) liegt daneben und kommt nur auf
#: Zuruf mit: Er ist rund 600 MB groß und wird für die Arbeit an einer
#: Oberfläche nicht gebraucht. Wer am Städtevergleich arbeitet, nimmt ihn mit.
STAEDTE_ABZUG = SPEICHER / "cities.sqlite"
STAEDTE_FERN = "/home/tim/app/data/cities.sqlite"
#: Die Rohernte je Stadt. Sie kommt beim `schieb` mit, damit der erste
#: Cron-Lauf auf dem Server dedupliziert statt sechs Städte neu zu holen.
STAEDTE_ROH_FERN = "/home/tim/app/data/cities-raw"

#: Quellen. Die Namen sind SSH-Hosts aus ``~/.ssh/config``.
QUELLEN = {
    "dev": ("tk-dev", "/home/tim/app/data/council.sqlite"),
    "prod": ("tk-nwz", "/home/tim/app/data/council.sqlite"),
}

#: Tabellen, deren INHALT nicht mitkommt (die Tabelle selbst bleibt, damit das
#: Schema vollständig ist). Als MUSTER und nicht als Namensliste: Die Vektor-
#: Tabellen heißen auf dev schon englisch und auf Prod noch deutsch, und beim
#: ersten Versuch fehlte genau deshalb `council_template_embeddings` — 55 MB,
#: die niemand braucht. Ein Muster überlebt die nächste Umbenennung.
OHNE_INHALT_MUSTER = r"%\_embeddings"

#: Spalten, die geleert werden — Rohtexte, die nur die Suche und die
#: KI-Pipeline brauchen. ``council_anlagen`` allein sind 171 MB.
OHNE_SPALTE = (
    ("council_anlagen", "raw_text"),
    ("council_attachments", "raw_text"),
)

#: Ab wann der Abzug als alt gilt.
ALT_AB_TAGEN = 14


def _nutzertabellen() -> list[str]:
    """Die nutzerbezogenen Tabellen — aus dem Code, nicht abgeschrieben."""
    sys.path.insert(0, str(WURZEL))
    from council.store import COUNCIL_USER_OWNED_TABLES

    return [tabelle for tabelle, _spalte in COUNCIL_USER_OWNED_TABLES]


# Läuft auf dem SERVER. Bewusst ohne jeden Import aus diesem Repo: Dort liegt
# ein anderer Stand, und mehr als sqlite3 braucht es nicht.
FERN = r'''
import json, os, sqlite3, sys
# Der Plan kommt über die Standardeingabe, NICHT als Argument: ssh fügt die
# Argumente zu einer Zeichenkette zusammen, die die Shell auf dem Server noch
# einmal auseinandernimmt — geschweifte Klammern in JSON überlebt das nicht.
quelle, ziel = sys.argv[1], sys.argv[2]
plan = json.loads(sys.stdin.read())
for rest in ("", "-wal", "-shm"):
    try: os.unlink(ziel + rest)
    except FileNotFoundError: pass
# Vollständige Kopie über die SQLite-API: nimmt einen offenen WAL korrekt mit,
# statt eine halb geschriebene Datei zu erwischen.
auf = sqlite3.connect("file:%s?mode=ro" % quelle, uri=True)
ab = sqlite3.connect(ziel)
auf.backup(ab)
auf.close()
vorher = os.path.getsize(ziel)
geleert = []
vektoren = [r[0] for r in ab.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ESCAPE '\\'",
    (plan["ohne_inhalt_muster"],))]
for t in vektoren + plan["nutzertabellen"]:
    try:
        n = ab.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
    except sqlite3.OperationalError:
        continue
    ab.execute('DELETE FROM "%s"' % t)
    geleert.append((t, n))
for t, s in plan["ohne_spalte"]:
    try:
        ab.execute('UPDATE "%s" SET "%s" = NULL WHERE "%s" IS NOT NULL' % (t, s, s))
    except sqlite3.OperationalError:
        continue
    geleert.append(("%s.%s" % (t, s), -1))
ab.commit()
ab.execute("VACUUM")
ab.close()
print(json.dumps({"vorher": vorher, "nachher": os.path.getsize(ziel),
                  "geleert": geleert}))
'''


def _lauf(befehl: list[str], eingabe: bytes | None = None, still: bool = False):
    return subprocess.run(befehl, input=eingabe, capture_output=still, check=True)


def hol(quelle: str) -> int:
    if quelle not in QUELLEN:
        print(f"Unbekannte Quelle {quelle!r} — bekannt: {', '.join(QUELLEN)}", file=sys.stderr)
        return 2
    host, pfad = QUELLEN[quelle]
    fern_ziel = f"/tmp/ratslotse-abzug-{os.getpid()}.sqlite"
    plan = json.dumps({
        "ohne_inhalt_muster": OHNE_INHALT_MUSTER,
        "ohne_spalte": [list(x) for x in OHNE_SPALTE],
        "nutzertabellen": _nutzertabellen(),
    })

    print(f"… Abzug auf {host} bauen (die Originaldatei wird nur gelesen)")
    t0 = time.monotonic()
    _lauf(["ssh", host, "cat > /tmp/ratslotse-abspecken.py"], FERN.encode())
    fertig = subprocess.run(
        ["ssh", host, "python3", "/tmp/ratslotse-abspecken.py", pfad, fern_ziel],
        input=plan, capture_output=True, text=True)
    if fertig.returncode:
        print(fertig.stdout + fertig.stderr, file=sys.stderr)
        return 1
    bericht = json.loads(fertig.stdout.strip().splitlines()[-1])

    SPEICHER.mkdir(parents=True, exist_ok=True)
    zwischen = ABZUG.with_suffix(".teil")
    print(f"… {bericht['nachher'] / 1e6:.0f} MB holen "
          f"(von {bericht['vorher'] / 1e6:.0f} MB abgespeckt)")
    with zwischen.open("wb") as ziel:
        subprocess.run(["ssh", host, "cat", fern_ziel], stdout=ziel, check=True)
    zwischen.replace(ABZUG)
    subprocess.run(["ssh", host, "rm", "-f", fern_ziel, "/tmp/ratslotse-abspecken.py"],
                   check=False)

    STAND.write_text(json.dumps({
        "quelle": quelle,
        "host": host,
        "geholt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": ABZUG.stat().st_size,
        "geleert": bericht["geleert"],
    }, indent=1, ensure_ascii=False) + "\n")
    print(f"✓ {ABZUG}  ({ABZUG.stat().st_size / 1e6:.0f} MB, "
          f"{time.monotonic() - t0:.0f}s)")
    print("  Jetzt in diesen Worktree legen:  python scripts/lokale_daten.py setz")
    return 0


def hol_staedte(quelle: str) -> int:
    """Den Städte-Speicher unverändert herunterladen.

    Keine Abspeckung wie bei der Rats-Datenbank: Es stehen ausschließlich
    öffentliche Ratsdokumente anderer Städte darin, keine Konten, keine
    Personendaten. Deshalb reicht ein `scp`.
    """
    host, _ = QUELLEN[quelle]
    SPEICHER.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    print(f"Städte-Speicher von {quelle} holen …")
    _lauf(["scp", f"{host}:{STAEDTE_FERN}", str(STAEDTE_ABZUG)])
    print(f"✓ {STAEDTE_ABZUG}  ({STAEDTE_ABZUG.stat().st_size / 1e6:.0f} MB, "
          f"{time.monotonic() - t0:.0f}s)")
    return 0


def schieb_staedte(ziel: str, ja: bool) -> int:
    """Den Städte-Speicher von HIER auf einen Server legen — das Gegenstück zu ``hol``.

    **Warum kein Backfill auf dem Server.** Die naheliegende Antwort wäre, dort
    neu zu ernten und zu beurteilen. Das hieße 14 GB PDFs aus sechs Städten,
    Stunden Rechenzeit und rund 16 $ — um zu reproduzieren, was hier schon
    liegt. Und es gibt nichts zusammenzuführen: Gemessen am 09.09.2026 hat die
    dev-VM gar keine ``cities.sqlite``, Prod eine 270-KB-Hülle, die der
    Web-Dienst beim ersten Öffnen angelegt hat.

    **Was mitkommt und was nicht.** Die Datenbank (rund 1,4 GB) und die
    Rohernte (rund 500 MB); die 14 GB PDFs nicht. Ihre Texte stehen längst
    extrahiert in ``texts``, und der Web-Dienst liest nie eine Datei. Neue
    Vorlagen bringen ihre PDFs mit dem Wochen-Cron mit.

    **Warum ohne Dienst-Neustart.** Das Backend öffnet die Städte-Datenbank je
    Anfrage (``web/backend/app/deps.py``); ein Dateitausch darunter ist damit
    sicher.

    **Die Weigerung ist der wichtigere Teil.** Liegen auf dem Ziel schon
    Vorlagen oder Rückmeldungen, bricht der Lauf ab: Eine Rückmeldung eines
    Ratsmitglieds darf kein lokaler Stand überschreiben, und sobald der Cron
    dort läuft, ist der Server der frischere. ``--ja`` überstimmt das für den
    Fall, dass jemand wirklich ersetzen will.
    """
    quelle = WURZEL / "data" / "cities.sqlite"
    if not quelle.exists():
        print(f"{quelle.relative_to(WURZEL)} gibt es nicht.", file=sys.stderr)
        return 1
    host, _ = QUELLEN[ziel]

    bestand = _fernbestand(host)
    if bestand and not ja:
        print(f"Auf {ziel} liegen schon {bestand['papers']} Vorlagen und "
              f"{bestand['feedback']} Rückmeldungen.", file=sys.stderr)
        print("Ein Sync würde sie überschreiben. --ja überstimmt das.",
              file=sys.stderr)
        return 1

    SPEICHER.mkdir(parents=True, exist_ok=True)
    kompakt = SPEICHER / "cities-schieb.sqlite"
    if kompakt.exists():
        kompakt.unlink()
    print("Kompakte Kopie schreiben (VACUUM INTO) …")
    # Über den Store, nicht per Dateikopie: Der WAL muss eingecheckt sein,
    # sonst fehlt dem Ziel alles seit dem letzten Checkpoint.
    sys.path.insert(0, str(WURZEL))
    from council.cities.store import CitiesStore

    store = CitiesStore(quelle)
    try:
        store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        store._conn.execute("VACUUM INTO ?", (str(kompakt),))
    finally:
        store.close()
    print(f"  {kompakt.stat().st_size / 1e6:.0f} MB")

    t0 = time.monotonic()
    print(f"Datenbank nach {ziel} kopieren …")
    _lauf(["scp", str(kompakt), f"{host}:{STAEDTE_FERN}"])
    roh = WURZEL / "data" / "cities-raw"
    if roh.exists():
        print("Rohernte kopieren (damit der erste Cron dedupliziert) …")
        _lauf(["ssh", host, f"mkdir -p {STAEDTE_ROH_FERN}"])
        _lauf(["rsync", "-a", "--delete", f"{roh}/", f"{host}:{STAEDTE_ROH_FERN}/"])
    print(f"✓ {ziel} hat den Stand von hier ({time.monotonic() - t0:.0f}s).")
    print("  Kein Dienst-Neustart nötig — das Backend öffnet die Datei je Anfrage.")
    return 0


def _fernbestand(host: str) -> dict | None:
    """Was auf dem Ziel schon liegt — oder ``None``, wenn dort nichts ist."""
    ergebnis = subprocess.run(
        ["ssh", host, "python3 - <<'EOF'\n"
         "import sqlite3, json, os\n"
         "p = '/home/tim/app/data/cities.sqlite'\n"
         "if not os.path.exists(p):\n"
         "    print('{}')\n"
         "else:\n"
         "    c = sqlite3.connect('file:' + p + '?mode=ro', uri=True)\n"
         "    def n(t):\n"
         "        try: return c.execute('SELECT count(*) FROM ' + t).fetchone()[0]\n"
         "        except Exception: return 0\n"
         "    print(json.dumps({'papers': n('papers'), 'feedback': n('feedback')}))\n"
         "EOF"],
        capture_output=True, text=True)
    if ergebnis.returncode != 0:
        return None
    try:
        daten = json.loads(ergebnis.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None
    if daten.get("papers") or daten.get("feedback"):
        return daten
    return None


def setz(ueberschreiben: bool) -> int:
    if not ABZUG.exists():
        print("Kein Abzug da. Erst holen:  python scripts/lokale_daten.py hol",
              file=sys.stderr)
        return 1
    ziel = WURZEL / "data" / "council.sqlite"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists() and not ueberschreiben:
        print(f"{ziel.relative_to(WURZEL)} gibt es schon "
              f"({ziel.stat().st_size / 1e6:.0f} MB). Mit --ueberschreiben ersetzen.",
              file=sys.stderr)
        return 1
    for rest in ("", "-wal", "-shm"):
        p = Path(str(ziel) + rest)
        if p.exists():
            p.unlink()
    # Auf APFS ein Copy-on-write-Klon: kostet erst Platz, wenn geschrieben wird.
    geklont = False
    if platform.system() == "Darwin":
        geklont = subprocess.run(["cp", "-c", str(ABZUG), str(ziel)],
                                 capture_output=True).returncode == 0
    if not geklont:
        shutil.copy2(ABZUG, ziel)
    print(f"✓ {ziel.relative_to(WURZEL)} ({'geklont' if geklont else 'kopiert'})")
    _warnen()
    return 0


def setz_staedte(ueberschreiben: bool) -> int:
    if not STAEDTE_ABZUG.exists():
        print("Kein Städte-Abzug da. Erst holen:  "
              "python scripts/lokale_daten.py hol --mit-staedten", file=sys.stderr)
        return 1
    ziel = WURZEL / "data" / "cities.sqlite"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists() and not ueberschreiben:
        print(f"{ziel.relative_to(WURZEL)} gibt es schon "
              f"({ziel.stat().st_size / 1e6:.0f} MB). Mit --ueberschreiben ersetzen.",
              file=sys.stderr)
        return 1
    for rest in ("", "-wal", "-shm"):
        q = Path(str(ziel) + rest)
        if q.exists():
            q.unlink()
    geklont = False
    if platform.system() == "Darwin":
        geklont = subprocess.run(["cp", "-c", str(STAEDTE_ABZUG), str(ziel)],
                                 capture_output=True).returncode == 0
    if not geklont:
        shutil.copy2(STAEDTE_ABZUG, ziel)
    print(f"✓ {ziel.relative_to(WURZEL)} ({'geklont' if geklont else 'kopiert'})")
    return 0


def _warnen() -> None:
    if not STAND.exists():
        return
    stand = json.loads(STAND.read_text())
    geholt = datetime.fromisoformat(stand["geholt"])
    tage = (datetime.now(timezone.utc) - geholt).days
    if tage >= ALT_AB_TAGEN:
        print(f"ACHTUNG: Der Abzug ist {tage} Tage alt (von {stand['quelle']}). "
              f"Gegen alte Daten zu prüfen fühlt sich an wie gegen echte.\n"
              f"  python scripts/lokale_daten.py hol", file=sys.stderr)


def stand() -> int:
    if not ABZUG.exists():
        print("Kein Abzug im Zwischenspeicher.")
        print(f"  {SPEICHER}")
        return 0
    s = json.loads(STAND.read_text()) if STAND.exists() else {}
    print(f"Abzug:   {ABZUG}")
    print(f"Größe:   {ABZUG.stat().st_size / 1e6:.0f} MB")
    print(f"Quelle:  {s.get('quelle', '?')} ({s.get('host', '?')})")
    print(f"Geholt:  {s.get('geholt', '?')}")
    leer = [t for t, _ in s.get("geleert", [])]
    if leer:
        print(f"Geleert: {', '.join(leer)}")
    hier = WURZEL / "data" / "council.sqlite"
    print(f"In diesem Worktree: "
          f"{'ja, %.0f MB' % (hier.stat().st_size / 1e6) if hier.exists() else 'nein'}")
    _kopie_gegen_abzug(hier)
    _warnen()
    return 0


def _kopie_gegen_abzug(kopie: Path) -> None:
    """Ist die Kopie in diesem Worktree älter als der Abzug — und was fehlt ihr?

    Der Zwischenspeicher wird von ALLEN Worktrees geteilt. Holt eine andere
    Sitzung neue Daten, ist die eigene Kopie ab da veraltet, ohne dass etwas
    darauf hindeutet. Am 02.09.2026 stand ``council_liquidity`` deshalb lokal
    auf 0 Zeilen, während der Abzug 137 hatte — und der naheliegende Schluss
    („der Ingest ist ausgefallen") wäre falsch gewesen.
    """
    if not kopie.exists():
        return
    if kopie.stat().st_mtime < ABZUG.stat().st_mtime - 60:
        print("\n  ACHTUNG: Deine Kopie ist ÄLTER als der Abzug — eine andere")
        print("  Sitzung hat inzwischen neu geholt. Frische Tabellen fehlen dir:")
        print("      python scripts/lokale_daten.py setz --ueberschreiben")

    sys.path.insert(0, str(WURZEL))
    from kern.dbfehler import nur_lesen
    try:
        a, b = nur_lesen(ABZUG), nur_lesen(kopie)
    except sqlite3.Error:
        return
    try:
        def zaehlen(verbindung):
            aus = {}
            for (name,) in verbindung.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"):
                try:
                    aus[name] = verbindung.execute(
                        f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                except sqlite3.Error:
                    pass
            return aus

        im_abzug, in_kopie = zaehlen(a), zaehlen(b)
        fehlen = sorted(n for n, z in im_abzug.items() if z > 0 and in_kopie.get(n, 0) == 0)
        if fehlen:
            print(f"\n  Im Abzug gefüllt, in deiner Kopie leer ({len(fehlen)}):")
            for name in fehlen[:12]:
                print(f"      {name:40s} {im_abzug[name]} Zeilen")
            if len(fehlen) > 12:
                print(f"      … und {len(fehlen) - 12} weitere")
            print("  → python scripts/lokale_daten.py setz --ueberschreiben")
    finally:
        a.close()
        b.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    unter = p.add_subparsers(dest="was", required=True)
    h = unter.add_parser("hol", help="Abzug vom Server bauen und herunterladen")
    h.add_argument("--von", default="dev", choices=sorted(QUELLEN))
    h.add_argument("--mit-staedten", action="store_true",
                   help="den Städte-Speicher (council/cities) mitnehmen, ~600 MB")
    s = unter.add_parser("setz", help="Abzug in data/ dieses Worktrees legen")
    s.add_argument("--ueberschreiben", action="store_true")
    s.add_argument("--mit-staedten", action="store_true",
                   help="den Städte-Speicher mitlegen")
    sch = unter.add_parser(
        "schieb", help="den Städte-Speicher von HIER auf einen Server legen")
    sch.add_argument("--nach", default="dev", choices=sorted(QUELLEN))
    sch.add_argument("--staedte", action="store_true", required=True,
                     help="bislang der einzige Speicher, der so wandert — die "
                          "Rats-Datenbank trägt Konten und geht nie von hier weg")
    sch.add_argument("--ja", action="store_true",
                     help="auch schieben, wenn auf dem Ziel schon Daten liegen")
    unter.add_parser("stand", help="Was liegt da, und wie alt?")
    args = p.parse_args()

    if args.was == "hol":
        code = hol(args.von)
        if code == 0 and args.mit_staedten:
            code = hol_staedte(args.von)
        return code
    if args.was == "schieb":
        return schieb_staedte(args.nach, args.ja)
    if args.was == "setz":
        code = setz(args.ueberschreiben)
        if code == 0 and args.mit_staedten:
            code = setz_staedte(args.ueberschreiben)
        return code
    return stand()


if __name__ == "__main__":
    raise SystemExit(main())
