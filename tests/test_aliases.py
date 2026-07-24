"""Tests für die Zusammenführung doppelter Themen (council.aliases).

Die Fälle stammen aus der Messung am Produktionsbestand: Was zusammengehört
(„Bäderbetrieb Oldenburg" / „Bäderbetrieb der Stadt Oldenburg"), was nicht
(„Fliegerhorst" / „Grundschule Fliegerhorst") — und vor allem, dass die
Zusammenführung reversibel bleibt.
"""
from council import aliases
from council.store import CouncilStore


# --- Namensnormalisierung --------------------------------------------------

def test_rechtsform_wird_entfernt():
    assert aliases.strip_legal("Deutsche Bahn AG") == "Deutsche Bahn"
    assert aliases.strip_legal("IBIS e. V.") == "IBIS"
    assert aliases.strip_legal("Verkehr und Wasser GmbH") == "Verkehr und Wasser"


def test_ortszusatz_wird_entfernt():
    assert aliases.strip_city("Bäderbetrieb der Stadt Oldenburg") == "Bäderbetrieb"
    assert aliases.strip_city("Oldenburger Hauptbahnhof") == "Hauptbahnhof"


def test_praefix_wird_entfernt():
    assert aliases.strip_prefix("Eigenbetrieb Hafen") == "Hafen"
    assert aliases.strip_prefix("Sanierungsgebiet Kreyenbrück Nord") == "Kreyenbrück Nord"
    assert aliases.strip_prefix("Neues Stadtmuseum") == "Stadtmuseum"
    assert aliases.strip_prefix("Fliegerhorst") == "Fliegerhorst"


def test_core_fasst_schreibweisen_zusammen():
    assert aliases.core("Bäderbetrieb Oldenburg") == aliases.core("Bäderbetrieb der Stadt Oldenburg")
    assert aliases.core("Abfall-Lern-Pfad") == aliases.core("Abfall-Lernpfad")
    assert aliases.core("Fliegerhorst") != aliases.core("Grundschule Fliegerhorst")


def test_initialen_fuer_abkuerzungen():
    assert aliases.initials("Verkehr und Wasser GmbH") == "vwg"      # "und" zählt nicht
    assert aliases.initials("Deutsches Rotes Kreuz") == "drk"


# --- Kandidatenfindung -----------------------------------------------------

def _ents(*specs) -> list[dict]:
    out = []
    for i, (name, n) in enumerate(specs, start=1):
        out.append({"id": i, "slug": f"e{i}", "name": name, "kind": "organisation", "n": n})
    return out


def test_findet_rechtsform_und_ortsvarianten():
    ents = _ents(("Bäderbetrieb Oldenburg", 15), ("Bäderbetrieb der Stadt Oldenburg", 36))
    got = aliases.candidates(ents, {1: {1, 2}, 2: {3, 4}})
    assert [c["art"] for c in got] == ["rechtsform_ort"]


def test_findet_abkuerzung():
    ents = _ents(("VWG", 21), ("Verkehr und Wasser GmbH", 41))
    ents[0]["name"] = "VWG"
    got = aliases.candidates(ents, {1: {1}, 2: {2}})
    assert any(c["art"] == "abkuerzung" for c in got)


def test_teilstring_braucht_embedding_rueckhalt():
    """Sonst entstehen 137 Teilstring-Paare, von denen die meisten keine
    Dubletten sind (Fliegerhorst/Grundschule Fliegerhorst)."""
    import numpy as np
    ents = _ents(("Fliegerhorst", 158), ("Grundschule Fliegerhorst", 3))
    decs = {1: {1, 2}, 2: {3}}
    assert aliases.candidates(ents, decs, centroids=None) == []
    fern = {1: np.array([1.0, 0.0], dtype="float32"), 2: np.array([0.0, 1.0], dtype="float32")}
    assert aliases.candidates(ents, decs, centroids=fern) == []
    nah = {1: np.array([1.0, 0.0], dtype="float32"), 2: np.array([0.99, 0.14], dtype="float32")}
    assert len(aliases.candidates(ents, decs, centroids=nah)) == 1


