"""Der Wächter für stumme Ernte-Fehler.

Die vier Fehler vom 08.09.2026 haben sich alle nicht gemeldet: kein Absturz,
kein roter Test, keine auffällige Kennzahl. Diese Suite hält fest, dass
mindestens ihre *Form* künftig auffällt — jeder Testfall stellt einen davon
nach.
"""
from __future__ import annotations

import pytest

from council.cities import pruefung
from council.cities.model import (
    AgendaItem, Batch, Body, Consultation, File, FileRole, Meeting, Outcome, Paper,
)
from council.cities.store import CitiesStore


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("teststadt", "Teststadt", "NI", "allris4"))
    yield s
    s.close()


def bestand(store: CitiesStore, *, papiere: int, sitzungen: int,
            mit_ergebnis: int, mit_beratung: int | None = None,
            mit_text: int | None = None) -> None:
    """Einen Bestand bauen, dessen Verhältnisse die Regeln prüfen können."""
    mit_beratung = papiere if mit_beratung is None else mit_beratung
    mit_text = papiere if mit_text is None else mit_text
    batch = Batch(
        meetings=[Meeting(f"m{i}", "teststadt", None, f"Sitzung {i}", "2026-01-01")
                  for i in range(sitzungen)],
        papers=[Paper(f"p{i}", "teststadt", f"Vorlage {i}") for i in range(papiere)],
    )
    for i in range(mit_beratung):
        top = f"a{i}"
        batch.agenda_items.append(AgendaItem(
            top, f"m{i % max(sitzungen, 1)}", f"Vorlage {i}",
            outcome=Outcome.ACCEPTED if i < mit_ergebnis else Outcome.NONE))
        batch.consultations.append(Consultation(f"c{i}", f"p{i}", agenda_item_id=top))
    for i in range(mit_text):
        batch.files.append(File(f"f{i}", "teststadt", FileRole.MAIN, paper_id=f"p{i}"))
    store.upsert_batch(batch)
    for i in range(mit_text):
        store.put_text(f"f{i}", "pdf", "1", "Volltext der Vorlage.", 1, "ok")


def regeln(befunde) -> set[str]:
    return {b.regel for b in befunde}


def test_gesunde_stadt_gibt_keinen_befund(store):
    bestand(store, papiere=400, sitzungen=80, mit_ergebnis=300)
    assert pruefung.pruefe(store) == []


def test_fehlende_sitzungen_fallen_auf(store):
    """Osnabrück hatte 137 Sitzungen zu 2.864 Vorlagen — 20,9 je Sitzung.

    Ursache war die Rückwärts-Blätterung, die bei Sitzungen nach `date` fragte
    statt nach `start`. Ohne Sitzung kein Tagesordnungspunkt, ohne Punkt kein
    Ergebnis: Der Fehler kostete die halbe Beschlusslage dreier Städte.
    """
    bestand(store, papiere=400, sitzungen=5, mit_ergebnis=300)
    assert "papiere_je_sitzung" in regeln(pruefung.pruefe(store))


def test_beratungen_ohne_ergebnis_fallen_auf(store):
    """Magdeburgs Fall: 0 von 700 Vorlagen mit Ergebnis, 5.982 Punkte mit einem."""
    bestand(store, papiere=400, sitzungen=80, mit_ergebnis=0)
    assert "anteil_mit_ergebnis" in regeln(pruefung.pruefe(store))


def test_fehlende_texte_fallen_auf(store):
    """Ohne Text keine Einordnung, ohne Einordnung keine Idee.

    Osnabrück stand bei 0,29 (Textstufe nie gelaufen), Potsdam bei 0,12
    (Dateien nie geholt) — beide sahen in jeder Liste normal aus.
    """
    bestand(store, papiere=400, sitzungen=80, mit_ergebnis=300, mit_text=40)
    assert "anteil_mit_text" in regeln(pruefung.pruefe(store))


def test_verlorene_beratungen_fallen_auf(store):
    """Magdeburg vergab eine Beratungs-Kennung sechsmal; die Stationen
    überschrieben sich beim Schreiben, 575 gingen verloren."""
    bestand(store, papiere=400, sitzungen=80, mit_ergebnis=50, mit_beratung=40)
    assert "anteil_mit_beratung" in regeln(pruefung.pruefe(store))


def test_kleine_staedte_werden_nicht_geprueft(store):
    """Unter 200 Vorlagen ist jeder Anteil Rauschen."""
    bestand(store, papiere=50, sitzungen=1, mit_ergebnis=0, mit_beratung=0)
    assert pruefung.pruefe(store) == []


def test_unbekanntes_vokabular_zeigt_die_haeufigsten(store):
    """Womit man eine neue Stadt anschließt: Was versteht die Regel nicht?"""
    store.upsert_batch(Batch(
        meetings=[Meeting("m1", "teststadt", None, "Rat", "2026-01-01")],
        agenda_items=[
            AgendaItem("a1", "m1", "A", result_raw="schriftliche Stellungnahme"),
            AgendaItem("a2", "m1", "B", result_raw="schriftliche Stellungnahme"),
            AgendaItem("a3", "m1", "C", result_raw="Einzelabstimmung"),
            # Ein zugeordnetes Ergebnis gehört NICHT auf die Liste.
            AgendaItem("a4", "m1", "D", result_raw="beschlossen", outcome=Outcome.ACCEPTED),
        ]))
    assert pruefung.unbekanntes_vokabular(store, "teststadt") == [
        ("schriftliche Stellungnahme", 2), ("Einzelabstimmung", 1)]
