"""Prüfungsfeststellungen aus den Schlussberichten des Rechnungsprüfungsamts.

Das Fixture ist ein verkürzter, aber **wörtlicher** Ausschnitt aus dem echten
pypdf-Extrakt des Schlussberichts zum Jahresabschluss 2023 (``council_anlagen``
document_id 280863): Titelblock, Inhaltsverzeichnis, Randmarken-Legende und
zwei Abschnitte mit ihren Feststellungen — inklusive der Eigenheiten, an denen
ein naiver Parser scheitert:

- der Titel steht über vier Zeilen (ein ``LIKE 'Schlussbericht des …'`` in SQL
  findet damit gar nichts),
- die Legende schreibt die Marken in genau der Form, die auch im Fließtext
  gilt (wer sie mitzählt, zählt jede Marke einmal zu oft),
- eine Feststellung läuft über einen Seitenumbruch, die Kopfzeile steht also
  mitten im Textblock,
- Wörter sind am Zeilenende getrennt („Haus-\\nhaltsjahres").
"""
from __future__ import annotations

from council import pruefberichte
from council.store import CouncilStore

# --- Fixtures ---------------------------------------------------------------

TITEL = (
    "Schlussbericht \n"
    "des Rechnungsprüfungsamtes über die \n"
    "Prüfung des Jahresabschlusses 2023 \n"
    "der Stadt Oldenburg (Oldb) \n \n"
)

INHALT = """Inhaltsverzeichnis \n \n \nTextziffer   Seite \n \n \nVorbemerkungen 5 \n1. Grundlagen der Prüfung des Jahresabschlusses 6 \n1.1 Prüfungsauftrag 6 \n1.1.1 Prüfungsunterlagen 7 \n1.1.2 Vorlage 7 \n4.2.4 Bilanzposition: Schulden 35 \n4.2.5 Bilanzposition: Rückstellungen 37 \n
"""

LEGENDE = """In diesem Bericht verwendet das Rechnungsprüfungsamt zu den Prüfungsfeststellungen \nnachstehende Randbemerkungen: \n B  Beanstandung \n festgestellter bedeutsamer Mangel \n WB  Wiederholte Beanstandung \n ein bereits in Vorjahren festgestellter bedeutsamer Mangel, der noch nicht \nausgeräumt beziehungsweise erledigt worden ist \n H  Hinweis \n zur künftigen Beachtung beziehungsweise Beschreibung eines Sachverhaltes, der \nim Zusammenhang mit der Prüfung festgestellt worden ist   \nStadt Oldenburg (Oldb) - Rechnungsprüfungsamt 2 3 . 0 7 . 2 0 2 4  \nSchlussbericht über die Prüfung  \ndes Jahresabschlusses 2023  Seite 6 \n
"""

KOERPER = """
1. Grundlagen der Prüfung des Jahresabschlusses \n \n \n 1.1 Prüfungsauftrag \n \nDie Stadt Oldenburg führt ihre Haushaltswirtschaft nach den Grundsätzen ordnungsmäßiger \nBuchführung im Rechnungsstil der doppelten Buchführung gemäß § 110 Absatz 3 NKomVG. \n \n1.1.2 Vorlage \n \nDie dem Jahresabschluss 2023 zu Grunde liegende Bilanz gemäß § 55 KomHKVO wurde \nentgegen der gesetzlichen Vorgabe erst am 10.04.2024 vom Oberbürgermeister unterzeichnet \nund ging beim Rechnungsprüfungsamt am gleichen Tag ein. \n \n H  Die gesetzliche Frist zur Aufstellung des Jahresabschlusses wurde von der Verwaltung nicht \neingehalten. Das Rechnungsprüfungsamt weist daraufhin, dass zukünftig der Jahresabschluss \ngemäß § 129 Absatz 1 Satz 1 NKomVG innerhalb von drei Monaten nach Ende des Haus-\nhaltsjahres aufzustellen ist.  \n \nStadt Oldenburg (Oldb) - Rechnungsprüfungsamt 2 3 . 0 7 . 2 0 2 4  \nSchlussbericht über die Prüfung  \ndes Jahresabschlusses 2023  Seite 8 \n \nNach § 129 Absatz 1 Satz 2 NKomVG stellt der Oberbürgermeister den Jahresabschluss auf. \n \nStadt Oldenburg (Oldb) - Rechnungsprüfungsamt 2 3 . 0 7 . 2 0 2 4  \nSchlussbericht über die Prüfung  \ndes Jahresabschlusses 2023  Seite 36 \n \n4.2.4 Bilanzposition: Schulden  \n \nDie Anzahl der Buchungen reduzierte sich um rund 36 Prozent von 2.693 im Jahre 2022 auf \n1.723 im Jahre 2023. \n \n WB  Das Rechnungsprüfungsamt beanstandet, dass Akontozahlungen, insbesondere den Zeitraum \nvor dem Berichtsjahr betreffend, nicht zeitgerecht verbucht wurden. \n \nStadt Oldenburg (Oldb) - Rechnungsprüfungsamt 2 3 . 0 7 . 2 0 2 4  \nSchlussbericht über die Prüfung  \ndes Jahresabschlusses 2023  Seite 37 \n \nDie Verwaltung hat hierzu erklärt, dass eine entsprechende Umsetzung bis 31.12.2024 \nerfolgen soll. \n \n4.2.5 Bilanzposition: Rückstellungen  \n \nDie Reduzierung bei den Rückstellungen um rund 5,2 Millionen Euro ist vorrangig \nzurückzuführen auf notwendig gewordene Anpassungen. \n
"""

