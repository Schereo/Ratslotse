"""Die Planjahre aus dem Gesamtergebnishaushalt — und ihre Trennlinie.

Die eine Sache, die hier still falsch werden kann und dann jahrelang niemandem
auffällt: **Der Haushaltsplan nennt fünf Spalten „Ansatz", beschlossen ist aber
nur eine.** Die anderen vier sind das Vorjahr (fortgeschrieben) und die
mittelfristige Finanzplanung nach § 8 NKomVG. Wer sie zusammenwirft, hat für
2029 einen Plan auf der Seite stehen, den kein Rat je beschlossen hat — und die
Zahl sieht genauso solide aus wie jede andere.

Deshalb prüft diese Datei drei Dinge in dieser Reihenfolge:

1. dass Ansatz und Finanzplanung getrennt in der Datenbank landen und getrennt
   bleiben, auch über mehrere Jahrgänge desselben Jahres hinweg;
2. dass beide Pflicht-Proben wirklich schließen — mit je einem Fall, der sie
   reißt und korrekt verworfen wird;
3. dass der Parser die drei Fallen des Textextrakts übersteht (Fußnotenzeichen,
   umbrochene Postennamen, ein leerer Posten mit einer Kontenzeile dahinter).

``GEH_2026`` ist **echter** Text aus dem Dokument 297441 (Haushalt 2026,
Anlage 005): Kopf und Postenzeilen wörtlich, nur die 300 Kontenzeilen
dazwischen sind weggelassen — bis auf die eine hinter Posten 10, die die Falle
stellt. Der Ausschnitt liefert dieselben 92 Zeilen und dieselbe Ist-Spalte wie
der Volltext (nachgemessen 16.08.2026).
"""
from __future__ import annotations

import pytest

from council import income_budget as eh
from council import finanzquellen, herkunft
from council.store import CouncilStore

# --- Echter Ausschnitt aus „2026 005 Vw Gesamtergebnishaushalt" -------------

GEH_2026 = """www.oldenburg.de

Stadt Oldenburg



Gesamtergebnishaushalt
221

222
Gesamtergebnishaushalt
Erträge und Aufwendungen Ergebnis 2024
- Euro -
Ansatz 2025
- Euro -
Ansatz 2026
- Euro -
Ansatz 2027
- Euro -
Ansatz 2028
- Euro -
Ansatz 2029
- Euro -
Ordentliche Erträge
01. Steuern und ähnliche Abgaben 377.878.954,16 332.705.720 388.377.600 366.584.100 372.762.700 378.699.900388.377.600388.377.600
02. Zuwendungen u. allgemeine
Umlagen 1)
179.073.160,27 144.078.403 145.012.116 143.345.229 143.281.760 142.594.760145.012.116145.012.116
03. Auflösungserträge aus
Sonderposten
14.330.098,51 14.433.886 14.430.410 14.530.720 14.629.597 14.729.90814.430.41014.430.410
04. sonstige Transfererträge 10.051.213,27 8.543.520 9.374.006 9.376.506 9.379.006 9.381.5069.374.0069.374.006
05. öffentlich-rechtliche Entgelte 2) 25.880.028,87 26.011.678 26.622.594 27.409.473 27.409.473 27.409.47326.622.59426.622.594
06. privatrechtliche Entgelte 18.996.664,99 21.574.444 23.885.664 23.897.414 23.888.064 23.879.66423.885.66423.885.664
07. Kostenerstattungen und
Kostenumlagen
133.580.259,22 135.674.968 146.842.124 151.122.124 155.342.124 160.192.124146.842.124146.842.124
08. Zinsen und ähnliche
Finanzerträge
20.134.208,67 21.410.200 16.967.800 12.662.800 12.663.500 12.643.20016.967.80016.967.800
09. aktivierungsfähige
Eigenleistungen
1.371.028,75 1.775.000 1.780.000 1.735.000 1.735.000 1.735.0001.780.0001.780.000
10. Bestandsveränderungen
35111004 Konzessionsabgabe Wasser VWG 2.507.748,56 2.800.000 2.800.000 2.800.000 2.800.0002.800.000
11. sonstige ordentliche Erträge 18.216.232,34 14.889.600 15.282.400 15.278.500 15.274.600 15.270.70015.282.40015.282.400
12.= Summe ordentliche Erträge 799.511.849,05 721.097.419 788.574.714 765.941.865 776.365.824 786.536.235788.574.714
Ordentliche Aufwendungen
13. Personalaufwendungen 184.779.048,00 195.064.660 209.443.324 213.426.387 217.494.208 221.641.790209.443.324209.443.324
14. Versorgungsaufwendungen 11.669.541,00 6.900.000 6.900.000 6.900.000 6.900.000 6.900.0006.900.0006.900.000
15. Aufwendungen für Sach- und
Dienstleistungen
42.908.852,81 52.327.083 53.098.053 51.758.763 51.519.103 50.706.60353.098.05353.098.053
16. Abschreibungen 35.264.008,23 35.458.813 36.629.987 38.127.753 39.628.748 41.129.74336.629.98736.629.987
17. Zinsen und ähnliche
Aufwendungen
4.228.925,87 3.344.500 2.468.350 3.076.400 5.474.450 8.695.4002.468.3502.468.350
18. Transferaufwendungen 323.748.574,83 354.902.122 390.460.256 401.441.508 413.344.936 423.946.656390.460.256390.460.256
19. sonstige ordentliche
Aufwendungen
162.146.432,55 169.265.918 181.775.088 181.100.917 180.830.166 180.885.166181.775.088181.775.088
20.= Summe ordentliche
Aufwendungen
764.745.383,29 817.263.097 880.775.058 895.831.727 915.191.611 933.905.358880.775.058
21. ordentliches Ergebnis
Jahresüberschuss(+)/Jahresfehlbet
rag (-)
34.766.465,76 -96.165.678 -92.200.345 -129.889.862 -138.825.787 -147.369.123-92.200.345
22. außerordentliche Erträge 1.790.782,92 6.263.000 3.840.050 4.952.450 46.050 46.0503.840.0503.840.050
23. außerordentliche Aufwendungen 30.293.264,68 1.572.000 931.000 255.000 255.000 255.000931.000931.000
24. außerordentliches Ergebnis -28.502.481,76 4.691.000 2.909.050 4.697.450 -208.950 -208.9502.909.050
Jahresergebnis Überschuss
(+)/Fehlbetrag (-)
6.263.984,00 -91.474.678 -89.291.295 -125.192.412 -139.034.737 -147.578.073-89.291.295"""

