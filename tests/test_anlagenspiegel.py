"""Anlagenspiegel aus dem Jahresabschluss (council/anlagenspiegel.py).

Die Fixtures sind gekürzte, aber **wörtliche** Auszüge der echten Abschlüsse
(Stand 18.08.2026); die Dokumentnummer steht jeweils dabei. Jede beweist eine
Falle, die beim Vermessen der acht Jahrgänge aufgefallen ist.

Der Aufbau folgt ``tests/test_buergschaften.py``.
"""
from council import anlagenspiegel as asp

# Dok 295294, Jahresabschluss 2024 — das Layout ab 2021 mit DREIZEHN
# Wertspalten (der Abschreibungs-Block hat eine Umbuchungs-Spalte).
KOPF_13 = """
Anlagen zum Anhang
JA 300
8.1 Anlagenübersicht
gem. § 57 Abs. 2 KomHKVO
Vermögen ¹)
- Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro -
  + - +/-     - - + +/-
1 2 3 4 5 6 7 8 9 10 11 12 13 14
"""

ZEILE_2024 = """1.   Immaterielles
Vermögensgegenst
ände 2)
126.898.598,25 13.478.238,51 -2.592.218,16 -23.379,70 137.761.238,90 -42.388.697,95 -6.523.027,43 2.541.325,16 3.333,00 0,00 -46.367.067,22 91.394.171,68 84.509.900,30
"""

# Dok 219464, Jahresabschluss 2019 — das ältere Layout mit ZWÖLF Spalten:
# im Abschreibungs-Block fehlt „Umbuchungen".
KOPF_12 = """
Anlagen zum Anhang
JA 284
8.1 Anlagenübersicht
Vermögen ¹)
- Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro - - Euro -
  + - +/-     - - +
1 2 3 4 5 6 7 8 9 10 11 12 13
"""

# Diese beiden Zeilen sind echt und gehören zusammen: 2019 wurden 396.635,53 €
# vom Infrastrukturvermögen zu den Bauten auf fremden Grundstücken umgebucht.
# Das Layout HAT keine Umbuchungs-Spalte — die Verschiebung steht nur als
# Differenz da, und zwar zweimal mit umgekehrtem Vorzeichen.
ZEILE_2019_INFRA = """2.   Sachvermögen
441.104.851,45 12.464.129,10 -1.020.365,74 4.342.127,21 456.890.742,02 -104.545.286,14 -14.930.116,10 1.020.365,74 0,00 -118.058.671,97 338.832.070,05 336.559.565,31
"""


def test_dreizehn_spalten_und_drei_ketten():
    g = asp.parse_anlagenspiegel(KOPF_13 + ZEILE_2024, 2024)
    assert len(g) == 1
    z = g[0]
    assert z["spalten"] == 13
    assert z["additions"] == 13_478_238.51
    assert z["depreciation"] == -6_523_027.43
    assert z["book_value"] == 91_394_171.68

    bestanden, risse = asp.probe(z)
    assert risse == []
    assert set(bestanden) == {asp.PROBE_AHK, asp.PROBE_ABSCHREIBUNG, asp.PROBE_BUCHWERT}


def test_umbrueche_im_label_werden_geheilt():
    """„Vermögensgegenst\\nände" darf nicht als „Vermögensgegenst änd" enden.

    Die PDF-Extraktion bricht mitten im Wort um. Ein Label mit Leerzeichen im
    Wortinneren sähe nach einem Fehler der Stadt aus und wäre einer von uns.
    """
    z = asp.parse_anlagenspiegel(KOPF_13 + ZEILE_2024, 2024)[0]
    assert z["label"] == "Immaterielles Vermögensgegenstände"
    assert "  " not in z["label"]


def test_zwoelf_spalten_werden_erkannt_und_gefuellt():
    """Bis 2020 fehlt die Umbuchungs-Spalte — erkannt, nicht geraten.

    Die Spaltenzahl steht im Dokument (Nummernzeile, ersatzweise die
    Euro-Marken). Wer dreizehn annimmt, verteilt zwölf Werte auf dreizehn
    Felder: Die Buchwerte rutschen um eine Spalte, und die Probe reißt an
    einer Stelle, die gar nicht schuld ist.
    """
    g = asp.parse_anlagenspiegel(KOPF_12 + ZEILE_2019_INFRA, 2019)
    assert len(g) == 1
    z = g[0]
    assert z["spalten"] == 12
    assert z["depreciation_transfers"] == 0.0    # gibt es in diesem Layout nicht
    assert z["book_value"] == 338_832_070.05   # NICHT um eine Spalte verschoben
    assert z["book_value_prior_year"] == 336_559_565.31

    bestanden, risse = asp.probe(z)
    # Die AHK-Kette und der Buchwert gehen auf; die Abschreibungskette wird
    # in diesem Layout gar nicht erst geprüft — sie KANN nicht schließen.
    assert asp.PROBE_AHK in bestanden and asp.PROBE_BUCHWERT in bestanden
    assert asp.PROBE_ABSCHREIBUNG not in bestanden
    assert risse == []


