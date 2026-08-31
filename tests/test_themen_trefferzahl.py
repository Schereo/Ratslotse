"""Eine Zahl für „Beschlüsse zu diesem Thema" — an allen drei Stellen.

Hintergrund (Tim, Build 12 auf dem iPad): Dasselbe Thema
„Fliegerhorststraße" trug drei verschiedene Zahlen. Die Themen-Karte sagte
„40+ Beschlüsse", das Blatt „Thema anpassen" darüber „12 Beschlüsse", und der
Klick auf „alle ansehen" landete in einer Liste mit 25 Einträgen. Drei
Rechenwege:

  Karte   gespeicherte Treffer des Matching-Laufs
  Blatt   eigene Suche mit eigener Schwelle und Deckel 12 (= die Länge des
          LLM-Kontexts, nie als Zähler gedacht)
  Liste   gespeicherte Treffer, aber die Suchseite stand auf „nur Beschlüsse"
          und warf die Berichte still heraus

Diese Tests halten die Vereinheitlichung fest: **eine** Definition
(``council.topic_intel.treffer``), **ein** Deckel, und der Weg hinter „alle
ansehen" zeigt dieselbe Menge, die die Karte zählt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from council import topic_intel

ROOT = Path(__file__).resolve().parents[1]


def test_matching_lauf_und_web_rechnen_mit_derselben_funktion():
    """Der Cron-Lauf darf keine eigene Kopie der Definition haben — sonst
    driften Karte und Blatt beim nächsten Schwellenwert wieder auseinander."""
    from scripts import match_topics_decisions as lauf

    assert lauf.treffer is topic_intel.treffer
    assert lauf.SCHWELLE == topic_intel.SCHWELLE
    assert lauf.DECKEL == topic_intel.DECKEL
    # Der Deckel ist Vorgabe des Laufs, nicht nur ein CLI-Zufall.
    assert lauf.process.__defaults__[0] == topic_intel.DECKEL


def test_stichtag_ist_ueberall_derselbe():
    """„Aktuell" darf nicht zweimal gerechnet werden: Die Karte zählt „n in 6
    Monaten", der Wochenlauf entscheidet damit, ob ein neuer Treffer eine Mail
    wert ist (30.08.2026). Zwei Kopien wären zwei Grenzen, sobald jemand eine
    davon anfasst — genau die Sorte Drift, die dieser Datei ihren Namen gab.
    """
    from scripts import match_topics_decisions as lauf

    assert lauf.vor_sechs_monaten is topic_intel.vor_sechs_monaten
    # Die Web-Seite derselben Grenze prüft `test_backend_api`, wo der
    # Backend-Pfad schon im sys.path liegt.


class _Store:
    """Gerade genug Store, damit ``zaehle_treffer`` nicht vorzeitig abbricht."""

    def embeddings_version(self):
        return (5, 5, 1)


def test_blatt_zaehlt_wie_die_karte(monkeypatch):
    """„Passt gerade auf" nennt jetzt die Zahl der EINEN Definition — samt
    Deckel-Kennzeichen. Vorher stand dort die Länge des Prompt-Kontexts (12),
    während die Karte „40+" sagte."""
    monkeypatch.setattr(topic_intel, "find_matches",
                        lambda *a, **k: [{"title": "Fliegerhorst: Erschließung"}] * 3)
    monkeypatch.setattr(topic_intel, "treffer",
                        lambda *a, **k: ([(i, 0.5) for i in range(topic_intel.DECKEL)], True, 120))
    monkeypatch.setattr(topic_intel, "_call_model", lambda *a, **k: {
        "einordnung": "belegt", "beschreibung": "Ein Satz.", "begruendung": ""})

    r = topic_intel.analyse(_Store(), "Fliegerhorststraße", "Alles rund um den Fliegerhorst.")
    assert r["matches"] == topic_intel.DECKEL
    assert r["matches_capped"] is True


def test_schablone_meldet_sich_im_log(monkeypatch, caplog):
    """Fällt die Beschreibung auf die Schablone zurück, muss das im Log stehen.

    Vorher war der Weg stumm: ``_call_model`` fing jeden Fehler ab und gab
    ``None`` zurück, die Nutzer:in bekam „Beschlüsse, Planungen und Maßnahmen …
    rund um X" und von außen war nicht zu sehen, wie oft das passiert — man
    konnte es nur hinterher an den gespeicherten Beschreibungen abzählen
    (Tims Frage 28.08.2026).
    """
    import logging

    def modell_weg(*a, **k):
        raise RuntimeError("Zeitüberschreitung")

    monkeypatch.setattr(topic_intel.prompts, "render", lambda *a, **k: "prompt")
    monkeypatch.setattr(topic_intel.llm, "chat_complete", modell_weg)
    with caplog.at_level(logging.WARNING, logger="council.topic_intel"):
        assert topic_intel._call_model("Cäcilienbrücke", []) is None
    meldungen = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    # Der Themen-Name gehört mit hinein, sonst lässt sich ein wiederkehrender
    # Ausreißer im Log nicht von einem einmaligen Aussetzer unterscheiden.
    assert any("Cäcilienbrücke" in m and "Schablone" in m for m in meldungen), meldungen


