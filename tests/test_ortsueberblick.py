"""Überblick über einen Ort: „Was plant die Stadt für die Innenstadt?"

Am 23.11.2026 auf Prod: Die Frage nennt außer dem Ort kein Thema, und der
Reranker zog die Titel nach vorn, die den Ortsnamen tragen — vier Beratungen
des „Sofortprogramms … zur Unterstützung der Innenstadt“ von 2021. Das
Sanierungsgebiet Mittlere Innenstadt (2025/26) stand auf Rang 55 bis 81 von
147, und die Rahmenplanung Nördliche Innenstadt kam gar nicht erst vor den
Reranker, weil die Vorauswahl stadtweit suchte und erst danach auf den Ort
filterte. Hier steht, dass beides nicht mehr passiert.

Offline: kein Sprachmodell, keine echten Embeddings; der Store läuft in tmp_path.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from council import embeddings as emb
from council import qa
from council.scraper import CouncilSession
from council.store import CouncilStore

HEUTE = date(2026, 11, 23)


# --- Erkennung -------------------------------------------------------------

@pytest.mark.parametrize("frage, ort", [
    ("Was plant die Stadt für die Innenstadt?", "Innenstadt"),
    ("Welche Projekte gibt es in Osternburg?", "Osternburg"),
    ("Was wurde in Kreyenbrück beschlossen?", "Kreyenbrück"),
    ("Was tut sich in Donnerschwee?", "Donnerschwee"),
    ("Was ist am Schlossplatz geplant?", "Schlossplatz"),
])
def test_ueberblicksfragen_werden_erkannt(frage, ort):
    assert qa.place_overview_question(frage, ort)


@pytest.mark.parametrize("frage, ort", [
    # Ein Sachwort reicht für den semantischen Weg.
    ("Welche Radwege werden in Osternburg gebaut?", "Osternburg"),
    ("Was passiert in Wechloy mit der Grundschule?", "Wechloy"),
    # „Stand“ fragt nach EINER Sache — dort gewinnt die Semantik.
    ("Wie ist der Stand bei der Cäcilienbrücke?", "Cäcilienbrücke"),
    # Der Ort steht gar nicht in der Frage (Alias, Rückbezug).
    ("Was plant die Stadt dort?", "Innenstadt"),
])
def test_sachfragen_bleiben_beim_semantischen_weg(frage, ort):
    assert not qa.place_overview_question(frage, ort)


# --- Auswahl ---------------------------------------------------------------

def _zeile(i, datum, titel, wert, vorlage=None, akte=None):
    return {"id": i, "session_date": datum, "title": titel, "importance": wert,
            "template_number": vorlage, "matter_id": akte}


INNENSTADT = [
    # Das alte Programm: wichtig damals, viermal beraten, Titel mit Ortsnamen.
    _zeile(1, "2021-03-22", "Sofortprogramm der Stadt Oldenburg zur Unterstützung der Innenstadt", 58, "21/0258", 10),
    _zeile(2, "2021-03-22", "Sofortprogramm der Stadt Oldenburg zur Unterstützung der Innenstadt", 19, "21/0258", 10),
    _zeile(3, "2021-04-22", "Sofortprogramm der Stadt Oldenburg zur Unterstützung der Innenstadt - mündlicher Bericht", 28, None, 11),
    _zeile(4, "2021-09-06", "Sofortprogramm der Stadt Oldenburg zur Unterstützung der Innenstadt", 22, None, 11),
    # Ein Vorhaben in zwei Vorlagen: derselbe Titelkopf vor dem Gedankenstrich.
    _zeile(5, "2025-08-25", "Sanierungsgebiet Mittlere Innenstadt – Beginn der Vorbereitenden Untersuchung", 49, "25/0468", 20),
    _zeile(6, "2026-06-01", "Sanierungsgebiet Mittlere Innenstadt – Übernahme der Kosten, Ergebnis VU/ISEK", 52, "26/0331", 21),
    _zeile(7, "2026-05-21", "Sanierungsgebiet Mittlere Innenstadt – Übernahme der Kosten", 51, "26/0331", 21),
    # Dieselbe Vorlage, ein Titel ohne den Namen.
    _zeile(8, "2025-06-30", "Sanierungsgebiet Nördliche Innenstadt - Rahmenplanung", 79, "25/0310", 30),
    _zeile(9, "2025-05-28", "Rahmenplanung", 70, "25/0310", 30),
    _zeile(10, "2026-06-29", "Umsetzung der Pflasterung am Rathausmarkt", 40, None, 40),
    # Ein Beschluss ohne Titel — im Kontext stünde nur eine Nummer.
    _zeile(11, "2026-08-31", None, 81, None, 50),
]


def test_aktuelle_vorgaenge_vor_dem_alten_programm():
    """Drei Vorgänge vorn: Mittlere Innenstadt, Nördliche Innenstadt,
    Rathausmarkt. Das Sofortprogramm von 2021 nicht, obwohl sein Titel den
    Ortsnamen trägt und es damals wichtig war."""
    ids = qa.select_place_overview(INNENSTADT, today=HEUTE, matters=3)
    assert ids[:4] == [6, 5, 8, 10]
    assert not {1, 2, 3, 4} & set(ids[:4])


def test_der_zweite_beschluss_kommt_aus_einer_anderen_vorlage():
    """6 und 7 sind dieselbe Vorlage (Ausschuss und Rat) — zweimal dasselbe.
    5 ist der Beginn der Voruntersuchung: Er zeigt, wie weit das Vorhaben ist.
    Bei der Nördlichen Innenstadt gibt es nur eine Vorlage, also nur einen."""
    ids = qa.select_place_overview(INNENSTADT, today=HEUTE, matters=3)
    kopf = ids[:4]
    assert 7 not in kopf and 9 not in kopf


def test_alles_kommt_genau_einmal_zurueck():
    ids = qa.select_place_overview(INNENSTADT, today=HEUTE)
    assert sorted(ids) == sorted(r["id"] for r in INNENSTADT)


def test_ohne_titel_ganz_hinten():
    """Wichtig-Wert 81 und brandneu — aber ohne Titel stünde im Kontext nur
    eine Nummer."""
    assert qa.select_place_overview(INNENSTADT, today=HEUTE)[-1] == 11
    assert qa.select_place_overview(INNENSTADT, today=HEUTE, matters=2)[-1] == 11


def test_projekt_entitaet_legt_vorgaenge_zusammen():
    """Bebauungsplan, Bürgschaft und Vergabe des Stadions haben je eigene
    Vorlagen — erst die Projekt-Entität macht daraus einen Vorgang."""
    rows = [
        _zeile(1, "2026-06-01", "Stadionneubau Maastrichter Straße", 85, "26/0396", 1),
        _zeile(2, "2026-06-01", "Ausfallbürgschaft für die Stadion Oldenburg GmbH", 76, "26/0374", 2),
        _zeile(3, "2026-04-13", "Bebauungsplan 831", 76, "26/0172", 3),
        _zeile(4, "2026-02-19", "Bebauungsplan 844 (Bahnhofsviertel)", 58, "26/0100", 4),
    ]
    entitaeten = [
        {"matter_id": 1, "slug": "stadionneubau", "name": "Stadionneubau Maastrichter Straße", "kind": "project", "n": 15},
        {"matter_id": 2, "slug": "stadionneubau", "name": "Stadionneubau Maastrichter Straße", "kind": "project", "n": 15},
        {"matter_id": 3, "slug": "stadionneubau", "name": "Stadionneubau Maastrichter Straße", "kind": "project", "n": 15},
        # Der gefragte Ort selbst und ein Riese legen NICHT zusammen.
        {"matter_id": 4, "slug": "donnerschwee", "name": "Donnerschwee", "kind": "place", "n": 30},
        {"matter_id": 1, "slug": "donnerschwee", "name": "Donnerschwee", "kind": "place", "n": 30},
        {"matter_id": 4, "slug": "stadt", "name": "Stadtverwaltung", "kind": "organisation", "n": 900},
        {"matter_id": 1, "slug": "stadt", "name": "Stadtverwaltung", "kind": "organisation", "n": 900},
    ]
    keys = qa.overview_entity_keys(entitaeten, "Donnerschwee")
    assert keys == {1: ["stadionneubau"], 2: ["stadionneubau"], 3: ["stadionneubau"]}
    ids = qa.select_place_overview(rows, today=HEUTE, matters=2, per_matter=2, entity_keys=keys)
    # Zwei Vorgänge vorn: das Stadion (höchstens zwei Beschlüsse) und der B-Plan 844.
    assert 4 in ids[:3]
    assert len({1, 2, 3} & set(ids[:3])) == 2


def test_stadtteile_legen_nicht_zusammen():
    entitaeten = [{"matter_id": 1, "slug": "eversten", "name": "Eversten", "kind": "place", "n": 12}]
    assert qa.overview_entity_keys(entitaeten, "Innenstadt", {"Eversten"}) == {}


# --- Store -----------------------------------------------------------------

def test_store_liefert_zeilen_mit_grundakte(tmp_path):
    cs = CouncilStore(str(tmp_path / "c.sqlite"))
    cs.save_session(CouncilSession(1, "Rat", "2026-06-01", "17:00", "Rathaus"))
    with cs._conn:
        cs._conn.execute("INSERT INTO council_decisions (id, ksinr, position, item_number, title, kind, importance, template_number)"
                         " VALUES (7, 1, 1, '1', 'Sanierungsgebiet Mittlere Innenstadt', 'decision', 52, '26/0331')")
        cs._conn.execute("INSERT INTO council_decisions (id, ksinr, position, item_number, title, kind)"
                         " VALUES (8, 1, 2, '1.1', 'Änderungsantrag', 'amendment')")
        cs._conn.execute("INSERT INTO council_matter_items (matter_id, item_type, item_id, source) VALUES (3, 'decision', 7, 'vorlage')")
    rows = cs.place_overview_rows([7, 8])
    assert rows == [{"id": 7, "session_date": "2026-06-01", "title": "Sanierungsgebiet Mittlere Innenstadt",
                     "template_number": "26/0331", "importance": 52, "matter_id": 3}]
    cs.close()


# --- Vorauswahl im Ort -----------------------------------------------------

def test_vektorsuche_mit_ortsfilter_sucht_im_ort(monkeypatch):
    """Stadtweit läge Beschluss 3 hinter 1 und 2 — im Ort ist er der beste.
    Vorher kam er bei einem Pool von zwei gar nicht vor den Reranker."""
    ids = [1, 2, 3, 4]
    mat = np.array([[1.0, 0.0], [0.9, 0.1], [0.7, 0.3], [0.0, 1.0]])
    monkeypatch.setattr(emb, "_matrix", lambda store: (ids, mat))
    qv = np.array([1.0, 0.0])
    assert [i for i, _ in emb._search_vec(None, qv, top_k=2)] == [1, 2]
    assert [i for i, _ in emb._search_vec(None, qv, top_k=2, min_score=0.2, allowed={3, 4})] == [3]
    assert emb._search_vec(None, qv, top_k=2, allowed=set()) == []


# --- Prompt ----------------------------------------------------------------

def test_ueberblicksregel_steht_nur_beim_ueberblick_im_prompt():
    ort = {"id": "innenstadt", "name": "Innenstadt", "kind_label": "Ortsbereich"}
    mit, _ = qa._answer_messages("Was plant die Stadt für die Innenstadt?", [{"id": 1, "title": "T"}],
                                 typ="place", ort=ort, overview=True)
    ohne, _ = qa._answer_messages("Was plant die Stadt für die Innenstadt?", [{"id": 1, "title": "T"}],
                                  typ="place", ort=ort)
    text = lambda m: " ".join(str(x.get("content")) for x in m)  # noqa: E731
    assert "ÜBERBLICK ÜBER DEN ORT" in text(mit)
    assert "ÜBERBLICK ÜBER DEN ORT" not in text(ohne)


# --- Beleglage --------------------------------------------------------------

def test_ueberblick_gilt_nicht_als_duenn():
    """Die Auswahl trägt keine Rerank-Scores. Als „dünn“ verlangte der Prompt
    einen ersten Satz „die Unterlagen geben wenig her“ und eine kurze
    Antwort — bei zwölf belegten Vorgängen das Gegenteil der Wahrheit."""
    ohne_scores = [{"id": i, "title": "T"} for i in range(12)]
    assert qa.beleglage(ohne_scores) == "duenn"
    assert qa.beleglage(ohne_scores, deterministic=True) == "solide"
    assert qa.beleglage(ohne_scores[:2], deterministic=True) == "duenn"
