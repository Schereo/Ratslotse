"""Die lange Ausgabenreihe (Datensatz 1102, 1972 bis heute).

Die Fixtures sind **echte, gekürzte Auszüge** der drei Quelldateien vom
17.08.2026 — derselbe Textextrakt, den pypdf aus dem Jahrbuch-PDF liefert, und
dieselben CSV-Zeilen, die das Open-Data-Portal ausliefert. Sie enthalten jede
Eigenheit, an der ein naiver Parser scheitert oder, schlimmer, still das
Falsche liest:

- **Die ältere CSV beschriftet ihre Beträge falsch** („Ausgaben insgesamt in
  Euro"), tatsächlich sind es Tausend Euro. Wer dem Kopf glaubt, zeigt für
  1972 statt 76,5 Mio. € einen Betrag von 76.493 € — und niemandem fällt es
  auf, weil die Zahl für sich plausibel aussieht.
- **Die Fußnotenziffer klebt im PDF-Titel an der Jahreszahl**
  (``2010 bis 20251``), dieselbe Falle wie bei Tabelle 1107.
- **Der Pro-Kopf-Wert von 2023 trägt ein ``r``** für „revidiert".
- **2021 widersprechen sich PDF und CSV** um 4,662 Mio. €.
- **Die Naht 2009/2010** trennt zwei Größen aus zwei Rechnungswesen.

Der Aufbau folgt ``tests/test_investitionen_ist.py``; der Unterschied ist die
Zahl der Proben. Dort trägt eine einzige Rechnung die Tabelle, hier sind es
drei gestaffelte — und welche ein Jahrgang bestanden hat, steht an seiner
Zeile. Genau das macht die 2021er-Ausnahme überhaupt auflösbar.
"""
from __future__ import annotations

import pytest

from council import expense_series as ar
from council import herkunft
from council.store import CouncilStore

# --- Fixtures ---------------------------------------------------------------

#: Textextrakt des echten PDFs (``1102-2025-AZ.pdf``), gekürzt auf die
#: Jahrgänge, die etwas beweisen: die Ränder beider Blöcke, das Jahr des
#: Widerspruchs (2021) und der revidierte Pro-Kopf-Wert (2023).
PDF = """Stadt Oldenburg (Oldb) - Statistik
1102  Ausgaben des Verwaltungshaushalts 2002 bis 2009
             - Anordnungssoll -
Einwohner
Stand: 31. Dezember total je Einwohner
des Vorjahres (Tausend Euro)  (Euro)
S 1 S 2 S 3 S 4
2002 155.908 338.725 2.173
2009 160.279 380.913 2.377
 Ordentliche Aufwendungen des Ergebnishaushalts 2010 bis 20251
   - Gesamtergebnisrechnung -
Einwohner
Stand: 31. Dezember total je Einwohner
des Vorjahres2,3 (Tausend Euro)  (Euro)
S 1 S 2 S 3 S 4
2010 161.334 358.800 2.224
2020 169.077 588.167 3.479
2021 169.605 608.910 3.590
2023 174.445 683.319      3.917r
2024 176.242 764.745 4.339
2025 176.614 850.170 4.814
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1  Einführung Neues Kommunales Rechnungswesen (NKR) zum 01. Januar 2010.
2  Ab 2012 revidierte amtliche Einwohnerzahl auf der Basis des Zensus 2011.
3  Ab 2023 revidierte amtliche Einwohnerzahl auf der Basis des Zensus 2022.
Ausgaben
Aufwendungen
Kapitel 11 - Verwaltung und Finanzen
Haushaltsjahr
Haushaltsjahr
Fachdienst Geo und Daten
"""

#: Die ältere CSV — mit ihrem falschen Spaltenkopf („in Euro").
CSV_KAMERAL = """Haushaltsjahr;EW am 31.12. des Vorjahres;Ausgaben insgesamt in Euro;Ausgaben je Einwohner in Euro
1972;133212;76493;574
2001;154832;315559;2038
2002;155908;338725;2173
2009;160279;380913;2377
"""

#: Die jüngere CSV — mit der falschen Zahl für 2021 (613.572 statt 608.910).
CSV_DOPPIK = """Haushaltsjahr;Einwohner am 31.12. des Vorjahres;Aufwendungen gesamt [T Euro];Aufwendungen je Einwohner [Euro]
2010;161334;358800;2224
2020;169077;588167;3479
2021;169605;613572;3611
2023;174445;683319;3917
2024;176242;764745;4339
2025;176614;850170;4814
"""

