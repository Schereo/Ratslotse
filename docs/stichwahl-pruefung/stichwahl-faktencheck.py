"""Unabhängige Stadtgesamtwerte; liest Quellen, importiert kein Wahlmodell.

Aufruf: python3.12 stichwahl-faktencheck.py /pfad/zum/repo > nachrechnung.json
Die 2014er Quellen liegen als unveränderte Kopien aus dem geprüften Git-Commit bei.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1]).resolve()
PR2014 = "a78689b63d225a893c0ab26ae643b3bdea73ab5b"
FROZEN_2014 = {
    "hauptwahl-wahlbezirke.csv": "9ac4f61853682afaa4fbcb61e92013a5512f4d73afe5f01372b85965ffb9587d",
    "stichwahl-wahlbezirke.csv": "87e8e606a6a5ac61916b06e122541631ccd6e31add83a0ca357c04622250c024",
}
SOURCES = {}


def source(path, commit=None):
    if commit:
        assert commit == PR2014
        filename = Path(path).name
        data = (Path(__file__).resolve().parent / "quellen-2014" / filename).read_bytes()
        assert hashlib.sha256(data).hexdigest() == FROZEN_2014[filename], filename
    else:
        data = (ROOT / path).read_bytes()
    SOURCES[path] = {"sha256": hashlib.sha256(data).hexdigest(), "git_commit": commit}
    return data.decode("utf-8-sig")


def pct(n, d):
    return 100 * n / d if d else None


def overview(path):
    table = json.loads(source(path))["tabelle"]
    headers = [c["labelKurz"] for c in table["header"][2:]]
    rows = []
    city = None
    for row in table["zeilen"]:
        number = re.match(r"^(\d+)\s", row["label"])
        if not number and not row["label"].startswith("Stadt Oldenburg"):
            continue
        assert row["statusProzent"] == 100, row["label"]
        values = [int(f["absolut"].replace(".", "").replace("\u00a0", "")) for f in row["felder"]]
        assert len(values) == len(headers)
        assert sum(values[3:]) == values[2], row["label"]
        assert 0 <= values[2] <= values[1]
        if number:
            rows.append((int(number.group(1)), dict(zip(headers, values))))
        else:
            assert city is None
            city = dict(zip(headers, values))
    assert rows and len({n for n, _ in rows}) == len(rows)
    total = {key: sum(row[key] for _, row in rows) for key in headers}
    if city is not None:
        assert city == total, "Bezirks- und Stadtsummen weichen ab"
    assert total["Wahlbeteiligung"] <= total["Wahlberechtigte"]
    return total, rows


def brief(total, rows):
    out = {}
    for label, postal in [("urne", False), ("brief", True)]:
        chosen = [row for n, row in rows if (n >= 900) == postal]
        subtotal = {k: sum(r[k] for r in chosen) for k in total}
        finalists = subtotal["Rohr, GRÜNE"] + subtotal["Prange, SPD"]
        out[label] = {
            "bezirke": len(chosen), "waehlende": subtotal["Wahlbeteiligung"],
            "gueltige_stimmen": subtotal["gültig"], "finalisten_stimmen": finalists,
            "rohr_stimmen": subtotal["Rohr, GRÜNE"], "prange_stimmen": subtotal["Prange, SPD"],
            "rohr_anteil_alle_pct": pct(subtotal["Rohr, GRÜNE"], subtotal["gültig"]),
            "rohr_anteil_zweier_pct": pct(subtotal["Rohr, GRÜNE"], finalists),
        }
    return out


def csv2014(filename):
    path = "tests/fixtures/wahlabend/stichwahl-2014/" + filename
    rows = list(csv.DictReader(io.StringIO(source(path, PR2014)), delimiter=";"))
    columns = [c for c in rows[0] if c in {"A", "B", "D"} or re.fullmatch(r"D\d+", c)]
    district = [r for r in rows if int(r["gebiet-nr"]) != 0]
    assert len({r["gebiet-nr"] for r in district}) == len(district)
    for row in district:
        assert row["anz-schnellmeldungen"] == row["max-schnellmeldungen"]
        assert sum(int(row[c]) for c in columns if c.startswith("D") and c != "D") == int(row["D"])
    return {c: sum(int(r[c]) for r in district) for c in columns}


def history(first, second, candidates):
    # Einheitliches Schema: Wahlberechtigte, Wählende, gültige Stimmen.
    a, b = first, second
    invalid_a, invalid_b = a["B"] - a["D"], b["B"] - b["D"]
    changes = {name: {
        "erster_wahlgang": before, "stichwahl": after, "differenz": after - before,
        "veraenderung_pct": pct(after - before, before), "faktor": after / before,
    } for name, before, after in candidates}
    eliminated = a["D"] - sum(c[1] for c in candidates)
    gain = sum(c[2] - c[1] for c in candidates)
    assert sum(c[2] for c in candidates) == b["D"]
    assert gain - eliminated == b["D"] - a["D"]
    assert b["B"] - a["B"] == b["D"] - a["D"] + invalid_b - invalid_a
    return {
        "wahlberechtigte": [a["A"], b["A"]], "waehlende": [a["B"], b["B"]],
        "gueltige_stimmen": [a["D"], b["D"]], "ungueltige_stimmzettel": [invalid_a, invalid_b],
        "veraenderung_waehlende": b["B"] - a["B"],
        "veraenderung_gueltige_stimmen": b["D"] - a["D"],
        "veraenderung_ungueltige_stimmzettel": invalid_b - invalid_a,
        "wahlbeteiligung_pct": [pct(a["B"], a["A"]), pct(b["B"], b["A"])],
        "wahlbeteiligung_delta_pp": pct(b["B"], b["A"]) - pct(a["B"], a["A"]),
        "verhaeltnis_waehlendenzahlen_pct": pct(b["B"], a["B"]),
        "ausgeschiedene_stimmen_erster_wahlgang": eliminated,
        "zuwachs_finalisten_zusammen": gain, "kandidaten": changes,
    }


ob, rows = overview("kommunalwahl/referenz-2026/praesentation-ob-wahlbezirke.json")
methods = brief(ob, rows)
assert len(rows) == 133 and methods["brief"]["bezirke"] == 42
council = {}
for year in [2021, 2026]:
    base = f"kommunalwahl/referenz-{year}/ratswahl-{year}"
    metadata = json.loads(source(base + ".json"))
    cdu = next(p["index"] for p in metadata["parteien"] if p["slug"] == "cdu")
    city = list(csv.DictReader(io.StringIO(source(base + "-stadt.csv")), delimiter=";"))
    districts = list(csv.DictReader(io.StringIO(source(base + "-wahlbezirke.csv")), delimiter=";"))
    assert len(city) == 1
    # Der Export hat sein Schema geändert: 2021 ist D2_4 eine Einzelperson,
    # 2026 dagegen ist D3_4 die Summe der Liste. Nicht dieselben Suffixe raten.
    suffix = "summe_liste_kandidaten" if year == 2021 else "4"
    column = f"D{cdu}_{suffix}"
    total_columns = [k for k in city[0] if re.fullmatch(r"D\d+_" + suffix, k)]
    for row in [*city, *districts]:
        assert row["anz-schnellmeldungen"] == row["max-schnellmeldungen"]
        assert row[column], "Die zu prüfende CDU-Summe darf nicht fehlen"
        # Nicht jeder Einzelwahlvorschlag tritt in jedem Wahlbereich an.
        # Die ausgewiesenen Listensummen müssen dennoch alle Stimmen ergeben.
        assert sum(int(row[k]) for k in total_columns if row[k]) == int(row["D"])
    total = int(city[0][column])
    list_key, person_key = ((f"D{cdu}_liste", f"D{cdu}_summe_kandidaten")
                            if year == 2021 else (f"D{cdu}_1", f"D{cdu}_3"))
    assert int(city[0][list_key]) + int(city[0][person_key]) == total
    assert total == sum(int(d[column]) for d in districts)
    council[str(year)] = total
a14, b14 = csv2014("hauptwahl-wahlbezirke.csv"), csv2014("stichwahl-wahlbezirke.csv")
a21, _ = overview("tests/fixtures/wahlabend/stichwahl-2021/uebersicht-223-erster-wahlgang.json")
b21, _ = overview("tests/fixtures/wahlabend/stichwahl-2021/uebersicht-224-stichwahl.json")
def normalize21(row):
    return {"A": row["Wahlberechtigte"], "B": row["Wahlbeteiligung"], "D": row["gültig"]}
result = {
    "zweck": "Unabhängige deskriptive Prüfung von Stadtgesamtwerten",
    "ob_2026": ob, "wahlarten_2026": methods,
    "nichtwaehlende_2026": ob["Wahlberechtigte"] - ob["Wahlbeteiligung"],
    "ausgeschiedene_2026": ob["gültig"] - ob["Rohr, GRÜNE"] - ob["Prange, SPD"],
    "cdu_ratswahl_stimmen": council,
    "historie_2014": history(a14, b14, [("Krogmann", a14["D1"], b14["D1"]), ("Baak", a14["D3"], b14["D2"])]),
    "historie_2021": history(normalize21(a21), normalize21(b21), [
        ("Krogmann", a21["Krogmann, SPD"], b21["Krogmann, SPD"]),
        ("Fuhrhop", a21["Fuhrhop, GRÜNE"], b21["Fuhrhop, GRÜNE"])]),
    "quellen": SOURCES,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
