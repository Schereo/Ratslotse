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
Produkt: Archivierung (P10.111023)
Amt für Kultur, Museen und Sport
Verantwortlich: Fachdienstleitung Zentrale Dienste
Das Produkt umfasst die Bewertung der Archivwürdigkeit von Medien aller Art, die Erschließung,
Verwahrung und Pflege der Archivbestände sowie die Beratung, Vermittlung und Information Dritter.
Auch zu den Bereichen Forschung und Dokumentation der Stadtgeschichte werden Leistungen
erbracht.
Kurzbeschreibung:
Bundesarchivgesetz, Nds. Archivgesetz, Entgeltordnung des Stadtarchivs Oldenburg, Benutzungs-
und Gebührenordnung des Landesarchivs (Standort Oldenburg), Vertrag mit dem Landesarchiv,
verschiedene privatrechtliche Vereinbarungen
Auftragsgrundlage:
Grad der Beeinflussbarkeit: niedrig
Wirkungskreis: übertragender und eigener Wirkungskreis
gesamte Stadtverwaltung, alle Oldenburger Einwohnerinnen und Einwohner, weitere Behörden,
Historikerinnen und Historiker
Zielgruppe(n):
Sicherung potenziellen Archivgutes
Ziel(e):
702
Teilergebnishaushalt THH06: Kultur, Museen, Sport
Produkt: Archivierung (P10.111023)
Leistung: Archivierung (Leistung) (P10.111023.001)
Amt für Kultur, Museen und Sport
Vorgänge aus den verschiedensten Bereichen der Stadtverwaltung werden hinsichtlich der
Archivwürdigkeit bewertet und gegebenenfalls im Stadtarchiv verwahrt. Die Pflege und die Bildung
neuer Archivbestände ist eine weitere Aufgabe im Rahmen dieser Leistung.
Kurzbeschreibung:
Bundesarchivgesetz, Nds. Archivgesetz
Auftragsgrundlage:
Grad der Beeinflussbarkeit: hoch
Wirkungskreis: eigener Wirkungskreis
Teilergebnishaushalt THH06: Kultur, Museen, Sport
Produkt: Ohne Summenzeile (P10.999999)
Amt für Kultur, Museen und Sport
Erträge und Aufwendungen Ergebnis 2018
Ansatz 2019
"""

# Steckbrief mit der Grunddaten-Tabelle DAZWISCHEN: Ihr Label steht
# ausnahmsweise VOR seinem Inhalt, die Tabelle liegt also zwischen
# „Wirkungskreis:" und „Zielgruppe(n):" und lief ungefiltert als Zielgruppe
# auf die Seite. Wörtlicher Ausschnitt aus THH10 (Haushalt 2023).
THH_MIT_GRUNDDATEN = """Teilergebnishaushalt THH10: Soziales und Gesundheit
Produkt: Sozialhilfe SGB XII ö.T. (P10.311101)
Amt für Teilhabe und Soziales
Erträge und Aufwendungen Ergebnis 2021
- Euro -
Ansatz 2022
- Euro -
12. =Summe ordentliche
Erträge
1.000,00 2.000
20. = Summe ordentliche
Aufwendungen
3.000,00 5.000
21. ordentliches Ergebnis -2.000,00 -3.000
1091
Teilergebnishaushalt THH10: Soziales und Gesundheit
Produkt: Sozialhilfe SGB XII ö.T. (P10.311101)
Amt für Teilhabe und Soziales
Verantwortlich: Amtsleitung
Die Aufgabe der Sozialhilfe ist es, den Leistungsberechtigten die Führung eines Lebens zu
ermöglichen, das der Würde des Menschen entspricht.
Kurzbeschreibung:
Sozialgesetzbuch Zwölftes Buch (SGB XII),
dazu erlassene Verordnungen, Niedersächsisches Ausführungsgesetz zum SGB IX und SGB XII,
SGB I und X
Auftragsgrundlage:
Grad der Beeinflussbarkeit: Niedrig
Wirkungskreis: Eigener Wirkungskreis
Grunddaten:
Einheit
Ist 2021 Plan 2022 Plan 2023 Plan 2024 Plan 2025 Plan 2026
Mitarbeiter/innen PRS 3,46 3,44 3,50 3,50 3,50 3,50
Mitarbeiter/innen,
vollzeitverrechnet PRS 3,15 3,09 3,15 3,15 3,15 3,15
HLU ö.T.,
Leistungsberechtigte
PRS 98 100 110 110 110 110
1092
1092
1092
Teilergebnishaushalt THH10: Soziales und Gesundheit
Produkt: Sozialhilfe SGB XII ö.T. (P10.311101)
Amt für Teilhabe und Soziales
Einheit Ist 2021 Plan 2022 Plan 2023 Plan 2024 Plan 2025 Plan 2026
BuT SGB XII ö.T.:
Teilhabe am sozialen
und kulturellen Leben,
Leistungsberechtigte
PRS 24 20 30 30 30 30
Kinder und Jugendliche bis 18 Jahre, die ihren notwendigen Lebensunterhalt nicht oder nicht
ausreichend aus eigenen Kräften und Mitteln, vor allem aus Einkommen und Vermögen, beschaffen
oder die für sie notwendigen Tätigkeiten nicht ausführen können oder eine Absicherung im
Krankheitsfall benötigen.
Zielgruppe(n):
Steigerung der Qualität, Ausbau der Beratungskultur, zeitnahe Auskünfte und Hilfestellungen, gute
Erreichbarkeit.
Ziel(e):
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


