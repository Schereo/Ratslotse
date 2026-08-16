"""Haushalts-Ingestion + deterministische Quizfragen (ohne Netz/PDF-Download).

Das Fixture ist der ECHTE pypdf-Extrakt der Seite „Übersicht Ergebnishaushalt"
aus dem beschlossenen Haushaltsplan 2026 (04_…UEbersichten.pdf, S. 15) —
so testet der Parser exakt das Produktions-Layout.
"""
from __future__ import annotations

import json

from council import haushalt
from council.store import CouncilStore

PAGE_2026 = """Übersicht Ergebnishaushalt
Ergebnishaushalt Ordentliche
Erträge
Ordentliche
Aufwendungen
Ordentliches
Ergebnis
(Überschuss (+)
Fehlbetrag (-))
Außerordentliche
Erträge
Außerordentliche
Aufwendungen
Außerordentliches
Ergebnis
(Überschuss (+)
Fehlbetrag (-))
-Euro- -Euro- -Euro- -Euro- -Euro- -Euro-
1 2 3 4 5 6 7
Verwaltungsführung 867.043 9.711.555 -8.844.512
Personal/Organisation/Digitalisierung/IT 2.699.963 47.228.467 -44.528.505 10.650 0 10.650
Wirtschaftsförderung, Liegenschaften 2.217.788 7.398.938 -5.181.150 3.794.000 916.000 2.878.000
Finanzmanagement und Recht 529.282.894 100.677.045 428.605.849
Sicherheit und Ordnung 31.887.296 65.370.096 -33.482.800 12.000 12.000
Kultur, Museen, Sport 1.881.825 39.716.419 -37.834.594 531.000 -531.000
Stadtplanung 612.468 7.380.665 -6.768.196 0 0 0
Verkehr und Straßenbau 17.510.637 46.194.645 -28.684.009
Klima/Umwelt/Mobilität/Bau/Grün/Friedh. 6.000.586 32.218.453 -26.217.867 8.400 8.400
Soziales und Gesundheit 169.924.514 283.120.052 -113.195.538
Jugend und Familie 39.340.080 169.215.200 -129.875.119 0 0 0
Schule und Bildung 10.216.594 75.319.287 -65.102.693
nicht rechtsfähige Stiftungen 419.204 367.565 51.639 15.000 15.000 0
Summe 812.860.891 883.918.387 -71.057.496 3.840.050 1.462.000 2.378.050
115"""


def test_parse_ergebnishaushalt():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    assert len(rows) == 14 and sum(r["is_summe"] for r in rows) == 1
    soziales = next(r for r in rows if r["bereich"] == "Soziales und Gesundheit")
    assert soziales["ertraege"] == 169_924_514 and soziales["aufwendungen"] == 283_120_052
    assert soziales["ergebnis"] == -113_195_538
    summe = next(r for r in rows if r["is_summe"])
    assert summe["aufwendungen"] == 883_918_387
    # Kopf-/Fußzeilen („-Euro-", Spaltennummern, Seitenzahl) fallen raus:
    assert not any("Euro" in r["bereich"] for r in rows)
    # Summen-Validierung stimmt (Basis des extract_from_pdf-Guards):
    parts = [r for r in rows if not r["is_summe"]]
    assert abs(sum(r["aufwendungen"] for r in parts) - summe["aufwendungen"]) < 0.01 * summe["aufwendungen"]


