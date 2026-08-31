"""Die Gewerbesteuerstatistik des Landesamts für Statistik Niedersachsen.

Die Fixtures sind **echte, gekürzte Ausschnitte** aus zwei geprüften
Statistischen Berichten (L IV 13, Erhebungsjahre 2017 und 2021,
``/download/186648`` und ``/download/227059``) — dieselben Zeilennummern,
dieselben Spaltenköpfe, dieselben Zahlen. Gebaut werden sie mit demselben
XLSX-Schreiber wie beim Städtevergleich, also als **richtige** Mappen: Was
hier geprüft wird, ist der Leser und nicht nur die Auswertung darüber.

Zwei Jahrgänge und nicht einer, weil genau dazwischen die Falle liegt, an der
ein naiver Parser scheitert:

- **Die Spaltenköpfe sind umformuliert worden.** 2017 heißt es „Betrag der
  Festsetzungen und Zerlegungen … mit positivem Steuermessbetrag in €", 2021
  „Festsetzungen und Zerlegungen …; darunter mit positivem Steuermessbetrag in
  Euro". Auch die Schlüsselspalte hat einen neuen Namen bekommen.
- **Die Einheit steht nicht überall.** Blatt 6.2 nennt sie im Jahrgang 2017
  gar nicht — deshalb darf sie nicht das Merkmal sein, an dem eine
  Betragsspalte erkannt wird.
- **Der Städtename wandert** („Oldenburg (Oldenburg), Stadt" → „Oldenburg
  (Oldb), Stadt"). Verbunden wird über die Schlüsselnummer, die in 6.1
  dreistellig und in 6.2 sechsstellig steht.
- **2017 wiederholt Blatt 6.1 die Schlüsselspalte am Zeilenende.**
- **„g" ist kein Nullwert.** Es steht für die Geheimhaltung — 2021 bei den
  Beträgen von Salzgitter und Wolfsburg, 2020 bei allen neun Spalten.
"""
from __future__ import annotations

import pytest

from council import gewerbesteuerstatistik as gs
from council import herkunft
from council.store import CouncilStore
from tests.test_staedtevergleich import schreibe_xlsx

# --- Fixtures: der Bericht 2021 (neue Schreibweise) -------------------------

_KOPF_61_2021 = [
    "Amtlicher Gemeindeschlüssel",
    "Kreisfreie Städte, Landkreise, Statistische Region, Land",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten;"
    " darunter mit positivem Steuermessbetrag",
    "Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten; darunter"
    " mit positivem Steuermessbetrag in Euro",
    "Anzahl der reinen Festsetzungen steuerpflichtiger Gewerbebetriebe",
    "Anzahl der reinen Festsetzungen steuerpflichtiger Gewerbebetriebe;"
    " darunter: mit positivem Steuermessbetrag",
    "Reine Festsetzungen steuerpflichtiger Gewerbebetriebe; darunter mit"
    " positivem Steuermessbetrag; in Euro",
    "Anzahl der Zerlegungen von Betriebsstätten",
    "Anzahl der Zerlegungen von Betriebsstätten; darunter mit positivem"
    " Steuermessbetrag",
    "Zerlegungen von Betriebsstätten; darunter mit positivem Steuermessbetrag;"
    " in Euro",
    "Zeilenende",
]

_KOPF_62_2021 = [
    "Amtlicher Gemeindeschlüssel",
    "Gemeinden, Land",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten"
    " mit positivem Steuermessbetrag",
    "Betrag der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten"
    " mit positivem Steuermessbetrag, in Euro",
    "Nachrichtlich: Hebesatz in Prozent",
    "Zeilenende",
]

