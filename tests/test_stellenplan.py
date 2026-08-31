"""Der Stellenplan — und die Frage, wem die unbesetzten Stellen gehören.

Zwei Dinge können hier still falsch werden und sähen danach genauso solide
aus wie jede richtige Zahl:

1. **Die Besetzungsspalten gehören zur Vorjahresspalte, nicht zum
   Haushaltsjahr.** Der Plan sagt für 2026 „815 Stellen" und daneben, wie es
   am 30.6.2025 aussah: 796 Stellen, davon 143,71 nicht besetzt. Wer die
   143,71 gegen die 815 rechnet, erfindet eine Lücke, die es nicht gibt — und
   niemand merkt es, weil beide Zahlen im selben Kasten stehen.
2. **Ein Jahrgang kann halb hereinkommen.** Der Plan hat zwei Teile, und im
   Jahrgang 2026 gibt der Textextrakt für Teil B Glyphen statt Buchstaben aus.
   Ein Jahrgang mit nur Teil A sieht in jeder Jahresliste aus wie ein ganzer,
   unterschlägt aber 1.700 Tarifstellen.

Dazu kommt der Fall, an dem sich entscheidet, ob eine Regel Ehrlichkeit
herstellt oder bloß Strenge: Der Stellenplan 2023 **widerspricht sich selbst**
— zwei Zeilen in Teil B, eine Stelle in der falschen Zeile verbucht. Die
Summenzeilen darüber gehen auf. Diese Datei hält fest, dass beide Zeilen
gespeichert und gekennzeichnet werden, statt 140 belegte Zeilen wegen eines
städtischen Übertragsfehlers zu verlieren.

``STELLENPLAN_2026_A`` ist **echter** Text aus dem Dokument 297432 (Haushalt
2026, Anlage 022): Teil A vollständig und wörtlich, Kopf, Seitenwechsel und
Vermerke inklusive. Der Ausschnitt liefert dieselben 46 Zeilen und dieselben
Summen wie der Volltext (nachgemessen 16.08.2026).

``TEIL_B_KLEIN`` ist **kein** Auszug, sondern nachgebaut: Teil B in klein,
damit die Gruppenprobe ohne 140 Zeilen läuft. Kopf und die vier Zeilen stehen
wörtlich so im Plan 2025; die Summenzeile ist die Summe genau dieser vier.
"""
from __future__ import annotations

import pytest

from council import finanzquellen, herkunft
from council import stellenplan as sp
from council.store import CouncilStore

# --- Echter Auszug: „2026 022 Vw Stellenplan", Teil A -----------------------