def test_build_questions_grounded_and_asymmetric():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    qs = haushalt.build_questions(rows, 2026, "http://pdf")
    assert len(qs) >= 9
    est = [q for q in qs if q.get("qtype") == "estimate"]
    mc = [q for q in qs if q.get("qtype") != "estimate"]
    assert est and mc
    for q in est:
        # Antwort liegt in der Spanne, aber NICHT in der Mitte (Slider-Exploit).
        lo, hi, v = q["range_min"], q["range_max"], q["answer_value"]
        assert lo < v < hi
        assert abs((v - lo) / (hi - lo) - 0.5) > 0.08
        assert q["answer_unit"] in ("Mio. Euro", "Prozent") and q["source_ref"] == "http://pdf"
        assert q["topic"] == "Haushalt" and q["area_key"] == "haushalt"
    # Gesamt-Aufwendungen: 883,9 Mio → 884.
    gesamt = next(q for q in est if "insgesamt" in q["question"])
    assert gesamt["answer_value"] == 884.0
    # MC „größter Ausgabenblock" zeigt auf Soziales und Gesundheit.
    top = next(q for q in mc if "am meisten" in q["question"])
    assert top["options"][top["correct_index"]] == "Soziales und Gesundheit"
    assert len(top["options"]) == 4 and len(set(top["options"])) == 4
    # Ertrags-MC → Finanzmanagement und Recht.
    ertrag = next(q for q in mc if "Einnahmen" in q["question"])
    assert ertrag["options"][ertrag["correct_index"]] == "Finanzmanagement und Recht"


def test_chart_json_shape():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    qs = haushalt.build_questions(rows, 2026, "http://pdf")
    soz = next(q for q in qs if "Soziales und Gesundheit" in q["question"])
    chart = json.loads(soz["chart"])
    assert chart["unit"] == "Mio. Euro" and len(chart["items"]) == 13
    # absteigend sortiert, der gefragte Bereich hervorgehoben
    values = [it["value"] for it in chart["items"]]
    assert values == sorted(values, reverse=True)
    assert chart["items"][0]["label"] == "Soziales und Gesundheit"
    assert chart["items"][0].get("highlight") is True
    assert sum(1 for it in chart["items"] if it.get("highlight")) == 1


def test_store_haushalt_roundtrip_and_quiz(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    assert store.save_haushalt(2026, rows, "http://pdf") == 14
    assert store.save_haushalt(2026, rows, "http://pdf") == 14  # Re-Ingest idempotent
    got = store.get_haushalt(2026)
    assert len(got) == 14 and got[-1]["bereich"] == "Summe"  # Summe sortiert ans Ende
    assert got[0]["bereich"] == "Soziales und Gesundheit"    # größte Aufwendungen zuerst

    qs = haushalt.build_questions(rows, 2026, "http://pdf")
    n = store.save_quiz_questions(qs)
    assert n == len(qs)
    assert store.save_quiz_questions(qs) == 0  # Dedup über content_hash
    # Thema taucht mit kuratiertem Label auf:
    themes = {t["area_key"]: t["label"] for t in store.quiz_themes()}
    assert themes.get("haushalt") == "Stadt-Haushalt"
    # Chart NICHT in der Runde, aber in der Auflösung:
    picked = store.pick_quiz_questions([("thema", "haushalt")], None, [], 20)
    assert picked and all("chart" not in p for p in picked)
    full = store.get_quiz_question(picked[0]["id"])
    assert isinstance(full.get("chart"), dict) and full["chart"]["items"]


def test_extract_from_pdf_rejects_broken_sums(monkeypatch, tmp_path):
    # Layout-Drift-Guard: stimmt die Summenzeile nicht, wird NICHTS geliefert.
    kaputt = PAGE_2026.replace("883.918.387", "500.000.000")

    class FakePage:
        def extract_text(self):
            return kaputt

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage()]

    monkeypatch.setattr(haushalt, "PdfReader", FakeReader)
    assert haushalt.extract_from_pdf("egal.pdf") == []


# ---- v2: Anteils-/Erträge-/Ranking-Fragen + Trend über mehrere Jahre --------

def _shift(rows: list[dict], factor: float) -> list[dict]:
    """Fixture-Jahre simulieren: alle Beträge skaliert (Namen identisch)."""
    return [{**r, "ertraege": r["ertraege"] * factor,
             "aufwendungen": r["aufwendungen"] * factor,
             "ergebnis": r["ergebnis"] * factor} for r in rows]