def test_ohne_reranker_wird_keine_fremde_zahl_erfunden(monkeypatch):
    """Fällt der Cross-Encoder aus, zählen ersatzweise die Belege — aber nie
    eine Zahl aus einer zweiten, dauerhaft danebenliegenden Quelle: Der Deckel
    bleibt aus, sonst behauptete das Blatt ein „+", das niemand geprüft hat."""
    monkeypatch.setattr(topic_intel, "find_matches",
                        lambda *a, **k: [{"title": "Brücke saniert"}] * 4)

    def kein_reranker(*a, **k):
        raise RuntimeError("Cross-Encoder nicht verfügbar")

    monkeypatch.setattr(topic_intel, "treffer", kein_reranker)
    monkeypatch.setattr(topic_intel, "_call_model", lambda *a, **k: {
        "einordnung": "belegt", "beschreibung": "Ein Satz.", "begruendung": ""})

    r = topic_intel.analyse(_Store(), "Cäcilienbrücke", "Sanierung der Hubbrücke.")
    assert r["matches"] == 4
    assert r["matches_capped"] is False


def test_leerer_embedding_bestand_zaehlt_gar_nicht(monkeypatch):
    """Ohne Embeddings hat der Matching-Lauf nie etwas gespeichert — dann darf
    der Web-Request auch nicht anfangen, das große Reranker-Modell zu laden
    (frische Umgebungen, Tests)."""
    class _Leer:
        def embeddings_version(self):
            return (0, 0, 1)

    def darf_nicht(*a, **k):
        raise AssertionError("ohne Embedding-Bestand wird nicht gesucht")

    monkeypatch.setattr(topic_intel, "treffer", darf_nicht)
    assert topic_intel.zaehle_treffer(_Leer(), "Irgendwas", "Irgendwas.") is None


# ---- „alle ansehen" muss halten, was die Karte verspricht -------------------

def _lies(rel: str) -> str:
    return (ROOT / "web" / "frontend" / rel).read_text(encoding="utf-8")


def test_alle_ansehen_schaltet_die_kategorie_auf_alle():
    """Der Link aus „Meine Themen" führt in die Suchseite. Deren Voreinstellung
    ist „nur Beschlüsse" — und die warf aus einer 40er-Trefferliste alle
    Berichte heraus (Fliegerhorststraße: 40 gespeichert, 25 angezeigt). Der
    Link muss die Kategorie deshalb ausdrücklich öffnen.

    Quer über zwei Sprachen geprüft, weil genau hier die Zusage der Karte
    eingelöst wird und ein pytest-Lauf billiger ist als ein iPad-Befund.
    """
    karte = _lies("components/themen-karte.tsx")
    assert "/council?tab=decisions&cat=all&topic=" in karte


def test_trefferliste_faellt_bei_einem_thema_auf_alle_zurueck():
    """Auch ohne ?cat= in der URL (getippt, geteilt, aus einem alten Link):
    Steht ein Thema im Filter, zeigt die Liste dessen ganze Menge."""
    view = _lies("app/(app)/council/view.tsx")
    assert "topicId ? \"all\" : \"vote\"" in view


def test_trefferliste_kennt_den_deckel():
    """Sagt die Karte „40+", darf die Liste nicht „40" behaupten."""
    view = _lies("app/(app)/council/view.tsx")
    assert "decision_count_capped" in view
    assert "topicCapped ? \"+\" : \"\"" in view


# ---- die Zahl gibt es sofort, nicht erst am Sonntag ------------------------

def test_anlegen_rechnet_mit_derselben_definition():
    """Der Sofort-Abgleich beim Anlegen darf keine eigene Suche sein — sonst
    steht die vierte Zahl im Raum. Er nimmt ``topic_intel.treffer`` und legt
    das Ergebnis ab, damit „alle ansehen" dieselbe Menge zeigt.

    Die beiden Schlüsselwörter sind kein Stil, sondern die zwei Fallen:
    ``als_neu=False`` hält den Bestand aus dem Wochenüberblick heraus,
    ``mark_topic_hits_seen`` verhindert ein „n neu" für Beschlüsse, die die
    Nutzer:in gerade erst als Zahl entstehen sieht.
    """
    source = (ROOT / "web" / "backend" / "app" / "routers" / "topics.py").read_text(encoding="utf-8")
    assert "topic_intel.treffer(" in source
    assert "save_topic_decision_matches" in source
    assert "als_neu=False" in source
    assert "mark_topic_hits_seen" in source


def test_karte_trennt_die_beiden_nullen():
    """Zwei Nullen sahen auf der Karte gleich aus, und eine davon log: „Noch
    keine Treffer — wir melden uns, sobald der Rat dazu entscheidet" stand auch
    unter einem Thema, das schlicht noch nicht gerechnet worden war
    („Schulbegleitung", 34 Beschlüsse seit 2018 — Tim, 28.08.2026)."""
    karte = _lies("components/themen-karte.tsx")
    # Beide Zustände hängen an `matched` — die Karte behauptet also nur dort
    # etwas über den Rat, wo wirklich gerechnet wurde.
    assert "topic.matched" in karte
    assert "Treffer werden noch gezählt" in karte
    assert "Noch nichts gefunden" in karte
    # Der alte Satz behauptete beides zugleich und war bei einem frisch
    # angelegten Thema schlicht falsch.
    assert "Noch keine Treffer" not in karte


@pytest.mark.parametrize("datei", [
    "components/themen-karte.tsx",
    "app/(app)/council/view.tsx",
])
def test_keine_glatte_endzahl_ohne_deckel_pruefung(datei):
    """Beide Stellen, die die Zahl zeigen, müssen das Deckel-Kennzeichen
    überhaupt kennen — sonst schleicht sich die glatte Endzahl zurück."""
    assert "capped" in _lies(datei)
