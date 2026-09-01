"""Die Ist-Investitionen aus den Tabellen 1107/1107-1 des Statistischen Jahrbuchs.

Die Fixture ist ein **echter, gekürzter Textextrakt** der Datei
(``1107-1107-1-2025-AZ.pdf``, Stand 08.07.2026) — dieselben zwei Tabellen in
derselben Datei, dieselbe Kopf-und-Fuß-Reihenfolge, die pypdf tatsächlich
liefert, und dieselben Zahlen. Sie enthält jede Eigenheit, an der ein naiver
Parser scheitert:

- **Zwei Tabellen mit verschiedener Spaltenzahl in einem Text.** 1107 hat
  fünf Wertspalten, 1107-1 hat sieben. Wer beide durch dieselbe
  Feldzahl-Prüfung schickt, verliert eine davon komplett.
- **Die Fußnotenziffer klebt im Titel an der Jahreszahl** (``2010 bis 20251``
  = „2010 bis 2025" mit Fußnote 1). An dieser Stelle scheitert die
  Spannen-Erkennung, nicht an den Datenzeilen.
- **2019 reißt die Zeilensumme im Dokument selbst** — die sechs
  Auszahlungsarten ergeben 1,304 Mio. € weniger als die Summe daneben.
- Die Spaltenköpfe stehen im Extrakt teils **unter** den Daten, und ein
  versprengtes „Finanzanlage-/vermögen" landet ganz am Seitenende.

Der Unterschied zu ``tests/test_schulden.py``, und der Grund für einen
eigenen Test: Dort rettete eine zweite, unabhängige Probe den gerissenen
Jahrgang, sodass die Summe blieb und nur die Aufteilung fiel. Hier gibt es
keine zweite Probe — also fällt der ganze Jahrgang, und genau das prüft
:func:`test_2019_faellt_ganz_heraus`.
"""
from __future__ import annotations

import pytest

from council import herkunft, investitionen_ist as ii
from council.store import CouncilStore

# --- Fixtures ---------------------------------------------------------------

#: Der Textextrakt der echten Datei, gekürzt auf die Jahrgänge, die etwas
#: beweisen: bei 1107 der erste und der letzte, bei 1107-1 der erste, das Paar
#: um den Sprung von 2018, der gerissene 2019 mit seinen Nachbarn und der
#: jüngste 2025.
TABELLE = """Stadt Oldenburg (Oldb) - Statistik
1107  Ausgaben der Stadt Oldenburg für eigene Investitionen
          in Tausend Euro 2003 bis 2009
                -  Rechnungsergebnisse
Haushalts- Gewährung Erwerb von Baumaß- Neuanschaf- insgesamt
year von Darlehen Grundver- nahmen fungen von
mögen beweglichen
Vermögen
S 1 S 2 S 3 S 4 S 5 S 6
2003 0 5.383 14.792 3.073 23.248
2009 20 2.252 25.536 5.345 33.153
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1107-1 Auszahlungen der Stadt Oldenburg für Investitionstätigkeiten
            in Tausend Euro 2010 bis 20251
               -  Rechnungsergebnisse laut Finanzrechnung der Kernverwaltung -
Haushalts- Aktivierbare Erwerb von Baumaß- Erwerb von Erwerb von Sonstige insgesamt
year Zuwendungen Grundstücken nahmen beweglichem Sachver- Investitions-
und Gebäuden mögen tätigkeit
S 1 S 2 S 3 S 4 S 5 S 6 S 7 S 8
2010 4.814 3.313 6.331 4.112 239 2 18.811
2017 4.933 1.574 8.150 6.750 519 123 22.049
2018 6.377 1.977 15.885 4.536 478 19.000 48.253
2019 6.004 3.306 19.304 6.701 626 30.654 67.899
2020 9.165 1.753 16.462 8.340 495 34.266 70.481
2025 14.790 219 16.208 8.528 945 20.083 60.773
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1 Einführung Neues Komunales Rechnungswesens (NKR) zum 01. Januar 2010.
Kapitel 11 - Verwaltung und Finanzen
Finanzanlage-
vermögen
Fachdienst Geo und Daten
"""


