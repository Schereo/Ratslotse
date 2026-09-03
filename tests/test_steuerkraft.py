"""Die dritte Komponente des Finanzausgleichs (Blatt „9a" der KFA-Tabellen).

Die Fixtures sind **echte, gekürzte Ausschnitte** aus zwei geprüften
LSN-Dateien — KFA 2026 (``/download/227086``) und KFA 2023
(``/download/193990``): dieselben Zeilennummern, dieselben Spaltenköpfe,
dieselben Zahlen. Zwei Ausgaben, weil sich zwischen ihnen genau das ändert,
woran ein positionsbasierter Parser scheitert:

- Die **Schlüsselnummer** steht 2023 sechsstellig (``403000``), 2026
  dreistellig (``403``).
- Die Kopfzeile schreibt 2023 „Euro je Einwohner/Einwohnerin", 2026
  „Euro je Einwohnerin/Einwohner" — dieselbe Spalte, andere Reihenfolge.
- Der Kopftext des **Nettobetrags** enthält das Wort
  „Finanzausgleichsumlage". Wer die Komponenten zuerst matcht, hält die
  Netto-Spalte für die Umlage und meldet dann eine Datei ohne Nettobetrag.

Die Zahlen sind die echten: Oldenburg bekommt für das Ausgleichsjahr 2025
51.653 + 17.557 + 10.575 = 79.785 T€. Der Open-Data-Datensatz 1106 der Stadt
führt davon 69.210 T€ — die ersten beiden Summanden, auf den Euro.
"""
from __future__ import annotations

import pytest

from council import tax_capacity as sk
from council.store import CouncilStore
from tests.test_staedtevergleich import schreibe_xlsx

# Zeile 8 ist die Vorlesehilfe-Kopfzeile; die Datei sagt das in Zeile 3 selbst.
_HINWEIS = "Der Tabellenkopf für Vorlesehilfen befindet sich in Zeile 8"


def _kopf(prior_year: int, year: int, ew_schreibweise: str) -> list:
    def block(j: int) -> list:
        return [
            f"Schlüsselzuweisungen für Gemeindeaufgaben im Jahr {j}, Beträge in 1000 Euro",
            f"Schlüsselzuweisungen für Kreisaufgaben im Jahr {j}, Beträge in 1000 Euro",
            f"Zuweisungen für Aufgaben des übertragenen Wirkungskreises im Jahr {j}, "
            f"Beträge in 1000 Euro",
            f"Finanzausgleichsumlage im Jahr {j}, Beträge in 1000 Euro",
            f"Nettobetrag1) (Summe der Schlüssel- / Zuweisungen für Gemeinde-, Kreis- und "
            f"Aufgaben des übertragenen Wirkungskreises abzüglich der Finanzausgleichsumlage "
            f"im Jahr {j}), Beträge in 1000 Euro",
            f"Nettobetrag1) (Summe der Schlüssel- / Zuweisungen für Gemeinde-, Kreis- und "
            f"Aufgaben des übertragenen Wirkungskreises abzüglich der Finanzausgleichsumlage "
            f"im Jahr {j}), Beträge in {ew_schreibweise}2)",
        ]
    return (["Schlüsselnummer der Kreisfreien Stadt", "Bezeichnung der kreisfreien Stadt"]
            + block(prior_year) + block(year)
            + [f"Abweichung des Nettobetrags1) des Jahres {year} vom Nettobetrag1) des "
               f"Jahres {prior_year} in 1000 Euro"])


def _blatt(schluessel_lang: bool, ew_schreibweise: str) -> dict[int, list]:
    def key(n: str) -> float:
        return float(n + "000") if schluessel_lang else float(n)
    return {
        1: ["Kommunaler Finanzausgleich 2026", "Zeilenende"],
        2: ["Stand: 26.03.2026", "Zeilenende"],
        3: [_HINWEIS, "Zeilenende"],
        8: _kopf(2025, 2026, ew_schreibweise),
        # Oldenburg, echte Werte beider Jahrgänge.
        9: [key("403"), "Oldenburg (Oldb), Stadt",
            51653.0, 17557.0, 10575.0, 0.0, 79785.0, 452.27,
            62654.0, 19624.0, 11160.0, 0.0, 93438.0, 529.66, 13653.0],
        # Wolfsburg — die einzige Stadt mit einer Finanzausgleichsumlage
        # ungleich null. Ohne sie liefe die Probe an einem Sonderfall vorbei.
        10: [key("103"), "Wolfsburg, Stadt",
             0.0, 592.0, 7763.0, 7926.0, 428.0, 3.31,
             50366.0, 1000.0, 8000.0, 0.0, 59366.0, 459.0, 58938.0],
        # Eine Zwischenüberschrift ohne Schlüsselnummer, wie sie im Blatt
        # tatsächlich zwischen den Zeilen steht.
        11: [None, "Statistische Region Braunschweig"],
        12: [key("404"), "Osnabrück, Stadt",
             81969.0, 28780.0, 9927.0, 0.0, 120676.0, 728.16,
             95684.0, 30000.0, 10000.0, 0.0, 135684.0, 818.0, 15008.0],
    }


