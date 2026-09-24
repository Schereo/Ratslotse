"""Die Jahresabschlüsse der Gesellschaften (council/gesellschaft_abschluss.py).

Die Fixtures sind die Wortrahmen-Texte echter Anlagen: VWG 2025 (Bilanz
zweispaltig, vier Beträge in der Summenzeile; GuV), VWG 2023 (Querformat,
/Rotate 90), OTM 2025 (GuV mit Minus), Stadion KG 2024 (erstes Geschäftsjahr,
Vergleichsspalte ist die Eröffnungsbilanz) und 2025 (Fehlbetrag ohne Minus)."""
from __future__ import annotations

import json
from pathlib import Path

from council import gesellschaft_abschluss as ga
from council.store import CouncilStore

FX = json.loads((Path(__file__).parent / "fixtures" / "gesellschaft_abschluss_texte.json")
                .read_text())

VWG_2025 = "Verkehr und Wasser GmbH (VWG): Jahresabschluss 2025 - Beschluss"
VWG_2023 = "Verkehr und Wasser GmbH (VWG): Jahresabschluss 2023 - Beschluss"
OTM_2025 = "Oldenburg Tourismus und Marketing GmbH (OTM): Jahresabschluss 2025 - Beschluss"
STADION_2024 = "Stadion Oldenburg GmbH & Co. KG: Jahresabschluss 2024 - Beschluss"
STADION_2025 = "Stadion Oldenburg GmbH & Co. KG: Jahresabschluss 2025 - Beschluss"


def _werte(lesung):
    return {(k.year, k.metric): k.value for k in lesung.kennzahlen}


def test_titel_ordnet_gesellschaft_und_jahr_zu():
    assert ga.gesellschaft_aus_titel(VWG_2025) == ("vwg", 2025)
    # Die Komplementärin vor der KG, deren Name in ihrem steckt.
    assert ga.gesellschaft_aus_titel(
        "Weser-Ems Halle Oldenburg Beteiligungs-GmbH: Jahresabschluss 2025 - Beschluss"
    ) == ("weh_komplementaer", 2025)
    assert ga.gesellschaft_aus_titel(
        "Weser-Ems Halle Oldenburg GmbH & Co. KG Jahresabschluss 2018 - Beschluss") == ("weh", 2018)
    # Die Stadionplanungsgesellschaft ist die spätere Beteiligungs-GmbH.
    assert ga.gesellschaft_aus_titel(
        "Stadionplanungsgesellschaft mbH: Jahresabschluss 2023 - Beschluss"
    ) == ("stadion_komplementaer", 2023)
    assert ga.gesellschaft_aus_titel("Jahresabschluss 2025 der Klävemann-Stiftung") is None


def test_label_waehlt_bilanz_und_guv_und_laesst_den_lagebericht():
    assert ga.art_aus_label("Bilanz 2025 VWG") == "bilanz"
    assert ga.art_aus_label("3 GuV") == "guv"
    assert ga.art_aus_label("Gewinn- und Verlustrechung") == "guv"
    assert ga.art_aus_label("Bilanz, Gewinn- und Verlustrechnung, Lagebericht") == "beide"
    assert ga.art_aus_label("Lagebericht 2025 VWG") is None
    assert ga.art_aus_label("OTM JAP 24 (Lagebericht aus Prüfungsbericht)") is None


def test_bilanzsumme_aus_der_zweispaltigen_bilanz():
    """Die Summenzeile trägt vier Beträge (Aktiva GJ, VJ | Passiva GJ, VJ).
    Das Paar (Vorjahr, Geschäftsjahr) am Übergang steht nur einmal und darf
    nicht gewinnen, obwohl sein erster Betrag größer ist."""
    w = _werte(ga.lies_anlage(FX["vwg_bilanz_2025"], VWG_2025, "Bilanz 2025 VWG", 308012))
    assert w[(2025, "bilanzsumme")] == 66_836_379.55
    # = Beteiligungsbericht 2024
    assert w[(2024, "bilanzsumme")] == 68_966_726.15


def test_querformat_bilanz_wird_gelesen():
    """/Rotate 90: Ohne die Drehmatrix stünden die Zeilen senkrecht."""
    w = _werte(ga.lies_anlage(FX["vwg_bilanz_2023_quer"], VWG_2023, "Bilanz 2023", 276838))
    assert w[(2023, "bilanzsumme")] == 68_592_671.71
    assert w[(2022, "bilanzsumme")] == 70_790_577.50