@pytest.fixture()
def gelesen():
    return ii.lies(TABELLE)


# --- Die zwei Tabellen erkennen ---------------------------------------------

def test_erkenne_findet_beide_tabellen():
    """Beide Titel, beide Spannen — und ``1107-1`` verschluckt ``1107`` nicht."""
    assert ii.erkenne(TABELLE) == {"kameral": (2003, 2009), "doppik": (2010, 2025)}


def test_die_fussnotenziffer_im_titel_verschiebt_die_spanne_nicht():
    """``2010 bis 20251`` sind 2010 bis 2025 mit Fußnote 1 — nicht bis 20251.

    Die Falle sitzt hier im TITEL und nicht in den Datenzeilen (anders als bei
    Tabelle 1108, wo die Marken an den Beträgen kleben). Ohne die Regel „ein
    Jahr hat vier Stellen, was danach kommt ist die Marke" fände die Erkennung
    entweder gar nichts oder eine Spanne bis ins Jahr 20251 — und dann meldete
    :func:`ii.lies` 18.000 fehlende Jahrgänge."""
    assert "20251" in TABELLE, "die Fixture hat die Marke verloren"
    assert ii.erkenne(TABELLE)["doppik"][1] == 2025


def test_ohne_titel_kein_abschnitt():
    """Ein Text ohne die Titel liefert nichts — statt Zahlen zu raten."""
    result = ii.lies("2010 4.814 3.313 6.331 4.112 239 2 18.811")
    assert result["zeilen"] == []
    assert result["spannen"] == {}


# --- Die Zeilen lesen -------------------------------------------------------

def test_beide_reihen_kommen_mit_ihren_eigenen_arten(gelesen):
    """Kameral vier Auszahlungsarten, doppisch sechs — je Regelwerk eigene."""
    kameral = [z for z in gelesen["zeilen"] if z["accounting_system"] == "kameral"]
    doppik = [z for z in gelesen["zeilen"] if z["accounting_system"] == "doppik"]
    assert [z["year"] for z in kameral] == [2003, 2009]
    assert [z["year"] for z in doppik] == [2010, 2017, 2018, 2020, 2025]
    assert len(ii.ARTEN["kameral"]) == 4
    assert len(ii.ARTEN["doppik"]) == 6
    # Und kein Feldname doppelt sich zwischen den Regelwerken außer der Summe.
    gemeinsam = set(ii.ARTEN["kameral"]) & set(ii.ARTEN["doppik"])
    assert not gemeinsam, (
        f"{gemeinsam} steht in beiden Rechnungswesen — ein gemeinsamer Feldname "
        "lädt dazu ein, über die Umstellung 2010 hinweg eine Reihe zu bilden")


def test_betraege_stehen_in_euro(gelesen):
    """Die Quelle rechnet in Tausend Euro, gespeichert wird in Euro."""
    z = next(z for z in gelesen["zeilen"] if z["year"] == 2025)
    assert z["total"] == 60_773_000
    assert z["baumassnahmen"] == 16_208_000
    assert z["sonstige"] == 20_083_000


def test_die_kamerale_zeile_traegt_ihre_eigenen_felder(gelesen):
    """2003 hat „Gewährung von Darlehen", nicht „Aktivierbare Zuwendungen"."""
    z = next(z for z in gelesen["zeilen"] if z["year"] == 2003)
    assert z["darlehen"] == 0
    assert z["baumassnahmen_k"] == 14_792_000
    assert "zuwendungen" not in z, "eine doppische Spalte in einer kameralen Zeile"


