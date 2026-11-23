#!/usr/bin/env python3
"""Bestand der Ratsdaten zweier Umgebungen nebeneinander — was „Frag den Rat“ liest.

**Anlass (23.11.2026).** Der Gold-Lauf von „Frag den Rat“ fand auf dev 142 von
200 Belegen im Kontext, auf Prod 158 — mit demselben Code. Acht der Belege, die
nur auf dev fehlten, gab es dort gar nicht: Sitzungen ohne einen einzigen
Beschluss, der Ausschuss für Allgemeine Angelegenheiten 2025 mit 0 statt 44
Beschlüssen. Die übrigen gab es, die Suche fand sie nicht — Verdacht auf
fehlende Embeddings, weil die nur ein Cron auf Prod nachrechnet. Ohne SSH auf
die VMs (1Password gesperrt) ließ sich das nicht nachzählen; dieser Lauf zählt
über den Deploy-Key.

**Was gezählt wird:** Beschlüsse, vergangene Sitzungen ohne Beschluss,
Protokolle, Wortbeiträge, Presse, Vorlagen- und Anlagentexte, je Bestand der
Anteil mit Embedding, Grundakten, Ortszuordnung — und je Gremium und Jahr die
Beschlüsse, damit eine Lücke ihren Namen bekommt. Nur Zahlen, keine Inhalte.
Die Datenbank wird nur lesend geöffnet (``mode=ro``).

Aufruf::

    # auf der VM
    .venv/bin/python scripts/council_inventory.py --collect --db data/council.sqlite > dev.json
    # auf dem Runner (nur Standardbibliothek)
    python3 scripts/council_inventory.py --compare dev.json prod.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date

#: Gremien-Lücken ab dieser Größe (Beschlüsse je Jahr) kommen in den Bericht.
GAP_MIN = 5
#: Jahre, für die die Gremien einzeln gezählt werden.
COMMITTEE_YEARS = 3


def _scalar(conn: sqlite3.Connection, sql: str, *args: object) -> int | str | None:
    """Ein Wert — oder ``None``, wenn die Tabelle in dieser Umgebung fehlt."""
    try:
        row = conn.execute(sql, args).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def _by_key(conn: sqlite3.Connection, sql: str, *args: object) -> dict[str, int]:
    try:
        return {str(k): int(v) for k, v in conn.execute(sql, args).fetchall()}
    except sqlite3.OperationalError:
        return {}


def collect(db: str, today: str | None = None) -> dict:
    """Die Kennzahlen einer Ratsdatenbank."""
    today = today or date.today().isoformat()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    decisions = ("FROM council_decisions d JOIN council_sessions s ON s.ksinr = d.ksinr "
                 "WHERE d.kind = 'decision'")
    out: dict = {
        "decisions_by_year": _by_key(
            conn, f"SELECT substr(s.session_date, 1, 4) y, count(*) {decisions} GROUP BY y"),
        "empty_past_sessions_by_year": _by_key(
            conn, "SELECT substr(s.session_date, 1, 4) y, count(*) FROM council_sessions s "
                  "WHERE s.session_date < ? AND NOT EXISTS "
                  "(SELECT 1 FROM council_decisions d WHERE d.ksinr = s.ksinr) GROUP BY y", today),
        "speeches_by_year": _by_key(
            conn, "SELECT substr(s.session_date, 1, 4) y, count(*) FROM council_speeches w "
                  "JOIN council_sessions s ON s.ksinr = w.ksinr GROUP BY y"),
        "latest_session_with_decisions": _scalar(conn, f"SELECT max(s.session_date) {decisions}"),
    }
    first_year = int(today[:4]) - COMMITTEE_YEARS + 1
    out["decisions_by_committee"] = {
        f"{y}|{c}": n for (y, c), n in (
            ((str(r[0]), str(r[1])), int(r[2])) for r in conn.execute(
                f"SELECT substr(s.session_date, 1, 4) y, s.committee, count(*) {decisions} "
                f"AND s.session_date >= ? GROUP BY y, s.committee", (f"{first_year}-01-01",)))}

    def share(base_sql: str, covered_sql: str) -> dict:
        base, covered = _scalar(conn, base_sql), _scalar(conn, covered_sql)
        return {"base": base, "covered": covered}

    out["totals"] = {
        "decisions": _scalar(conn, f"SELECT count(*) {decisions}"),
        "sessions": _scalar(conn, "SELECT count(*) FROM council_sessions"),
        "protocols": _scalar(conn, "SELECT count(*) FROM council_protocols"),
        "protocols_without_decisions": _scalar(
            conn, "SELECT count(*) FROM council_protocols p WHERE NOT EXISTS "
                  "(SELECT 1 FROM council_decisions d WHERE d.ksinr = p.ksinr)"),
        "speeches": _scalar(conn, "SELECT count(*) FROM council_speeches"),
        "press": _scalar(conn, "SELECT count(*) FROM council_press"),
        "press_latest": _scalar(conn, "SELECT max(date) FROM council_press"),
        "templates_with_text": _scalar(
            conn, "SELECT count(*) FROM council_templates WHERE raw_text IS NOT NULL AND raw_text != ''"),
        "attachments_with_text": _scalar(
            conn, "SELECT count(*) FROM council_attachments WHERE raw_text IS NOT NULL AND raw_text != ''"),
        "matter_items": _scalar(conn, "SELECT count(*) FROM council_matter_items"),
        "entity_matters": _scalar(conn, "SELECT count(*) FROM council_entity_matters"),
        "located_decisions": _scalar(conn, "SELECT count(DISTINCT decision_id) FROM council_decision_locations"),
    }
    out["embeddings"] = {
        "decisions": share(f"SELECT count(*) {decisions}",
                           "SELECT count(DISTINCT e.decision_id) FROM council_embeddings e "
                           "JOIN council_decisions d ON d.id = e.decision_id WHERE d.kind = 'decision'"),
        "speeches": share("SELECT count(*) FROM council_speeches",
                          "SELECT count(DISTINCT contribution_id) FROM council_speeches_embeddings"),
        "press": share("SELECT count(*) FROM council_press",
                       "SELECT count(DISTINCT press_id) FROM council_press_embeddings"),
        "templates": share(
            "SELECT count(*) FROM council_templates WHERE raw_text IS NOT NULL AND raw_text != ''",
            "SELECT count(DISTINCT template_number) FROM council_template_embeddings"),
        "attachments": share(
            "SELECT count(*) FROM council_attachments WHERE raw_text IS NOT NULL AND raw_text != ''",
            "SELECT count(DISTINCT document_id) FROM council_anlage_embeddings"),
    }
    out["tables"] = _tables(conn)
    conn.close()
    return out


#: Spalten, an denen man sieht, worauf eine Tabelle verweist: Die ersten fünf
#: sind über alle Umgebungen gleich (sie stammen aus dem Ratsinformationssystem
#: oder sind Texte), ``decision_id`` & Co. sind je Umgebung eigene Nummern.
KEY_COLUMNS = ("ksinr", "kvonr", "template_number", "document_id", "slug",
               "decision_id", "press_id", "contribution_id", "speech_id", "matter_id", "entity_id")


def _tables(conn: sqlite3.Connection) -> dict:
    """Je Tabelle die Zeilenzahl und die Verweis-Spalten (ohne FTS-Schattentabellen)."""
    out: dict = {}
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    shadow = ("_data", "_idx", "_content", "_docsize", "_config")
    for name in names:
        if any(name.endswith(x) for x in shadow) and "_fts" in name:
            continue
        try:
            rows = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
        except sqlite3.OperationalError:
            continue
        out[name] = {"rows": rows, "keys": [c for c in cols if c in KEY_COLUMNS]}
    return out


def _pct(part: object, whole: object) -> str:
    if not isinstance(part, int) or not isinstance(whole, int) or whole == 0:
        return "—"
    return f"{100 * part / whole:.0f} %"


def _diff(a: object, b: object) -> str:
    if isinstance(a, int) and isinstance(b, int):
        return f"{a - b:+d}"
    return ""


def compare(dev: dict, prod: dict) -> str:
    """Markdown-Bericht dev gegen Prod; Differenz immer dev − Prod."""
    lines = ["# Ratsbestand dev ↔ Prod", "", "Differenz = dev − Prod.", "",
             "## Bestände", "", "| | dev | Prod | Differenz |", "|---|---:|---:|---:|"]
    for key in prod.get("totals", {}):
        a, b = dev.get("totals", {}).get(key), prod["totals"][key]
        lines.append(f"| {key} | {a} | {b} | {_diff(a, b)} |")
    lines.append(f"| latest_session_with_decisions | {dev.get('latest_session_with_decisions')} | "
                 f"{prod.get('latest_session_with_decisions')} | |")
    lines += ["", "## Embeddings (Anteil des Bestands)", "",
              "| Bestand | dev | Prod |", "|---|---:|---:|"]
    for key, p in prod.get("embeddings", {}).items():
        d = dev.get("embeddings", {}).get(key, {})
        lines.append(f"| {key} | {d.get('covered')}/{d.get('base')} ({_pct(d.get('covered'), d.get('base'))}) "
                     f"| {p.get('covered')}/{p.get('base')} ({_pct(p.get('covered'), p.get('base'))}) |")
    for title, key in (("Beschlüsse je Jahr", "decisions_by_year"),
                       ("Vergangene Sitzungen ohne Beschluss", "empty_past_sessions_by_year"),
                       ("Wortbeiträge je Jahr", "speeches_by_year")):
        lines += ["", f"## {title}", "", "| Jahr | dev | Prod | Differenz |", "|---|---:|---:|---:|"]
        years = sorted(set(dev.get(key, {})) | set(prod.get(key, {})))
        for y in years:
            a, b = dev.get(key, {}).get(y, 0), prod.get(key, {}).get(y, 0)
            lines.append(f"| {y} | {a} | {b} | {_diff(a, b)} |")
    gaps = []
    keys = set(dev.get("decisions_by_committee", {})) | set(prod.get("decisions_by_committee", {}))
    for k in keys:
        a = dev.get("decisions_by_committee", {}).get(k, 0)
        b = prod.get("decisions_by_committee", {}).get(k, 0)
        if abs(a - b) >= GAP_MIN:
            gaps.append((a - b, k, a, b))
    lines += ["", f"## Gremien mit Lücke (ab {GAP_MIN} Beschlüssen je Jahr)", "",
              "| Jahr | Gremium | dev | Prod | Differenz |", "|---|---|---:|---:|---:|"]
    for d, k, a, b in sorted(gaps):
        year, committee = k.split("|", 1)
        lines.append(f"| {year} | {committee} | {a} | {b} | {d:+d} |")
    dt, pt = dev.get("tables", {}), prod.get("tables", {})
    if dt or pt:
        lines += ["", "## Tabellen, in denen dev mehr hat", "",
                  "Kandidaten für Daten, die es nur auf dev gibt (Anreicherungen, Nachläufe).", "",
                  "| Tabelle | dev | Prod | Verweise |", "|---|---:|---:|---|"]
        for name in sorted(set(dt) | set(pt)):
            a = dt.get(name, {}).get("rows", 0)
            b = pt.get(name, {}).get("rows", 0)
            if a > b and (b == 0 or a >= b * 1.05) and a - b >= 5:
                keys = ", ".join(dt.get(name, {}).get("keys", []))
                lines.append(f"| {name} | {a} | {b} | {keys} |")
        lines += ["", "## Tabellen, die nur eine Umgebung hat", "",
                  "| Tabelle | nur auf | Zeilen |", "|---|---|---:|"]
        for name in sorted(set(dt) ^ set(pt)):
            wo, rows = ("dev", dt[name]["rows"]) if name in dt else ("Prod", pt[name]["rows"])
            lines.append(f"| {name} | {wo} | {rows} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Bestand der Ratsdaten zweier Umgebungen nebeneinander")
    ap.add_argument("--collect", action="store_true", help="Kennzahlen dieser VM als JSON ausgeben")
    ap.add_argument("--db", default="data/council.sqlite")
    ap.add_argument("--compare", nargs=2, metavar=("DEV_JSON", "PROD_JSON"))
    args = ap.parse_args()
    if args.collect:
        json.dump(collect(args.db), sys.stdout, ensure_ascii=False, indent=1)
        return 0
    if args.compare:
        dev = json.load(open(args.compare[0], encoding="utf-8"))
        prod = json.load(open(args.compare[1], encoding="utf-8"))
        sys.stdout.write(compare(dev, prod))
        return 0
    ap.error("--collect oder --compare angeben")
    return 2


if __name__ == "__main__":
    sys.exit(main())