def test_v2_share_ertraege_ranking():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    qs = haushalt.build_questions(rows, 2026, "http://pdf")
    # Anteils-Frage: 283/884 → 32 %, Donut-Chart mit hervorgehobenem Segment.
    anteil = next(q for q in qs if "Prozent" in q["question"])
    assert anteil["answer_value"] == 32.0 and anteil["answer_unit"] == "Prozent"
    share = json.loads(anteil["chart"])
    assert share["type"] == "share" and len(share["items"]) == 2
    assert share["items"][0]["highlight"] and share["items"][0]["value"] == 32
    assert share["items"][1]["value"] == 68
    # Erträge-Frage: 812,9 Mio → 813, Balken-Chart über die Erträge.
    ertraege = next(q for q in qs if "einzunehmen" in q["question"])
    assert ertraege["answer_value"] == 813.0
    assert json.loads(ertraege["chart"])["title"].startswith("Geplante Erträge")
    # Ranking-MC „am wenigsten": korrekt = kleinster der vier Optionen.
    wenigsten = next(q for q in qs if "am wenigsten" in q["question"])
    by_name = {r["bereich"]: r["aufwendungen"] for r in rows if not r["is_summe"]}
    vals = [by_name[o] for o in wenigsten["options"]]
    assert by_name[wenigsten["options"][wenigsten["correct_index"]]] == min(vals)


def test_trend_questions():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    by_year = {2020: _shift(rows, 0.66), 2023: _shift(rows, 0.80), 2026: rows}
    qs = haushalt.build_trend_questions(by_year, "http://pdf")
    assert len(qs) == 2
    # Wachstums-Schätzfrage: 1/0.66 - 1 ≈ +52 %, Trend-Chart mit 3 Jahren.
    wachstum = next(q for q in qs if q["qtype"] == "estimate")
    assert wachstum["answer_value"] == 52.0 and wachstum["answer_unit"] == "Prozent"
    trend = json.loads(wachstum["chart"])
    assert trend["type"] == "trend" and [i["label"] for i in trend["items"]] == ["2020", "2023", "2026"]
    assert trend["items"][-1].get("highlight") is True
    # Wachstums-MC: gleiche Skalierung → größter absoluter Zuwachs = größter Bereich.
    mc = next(q for q in qs if q["qtype"] == "mc")
    assert mc["options"][mc["correct_index"]] == "Soziales und Gesundheit"
    assert len(set(mc["options"])) == 4


def test_trend_needs_two_years():
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    assert haushalt.build_trend_questions({2026: rows}, "http://pdf") == []
    assert haushalt.build_trend_questions({}, "http://pdf") == []


def test_refresh_quiz_payloads_extends_trend(tmp_path):
    # Trend-Frage entsteht mit 2 Jahren; kommt ein Jahr dazu, verlängert der
    # Refresh die Trendlinie derselben Frage (gleicher content_hash).
    store = CouncilStore(tmp_path / "c.sqlite")
    rows = haushalt.parse_ergebnishaushalt(PAGE_2026)
    early = haushalt.build_trend_questions({2020: _shift(rows, 0.66), 2026: rows}, "http://pdf")
    store.save_quiz_questions(early)
    q_id = store.pick_quiz_questions([("thema", "haushalt")], None, [], 10)[0]["id"]
    assert len(store.get_quiz_question(q_id)["chart"]["items"]) == 2
    later = haushalt.build_trend_questions(
        {2020: _shift(rows, 0.66), 2023: _shift(rows, 0.8), 2026: rows}, "http://pdf")
    assert store.save_quiz_questions(later) == 0        # gleiche Hashes → kein Insert
    assert store.refresh_quiz_payloads(later) >= 1      # aber Payload aufgefrischt
    assert len(store.get_quiz_question(q_id)["chart"]["items"]) == 3


# --- Open-Data-CSVs (opendata.oldenburg.de) -----------------------------------
# Fixtures sind ECHTE Ausschnitte der Portal-Dateien (Stand 08/2026) — Format-
# Eigenheiten inklusive: Leerzeichen um Zahlen, Doppel-Leerzeichen im Namen,
# transliterierte Umlaute, Fehlbedarf-Zeile mit leerer Erträge-Spalte.

