"""Die Idee als Ganzes: ``idea_groups`` und ihre Überschrift (Plan PR 47/49).

Die Übersicht der Bewegungen braucht je Idee Städte, Zeitraum, Ergebnisse
und eine Überschrift. Rechnete jeder Client das selbst aus 7.556 Karten, wäre
es in zwei Clients zweimal falsch — deshalb eine Tabelle, geschrieben vom
Cluster-Schritt. Diese Tests halten fest, was dort zählt und was nicht.
"""
from __future__ import annotations

import json

import pytest

from council.cities import clusters
from council.cities.index import EMBED_MODEL
from council.cities.model import Batch, Paper
from council.cities.store import CitiesStore


def _classify(store, pid: str, instrument: str, field: str = "klima_umwelt") -> None:
    store.put_annotation("paper", pid, "classify", "2",
                         {"field": field, "transfer": "direct", "competence": "own",
                          "instrument": instrument, "summary": f"{instrument}."},
                         "h", "m", 0.0)


@pytest.fixture()
def store(tmp_path):
    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper("ha/1", "hannover", "Hitzeaktionsplan Hannover", date="2023-06-01", kind="motion"),
            Paper("ha/2", "hannover", "Hitzeaktionsplan fortschreiben", date="2025-02-01", kind="motion"),
            Paper("ms/1", "muenster", "Hitzeschutz", date="2024-05-01", kind="proposal"),
            Paper("po/1", "potsdam", "Hitze", date="2024-09-01", kind="inquiry"),
            Paper("po/2", "potsdam", "Hitze, ausgeschlossen", date="2024-10-01", kind="motion"),
            Paper("po/3", "potsdam", "Antwort der Verwaltung", date="2024-11-01", kind="answer"),
            Paper("ol/1", "oldenburg", "Hitze in Oldenburg", date="2023-01-01", kind="motion"),
        ]))
        for pid, inst in (("ha/1", "Hitzeaktionsplan aufstellen"),
                          ("ha/2", "Hitzeaktionsplan fortschreiben"),
                          ("ms/1", "Hitzeschutzkonzept erstellen"),
                          ("po/1", "Hitzeaktionsplan erstellen"),
                          ("po/2", "Tempo 30"), ("po/3", "Antwort"),
                          ("ol/1", "Hitzeaktionsplan prüfen")):
            _classify(s, pid, inst)
        s.replace_idea_clusters(EMBED_MODEL, "1", [
            (EMBED_MODEL, "1", 1, pid, score) for pid, score in (
                ("ha/1", 0.95), ("ha/2", 0.9), ("ms/1", 0.8), ("po/1", 0.97),
                ("po/2", 0.5), ("po/3", 0.6), ("ol/1", 0.99))])
        s.put_annotation("cluster", "1:1", "cluster_check", "1",
                         {"label": "Hitzeaktionsplan", "drop": ["po/2"], "reason": "",
                          "stable": True}, "h", "m", 0.0)
        yield s


def _gruppe(store, cid: int = 1) -> dict:
    zeile = store.idea_group(EMBED_MODEL, "1", cid)
    assert zeile is not None
    return zeile


def test_was_zaehlt_und_was_nicht(store):
    """Drei Städte, vier Vorlagen: die Ausgeschlossene, die Antwort und die
    Oldenburger zählen nicht — Oldenburg steht nur als Hinweis daneben."""
    clusters.rebuild_idea_groups(store)
    g = _gruppe(store)
    assert g["cities"] == 3
    assert g["members"] == 4
    assert g["oldenburg_members"] == 1
    assert g["first_date"] == "2023-06-01" and g["last_date"] == "2025-02-01"
    zeitleiste = json.loads(g["timeline"])
    assert [p["paper_id"] for p in zeitleiste] == ["ha/1", "ms/1", "po/1", "ha/2"]
    assert all(p["body_id"] != "oldenburg" for p in zeitleiste)
    staedte = json.loads(g["per_city"])
    assert [s["body_id"] for s in staedte] == ["hannover", "muenster", "potsdam"], \
        "je Stadt nach erstem Datum"
    assert staedte[0]["members"] == 2


def test_das_ergebnis_kommt_aus_derselben_quelle_wie_die_karte(store, monkeypatch):
    """EINE Herleitung: Sonst stünde auf der Übersicht „angenommen" und auf
    der Karte „vertagt"."""
    gefragt: list[str] = []

    def ergebnis(pid):
        gefragt.append(pid)
        return {"outcome": "accepted"} if pid == "ha/1" else None

    monkeypatch.setattr(store, "outcome_for_paper", ergebnis)
    clusters.rebuild_idea_groups(store)
    g = _gruppe(store)
    assert json.loads(g["outcomes"]) == {"accepted": 1}
    assert set(gefragt) == {"ha/1", "ha/2", "ms/1", "po/1"}


def test_eine_unbelegte_gruppe_faellt_aus_der_liste(store):
    store.put_annotation("cluster", "1:1", "cluster_check", "1",
                         {"label": "Hitze", "drop": [], "reason": "", "stable": False},
                         "h", "m", 0.0)
    clusters.rebuild_idea_groups(store)
    assert _gruppe(store)["stable"] == 0
    zeilen, gesamt = store.idea_groups(EMBED_MODEL, "1", min_cities=2)
    assert gesamt == 0 and zeilen == []


