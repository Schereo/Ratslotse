#!/usr/bin/env python3
"""Berechnet die "Hängt zusammen mit…"-Nachbarn je Thema (``council_entity_related``).

Reine Rechnung auf vorhandenen Daten — kein LLM-Aufruf, keine Kosten, Laufzeit
unter einer Minute. Wie ``embed_decisions.py`` braucht der Lauf numpy, das
bewusst nicht in ``requirements.txt`` steht (der Web-Service liest nur die fertige
Tabelle)::

    python scripts/build_entity_relations.py --report      # nur ansehen
    python scripts/build_entity_relations.py               # rechnen + speichern

``--report`` schreibt nichts und legt die berechneten Nachbarn zum Durchsehen vor.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import related  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def compute(store: CouncilStore, top_k: int, min_evidence: int,
            fit: float, no_text: bool) -> tuple[list[tuple], dict]:
    entities = store.entity_rows()
    links = store.entity_link_rows()
    decisions = store.decision_texts()
    vectors = related.load_vectors(store.get_embeddings())
    committees = store.committee_names()
    if not vectors:
        print("! Keine Embeddings — Textabgleich und Auffüllung entfallen.\n"
              "  Erst scripts/embed_decisions.py laufen lassen.", file=sys.stderr)
    return related.build(
        entities, links, decisions, vectors, committees,
        top_k=top_k, min_evidence=min_evidence, fit_threshold=fit,
        use_text_match=not no_text,
    )


def report(store: CouncilStore, rows: list[tuple], stats: dict, sample: int) -> None:
    by_slug: dict[str, list[tuple]] = {}
    for slug, neighbor, rel_type, rank, score, evidence in rows:
        by_slug.setdefault(slug, []).append((rank, neighbor, rel_type, score, evidence))
    ents = {e["slug"]: e for e in store.entity_rows()}

    print("\n" + "=" * 78)
    print("BERECHNETE NACHBARN — Durchsicht vor dem Speichern")
    print("=" * 78)
    ranked = sorted((e for e in ents.values() if e["slug"] in by_slug),
                    key=lambda e: -e["n"])[:sample]
    for e in ranked:
        print(f"\n▸ {e['name']}  ({e['kind']}, {e['n']} Beschlüsse)")
        for rank, neighbor, rel_type, score, evidence in sorted(by_slug[e["slug"]]):
            nb = ents.get(neighbor, {}).get("name", neighbor)
            tag = f"belegt  {evidence:>2} gemeinsame" if rel_type == "belegt" else "ähnlich  —         "
            print(f"    {tag}  {score:.2f}  {nb}")

    print("\n" + "-" * 78)
    print(f"Entitäten (inhaltlich)      {stats['entities']:>6}"
          f"   ausgefiltert als Gremium: {stats['structural']}")
    print(f"Links laut LLM              {stats['llm_links']:>6}")
    print(f"  + Textabgleich            {stats['text_added']:>6}"
          f"   verworfen (Passung): {stats['text_rejected']}")
    print(f"Paare roh                   {stats['pairs_raw']:>6}")
    print(f"  davon belegt (Evidenz)    {stats['pairs_proven']:>6}"
          f"   als Alias unterdrückt: {stats['alias_suppressed']}")
    print(f"Themen mit belegtem Nachbarn{stats['with_proven']:>6}"
          f"   ({stats['coverage_proven']:.0%} Abdeckung)")
    print(f"Zeilen gesamt               {stats['rows']:>6}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--top-k", type=int, default=related.TOP_K)
    ap.add_argument("--min-evidence", type=int, default=related.MIN_EVIDENCE)
    ap.add_argument("--fit", type=float, default=related.FIT_THRESHOLD)
    ap.add_argument("--no-text-match", action="store_true",
                    help="nur LLM-Links verwenden (Vergleichslauf)")
    ap.add_argument("--report", action="store_true", help="nur anzeigen, nichts speichern")
    ap.add_argument("--sample", type=int, default=25, help="Themen in der Durchsicht")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        rows, stats = compute(store, args.top_k, args.min_evidence, args.fit, args.no_text_match)
        if args.report:
            report(store, rows, stats, args.sample)
            print("\n(--report: nichts gespeichert)")
            return 0
        saved = store.save_entity_relations(rows)
        print(f"=== gespeichert: {saved} Nachbarschaften für {stats['entities']} Themen "
              f"({stats['coverage_proven']:.0%} mit belegtem Nachbarn) ===")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
