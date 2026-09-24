"""Die Zahlen im Vorbericht (council/vorbericht_zahlen.py).

``fixtures/vorbericht_zahlen_seiten.json`` ist der Text echter Seiten der
Vorberichte 2026 (Dokument 297437) und 2021 (224264): Fehlbeträge,
Steuer-Diagramme, Personaltabelle. Die Leerseiten dazwischen fehlen; die
Seitennummer steht als Schlüssel.
"""
import json
from pathlib import Path


from council import vorbericht_zahlen as vz

FIX = json.loads((Path(__file__).parent / "fixtures" / "vorbericht_zahlen_seiten.json")
                 .read_text(encoding="utf-8"))


def _lesung(jahr: int) -> vz.Lesung:
    seiten = FIX[str(jahr)]["seiten"]
    # Seitennummern erhalten: fehlende Seiten als leer.
    alle = [""] * max(int(k) for k in seiten)
    for k, t in seiten.items():
        alle[int(k) - 1] = t
    return vz.lies(alle, jahr)


def _wert(l, reihe, jahr, art):
    return next(w.amount for w in l.werte if (w.series, w.year, w.variant) == (reihe, jahr, art))


def test_steuer_diagramm_mit_prognose_und_finanzplanung():
    l = _lesung(2026)
    assert _wert(l, "tax_trade", 2024, "actual") == 220_100_000
    assert _wert(l, "tax_trade", 2025, "prior_budget") == 169_000_000
    assert _wert(l, "tax_trade", 2025, "forecast") == 210_000_000
    assert _wert(l, "tax_trade", 2026, "budget") == 218_000_000
    assert _wert(l, "tax_trade", 2029, "financial_plan") == 190_000_000
    # Der Titel des Einkommensteuer-Diagramms läuft über zwei Zeilen.
    assert _wert(l, "tax_income", 2026, "budget") == 107_900_000


def test_fehlbetraege_nach_bildunterschrift():
    """„2019 – 2024 Ist, 2025 Prognose, 2026 – 2029 Plan": Die nackte 2025 ist
    die Prognose, nicht ein Ist."""
    l = _lesung(2026)
    assert _wert(l, "result", 2024, "actual") == 6_300_000
    assert _wert(l, "result", 2025, "forecast") == -64_100_000
    assert _wert(l, "result", 2026, "budget") == -89_300_000
    assert {w.variant for w in l.werte if w.series == "result" and w.year == 2025} == {"forecast"}


def test_personaltabelle_rechnet_sich_selbst():
    l = _lesung(2026)
    assert _wert(l, "personnel_active", 2026, "budget") == 209_443_325
    assert _wert(l, "personnel_provisions", 2026, "budget") == 16_940_200
    assert _wert(l, "personnel_active", 2024, "actual") == 184_779_048
    assert not [h for h in l.hinweise if h.startswith("Personal")]


def test_mehrere_zahlen_in_einer_zeile_2021():
    l = _lesung(2021)
    assert _wert(l, "personnel_active", 2022, "financial_plan") == 156_724_671
    assert _wert(l, "personnel_net", 2024, "financial_plan") == 152_727_262
    assert not [h for h in l.hinweise if h.startswith("Personal")]


def test_probe_gegen_den_ergebnishaushalt():
    l = _lesung(2026)
    plan = {(2026, 13): 209_443_324, (2026, 14): 6_900_000,
            (2026, 21): -92_200_345, (2026, 24): 2_909_050}
    assert vz.pruefe_gegen_plan(l, plan) == []
    plan[(2026, 13)] = 200_000_000
    assert any("personnel_active 2026" in f for f in vz.pruefe_gegen_plan(l, plan))


def test_verstellte_summe_faellt_auf():
    """Zwei Euro Rundung sind erlaubt, eine vertauschte Ziffer nicht."""
    werte = [vz.Wert("personnel_active", 2026, "budget", 1000, 1),
             vz.Wert("personnel_pension", 2026, "budget", 100, 1),
             vz.Wert("personnel_total", 2026, "budget", 1010, 1),
             vz.Wert("personnel_provisions", 2026, "budget", 10, 1),
             vz.Wert("personnel_net", 2026, "budget", 1000, 1)]
    assert vz.pruefe_personal(werte) == ["Personal 2026: aktiv + Versorgung ≠ Summe"]


def test_ungleichmaessige_achse_wird_verworfen():
    text = ("2024 Ist, ab 2025 Plan (Grafik 1)\n10,0\n11,0\n12,0\n5,0\n7,0\n20,0\n"
            "2024\n2025\n2026\nErträge aus der Gewerbesteuer in Millionen Euro\n")
    werte, hinweise = vz.lies_diagramme(text, 2025, 1)
    assert werte == [] and "Achse" in hinweise[0]


def test_speichern_und_endpunkt(tmp_path):
    import sys
    from dataclasses import asdict

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
    from app.routers.council import haushalt_vorbericht_zahlen
    from council import herkunft
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        for jahr in (2021, 2026):
            store.save_vorbericht_zahlen(jahr, [asdict(w) for w in _lesung(jahr).werte], herkunft.Herkunft(
                kind="ris", probe=[vz.PROBE], document_id=FIX[str(jahr)]["document_id"], label="Vorbericht"))
        assert "council_budget_preface_figures" not in store.herkunft_luecken()
        a = haushalt_vorbericht_zahlen(series=["tax_trade"], _user={}, store=store)
        assert [p["plan_budget_year"] for p in a["plans"]] == [2026, 2021]
        assert {f["series"] for p in a["plans"] for f in p["figures"]} == {"tax_trade"}
    finally:
        store.close()