#: Blatt 6.1, Erhebungsjahr 2021 — vier Datenzeilen, von denen nur zwei
#: hereingehören: Ammerland ist ein Landkreis, „Niedersachsen" eine Summe.
_BLATT_61_2021 = {
    1: ["Zum Inhaltsverzeichnis"],
    2: ["6. Gewerbesteuerpflichtige 2021 – Festsetzung und Zerlegung nach Sitz"
        " des Betriebes/der Betriebsstätte"],
    3: ["6.1 Land, kreisfreie Städte, Landkreise"],
    4: ["Vorlesbarer Tabellenkopf in Zeile 8"],
    5: ["Schlüssel- nummer", "Kreisfreie Städte Landkreise Statistische Region Land"],
    8: _KOPF_61_2021,
    9: ["101", "Braunschweig, Stadt", 10446, 4654, 36807587,
        8744, 3596, 18735408, 1702, 1058, 18072179, "Zeilenende"],
    10: ["102", "Salzgitter, Stadt", 2968, 1337, "g",
         2412, 987, "g", 556, 350, "g", "Zeilenende"],
    11: ["403", "Oldenburg (Oldb), Stadt", 8421, 3642, 30015356,
         6996, 2763, 14103549, 1425, 879, 15911807, "Zeilenende"],
    12: ["451", "Ammerland", 7371, 3462, 20534986,
         6276, 2742, 13235512, 1095, 720, 7299474, "Zeilenende"],
    13: ["Für Niedersachsen keine Schlüsselnummer vergeben", "Niedersachsen1)",
         384667, 175480, 1240486232, 318316, 133096, 666369642,
         66351, 42384, 574116590, "Zeilenende"],
}

_BLATT_62_2021 = {
    1: ["Zum Inhaltsverzeichnis"],
    3: ["6.2 Gemeinden"],
    4: ["Vorlesbarer Tabellenkopf in Zeile 8."],
    8: _KOPF_62_2021,
    9: ["101000", "Braunschweig, Stadt", 10446, 4654, 36807587, 450, "Zeilenende"],
    10: ["102000", "Salzgitter, Stadt", 2968, 1337, "g", 440, "Zeilenende"],
    11: ["403000", "Oldenburg (Oldb), Stadt", 8421, 3642, 30015356, 439, "Zeilenende"],
    12: ["453003", "Cappeln (Oldenburg)", 461, 186, 1197149, 340, "Zeilenende"],
}

_TITEL_2021 = {
    1: ["Statistische Berichte Niedersachsen"],
    3: ["L IV 13 − j / 2021"],
    5: ["Gewerbesteuerstatistik 2021"],
}

_IMPRESSUM_2021 = {
    1: ["Impressum"],
    4: ["Erscheinungsweise: jährlich Erschienen im März 2026"],
}


# --- Fixtures: der Bericht 2017 (alte Schreibweise) -------------------------

_KOPF_61_2017 = [
    "Regionale Gliederung nach AGS",
    "Kreisfreie Stadt, Landkreis, Statistische Region, Land",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten",
    "Anzahl der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten"
    " mit positivem Steuermessbetrag",
    "Betrag der Festsetzungen und Zerlegungen von Betrieben und Betriebsstätten"
    " mit positivem Steuermessbetrag in €",
    "Anzahl der reinen Festsetzungen steuerpflichtiger Gewerbebetriebe",
    "Anzahl der reinen Festsetzungen steuerpflichtiger Gewerbebetriebe mit"
    " positivem Steuermessbetrag",
    "Betrag der reinen Festsetzungen steuerpflichtiger Gewerbebetriebe mit"
    " positivem Steuermessbetrag in €",
    "Anzahl der Zerlegungen von Betriebsstätten",
    "Anzahl der Zerlegungen von Betriebsstätten mit positivem Steuermessbetrag",
    "Betrag der Zerlegungen von Betriebsstätten mit positivem Steuermessbetrag"
    " in €",
    # Die Wiederholungsspalte, die es nur 2017 gibt.
    "Regionale Gliederung nach AGS",
    "Zeilenende",
]

_BLATT_61_2017 = {
    1: ["Zum Inhaltsverzeichnis"],
    4: ["Vorlesbarer Tabellenkopf in Zeile 8."],
    8: _KOPF_61_2017,
    9: ["403", "Oldenburg (Oldenburg), Stadt", 8071, 3481, 26579797,
        6622, 2566, 10718050, 1449, 915, 15861747, "403", "Zeilenende"],
}

_BLATT_62_2017 = {
    1: ["Zum Inhaltsverzeichnis"],
    4: ["Vorlesbarer Tabellenkopf in Zeile 8."],
    8: ["Regionale Gliederung nach AGS",
        "Gemeinde, Land",
        "Anzahl der Festsetzungen und Zerlegungen von Betrieben und"
        " Betriebsstätten",
        "Anzahl der Festsetzungen und Zerlegungen von Betrieben und"
        " Betriebsstätten mit positivem Steuermessbetrag",
        # OHNE Einheit — genau so steht es im Jahrgang 2017.
        "Betrag der Festsetzungen und Zerlegungen von Betrieben und"
        " Betriebsstätten mit positivem Steuermessbetrag",
        "Nachrichtlich: Hebesatz in Prozent",
        "Zeilenende"],
    9: ["403000", "Oldenburg (Oldenburg), Stadt", 8071, 3481, 26579797, 439,
        "Zeilenende"],
}