#: Derselbe Ausschnitt aus dem Haushalt 2025 (Dokument 282812). Er wird
#: gebraucht, weil sich die beiden Jahrgänge überlappen: 2026, 2027 und 2028
#: stehen in **beiden** Dokumenten — hier als Finanzplanung, im Haushalt 2026
#: teils als beschlossener Ansatz. Genau daran entscheidet sich, ob der
#: Schlüssel der Tabelle trägt.
GEH_2025 = """www.oldenburg.de

Stadt Oldenburg



Gesamtergebnishaushalt
235
236
Gesamtergebnishaushalt
Erträge und Aufwendungen Ergebnis 2023
- Euro -
Ansatz 2024
- Euro -
Ansatz 2025
- Euro -
Ansatz 2026
- Euro -
Ansatz 2027
- Euro -
Ansatz 2028
- Euro -
Ordentliche Erträge
01. Steuern und ähnliche Abgaben 341.608.473,52 302.740.000 335.138.000 341.606.700 348.363.900 354.616.300335.138.000335.138.000
02. Zuwendungen u. allgemeine
Umlagen 1)
168.262.169,22 164.748.414 172.930.600 172.876.200 172.600.000 172.577.200172.930.600172.930.600
03. Auflösungserträge aus
Sonderposten
14.233.197,95 14.955.126 14.433.886 14.533.518 14.633.150 14.732.78414.433.88614.433.886
04. sonstige Transfererträge 10.083.429,75 7.939.884 8.543.520 8.543.520 8.543.520 8.543.5208.543.5208.543.520
05. öffentlich-rechtliche Entgelte 2) 23.689.299,60 24.553.515 26.612.578 26.612.578 26.612.578 26.612.57826.612.57826.612.578
06. privatrechtliche Entgelte 18.609.454,35 18.321.920 21.541.784 21.585.954 21.618.104 21.610.00421.541.78421.541.784
07. Kostenerstattungen und
Kostenumlagen
123.489.564,42 127.671.132 135.163.588 137.225.129 135.686.765 135.706.765135.163.588135.163.588
08. Zinsen und ähnliche
Finanzerträge
16.384.303,15 16.003.400 16.230.700 15.851.500 15.752.900 15.679.90016.230.70016.230.700
09. aktivierungsfähige
Eigenleistungen
1.397.311,62 2.063.000 1.775.000 1.770.000 1.725.000 1.725.0001.775.0001.775.000
10. Bestandsveränderungen
11. sonstige ordentliche Erträge 15.654.792,86 14.933.300 14.889.600 14.889.600 14.889.600 14.889.60014.889.60014.889.600
12.= Summe ordentliche Erträge 733.411.996,44 693.929.691 747.259.256 755.494.699 760.425.518 766.693.651747.259.256
Ordentliche Aufwendungen
13. Personalaufwendungen 164.821.893,60 183.331.543 193.953.244 197.663.096 201.273.763 205.099.163193.953.244193.953.244
14. Versorgungsaufwendungen 936.318,20 6.900.000 6.900.000 6.900.000 6.900.000 6.900.0006.900.0006.900.000
15. Aufwendungen für Sach- und
Dienstleistungen
40.126.331,76 45.356.915 51.082.194 49.995.928 49.730.178 49.309.97851.082.19451.082.194
16. Abschreibungen 34.258.787,59 33.909.828 35.458.813 36.457.632 37.456.450 38.458.43735.458.81335.458.813
17. Zinsen und ähnliche
Aufwendungen
2.403.740,92 3.429.300 3.344.500 3.073.300 2.886.700 2.725.7003.344.5003.344.500
18. Transferaufwendungen 284.740.806,87 297.676.215 346.202.391 357.050.198 363.683.590 369.901.797346.202.391346.202.391
19. sonstige ordentliche
Aufwendungen
156.031.241,19 157.566.547 168.275.202 166.334.777 166.212.277 165.924.777168.275.202168.275.202
20.= Summe ordentliche
Aufwendungen
683.319.120,13 728.170.348 805.216.345 817.474.931 828.142.957 838.319.852805.216.345
21. ordentliches Ergebnis
Jahresüberschuss(+)/Jahresfehlbet
rag (-)
50.092.876,31 -34.240.657 -57.957.089 -61.980.232 -67.717.440 -71.626.201-57.957.089
22. außerordentliche Erträge 2.192.404,96 3.526.500 6.263.000 2.727.000 43.400 43.4006.263.0006.263.000
23. außerordentliche Aufwendungen 27.975.842,37 1.216.500 931.000 255.000 255.000 255.000931.000931.000
24. außerordentliches Ergebnis -25.783.437,41 2.310.000 5.332.000 2.472.000 -211.600 -211.6005.332.000
Jahresergebnis Überschuss
(+)/Fehlbetrag (-)
24.309.438,90 -31.930.657 -52.625.089 -59.508.232 -67.929.040 -71.837.801-52.625.089"""


