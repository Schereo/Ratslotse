"""Ideen-Cluster: dieselbe Sache in mehreren Städten.

Die Tests rechnen mit handgeschriebenen Vektoren, nicht mit fastembed — sonst
prüften sie das Einbettungsmodell und nicht die Gruppierung.
"""
from __future__ import annotations

import numpy as np
import pytest

from council.cities import clusters as cl
from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore

MODELL = "test-modell"


def vektor(*werte: float) -> bytes:
    v = np.array(werte, dtype=np.float32)
    return (v / np.linalg.norm(v)).tobytes()


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    s.upsert_body(Body("oldenburg", "Oldenburg", "NI", "oldenburg"))
    yield s
    s.close()


def idee(store: CitiesStore, kennung: str, stadt: str, titel: str,
         instrument: str, v: bytes) -> None:
    store.upsert_batch(Batch(papers=[Paper(kennung, stadt, titel)]))
    store.put_annotation("paper", kennung, "classify", "2",
                         {"field": "klima_umwelt", "transfer": "adaptable",
                          "competence": "council", "instrument": instrument,
                          "summary": "Zusammenfassung."}, "h" + kennung)
    store.put_object_embedding(cl.IDEA_KIND, kennung, MODELL, "h" + kennung, v)


# ------------------------------------------------------------------ Der Text

def test_die_idee_ist_instrument_und_zusammenfassung():
    """Kein Titel, keine Stadt, kein Datum — genau die trennen zwei Städte,
    die dasselbe tun."""
    text = cl.idea_text({"instrument": "Verpackungssteuer einführen",
                         "summary": "Eine Steuer auf Einwegverpackungen.",
                         "field": "klima_umwelt"})
    assert text.startswith("Verpackungssteuer einführen")
    assert "Einwegverpackungen" in text
    assert cl.idea_text({"instrument": None}) == "", \
        "ohne Instrument gibt es keine Idee zum Vergleichen"


# --------------------------------------------------------------- Gruppierung