#: Posten 20 der Gesamtrechnung aus den Jahresabschlüssen — die
#: **Kernverwaltung ohne** die nicht rechtsfähigen Stiftungen. Echte Werte.
ABSCHLUESSE = {
    2020: 587_980_452.10,
    2021: 608_695_348.83,
    2023: 683_032_270.32,
    2024: 764_416_063.76,
}


@pytest.fixture()
def gelesen():
    return ar.lies(CSV_KAMERAL, CSV_DOPPIK, PDF, ABSCHLUESSE)


# --- Die beiden Blöcke erkennen ---------------------------------------------

def test_erkenne_findet_beide_bloecke():
    """Beide Titel, beide Spannen — der zweite trägt keine Tabellennummer."""
    assert ar.erkenne(PDF) == {"kameral": (2002, 2009), "doppik": (2010, 2025)}


def test_die_fussnotenziffer_im_titel_verschiebt_die_spanne_nicht():
    """``2010 bis 20251`` sind 2010 bis 2025 mit Fußnote 1 — nicht bis 20251."""
    assert "20251" in PDF, "die Fixture hat die Marke verloren"
    assert ar.erkenne(PDF)["doppik"][1] == 2025


def test_das_pdf_deckt_die_reihe_nicht_ab(gelesen):
    """Die Reihe beginnt 1972, das PDF erst 2002.

    Die dreißig ältesten Jahrgänge stehen NUR im Open-Data-Portal. Wer die
    Spanne des PDFs für die Spanne der Reihe hält, verliert sie — und merkt es
    nicht, weil das PDF in sich vollständig aussieht."""
    assert gelesen["spannen"]["kameral"][0] == 2002
    assert gelesen["zeilen"][0]["year"] == 1972
    nur_csv = [z for z in gelesen["zeilen"] if z["year"] < 2002]
    assert nur_csv and all(z["source"] == "csv" for z in nur_csv)


# --- Die Einheit ------------------------------------------------------------

def test_der_falsche_spaltenkopf_der_alten_csv_wird_nicht_geglaubt(gelesen):
    """„Ausgaben insgesamt in Euro" sind Tausend Euro — das entscheidet die Probe.

    Die stillste aller Fallen: Beide Lesarten liefern eine plausible Zahl, und
    nur die Pro-Kopf-Spalte derselben Zeile sagt, welche stimmt. 76.493 T€
    durch 133.212 Einwohner*innen sind 574 € — genau der Wert, den die Datei
    daneben ausweist. In Euro gelesen wären es 0,57 €."""
    assert "in Euro" in CSV_KAMERAL.splitlines()[0], "die Fixture ist geglättet"
    z = next(z for z in gelesen["zeilen"] if z["year"] == 1972)
    assert z["amount"] == 76_493_000


def test_eine_echte_euro_datei_faellt_komplett_durch():
    """Stellte die Stadt wirklich auf Euro um, käme nichts herein.

    Der Gegenbeweis zur festen Einheit: Sie ist keine Annahme, die im Dunkeln
    steht, sondern eine, die in jeder Zeile geprüft wird. Eine Datei mit
    echten Euro-Beträgen reißt die Pro-Kopf-Probe um den Faktor 1000 — und
    dann steht dort nichts statt des Tausendfachen."""
    euro = ("Haushaltsjahr;EW;Ausgaben insgesamt in Euro;je Einwohner\n"
            "1972;133212;76493000;574\n")
    result = ar.lies(euro, "", None, None)
    assert result["zeilen"] == []
    assert result["verworfen"][0]["year"] == 1972


def test_die_marke_revidiert_zerlegt_den_pro_kopf_wert_nicht():
    """``3.917r`` sind 3.917 mit der Marke „revidiert", nicht 39.171."""
    z = next(z for z in ar.parse_pdf(PDF) if z["year"] == 2023)
    assert z["per_capita"] == 3917
    assert z["revised"] is True


# --- Die Naht ---------------------------------------------------------------

def test_jede_zeile_traegt_ihr_regelwerk(gelesen):
    """Links der Naht kameral, rechts doppisch — an jeder einzelnen Zeile."""
    for z in gelesen["zeilen"]:
        erwartet = "kameral" if z["year"] < ar.NAHT_AB else "doppik"
        assert z["accounting_system"] == erwartet, z


