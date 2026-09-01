"""Die Schuldenzeitreihe aus Tabelle 1108 des Statistischen Jahrbuchs.

Die Fixture ist ein **echter, gekürzter Textextrakt** der Tabelle
(``1108-2025-AZ.pdf``, Stand 08.07.2026) — dieselben Spalten, dieselbe
Kopf-und-Fuß-Reihenfolge, die pypdf tatsächlich liefert, und dieselben Zahlen.
Sie enthält jede Eigenheit, an der ein naiver Parser scheitert:

- **Fußnotenziffern kleben an den Beträgen** (``26.5981`` = 26.598 mit Fußnote
  1, nicht 265.981). Vier Jahrgänge sind betroffen.
- **Revidierte Werte tragen ein ``r``** (``251.160r``).
- **2022 reißt die Summenprobe im Dokument selbst** — die Schuldenarten
  ergeben 1,078 Mio. € mehr als die Summe daneben.
- Die Spaltenköpfe stehen im Extrakt **unter** den Daten, die Jahreszahl ist
  vierstellig und ohne Tausenderpunkt (an ihr scheitert die Zellen-Regel, wenn
  man sie nicht getrennt liest).

Was hier nicht getestet wird, weil es nicht zu dieser Schicht gehört: der
Schuldenstand aus dem Vorbericht des Haushaltsplans. Der bleibt draußen —
seine Werte stehen in einem Diagramm, dessen Achsenbeschriftungen im
Textextrakt nicht von Datenwerten zu unterscheiden sind. Keine Probe möglich,
also nicht eingelesen.
"""
from __future__ import annotations

import pytest

from council import finanzquellen, herkunft, schulden
from council.store import CouncilStore

# --- Fixtures ---------------------------------------------------------------

#: Der Textextrakt der echten Tabelle, gekürzt auf die Jahrgänge, die etwas
#: beweisen: die ersten beiden, alle vier mit Fußnotenmarken, das Paar um die
#: EGH-Gründung 2010, den gerissenen Jahrgang 2022 mit seinen Nachbarn, den
#: revidierten 2024 und den jüngsten 2025.
TABELLE = """Stadt Oldenburg (Oldb) - Statistik
1108   Stand der Verschuldung der Stadt Oldenburg 1995 bis 2025
            - Bevölkerungsstand: 31. Dezember des Vorjahres
S 1 S 2 S 3 S 4 S 5 S 6 S 7
1995 250.448 244 2.352 48.472 301.516 2.014
1996 264.974 88 1.808 50.678 317.548 2.098
1999 251.988 0 273    26.5981 278.859 1.807
2001 112.962 0 154    24.6552 137.771 891
2008     133.1993 0 0    19.2423 152.441 957
2009 130.827 0 0 18.627 149.454 932
2010      30.5434 0 0 123.4544 153.997 955
2021 53.074 0 0          218.579 271.653 1.602
2022 49.745 0 0 232.790 281.457 1.652
2023 46.577 0 0 235.338 281.915 1.616
2024 43.691 0 0 251.160r 294.851r 1.673r
2025 40.804 0 0 296.190 336.994 1.908
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1  Ab 1999 ohne Kliniken, die jetzt als Klinikum Oldenburg AöR geführt werden.
2  Zum 01. Januar 2001 wurde die Stadtentwässerung auf den Oldenburgisch-\
Ostfriesischen Wasserverband übertragen.
3  Ausgliederung des Eigenbetriebs Weser-Ems Halle Oldenburg in die Weser-Ems Halle
   Oldenburg GmbH & Co. KG. Die Schulden des Eigenbetriebs verbleiben rechtlich
   bei der Stadt.
4  Gründung des Eigenbetriebes Gebäudewirtschaft und Hochbau (EGH) zum 01.Januar 2010.
Kapitel 11 - Verwaltung und Finanzen
Jahr
         Schulden in Tausend Euro total
Schulden aus
Kreditmarkt-
mittel
Tausend Euro Euro
je Einwohner5,6
Fachdienst Geo und Daten
"""

#: Die Einwohnerzahlen aus Datensatz 1102 (Stichtag 31.12. des Vorjahres) —
#: der Divisor der unabhängigen Gegenprobe, mit den echten Werten.
EINWOHNER = {2010: 161334, 2021: 169605, 2022: 170389, 2023: 174445,
             2024: 176242, 2025: 176614}


@pytest.fixture()
def gelesen():
    return schulden.lies(TABELLE, EINWOHNER)


def _zeile(result, year):
    return next(z for z in result["zeilen"] if z["year"] == year)


