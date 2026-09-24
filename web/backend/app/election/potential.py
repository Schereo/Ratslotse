"""Das Wähler*innen-Potenzial für die Stichwahl — je Wahlbezirk, mit Reglern.

P1 aus ``docs/plan-stichwahl-potenzial.md``. Reine Funktionen über die
eingefrorenen Bezirksstände; kein Netz, keine Datenbank. Der Bericht
``scripts/stichwahl_potenzial.py`` und der Endpunkt
``/api/wahlabend/stichwahl/potenzial`` rechnen beide hier.

**Was das Modell tut.** Für jede ausgeschiedene Kandidatur des ersten
Wahlgangs zwei Zahlen: welcher Anteil ihrer Stimmen in der Stichwahl zu Rohr
geht, welcher zu Prange; der Rest bleibt zu Hause. Dazu die CDU-Zweitstimmen
der Ratswahl als eigener Hebel (die CDU hat keine OB-Kandidatur und
unterstützt Rohr) — mit der Einschränkung, dass diese Menschen im ersten
Wahlgang schon jemanden gewählt haben, der Hebel also NICHT zu den
Stimmen addiert, sondern nur verschiebt. Und drei Beteiligungs-Regler:
wie viele der Rohr-Basis, der Prange-Basis und der Umworbenen wieder
wählen gehen.

**Was es nicht tut.** Es sieht nicht, wer wen gewählt hat. Eine
Bezirksstatistik zeigt, WO Stimmen liegen; die Regler sind Annahmen, und
jede Antwort trägt ``caveats``, die das sagen. Gemessen ist nur die
Ausgangslage — und die Lehre von 2021 (``lessons_2021``), die wegen der
gleichzeitigen Bundestagswahl NICHT als Wanderungsschätzung taugt.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..antworten import (
    RunoffCandidateStrength,
    RunoffLessons2014,
    RunoffLessons2021,
    RunoffPotential,
    RunoffPotentialAssumption,
    RunoffPotentialBundle,
    RunoffPotentialDistrict,
    RunoffStrengthGroup,
)
from . import mayor_districts

#: Repo-Wurzel: web/backend/app/election/ -> vier Ebenen hoch.
ROOT = Path(__file__).resolve().parents[4]
REFERENZ = ROOT / "kommunalwahl" / "referenz-2026" / "praesentation-ob-wahlbezirke.json"
#: Die Ratswahl vom selben Tag — CDU-Stimmen und Wahlscheine je Bezirk.
RATSWAHL26 = ROOT / "kommunalwahl" / "referenz-2026"
GEO = ROOT / "web" / "frontend" / "public" / "geo" / "wahlbezirke-oldenburg.json"
FIX21 = ROOT / "tests" / "fixtures" / "wahlabend" / "stichwahl-2021"
#: 2014 als Open-Data-CSV des Votemanagers (Hauptwahl 28.09., Stichwahl 12.10.).
FIX14 = ROOT / "tests" / "fixtures" / "wahlabend" / "stichwahl-2014"

DUELL = ("rohr", "prange")
#: Die Ausgeschiedenen, wie die Bezirksdatei sie führt (Castur und Stille
#: stecken dort in „Sonstige").
AUSGESCHIEDEN: dict[str, str] = {
    "boldt": "Heike Boldt (Linke)", "butzin": "Ralf Butzin", "froehlich": "Sebastian Fröhlich (FDP)",
    "kuessner": "Byanca Küßner", "wilkens": "Holger Martin Wilkens (BB-OL)",
    #: Castur und Stille: die Bezirksdatei führt sie nur als „Sonstige" —
    #: gültige Stimmen minus alle benannten Kandidaturen.
    "others": "Sonstige (Castur, Stille)",
}
#: Vorgaben je Kandidatur: (zu Rohr, zu Prange) in Prozent — Annahmen,
#: keine gemessenen Wechsel.
VORGABE: dict[str, tuple[float, float]] = {
    "boldt": (55, 15), "kuessner": (45, 15), "butzin": (40, 20),
    "froehlich": (20, 35), "wilkens": (15, 30), "others": (30, 30),
}
VORGABE_CDU: tuple[float, float] = (25, 25)
# Zusätzlicher Rückgang je Ausgangsgruppe; die Wechselannahmen lassen bereits
# einen Teil der Stimmen für ausgeschiedene Kandidaturen unzugeordnet.
TURNOUT_VORGABE = 95.0
#: Unter diesem Ertrag je 1.000 Wahlberechtigte heißt ein Bezirk „liegenlassen".
ERTRAG_GERING = 20.0
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}


@dataclass(frozen=True)
class Regler:
    """Alle Annahmen einer Rechnung — was der Endpunkt als Query nimmt."""
    #: Slug → (zu Rohr, zu Prange) in Prozent.
    transfers: dict[str, tuple[float, float]]
    cdu: tuple[float, float] = VORGABE_CDU
    #: Beteiligung in Prozent der Erstrunden-Wählenden je Lager.
    turnout_rohr: float = TURNOUT_VORGABE
    turnout_prange: float = TURNOUT_VORGABE
    turnout_pool: float = TURNOUT_VORGABE

    @classmethod
    def vorgabe(cls) -> Regler:
        return cls(transfers=dict(VORGABE))


def _lade_2026() -> dict[int, mayor_districts.MayorDistrict]:
    known = {s: "" for s in DUELL + tuple(AUSGESCHIEDEN) if s != "others"}
    aus = {d.number: d for d in mayor_districts.parse_overview(json.loads(REFERENZ.read_text(encoding="utf-8")), known)}
    for d in aus.values():
        d.votes["others"] = max(0, (d.valid_votes or 0) - sum(v or 0 for v in d.votes.values()))
    return aus


@dataclass(frozen=True)
class Ratswahl:
    """Was die Ratswahl vom selben Tag je Bezirk beisteuert."""
    #: Bezirk → CDU-Stimmen (Listen- + Personenstimmen).
    cdu: dict[int, int]
    #: Bezirk → dort ausgestellte Wahlscheine (Spalte A2).
    ballot_papers: dict[int, int]
    ballot_papers_city: int
    #: Gültige Stimmen je Wählendem — bis zu drei je Person (2026: 2,93 amtlich, 2,91 vorläufig).
    votes_per_voter: float


def _ratswahl_2026() -> Ratswahl:
    """Aus der Open-Data-CSV der Ratswahl 2026 — nicht aus der Generalprobe,
    die trägt die Zahlen von 2021 (der Fehler bis 16.09.2026: 37.430 CDU-
    Stimmen von 2021 statt 34.608 von 2026)."""
    import csv

    from . import reference

    idx = next(i for i, slug in reference._load(RATSWAHL26).slug_by_index.items() if slug == "cdu")
    spalte = f"D{idx}_4"
    cdu: dict[int, int] = {}
    scheine: dict[int, int] = {}
    stadt_scheine = 0
    je_waehler = 3.0
    with (RATSWAHL26 / "ratswahl-2026-wahlbezirke.csv").open(encoding="utf-8", newline="") as f:
        for zeile in csv.DictReader(f, delimiter=";"):
            nr = int(zeile["gebiet-nr"])
            cdu[nr] = int(zeile[spalte] or 0)
            scheine[nr] = int(zeile["A2"] or 0)
    with (RATSWAHL26 / "ratswahl-2026-stadt.csv").open(encoding="utf-8", newline="") as f:
        stadt = next(csv.DictReader(f, delimiter=";"))
        stadt_scheine = int(stadt["A2"] or 0)
        if int(stadt["B"] or 0):
            je_waehler = int(stadt["D"] or 0) / int(stadt["B"])
    return Ratswahl(cdu=cdu, ballot_papers=scheine, ballot_papers_city=stadt_scheine, votes_per_voter=round(je_waehler, 2))


def _v(d: mayor_districts.MayorDistrict, slug: str) -> int:
    return d.votes.get(slug) or 0


def _strategie(row: RunoffPotentialDistrict, pool_median: float) -> str:
    if row["postal"]:
        return "postal"
    if (row["yield_per_1000"] or 0) < ERTRAG_GERING:
        return "skip"
    stark = (row["rohr_pct_of_two"] or 0) >= 50
    pool_gross = row["pool_pct"] >= pool_median
    if stark and pool_gross:
        return "both"
    if stark:
        return "hold"
    return "persuade"


def compute(regler: Regler | None = None) -> RunoffPotential:
    """Die ganze Rechnung zu einem Reglerstand."""
    r = regler or Regler.vorgabe()
    D = _lade_2026()
    geo = {f["properties"]["nr"]: f["properties"] for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]}
    rat = _ratswahl_2026()
    t_r, t_p, t_pool = r.turnout_rohr / 100, r.turnout_prange / 100, r.turnout_pool / 100
    # Nichtwählende je Urnenbezirk: Wer einen Wahlschein hatte, hat meist per
    # Brief gewählt — und die zählt ein 9xx-Bezirk, nicht der Wohnbezirk. Die
    # Wahlscheine des Bezirks werden deshalb abgezogen, gewichtet damit, wie
    # viele davon stadtweit auch genutzt wurden.
    brief_waehlende = sum(d.voters or 0 for d in D.values() if d.postal and d.counted)
    schein_quote = brief_waehlende / rat.ballot_papers_city if rat.ballot_papers_city else 0.0

    rows: list[RunoffPotentialDistrict] = []
    for n, d in sorted(D.items()):
        if not d.counted:
            continue
        rohr, prange = _v(d, "rohr"), _v(d, "prange")
        pool = sum(_v(d, s) for s in r.transfers)
        zu_r = sum(_v(d, s) * a / 100 for s, (a, _) in r.transfers.items()) * t_pool
        zu_p = sum(_v(d, s) * b / 100 for s, (_, b) in r.transfers.items()) * t_pool
        cdu_stimmen = rat.cdu.get(n, 0)
        cdu_personen = round(cdu_stimmen / rat.votes_per_voter) if rat.votes_per_voter else 0
        # Der CDU-Regler verschiebt nur den SALDO: Diese Menschen haben im
        # ersten Wahlgang schon jemanden gewählt. Gerechnet in Personen, nicht
        # in Ratswahl-Stimmen — jede Person hatte bis zu drei davon.
        cdu_netto = cdu_personen * (r.cdu[0] - r.cdu[1]) / 100
        rohr2 = rohr * t_r + zu_r + max(cdu_netto, 0)
        prange2 = prange * t_p + zu_p + max(-cdu_netto, 0)
        scheine = 0 if d.postal else rat.ballot_papers.get(n, 0)
        nicht = 0 if d.postal else max(0, (d.eligible or 0) - (d.voters or 0) - round(scheine * schein_quote))
        zwei = rohr + prange
        valid = d.valid_votes or (zwei + pool) or 1
        net_total = (rohr2 - prange2) - (rohr - prange)
        rows.append(RunoffPotentialDistrict(
            number=n, name=d.name, area=d.area, area_roman=ROMAN.get(d.area, str(d.area)), postal=d.postal,
            district_name=geo.get(n, {}).get("name", "Briefwahl"),
            eligible=d.eligible or 0, voters=d.voters or 0, ballot_papers=scheine, non_voters=nicht,
            rohr=rohr, prange=prange, rohr_pct_of_two=round(100 * rohr / zwei, 1) if zwei else None,
            pool=pool, pool_pct=round(100 * pool / valid, 1), cdu_council=cdu_stimmen, cdu_voters_est=cdu_personen,
            eliminated={s: _v(d, s) for s in r.transfers},
            projected_rohr=round(rohr2), projected_prange=round(prange2),
            net_convince=round(zu_r - zu_p, 1), net_cdu=round(cdu_netto, 1), net_total=round(net_total, 1),
            yield_per_1000=round(1000 * net_total / d.eligible, 1) if d.eligible else None,
            strategy="",
        ))
    pool_median = statistics.median([z["pool_pct"] for z in rows if not z["postal"]]) if rows else 0.0
    for z in rows:
        z["strategy"] = _strategie(z, pool_median)

    # Stadtbezirke gebündelt — die Einheit, in der ein Team sich die Stadt aufteilt.
    b: dict[str, dict] = defaultdict(lambda: {"n": [], "eligible": 0, "non_voters": 0, "rohr": 0, "prange": 0, "net": 0.0, "pool": 0})
    for z in rows:
        if z["postal"]:
            continue
        o = b[z["district_name"]]
        o["n"].append(z["number"]); o["eligible"] += z["eligible"]; o["non_voters"] += z["non_voters"]
        o["rohr"] += z["rohr"]; o["prange"] += z["prange"]; o["net"] += z["net_total"]; o["pool"] += z["pool"]
    bundles = [RunoffPotentialBundle(
        district_name=name, numbers=sorted(o["n"]), districts=len(o["n"]), eligible=o["eligible"],
        non_voters=o["non_voters"], rohr=o["rohr"], prange=o["prange"], pool=o["pool"],
        rohr_pct_of_two=round(100 * o["rohr"] / (o["rohr"] + o["prange"]), 1) if o["rohr"] + o["prange"] else None,
        net_total=round(o["net"], 1), yield_per_1000=round(1000 * o["net"] / o["eligible"], 1) if o["eligible"] else None,
    ) for name, o in b.items()]
    bundles.sort(key=lambda x: -x["net_total"])

    rohr_g = sum(z["rohr"] for z in rows)
    prange_g = sum(z["prange"] for z in rows)
    urne = [z for z in rows if not z["postal"]]
    brief = [z for z in rows if z["postal"]]

    def anteil(teil: list[RunoffPotentialDistrict]) -> float | None:
        s = sum(z["rohr"] + z["prange"] for z in teil)
        return round(100 * sum(z["rohr"] for z in teil) / s, 1) if s else None

    zaehler: dict[str, int] = defaultdict(int)
    for z in rows:
        zaehler[z["strategy"]] += 1
    return RunoffPotential(
        rohr=rohr_g, prange=prange_g, lead=prange_g - rohr_g,
        pool=sum(z["pool"] for z in rows),
        eligible=sum(z["eligible"] for z in rows), voters=sum(z["voters"] for z in rows),
        cdu_council=sum(z["cdu_council"] for z in rows), cdu_voters_est=sum(z["cdu_voters_est"] for z in rows),
        votes_per_voter=rat.votes_per_voter,
        non_voters=sum(z["non_voters"] for z in rows),
        rohr_pct_urn=anteil(urne), rohr_pct_postal=anteil(brief),
        assumptions=[RunoffPotentialAssumption(slug=s, name=AUSGESCHIEDEN.get(s, s), to_rohr=a, to_prange=bb,
                                               votes=sum(z["eliminated"].get(s, 0) for z in rows))
                     for s, (a, bb) in r.transfers.items()],
        cdu_to_rohr=r.cdu[0], cdu_to_prange=r.cdu[1],
        turnout_rohr=r.turnout_rohr, turnout_prange=r.turnout_prange, turnout_pool=r.turnout_pool,
        projected_rohr=sum(z["projected_rohr"] for z in rows), projected_prange=sum(z["projected_prange"] for z in rows),
        net_total=round(sum(z["net_total"] for z in rows)),
        balance=round(sum(z["projected_rohr"] - z["projected_prange"] for z in rows)),
        strategy_counts=dict(zaehler), pool_pct_median=round(pool_median, 1),
        districts=rows, bundles=bundles, lessons_2021=lessons_2021(), lessons_2014=lessons_2014(),
        caveats=[
            "Die Regler beschreiben Annahmen. Die Bezirksergebnisse zeigen, wo Stimmen abgegeben wurden, aber nicht, wie einzelne Menschen bei der Stichwahl abstimmen werden.",
            "Die CDU erhielt bei der Ratswahl Stimmen, keine bestimmte Zahl von Personen: Jede Person konnte bis zu drei Stimmen abgeben. Das Modell schätzt eine Personenzahl anhand der durchschnittlichen Stimmen je Wählendem. Der CDU-Regler verändert nur den Saldo, denn diese Menschen haben bereits im ersten Wahlgang gewählt.",
            "Die Zahl der Nichtwählenden je Urnenbezirk ist geschätzt. Dafür werden von den Wahlberechtigten die Urnenwählenden und ein geschätzter Anteil der ausgestellten Wahlscheine abgezogen. Stadtweit stimmt die Summe; die Briefwahlbezirke weisen selbst keine Wahlberechtigten aus.",
            "Die Stichwahl 2021 fand am Tag der Bundestagswahl statt. Aus ihren Ergebnissen lässt sich nicht ablesen, wie einzelne Menschen ihre Stimme zwischen den Wahlgängen verändert haben.",
            "2014 waren die Ausgangsbedingungen anders: SPD gegen CDU, die Grünen nicht mehr in der Stichwahl und keine weitere Wahl am selben Tag. Die Zahlen vergleichen Gesamtergebnisse, kein individuelles Wahlverhalten.",
        ],
    )


def lessons_2021() -> RunoffLessons2021:
    """Krogmann gegen Fuhrhop, beide Wahlgänge, je Bezirk — als Zahlen."""
    e1 = {d.number: d for d in mayor_districts.parse_overview(
        json.loads((FIX21 / "uebersicht-223-erster-wahlgang.json").read_text(encoding="utf-8")),
        {"krogmann": "", "fuhrhop": ""})}
    e2 = {d.number: d for d in mayor_districts.parse_overview(
        json.loads((FIX21 / "uebersicht-224-stichwahl.json").read_text(encoding="utf-8")),
        {"krogmann": "", "fuhrhop": ""})}
    nums = sorted(set(e1) & set(e2))
    # Fünftel nur über die Urnenbezirke — dieselbe Gruppenbildung wie 2014.
    nach = sorted((n for n in nums if not e1[n].postal), key=lambda n: _v(e1[n], "fuhrhop") / max(1, e1[n].valid_votes or 1))
    k = len(nach) // 5
    fuenftel = []
    for i in range(5):
        teil = nach[i * k:(i + 1) * k] if i < 4 else nach[4 * k:]
        fuenftel.append(round(sum(_v(e2[n], "fuhrhop") for n in teil) / max(1, sum(_v(e1[n], "fuhrhop") for n in teil)), 2))

    def anteil(e: dict, post: bool) -> float:
        f = sum(_v(d, "fuhrhop") for d in e.values() if d.postal == post)
        kk = sum(_v(d, "krogmann") for d in e.values() if d.postal == post)
        return round(100 * f / (f + kk), 1)
    return RunoffLessons2021(
        voters_first=sum(e1[n].voters or 0 for n in nums), voters_runoff=sum(e2[n].voters or 0 for n in nums),
        fuhrhop_first=sum(_v(e1[n], "fuhrhop") for n in nums), fuhrhop_runoff=sum(_v(e2[n], "fuhrhop") for n in nums),
        krogmann_first=sum(_v(e1[n], "krogmann") for n in nums), krogmann_runoff=sum(_v(e2[n], "krogmann") for n in nums),
        fuhrhop_growth_by_fifth=fuenftel,
        fuhrhop_pct_urn_first=anteil(e1, False), fuhrhop_pct_urn_runoff=anteil(e2, False),
        fuhrhop_pct_postal_first=anteil(e1, True), fuhrhop_pct_postal_runoff=anteil(e2, True),
        note="Die Stichwahl am 26. September 2021 fand am Tag der Bundestagswahl statt. Die Zahl der Wählenden lag rund 12 Prozent über der des ersten Wahlgangs.",
    )


def _lade_2014(datei: str, spalten: dict[str, str]) -> dict[int, dict[str, int]]:
    """Eine Open-Data-CSV des Votemanagers (2014): je Bezirk Wahlberechtigte
    (A), Wählende (B), gültige Stimmen (D) und die Kandidaturen (D1…). Die
    Briefwahlbezirke (9xx) führen unter B nur die Wahlscheine — für sie
    zählen die gültigen Stimmen."""
    import csv

    aus: dict[int, dict[str, int]] = {}
    with (FIX14 / datei).open(encoding="utf-8", newline="") as f:
        for zeile in csv.DictReader(f, delimiter=";"):
            nr = int(zeile["gebiet-nr"])
            if nr == 0:
                continue
            werte = {"eligible": int(zeile["A"] or 0), "voters": int(zeile["B"] or 0), "valid": int(zeile["D"] or 0)}
            for slug, spalte in spalten.items():
                werte[slug] = int(zeile[spalte] or 0)
            aus[nr] = werte
    return aus


def lessons_2014() -> RunoffLessons2014:
    """Krogmann gegen Baak, beide Wahlgänge je Bezirk — die Stichwahl ohne
    Bundestagswahl daneben. Reihenfolge der Spalten laut Gesamtergebnis:
    D1 Krogmann, D2 Rieken (Grüne), D3 Baak, D4 Kreuzwieser (WFO)."""
    e1 = _lade_2014("hauptwahl-wahlbezirke.csv", {"krogmann": "D1", "rieken": "D2", "baak": "D3", "kreuzwieser": "D4"})
    e2 = _lade_2014("stichwahl-wahlbezirke.csv", {"krogmann": "D1", "baak": "D2"})
    nums = sorted(set(e1) & set(e2))
    urne = [n for n in nums if n < 900]
    nach = sorted(urne, key=lambda n: e1[n]["krogmann"] / max(1, e1[n]["valid"]))
    k = len(nach) // 5
    wieder, kg, bg = [], [], []
    for i in range(5):
        teil = nach[i * k:(i + 1) * k] if i < 4 else nach[4 * k:]
        wieder.append(round(100 * sum(e2[n]["voters"] for n in teil) / max(1, sum(e1[n]["voters"] for n in teil)), 1))
        kg.append(round(sum(e2[n]["krogmann"] for n in teil) / max(1, sum(e1[n]["krogmann"] for n in teil)), 2))
        bg.append(round(sum(e2[n]["baak"] for n in teil) / max(1, sum(e1[n]["baak"] for n in teil)), 2))

    def nach_staerke(slug: str) -> RunoffCandidateStrength:
        # Beide Kandidaten bekommen eine eigene Sortierung. Gleich viele
        # Bezirke pro Randgruppe machen absolute Zugewinne vergleichbar.
        sortiert = sorted(urne, key=lambda n: (e1[n][slug] / max(1, e1[n]["valid"]), n))
        anzahl = round(len(sortiert) / 5)

        def gruppe(bezirke: list[int]) -> RunoffStrengthGroup:
            erste = sum(e1[n][slug] for n in bezirke)
            zweite = sum(e2[n][slug] for n in bezirke)
            return RunoffStrengthGroup(
                districts=len(bezirke), first=erste, runoff=zweite,
                change=zweite - erste, change_pct=round(100 * (zweite - erste) / max(1, erste), 1),
            )

        return RunoffCandidateStrength(weak=gruppe(sortiert[:anzahl]), strong=gruppe(sortiert[-anzahl:]))

    def anteil(e: dict[int, dict[str, int]], post: bool) -> float:
        kk = sum(v["krogmann"] for n, v in e.items() if (n >= 900) == post)
        b = sum(v["baak"] for n, v in e.items() if (n >= 900) == post)
        return round(100 * kk / max(1, kk + b), 1)

    v1 = sum(e1[n]["voters"] for n in nums)
    v2 = sum(e2[n]["voters"] for n in nums)
    return RunoffLessons2014(
        voters_first=v1, voters_runoff=v2, return_rate_pct=round(100 * v2 / max(1, v1), 1),
        krogmann_first=sum(e1[n]["krogmann"] for n in nums), krogmann_runoff=sum(e2[n]["krogmann"] for n in nums),
        baak_first=sum(e1[n]["baak"] for n in nums), baak_runoff=sum(e2[n]["baak"] for n in nums),
        eliminated_first=sum(e1[n]["rieken"] + e1[n]["kreuzwieser"] for n in nums),
        return_by_fifth=wieder, krogmann_growth_by_fifth=kg, baak_growth_by_fifth=bg,
        krogmann_strength=nach_staerke("krogmann"), baak_strength=nach_staerke("baak"),
        krogmann_pct_urn_first=anteil(e1, False), krogmann_pct_urn_runoff=anteil(e2, False),
        krogmann_pct_postal_first=anteil(e1, True), krogmann_pct_postal_runoff=anteil(e2, True),
        note="Die Stichwahl am 12. Oktober 2014 fand zwei Wochen nach dem ersten Wahlgang statt. Anders als 2021 "
             "gab es am selben Tag keine weitere Wahl. Verglichen werden Gesamtzahlen; das Verhalten einzelner "
             "Menschen lässt sich daraus nicht ablesen.",
    )
