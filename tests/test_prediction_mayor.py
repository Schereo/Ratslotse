"""Die OB-Wahl aus der Ergebnisdarstellung (``election/mayor.py``).

Gegen die echte 2021er Fixture (``tests/fixtures/wahlabend/ob-2021.json``,
gemessen 11.09.2026 direkt beim Votemanager) — dieselbe Quelle, dieselbe
Form wie am 13.09.2026, nur mit den Namen von 2021.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app.election import mayor  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wahlabend" / "ob-2021.json"


@pytest.fixture
def payload_2021() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ slug_of

@pytest.mark.parametrize("name, erwartet", [
    ("Jascha Rohr", "rohr"),
    ("Ulf Prange", "prange"),
    ("Heike Boldt", "boldt"),
    ("Sebastian Fröhlich", "froehlich"),
    ("Ralf Butzin", "butzin"),
    ("Yakup Castur", "castur"),
    ("Byanca Küßner", "kuessner"),
    ("Michael Stille", "stille"),
    ("Holger Martin Wilkens", "wilkens"),
])
def test_slug_of_die_neun_2026er_kandidaturen(name, erwartet):
    assert mayor.slug_of(name) == erwartet


def test_slug_of_bare_nachname_ohne_leerzeichen():
    """Die Ergebnisdarstellung liefert nur den Nachnamen vor dem Komma —
    ``slug_of`` muss auch damit klarkommen, nicht nur mit dem vollen Namen."""
    assert mayor.slug_of("Krogmann") == "krogmann"
    assert mayor.slug_of("Küßner") == "kuessner"


def test_die_neun_slugs_sind_verschieden():
    cands = mayor.candidates()
    assert len(cands) == 9
    slugs = [c.slug for c in cands]
    assert len(set(slugs)) == 9, slugs


def test_candidates_traegt_partei_aus_der_klammer():
    cands = {c.slug: c for c in mayor.candidates()}
    assert cands["rohr"].party == "GRÜNE"
    assert cands["prange"].party == "SPD"
    assert cands["butzin"].party == "Einzelwahlvorschlag"
    assert all(c.votes is None and c.share_pct is None for c in cands.values())


# ------------------------------------------------------------------ parse()

def test_parse_ohne_komponente_ist_none():
    """Vor der Auszählung liegt in der Datei nur ein Zeitstempel — wie bei
    der Ratswahl (``presentation.parse_area``)."""
    assert mayor.parse({"zeitstempel": "11.09.2026 12:00"}) is None


def test_parse_2021_liefert_alle_kandidaturen_mit_stimmen(payload_2021):
    bekannt = mayor.candidates()  # die NEUN von 2026 — 2021 hatte andere Namen
    result = mayor.parse(payload_2021, bekannt)
    assert result is not None
    assert result.phase == "complete"
    assert result.reports_expected == result.reports_received == 133
    assert result.valid_votes == 72248
    assert result.invalid_ballots == 517
    assert result.turnout_pct == pytest.approx(53.83, abs=0.01)
    # Krogmann/SPD gehört zu keiner der neun 2026er-Kandidaturen — zählt
    # trotzdem mit (Muster: „CSV-Spalten ohne Register-Eintrag zählen mit").
    krogmann = next(c for c in result.candidates if c.slug == "krogmann")
    assert krogmann.votes == 29564
    assert krogmann.share_pct == pytest.approx(40.92, abs=0.01)
    assert any("krogmann" in n.lower() or "Krogmann" in n for n in result.notes)
    # Alle neun bekannten Kandidaturen stehen da, auch ohne eigene Stimmen.
    assert {c.slug for c in bekannt} <= {c.slug for c in result.candidates}


def test_parse_2021_stichwahl_wird_erkannt(payload_2021):
    result = mayor.parse(payload_2021)
    assert result is not None
    assert set(result.runoff) == {"krogmann", "fuhrhop"}


def test_parse_ungueltige_stimmen_nicht_mit_gueltigen_stimmen_verwechselt(payload_2021):
    """Die Falle aus dem Modul-Docstring: „ungültige Stimmen" enthält
    „gültige Stimmen" als Teilstring. Eine naive ``in``-Prüfung würde den
    Wert der ungültigen Zeile in ``valid_votes`` schreiben."""
    result = mayor.parse(payload_2021)
    assert result is not None
    assert result.invalid_ballots == 517
    assert result.valid_votes == 72248
    assert result.invalid_ballots != result.valid_votes


def test_parse_unbekannter_name_erzeugt_eigene_zeile_und_hinweis(payload_2021):
    """Simuliert die reale Lage am 13.09.2026: Von den neun 2026er-Namen ist
    KEINER in der 2021er-Fixture enthalten. Trotzdem bleibt jede Zeile der
    Darstellung sichtbar — mitgezählt, nicht verworfen."""
    result = mayor.parse(payload_2021, mayor.candidates())
    assert result is not None
    gefundene_slugs = {c.slug for c in result.candidates if c.party == ""}
    assert len(gefundene_slugs) >= 5  # mindestens die eindeutig fremden Namen
    assert len(result.notes) >= 5


# ------------------------------------------------------------------ probe()

def test_probe_skaliert_stimmen_am_auszaehlungsstand():
    voll = mayor.probe(None)
    halb = mayor.probe(66)  # knapp die Hälfte von 133
    leer = mayor.probe(0)
    assert voll.phase == "complete"
    assert leer.phase == "before"
    assert halb.phase == "counting"
    voll_stimmen = sum(c.votes or 0 for c in voll.candidates)
    halb_stimmen = sum(c.votes or 0 for c in halb.candidates)
    assert 0 < halb_stimmen < voll_stimmen
    assert leer.reports_received == 0


def test_probe_ohne_stichwahl_vor_dem_endstand():
    """Der Stichwahl-Satz gilt nur für den ENDSTAND — ein Teilstand soll
    nicht schon eine Stichwahl behaupten, die noch gar nicht feststeht."""
    halb = mayor.probe(66)
    assert halb.runoff == ()
    voll = mayor.probe(None)
    assert voll.runoff != ()


# ------------------------------------------------------------------ fetch() gegen einen echten Server

def test_fetch_ohne_server_liefert_bare_ergebnis_ohne_zu_werfen(monkeypatch):
    monkeypatch.setenv("WAHLABEND_VOTEMANAGER_URL", "http://127.0.0.1:1")  # niemand hört hier zu
    mayor.reset()
    result = mayor.fetch()
    assert result.ok is False
    assert result.error
    assert len(result.candidates) == 9
    mayor.reset()
