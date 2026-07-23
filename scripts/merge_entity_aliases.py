#!/usr/bin/env python3
"""Führt doppelte Themen zusammen (``council_entity_aliases``).

Die Entitäten-Extraktion benennt dieselbe Sache je Batch unterschiedlich, sodass
ein Gegenstand über mehrere Themen-Seiten verstreut liegt — der Bäderbetrieb unter
vier Namen, die Gebäudewirtschaft unter drei plus Abkürzung. Dieses Skript findet
die Kandidaten über Namensnormalisierung, lässt sie vom LLM einzeln prüfen und
schreibt die bestätigten Zusammenführungen::

    python scripts/merge_entity_aliases.py --report   # nur ansehen, nichts ändern
    python scripts/merge_entity_aliases.py --dry-run  # inkl. LLM-Prüfung, ohne Speichern
    python scripts/merge_entity_aliases.py            # prüfen, speichern, neu ableiten

Reversibel: Geschrieben wird nur die Alias-Tabelle. Die Roh-Beobachtungen bleiben
unangetastet — eine Zuordnung löschen (Admin-UI) und neu ableiten stellt den
vorherigen Stand her. Von Hand gesetzte Zuordnungen überschreibt der Lauf nie.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import aliases  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _centroids(store: CouncilStore, ent_decs: dict) -> dict:
    """Semantischer Schwerpunkt je Entität — nur zum Vorfiltern der Teilstring-Paare.
    Fehlt numpy oder fehlen Embeddings, läuft der Rest ohne diesen Filter weiter."""
    try:
        import numpy as np
    except ImportError:
        print("! numpy fehlt — Teilstring-Kandidaten werden übersprungen.", file=sys.stderr)
        return {}
    vectors = {r[0]: np.frombuffer(r[1], dtype="float32") for r in store.get_embeddings()}
    if not vectors:
        print("! Keine Embeddings — Teilstring-Kandidaten werden übersprungen.", file=sys.stderr)
        return {}
    out = {}
    for eid, decs in ent_decs.items():
        vs = [vectors[d] for d in decs if d in vectors]
        if not vs:
            continue
        v = np.mean(vs, axis=0)
        norm = float(np.linalg.norm(v))
        if norm > 0:
            out[eid] = v / norm
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--report", action="store_true",
                    help="nur die Kandidaten zeigen, kein LLM, nichts speichern")
    ap.add_argument("--dry-run", action="store_true",
                    help="mit LLM-Prüfung, aber ohne zu speichern")
    ap.add_argument("--limit", type=int, default=0, help="höchstens N Paare prüfen")
    ap.add_argument("--min-emb", type=float, default=aliases.MIN_EMB)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        entities = store.entity_rows()
        by_id = {e["id"]: e for e in entities}
        ent_decs: dict[int, set] = {}
        for eid, did in store.entity_link_rows():
            ent_decs.setdefault(eid, set()).add(did)

        cands = aliases.candidates(entities, ent_decs, _centroids(store, ent_decs), args.min_emb)
        if args.limit:
            cands = cands[:args.limit]

        by_art: dict[str, int] = {}
        for c in cands:
            by_art[c["art"]] = by_art.get(c["art"], 0) + 1
        print(f"Themen gesamt: {len(entities)}")
        print(f"Kandidatenpaare: {len(cands)}  " +
              " · ".join(f"{k} {v}" for k, v in sorted(by_art.items())))

        if args.report:
            print("\n--- Kandidaten (ungeprüft) ---")
            for c in cands:
                a, b = by_id[c["a"]], by_id[c["b"]]
                emb = f"{c['emb']:.2f}" if c["emb"] is not None else "  — "
                print(f"  [{c['art']:<14}] emb={emb} ov={c['overlap']:.2f}  "
                      f"{a['name'][:34]:<34} ({a['n']:>3}) | {b['name'][:34]} ({b['n']})")
            print("\n(--report: kein LLM aufgerufen, nichts gespeichert)")
            return 0

        titles = store.entity_titles()
        print(f"\nLLM-Prüfung von {len(cands)} Paaren…", flush=True)
        confirmed = aliases.decide(cands, entities, titles)
        print(f"bestätigt: {len(confirmed)} von {len(cands)}\n")

        known = store.known_entity_slugs()
        rows, seen = [], set()
        now = datetime.now().isoformat(timespec="seconds")
        for c in confirmed:
            alias_e, canon_e = by_id[c["alias"]], by_id[c["canonical"]]
            if alias_e["slug"] in seen or canon_e["slug"] not in known:
                continue
            seen.add(alias_e["slug"])
            rows.append((alias_e["slug"], canon_e["slug"], "llm", c["reason"], now))
            print(f"  {alias_e['name'][:36]:<36} → {canon_e['name'][:36]:<36} {c['reason'][:60]}")

        if args.dry_run:
            print(f"\n(--dry-run: {len(rows)} Zusammenführungen NICHT gespeichert)")
            return 0

        store.save_entity_aliases(rows, replace=True)
        n_ents, n_links = store.rebuild_entities_from_obs()
        print(f"\n=== {len(rows)} Zusammenführungen gespeichert; "
              f"Themen neu abgeleitet: {n_ents} ({n_links} Verknüpfungen) ===")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