# --- Produkt-Steckbrief ------------------------------------------------------

def test_steckbrief_liest_label_rueckwaerts():
    """Die Label stehen im extrahierten Text NACH ihrem Inhalt. Wer vorwärts
    liest, bekommt jedes Feld um eines verschoben — die Kurzbeschreibung wäre
    dann das Gesetz."""
    p = finanzberichte.parse_teilergebnishaushalt(THH_PLAN)[0]
    assert p["kurzbeschreibung"].startswith("Das Produkt umfasst die Bewertung der Archivwürdigkeit")
    assert p["kurzbeschreibung"].endswith("werden Leistungen erbracht.")
    assert p["auftragsgrundlage"].startswith("Bundesarchivgesetz, Nds. Archivgesetz")
    assert "Vertrag mit dem Landesarchiv" in p["auftragsgrundlage"]
    # Genau die Verwechslung, die eine Vorwärtslesung produzieren würde:
    assert "Bundesarchivgesetz" not in p["kurzbeschreibung"]
    assert "Das Produkt umfasst" not in p["auftragsgrundlage"]


def test_steckbrief_inline_felder():
    """Kurze Werte passen im PDF neben ihr Label und stehen deshalb DAHINTER."""
    p = finanzberichte.parse_teilergebnishaushalt(THH_PLAN)[0]
    assert p["beeinflussbarkeit_roh"] == "niedrig"
    assert p["beeinflussbarkeit"] == "niedrig"
    assert p["wirkungskreis"] == "übertragender und eigener Wirkungskreis"
    assert p["zielgruppe"].startswith("gesamte Stadtverwaltung, alle Oldenburger")
    # „Verantwortlich: …" steht auf derselben Zeile wie sein Label und darf
    # nicht vorn in der Kurzbeschreibung landen.
    assert "Fachdienstleitung" not in p["kurzbeschreibung"]
    # Und der Wirkungskreis nicht vorn in der Zielgruppe.
    assert "Wirkungskreis" not in p["zielgruppe"]


def test_steckbrief_ignoriert_leistungen():
    """Jede Leistung trägt einen eigenen Steckbrief mit denselben Feldern.
    Ungefiltert bekäme das Produkt den Text einer Unterposition."""
    p = finanzberichte.parse_teilergebnishaushalt(THH_PLAN)[0]
    assert "Vorgänge aus den verschiedensten Bereichen" not in p["kurzbeschreibung"]
    assert p["beeinflussbarkeit"] == "niedrig"      # nicht das „hoch" der Leistung
    assert p["wirkungskreis"] != "eigener Wirkungskreis"


def test_steckbrief_ohne_tabelle():
    """Zwischen „Wirkungskreis:" und „Zielgruppe(n):" kann die ganze
    Grunddaten-Tabelle stehen — sie stand sonst als Zielgruppe auf der Seite."""
    p = finanzberichte.parse_teilergebnishaushalt(THH_MIT_GRUNDDATEN)[0]
    assert p["zielgruppe"].startswith("Kinder und Jugendliche bis 18 Jahre")
    for rest in ("Einheit", "PRS", "Mitarbeiter/innen", "Plan 2024"):
        assert rest not in p["zielgruppe"]
    # Auch der wiederholte Seitenkopf gehört nicht in den Fließtext.
    assert "Teilergebnishaushalt" not in p["zielgruppe"]
    assert "Amt für Teilhabe und Soziales" not in p["zielgruppe"]


def test_beeinflussbarkeit_normalisiert():
    """Die Pläne schreiben denselben Spielraum mal „niedrig", mal „gering",
    mal groß. Der Rohwert bleibt daneben stehen."""
    norm = finanzberichte.normalisiere_beeinflussbarkeit
    assert norm("gering") == "niedrig"
    assert norm("Niedrig") == norm("niedrig") == "niedrig"
    assert norm("Mittel") == "mittel" and norm("hoch") == "hoch"
    # Mischformen bekommen keine Stufe — jede Wahl wäre eine Behauptung.
    assert norm("niedrig/mittel bei Prävention") is None
    assert norm("") is None and norm(None) is None

    p = finanzberichte.parse_teilergebnishaushalt(THH_MIT_GRUNDDATEN)[0]
    assert p["beeinflussbarkeit_roh"] == "Niedrig"   # Wortlaut des Plans
    assert p["beeinflussbarkeit"] == "niedrig"       # normalisiert