STELLENPLAN_2026_A = """1523
1524
Stellenplan 00100 Stadt Oldenburg
Teil A: Beamtinnen und Beamte Datum: 01.01.2026
Lfd.Nr. Laufbahngruppen und Bes.-Gruppe Zahl der Stellen im Zahl der Stellen im Vorjahr Vermerke, Erläuterungen
Amtsbezeichnungen Haushaltsjahr 2026 insgesamt davon am 30.6.2025
insgesamt tatsächlich besetzt nicht
mit
Beamtinnen/
Beamten
mit
Arbeitnehmerinnen/
Arbeitnehmer
besetzt
1 2 3 4 5 6 7 8 9
Stadt Oldenburg
Beamte auf Zeit
1 Oberbürgermeister/-in B 8 1,00 1,00 1,00 0,00 0,00 Dienstaufwandsentschädigung gem. Nds.
KomBesVO
2 Erster Stadtrat/ Erste Stadträtin B 6 1,00 1,00 1,00 0,00 0,00 Dienstaufwandsentschädigung gem. Nds.
KomBesVO
3 Dezernent/-in B 5 2,00 2,00 1,00 0,00 1,00 Dienstaufwandsentschädigung gem. Nds.
KomBesVO
4 Stadtbaurat/-rätin B 5 1,00 1,00 1,00 0,00 0,00 Dienstaufwandsentschädigung gem. Nds.
KomBesVO
Summe Beamte auf Zeit 5,00 5,00 4,00 0,00 1,00
Laufbahngruppe 2
5 Leitende/r Baudirektor/-in A 16 3,00 3,00 1,00 2,00 0,00
6 Leitende/r Bibliotheksdirektor/-in A 16 1,00 1,00 1,00 0,00 0,00
7 Leitende/r Branddirektor/-in A 16 1,00 1,00 1,00 0,00 0,00
8 Leitende/r Medizinaldirektor/-in A 16 1,00 1,00 1,00 0,00 0,00
9 Leitende/r Städt. Direktor/-in A 16 8,00 7,00 6,00 1,00 0,00
10 Leitende/r Veterinärdirektor/-in A 16 1,00 1,00 1,00 0,00 0,00
11 Branddirektor/in A 15 1,00 1,00 1,00 0,00 0,00
12 Medizinaldirektor/-in A 15 3,00 3,00 2,00 1,00 0,00
13 Städt. Direktor/-in A 15 5,00 3,00 1,00 2,00 0,00
14 Veterinärdirektor/-in A 15 1,00 1,00 0,88 0,00 0,13
15 Bauoberrat/-rätin A 14 5,00 5,00 0,00 5,00 0,00
16 Brandoberrat/-rätin A 14 2,00 1,00 0,00 0,00 1,00
17 Städt. Oberrat/-rätin A 14 6,00 7,00 6,25 0,50 0,25
18 Vermessungsoberrat/-rätin A 14 1,00 1,00 0,00 1,00 0,00
19 Veterinäroberrat/-rätin A 14 3,00 2,00 1,00 0,00 1,00
20 Brandrat/-rätin A 13 6,00 5,00 4,85 0,00 0,15
21 Städt. Rat/ Rätin A 13 27,00 27,00 22,43 2,87 1,70
22 Bauamtsrat/-rätin A 12 1,00 1,00 0,00 0,76 0,24
Ent w u r f  2 0 2 6
1525
Stellenplan 00100 Stadt Oldenburg
Teil A: Beamtinnen und Beamte Datum: 01.01.2026
Lfd.Nr. Laufbahngruppen und Bes.-Gruppe Zahl der Stellen im Zahl der Stellen im Vorjahr Vermerke, Erläuterungen
Amtsbezeichnungen Haushaltsjahr 2026 insgesamt davon am 30.6.2025
insgesamt tatsächlich besetzt nicht
mit
Beamtinnen/
Beamten
mit
Arbeitnehmerinnen/
Arbeitnehmer
besetzt
1 2 3 4 5 6 7 8 9
23 Brandamtsrat/-rätin A 12 4,00 3,00 2,00 0,00 1,00
24 Stadtamtsrat/-rätin A 12 70,00 66,00 43,68 8,35 13,97 1,00* KU A11 nach Ende der Besetzung 2,00* KW
nach Ende der Beurlaubung
25 Archivamtmann/-frau A 11 1,00 1,00 1,00 0,00 0,00
26 Bauamtmann/-frau A 11 4,00 4,00 2,00 1,50 0,50
27 Brandamtmann/-frau A 11 28,00 27,00 23,25 0,00 3,75
28 Stadtamtmann/-frau A 11 110,00 100,00 57,55 28,24 14,21 2,00* KW nach Ende der Beurlaubung 1,00* KW
nach Ende der Freistellungsvoraussetzungen
29 Brandoberinspektor/-in A 10 9,00 8,00 7,00 0,00 1,00
30 Stadtoberinspektor/-in A 10 120,00 124,00 57,80 36,37 29,83 8,00* KW 31.12.2026 1,00* KW nach Ende der
Beurlaubung
31 Stadtinspektor/-in A 09 8,00 8,00 5,00 0,77 2,23
Summe Laufbahngruppe 2 430,00 412,00 249,69 91,36 70,96
Laufbahngruppe 1
32 Hauptbrandmeister/-in A 09 80,00 81,00 62,60 0,00 18,40
33 Hauptbrandmeister/-in mit Amtszulage A 09 8,00 8,00 7,00 0,00 1,00
34 Lebensmittelkontrollamtsinspektor/-in A 09 4,00 4,00 2,99 0,00 1,01
35 Lebensmittelkontrollamtsinspektor/-in
mit AZ
A 09 1,00 1,00 1,00 0,00 0,00
36 Stadtamtsinspektor/-in A 09 23,00 23,00 14,50 6,54 1,96 2,00* KU A8 nach Ende der Besetzung
37 Stadtamtsinspektor/-in mit Amtszulage A 09 4,00 4,00 3,63 0,00 0,38
38 Oberbrandmeister/-in A 08 58,00 58,00 45,00 0,00 13,00
39 Stadthauptsekretär/-in A 08 134,00 131,00 41,60 66,53 22,87 3,00* KW 31.12.2026
40 Brandmeister/-in A 07 17,00 17,00 16,50 0,00 0,50
41 Stadtobersekretär/-in A 07 44,00 45,00 6,35 27,44 11,21 5,00* KW 31.12.2026 1,00* KW 31.12.2032 1,00*
KW nach Ende der Beurlaubung
42 Stadtsekretär/-in A 06 7,00 7,00 1,00 4,58 1,42 1,00* KW 31.12.2026
Summe Laufbahngruppe 1 380,00 379,00 202,17 105,09 71,75
Summe Stadt Oldenburg 815,00 796,00 455,86 196,45 143,71
Summe 815,00 796,00 455,86 196,45 143,71
"""

