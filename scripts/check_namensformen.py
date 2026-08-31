#!/usr/bin/env python3
"""Bericht: Welche Namensformen könnten zu **einer** Person gehören?

Manche Menschen stehen in den Anwesenheitslisten unter zwei Namensformen —
„Tim Harms" und „Tim Ebbeke Harms". Ohne Zuordnung zerfällt so eine Person in
zwei Profile mit je einem Teil ihrer Sitzungen. Zusammengeführt wird über die
gepflegte Liste in `council/namensformen.py`; **dieses Skript schreibt nichts**,
es liefert die Vorschläge dafür.

Absichtlich ein Bericht und kein Automatismus: Die Bedingung (gleicher
Nachname, gleicher Vorname oder ein Namensteil mehr, nie gemeinsam in einer
Sitzung) findet auch Paare wie „Jan-Eike Meyer" (Gast einer Betriebs-GmbH) und
„Jan-Martin Meyer" (Ratsmitglied) — zwei verschiedene Menschen. Eine falsch
zusammengeführte Gruppe wäre die Behauptung, zwei reale Personen seien eine,
und sähe hinterher wie ein ganz normales Profil aus. Deshalb entscheidet hier
ein Mensch.

Was zu prüfen ist, bevor ein Paar in `GRUPPEN` wandert (die Ausgabe zeigt es):

* dieselbe Fraktion bzw. dieselbe Rolle,
* Auftritte in denselben Gremien,
* keine gemeinsame Anwesenheitsliste (die Bedingung filtert schon),
* bei Ratsmitgliedern: ein durchgehendes Mandat im Ratsinformationssystem
  (`council_memberships`), das beide Zeiträume überspannt.

    .venv/bin/python scripts/check_namensformen.py
    .venv/bin/python scripts/check_namensformen.py --alle   # auch Geführtes
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import namensformen
from council.store import CouncilStore

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _bestand(store: CouncilStore) -> dict[str, dict]:
    """Je Namensform (ungefaltet!): Sitzungen, Zeitraum, Rollen, Fraktionen."""
    aus: dict[str, dict] = defaultdict(
        lambda: {"ksinr": set(), "erste": None, "letzte": None,
                 "roles": Counter(), "parteien": Counter(),
                 "committees": set(), "namen": Counter()})
    for r in store._conn.execute(
            """SELECT a.name, a.ksinr, a.role, a.party, cs.committee, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.name IS NOT NULL AND a.name != ''"""):
        sl = CouncilStore._person_slug(r["name"])
        if not sl:
            continue
        e = aus[sl]
        e["ksinr"].add(r["ksinr"])
        e["roles"][r["role"]] += 1
        e["namen"][r["name"]] += 1
        e["committees"].add(r["committee"])
        if r["party"]:
            e["parteien"][r["party"]] += 1
        d = r["session_date"]
        e["erste"] = d if e["erste"] is None else min(e["erste"], d)
        e["letzte"] = d if e["letzte"] is None else max(e["letzte"], d)
    return aus


def _zeile(slug: str, e: dict) -> str:
    party = ", ".join(p for p, _ in e["parteien"].most_common(2)) or "—"
    roles = ", ".join(f"{r}×{n}" for r, n in e["roles"].most_common())
    return (f"    {slug:34s} {len(e['ksinr']):4d} Sitzungen  "
            f"{e['erste']} … {e['letzte']}  [{roles}]  {party}")


def main(alle: bool = False, db: Path | None = None) -> dict:
    store = CouncilStore(str(db or COUNCIL_DB))
    try:
        balance = _bestand(store)
        paare = namensformen.verdachtsfaelle({s: e["ksinr"] for s, e in balance.items()})
        offen = [p for p in paare if not p["gefuehrt"]]
        print(f"{len(balance)} Namensformen, {len(namensformen.GRUPPEN)} geführte Gruppen, "
              f"{len(offen)} ungeprüfte Verdachtspaare\n")
        for p in (paare if alle else offen):
            a, b = balance[p["a"]], balance[p["b"]]
            mark = " (geführt)" if p["gefuehrt"] else ""
            print(f"  {p['a']}  ↔  {p['b']}{mark}")
            print(_zeile(p["a"], a))
            print(_zeile(p["b"], b))
            gemeinsam = sorted(a["committees"] & b["committees"])
            print(f"    gemeinsame Gremien: {', '.join(gemeinsam) if gemeinsam else '—'}")
            print()
        if offen:
            print("Geprüfte Paare gehören nach council/namensformen.py → GRUPPEN.")
        return {"formen": len(balance), "verdacht": len(offen)}
    finally:
        store.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alle", action="store_true",
                    help="auch die bereits geführten Gruppen zeigen")
    ap.add_argument("--db", type=Path, default=None)
    args = ap.parse_args()
    main(alle=args.alle, db=args.db)
