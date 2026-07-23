"""Tests für die Themen-Nachbarschaften (council.related).

Die Fälle bilden ab, was die Durchsicht an echten Daten zutage gefördert hat:
Gremien dürfen nicht in den Graph, Dubletten der Entitäten-Extraktion dürfen nicht
als "Verwandtschaft" erscheinen, und belegte Kanten müssen vor den bloß ähnlichen
einsortiert werden.
"""
from council import related
from council.store import CouncilStore


def _entities(*names) -> list[dict]:
    return [{"id": i, "slug": n.lower().replace(" ", "-"), "name": n, "kind": "ort", "n": 0}
            for i, n in enumerate(names, start=1)]


# --- Gremien-Filter --------------------------------------------------------

def test_gremien_gelten_als_struktur():
    assert related.is_structural("Sozialausschuss")
    assert related.is_structural("Jugendhilfeausschuss")
    assert related.is_structural("Gestaltungsbeirat")
    assert related.is_structural("Rat der Stadt Oldenburg")
    assert not related.is_structural("Fliegerhorst")
    assert not related.is_structural("Klinikum Oldenburg")


def test_gremien_aus_der_committees_tabelle():
    assert related.is_structural("Runder Tisch Verkehr", {"runder tisch verkehr"})
    assert not related.is_structural("Runder Tisch Verkehr", set())


# --- Alias-Erkennung -------------------------------------------------------

def test_dubletten_werden_als_alias_erkannt():
    # Namensvarianten derselben Sache — starke Überlappung + Teilstring.
    assert related.is_alias("Nadorster Straße", "Untere Nadorster Straße", 0.48)
    assert related.is_alias("Hafen", "Hafen der Stadt Oldenburg", 0.60)
    assert related.is_alias("Hallensichel", "Hallensichel-Ost", 0.90)


def test_echte_beziehungen_sind_kein_alias():
    # Teilstring, aber schwache Überlappung → eigenständiger Gegenstand.
    assert not related.is_alias("Fliegerhorst", "Grundschule Fliegerhorst", 0.02)
    assert not related.is_alias("Stadtmuseum", "Tiefgarage Am Stadtmuseum", 0.07)
    assert not related.is_alias("Kreyenbrück", "IGS Kreyenbrück", 0.21)
    # Kein Teilstring → nie ein Alias, egal wie stark die Überlappung.
    assert not related.is_alias("Meerkamp", "Mittagsweg", 1.0)


# --- Textabgleich ----------------------------------------------------------

def test_textabgleich_findet_nennungen_mit_wortgrenzen():
    ents = _entities("Fliegerhorst", "Eversten")
    decisions = [
        {"id": 1, "text": "Bebauungsplan für den Fliegerhorst"},
        {"id": 2, "text": "Sanierung Everstenholz"},   # darf NICHT als Eversten zählen
    ]
    found = related.text_matches(ents, decisions)
    assert found[1] == {1}
    assert 2 not in found


def test_textabgleich_ueberspringt_gremien_und_kurze_namen():
    ents = _entities("Sozialausschuss", "Hafen")   # Hafen < MIN_NAME_LEN
    decisions = [{"id": 1, "text": "Bericht des Sozialausschuss zum Hafen"}]
    assert related.text_matches(ents, decisions) == {}


# --- Aufbau der Nachbarschaften -------------------------------------------

def test_belegte_kanten_brauchen_mindestevidenz():
    ents = _entities("A-Straße", "B-Straße", "C-Straße")
    links = [(1, 10), (2, 10),           # A+B einmal gemeinsam
             (1, 11), (2, 11),           # A+B ein zweites Mal
             (1, 12), (3, 12)]           # A+C nur einmal
    rows, stats = related.build(ents, links, [], {}, use_text_match=False)
    pairs = {(s, n) for s, n, t, *_ in rows if t == "belegt"}
    assert ("a-straße", "b-straße") in pairs
    assert ("a-straße", "c-straße") not in pairs   # nur 1 gemeinsamer Beschluss
    assert stats["pairs_proven"] == 1