#: Nachgebaut, nicht ausgeschnitten (s. Modulkopf): Teil B mit vier echten
#: Zeilen aus dem Plan 2025 und ihrer Summe.
TEIL_B_KLEIN = """Stellenplan 00100 Stadt Oldenburg
Teil B: Arbeitnehmerinnen und Arbeitnehmer Datum: 01.01.2025
Lfd.Nr. Funktionsbezeichnung Entgeltgruppe Zahl der Zahl der Stellen im Vorjahr Vermerke, Erläuterungen
Sondertarif Stellen im insgesamt davon am 30.6.2024
Haushaltsjahr 2025 tatsächlich
besetzt
nicht
besetzt
1 2 3 4 5 6 7 8
Beschäftigte
1 Amtsleiter/-in 15 2,00 2,00 2,00 0,00
2 Arzt/ Ärztin 15 5,00 5,00 4,18 0,82
3 Tierarzt/-ärztin 14 6,00 6,00 1,51 4,49
4 Beschäftigte/r Verwaltung 12 10,00 9,00 9,51 -0,51
Summe Beschäftigte TVöD 23,00 22,00 17,20 4,80
"""

#: Die zwei Zeilen aus dem Plan 2023, in denen sich die Stadt selbst
#: widerspricht: eine Stelle in der falschen Zeile verbucht (+1,00 hier,
#: −1,00 dort). Wörtlich aus Dokument 253355, Teil B.
UNSTIMMIGE_ZEILEN_2023 = """Stellenplan 00100 Stadt Oldenburg
Teil B: Arbeitnehmerinnen und Arbeitnehmer Datum: 01.01.2023
Lfd.Nr. Funktionsbezeichnung Entgeltgruppe Zahl der Zahl der Stellen im Vorjahr Vermerke, Erläuterungen
Sondertarif Stellen im insgesamt davon am 30.6.2022
Haushaltsjahr 2023 tatsächlich
besetzt
nicht
besetzt
1 2 3 4 5 6 7 8
Beschäftigte
34 Dipl.-Ingenieur/-in 11 79,00 75,00 52,79 23,21 1,00* KW 31.12.2023
40 Verw.-Angest. 11 36,00 29,00 23,04 4,96
Summe Beschäftigte TVöD 115,00 104,00 75,83 28,17
"""


def _anlage(store: CouncilStore, text: str, document_id: int = 297432,
            label: str = "2026 022 Vw Stellenplan Haushalt 2026 Verwaltungsentwurf",
            ) -> None:
    """Ein Stellenplan als Anlage im Bestand — so, wie ihn der
    Protokoll-Scraper ablegt."""
    store._conn.execute(
        "INSERT OR REPLACE INTO council_anlagen (document_id, kvonr, label, url, "
        " raw_text, n_pages, fetched_at) VALUES (?,?,?,?,?,?,?)",
        (document_id, 1, label, f"https://example.org/{document_id}.pdf",
         text, 20, "2026-08-16"))
    store._conn.commit()


def _teil(text: str, name: str = "A") -> dict:
    return next(t for t in sp.lies(text)["teile"] if t["teil"] == name)


def _gesamt(teil: dict) -> dict:
    return next(z for z in teil["zeilen"] if z["art"] == "gesamt")


