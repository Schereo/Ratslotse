"""Wächter für den Städte-Speicher — die Architektur, als Test.

Drei Regeln, deren Bruch die Flexibilität kostet, für die der Speicher gebaut
ist. Sie stehen hier und nicht in einer Prosa-Zeile, weil eine Prosa-Zeile
niemanden aufhält (``tests/CLAUDE.md``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from council.cities import registry
from council.cities.store import CitiesStore

CITIES_DIR = Path(__file__).resolve().parents[1] / "council" / "cities"

#: Die Spalten der normalisierten Schicht. **Diese Liste ist der Wächter:**
#: Eine neue Spalte in einer dieser Tabellen ist fast immer eine Annotation am
#: falschen Ort. Wer wirklich eine braucht, trägt sie hier ein und begründet
#: es im Pull Request.
SCHICHT_1_SPALTEN: dict[str, set[str]] = {
    "bodies": {"id", "name", "state", "ris_vendor", "oparl_url", "license",
               "population", "first_fetched", "last_fetched"},
    "organizations": {"id", "body_id", "name", "kind_raw", "kind"},
    "meetings": {"id", "body_id", "organization_id", "name", "start", "end",
                 "state_raw", "cancelled"},
    "agenda_items": {"id", "meeting_id", "number", "position", "name", "public",
                     "result_raw", "outcome", "resolution_text"},
    "papers": {"id", "body_id", "reference", "name", "date", "paper_type_raw",
               "kind", "originator_org_id", "under_direction_of_id", "web"},
    "files": {"id", "body_id", "paper_id", "agenda_item_id", "meeting_id", "role",
              "name", "mime", "size", "access_url", "sha256"},
    "consultations": {"id", "paper_id", "meeting_id", "agenda_item_id",
                      "organization_id", "role_raw", "authoritative"},
}

#: Wörter, an denen man eine Meinung erkennt. Keins davon gehört als
#: Spaltenname in Schicht 1.
MEINUNGS_WOERTER = ("field", "topic", "thema", "summary", "zusammenfassung",
                    "instrument", "transfer", "score", "rating", "importance",
                    "interest", "impact", "competence", "sentiment", "label")


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    yield s
    s.close()


def test_schicht_1_traegt_keine_meinung(store):
    """Was ein Modell sagt, gehört in ``annotations`` — nicht als Spalte."""
    for tabelle, erlaubt in SCHICHT_1_SPALTEN.items():
        ist = {r[1] for r in store._conn.execute(f"PRAGMA table_info({tabelle})")}
        neu = ist - erlaubt
        assert not neu, (
            f"Neue Spalte(n) {sorted(neu)} in {tabelle}. Gehört das in die Tabelle "
            f"`annotations` (Schicht 3)? Wenn nicht: Liste in "
            f"tests/test_cities_guards.py ergänzen und im Pull Request begründen.")
        fehlt = erlaubt - ist
        assert not fehlt, (
            f"Spalte(n) {sorted(fehlt)} fehlen in {tabelle} — Liste veraltet oder "
            f"Migration vergessen.")
        verdaechtig = [s for s in ist for w in MEINUNGS_WOERTER if w in s.lower()]
        assert not verdaechtig, (
            f"Spalte(n) {verdaechtig} in {tabelle} klingen nach einer Bewertung. "
            f"Bewertungen gehören in `annotations`.")


def test_kein_person_objekt(store):
    """Ratsmitglieder anderer Städte gehören nicht in unsere Datenbank.

    Für die Frage „welche Fraktion" reicht die Organisation; dieselbe Linie
    zieht ``council/stammdaten.py`` für Oldenburg (pe0051 trägt Privatadresse
    und Telefon).
    """
    tabellen = {r[0] for r in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert not [t for t in tabellen if "person" in t.lower() or "member" in t.lower()]

    for pfad in CITIES_DIR.rglob("*.py"):
        quelle = pfad.read_text(encoding="utf-8")
        # Kommentare und Docstrings dürfen das Wort erklären; Code nicht.
        ohne_kommentare = re.sub(r"#.*", "", quelle)
        ohne_kommentare = re.sub(r'""".*?"""', "", ohne_kommentare, flags=re.S)
        treffer = re.findall(r"originatorPerson|oparl:Person|\bpersons?\b", ohne_kommentare, re.I)
        assert not treffer, (
            f"{pfad.name} greift auf Personen zu ({set(treffer)}). "
            f"Der Städte-Speicher speichert keine Personen — siehe docs/vorschlag-staedte-speicher.md § 7.")


def test_registry_ist_vollstaendig():
    for body in registry.BODIES.values():
        assert body.dialect in registry.DIALECTS, f"{body.id}: unbekannter Dialekt {body.dialect}"
        if body.dialect != "oldenburg":
            assert body.system_url, f"{body.id}: aktive Stadt ohne Endpunkt"
            assert body.system_url.startswith("https://"), f"{body.id}: Endpunkt ohne TLS"
        assert re.fullmatch(r"[a-z0-9_-]+", body.id), f"{body.id}: Slug mit Sonderzeichen"
        assert body.id == body.id.lower()
        assert len(body.state) == 2, f"{body.id}: Bundesland-Kürzel erwartet"
    assert "oldenburg" in registry.BODIES, "Oldenburg gehört als Stadt Nummer null in den Speicher"
    assert registry.BODIES["oldenburg"].active, "Ohne Oldenburg ist kein Vergleich symmetrisch"
    ids = [b.id for b in registry.active_bodies()]
    assert len(ids) == len(set(ids))


def test_rohablage_wird_nicht_veraendert():
    """Schicht 0 ist append-only — kein UPDATE, kein DELETE auf ``raw_*``."""
    for pfad in CITIES_DIR.rglob("*.py"):
        quelle = pfad.read_text(encoding="utf-8")
        treffer = re.findall(r"(?:UPDATE|DELETE\s+FROM)\s+raw_\w+", quelle, re.I)
        assert not treffer, (
            f"{pfad.name} verändert die Rohablage ({treffer}). Sie ist append-only: "
            f"Ein geändertes Objekt bekommt eine neue Zeile, damit die Geschichte "
            f"eines Vorgangs erhalten bleibt.")


def test_die_oberflaeche_liest_die_aktuelle_fassung():
    """Welche Fassung die Ideen-Seite zeigt, darf nicht still veralten.

    Ein neuer Annotator liegt bewusst NEBEN dem alten (`(annotator, version)`
    im Schlüssel), bis der Bestand durchgerechnet ist — die Oberfläche zeigt
    solange die alte Fassung. Der Haken: Danach muss jemand die Zeile
    umstellen, und wenn es niemand tut, passiert nichts Sichtbares. Genau so
    zeigte die Karte am 09.09.2026 noch 1.254 Urteile aus Fassung 1, während
    9.484 aus Fassung 3 danebenlagen.

    Wer während einer Umstellung absichtlich die alte Fassung zeigt, ändert
    diesen Test im selben PR und schreibt dazu, warum — dann ist die
    Entscheidung sichtbar statt vergessen.
    """
    from council.cities.annotators import get
    from council.cities.store import CitiesStore

    for konstante, schluessel in ((CitiesStore.IDEEN_CLASSIFY, "classify"),
                                  (CitiesStore.IDEEN_FIT, "fit"),
                                  (CitiesStore.IDEEN_EFFORT, "effort")):
        ann = get(schluessel)
        assert konstante == (ann.key, ann.version), (
            f"Die Ideen-Seite liest {schluessel} in Fassung {konstante[1]}, "
            f"der Annotator steht auf {ann.version}.")


def test_die_ideen_abfragen_filtern_dieselben_vorlagenarten():
    """`IDEA_KINDS` steht in Python, die Abfrage trägt die Werte im SQL.

    Sie dort als Platzhalter zu binden ginge nicht ohne zusammengesetztes
    SQL, und genau das überspringt `tests/test_sql_spalten.py` — der Wächter
    wäre an der neuesten Abfrage blind. Also stehen die Werte ausgeschrieben
    da, und dieser Test hält sie an der Liste. Ein Tippfehler filterte sonst
    still die halbe Liste weg.

    Die Volltextsuche (`_SUCHE`) ist ABSICHTLICH nicht dabei: Wer nach
    „Hitzeschutz" sucht, will auch die Antwort der Verwaltung finden.
    """
    import re

    from council.cities.model import IDEA_KINDS
    from council.cities.store import CitiesStore

    erwartet = tuple(k.value for k in IDEA_KINDS)
    for name in ("_IDEEN_ZAEHLEN", "_IDEEN_JE_STATUS", "_IDEEN_ZEILEN"):
        treffer = re.search(r"p\.kind IN \(([^)]*)\)", getattr(CitiesStore, name))
        assert treffer, f"{name} filtert die Vorlagenart nicht mehr"
        im_sql = tuple(x.strip().strip("'") for x in treffer.group(1).split(","))
        assert im_sql == erwartet, (
            f"{name} filtert {im_sql}, model.IDEA_KINDS sagt {erwartet}")
    assert "p.kind IN" not in CitiesStore._SUCHE, (
        "die Volltextsuche soll auch Antworten und Mitteilungen finden")


def test_das_richtungs_goldenset_kennt_nur_gueltige_werte():
    """Ein Golden Set mit einem Wert, den es nicht mehr gibt, misst nichts.

    Genau das wäre am 09.09.2026 passiert: Die erste Fassung von `stance`
    hatte fünf Klassen (`introduce`/`expand`/`restrict`/`stop`/`review`) und
    traf 72 %; sechs der dreizehn Fehler lagen zwischen `introduce` und
    `expand`, einer Grenze, für die es keine Regel gibt. Zusammengelegt zu
    drei Klassen: 87 %. Die alten Werte stehen als `expected_fein` noch in
    den Fällen — sie dokumentieren die Zusammenlegung, sie messen nicht.
    """
    import json
    from pathlib import Path as P

    from council.cities.annotators import STANCE_VALUES

    datei = P(__file__).resolve().parents[1] / "eval" / "cases_cities_stance.json"
    faelle = json.loads(datei.read_text(encoding="utf-8"))
    assert faelle, "ohne Fälle misst der Prüfstand nichts"
    unbekannt = {f["expected"] for f in faelle} - set(STANCE_VALUES)
    assert not unbekannt, (
        f"Das Golden Set erwartet {sorted(unbekannt)}, `STANCE_VALUES` kennt "
        f"nur {list(STANCE_VALUES)}.")
    assert sum(1 for f in faelle if f["expected"] == "against") >= 5, (
        "Ohne Gegenrichtungen prüft der Lauf genau das nicht, wofür es den "
        "Annotator gibt")
