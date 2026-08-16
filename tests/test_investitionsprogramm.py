"""Das Investitionsprogramm — die drei Proben und die drei Fallen.

Diese Schicht bringt die stärkste Quellenlage des Haushalts-Bereichs mit: Das
Dokument rechnet sich auf **drei** Ebenen selbst vor, und die mittlere davon
verbindet zwei Stellen, die rund siebzig Seiten auseinanderliegen. Geprüft wird
deshalb von beiden Seiten:

1. Gehen die drei Proben an echtem Text auf?
2. Wird ein Jahrgang, der eine davon reißt, wirklich **verworfen** statt
   halb gespeichert? Drei Wege hinein, einer je Probe.

Dazu die drei Fallen des Textextrakts. Alle drei sind beim Bauen wirklich
aufgetreten, jede hat einen Jahrgang oder einen Teilhaushalt gekostet, und jede
steht hier mit dem Ausschnitt, an dem sie aufgefallen ist:

* **Doppelzählung.** Jede Maßnahme steht zweimal da — als IPSP-Element und als
  Sachkonto-Detailzeile mit denselben Beträgen.
* **Umbrochene Namen.** Der Rest landet mal auf einer eigenen Zeile, mal vor
  den Beträgen derselben Zeile.
* **Ziffern im Namen.** Fachdienst- und Bebauungsplan-Nummern sehen wie
  Beträge aus; die erste Fassung las „FD 102" als 102 € und verlor 134.898 €.

``IP_2026`` ist **echter** Text aus Dokument 297440 (Haushalt 2026,
Anlage 004): das Gesamtinvestitionsprogramm wörtlich und vollständig, dazu der
Abschnitt THH04 wörtlich und vollständig — mitsamt dem Seitenumbruch in seiner
Mitte, der die Kopfzeilen ein zweites Mal bringt. Beides zusammen trägt alle
drei Proben (nachgemessen 17.08.2026).
"""
from __future__ import annotations

import pytest

from council import finanzquellen, herkunft
from council import investitionsprogramm as ip
from council.store import CouncilStore

# --- Echter Ausschnitt aus „2026 004 Vw Investitionsprogramm" ----------------

