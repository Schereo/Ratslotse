"""Städtevergleich aus den Tabellen des Landesamts für Statistik Niedersachsen.

Die Fixtures sind **echte, gekürzte Ausschnitte** aus den beiden geprüften
LSN-Dateien (KFA 2025/2026, ``/download/216492`` und ``/download/227086``;
Realsteuervergleich 2025, ``/download/230730``) — dieselben Zeilennummern,
dieselben Spaltenköpfe, dieselben Zahlen. Gebaut werden sie als **richtige
XLSX-Mappen** (ZIP + XML mit ``sharedStrings``), damit der Leser dieses
Projekts mitgeprüft wird und nicht nur die Auswertung darüber.

Jede Eigenheit, an der ein naiver Parser scheitert, steckt in mindestens
einem Fall:

- Der Städtename **wechselt** zwischen den Jahrgängen (``Oldenburg (Oldb),
  Stadt`` → ``Oldenburg (Oldenburg), Stadt``) — verbunden wird über die
  Schlüsselnummer.
- Die Schlüsselnummer steht in den beiden Quellen **verschieden lang**
  (``403000`` gegen ``403``).
- Zwischen den Datenzeilen stehen Zwischenüberschriften („Statistische Region
  Braunschweig") und Summenzeilen, die keine Stadt sind.
- Die Gewerbesteuer steht dreimal da (brutto, Umlage, netto). Die Rechenprobe
  gilt für **brutto**, angezeigt wird **netto** — der Fall, der beim Bauen
  tatsächlich alle acht Städte verworfen hat, ist als eigener Test drin.
- Die Grundsteuer A ist so klein (13–44 T€), dass die Rundung auf volle
  Tausend Euro 1–3 % ausmacht. Eine feste Prozentschranke verwürfe sie.
"""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape

import pytest

from council import herkunft, staedtevergleich as sv
from council.store import CouncilStore

# --- Eine echte XLSX-Mappe bauen -------------------------------------------


def _spaltenname(i: int) -> str:
    name = ""
    i += 1
    while i:
        i, rest = divmod(i - 1, 26)
        name = chr(65 + rest) + name
    return name


def schreibe_xlsx(pfad, blaetter: dict[str, dict[int, list]]) -> str:
    """``{Blattname: {Zeilennummer: [Werte]}}`` → echte XLSX-Datei.

    Lässt Zeilen und Zellen bewusst **aus**, wo nichts steht — genau so
    speichert Excel, und genau daran verrutscht ein Parser, der Zeilen
    abzählt statt sie zu lesen.
    """
    texte: list[str] = []
    index: dict[str, int] = {}

    def text_id(value: str) -> int:
        if value not in index:
            index[value] = len(texte)
            texte.append(value)
        return index[value]

    blatt_xml: dict[str, str] = {}
    for name, zeilen in blaetter.items():
        teile = []
        for nr in sorted(zeilen):
            zellen = []
            for i, value in enumerate(zeilen[nr]):
                if value is None or value == "":
                    continue
                ref = f"{_spaltenname(i)}{nr}"
                if isinstance(value, (int, float)):
                    zellen.append(f'<c r="{ref}"><v>{value}</v></c>')
                else:
                    zellen.append(
                        f'<c r="{ref}" t="s"><v>{text_id(str(value))}</v></c>')
            teile.append(f'<row r="{nr}">{"".join(zellen)}</row>')
        blatt_xml[name] = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(teile)}</sheetData></worksheet>')

    pfad = str(pfad)
    with zipfile.ZipFile(pfad, "w") as z:
        sheets, rels = [], []
        for n, name in enumerate(blatt_xml, start=1):
            sheets.append(
                f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>')
            rels.append(
                f'<Relationship Id="rId{n}" Target="worksheets/sheet{n}.xml" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/worksheet"/>')
            z.writestr(f"xl/worksheets/sheet{n}.xml", blatt_xml[name])
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(sheets)}</sheets></workbook>')
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            f'relationships">{"".join(rels)}</Relationships>')
        z.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + "".join(f"<si><t>{escape(t)}</t></si>" for t in texte) + "</sst>")
    return pfad