@pytest.fixture()
def kfa2026(tmp_path) -> str:
    """Die Ausgabe 2026: dreistellige Schlüsselnummer, „Einwohnerin/Einwohner"."""
    return schreibe_xlsx(tmp_path / "kfa2026.xlsx",
                         {"9a": _blatt(False, "Euro je Einwohnerin/Einwohner")})


@pytest.fixture()
def kfa2023(tmp_path) -> str:
    """Die Ausgabe 2023: sechsstellige Nummer, „Einwohner/Einwohnerin"."""
    return schreibe_xlsx(tmp_path / "kfa2023.xlsx",
                         {"9a": _blatt(True, "Euro je Einwohner/Einwohnerin")})


# --- Lesen ------------------------------------------------------------------

def test_beide_ausgleichsjahre_werden_gelesen(kfa2026):
    jahrgaenge = sk.lies_zuweisungen(kfa2026)
    assert [j.year for j in jahrgaenge] == [2025, 2026]
    assert all(j.as_of == "26.03.2026" for j in jahrgaenge)


def test_die_dritte_komponente_ist_die_luecke_im_open_data_datensatz(kfa2026):
    """Der Kern des Ganzen: 51.653 + 17.557 = 69.210 T€ steht im Datensatz
    1106 der Stadt. 10.575 T€ fehlen dort — und die stehen hier."""
    j2025 = sk.lies_zuweisungen(kfa2026)[0]
    ol = j2025.staedte["403000"]
    assert ol["zuweisungen_gemeindeaufgaben"] == 51653
    assert ol["zuweisungen_kreisaufgaben"] == 17557
    assert ol[sk.UEBERTRAGEN] == 10575
    assert ol["nettobetrag"] == 79785
    # Was der städtische Datensatz führt, ist exakt die Summe der ersten beiden.
    assert ol["zuweisungen_gemeindeaufgaben"] + ol["zuweisungen_kreisaufgaben"] == 69210


def test_nur_die_kreisfreien_staedte_und_keine_zwischenueberschrift(kfa2026):
    j = sk.lies_zuweisungen(kfa2026)[0]
    assert set(j.staedte) == {"403000", "103000", "404000"}


def test_die_ausgabe_2023_liest_sich_genauso(kfa2023):
    """Sechsstellige Schlüsselnummer, gedrehte Einwohner-Schreibweise — der
    Parser liest über den Kopftext, nicht über die Spaltennummer."""
    j2025, j2026 = sk.lies_zuweisungen(kfa2023)
    assert j2025.staedte["403000"][sk.UEBERTRAGEN] == 10575
    assert j2026.staedte["403000"]["nettobetrag"] == 93438


def test_nettobetrag_wird_nicht_fuer_die_umlage_gehalten(kfa2026):
    """Der Kopftext des Nettobetrags enthält das Wort
    „Finanzausgleichsumlage". Wolfsburg hat als einzige Stadt eine echte
    Umlage — verwechselt der Parser die Spalten, steht hier 7.926 statt 0."""
    ol = sk.lies_zuweisungen(kfa2026)[0].staedte["403000"]
    wob = sk.lies_zuweisungen(kfa2026)[0].staedte["103000"]
    assert ol["finanzausgleichsumlage"] == 0
    assert wob["finanzausgleichsumlage"] == 7926
    assert wob["nettobetrag"] == 428


def test_blatt_ohne_erwartete_spalten_bricht_ab(tmp_path):
    """Lieber abbrechen als über Spaltenpositionen raten."""
    pfad = schreibe_xlsx(tmp_path / "kaputt.xlsx", {"9a": {
        1: ["Kommunaler Finanzausgleich"], 3: [_HINWEIS],
        8: ["Schlüsselnummer der Kreisfreien Stadt", "Bezeichnung der kreisfreien Stadt",
            "Irgendwas ganz anderes im Jahr 2026"],
        9: [403.0, "Oldenburg (Oldb), Stadt", 1.0]}})
    with pytest.raises(ValueError, match="nicht die erwarteten Spalten"):
        sk.lies_zuweisungen(pfad)


# --- Proben -----------------------------------------------------------------

def test_komponentenprobe_geht_fuer_alle_staedte_auf(kfa2026):
    for budget_year in sk.lies_zuweisungen(kfa2026):
        probe = sk.probe_komponenten(budget_year)
        assert probe["ok"], probe["abweichungen"]
        assert probe["geprueft"] == 3
        assert "3 von 3 Städten" in probe["result"]