def test_jahresergebnis_mit_und_ohne_minus():
    w = _werte(ga.lies_anlage(FX["vwg_guv_2025"], VWG_2025, "GuV 2025 VWG", 308013))
    assert w[(2025, "jahresergebnis")] == 0.0
    w = _werte(ga.lies_anlage(FX["otm_guv_2025"], OTM_2025, "3 GuV", 309164))
    assert w[(2025, "jahresergebnis")] == -1_187_942.65
    assert w[(2024, "jahresergebnis")] == -1_121_896.30
    # „6. Jahresfehlbetrag 781.488,67" — ohne Minus gedruckt, trotzdem Verlust.
    w = _werte(ga.lies_anlage(FX["stadion_guv_2025"], STADION_2025,
                              "Gewinn- und Verlustrechnung Stadion", 309473))
    assert w[(2025, "jahresergebnis")] == -781_488.67
    assert w[(2024, "jahresergebnis")] == -179_711.25


def test_erstes_geschaeftsjahr_hat_kein_vorjahr():
    """Stadion KG, gegründet 07.06.2024: Die zweite Spalte der Bilanz ist die
    Eröffnungsbilanz (5.000 €), die GuV hat nur eine Spalte — und die Zeile
    darunter („Belastung auf Kapitalkonten") ist kein Vorjahr."""
    w = _werte(ga.lies_anlage(FX["stadion_bilanz_2024"], STADION_2024, "Bilanz Stadion", 292521))
    assert w == {(2024, "bilanzsumme"): 133_251.97}
    w = _werte(ga.lies_anlage(FX["stadion_guv_2024"], STADION_2024, "GuV Stadion", 292522))
    assert w == {(2024, "jahresergebnis"): -179_711.25}


def _k(company, year, value, **x):
    return {"company": company, "indicator": "jahresergebnis", "year": year, "value": value,
            "unit": "eur", "report_year": 2024, "n_reports": 1, "herkunft_id": 1,
            "fetched_at": "x", **x}


def _a(company, year, value):
    return {"company": company, "indicator": "jahresergebnis", "year": year, "value": value,
            "report_year": year, "confirmations": 1, "herkunft_id": 9, "fetched_at": "y"}


def test_eine_reihe_aus_zwei_quellen():
    bericht = [_k("otm", 2024, -1_121_896.30)]
    abschluesse = [_a("otm", 2024, -1_121_896.30), _a("otm", 2025, -1_187_942.65),
                   _a("vhs", 2023, 98_765.95), _a("fremd", 2025, 1.0)]
    reihe = ga.reihe_ergaenzen(bericht, abschluesse, {"otm", "vhs"})
    by = {(r["company"], r["year"]): r for r in reihe}
    # Überlappung: der Bericht gilt, der Abschluss bezeugt.
    assert by[("otm", 2024)]["source"] == "holdings_report"
    assert by[("otm", 2024)]["n_reports"] == 2
    # Das neue Jahr kommt aus dem Abschluss, mit dessen Beleg.
    assert by[("otm", 2025)]["source"] == "annual_accounts"
    assert by[("otm", 2025)]["herkunft_id"] == 9
    # Eine Gesellschaft ohne Kennzahl im Bericht, aber mit Karte: ganz aus dem Abschluss.
    assert by[("vhs", 2023)]["source"] == "annual_accounts"
    # Ohne Karte keine Zeile.
    assert ("fremd", 2025) not in by


def test_bei_widerspruch_gilt_der_abschluss():
    """Tims Entscheidung 24.09.2026 — die Zahl des Berichts bleibt sichtbar."""
    reihe = ga.reihe_ergaenzen([_k("otm", 2024, -1_121_896.30)],
                               [_a("otm", 2024, -1_000_000.00)], {"otm"})
    assert reihe[0]["value"] == -1_000_000.00
    assert reihe[0]["source"] == "annual_accounts"
    assert reihe[0]["report_value"] == -1_121_896.30
    assert reihe[0]["herkunft_id"] == 9


def test_speichern_ersetzt_den_bestand(tmp_path):
    from council import herkunft as h
    store = CouncilStore(tmp_path / "c.sqlite")
    lauf = h.Herkunft(kind="ris", label="Lauf", probe=[ga.PROBE_BILANZ],
                      url="https://buergerinfo.oldenburg.de/vo040.asp")
    zeile = {"enterprise": "otm", "year": 2025, "metric": "jahresergebnis",
             "value": -1_187_942.65, "unit": "EUR", "report_year": 2025,
             "confirmations": 1, "conflicts": 0, "document_id": 309164,
             "probes": [ga.PROBE_GUV]}
    store.save_company_accounts([zeile, {**zeile, "year": 2024}], lauf)
    store.save_company_accounts([zeile], lauf)
    rows = store.get_company_accounts()
    assert [(r["company"], r["year"]) for r in rows] == [("otm", 2025)]
    assert rows[0]["probes"] == [ga.PROBE_GUV]
    assert store.company_account_einheiten() == {(2025, "otm")}
    store.close()