# --- Fixtures: Kommunaler Finanzausgleich ----------------------------------

_KFA_KOPF = [
    "Schlüsselnummer der Kreisfreien Stadt, Gemeinde und Samtgemeinde",
    "Bezeichnung der Kreisfreien Stadt, Gemeinde und Samtgemeinde",
    "Einwohnerzahl1) vom 30.06.{ew}",
    "Steuerkraftmesszahlen {vor}, Beträge in 1000 Euro",
    "Steuerkraftmesszahlen {year}, Beträge in 1000 Euro",
    "Abweichung Steuerkraftmesszahlen {year} abzüglich Steuerkraftmesszahlen {vor}",
    "Relative Zu- und Abnahme der Steuerkraftmesszahl {year} gegenüber {vor}",
]

#: Wörtlich aus KFA 2026, Blatt ST_KR_MESS_VGL: die acht kreisfreien Städte,
#: dazu zwei kreisangehörige Gemeinden als Beifang (sie stehen in derselben
#: Tabelle und dürfen NICHT in den Städtevergleich geraten).
KFA2026_ZEILEN = [
    (101000, "Braunschweig, Stadt", 253016, 403161, 384070),
    (102000, "Salzgitter, Stadt", 104755, 113280, 109666),
    (103000, "Wolfsburg, Stadt", 129339, 314959, 233702),
    (151009, "Gifhorn, Stadt *", 42788, 50462, 53025),
    (401000, "Delmenhorst, Stadt", 81247, 66096, 77099),
    (402000, "Emden, Stadt", 49125, 76955, 74287),
    (403000, "Oldenburg (Oldenburg), Stadt", 176410, 325716, 348164),
    (404000, "Osnabrück, Stadt", 165727, 256877, 273609),
    (405000, "Wilhelmshaven, Stadt", 75190, 81009, 99674),
    (451002, "Bad Zwischenahn *", 29102, 30215, 31877),
]

#: Derselbe Ausschnitt aus KFA 2025. Die Hauptspalte (2025) muss die
#: Vorjahresspalte von 2026 reproduzieren — das ist die Probe. Oldenburg
#: heißt hier noch anders.
KFA2025_ZEILEN = [
    (101000, "Braunschweig, Stadt", 252824, 404439, 403161),
    (102000, "Salzgitter, Stadt", 105121, 133931, 113280),
    (103000, "Wolfsburg, Stadt", 129443, 402284, 314959),
    (151009, "Gifhorn, Stadt *", 42706, 47008, 50462),
    (401000, "Delmenhorst, Stadt", 81232, 63236, 66096),
    (402000, "Emden, Stadt", 49443, 82022, 76955),
    (403000, "Oldenburg (Oldb), Stadt", 176336, 279816, 325716),
    (404000, "Osnabrück, Stadt", 165526, 255019, 256877),
    (405000, "Wilhelmshaven, Stadt", 75909, 75851, 81009),
    (451002, "Bad Zwischenahn", 29050, 28914, 30215),
]


def _kfa_blatt(year: int, zeilen: list[tuple]) -> dict[int, list]:
    vor = year - 1
    kopf = [t.format(year=year, vor=vor, ew=vor) for t in _KFA_KOPF]
    blatt: dict[int, list] = {
        1: ["Kommunaler Finanzausgleich"],
        2: [f"Stand: 26.03.{year}"],
        # Der Zeiger auf die Vorlesehilfe — er ist die einzige Angabe, aus der
        # der Parser die Kopfzeile ermittelt.
        3: ["Der Tabellenkopf für Vorlesehilfen befindet sich in Zeile 14."],
        13: [None, None, None, "Beträge in 1.000 EUR", None, None, "%"],
        14: kopf,
    }
    for i, (key, name, ew, v, c) in enumerate(zeilen):
        blatt[15 + i] = [key, name, ew, v, c, c - v, round((c - v) / v * 100, 1)]
    return blatt


@pytest.fixture
def kfa2026(tmp_path):
    return schreibe_xlsx(tmp_path / "kfa2026.xlsx",
                         {"ST_KR_MESS_VGL": _kfa_blatt(2026, KFA2026_ZEILEN)})