# --- Erkennung --------------------------------------------------------------


def test_erkennt_tabelle_und_spanne_aus_dem_titel():
    """Die Spanne kommt aus dem Titel und nicht aus den gelesenen Zeilen —
    nur so lässt sich prüfen, ob der Parser Jahrgänge verloren hat."""
    assert schulden.erkenne(TABELLE) == (1995, 2025)


def test_fremdes_dokument_wird_nicht_gelesen():
    """Ohne den Titel ist es nicht Tabelle 1108, egal wie plausibel die Zahlen
    aussehen. Der Ingest bricht daraufhin ab, statt irgendetwas zu speichern."""
    assert schulden.erkenne("1104 Steuereinnahmen\n2025 1.234 5.678") is None
    assert schulden.erkenne("") is None


# --- Zellen: Fußnoten und Marken -------------------------------------------


@pytest.mark.parametrize("field,value,mark", [
    ("301.516", 301516, ""),      # gewöhnlich
    ("0", 0, ""),
    ("891", 891, ""),             # dreistellig ohne Punkt
    ("26.5981", 26598, "1"),      # Fußnote 1 klebt am Betrag
    ("133.1993", 133199, "3"),
    ("123.4544", 123454, "4"),
    ("251.160r", 251160, "r"),    # revidiert
    ("1.673r", 1673, "r"),
])
def test_fussnoten_und_marken_kleben_nicht_am_betrag(field, value, mark):
    """``26.5981`` sind 26.598 mit Fußnote 1 und nicht 265.981.

    Auflösbar, weil deutsche Tausendergruppen genau drei Ziffern haben — was
    hinter der letzten vollständigen Gruppe steht, gehört nicht zur Zahl. Ein
    Parser, der bloß die Punkte entfernt, liest hier das Zehnfache und meldet
    nichts."""
    assert schulden._zelle(field) == (value, mark)


def test_punktloses_feld_gilt_ungeteilt():
    """Ohne Tausenderpunkt wird nicht getrennt: ``1234`` sind 1234 und nicht
    123 mit Fußnote 4. Sonst schrumpfte eine Zahl still um eine Stelle, sobald
    die Quelle ihr Zahlenformat ändert — so fällt sie stattdessen durch die
    Summenprobe."""
    assert schulden._zelle("1234") == (1234, "")
    assert schulden._zelle("Quelle:") == (None, "")


# --- Die Summenprobe --------------------------------------------------------


def test_summenprobe_schliesst_wo_die_quelle_stimmt(gelesen):
    """30 von 31 Jahrgängen der echten Tabelle gehen auf den Euro auf — und
    darunter alle vier mit Fußnotenmarken. Die Probe prüft damit nicht nur die
    Quelle, sondern auch, dass der Entzerrer keine Ziffer abgeschnitten hat."""
    for year in (1995, 1999, 2001, 2008, 2010, 2024, 2025):
        ok, deviation = schulden.summenprobe(_zeile(gelesen, year))
        assert ok, f"{year}: {deviation:+,.0f} €"
        assert deviation == 0


def test_summenprobe_faengt_eine_verdrehte_spalte():
    """Wären zwei Spalten vertauscht, ginge die Rechnung nicht mehr auf — das
    ist der Fehler, den zeilenweises Lesen nicht bemerkt."""
    row = dict(_zeile(schulden.lies(TABELLE, EINWOHNER), 2025))
    row["credit_market"], row["municipal_enterprises"] = 296_190_000, 40_804_000
    row["total"] = 336_994_000
    ok, _ = schulden.summenprobe(row)
    assert ok, "Vertauschen zweier Summanden ändert die Summe nicht"
    row["municipal_enterprises"] = 41_000_000
    ok, deviation = schulden.summenprobe(row)
    assert not ok and deviation != 0


# --- Die unabhängige Gegenprobe --------------------------------------------


def test_prokopfprobe_geht_gegen_die_einwohnerzahlen_auf(gelesen):
    """Gesamtschuld ÷ Einwohnerzahl = der ausgewiesene Pro-Kopf-Betrag.

    Die stärkere der beiden Proben: Ihr Divisor stammt aus Datensatz 1102 des
    Open-Data-Portals, also aus einer anderen Veröffentlichung als die Tabelle.
    Dass beide sich treffen, kann kein Übertragungsfehler auf unserer Seite
    erzeugen."""
    for year, zahl in EINWOHNER.items():
        ok, gerechnet = schulden.prokopfprobe(_zeile(gelesen, year), zahl)
        assert ok, f"{year}: {gerechnet:.2f} gerechnet"
    # 2025 im Klartext: 336.994.000 € / 176.614 = 1.908,08 €, ausgewiesen 1.908.
    ok, gerechnet = schulden.prokopfprobe(_zeile(gelesen, 2025), 176614)
    assert ok and round(gerechnet) == 1908


