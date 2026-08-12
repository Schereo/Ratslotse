#!/usr/bin/env python3
"""Fragen und Antworten EINES Kontos ausgeben — zur Qualitätsprüfung.

Das Admin-Panel zeigt bewusst nur Nutzungs-Zahlen (wie oft jemand gefragt hat),
nicht die Inhalte: Gespeicherte Gespräche liegen „im Konto" der Nutzerin, und
eine Admin-Ansicht dafür wäre ein eigenes Versprechen mit eigenem
Datenschutz-Hinweis. Wer die Antwortqualität an echten Fragen prüfen will,
braucht sie trotzdem — dafür dieses Skript, das nur auf dem Server läuft:

    .venv/bin/python scripts/qa_verlauf.py kbrumann@yahoo.de

Ausgabe: gespeicherte Gespräche (nur wenn das Konto dem Speichern zugestimmt
hat), gründliche Recherchen und abgegebenes Feedback. Mit ``--kurz`` bleiben
die Antworttexte weg — dann ist es eine reine Übersicht.

Bewusst NICHT als Ops-Workflow in GitHub Actions: Die Ausgabe enthält
personenbezogene Inhalte, und die Action-Logs eines öffentlichen Repos wären
der falsche Ort dafür.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402
from nwz.store import Store  # noqa: E402


def _pfad(name: str) -> str:
    """DB-Pfad wie in den anderen Ops-Skripten: Env (NWZ_DB/COUNCIL_DB) vor
    dem Repo-Default unter data/."""
    import os

    return os.environ.get(f"{name.upper()}_DB") or str(
        Path(__file__).resolve().parents[1] / "data" / f"{name}.sqlite")


def main() -> dict:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("email", help="E-Mail-Adresse des Kontos")
    p.add_argument("--kurz", action="store_true", help="ohne Antworttexte")
    args = p.parse_args()

    nwz = Store(_pfad("nwz"))
    council = CouncilStore(_pfad("council"))
    try:
        konto = nwz.get_web_user_by_email(args.email)
        if not konto:
            print(f"Kein Konto zu {args.email!r}.")
            return {"Konten": 0}
        uid = konto["id"]
        print(f"Konto {uid} · {konto['email']} · Status {konto.get('status')} · "
              f"registriert {str(konto.get('created_at'))[:16]}")
        speichern = nwz.get_qa_speichern(uid)
        print(f"Gespräche speichern: {speichern!r} "
              f"({'ja' if speichern == 1 else 'nein — dann liegen hier keine Verläufe'})")

        gespraeche = nwz._conn.execute(
            "SELECT id, titel, created FROM qa_gespraeche WHERE user_id = ? ORDER BY id",
            (uid,)).fetchall()
        print(f"\n=== Gespräche: {len(gespraeche)} ===")
        n_turns = 0
        for g in gespraeche:
            print(f"\n--- Gespräch {g['id']} ({str(g['created'])[:16]}): {g['titel']}")
            turns = nwz._conn.execute(
                "SELECT frage, antwort, quellen, created FROM qa_gespraech_turns "
                "WHERE gespraech_id = ? ORDER BY id", (g["id"],)).fetchall()
            n_turns += len(turns)
            for t in turns:
                q = json.loads(t["quellen"] or "{}")
                quellen, zitiert = q.get("sources", []), q.get("cited", [])
                print(f"\n  [{str(t['created'])[:16]}] FRAGE: {t['frage']}")
                print(f"  ANTWORT: {len(t['antwort'] or '')} Zeichen, "
                      f"{len(zitiert)} Zitate, {len(quellen)} Quellen"
                      + "".join(f", {len(q[k])} {k}" for k in
                                ("debatten", "presse", "planungen", "anlagen") if q.get(k)))
                if not args.kurz:
                    for zeile in (t["antwort"] or "").splitlines():
                        if zeile.strip():
                            print(f"    {zeile}")
                for s in quellen[:12]:
                    print(f"    [{s.get('id')}] {str(s.get('session_date'))[:10]} "
                          f"{str(s.get('committee'))[:24]:24s} {str(s.get('title'))[:64]}")

        print("\n=== Gründliche Recherchen ===")
        for r in nwz._conn.execute(
                "SELECT frage, status, length(bericht) n, created FROM deep_research_jobs "
                "WHERE user_id = ? ORDER BY created", (uid,)):
            print(f"  {str(r['created'])[:16]} {r['status']:12s} "
                  f"{r['n'] or 0:5d} Zeichen · {r['frage']}")

        print("\n=== Feedback ===")
        for f in council._conn.execute(
                "SELECT created, bewertung, frage, grund FROM council_qa_feedback "
                "WHERE user_id = ? ORDER BY created", (uid,)):
            print(f"  {str(f['created'])[:16]} {f['bewertung']} · {f['frage'][:70]}"
                  + (f"\n      Grund: {f['grund']}" if f["grund"] else ""))
        return {"Gespräche": len(gespraeche), "Fragen": n_turns}
    finally:
        nwz.close()
        council.close()


if __name__ == "__main__":
    print(main())