BERICHT = TITEL + INHALT + LEGENDE + KOERPER

#: Wörtlicher Anfang der formgleichen Berichte, die NICHT die Kernverwaltung
#: betreffen — sie tragen dieselbe Jahreszahl und ähnliche Labels.
STIFTUNG = (
    "Schlussbericht \nüber die Prüfung des Jahresabschlusses zum 31. Dezember 2023 "
    "der Klävemann-Stiftung \n"
)
EIGENBETRIEB = (
    "Bericht über die Prüfung des Jahresabschlusses und des Lageberichtes zum "
    "31.12.2023 des Eigenbetriebs Gebäudewirtschaft \n"
)
#: So sieht der Jahrgang 2024 im Bestand aus: Das PDF bringt keine
#: Zeichenzuordnung mit, der Extrakt besteht aus Glyphen-Nummern.
KAPUTT = "□\n□\n□\n/1 /2 /3 /4 /5 /6 /6 /7 /8 /9 /10 /2 /3 /11\n□\n/12 /8 /6 □ /13 /8 /2 \n"


# --- Zuordnung: welcher Bericht gehört zu welchem Abschluss? -----------------

def test_erkennt_jahrgang_trotz_vierzeiligem_titel():
    assert pruefberichte.erkenne_jahrgang(BERICHT) == 2023


def test_verwechselt_stiftung_und_eigenbetrieb_nicht():
    """Die Labels taugen zur Unterscheidung nicht — der Textanfang schon."""
    assert pruefberichte.erkenne_jahrgang(STIFTUNG) is None
    assert pruefberichte.erkenne_jahrgang(EIGENBETRIEB) is None


def test_kaputter_textextrakt_faellt_durch():
    """2024 wird nicht erzwungen: kein brauchbarer Text, keine zweite Kopie."""
    assert pruefberichte.erkenne_jahrgang(KAPUTT) is None
    assert pruefberichte.parse_feststellungen(KAPUTT)["feststellungen"] == []


# --- Legende und Inhaltsverzeichnis -----------------------------------------

def test_legende_kommt_aus_dem_dokument():
    legende = pruefberichte.parse_legende(BERICHT)
    assert sorted(legende) == ["B", "H", "WB"]  # 2023 kennt kein K mehr
    assert legende["WB"]["name"] == "Wiederholte Beanstandung"
    assert legende["WB"]["explanation"].startswith("ein bereits in Vorjahren")
    # Die Erläuterung darf nicht in den Bericht hineinlaufen.
    assert "Grundlagen der Prüfung" not in legende["H"]["explanation"]


def test_inhaltsverzeichnis_liefert_textziffern():
    ivz = pruefberichte.parse_inhaltsverzeichnis(BERICHT)
    assert ivz["1.1.2"] == "Vorlage"
    assert ivz["4.2.4"] == "Bilanzposition: Schulden"


# --- Feststellungen ---------------------------------------------------------

def test_feststellungen_mit_marke_textziffer_und_seite():
    result = pruefberichte.parse_feststellungen(BERICHT)
    assert result["year"] == 2023
    assert result["verworfen"] == []
    gefunden = result["feststellungen"]
    assert [f["mark"] for f in gefunden] == ["H", "WB"]

    note, beanstandung = gefunden
    assert note["text_number"] == "1.1.2"
    assert note["section"] == "Vorlage"
    assert note["mark_name"] == "Hinweis"
    assert note["page"] == 6  # letzte Kopfzeile vor der Marke
    assert beanstandung["text_number"] == "4.2.4"
    assert beanstandung["page"] == 36
    assert beanstandung["mark_name"] == "Wiederholte Beanstandung"