# --- 1. Wem die unbesetzten Stellen gehören ---------------------------------

def test_besetzung_gehoert_zum_stichtag_nicht_zum_haushaltsjahr():
    """Die eine Verwechslung, die eine Lücke erfindet, die es nicht gibt.

    Der Plan 2026 sieht 815 Stellen vor. Unbesetzt waren 143,71 — von den
    796 Stellen des Vorjahres, gezählt am 30.6.2025. 815 − 652,31 wäre
    162,69 und damit eine Zahl, die in keinem Dokument steht."""
    g = _gesamt(_teil(STELLENPLAN_2026_A))
    assert g["stellen_plan"] == 815.00
    assert g["positions_prior_year"] == 796.00
    assert g["nicht_besetzt"] == 143.71
    assert g["besetzt"] == pytest.approx(652.31)
    # Die Rechnung geht gegen das Vorjahr auf — und gegen das Planjahr nicht.
    assert g["besetzt"] + g["nicht_besetzt"] == pytest.approx(796.00, abs=0.05)
    assert abs(g["besetzt"] + g["nicht_besetzt"] - g["stellen_plan"]) > 18


def test_stichtag_steht_an_der_zeile():
    """Ohne ihn ist „143,71 unbesetzt" eine Zahl ohne Datum."""
    assert _teil(STELLENPLAN_2026_A)["as_of_date"] == "2025-06-30"


def test_teil_a_trennt_beamte_und_tarifbeschaeftigte():
    """Eine Beamtenstelle darf mit Tarifbeschäftigten besetzt werden — der
    Plan weist das getrennt aus, und beides zusammen ist die Besetzung."""
    g = _gesamt(_teil(STELLENPLAN_2026_A))
    assert g["besetzt_beamte"] == 455.86
    assert g["besetzt_arbeitnehmer"] == 196.45
    assert g["besetzt"] == pytest.approx(455.86 + 196.45)


# --- 2. Was der Textextrakt an Fallen stellt --------------------------------

def test_der_seitenwechsel_verdoppelt_keine_zeile():
    """Kopf und Spaltennummern stehen auf jeder Seite noch einmal. Sie dürfen
    weder als Daten noch als zweiter Teil A durchgehen."""
    teil = _teil(STELLENPLAN_2026_A)
    posten = [z for z in teil["zeilen"] if z["art"] == "posten"]
    assert len(posten) == 42
    assert [z["seq_no"] for z in posten] == list(range(1, 43))


def test_ueber_drei_zeilen_umbrochener_name_bleibt_eine_zeile():
    """Nr. 35 steht im Extrakt als „Lebensmittelkontrollamtsinspektor/-in" /
    „mit AZ" / „A 09 1,00 …" — drei Zeilen, ein Datensatz."""
    z = next(z for z in _teil(STELLENPLAN_2026_A)["zeilen"] if z["seq_no"] == 35)
    assert z["label"] == "Lebensmittelkontrollamtsinspektor/-in mit AZ"
    assert z["besoldung"] == "A 09"
    assert z["stellen_plan"] == 1.00


def test_vermerke_erzeugen_keine_phantomzeile():
    """Hinter Nr. 24 steht „1,00* KU A11 nach Ende der Besetzung 2,00* KW" —
    eine Zahl, ein Buchstabe-Zahl-Paar und ein Umbruch. Nichts davon ist eine
    Zeile, und nichts davon gehört in die Bezeichnung der nächsten."""
    zeilen = {z["seq_no"]: z for z in _teil(STELLENPLAN_2026_A)["zeilen"]}
    assert zeilen[24]["label"] == "Stadtamtsrat/-rätin"
    assert zeilen[24]["nicht_besetzt"] == 13.97
    assert zeilen[25]["label"] == "Archivamtmann/-frau"


