#!/usr/bin/env python3
"""Das Wähler*innen-Potenzial für die Stichwahl — je Wahlbezirk, aus dem
ersten Wahlgang, gegen die Erfahrung von 2021.

Bericht, keine Ausführung: Das Skript liest die eingefrorenen Stände aus dem
Repo (``kommunalwahl/referenz-2026/`` und ``tests/fixtures/wahlabend/
stichwahl-2021/``), schreibt nichts und ruft nichts ab. Es ist der Rechenkern
hinter ``docs/plan-stichwahl-potenzial.md`` — die Zahlen dort kommen von hier,
und wer eine Annahme ändern will, ändert sie am Schalter, nicht im Kopf.

    python scripts/stichwahl_potenzial.py                     # der Bericht
    python scripts/stichwahl_potenzial.py --boldt 70 15       # Linke wandert 70 % zu Rohr, 15 % zu Prange
    python scripts/stichwahl_potenzial.py --json out.json     # je Bezirk als JSON (für die Seite)

**Was das Modell annimmt und was nicht.** Je ausgeschiedener Kandidatur zwei
Zahlen: welcher Anteil ihrer Erstrunden-Stimmen zu Rohr, welcher zu Prange
geht; der Rest bleibt zu Hause. Das sind ANNAHMEN — Vorgaben unten, auf der
Seite als Regler. Eine Bezirksstatistik kann nicht sehen, wer wen gewählt
hat; sie kann nur sagen, WO die Stimmen liegen, um die es geht.

**Warum 2021 nur bedingt hilft.** Die Stichwahl am 26.09.2021 fiel auf den
Tag der Bundestagswahl: 12 % MEHR Wählende als im ersten Wahlgang, beide
Kandidaturen wuchsen um die Hälfte. Eine Stimmen-Wanderung lässt sich daraus
nicht schätzen (die Regression liefert Übertragungsquoten über 1 — Unsinn).
Was 2021 trotzdem zeigt: Fuhrhop wuchs in ihren SCHWÄCHSTEN Bezirken am
stärksten (× 2,2 gegen × 1,55 in den Hochburgen), und die Briefwahl war ihre
bessere Hälfte (50 % gegen 44 % an der Urne).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import mayor_districts, service  # noqa: E402

REFERENZ = WURZEL / "kommunalwahl" / "referenz-2026" / "praesentation-ob-wahlbezirke.json"
GEO = WURZEL / "web" / "frontend" / "public" / "geo" / "wahlbezirke-oldenburg.json"
FIX21 = WURZEL / "tests" / "fixtures" / "wahlabend" / "stichwahl-2021"

#: Die beiden in der Stichwahl.
DUELL = ("rohr", "prange")
#: Die Ausgeschiedenen, wie sie in der Bezirksdatei heißen (Castur und Stille
#: stecken dort in „Sonstige" — die Datei führt sie nicht einzeln).
AUSGESCHIEDEN = ("boldt", "froehlich", "butzin", "kuessner", "wilkens")
#: Vorgabe je Kandidatur: (Anteil zu Rohr, Anteil zu Prange) in Prozent.
#: Boldt (Linke) und Küßner: Tims Einschätzung „inhaltlich am nächsten";
#: Butzin hat Rohr öffentlich unterstützt; FDP und BB-OL eher bürgerlich.
VORGABE: dict[str, tuple[float, float]] = {
    "boldt": (55, 15), "kuessner": (45, 15), "butzin": (40, 20),
    "froehlich": (20, 35), "wilkens": (15, 30),
}
#: CDU-Zweitstimmen der Ratswahl: Die CDU hat keine OB-Kandidatur und
#: unterstützt Rohr. Wie viele ihrer Wählenden folgen, ist die unsicherste
#: Größe überhaupt — Vorgabe: netto 0 (gleich viele zu beiden).
VORGABE_CDU = (25, 25)


def lade_2026() -> dict[int, mayor_districts.MayorDistrict]:
    known = {s: "" for s in DUELL + AUSGESCHIEDEN}
    return {d.number: d for d in mayor_districts.parse_overview(json.loads(REFERENZ.read_text(encoding="utf-8")), known)}


def lade_2021() -> tuple[dict, dict]:
    e1 = {d.number: d for d in mayor_districts.parse_overview(
        json.loads((FIX21 / "uebersicht-223-erster-wahlgang.json").read_text(encoding="utf-8")),
        {"krogmann": "", "gathmann": "", "fuhrhop": "", "hoepken": ""})}
    e2 = {d.number: d for d in mayor_districts.parse_overview(
        json.loads((FIX21 / "uebersicht-224-stichwahl.json").read_text(encoding="utf-8")),
        {"krogmann": "", "fuhrhop": ""})}
    return e1, e2


def cdu_je_bezirk() -> dict[int, int]:
    reg = service.load_register()
    liste = service.districts(reg, service.probe_snapshot(reg, service.load_reference(), None), "probe")
    out = {}
    for d in liste["districts"]:
        p = next((x for x in d["parties"] if x["slug"] == "cdu"), None)
        out[d["number"]] = (p["votes"] if p else 0) or 0
    return out


def v(d: mayor_districts.MayorDistrict, slug: str) -> int:
    return d.votes.get(slug) or 0


def tsd(n: float, vorzeichen: bool = False) -> str:
    """1234567 → „1.234.567" — deutsche Tausenderpunkte, ohne den Text daneben anzufassen."""
    text = f"{abs(n):,.0f}".replace(",", ".")
    if vorzeichen:
        return ("+" if n >= 0 else "−") + text
    return ("−" if n < 0 else "") + text