IP_2026 = """146
Gesamtinvestitionsprogramm
Investitionssummen je Teilhaushalt
Teilhaushalt
2 5431
- Euro -- Euro - - Euro - - Euro -- Euro - - Euro -
8
- Euro - - Euro -
976
- Euro -
10
Gesamt-
investitions-
summe
bisher
bereitgestellt
Ansatz 2026 Ansatz 2027 VE für 2027 Ansatz 2028 VE für 2028 Ansatz 2029 VE für 2029
Personal- u.
Verwaltungsmanagement 6.584.306 154.906 1.751.900 2.022.500 1.292.500 1.362.500
Wirtschaftsförderung,
Liegenschaften
92.398.800 53.057.600 14.977.500 4.950.400 9.146.000 10.398.200 2.000.000 9.015.100 2.000.000
Finanzmanagement und Recht -121.369.520 1.500.000 -38.563.190 -92.958.510 4.321.740 4.330.440
Sicherheit und Ordnung 14.892.100 2.305.000 2.043.000 3.425.900 1.580.000 2.827.400 4.290.800
Kultur, Museen, Sport 19.412.200 4.204.600 7.547.900 3.609.900 3.065.000 3.464.900 2.920.000 584.900
Stadtplanung 37.912.742 30.411.542 769.600 2.906.600 2.000.000 1.538.300 2.286.700
Verkehr und Straßenbau 74.514.290 17.423.090 11.177.700 18.985.500 6.568.000 16.225.500 5.050.000 10.702.500 2.100.000
Klima/Umwelt/Mobilität/Bau/Grün/Fri
edh.
29.989.300 6.649.600 6.963.000 7.171.200 2.865.000 4.893.500 4.312.000
Soziales und Gesundheit 1.982.400 836.400 509.000 579.000 545.000 29.000 29.000
Jugend und Familie 5.521.500 1.519.000 2.707.500 1.450.000 647.500 647.500
Schule und Bildung 8.302.800 1.875.700 2.275.700 200.000 2.075.700 2.075.700
Gesamtsumme 170.140.918 116.542.738 10.571.110 -44.324.310 27.419.000 47.714.240 9.970.000 39.637.140 4.100.000
THH04 Finanzmanagement und Recht
Investitionen und Investitionsförderungsmaßnahmen
Investitionsmaßnahme
2 5431
- Euro -- Euro - - Euro - - Euro -- Euro - - Euro -
8
- Euro - - Euro -
976
- Euro -
10
Gesamt-
investitions-
summe
bisher
bereitgestellt
Ansatz 2026 Ansatz 2027 VE für 2027 Ansatz 2028 VE für 2028 Ansatz 2029 VE für 2029
I10.090015.510 Medientechnik
Besprechungsräume 7.000 7.000
I10.090015 Medientechnik 7.000 7.000
I10.090126.525 Umlage nach dem
KHG, 2026
4.749.040 4.749.040
I10.090126 Umlage nach dem
KHG, 2026
4.749.040 4.749.040
I10.090127.525 Umlage nach dem
KHG, 2027
4.749.040 4.749.040
I10.090127 Umlage nach dem
KHG, 2027
4.749.040 4.749.040
I10.090128.525 Umlage nach dem
KHG, 2028
4.749.040 4.749.040
I10.090128 Umlage nach dem
KHG, 2028
4.749.040 4.749.040
I10.090129.525 Umlage nach dem
KHG, 2029
4.749.040 4.749.040
I10.090129 Umlage nach dem
KHG, 2029
4.749.040 4.749.040
I10.090526.565 Schuldendienst
Ausleihungen, 2026
-434.400 -434.400
I10.090526 Schuldendienst
Ausleihungen, 2026
-434.400 -434.400
I10.090527.565 Schuldendienst
Ausleihungen, 2027
-436.100 -436.100
I10.090527 Schuldendienst
Ausleihungen, 2027
-436.100 -436.100
I10.090528.565 Schuldendienst
Ausleihungen, 2028
-437.300 -437.300
I10.090528 Schuldendienst
Ausleihungen, 2028
-437.300 -437.300
I10.090529.565 Schuldendienst
Ausleihungen, 2029
-428.600 -428.600
I10.090529 Schuldendienst
Ausleihungen, 2029
-428.600 -428.600
158
THH04 Finanzmanagement und Recht
Investitionen und Investitionsförderungsmaßnahmen
Investitionsmaßnahme
2 5431
- Euro -- Euro - - Euro - - Euro -- Euro - - Euro -
8
- Euro - - Euro -
976
- Euro -
10
Gesamt-
investitions-
summe
bisher
bereitgestellt
Ansatz 2026 Ansatz 2027 VE für 2027 Ansatz 2028 VE für 2028 Ansatz 2029 VE für 2029
I10.091826.525 SAP Lizenz, 2026 13.000 13.000
I10.091826 SAP Lizenz, 2026 13.000 13.000
I10.091827.525 SAP Lizenz, 2027 10.000 10.000
I10.091827 SAP Lizenz, 2027 10.000 10.000
I10.091828.525 SAP Lizenz, 2028 10.000 10.000
I10.091828 SAP Lizenz, 2028 10.000 10.000
I10.091829.525 SAP Lizenz, 2029 10.000 10.000
I10.091829 SAP Lizenz, 2029 10.000 10.000
I10.093126.565 Tilgung -
Ausleihung Beteiligungen, 2026 -47.797.830 -47.797.830
I10.093126 Ausleihung an
Beteiligungen, 2026
-47.797.830 -47.797.830
I10.093127.565 Tilgung -
Ausleihung Beteiligungen, 2027
-105.881.450 -105.881.450
I10.093127 Ausleihung an
Beteiligungen, 2027
-105.881.450 -105.881.450
I10.093751.520 Eig.kap.
Zusch.Stadion Oldb GmbH & Co KG
15.000.000 1.500.000 4.900.000 8.600.000
I10.093751 Eigenkapitalzuschuss 15.000.000 1.500.000 4.900.000 8.600.000
Gesamtsumme -121.369.520 1.500.000 -38.563.190 -92.958.510 4.321.740 4.330.440
"""