def test_die_ausbildungstabelle_wird_nicht_mitgelesen():
    """Im selben PDF folgt „Dienstkräfte in der Ausbildungszeit": sechs
    Spalten, keine Besetzung, keine Summenzeile. Ihre Zeilen sehen einer
    Stellenzeile ähnlich genug, um mitgelesen zu werden — und wären dann
    Stellen, die niemand geplant hat."""
    text = STELLENPLAN_2026_A + """Dienstkräfte in der Ausbildungszeit
I. Nachwuchskräfte und informatorisch beschäftigte Kräfte im Stellenplan 2026
1 2 3 4 5 6
1 Bachelor "Bauingenieurwesen" Studienrichtlinie TVöD-V 1,00 1,00
2 Bachelor "Öffentliche Verwaltung" Praktikumsvergütung/Stipendium 9,00 11,00
"""
    teil = _teil(text)
    assert teil["bestanden"] is True
    assert teil["verworfen"] == 0
    assert _gesamt(teil)["stellen_plan"] == 815.00
    assert not [z for z in teil["zeilen"] if "Bachelor" in z["label"]]


# --- 3. Die Proben ----------------------------------------------------------

def test_alle_vier_proben_gehen_auf():
    teil = _teil(STELLENPLAN_2026_A)
    assert teil["bestanden"] is True
    assert [p["probe"] for p in teil["probes"]] == [
        "stellenplan_spaltenprobe", "stellenplan_gruppensummen",
        "stellenplan_besetzung", "stellenplan_gesamtsumme"]
    assert all(p["probe"] in herkunft.PROBEN for p in teil["probes"])


def test_teil_b_traegt_drei_proben_statt_vier():
    """Teil B hat eine Gruppe, deren Summe zugleich die Gesamtsumme ist. Eine
    vierte Probe zu behaupten hieße, dieselbe Rechnung zweimal zu zählen."""
    teil = _teil(TEIL_B_KLEIN, "B")
    assert teil["bestanden"] is True
    assert [p["probe"] for p in teil["probes"]] == [
        "stellenplan_spaltenprobe", "stellenplan_gruppensummen",
        "stellenplan_besetzung"]
    g = _gesamt(teil)
    assert g["stellen_plan"] == 23.00
    # Teil B kennt die Aufteilung der Besetzung nicht.
    assert g.get("besetzt_beamte") is None


def test_ueberbesetzung_bleibt_negativ():
    """„nicht besetzt −0,51" heißt: mehr Menschen als Stellen. Das ist eine
    Angabe des Plans und keine Fehlmessung — sie darf nicht auf 0 fallen."""
    z = next(z for z in _teil(TEIL_B_KLEIN, "B")["zeilen"] if z["seq_no"] == 4)
    assert z["nicht_besetzt"] == -0.51


def test_andere_spaltenzahl_wird_gar_nicht_erst_gelesen():
    """Die Spaltenprobe ist das Eintrittsbillett: Nennt die Tabelle acht
    Spalten, wo Teil A neun hat, ist es ein anderes Dokument — und die
    Bedeutung jeder Spalte wäre geraten."""
    text = STELLENPLAN_2026_A.replace("1 2 3 4 5 6 7 8 9", "1 2 3 4 5 6 7 8")
    teil = _teil(text)
    assert teil["bestanden"] is False
    assert teil["zeilen"] == []
    assert "Spalten" in teil["nachweis"]


def test_gerissene_gruppensumme_verwirft_den_ganzen_teil():
    text = STELLENPLAN_2026_A.replace(
        "Summe Laufbahngruppe 2 430,00 412,00 249,69 91,36 70,96",
        "Summe Laufbahngruppe 2 431,00 412,00 249,69 91,36 70,96")
    teil = _teil(text)
    assert teil["bestanden"] is False
    assert teil["zeilen"] == []
    assert "Laufbahngruppe 2" in teil["nachweis"]


def test_gerissene_gesamtsumme_verwirft_den_ganzen_teil():
    """Der Plan nennt die Gesamtzeile zweimal. Weicht die zweite ab, ist die
    Tabelle nicht mehr in sich stimmig — dann gibt es keine halben Zahlen."""
    text = STELLENPLAN_2026_A.replace(
        "Summe 815,00 796,00 455,86 196,45 143,71",
        "Summe 820,00 796,00 455,86 196,45 143,71")
    teil = _teil(text)
    assert teil["bestanden"] is False
    assert teil["zeilen"] == []