def _anlage(store: CouncilStore, text: str, document_id: int = 297441) -> None:
    """Ein Gesamtergebnishaushalt als Anlage im Bestand — so, wie ihn der
    Protokoll-Scraper ablegt."""
    store._conn.execute(
        "INSERT OR REPLACE INTO council_anlagen (document_id, kvonr, label, url, "
        " raw_text, n_pages, fetched_at) VALUES (?,?,?,?,?,?,?)",
        (document_id, 1, "2026 005 Vw Gesamtergebnishaushalt",
         "https://example.org/geh2026.pdf", text, 18, "2026-08-16"))
    store._conn.commit()


def _quelle(document_id: int = 297441) -> herkunft.Herkunft:
    return herkunft.Herkunft(
        kind="ris", probe=["ergebnishaushalt_summenzeilen",
                          "ergebnishaushalt_planspalte"],
        document_id=document_id, label="2026 005 Vw Gesamtergebnishaushalt",
        url="https://example.org/geh2026.pdf",
        citation="Gesamtergebnishaushalt, Posten 1–24")


# --- 1. Die Trennlinie -------------------------------------------------------

def test_planjahr_kommt_aus_dem_kopf_nicht_aus_dem_label():
    """Vier der acht Dokumente heißen bloß „005 Gesamtergebnishaushalt".

    Und selbst wo eine Jahreszahl im Label steht, wäre sie die falsche Quelle:
    Der Kopf führt sechs Jahre, und das beschlossene ist das **dritte**."""
    assert eh.budget_year(GEH_2026) == 2026
    assert eh.kopfjahre(GEH_2026) == [2024, 2025, 2026, 2027, 2028, 2029]
    assert eh.budget_year(GEH_2025) == 2025
    assert eh.budget_year(None) is None


