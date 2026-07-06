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
    assert len(qs) >= 6
    est = [q for q in qs if q.get("qtype") == "estimate"]
    mc = [q for q in qs if q.get("qtype") != "estimate"]
    assert est and mc
    for q in est:
        # Antwort liegt in der Spanne, aber NICHT in der Mitte (Slider-Exploit).
        lo, hi, v = q["range_min"], q["range_max"], q["answer_value"]
        assert lo < v < hi
        assert abs((v - lo) / (hi - lo) - 0.5) > 0.08
        assert q["answer_unit"] == "Mio. Euro" and q["source_ref"] == "http://pdf"
        assert q["topic"] == "Haushalt" and q["area_key"] == "haushalt"
    # Gesamt-Aufwendungen: 883,9 Mio → 884.
    gesamt = next(q for q in est if "insgesamt" in q["question"])
    assert gesamt["answer_value"] == 884.0
    # MC „größter Ausgabenblock" zeigt auf Soziales und Gesundheit.
    top = next(q for q in mc if "am meisten" in q["question"])
    assert top["options"][top["correct_index"]] == "Soziales und Gesundheit"
    assert len(top["options"]) == 4 and len(set(top["options"])) == 4
    # Ertrags-MC → Finanzmanagement und Recht.
    ertrag = next(q for q in mc if "Erträge" in q["question"])
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