def _mappe(tmp_path, name: str, blatt61: dict, blatt62: dict,
           titel: dict, impressum: dict) -> str:
    return schreibe_xlsx(tmp_path / name, {
        "Titel": titel, "Impressum": impressum,
        "6.1": blatt61, "6.2": blatt62})


@pytest.fixture
def bericht2021(tmp_path) -> str:
    return _mappe(tmp_path, "gewst2021.xlsx", _BLATT_61_2021, _BLATT_62_2021,
                  _TITEL_2021, _IMPRESSUM_2021)


@pytest.fixture
def bericht2017(tmp_path) -> str:
    return _mappe(tmp_path, "gewst2017.xlsx", _BLATT_61_2017, _BLATT_62_2017,
                  {3: ["L IV 13 − j / 2017"], 5: ["Gewerbesteuerstatistik 2017"]},
                  {4: ["Erscheinungsweise: jährlich Erschienen im August 2022"]})


# --- Der Kopf ---------------------------------------------------------------

def test_erhebungsjahr_und_erscheinen_stehen_getrennt(bericht2021):
    """Fünf Jahre liegen dazwischen — beide Angaben gehören an die Zahl."""
    jg = gs.lies_bericht(bericht2021)
    assert jg.year == 2021
    assert jg.erschienen == "Erschienen im März 2026"
    assert jg.korrektur is None
    assert jg.stand == "Erschienen im März 2026"


def test_korrigierte_fassung_landet_im_stand(tmp_path):
    """Der Jahrgang 2020 ist am 11.02.2026 nachgebessert worden. Wer eine
    korrigierte Fassung gelesen hat, muss das an der Zahl sehen können."""
    pfad = _mappe(tmp_path, "korr.xlsx", _BLATT_61_2021, _BLATT_62_2021,
                  {3: ["L IV 13 − j / 2021"],
                   5: ["Gewerbesteuerstatistik 2021 Korrigierte Fassung vom 11.02.2026"]},
                  _IMPRESSUM_2021)
    jg = gs.lies_bericht(pfad)
    assert jg.korrektur == "Korrigierte Fassung vom 11.02.2026"
    assert jg.stand == "Erschienen im März 2026, Korrigierte Fassung vom 11.02.2026"


def test_ohne_erhebungsjahr_bricht_der_lauf_ab(tmp_path):
    pfad = _mappe(tmp_path, "ohne.xlsx", _BLATT_61_2021, _BLATT_62_2021,
                  {1: ["Statistische Berichte Niedersachsen"]}, _IMPRESSUM_2021)
    with pytest.raises(ValueError, match="kein Erhebungsjahr"):
        gs.lies_bericht(pfad)


# --- Die Spaltenzuordnung ---------------------------------------------------

def test_beide_schreibweisen_ergeben_dieselbe_zuordnung():
    """Der Kern dieser Schicht: 2017 und 2021 sagen dasselbe mit anderen Worten.

    Ohne diesen Test fiele eine Umformulierung erst im Betrieb auf — und dann
    als fehlende Spalte, nicht als falsche Zahl (dafür sorgt die Abbruchregel
    in ``_blatt``)."""
    def kopf(zeile):
        return {i: t for i, t in enumerate(zeile) if t != "Zeilenende"}

    alt = gs.spaltenzuordnung(kopf(_KOPF_61_2017))
    neu = gs.spaltenzuordnung(kopf(_KOPF_61_2021))
    assert set(alt) == set(neu) == set(gs.ERWARTET_KREISE)
    # Die Positionen sind in beiden Jahrgängen dieselben — die Umbenennung hat
    # die Reihenfolge nicht angetastet.
    assert alt == neu


def test_hebesatzspalte_ist_kein_betrag():
    """„Nachrichtlich: Hebesatz in Prozent" gehört zu keinem Block. Landete er
    als Betrag in der Zuordnung, stünden 439 Euro Steuermessbetrag da."""
    zuordnung = gs.spaltenzuordnung(
        {i: t for i, t in enumerate(_KOPF_62_2021) if t != "Zeilenende"})
    assert set(zuordnung) == set(gs.ERWARTET_GEMEINDEN)