def test_ansatz_und_finanzplanung_landen_getrennt():
    """Der Kern des Ganzen: 2026 ist ein Ansatz, 2027–2029 sind es nicht."""
    r = eh.lies(GEH_2026)
    assert r["bestanden"] is True

    nach_art: dict[str, set[int]] = {}
    for z in r["zeilen"]:
        nach_art.setdefault(z["kind"], set()).add(z["year"])
    assert nach_art == {"ansatz": {2026},
                        "finanzplanung": {2027, 2028, 2029}}

    # Die beiden vorderen Spalten werden gar nicht erst gespeichert: Die erste
    # ist ein Ist (dafür gibt es council_ergebnisrechnung), die zweite ein
    # fortgeschriebener Vorjahresansatz, der dem beschlossenen widerspräche.
    assert 2024 not in {z["year"] for z in r["zeilen"]}
    assert 2025 not in {z["year"] for z in r["zeilen"]}


def test_die_gespeicherten_betraege_sind_die_des_dokuments():
    """Stichproben gegen das PDF — die dritte Spalte, nicht die letzte."""
    r = eh.lies(GEH_2026)
    ansatz = {z["nr"]: z["amount"] for z in r["zeilen"] if z["kind"] == "ansatz"}
    assert ansatz[1] == 388_377_600.0        # Steuern und ähnliche Abgaben
    assert ansatz[12] == 788_574_714.0       # Summe ordentliche Erträge
    assert ansatz[20] == 880_775_058.0       # Summe ordentliche Aufwendungen
    assert ansatz[21] == -92_200_345.0       # ordentliches Ergebnis

    # Die Finanzplanung trägt andere Zahlen — und zwar die des richtigen Jahres.
    fp = {(z["year"], z["nr"]): z["amount"] for z in r["zeilen"]
          if z["kind"] == "finanzplanung"}
    assert fp[(2027, 1)] == 366_584_100.0
    assert fp[(2028, 1)] == 372_762_700.0
    assert fp[(2029, 1)] == 378_699_900.0

    # Die Bezeichnungen sind dieselben wie im Jahresabschluss — sonst ließe
    # sich keine Zeitreihe über beide Quellen bilden.
    assert {z["label"] for z in r["zeilen"] if z["nr"] == 1} == {
        "Steuern und ähnliche Abgaben"}


def test_ist_spalte_wird_gelesen_aber_nicht_gespeichert():
    """Sie ist die Gegenprobe, nicht der Bestand: Das Ist eines Jahres steht
    im Jahresabschluss, und zwar für die Kernverwaltung."""
    r = eh.lies(GEH_2026)
    assert r["ist_jahr"] == 2024
    assert r["ist"][1] == 377_878_954.16
    assert r["ist"][12] == 799_511_849.05
    assert all(z["year"] != 2024 for z in r["zeilen"])


# --- 2. Die Pflicht-Proben ---------------------------------------------------

def test_summenprobe_wirft_einen_verrutschten_jahrgang_weg():
    """Ein Dokument, dessen Tabelle nicht aufgeht, liefert **keine** Zeilen.

    Verändert wird genau eine Zahl: die Steuern in der Ansatz-Spalte. Damit
    stimmt die Summenzeile 12 nicht mehr — und weil die Probe in allen sechs
    Spalten läuft, reicht diese eine Zeile, um den Jahrgang zu verwerfen.
    Halbe Zahlen gibt es nicht."""
    kaputt = GEH_2026.replace("388.377.600 366.584.100", "389.377.600 366.584.100", 1)
    r = eh.lies(kaputt)
    assert r["bestanden"] is False
    assert r["zeilen"] == []
    assert r["budget_year"] == 2026          # erkannt, aber nicht übernommen
    (summen,) = [p for p in r["probes"] if p["probe"] == "ergebnishaushalt_summenzeilen"]
    assert summen["ok"] is False
    assert "Posten 1–11" in summen["warum"] and "Spalte 3" in summen["warum"]
    assert summen["warum"] in r["nachweis"]


def test_rundung_von_einem_euro_wirft_keinen_jahrgang_weg():
    """Die Gegenrichtung: Die Stadt rundet ihre Summenzeilen kaufmännisch,
    über sieben Summanden kommt so bis zu 1 € zusammen. Eine Probe, die daran
    scheitert, verlöre echte Jahrgänge — gemessen an acht Dokumenten treten
    genau solche 1-€-Reste in fünf davon auf."""
    knapp = GEH_2026.replace("388.377.600 366.584.100", "388.377.601 366.584.100", 1)
    assert eh.lies(knapp)["bestanden"] is True


def test_summenprobe_prueft_auch_die_finanzplanungsspalten():
    """Sonst käme ein Jahrgang durch, dessen Ansatz stimmt und dessen
    Vorausschau verrutscht ist — und niemand sähe es."""
    kaputt = GEH_2026.replace("372.762.700 378.699.900", "372.772.700 378.699.900", 1)
    r = eh.lies(kaputt)
    assert r["bestanden"] is False
    (summen,) = [p for p in r["probes"] if p["probe"] == "ergebnishaushalt_summenzeilen"]
    assert "Spalte 5" in summen["warum"]