def test_legende_wird_nicht_mitgezaehlt():
    """Die Legende schreibt B/WB/H genau wie der Fließtext. Wer vor dem
    Berichtsanfang zu zählen beginnt, zählt jede Marke einmal zu oft."""
    gefunden = pruefberichte.parse_feststellungen(BERICHT)["feststellungen"]
    assert len(gefunden) == 2
    assert not any("festgestellter bedeutsamer Mangel" == f["text"] for f in gefunden)


def test_text_endet_an_der_naechsten_ueberschrift():
    beanstandung = pruefberichte.parse_feststellungen(BERICHT)["feststellungen"][1]
    assert beanstandung["text"].endswith("nicht zeitgerecht verbucht wurden.")
    assert "Rückstellungen" not in beanstandung["text"]


def test_seitenkopf_faellt_aus_dem_text():
    """Die Kopfzeile steht mitten im Block, wenn ein Befund über einen
    Seitenumbruch läuft — im Zitat hat sie nichts zu suchen."""
    for f in pruefberichte.parse_feststellungen(BERICHT)["feststellungen"]:
        assert "Seite 3" not in f["text"]
        assert "2 3 . 0 7 . 2 0 2 4" not in f["text"]
        assert "Seite 3" not in (f["follow_paragraph"] or "")


def test_silbentrennung_wird_zusammengezogen():
    note = pruefberichte.parse_feststellungen(BERICHT)["feststellungen"][0]
    assert "Haushaltsjahres" in note["text"]
    assert "Haus-" not in note["text"]


def test_ergaenzungsstrich_bleibt_stehen():
    """„Ertrags-\\nund Aufwandsseite" ist kein Trennstrich."""
    assert pruefberichte.saeubern("Ertrags-\nund Aufwandsseite") == "Ertrags- und Aufwandsseite"
    assert pruefberichte.saeubern("Programm-\nUpdates") == "Programm-Updates"
    assert pruefberichte.saeubern("Bescheini-\ngungen") == "Bescheinigungen"


def test_antwort_der_verwaltung_steht_getrennt():
    """Was direkt darauf folgt, gehört dazu — aber nicht in die Beanstandung."""
    beanstandung = pruefberichte.parse_feststellungen(BERICHT)["feststellungen"][1]
    assert beanstandung["follow_paragraph"].startswith("Die Verwaltung hat hierzu erklärt")
    assert "Die Verwaltung hat hierzu erklärt" not in beanstandung["text"]


# --- Der Konsistenz-Check: was die Klammer nicht erfüllt, fliegt raus --------

def test_marke_ohne_legendeneintrag_wird_verworfen():
    """Der Bericht 2023 erklärt kein K. Eine K-Marke im Fließtext ist damit
    ein Extraktionsartefakt und keine Feststellung — sie zu übernehmen hieße,
    dem Dokument etwas zu unterstellen, was es nicht sagt."""
    manipuliert = BERICHT.replace(
        "\n WB  Das Rechnungsprüfungsamt beanstandet, dass Akontozahlungen",
        "\n K  Das Rechnungsprüfungsamt beanstandet, dass Akontozahlungen")
    result = pruefberichte.parse_feststellungen(manipuliert)
    assert [f["mark"] for f in result["feststellungen"]] == ["H"]
    assert result["verworfen"] == [
        {"mark": "K", "grund": "nicht in der Legende erklärt"}]


def test_marke_ohne_textziffer_wird_verworfen():
    """Ohne Inhaltsverzeichnis gibt es keine Fundstelle — und ohne Fundstelle
    keine Feststellung, auch wenn die Marken im Text stehen."""
    ohne_ivz = BERICHT.replace(INHALT, "Inhaltsverzeichnis \n \n")
    result = pruefberichte.parse_feststellungen(ohne_ivz)
    assert result["year"] == 2023
    assert result["feststellungen"] == []


def test_bericht_ohne_legende_liefert_nichts():
    ohne_legende = BERICHT.replace("Randbemerkungen", "Anmerkungen")
    assert pruefberichte.parse_feststellungen(ohne_legende)["feststellungen"] == []


def test_unterschrift_der_amtsleitung_ist_keine_marke():
    """Am Berichtsende steht der Name in gesperrter Schrift („K R U P K E").
    Mit nur einem Leerzeichen hinter der Marke ginge er als K-Marke durch."""
    mit_unterschrift = BERICHT + "\nK R U P K E \nLeiterin des Rechnungsprüfungsamtes \n"
    result = pruefberichte.parse_feststellungen(mit_unterschrift)
    assert [f["mark"] for f in result["feststellungen"]] == ["H", "WB"]