def test_besetzung_gegen_die_falsche_spalte_reisst_die_probe():
    """Die Probe, die das eigentliche Missverständnis fängt: Stünde in der
    Vorjahresspalte das Planjahr, ginge besetzt + nicht besetzt nicht mehr
    auf — hier um 19 Stellen daneben, weit jenseits jeder Rundung."""
    ok, warum = sp.besetzungsprobe([{
        "positions_prior_year": 815.00, "besetzt": 652.31,
        "nicht_besetzt": 143.71, "name": "Stadt Oldenburg", "zeilen": 42}])
    assert ok is False
    assert "-19.0" in warum or "-18.9" in warum


def test_die_toleranz_waechst_mit_der_zeilenzahl():
    """Der Plan rundet jede Zeile auf zwei Nachkommastellen; die Reste
    addieren sich in die Summenzeile. Ein fester Wert wäre genau falsch herum
    streng — er ginge bei vier Zeilen durch und schlüge bei 140 zu."""
    assert sp.besetzungstoleranz(4) == pytest.approx(sp.TOLERANZ)
    assert sp.besetzungstoleranz(143) == pytest.approx(1.43)


# --- 4. Wenn der Plan sich selbst widerspricht ------------------------------

def test_widerspruechliche_zeilen_werden_gekennzeichnet_nicht_verworfen():
    """Der Stellenplan 2023 verbucht eine Stelle in der falschen Zeile: bei
    „Dipl.-Ingenieur/-in E 11" eine zu viel, bei „Verw.-Angest. E 11" eine zu
    wenig. In der Gruppensumme heben sich beide auf.

    Ein Gate auf jeder Einzelzeile risse dafür einen Teil mit 140 Zeilen und
    1.643 Stellen ein — wegen eines Übertrags, den das Dokument selbst wieder
    geraderückt. Gespeichert wird deshalb, was im Plan steht, mit einer
    Markierung daneben."""
    teil = _teil(UNSTIMMIGE_ZEILEN_2023, "B")
    assert teil["bestanden"] is True
    assert [u["seq_no"] for u in teil["unstimmig"]] == [34, 40]
    assert [u["deviation"] for u in teil["unstimmig"]] == [1.0, -1.0]

    posten = {z["seq_no"]: z for z in teil["zeilen"] if z["art"] == "posten"}
    assert posten[34]["consistent"] == 0
    assert posten[40]["consistent"] == 0
    # Und der Wert selbst bleibt der des Dokuments — nicht zurechtgerechnet.
    assert posten[34]["besetzt"] == 52.79
    assert _gesamt(teil)["consistent"] == 1


def test_ein_stimmiger_jahrgang_meldet_keine_ausreisser():
    assert _teil(STELLENPLAN_2026_A)["unstimmig"] == []


# --- 5. Ein Jahrgang kann halb hereinkommen ---------------------------------

def test_fehlender_teil_b_wird_als_glyphensalat_erkannt():
    """Im Stellenplan 2026 steht Teil B im PDF, liefert im Textextrakt aber
    Glyphen-Nummern statt Buchstaben. Das ist etwas anderes als „gibt es
    nicht" — und nur mit diesem Unterschied lässt sich sagen, warum die
    Tarifstellen für 2026 fehlen."""
    text = STELLENPLAN_2026_A + (
        "/0 /1 /2 /3 /3 /2 /4 /5 /3 /6 /4 /i255 /0 /1 /6 /10 /1 /i255 /11 /3\n")
    gelesen = sp.lies(text)
    assert gelesen["glyphen"] is True
    assert [t["teil"] for t in gelesen["teile"]] == ["A"]


