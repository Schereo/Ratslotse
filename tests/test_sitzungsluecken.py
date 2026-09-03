"""Zwei Löcher im Sitzungs-/Protokollbestand, gefunden am 03.09.2026 über die
Frage „warum steht bei zwei Ausschüssen keine Beschlusszahl?".

* Der Kalenderlauf sah nur nach vorn — 14 der 79 Sitzungen des Jahres 2026
  fehlten dauerhaft, darunter die einzige Sitzung des Ausschusses für
  Wirtschaftsförderung.
* Die Protokoll-Erkennung verlangte das Wort „öffentlich" in der Beschriftung —
  der Ausschuss für Allgemeine Angelegenheiten schreibt es nicht dazu und stand
  seit seiner ersten Sitzung ohne jeden Beschluss da.

Beides ohne Netz geprüft: die Beschriftungsregel gegen echte Beschriftungen aus
dem Ratsinfo, der Rückblick gegen einen Scraper-Doppelgänger.
"""
from datetime import date, timedelta

import pytest

from council.protocols import is_public_protocol_label
from council.scraper import CouncilScraper


# ------------------------------------------------------ Protokoll-Beschriftung

@pytest.mark.parametrize("label", [
    "Protokoll Rat 29.06.2026 öffentlich",          # die übliche Oldenburger Form
    "Protokoll KulturA 16.06.2026 öffentlich",
    "Protokoll (öffentlich) AFB 03.06.2026",
    "Protokoll AAA 17.08.2026",                      # der Ausschuss, der es weglässt
    "Protokoll ASUK 11.06.2026",
    "Niederschrift über die Sitzung vom 01.06.2026",
])
def test_oeffentliches_protokoll_wird_erkannt(label):
    assert is_public_protocol_label(label)


@pytest.mark.parametrize("label", [
    "Niederschrift 12/25 nichtöffentlich",
    "Protokoll nicht öffentlich",
    "Protokoll nicht-öffentlich",
    # Eine Vorlage ÜBER ein Protokoll ist kein Protokoll — der Genitiv verrät sie.
    "Genehmigung des Protokolls Nr. 07/26 vom 11.05.2026",
    "Vorlage",
    "Aushang",
])
def test_fremde_beschriftungen_bleiben_draussen(label):
    assert not is_public_protocol_label(label)


# ------------------------------------------------------------------ Rückblick

class _KalenderDoppel(CouncilScraper):
    """Ein Ratsinfo aus dem Gedächtnis: je Monat eine Liste von Sitzungs-IDs."""

    def __init__(self, je_monat: dict[tuple[int, int], list[int]]):
        self.je_monat = je_monat
        self.gefragt: list[tuple[int, int]] = []

    def session_ids_for_month(self, year: int, month: int) -> list[int]:
        self.gefragt.append((year, month))
        return self.je_monat.get((year, month), [])


def _vormonat(d: date, n: int) -> tuple[int, int]:
    erster = d.replace(day=1)
    for _ in range(n):
        erster = (erster - timedelta(days=1)).replace(day=1)
    return erster.year, erster.month


def test_rueckblick_liest_die_letzten_monate_nicht_den_laufenden():
    heute = date.today()
    doppel = _KalenderDoppel({_vormonat(heute, 1): [11], _vormonat(heute, 3): [33]})
    ids = doppel.past_session_ids(months_back=3)

    assert ids == [11, 33]
    # Genau die drei Vormonate, keiner doppelt, der laufende NICHT (den holt
    # `upcoming_calendar` ohnehin).
    assert doppel.gefragt == [_vormonat(heute, n) for n in (1, 2, 3)]
    assert (heute.year, heute.month) not in doppel.gefragt


def test_rueckblick_ueber_den_jahreswechsel():
    doppel = _KalenderDoppel({})
    doppel.past_session_ids(months_back=3)
    # Drei verschiedene Monate — der naive Weg („Monat minus n") landet im
    # Januar bei Monat 0 und wirft; hier zählt der Monatserste rückwärts.
    assert len(set(doppel.gefragt)) == 3


def test_rueckblick_entdoppelt():
    heute = date.today()
    doppel = _KalenderDoppel({_vormonat(heute, 1): [7, 7, 8], _vormonat(heute, 2): [8, 9]})
    assert doppel.past_session_ids(months_back=2) == [7, 8, 9]


# ------------------------------------------------- Nachtrag im Watcher-Lauf

def test_watcher_traegt_nur_unbekannte_sitzungen_nach(tmp_path, monkeypatch):
    """Der Rückblick holt die fehlende Sitzung — und nur sie.

    Die zweite Hälfte ist die wichtigere: Ohne den Abgleich gegen den Bestand
    zöge der Watcher bei JEDEM Lauf jede Sitzung der letzten drei Monate neu
    (Dutzende Abrufe für nichts).
    """
    from council import watcher
    from council.scraper import AgendaItem, CouncilSession
    from council.store import CouncilStore

    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    vergangen = (date.today() - timedelta(days=40)).isoformat()
    store.save_session(CouncilSession(
        ksinr=100, committee="Kulturausschuss", session_date=vergangen,
        session_time="17:00", location="Saal", agenda_items=[]))
    store.close()

    geholt: list[int] = []

    def fake_fetch(self, ksinr):
        geholt.append(ksinr)
        return CouncilSession(
            ksinr=ksinr, committee="Ausschuss für Wirtschaftsförderung",
            session_date=vergangen, session_time="17:00", location="Alte Fleiwa",
            agenda_items=[AgendaItem(item_number="Ö 1", title="Standortmarketing")])

    monkeypatch.setattr(watcher.CouncilScraper, "upcoming_calendar",
                        lambda self, months_ahead=3: ([], []))
    monkeypatch.setattr(watcher.CouncilScraper, "past_session_ids",
                        lambda self, months_back=3: [100, 101])
    monkeypatch.setattr(watcher.CouncilScraper, "fetch_session", fake_fetch)

    stats: dict = {}
    watcher.run_watcher(db, [], stats=stats)

    assert geholt == [101]                       # die bekannte 100 bleibt unangetastet
    assert stats["Nachgetragene Sitzungen"] == 1

    store = CouncilStore(db)
    assert store.get_session(101)["committee"] == "Ausschuss für Wirtschaftsförderung"
    assert store.known_session_ids([100, 101, 102]) == {100, 101}
    assert store.known_session_ids([]) == set()
    store.close()