def test_zwei_nahe_ideen_bilden_einen_cluster(store):
    idee(store, "os:1", "osnabrueck", "Verpackungssteuer", "Verpackungssteuer einführen",
         vektor(1.0, 0.0, 0.0))
    idee(store, "ol:1", "oldenburg", "Verpackungssteuer", "Verpackungssteuer erheben",
         vektor(0.99, 0.14, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 1 and zahlen["members"] == 2


def test_ferne_ideen_bleiben_getrennt(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Radweg bauen", vektor(0.0, 1.0))
    assert cl.build_clusters(store, MODELL, threshold=0.86, version="1")["clusters"] == 0


def test_ein_einzelnes_papier_ist_kein_cluster(store):
    """5.000 Einzelmengen in der Tabelle müsste jede Auswertung wegfiltern."""
    idee(store, "os:1", "osnabrueck", "A", "Alleinstellungsmerkmal", vektor(1.0, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 0 and zahlen["members"] == 0


def test_die_kette_bleibt_zusammen(store):
    """Single linkage ist Absicht: Eine Idee wandert über Zwischenglieder.

    Osnabrücks „Mehrwegsystem erproben" liegt nah an Münsters „Mehrwegpfand
    einführen", das nah an Potsdams „Verpackungssteuer prüfen" — die beiden
    Enden aber nicht aneinander. Average linkage zerschnitte die Kette; genau
    sie ist die Idee, die durch die Republik läuft.
    """
    idee(store, "a", "osnabrueck", "A", "Mehrwegsystem erproben", vektor(1.0, 0.0, 0.0))
    idee(store, "b", "osnabrueck", "B", "Mehrwegpfand einführen", vektor(0.93, 0.37, 0.0))
    idee(store, "c", "oldenburg", "C", "Verpackungssteuer prüfen", vektor(0.73, 0.68, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 1 and zahlen["members"] == 3, \
        "a–b und b–c liegen über der Schwelle, a–c nicht — die Kette hält"


# -------------------------------------------------------------------- Lesen

def test_der_cluster_nennt_seine_staedte_und_ob_oldenburg_dabei_ist(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    (z,) = store.cluster_stats(MODELL, "1")
    assert z["members"] == 2 and z["cities"] == 2 and z["has_oldenburg"] == 1

    mitglieder = store.cluster_of("os:1", MODELL, "1")
    assert {m["id"] for m in mitglieder} == {"os:1", "ol:1"}
    assert mitglieder[0]["score"] >= mitglieder[-1]["score"], \
        "das typischste Mitglied steht vorn, nicht das zufällig erste"


def test_ein_papier_ausserhalb_hat_keinen_cluster(store):
    idee(store, "os:1", "osnabrueck", "A", "Alleinstellung", vektor(1.0, 0.0))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert store.cluster_of("os:1", MODELL, "1") == []


def test_ein_zweiter_lauf_ersetzt_statt_zu_verdoppeln(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert sum(z["members"] for z in store.cluster_stats(MODELL, "1")) == 2


def test_zwei_fassungen_liegen_nebeneinander(store):
    """Wie bei den Annotatoren: Die neue Fassung ersetzt die alte erst, wenn
    die Messung entschieden hat."""
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    cl.build_clusters(store, MODELL, threshold=0.999, version="2")
    assert store.cluster_stats(MODELL, "1") and not store.cluster_stats(MODELL, "2")


# --------------------------------------------------------------- Einbetten

def test_nur_uebertragbares_wird_eingebettet(store, monkeypatch):
    """An einem Bebauungsplan stellt sich „hat das noch jemand?" nicht."""
    store.upsert_batch(Batch(papers=[
        Paper("os:1", "osnabrueck", "Übertragbar"),
        Paper("os:2", "osnabrueck", "Nur hier")]))
    for kennung, transfer in (("os:1", "adaptable"), ("os:2", "local")):
        store.put_annotation("paper", kennung, "classify", "2",
                             {"field": "klima_umwelt", "transfer": transfer,
                              "competence": "council", "instrument": "Etwas tun",
                              "summary": "x"}, "h" + kennung)
    gesehen: list[str] = []
    monkeypatch.setattr(cl, "EMBED_MODEL", MODELL)
    import council.cities.index as index_modul
    monkeypatch.setattr(index_modul, "_embed",
                        lambda texte: (gesehen.extend(texte),
                                       np.ones((len(texte), 2), dtype=np.float32))[1])
    assert cl.embed_ideas(store, MODELL) == 1
    assert len(gesehen) == 1


def test_unveraenderte_ideen_werden_nicht_neu_gerechnet(store, monkeypatch):
    store.upsert_batch(Batch(papers=[Paper("os:1", "osnabrueck", "A")]))
    store.put_annotation("paper", "os:1", "classify", "2",
                         {"field": "klima_umwelt", "transfer": "adaptable",
                          "competence": "council", "instrument": "Etwas tun",
                          "summary": "x"}, "h1")
    import council.cities.index as index_modul
    monkeypatch.setattr(index_modul, "_embed",
                        lambda texte: np.ones((len(texte), 2), dtype=np.float32))
    assert cl.embed_ideas(store, MODELL) == 1
    assert cl.embed_ideas(store, MODELL) == 0, "derselbe Text, derselbe Vektor"


# ------------------------------------------------------------ Gegenrichtung

def test_der_cluster_findet_die_fremden_gegenstuecke(store):
    """„Wie ging dieselbe Sache anderswo aus?" — die Frage am Abend vor der
    Sitzung. Sie braucht nur den Cluster und das Ergebnis je Mitglied."""
    from council.cities.model import AgendaItem, Consultation, Meeting, Outcome

    idee(store, "os:1", "osnabrueck", "Grundsteuer C prüfen",
         "Grundsteuer C einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "Einführung der Grundsteuer C",
         "Grundsteuer C prüfen", vektor(0.99, 0.14))
    store.upsert_batch(Batch(
        meetings=[Meeting("os:m:1", "osnabrueck", None, "Rat", "2026-02-01")],
        agenda_items=[AgendaItem("os:a:1", "os:m:1", "Grundsteuer C",
                                 result_raw="verwiesen", outcome=Outcome.REFERRED)],
        consultations=[Consultation("os:c:1", "os:1", agenda_item_id="os:a:1")]))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")

    fremde = [m for m in store.cluster_of("ol:1", MODELL, "1")
              if m["body_id"] != "oldenburg"]
    assert [m["id"] for m in fremde] == ["os:1"]
    assert (store.outcome_for_paper("os:1") or {}).get("outcome") == "referred", \
        "ohne das Ergebnis beantwortet der Cluster die Frage nicht"