def test_die_naht_liegt_zwischen_2009_und_2010(gelesen):
    """Das Umstellungsdatum steht in der Fußnote der Quelle: 01.01.2010."""
    assert ar.NAHT_AB == 2010
    years = [z["year"] for z in gelesen["zeilen"]]
    assert 2009 in years and 2010 in years
    assert next(z for z in gelesen["zeilen"] if z["year"] == 2009)["accounting_system"] \
        == "kameral"
    assert next(z for z in gelesen["zeilen"] if z["year"] == 2010)["accounting_system"] \
        == "doppik"


def test_die_beiden_regelwerke_haben_eigene_titel_und_abgrenzungen():
    """Zwei Namen, zwei Sätze — keine gemeinsame Beschriftung.

    Eine gemeinsame lüde dazu ein, die Reihe als eine Größe zu lesen. Die
    Quelle nennt sie verschieden, und beide Namen reisen deshalb bis in die
    Legende der Grafik durch."""
    assert set(ar.TITEL) == set(ar.ABGRENZUNG) == set(ar.REGELWERK) \
        == {"kameral", "doppik"}
    assert ar.TITEL["kameral"] != ar.TITEL["doppik"]
    assert ar.ABGRENZUNG["kameral"] != ar.ABGRENZUNG["doppik"]
    # Und die Abgrenzung sagt jeweils, was NICHT drin ist.
    assert "Investitionen" in ar.ABGRENZUNG["kameral"]
    assert "Investitionen" in ar.ABGRENZUNG["doppik"]


def test_eine_zeile_im_falschen_block_wird_nicht_umsortiert():
    """Ein Jahr ab 2010 in der kameralen Datei fällt heraus.

    Nicht „ins richtige Regelwerk schieben": Wenn die Stadt ihren Schnitt
    verschiebt, ist das eine Nachricht und keine Sortierfrage. Eine still
    umsortierte Zeile stünde unter der falschen Abgrenzung und wäre in sich
    trotzdem stimmig — die schlimmste Sorte Fehler."""
    falsch = ("Haushaltsjahr;EW;Betrag;je Einwohner\n"
              "2011;162173;371743;2292\n")
    result = ar.lies(falsch, "", None, None)
    assert result["zeilen"] == []
    reason = result["verworfen"][0]["reason"]
    assert "kameral" in reason and "doppik" in reason


def test_kein_lesepfad_rechnet_ueber_die_naht(gelesen):
    """Die Reihe liefert Jahreswerte, keine Summen oder Wachstumsraten.

    Der Test ist eine Zusicherung an die Oberfläche: Dieses Modul stellt
    nichts bereit, womit sich „von 1972 bis 2025 um X Prozent gestiegen"
    rechnen ließe — die Antwort verrät die Naht nicht, sie zeigt sie."""
    verboten = [n for n in dir(ar)
                if n.startswith(("summe", "wachstum", "change", "trend"))]
    assert not verboten, f"{verboten} lädt zur Rechnung über die Naht ein"
    assert set(gelesen) == {"zeilen", "verworfen", "konflikte", "spannen",
                            "fehlende_jahrgaenge", "probes"}


# --- Die Proben -------------------------------------------------------------

def test_ohne_bestandene_probe_kommt_kein_wert_herein(gelesen):
    """Die Grundregel: Jede Zeile im Bestand nennt ihre Proben."""
    for z in gelesen["zeilen"]:
        assert z["probes"], z
        for name in z["probes"]:
            assert name in herkunft.PROBEN, (
                f"{name} steht in keiner Erklärung — der Beleg auf der Seite "
                "bliebe leer")


def test_die_pro_kopf_probe_traegt_jede_zeile(gelesen):
    """Die einzige Probe, die alle 54 Jahrgänge haben — auch die ältesten."""
    for z in gelesen["zeilen"]:
        assert "ausgabenreihe_prokopf" in z["probes"], z


def test_eine_zeile_ohne_pro_kopf_wert_kommt_nicht_herein():
    """Fehlt die dritte Spalte, gibt es nichts zu prüfen — also nichts zu speichern."""
    ohne = ("Haushaltsjahr;EW;Betrag;je Einwohner\n"
            "1980;136155;142655;\n")
    assert ar.lies(ohne, "", None, None)["zeilen"] == []


