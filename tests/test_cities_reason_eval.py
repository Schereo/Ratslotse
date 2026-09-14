"""Der Maßstab für das „Warum" — und die zwei Weisen, wie er selbst log.

Zweimal hat dieser Prüfstand einen Modellfehler gemeldet, wo keiner war:
am 10.09.2026 ein falsch gesetztes Handlabel, am 13.09.2026 ein
Zeichenketten-Vergleich über Zahlen. Beides sind teure Irrtümer — sie halten
einen Annotator auf, der in Ordnung ist, und ein Prüfstand, dem man nicht
glaubt, ist keiner.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_pfad = Path(__file__).resolve().parents[1] / "eval" / "run_cities_reason.py"
_spec = importlib.util.spec_from_file_location("run_cities_reason", _pfad)
assert _spec and _spec.loader
reason_eval = importlib.util.module_from_spec(_spec)
sys.modules["run_cities_reason"] = reason_eval
_spec.loader.exec_module(reason_eval)


@pytest.mark.parametrize("erwartet,bekommen", [
    # Alle Paare unten sind GEMESSEN, keins ausgedacht: Sie stammen aus den
    # Läufen vom 12. und 13.09.2026 gegen die 36 Handfälle.
    ("mit 6 Ja-, 34 Neinstimmen und 5 Enthaltungen",
     "6 Ja, 34 Nein, 5 Enthaltungen (Änderungsantrag); 7 Ja, 3 Nein, 0 Enthaltungen"),
    ("mit 21 Ja-, 24 Neinstimmen und 1 Enthaltung", "21 Ja, 24 Nein, 1 Enthaltung"),
    ("0 – 2 – 4", "0 Ja, 2 Nein, 4 Enthaltungen"),
    ("dafür: 6 dagegen: 0 Enthaltungen: 0", "6 Ja, 0 Nein, 0 Enthaltungen"),
    ("mit 7 Ja-Stimmen und einer Enthaltung", "7 Ja-Stimmen und eine Enthaltung"),
    ("einstimmig", "Einstimmig angenommen"),
])
def test_dieselbe_abstimmung_in_anderer_schreibweise_gilt_als_getroffen(erwartet, bekommen):
    assert reason_eval._gleich(erwartet, bekommen)


@pytest.mark.parametrize("erwartet,bekommen", [
    # Eine ANDERE Abstimmung bleibt eine andere — 41 Ja sind nicht 0 Ja.
    ("mit 0 Ja-, 42 Neinstimmen und 0 Enthaltungen", "41 Ja, 0 Nein, 0 Enthaltungen"),
    ("einstimmig", "bei einer Gegenstimme"),
    ("Einstimmig angenommen", None),
])
def test_eine_andere_abstimmung_gilt_nicht_als_getroffen(erwartet, bekommen):
    assert not reason_eval._gleich(erwartet, bekommen)


def test_zwei_abstimmungen_im_abschnitt_werden_beide_gelesen():
    """Änderungsantrag und Hauptantrag stehen oft im selben Abschnitt.

    Wer nur die letzte liest, verwirft die, die ein Mensch ins Golden Set
    geschrieben hat — gemessen an genau diesem Fall.
    """
    assert reason_eval._stimmen(
        "6 Ja, 34 Nein, 5 Enthaltungen (Änderungsantrag); 7 Ja, 3 Nein, 0 Enthaltungen"
    ) == [(6, 34, 5), (7, 3, 0)]


def test_ohne_gegenstimmen_gibt_es_kein_tripel():
    """Eine geratene Null wäre eine Behauptung, kein Messwert."""
    assert reason_eval._stimmen("mit 7 Ja-Stimmen und einer Enthaltung") == []


def test_ein_fehlgeschlagener_aufruf_ist_keine_erfundene_begruendung():
    """Der teuerste Irrtum des Prüfstands, als Wächter festgehalten.

    Bis zum 13.09.2026 landete jede Ausnahme in derselben Liste wie eine
    erfundene Begründung — und riss damit die harte Schranke („null
    Erfindungen"), ohne dass das Modell etwas falsch gemacht hätte. Gemessen:
    Derselbe Fall lief beim nächsten Versuch fehlerfrei durch.
    """
    import inspect
    zeilen = inspect.getsource(reason_eval.ein_lauf).splitlines()
    start = next(i for i, z in enumerate(zeilen) if "except Exception" in z)
    # Nur der Zweig selbst: bis zum `continue`, das ihn beendet.
    ende = next(i for i, z in enumerate(zeilen[start:], start) if z.strip() == "continue")
    zweig = "\n".join(zeilen[start:ende + 1])
    assert "fehler.append" in zweig, (
        "Der Fehlerzweig schreibt nicht in `fehler` — läuft er wieder in "
        "`erfunden`, misst der Prüfstand das Netz statt das Modell.")
    assert "erfunden.append" not in zweig, (
        "Eine Ausnahme zählt wieder als erfundene Begründung. Ein Netzwackler "
        "reißt damit die harte Schranke, ohne dass das Modell etwas tat.")