CSV_2024 = """Teilhaushalt;Bezeichnung;Ertraege [Euro];Aufwendungen [Euro]
THH01;Verwaltungsfuehrung; 446.540,00 ; 8.153.186,00 
THH04;Finanzmanagement und Recht; 444.505.552,00 ; 61.926.379,00 
THH05;Sicherheit  und Ordnung; 26.296.342,00 ; 55.971.760,00 
THH08;Verkehr und Strassenbau; 17.769.486,00 ; 41.590.574,00 
THH10;Soziales und Gesundheit; 144.236.532,00 ; 231.189.997,00 
THH13;Nicht rechtsfaehige Stiftungen; 310.505,00 ; 286.683,00 
Gesamtergebnishaushalt;; 633.564.957,00 ; 399.118.579,00 
Ordentliches Ergebnis (Fehlbedarf);;;-34.240.657,00 
"""

CSV_STEUERN = """Haushaltsjahr;Grundsteuer A+B;Gewerbesteuer (-umlage);Einkommensteueranteil;Gemeindeanteil an der Umsatzsteuer ;Getraenkesteuer;Vergnuegungssteuer;sonstige Steuern;insgesamt
1998;17629000;42719000;38025000;5428000;0;1321000;426000;105548000
2025;32585000;222117000;106086000;22233000;0;3368000;819000;387208000
"""

CSV_STEUERKRAFT = """Ausgleichsjahr;Steuerkraftmesszahl [Euro];Steuerkraftmesszahl [Euro/EW];Schluesselzuweisungen, Anordnungssoll [Euro];Schluesselzuweisungen, Anordnungssoll [Euro/EW]
1992;62980848;434;21478603;148
2025;348164497;1971;82278144;466
"""


def test_parse_opendata_ergebnishaushalt():
    rows = haushalt.parse_opendata_ergebnishaushalt(CSV_2024)
    # 6 Teilhaushalte + Summe; die redundante Fehlbedarf-Zeile fällt weg.
    assert len(rows) == 7 and sum(r["is_summe"] for r in rows) == 1
    vf = next(r for r in rows if r["bereich"] == "Verwaltungsführung")  # Umlaut restauriert
    assert vf["ertraege"] == 446_540.0 and vf["aufwendungen"] == 8_153_186.0
    assert vf["ergebnis"] == 446_540.0 - 8_153_186.0
    sich = next(r for r in rows if "Sicherheit" in r["bereich"])
    assert sich["bereich"] == "Sicherheit und Ordnung"  # Doppel-Leerzeichen normalisiert
    assert any(r["bereich"] == "Verkehr und Straßenbau" for r in rows)
    summe = next(r for r in rows if r["is_summe"])
    assert summe["bereich"] == "Summe"  # PDF-Konvention, damit Trends matchen


def test_parse_opendata_rejects_broken_sums():
    kaputt = CSV_2024.replace("633.564.957,00", "100.000,00")
    assert haushalt.parse_opendata_ergebnishaushalt(kaputt) == []


def test_parse_steuereinnahmen_langformat():
    rows = haushalt.parse_steuereinnahmen(CSV_STEUERN)
    assert len(rows) == 16  # 2 Jahre × 8 Spalten
    gew_2025 = next(r for r in rows if r["jahr"] == 2025 and r["art"].startswith("Gewerbesteuer"))
    assert gew_2025["betrag"] == 222_117_000.0
    # Umlaute restauriert, Kopf-Leerzeichen weg:
    arten = {r["art"] for r in rows}
    assert "Vergnügungssteuer" in arten and "Gemeindeanteil an der Umsatzsteuer" in arten


def test_parse_steuerkraft_und_store_roundtrip(tmp_path):
    kraft = haushalt.parse_steuerkraft(CSV_STEUERKRAFT)
    assert [k["jahr"] for k in kraft] == [1992, 2025]
    assert kraft[1]["messzahl"] == 348_164_497.0 and kraft[1]["zuweisungen_je_ew"] == 466.0

    store = CouncilStore(tmp_path / "c.sqlite")
    steuern = haushalt.parse_steuereinnahmen(CSV_STEUERN)
    assert store.save_steuereinnahmen(steuern, "http://csv") == 16
    assert store.save_steuereinnahmen(steuern, "http://csv") == 16  # idempotent
    assert len(store.get_steuereinnahmen()) == 16
    assert store.save_steuerkraft(kraft, "http://csv") == 2
    got = store.get_steuerkraft()
    assert got[0]["jahr"] == 1992 and got[-1]["messzahl_je_ew"] == 1971.0