def test_die_gegenprobe_erklaert_ihren_versatz(gelesen):
    """Statistik minus Ergebnisrechnung = die nicht rechtsfähigen Stiftungen.

    Der gemessene Versatz liegt in jedem Jahrgang zwischen 0,03 und 0,05 % und
    ist keine Unschärfe: Die Statistik zählt die Gesamtergebnisrechnung
    (Kernhaushalt UND Stiftungen), ``council_ergebnisrechnung`` nur die
    Kernverwaltung. Die Toleranz deckt genau das ab — und nichts, was danach
    kommt."""
    for year, kern in ABSCHLUESSE.items():
        z = next(z for z in gelesen["zeilen"] if z["year"] == year)
        anteil = (z["amount"] - kern) / kern
        assert 0 < anteil < 0.0005, f"{year}: {anteil:.5%}"
        assert "ausgabenreihe_jahresabschluss" in z["probes"]
    # Und der Erklärsatz benennt die Ursache statt sie offenzulassen.
    assert "Stiftungen" in herkunft.PROBEN["ausgabenreihe_jahresabschluss"]


def test_ein_jahrgang_gegen_seinen_abschluss_faellt_wenn_er_zu_weit_liegt():
    """Der Jahresabschluss gewinnt — er ist das geprüfte Dokument."""
    daneben = {**ABSCHLUESSE, 2024: 700_000_000.0}
    result = ar.lies(CSV_KAMERAL, CSV_DOPPIK, PDF, daneben)
    assert 2024 not in [z["year"] for z in result["zeilen"]]
    reason = next(v for v in result["verworfen"] if v["year"] == 2024)["reason"]
    assert "Ergebnisrechnung" in reason and "Stiftungen" in reason


def test_jahre_ohne_abschluss_tragen_die_probe_nicht(gelesen):
    """2025 hat noch keinen Jahresabschluss — und behauptet auch keinen.

    Der eigentliche Gewinn dieser Quelle: Die Gesamtsumme des abgelaufenen
    Jahres steht hier Monate vor dem Abschluss. Sie darf deshalb nicht so
    aussehen, als sei sie gegen ihn geprüft."""
    z = next(z for z in gelesen["zeilen"] if z["year"] == 2025)
    assert "ausgabenreihe_jahresabschluss" not in z["probes"]
    assert z["year"] > max(ABSCHLUESSE)


# --- Die Ausnahme 2021 ------------------------------------------------------

def test_2021_der_widerspruch_wird_festgehalten(gelesen):
    """Die eine Stelle, an der sich zwei amtliche Quellen widersprechen.

    Das CSV nennt 613.572 T€, das PDF 608.910 T€. Übernommen wird das PDF —
    seine Zeile geht in sich auf (608.910.000 ÷ 169.605 = 3.590,17 gegen
    ausgewiesene 3.590), die CSV-Zeile nicht (3.617,65 gegen 3.611). Der
    Jahresabschluss 2021 bestätigt das PDF.

    Der abweichende Wert wird NICHT weggeworfen: Er steht als
    ``conflict_amount`` an der Zeile, damit die Seite ihn nennen kann. Eine
    stille Korrektur sähe aus wie eine saubere Reihe und wäre eine Behauptung
    über eine amtliche Quelle."""
    z = next(z for z in gelesen["zeilen"] if z["year"] == 2021)
    assert z["amount"] == 608_910_000
    assert z["source"] == "pdf"
    assert z["conflict_amount"] == 613_572_000
    assert z["conflict_source"] == "csv"
    # Die Zweitquellenprobe hat für dieses Jahr NICHT bestanden und steht
    # deshalb auch nicht an der Zeile — der Beleg zeigt, was wirklich trug.
    assert z["probes"] == ["ausgabenreihe_prokopf", "ausgabenreihe_jahresabschluss"]


def test_der_widerspruch_steht_auch_als_eigener_befund(gelesen):
    """… und zwar mit gemessener Differenz, nicht als Adjektiv."""
    assert len(gelesen["konflikte"]) == 1
    k = gelesen["konflikte"][0]
    assert k["year"] == 2021
    assert k["difference"] == 4_662_000
    assert k["gewaehlt"] == "pdf" and k["verworfen"] == "csv"


def test_es_ist_der_einzige_widerspruch(gelesen):
    """23 der 24 gemeinsamen Jahre stimmen überein — genau eines nicht."""
    p = gelesen["probes"]
    assert p["zweitquelle_gerissen"] == 1
    assert p["zweitquelle_bestanden"] == len(
        [z for z in gelesen["zeilen"] if z["source"] == "pdf"]) - 1


