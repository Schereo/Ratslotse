"""Die Investitionen des Finanzhaushalts — und die Probe, die sie trägt.

Diese Schicht ist die erste des Haushalts-Bereichs, deren Quelle eine
Rechenprobe **in der Datei selbst** mitbringt: Die Teilhaushalts-Zeilen ergeben
die Summenzeile, die dieselbe Datei ausweist. Damit hängt alles an einer Frage,
und die wird hier von beiden Seiten geprüft:

1. Geht die Probe an echten Dateien auf? (``FH_2022`` und ``FH_2025`` sind
   **wörtlich** die CSVs des Portals, 782 bzw. 775 Byte — ganz, nicht gekürzt.)
2. Wird ein Jahrgang, der sie reißt, wirklich **verworfen** statt geschätzt?
   Vier Wege hinein: ein manipulierter Betrag, eine fehlende Summenzeile, eine
   zu kurze Tabelle, eine fremde Kopfzeile.

Dazu die zwei Dinge, die still falsch werden könnten und dann niemandem
auffallen:

* Der *Gesamtbetrag des Finanzhaushaltes* darf **nicht** als geprüft
  dastehen. Er zählt die laufende Verwaltungstätigkeit mit, keine Zeile der
  Datei summiert sich auf ihn — er bekommt deshalb eine eigene Herkunft mit
  ``herkunft.UNGEPRUEFT``. Eine gemeinsame Herkunft mit den Investitionen
  behauptete für ihn eine Probe, die es nicht gibt.
* Ein Teilhaushalt muss über die Jahrgänge hinweg **denselben Namen** tragen.
  Das Portal schreibt 2022 „Verkehr und Straßenbau" und 2025 „Verkehr und
  Strassenbau"; wer das durchlässt, hat in jeder Zeitreihe zwei Bereiche, wo
  einer ist.
"""
from __future__ import annotations

import pytest

from council import finanzquellen, herkunft, investitionen as inv
from council.store import CouncilStore

# --- Echte Dateien des Open-Data-Portals (Datensatz 1101) -------------------
# Abgerufen am 16.08.2026, wörtlich und vollständig. 2022 ist der Jahrgang mit
# den Schreibweisen-Ausreißern: „Sicherheit  und Ordnung" mit doppeltem
# Leerzeichen, „Gruen u Friedhoefe" statt „Gruen und Friedhoefe", und als
# einziger mit der Kopfzeile „Einzahlungen in Euro" statt „[Euro]".

FH_2022 = """Teilhaushalt;Bezeichnung;Einzahlungen in Euro;Auszahlungen in Euro
THH01;Verwaltungsfuehrung;0;36800
THH02;Personal- und Verwaltungsmanagement;10000;1772000
THH03;Wirtschaftsfoerderung, Liegenschaften;20282920;16594000
THH04;Finanzmanagement und Recht;4438981;59217661
THH05;Sicherheit  und Ordnung;35000;1254220
THH06;Kultur, Museen, Sport;0;3383400
THH07;Stadtplanung;2296200;2185000
THH08;Verkehr und Straßenbau;4234600;9708500
THH09;Umwelt, Bauordnung, Gruen u Friedhoefe;100000;5210200
THH10;Soziales und Gesundheit;0;18000
THH11;Jugend und Familie;900000;1756500
THH12;Schule und Bildung;2033000;3673500
THH13;Nicht rechtsfaehige Stiftungen;26700;0
Finanzhaushalt Gesamtinvestitionen;;34357401;104809781
Gesamtbetrag des Finanzhaushaltes;;668235559;709888388
"""

FH_2025 = """Teilhaushalt;Bezeichnung;Einzahlungen [Euro];Auszahlungen [Euro]
THH01;Verwaltungsfuehrung;0;44500
THH02;Personal- und Verwaltungsmanagement;8000;1542500
THH03;Wirtschaftsfoerderung, Liegenschaften;13878863;14130150
THH04;Finanzmanagement und Recht;21065300;36813610
THH05;Sicherheit und Ordnung;80000;1855000
THH06;Kultur, Museen, Sport;120000;1356400
THH07;Stadtplanung;4206000;4259000
THH08;Verkehr und Strassenbau;145000;10451500
THH09;Umwelt, Bauordnung, Gruen und Friedhoefe;141000;5918860
THH10;Soziales und Gesundheit;0;782000
THH11;Jugend und Familie;0;1715500
THH12;Schule und Bildung;0;1912500
THH13;Nicht rechtsfaehige Stiftungen;27900;0
Finanzhaushalt Gesamtinvestitionen;;39672063;80781520
Gesamtbetrag des Finanzhaushaltes;;743796496;850520503
"""