def test_eine_doppische_zeile_im_kameralen_abschnitt_faellt_durch():
    """Sieben Felder, wo fünf hingehören: unlesbar statt zurechtgebogen.

    Der Schutz gegen den Fall, dass die Stadt die beiden Tabellen eines Tages
    anders zusammensetzt. Eine Zeile mit zu vielen Feldern darf nicht still in
    die falsche Reihe rutschen — dort wäre sie in sich stimmig und trotzdem
    unter der falschen Abgrenzung gespeichert."""
    zeilen = ii.parse("2019 6.004 3.306 19.304 6.701 626 30.654 67.899", "kameral")
    assert len(zeilen) == 1
    assert zeilen[0]["unlesbar"]


# --- Die Probe --------------------------------------------------------------

def test_zeilensumme_haelt_in_jedem_uebernommenen_jahrgang(gelesen):
    """Kein Jahrgang kommt herein, dessen Arten die Summe nicht ergeben."""
    for z in gelesen["zeilen"]:
        ok, deviation = ii.zeilensumme(z)
        assert ok, f"{z['year']}: {deviation:+,.0f} €"


def test_2019_faellt_ganz_heraus():
    """Der Kern dieser Schicht: kein halber Jahrgang.

    2019 ergeben die sechs Auszahlungsarten 66.595 T€, ausgewiesen sind
    67.899 T€. Bei den Schulden trüge eine zweite, unabhängige Probe in so
    einem Fall wenigstens die Summe (Fall 2022, ``council/schulden.py``) —
    diese Tabelle hat keine. Also fällt der Jahrgang mit allen sieben Zahlen,
    und die Summe kommt NICHT als „wenigstens die stimmt" herein."""
    result = ii.lies(TABELLE)
    assert 2019 not in [z["year"] for z in result["zeilen"]]
    verworfen = [v for v in result["verworfen"] if v["year"] == 2019]
    assert len(verworfen) == 1
    assert "1.304.000" in verworfen[0]["reason"], verworfen[0]["reason"]
    # Deutsche Schreibweise, nicht 1,304,000 — der Grund landet im Protokoll.
    assert "1,304,000" not in verworfen[0]["reason"]


def test_die_differenz_kommt_als_zahl_neben_dem_satz():
    """Die gemessene Lücke ist eine Zahl, nicht nur ein Wort im Grund.

    Der Grund ist ein Satz für Menschen („um -1.304.000 € gerissen"). Wer den
    Betrag später auf der Seite zeigen will, müsste ihn aus diesem Satz
    zurückparsen — eine zweite, stille Schnittstelle, die beim nächsten
    Umformulieren bricht. Deshalb reist die Differenz als ``float`` mit,
    vorzeichenbehaftet und in Euro: 66.595 T€ gezählt gegen 67.899 T€
    ausgewiesen."""
    verworfen = next(v for v in ii.lies(TABELLE)["verworfen"] if v["year"] == 2019)
    assert verworfen["difference"] == -1_304_000
    # Und der Satz nennt dieselbe Zahl — zwei Auskünfte, eine Messung.
    assert ii.de_zahl(verworfen["difference"], vorzeichen=True) in verworfen["reason"]


def test_eine_unzerlegbare_zeile_hat_KEINE_differenz():
    """Ohne zerlegte Felder gibt es nichts zu messen — und dann steht dort
    ``None`` und nicht ``0``.

    Eine Null wäre an dieser Stelle die Behauptung „die Arten ergaben die
    Summe genau", also das Gegenteil des Befunds."""
    kaputt = TABELLE.replace("2017 4.933 1.574 8.150 6.750 519 123 22.049",
                             "2017 4.933 1.574 8.150 6.750 519 22.049")
    verworfen = next(v for v in ii.lies(kaputt)["verworfen"] if v["year"] == 2017)
    assert verworfen["difference"] is None
    assert "zerlegbar" in verworfen["reason"]


