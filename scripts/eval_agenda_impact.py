#!/usr/bin/env python3
"""Wochen-Karte gegenprüfen: Wen hätte sie hervorgehoben — und wen jetzt?

Läuft über vergangene Wochen und stellt drei Auswahlen nebeneinander:

* **alt** — die Heuristik vor dem 15.08.2026 (Behandlungsart als Summand,
  Entitäts-Gewicht bis 2.0, kein Bindungs- und kein Gremien-Signal),
* **regeln** — dieselbe Heuristik mit den neuen Regeln,
* **tragweite** — die LLM-Bewertung (``council/impact.py``), dieselbe Rubrik
  wie bei den Beschlüssen.

Damit lässt sich die Frage beantworten, mit der das Ganze anfing: „Fühlt sich
der hervorgehobene Punkt wie der wichtigste der Woche an?" — und zwar an
Wochen, die schon vorbei sind::

    python scripts/eval_agenda_impact.py --wochen 8
    python scripts/eval_agenda_impact.py --wochen 12 --ohne-llm   # nur Regeln

Kostet je Woche einen LLM-Aufruf pro 20 Punkte; ``--ohne-llm`` kostet nichts.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.impact import BATCH_SIZE, rate_agenda_batch  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def alte_heuristik(p: dict, entitaeten: list[tuple[str, int]], store: CouncilStore) -> float:
    """Der Stand vor dem 15.08.2026 — zum Vergleich nachgebaut."""
    rang = 0.0
    art = (p.get("behandlung") or "").lower()
    if "entscheid" in art:
        rang += 3.0
    elif "vorberat" in art:
        rang += 2.0
    elif art:
        rang += 0.5
    if store._ANTRAG_RE.search(p["title"]):
        rang += 1.5
    gefaltet = f" {store._falte_namen(p['title'])} "
    gewicht = max((n for name, n in entitaeten if name and f" {name} " in gefaltet), default=0)
    if gewicht:
        rang += min(2.0, math.log10(gewicht))
    if p.get("vorgeschichte"):
        rang += 1.0
    if p.get("summary"):
        rang += 0.4
    if p.get("vorlage_nr"):
        rang += 0.2
    if store._PERSONALIE_RE.search(p["title"]):
        rang -= 2.0
    return round(rang, 2)


def punkte_der_woche(store: CouncilStore, von: str, bis: str) -> list[dict]:
    """Dieselbe Auswahl wie die Wochen-Karte, nur für ein beliebiges Fenster."""
    sitzungen = [dict(r) for r in store._conn.execute(
        "SELECT ksinr, committee, session_date FROM council_sessions "
        "WHERE session_date BETWEEN ? AND ? ORDER BY session_date", (von, bis))]
    if not sitzungen:
        return []
    ph = ",".join("?" * len(sitzungen))
    nach_sitzung = {s["ksinr"]: s for s in sitzungen}
    rohe = store._conn.execute(
        f"SELECT a.ksinr, a.item_number, a.title, a.vorlage_nr, a.kvonr, s.summary, "
        f"       substr(v.raw_text, 1, 1200) AS sachverhalt "
        f"FROM council_agenda_items a "
        f"LEFT JOIN agenda_item_summaries s ON s.ksinr = a.ksinr AND s.item_number = a.item_number "
        f"LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
        f"WHERE a.ksinr IN ({ph}) AND a.is_public = 1 ORDER BY a.id",
        [s["ksinr"] for s in sitzungen]).fetchall()

    punkte = []
    for r in rohe:
        titel = (r["title"] or "").strip()
        if not titel or store._FORMALIE_RE.search(titel):
            continue
        sitz = nach_sitzung[r["ksinr"]]
        punkte.append({
            "ksinr": r["ksinr"], "item_number": r["item_number"], "title": titel,
            "summary": (r["summary"] or "").strip() or None,
            "sachverhalt": r["sachverhalt"], "vorlage_nr": r["vorlage_nr"], "kvonr": r["kvonr"],
            "committee": sitz["committee"], "session_date": sitz["session_date"],
        })
    # Behandlungsart und Vorgeschichte wie im Original
    kvonrs = [p["kvonr"] for p in punkte if p["kvonr"]]
    stationen: dict[int, list] = {}
    if kvonrs:
        ph2 = ",".join("?" * len(kvonrs))
        for b in store._conn.execute(
                f"SELECT kvonr, datum, ergebnis FROM council_beratungen "
                f"WHERE kvonr IN ({ph2}) ORDER BY datum", kvonrs):
            stationen.setdefault(b["kvonr"], []).append(dict(b))
    for p in punkte:
        reihe = stationen.get(p["kvonr"] or 0, [])
        heutige = next((b for b in reihe if b["datum"] == p["session_date"]), None)
        p["behandlung"] = (heutige or {}).get("ergebnis")
        p["vorgeschichte"] = sum(1 for b in reihe if (b["datum"] or "9999") < p["session_date"])
        p["antragsteller"], p["titel_kurz"] = store._titel_zerlegen(p["title"])
        p["topic_name"] = None
        p["stationen"] = len(reihe)
        # Das Signal, das den Unterschied macht: Wie oft stand genau das schon
        # auf einer Tagesordnung? (Zuwendungen 101×, Haushaltssatzung 3×.)
        p["wiederkehr"] = store._wiederkehr().get(store._wiederkehr_schluessel(p["title"]), 1)
    # Beschlussvorschlag und Kostenteil aus der Vorlage nachladen
    kv = [p["kvonr"] for p in punkte if p["kvonr"]]
    if kv:
        ph3 = ",".join("?" * len(kv))
        vor = {r["kvonr"]: dict(r) for r in store._conn.execute(
            f"SELECT kvonr, beschlussvorschlag, finanz_check, amt FROM council_vorlagen "
            f"WHERE kvonr IN ({ph3})", kv)}
        for p in punkte:
            p.update({k: v for k, v in (vor.get(p["kvonr"]) or {}).items() if k != "kvonr"})
    return punkte


def kurz(p: dict, n: int = 54) -> str:
    return (p.get("titel_kurz") or p["title"])[:n]


def main() -> int:
    ap = argparse.ArgumentParser(description="Wochen-Auswahl gegen vergangene Wochen prüfen")
    ap.add_argument("--wochen", type=int, default=8)
    ap.add_argument("--abstand", type=int, default=14, help="Tage zwischen den Stichproben")
    ap.add_argument("--ohne-llm", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    entitaeten = [(store._falte_namen(r["name"]), r["n"]) for r in store._conn.execute(
        "SELECT name, n FROM council_entities WHERE n >= 5") if len(r["name"] or "") >= 4]

    unterschiede = 0
    geprueft = 0
    for i in range(args.wochen):
        ende = date.today() - timedelta(days=7 + i * args.abstand)
        start = ende - timedelta(days=7)
        punkte = punkte_der_woche(store, start.isoformat(), ende.isoformat())
        if not punkte:
            continue
        geprueft += 1
        store._punkte_bewerten(punkte)
        for p in punkte:
            p["alt"] = alte_heuristik(p, entitaeten, store)

        if not args.ohne_llm:
            for start_i in range(0, len(punkte), BATCH_SIZE):
                teil = punkte[start_i : start_i + BATCH_SIZE]
                for j, p in enumerate(teil):
                    p["id"] = start_i + j
                nach_id = {p["id"]: p for p in teil}
                for iid, score, warum in rate_agenda_batch(teil):
                    if iid in nach_id:
                        nach_id[iid]["tragweite"] = score
                        nach_id[iid]["grund"] = warum

        alt_top = max(punkte, key=lambda p: p["alt"])
        neu_top = max(punkte, key=lambda p: p["wichtig"])
        llm_top = max((p for p in punkte if "tragweite" in p),
                      key=lambda p: p["tragweite"], default=None)

        print(f"\n=== {start:%d.%m.} – {ende:%d.%m.%Y} · {len(punkte)} Punkte ===")
        print(f"  alt       {alt_top['alt']:>5}  {kurz(alt_top)}")
        print(f"  regeln    {neu_top['wichtig']:>5}  {kurz(neu_top)}")
        if llm_top:
            print(f"  tragweite {llm_top['tragweite']:>5}  {kurz(llm_top)}")
            if llm_top.get("grund"):
                print(f"            ↳ {llm_top['grund'][:88]}")
            if kurz(llm_top) != kurz(alt_top):
                unterschiede += 1

    print(f"\n{unterschiede} von {geprueft} Wochen bekommen einen anderen Spitzenpunkt als bisher.")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