def test_prokopfprobe_ohne_einwohnerzahl_ist_kein_urteil(gelesen):
    """Vor 2010 kennt der Bestand keine Einwohnerzahlen. Das ist eine fehlende
    Probe und kein Durchfallen — sonst verlöre die Reihe ihre erste Hälfte."""
    assert schulden.prokopfprobe(_zeile(gelesen, 1995), None) == (None, None)
    assert gelesen["probes"]["prokopf_ohne_einwohnerzahl"] > 0


def test_prokopfprobe_faengt_einen_faktor_tausend():
    """Die Quelle rechnet in Tausend Euro. Wer die Umrechnung vergisst, liegt
    um Faktor 1000 daneben — die Summenprobe merkt davon nichts, weil sie
    innerhalb derselben Einheit rechnet. Diese hier merkt es."""
    row = {"year": 2025, "total": 336_994, "per_capita": 1908}
    ok, _ = schulden.prokopfprobe(row, 176614)
    assert not ok


# --- Der Fall 2022: was die Probe reißt, wird verworfen --------------------


def test_2022_verliert_seine_aufteilung_aber_nicht_seine_summe(gelesen):
    """Der Jahrgang, für den beide Proben gebaut sind.

    Im Dokument selbst ergeben die Schuldenarten 282.535 T€, ausgewiesen sind
    281.457 T€. Die Summenprobe reißt; welche Spalte danebenliegt, sagt die
    Quelle nicht. Also fällt die **Aufteilung** weg — geschätzt wird nichts.
    Die **Summe** trägt die unabhängige Pro-Kopf-Probe und bleibt: Sie zu
    verwerfen hieße, eine belegte Zahl wegzuwerfen."""
    z = _zeile(gelesen, 2022)
    assert z["total"] == 281_457_000
    assert z["per_capita"] == 1652
    assert all(z[art] is None for art in schulden.ARTEN)
    assert z["breakdown_rejected"] == 1_078_000
    assert z["probes"] == ["debt_per_capita"]
    # Und die Nachbarjahre behalten ihre Aufteilung — es fällt nur der eine.
    assert _zeile(gelesen, 2021)["credit_market"] == 53_074_000
    assert _zeile(gelesen, 2023)["credit_market"] == 46_577_000


def test_ohne_jede_bestandene_probe_faellt_der_jahrgang_ganz_weg():
    """2022 überlebt nur, weil eine Einwohnerzahl da ist. Ohne sie hat der
    Jahrgang gar keine Probe mehr — und dann steht er nirgends."""
    ohne = schulden.lies(TABELLE, {j: z for j, z in EINWOHNER.items() if j != 2022})
    assert all(z["year"] != 2022 for z in ohne["zeilen"])
    verworfen = next(v for v in ohne["verworfen"] if v["year"] == 2022)
    assert "Summenprobe" in verworfen["reason"]
    assert "keine Einwohnerzahl" in verworfen["reason"]


# --- Einheiten und Inhalt ---------------------------------------------------


def test_betraege_kommen_in_euro_an(gelesen):
    """Die Quelle rechnet in Tausend Euro, gespeichert wird wie überall im
    Bereich in Euro — der Pro-Kopf-Betrag steht dort schon."""
    z = _zeile(gelesen, 2025)
    assert z["total"] == 336_994_000
    assert z["credit_market"] == 40_804_000
    assert z["municipal_enterprises"] == 296_190_000
    assert z["per_capita"] == 1908


def test_revidierte_werte_bleiben_als_angabe_erhalten(gelesen):
    """Das ``r`` der Quelle heißt „nachträglich korrigiert". Das ist eine
    Angabe über die Zahl und darf auf der Seite stehen."""
    assert _zeile(gelesen, 2024)["revised"] is True
    assert _zeile(gelesen, 2025)["revised"] is False