def test_ohne_das_pdf_faellt_2021_ganz_heraus():
    """Kein PDF, keine zweite Meinung — dann kommt die falsche Zahl NICHT herein.

    Der wichtigste Rückfall dieser Schicht. Bliebe der CSV-Wert stehen, weil
    er die einzige verfügbare Angabe ist, stünde ein um 4,66 Mio. € falscher
    Betrag im Bestand. Er fällt stattdessen an seiner eigenen
    Pro-Kopf-Rechnung."""
    result = ar.lies(CSV_KAMERAL, CSV_DOPPIK, None, ABSCHLUESSE)
    assert 2021 not in [z["year"] for z in result["zeilen"]]
    assert [v["year"] for v in result["verworfen"]] == [2021]


def test_zwei_stimmige_quellen_mit_zwei_betraegen_entscheiden_nichts():
    """Wenn BEIDE ihre eigene Rechnung erfüllen und trotzdem abweichen,
    kommt nichts herein.

    Der Fall ist heute hypothetisch und die Regel trotzdem die richtige: An
    dieser Stelle gäbe es nichts, womit sich entscheiden ließe, welche der
    beiden amtlichen Angaben gilt — und „die neuere gewinnt" wäre geraten."""
    pdf = PDF.replace("2010 161.334 358.800 2.224", "2010 161.334 400.000 2.479")
    result = ar.lies(CSV_KAMERAL, CSV_DOPPIK, pdf, None)
    assert 2010 not in [z["year"] for z in result["zeilen"]]
    reason = next(v for v in result["verworfen"] if v["year"] == 2010)["reason"]
    assert "verschiedene Beträge" in reason


# --- Der Weg in den Bestand -------------------------------------------------

def test_der_probennachweis_nennt_zahlen(gelesen):
    """Der Messwert im Beleg zählt, er bewertet nicht."""
    text = ar.probennachweis(gelesen)
    assert "Pro-Kopf-Probe" in text
    assert str(gelesen["probes"]["prokopf_bestanden"]) in text
    for wort in ("gut", "zuverlässig", "korrekt", "sauber"):
        assert wort not in text.lower()


def test_speichern_und_lesen(tmp_path, gelesen):
    """Rundlauf durch den Store — inklusive Proben-Liste und Konflikt."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        n = store.save_ausgabenreihe(gelesen["zeilen"], herkunft.Herkunft(
            art="stadt", url=ar.TABELLE_URL, probe="ausgabenreihe_prokopf",
            label="Tabelle 1102", citation="Kapitel 11"))
        assert n == len(gelesen["zeilen"])
        zurueck = store.get_ausgabenreihe()
        assert [z["year"] for z in zurueck] == sorted(
            z["year"] for z in gelesen["zeilen"])
        # Die Proben kommen als LISTE zurück, nicht als Trennzeichen-String.
        z2021 = next(z for z in zurueck if z["year"] == 2021)
        assert z2021["probes"] == ["ausgabenreihe_prokopf",
                                   "ausgabenreihe_jahresabschluss"]
        assert z2021["conflict_amount"] == 613_572_000
        assert all(z["herkunft_id"] for z in zurueck)
        assert "council_ausgabenreihe" not in store.herkunft_luecken()
        assert store.ausgabenreihe_jahre()[0] == 1972
    finally:
        store.close()


def test_die_tabelle_fuehrt_keine_einwohnerzahl(tmp_path, gelesen):
    """Die Sperre gegen „Ausgaben pro Kopf seit 1972".

    Der Divisor liegt bewusst nicht im Bestand: Die Einwohnerreihe hat zwei
    Zensus-Brüche (2011 und 2022), an denen ein Pro-Kopf-Wert springt, ohne
    dass sich etwas verändert hätte. Was die API nicht liefern kann, kann das
    Frontend nicht versehentlich zeichnen — deshalb ist die fehlende Spalte
    eine Zusicherung und kein Versehen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_ausgabenreihe(gelesen["zeilen"][:1], herkunft.Herkunft(
            art="stadt", url=ar.TABELLE_URL, probe="ausgabenreihe_prokopf"))
        spalten = {r[1] for r in store._conn.execute(
            "PRAGMA table_info(council_ausgabenreihe)")}
        assert not spalten & {"einwohner", "per_capita", "pro_kopf"}
        assert not any(k in store.get_ausgabenreihe()[0]
                       for k in ("einwohner", "per_capita"))
    finally:
        store.close()


def test_die_tabelle_ist_als_herkunftstraeger_angemeldet():
    """Sonst bekäme sie keine ``herkunft_id`` und die Lücken-Meldung schwiege."""
    assert "council_ausgabenreihe" in herkunft.HERKUNFT_TABELLEN