# --- Die Probe geht auf ------------------------------------------------------

@pytest.mark.parametrize("text, jahr, ein, aus", [
    (FH_2022, 2022, 34_357_401, 104_809_781),
    (FH_2025, 2025, 39_672_063, 80_781_520),
])
def test_echte_datei_besteht_die_summenprobe(text, jahr, ein, aus):
    """Beide Jahrgänge gehen auf — und zwar auf den Euro genau."""
    r = inv.lies(text, jahr)
    assert r["bestanden"] is True
    assert len(r["zeilen"]) == 13
    assert r["gesamt"]["einzahlungen"] == ein
    assert r["gesamt"]["auszahlungen"] == aus
    # Die Probe rechnet wirklich, statt die Zeile nur abzuschreiben.
    assert sum(z["einzahlungen"] for z in r["zeilen"]) == ein
    assert sum(z["auszahlungen"] for z in r["zeilen"]) == aus
    # Der Nachweis steht später neben der Zahl auf der Seite.
    assert "13 Teilhaushalte" in r["nachweis"]
    # Deutsche Schreibweise: Der Satz steht später im Beleg neben der Zahl.
    assert "Restbetrag 0,00 €" in r["nachweis"]


def test_teilhaushalte_kommen_sortiert_und_vollstaendig():
    r = inv.lies(FH_2025, 2025)
    assert [z["thh_nr"] for z in r["zeilen"]] == list(range(1, 14))


def test_gesamtbetrag_finanzhaushalt_wird_getrennt_gefuehrt():
    """Die Bezugsgröße ist um ein Vielfaches größer als die Investitionen —
    genau deshalb darf sie nicht in derselben Summe landen."""
    r = inv.lies(FH_2025, 2025)
    assert r["finanzhaushalt"]["auszahlungen"] == 850_520_503
    assert r["gesamt"]["auszahlungen"] == 80_781_520
    assert r["finanzhaushalt"]["auszahlungen"] > 10 * r["gesamt"]["auszahlungen"]


# --- Die Probe reißt: verworfen statt geschätzt ------------------------------

def test_manipulierter_betrag_wird_verworfen():
    """Ein einziger geänderter Euro reicht — und dann gibt es keine halben
    Zahlen, sondern gar keine.

    Genau ein Euro ist hier die schärfste Probe, die die Datei zulässt: Sie
    führt volle Euro, kleiner kann eine Abweichung nicht sein. Eine Toleranz
    von 1 € wäre für diesen Fall blind (s. ``inv.TOLERANZ_EUR``)."""
    kaputt = FH_2025.replace("THH08;Verkehr und Strassenbau;145000;10451500",
                             "THH08;Verkehr und Strassenbau;145000;10451501")
    r = inv.lies(kaputt, 2025)
    assert r["bestanden"] is False
    assert r["zeilen"] == []
    assert r["gesamt"] is None
    # Die Bezugsgröße fällt mit: ohne geprüfte Investitionssumme daneben wäre
    # sie eine große Zahl ohne Aussage.
    assert r["finanzhaushalt"] is None
    assert "Auszahlungen" in r["nachweis"]
    # Und die Begründung nennt die Beträge deutsch, nicht „80,781,521.00".
    assert "80.781.521,00 €" in r["nachweis"]
    assert "+1,00 €" in r["nachweis"]


def test_probe_prueft_auch_die_einzahlungsspalte():
    """Nur die Auszahlungen zu prüfen wäre die halbe Probe."""
    kaputt = FH_2025.replace("THH03;Wirtschaftsfoerderung, Liegenschaften;13878863;",
                             "THH03;Wirtschaftsfoerderung, Liegenschaften;13878000;")
    r = inv.lies(kaputt, 2025)
    assert r["bestanden"] is False
    assert "Einzahlungen" in r["nachweis"]


def test_fehlende_summenzeile_wird_verworfen():
    ohne = "\n".join(ln for ln in FH_2025.splitlines()
                     if not ln.startswith("Finanzhaushalt Gesamtinvestitionen"))
    r = inv.lies(ohne, 2025)
    assert r["bestanden"] is False
    assert "fehlt" in r["nachweis"]


def test_zu_kurze_tabelle_wird_verworfen():
    """Zwei Zeilen, deren Summe zufällig aufgeht, sind keine Tabelle."""
    kurz = ("Teilhaushalt;Bezeichnung;Einzahlungen [Euro];Auszahlungen [Euro]\n"
            "THH01;Verwaltungsfuehrung;0;100\n"
            "THH02;Personal- und Verwaltungsmanagement;0;200\n"
            "Finanzhaushalt Gesamtinvestitionen;;0;300\n")
    r = inv.lies(kurz, 2025)
    assert r["bestanden"] is False
    assert "Teilhaushalts-Zeilen" in r["nachweis"]