def test_steckbrief_erfindet_nichts():
    """Fehlt ein Feld, bleibt es None — es wird nicht vom Nachbarprodukt
    geerbt (der Fehler, den es bei den Zahlen schon einmal gab)."""
    ohne = THH_PLAN.replace(
        "Das Produkt umfasst die Bewertung der Archivwürdigkeit von Medien aller Art, die Erschließung,\n"
        "Verwahrung und Pflege der Archivbestände sowie die Beratung, Vermittlung und Information Dritter.\n"
        "Auch zu den Bereichen Forschung und Dokumentation der Stadtgeschichte werden Leistungen\n"
        "erbracht.\n", "")
    p = finanzberichte.parse_teilergebnishaushalt(ohne)[0]
    assert p["kurzbeschreibung"] is None
    # Die übrigen Felder bleiben lesbar.
    assert p["auftragsgrundlage"].startswith("Bundesarchivgesetz")
    assert p["beeinflussbarkeit"] == "niedrig"


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
    # Der Steckbrief überlebt die Runde durch die Datenbank.
    gespeichert = store.get_produkte(2019, thh_nr=6)[0]
    assert gespeichert["beeinflussbarkeit"] == "niedrig"
    assert gespeichert["beeinflussbarkeit_roh"] == "niedrig"
    assert gespeichert["wirkungskreis"] == "übertragender und eigener Wirkungskreis"
    assert "Archivwürdigkeit" in gespeichert["kurzbeschreibung"]
    store.close()


def test_produkt_suche_und_filter(tmp_path):
    """Suche und Filter laufen serverseitig — mit dem Steckbrief trägt jede
    Zeile mehrere hundert Zeichen Fließtext."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_produkte(2019, finanzberichte.parse_teilergebnishaushalt(THH_PLAN),
                        "THH06", None)
    store.save_produkte(2019, finanzberichte.parse_teilergebnishaushalt(THH_MIT_GRUNDDATEN),
                        "THH10", None)
    assert len(store.get_produkte(2019)) == 2

    # Name, Nummer, Amt und Kurzbeschreibung sind durchsuchbar …
    assert [p["produkt_nr"] for p in store.get_produkte(2019, suche="Archiv")] == ["P10.111023"]
    assert [p["produkt_nr"] for p in store.get_produkte(2019, suche="P10.311101")] == ["P10.311101"]
    assert [p["produkt_nr"] for p in store.get_produkte(2019, suche="Teilhabe")] == ["P10.311101"]
    assert [p["produkt_nr"] for p in store.get_produkte(2019, suche="Archivwürdigkeit")] == ["P10.111023"]
    # … mehrere Begriffe grenzen ein (UND), statt zu erweitern.
    assert store.get_produkte(2019, suche="Archiv Sozialhilfe") == []
    assert store.get_produkte(2019, suche="Klärwerk") == []

    assert len(store.get_produkte(2019, beeinflussbarkeit="niedrig")) == 2
    assert store.get_produkte(2019, beeinflussbarkeit="hoch") == []
    assert [p["produkt_nr"] for p in
            store.get_produkte(2019, amt="Amt für Teilhabe und Soziales")] == ["P10.311101"]

    # Einzelabruf für den Steckbrief — auch wenn ein Filter ihn ausblendete.
    assert store.produkt(2019, "P10.111023")["produkt_name"] == "Archivierung"
    assert store.produkt(2019, "P10.000000") is None

    f = store.produkt_facetten(2019)
    assert {a["amt"] for a in f["aemter"]} == {"Amt für Kultur, Museen und Sport",
                                              "Amt für Teilhabe und Soziales"}
    assert f["spielraum"] == {"niedrig": 2}
    assert f["mit_feld"]["kurzbeschreibung"] == 2
    store.close()


def test_produkt_steckbrief_migration(tmp_path):
    """Bestandsdatenbanken bekommen die Spalten per ALTER TABLE — der
    Primärschlüssel bleibt, die vorhandenen Zeilen bleiben stehen."""
    import sqlite3
    pfad = tmp_path / "alt.sqlite"
    conn = sqlite3.connect(pfad)
    conn.execute(
        "CREATE TABLE council_produkte ("
        "jahr INTEGER NOT NULL, produkt_nr TEXT NOT NULL, produkt_name TEXT NOT NULL, "
        "thh_nr INTEGER, thh_name TEXT, amt TEXT, "
        "ertraege REAL, aufwendungen REAL, ergebnis REAL, "
        "quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, "
        "PRIMARY KEY (jahr, produkt_nr))")
    conn.execute("INSERT INTO council_produkte VALUES "
                 "(2019,'P10.111023','Archivierung',6,'Kultur',NULL,1,2,-1,NULL,NULL,'x')")
    conn.commit()
    conn.close()

    store = CouncilStore(pfad)
    alt = store.produkt(2019, "P10.111023")
    assert alt["produkt_name"] == "Archivierung"   # Bestand unangetastet
    assert alt["kurzbeschreibung"] is None         # neue Spalte, noch leer
    assert store.get_produkte(2019, suche="Archiv")[0]["produkt_nr"] == "P10.111023"
    store.close()


# --- Plan gegen Ist je Teilhaushalt -----------------------------------------
# Der Jahresabschluss führt dieselbe Tabelle noch einmal je Teilhaushalt.
# Fixture ist ein Ausschnitt aus dem Abschluss 2023 (THH01), gekürzt auf die
# Posten, die für „geplant gegen tatsächlich" zählen.

JA_THH = """3.1 Ergebnisrechnung Kernverwaltung
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
ordentliche Erträge
01. Steuern und ähnliche Abgaben 305.411.797,55 287.275.000,00  341.608.473,52 54.333.473,52
12. = Summe ordentliche Erträge 696.627.777,13 664.574.528,42  732.987.197,61 68.412.669,19
20. = Summe ordentliche
Aufwendungen 661.705.829,31 674.305.462,42  683.032.270,32 8.726.807,90
Gesamtergebnisrechnung
5 Teilhaushalte
Teilhaushalt 01 - Verwaltungsführung