def test_die_luecke_wird_gemeldet(gelesen):
    """Was der Titel ankündigt und nicht ankommt, ist ein Befund.

    Die Fixture ist gekürzt, deshalb fehlen viele Jahrgänge — geprüft wird,
    dass 2019 darunter ist und dass die Lücke nach Regelwerk getrennt kommt."""
    assert 2019 in gelesen["fehlende_jahrgaenge"]["doppik"]
    assert 2003 not in gelesen["fehlende_jahrgaenge"].get("kameral", [])


def test_probennachweis_nennt_zahlen_keine_adjektive(gelesen):
    text = ii.probennachweis(gelesen)
    assert "7 von 8" in text, text
    assert "2019" in text


# --- Die Zellen-Regel -------------------------------------------------------

@pytest.mark.parametrize("field,erwartet", [
    ("18.811", 18811),
    ("0", 0),
    ("2", 2),
    ("239", 239),
    # Eine Fußnotenziffer hinter einer vollständigen Tausendergruppe gehört
    # nicht zur Zahl: 26.598 mit Fußnote 1, nicht 265.981. Heute trägt kein
    # Betrag dieser Tabelle eine Marke — die Regel fängt den Tag ab, an dem
    # die Stadt eine anhängt.
    ("26.5981", 26598),
    ("1.234.5679", 1234567),
    # Ohne Tausenderpunkt gilt das Feld ungeteilt: 239 ist nicht 23 mit
    # Fußnote 9.
    ("2391", 2391),
    ("x", None),
    ("", None),
])
def test_zelle(field, erwartet):
    assert ii._zelle(field) == erwartet


def test_de_zahl_schreibt_deutsch():
    assert ii.de_zahl(1_304_000) == "1.304.000"
    assert ii.de_zahl(60.773, 1) == "60,8"
    assert ii.de_zahl(-1_304_000, vorzeichen=True) == "-1.304.000"


# --- Herkunft ---------------------------------------------------------------

def test_die_probe_ist_dem_herkunfts_register_bekannt():
    """Ein Probenname, den ``herkunft.PROBEN`` nicht kennt, lässt sich gar
    nicht erst speichern (``ValueError``) — und ohne Eintrag dort hätte der
    Beleg auf der Seite keinen Satz für Leser*innen."""
    assert "investitionen_ist_zeilensumme" in herkunft.PROBEN
    h = herkunft.Herkunft(kind="city", url=ii.TABELLE_URL,
                          probe="investitionen_ist_zeilensumme")
    assert h.geprueft
    assert herkunft.probe_texte(h.probe)


def test_beide_tabellen_stehen_im_herkunfts_register():
    for tabelle in ("council_investitionen_ist", "council_investitionen_ist_arten",
                    "council_investitionen_ist_verworfen"):
        assert tabelle in herkunft.HERKUNFT_TABELLEN


# --- Speichern und Lesen ----------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _speichern(store, gelesen):
    for accounting_system in ("kameral", "doppik"):
        part = [z for z in gelesen["zeilen"] if z["accounting_system"] == accounting_system]
        verworfen = [v for v in gelesen["verworfen"] if v["accounting_system"] == accounting_system]
        store.save_investitionen_ist(part, herkunft.Herkunft(
            kind="city", url=ii.TABELLE_URL,
            probe="investitionen_ist_zeilensumme",
            citation=f"Tabelle {accounting_system}",
            probe_result=f"{len(part)} Jahrgänge"), verworfen=verworfen)


def test_speichern_und_lesen(store, gelesen):
    _speichern(store, gelesen)
    series = store.get_investitionen_ist()
    assert [z["year"] for z in series] == [2003, 2009, 2010, 2017, 2018, 2020, 2025]
    juengster = series[-1]
    assert juengster["accounting_system"] == "doppik"
    assert juengster["total"] == 60_773_000
    # Die Arten kommen in der Spaltenfolge der Quelle und tragen ihren Titel.
    assert [a["title"] for a in juengster["arten"]] == [
        t for _, t in ii.SPALTEN["doppik"][:-1]]
    assert sum(a["amount"] for a in juengster["arten"]) == juengster["total"]
    # Und die kamerale Zeile hat ihre eigenen vier.
    assert len(series[0]["arten"]) == 4
    assert series[0]["arten"][0]["title"] == "Gewährung von Darlehen"


