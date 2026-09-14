"""Eine Gruppe, über die sich drei Stimmen nicht einig sind, behauptet nichts.

Die Gruppierung kettet (einfache Verknüpfung, bewusst — s.
``build_clusters``). Meist ist das Ergebnis eine echte Idee mit ein, zwei
Ausreißern, und ``cluster_check`` putzt sie. Manchmal entsteht aber eine
Kette ohne Mitte: **Gruppe 1 hatte am 14.09.2026 86 Vorlagen aus 9 Städten**,
von Sportförderrichtlinien über Briefwahlbezirke und Schiedspersonenwahl bis
zu einem Nachtfahrverbot für Mähroboter.

Dort gibt es nichts zu putzen, und das Modell merkte es nicht: Es suchte
pflichtgemäß die „Mehrheit", nannte sie „Sportförderung" und entfernte
**ein** Mitglied von 86.

Das wäre eine Zahl in einem Bericht — wenn nicht nach ``peers DESC``
sortiert würde. So standen **1,2 % des Bestands für 17 % der ersten dreißig
Karten je Feld**: Was verkettet ist, ist groß, und was groß ist, kommt nach
oben.
"""
from __future__ import annotations


import pytest

from council.cities import clusters
from council.cities.annotators import get as get_annotator
from council.cities.model import Batch, Paper
from council.cities.store import CitiesStore


def test_der_prueflauf_kuerzt_nicht_mehr_stumm():
    """Der Wächter gegen den Ausschnitt, der wie ein Urteil aussah.

    Bei 86 Mitgliedern sah das Modell **68 Zeilen**, die letzte mitten im
    Wort — und konnte die übrigen 18 gar nicht beanstanden. Genau eine von
    1.439 Gruppen lief dagegen: ausgerechnet die schlimmste.
    """
    import inspect

    # Nur der CODE, nicht die Kommentare: Der Grund steht dort ausführlich,
    # und ein Wächter, der seine eigene Begründung findet, prüft nichts.
    quelle = "\n".join(z for z in inspect.getsource(clusters.check_clusters).splitlines()
                       if not z.lstrip().startswith("#"))
    assert "zeilen[:ann.input_chars" not in quelle, (
        "cluster_check legt der Gruppe wieder nur einen Ausschnitt vor — "
        "was dem Modell nicht vorliegt, kann es nicht beanstanden.")
    assert "logger.warning" in quelle, (
        "Eine übergroße Gruppe muss sich melden, statt still durchzulaufen.")


def test_die_schwelle_trennt_die_gemessenen_gruppen():
    """Die Zahl ist an echten Gruppen gemessen, nicht geraten.

    Drei Läufe je Gruppe, 14.09.2026. Steigt ``UNEINIG_AB`` über 0,83, gilt
    das Sammelbecken wieder als belegt; sinkt sie unter 0,33, fallen echte
    Gruppen wie „Kinderbetreuung" mit hinein.
    """
    gemessen = {
        "Sammelbecken (86)": 0.83,      # keine gemeinsame Sache
        "Kinderbetreuung (18)": 0.33,   # echte Gruppe, unruhiges Urteil
        "Jugendförderung (24)": 0.25,
        "Baumfällungen (16)": 0.19,
        "Straßenbauprogramm (20)": 0.15,
        "Parkgebühren (55)": 0.02,
        "Tempo 30 (19)": 0.0,
    }
    ueber = {n for n, s in gemessen.items() if s > clusters.UNEINIG_AB}
    assert ueber == {"Sammelbecken (86)"}, (
        f"Die Schwelle {clusters.UNEINIG_AB} trifft {ueber or 'nichts'} — "
        "gemeint ist genau die Gruppe ohne gemeinsame Sache.")


def test_drei_stimmen_nur_fuer_die_grossen():
    """Kleine Gruppen dreimal zu lesen kostet, ohne etwas zu finden."""
    assert clusters.STIMMEN_AB_MITGLIEDERN > clusters.CHECK_AB_MITGLIEDERN
    assert clusters.STIMMEN >= 3, "Zwei Stimmen haben keine Mehrheit"


def test_unbelegt_ist_kein_pflichtfeld_des_modells():
    """`stable` schreibt der LAUF, nicht das Modell.

    Ein Modell, das sich selbst für einig erklärt, misst nichts. Deshalb
    trägt die Nutzlast eine Vorgabe, und die ist `True`: Wer nur einmal
    gelesen wird, gilt als belegt wie bisher.
    """
    last = get_annotator("cluster_check").payload.model_validate(
        {"label": "Radwege bauen", "drop": [], "reason": ""})
    assert last.stable is True


@pytest.fixture()
def store(tmp_path):
    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper(f"{stadt}/p1", stadt, f"Sache in {stadt}",
                  date="2024-05-01", kind="motion")
            for stadt in ("hannover", "muenster", "potsdam")]))
        yield s


def _gruppe(store, stable: bool, version: str = "1"):
    """Eine Dreiergruppe über drei Städte, mit einem Prüfurteil daneben."""
    from council.cities.index import EMBED_MODEL

    store.replace_idea_clusters(EMBED_MODEL, version, [
        (EMBED_MODEL, version, 1, f"{stadt}/p1", 0.9)
        for stadt in ("hannover", "muenster", "potsdam")])
    store.put_annotation("cluster", f"{version}:1", "cluster_check", "1",
                         {"label": "Sache", "drop": [], "reason": "",
                          "stable": stable}, "h", "modell", 0.0)


def test_eine_unbelegte_gruppe_zaehlt_keine_staedte(store):
    """Der Kern: Aus „auch in 2 anderen Städten" wird nichts."""
    from council.cities.index import EMBED_MODEL

    for stadt in ("hannover", "muenster", "potsdam"):
        store.put_annotation("paper", f"{stadt}/p1", "fit", "4",
                             {"status": "missing", "confidence": "high",
                              "reason": "…", "evidence": []}, "h", "m", 0.0)
    _gruppe(store, stable=True)
    store.rebuild_group_status(EMBED_MODEL, "1", "4")
    zeilen = store._conn.execute(
        "SELECT body_id, peers FROM idea_group_status ORDER BY body_id").fetchall()
    assert [r["peers"] for r in zeilen] == [2, 2, 2], "belegte Gruppe zählt die anderen"

    _gruppe(store, stable=False)
    store.rebuild_group_status(EMBED_MODEL, "1", "4")
    zeilen = store._conn.execute(
        "SELECT body_id, peers FROM idea_group_status ORDER BY body_id").fetchall()
    assert [r["peers"] for r in zeilen] == [0, 0, 0], (
        "Eine Gruppe ohne gemeinsame Sache zählt wieder fremde Städte mit - "
        "und steht über ORDER BY peers DESC damit wieder auf Seite eins.")


def test_die_mitglieder_bleiben_in_der_liste(store):
    """Unbelegt heißt „wir wissen es nicht", nicht „weg damit".

    Die Vorlagen sind echt und ihr Urteil auch; nur die Aussage über die
    anderen Städte fällt weg.
    """
    from council.cities.index import EMBED_MODEL

    _gruppe(store, stable=False)
    store.rebuild_group_status(EMBED_MODEL, "1", "4")
    assert len(store.papers()) == 3
