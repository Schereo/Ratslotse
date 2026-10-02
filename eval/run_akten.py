#!/usr/bin/env python3
"""Akten-Abdeckung (Benchmark B4 aus docs/plan-akte.md) — ohne Sprachmodell.

Frage: Landet alles, was ein Gold-Fall als Beleg nennt, in DERSELBEN Akte wie
sein Kernbeschluss? Gemessen wird nicht die Suche, sondern die Gruppierung:
Ist die Akte vollständig, kann die Suche sie ganz lesen; fehlt ein Beleg in
der Akte, hilft auch die beste Suche nicht.

Ablauf je Fall (``eval/cases_deep_gold.json``):

1. Jeder Material-Eintrag wird in Datenbank-Zeilen aufgelöst (Beschluss,
   Wortbeitrag, Pressemitteilung, Vorlage, Tagesordnungspunkt). Ein Eintrag,
   der keine Zeile trifft, ist ein Fehler im Gold — er wird gemeldet, nicht
   gezählt.
2. Der **Einstieg** sind die Beschlüsse hinter den Kernfakten (Gewicht 3);
   gibt es dort keinen Beschluss-Beleg, alle Beschluss-Belege des Falls.
3. Eine **Methode** baut aus dem Einstieg die Akte. Gemessen wird, welcher
   Anteil der Belege in ihr liegt, und wie groß sie ist — eine Akte, die die
   halbe Datenbank enthält, deckt alles ab und taugt nichts.

Personen- und Sitzungsfragen sind keine Vorgänge; ein Fall mit
``"akte": false`` zählt hier nicht mit (sein Maß ist der Gold-Lauf).
Pressemitteilungen hängen bis Phase 2 an keiner Akte; die Abdeckung wird
deshalb auch **ohne Presse** ausgewiesen (Tor von Phase 1).

Methoden:

- ``vorlage``: Beschlüsse derselben Vorlagennummer (``26/0396`` = ``26/0396/1``).
- ``entitaeten``: heutiger Stand — alle Beschlüsse, die eine Themen-Entität
  mit dem Einstieg teilen.
- ``grundakte``: ab Phase 1 (``council_matter_items``).

Alle Methoden hängen Wortbeiträge über Sitzung und TOP an ihren Beschluss
(dieselbe Regel wie ``wortbeitraege_zu_beschluessen``, ohne Deckel).
Pressemitteilungen hängen heute an keiner Akte.

    python eval/run_akten.py                       # alle Methoden, data/council.sqlite
    python eval/run_akten.py --methode entitaeten --zeigen
    python eval/run_akten.py --db /pfad/zum/abzug.sqlite --save label
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

CASES = WURZEL / "eval" / "cases_deep_gold.json"
ERGEBNISSE = WURZEL / "eval" / "results" / "akten"
METHODEN = ("vorlage", "entitaeten", "grundakte")


def _vorlage_basis(nr: str | None) -> str:
    """„26/0396/1" → „26/0396"; leer bleibt leer."""
    m = re.match(r"\s*(\d{2}/\d{4})", nr or "")
    return m.group(1) if m else ""


# --------------------------------------------------------------------------- #
# Belege auflösen
# --------------------------------------------------------------------------- #

def belege_aufloesen(conn: sqlite3.Connection, m: dict) -> set[tuple[str, int]]:
    """Material-Eintrag → {(Art, id)} der Zeilen, die er meint."""
    art = m["art"]
    if art == "beschluss":
        rows = conn.execute(
            "SELECT d.id FROM council_decisions d JOIN council_sessions s ON s.ksinr = d.ksinr "
            "WHERE substr(s.session_date, 1, 10) = ? AND s.committee LIKE ? AND d.title LIKE ?",
            (m["session_date"], f"%{m.get('committee', '')}%",
             f"%{m.get('titel_enthaelt', '')}%")).fetchall()
        return {("beschluss", r[0]) for r in rows}
    if art == "debatte":
        out = set()
        for wort in m["text_enthaelt_eins"]:
            rows = conn.execute(
                "SELECT w.id FROM council_speeches w JOIN council_sessions s ON s.ksinr = w.ksinr "
                "WHERE substr(s.session_date, 1, 10) = ? "
                "AND (w.text LIKE ? OR coalesce(w.answer, '') LIKE ?)",
                (m["session_date"], f"%{wort}%", f"%{wort}%")).fetchall()
            out |= {("debatte", r[0]) for r in rows}
        return out
    if art == "presse":
        rows = conn.execute(
            "SELECT id FROM council_press WHERE substr(date, 1, 10) = ? AND title LIKE ?",
            (m["date"], f"%{m['titel_enthaelt']}%")).fetchall()
        return {("presse", r[0]) for r in rows}
    if art == "vorlage":
        rows = conn.execute(
            "SELECT kvonr FROM council_templates WHERE template_number LIKE ?",
            (f"{m['template_number']}%",)).fetchall()
        return {("vorlage", r[0]) for r in rows}
    if art == "beratung":
        rows = conn.execute(
            "SELECT a.id FROM council_agenda_items a JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE substr(s.session_date, 1, 10) = ? AND s.committee LIKE ? AND a.title LIKE ?",
            (m["session_date"], f"%{m.get('committee', '')}%",
             f"%{m['titel_enthaelt']}%")).fetchall()
        return {("beratung", r[0]) for r in rows}
    raise ValueError(f"unbekannte Material-Art {art!r}")


def einstieg(case: dict, aufgeloest: dict[str, set]) -> set[int]:
    """Beschluss-ids hinter den Kernfakten (Gewicht 3), sonst alle Beschluss-Belege."""
    kern = {p["id"] for p in case["pflicht"] if p["gewicht"] >= 3}
    def ids(nur_kern: bool) -> set[int]:
        return {i for m in case.get("material", [])
                if m["art"] == "beschluss" and (not nur_kern or set(m["fuer"]) & kern)
                for art, i in aufgeloest.get(m["id"], set())}
    return ids(True) or ids(False)


# --------------------------------------------------------------------------- #
# Akten bauen
# --------------------------------------------------------------------------- #

def _beschluesse_zu_vorlagen(conn, basen: set[str]) -> set[int]:
    out: set[int] = set()
    for b in basen:
        out |= {r[0] for r in conn.execute(
            "SELECT id FROM council_decisions WHERE template_number LIKE ?", (f"{b}%",))}
    return out


def _akte_aus_beschluessen(store, conn, beschluesse: set[int]) -> set[tuple[str, int]]:
    """Beschlüsse plus alles, was heute schon eindeutig an ihnen hängt:
    Wortbeiträge ihres TOPs, Vorlage und Tagesordnungspunkte derselben Nummer."""
    akte = {("beschluss", i) for i in beschluesse}
    if not beschluesse:
        return akte
    decs = store.get_decisions_by_ids(sorted(beschluesse))
    for w in store.wortbeitraege_zu_beschluessen(decs, max_gesamt=10**6, max_je_top=10**6):
        akte.add(("debatte", w["id"]))
    basen = {_vorlage_basis(d.get("template_number")) for d in decs} - {""}
    for b in basen:
        akte |= {("vorlage", r[0]) for r in conn.execute(
            "SELECT kvonr FROM council_templates WHERE template_number LIKE ?", (f"{b}%",))}
        akte |= {("beratung", r[0]) for r in conn.execute(
            "SELECT id FROM council_agenda_items WHERE template_number LIKE ?", (f"{b}%",))}
    return akte


def akte_vorlage(store, conn, start: set[int]) -> set[tuple[str, int]]:
    basen = {_vorlage_basis(r[0]) for r in conn.execute(
        f"SELECT template_number FROM council_decisions WHERE id IN ({','.join('?' * len(start))})",
        sorted(start))} - {""}
    return _akte_aus_beschluessen(store, conn, set(start) | _beschluesse_zu_vorlagen(conn, basen))


def akte_entitaeten(store, conn, start: set[int]) -> set[tuple[str, int]]:
    ph = ",".join("?" * len(start))
    ents = {r[0] for r in conn.execute(
        f"SELECT entity_id FROM council_entity_links WHERE decision_id IN ({ph})", sorted(start))}
    beschluesse = set(start)
    if ents:
        beschluesse |= {r[0] for r in conn.execute(
            f"SELECT decision_id FROM council_entity_links WHERE entity_id IN "
            f"({','.join('?' * len(ents))})", sorted(ents))}
    return _akte_aus_beschluessen(store, conn, beschluesse)


def akte_grundakte(store, conn, start: set[int]) -> set[tuple[str, int]]:
    """Ab Phase 1: alle Zeilen der Grundakten, in denen der Einstieg liegt."""
    try:
        ph = ",".join("?" * len(start))
        matters = {r[0] for r in conn.execute(
            f"SELECT matter_id FROM council_matter_items WHERE item_type = 'decision' "
            f"AND item_id IN ({ph})", sorted(start))}
    except sqlite3.OperationalError:
        return set()
    if not matters:
        return set()
    namen = {"decision": "beschluss", "speech": "debatte", "press": "presse",
             "template": "vorlage", "agenda_item": "beratung"}
    rows = conn.execute(
        f"SELECT item_type, item_id FROM council_matter_items WHERE matter_id IN "
        f"({','.join('?' * len(matters))})", sorted(matters)).fetchall()
    return {(namen[t], i) for t, i in rows if t in namen}


BAUER = {"vorlage": akte_vorlage, "entitaeten": akte_entitaeten, "grundakte": akte_grundakte}


# --------------------------------------------------------------------------- #
# Messen
# --------------------------------------------------------------------------- #

def messen(db: Path, methoden: list[str], zeigen: bool = False) -> dict:
    from council.store import CouncilStore

    store = CouncilStore(db)
    conn = store._conn
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    bericht: dict = {"db": str(db), "methoden": {}}
    for methode in methoden:
        if methode == "grundakte" and not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'council_matter_items'").fetchone():
            print(f"[{methode}] übersprungen — council_matter_items fehlt (Phase 1)")
            continue
        faelle, summe_ok, summe_n = [], 0, 0
        ohne_ok = ohne_n = 0
        je_art: dict[str, list[int]] = {}
        for case in cases:
            if case.get("akte") is False:
                continue
            aufgeloest = {m["id"]: belege_aufloesen(conn, m) for m in case.get("material", [])}
            leer = [mid for mid, rows in aufgeloest.items() if not rows]
            start = einstieg(case, aufgeloest)
            akte = BAUER[methode](store, conn, start) if start else set()
            drin = {mid: bool(rows & akte) for mid, rows in aufgeloest.items() if rows}
            ok = sum(drin.values())
            summe_ok += ok
            summe_n += len(drin)
            arten = {m["id"]: m["art"] for m in case.get("material", [])}
            for mid, da in drin.items():
                je_art.setdefault(arten[mid], [0, 0])
                je_art[arten[mid]][0] += da
                je_art[arten[mid]][1] += 1
                if arten[mid] != "presse":
                    ohne_ok += da
                    ohne_n += 1
            groesse = {art: sum(1 for a, _ in akte if a == art)
                       for art in ("beschluss", "debatte", "presse", "vorlage", "beratung")}
            faelle.append({"id": case["id"], "abdeckung": round(ok / len(drin), 3) if drin else None,
                           "drin": ok, "belege": len(drin), "fehlt": [k for k, v in drin.items() if not v],
                           "unaufloesbar": leer, "einstieg": sorted(start), "groesse": groesse})
            if zeigen:
                print(f"[{methode}] {case['id']:48} {ok:2}/{len(drin):2}  "
                      f"Akte {groesse}  fehlt {faelle[-1]['fehlt']}"
                      + (f"  UNAUFLÖSBAR {leer}" if leer else ""))
        gesamt = round(summe_ok / summe_n, 3) if summe_n else None
        mittel_groesse = {art: round(sum(f["groesse"][art] for f in faelle) / len(faelle), 1)
                          for art in faelle[0]["groesse"]} if faelle else {}
        ohne = round(ohne_ok / ohne_n, 3) if ohne_n else None
        bericht["methoden"][methode] = {"abdeckung": gesamt, "abdeckung_ohne_presse": ohne,
                                        "belege": summe_n, "je_art": je_art,
                                        "mittlere_groesse": mittel_groesse, "faelle": faelle}
        print(f"[{methode}] Abdeckung {gesamt:.1%} ({summe_ok}/{summe_n}), ohne Presse "
              f"{ohne:.1%} ({ohne_ok}/{ohne_n}), je Art "
              + ", ".join(f"{a} {v[0]}/{v[1]}" for a, v in sorted(je_art.items()))
              + f", mittlere Akte {mittel_groesse}")
    store.close()
    return bericht


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", type=Path, default=WURZEL / "data" / "council.sqlite")
    ap.add_argument("--methode", choices=METHODEN, action="append")
    ap.add_argument("--zeigen", action="store_true", help="je Fall eine Zeile")
    ap.add_argument("--save", metavar="LABEL", help=f"Ergebnis nach {ERGEBNISSE}/<label>.json")
    args = ap.parse_args()
    bericht = messen(args.db, args.methode or list(METHODEN), zeigen=args.zeigen)
    if args.save:
        ERGEBNISSE.mkdir(parents=True, exist_ok=True)
        ziel = ERGEBNISSE / f"{args.save}.json"
        ziel.write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