def test_parse_einwohner():
    """Einwohnerzahlen aus dem 1102-CSV — Bezugsgröße für Pro-Kopf-Angaben.
    Die Aufwendungs-Spalten desselben CSV bleiben bewusst ungenutzt (sie sind
    weder als Plan noch als Ist gekennzeichnet)."""
    csv = ("Haushaltsjahr;Einwohner am 31.12. des Vorjahres;Aufwendungen gesamt [T Euro];"
           "Aufwendungen je Einwohner [Euro]\n"
           "2010;161334;358800;2224\n"
           "2025;176614;850170;4814\n"
           "Fußnote;;;\n")
    rows = haushalt.parse_einwohner(csv)
    assert rows == [{"jahr": 2010, "einwohner": 161334}, {"jahr": 2025, "einwohner": 176614}]


def test_store_einwohner_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.save_einwohner(
        [{"jahr": 2024, "einwohner": 176242}, {"jahr": 2025, "einwohner": 176614}], "http://csv") == 2
    assert store.einwohner_aktuell() == {"jahr": 2025, "einwohner": 176614}
    store.close()


# --- Jahresabschluss und Teilhaushalte (council/finanzberichte.py) -----------
# Fixtures sind echte Ausschnitte aus den RIS-Anlagen: Jahresabschluss 2023
# (Ergebnisrechnung der Kernverwaltung) und ein Teilhaushalts-Plan. Beide
# Formate haben Eigenheiten, die der Parser aushalten muss — mehrzeilige
# Bezeichnungen, leere Spalten, angeklebte Seitenzahlen.

from council import finanzberichte  # noqa: E402

JA_2023 = """3.1 Ergebnisrechnung Kernverwaltung
Erträge und Aufwendungen Ergebnis des
Vorjahres
2022
Ansätze des
Haushaltsjahres
2023
Veränderung
durch Nachtrag
Ergebnis des
Haushaltsjahres
2023
mehr (+) /
weniger (-)4)
2023
 - Euro -
1 2 3 4 5 6 7
ordentliche Erträge
01. Steuern und ähnliche Abgaben 305.411.797,55 287.275.000,00  341.608.473,52 54.333.473,52
02. Zuwendungen und allgemeine
Umlagen 1) 174.056.740,20 173.491.384,15  168.262.169,22 -5.229.214,93
12. = Summe ordentliche Erträge 696.627.777,13 664.574.528,42  732.987.197,61 68.412.669,19
JA 23
ordentliche Aufwendungen
13. Personalaufwendungen 156.269.655,13 165.843.899,07  164.821.893,60 -1.022.005,47 249.897,84
20. = Summe ordentliche
Aufwendungen 661.705.829,31 674.305.462,42  683.032.270,32 8.726.807,90 12.508.878,04
21. ordentliches Ergebnis 34.921.947,82 -9.730.934,00  49.954.927,29 59.685.861,29 -12.508.878,04
3.2 Gesamtergebnisrechnung
01. Steuern und ähnliche Abgaben 999.999.999,99 888.888.888,88  777.777.777,77 -111.111.111,11
"""

THH_PLAN = """Teilergebnishaushalt THH06: Kultur, Museen, Sport
Produkt: Archivierung (P10.111023)
Amt für Kultur, Museen und Sport
Erträge und Aufwendungen Ergebnis 2018
- Euro -
Ansatz 2019
- Euro -
Ansatz 2020
- Euro -
Ansatz 2021
- Euro -
Ansatz 2022
- Euro -
Ansatz 2023
- Euro -
Ordentliche Erträge
06. privatrechtliche Entgelte 4.861,50 2.000 3.500 3.500 3.5003.500
12. =Summe ordentliche
Erträge
13.583,31 4.206 5.684 5.684 5.684 5.684
Ordentliche Aufwendungen
20. = Summe ordentliche
Aufwendungen
419.068,76 484.239 436.282 443.160 450.173 457.319
21. ordentliches Ergebnis -405.485,45 -480.033 -430.598 -437.476 -444.489 -451.635
601
Teilergebnishaushalt THH06: Kultur, Museen, Sport
Produkt: Ohne Summenzeile (P10.999999)
Amt für Kultur, Museen und Sport
Erträge und Aufwendungen Ergebnis 2018
Ansatz 2019
"""