def test_gezielte_arten_brauchen_keine_embeddings():
    """Rechtsform/Abkürzung/Präfix sind scharf genug, um auch ohne Vektoren
    zur Prüfung zu gehen — sonst fielen sie ohne Embeddings still aus."""
    ents = _ents(("IBIS", 4), ("IBIS e.V.", 6))
    assert len(aliases.candidates(ents, {1: {1}, 2: {2}}, centroids=None)) == 1


# --- Ketten und Zyklen -----------------------------------------------------

def test_ketten_werden_aufgeloest():
    assert aliases.resolve_chains({"a": "b", "b": "c"}) == {"a": "c", "b": "c"}


def test_zyklen_werden_verworfen():
    """Ohne Zyklusschutz würde die Auflösung endlos laufen oder Themen ganz
    verschwinden lassen."""
    assert aliases.resolve_chains({"a": "b", "b": "a"}) == {}
    assert aliases.resolve_chains({"a": "a"}) == {}


# --- Store: Zusammenführung + Rücknahme ------------------------------------

def _store_with_obs(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.add_entity_observations(
        [(1, "baederbetrieb-oldenburg", "Bäderbetrieb Oldenburg", "organisation"),
         (2, "baederbetrieb-oldenburg", "Bäderbetrieb Oldenburg", "organisation"),
         (3, "baederbetrieb-der-stadt-oldenburg", "Bäderbetrieb der Stadt Oldenburg", "organisation"),
         (4, "baederbetrieb-der-stadt-oldenburg", "Bäderbetrieb der Stadt Oldenburg", "organisation"),
         (5, "fliegerhorst", "Fliegerhorst", "ort"),
         (6, "fliegerhorst", "Fliegerhorst", "ort")],
        [1, 2, 3, 4, 5, 6])
    store.rebuild_entities_from_obs()
    return store


def test_ohne_alias_bleiben_es_zwei_themen(tmp_path):
    store = _store_with_obs(tmp_path)
    names = {e["name"] for e in store.entity_rows()}
    assert "Bäderbetrieb Oldenburg" in names and "Bäderbetrieb der Stadt Oldenburg" in names
    store.close()


def test_zusammenfuehrung_bundelt_beschluesse(tmp_path):
    store = _store_with_obs(tmp_path)
    store.save_entity_aliases([("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg",
                                "llm", "nur Ortszusatz", "2026-07-23T10:00:00")])
    store.rebuild_entities_from_obs()
    ents = {e["slug"]: e for e in store.entity_rows()}
    assert "baederbetrieb-oldenburg" not in ents          # Dublette verschwunden
    canon = ents["baederbetrieb-der-stadt-oldenburg"]
    assert canon["n"] == 4                                 # alle vier Beschlüsse an einer Stelle
    assert canon["name"] == "Bäderbetrieb der Stadt Oldenburg"   # Name vom Kanon, nicht vom Alias
    assert "fliegerhorst" in ents                          # Unbeteiligte bleiben unberührt
    store.close()


def test_ruecknahme_stellt_den_vorherigen_stand_her(tmp_path):
    """Der Kern der Reversibilität: council_entity_obs bleibt unangetastet."""
    store = _store_with_obs(tmp_path)
    before = {(e["slug"], e["n"]) for e in store.entity_rows()}
    store.save_entity_aliases([("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg",
                                "llm", "nur Ortszusatz", "2026-07-23T10:00:00")])
    store.rebuild_entities_from_obs()
    assert {e["slug"] for e in store.entity_rows()} != {s for s, _ in before}

    assert store.delete_entity_alias("baederbetrieb-oldenburg") is True
    store.rebuild_entities_from_obs()
    assert {(e["slug"], e["n"]) for e in store.entity_rows()} == before
    store.close()


def test_alter_slug_fuehrt_zum_kanon_statt_ins_leere(tmp_path):
    """Links und Lesezeichen von vor der Zusammenführung dürfen nicht brechen."""
    store = _store_with_obs(tmp_path)
    store._conn.execute(
        "INSERT INTO council_sessions(ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (1,'Rat','2026-01-01','18:00','Rathaus','2026-01-01')")
    for did in (1, 2, 3, 4):
        store._conn.execute(
            "INSERT INTO council_decisions(id, ksinr, position, title) VALUES (?,1,?,?)",
            (did, did, f"Beschluss {did}"))
    store._conn.commit()
    store.save_entity_aliases([("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg",
                                "llm", "nur Ortszusatz", "2026-07-23T10:00:00")])
    store.rebuild_entities_from_obs()

    detail = store.entity_detail("baederbetrieb-oldenburg")
    assert detail is not None
    assert detail["entity"]["slug"] == "baederbetrieb-der-stadt-oldenburg"
    assert detail["merged_from"] == "baederbetrieb-oldenburg"
    assert store.entity_detail("gibt-es-nicht") is None
    store.close()


def test_admin_liste_zeigt_ketten_das_echte_endziel(tmp_path):
    """Kette A→B, danach B→C: die Admin-Liste muss für A das ENDZIEL C nennen,
    nicht das weggemergte Zwischenglied B (sonst leerer Ziel-Name + die nach
    canonical_slug gruppierende UI spaltet ein Thema auf zwei Gruppen)."""
    store = _store_with_obs(tmp_path)
    # A = baederbetrieb-oldenburg → B = baederbetrieb-der-stadt-oldenburg → C = fliegerhorst
    store.save_entity_aliases([
        ("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg", "llm", "Ortszusatz", "2026-07-23T10:00:00"),
        ("baederbetrieb-der-stadt-oldenburg", "fliegerhorst", "llm", "Kette", "2026-07-23T10:01:00"),
    ])
    store.rebuild_entities_from_obs()

    rows = {r["slug"]: r for r in store.list_entity_aliases()}
    # Beide Kettenglieder zeigen auf das reale Endziel — Name gefüllt, nicht None.
    for slug in ("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg"):
        assert rows[slug]["canonical_slug"] == "fliegerhorst"
        assert rows[slug]["canonical_name"] == "Fliegerhorst"
        assert rows[slug]["canonical_n"] is not None
    # Rücknahme adressiert weiterhin den Alias selbst (per slug, nicht Ziel).
    assert store.delete_entity_alias("baederbetrieb-oldenburg") is True
    store.close()


def test_manuelle_zuordnung_wird_nicht_ueberschrieben(tmp_path):
    """Ein automatischer Lauf darf eine Handkorrektur nicht rückgängig machen."""
    store = _store_with_obs(tmp_path)
    store.save_entity_aliases([("baederbetrieb-oldenburg", "fliegerhorst",
                                "manuell", "von Hand", "2026-07-23T10:00:00")])
    store.save_entity_aliases([("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg",
                                "llm", "LLM meint anders", "2026-07-24T10:00:00")], replace=True)
    assert store.entity_aliases()["baederbetrieb-oldenburg"] == "fliegerhorst"
    store.close()


def test_kanon_ohne_eigene_beobachtung_bleibt_benannt(tmp_path):
    """Grenzfall: zeigt ein Alias auf einen Slug, der selbst unter der
    min_n-Schwelle liegt, darf die Gruppe nicht namenlos werden."""
    store = CouncilStore(tmp_path / "council.sqlite")
    store.add_entity_observations(
        [(1, "vwg", "VWG", "organisation"), (2, "vwg", "VWG", "organisation"),
         (3, "verkehr-und-wasser", "Verkehr und Wasser GmbH", "organisation")],
        [1, 2, 3])
    store.save_entity_aliases([("vwg", "verkehr-und-wasser", "llm", "Abkürzung",
                                "2026-07-23T10:00:00")])
    store.rebuild_entities_from_obs()
    ents = {e["slug"]: e for e in store.entity_rows()}
    assert ents["verkehr-und-wasser"]["name"] == "Verkehr und Wasser GmbH"
    assert ents["verkehr-und-wasser"]["n"] == 3
    store.close()


def test_admin_liste_zeigt_beide_namen(tmp_path):
    store = _store_with_obs(tmp_path)
    store.save_entity_aliases([("baederbetrieb-oldenburg", "baederbetrieb-der-stadt-oldenburg",
                                "llm", "nur Ortszusatz", "2026-07-23T10:00:00")])
    store.rebuild_entities_from_obs()
    rows = store.list_entity_aliases()
    assert len(rows) == 1
    assert rows[0]["alias_name"] == "Bäderbetrieb Oldenburg"       # aus den Beobachtungen
    assert rows[0]["canonical_name"] == "Bäderbetrieb der Stadt Oldenburg"
    assert rows[0]["source"] == "llm"
    store.close()


# --- LLM-Auswertung (ohne echten Aufruf) -----------------------------------

def _fake_response(payload: str):
    class _Msg:
        content = payload

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    return _Resp()


def test_abkuerzung_bekommt_immer_die_langform_als_hauptnamen(monkeypatch):
    """Das Modell liest „kürzeste kanonische Form" gern als „Abkürzung" und
    schlug im Lauf „Eigenbetrieb Gebäudewirtschaft und Hochbau → EGH" vor. Eine
    Themen-Seite „EGH" sagt aber niemandem etwas."""
    ents = [{"id": 1, "slug": "vwg", "name": "VWG", "kind": "organisation", "n": 21},
            {"id": 2, "slug": "vuw", "name": "Verkehr und Wasser GmbH",
             "kind": "organisation", "n": 41}]
    pairs = [{"a": 1, "b": 2, "art": "abkuerzung", "overlap": 0.0, "emb": 0.75}]
    monkeypatch.setattr(
        aliases.llm, "chat_complete",
        lambda **kw: _fake_response(
            '{"paare": [{"id": 0, "gleich": true, "kanonisch": "VWG", "grund": "Abkürzung"}]}'))

    got = aliases.decide(pairs, ents, {})
    assert len(got) == 1
    assert got[0]["canonical"] == 2 and got[0]["alias"] == 1   # Langform gewinnt


def test_llm_ablehnung_wird_respektiert(monkeypatch):
    ents = [{"id": 1, "slug": "fh", "name": "Fliegerhorst", "kind": "ort", "n": 158},
            {"id": 2, "slug": "gs", "name": "Grundschule Fliegerhorst", "kind": "ort", "n": 3}]
    pairs = [{"a": 1, "b": 2, "art": "teilstring", "overlap": 0.02, "emb": 0.64}]
    monkeypatch.setattr(
        aliases.llm, "chat_complete",
        lambda **kw: _fake_response('{"paare": [{"id": 0, "gleich": false, "grund": "Schule am Ort"}]}'))
    assert aliases.decide(pairs, ents, {}) == []


def test_kaputte_llm_antwort_kippt_den_lauf_nicht(monkeypatch):
    """Ein Batch darf nicht die übrigen mitreißen — sonst ist ein Lauf über
    165 Paare von einem einzigen Ausrutscher abhängig."""
    ents = [{"id": 1, "slug": "a", "name": "IBIS", "kind": "organisation", "n": 4},
            {"id": 2, "slug": "b", "name": "IBIS e.V.", "kind": "organisation", "n": 6}]
    pairs = [{"a": 1, "b": 2, "art": "rechtsform_ort", "overlap": 0.0, "emb": 0.87}]
    monkeypatch.setattr(aliases.llm, "chat_complete",
                        lambda **kw: _fake_response("kein JSON"))
    assert aliases.decide(pairs, ents, {}) == []
