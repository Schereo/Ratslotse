"""Der Konzern Stadt Oldenburg aus dem konsolidierten Gesamtabschluss.

Alle Fixtures sind verkürzte, aber **wörtliche** Ausschnitte aus echten
pypdf-Extrakten der Prüfberichte in ``council_anlagen`` — jeder mit genau der
Eigenheit, an der ein naiver Parser scheitert:

- **2016** (``document_id`` 213675) trägt als Label schlicht „Anlage", und der
  Titel steht über fünf Zeilen. Ein ``LIKE 'Bericht über die Prüfung des
  konsolidierten Gesamtabschlusses zum 31.12.2016%'`` findet ihn nicht.
- **2024** (302709) hat ein Aktenzeichen-Deckblatt vor dem Titel.
- **2018** (232995) nummeriert die Ertragssumme als Posten 15, ab **2019**
  ist es Posten 13 — wer die Nummer liest, bekommt danach still etwas anderes.
- **2019** (241486) hat im ganzen Abschnitt **keine Zeilenumbrüche**; die
  nächste Postennummer klebt am Vorjahreswert.
- **2014** (198760) führt die Vorjahresspalte in **TEUR**, hat Unterposten
  (8.1, 8.2) und Leerzeichen mitten in Beträgen.
- **2018** weist in der Trägeraufstellung eine Konsolidierungszeile aus, die
  nicht zur eigenen Summe passt — der Bericht des Folgejahres führt dort
  −80.398 statt −80.462. Diese Aufstellung **muss** verworfen werden.
"""
from __future__ import annotations

import pytest

from council import herkunft, konzernabschluss as ka
from council.store import CouncilStore

#: Die Herkunft, die ein echter Lauf für den Jahrgang 2024 baut — Anker auf
#: die Anlage, Fundstelle im Dokument, die drei Proben der Ergebnisrechnung.
def _herkunft(fundstelle: str, proben: list[str], messwert: str = "") -> herkunft.Herkunft:
    return herkunft.Herkunft(
        art="ris", dokument_id=302709, label="Prüfbericht GA 2024",
        url="https://example.org/ga2024.pdf", fundstelle=fundstelle,
        probe=proben, probe_ergebnis=messwert or None,
        stand="Gesamtabschluss zum 31.12.2024")

# --- Fixtures: Dokumentköpfe ------------------------------------------------

KOPF_2016 = (
    'Bericht \nüber die Prüfung des \nkonsolidierten Gesamtabschlusses  \n'
    'zum 31.12.2016 der  \nStadt Oldenburg (Oldb)\n'
    'Stadt Oldenburg (Oldb) – Rechnungsprüfungsamt   \n'
    'Prüfung des konsolidierten Gesamtabschlusses 2016 Seite 1 \n'
)

KOPF_2024 = (
    'Aktenzeichen          Datum \n11.70.11-2025/015719        20.01.2026 \n'
    '  Telefon \n 2208 \n \n \n \n'
    'Bericht \n \nüber die Prüfung des \nkonsolidierten Gesamtabschlusses  \n'
    'zum 31.12.2024 der Stadt Oldenburg (Oldb) \n'
)

#: Der Schlussbericht des Rechnungsprüfungsamts fällt in denselben
#: SQL-Vorfilter (er erwähnt den Gesamtabschluss), ist aber ein anderes
#: Dokument — hier scheidet er aus.
KOPF_SCHLUSSBERICHT = (
    'Schlussbericht \ndes Rechnungsprüfungsamtes über die \n'
    'Prüfung des Jahresabschlusses 2023 \nder Stadt Oldenburg (Oldb) \n'
    'Der konsolidierten Gesamtabschlusses wird gesondert geprüft. \n'
)

# --- Fixtures: Gesamtergebnisrechnung ---------------------------------------