def test_parse_ergebnisrechnung_plan_und_ist():
    posten = finanzberichte.parse_ergebnisrechnung(JA_2023, 2023)
    nach_nr = {p["nr"]: p for p in posten}
    steuern = nach_nr[1]
    assert steuern["ansatz"] == 287_275_000.0      # geplant
    assert steuern["ergebnis"] == 341_608_473.52   # tatsächlich
    assert steuern["vorjahr"] == 305_411_797.55
    # Mehrzeilige Bezeichnung („Zuwendungen und allgemeine\nUmlagen 1)")
    assert nach_nr[2]["ergebnis"] == 168_262_169.22
    # Summenzeilen als solche markiert
    assert nach_nr[12]["ist_summe"] == 1 and nach_nr[20]["ist_summe"] == 1
    assert nach_nr[12]["ansatz"] == 664_574_528.42
    # Die Gesamtergebnisrechnung (anderer Umfang!) darf NICHT mitgelesen werden.
    assert steuern["ansatz"] != 888_888_888.88


def test_ergebnisrechnung_verwirft_unplausible_zeilen():
    """Stimmt die dokumentierte Beziehung Abweichung = Ergebnis − Ansatz nicht,
    ist die Spaltenzuordnung unsicher — dann lieber nichts."""
    kaputt = JA_2023.replace("54.333.473,52", "11.111.111,11")
    nach_nr = {p["nr"]: p for p in finanzberichte.parse_ergebnisrechnung(kaputt, 2023)}
    assert 1 not in nach_nr        # Steuern-Zeile fällt raus
    assert 12 in nach_nr           # der Rest bleibt lesbar


def test_parse_teilergebnishaushalt_produkte():
    produkte = finanzberichte.parse_teilergebnishaushalt(THH_PLAN)
    assert len(produkte) == 1      # das zweite Produkt hat keine Summenzeilen
    p = produkte[0]
    assert p["produkt_nr"] == "P10.111023" and p["produkt_name"] == "Archivierung"
    assert p["thh_nr"] == 6 and p["amt"] == "Amt für Kultur, Museen und Sport"
    # Haushaltsjahr = ERSTER Ansatz (2019), nicht das letzte Finanzplanungsjahr
    assert p["jahr"] == 2019
    assert p["ertraege"] == 4206.0 and p["aufwendungen"] == 484_239.0
    assert p["ergebnis"] == -480_033.0
    # Die angeklebte Seitenzahl (601) darf kein Wert werden.
    assert p["ergebnis"] != 601


def test_teilergebnishaushalt_prueft_summe():
    kaputt = THH_PLAN.replace("-405.485,45 -480.033", "-405.485,45 -999.999")
    assert finanzberichte.parse_teilergebnishaushalt(kaputt) == []


def test_store_finanzberichte_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    posten = finanzberichte.parse_ergebnisrechnung(JA_2023, 2023)
    assert store.save_ergebnisrechnung(2023, posten, "JA 2023", "http://x") == len(posten)
    assert store.save_ergebnisrechnung(2023, posten, "JA 2023", "http://x") == len(posten)  # idempotent
    assert store.ergebnisrechnung_jahre() == [2023]
    geladen = {p["nr"]: p for p in store.get_ergebnisrechnung(2023)}
    assert geladen[1]["ansatz"] == 287_275_000.0

    produkte = finanzberichte.parse_teilergebnishaushalt(THH_PLAN)
    assert store.save_produkte(2019, produkte, "THH06", None) == 1
    assert store.produkte_jahre() == [2019]
    assert store.get_produkte(2019, thh_nr=6)[0]["produkt_name"] == "Archivierung"
    assert store.get_produkte(2019, thh_nr=99) == []
    store.close()
