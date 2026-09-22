"""``CitiesStore``: Rohablage, Upsert, Annotationen, Indizes.

Der wichtigste Fall hier ist die **Idempotenz**: Jede Stufe der Pipeline wird
im Zweifel zweimal gestartet (Cron doppelt, Absturz mittendrin, manueller
Nachlauf). Zweimal dasselbe zu schreiben darf nichts ändern.
"""
from __future__ import annotations

import pytest

from council.cities.model import (
    AgendaItem, Batch, Body, Consultation, File, FileRole, Meeting, Organization,
    OrgKind, Outcome, Paper, PaperKind,
)
from council.cities.store import CitiesStore, canonical_hash


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    yield s
    s.close()


def beispiel_batch() -> Batch:
    return Batch(
        organizations=[
            Organization("os:org:1", "osnabrueck", "Rat der Stadt Osnabrück", "Gremium", OrgKind.COUNCIL),
            Organization("os:org:2", "osnabrueck", "Stadtbezirksrat Nord", "Gremium", OrgKind.DISTRICT),
        ],
        meetings=[Meeting("os:m:1", "osnabrueck", "os:org:1", "Sitzung des Rates", "2026-06-30T16:00:00")],
        agenda_items=[
            AgendaItem("os:a:1", "os:m:1", "Mehrweg fördern", number="4.2", position=7,
                       result_raw="ungeändert beschlossen", outcome=Outcome.ACCEPTED),
            AgendaItem("os:a:2", "os:m:1", "Bericht", number="5", position=8),
        ],
        papers=[Paper("os:p:1", "osnabrueck", "Mehrweg fördern", reference="VO/2026/5306",
                      date="2026-06-30", paper_type_raw="Antrag", kind=PaperKind.MOTION,
                      web="https://example.org/vo/1")],
        files=[File("os:f:1", "osnabrueck", FileRole.MAIN, paper_id="os:p:1",
                    name="Sammeldokument öffentlich", mime="application/pdf", size=1234,
                    access_url="https://example.org/doc/1")],
        consultations=[Consultation("os:c:1", "os:p:1", meeting_id="os:m:1",
                                    agenda_item_id="os:a:1", organization_id="os:org:1",
                                    role_raw="Entscheidung", authoritative=True)],
    )


# ------------------------------------------------------------------ Schicht 0

