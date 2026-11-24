#!/usr/bin/env python3
"""Die Ratsdaten von Prod nach dev spiegeln — nachts, ohne Personenbezug.

**Warum.** Auf dev laufen keine Crons. Nach der Zusammenführung am 27.08.2026
lief dev Prod deshalb davon: Am 23.11.2026 fehlten dort 358 Beschlüsse, 150
Protokolle, 9.709 Wortbeiträge (−18 %, in jedem Jahr seit 2018) und alle
Pressemitteilungen seit dem 26.08.; der Ausschuss für Allgemeine
Angelegenheiten hatte 2024 und 2025 null Beschlüsse statt 52 und 44
(gemessen mit ``ops-council-inventory.yml``). Der Gold-Lauf von „Frag den Rat“
fand auf dev deshalb 142 von 200 Belegen, auf Prod 158 — mit demselben Code.
Jede Messung auf dev war damit verzerrt. Tims Entscheidung (23.11.2026): dev
bekommt die Ratsdaten von Prod.

**Zwei Schritte, zwei Maschinen** (``ops-dev-mirror.yml`` ruft beide auf):

``snapshot`` — auf **Prod**. Eine vollständige Kopie über die SQLite-API
(nimmt einen offenen WAL korrekt mit, die Originaldatei wird nur gelesen).
Danach werden die nutzerbezogenen Tabellen geleert —
``council.store.COUNCIL_USER_OWNED_TABLES``, dieselbe Liste, die das
Konto-Löschen benutzt, dazu ``COUNCIL_USER_TEXT_TABLES`` (gestellte Fragen
ohne Konto-Spalte) — mit ``secure_delete`` und ``VACUUM INTO``, damit nichts
davon in freien Seiten der Datei überlebt. Das passiert, **bevor** die Datei
Prod verlässt, in einem nur für den eigenen Nutzer lesbaren Verzeichnis.

``swap`` — auf **dev**. Prüft die Kopie (Integrität, und dass sie nicht
deutlich weniger Beschlüsse trägt als dev), übernimmt, was es nur auf dev gibt,
und tauscht die Datei aus. Die alte bleibt als Sicherung liegen.

**Was dev behält:**

* ``DEV_ONLY_TABLES`` — Anreicherungen hinter Schaltern, die bisher nur auf dev
  gelaufen sind (Fachwörter, Wahlprogramm-Einordnungen, Dossiers, …). Sie
  hängen an Schlüsseln, die über alle Umgebungen gleich sind (Vorlagennummer,
  Sitzung, Gegenstand), und überleben den Tausch deshalb.
* Jede Tabelle, die auf Prod leer und auf dev gefüllt ist und an keiner
  umgebungseigenen Nummer hängt — damit eine neue dev-Anreicherung nicht über
  Nacht verschwindet, bevor jemand sie in die Liste einträgt.
* Die nutzerbezogenen Tabellen von dev (die Konten von dev, nicht die von Prod).

Gibt es eine Zeile auf beiden Seiten, gewinnt Prod (``INSERT OR IGNORE``).

**Was sich auf dev ändert:** Die Beschluss-ids sind danach die von Prod. Was in
der Konten-Datenbank von dev auf eine Beschluss-id zeigt (gemerkte Beschlüsse,
Belege alter Gespräche), zeigt danach auf einen anderen Beschluss — dev trägt
nur Testkonten. Dafür sind Links zwischen dev und Prod ab jetzt dieselben.

Was verloren ginge, steht im Bericht: Tabellen, die dev voller hatte und die
nicht übernommen wurden, und Spalten, die es nur in der dev-Datei gab.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

#: Anreicherungen, die es (noch) nur auf dev gibt. Wer auf dev etwas
#: anreichert, das Prod nicht hat, trägt die Tabelle hier ein — der Bericht des
#: Spiegels nennt jede Tabelle, die dev voller hatte und die verloren ginge.
DEV_ONLY_TABLES = (
    "template_terms",             # Fachwörter aus der Vorlage (begriffe-aus-vorlage)
    "template_program_stances",   # Wahlprogramme am Punkt (wahlprogramm-am-punkt)
    "budget_draft_findings",      # Was der Haushaltsentwurf zeigt (haushaltsentwurf-befunde)
    "program_vectors",            # Vektoren der Wahlprogramme dazu
    "template_dossiers",          # Vorlagen aufbereiten (Prod-Bestand läuft nach)
    "agenda_item_arguments",      # Argumente am Punkt (punkt-argumente)
    "page_questions",             # Vorschlagsfragen der Punkt-Seite
    "council_session_sentences",  # Sitzungssätze
    "motion_extracts",            # Anträge ausgelesen
)

#: Spalten, die auf eine umgebungseigene Nummer zeigen. Eine Tabelle damit wird
#: nie automatisch übernommen — die Nummer bedeutete auf dev etwas anderes.
ENV_ID_COLUMNS = {"decision_id", "contribution_id", "press_id", "speech_id",
                  "entity_id", "matter_id"}

#: Die Kopie darf nicht deutlich kleiner sein als das, was dev schon hat.
#: Fehlen auf Prod plötzlich zehn Prozent der Beschlüsse, ist etwas kaputt —
#: dann bleibt dev, wie es ist, und der Lauf wird rot.
MIN_DECISION_RATIO = 0.9


def _user_owned_tables() -> list[str]:
    """Aus dem Code der Maschine, auf der das Skript läuft (``~/app``)."""
    from council.store import COUNCIL_USER_OWNED_TABLES

    return [table for table, _owner in COUNCIL_USER_OWNED_TABLES]


def _user_text_tables() -> list[str]:
    """Freitext von Nutzern ohne Konto-Spalte (s. ``COUNCIL_USER_TEXT_TABLES``).
    Ein älterer Stand auf der Maschine kennt die Liste vielleicht noch nicht —
    dann gilt die Fassung aus diesem Skript."""
    try:
        from council.store import COUNCIL_USER_TEXT_TABLES
        return list(COUNCIL_USER_TEXT_TABLES)
    except ImportError:
        return ["council_partei_meinungen_cache"]


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _rows(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def _is_fts(table: str) -> bool:
    return "_fts" in table


def snapshot(db: str, out: str, user_owned: list[str]) -> dict:
    """Kopie ohne Personenbezug. Die Quelle wird nur gelesen.

    Ein bloßes ``DELETE`` reicht nicht: SQLite gibt die Seiten nur frei, der
    alte Inhalt stünde weiter in der Datei und ginge mit nach dev. Deshalb
    ``secure_delete`` (überschreibt mit Nullen) und danach ``VACUUM INTO`` in
    eine frische Datei, die keine freien Seiten mehr kennt. Die Zwischenkopie
    wird gelöscht, bevor die Funktion zurückkehrt.
    """
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(out + suffix).unlink(missing_ok=True)
    work = out + ".arbeit"
    for suffix in ("", "-journal"):
        Path(work + suffix).unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(work)
    src.backup(dst)
    src.close()
    dst.execute("PRAGMA secure_delete = ON")
    cleared: dict[str, int] = {}
    existing = set(_tables(dst))
    for table in user_owned:
        if table in existing:
            cleared[table] = _rows(dst, table)
            dst.execute(f'DELETE FROM "{table}"')
    dst.commit()
    dst.execute("VACUUM INTO ?", (out,))
    dst.close()
    for suffix in ("", "-journal"):
        Path(work + suffix).unlink(missing_ok=True)
    return {"bytes": os.path.getsize(out), "cleared": cleared}


def _copy_rows(old: sqlite3.Connection, new: sqlite3.Connection, table: str) -> int:
    """Zeilen von ``old`` nach ``new``, die es dort noch nicht gibt. Über die
    gemeinsamen Spalten — die Schemata der beiden Dateien können auseinander
    liegen (dev ist im Code weiter als Prod)."""
    cols = [c for c in _columns(old, table) if c in set(_columns(new, table))]
    if not cols:
        return 0
    names = ", ".join(f'"{c}"' for c in cols)
    marks = ", ".join("?" * len(cols))
    before = _rows(new, table)
    new.executemany(f'INSERT OR IGNORE INTO "{table}" ({names}) VALUES ({marks})',
                    old.execute(f'SELECT {names} FROM "{table}"'))
    return _rows(new, table) - before


def swap(new_path: str, db: str, user_owned: list[str], backup: str | None = None,
         dry_run: bool = False) -> dict:
    """Die Kopie von Prod an die Stelle der dev-Datei setzen.

    Erst prüfen und anreichern (in der NEUEN Datei), dann tauschen. Bricht vor
    dem Tausch ab, wenn die Kopie kaputt oder unplausibel klein ist; die
    dev-Datei bleibt dann unberührt.
    """
    report: dict = {"preserved": {}, "auto_preserved": {}, "lost_tables": {}, "dev_only_columns": {}}
    new = sqlite3.connect(new_path)
    check = new.execute("PRAGMA quick_check").fetchone()[0]
    if check != "ok":
        raise SystemExit(f"Kopie von Prod ist beschädigt: {check}")
    old = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

    def decisions(conn: sqlite3.Connection) -> int:
        try:
            return int(conn.execute(
                "SELECT count(*) FROM council_decisions WHERE kind = 'decision'").fetchone()[0])
        except sqlite3.OperationalError:
            return 0

    report["decisions_dev"], report["decisions_prod"] = decisions(old), decisions(new)
    if report["decisions_dev"] and report["decisions_prod"] < MIN_DECISION_RATIO * report["decisions_dev"]:
        raise SystemExit(
            f"Unplausibel: Prod-Kopie trägt {report['decisions_prod']} Beschlüsse, dev "
            f"{report['decisions_dev']} — dev bleibt, wie es ist.")

    old_tables, new_tables = set(_tables(old)), set(_tables(new))
    keep = [t for t in (*DEV_ONLY_TABLES, *user_owned) if t in old_tables and t in new_tables]
    for table in keep:
        report["preserved"][table] = _copy_rows(old, new, table)
    for table in sorted(old_tables & new_tables):
        if table in keep or _is_fts(table):
            continue
        dev_rows, prod_rows = _rows(old, table), _rows(new, table)
        if dev_rows and not prod_rows and not (set(_columns(old, table)) & ENV_ID_COLUMNS):
            report["auto_preserved"][table] = _copy_rows(old, new, table)
        elif dev_rows > prod_rows * 1.05 and dev_rows - prod_rows >= 5:
            report["lost_tables"][table] = {"dev": dev_rows, "prod": prod_rows}
    for table in sorted(old_tables - new_tables):
        if not _is_fts(table) and _rows(old, table):
            report["lost_tables"][table] = {"dev": _rows(old, table), "prod": None}
    for table in sorted(old_tables & new_tables):
        extra = set(_columns(old, table)) - set(_columns(new, table))
        for col in sorted(extra):
            filled = int(old.execute(
                f'SELECT count(*) FROM "{table}" WHERE "{col}" IS NOT NULL').fetchone()[0])
            if filled:
                report["dev_only_columns"][f"{table}.{col}"] = filled
    new.commit()
    new.close()
    old.close()
    if dry_run:
        report["swapped"] = False
        return report

    # Platz: die Sicherung (≈ alte Datei) und, wenn die neue Datei auf einer
    # anderen Platte liegt, ihre Kopie neben die alte. Der Workflow legt sie
    # gleich nach data/, dann ist der Tausch ein Umbenennen.
    here = Path(db).resolve().parent
    need = (1.2 * os.path.getsize(db) if backup else 0)
    if os.stat(new_path).st_dev != os.stat(here).st_dev:
        need += os.path.getsize(new_path)
    free = shutil.disk_usage(here).free
    if free < need:
        raise SystemExit(f"Zu wenig Platz neben {db}: {free / 1e9:.1f} GB frei, "
                         f"gebraucht ≈ {need / 1e9:.1f} GB.")
    if backup:
        Path(backup).parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        dst = sqlite3.connect(backup)
        src.backup(dst)
        src.close()
        dst.close()
    staged = db + ".spiegel"
    shutil.move(new_path, staged)
    # Dieselben Rechte wie die alte Datei: Das Skript läuft mit umask 077, der
    # Dienst muss die neue Datei aber genauso öffnen können wie bisher.
    os.chmod(staged, os.stat(db).st_mode & 0o777)
    # Den WAL der alten Datei leeren, BEVOR sie ersetzt wird: Ein Rest-WAL
    # neben der neuen Datei würde beim nächsten Öffnen in sie eingespielt.
    # Der laufende Dienst hält die alte Datei bis zum Neustart offen; der
    # Workflow startet ihn direkt danach neu.
    try:
        live = sqlite3.connect(db)
        live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        live.close()
    except sqlite3.Error:
        pass
    os.replace(staged, db)
    for suffix in ("-wal", "-shm"):
        Path(db + suffix).unlink(missing_ok=True)
    report["swapped"] = True
    return report


def markdown(report: dict) -> str:
    lines = ["# Ratsdaten Prod → dev", "",
             f"Beschlüsse vorher (dev): {report.get('decisions_dev')} · "
             f"nachher (Prod): {report.get('decisions_prod')} · "
             f"getauscht: {'ja' if report.get('swapped') else 'nein'}", ""]
    for title, key in (("Von dev übernommen (Liste)", "preserved"),
                       ("Von dev übernommen (nur dev hatte Daten)", "auto_preserved")):
        lines += [f"## {title}", "", "| Tabelle | Zeilen dazu |", "|---|---:|"]
        lines += [f"| {t} | {n} |" for t, n in report.get(key, {}).items()] or ["| — | |"]
        lines.append("")
    lines += ["## Verloren gegangen", "",
              "Tabellen, die dev voller hatte, und Spalten, die es nur in der dev-Datei gab. "
              "Steht hier etwas, gehört die Tabelle in `DEV_ONLY_TABLES` oder auf Prod.", "",
              "| Tabelle / Spalte | dev | Prod |", "|---|---:|---:|"]
    lost = [f"| {t} | {v['dev']} | {v['prod']} |" for t, v in report.get("lost_tables", {}).items()]
    lost += [f"| {c} | {n} gefüllt | — |" for c, n in report.get("dev_only_columns", {}).items()]
    lines += lost or ["| — | | |"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Ratsdaten von Prod nach dev spiegeln")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("snapshot", help="auf Prod: Kopie ohne nutzerbezogene Tabellen")
    s1.add_argument("--db", default="data/council.sqlite")
    s1.add_argument("--out", required=True)
    s2 = sub.add_parser("swap", help="auf dev: Kopie prüfen, anreichern, tauschen")
    s2.add_argument("--new", required=True)
    s2.add_argument("--db", default="data/council.sqlite")
    s2.add_argument("--backup", default="data/backups/council_vor-spiegel.sqlite")
    s2.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, os.getcwd())
    os.umask(0o077)  # Kopien nur für den eigenen Nutzer lesbar
    user_owned = _user_owned_tables()
    if args.cmd == "snapshot":
        print(json.dumps(snapshot(args.db, args.out, user_owned + _user_text_tables())))
        return 0
    report = swap(args.new, args.db, user_owned, backup=args.backup, dry_run=args.dry_run)
    sys.stdout.write(markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