#: 2018 — alte Nummerierung (15/25/26/30), beide Spalten in Euro, umbrochene
#: Beschriftungen (Posten 2, 5, 11, 12, 22, 23).
GER_2018 = """3.2 Gesamtergebnisrechnung

Stadt Oldenburg
Gesamtergebnisrechnung für die Zeit vom 1. Januar bis 31. Dezember 2018
Ergebnis Ergebnis des
des Haushaltsjahres Vorjahres
€ €
1. Steuern und ähnliche Abgaben 269.835.099,83 239.004.300,84
2. Zuwendungen und allgemeine Umlagen, außer
für Investitionstätigkeit 150.649.316,24 119.910.445,97
10. Bestandsveränderungen - 510.903,43 271.016,98
15. Ordentliche Gesamterträge 927.894.462,76 864.627.427,83
16. Personalaufwendungen 314.461.219,25 310.638.717,07
20. Zinsen und ähnliche Aufwendungen 9.637.446,97 11.423.463,87
25. Ordentliche Gesamtaufwendungen 878.621.831,00 857.439.028,27
26. Ordentliches Gesamtergebnis 49.272.631,76 7.188.399,56
27. Außerordentliche Erträge 6.361.235,40 6.898.447,49
28. Außerordentliche Aufwendungen 890.294,36 2.015.454,52
29. Außerordentlichen Ergebnis 5.470.941,04 4.882.992,97
30. Gesamtjahresergebnis 54.743.572,80 12.071.392,53
"""

#: 2019 — die ganze Tabelle in EINER Zeile, neue Nummerierung (13/21/22/26).
GER_2019 = (
    '- 5 - \n3.2 Gesamtergebnisrechnung \n \n  \n'
    'Stadt OldenburgGesamtergebnisrechnung für die Zeit vom 1. Januar bis '
    '31. Dezember 2019Ergebnis Ergebnis desdes Haushaltsjahres Vorjahres€ €'
    '1. Steuern und ähnliche Abgaben 274.850.289,05 269.835.099,83'
    '2. Zuwendungen und allgemeine Umlagen, außer für Investitionstätigkeit '
    '137.031.192,72 150.649.316,24'
    '10. Bestandsveränderungen 91.324,19 - 510.903,43'
    '13. Ordentliche Gesamterträge 932.052.457,60 927.894.462,76'
    '14. Personalaufwendungen 330.970.648,89 314.461.219,25'
    '18. Zinsen und ähnliche Aufwendungen 10.130.631,71 9.637.446,97'
    '21. Ordentliche Gesamtaufwendungen 922.350.191,52 878.621.831,00'
    '22. Ordentliches Gesamtergebnis 9.702.266,08 49.272.631,76'
    '23. Außerordentliche Erträge 11.496.311,69 6.361.235,40'
    '24. Außerordentliche Aufwendungen 2.596.997,37 890.294,36'
    '25. Außerordentlichen Ergebnis 8.899.314,32 5.470.941,04'
    '26. Gesamtjahresergebnis 18.601.580,40 54.743.572,80\n'
    ' \n- 6 - \n3.3 Anlagenübersicht \n \n'
    'Euro Euro Euro Euro+ - +/- +1 2 3 41.   Immaterielles Vermögen'
    '1.1 Konzessionen5.416,360,000,000,005.416,36\n'
)

#: 2014 — Vorjahresspalte in TEUR, Unterposten 20.1/20.2 mit der Summe auf
#: einer eigenen Zeile, Leerzeichen mitten in Beträgen (Posten 2 und 16).
GER_2014 = """5.2  Gesamtergebnisrechnung für 2014

  2014 2014 2013
  EUR EUR TEUR
1. Steuern und ähnliche Abgaben  205.903.460,52  183.330
2. Zuwendungen und allgemeine Umlagen  105.667.339, 23  98.266
15. ordentliche Gesamterträge  760.810.621,37  711.430
16. Aufwendungen für aktives Personal  268.436.724, 73  249.616
20. Zinsen und sonstige Finanzaufwendungen
20.1. Zinsaufwendungen 11.209.002,22   11.373
20.2. sonstige Finanzaufwendungen 921.837,75   1.023
   12.130.839,97  12.396
25. ordentliche Gesamtaufwendungen  736.162.472,00  696.490
26. ordentliches Gesamtergebnis  24.648.149,37  14.940
27. außerordentliche Erträge  2.024.722,56  2.106
28. außerordentliche Aufwendungen  1.560.395,87  3.344
29. außerordentliches Ergebnis  464.326,69  -1.238
30. Gesamtjahresüberschuss  25.112.476,06  13.700
"""

