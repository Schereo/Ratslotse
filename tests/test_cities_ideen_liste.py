"""Die Ideen-Liste zählt IDEEN, nicht Vorlagen.

Gemessen am 09.09.2026: Von 262 Einträgen („fehlt in Oldenburg", in
mindestens zwei anderen Räten) waren **195 Wiederholungen** — dieselbe
Stadt, dieselbe Idee, ein zweiter oder dritter Anlauf. Potsdam steht mit
drei Vorlagen zum Denkmalpflege-Konzept da, Münster mit zwei zum Jugendrat.
Wer die Liste liest, sieht dreimal dieselbe Sache und hält sie für drei.
"""
from __future__ import annotations

import json

import pytest

from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore

MODELL = "test-mini"


@pytest.fixture()
def cities(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("potsdam", "Potsdam", "BB", "allris4"))
    s.upsert_body(Body("muenster", "Münster", "NW", "session"))
    s.upsert_batch(Batch(papers=[
        # Dreimal dieselbe Sache aus Potsdam, aufsteigend datiert.
        Paper("po:1", "potsdam", "Denkmalpflege-Konzept", date="2024-02-01",
              kind="motion"),
        Paper("po:2", "potsdam", "Denkmalpflege-Konzept, erneut", date="2024-02-23",
              kind="motion"),
        Paper("po:3", "potsdam", "Denkmalpflege-Konzept, dritter Anlauf",
              date="2025-08-22", kind="motion"),
        # Eine ANDERE Stadt, dieselbe Idee — bleibt eine eigene Zeile.
        Paper("ms:1", "muenster", "Denkmalpflege-Konzept", date="2024-06-01",
              kind="motion"),
    ]))
    for pid in ("po:1", "po:2", "po:3", "ms:1"):
        s.put_annotation("paper", pid, "classify", "2",
                         {"field": "kultur_sport", "transfer": "adaptable",
                          "competence": "council",
                          "instrument": "Denkmalpflege-Konzept erstellen",
                          "summary": "."}, "h" + pid)
        s.put_annotation("paper", pid, "fit", "3",
                         {"status": "missing", "evidence": [], "reason": ".",
                          "confidence": "high"}, "f" + pid)
    s.replace_idea_clusters(MODELL, "1", [
        (MODELL, "1", 7, "po:1", 0.9), (MODELL, "1", 7, "po:2", 0.9),
        (MODELL, "1", 7, "po:3", 0.9), (MODELL, "1", 7, "ms:1", 0.9)])
    # Der fünfte Cluster-Schritt: Mehrheits-Status je Stadt und Gruppe.
    s.rebuild_group_status(MODELL, "1", "3")
    yield s
    s.close()


def test_antworten_und_mitteilungen_stehen_nicht_auf_der_liste(cities):
    """Die Verwaltung REAGIERT dort — die Idee steht in der Anfrage.

    Gemessen am 09.09.2026 waren 35 der 87 Einträge `answer`, `notice` oder
    `report`. Sie machten die Liste nicht länger, sondern nur voller.
    """
    cities.upsert_batch(Batch(papers=[
        Paper("po:9", "potsdam", "Antwort auf die Anfrage", date="2026-09-01",
              kind="answer"),
    ]))
    cities.put_annotation("paper", "po:9", "classify", "2",
                          {"field": "kultur_sport", "transfer": "adaptable",
                           "competence": "council",
                           "instrument": "Denkmalpflege-Konzept erstellen",
                           "summary": "."}, "hpo9")
    cities.put_annotation("paper", "po:9", "fit", "3",
                          {"status": "missing", "evidence": [], "reason": ".",
                           "confidence": "high"}, "fpo9")
    # In DERSELBEN Gruppe und JÜNGER als der Antrag — genau der Fall, in dem
    # sie ihn verdrängen würde und danach selbst durch den Art-Filter fiele.
    cities.replace_idea_clusters(MODELL, "1", [
        (MODELL, "1", 7, "po:1", 0.9), (MODELL, "1", 7, "po:2", 0.9),
        (MODELL, "1", 7, "po:3", 0.9), (MODELL, "1", 7, "ms:1", 0.9),
        (MODELL, "1", 7, "po:9", 0.9)])
    cities.rebuild_group_status(MODELL, "1", "3")
    zeilen, _, _ = cities.ideas("kultur_sport", status=("missing",))
    assert "po:9" not in {z["id"] for z in zeilen}
    assert {z["id"] for z in zeilen} == {"po:3", "ms:1"}, (
        "die jüngere Antwort darf den Antrag auch nicht verdrängen")