def test_einheit_ist_der_teil_nicht_der_jahrgang(tmp_path):
    """Ein Jahrgang mit nur einem Teil darf nicht als fertig gelten — sonst
    zöge ihn kein Lauf je nach."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, STELLENPLAN_2026_A)
    finanzquellen.lies_stellenplaene(store, finanzquellen.Protokoll(still=True))

    assert store.stellenplan_einheiten() == {(2026, "A")}
    offen = finanzquellen.QUELLEN["stellenplan"].offene_einheiten(store)
    assert offen == {(2026, "B")}
    store.close()


# --- 6. Einlesen, Herkunft, Bestandsschutz ----------------------------------

def test_jede_zeile_weiss_woher_sie_kommt(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, STELLENPLAN_2026_A)
    finanzquellen.lies_stellenplaene(store, finanzquellen.Protokoll(still=True))

    assert store.herkunft_luecken() == {}
    zeilen = store.get_stellenplan()
    assert zeilen and all(z["herkunft_id"] for z in zeilen)

    quelle = store.get_herkunft([zeilen[0]["herkunft_id"]])[0]
    assert quelle["document_id"] == 297432
    assert quelle["citation"] == "Teil A: Beamtinnen und Beamte"
    # Es ist der Verwaltungsentwurf, nicht der Beschluss — und die Besetzung
    # hat einen Stichtag. Beides muss der Beleg sagen können.
    assert "Stand der Einbringung" in quelle["stand"]
    assert "2025-06-30" in quelle["stand"]
    assert quelle["probe"].startswith("stellenplan_spaltenprobe")
    store.close()


def test_die_summen_kommen_aus_dem_dokument_nicht_aus_unserer_addition(tmp_path):
    """Auf der Seite soll die Zahl der Stadt stehen. Sie steht deshalb als
    eigene Zeile in der Tabelle, mit derselben Herkunft wie die Posten."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, STELLENPLAN_2026_A)
    finanzquellen.lies_stellenplaene(store, finanzquellen.Protokoll(still=True))

    summen = store.get_stellenplan(art="gesamt")
    assert len(summen) == 1
    assert summen[0]["stellen_plan"] == 815.0
    assert [g["gruppe"] for g in store.get_stellenplan(art="gruppe")] == [
        "Beamte auf Zeit", "Laufbahngruppe 2", "Laufbahngruppe 1"]
    store.close()


def test_ingest_liest_ein_und_tut_beim_zweiten_mal_nichts(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, STELLENPLAN_2026_A)
    p = finanzquellen.Protokoll(still=True)
    erst = finanzquellen.lies_stellenplaene(store, p, nur_fehlende=True)
    assert erst["neue_einheiten"] == [(2026, "A")]

    zweit = finanzquellen.lies_stellenplaene(store, p, nur_fehlende=True)
    assert zweit["neue_einheiten"] == []
    assert len(store.get_stellenplan()) == len(store.get_stellenplan())
    store.close()


def test_ein_gerissener_teil_laesst_den_bestand_stehen(tmp_path):
    """Ändert die Stadt ihr Layout, liefert der Parser irgendwann nichts. Das
    darf einen gefüllten Jahrgang nicht ersetzen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, STELLENPLAN_2026_A)
    p = finanzquellen.Protokoll(still=True)
    finanzquellen.lies_stellenplaene(store, p)
    vorher = store.get_stellenplan()

    _anlage(store, STELLENPLAN_2026_A.replace(
        "Summe 815,00 796,00 455,86 196,45 143,71",
        "Summe 820,00 796,00 455,86 196,45 143,71"))
    finanzquellen.lies_stellenplaene(store, p)
    assert store.get_stellenplan() == vorher
    store.close()


def test_geaenderter_stellenplan_bleibt_draussen(tmp_path):
    """Der „Geänderte Stellenplan Teil B" von 2021 besteht seine Proben — und
    gehört trotzdem nicht in die Reihe: Er ist eine Änderung des Plans statt
    des eingebrachten Plans und trägt nur Teil B. Ein Jahr, das nur die
    Tarifhälfte zeigt, läse sich wie ein Jahr ohne Beamtenstellen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, TEIL_B_KLEIN, document_id=210792,
            label="Geänderter Stellenplan Teil B - Arbeitnehmerinnen und Arbeitnehmer")
    finanzquellen.lies_stellenplaene(store, finanzquellen.Protokoll(still=True))
    assert store.get_stellenplan() == []
    store.close()


def test_jahrgang_kommt_aus_dem_kopf_nicht_aus_dem_label():
    """Die vier Dokumente heißen „022 2023 Stellenplan", „2024 021 IVw
    Stellenplan", „2025 022 Vw Stellenplan Haushalt 2025 …" — drei
    Schreibweisen, und eine trägt zwei Jahreszahlen. Der Tabellenkopf sagt es
    einmal und eindeutig."""
    assert sp.budget_year(STELLENPLAN_2026_A) == 2026
    assert sp.budget_year("2024 021 IVw Stellenplan") is None
