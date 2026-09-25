#!/usr/bin/env python3
"""Baut ``eval/cases_fakten_mehrstufig_rat.json``: Lotti auf Rats-Seiten, mit
Fragen, deren Antwort NICHT auf der Seite steht.

    python eval/build_fakten_mehrstufig_rat.py --stichtag 2026-09-24

**Wozu (24.09.2026).** Die mehrstufigen Haushaltsfälle messen, ob Lotti
nachschlägt. Auf den Rats-Seiten (Beschluss, Sitzung, Themenfeld) fehlte so
ein Satz: Dort kennt Lotti den Beschluss, die Sitzung oder das Themenfeld,
aber nicht die Beratung in den Ausschüssen davor, die Sitzung davor oder
danach, die Zahl der Beschlüsse eines Jahres, den Wirtschaftsplan hinter
einem Beschluss. Die Fragen sagen „hier“ oder „diese“, damit Lotti sie selbst
beantwortet, statt sie an Frag den Rat weiterzureichen
(``assistant.archiv_sofort``).

Gold, Schlüssel und Vorbedingungen wie in ``build_fakten_rat.py`` (dessen
Helfer hier benutzt werden): natürliche Schlüssel statt Zeilen-IDs, und
:func:`erwarte` bricht ab, wenn die Daten den Fall nicht mehr tragen.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from eval.build_fakten_rat import (  # noqa: E402
    DB_STANDARD, BaukastenFehler, Quelle, erwarte, fall, g_datum, g_text, g_zahl, q_beschluss,
)

ZIEL = WURZEL / "eval" / "cases_fakten_mehrstufig_rat.json"
K = "rat/mehrstufig"


def _wert(q: Quelle, sql: str, *args) -> float:
    r = q.conn.execute(sql, args).fetchone()
    if r is None or r[0] is None:
        raise BaukastenFehler(f"kein Wert: {sql} {args}")
    return float(r[0])


def baue(q: Quelle) -> list[dict]:
    gst = q.beschluss("Rat", "2025-12-15", vorlage="25/0615")
    erwarte(gst["outcome"] == "rejected", "8468: abgelehnt")
    gst_fa = q.beschluss("Ausschuss für Finanzen und Beteiligungen", "2025-11-05",
                         vorlage="25/0615")
    erwarte(gst_fa["outcome"] == "postponed", "8076: im Finanzausschuss vertagt")
    stadion = q.beschluss("Rat", "2026-06-01", vorlage="26/0396")
    bbgo = q.beschluss("Rat", "2025-12-15", titel="Bäderbetriebsgesellschaft Oldenburg mbH (BBGO): Wirtschaftsplan 2026")
    bbo = q.beschluss("Rat", "2026-02-09", titel="Bäderbetrieb der Stadt Oldenburg (BBO): Wirtschaftsplan 2026")
    rat_2906 = q.sitzung("Rat", "2026-06-29")
    rat_0106 = q.sitzung("Rat", "2026-06-01")
    sport = q.sitzung("Sportausschuss", "2026-05-13")
    naechster_sport = q.naechste_sitzung("Sportausschuss")

    rate = "SELECT rate FROM council_tax_rates WHERE kind = 'Grundsteuer B' AND year = ?"
    grundsteuer = "SELECT amount FROM council_taxes WHERE kind = 'Grundsteuer A+B' AND year = ?"
    bp = "SELECT {} FROM council_business_plans WHERE enterprise = ? AND year = ?"
    verkehr_2025 = ("SELECT COUNT(*) FROM council_decisions d JOIN council_sessions s USING(ksinr) "
                    "WHERE d.policy_field = 'verkehr' AND s.session_date LIKE '2025%' "
                    "AND d.kind = 'decision'")
    rat_sitzungen = "council_sessions committee='Rat', 2026"
    zeitabh = (f"ZEITABHÄNGIG: Goldwert relativ zum Stichtag {q.stichtag} gezogen — vor einem "
               "Lauf nach diesem Termin den Baukasten neu laufen lassen.")

    faelle = [
        # --- Beratungsfolge: dieselbe Vorlage in anderen Gremien -------------
        fall("rat-mehr-grundsteuer-ausschuss", "lotti",
             "Wurde diese Vorlage vorher schon in einem Ausschuss beraten?",
             f"{K}/beratungsfolge",
             [g_text([["Finanzen", "Finanzausschuss"]], q_beschluss(gst_fa, "committee")),
              g_datum(gst_fa["session_date"], q_beschluss(gst_fa, "session_date")),
              g_text([["vertagt", "verschoben"]], q_beschluss(gst_fa, "outcome=postponed"))],
             route="/council/decision", refs={"decision_id": gst["id"]},
             notiz="Vorlage 25/0615: Finanzausschuss 05.11.2025 vertagt, Rat 01.12.2025 vertagt, "
                   "Finanzausschuss und Rat 15.12.2025 abgelehnt. Die Seite zeigt nur den "
                   "Ratsbeschluss."),
        # --- Beschluss → Haushalt ------------------------------------------
        fall("rat-mehr-grundsteuer-heute", "lotti",
             "Wie hoch ist der Hebesatz der Grundsteuer B heute, nachdem das hier abgelehnt wurde?",
             f"{K}/haushalt",
             [g_zahl(_wert(q, rate, 2025), "%", "Hebesatz Grundsteuer B seit 2025",
                     "council_tax_rates kind='Grundsteuer B' year=2025")],
             route="/council/decision", refs={"decision_id": gst["id"]}),
        fall("rat-mehr-grundsteuer-ertrag", "lotti",
             "Wie viel bringt diese Steuer der Stadt im Jahr ein?",
             f"{K}/haushalt",
             [g_zahl(_wert(q, grundsteuer, 2025), "€", "Grundsteuer A+B 2025",
                     "council_taxes kind='Grundsteuer A+B' year=2025", jahr=2025, toleranz=0.02)],
             route="/council/decision", refs={"decision_id": gst["id"]}),
        fall("rat-mehr-stadion-wirtschaftsplan", "lotti",
             "Wie viel Verlust plant die Stadiongesellschaft laut Wirtschaftsplan 2026?",
             f"{K}/haushalt",
             [g_zahl(abs(_wert(q, bp.format("result"), "stadion", 2026)), "€",
                     "Plan-Ergebnis Stadion 2026", "council_business_plans stadion 2026; result",
                     jahr=2026, toleranz=0.02)],
             route="/council/decision", refs={"decision_id": stadion["id"]}),
        fall("rat-mehr-bbgo-vorjahr", "lotti",
             "Wie viel Minus war im Wirtschaftsplan des Jahres davor geplant?",
             f"{K}/haushalt",
             [g_zahl(abs(_wert(q, bp.format("result"), "bbgo", 2025)), "€",
                     "Plan-Ergebnis BBGO 2025", "council_business_plans bbgo 2025; result",
                     jahr=2025, toleranz=0.02)],
             route="/council/decision", refs={"decision_id": bbgo["id"]}),
        fall("rat-mehr-bbo-2020", "lotti",
             "Wie viel mehr gibt der Bäderbetrieb hier aus als 2020?",
             f"{K}/haushalt",
             [g_zahl(_wert(q, bp.format("expenses"), "bbo", 2020), "€", "BBO Aufwendungen Plan 2020",
                     "council_business_plans bbo 2020; expenses", jahr=2020, toleranz=0.02),
              g_zahl(_wert(q, bp.format("expenses"), "bbo", 2026), "€", "BBO Aufwendungen Plan 2026",
                     "council_business_plans bbo 2026; expenses", jahr=2026, toleranz=0.02)],
             route="/council/decision", refs={"decision_id": bbo["id"]}),
        # --- Sitzungen davor und danach ---------------------------------------
        fall("rat-mehr-sitzung-davor", "lotti",
             "Wann war die Ratssitzung vor dieser hier?",
             f"{K}/sitzungen",
             [g_datum(rat_0106["session_date"], rat_sitzungen)],
             route="/council/sitzung", refs={"ksinr": rat_2906["ksinr"]}),
        fall("rat-mehr-sitzung-danach", "lotti",
             "Wann tagt der Rat nach dieser Sitzung wieder?",
             f"{K}/sitzungen",
             [g_datum("2026-08-31", rat_sitzungen)],
             route="/council/sitzung", refs={"ksinr": rat_2906["ksinr"]}),
        fall("rat-mehr-sitzung-davor-stadion", "lotti",
             "Was stand in der Ratssitzung vor dieser hier auf der Tagesordnung?",
             f"{K}/sitzungen",
             [g_datum("2026-04-13", rat_sitzungen)],
             route="/council/sitzung", refs={"ksinr": rat_0106["ksinr"]}),
        fall("rat-mehr-sport-naechste", "lotti",
             "Wann tagt dieser Ausschuss das nächste Mal?",
             f"{K}/sitzungen",
             [g_datum(naechster_sport["session_date"],
                      "council_sessions ∪ council_scheduled_sessions, erste Sportausschuss-Sitzung "
                      f"nach {q.stichtag}")],
             route="/council/sitzung", refs={"ksinr": sport["ksinr"]}, notiz=zeitabh),
        # --- Zählen -----------------------------------------------------------
        fall("rat-mehr-verkehr-2025", "lotti",
             "Wie viele Beschlüsse gab es in diesem Themenfeld 2025?",
             f"{K}/zaehlen",
             [g_zahl(_wert(q, verkehr_2025), "", "Verkehrsbeschlüsse 2025",
                     "COUNT council_decisions policy_field='verkehr', kind='decision', Sitzung 2025",
                     toleranz=0.05)],
             route="/council/thema", refs={"slug": "verkehr"},
             notiz="Zählt Beschlüsse jedes Ergebnisses; 5 % Spielraum für die Frage, ob "
                   "Kenntnisnahmen mitzählen."),
        # --- nicht in den Daten -----------------------------------------------
        fall("rat-mehr-nd-stadion-zuschauer", "lotti",
             "Wie viele Zuschauer kamen letzte Saison zu den Spielen, um die es hier geht?",
             f"{K}/nicht-in-daten", [],
             route="/council/decision", refs={"decision_id": stadion["id"]},
             antwort_in_daten=False,
             notiz="Zuschauerzahlen stehen in keinem Beschluss, keiner Vorlage und keiner "
                   "Haushaltstabelle."),
    ]
    ids = [f["id"] for f in faelle]
    erwarte(len(ids) == len(set(ids)), "doppelte Fall-IDs")
    return faelle


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--db", default=str(DB_STANDARD))
    ap.add_argument("--stichtag", default=date.today().isoformat())
    args = ap.parse_args(argv)
    faelle = baue(Quelle(Path(args.db), args.stichtag))
    ZIEL.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ {len(faelle)} Fälle → {ZIEL.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