def test_planspaltenprobe_haelt_die_trennlinie():
    """Ohne die Wiederholung am Zeilenende wäre „dritte Spalte = Ansatz" eine
    Reihenfolgeannahme. Fehlt sie in **einer** Zeile, ist sie kein Beleg mehr.

    Hier verliert Posten 01 seine Wiederholung; die Summen gehen weiter auf,
    trotzdem wird nichts gespeichert."""
    ohne_echo = GEH_2026.replace(
        "378.699.900388.377.600388.377.600", "378.699.900", 1)
    r = eh.lies(ohne_echo)
    assert r["bestanden"] is False
    assert r["zeilen"] == []
    (summen,) = [p for p in r["probes"] if p["probe"] == "ergebnishaushalt_summenzeilen"]
    (spalte,) = [p for p in r["probes"] if p["probe"] == "ergebnishaushalt_planspalte"]
    assert summen["ok"] is True           # die Tabelle selbst ist in Ordnung …
    assert spalte["ok"] is False          # … aber die Trennlinie ist unbelegt
    assert "Posten 1" in spalte["warum"]


def test_planspaltenprobe_merkt_wenn_die_wiederholung_woanders_hinzeigt():
    """Zeigte sie auf eine Finanzplanungsspalte, hätten wir die falsche Zahl
    als Beschlusslage gespeichert — der teuerste denkbare Fehler hier."""
    verschoben = GEH_2026.replace(
        "378.699.900388.377.600388.377.600", "378.699.900366.584.100", 1)
    r = eh.lies(verschoben)
    assert r["bestanden"] is False
    assert r["zeilen"] == []
    (spalte,) = [p for p in r["probes"] if p["probe"] == "ergebnishaushalt_planspalte"]
    assert "nicht auf das Planjahr" in spalte["warum"]
    assert "366,584,100" in spalte["warum"]     # die Zahl, auf die sie zeigte


def test_fremder_tabellenkopf_liefert_nichts():
    """Ein Dokument mit anderem Kopf ist ein anderes Dokument. Geraten wird
    nichts — auch nicht „wird schon dieselbe Reihenfolge sein"."""
    for kopf in ("Ergebnis 2024\nAnsatz 2025\nAnsatz 2026",     # zu wenige Spalten
                 "Ansatz 2024\nAnsatz 2025\nAnsatz 2026\nAnsatz 2027\n"
                 "Ansatz 2028\nAnsatz 2029",                    # keine Ist-Spalte
                 "Ergebnis 2024\nAnsatz 2025\nAnsatz 2027\nAnsatz 2028\n"
                 "Ansatz 2029\nAnsatz 2030"):                   # Lücke im Jahreslauf
        assert eh.kopfjahre(kopf) == []
        r = eh.lies(kopf)
        assert r["bestanden"] is False and r["zeilen"] == []
        assert r["budget_year"] is None


# --- 3. Die Fallen des Textextrakts -----------------------------------------

def test_fussnotenzeichen_kosten_keinen_posten():
    """„… u. allgemeine Umlagen 1)" — die 1 ist keine Zahl der Tabelle.

    Ohne diesen Schnitt fielen die Posten 02 und 05 aus, mit ihnen die
    Summenprobe und damit die Jahrgänge 2025 und 2026, um die es hier geht."""
    r = eh.lies(GEH_2026)
    ansatz = {z["nr"]: z["amount"] for z in r["zeilen"] if z["kind"] == "ansatz"}
    assert ansatz[2] == 145_012_116.0     # nicht 1,0
    assert ansatz[5] == 26_622_594.0


def test_leerer_posten_faellt_nicht_auf_die_kontenzeile_herein():
    """Posten 10 (Bestandsveränderungen) ist in allen acht Jahrgängen leer;
    dahinter steht direkt eine Kontenzeile. Aus deren achtstelliger Kontonummer
    würde die Betrags-Regex „351", „110", „04" machen.

    Der Posten fehlt deshalb ganz — und dass er wirklich 0 war, beweist das
    Dokument selbst: Die Summenzeile 12 geht ohne ihn auf."""
    r = eh.lies(GEH_2026)
    assert 10 not in {z["nr"] for z in r["zeilen"]}
    assert 10 not in r["ist"]
    assert r["bestanden"] is True
    # Die Konzessionsabgabe der Kontenzeile ist nirgends gelandet.
    assert 2_507_748.56 not in set(r["ist"].values())
    assert 2_800_000.0 not in {z["amount"] for z in r["zeilen"]}


