#!/usr/bin/env python3
"""Zuordnung Antrag ↔ Teilabstimmung ohne Modell (Plan Vorlagen § 7.3): bis zu
30 Anträge an Punkten mit Teilabstimmungen; jede getroffene Zuordnung wird zur
Handprüfung ausgegeben (Label gegen Titel), dazu die Trefferquote."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import document_types, motions  # noqa: E402
from council.parties import parties_in_text  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main(n: int = 30) -> None:
    s = CouncilStore(str(ROOT / "data" / "council.sqlite"))
    rows = s._conn.execute(  # noqa: SLF001
        "SELECT DISTINCT aa.document_id, aa.label, aa.ksinr, aa.item_number FROM council_agenda_attachments aa "
        "WHERE EXISTS (SELECT 1 FROM council_decisions d WHERE d.ksinr = aa.ksinr AND d.kind = 'subvote' "
        "AND d.parent_item = trim(replace(replace(aa.item_number, 'Ö', ''), 'DZT', ''))) "
        "ORDER BY aa.document_id DESC").fetchall()
    # Dazu Anträge an der VORLAGE (über alle Stationen, wie `item_documents`
    # sie auch dem Punkt zeigt) — lokal fanden sich an Punkt-Anlagen nur 9.
    rows += s._conn.execute(  # noqa: SLF001
        "SELECT DISTINCT at.document_id, at.label, a.ksinr, a.item_number FROM council_attachments at "
        "JOIN council_templates t ON t.kvonr = at.kvonr "
        "JOIN council_agenda_items a ON a.template_number = t.template_number "
        "WHERE EXISTS (SELECT 1 FROM council_decisions d WHERE d.ksinr = a.ksinr AND d.kind = 'subvote' "
        "AND d.parent_item = trim(replace(replace(a.item_number, 'Ö', ''), 'DZT', ''))) "
        "ORDER BY at.document_id DESC").fetchall()
    gesehen: set = set()
    faelle = []
    for r in rows:
        # Nur Änderungsanträge bekommen eine Teilabstimmung (store_unterlagen.item_amendments).
        art = (s.document_profiles([r["document_id"]]).get(r["document_id"]) or {}).get("doc_type") \
            or document_types.classify(r["label"])
        if art == "amendment" and (r["document_id"], r["ksinr"]) not in gesehen:
            gesehen.add((r["document_id"], r["ksinr"]))
            faelle.append(r)
    faelle = faelle[:n]
    getroffen = 0
    for r in faelle:
        nr = re.sub(r"^\D+", "", r["item_number"]).strip()
        subs = [dict(x) | {"factions": json.loads(x["factions"] or "[]")} for x in s._conn.execute(  # noqa: SLF001
            "SELECT id, title, factions FROM council_decisions WHERE ksinr = ? AND kind = 'subvote' AND parent_item = ?",
            (r["ksinr"], nr))]
        ex = (s.motion_extract(r["document_id"]) or {}).get("payload") or {}
        profil = s.document_profiles([r["document_id"]]).get(r["document_id"]) or {}
        motion = {"applicants": ex.get("applicants") or profil.get("applicants") or parties_in_text(r["label"]),
                  "label": r["label"],
                  "target": ex.get("target"), "meaning": (ex.get("meaning") or {}).get("text")}
        treffer = motions.match_subvote(motion, subs)
        titel = next((x["title"] for x in subs if x["id"] == treffer), None)
        getroffen += treffer is not None
        print(f"{r['document_id']} {r['ksinr']} {r['item_number']}: {r['label'][:70]}\n   → {titel[:110] if titel else '— keine Zuordnung'} ({len(subs)} Teilabstimmungen)")
    print(f"\n{getroffen} von {len(faelle)} zugeordnet")


if __name__ == "__main__":
    main()