def test_fehlende_spalte_bricht_ab_statt_zu_raten(tmp_path):
    verstuemmelt = {**_BLATT_61_2021}
    verstuemmelt[8] = [t for t in _KOPF_61_2021 if "Zerlegungen von Betriebsstätten" not in t]
    pfad = _mappe(tmp_path, "kaputt.xlsx", verstuemmelt, _BLATT_62_2021,
                  _TITEL_2021, _IMPRESSUM_2021)
    with pytest.raises(ValueError, match="zerlegung_count"):
        gs.lies_bericht(pfad)


# --- Die Zeilen -------------------------------------------------------------

def test_oldenburg_wird_vollstaendig_gelesen(bericht2021):
    jg = gs.lies_bericht(bericht2021)
    zeilen, verworfen = gs.zeilen(jg)
    assert not verworfen
    ol = next(z for z in zeilen if z["schluessel"] == gs.OLDENBURG)
    assert ol["faelle"] == 8421
    assert ol["cases_positive"] == 3642
    assert ol["tax_base_eur"] == 30015356
    assert ol["festsetzungen"] == 6996
    assert ol["apportionments_positive"] == 879
    assert ol["apportioned_assessment_eur"] == 15911807
    # Der Hebesatz kommt aus dem ANDEREN Blatt und muss trotzdem an der Zeile
    # stehen — er ist die Brücke zum Statistischen Jahrbuch.
    assert ol["hebesatz"] == 439
    assert ol["gesperrt"] is False


def test_landkreise_und_summenzeilen_kommen_nicht_herein(bericht2021):
    """Blatt 6.1 führt Landkreise und die Landessumme in denselben Spalten.

    Der Landkreis Ammerland (451) trägt eine dreistellige Nummer wie die
    kreisfreien Städte; ohne die Prüfung gegen die Städteliste stünde er als
    „451000" im Bestand."""
    jg = gs.lies_bericht(bericht2021)
    zeilen, _ = gs.zeilen(jg)
    assert {z["schluessel"] for z in zeilen} == {"101000", "102000", "403000"}


def test_der_gespeicherte_name_ist_unserer_nicht_der_der_datei(bericht2017, bericht2021):
    """Die Datei schreibt die Stadt je Jahrgang anders. Eine Reihe, die ihren
    eigenen Namen wechselt, sieht in jeder Anzeige nach zwei Städten aus."""
    alt, _ = gs.zeilen(gs.lies_bericht(bericht2017))
    neu, _ = gs.zeilen(gs.lies_bericht(bericht2021))
    beide = [z for z in alt + neu if z["schluessel"] == gs.OLDENBURG]
    assert len(beide) == 2
    assert {z["stadt"] for z in beide} == {"Oldenburg"}


def test_alte_schreibweise_ergibt_dieselben_zahlen(bericht2017):
    """Derselbe Parser, anderer Jahrgang — inklusive Wiederholungsspalte und
    fehlender Einheit in Blatt 6.2."""
    jg = gs.lies_bericht(bericht2017)
    assert jg.year == 2017
    zeilen, verworfen = gs.zeilen(jg)
    assert not verworfen
    assert zeilen[0]["faelle"] == 8071
    assert zeilen[0]["tax_base_eur"] == 26579797
    assert zeilen[0]["hebesatz"] == 439


# --- Die Geheimhaltung ------------------------------------------------------

def test_gesperrter_betrag_wird_nicht_zu_null(bericht2021):
    """Salzgitter zahlt Gewerbesteuer — der Betrag darf nur nicht genannt
    werden. Ein Parser, der „g" zu 0 macht, behauptet das Gegenteil."""
    jg = gs.lies_bericht(bericht2021)
    zeilen, _ = gs.zeilen(jg)
    sz = next(z for z in zeilen if z["schluessel"] == "102000")
    assert sz["tax_base_eur"] is None
    assert sz["gesperrt"] is True
    # Die Anzahlen stehen trotzdem da und sind die eigentliche Auskunft.
    assert sz["faelle"] == 2968
    assert sz["cases_positive"] == 1337