def test_umbrochene_postennamen_bleiben_lesbar():
    """„07. Kostenerstattungen und\\nKostenumlagen" steht über zwei Zeilen."""
    r = eh.lies(GEH_2026)
    ansatz = {z["nr"]: z["amount"] for z in r["zeilen"] if z["kind"] == "ansatz"}
    assert ansatz[7] == 146_842_124.0
    assert ansatz[15] == 53_098_053.0


def test_zeile_ohne_nummer_hinter_posten_24_bleibt_draussen():
    """Direkt hinter Posten 24 steht „Jahresergebnis …" ohne Postennummer.
    Ihre Zahlen gehörten sonst noch zu 24."""
    r = eh.lies(GEH_2026)
    ansatz = {z["nr"]: z["amount"] for z in r["zeilen"] if z["kind"] == "ansatz"}
    assert ansatz[24] == 2_909_050.0          # nicht -89.291.295 (Jahresergebnis)


def test_verschobene_nummerierung_wird_nicht_uebernommen():
    """Im Gesamtabschluss des Konzerns wanderte eine Summenzeile über die
    Jahre von Posten 15 auf 13. Passiert das hier, darf keine Zahl unter dem
    falschen Namen landen."""
    getauscht = GEH_2026.replace("01. Steuern und ähnliche Abgaben",
                                 "01. Personalaufwendungen", 1)
    r = eh.lies(getauscht)
    assert r["bestanden"] is False       # Posten 01 fehlt → Summe 12 geht nicht auf


# --- 4. Der Weg in die Datenbank --------------------------------------------

def test_store_haelt_ansatz_und_finanzplanung_auseinander(tmp_path):
    """Dieselben Jahre stehen in mehreren Plänen — der Schlüssel muss das
    aushalten, ohne dass der jüngste Plan den älteren stumm überschreibt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    p26 = eh.lies(GEH_2026)
    p25 = eh.lies(GEH_2025)
    assert p25["bestanden"] and p26["bestanden"]
    store.save_ergebnishaushalt(2026, p26["zeilen"], _quelle(297441))
    store.save_ergebnishaushalt(2025, p25["zeilen"], _quelle(282812))

    assert store.ergebnishaushalt_jahrgaenge() == [2025, 2026]
    # 2026 steht zweimal in der Tabelle — einmal als beschlossener Ansatz,
    # einmal als das, was der Plan 2025 dafür vorausgesehen hatte.
    fuer_2026 = {(z["plan_budget_year"], z["kind"]): z["amount"]
                 for z in store.get_ergebnishaushalt(year=2026) if z["nr"] == 12}
    assert fuer_2026 == {(2026, "ansatz"): 788_574_714.0,
                         (2025, "finanzplanung"): 755_494_699.0}

    # Und die Frage „was gilt?" hat genau eine Antwort.
    (beschlossen,) = [z for z in store.get_ergebnishaushalt(year=2026, kind="ansatz")
                      if z["nr"] == 12]
    assert beschlossen["amount"] == 788_574_714.0
    assert beschlossen["plan_budget_year"] == 2026
    store.close()


def test_ansatz_jahre_fuehren_keine_finanzplanung(tmp_path):
    """Ein Jahr-Umschalter, der 2029 anbietet, behauptet einen Beschluss."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_ergebnishaushalt(2026, eh.lies(GEH_2026)["zeilen"], _quelle())
    assert store.budgeted_years() == [2026]
    alle = {z["year"] for z in store.get_ergebnishaushalt()}
    assert alle == {2026, 2027, 2028, 2029}
    store.close()