def test_fremde_kopfzeile_wird_abgewiesen():
    """Läge unter der URL das Ergebnishaushalt-Blatt, hätte es Erträge statt
    Einzahlungen — und seine Summenprobe ginge womöglich trotzdem auf."""
    fremd = ("Teilhaushalt;Bezeichnung;Erträge;Aufwendungen\n"
             "THH01;Verwaltungsfuehrung;0;100\n"
             "Finanzhaushalt Gesamtinvestitionen;;0;100\n")
    r = inv.lies(fremd, 2025)
    assert r["bestanden"] is False
    assert "Kopfzeile" in r["nachweis"]
    assert inv.kopfprobe("Teilhaushalt;Bezeichnung;Erträge;Aufwendungen") is False
    assert inv.kopfprobe(FH_2022.splitlines()[0]) is True


def test_leere_datei():
    assert inv.lies("", 2025)["bestanden"] is False


# --- Schreibweisen und Jahrgang ---------------------------------------------

def test_teilhaushalt_heisst_ueber_die_jahrgaenge_gleich():
    """Sonst stünden in jeder Zeitreihe zwei Bereiche, wo einer ist."""
    def namen(text, jahr):
        return {z["thh_nr"]: z["bezeichnung"] for z in inv.lies(text, jahr)["zeilen"]}

    a, b = namen(FH_2022, 2022), namen(FH_2025, 2025)
    assert a[8] == b[8] == "Verkehr und Straßenbau"
    assert a[9] == b[9] == "Umwelt, Bauordnung, Grün und Friedhöfe"
    assert a[1] == b[1] == "Verwaltungsführung"
    # Doppeltes Leerzeichen im Portal-Namen darf nicht durchschlagen.
    assert a[5] == b[5] == "Sicherheit und Ordnung"


def test_unbekannter_name_laeuft_unveraendert_durch():
    """Ein neuer Teilhaushalts-Zuschnitt soll den Import nicht stoppen."""
    assert inv.name("Digitalisierung und Neues") == "Digitalisierung und Neues"


def test_jahrgang_kommt_aus_dem_dateinamen():
    """Die Datei selbst trägt keine Jahresangabe — die schwächste Stelle
    dieser Quelle, und deshalb eine eigene, geprüfte Funktion."""
    assert inv.jahrgang_aus_url(
        "https://opendata.oldenburg.de/sites/default/files/"
        "1101_Haushaltsplan_StadtOL_2025_Finanzhaushalt.csv") == 2025
    assert inv.jahrgang_aus_url(
        "https://opendata.oldenburg.de/sites/default/files/"
        "1101_Haushaltsplan_StadtOL_2024_Ergebnishaushalt.csv") is None
    assert inv.jahrgang_aus_url(None) is None


def test_alle_hinterlegten_urls_tragen_ihren_jahrgang():
    """Sonst spräche eine Zeile über ein anderes Jahr, als ihre URL zeigt."""
    from council import haushalt

    for jahr, url in haushalt.INVESTITIONEN_CSV_URLS.items():
        assert inv.jahrgang_aus_url(url) == jahr


# --- Speichern: Herkunft je Zeile, zwei Proben, keine Lücken -----------------

def _speichern(store: CouncilStore, text: str, jahr: int) -> dict:
    r = inv.lies(text, jahr)
    anker = dict(art="opendata", url=f"https://example.org/{jahr}_Finanzhaushalt.csv",
                 label=f"Finanzhaushalt der Stadt Oldenburg {jahr}")
    store.save_investitionen(
        jahr, r["zeilen"], r["gesamt"],
        herkunft.Herkunft(probe="investitionen_summenzeile",
                          fundstelle="Datensatz 1101, Tabellenblatt Finanzhaushalt",
                          probe_ergebnis=r["nachweis"], **anker),
        finanzhaushalt=r["finanzhaushalt"],
        herkunft_finanzhaushalt=herkunft.Herkunft(
            probe=herkunft.UNGEPRUEFT,
            fundstelle="Zeile „Gesamtbetrag des Finanzhaushaltes“", **anker))
    return r


def test_speichern_und_lesen(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2025, 2025)

    assert store.investitionen_jahre() == [2025]
    zeilen = store.get_investitionen(jahr=2025, ebene="teilhaushalt")
    assert len(zeilen) == 13
    assert {z["bezeichnung"] for z in zeilen} >= {"Schule und Bildung"}
    gesamt = store.get_investitionen(jahr=2025, ebene="investitionen")
    assert len(gesamt) == 1
    assert gesamt[0]["auszahlungen"] == 80_781_520
    # Jede Zeile weiß, woher sie kommt.
    assert store.herkunft_luecken() == {}
    assert all(z["herkunft_id"] is not None for z in store.get_investitionen())