def potenzial(annahmen: dict[str, tuple[float, float]], cdu: tuple[float, float]) -> list[dict]:
    """Je Bezirk: Basis, umworbene Stimmen, Netto-Erwartung, Nichtwählende, Ort."""
    D = lade_2026()
    geo = {f["properties"]["nr"]: f["properties"] for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]}
    cdu_stimmen = cdu_je_bezirk()
    zeilen = []
    for n, d in sorted(D.items()):
        if not d.counted:
            continue
        rohr, prange = v(d, "rohr"), v(d, "prange")
        netto = sum(v(d, s) * (a - b) / 100 for s, (a, b) in annahmen.items())
        netto_cdu = cdu_stimmen.get(n, 0) * (cdu[0] - cdu[1]) / 100
        pool = sum(v(d, s) for s in annahmen)
        nicht = 0 if d.postal else max(0, (d.eligible or 0) - (d.voters or 0))
        zwei = rohr + prange
        zeilen.append({
            "number": n, "name": d.name, "area": d.area, "postal": d.postal,
            "district_name": geo.get(n, {}).get("name", "Briefwahl"),
            "eligible": d.eligible or 0, "voters": d.voters or 0, "non_voters": nicht,
            "rohr": rohr, "prange": prange, "rohr_pct_of_two": round(100 * rohr / zwei, 1) if zwei else None,
            "pool": pool, "cdu_council": cdu_stimmen.get(n, 0),
            **{s: v(d, s) for s in AUSGESCHIEDEN},
            "net_convince": round(netto, 1), "net_cdu": round(netto_cdu, 1),
            "net_total": round(netto + netto_cdu, 1),
            "yield_per_1000": round(1000 * (netto + netto_cdu) / d.eligible, 1) if d.eligible else None,
        })
    return zeilen


