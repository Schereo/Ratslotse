"""Die Budgetberichte der Fachausschüsse (council/budgetberichte.py).

``fixtures/budgetberichte_seiten.json`` sind die Wortrahmen der Seiten mit
Teilfinanzrechnung aus vier echten Berichten (Dokumentnummer daneben), je
einer für die schwierigen Fälle: Erläuterung je Maßnahme und doppelte
Tabelle (26/0009), Einzahlungen mit Minus (20/0493), Kleinformat über
mehrere Seiten (21/0638), Maßnahme ohne Nummer und Kopf ohne „Bezeichnung"
(22/0177).
"""
import json
import sys
from pathlib import Path

import pytest

from council import budgetberichte as bb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

FIX = json.loads((Path(__file__).parent / "fixtures" / "budgetberichte_seiten.json")
                 .read_text(encoding="utf-8"))


def _lies(vorlage: str, as_of: str) -> bb.Bericht:
    f = FIX[vorlage]
    return bb.lies_seiten([[tuple(w) for w in s] for s in f["seiten"]], f["text"], as_of)


def test_erlaeuterung_je_massnahme_und_doppelte_tabelle():
    """26/0009 führt die Tabelle zweimal — gezählt wird sie einmal, und die
    Maßnahmen ergeben die Summenzeile."""
    b = _lies("26/0009", "2025-12-31")
    assert (b.sub_budget_no, b.form, b.budget_year) == (11, "nachrichtlich", 2025)
    assert b.pruefen(), b.hinweise
    assert len(b.massnahmen) == 8
    assert b.summe["A"] == (1_715_500, 2_985_368)
    dedestr = b.massnahmen[0]
    assert dedestr.nr == "I10.170066.525.008" and dedestr.name == "Inv.Zusch. Kita Dedestraße"
    assert (dedestr.planned, dedestr.forecast) == (0, 970_000)
    assert dedestr.note.startswith("Der Erweiterungsbau der Krippe ist fertiggestellt.")
    bereich = b.massnahmen[1]
    assert (bereich.nr, bereich.nr_bis) == ("I10.170073.525", "I10.170073.525.001")


def test_einzahlungen_mit_minus_zaehlen_als_betrag():
    """20/0493 druckt den Digitalpakt als „-2.655.000", die Summenzeile nicht."""
    b = _lies("20/0493", "2020-06-30")
    assert b.form == "verfuegbar" and b.sub_budget_no == 12
    assert b.pruefen(), b.hinweise
    digital = next(m for m in b.massnahmen if m.kind == "E" and "Digitalpakt" in m.name)
    assert digital.planned == 2_655_000
    assert all((m.planned or 0) >= 0 and (m.forecast or 0) >= 0 for m in b.massnahmen)


def test_kleinformat_ueber_mehrere_seiten():
    """21/0638: Kopf nur auf der ersten Seite, Zahlen ohne Tausenderpunkt und
    mit Dezimalpunkt („7711.2"), Summenzeile umbrochen („Auszahlungen für")."""
    b = _lies("21/0638", "2021-06-30")
    assert b.form == "kurz"
    assert b.pruefen(), b.hinweise
    assert len(b.massnahmen) == 16
    assert b.summe["A"] == (4_807_420, 6_409_364)
    land = next(m for m in b.massnahmen if m.nr == "I10.170321.555")
    assert land.forecast == 7711.2 and land.kind == "E"
    assert next(m for m in b.massnahmen if m.nr == "I10.060121.525").note.startswith("Hierbei handelt es sich")


def test_massnahme_ohne_nummer_und_kopf_ohne_bezeichnung():
    """22/0177: „kein Ansatz 2021" statt einer I10-Nummer, der Name steht über
    und unter der Betragszeile."""
    b = _lies("22/0177", "2021-12-31")
    assert b.pruefen(), b.hinweise
    ohne = [m for m in b.massnahmen if not m.nr]
    assert [m.name for m in ohne] == ["Zuschüsse Kita- Ausbau"]
    assert ohne[0].forecast == 2_600_000
    # Ein Tippfehler im Dokument (sieben Ziffern) bleibt, wie er dort steht.
    assert any(m.nr.startswith("I10.1702721") for m in b.massnahmen)


def test_gerundete_summenzeile_wird_vermerkt_nicht_verworfen():
    b = bb.Bericht(massnahmen=[bb.Massnahme("I10.1", None, "a", "A", 100_000, 1_219_506),
                                bb.Massnahme("I10.2", None, "b", "A", 0, 1_100_000)],
                   summe={"A": (100_000, 2_320_000)})
    assert b.pruefen() and b.gerundet == ["A forecast: Summenzeile 2.320.000 €, Maßnahmen 2.319.506 €"]
    b.summe["A"] = (100_000, 2_400_000)
    b.gerundet.clear()
    assert not b.pruefen()


def test_ohne_summenzeile_ungeprueft():
    b = bb.Bericht(massnahmen=[bb.Massnahme("I10.1", None, "a", "A", 1, 1)])
    assert not b.pruefen() and "keine Summenzeile für A" in b.hinweise


def test_stichtag_aus_titel_nicht_aus_dem_spaltenkopf():
    assert bb.stichtag("Finanz- und Leistungsbericht zum 30.06.2025", "…") == "2025-06-30"
    assert bb.stichtag("", "Budgetbericht THH 11 — 31.12.2019") == "2019-12-31"
    assert bb.stichtag("Anlage") is None


def test_ueberlappende_woerter_sind_zwei_zeilen():
    """23/0808: „2023" (Ende eines Namens) und der nächste Name liegen keine
    3 pt auseinander, stehen aber an derselben Stelle."""
    zeilen = bb._zeilen([(138, 580, 160, 588, "2023"), (138, 582, 180, 590, "Inv.Zusch."),
                         (190, 582, 200, 590, "A.")])
    assert [[w[4] for w in z] for z in zeilen] == [["2023"], ["Inv.Zusch.", "A."]]


def test_speichern_und_endpunkt(tmp_path):
    from dataclasses import asdict

    from council import herkunft
    from council.store import CouncilStore
    from app.routers.council import haushalt_budgetbericht

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        for vorlage, as_of in (("26/0009", "2025-12-31"), ("22/0177", "2021-12-31")):
            b = _lies(vorlage, as_of)
            assert b.pruefen()
            for _ in range(2):
                store.save_budgetbericht(
                    as_of, b.sub_budget_no, b.budget_year, [asdict(m) for m in b.massnahmen],
                    template_number=vorlage, herkunft=herkunft.Herkunft(
                        kind="ris", probe=[bb.PROBE_BUDGETBERICHT],
                        document_id=FIX[vorlage]["document_id"], label=vorlage))
        assert "council_budget_measures" not in store.herkunft_luecken()
        a = haushalt_budgetbericht(sub_budget=11, _user={}, store=store)
        assert [r["as_of"] for r in a["reports"]] == ["2025-12-31", "2021-12-31"]
        assert a["as_of"] == "2025-12-31" and len(a["measures"]) == 8
        assert a["reports"][0]["planned"] == pytest.approx(1_715_500)
        assert a["measures"][0]["note"].startswith("Der Erweiterungsbau")
        aelter = haushalt_budgetbericht(sub_budget=11, as_of="2021-12-31", _user={}, store=store)
        assert any(m["measure_no"] is None for m in aelter["measures"])
        assert haushalt_budgetbericht(sub_budget=4, _user={}, store=store)["measures"] == []
    finally:
        store.close()