#: Dasselbe wie GER_2018, aber die Ertragssumme ist um 100.000 € verfälscht —
#: so, wie ein zerschossener Extrakt sie liefern könnte. Die erste Probe reißt.
GER_KAPUTT = GER_2018.replace("927.894.462,76 864.627.427,83",
                              "927.994.462,76 864.627.427,83")

# --- Fixtures: Trägeraufstellung --------------------------------------------

TRAEGER_2024 = (
    'Die ordentlichen Gesamterträge entwickelten sich wie folgt: \n \n'
    ' 2024 2023 Veränderung \n TEUR TEUR TEUR \n'
    'Stadt Oldenburg 799.057 732.987 66.070 \n'
    'Klinikum Oldenburg AöR -Teilkonzern- 368.100 336.858 31.242 \n'
    'Weser-Ems Halle Oldenburg GmbH & Co. KG 6.383 6.170 213 \n'
    'Verkehr und Wasser GmbH 55.783 52.452 3.331 \n'
    'Abfallwirtschaftsbetrieb der Stadt Oldenburg 24.496 22.434 2.062 \n'
    'Bäderbetrieb der Stadt Oldenburg 8.253 7.709 544 \n'
    'Bäderbetriebsgesellschaft Oldenburg mbH 8.093 6.303 1.790 \n'
    'Eigenbetrieb Gebäudewirtschaft und Hochbau 69.889 68.831 1.058 \n'
    'Konsolidierung -98.506 -94.368 -4.138 \n'
    ' 1.241.548 1.139.376 102.172 \n \n'
)

#: 2018, Aufwendungsseite: Die Träger ergeben mit der ausgewiesenen
#: Konsolidierung 878.558, die Summenzeile nennt 878.622 — 64 TEUR
#: Unterschied. Der Bericht 2019 führt für 2018 −80.398 statt −80.462.
TRAEGER_2018_AUFW = (
    'Die ordentlichen Gesamtaufwendungen entwickelten sich wie folgt: \n \n'
    ' 2018 2017 Veränderung \n T€ T€ T€ \n'
    'Stadt Oldenburg 537.518 521.420 + 16.098 \n'
    'Klinikum Oldenburg AöR -Teilkonzern- 280.043 276.552 + 3.491 \n'
    'Weser-Ems Halle Oldenburg GmbH & Co. KG 9.571 9.538 + 33 \n'
    'Verkehr und Wasser GmbH 42.236 38.678 + 3.558 \n'
    'Abfallwirtschaftsbetrieb der Stadt Oldenburg 19.044 20.314  - 1.271 \n'
    'Bäderbetrieb der Stadt Oldenburg 4.267 6.729  - 2.463 \n'
    'Bäderbetriebsgesellschaft Oldenburg mbH 7.971 7.652 + 319 \n'
    'Eigenbetrieb Gebäudewirtschaft und Hochbau 58.370 59.263  - 892 \n'
    'Konsolidierung  - 80.462  - 82.708 + 2.246 \n \n'
    '878.622 857.439 + 21.183 \n \n'
)


def _rollen(ergebnis: dict) -> dict[str, float]:
    return {p["rolle"]: p["betrag"] for p in ergebnis["posten"] if p["rolle"]}


# --- Erkennung --------------------------------------------------------------