def bericht_2021() -> None:
    e1, e2 = lade_2021()
    nums = sorted(set(e1) & set(e2))
    w1 = sum(e1[n].voters or 0 for n in nums)
    w2 = sum(e2[n].voters or 0 for n in nums)
    f1 = sum(v(e1[n], "fuhrhop") for n in nums)
    f2 = sum(v(e2[n], "fuhrhop") for n in nums)
    k1 = sum(v(e1[n], "krogmann") for n in nums)
    k2 = sum(v(e2[n], "krogmann") for n in nums)
    print("== 2021: Krogmann gegen Fuhrhop ==")
    print(f"   Wählende R1 {tsd(w1)} → R2 {tsd(w2)} ({100 * w2 / w1:.0f} %; Stichwahl am Tag der Bundestagswahl)")
    print(f"   Fuhrhop {tsd(f1)} → {tsd(f2)} (× {f2 / f1:.2f})   Krogmann {tsd(k1)} → {tsd(k2)} (× {k2 / k1:.2f})")
    nach = sorted(nums, key=lambda n: v(e1[n], "fuhrhop") / max(1, e1[n].valid_votes or 1))
    k = len(nach) // 5
    print("   Fuhrhop R2/R1 nach Fünfteln ihrer Stärke (schwächste zuerst):", end=" ")
    for i in range(5):
        teil = nach[i * k:(i + 1) * k] if i < 4 else nach[4 * k:]
        print(f"× {sum(v(e2[n], 'fuhrhop') for n in teil) / max(1, sum(v(e1[n], 'fuhrhop') for n in teil)):.2f}", end="  ")
    print()

    def anteil(e, post):
        f = sum(v(d, "fuhrhop") for d in e.values() if d.postal == post)
        kk = sum(v(d, "krogmann") for d in e.values() if d.postal == post)
        return 100 * f / (f + kk)
    print(f"   Fuhrhop-Anteil der Zwei — Urne: R1 {anteil(e1, False):.1f} % → R2 {anteil(e2, False):.1f} %   Brief: R1 {anteil(e1, True):.1f} % → R2 {anteil(e2, True):.1f} %")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    for s in AUSGESCHIEDEN:
        ap.add_argument(f"--{s}", nargs=2, type=float, metavar=("ZU_ROHR", "ZU_PRANGE"), default=VORGABE[s],
                        help=f"Anteile in Prozent (Vorgabe {VORGABE[s][0]:.0f} {VORGABE[s][1]:.0f})")
    ap.add_argument("--cdu", nargs=2, type=float, metavar=("ZU_ROHR", "ZU_PRANGE"), default=VORGABE_CDU,
                    help="CDU-Zweitstimmen der Ratswahl (Vorgabe netto 0)")
    ap.add_argument("--json", type=Path, help="je Bezirk als JSON schreiben")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    annahmen = {s: tuple(getattr(args, s)) for s in AUSGESCHIEDEN}
    zeilen = potenzial(annahmen, tuple(args.cdu))

    rohr = sum(z["rohr"] for z in zeilen)
    prange = sum(z["prange"] for z in zeilen)
    print("== 2026: erster Wahlgang ==")
    print(f"   Rohr {tsd(rohr)}  Prange {tsd(prange)}  → Prange vorn um {tsd(prange - rohr)}")
    print(f"   umworben (Boldt, Fröhlich, Butzin, Küßner, Wilkens): {tsd(sum(z['pool'] for z in zeilen))}")
    print(f"   CDU-Zweitstimmen der Ratswahl: {tsd(sum(z['cdu_council'] for z in zeilen))}")
    print(f"   Nichtwählende an der Urne: {tsd(sum(z['non_voters'] for z in zeilen))}")
    brief = [z for z in zeilen if z["postal"]]
    urne = [z for z in zeilen if not z["postal"]]
    ant = lambda rows: 100 * sum(z["rohr"] for z in rows) / sum(z["rohr"] + z["prange"] for z in rows)
    print(f"   Rohr-Anteil der Zwei: Urne {ant(urne):.1f} %   Brief {ant(brief):.1f} %")
    print()
    print("== Annahmen (zu Rohr / zu Prange, in %) ==")
    for s, (a, b) in annahmen.items():
        print(f"   {s:10s} {a:4.0f} / {b:4.0f}")
    print(f"   cdu        {args.cdu[0]:4.0f} / {args.cdu[1]:4.0f}")
    netto = sum(z["net_total"] for z in zeilen)
    print(f"   → Netto für Rohr {tsd(netto, True)}  → Saldo {tsd(netto - (prange - rohr), True)} Stimmen")
    print()
    print("== Wo eine Tür am meisten bringt (Netto je 1.000 Wahlberechtigte, Urne) ==")
    for z in sorted(urne, key=lambda z: -(z["yield_per_1000"] or 0))[:args.top]:
        print(f"   {z['number']} {z['name'][:28]:28s} {z['district_name'][:16]:16s} WB {z['area']}  {z['yield_per_1000']:5.1f}   Rohr {z['rohr_pct_of_two']:4.1f} %  Nichtw. {z['non_voters']}")
    print()
    print("== Stadtbezirke gebündelt (Netto, Rohr-Anteil, Nichtwählende) ==")
    orte: dict[str, dict] = defaultdict(lambda: {"netto": 0.0, "rohr": 0, "prange": 0, "nicht": 0, "n": 0})
    for z in urne:
        o = orte[z["district_name"]]
        o["netto"] += z["net_total"]; o["rohr"] += z["rohr"]; o["prange"] += z["prange"]; o["nicht"] += z["non_voters"]; o["n"] += 1
    for name, o in sorted(orte.items(), key=lambda kv: -kv[1]["netto"])[:args.top]:
        print(f"   {name:20s} {o['n']:2d} Bez.  netto {o['netto']:+5.0f}  Rohr {100 * o['rohr'] / (o['rohr'] + o['prange']):4.1f} %  Nichtw. {tsd(o['nicht'])}")
    print()
    bericht_2021()
    if args.json:
        args.json.write_text(json.dumps(zeilen, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n{len(zeilen)} Bezirke → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
