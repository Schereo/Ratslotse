"""Eine Sitzung von 2019 ändert sich nicht mehr — also holen wir sie nicht.

Für die VORLAGEN gab es diese Regel seit #1326 (``muss_geholt_werden``); die
Sitzungen hatten keine. Bei Wolfsburg waren das allein **652 Abrufe je
Woche** — der Boden, unter den der Wochenlauf gar nicht kommen konnte, auch
nachdem #1330 und #1334 die flüchtigen Seitenteile herausgerechnet hatten.
"""
from __future__ import annotations

import inspect

import pytest

from council.cities.adapters import get_adapter
from council.cities.adapters._common import NACHLAUF_TAGE, abgeschlossene_sitzungen
from council.cities.model import Batch, Meeting
from council.cities.store import CitiesStore

HEUTE = "2026-09-14"


def _tage(tmp_path, sitzungen):
    """Über den echten Store, nicht über ein handgeschriebenes dict.

    Was `meeting_dates` liefert, ist die halbe Regel — eine Fixture daneben
    prüfte nur, dass der Test sich selbst versteht (s. tests/CLAUDE.md).
    """
    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(meetings=[
            Meeting(kennung, "wolfsburg", None, "Ratssitzung", start)
            for kennung, start in sitzungen]))
        return s.meeting_dates("wolfsburg")


def test_was_lange_vorbei_ist_bleibt_liegen(tmp_path):
    assert abgeschlossene_sitzungen(
        _tage(tmp_path, [("m/alt", "2019-03-04")]), HEUTE) == {"m/alt"}


def test_die_letzten_wochen_werden_weiter_geholt(tmp_path):
    """Dort hängt das Neue: die Niederschrift, ein nachgetragenes Ergebnis."""
    assert abgeschlossene_sitzungen(
        _tage(tmp_path, [("m/frisch", "2026-08-20")]), HEUTE) == set()


def test_eine_kuenftige_sitzung_erst_recht(tmp_path):
    """Ihre Tagesordnung entsteht gerade."""
    assert abgeschlossene_sitzungen(
        _tage(tmp_path, [("m/kommt", "2026-11-02")]), HEUTE) == set()


def test_ohne_datum_wird_geholt(tmp_path):
    """Über eine undatierte Sitzung weiß der Bestand nichts.

    Die Richtung ist Absicht: Ein Fehler hier lässt zu viel holen, nicht zu
    wenig. Eine nicht öffentliche Wolfsburger Sitzung ist genau so ein Fall —
    sie kommt als Hülle ohne Datum zurück.
    """
    tage = _tage(tmp_path, [("m/ohne", None), ("m/leer", ""),
                            ("m/kaputt", "unbekannt")])
    assert abgeschlossene_sitzungen(tage, HEUTE) == set()


def test_was_wir_noch_gar_nicht_haben_wird_geholt(tmp_path):
    """Sonst käme eine abgebrochene Ernte nie zu Ende — derselbe Grund wie
    bei den Vorlagen (Hildesheim stand am 13.09. bei 1.078 zu 1.089)."""
    tage = _tage(tmp_path, [("m/alt", "2019-03-04")])
    assert "m/nie-gesehen" not in abgeschlossene_sitzungen(tage, HEUTE)


def test_der_nachlauf_ist_grosszuegig():
    """Eine Niederschrift kommt Wochen später. Ein knappes Fenster hieße:
    Wir holen die Sitzung ein letztes Mal, bevor das „Warum" darin steht."""
    assert NACHLAUF_TAGE >= 60


def test_alle_drei_html_dialekte_fragen_vorher():
    """Der Wächter: Wer jede Sitzungsseite bei jedem Lauf neu holt, zahlt sie.

    Die drei Dialekte lesen Oberflächen und laufen dabei über den ganzen
    Index — anders als ``allris4``, das eine datierte Schnittstelle
    rückwärts blättert und von selbst aufhört.
    """
    for name in ("allris4_html", "allris_classic", "hannover_sim"):
        quelle = inspect.getsource(get_adapter(name).iter_meetings)
        assert "abgeschlossene_sitzungen" in quelle, (
            f"{name}.iter_meetings holt wieder jede Sitzung des Index — bei "
            "Wolfsburg sind das 652 Abrufe je Wochenlauf, ohne eine einzige "
            "Änderung zu finden.")


def test_die_ernte_fuellt_die_sitzungstage_wirklich(tmp_path, monkeypatch):
    """Der Wächter gegen die stille Fassung dieser Reparatur.

    Der erste Entwurf las die Sitzungstage aus ``client.raw`` — und die
    Rohablage einer Stadt hält Seiten, keine Termine: ``meeting_dates`` kam
    dort immer leer zurück, es wurde nie etwas übersprungen, und der Lauf
    sah genau so aus wie vorher. Kein Fehler, keine Meldung, keine Wirkung.
    """
    from council.cities import pipeline
    from council.cities.registry import BODIES

    haupt = tmp_path / "cities.sqlite"
    with CitiesStore(haupt) as s:
        s.upsert_batch(Batch(meetings=[
            Meeting("m/alt", "wolfsburg", None, "Ratssitzung", "2019-03-04")]))

    gesehen: dict[str, str] = {}

    class NurSchauen(Exception):
        pass

    def stolpern(self, client, spec):
        gesehen.update(client.sitzungstage)
        raise NurSchauen

    monkeypatch.setattr(type(pipeline.get_adapter("allris4_html")),
                        "discover", stolpern, raising=True)
    # Der Abbruch ist der Test: Wir wollen nur bis zum ersten Adapter-Aufruf,
    # nicht an einen fremden Server.
    with pytest.raises(NurSchauen):
        pipeline.fetch(BODIES["wolfsburg"], tmp_path / "roh", tmp_path / "dateien",
                       main_path=haupt)
    assert gesehen == {"m/alt": "2019-03-04"}, (
        "Die Ernte reicht die Sitzungstage nicht durch — die Regel greift "
        "dann nie, ohne dass irgendetwas rot wird.")
