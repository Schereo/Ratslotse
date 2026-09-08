"""Der Ausweg aus einer Sackgasse (Plan „Sehen und Zurückholen", Teil B / PR 7).

Der Anlass steht im Datenbestand: Am 09.08.2026 fragte jemand zweimal nach
„Giftmüll am Fliegerhorst", bekam zweimal „keine Informationen" und gab zweimal
Daumen runter — einmal mit dem Grund „Falschinfo". Er hatte recht; die
Unterlagen sagen „Sondermüll" und „Schießanlage".

Was hier festgehalten wird, ist vor allem die Bremse: Ein Vorschlag, der auch
danebenliegt, ist schlechter als keiner.
"""
from __future__ import annotations

from council.qa import alternativ_fragen


class FakeStore:
    """Ein Bestand aus wenigen Zeilen — die Regeln sollen ohne echte Datenbank
    prüfbar sein, sonst prüft der Test die Daten und nicht die Regel."""

    def __init__(self, zeilen: dict[int, str], volltext: dict[str, list[int]]):
        self._zeilen = zeilen
        self._volltext = volltext

    def search_decisions_fts(self, query: str, limit: int = 40):
        return [(i, 1.0, "") for i in self._volltext.get(query.lower(), [])][:limit]

    def get_decisions_by_ids(self, ids):
        return [{"id": i, "title": self._zeilen[i]} for i in ids if i in self._zeilen]


def test_das_wort_der_frage_muss_im_titel_stehen():
    """Ohne diese Bedingung schlug „Wie ist das Wetter morgen?" Grünstreifen,
    Sportförderung und einen Abfall-Lernpfad vor (gemessen, 08.09.2026)."""
    store = FakeStore(
        {1: "Pflege der Grünstreifen", 2: "Förderung des Sports"},
        {"wetter": [1, 2]},
    )
    assert alternativ_fragen(store, "Wie ist das Wetter morgen?") == []


def test_der_treffer_im_titel_wird_angeboten():
    store = FakeStore(
        {1: "Erweiterung des Sanierungsgebietes Fliegerhorst",
         2: "Irgendetwas ganz anderes"},
        {"fliegerhorst": [1, 2]},
    )
    fragen = alternativ_fragen(store, "Was ist mit dem Giftmüll am Fliegerhorst?")
    assert fragen == ['Was wurde zu „Erweiterung des Sanierungsgebietes Fliegerhorst“ entschieden?']


def test_teilwoerter_treffen_deutsche_komposita():
    """„Leerstand" muss „Wohnungsleerstand" finden — sonst greift die Regel bei
    genau der Wortbildung nicht, um die es im Deutschen ständig geht."""
    store = FakeStore({1: "Wohnungsleerstand in Oldenburg – Ergebnisse des Zensus"},
                      {"leerstand": [1]})
    fragen = alternativ_fragen(store, "Welcher Stadtteil hat den höchsten Leerstand?")
    assert len(fragen) == 1 and "Wohnungsleerstand" in fragen[0]


def test_geruestwoerter_gewinnen_nicht_gegen_den_inhalt():
    """„Thema" und „Fliegerhorst" standen beide in derselben Frage; die erste
    Fassung wählte „Thema" und schlug Vorträge über strukturellen Rassismus
    vor."""
    store = FakeStore(
        {1: 'Vortrag zum Thema "struktureller Rassismus"',
         2: "Sanierungsgebiet Fliegerhorst"},
        {"thema": [1], "fliegerhorst": [2]},
    )
    fragen = alternativ_fragen(store, "Erzähl mir was über das Thema Giftmüll am Fliegerhorst")
    assert fragen and "Fliegerhorst" in fragen[0] and "Rassismus" not in fragen[0]


def test_ohne_brauchbares_wort_kommt_nichts():
    store = FakeStore({}, {})
    assert alternativ_fragen(store, "Wie backe ich einen Kuchen?") == []
    assert alternativ_fragen(store, "") == []


def test_gedeckelt_auf_drei():
    store = FakeStore({i: f"Radverkehr Maßnahme {i}" for i in range(1, 9)},
                      {"radverkehr": list(range(1, 9))})
    assert len(alternativ_fragen(store, "Was läuft beim Radverkehr?")) == 3


def test_ein_kaputter_store_bricht_nichts():
    """Ein Ausweg, der wirft, macht aus einer schlechten Antwort einen Fehler."""

    class Kaputt:
        def search_decisions_fts(self, query, limit=40):
            raise RuntimeError("Index weg")

        def get_decisions_by_ids(self, ids):
            return []

    assert alternativ_fragen(Kaputt(), "Was ist mit dem Fliegerhorst?") == []