def test_filter_sortierung_und_suche(store):
    store.upsert_batch(Batch(papers=[
        Paper("ms/9", "muenster", "Radschnellweg", date="2026-03-01", kind="motion"),
        Paper("po/9", "potsdam", "Radschnellweg Potsdam", date="2026-04-01", kind="motion"),
    ]))
    _classify(store, "ms/9", "Radschnellweg bauen", "verkehr")
    _classify(store, "po/9", "Radschnellweg planen", "verkehr")
    store._conn.executemany(
        "INSERT INTO idea_clusters (model, version, cluster_id, paper_id, score) VALUES (?,?,?,?,?)",
        [(EMBED_MODEL, "1", 2, "ms/9", 0.9), (EMBED_MODEL, "1", 2, "po/9", 0.8)])
    store._conn.commit()
    for pid, name, summary in (("ms/9", "Radschnellweg", "Radschnellweg bauen."),
                               ("po/9", "Radschnellweg Potsdam", "Radschnellweg planen.")):
        store.fts_upsert(pid, pid[:2], name, None, "", summary)
    clusters.rebuild_idea_groups(store)

    _, gesamt = store.idea_groups(EMBED_MODEL, "1", min_cities=2)
    assert gesamt == 2
    _, gesamt = store.idea_groups(EMBED_MODEL, "1", min_cities=3)
    assert gesamt == 1
    zeilen, _ = store.idea_groups(EMBED_MODEL, "1", field="verkehr")
    assert [z["cluster_id"] for z in zeilen] == [2]
    zeilen, _ = store.idea_groups(EMBED_MODEL, "1", sort="staedte")
    assert [z["cluster_id"] for z in zeilen] == [1, 2]
    zeilen, _ = store.idea_groups(EMBED_MODEL, "1", sort="zuletzt")
    assert [z["cluster_id"] for z in zeilen] == [2, 1]
    zeilen, _ = store.idea_groups(EMBED_MODEL, "1", q="radschnellweg")
    assert [z["cluster_id"] for z in zeilen] == [2], "Suche über die Mitglieder"
    zeilen, _ = store.idea_groups(EMBED_MODEL, "1", q="hitzeaktion")
    assert [z["cluster_id"] for z in zeilen] == [1], "Suche im Label"
    _, gesamt = store.idea_groups(EMBED_MODEL, "1", q='"(kaputt')
    assert gesamt == 0, "kaputte Suchsyntax ist kein Serverfehler"
    assert store.idea_groups_axis(EMBED_MODEL, "1", 2) == ("2023-06-01", "2026-04-01")
    assert store.idea_group_counts(EMBED_MODEL, "1", 2) == {"klima_umwelt": 1, "verkehr": 1}


def test_der_oldenburg_filter_liest_idea_fit(store):
    clusters.rebuild_idea_groups(store)
    _, gesamt = store.idea_groups(EMBED_MODEL, "1", oldenburg=("missing",))
    assert gesamt == 0, "ohne Urteil kein Status — unter einem Filter fällt sie raus"
    _, gesamt = store.idea_groups(EMBED_MODEL, "1")
    assert gesamt == 1, "ohne Filter steht sie da"
    store.put_annotation("cluster", "1:1", "idea_fit", "1",
                         {"status": "partial", "situation": "…", "evidence": [],
                          "related": [], "confidence": "medium"}, "h", "m", 0.0)
    zeilen, gesamt = store.idea_groups(EMBED_MODEL, "1", oldenburg=("missing", "partial"))
    assert gesamt == 1
    assert json.loads(zeilen[0]["verdict_json"])["status"] == "partial"
    _, gesamt = store.idea_groups(EMBED_MODEL, "1", oldenburg=("present",))
    assert gesamt == 0


def test_die_mitglieder_samt_oldenburg_nach_datum(store):
    zeilen = store.idea_group_members(EMBED_MODEL, "1", 1)
    assert [z["id"] for z in zeilen] == ["ol/1", "ha/1", "ms/1", "po/1", "ha/2"]


# ------------------------------------------------------------- Überschrift


def _m(instrument, score, name="Titel"):
    return {"instrument": instrument, "score": score, "name": name}


def test_belegtes_label_gewinnt():
    mitglieder = [_m("Verpackungssteuersatzung einführen", 0.9),
                  _m("Verpackungssteuer einführen", 0.95), _m("Einwegsteuer", 0.8)]
    assert clusters.idea_label(mitglieder, "Verpackungssteuer") == "Verpackungssteuer"


def test_oberbegriff_ohne_beleg_weicht_dem_typischsten():
    mitglieder = [_m("Hitzeaktionsplan aufstellen", 0.97), _m("Hitzeschutzkonzept", 0.9)]
    assert clusters.idea_label(mitglieder, "Klimaanpassung") == "Hitzeaktionsplan aufstellen"


def test_leeres_label_nimmt_das_typischste():
    mitglieder = [_m("Baumschutzsatzung ändern", 0.8), _m("Baumschutzsatzung erlassen", 0.93)]
    assert clusters.idea_label(mitglieder, None) == "Baumschutzsatzung erlassen"


def test_unbelegte_gruppe_traut_ihrem_label_nicht():
    mitglieder = [_m("Sportförderung", 0.7), _m("Sportförderrichtlinie", 0.8),
                  _m("Mähroboter Nachtfahrverbot", 0.9)]
    assert clusters.idea_label(mitglieder, "Sportförderung", stable=False) \
        == "Mähroboter Nachtfahrverbot"


def test_fuellwoerter_belegen_nichts():
    """„Einführung prüfen" steckt in jedem zweiten Instrument."""
    mitglieder = [_m("Einführung prüfen Tempo 30", 0.9), _m("Einführung prüfen Radweg", 0.8)]
    assert clusters.idea_label(mitglieder, "Einführung prüfen") == "Einführung prüfen Tempo 30"


def test_ohne_instrument_der_titel():
    assert clusters.idea_label([_m(None, 0.5, "Antrag Hitze")], None) == "Antrag Hitze"