@pytest.fixture
def kfa2025(tmp_path):
    return schreibe_xlsx(tmp_path / "kfa2025.xlsx",
                         {"ST_KR_MESS_VGL": _kfa_blatt(2025, KFA2025_ZEILEN)})


# --- Fixtures: Realsteuervergleich -----------------------------------------

_RS_KOPF_2_1 = ["Schlüsselnummer", "Kreisfreie Stadt Landkreisbereich (LKB)"]
for _steuer in ("Grundsteuer A", "Grundsteuer B"):
    _RS_KOPF_2_1 += [
        f"{_steuer}; Grundbetrag; in 1000 EUR",
        f"{_steuer}; Grundbetrag; EUR je Einwohner/-in",
        f"{_steuer}; Hebesatz; in %",
        f"{_steuer}; Ist-Aufkommen; in 1000 EUR",
        f"{_steuer}; Ist-Aufkommen; EUR je Einwohner/-in",
    ]
_RS_KOPF_2_1 += [
    "Gewerbesteuer; Grundbetrag; in 1000 EUR",
    "Gewerbesteuer; Grundbetrag; EUR je Einwohner/-in",
    "Gewerbesteuer; Hebesatz; in %",
    "Gewerbesteuer; Ist-Aufkommen brutto; in 1000 EUR",
    "Gewerbesteuer; Ist-Aufkommen brutto; EUR je Einwohner/-in",
    "Gewerbesteuer; Gewerbesteuerumlage1); in 1000 EUR",
    "Gewerbesteuer; Gewerbesteuerumlage1); EUR je Einwohner/-in",
    "Gewerbesteuer; Ist-Aufkommen netto; in 1000 EUR",
    "Gewerbesteuer; Ist-Aufkommen netto; EUR je Einwohner/-in",
]

#: Wörtlich aus Blatt 2_1: Schlüssel, Name, dann je Steuer Grundbetrag,
#: Grundbetrag/EW, Hebesatz, Ist, Ist/EW — Gewerbesteuer mit brutto, Umlage,
#: netto.
RS_2_1 = {
    101: ["Braunschweig, Stadt", 41, 0.16, 400, 166, 0.66, 8514, 33.65, 750,
          63854, 252.37, 41679, 164.73, 450, 187555, 741.28, 13529, 53.47,
          174026, 687.81],
    401: ["Delmenhorst, Stadt", 13, 0.16, 557, 72, 0.89, 2647, 32.58, 557,
          14746, 181.49, 8539, 105.1, 435, 37144, 457.18, 3219, 39.62,
          33925, 417.56],
    403: ["Oldenburg (Oldb), Stadt", 13, 0.07, 500, 63, 0.36, 6027, 34.17, 539,
          32488, 184.16, 53740, 304.63, 439, 235920, 1337.34, 18343, 103.98,
          217576, 1233.36],
    404: ["Osnabrück, Stadt", 22, 0.14, 350, 79, 0.47, 6334, 38.22, 545,
          34520, 208.3, 36589, 220.78, 440, 160994, 971.44, 12460, 75.18,
          148534, 896.26],
}

#: Blatt 5_1 wörtlich — samt der beiden ``x`` bei Braunschweig, mit denen das
#: LSN „nicht anwendbar" schreibt. Sie müssen als Text durchlaufen, ohne den
#: Leser zu stören.
RS_5_1 = {
    101: ["Braunschweig, Stadt", 252559, 435722, 1730.18, 414132, 1638.03,
          405092, 1601.05, 418315, 1656.31, "x", "x"],
    401: ["Delmenhorst, Stadt", 80358, 77157, 981.71, 78841, 970.57,
          84474, 1039.72, 80157, 997.51, 1539.25, -35.2],
    403: ["Oldenburg (Oldb), Stadt", 175402, 290272, 1673.43, 342896, 1944.56,
          358758, 2033.66, 330642, 1885.05, 1786.24, 5.5],
    404: ["Osnabrück, Stadt", 165898, 263731, 1584.54, 270373, 1633.42,
          284091, 1714.21, 272732, 1643.97, 1863.03, -11.8],
}