def test_kanten_sind_beidseitig():
    ents = _entities("A-Straße", "B-Straße")
    links = [(1, 10), (2, 10), (1, 11), (2, 11)]
    rows, _ = related.build(ents, links, [], {}, use_text_match=False)
    assert ("a-straße", "b-straße", "belegt") in {(s, n, t) for s, n, t, *_ in rows}
    assert ("b-straße", "a-straße", "belegt") in {(s, n, t) for s, n, t, *_ in rows}


def test_alias_kante_wird_unterdrueckt():
    ents = _entities("Nadorster Straße", "Untere Nadorster Straße")
    links = [(1, d) for d in range(10, 20)] + [(2, d) for d in range(10, 20)]
    rows, stats = related.build(ents, links, [], {}, use_text_match=False)
    assert rows == []
    assert stats["alias_suppressed"] == 1


def test_gremien_kommen_nicht_in_den_graph():
    ents = _entities("Fliegerhorst", "Sozialausschuss")
    links = [(1, 10), (2, 10), (1, 11), (2, 11)]
    rows, stats = related.build(ents, links, [], {}, use_text_match=False)
    assert rows == []
    assert stats["structural"] == 1
    assert stats["entities"] == 1


def test_evidenz_wird_mitgeliefert():
    ents = _entities("A-Straße", "B-Straße")
    links = [(1, 10), (2, 10), (1, 11), (2, 11), (1, 12), (2, 12)]
    rows, _ = related.build(ents, links, [], {}, use_text_match=False)
    assert all(evidence == 3 for *_, evidence in rows)


# --- Store-Anbindung -------------------------------------------------------

def test_store_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.executemany(
        "INSERT INTO council_entities(id, slug, name, kind, n) VALUES (?,?,?,?,?)",
        [(1, "fliegerhorst", "Fliegerhorst", "ort", 158),
         (2, "entlastungsstrasse", "Entlastungsstraße", "ort", 40),
         (3, "brookweg", "Brookweg", "ort", 5)])
    store._conn.commit()
    store.save_entity_relations([
        ("fliegerhorst", "entlastungsstrasse", "belegt", 0, 0.31, 15),
        ("fliegerhorst", "brookweg", "aehnlich", 1, 0.74, 0),
    ])
    got = store.related_entities("fliegerhorst")
    assert [r["name"] for r in got] == ["Entlastungsstraße", "Brookweg"]
    assert got[0]["rel_type"] == "belegt" and got[0]["evidence"] == 15
    assert got[1]["rel_type"] == "aehnlich" and got[1]["evidence"] == 0
    # Neuberechnung ersetzt den alten Stand vollständig.
    store.save_entity_relations([("fliegerhorst", "brookweg", "belegt", 0, 0.5, 2)])
    assert [r["name"] for r in store.related_entities("fliegerhorst")] == ["Brookweg"]
    store.close()


def test_related_ueberlebt_entity_rebuild(tmp_path):
    """Die Tabelle ist slug-keyed — ein Rebuild von council_entities (neue IDs)
    darf die Nachbarschaften nicht ins Leere zeigen lassen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.executemany(
        "INSERT INTO council_entities(id, slug, name, kind, n) VALUES (?,?,?,?,?)",
        [(1, "fliegerhorst", "Fliegerhorst", "ort", 158),
         (2, "entlastungsstrasse", "Entlastungsstraße", "ort", 40)])
    store._conn.commit()
    store.save_entity_relations([("fliegerhorst", "entlastungsstrasse", "belegt", 0, 0.31, 15)])
    # extract_entities.py leert und füllt die Tabelle neu — mit anderen IDs.
    store._conn.execute("DELETE FROM council_entities")
    store._conn.executemany(
        "INSERT INTO council_entities(id, slug, name, kind, n) VALUES (?,?,?,?,?)",
        [(77, "fliegerhorst", "Fliegerhorst", "ort", 160),
         (88, "entlastungsstrasse", "Entlastungsstraße", "ort", 41)])
    store._conn.commit()
    assert [r["name"] for r in store.related_entities("fliegerhorst")] == ["Entlastungsstraße"]
    store.close()
