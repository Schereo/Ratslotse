"""Der Kartentext für Social Media: Kontextbau, Auswahl, Durchreichung.

Der LLM-Aufruf selbst wird ersetzt — geprüft wird, was das Modell zu sehen
bekommt und was mit seiner Antwort geschieht. Genau dort lagen die Fehler,
die diesen dritten Text nötig gemacht haben: Die Kurzfassung sieht nur den
Titel, der Tragweite-Grund wertet.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from council import social_text
from council.store import CouncilStore


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _sitzung(store, ksinr=1, tage=3, committee="Ausschuss für Finanzen und Beteiligungen"):
    tag = (date.today() + timedelta(days=tage)).isoformat()
    store._conn.execute(
        "INSERT OR REPLACE INTO council_sessions "
        "(ksinr, committee, session_date, session_time, location, fetched_at) "
        "VALUES (?, ?, ?, '17:00', 'Alte Fleiwa', '2026-08-30')", (ksinr, committee, tag))
    store._conn.commit()
    return tag


def _punkt(store, ksinr=1, nummer="Ö 10", titel="Ausfallbürgschaft für das Klinikum",
           kvonr=None, impact=None):
    store._conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public, kvonr) "
        "VALUES (?, ?, ?, 1, ?)", (ksinr, nummer, titel, kvonr))
    if impact is not None:
        store._conn.execute(
            "INSERT OR REPLACE INTO agenda_item_impact "
            "(ksinr, item_number, impact, reason, created_at) VALUES (?, ?, ?, ?, '2026-08-30')",
            (ksinr, nummer, impact, "Trägt ein hohes finanzielles Risiko."))
    store._conn.commit()


def test_kontext_nimmt_vorlage_und_anlagen():
    """Der Kern der Sache: Das Modell sieht Beschlussvorschlag, Kosten,
    Vorlagentext UND Anlagen — nicht nur den Titel wie die Kurzfassung."""
    punkt = {"committee": "Rat", "session_date": "2026-08-31",
             "title": "Bebauungsplan 837", "art": "Beschlussvorlage",
             "amt": "Stadtplanung", "beschlussvorschlag": "Der Rat beschließt …",
             "finanz_check": "Kosten: 1,2 Mio Euro", "klima_check": None,
             "raw_text": "Briefkopf. Sachverhalt: 8,6 Hektar, davon 3,9 im "
                         "Landschaftsschutzgebiet."}
    anlagen = [{"label": "Antrag der SPD", "is_antrag": 1, "antragsteller": "SPD-Fraktion",
                "raw_text": "Wir beantragen 110 Wohneinheiten."}]
    ktx, quelle = social_text.kontext(punkt, anlagen)

    assert "Bebauungsplan 837" in ktx
    assert "1,2 Mio Euro" in ktx
    assert "3,9 im Landschaftsschutzgebiet" in ktx      # aus dem Vorlagentext
    assert "110 Wohneinheiten" in ktx                    # aus der Anlage
    assert "Antrag von SPD-Fraktion" in ktx              # Anträge sind markiert
    # Der Briefkopf fliegt raus (vorlagen_kern), der Sachverhalt bleibt.
    assert "Briefkopf" not in ktx
    # Der Beschlussvorschlag ist als VORSCHLAG gekennzeichnet — sonst schreibt
    # das Modell „Der Rat beschließt" und nimmt das Ergebnis vorweg.
    assert "noch kein Beschluss" in ktx
    assert quelle == "vorlage+anlagen"


def test_kontext_meldet_ehrlich_wenn_nur_der_titel_da_ist():
    """``quelle`` beantwortet später die Frage, warum ein Text dünn ist."""
    ktx, quelle = social_text.kontext(
        {"committee": "Rat", "session_date": "2026-08-31", "title": "Irgendein Punkt"}, [])
    assert quelle == "titel"
    assert "Irgendein Punkt" in ktx


def test_grosse_anlagen_verdraengen_die_argumente_nicht():
    """Der „Materialband Lupenpläne" dieser Woche hat 400.000 Zeichen und ist
    als OCR-Text eine Kartensammlung. Der Antrag daneben hat 3.000 und sagt,
    was jemand will — er muss im Budget landen, nicht das Planwerk."""
    punkt = {"committee": "Rat", "session_date": "2026-08-31", "title": "Innenentwicklung",
             "raw_text": "Sachverhalt: kurz."}
    # Reihenfolge wie aus ``anlagen_fuer``: Anträge zuerst.
    anlagen = [{"label": "Antrag", "is_antrag": 1, "antragsteller": "CDU",
                "raw_text": "Kernforderung: mehr Innenentwicklung."},
               {"label": "Materialband", "is_antrag": 0, "antragsteller": None,
                "raw_text": "Planwerk " * 100_000}]
    ktx, _ = social_text.kontext(punkt, anlagen)

    assert "Kernforderung: mehr Innenentwicklung." in ktx
    assert len(ktx) <= social_text.VORLAGE_ZEICHEN + social_text.ANLAGEN_ZEICHEN + 2000


def test_nur_punkte_mit_tragweite_kosten_einen_aufruf(store):
    """Eine Woche hat rund 87 öffentliche Punkte, auf die Karten schaffen es
    etwa 20. Für die anderen wäre der Aufruf bezahlt und nie gelesen."""
    _sitzung(store)
    _punkt(store, nummer="Ö 10", impact=75)
    _punkt(store, nummer="Ö 11", titel="Ein unwichtiger Punkt", impact=10)
    _punkt(store, nummer="Ö 12", titel="Noch ohne Bewertung", impact=None)

    offen = store.agenda_items_needing_social_text(mindest_wichtig=40)
    assert [p["item_number"] for p in offen] == ["Ö 10"]

    # Geschriebenes wird nie erneut bezahlt.
    store.save_social_text(1, "Ö 10", "Zur Abstimmung steht …", "vorlage")
    assert store.agenda_items_needing_social_text(mindest_wichtig=40) == []


def test_vergangene_sitzungen_bleiben_draussen(store):
    """Der Text steht in einer VORSCHAU."""
    _sitzung(store, ksinr=2, tage=-3)
    _punkt(store, ksinr=2, impact=90)
    assert store.agenda_items_needing_social_text(mindest_wichtig=40) == []


def test_wochenvorschau_reicht_den_kartentext_durch(store):
    """Der Bot liest ihn über /api/social/wochenvorschau — er muss also im
    Punkt-Dict ankommen, neben der Kurzfassung, nicht statt ihrer."""
    _sitzung(store)
    _punkt(store, nummer="Ö 10", impact=75)
    store._conn.execute(
        "INSERT OR REPLACE INTO agenda_item_summaries "
        "(ksinr, item_number, summary, agenda_hash, created_at) "
        "VALUES (1, 'Ö 10', 'Der Ausschuss berät über die Bürgschaft.', 'h', '2026-08-30')")
    store._conn.commit()
    store.save_social_text(1, "Ö 10", "Zur Abstimmung steht eine Bürgschaft über "
                                      "13,5 Millionen Euro.", "vorlage+anlagen")

    punkte = store.wochenvorschau(tage=10, max_punkte=40)["punkte"]
    unserer = [p for p in punkte if p["item_number"] == "Ö 10"]
    assert unserer, "Punkt fehlt ganz in der Wochenvorschau"
    assert unserer[0]["social_text"].startswith("Zur Abstimmung steht")
    assert unserer[0]["summary"] == "Der Ausschuss berät über die Bürgschaft."


def test_ohne_brauchbare_antwort_bleibt_es_bei_nichts(monkeypatch):
    """Lieber keine Zeile als eine erfundene: Der Bot fällt dann auf die
    Kurzfassung zurück."""
    class _Antwort:
        def __init__(self, inhalt):
            self.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]

    monkeypatch.setattr(social_text.llm, "chat_complete",
                        lambda **kw: _Antwort("kein JSON, nur Prosa"))
    monkeypatch.setattr(social_text.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(social_text.prompts, "render", lambda *a, **k: "user")

    punkt = {"committee": "Rat", "session_date": "2026-08-31", "title": "Ein Punkt"}
    assert social_text.text_fuer(punkt, []) is None


def test_der_text_wird_auf_kartenlaenge_gekappt(monkeypatch):
    """Die Karte setzt den Satz, sie scrollt ihn nicht."""
    class _Antwort:
        def __init__(self, inhalt):
            self.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]

    lang = "Zur Abstimmung steht " + "sehr viel Text " * 60
    monkeypatch.setattr(social_text.llm, "chat_complete",
                        lambda **kw: _Antwort('{"text": "%s"}' % lang))
    monkeypatch.setattr(social_text.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(social_text.prompts, "render", lambda *a, **k: "user")

    text, _ = social_text.text_fuer(
        {"committee": "Rat", "session_date": "2026-08-31", "title": "Ein Punkt"}, [])
    assert len(text) <= social_text.MAX_ZEICHEN


def test_auch_die_restliste_traegt_den_kartentext(store):
    """Die zweite Karte einer Sitzung wird aus ``weitere_je_sitzung`` gebaut.

    Diese Liste entsteht Feld für Feld — und genau dort fehlte der neue
    Kartentext: Der Dringlichkeitsantrag zur PAK-Belastung stand auf der
    Karte, darunter nichts (Tims Befund 30.08.26). Dieselbe Falle hatte am
    19.08.26 schon die Kurzfassung erwischt.
    """
    _sitzung(store)
    # Vier Punkte: Die Wochenvorschau zeigt drei, der vierte landet in der
    # Restliste — und muss seinen Text behalten.
    for i, nr in enumerate(("Ö 1", "Ö 2", "Ö 3", "Ö 4")):
        _punkt(store, nummer=nr, titel=f"Ein inhaltlicher Punkt Nummer {i}",
               impact=90 - i)
        store.save_social_text(1, nr, f"Kartentext zu Punkt {i}.", "vorlage")

    daten = store.wochenvorschau(tage=10, max_punkte=40)
    assert all(p["social_text"] for p in daten["punkte"])
    rest = daten["weitere_je_sitzung"][1]
    assert rest, "kein Punkt in der Restliste — Test prüft nichts"
    assert all(p["social_text"] for p in rest)