def test_die_umbuchung_von_2010_bleibt_sichtbar(gelesen):
    """Der Beleg für die Abgrenzung: 2010 wandern 108,9 Mio. € aus dem
    Kreditportfolio in den neuen Eigenbetrieb (Fußnote 4). Die Kreditmarkt-
    Spalte bricht ein, die Summe bleibt fast unverändert. Wer nur die erste
    Spalte zeigte, verkündete einen Schuldenabbau um drei Viertel, den es nie
    gab — deshalb speichern wir die Spalten einzeln."""
    vorher, nachher = _zeile(gelesen, 2009), _zeile(gelesen, 2010)
    assert nachher["credit_market"] < vorher["credit_market"] * 0.3
    assert nachher["municipal_enterprises"] > vorher["municipal_enterprises"] * 6
    # Die Summe bewegt sich um weniger als 5 % — es ist eine Umbuchung.
    assert abs(nachher["total"] - vorher["total"]) < vorher["total"] * 0.05


def test_kein_jahrgang_der_angekuendigten_spanne_geht_verloren():
    """Der Titel nennt seine Spanne selbst. Was daraus fehlt, ist ein Befund —
    hier fehlt in der gekürzten Fixture natürlich vieles, und genau das soll
    der Lauf auch sagen können."""
    voll = schulden.lies(TABELLE, EINWOHNER)
    assert voll["spanne"] == (1995, 2025)
    assert 1997 in voll["fehlende_jahrgaenge"]      # in der Fixture ausgelassen
    assert 2025 not in voll["fehlende_jahrgaenge"]  # gelesen


# --- Store: Herkunft je Zeile ----------------------------------------------


def _herkunft(probe="debt_total_row"):
    return herkunft.Herkunft(
        kind="city", probe=probe, url=schulden.TABELLE_URL,
        label="Statistisches Jahrbuch, Tabelle 1108",
        citation="Kapitel 11, Tabelle 1108",
        probe_result="Testlauf", as_of="Schuldenstand zum 31.12.2025")


def test_speichern_und_lesen(tmp_path, gelesen):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        assert store.save_schulden(gelesen["zeilen"], _herkunft()) == 12
        zeilen = store.get_schulden()
        assert [z["year"] for z in zeilen] == sorted(z["year"] for z in zeilen)
        assert all(z["herkunft_id"] for z in zeilen)
        # Der Vertrag des Bereichs: keine Zeile ohne Herkunft.
        assert store.herkunft_luecken().get("council_schulden") is None
        assert store.schulden_jahre()[-1] == 2025

        h = store.get_herkunft([zeilen[0]["herkunft_id"]])[0]
        assert h["kind"] == "city"
        assert h["probes"] and "Schuldenarten" in h["probes"][0]

        # Der Jahrgang ohne Aufteilung kommt auch aus der Datenbank ohne sie —
        # NULL bleibt NULL und wird nicht unterwegs zu einer Null.
        z2022 = next(z for z in zeilen if z["year"] == 2022)
        assert z2022["credit_market"] is None
        assert z2022["total"] == 281_457_000
        assert z2022["breakdown_rejected"] == 1_078_000
    finally:
        store.close()


def test_zweimal_speichern_aendert_nichts(tmp_path, gelesen):
    """Der Lauf ist idempotent — sonst wüchse die Tabelle mit der Zahl der
    Läufe statt mit der Zahl der Jahrgänge."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_schulden(gelesen["zeilen"], _herkunft())
        erst = store.get_schulden()
        store.save_schulden(gelesen["zeilen"], _herkunft())
        assert store.get_schulden() == erst
    finally:
        store.close()


def test_eine_teillieferung_raeumt_den_bestand_nicht_ab(tmp_path, gelesen):
    """Gespeichert wird, was mitkommt — nicht gelöscht, was fehlt.

    Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist, darf den vorher
    gespeicherten Stand dieses Jahrgangs nicht mit wegräumen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_schulden(gelesen["zeilen"], _herkunft())
        store.save_schulden([z for z in gelesen["zeilen"] if z["year"] == 2025],
                            _herkunft())
        assert len(store.get_schulden()) == 12
    finally:
        store.close()