def test_jede_zeile_traegt_eine_herkunft(store, gelesen):
    _speichern(store, gelesen)
    assert all(z["herkunft_id"] is not None for z in store.get_investitionen_ist())
    luecken = {t: n for t, n in store.herkunft_luecken().items()
               if t.startswith("council_investitionen_ist")}
    assert not luecken, luecken


def test_ein_zweiter_lauf_laesst_keine_karteileichen(store, gelesen):
    """Verliert die Quelle eine Spalte, verschwindet sie auch im Bestand.

    Ohne das Löschen vor dem Schreiben bliebe die abgeschaffte Art stehen, und
    die Aufteilung summierte sich auf mehr als die Summe daneben — eine
    Zeile, die sich selbst widerspricht, ohne dass ein Lauf etwas meldet."""
    _speichern(store, gelesen)
    schmaler = dict(next(z for z in gelesen["zeilen"] if z["year"] == 2025))
    schmaler["sonstige"] = None
    schmaler["total"] = 40_690_000
    store.save_investitionen_ist([schmaler], herkunft.Herkunft(
        kind="city", url=ii.TABELLE_URL, probe="investitionen_ist_zeilensumme"))
    z = next(z for z in store.get_investitionen_ist() if z["year"] == 2025)
    assert [a["field"] for a in z["arten"]] == list(ii.ARTEN["doppik"][:-1])
    assert sum(a["amount"] for a in z["arten"]) == z["total"]


def test_ein_lauf_raeumt_die_anderen_jahrgaenge_nicht_ab(store, gelesen):
    """``save_*`` ersetzt nur, was die Lieferung mitbringt."""
    _speichern(store, gelesen)
    nur_2025 = [z for z in gelesen["zeilen"] if z["year"] == 2025]
    store.save_investitionen_ist(nur_2025, herkunft.Herkunft(
        kind="city", url=ii.TABELLE_URL, probe="investitionen_ist_zeilensumme"))
    assert len(store.get_investitionen_ist()) == 7


def test_die_verworfenen_jahrgaenge_stehen_mit_ihrer_differenz_im_bestand(
        store, gelesen):
    """Die Kette, die den Betrag an die Lücke bringt: Parser → Store.

    Ohne diese Zeile wüsste die Seite nur, DASS 2019 fehlt. Die Zahl daneben
    ist der Unterschied zwischen „2019 fehlt" und „2019 fehlt, weil 1,3 Mio. €
    auseinanderlagen" — und sie darf nirgends im Frontend stehen."""
    _speichern(store, gelesen)
    verworfen = store.get_investitionen_ist_verworfen()
    assert [v["year"] for v in verworfen] == [2019]
    assert verworfen[0]["accounting_system"] == "doppik"
    assert verworfen[0]["difference"] == -1_304_000
    assert verworfen[0]["herkunft_id"] is not None
    # Und der Jahrgang steht NICHT in der Reihe — die Lücke ist kein Wert.
    assert 2019 not in [z["year"] for z in store.get_investitionen_ist()]


