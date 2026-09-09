"""Ein Themen-Name, der in Wahrheit eine Liste ist (Teil B / PR 8).

Der Fall aus dem Bestand: „Stadtteile: Bürgerfelde Nord, Dietrichsfeld,
Helleheide, Brokhausen, Bloherfelde, Haarentor, Wechloy" — sieben Wünsche in
einem Feld, elf Treffer mit durchweg negativer Relevanz. Der Cross-Encoder
bewertet gegen EINEN Text, und eine Aufzählung hat kein Zentrum.

Der Erkenner ist bewusst konservativ: Ein falsches Aufteilen-Angebot ist
ärgerlicher als ein fehlendes.
"""
from __future__ import annotations

from council.topic_intel import aufteilbar


def test_der_echte_fall_aus_dem_bestand():
    name = ("Stadtteile: Bürgerfelde Nord, Dietrichsfeld, Helleheide, "
            "Brokhausen, Bloherfelde, Haarentor, Wechloy")
    teile = aufteilbar(name)
    assert teile == ["Bürgerfelde Nord", "Dietrichsfeld", "Helleheide",
                     "Brokhausen", "Bloherfelde", "Haarentor", "Wechloy"]


def test_zwei_themen_mit_komma():
    assert aufteilbar("Radverkehr, Kitas") == ["Radverkehr", "Kitas"]


def test_und_verbindet_haeufiger_als_es_aufzaehlt():
    """„Bus und Bahn" ist EIN Thema — es heißt sogar so in den Stadtthemen."""
    assert aufteilbar("Bus und Bahn") == []


def test_klammern_bleiben_unangetastet():
    """„Bebauungsplan 851 (Schützenweg, Haarentor)" ist eine Ortsangabe."""
    assert aufteilbar("Bebauungsplan 851 (Schützenweg, Haarentor)") == []


def test_ein_satz_mit_kommata_ist_keine_liste():
    assert aufteilbar("Wir wollen wissen, was der Rat zu Schulen sagt, und zwar genau") == []


def test_einzelne_namen_bleiben_einzeln():
    for name in ("Fliegerhorst", "Alte Fleiwa", "", "   ", "A, B"):
        assert aufteilbar(name) == [], name


def test_sehr_lange_listen_werden_nicht_angeboten():
    """Zwanzig Teile sind kein Bedienfehler mehr, sondern etwas anderes —
    und zwanzig Themen anzulegen wäre für niemanden ein Gefallen."""
    assert aufteilbar(", ".join(f"Ort {i}" for i in range(20))) == []


# ---- Die Fehlgriffe vom 09.09.2026, gemessen an plausiblen Eingaben ----

def test_ein_und_in_einem_teil_heisst_keine_liste():
    """„A, B und C" ist ein Satz mit Komma, kein Angebot für drei Themen —
    die erste Fassung machte daraus „A" und „B und C"."""
    assert aufteilbar("Radwege, Fahrradstraßen und Abstellanlagen") == []
    assert aufteilbar("Wohnen in Kreyenbrück, Bümmerstede und Krusenbusch") == []


def test_beisaetze_sind_keine_listen():
    for name in ("Oldenburg, Stadt der Wissenschaft", "Cäcilienbrücke, die Sanierung",
                 "Fliegerhorst, Wohnen für alle"):
        assert aufteilbar(name) == [], name


def test_zahlen_machen_einen_teil_zur_angabe():
    for name in ("Klimaschutz 2035, Maßnahmenplan", "Sanierung Cäcilienbrücke, Bauabschnitt 2",
                 "Bebauungsplan 851, Bebauungsplan 852"):
        assert aufteilbar(name) == [], name


def test_saubere_listen_gehen_weiterhin():
    assert aufteilbar("Kitas, Schulen, Spielplätze") == ["Kitas", "Schulen", "Spielplätze"]
    assert aufteilbar("Ofenerdiek; Etzhorn; Ohmstede") == ["Ofenerdiek", "Etzhorn", "Ohmstede"]
    assert aufteilbar("Themen: Wohnen, Verkehr, Klima") == ["Wohnen", "Verkehr", "Klima"]
    assert aufteilbar("Stadtteile: Bürgerfelde Nord,Dietrichsfeld,Haarentor") == [
        "Bürgerfelde Nord", "Dietrichsfeld", "Haarentor"]