_RS_KOPF_5_1 = [
    "Schlüsselnummer", "Kreisfreie Stadt Landkreisbereich (LKB)",
    "Durchschnittliche Zahl der Einwohner/-innen der Jahre 2023, 2024, 2025; Anzahl",
    "Steuereinnahmekraft; Jahr 2023; in 1000 EUR",
    "Steuereinnahmekraft; Jahr 2023; EUR je Einwohner/-in",
    "Steuereinnahmekraft; Jahr 2024; in 1000 EUR",
    "Steuereinnahmekraft; Jahr 2024; EUR je Einwohner/-in",
    "Steuereinnahmekraft; Jahr 2025; in 1000 EUR",
    "Steuereinnahmekraft; Jahr 2025; EUR je Einwohner/-in",
    "Steuereinnahmekraft; Dreijahresdurchschnitt; in 1000 EUR",
    "Steuereinnahmekraft; Dreijahresdurchschnitt; EUR je Einwohner/-in",
    "Vergleichswert Steuereinnahmekraft; EUR je Einwohner/-in",
    "Abweichung von Vergleichswert; in %",
]


def _rs_blatt(kopf: list[str], daten: dict[int, list]) -> dict[int, list]:
    blatt: dict[int, list] = {
        1: ["Zum Inhaltsverzeichnis"],
        2: ["2.1 Grundbeträge, Hebesätze und Ist-Aufkommen"],
        3: ["Der Tabellenkopf für Vorlesehilfen befindet sich in Zeile 7."],
        7: kopf,
        # Eine Zwischenüberschrift mitten im Bestand: keine Zahl in Spalte 1.
        8: ["Statistische Region Braunschweig"],
    }
    nr = 9
    for key, werte in daten.items():
        blatt[nr] = [key, *werte]
        nr += 1
    # Eine Summenzeile der Region — sie trägt eine Zahl in Spalte 1 (1) und
    # darf trotzdem nicht als Stadt gelesen werden.
    blatt[nr] = [1, "Statistische Region Braunschweig total"]
    return blatt


def _realsteuer_mappe(tmp_path, name="realsteuer.xlsx", zwei_eins=None):
    return schreibe_xlsx(tmp_path / name, {
        "Titel": {5: ["Realsteuervergleich 2025\n\nKorrigierte Version vom 30.07.2026"]},
        "2_1": _rs_blatt(_RS_KOPF_2_1, zwei_eins if zwei_eins is not None else RS_2_1),
        "5_1": _rs_blatt(_RS_KOPF_5_1, RS_5_1),
    })


@pytest.fixture
def realsteuer(tmp_path):
    return _realsteuer_mappe(tmp_path)


# --- Der Leser --------------------------------------------------------------

def test_schluessel_normalisieren_bringt_beide_schreibweisen_zusammen():
    """Ohne das fänden die zwei Quellen einander nie — und zwar lautlos."""
    assert sv.schluessel_normalisieren(403) == "403000"
    assert sv.schluessel_normalisieren("403") == "403000"
    assert sv.schluessel_normalisieren(403000) == "403000"
    assert sv.schluessel_normalisieren("403000.0") == "403000"
    assert sv.schluessel_normalisieren("Statistische Region Braunschweig") is None
    assert sv.schluessel_normalisieren(None) is None


def test_doctype_wird_abgelehnt(tmp_path):
    """Eine Mappe mit Dokumenttyp-Deklaration lesen wir gar nicht erst."""
    pfad = tmp_path / "boese.xlsx"
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr("xl/workbook.xml",
                   '<!DOCTYPE x [<!ENTITY a "aaa">]><workbook/>')
        z.writestr("xl/_rels/workbook.xml.rels", "<Relationships/>")
    with pytest.raises(ValueError, match="Dokumenttyp"):
        sv.blatt_lesen(str(pfad), "ST_KR_MESS_VGL")


def test_kfa_liest_die_acht_staedte(kfa2026):
    budget_year = sv.lies_kfa(kfa2026)
    assert (budget_year.year, budget_year.prior_year) == (2026, 2025)
    assert budget_year.as_of == "26.03.2026"
    # Alle Gemeinden der Datei, nicht nur die Städte: Die Überlappungsprobe
    # ist nur dann etwas wert, wenn sie über den ganzen Bestand läuft.
    assert len(budget_year.staedte) == len(KFA2026_ZEILEN)
    ol = budget_year.staedte["403000"]
    assert ol["tax_index_keur"] == 348164
    assert ol["population"] == 176410
    assert ol["prior_year_tax_index_keur"] == 325716