def test_bezugsgroesse_traegt_ungeprueft_die_investitionen_nicht(tmp_path):
    """Die eine Verwechslung, die diese Schicht teuer machen würde."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2025, 2025)

    je_ebene = {z["ebene"]: z for z in store.get_investitionen(jahr=2025)
                if z["ebene"] != "teilhaushalt"}
    herkuenfte = {h["id"]: h for h in store.get_herkunft()}
    geprueft = herkuenfte[je_ebene["investitionen"]["herkunft_id"]]
    bezug = herkuenfte[je_ebene["finanzhaushalt"]["herkunft_id"]]

    assert geprueft["probe"] == "investitionen_summenzeile"
    assert bezug["probe"] == herkunft.UNGEPRUEFT
    # Zwei verschiedene Aussagen, zwei verschiedene Datensätze.
    assert geprueft["id"] != bezug["id"]
    # Und der Erklärsatz für Leser*innen hängt dran.
    assert geprueft["proben"] and "Summenzeile" in geprueft["proben"][0]


def test_erneuter_lauf_ersetzt_statt_zu_verdoppeln(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2025, 2025)
    vorher = len(store.get_herkunft())
    _speichern(store, FH_2025, 2025)

    assert len(store.get_investitionen(jahr=2025)) == 15
    # Idempotent über den Fingerabdruck: keine neuen Herkunfts-Datensätze.
    assert len(store.get_herkunft()) == vorher


def test_jahrgaenge_stehen_nebeneinander(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2022, 2022)
    _speichern(store, FH_2025, 2025)
    assert store.investitionen_jahre() == [2022, 2025]
    assert len(store.get_investitionen()) == 30


# --- Registrierung: Probe, Tabelle, Quelle ----------------------------------

def test_probe_ist_mit_erklaersatz_registriert():
    """Ohne Eintrag in ``herkunft.PROBEN`` ließe sich die Herkunft gar nicht
    bauen — und im Beleg-Chip stünde nichts."""
    assert "investitionen_summenzeile" in herkunft.PROBEN
    assert "council_investitionen" in herkunft.HERKUNFT_TABELLEN
    with pytest.raises(ValueError):
        herkunft.Herkunft(art="opendata", probe="gibtsnicht",
                          url="https://example.org/x.csv")


def test_quelle_steht_im_datenstand(tmp_path):
    """Sonst fehlte die Schicht auf ``/haushalt`` — und niemand sähe, wenn ein
    Jahrgang ausbleibt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2025, 2025)

    assert "investitionen" in finanzquellen.REIHENFOLGE
    q = finanzquellen.QUELLEN["investitionen"]
    assert q.tabelle == "council_investitionen"
    assert q.bestand(store) == {(2025,)}
    # Kein Selbstlauf: Der Cron lädt nichts herunter, er meldet nur.
    assert q.automatisch is False
    assert q.nachschub and "ingest_finanzen_opendata" in q.nachschub

    zeile = next(z for z in finanzquellen.datenstand(store)
                 if z["key"] == "investitionen")
    assert zeile["jahrgaenge"] == [2025]
    assert zeile["quelle"] == "Open-Data-Portal der Stadt"


def test_takt_meldet_den_jahrgang_erst_im_folgejahr():
    """Gemessen an den vier Lieferungen des Portals: Der Jahrgang erscheint im
    Juni/Juli des FOLGEJAHRES (2025 → 14.07.2026). Wer hier früher meldet,
    schickt eine Überfällig-Warnung für etwas, das planmäßig läuft."""
    from datetime import date

    q = finanzquellen.QUELLEN["investitionen"]
    assert q.faellig_ab(2025) == date(2026, 7, 1)
    # Mitte 2026 ist 2025 der jüngste Jahrgang, den man erwarten darf.
    assert q.neuester_erwarteter(date(2026, 8, 16)) == 2025
    assert q.neuester_erwarteter(date(2026, 3, 1)) == 2024


def test_bestandsschutz_haelt_einen_leeren_lauf_drauSSen(tmp_path):
    """Ein leeres Ergebnis ersetzt nie einen gefüllten Jahrgang."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _speichern(store, FH_2025, 2025)
    p = finanzquellen.Protokoll(still=True)
    assert finanzquellen.bestandsschutz(p, "Investitionen 2025", 15, 0) is False
    assert p.warnungen