def test_verschiedene_probenlagen_bekommen_verschiedene_herkuenfte(tmp_path, gelesen):
    """2022 steht auf einer anderen Probe als seine Nachbarn. Eine gemeinsame
    Herkunft behauptete für ihn eine Summenprobe, die er nicht bestanden hat —
    der Beleg auf der Seite muss für SEINE Zahl gelten."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        for lage in {tuple(z["probes"]) for z in gelesen["zeilen"]}:
            part = [z for z in gelesen["zeilen"] if tuple(z["probes"]) == lage]
            store.save_schulden(part, _herkunft(probe=list(lage)))
        zeilen = {z["year"]: z for z in store.get_schulden()}
        h2022 = store.get_herkunft([zeilen[2022]["herkunft_id"]])[0]
        h2025 = store.get_herkunft([zeilen[2025]["herkunft_id"]])[0]
        assert h2022["probe"] == "debt_per_capita"
        assert "debt_total_row" in h2025["probe"]
        assert store.herkunft_luecken().get("council_schulden") is None
    finally:
        store.close()


# --- Der Datenstand ---------------------------------------------------------


def test_datenstand_kennt_die_schicht(tmp_path, gelesen):
    """Die Schicht muss im Block „Stand der Daten" auftauchen, sonst
    beantwortet er die Frage „warum steht hier 2025 und nicht 2026?" für die
    Schulden nicht."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_schulden(gelesen["zeilen"], _herkunft())
        row = next(z for z in finanzquellen.datenstand(store)
                     if z["key"] == "schulden")
        assert row["neuester"] == 2025
        assert row["source"] == "Portal der Stadt"
        # Von Hand nachzuziehen — also muss dastehen, womit.
        assert row["automatisch"] is False
        assert "ingest_schulden.py" in finanzquellen.QUELLEN["schulden"].nachschub
    finally:
        store.close()


def test_bestandsschutz_haelt_einen_kaputten_parser_draussen():
    """Der Ingest schreibt nur gegen ein Ergebnis, das den Bestand trägt.

    `save_schulden` löscht zwar nichts, was eine Lieferung nicht mitbringt —
    ein halb gelesener Satz kann den Bestand also nicht abräumen. Er könnte
    ihn aber überschreiben, wenn die Stadt ihr Tabellenlayout ändert und der
    Parser nur noch die Hälfte versteht. Davor schützt diese Regel; `0 Zeilen`
    bleibt auch mit `--schrumpf-erlauben` tabu."""
    def entscheide(neu: int, schuetzen: bool = True) -> bool:
        p = finanzquellen.Protokoll(still=True)
        return finanzquellen.bestandsschutz(p, "Schuldenzeitreihe", 31, neu,
                                            schuetzen=schuetzen)

    assert entscheide(31) is True          # voller Lauf
    assert entscheide(12) is False         # kaputter Parser
    assert entscheide(0) is False          # gar nichts gelesen
    # Der bewusste Handgriff lässt einen kleineren Satz durch …
    assert entscheide(12, schuetzen=False) is True
    # … ein leeres Ergebnis aber nie.
    assert entscheide(0, schuetzen=False) is False


def test_endpunkt_liefert_reihe_abgrenzung_und_belege(tmp_path, gelesen):
    """Der Endpunkt muss drei Dinge zusammen ausliefern: die Zahlen, ihre
    Abgrenzung und den Beleg. Ohne die Abgrenzung ist die Zahl mehrdeutig,
    ohne den Beleg unbelegt."""
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1] / "web" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.routers.council import haushalt_schulden

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_schulden(gelesen["zeilen"], _herkunft())
        answer = haushalt_schulden(_user=None, store=store)

        assert answer["years"][-1] == 2025
        assert answer["series"][-1]["total"] == 336_994_000
        # Die Abgrenzung kommt aus dem Parser-Modul, nicht aus dem Frontend.
        assert answer["scope_note"] == schulden.ABGRENZUNG
        assert [a["field"] for a in answer["column_kinds"]] == list(schulden.ARTEN)

        # Jede Zeile findet ihren Beleg, und der trägt Erklärsätze.
        for row in answer["series"]:
            h = answer["herkunft"][str(row["herkunft_id"])]
            assert h["probes"], "Beleg ohne Erklärsatz"
            assert h["url"]
    finally:
        store.close()


def test_endpunkt_bleibt_ohne_bestand_ruhig(tmp_path):
    """Eine Datenbank ohne Ingest-Lauf liefert eine leere Reihe statt eines
    Fehlers — die Seite zeigt sich dann ohne Zeitreihe."""
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1] / "web" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.routers.council import haushalt_schulden

    store = CouncilStore(tmp_path / "leer.sqlite")
    try:
        answer = haushalt_schulden(_user=None, store=store)
        assert answer["series"] == [] and answer["years"] == []
        assert answer["scope_note"]
    finally:
        store.close()


def test_abgrenzung_ist_benannt():
    """Kern und Konzern unterscheiden sich bei den Schulden um ein Vielfaches.
    Welche Abgrenzung diese Zahlen meinen, darf deshalb nicht im Kopf einer
    Datei stehenbleiben — es muss ein Wert sein, den die Oberfläche anschreiben
    kann."""
    assert "Eigenbetriebe" in schulden.ABGRENZUNG
    assert "Beteiligungen" in schulden.ABGRENZUNG
    assert "Eigenbetriebe" in finanzquellen.QUELLEN["schulden"].was