def test_jahrgang_aus_umbrochenem_titel():
    """Der Titel steht über fünf Zeilen — das Label sagt nur „Anlage"."""
    assert ka.jahrgang(KOPF_2016) == 2016


def test_jahrgang_hinter_aktenzeichen_deckblatt():
    assert ka.jahrgang(KOPF_2024) == 2024


def test_schlussbericht_ist_kein_gesamtabschluss():
    """Er erwähnt den Gesamtabschluss und fällt in denselben Vorfilter —
    trotzdem darf er hier nicht als Jahrgang durchgehen."""
    assert ka.jahrgang(KOPF_SCHLUSSBERICHT) is None
    assert ka.jahrgang("") is None
    assert ka.jahrgang(None) is None


# --- Gesamtergebnisrechnung -------------------------------------------------

def test_alte_nummerierung_wird_an_der_beschriftung_erkannt():
    """2018: Posten 15 ist die Ertragssumme, nicht Posten 13."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2018)
    assert ergebnis["bestanden"]
    rollen = _rollen(ergebnis)
    assert rollen["ertraege_summe"] == 927894462.76
    assert rollen["aufwendungen_summe"] == 878621831.00
    assert rollen["ord_ergebnis"] == 49272631.76
    assert rollen["gesamtergebnis"] == 54743572.80
    assert rollen["zinsaufwand"] == 9637446.97
    # Die Nummer wandert mit dem Jahrgang, die Rolle nicht.
    nummern = {p["rolle"]: p["nr"] for p in ergebnis["posten"] if p["rolle"]}
    assert nummern["ertraege_summe"] == 15


def test_neue_nummerierung_liefert_dieselben_rollen():
    """2019 zählt anders (13/21/22) — die Rollen heißen weiter gleich."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2019)
    assert ergebnis["bestanden"]
    rollen = _rollen(ergebnis)
    assert rollen["ertraege_summe"] == 932052457.60
    assert rollen["aufwendungen_summe"] == 922350191.52
    assert rollen["gesamtergebnis"] == 18601580.40
    nummern = {p["rolle"]: p["nr"] for p in ergebnis["posten"] if p["rolle"]}
    assert nummern["ertraege_summe"] == 13


def test_zeilenumbrueche_werden_wiederhergestellt():
    """2019 hat gar keine Umbrüche — trotzdem müssen alle Posten da sein,
    inklusive des negativen Werts mit Leerzeichen hinterm Minus."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2019)
    posten = {p["nr"]: p for p in ergebnis["posten"]}
    assert posten[1]["betrag"] == 274850289.05
    assert posten[1]["vorjahr"] == 269835099.83
    assert posten[10]["betrag"] == 91324.19
    assert posten[10]["vorjahr"] == -510903.43
    assert posten[2]["bezeichnung"].startswith("Zuwendungen und allgemeine Umlagen")


def test_entzerren_laesst_saubere_jahrgaenge_unveraendert():
    assert ka.entzerren(GER_2018) == GER_2018


def test_anlagenuebersicht_wird_nicht_mitgelesen():
    """Direkt hinter der Tabelle folgt die Anlagenübersicht, die ebenfalls
    mit „1." beginnt. Nach dem Gesamtjahresergebnis ist Schluss."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2019)
    assert ergebnis["posten"][-1]["rolle"] == "gesamtergebnis"
    assert not any("Konzessionen" in p["bezeichnung"] for p in ergebnis["posten"])


def test_vorjahresspalte_in_tausend_wird_umgerechnet():
    """2014: Kopf ``EUR EUR TEUR`` — die Vorjahreszahlen stehen in Tausend."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2014)
    assert ergebnis["bestanden"]
    posten = {p["nr"]: p for p in ergebnis["posten"]}
    assert posten[1]["betrag"] == 205903460.52
    assert posten[1]["vorjahr"] == 183330000.0
    assert posten[15]["vorjahr"] == 711430000.0


def test_unterposten_reissen_die_summe_nicht_an_sich():
    """2014 führt Posten 20 als Unterposten 20.1/20.2, die Summe steht auf
    einer eigenen Zeile ohne Nummer. Sie dem offenen Posten zuzuschlagen
    ergäbe 11,2 statt 12,1 Mio. Zinsaufwand — lieber gar kein Wert."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2014)
    rollen = _rollen(ergebnis)
    assert "zinsaufwand" not in rollen
    assert not any(p["betrag"] == 11209002.22 for p in ergebnis["posten"])