A. Teil-Ergebnisrechnung   THH01 Verwaltungsführung
Erträge und Aufwendungen Ergebnis des
Vorjahres
2022
Ansätze des
Haushaltsjahres
2023
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 20233)
Ergebnis des
Haushaltsjahres
2023
mehr (+) /
weniger (-)4)
2023
 - Euro -
1 2 3 4 5 6 7
Ordentliche Erträge
02. Zuwendungen u. allgem. Umlagen 1) 45.972,00 281.352,15  107.663,14 -173.689,01
12. =Summe ordentliche Erträge 448.727,99 568.542,15  475.819,90 -92.722,25
Ordentliche Aufwendungen
13. Personalaufwendungen 5.560.455,48 5.716.337,99  5.791.734,64 75.396,65
20. =Summe ordentliche Aufwendungen 8.011.111,11 674.305.462,42  683.032.270,32 8.726.807,90
B. Teil-Finanzrechnung THH01 Verwaltungsführung
12. =Summe ordentliche Erträge 111.111,11 222.222,22  333.333,33 111.111,11
"""


def test_parse_teilergebnisrechnungen():
    thh = finanzberichte.parse_teilergebnisrechnungen(JA_THH, 2023)
    assert len(thh) == 1
    t = thh[0]
    assert t["thh_nr"] == 1 and t["thh_name"] == "Verwaltungsführung"
    nach_nr = {p["nr"]: p for p in t["posten"]}
    # Die Werte stammen aus der Teil-ERGEBNISrechnung, nicht aus der
    # Teil-Finanzrechnung, die direkt darunter dieselben Postennummern trägt.
    assert nach_nr[12]["ansatz"] == 568_542.15
    assert nach_nr[12]["ergebnis"] == 475_819.90
    assert nach_nr[12]["ansatz"] != 222_222.22


def _summenzeilen(ertraege_plan, ertraege_ist, aufw_plan, aufw_ist):
    """Kleine Hilfe: die beiden Summenzeilen einer Ebene."""
    return [{"nr": 12, "plan": ertraege_plan, "ergebnis": ertraege_ist},
            {"nr": 20, "plan": aufw_plan, "ergebnis": aufw_ist}]


def test_summenprobe_faengt_stille_fehlgriffe():
    """Die zeilenweise Prüfung erkennt nicht, wenn für einen Teilhaushalt eine
    andere, in sich stimmige Tabelle gelesen wurde — im Abschluss 2022 wurde
    THH09 so mit 0,1 statt 26,8 Mio. € gelesen. Erst die Summe zeigt es."""
    gesamt = _summenzeilen(80_000_000.0, 82_000_000.0, 100_000_000.0, 99_000_000.0)
    passend = [{"posten": _summenzeilen(50e6, 51e6, 60e6, 59e6)},
               {"posten": _summenzeilen(30e6, 31e6, 40e6, 40e6)}]
    daneben = [{"posten": _summenzeilen(50e6, 51e6, 60e6, 59e6)},
               {"posten": _summenzeilen(30e6, 31e6, 100_000.0, 100_000.0)}]
    assert finanzberichte.summenprobe(passend, gesamt)[0] is True
    ok, anteil = finanzberichte.summenprobe(daneben, gesamt)
    assert ok is False and anteil > 0.3
    # Ohne Gesamtzeile keine Aussage — dann gilt die Probe als nicht bestanden.
    assert finanzberichte.summenprobe(passend, [])[0] is False


def test_summenprobe_prueft_auch_das_ist():
    """Nur den Plan zu prüfen genügt nicht: Ein Fehlgriff, der zufällig
    denselben Ansatz trägt, käme sonst durch."""
    gesamt = _summenzeilen(80e6, 82e6, 100e6, 99e6)
    # Plan stimmt auf den Cent, das Ist eines Teilhaushalts ist Unsinn.
    plan_ok_ist_falsch = [{"posten": _summenzeilen(50e6, 51e6, 60e6, 59e6)},
                          {"posten": _summenzeilen(30e6, 31e6, 40e6, 5e6)}]
    ok, anteil = finanzberichte.summenprobe(plan_ok_ist_falsch, gesamt)
    assert ok is False and anteil > 0.3


def test_store_plan_ist(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    gesamt = finanzberichte.parse_ergebnisrechnung(JA_THH, 2023)
    store.save_ergebnisrechnung(2023, gesamt, "JA 2023", None)
    for t in finanzberichte.parse_teilergebnisrechnungen(JA_THH, 2023):
        store.save_ergebnisrechnung(2023, t["posten"], "JA 2023", None,
                                    thh_nr=t["thh_nr"], thh_name=t["thh_name"])

    assert store.plan_ist_jahre() == [2023]
    pi = store.get_plan_ist(2023)
    assert pi["gesamt"]["ertraege_plan"] == 664_574_528.42
    assert pi["gesamt"]["ertraege_ist"] == 732_987_197.61
    assert len(pi["bereiche"]) == 1
    # 2023 vergleicht gegen den nackten Ansatz — Plan und Ansatz fallen zusammen.
    assert pi["gesamt"]["ertraege_ansatz"] == 664_574_528.42
    assert pi["gesamt"]["plan_art"] == "ansatz"
    b = pi["bereiche"][0]
    assert b["thh_nr"] == 1 and b["thh_name"] == "Verwaltungsführung"
    assert b["ertraege_plan"] == 568_542.15 and b["ertraege_ist"] == 475_819.90
    # Gesamtzeile und Teilhaushalt liegen nebeneinander in derselben Tabelle.
    assert len(store.get_ergebnisrechnung(2023)) > len(gesamt)
    store.close()


# --- Die drei abweichenden Spaltenlayouts -----------------------------------
# 2017, 2018 und 2020 scheiterten früher nicht am Text, sondern an drei
# verschiedenen Spaltenanordnungen. Die Fixtures sind echte Ausschnitte aus
# den jeweiligen RIS-Anlagen, samt der Eigenheiten, die sie schwierig machen.

# 2017: Ergebnis steht VOR dem Ansatz, und die Summenzeilen heißen „12.= Summe".
JA_2017 = """3.1 Ergebnisrechnung der Kernverwaltung
Erträge und Aufwendungen Ergebnis 2016 Ergebnis 2017 Ansatz 2017 Differenz aus Spalte 5:
bisher nicht
bewilligte
über-/außer-
planmäßige
Aufwendungen
- Euro -
Ordentliche Erträge
01. Steuern und ähnliche Abgaben 230.255.777,11 239.004.300,84 231.033.600,00 7.970.700,84
12.= Summe ordentliche Erträge 494.694.676,98 539.271.147,21 509.437.536,75 29.833.610,46
Ordentliche Aufwendungen
20.= Summe ordentliche Aufwendungen 491.747.154,41 521.419.747,44 509.265.601,41 12.154.146,03
21. ordentliches Ergebnis 2.947.522,57 17.851.399,77 171.935,34 17.679.464,43
3.2 Gesamtergebnisrechnung
"""

# 2018: elf Spalten, sechs davon dürfen leer bleiben. Bezugsgröße der
# Abweichung ist die Gesamtermächtigung, nicht der Ansatz.
JA_2018 = """3.1 Ergebnisrechnung der Kernverwaltung
Erträge und Aufwendungen Ergebnis des
Vorjahres
2017
Ansätze des
Haushalts-
jahres 2018
Veränderung
durch
Nachtrag
2018
Sonstige
Ermächti-
gungen 2018
3)
Ermächti-
gungen des
Haushalts-
jahres 2018 4)
Ermächti-
gungen aus
Haushalts-
vorjahren
2018
Gesamter-
mächti-
gungen im
Haushaltsjahr
2018 5)
Ergebnis des
Haushalts-
jahres 2018
mehr (+) /
weniger (-)
2018
Zu Spalte 5:
Davon bisher
nicht
bewilligte
über- /
außerplan-
mäßige
Aufwen-
dungen 6)
 - Euro -