def test_kfa_findet_die_kopfzeile_ueber_den_hinweis_der_datei(tmp_path):
    """Der Kopf steht nicht immer in Zeile 14 — die Datei sagt, wo er steht.

    Hier rutscht er auf 17 (als hätte das LSN drei Fußnoten eingefügt). Ein
    Parser mit fester Zeilennummer läse dann Einheiten statt Spaltennamen.
    """
    blatt = _kfa_blatt(2026, KFA2026_ZEILEN)
    verschoben = {(nr + 3 if nr >= 13 else nr): werte
                  for nr, werte in blatt.items()}
    verschoben[3] = ["Der Tabellenkopf für Vorlesehilfen befindet sich in Zeile 17."]
    pfad = schreibe_xlsx(tmp_path / "verschoben.xlsx", {"ST_KR_MESS_VGL": verschoben})
    assert sv.lies_kfa(pfad).staedte["403000"]["tax_index_keur"] == 348164


def test_kfa_ohne_hinweis_bricht_ab_statt_zu_raten(tmp_path):
    blatt = _kfa_blatt(2026, KFA2026_ZEILEN)
    blatt[3] = ["Irgendein anderer Hinweis"]
    pfad = schreibe_xlsx(tmp_path / "ohne.xlsx", {"ST_KR_MESS_VGL": blatt})
    with pytest.raises(ValueError, match="Vorlesehilfe"):
        sv.lies_kfa(pfad)


def test_ueberlappungsprobe_geht_ueber_alle_gemeinden_auf(kfa2025, kfa2026):
    probe = sv.probe_ueberlappung(sv.lies_kfa(kfa2025), sv.lies_kfa(kfa2026))
    assert probe["ok"]
    assert probe["geprueft"] == len(KFA2026_ZEILEN)
    assert "10 von 10" in probe["result"]


def test_ueberlappungsprobe_schlaegt_an_wenn_ein_wert_abweicht(tmp_path, kfa2026):
    """Der Fall, für den es die Probe gibt: eine still geänderte Zahl."""
    manipuliert = [(k, n, e, v, c if k != 404000 else c + 7)
                   for k, n, e, v, c in KFA2025_ZEILEN]
    pfad = schreibe_xlsx(tmp_path / "kaputt.xlsx",
                         {"ST_KR_MESS_VGL": _kfa_blatt(2025, manipuliert)})
    probe = sv.probe_ueberlappung(sv.lies_kfa(pfad), sv.lies_kfa(kfa2026))
    assert not probe["ok"]
    assert [a["key"] for a in probe["abweichungen"]] == ["404000"]


def test_ueberlappungsprobe_verlangt_aneinandergrenzende_jahrgaenge(kfa2026):
    """Zwei Ausgaben desselben Jahres greifen nicht ineinander."""
    with pytest.raises(ValueError, match="greifen nicht ineinander"):
        sv.probe_ueberlappung(sv.lies_kfa(kfa2026), sv.lies_kfa(kfa2026))


def test_steuerkraft_zeilen_nur_kreisfreie_staedte_und_ohne_pro_kopf(kfa2026):
    zeilen = sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026))
    key = {z["key"] for z in zeilen}
    assert key == set(sv.KREISFREIE_STAEDTE)
    assert "151009" not in key   # Gifhorn ist kreisangehörig
    # Der Pro-Kopf-Wert ist UNSERE Division und wird deshalb nicht gespeichert.
    assert {z["indicator"] for z in zeilen} == {"steuerkraftmesszahl", "population"}
    assert all(z["year"] == 2026 for z in zeilen)
    # Der Name kommt aus unserer Liste, nicht aus der Datei — sonst wechselte
    # er mit dem Jahrgang mit.
    assert {z["city"] for z in zeilen if z["key"] == "403000"} == {"Oldenburg"}