def test_vollstaendig_gesperrte_stadt_ist_kein_probenfehler(tmp_path):
    """Der Jahrgang 2020: Für Salzgitter und Wolfsburg steht in allen neun
    Spalten „g". Das ist eine Entscheidung des Landesamts, kein Lesefehler —
    und muss im Protokoll anders heißen, sonst sucht jemand einen Parserfehler,
    den es nicht gibt."""
    blatt = {**_BLATT_61_2021}
    blatt[10] = ["102", "Salzgitter, Stadt"] + ["g"] * 9 + ["Zeilenende"]
    blatt62 = {**_BLATT_62_2021}
    blatt62[10] = ["102000", "Salzgitter, Stadt", "g", "g", "g", 440, "Zeilenende"]
    pfad = _mappe(tmp_path, "gesperrt.xlsx", blatt, blatt62, _TITEL_2021,
                  _IMPRESSUM_2021)
    zeilen, verworfen = gs.zeilen(gs.lies_bericht(pfad))
    assert [v["grund"] for v in verworfen] == ["Geheimhaltung"]
    assert "102000" not in {z["schluessel"] for z in zeilen}


# --- Die Proben -------------------------------------------------------------

def test_summenprobe_faengt_eine_verrutschte_spalte(tmp_path):
    """Reine Festsetzungen + Zerlegungen = insgesamt. Wird eine Zahl
    angefasst, reißt die Rechnung — und die Stadt kommt nicht herein."""
    blatt = {**_BLATT_61_2021}
    blatt[11] = ["403", "Oldenburg (Oldb), Stadt", 8421, 3642, 30015356,
                 6996, 2763, 14103549, 1425, 879,
                 15911806,  # ein Euro zu wenig
                 "Zeilenende"]
    pfad = _mappe(tmp_path, "schief.xlsx", blatt, _BLATT_62_2021, _TITEL_2021,
                  _IMPRESSUM_2021)
    zeilen, verworfen = gs.zeilen(gs.lies_bericht(pfad))
    assert gs.OLDENBURG not in {z["schluessel"] for z in zeilen}
    assert verworfen[0]["grund"] == "Summenprobe"
    assert "gesamt_amount" in verworfen[0]["result"]


def test_summenprobe_laeuft_auch_ohne_betrag(bericht2021):
    """Bei Salzgitter sind nur die Beträge gesperrt. Die beiden Anzahl-Proben
    laufen trotzdem — und tragen die Zeile."""
    jg = gs.lies_bericht(bericht2021)
    probe = gs.probe_summen(jg.staedte["102000"])
    assert probe["ok"]
    assert [t["ok"] for t in probe["teilproben"]] == [True, True, None]


def test_blattprobe_stellt_die_zwei_tabellen_gegeneinander(bericht2021):
    probe = gs.probe_blaetter(gs.lies_bericht(bericht2021))
    assert probe["ok"]
    # Drei Städte, davon eine mit gesperrtem Betrag: 3 + 3 + 2 Werte.
    assert probe["geprueft"] == 8


def test_blattprobe_reisst_bei_widerspruch(tmp_path):
    blatt62 = {**_BLATT_62_2021}
    blatt62[11] = ["403000", "Oldenburg (Oldb), Stadt", 8421, 3641, 30015356,
                   439, "Zeilenende"]
    pfad = _mappe(tmp_path, "widerspruch.xlsx", _BLATT_61_2021, blatt62,
                  _TITEL_2021, _IMPRESSUM_2021)
    probe = gs.probe_blaetter(gs.lies_bericht(pfad))
    assert not probe["ok"]
    assert "gesamt_positiv" in probe["abweichungen"][0]["grund"]


def test_hebesatz_kommt_aus_der_treppe_nicht_aus_dem_jahr():
    """Tabelle 1105 führt nur die Änderungsjahre. Für 2021 gibt es keine
    Zeile — es gilt der Satz von 2015. Wer auf Gleichheit sucht, findet
    nichts und hielte die Probe für nicht durchführbar."""
    treppe = [
        {"year": 2011, "art": "Gewerbesteuer", "hebesatz": 430, "prior_rate": 410},
        {"year": 2015, "art": "Gewerbesteuer", "hebesatz": 439, "prior_rate": 430},
        {"year": 2015, "art": "Grundsteuer B", "hebesatz": 445, "prior_rate": 430},
        {"year": 2025, "art": "Grundsteuer B", "hebesatz": 539, "prior_rate": 445},
    ]
    assert gs.hebesatz_im_jahr(treppe, 2021) == 439
    assert gs.hebesatz_im_jahr(treppe, 2012) == 430
    assert gs.hebesatz_im_jahr(treppe, 2000) is None
    # Die Grundsteuer-Zeilen dürfen die Antwort nicht verändern.
    assert gs.hebesatz_im_jahr(treppe, 2025) == 439