#: Die Gesamtsumme, die das Dokument für THH04 ausweist.
THH04_SUMME = -121_369_520
#: Die Gesamtsumme des ganzen Investitionsprogramms 2026.
GESAMT_2026 = 170_140_918


@pytest.fixture()
def gelesen():
    return ip.lies(IP_2026, 2026)


# --- Die drei Proben gehen auf ----------------------------------------------

def test_alle_drei_proben_gehen_auf(gelesen):
    """Der echte Ausschnitt kommt vollständig durch."""
    assert gelesen["bestanden"] is True
    assert gelesen["kopfsumme"] == GESAMT_2026
    assert set(gelesen["abschnitte"]) == {4}
    assert gelesen["abschnitte"][4]["summe"] == THH04_SUMME


def test_massnahmen_ergeben_die_abschnittssumme(gelesen):
    """Probe 1, auf den Euro — nicht auf ein Prozent."""
    massnahmen = gelesen["abschnitte"][4]["massnahmen"]
    assert len(massnahmen) == 16
    assert sum(m["gesamtsumme"] for m in massnahmen) == THH04_SUMME


def test_abschnittssumme_steht_ein_zweites_mal_in_der_kopftabelle(gelesen):
    """Probe 2 — die stärkste: zwei Stellen, siebzig Seiten auseinander."""
    betraege = [z["gesamtsumme"] for z in gelesen["kopftabelle"]]
    assert THH04_SUMME in betraege
    ok, warum = ip.probe_wiederholung(gelesen["kopftabelle"],
                                      gelesen["abschnitte"])
    assert ok is True, warum


def test_kopftabelle_ergibt_ihre_gesamtsumme(gelesen):
    """Probe 3 — die elf Teilhaushalte ergeben 170.140.918 €."""
    assert len(gelesen["kopftabelle"]) == 11
    assert sum(z["gesamtsumme"] for z in gelesen["kopftabelle"]) == GESAMT_2026


def test_nachweis_nennt_zahlen_statt_behauptungen(gelesen):
    """Der Satz landet als ``probe_ergebnis`` im Beleg an der Zahl."""
    assert "16 Maßnahmen" in gelesen["nachweis"]
    assert "170.140.918,00" in gelesen["nachweis"]


# --- Falle 1: jede Maßnahme steht zweimal da --------------------------------

def test_detailzeilen_zaehlen_nicht_mit(gelesen):
    """Die ``.510``/``.525``-Zeilen tragen dieselben Beträge wie ihr
    Elternelement. Wer sie mitzählt, verdoppelt den Teilhaushalt."""
    codes = [m["code"] for m in gelesen["abschnitte"][4]["massnahmen"]]
    assert all(c.count(".") == 1 for c in codes), codes
    assert "I10.090126" in codes
    # Doppelt gezählt käme glatt das Doppelte heraus — der Test soll bei
    # einem Rückfall genau das zeigen.
    assert sum(m["gesamtsumme"] for m in gelesen["abschnitte"][4]["massnahmen"]) \
        != 2 * THH04_SUMME


def test_ein_elternelement_mit_mehreren_detailzeilen():
    """31 Elternelemente haben mehrere Detailzeilen; dann ist das Elternteil
    die Summe seiner Kinder und nur es darf gezählt werden."""
    text = """THH12 Schule und Bildung
I10.060126.525 Inv.Zusch. an EGH,
Inklusion, 2026 650.000 650.000
I10.060126.555 Inv.Zusch. vom
Land, Inklusion, 2026
-650.000 -650.000
I10.060126 Inklusion, Baukosten,
2026
0 0
Gesamtsumme 0 0
"""
    abschnitte = ip._lies_abschnitte(text.splitlines())
    massnahmen = abschnitte[12]["massnahmen"]
    assert [m["code"] for m in massnahmen] == ["I10.060126"]
    assert massnahmen[0]["gesamtsumme"] == 0


# --- Falle 2: umbrochene Namen ----------------------------------------------

