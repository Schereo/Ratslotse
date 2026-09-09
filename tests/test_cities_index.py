"""Chunks, Embeddings, Volltextindex und Nachbarschaften.

Das Einbetten selbst ist gemockt: Ein Test, der ein 220-MB-Modell lädt, misst
die Bibliothek, nicht unseren Code. Was hier zählt, ist die Buchhaltung —
dass nichts doppelt gerechnet wird, dass ein Modellwechsel den alten Index
nicht löscht, und dass Nachbarschaften **über Städtegrenzen hinweg** entstehen.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from council.cities import index
from council.cities.model import Batch, File, FileRole, Paper
from council.cities.store import CitiesStore

MODELL = "test-mini"


def falscher_vektor(text: str, dim: int = 8) -> np.ndarray:
    """Deterministischer „Vektor" aus dem Hash — gleiche Texte, gleiche Richtung."""
    roh = hashlib.sha256(text.encode("utf-8")).digest()[:dim]
    v = np.frombuffer(roh, dtype=np.uint8).astype("float32") - 128.0
    return v / (np.linalg.norm(v) or 1.0)


@pytest.fixture(autouse=True)
def ohne_echtes_modell(monkeypatch):
    monkeypatch.setattr(index, "_embed",
                        lambda texte: np.vstack([falscher_vektor(t) for t in texte]))


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_batch(Batch(
        papers=[
            Paper("ol:p:1", "oldenburg", "Kommunale Wärmeplanung", date="2026-06-01"),
            Paper("os:p:1", "osnabrueck", "Kommunale Wärmeplanung", date="2026-05-01"),
            Paper("os:p:2", "osnabrueck", "Ganz andere Sache", date="2026-05-02"),
        ],
        files=[
            File("ol:f:1", "oldenburg", FileRole.MAIN, paper_id="ol:p:1"),
            File("os:f:1", "osnabrueck", FileRole.MAIN, paper_id="os:p:1"),
            File("os:f:2", "osnabrueck", FileRole.MAIN, paper_id="os:p:2"),
        ]))
    s.put_text("ol:f:1", "council", "1", "Wärmeplan " * 400, 4, "ok")
    s.put_text("os:f:1", "pypdf", "1", "Wärmeplanung " * 400, 4, "ok")
    s.put_text("os:f:2", "pypdf", "1", "Etwas völlig anderes " * 200, 2, "ok")
    yield s
    s.close()


# -------------------------------------------------------------------- Chunks

def test_chunk_ueberlappt_und_deckelt():
    stuecke = index.chunk("A" * 20_000)
    assert len(stuecke) == index.MAX_CHUNKS
    # Jedes Fenster beginnt vor dem Ende des vorigen — sonst zerschneidet die
    # Grenze einen Satz und beide Hälften finden nichts.
    for (_i1, _t1, s1, e1), (_i2, _t2, s2, _e2) in zip(stuecke, stuecke[1:]):
        assert s2 < e1 and s2 > s1
    assert index.chunk("") == []
    assert index.chunk("   ") == []


def test_kurzer_text_gibt_genau_ein_fenster():
    stuecke = index.chunk("Kurz.")
    assert len(stuecke) == 1 and stuecke[0][1] == "Kurz."


def test_build_chunks_ist_idempotent(store):
    erst = index.build_chunks(store)
    assert erst > 0
    assert index.build_chunks(store) == 0, "zweiter Lauf darf nichts neu schneiden"


def test_geaenderter_text_erzeugt_neue_chunks(store):
    index.build_chunks(store)
    store.put_text("ol:f:1", "council", "1", "Ein ganz anderer Text " * 100, 2, "ok")
    assert index.build_chunks(store) > 0


# ---------------------------------------------------------------- Embeddings

def test_chunk_vektoren_nur_einmal(store):
    index.build_chunks(store)
    erst = index.embed_chunks(store, MODELL)
    assert erst > 0
    assert index.embed_chunks(store, MODELL) == 0


def test_ein_zweites_modell_loescht_das_erste_nicht(store):
    """Der Kern der Flexibilität: Zwei Modelle nebeneinander, vergleichbar."""
    index.build_chunks(store)
    index.embed_chunks(store, MODELL)
    assert index.embed_chunks(store, "anderes-modell") > 0
    zahlen = dict(store._conn.execute(
        "SELECT model, COUNT(*) FROM chunk_embeddings GROUP BY 1").fetchall())
    assert zahlen[MODELL] > 0 and zahlen["anderes-modell"] > 0