def test_steuerkraft_je_einwohner_ergibt_die_veroeffentlichten_werte(kfa2026):
    """Die Zahl, die die Seite trägt: Oldenburg ist Erster von acht."""
    zeilen = sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026))
    je_stadt: dict[str, dict] = {}
    for z in zeilen:
        je_stadt.setdefault(z["city"], {})[z["indicator"]] = z["value"]
    je_ew = {stadt: w["steuerkraftmesszahl"] * 1000 / w["population"]
             for stadt, w in je_stadt.items()}
    assert je_ew["Oldenburg"] == pytest.approx(1973.61, abs=0.01)
    assert je_ew["Osnabrück"] == pytest.approx(1650.96, abs=0.01)
    assert je_ew["Braunschweig"] == pytest.approx(1517.97, abs=0.01)
    assert je_ew["Delmenhorst"] == pytest.approx(948.95, abs=0.01)
    assert max(je_ew, key=je_ew.get) == "Oldenburg"


# --- Realsteuervergleich ----------------------------------------------------

def test_realsteuervergleich_liest_hebesaetze_und_einnahmekraft(realsteuer):
    rs = sv.lies_realsteuervergleich(realsteuer)
    assert rs.year == 2025
    assert rs.as_of == "Korrigierte Version vom 30.07.2026"
    ol = rs.tax_rates["403000"]
    assert (ol["rate_grundsteuer_a"], ol["rate_grundsteuer_b"],
            ol["rate_gewerbesteuer"]) == (500, 539, 439)
    # Angezeigt wird netto — brutto behält die Stadt nicht.
    assert ol["ist_je_ew_gewerbesteuer"] == pytest.approx(1233.36)
    assert rs.einnahmekraft["403000"]["je_jahr"][2025]["je_ew"] == pytest.approx(2033.66)


def test_zwischenueberschriften_und_summenzeilen_sind_keine_staedte(realsteuer):
    rs = sv.lies_realsteuervergleich(realsteuer)
    assert set(rs.tax_rates) <= set(sv.KREISFREIE_STAEDTE)
    assert "001000" not in rs.tax_rates     # die Regions-Summenzeile


def test_hebesatzprobe_traegt_auch_die_winzige_grundsteuer_a(realsteuer):
    """Oldenburgs Grundsteuer A: 13 T€ Grundbetrag, 2 T€ Abweichung — 3 %.

    Eine feste Prozentschranke verwürfe die Zeile. Die Toleranz folgt hier
    der Rundung auf volle Tausend Euro, und damit besteht sie.
    """
    rs = sv.lies_realsteuervergleich(realsteuer)
    probe = sv.probe_hebesatz(rs.tax_rates["403000"])
    assert probe["ok"], probe
    grundsteuer_a = next(t for t in probe["teilproben"] if t["steuer"] == "Grundsteuer A")
    assert grundsteuer_a["deviation"] == pytest.approx(2.0)
    assert grundsteuer_a["deviation"] / 63 > 0.03   # über 3 % — und trotzdem gut


def test_hebesatzprobe_prueft_die_gewerbesteuer_gegen_brutto(realsteuer):
    """Der Fehler, der beim Bauen alle acht Städte verworfen hat.

    ``Grundbetrag × Hebesatz`` ergibt das **Brutto**-Aufkommen; die
    Gewerbesteuerumlage geht erst danach ab. Wer gegen netto prüft, sieht als
    Abweichung exakt die Umlage — bei Oldenburg 18.343 T€.
    """
    rs = sv.lies_realsteuervergleich(realsteuer)
    ol = rs.tax_rates["403000"]
    assert ol["ist_gewerbesteuer"] == 235920        # brutto, für die Probe
    assert ol["netto_gewerbesteuer"] == 217576      # netto, für die Anzeige
    # Auch diese Identität geht nur auf Tausend Euro genau auf: Das LSN rundet
    # alle drei Beträge einzeln, deshalb bleibt ein Euro-Rest von ±1 T€.
    assert (ol["ist_gewerbesteuer"] - ol["umlage_gewerbesteuer"]
            == pytest.approx(ol["netto_gewerbesteuer"], abs=1.0))
    # Und gegen netto geprüft wäre die Abweichung exakt die Umlage gewesen.
    erwartet_brutto = ol["grundbetrag_gewerbesteuer"] * ol["rate_gewerbesteuer"] / 100
    assert (erwartet_brutto - ol["netto_gewerbesteuer"]
            == pytest.approx(ol["umlage_gewerbesteuer"], abs=2.0))


