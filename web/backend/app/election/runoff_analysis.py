"""Stadtweite Wahlanalyse aus eingefrorenen Ergebnissen, ohne Prognose.

Wahlberechtigte stehen in den Urnenbezirken, Briefwählende in separaten
Zählbezirken. Nichtteilnahme ist deshalb nur für die ganze Stadt bestimmbar.
Die Ratswahl 2026 wird ausdrücklich aus 2026 geladen, nie aus der Referenz
der Generalprobe (2021). Historische Vergleiche benutzen Stadtgesamtwerte
beider Wahlgänge statt unterschiedlich gebildeter Bezirksgruppen.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..antworten import (
    RunoffAnalysis,
    RunoffAnalysisCandidate,
    RunoffAnalysisChange,
    RunoffAnalysisCouncil,
    RunoffAnalysisHistory,
    RunoffAnalysisMethod,
    RunoffAnalysisTotals,
)
from . import mayor_districts, votemanager

ROOT = Path(__file__).resolve().parents[4]
REFERENCE = ROOT / "kommunalwahl" / "referenz-2026"
FIXTURES = ROOT / "tests" / "fixtures" / "wahlabend"
SOURCE_2026 = "https://votemanager.kdo.de/20260913/03403000/praesentation/ergebnis.html?id=ebene_-6360_id_10357&stimmentyp=0&wahl_id=2552"
NAMES = {
    "prange": "Ulf Prange", "rohr": "Jascha Rohr", "boldt": "Heike Boldt",
    "butzin": "Ralf Butzin", "froehlich": "Sebastian Fröhlich",
    "kuessner": "Byanca Küßner", "wilkens": "Holger Martin Wilkens",
}
FINALISTS = {"prange", "rohr"}


def percent(value: int | float, base: int | float) -> float | None:
    """Ein leerer Nenner ist unbekannt, nicht 0 %. Erst die Anzeige rundet."""
    return 100 * value / base if base > 0 else None


def _read(path: Path, names: dict[str, str]) -> list[mayor_districts.MayorDistrict]:
    rows = list(mayor_districts.parse_overview(json.loads(path.read_text(encoding="utf-8")), names))
    if not rows or any(not row.counted for row in rows):
        raise ValueError(f"Unvollständiger Wahlstand: {path.name}")
    return rows


def _required(value: int | None) -> int:
    if value is None or value < 0:
        raise ValueError("Wahldaten fehlen oder sind negativ")
    return value


def totals(rows: list[mayor_districts.MayorDistrict]) -> RunoffAnalysisTotals:
    eligible = sum(_required(row.eligible) for row in rows)
    voters = sum(_required(row.voters) for row in rows)
    valid = sum(_required(row.valid_votes) for row in rows)
    if not 0 <= valid <= voters <= eligible:
        raise ValueError("Stadtsummen der Wahldaten widersprechen sich")
    return RunoffAnalysisTotals(
        eligible=eligible, voters=voters,
        urn_voters=sum(_required(row.voters) for row in rows if not row.postal),
        postal_voters=sum(_required(row.voters) for row in rows if row.postal),
        valid_votes=valid, invalid_ballots=voters - valid,
        non_voters=eligible - voters, turnout_pct=percent(voters, eligible),
    )


def _votes(rows: list[mayor_districts.MayorDistrict], slug: str) -> int:
    return sum(_required(row.votes.get(slug)) for row in rows)


def _candidates(rows: list[mayor_districts.MayorDistrict]) -> list[RunoffAnalysisCandidate]:
    valid = sum(_required(row.valid_votes) for row in rows)
    result = [RunoffAnalysisCandidate(
        slug=slug, name=name, votes=_votes(rows, slug),
        share_all_pct=percent(_votes(rows, slug), valid), in_runoff=slug in FINALISTS,
    ) for slug, name in NAMES.items()]
    other = valid - sum(row["votes"] for row in result)
    if other < 0:
        raise ValueError("Kandidatenstimmen übersteigen die gültigen Stimmen")
    result.append(RunoffAnalysisCandidate(
        slug="other", name="Michael Stille und Yakup Castur", votes=other,
        share_all_pct=percent(other, valid), in_runoff=False,
    ))
    return sorted(result, key=lambda row: -row["votes"])


def council() -> RunoffAnalysisCouncil:
    """Die explizite Jahreszahl verhindert einen stillen Griff zur Vorwahl."""
    metadata = json.loads((REFERENCE / "ratswahl-2026.json").read_text(encoding="utf-8"))
    index = next(int(p["index"]) for p in metadata["parteien"] if p["slug"] == "cdu")
    city = votemanager.parse((REFERENCE / "ratswahl-2026-stadt.csv").read_text(encoding="utf-8"))[0]
    cdu = city.lists[index]
    total, list_votes, candidate_votes = _required(cdu.total), _required(cdu.list_votes), _required(cdu.candidate_sum)
    if list_votes + candidate_votes != total:
        raise ValueError("Listen- und Personenstimmen summieren sich nicht")
    return RunoffAnalysisCouncil(
        year=2026, cdu_votes=total, cdu_list_votes=list_votes, cdu_candidate_votes=candidate_votes,
        source_url=metadata["quelle"]["url"],
    )


def _read_2014(filename: str, columns: dict[str, str]) -> list[mayor_districts.MayorDistrict]:
    result = []
    with (FIXTURES / "stichwahl-2014" / filename).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            number = int(row["gebiet-nr"])
            if number == 0:
                continue
            result.append(mayor_districts.MayorDistrict(
                number=number, name=row["gebiet-name"], area=0, postal=number >= 900,
                counted=row["anz-schnellmeldungen"] == row["max-schnellmeldungen"],
                eligible=int(row["A"]), voters=int(row["B"]), valid_votes=int(row["D"]),
                votes={slug: int(row[column]) for slug, column in columns.items()},
            ))
    if not result or any(not row.counted for row in result):
        raise ValueError("Unvollständiger Wahlstand 2014")
    return result


def _history(
    year: int, first_date: str, runoff_date: str,
    first: list[mayor_districts.MayorDistrict], runoff: list[mayor_districts.MayorDistrict],
    names: dict[str, str], source_urls: list[str], context: str,
) -> RunoffAnalysisHistory:
    a, b = totals(first), totals(runoff)
    changes = []
    for slug, name in names.items():
        before, after = _votes(first, slug), _votes(runoff, slug)
        changes.append(RunoffAnalysisChange(
            name=name, first_votes=before, runoff_votes=after, change_votes=after - before,
            change_pct=percent(after - before, before), growth_factor=after / before if before else None,
        ))
    return RunoffAnalysisHistory(
        year=year, first_date=first_date, runoff_date=runoff_date, first=a, runoff=b,
        change_voters=b["voters"] - a["voters"],
        change_voters_pct=percent(b["voters"] - a["voters"], a["voters"]),
        voter_count_ratio_pct=percent(b["voters"], a["voters"]),
        turnout_change_pp=(b["turnout_pct"] - a["turnout_pct"]
                           if b["turnout_pct"] is not None and a["turnout_pct"] is not None else None),
        candidates=changes, source_urls=source_urls, context=context,
    )


def history() -> list[RunoffAnalysisHistory]:
    names14 = {"krogmann": "Jürgen Krogmann", "baak": "Christoph Baak"}
    names21 = {"krogmann": "Jürgen Krogmann", "fuhrhop": "Daniel Fuhrhop"}
    return [
        _history(
            2014, "2014-09-28", "2014-10-12",
            _read_2014("hauptwahl-wahlbezirke.csv", {"krogmann": "D1", "baak": "D3"}),
            _read_2014("stichwahl-wahlbezirke.csv", {"krogmann": "D1", "baak": "D2"}),
            names14,
            ["https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterwahl_NDS_51_Gemeinde_Stadt_Oldenburg_Oldenburg.html",
             "https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterstichwahl_NDS_52_Gemeinde_Stadt_Oldenburg_Oldenburg.html"],
            "2014 sank die Wählendenzahl. Das Verhältnis der Gesamtzahlen zeigt nicht, "
            "welche Menschen erneut teilnahmen. Auch erstmals Teilnehmende können darunter sein.",
        ),
        _history(
            2021, "2021-09-12", "2021-09-26",
            _read(FIXTURES / "stichwahl-2021" / "uebersicht-223-erster-wahlgang.json", names21),
            _read(FIXTURES / "stichwahl-2021" / "uebersicht-224-stichwahl.json", names21),
            names21,
            ["https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20210917-11_KW_Bekanntmachung_Ergebnis_OB.pdf",
             "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20211001-2021-09-30_Bekanntmachung_Stichwahl_OB.pdf"],
            "Die Stichwahl 2021 fand am Tag der Bundestagswahl statt. Wie stark dieser gemeinsame "
            "Termin die Beteiligung beeinflusste, lässt sich aus den Ergebnissen allein nicht bestimmen.",
        ),
    ]


def compute() -> RunoffAnalysis:
    rows = _read(REFERENCE / "praesentation-ob-wahlbezirke.json", NAMES)
    candidates = _candidates(rows)
    methods = []
    for postal, name in [(False, "Urnenwahl"), (True, "Briefwahl")]:
        selected = [row for row in rows if row.postal == postal]
        finalists = [row for row in _candidates(selected) if row["in_runoff"]]
        methods.append(RunoffAnalysisMethod(
            name=name, voters=sum(_required(row.voters) for row in selected),
            valid_votes=sum(_required(row.valid_votes) for row in selected),
            finalist_votes=sum(row["votes"] for row in finalists), candidates=finalists,
        ))
    return RunoffAnalysis(
        election_date="2026-09-13", data_status="Vorläufiges Ergebnis · Datenabzug vom 14. September 2026",
        source_url=SOURCE_2026, district_count=len(rows),
        urn_district_count=sum(not row.postal for row in rows), postal_district_count=sum(row.postal for row in rows),
        totals=totals(rows), candidates=candidates, lead_votes=abs(_votes(rows, "prange") - _votes(rows, "rohr")),
        eliminated_votes=sum(row["votes"] for row in candidates if not row["in_runoff"]),
        grouped_other_votes=next(row["votes"] for row in candidates if row["slug"] == "other"),
        voting_methods=methods, council=council(), history=history(),
    )