def test_die_spaltenzahl_kommt_auch_ohne_nummernzeile():
    """2017 druckt keine Spaltennummern — dann zählen die Euro-Marken.

    Zwei unabhängige Signale für dieselbe Angabe. Ohne das zweite fiele der
    älteste Jahrgang ersatzlos heraus.
    """
    ohne_nummern = KOPF_12.replace("1 2 3 4 5 6 7 8 9 10 11 12 13", "")
    assert asp.spaltenzahl(ohne_nummern) == 12
    assert asp.parse_anlagenspiegel(ohne_nummern + ZEILE_2019_INFRA, 2017)


def test_ein_drittes_layout_wird_nicht_zurechtgebogen():
    """Weder 12 noch 13 Spalten heißt: hinsehen, nicht raten."""
    fremd = KOPF_12.replace("1 2 3 4 5 6 7 8 9 10 11 12 13", "1 2 3 4 5")
    fremd = fremd.replace("- Euro - " * 5, "")
    assert asp.parse_anlagenspiegel(fremd + ZEILE_2019_INFRA, 2099) == []


def test_umbuchungen_muessen_sich_aufheben():
    """Die Probe für die Jahrgänge ohne Umbuchungs-Spalte.

    Was einer Vermögensart fehlt, muss einer anderen zugewachsen sein. Geht
    der Saldo auf, sind die Differenzen belegte Verschiebungen und keine
    Lücken — 2019 waren es 396.635,53 € zwischen zwei Positionen.
    """
    zeilen = [
        {"nr": "1", "depreciation_opening": -100.0, "depreciation": -10.0, "depreciation_releases": 0.0,
         "write_ups": 0.0, "depreciation_transfers": 0.0, "depreciation_closing": -60.0},
        {"nr": "2", "depreciation_opening": -200.0, "depreciation": -20.0, "depreciation_releases": 0.0,
         "write_ups": 0.0, "depreciation_transfers": 0.0, "depreciation_closing": -270.0},
        # Untergliederung — darf NICHT mitzählen, sonst wäre alles doppelt.
        {"nr": "2.1", "depreciation_opening": -50.0, "depreciation": -5.0, "depreciation_releases": 0.0,
         "write_ups": 0.0, "depreciation_transfers": 0.0, "depreciation_closing": -105.0},
    ]
    balance, risse = asp.umbuchungsprobe(zeilen)
    assert balance == 0.0 and risse == []

    zeilen[1]["depreciation_closing"] = -300.0            # jetzt fehlen 30
    balance, risse = asp.umbuchungsprobe(zeilen)
    assert abs(balance + 30.0) < 0.01 and len(risse) == 1


def test_die_bilanz_gegenprobe_kennt_nur_das_immaterielle_vermoegen():
    """Sachvermögen und Finanzvermögen zählen hier ANDERES als in der Bilanz.

    Die Fußnote der Tabelle sagt es selbst: ohne Vorräte, ohne geringwertige
    Vermögensgegenstände, ohne Forderungen. Ein Abgleich dieser beiden meldet
    verlässlich eine Differenz, die keine ist — beim ersten Versuch 184 Mio. €
    beim Finanzvermögen, und die Zahl war korrekt.
    """
    assert set(asp.BILANZ_ROLLE) == {"1"}

    zeilen = asp.parse_anlagenspiegel(KOPF_13 + ZEILE_2024, 2024)
    bilanz = [{"role": "immaterielles_vermoegen", "wert": 91_394_171.68},
              {"role": "finanzvermoegen", "wert": 645_348_451.45}]
    assert asp.gegen_bilanz(zeilen, bilanz) == []

    falsch = [{"role": "immaterielles_vermoegen", "wert": 91_000_000.0}]
    assert len(asp.gegen_bilanz(zeilen, falsch)) == 1


def test_die_strassenzeile_ueberlebt_den_zeilenumbruch():
    """„Verkehrslen-\\nkungsanlagen" — genau die Zeile, um die es geht.

    Ein Muster ohne Zeilenumbruch im Label überspringt sie und liefert die
    Nachbarzeilen; die Lücke fiele niemandem auf.
    """
    auszug = ("Gleisanlagen 237.306,42 € 214.883,42 € "
              "Straßen, Wege, Plätze, Verkehrslen-\nkungsanlagen "
              "142.874.798,00 € 133.281.788,00 € "
              "Strom-, Gas-, Wasserleitungen 107.417,00 € 102.412,00 €")
    gruppen = asp.parse_sachvermoegen_gruppen(auszug, 2024)
    strassen = [g for g in gruppen if "traße" in g["gruppe"]]
    assert len(strassen) == 1
    s = strassen[0]
    assert s["book_value_prior_year"] == 142_874_798.00
    assert s["book_value"] == 133_281_788.00
    # Die Reihenfolge ist Vorjahr, dann Jahr — gedreht würde aus dem
    # Substanzverlust ein Zuwachs.
    assert s["book_value"] < s["book_value_prior_year"]
    assert "kungsanlagen" not in s["gruppe"].replace("Verkehrslenkungsanlagen", "")