def test_name_auf_eigener_zeile_vor_den_betraegen(gelesen):
    """„I10.090126 Umlage nach dem" / „KHG, 2026" / „4.749.040 4.749.040"."""
    m = next(m for m in gelesen["abschnitte"][4]["massnahmen"]
             if m["code"] == "I10.090126")
    assert m["bezeichnung"] == "Umlage nach dem KHG, 2026"
    assert m["gesamtsumme"] == 4_749_040


def test_jahr_teilt_sich_die_zeile_mit_den_betraegen():
    """„Erwerb Sportgeräte," / „2027 110.000 110.000" — das führende Jahr ist
    der Rest des Namens, nicht der Betrag. Diese Falle kostete THH06."""
    assert ip.betragslauf("2027 110.000 110.000") == ("2027", 110_000)


def test_bindestrich_am_umbruch_wird_nicht_zum_leerzeichen():
    """„IuK: IT-" + „Sicherheitsinfrastruktur" ist ein Wort, „Rad-" + „und
    Gehwege" sind zwei."""
    assert ip._namen_fuegen(["IuK: IT-", "Sicherheitsinfrastruktur, 2026"]) \
        == "IuK: IT-Sicherheitsinfrastruktur, 2026"
    assert ip._namen_fuegen(["Rad-", "und Gehwege"]) == "Rad- und Gehwege"


# --- Falle 3: Ziffern im Namen sind keine Beträge ---------------------------

def test_fachdienstnummer_im_namen_ist_kein_betrag():
    """Die Falle, die THH02 134.898 € gekostet hat: Die erste Fassung las die
    102 als Betrag, weil sie vom Zeilenanfang her nach der ersten Zahl suchte."""
    assert ip.betragslauf("Erwerb Software/Lizenzen, FD 102, 2026 135.000 135.000") \
        == ("Erwerb Software/Lizenzen, FD 102, 2026", 135_000)


def test_bebauungsplannummer_ist_kein_betrag():
    """„Kompensation, BPL 823" trägt keinen Betrag — die Zeile darf nicht als
    Betragszeile durchgehen, sonst endet der Name dort."""
    assert ip.betragslauf("Kompensation, BPL 823") is None


def test_betraege_unter_tausend_auf_eigener_zeile():
    """„6.100 4.000 700 700 700" — die 700 sind echte Beträge; die erste Zahl
    ist die Gesamtinvestitionssumme."""
    assert ip.betragslauf("6.100 4.000 700 700 700") == ("", 6_100)


@pytest.mark.parametrize("zeile", ["214", "2026", "2 5431"])
def test_seitenzahl_spaltenkopf_und_jahr_sind_keine_betragszeile(zeile):
    """Alle drei stehen im Dokument und sähen als Betrag plausibel aus."""
    assert ip.betragslauf(zeile) is None


# --- Was die Probe reißt, wird verworfen ------------------------------------

def test_verfaelschte_massnahme_kippt_den_jahrgang():
    """Probe 1 gerissen: eine Maßnahme um 1.000 € verändert."""
    kaputt = IP_2026.replace("I10.091826 SAP Lizenz, 2026 13.000 13.000",
                             "I10.091826 SAP Lizenz, 2026 14.000 14.000")
    g = ip.lies(kaputt, 2026)
    assert g["bestanden"] is False
    assert g["abschnitte"] == {}
    assert "THH04" in g["nachweis"]


def test_abschnittssumme_ohne_entsprechung_in_der_kopftabelle():
    """Probe 2 gerissen: Die Kopftabellen-Zeile für THH04 verschwindet."""
    kaputt = IP_2026.replace(
        "Finanzmanagement und Recht -121.369.520 1.500.000 -38.563.190 "
        "-92.958.510 4.321.740 4.330.440\n", "")
    g = ip.lies(kaputt, 2026)
    assert g["bestanden"] is False
    assert "Kopftabelle führt diesen Betrag nicht" in g["nachweis"]


def test_verfaelschte_kopfsumme_kippt_den_jahrgang():
    """Probe 3 gerissen: Die ausgewiesene Gesamtsumme stimmt nicht mehr."""
    kaputt = IP_2026.replace("Gesamtsumme 170.140.918",
                             "Gesamtsumme 170.140.900")
    g = ip.lies(kaputt, 2026)
    assert g["bestanden"] is False
    assert g["kopftabelle"] == []