def test_jede_zeile_weiss_woher_sie_kommt(tmp_path):
    """`herkunft_luecken()` ist leer — der Sollzustand nach jedem Lauf."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_ergebnishaushalt(2026, eh.lies(GEH_2026)["zeilen"], _quelle())
    assert store.herkunft_luecken() == {}
    row = store._conn.execute(
        "SELECT p.amount, h.probe, h.document_id, h.citation "
        "FROM council_ergebnishaushalt p "
        "JOIN council_herkunft h ON h.id = p.herkunft_id LIMIT 1").fetchone()
    assert row["document_id"] == 297441
    assert row["probe"] == ("ergebnishaushalt_summenzeilen,"
                              "ergebnishaushalt_planspalte")
    # Beide Proben tragen einen Satz für Leserinnen — sonst ließe sich die
    # Herkunft gar nicht erst bauen.
    (h,) = store.get_herkunft()
    assert len(h["probes"]) == 2
    assert "hervorgehoben" in h["probes"][1]
    store.close()


def test_ingest_liest_ein_und_tut_beim_zweiten_mal_nichts(tmp_path):
    """Der ganze Weg: Anlage → Proben → Tabelle. Und dann noch einmal."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, GEH_2026)

    p = finanzquellen.Protokoll(still=True)
    erst = finanzquellen.lies_ergebnishaushalte(store, p)
    assert erst["neue_jahrgaenge"] == [2026]
    assert erst["planzeilen"] == 92 and erst["plan_verworfen"] == 0
    assert not p.warnungen

    vorher = store.get_ergebnishaushalt()
    # Der Cron-Weg: `nur_fehlende` sieht den Jahrgang und rührt ihn nicht an.
    zweit = finanzquellen.lies_ergebnishaushalte(store, p, nur_fehlende=True)
    assert zweit["neue_jahrgaenge"] == [] and zweit["planzeilen"] == 0
    assert store.get_ergebnishaushalt() == vorher
    # Und der Weg von Hand schreibt denselben Inhalt zurück, nicht doppelt.
    finanzquellen.lies_ergebnishaushalte(store, p)
    assert store.get_ergebnishaushalt() == vorher
    store.close()


def test_herkunft_sagt_dass_es_der_entwurf_ist(tmp_path):
    """Anlage 005 hängt an der Einbringungs-Vorlage, nicht am Beschluss.

    Gemessen an den sechs Jahren mit Jahresabschluss liegt dieser Ansatz bei
    den ordentlichen Erträgen 0,7 bis 13,1 Mio. € unter dem, was der Abschluss
    als Bezugsgröße führt — der Rat ändert den Entwurf. Wer die Zahl anzeigt,
    zeigt den Vorschlag der Verwaltung; steht das nicht an der Herkunft, kann
    die Seite es auch nicht anschreiben."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, GEH_2026)
    finanzquellen.lies_ergebnishaushalte(store, finanzquellen.Protokoll(still=True))

    (h,) = store.get_herkunft()
    assert h["as_of"] == "Haushaltsplan 2026, Anlage 005 — Stand der Einbringung"
    assert "Ansatz 2026" in h["citation"]
    store.close()


def test_ingest_speichert_nichts_wenn_die_probe_reisst(tmp_path):
    """Ein Dokument mit gerissener Probe bleibt draußen — mit Begründung."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, GEH_2026.replace(
        "388.377.600 366.584.100", "389.377.600 366.584.100", 1))

    p = finanzquellen.Protokoll(still=True)
    bericht = finanzquellen.lies_ergebnishaushalte(store, p)
    assert bericht["neue_jahrgaenge"] == []
    assert bericht["plan_verworfen"] == 1
    assert store.get_ergebnishaushalt() == []
    assert any("nicht gespeichert" in w for w in p.warnungen)
    store.close()


def test_ein_gerissener_jahrgang_laesst_den_bestand_stehen(tmp_path):
    """Der gefährlichste Fall im unbeaufsichtigten Lauf: Die Stadt ändert ihr
    PDF-Layout, der Parser liefert nichts mehr — und der Lauf tauscht einen
    gefüllten Jahrgang gegen Leere. Das darf nicht passieren, auch nicht
    stillschweigend."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_ergebnishaushalt(2026, eh.lies(GEH_2026)["zeilen"], _quelle())
    _anlage(store, GEH_2026.replace(
        "388.377.600 366.584.100", "389.377.600 366.584.100", 1))

    p = finanzquellen.Protokoll(still=True)
    bericht = finanzquellen.lies_ergebnishaushalte(store, p)
    assert bericht["plan_verworfen"] == 1
    assert len(store.get_ergebnishaushalt()) == 92        # unangetastet
    assert store.budgeted_years() == [2026]
    store.close()


def test_zweites_dokument_zum_selben_jahrgang_wird_gemeldet(tmp_path):
    """Der Vorbericht liegt in manchen Jahren dreifach im Bestand. Käme das
    beim Gesamtergebnishaushalt vor, entschiede sonst die Sortierung, welcher
    Stand gilt — das gehört gemeldet, nicht nebenbei entschieden."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _anlage(store, GEH_2026, document_id=297441)
    _anlage(store, GEH_2026, document_id=297999)

    p = finanzquellen.Protokoll(still=True)
    bericht = finanzquellen.lies_ergebnishaushalte(store, p)
    assert bericht["neue_jahrgaenge"] == [2026]
    assert len(store.get_ergebnishaushalt()) == 92
    assert any("zweites Dokument" in w for w in p.warnungen)
    store.close()