def test_betrag_mit_leerzeichen_wird_verworfen():
    """„105.667.339, 23" ist kein lesbarer Betrag — die Zeile fällt weg,
    statt eine geratene Zahl zu liefern."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_2014)
    nummern = {p["nr"] for p in ergebnis["posten"]}
    assert 2 not in nummern
    assert 16 not in nummern
    assert 15 in nummern  # der saubere Nachbar bleibt


def test_gerissene_probe_verwirft_den_jahrgang():
    """Die zentrale Regel: Was die Rechenprobe reißt, kommt nicht durch."""
    ergebnis = ka.parse_gesamtergebnisrechnung(GER_KAPUTT)
    assert ergebnis is not None
    assert not ergebnis["bestanden"]
    gerissen = [p for p in ergebnis["proben"] if not p["ok"]]
    assert len(gerissen) == 1
    assert gerissen[0]["delta"] == 100000.0
    # `lies` gibt dann gar keine Posten heraus.
    assert ka.lies(GER_KAPUTT)["posten"] == []


def test_ohne_tabelle_kein_ergebnis():
    assert ka.parse_gesamtergebnisrechnung("Nur Fließtext ohne Tabelle.") is None
    assert ka.lies("")["bestanden"] is False


# --- Trägeraufstellung ------------------------------------------------------

def test_traeger_werden_mit_schluessel_gelesen():
    bloecke = ka.parse_traeger(TRAEGER_2024)
    assert len(bloecke) == 1
    block = bloecke[0]
    assert block["art"] == "ertraege"
    assert block["spaltenprobe_ok"]
    assert block["verworfen"] == 0
    nach_key = {z["traeger_key"]: z for z in block["zeilen"]}
    assert nach_key["stadt"]["betrag_teur"] == 799057
    assert nach_key["klinikum"]["betrag_teur"] == 368100
    assert nach_key["konsolidierung"]["betrag_teur"] == -98506
    assert block["summe_teur"] == 1241548


def test_spaltenprobe_verwirft_widerspruechliche_aufstellung():
    """2018 Aufwendungen: Die Konsolidierungszeile des Berichts passt nicht
    zu seiner eigenen Summenzeile (64 TEUR Unterschied)."""
    block = ka.parse_traeger(TRAEGER_2018_AUFW)[0]
    assert block["art"] == "aufwendungen"
    assert not block["spaltenprobe_ok"]
    assert block["spaltenprobe_delta"] == -64.0
    # Und `lies` nimmt sie deshalb nicht auf.
    ergebnis = ka.lies(GER_2018 + TRAEGER_2018_AUFW)
    assert ergebnis["bestanden"]          # die Postentabelle bleibt gültig
    assert ergebnis["traeger"] == []      # die Aufstellung nicht
    assert ergebnis["traeger_gefunden"] == 1


def test_querprobe_verlangt_uebereinstimmung_mit_der_postentabelle():
    """Trägersumme und Summenposten stammen aus verschiedenen Kapiteln
    desselben Berichts — sie müssen dasselbe sagen."""
    ergebnis = ka.lies(GER_2019 + TRAEGER_2024)
    # 2019er Postentabelle gegen 2024er Trägerliste: passt nicht zusammen.
    assert ergebnis["traeger"] == []
    assert ergebnis["traeger_gefunden"] == 1


def test_vorzeichen_mit_leerzeichen():
    """Bis 2020 schreibt der Bericht „ - 80.462" und „+ 16.098"."""
    block = ka.parse_traeger(TRAEGER_2018_AUFW)[0]
    nach_key = {z["traeger_key"]: z for z in block["zeilen"]}
    assert nach_key["konsolidierung"]["betrag_teur"] == -80462
    assert nach_key["stadt"]["vorjahr_teur"] == 521420


def test_ohne_traegeraufstellung_keine_warnung():
    """Bis 2016 kennt der Bericht den Abschnitt 4.1.1 noch nicht. Das ist
    eine Lücke der Quelle, keine gerissene Probe."""
    ergebnis = ka.lies(GER_2014)
    assert ergebnis["bestanden"]
    assert ergebnis["traeger_gefunden"] == 0
    assert ergebnis["verworfen"] == 0


# --- Zusammenspiel ----------------------------------------------------------

def test_lies_liefert_probennachweis():
    ergebnis = ka.lies(GER_2018 + TRAEGER_2024.replace(
        "1.241.548 1.139.376 102.172", "927.894 864.627 63.267"))
    nachweis = ka.probennachweis(ergebnis["proben"])
    assert "ordentliches Ergebnis" in nachweis
    assert "Gesamtjahresergebnis" in nachweis
    assert "Δ 0.00" in nachweis


def test_speichern_und_lesen(tmp_path):
    """Der Weg in die Datenbank und zurück — inklusive der Einheit: Posten
    stehen in Euro, Trägerzeilen in TEUR."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        ergebnis = ka.lies(GER_2024_ZUSAMMEN)
        assert ergebnis["bestanden"]
        traeger = [z | {"art": b["art"]}
                   for b in ergebnis["traeger"] for z in b["zeilen"]]
        store.save_konzern_jahrgang(
            2024, ergebnis["posten"], traeger,
            _herkunft("Abschnitt 3.2, Gesamtergebnisrechnung des Konzerns",
                      ["konzern_ergebnisprobe", "konzern_ausserordentlich",
                       "konzern_gesamtergebnis"],
                      ka.probennachweis(ergebnis["proben"])),
            _herkunft("Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern",
                      ["konzern_zeilenprobe", "konzern_traegersumme",
                       "konzern_querprobe"],
                      ka.traegernachweis(ergebnis["traeger"])))

        assert store.konzern_jahre() == [2024]
        posten = {p["rolle"]: p for p in store.get_konzern_posten(2024) if p["rolle"]}
        assert posten["ertraege_summe"]["betrag"] == 1241548906.55

        zeilen = {z["traeger_key"]: z for z in store.get_konzern_traeger(2024)}
        assert zeilen["stadt"]["betrag_teur"] == 799057

        # Zwei Abschnitte, zwei Herkünfte — nicht eine für den ganzen Jahrgang.
        hid_posten = posten["ertraege_summe"]["herkunft_id"]
        hid_traeger = zeilen["stadt"]["herkunft_id"]
        assert hid_posten != hid_traeger
        nach_id = {h["id"]: h for h in store.get_herkunft()}
        assert nach_id[hid_posten]["fundstelle"].startswith("Abschnitt 3.2")
        assert nach_id[hid_traeger]["fundstelle"].startswith("Abschnitt 4.1.1")
        assert nach_id[hid_posten]["dokument_id"] == 302709
        assert nach_id[hid_posten]["stand"] == "Gesamtabschluss zum 31.12.2024"
        # Die Erklärsätze für die Leserin kommen aus herkunft.PROBEN.
        assert len(nach_id[hid_posten]["proben"]) == 3
        assert "ordentliches Ergebnis" in " ".join(nach_id[hid_posten]["proben"])

        # Keine Zeile ohne Herkunft — das ist der Sollzustand.
        luecken = {t: n for t, n in store.herkunft_luecken().items() if n}
        assert "council_konzern_posten" not in luecken
        assert "council_konzern_traeger" not in luecken

        # Zweimal speichern ersetzt, statt zu verdoppeln — und legt keine
        # zweite Herkunft an (idempotent über den Fingerabdruck).
        vorher = len(store.get_herkunft())
        store.save_konzern_jahrgang(
            2024, ergebnis["posten"], traeger,
            _herkunft("Abschnitt 3.2, Gesamtergebnisrechnung des Konzerns",
                      ["konzern_ergebnisprobe", "konzern_ausserordentlich",
                       "konzern_gesamtergebnis"],
                      ka.probennachweis(ergebnis["proben"])),
            _herkunft("Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern",
                      ["konzern_zeilenprobe", "konzern_traegersumme",
                       "konzern_querprobe"],
                      ka.traegernachweis(ergebnis["traeger"])))
        assert len(store.get_konzern_posten(2024)) == len(ergebnis["posten"])
        assert len(store.get_herkunft()) == vorher
    finally:
        store.close()