def test_hebesatzprobe_gegen_das_jahrbuch(bericht2021):
    jg = gs.lies_bericht(bericht2021)
    assert gs.probe_hebesatz(jg, gs.OLDENBURG, 439.0)["ok"] is True
    assert gs.probe_hebesatz(jg, gs.OLDENBURG, 445.0)["ok"] is False
    # Ohne Vergleichswert gilt sie als NICHT GELAUFEN, nicht als bestanden.
    assert gs.probe_hebesatz(jg, gs.OLDENBURG, None)["ok"] is None


# --- Speichern --------------------------------------------------------------

def _herkunft() -> herkunft.Herkunft:
    return herkunft.Herkunft(
        art="lsn",
        probe=["gewst_summenprobe", "gewst_blattprobe", "gewst_hebesatzprobe"],
        label="Gewerbesteuerstatistik 2021 (Statistischer Bericht L IV 13)",
        url="https://example.org/gewst2021.xlsx",
        citation="Blatt 6.1 und 6.2", probe_result="3 Städte nachgerechnet",
        stand="Erschienen im März 2026")


def test_die_proben_sind_bekannte_namen():
    """Eine Herkunft mit unbekannter Probe ließe sich gar nicht erst bauen —
    und der Erklärsatz landet über die API im Beleg-Chip."""
    for name in ("gewst_summenprobe", "gewst_blattprobe", "gewst_hebesatzprobe"):
        assert name in herkunft.PROBEN
    assert "council_gewerbesteuerstatistik" in herkunft.HERKUNFT_TABELLEN


def test_speichern_und_lesen(tmp_path, bericht2021):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        zeilen, _ = gs.zeilen(gs.lies_bericht(bericht2021))
        assert store.save_gewerbesteuerstatistik(zeilen, _herkunft()) == 3
        gelesen = store.get_gewerbesteuerstatistik(gs.OLDENBURG)
        assert [z["year"] for z in gelesen] == [2021]
        assert gelesen[0]["cases_positive"] == 3642
        assert all(z["herkunft_id"] for z in gelesen)
        assert store.herkunft_luecken().get("council_gewerbesteuerstatistik") is None
        h = store.get_herkunft([gelesen[0]["herkunft_id"]])[0]
        assert h["art"] == "lsn"
        assert len(h["probes"]) == 3
        # Der gesperrte Betrag bleibt NULL — und ist von „null Euro" zu
        # unterscheiden, weil die Zeile es sagt.
        sz = [z for z in store.get_gewerbesteuerstatistik() if z["schluessel"] == "102000"]
        assert sz[0]["tax_base_eur"] is None and sz[0]["gesperrt"] == 1
    finally:
        store.close()


def test_ein_jahrgang_ersetzt_nur_sich_selbst(tmp_path, bericht2017, bericht2021):
    """Korrigierte Fassungen gibt es (Jahrgang 2020). Ein zweiter Lauf für
    2021 darf 2017 nicht mitnehmen — und den eigenen Jahrgang vollständig
    ersetzen, statt Zeilen stehen zu lassen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        for pfad in (bericht2017, bericht2021):
            zeilen, _ = gs.zeilen(gs.lies_bericht(pfad))
            store.save_gewerbesteuerstatistik(zeilen, _herkunft())
        assert [z["year"] for z in store.get_gewerbesteuerstatistik(gs.OLDENBURG)] \
            == [2017, 2021]

        zeilen, _ = gs.zeilen(gs.lies_bericht(bericht2021))
        store.save_gewerbesteuerstatistik(zeilen, _herkunft())
        alle = store.get_gewerbesteuerstatistik()
        assert [z["year"] for z in store.get_gewerbesteuerstatistik(gs.OLDENBURG)] \
            == [2017, 2021]
        assert len(alle) == 4  # 2017: Oldenburg · 2021: drei Städte
    finally:
        store.close()


def test_leere_datenbank_antwortet_leer(tmp_path):
    """Frische Maschine ohne Ingest-Lauf: Der Steckbrief zeigt den Block dann
    ohne diese Zahlen — er darf nicht mit einem Fehler antworten."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        assert store.get_gewerbesteuerstatistik() == []
        assert store.get_gewerbesteuerstatistik("403000") == []
    finally:
        store.close()