# --- 5. Die Gegenprobe -------------------------------------------------------

def test_gegenprobe_misst_und_verwirft_nicht():
    """Die Ist-Spalte ist die **Gesamt**ebene (mit den nicht rechtsfähigen
    Stiftungen), `council_ergebnisrechnung` die Kernverwaltung. Beide Zahlen
    sind richtig und beide heißen „Ergebnis 2024".

    Gemessen an acht Jahrgängen: 6 bis 8 von 23 Posten stimmen exakt überein,
    der größte Abstand liegt bei 0,075 % der Ertragssumme. Deshalb ist das
    hier eine Messung mit Warnschwelle, kein Gate."""
    r = eh.lies(GEH_2026)
    kern = dict(r["ist"])
    kern[1] = kern[1] - 12_000.0          # Stiftungsanteil, so groß wie echt
    g = eh.gegenprobe(r["ist"], kern)
    assert g["geprueft"] == 23 and g["gleich"] == 22
    assert g["posten"] == 1 and g["groesste_abweichung"] == pytest.approx(12_000.0)
    assert g["plausibel"] is True

    # Eine Spalte aus dem falschen Jahr fällt dagegen auf.
    falsch = dict(r["ist"])
    falsch[12] = falsch[12] * 0.9
    g2 = eh.gegenprobe(r["ist"], falsch)
    assert g2["plausibel"] is False
    assert g2["anteil"] > eh.GEGENPROBE_GRENZE

    # Ohne Vergleichsbestand wird nichts behauptet.
    assert eh.gegenprobe(r["ist"], {})["plausibel"] is None


# --- 6. Der Altbestand: plan fällt auf ansatz zurück -------------------------

def test_plan_faellt_auf_ansatz_zurueck(tmp_path):
    """Regressionstest zum Befund „2023 und 2024 tragen keinen Plan".

    Die Spalten `plan`/`plan_kind` kamen mit #510 per ALTER TABLE dazu, und
    ALTER TABLE füllt nichts nach: Jede vorher geschriebene Zeile trägt dort
    NULL, obwohl `ansatz` danebensteht und stimmt. `get_plan_ist` sollte das
    abfangen — tat es aber nicht, weil ``r.get("plan", r.get("ansatz"))``
    seinen Vorgabewert nur bei **fehlendem Schlüssel** nimmt, und der Schlüssel
    kommt aus einem SELECT, ist also immer da. Der Zweig war toter Code, und
    `/haushalt/plan-ist` schrieb „Planwerte konnten wir nicht auslesen" über
    jeden Jahrgang eines nicht neu eingelesenen Bestands."""
    store = CouncilStore(tmp_path / "c.sqlite")
    q = herkunft.Herkunft(kind="ris", probe=herkunft.UNBEKANNT, document_id=1,
                          label="Jahresabschluss 2023", url="https://example.org/ja.pdf")
    # So sieht eine Zeile aus, die vor #510 geschrieben wurde: ansatz ja,
    # plan und plan_kind nein.
    alt = [{"nr": 12, "label": "Summe ordentliche Erträge", "budgeted": 664_574_528.42,
            "plan": None, "result": 732_987_197.61, "is_total": 1},
           {"nr": 20, "label": "Summe ordentliche Aufwendungen",
            "budgeted": 674_305_462.42, "plan": None, "result": 683_032_270.32,
            "is_total": 1}]
    store.save_ergebnisrechnung(2023, alt, q)
    store.save_ergebnisrechnung(2023, alt, q, sub_budget_no=7, sub_budget_name="Stadtplanung")
    # Der Schreibweg füllt `plan` schon aus `ansatz` …
    gespeichert = {z["nr"]: z for z in store.get_ergebnisrechnung(2023)}
    assert gespeichert[12]["plan"] == 664_574_528.42

    # … und der Lesepfad hält auch stand, wenn in der Tabelle wirklich NULL
    # steht (Altbestand, den kein Schreibweg mehr anfasst).
    store._conn.execute("UPDATE council_ergebnisrechnung SET plan = NULL")
    store._conn.commit()
    d = store.get_plan_ist(2023)
    assert d["gesamt"]["revenues_planned"] == 664_574_528.42
    assert d["gesamt"]["expenses_planned"] == 674_305_462.42
    # Auch je Bereich — sonst stünde die Gesamtzeile da und die Tabelle leer.
    assert d["bereiche"][0]["revenues_planned"] == 664_574_528.42
    store.close()