def test_stadt_mit_kaputter_hebesatzprobe_wird_verworfen(tmp_path):
    """Der Verwurf-Fall: eine Zeile, deren Rechnung nicht aufgeht, kommt gar
    nicht herein — mit Begründung, damit die Lücke sichtbar bleibt."""
    kaputt = {k: list(v) for k, v in RS_2_1.items()}
    # Oldenburgs Gewerbesteuer-Brutto durch den Netto-Betrag ersetzt: genau
    # die Verwechslung, gegen die die Probe schützt (Spalte „Ist-Aufkommen
    # brutto", 15. Wert der Zeile einschließlich Name).
    kaputt[403][14] = 217576
    pfad = _realsteuer_mappe(tmp_path, "kaputt.xlsx", zwei_eins=kaputt)
    zeilen, verworfen = sv.zeilen_realsteuern(sv.lies_realsteuervergleich(pfad))

    assert [v["city"] for v in verworfen] == ["Oldenburg"]
    assert verworfen[0]["reason"] == "Hebesatzprobe"
    # Die anderen Städte bleiben — ein Fehler in einer Zeile darf nicht den
    # ganzen Jahrgang mitnehmen.
    hebesatz_staedte = {z["city"] for z in zeilen if z["indicator"].startswith("hebesatz_")}
    assert hebesatz_staedte == {"Braunschweig", "Delmenhorst", "Osnabrück"}
    # Die Steuereinnahmekraft steht in einem anderen Blatt und ist von der
    # Hebesatzprobe nicht betroffen — Oldenburg bleibt dort drin.
    assert any(z["city"] == "Oldenburg"
               and z["indicator"] == "steuereinnahmekraft_je_ew" for z in zeilen)


def test_dreijahresmittel_probe(realsteuer):
    rs = sv.lies_realsteuervergleich(realsteuer)
    assert sv.probe_dreijahresmittel(rs.einnahmekraft["403000"])["ok"]
    # Ein verbogener Durchschnitt fliegt auf.
    verbogen = dict(rs.einnahmekraft["403000"], mittel_teur=340000)
    assert not sv.probe_dreijahresmittel(verbogen)["ok"]


def test_unvollstaendiger_dreijahresblock_gilt_nicht_als_geprueft():
    assert not sv.probe_dreijahresmittel({"je_jahr": {2025: {"teur": 1, "je_ew": 1}},
                                          "mittel_teur": 1})["ok"]


def test_jeder_jahreswert_traegt_sein_eigenes_jahr(realsteuer):
    """Der Realsteuervergleich 2025 führt auch 2023 und 2024. Alles unter dem
    Dateijahr abzulegen machte aus drei Jahren eines."""
    zeilen, _ = sv.zeilen_realsteuern(sv.lies_realsteuervergleich(realsteuer))
    years = {z["year"] for z in zeilen if z["indicator"] == "steuereinnahmekraft_je_ew"}
    assert years == {2023, 2024, 2025}
    assert {z["year"] for z in zeilen if z["indicator"].startswith("hebesatz_")} == {2025}
    ol25 = next(z for z in zeilen if z["city"] == "Oldenburg"
                and z["indicator"] == "steuereinnahmekraft_je_ew" and z["year"] == 2023)
    assert ol25["value"] == pytest.approx(1673.43)


# --- Speichern --------------------------------------------------------------

def _herkunft(probe="lsn_zweijahresueberlappung") -> herkunft.Herkunft:
    return herkunft.Herkunft(
        kind="lsn", probe=probe, label="Kommunaler Finanzausgleich 2026",
        url="https://example.org/kfa2026.xlsx",
        citation="Blatt ST_KR_MESS_VGL", probe_result="403 von 403",
        as_of="26.03.2026")