def test_schema_zweimal_oeffnen_aendert_nichts(tmp_path):
    pfad = tmp_path / "cities.sqlite"
    s1 = CitiesStore(pfad)
    vorher = sorted(r[0] for r in s1._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')"))
    s1.close()
    s2 = CitiesStore(pfad)
    nachher = sorted(r[0] for r in s2._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')"))
    s2.close()
    assert vorher == nachher


def test_rohablage_dedupliziert_unveraendertes(store):
    obj = {"id": "https://example.org/p/1", "name": "Titel", "date": "2026-01-01"}
    assert store.put_raw_object("osnabrueck", "paper", obj["id"], obj) is True
    # Dasselbe Objekt, andere Schlüsselreihenfolge -> derselbe Hash, keine Zeile.
    gedreht = {"date": "2026-01-01", "name": "Titel", "id": obj["id"]}
    assert store.put_raw_object("osnabrueck", "paper", obj["id"], gedreht) is False
    assert store.raw_count("osnabrueck", "paper") == 1

    geaendert = dict(obj, name="Titel, korrigiert")
    assert store.put_raw_object("osnabrueck", "paper", obj["id"], geaendert) is True
    # Zwei Fassungen, aber nur EIN Objekt — und die neuere gewinnt.
    assert store.raw_count("osnabrueck", "paper") == 1
    assert store.latest_raw(obj["id"])["name"] == "Titel, korrigiert"
    assert len(list(store.raw_objects("osnabrueck", "paper"))) == 1


def test_canonical_hash_ist_reihenfolgeunabhaengig():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


# ------------------------------------------------------------------ Schicht 1

def test_upsert_batch_ist_idempotent(store):
    store.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    erst = store.upsert_batch(beispiel_batch())
    assert erst["papers"] == 1 and erst["agenda_items"] == 2
    store.upsert_batch(beispiel_batch())
    assert store.paper_count("osnabrueck") == 1
    assert len(store.agenda_items("os:m:1")) == 2
    assert len(store.organizations("osnabrueck")) == 2


def test_upsert_batch_aktualisiert_geaenderte_felder(store):
    store.upsert_batch(beispiel_batch())
    batch = beispiel_batch()
    batch.papers = [Paper("os:p:1", "osnabrueck", "Mehrweg fördern — neue Fassung",
                          reference="VO/2026/5306", date="2026-06-30",
                          paper_type_raw="Antrag", kind=PaperKind.MOTION)]
    store.upsert_batch(batch)
    p = store.paper("os:p:1")
    assert p["name"].endswith("neue Fassung")
    # web war im zweiten Batch nicht gesetzt und darf nicht verloren gehen.
    assert p["web"] == "https://example.org/vo/1"


def test_outcome_for_paper_bevorzugt_authoritative(store):
    batch = beispiel_batch()
    # Zweite Station: Vorberatung, anderes Ergebnis, NICHT authoritative.
    batch.meetings.append(Meeting("os:m:2", "osnabrueck", "os:org:1", "Vorberatung", "2026-07-15T16:00:00"))
    batch.agenda_items.append(AgendaItem("os:a:3", "os:m:2", "Mehrweg fördern",
                                         result_raw="vertagt", outcome=Outcome.POSTPONED))
    batch.consultations.append(Consultation("os:c:2", "os:p:1", meeting_id="os:m:2",
                                            agenda_item_id="os:a:3", role_raw="Vorberatung",
                                            authoritative=False))
    store.upsert_batch(batch)
    erg = store.outcome_for_paper("os:p:1")
    assert erg["outcome"] == "accepted"


def test_outcome_for_paper_ohne_ergebnis_ist_none(store):
    batch = beispiel_batch()
    batch.agenda_items = [AgendaItem("os:a:1", "os:m:1", "Mehrweg fördern")]
    store.upsert_batch(batch)
    assert store.outcome_for_paper("os:p:1") is None


def test_files_without_bytes(store):
    store.upsert_batch(beispiel_batch())
    offen = store.files_without_bytes("osnabrueck")
    assert [f["id"] for f in offen] == ["os:f:1"]
    store.set_file_sha("os:f:1", "abc123")
    assert store.files_without_bytes("osnabrueck") == []


# ------------------------------------------------------------------ Schicht 2

def test_text_for_paper_nimmt_hauptdokument(store):
    batch = beispiel_batch()
    batch.files.append(File("os:f:2", "osnabrueck", FileRole.AUXILIARY, paper_id="os:p:1",
                            name="Anlage 1"))
    store.upsert_batch(batch)
    store.put_text("os:f:2", "pypdf", "1", "Anlagentext, viel laenger als der Haupttext" * 5, 3, "ok")
    store.put_text("os:f:1", "pypdf", "1", "Der Sachverhalt.", 1, "ok")
    assert store.text_for_paper("os:p:1", "pypdf", "1") == "Der Sachverhalt."


def test_files_without_text(store):
    store.upsert_batch(beispiel_batch())
    store.set_file_sha("os:f:1", "abc")
    assert [f["id"] for f in store.files_without_text("pypdf", "1")] == ["os:f:1"]
    store.put_text("os:f:1", "pypdf", "1", "Text", 1, "ok")
    assert store.files_without_text("pypdf", "1") == []
    # Ein NEUER Extraktor sieht dieselbe Datei wieder als offen.
    assert [f["id"] for f in store.files_without_text("layout", "1")] == ["os:f:1"]


# ------------------------------------------------------------------ Schicht 3

def test_annotation_schreiben_und_lesen(store):
    store.upsert_batch(beispiel_batch())
    store.put_annotation("paper", "os:p:1", "classify", "2",
                         {"field": "klima_umwelt", "transfer": "adaptable"},
                         source_hash="h1", model="m", cost_usd=0.0001)
    a = store.annotation("paper", "os:p:1", "classify", "2")
    assert a["payload"]["field"] == "klima_umwelt"
    assert store.annotation_values("classify", "2", "transfer") == [("os:p:1", "adaptable")]


def test_annotation_versionen_liegen_nebeneinander(store):
    """Der Kern der Flexibilität: Fassung 1 und 2 gleichzeitig, vergleichbar."""
    store.upsert_batch(beispiel_batch())
    store.put_annotation("paper", "os:p:1", "classify", "1", {"transfer": "local"}, "h1")
    store.put_annotation("paper", "os:p:1", "classify", "2", {"transfer": "adaptable"}, "h1")
    assert store.annotation("paper", "os:p:1", "classify", "1")["payload"]["transfer"] == "local"
    assert store.annotation("paper", "os:p:1", "classify", "2")["payload"]["transfer"] == "adaptable"


def test_annotations_missing_findet_offene_und_veraltete(store):
    store.upsert_batch(beispiel_batch())
    assert [p["id"] for p in store.annotations_missing("paper", "classify", "2")] == ["os:p:1"]
    store.put_annotation("paper", "os:p:1", "classify", "2", {"x": 1}, source_hash="h1")
    assert store.annotations_missing("paper", "classify", "2") == []
    # Text hat sich geändert -> neuer source_hash -> wieder offen.
    offen = store.annotations_missing("paper", "classify", "2", source_hashes={"os:p:1": "h2"})
    assert [p["id"] for p in offen] == ["os:p:1"]


def test_put_annotation_weist_unbekannte_objektart_ab(store):
    with pytest.raises(ValueError):
        store.put_annotation("vorlage", "x", "classify", "2", {}, "h")


# ------------------------------------------------------------------ Schicht 4

def test_fts_findet_ueber_umlaute_hinweg(store):
    """``remove_diacritics 2`` macht ö zu o — aber NICHT zu oe.

    Wer „Buergerbeteiligung" tippt, findet „Bürgerbeteiligung" also nicht.
    Dieselbe Eigenschaft hat die Volltextsuche über die Oldenburger
    Beschlüsse; die Umschreibung gehört, wenn überhaupt, in die Suchschicht.
    """
    store.upsert_batch(beispiel_batch())
    store.fts_upsert("os:p:1", "osnabrueck", "Mehrweg fördern", "VO/2026/5306",
                     "Der Rat möge beschließen, Mehrweggeschirr zu fördern.", "Mehrweg fördern")
    assert [t["paper_id"] for t in store.fts_search("fordern")] == ["os:p:1"]
    assert [t["paper_id"] for t in store.fts_search("fördern")] == ["os:p:1"]
    assert store.fts_search("foerdern") == []
    assert [t["paper_id"] for t in store.fts_search("Mehrweggeschirr")] == ["os:p:1"]
    # Zweimal indizieren erzeugt keinen doppelten Treffer.
    store.fts_upsert("os:p:1", "osnabrueck", "Mehrweg fördern", "VO/2026/5306", "Text", "Kurz")
    assert len(store.fts_search("Mehrweg")) == 1


def test_fts_search_ueberlebt_kaputte_syntax(store):
    assert store.fts_search('was ist "das') == []


def test_neighbors_ersetzt_und_filtert_stadt(store):
    store.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    store.upsert_batch(beispiel_batch())
    store.upsert_batch(Batch(papers=[Paper("ol:p:9", "oldenburg", "Mehrweg in Oldenburg")]))
    store.replace_neighbors("mini", "paper", "ol:p:9", [("paper", "os:p:1", 0.81)])
    treffer = store.neighbors("paper", "ol:p:9", "mini")
    assert treffer[0]["b_id"] == "os:p:1" and treffer[0]["body_id"] == "osnabrueck"
    assert store.neighbors("paper", "ol:p:9", "mini", exclude_body="osnabrueck") == []
    # Zweiter Lauf ersetzt, statt zu häufen.
    store.replace_neighbors("mini", "paper", "ol:p:9", [("paper", "os:p:1", 0.9)])
    assert len(store.neighbors("paper", "ol:p:9", "mini")) == 1


def test_object_embeddings_puffer(store):
    store.upsert_batch(beispiel_batch())
    store.put_object_embedding("paper", "os:p:1", "mini", "h1", b"\x00\x01\x02\x03")
    ids, bodies, buf = store.object_embeddings("mini")
    assert ids == ["os:p:1"] and bodies == ["osnabrueck"] and buf == b"\x00\x01\x02\x03"
    assert store.object_embedding_hashes("mini") == {"os:p:1": "h1"}


# ------------------------------------------------------------------- Betrieb

def test_stages(store):
    assert store.stage_done("paper", "os:p:1", "extract", "1") is False
    store.mark_stage("paper", "os:p:1", "extract", "1", "done")
    assert store.stage_done("paper", "os:p:1", "extract", "1") is True
    store.mark_stage("paper", "os:p:2", "extract", "1", "error", "kaputt")
    assert store.stage_counts("extract", "1") == {"done": 1, "error": 1}


def test_stats(store):
    store.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    store.upsert_batch(beispiel_batch())
    store.set_file_sha("os:f:1", "abc")
    store.put_text("os:f:1", "pypdf", "1", "Text", 1, "ok")
    (zeile,) = store.stats()
    assert zeile["papers"] == 1
    assert zeile["papers_with_text"] == 1
    assert zeile["agenda_items"] == 2
    assert zeile["agenda_items_with_outcome"] == 1


def test_transaction_klammert_und_verschachtelt_sich_weg(store):
    with store.transaction():
        store.upsert_batch(beispiel_batch())      # nutzt selbst transaction()
        store.put_annotation("paper", "os:p:1", "classify", "2", {"x": 1}, "h")
    assert store.paper_count() == 1
    assert store.annotation("paper", "os:p:1", "classify", "2") is not None


def test_stats_zeigen_den_rueckstand(store):
    """Was fehlt, muss zählbar sein — sonst wächst es still.

    Am 08.09.2026 waren 19 % des Bestands eingeordnet, und niemand hätte es
    gemerkt: Der Wochen-Cron deckelt bei 3.000 Vorlagen je Lauf, und keine
    Kennzahl nannte den Rückstand.
    """
    store.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    batch = beispiel_batch()
    batch.papers.append(Paper("os:p:2", "osnabrueck", "Zweites Papier"))
    store.upsert_batch(batch)
    store.put_annotation("paper", "os:p:1", "classify", "2", {"field": "verkehr"}, "h1")
    store.put_object_embedding("paper", "os:p:1", "modell-a", "h1", b"\x00" * 8)

    z = {r["id"]: r for r in store.stats("modell-a")}["osnabrueck"]
    assert z["papers"] == 2
    assert z["papers_unclassified"] == 1, "os:p:2 hat keine Einordnung"
    assert z["papers_unembedded"] == 1, "os:p:2 hat keinen Vektor"
    assert z["papers_with_outcome"] == 1, "os:p:1 hängt an einem TOP mit Ergebnis"

    # Ein ANDERES Modell heißt: alles unbelegt. Die Schwelle 0,70 und die
    # Nachbarschaften sind modellspezifisch — die Zahl muss es auch sein.
    andere = {r["id"]: r for r in store.stats("modell-b")}["osnabrueck"]
    assert andere["papers_unembedded"] == 2


# --------------------------------------------------- Die Migrationsschleife

def _form(pfad) -> dict[str, set[str]]:
    """``{tabelle: {spalte, …}}`` — die vergleichbare Form einer Datenbank.

    Dasselbe Maß wie in ``tests/test_migration_bestand.py``: Tabellen und ihre
    Spalten, ohne Rücksicht auf den Wortlaut der CREATE-Anweisung (der trägt
    Kommentare, die sich ändern dürfen).
    """
    import sqlite3

    conn = sqlite3.connect(pfad)
    try:
        tabellen = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        return {t: {r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')}
                for t in tabellen}
    finally:
        conn.close()


def _stand_setzen(pfad, stand: int) -> None:
    import sqlite3

    conn = sqlite3.connect(pfad)
    try:
        with conn:
            conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (str(stand),))
    finally:
        conn.close()


def _marken(pfad) -> set[str]:
    import sqlite3

    conn = sqlite3.connect(pfad)
    try:
        return {r[0] for r in conn.execute(
            "SELECT key FROM meta WHERE key LIKE 'probe_%'")}
    finally:
        conn.close()


#: Fünf erfundene Migrationen, **absichtlich verdreht** und jede mit einer
#: sichtbaren Spur. Sie prüfen den MECHANISMUS, nicht ein Symptom — und das
#: ist hier nicht Bequemlichkeit, sondern notwendig: Die echten Migrationen 2
#: bis 6 legen ausschließlich Tabellen an, die ``SCHEMA`` bei jedem Öffnen
#: ohnehin anlegt. Ob sie liefen, ist an der Datenbank deshalb gar nicht
#: abzulesen (genau deshalb ist Prod heil geblieben, gemessen am 21.09.2026).
#: Die nächste Migration, die Zeilen anfasst statt Tabellen — Migration 7 ist
#: so eine —, wäre dagegen unwiederbringlich verloren.
VERDREHTE_PROBEN: list[tuple[int, str]] = [
    (n, f"INSERT INTO meta (key, value) VALUES ('probe_{n}', '1');")
    for n in (5, 2, 4, 1, 3)
]


def test_jede_migration_laeuft_egal_wo_sie_in_der_liste_steht(tmp_path, monkeypatch):
    """Der Fehler vom 21.09.2026, in einem Test.

    ``_migrate`` setzt nach jedem Schritt ``stand = version``. Stand eine
    kleinere Nummer HINTER einer größeren, galt sie danach als erledigt und
    lief nie. ``MIGRATIONS`` war von neu nach alt sortiert — für jede
    Datenbank unterhalb von Stand 7 lief damit ausschließlich Migration 7.
    Aufgefallen ist es erst, als Migration 8 vorangestellt die 7 verschluckte.
    """
    from council.cities import store as store_modul

    monkeypatch.setattr(store_modul, "MIGRATIONS", VERDREHTE_PROBEN)
    pfad = tmp_path / "cities.sqlite"
    CitiesStore(pfad).close()
    assert _marken(pfad) == {f"probe_{n}" for n in range(1, 6)}


def test_eine_gewachsene_datenbank_holt_nur_das_neuere_nach(tmp_path, monkeypatch):
    """Die Gegenrichtung: Was die Datenbank schon gesehen hat, läuft NICHT
    noch einmal. Sonst wäre aus der Reparatur ein doppelter Lauf geworden —
    bei einer Migration, die Zeilen löscht, ein Datenverlust."""
    from council.cities import store as store_modul

    monkeypatch.setattr(store_modul, "MIGRATIONS", VERDREHTE_PROBEN)
    pfad = tmp_path / "cities.sqlite"
    CitiesStore(pfad).close()
    _stand_setzen(pfad, 3)
    import sqlite3
    conn = sqlite3.connect(pfad)
    with conn:
        conn.execute("DELETE FROM meta WHERE key LIKE 'probe_%'")
    conn.close()

    CitiesStore(pfad).close()
    assert _marken(pfad) == {"probe_4", "probe_5"}, (
        "nur was größer als der Stand ist, darf nachlaufen")


def test_die_echten_migrationen_sind_wiederholbar(tmp_path):
    """Eine Migration, die beim zweiten Lauf stolpert, bricht den nächsten
    Deploy (``tests/CLAUDE.md``). Seit sie sortiert laufen, laufen auf einer
    frischen Datenbank ALLE — vorher war es nur die höchste, die übrigen sind
    also zum ersten Mal in diesem Pfad."""
    pfad = tmp_path / "cities.sqlite"
    CitiesStore(pfad).close()
    from council.cities.schema import SCHEMA_VERSION

    soll = _form(pfad)
    for stand in range(SCHEMA_VERSION):
        _stand_setzen(pfad, stand)
        CitiesStore(pfad).close()
        assert _form(pfad) == soll, f"nach einem Lauf ab Stand {stand}"


def test_hoechste_migration_und_schema_version_passen_zusammen():
    """Sonst entsteht eine Tabelle auf einer frischen Datenbank, aber auf
    keiner gewachsenen — oder umgekehrt."""
    from council.cities.schema import MIGRATIONS, SCHEMA_VERSION

    nummern = [v for v, _ in MIGRATIONS]
    assert len(nummern) == len(set(nummern)), "eine Nummer kommt doppelt vor"
    assert max(nummern) == SCHEMA_VERSION


def test_altversion_zaehlt_was_ein_versionssprung_entwertet(tmp_path):
    """Die Zahl, die aus einer Nebenwirkung eine Entscheidung macht.

    Am 15.09.2026 hob #1370 den `fit`-Annotator von 3 auf 4 — 9.560 Urteile
    galten damit als nicht vorhanden, und der nächste Sonntagslauf urteilte
    sie neu: vierzehn Stunden, drei bis vier Sonntage, rund sechs Dollar.
    Jetzt steht sie als Kennzahl `veraltet_<annotator>` im Cron-Lauf.
    """
    s = CitiesStore(tmp_path / "cities.sqlite")
    try:
        s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
        s.upsert_batch(Batch(papers=[
            Paper("os:p:1", "osnabrueck", "Eins", date="2026-05-01"),
            Paper("os:p:2", "osnabrueck", "Zwei", date="2026-05-02")]))
        s.put_annotation("paper", "os:p:1", "fit", "3", {"status": "partial"}, "h1")
        s.put_annotation("paper", "os:p:2", "fit", "4", {"status": "partial"}, "h2")
        assert s.annotations_altversion("fit", "4") == 1
        assert s.annotations_altversion("fit", "3") == 1
        assert s.annotations_altversion("classify", "2") == 0
    finally:
        s.close()


def test_suchwoerter_ueberleben_den_lauf(tmp_path):
    """Ein Zwischenspeicher, kein Urteil — deshalb eine eigene Tabelle."""
    s = CitiesStore(tmp_path / "cities.sqlite")
    try:
        assert s.evidence_terms() == {}
        assert s.put_evidence_terms([("os:p:1", "h1", ["Wärmenetz"])]) == 1
        assert s.evidence_terms() == {"os:p:1": ("h1", ["Wärmenetz"])}
        # Derselbe Schlüssel wird überschrieben, nicht verdoppelt.
        s.put_evidence_terms([("os:p:1", "h2", ["Fernwärme"])])
        assert s.evidence_terms() == {"os:p:1": ("h2", ["Fernwärme"])}
        assert s.put_evidence_terms([]) == 0
    finally:
        s.close()