# --- Ketten über Jahrgänge --------------------------------------------------

def test_kettenschluessel_ueberbrueckt_umbenennungen():
    """„Internes Kontrollsystem (IKS)" heißt ab 2020 nur noch „Internes
    Kontrollsystem" — dieselbe Sache, also derselbe Schlüssel."""
    assert (pruefberichte.kettenschluessel("Internes Kontrollsystem (IKS)")
            == pruefberichte.kettenschluessel("Internes Kontrollsystem"))
    assert (pruefberichte.kettenschluessel("Plan-Ist-Vergleich")
            != pruefberichte.kettenschluessel("Haushaltsüberwachung"))


# --- Speicherung ------------------------------------------------------------

def test_speichern_und_lesen(tmp_path, quelle):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        gefunden = pruefberichte.parse_feststellungen(BERICHT)["feststellungen"]
        n = store.save_pruefbericht(2023, gefunden, quelle(
            "Schlussbericht 2023",
            "https://buergerinfo.oldenburg.de/getfile.php?id=280863&type=do",
            probe="legende_und_verzeichnis"))
        assert n == 2
        assert store.pruefbericht_jahre() == [2023]
        zeilen = store.get_pruefberichte()
        assert [z["mark"] for z in zeilen] == ["H", "WB"]
        assert zeilen[1]["text_number"] == "4.2.4"
        assert zeilen[1]["kette"] == pruefberichte.kettenschluessel("Bilanzposition: Schulden")
        assert zeilen[1]["source_url"].endswith("id=280863&type=do")

        # Erneuter Ingest ersetzt den Jahrgang, statt ihn zu verdoppeln.
        store.save_pruefbericht(2023, gefunden, quelle(
            "Schlussbericht 2023", "https://example.org/sb2023.pdf",
            probe="legende_und_verzeichnis"))
        assert len(store.get_pruefberichte(2023)) == 2
    finally:
        store.close()


# --------------------------------------------------------------------------
# Der Titel muss vorne stehen — aber nicht an Position 0
# --------------------------------------------------------------------------

BRIEFKOPF = ("Stadt Oldenburg\nStadt Oldenburg (Oldb) | Rechnungsprüfungsamt\n\n"
             "Schlussbericht des Rechnungsprüfungsamtes über die Prüfung\n"
             "des Jahresabschlusses 2024 der Stadt Oldenburg (Oldb)\n")
OHNE_BRIEFKOPF = ("Schlussbericht des Rechnungsprüfungsamtes über die Prüfung\n"
                  "des Jahresabschlusses 2022 der Stadt Oldenburg (Oldb)\n")
STIFTUNG = ("Stadt Oldenburg (Oldb) | Rechnungsprüfungsamt\n"
            "Schlussbericht des Rechnungsprüfungsamtes über die Prüfung\n"
            "des Jahresabschlusses zum 31. Dezember 2024 der Klävemann-Stiftung\n")


def test_briefkopf_vor_dem_titel_faellt_nicht_mehr_durch():
    """Der Schlussbericht 2024 hat keine brauchbare Textebene und muss per OCR
    gelesen werden — dort steht davor, was auf dem Papier auch davorsteht.

    Mit dem alten ``^``-Anker fiel der Jahrgang durch, ohne dass irgendetwas
    an ihm falsch war."""
    assert pruefberichte.erkenne_jahrgang(BRIEFKOPF) == 2024


def test_ohne_briefkopf_geht_es_weiterhin():
    """Die Textebene der älteren Jahrgänge beginnt direkt mit dem Titel."""
    assert pruefberichte.erkenne_jahrgang(OHNE_BRIEFKOPF) == 2022


def test_ein_stiftungsbericht_geht_weiterhin_nicht_durch():
    """Die Unterscheidung leistet „der Stadt Oldenburg" am Ende des Titels,
    nicht die Position: Die Stiftungs- und Eigenbetriebsberichte schreiben
    dort „…des Jahresabschlusses zum 31. Dezember". Genau das war der Grund
    für die strenge Erkennung — und genau das bleibt streng."""
    assert pruefberichte.erkenne_jahrgang(STIFTUNG) is None


def test_der_titel_muss_trotzdem_vorne_stehen():
    """Ein Fenster, kein Freibrief: Mitten im Bericht wird ein Schlussbericht
    nicht noch einmal betitelt."""
    weit_hinten = ("Blindtext. " * 200) + OHNE_BRIEFKOPF
    assert pruefberichte.erkenne_jahrgang(weit_hinten) is None