def test_komponentenprobe_faellt_auf_wenn_ein_teil_fehlt(kfa2026):
    budget_year = sk.lies_zuweisungen(kfa2026)[0]
    budget_year.staedte["403000"][sk.UEBERTRAGEN] = 0     # die Lücke, um die es geht
    probe = sk.probe_komponenten(budget_year)
    assert not probe["ok"]
    assert probe["abweichungen"][0]["key"] == "403000"
    assert "69210 statt 79785" in probe["abweichungen"][0]["reason"]


def test_rundung_auf_volle_tausend_reisst_die_probe_nicht(kfa2026):
    budget_year = sk.lies_zuweisungen(kfa2026)[0]
    budget_year.staedte["403000"]["nettobetrag"] = 79786   # 1 T€ Rundung
    assert sk.probe_komponenten(budget_year)["ok"]


def test_jahrbuchabgleich_geht_auf_und_nennt_beide_zahlen(kfa2026):
    """Die stärkere Probe: eine Landesbehörde gegen die Bücher der Stadt.
    Tabelle 1103 des Statistischen Jahrbuchs nennt für das Haushaltsjahr 2025
    unter „Finanzzuweisungen" 79.787 T€ (vorläufiges Rechnungsergebnis)."""
    budget_year = sk.lies_zuweisungen(kfa2026)[0]
    probe = sk.probe_gegen_jahrbuch(budget_year, 79787)
    assert probe["ok"]
    assert probe["lsn_teur"] == 79785 and probe["jahrbuch_teur"] == 79787
    assert probe["abweichung_prozent"] < 0.01


def test_jahrbuchabgleich_reisst_wenn_eine_komponente_fehlt(kfa2026):
    """Die Toleranz ist so gewählt, dass die kleinste Komponente (13 % der
    Summe) sie zwangsläufig reißt — sonst wäre sie keine Probe."""
    budget_year = sk.lies_zuweisungen(kfa2026)[0]
    budget_year.staedte["403000"]["nettobetrag"] = 69210   # ohne die dritte
    assert not sk.probe_gegen_jahrbuch(budget_year, 79787)["ok"]


# --- Speichern --------------------------------------------------------------

def test_zeilen_tragen_tausend_euro_und_keine_pro_kopf_spalte(kfa2026):
    zeilen = sk.zeilen_finanzausgleich(sk.lies_zuweisungen(kfa2026)[0])
    assert {z["unit"] for z in zeilen} == {"teur"}
    assert not [z for z in zeilen if z["indicator"] == "nettobetrag_je_ew"]
    ol = {z["indicator"]: z["value"] for z in zeilen if z["key"] == "403000"}
    assert ol == {"zuweisungen_gemeindeaufgaben": 51653.0,
                  "zuweisungen_kreisaufgaben": 17557.0,
                  "zuweisungen_uebertragener_wirkungskreis": 10575.0,
                  "finanzausgleichsumlage": 0.0, "nettobetrag": 79785.0}
    assert {z["city"] for z in zeilen if z["key"] == "403000"} == {"Oldenburg"}


def test_gespeichert_kommt_je_ausgleichsjahr_eine_zeile_zurueck(tmp_path, kfa2026):
    from council.herkunft import Herkunft

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        zeilen: list[dict] = []
        for budget_year in sk.lies_zuweisungen(kfa2026):
            zeilen += sk.zeilen_finanzausgleich(budget_year)
        store.save_staedtevergleich("fiscal_equalization", zeilen, Herkunft(
            kind="lsn", probe=["fiscal_equalisation_components", "fiscal_equalisation_yearbook_match"],
            label="KFA 2026", url="https://example.org/kfa.xlsx",
            probe_result="3 von 3 Städten"))

        series = store.get_finanzausgleich()
        assert [r["year"] for r in series] == [2025, 2026]
        assert series[0]["zuweisungen_uebertragener_wirkungskreis"] == 10575
        assert series[1]["nettobetrag"] == 93438
        # Und die Steuerkraft-Reihe bleibt davon unberührt.
        assert store.get_staedtevergleich("tax_capacity") == []
    finally:
        store.close()


def test_unbekannte_stadt_liefert_leere_reihe(tmp_path, kfa2026):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert store.get_finanzausgleich("999000") == []
    finally:
        store.close()


def test_die_proben_stehen_im_verzeichnis():
    """`council/herkunft.py` erzwingt, dass jede Probe dort erklärt ist —
    der Text landet im Beleg-Chip und beantwortet „warum soll ich das glauben?"."""
    from council.herkunft import PROBEN

    assert "fiscal_equalisation_components" in PROBEN
    assert "fiscal_equalisation_yearbook_match" in PROBEN