def test_lsn_ist_eine_bekannte_quellenart():
    """Ohne den Eintrag ließe sich die Herkunft gar nicht bauen."""
    assert "lsn" in herkunft.ARTEN
    for name in ("lsn_zweijahresueberlappung", "lsn_hebesatzprobe",
                 "lsn_dreijahresmittel"):
        assert name in herkunft.PROBEN
        assert herkunft.PROBEN[name].endswith(".")


def test_speichern_und_lesen(tmp_path, kfa2026):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        zeilen = sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026))
        assert store.save_staedtevergleich("tax_capacity", zeilen, _herkunft()) == 16
        gelesen = store.get_staedtevergleich("tax_capacity")
        assert len(gelesen) == 16
        assert all(z["herkunft_id"] for z in gelesen)
        assert store.herkunft_luecken().get("council_staedtevergleich") is None
        # Die Erklärsätze der Probe hängen an der Herkunft und sind für die
        # Leserin geschrieben.
        h = store.get_herkunft([gelesen[0]["herkunft_id"]])[0]
        assert h["kind"] == "lsn"
        assert h["probes"] and "Finanzausgleichs" in h["probes"][0]
    finally:
        store.close()


def test_erneutes_speichern_ersetzt_nur_die_eigene_reihe(tmp_path, kfa2026, realsteuer):
    """Die beiden Reihen kommen aus verschiedenen Dateien, die zu
    verschiedenen Zeiten erscheinen. Ein Lauf für die eine darf die andere
    nicht wegräumen — sonst hinge der Bestand an der Reihenfolge."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_staedtevergleich(
            "tax_capacity", sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026)), _herkunft())
        zeilen, _ = sv.zeilen_realsteuern(sv.lies_realsteuervergleich(realsteuer))
        store.save_staedtevergleich("real_taxes", zeilen,
                                    _herkunft(probe="lsn_hebesatzprobe"))
        assert len(store.get_staedtevergleich("tax_capacity")) == 16

        # Steuerkraft erneut — die Realsteuern bleiben unangetastet.
        vorher = len(store.get_staedtevergleich("real_taxes"))
        store.save_staedtevergleich(
            "tax_capacity", sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026)), _herkunft())
        assert len(store.get_staedtevergleich("tax_capacity")) == 16
        assert len(store.get_staedtevergleich("real_taxes")) == vorher
        assert len(store.get_staedtevergleich()) == 16 + vorher
    finally:
        store.close()


# --- Der Endpunkt -----------------------------------------------------------

def test_endpunkt_liefert_werte_und_den_beleg(tmp_path, kfa2026):
    """Der Endpunkt hängt die Erklärung an die Zahlen — und löst die
    Ratsvorlage über ihre NUMMER auf, nicht über eine gespeicherte id."""
    import sys
    from pathlib import Path

    # Der Endpunkt wird direkt aufgerufen statt über einen TestClient: Die
    # `Depends`-Vorgaben sind gewöhnliche Standardwerte, und so braucht dieser
    # Test weder App-Start noch Anmeldung noch die globalen DB-Umgebungs-
    # variablen, die `tests/test_backend_api.py` beim Import setzt.
    backend = Path(__file__).resolve().parents[1] / "web" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.routers.council import haushalt_vergleich, VERGLEICH_BELEG_VORLAGE

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_staedtevergleich(
            "tax_capacity", sv.zeilen_steuerkraft(sv.lies_kfa(kfa2026)), _herkunft())
        answer = haushalt_vergleich(_user=None, store=store)

        assert len(answer["cities"]) == 8
        oldenburg = next(s for s in answer["cities"] if s["is_oldenburg"])
        assert oldenburg["name"] == "Oldenburg"
        assert oldenburg["below_100k"] is False
        assert next(s for s in answer["cities"]
                    if s["name"] == "Delmenhorst")["below_100k"] is True

        assert answer["years"]["tax_capacity"] == [2026]
        assert len(answer["values"]) == 16
        assert answer["herkunft"]

        # Ohne Vorlagen-Bestand bleibt der Beleg leer — aber er ist da, und
        # die Vorlagennummer steht drin.
        assert answer["citation"]["template_number"] == VERGLEICH_BELEG_VORLAGE
        assert "17170" in answer["citation"]["template_url"]
        assert answer["citation"]["decision_id"] is None
    finally:
        store.close()