def test_objektvektoren_nutzen_die_annotation(store):
    store.put_annotation("paper", "ol:p:1", "classify", "2",
                         {"summary": "Der Wärmeplan wird beschlossen.",
                          "instrument": "Kommunale Wärmeplanung"}, "h1")
    assert index.embed_objects(store, MODELL) == 3
    assert index.embed_objects(store, MODELL) == 0, "unverändert = nichts zu tun"
    # Eine NEUE Annotation ändert den Text und damit den Vektor.
    store.put_annotation("paper", "ol:p:1", "classify", "2",
                         {"summary": "Etwas ganz anderes.", "instrument": "X"}, "h2")
    assert index.embed_objects(store, MODELL) == 1


def test_object_text_faellt_auf_den_volltext_zurueck():
    ohne = index.object_text({"name": "Titel"}, None, "Sachverhalt: lange Geschichte.")
    assert "Sachverhalt" in ohne
    mit = index.object_text({"name": "Titel"}, {"summary": "Kurz.", "instrument": "Ding"},
                            "Sachverhalt: lange Geschichte.")
    assert "Sachverhalt" not in mit and "Kurz." in mit


# ------------------------------------------------------------- Nachbarschaft

def test_nachbarn_gehen_ueber_stadtgrenzen(store):
    """Der eigentliche Zweck: Der Oldenburger Beschluss findet den Osnabrücker."""
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=-0.99)
    treffer = store.neighbors("paper", "ol:p:1", MODELL)
    assert treffer, "ohne Nachbarn in anderen Städten wäre der Speicher sinnlos"
    assert {t["body_id"] for t in treffer} == {"osnabrueck"}


def test_nachbarn_aus_derselben_stadt_kommen_gar_nicht_erst_rein(store):
    """Sie beantworten die Frage nicht — und verdrängten die fremden aus den
    besten acht (gemessen: 3.830 von 5.596 Oldenburger Kanten zeigten auf
    Oldenburg)."""
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=-0.99)
    for a_id in ("os:p:1", "os:p:2"):
        assert {t["body_id"] for t in store.neighbors("paper", a_id, MODELL)} == {"oldenburg"}


def test_nachbarn_sind_nach_naehe_sortiert(store):
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=-0.99)
    werte = [t["score"] for t in store.neighbors("paper", "ol:p:1", MODELL)]
    assert werte == sorted(werte, reverse=True)


def test_kein_papier_ist_sein_eigener_nachbar(store):
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=-0.99)
    assert all(t["b_id"] != "ol:p:1" for t in store.neighbors("paper", "ol:p:1", MODELL))


def test_schwelle_haelt_unverwandtes_draussen(store):
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=0.999)
    assert store.neighbors("paper", "ol:p:1", MODELL) == []


def test_zweiter_lauf_haeuft_keine_kanten_an(store):
    index.embed_objects(store, MODELL)
    index.build_neighbors(store, MODELL, min_score=-0.99)
    vorher = len(store.neighbors("paper", "ol:p:1", MODELL))
    index.build_neighbors(store, MODELL, min_score=-0.99)
    assert len(store.neighbors("paper", "ol:p:1", MODELL)) == vorher


# --------------------------------------------------------------------- Suche

def test_volltextindex_findet_ueber_die_zusammenfassung(store):
    store.put_annotation("paper", "os:p:1", "classify", "2",
                         {"summary": "Hitzeaktionsplan für die Innenstadt."}, "h")
    assert index.build_fts(store) == 3
    treffer = store.fts_search("Hitzeaktionsplan")
    assert [t["paper_id"] for t in treffer] == ["os:p:1"]


def test_volltextindex_bleibt_bei_zwei_laeufen_eindeutig(store):
    """Zwei Papiere heißen so — nach zwei Läufen dürfen es nicht vier sein."""
    index.build_fts(store)
    erst = [t["paper_id"] for t in store.fts_search("Wärmeplanung")]
    assert len(erst) == 2
    index.build_fts(store)
    assert [t["paper_id"] for t in store.fts_search("Wärmeplanung")] == erst


def test_run_macht_alle_schritte(store):
    zahlen = index.run(store, model=MODELL)
    assert zahlen["chunks"] > 0 and zahlen["chunk_vectors"] > 0
    assert zahlen["object_vectors"] == 3 and zahlen["fts"] == 3
    assert zahlen["neighbors"] >= 0