def test_fremdes_dokument_wird_nicht_gelesen():
    """Ohne die Überschrift der Kopftabelle ist es ein anderes Dokument."""
    g = ip.lies("Stadt Oldenburg\nStellenplan\nTeil A\n", 2026)
    assert g["bestanden"] is False
    assert "Investitionssummen je Teilhaushalt" in g["nachweis"]


# --- Der Jahrgang kommt aus dem Text, nicht aus dem Label -------------------

def test_jahrgang_aus_der_ersten_ansatzspalte():
    """Vier der acht Anlagen heißen nur „004 Investitionsprogramm"."""
    assert ip.jahrgang(IP_2026) == 2026
    assert ip.jahrgang("Ansatz 2019 Ansatz 2020 VE für 2020") == 2019
    assert ip.jahrgang("kein Tabellenkopf") is None


# --- Speichern: drei Ebenen, eine Herkunft ---------------------------------

def test_speichern_legt_drei_ebenen_an(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        g = ip.lies(IP_2026, 2026)
        store.save_investitionsprogramm(2026, g, herkunft.Herkunft(
            art="ris", probe=["investitionsprogramm_abschnitt",
                              "investitionsprogramm_wiederholung",
                              "investitionsprogramm_kopftabelle"],
            dokument_id=297440, label="2026 004 Vw Investitionsprogramm",
            probe_ergebnis=g["nachweis"]))

        assert store.investitionsprogramm_jahre() == [2026]
        massnahmen = store.get_investitionsmassnahmen(jahr=2026, ebene="massnahme")
        assert len(massnahmen) == 16
        gesamt = store.get_investitionsmassnahmen(jahr=2026, ebene="gesamt")
        assert gesamt[0]["gesamtsumme"] == GESAMT_2026
        # Keine Zeile ohne Herkunft — sonst meldet sie `herkunft_luecken`.
        assert all(m["herkunft_id"] for m in massnahmen)
        assert not store.herkunft_luecken().get("council_investitionsmassnahmen")
    finally:
        store.close()


def test_zweiter_lauf_ersetzt_statt_zu_verdoppeln(tmp_path):
    """Idempotenz: Derselbe Jahrgang zweimal eingelesen bleibt derselbe."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        g = ip.lies(IP_2026, 2026)
        h = herkunft.Herkunft(art="ris", probe="investitionsprogramm_abschnitt",
                              dokument_id=297440)
        store.save_investitionsprogramm(2026, g, h)
        store.save_investitionsprogramm(2026, g, h)
        assert len(store.get_investitionsmassnahmen(jahr=2026,
                                                    ebene="massnahme")) == 16
    finally:
        store.close()


# --- Die Quelle ist angemeldet ---------------------------------------------

def test_quelle_steht_im_verzeichnis_und_in_der_reihenfolge():
    """Ohne beides fehlte die Schicht im Datenstand — und der Cron wüsste
    nicht, wann er sie erwarten soll."""
    q = finanzquellen.QUELLEN["investitionsprogramm"]
    assert q.tabelle == "council_investitionsmassnahmen"
    assert q.automatisch is True
    assert q.herkunft == "ris"
    # Anlage 004 kommt mit dem Haushaltsplan im Oktober des Vorjahres.
    assert (q.erwarteter_monat, q.versatz) == (10, -1)
    assert q.faellig_ab(2026).isoformat() == "2025-10-01"
    assert "investitionsprogramm" in finanzquellen.REIHENFOLGE
    # Direkt hinter den Investitionen: dieselbe Frage, eine Stufe feiner.
    r = finanzquellen.REIHENFOLGE
    assert r.index("investitionsprogramm") == r.index("investitionen") + 1


def test_alle_proben_sind_erklaert():
    """Ein Probenname ohne Satz für Leser*innen fliegt beim Bauen der Herkunft
    auf — hier fällt er schon vorher auf."""
    for name in ("investitionsprogramm_abschnitt",
                 "investitionsprogramm_wiederholung",
                 "investitionsprogramm_kopftabelle"):
        assert name in herkunft.PROBEN
        assert len(herkunft.PROBEN[name]) > 40