def test_ein_geretteter_jahrgang_verliert_seinen_lueckeneintrag(store, gelesen):
    """Korrigiert die Stadt ihre Tabelle, verschwindet die Lücke mit ihr.

    Ohne das Löschen stünde derselbe Jahrgang in beiden Tabellen, und die
    Seite zeigte eine beschriftete Lücke neben einer gezeichneten Säule."""
    _speichern(store, gelesen)
    assert [v["year"] for v in store.get_investitionen_ist_verworfen()] == [2019]
    geheilt = ii.parse("2019 6.004 3.306 19.304 6.701 626 30.654 66.595", "doppik")
    assert ii.zeilensumme(geheilt[0])[0], "die Testzeile muss die Probe bestehen"
    store.save_investitionen_ist(geheilt, herkunft.Herkunft(
        kind="city", url=ii.TABELLE_URL, probe="investitionen_ist_zeilensumme"))
    assert store.get_investitionen_ist_verworfen() == []
    assert 2019 in [z["year"] for z in store.get_investitionen_ist()]


def test_leere_datenbank_liefert_leer(store):
    """Ohne Ingest-Lauf keine Ausnahme, sondern nichts."""
    assert store.get_investitionen_ist() == []
    assert store.investitionen_ist_jahre() == []
    assert store.get_investitionen_ist_verworfen() == []
    assert store.investitionen_ist_kontext() is None


# --- Der Baustein für die KI-Frage ------------------------------------------

def test_kontext_nimmt_nur_die_doppische_reihe(store, gelesen):
    """Kameral und doppisch nebeneinander im Prompt wären eine Einladung,
    sie zu einer Reihe zu addieren."""
    _speichern(store, gelesen)
    k = store.investitionen_ist_kontext()
    assert k["year"] == 2025
    assert k["reihe_ab"] == 2010, "die kamerale Reihe ist mit hereingerutscht"
    assert k["hoch"]["year"] == 2020
    assert k["abgrenzung"] == ii.ABGRENZUNG
    assert k["beleg"]["url"] == ii.TABELLE_URL


def test_kontext_nennt_die_luecke(store, gelesen):
    """Ohne diese Angabe liest ein Modell die Reihe als geschlossen."""
    _speichern(store, gelesen)
    assert 2019 in store.investitionen_ist_kontext()["fehlend"]


def test_der_prompt_baustein_verbietet_die_quote(store, gelesen):
    """Die Regel, für die es diesen Baustein überhaupt gibt.

    Plan und Ist stehen zum ersten Mal zusammen im Kontext, und
    „Ist ÷ Plan = Umsetzungsquote" liegt einem Sprachmodell am nächsten. Sie
    steht in keinem Dokument."""
    from council import qa

    _speichern(store, gelesen)
    text = qa._gebaut_block(store.investitionen_ist_kontext())
    assert "Umsetzungsquote" in text
    assert "NIE GEGEN DEN PLAN RECHNEN" in text
    assert "60.773.000 €" in text, "der Betrag fehlt oder steht englisch"
    assert "2019" in text, "die Lücke steht nicht im Baustein"
    # Der Beleg reist mit: Ohne ihn nennt die Antwort kein Dokument.
    assert "Tabelle doppik" in text


def test_die_facette_zieht_plan_und_ist_gemeinsam():
    """„Was wird gebaut?" hat beides, und die Frage sagt selten, welches."""
    from council import qa

    facetten = qa.geld_facetten("Wie viel investiert Oldenburg?", "geld")
    assert {"investitionen", "gebaut"} <= facetten
    # Und sie stehen im Budget nebeneinander, damit nicht eines allein
    # durchkommt und die Warnung an einer fehlenden Zahl hängt.
    i = qa.GELD_FACETTEN.index("investitionen")
    assert qa.GELD_FACETTEN[i + 1] == "gebaut"


def test_geld_kontext_ueberlebt_eine_frische_datenbank(store):
    """Neue Store-Abfragen gehören in ``_sicher`` — sonst reißt die ganze
    Antwort, sobald eine Tabelle fehlt (``tests/test_haushalt_gate.py``)."""
    from council import qa

    aus = qa.geld_kontext(store, "Wie viel wurde gebaut?", typ="geld")
    assert "gebaut" in aus["facetten"]
    assert aus.get("gebaut") is None