1 2 3 4 5 6 7 8 9 10 11
ordentliche Erträge
01. Steuern und ähnliche Abgaben 239.004.300,84 244.413.700,00  3.900.000,00 248.313.700,00  248.313.700,00 269.835.099,83 21.521.399,83
12. = Summe ordentliche Erträge 539.271.147,21 548.948.733,89  7.888.050,82 556.836.784,71  556.836.784,71 591.905.846,44 35.069.061,73
ordentliche Aufwendungen
20. = Summe ordentliche Aufwendungen 521.419.747,44 540.007.674,03  7.663.352,16 547.671.026,19 3.443.863,58 551.114.889,77 537.517.730,88 -13.597.158,89
21. ordentliches Ergebnis 17.851.399,77 8.941.059,86  224.698,66 9.165.758,52 -3.443.863,58 5.721.894,94 54.388.115,56 48.666.220,62
3.2 Gesamtergebnisrechnung
"""

# 2020: Nachtragshaushalt. Die Fußnote der Tabelle sagt die Regel selbst:
# „Spalte 6 = Spalte 5 − Summe (Spalte 3 + Spalte 4)". Posten 03 hat keinen
# Nachtrag und vergleicht deshalb in derselben Tabelle gegen den nackten Ansatz.
JA_2020 = """3.1 Ergebnisrechnung der Kernverwaltung
Erträge und Aufwendungen Ergebnis des
Vorjahres 2019
Ansätze des
Haushaltsjahres
2020
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2020
Ergebnis des
Haushaltsjahres
2020
mehr (+) /
weniger (-) 3)
2020
Ermächtigung
aus Haushalts-
vorjahren 2020
- Euro -
1 2 3 4 5 6 7 8
ordentliche Erträge
01. Steuern und ähnliche Abgaben 274.850.289,05 269.277.800,00 -27.974.100,00 257.975.691,73 16.671.991,73
03. Auflösungserträge aus Sonderposten 14.491.750,10 14.900.000,00  14.878.093,32 -21.906,68
12. = Summe ordentliche Erträge 591.872.634,00 588.539.108,34 2.731.100,00 632.156.295,42 40.886.087,08
ordentliche Aufwendungen
20. = Summe ordentliche Aufwendungen 570.400.593,06 582.261.479,18 27.208.150,00 587.980.452,10 -21.489.177,08
21. ordentliches Ergebnis 21.472.040,94 6.277.629,16 -24.477.050,00 44.175.843,32 62.375.264,16
3.2 Gesamtergebnisrechnung
"""


def test_ergebnisrechnung_2017_ergebnis_steht_vor_dem_ansatz():
    """2017 dreht die Reihenfolge um: Vorjahr, Ergebnis, Ansatz, Differenz.
    Eine feste Reihenfolgeannahme vertauschte hier Plan und Ist."""
    nach_nr = {p["nr"]: p for p in finanzberichte.parse_ergebnisrechnung(JA_2017, 2017)}
    assert nach_nr[1]["ansatz"] == 231_033_600.00        # geplant
    assert nach_nr[1]["ergebnis"] == 239_004_300.84      # tatsächlich
    assert nach_nr[1]["vorjahr"] == 230_255_777.11
    # Die Summenzeilen heißen „12.= Summe" ohne Leerzeichen vor dem Gleich.
    assert nach_nr[12]["ansatz"] == 509_437_536.75
    assert nach_nr[12]["ergebnis"] == 539_271_147.21
    assert nach_nr[20]["ansatz"] == 509_265_601.41
    # Ohne Nachtrag und ohne Ermächtigungsspalte ist der Plan der Ansatz.
    assert nach_nr[12]["plan"] == nach_nr[12]["ansatz"]
    assert nach_nr[12]["plan_art"] == "ansatz"


def test_ergebnisrechnung_2018_bezug_ist_die_gesamtermaechtigung():
    """2018 vergleicht das Ist nicht mit dem Ansatz, sondern mit der
    Gesamtermächtigung — 7,9 bzw. 11,1 Mio. € Unterschied. Beide Werte
    müssen erhalten bleiben, sonst ist die Mehrjahres-Kurve still falsch."""
    nach_nr = {p["nr"]: p for p in finanzberichte.parse_ergebnisrechnung(JA_2018, 2018)}
    ertraege, aufwendungen = nach_nr[12], nach_nr[20]
    assert ertraege["plan_art"] == "gesamtermaechtigung"
    assert ertraege["plan"] == 556_836_784.71          # Bezug der Abweichung
    assert ertraege["ansatz"] == 548_948_733.89        # ursprünglicher Ansatz
    assert ertraege["ergebnis"] == 591_905_846.44
    assert aufwendungen["plan"] == 551_114_889.77
    assert aufwendungen["ansatz"] == 540_007_674.03
    assert aufwendungen["ergebnis"] == 537_517_730.88
    # Die Abweichung bezieht sich auf den Plan, nicht auf den Ansatz.
    assert abs((aufwendungen["ergebnis"] - aufwendungen["plan"])
               - aufwendungen["abweichung"]) < 0.01


def test_ergebnisrechnung_2020_bezug_ist_ansatz_plus_nachtrag():
    """2020 ist der Jahrgang, an dem am meisten hängt: Der Corona-Nachtrag
    verschiebt die Aufwendungen um 27,2 Mio. €. Ob die Stadt „21,5 Mio.
    weniger ausgegeben als geplant" hat oder „5,7 Mio. mehr", entscheidet
    allein diese Wahl — beide Zahlen stehen in derselben Zeile."""
    nach_nr = {p["nr"]: p for p in finanzberichte.parse_ergebnisrechnung(JA_2020, 2020)}
    aufwendungen = nach_nr[20]
    assert aufwendungen["plan_art"] == "ansatz_nachtrag"
    assert aufwendungen["ansatz"] == 582_261_479.18                 # vor Nachtrag
    assert aufwendungen["plan"] == 609_469_629.18                   # + 27,2 Mio.
    assert aufwendungen["ergebnis"] == 587_980_452.10
    assert round(aufwendungen["plan"] - aufwendungen["ansatz"], 2) == 27_208_150.00
    # Gegen den Plan: 21,5 Mio. weniger. Gegen den Ansatz: 5,7 Mio. mehr.
    assert round(aufwendungen["abweichung"] / 1e6, 1) == -21.5
    assert round((aufwendungen["ergebnis"] - aufwendungen["ansatz"]) / 1e6, 1) == 5.7
    # Zeilen ohne Nachtrag vergleichen in derselben Tabelle gegen den Ansatz.
    assert nach_nr[3]["plan_art"] == "ansatz"
    assert nach_nr[3]["plan"] == nach_nr[3]["ansatz"] == 14_900_000.00


def test_strukturprobe_12_minus_20_ist_21():
    """Probe innerhalb der Tabelle, ohne jede zweite Quelle."""
    for text, jahr in ((JA_2017, 2017), (JA_2018, 2018), (JA_2020, 2020)):
        posten = finanzberichte.parse_ergebnisrechnung(text, jahr)
        ok, warum = finanzberichte.strukturprobe(posten)
        assert ok is True, f"{jahr}: {warum}"
    # Stimmt das ordentliche Ergebnis nicht, fällt der Jahrgang durch.
    posten = finanzberichte.parse_ergebnisrechnung(JA_2017, 2017)
    for p in posten:
        if p["nr"] == 21:
            p["ergebnis"] += 5000
    ok, warum = finanzberichte.strukturprobe(posten)
    assert ok is False and "12 − 20 − 21" in warum


def test_vorjahreskette_ueber_dokumentgrenzen():
    """Das Ist eines Jahres taucht im Folgejahrgang als Vorjahresspalte auf."""
    p2017 = finanzberichte.parse_ergebnisrechnung(JA_2017, 2017)
    p2018 = finanzberichte.parse_ergebnisrechnung(JA_2018, 2018)
    assert finanzberichte.vorjahreskette({2017: p2017, 2018: p2018}) == []
    # Ein einzelner Jahrgang ohne Nachbarn hat keine Kette — und reißt keine.
    assert finanzberichte.vorjahreskette({2017: p2017}) == []
    # Ein verfälschtes Ist bricht das Glied.
    verbogen = [dict(p) for p in p2017]
    for p in verbogen:
        if p["nr"] == 12:
            p["ergebnis"] = 1.0
    kaputt = finanzberichte.vorjahreskette({2017: verbogen, 2018: p2018})
    assert kaputt and kaputt[0][0] == 2017 and kaputt[0][1] == 2018


def test_thh_kopf_mit_zeilenumbruch():
    """Im Abschluss 2022 fällt bei THH09 ein Zeilenumbruch mitten in die
    Überschrift („A. Teil\\n-Ergebnisrechnung THH09"). Ohne den Umbruch im
    Muster fand der Parser nur die Fortsetzungsseite ohne Summenzeilen und
    verwarf über die Summenprobe die ganze Teilhaushalts-Ebene."""
    umbrochen = JA_THH.replace("A. Teil-Ergebnisrechnung   THH01",
                               "A. Teil\n-Ergebnisrechnung   THH01")
    thh = finanzberichte.parse_teilergebnisrechnungen(umbrochen, 2023)
    assert len(thh) == 1 and thh[0]["thh_nr"] == 1
    assert {p["nr"] for p in thh[0]["posten"]} >= {12, 20}


def test_vorzeichen_wird_nur_auf_den_cent_repariert():
    """Fehlt im Dokument ein Minuszeichen, darf der Parser es ergänzen — aber
    nur, wenn der Betrag exakt passt, und der Fall wird ausgewiesen."""
    ohne_minus = JA_2017.replace("509.265.601,41 12.154.146,03",
                                 "521.419.747,44 12.154.146,03")
    nach_nr = {p["nr"]: p for p in
               finanzberichte.parse_ergebnisrechnung(ohne_minus, 2017)}
    # Hier passt gar nichts mehr auf den Cent — die Zeile fällt raus.
    assert 20 not in nach_nr or not nach_nr[20].get("vorzeichen_repariert")


def test_vorzeichen_reparatur_faellt_nicht_auf_nullzeilen_herein():
    """Ohne Zusatzbedingung erfüllt jedes „X | 0,00 | X" die Vorzeichenprobe.
    Im Abschluss 2018 hätte das für THH11 ein Ist von 0,00 € eingetragen,
    richtig sind 105,0 Mio. €."""
    kopf = {"positionen": {"vorjahr": 0, "ansatz": 1, "ergebnis": 2, "abweichung": 3},
            "varianten": ("ansatz",), "hat_vorjahr": True}
    # Vorjahr, dann das tückische Tripel, dann die echte Spaltenfolge.
    zahlen = [102_428_787.88, 105_442_887.67, 0.0, 105_442_887.67,
              61_095.97, 105_503_983.64, 104_950_447.44, -553_536.20]
    werte = finanzberichte._spalten_zuordnen(zahlen, kopf)
    assert werte is not None
    assert werte["ergebnis"] == 104_950_447.44      # nicht 0,00
    assert werte["plan"] == 105_503_983.64
    assert werte["vorzeichen_repariert"] is False


# --- Das „Warum": Erläuterungen zu den Abweichungen -------------------------
# Echter Ausschnitt aus Abschnitt 6.3.1 des Jahresabschlusses 2024, samt
# Silbentrennung am Zeilenende und eingestreutem Seitenfuß („JA 161").

JA_WARUM = """6.3.1
Erläuterung der erheblichen Plan / Ist-Abweichungen in der Ergebnis-
rechnung

Als erheblich werden die Abweichungen betrachtet, die mindestens 20 % ge-
genüber dem Ansatz ausmachen.

JA 161

01. Steuern und ähnliche Abgaben (+75,1 Millionen Euro, +24,82 %)

Die in dieser Kontengruppe planüberschreitenden Mehrerträge entfallen na-
hezu auf den Bereich der Gewerbesteuer und resultieren unter anderem aus
einem Einmaleffekt.

04. sonstige Transfererträge (+2,1 Millionen Euro, +26,59 %)

Im Teilhaushalt 10 ergeben sich Mehrerträge von circa 415.000 Euro.

6.3.2
Erläuterung der erheblichen Plan / Ist-Abweichungen in der Finanzrech-
nung
Laufende Verwaltungstätigkeit
"""


def test_parse_abweichungsgruende():
    gruende = finanzberichte.parse_abweichungsgruende(JA_WARUM, 2024)
    nach_nr = {g["nr"]: g for g in gruende}
    assert set(nach_nr) == {1, 4}
    steuern = nach_nr[1]
    assert steuern["delta_mio"] == 75.1 and steuern["prozent"] == 24.82
    assert steuern["bezeichnung"] == "Steuern und ähnliche Abgaben"
    # Silbentrennung aufgelöst, Seitenfuß raus, Wortlaut unverändert.
    assert "nahezu auf den Bereich der Gewerbesteuer" in steuern["text"]
    assert "na- hezu" not in steuern["text"]
    assert "JA 161" not in steuern["text"]
    # Der Abschnitt zur FINANZrechnung trägt dieselbe Überschrift und darf
    # nicht mitgelesen werden.
    assert "Laufende Verwaltungstätigkeit" not in steuern["text"]


def test_abweichungsgruende_brauchen_die_rechenprobe():
    """Die Überschrift nennt die Abweichung doppelt — als Betrag und als
    Prozentsatz. Beides muss zur geparsten Tabellenzeile passen."""
    gruende = finanzberichte.parse_abweichungsgruende(JA_WARUM, 2024)
    passend = [{"nr": 1, "abweichung": 75_138_954.16, "plan": 302_740_000.00},
               {"nr": 4, "abweichung": 2_100_000.00, "plan": 7_898_000.00}]
    angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(gruende, passend)
    assert len(angenommen) == 2 and abgelehnt == []

    # Betrag passt nicht → raus.
    daneben = [{"nr": 1, "abweichung": 5_000_000.00, "plan": 302_740_000.00}]
    angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(gruende, daneben)
    assert angenommen == [] and len(abgelehnt) == 2

    # Betrag passt, Prozentsatz nicht → ebenfalls raus.
    schief = [{"nr": 1, "abweichung": 75_138_954.16, "plan": 1_000_000_000.00}]
    angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(gruende, schief)
    assert angenommen == [] and any("%" in a for a in abgelehnt)


def test_store_abweichungsgruende_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    gruende = finanzberichte.parse_abweichungsgruende(JA_WARUM, 2024)
    assert store.save_abweichungsgruende(2024, gruende, "JA 2024", "http://x") == 2
    assert store.save_abweichungsgruende(2024, gruende, "JA 2024", "http://x") == 2
    geladen = store.get_abweichungsgruende(2024)
    assert [g["nr"] for g in geladen] == [1, 4]
    assert geladen[0]["prozent"] == 24.82
    assert store.get_abweichungsgruende(1999) == []
    store.close()


# --- Schlussberichte des Rechnungsprüfungsamts ------------------------------

def test_pruefbericht_erkennung():
    """Die Labels taugen zur Auswahl nicht — „Schlussbericht JA 2017" ist der
    Bericht zum Eigenbetrieb. Erkannt wird an der Eingangsformel, und die ist
    im Volltext umbrochen: Ein LIKE darauf findet nichts."""
    echt = ("Schlussbericht des Rechnungsprüfungsamtes über die \n"
            "Prüfung des Jahresabschlusses 2021 der Stadt Oldenburg (Oldb)\n"
            "Rechnungsprüfungsamt " + "Text zur Prüfung. " * 50)
    treffer = finanzberichte.pruefbericht_aus_anlage("13 Schlussbericht RPA 2021", echt)
    assert treffer and treffer["jahr"] == 2021 and treffer["lesbar"] is True

    # Stiftungen und Eigenbetriebe tragen eine andere Formel.
    stiftung = ("Schlussbericht des Rechnungsprüfungsamtes über die Prüfung des "
                "Jahresabschlusses 2021 der Klävemann-Stiftung " + "Text. " * 50)
    assert finanzberichte.pruefbericht_aus_anlage("Klävemann 2021", stiftung) is None

    # 2024: Der Volltext ist Glyphen-Müll, das Dokument bleibt verlinkbar.
    kaputt = "□ □ /12 /8 /6 □ /13 /8 /2 /3 /14 /5 " * 40
    treffer = finanzberichte.pruefbericht_aus_anlage(
        "Schlussbericht des Rechnungsprüfungsamtes über die Prüfung des "
        "Jahresabschlusses 2024 der Stadt Oldenburg (Oldb)", kaputt)
    assert treffer and treffer["jahr"] == 2024 and treffer["lesbar"] is False


def test_store_pruefberichte_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_pruefbericht_quelle(2023, "Schlussbericht 2023", "http://x", 61, True)
    store.save_pruefbericht_quelle(2024, "Schlussbericht 2024", "http://y", 64, False)
    berichte = store.get_pruefbericht_quellen()
    assert [b["jahr"] for b in berichte] == [2023, 2024]
    assert berichte[0]["lesbar"] == 1 and berichte[1]["lesbar"] == 0
    store.close()
