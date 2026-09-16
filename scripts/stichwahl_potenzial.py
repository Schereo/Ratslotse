#!/usr/bin/env python3
"""Das Wähler*innen-Potenzial für die Stichwahl — der Bericht auf der Konsole.

Bericht, keine Ausführung: liest die eingefrorenen Stände aus dem Repo,
schreibt nichts, ruft nichts ab. Die Rechnung selbst steht in
``web/backend/app/election/potential.py`` — dieselbe, die der Endpunkt
``/api/wahlabend/stichwahl/potenzial`` liefert. Der Plan dazu:
``docs/plan-stichwahl-potenzial.md``.

    python scripts/stichwahl_potenzial.py                     # der Bericht mit Vorgaben
    python scripts/stichwahl_potenzial.py --boldt 70 15       # Linke: 70 % zu Rohr, 15 % zu Prange
    python scripts/stichwahl_potenzial.py --turnout-rohr 90   # nur 90 % der Rohr-Basis kommen wieder
    python scripts/stichwahl_potenzial.py --json out.json     # die ganze Antwort als JSON
    python scripts/stichwahl_potenzial.py --link              # die Adresse der Seite (Token aus der .env)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import potential  # noqa: E402


def tsd(n: float, vorzeichen: bool = False) -> str:
    """1234567 → „1.234.567" — deutsche Tausenderpunkte."""
    text = f"{abs(n):,.0f}".replace(",", ".")
    if vorzeichen:
        return ("+" if n >= 0 else "−") + text
    return ("−" if n < 0 else "") + text


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    for s, (a, b) in potential.VORGABE.items():
        ap.add_argument(f"--{s}", nargs=2, type=float, metavar=("ZU_ROHR", "ZU_PRANGE"), default=(a, b),
                        help=f"Anteile in Prozent (Vorgabe {a:.0f} {b:.0f})")
    ap.add_argument("--cdu", nargs=2, type=float, metavar=("ZU_ROHR", "ZU_PRANGE"), default=potential.VORGABE_CDU,
                    help="CDU-Wählende der Ratswahl, geschätzt aus den Stimmen (Vorgabe netto 0)")
    ap.add_argument("--turnout-rohr", type=float, default=100, help="Beteiligung der Rohr-Basis in %% der Erstrunde")
    ap.add_argument("--turnout-prange", type=float, default=100)
    ap.add_argument("--turnout-pool", type=float, default=100, help="Beteiligung der Umworbenen")
    ap.add_argument("--json", type=Path, help="die ganze Antwort als JSON schreiben")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--link", action="store_true", help="nur die Adresse der Seite mit dem Token dieser Umgebung")
    args = ap.parse_args()

    if args.link:
        from app.config import get_settings
        from app.routers.wahlabend import wahlkampf_token

        token = wahlkampf_token()
        if token is None:
            print("Kein Token: WEB_JWT_SECRET steht auf dem Vorgabewert und WAHLKAMPF_TOKEN ist nicht gesetzt.")
            return 1
        print(f"{get_settings().app_base_url.rstrip('/')}/stichwahl/potenzial?k={token}")
        return 0

    regler = potential.Regler(
        transfers={s: tuple(getattr(args, s)) for s in potential.VORGABE},
        cdu=tuple(args.cdu), turnout_rohr=args.turnout_rohr, turnout_prange=args.turnout_prange,
        turnout_pool=args.turnout_pool,
    )
    p = potential.compute(regler)

    print("== 2026: erster Wahlgang ==")
    print(f"   Rohr {tsd(p['rohr'])}  Prange {tsd(p['prange'])}  → Prange vorn um {tsd(p['lead'])}")
    print(f"   umworben ({', '.join(a['name'].split(' (')[0].split()[-1] for a in p['assumptions'])}): {tsd(p['pool'])}")
    print(f"   CDU-Stimmen der Ratswahl: {tsd(p['cdu_council'])} (≈ {tsd(p['cdu_voters_est'])} Wählende)   "
          f"Nichtwählende: {tsd(p['non_voters'])} von {tsd(p['eligible'])} (je Bezirk geschätzt)")
    print(f"   Rohr-Anteil der Zwei: Urne {p['rohr_pct_urn']} %   Brief {p['rohr_pct_postal']} %")
    print()
    print("== Annahmen (zu Rohr / zu Prange, in %) ==")
    for a in p["assumptions"]:
        print(f"   {a['slug']:10s} {a['to_rohr']:4.0f} / {a['to_prange']:4.0f}   ({tsd(a['votes'])} Stimmen)")
    print(f"   cdu        {p['cdu_to_rohr']:4.0f} / {p['cdu_to_prange']:4.0f}")
    print(f"   Beteiligung: Rohr-Basis {p['turnout_rohr']:.0f} %, Prange-Basis {p['turnout_prange']:.0f} %, Umworbene {p['turnout_pool']:.0f} %")
    print(f"   → Vorsprung gewonnen {tsd(p['net_total'], True)}  → Saldo Rohr − Prange {tsd(p['balance'], True)} Stimmen")
    print(f"   Strategien: {p['strategy_counts']}")
    print()
    print("== Wo eine Tür am meisten bringt (netto je 1.000 Wahlberechtigte, Urne) ==")
    urne = [z for z in p["districts"] if not z["postal"]]
    for z in sorted(urne, key=lambda z: -(z["yield_per_1000"] or 0))[:args.top]:
        print(f"   {z['number']} {z['name'][:28]:28s} {z['district_name'][:16]:16s} WB {z['area_roman']:3s} {z['yield_per_1000']:5.1f}  {z['strategy']:12s} Rohr {z['rohr_pct_of_two']:4.1f} %  Nichtw. {z['non_voters']}")
    print()
    print("== Stadtbezirke gebündelt ==")
    for b in p["bundles"][:args.top]:
        print(f"   {b['district_name']:20s} {b['districts']:2d} Bez.  netto {b['net_total']:+6.0f}  je 1.000: {b['yield_per_1000']:5.1f}  Rohr {b['rohr_pct_of_two']:4.1f} %  Nichtw. {tsd(b['non_voters'])}")
    print()
    l = p["lessons_2021"]
    print("== 2021: Krogmann gegen Fuhrhop ==")
    print(f"   Wählende R1 {tsd(l['voters_first'])} → R2 {tsd(l['voters_runoff'])} ({100 * l['voters_runoff'] / l['voters_first']:.0f} %) — {l['note']}")
    print(f"   Fuhrhop {tsd(l['fuhrhop_first'])} → {tsd(l['fuhrhop_runoff'])}   Krogmann {tsd(l['krogmann_first'])} → {tsd(l['krogmann_runoff'])}")
    print(f"   Fuhrhop R2/R1 nach Fünfteln seiner Stärke (schwächste zuerst): {'  '.join(f'× {x:.2f}' for x in l['fuhrhop_growth_by_fifth'])}")
    print(f"   Fuhrhop-Anteil der Zwei — Urne {l['fuhrhop_pct_urn_first']} → {l['fuhrhop_pct_urn_runoff']} %   Brief {l['fuhrhop_pct_postal_first']} → {l['fuhrhop_pct_postal_runoff']} %")
    for c in p["caveats"]:
        print(f"   ! {c}")
    if args.json:
        args.json.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