def test_dubletten_je_stadt_werden_zusammengezogen(cities):
    zeilen, gesamt, _ = cities.ideas("kultur_sport", status=("missing",))
    kennungen = [z["id"] for z in zeilen]
    assert gesamt == 2, "eine Zeile je Stadt und Idee, nicht je Vorlage"
    assert kennungen == ["po:3", "ms:1"] or kennungen == ["ms:1", "po:3"]
    assert "po:1" not in kennungen and "po:2" not in kennungen


def test_die_juengste_vertritt_die_idee(cities):
    """Wer eine Sache dreimal beantragt hat, hat sie beim dritten Mal am
    besten formuliert — und das Datum sagt, ob sie noch läuft."""
    zeilen, _, _ = cities.ideas("kultur_sport", status=("missing",))
    potsdam = [z for z in zeilen if z["body_id"] == "potsdam"][0]
    assert potsdam["id"] == "po:3"


def test_die_verdraengten_kommen_als_geschwister_mit(cities):
    zeilen, _, _ = cities.ideas("kultur_sport", status=("missing",))
    potsdam = [z for z in zeilen if z["body_id"] == "potsdam"][0]
    geschwister = json.loads(potsdam["siblings_json"] or "[]")
    assert {g["id"] for g in geschwister} == {"po:1", "po:2"}
    muenster = [z for z in zeilen if z["body_id"] == "muenster"][0]
    assert json.loads(muenster["siblings_json"] or "[]") == [], (
        "wer die Sache nur einmal behandelt hat, hat keine Geschwister")


def test_ein_ausgeschlossenes_mitglied_verdraengt_nichts(cities):
    """`cluster_check` hat po:3 aus der Gruppe geworfen — es gehört nicht zu
    dieser Idee und ist deshalb auch keine Dublette, sondern eine eigene."""
    cities.put_annotation("cluster", "1:7", "cluster_check", "1",
                          {"label": "Denkmalpflege", "drop": ["po:3"],
                           "reason": "."}, "c7")
    cities.rebuild_group_status(MODELL, "1", "3")
    zeilen, gesamt, _ = cities.ideas("kultur_sport", status=("missing",))
    kennungen = {z["id"] for z in zeilen}
    assert gesamt == 3
    assert kennungen == {"po:2", "po:3", "ms:1"}, (
        "po:2 vertritt jetzt die Gruppe, po:3 steht für sich")


def test_die_mehrheit_entscheidet_nicht_die_juengste(cities):
    """Zwei von drei Potsdamer Urteilen sagen „fehlt", das jüngste sagt
    „vorhanden" — die Idee fehlt, und vertreten wird sie von der jüngsten
    Vorlage MIT dem Mehrheitsurteil.

    Gemessen am 10.09.2026: 119 von 1.062 Gruppen uneinheitlich, bei 14
    davon widersprach die jüngste ihrer Mehrheit. Als lebende Abfrage 0,65 s
    je Seite — deshalb liegt die Mehrheit in `idea_group_status`.
    """
    cities.put_annotation("paper", "po:3", "fit", "3",
                          {"status": "present", "evidence": [], "reason": ".",
                           "confidence": "high"}, "fpo3b")
    cities.rebuild_group_status(MODELL, "1", "3")
    fehlt, gesamt, zaehler = cities.ideas("kultur_sport", status=("missing",))
    potsdam = [z for z in fehlt if z["body_id"] == "potsdam"]
    assert potsdam and potsdam[0]["id"] == "po:2", (
        "die jüngste MIT Mehrheitsurteil vertritt — nicht po:3, das abweicht")
    assert potsdam[0]["group_status"] == "missing" and potsdam[0]["group_votes"] == "3/2"
    vorhanden, _, _ = cities.ideas("kultur_sport", status=("present",))
    assert not [z for z in vorhanden if z["body_id"] == "potsdam"], (
        "die abweichende Vorlage darf nicht als eigene ‚vorhanden'-Zeile auftauchen")
    assert zaehler.get("missing") == 2, "Statusleiste zählt Ideen, nicht Vorlagen"


def test_ohne_cluster_bleibt_jede_vorlage_eine_zeile(cities):
    """Die Gegenrichtung: Ohne Gruppierung darf nichts verschwinden."""
    cities.replace_idea_clusters(MODELL, "1", [])
    cities.rebuild_group_status(MODELL, "1", "3")
    _, gesamt, _ = cities.ideas("kultur_sport", status=("missing",))
    assert gesamt == 4


def test_zaehler_und_zeilen_sehen_dasselbe(cities):
    """Zählen, Blättern und die Statusleiste teilen eine Bedingung — laufen
    sie auseinander, springt das Blättern."""
    zeilen, gesamt, zaehler = cities.ideas("kultur_sport", status=("missing",))
    assert gesamt == len(zeilen) == sum(zaehler.values())