def test_herkunft_ohne_probe_ist_nicht_baubar():
    """Die Regel des Formats, an unserem Fall: Wer speichern will, muss
    sagen, womit die Zahl abgesichert ist."""
    with pytest.raises(ValueError):
        herkunft.Herkunft(art="ris", probe=[], dokument_id=302709)
    with pytest.raises(ValueError):
        herkunft.Herkunft(art="ris", probe="konzern_erfunden", dokument_id=302709)


def test_gegenprobe_gegen_die_kernverwaltung(tmp_path):
    """Die stärkste unabhängige Bestätigung: Die Trägerzeile „Stadt
    Oldenburg" muss den Ist-Wert wiedergeben, den unser Jahresabschluss-
    Parser aus einem ANDEREN Dokument gelesen hat."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_ergebnisrechnung(2024, [
            {"nr": 12, "bezeichnung": "Summe ordentliche Erträge",
             "ergebnis": 799057202.86, "ist_summe": 1},
            {"nr": 20, "bezeichnung": "Summe ordentliche Aufwendungen",
             "ergebnis": 764416063.76, "ist_summe": 1},
        ], herkunft.Herkunft(
            art="ris", probe="strukturprobe", dokument_id=295294,
            label="Jahresabschluss 2024", url="https://example.org/ja2024.pdf"))

        ist = store.kernverwaltung_ist()
        assert ist[2024]["ertraege"] == 799057202.86

        ergebnis = ka.lies(GER_2024_ZUSAMMEN)
        stadt = next(z for b in ergebnis["traeger"] for z in b["zeilen"]
                     if z["traeger_key"] == "stadt")
        # Der Bericht rundet auf Tausend — genauer geht der Abgleich nicht.
        assert abs(stadt["betrag_teur"] - ist[2024]["ertraege"] / 1000.0) <= 1.0
    finally:
        store.close()


#: Gesamtergebnisrechnung 2024 (auf die tragenden Posten gekürzt) samt der
#: zugehörigen Trägeraufstellung — beide aus `document_id` 302709, damit die
#: Querprobe echt ist und nicht gestellt.
GER_2024_ZUSAMMEN = """3.2 Gesamtergebnisrechnung
2024 2023
EUR EUR
1. Steuern und ähnliche Abgaben 349.906.048,17 341.608.473,52
13. Summe ordentliche Erträge 1.241.548.906,55 1.139.375.959,21
14. Personalaufwendungen 428.874.281,01 401.059.603,04
18. Zinsen und ähnliche Aufwendungen 11.508.664,63 9.037.003,60
21. Summe ordentliche Aufwendungen 1.234.483.072,81 1.111.151.067,51
22. ordentliches Ergebnis 7.065.833,74 28.224.891,70
23. außerordentliche Erträge 1.541.204,05 3.698.189,04
24. außerordentliche Aufwendungen 1.646.520,60 1.412.121,33
25. außerordentliches Ergebnis -105.316,55 2.286.067,71
26. Gesamtjahresergebnis 6.960.517,19 30.510.959,41
""" + TRAEGER_2024
