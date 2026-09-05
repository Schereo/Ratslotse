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


def _punkt(store, ksinr=1, nummer="Ö 10", title="Ausfallbürgschaft für das Klinikum",
           kvonr=None, impact=None, vorlage=True):
    """Ein Tagesordnungspunkt — standardmäßig MIT Vorlagentext.

    Ohne Material gäbe es nichts zu lesen, was die Kurzfassung nicht schon
    aus dem Titel hätte; solche Punkte lässt die Auswahl bewusst liegen.
    """
    if vorlage and kvonr is None:
        kvonr = 9000 + len(nummer) * 10 + ord(nummer[-1])
    store._conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public, kvonr) "
        "VALUES (?, ?, ?, 1, ?)", (ksinr, nummer, title, kvonr))
    if vorlage:
        store._conn.execute(
            "INSERT OR REPLACE INTO council_templates (kvonr, template_number, title, raw_text, "
            "fetched_at) VALUES (?, ?, ?, ?, '2026-08-30')",
            (kvonr, "26/0001", title, "Sachverhalt: Die Stadt bürgt für ein Darlehen."))
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
             "title": "Bebauungsplan 837", "kind": "Beschlussvorlage",
             "office": "Stadtplanung", "proposed_decision": "Der Rat beschließt …",
             "financial_impact": "Kosten: 1,2 Mio Euro", "climate_impact": None,
             "raw_text": "Briefkopf. Sachverhalt: 8,6 Hektar, davon 3,9 im "
                         "Landschaftsschutzgebiet."}
    anlagen = [{"label": "Antrag der SPD", "is_motion": 1, "applicants": "SPD-Fraktion",
                "raw_text": "Wir beantragen 110 Wohneinheiten."}]
    ktx, source = social_text.kontext(punkt, anlagen)

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
    assert source == "template+attachments"


def test_kontext_meldet_ehrlich_wenn_nur_der_titel_da_ist():
    """``source`` beantwortet später die Frage, warum ein Text dünn ist."""
    ktx, source = social_text.kontext(
        {"committee": "Rat", "session_date": "2026-08-31", "title": "Irgendein Punkt"}, [])
    assert source == "title"
    assert "Irgendein Punkt" in ktx


def test_grosse_anlagen_verdraengen_die_argumente_nicht():
    """Der „Materialband Lupenpläne" dieser Woche hat 400.000 Zeichen und ist
    als OCR-Text eine Kartensammlung. Der Antrag daneben hat 3.000 und sagt,
    was jemand will — er muss im Budget landen, nicht das Planwerk."""
    punkt = {"committee": "Rat", "session_date": "2026-08-31", "title": "Innenentwicklung",
             "raw_text": "Sachverhalt: kurz."}
    # Reihenfolge wie aus ``anlagen_fuer``: Anträge zuerst.
    anlagen = [{"label": "Antrag", "is_motion": 1, "applicants": "CDU",
                "raw_text": "Kernforderung: mehr Innenentwicklung."},
               {"label": "Materialband", "is_motion": 0, "applicants": None,
                "raw_text": "Planwerk " * 100_000}]
    ktx, _ = social_text.kontext(punkt, anlagen)

    assert "Kernforderung: mehr Innenentwicklung." in ktx
    assert len(ktx) <= social_text.VORLAGE_ZEICHEN + social_text.ANLAGEN_ZEICHEN + 2000


def test_jeder_inhaltliche_punkt_bekommt_einen_text(store):
    """Seit 30.08.26 gilt nicht mehr die Karten-Auswahl, sondern die
    Tagesordnung: Im Web wird sie ganz gelesen, und unter den Punkten jenseits
    der Top 20 stand die titelbasierte Kurzfassung oder gar nichts (Tims
    Entscheidung). Die Tragweite sortiert nur noch."""
    _sitzung(store)
    _punkt(store, nummer="Ö 10", impact=75)
    _punkt(store, nummer="Ö 11", title="Ein Punkt mit wenig Tragweite", impact=10)
    _punkt(store, nummer="Ö 12", title="Noch ohne Bewertung", impact=None)

    offen = store.agenda_items_needing_social_text()
    assert [p["item_number"] for p in offen] == ["Ö 10", "Ö 11", "Ö 12"], \
        "hoch bewertet zuerst, Unbewertetes zuletzt — aber alle drei"

    # Geschriebenes wird nie erneut bezahlt — sobald BEIDES da ist, Text und
    # Überschrift (s. test_offen_ist_auch_was_noch_keine_ueberschrift_hat).
    store.save_social_text(1, "Ö 10", "Zur Abstimmung steht …", "vorlage",
                           headline="Bürgschaft fürs Klinikum")
    assert [p["item_number"] for p in store.agenda_items_needing_social_text()] \
        == ["Ö 11", "Ö 12"]


def test_formalien_und_materiallose_punkte_kosten_nichts(store):
    """Zwei Grenzen bleiben. „Genehmigung der Tagesordnung" braucht keinen
    Satz — und ein Punkt ohne Vorlage und ohne Anlage hat nichts, was die
    Kurzfassung nicht schon aus dem Titel hätte."""
    _sitzung(store)
    _punkt(store, nummer="Ö 1", title="Genehmigung der Tagesordnung", impact=5)
    _punkt(store, nummer="Ö 2", title="Einwohnerfragestunde", impact=5)
    _punkt(store, nummer="Ö 3", title="Bericht ohne jede Vorlage dazu",
           impact=50, vorlage=False)
    _punkt(store, nummer="Ö 4", title="Ausfallbürgschaft für das Klinikum", impact=50)

    assert [p["item_number"] for p in store.agenda_items_needing_social_text()] == ["Ö 4"]


def test_dringlichkeitsantrag_kommt_ueber_seine_anlage_hinein(store):
    """Er hat keine Vorlage — sein ganzer Inhalt steht im PDF an der Zeile.
    Ohne diesen Weg fiele er durch die Material-Prüfung."""
    _sitzung(store)
    _punkt(store, nummer="DZT 1", title="Dringlichkeitsantrag: PAK-Belastung",
           impact=65, vorlage=False)
    store._conn.execute(
        "INSERT INTO council_agenda_attachments (ksinr, item_number, label, url, raw_text) "
        "VALUES (1, 'DZT 1', 'Dringlichkeitsantrag PAK', 'https://example.org/a.pdf', ?)",
        ("Die Gruppe beantragt eine sofortige Prüfung der Flugplatzbäke.",))
    store._conn.commit()

    offen = store.agenda_items_needing_social_text()
    assert [p["item_number"] for p in offen] == ["DZT 1"]
    assert offen[0]["anlage_text"].startswith("Die Gruppe beantragt")


def test_vergangene_sitzungen_bleiben_draussen(store):
    """Der Text steht in einer VORSCHAU."""
    _sitzung(store, ksinr=2, tage=-3)
    _punkt(store, ksinr=2, impact=90)
    assert store.agenda_items_needing_social_text(mindest_wichtig=40) == []


def test_wochenvorschau_reicht_den_kartentext_durch(store):
    """Der Bot liest ihn über /api/social/week-preview — er muss also im
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

    punkte = store.wochenvorschau(tage=10, max_punkte=40)["items"]
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

    text, _, ueberschrift = social_text.text_fuer(
        {"committee": "Rat", "session_date": "2026-08-31", "title": "Ein Punkt"}, [])
    assert len(text) <= social_text.MAX_ZEICHEN
    # Ohne Überschrift in der Antwort bleibt der Text trotzdem stehen — auf
    # der Karte steht dann der amtliche Titel.
    assert ueberschrift is None


def test_ueberschrift_kommt_bereinigt_mit(monkeypatch):
    """Die Überschrift sagt, worum es geht — der amtliche Titel sagt oft nur,
    wer wann eingereicht hat („Änderungsantrag der CDU-Fraktion vom
    10.06.2026", Tims Befund 05.09.26). Das Modell schreibt gern einen Punkt
    ans Ende und Anführungszeichen drumherum; beides ist kein Titel."""
    class _Antwort:
        def __init__(self, inhalt):
            self.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]

    monkeypatch.setattr(social_text.llm, "chat_complete", lambda **kw: _Antwort(
        '{"headline": "„Baumschutzsatzung bis Jahresende aussetzen.", '
        '"text": "Die CDU beantragt, die Satzung bis 31. Dezember 2026 auszusetzen."}'))
    monkeypatch.setattr(social_text.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(social_text.prompts, "render", lambda *a, **k: "user")
    monkeypatch.setattr(social_text.kritiker, "pruefe_llm", lambda text, source: (True, ""))

    punkt = {"committee": "Ausschuss für Stadtgrün, Umwelt und Klima",
             "session_date": "2026-09-10",
             "title": "Änderungsantrag der CDU-Fraktion vom 10.06.2026",
             "raw_text": "Sachverhalt: Aussetzung der Baumschutzsatzung bis 31. Dezember 2026."}
    text, _, ueberschrift = social_text.text_fuer(punkt, [])
    assert ueberschrift == "Baumschutzsatzung bis Jahresende aussetzen"
    assert text.startswith("Die CDU beantragt")


def test_ueberschrift_haelt_dieselben_regeln_wie_der_text():
    """Dieselben Netze wie beim Satz — und die eigene Länge. Fällt sie durch,
    fällt nur SIE: Der Text bleibt, die Karte zeigt den amtlichen Titel."""
    quelle = "Sachverhalt: 400 Euro je Baum."
    assert social_text.ueberschrift_pruefen("400 Euro Ausgleich je Baum", quelle) \
        == ("400 Euro Ausgleich je Baum", None)
    # Erfundene Zahl, Wertung, vorweggenommenes Ergebnis, Länge, leer.
    assert social_text.ueberschrift_pruefen("500 Euro je Baum", quelle)[0] is None
    assert social_text.ueberschrift_pruefen("Wichtige Baumschutz-Reform", quelle)[0] is None
    assert social_text.ueberschrift_pruefen("Rat beschließt neue Satzung", quelle)[0] is None
    zu_lang, mangel = social_text.ueberschrift_pruefen("Ein Wort " * 20, quelle)
    assert zu_lang is None and "zu lang" in mangel
    assert social_text.ueberschrift_pruefen(None, quelle) == (None, "leer")


def test_offen_ist_auch_was_noch_keine_ueberschrift_hat(store):
    """Zeilen von vor 09/2026 haben einen Text, aber keine Überschrift. Der
    Nachtlauf holt sie nach — und schreibt dabei beides neu, weil beides in
    einem Aufruf entsteht."""
    _sitzung(store)
    _punkt(store, nummer="Ö 10", impact=75)
    store.save_social_text(1, "Ö 10", "Zur Abstimmung steht …", "template")
    assert [p["item_number"] for p in store.agenda_items_needing_social_text()] == ["Ö 10"]
    store.save_social_text(1, "Ö 10", "Zur Abstimmung steht …", "template",
                           headline="Bürgschaft fürs Klinikum")
    assert store.agenda_items_needing_social_text() == []


def test_auch_die_restliste_traegt_den_kartentext(store):
    """Die zweite Karte einer Sitzung wird aus ``further_per_session`` gebaut.

    Diese Liste entsteht Feld für Feld — und genau dort fehlte der neue
    Kartentext: Der Dringlichkeitsantrag zur PAK-Belastung stand auf der
    Karte, darunter nichts (Tims Befund 30.08.26). Dieselbe Falle hatte am
    19.08.26 schon die Kurzfassung erwischt.
    """
    _sitzung(store)
    # Vier Punkte: Die Wochenvorschau zeigt drei, der vierte landet in der
    # Restliste — und muss seinen Text behalten.
    for i, nr in enumerate(("Ö 1", "Ö 2", "Ö 3", "Ö 4")):
        _punkt(store, nummer=nr, title=f"Ein inhaltlicher Punkt Nummer {i}",
               impact=90 - i)
        store.save_social_text(1, nr, f"Kartentext zu Punkt {i}.", "vorlage")

    daten = store.wochenvorschau(tage=10, max_punkte=40)
    assert all(p["social_text"] for p in daten["items"])
    rest = daten["further_per_session"][1]
    assert rest, "kein Punkt in der Restliste — Test prüft nichts"
    assert all(p["social_text"] for p in rest)


def test_gekuerzt_wird_am_satz_nicht_im_wort():
    """``text[:240]`` endete mitten im Wort: „… als nach der Baumschutzsatzun"
    (Kompensations-Punkt des Rats vom 31.08.26). Auf einer Karte fiel das nicht
    auf — in der Tagesordnung und in der Mail steht es so da."""
    from council.social_text import MAX_ZEICHEN, kuerzen

    lang = ("Zur Abstimmung steht, bei städtischen Bau- und Infrastrukturprojekten "
            "das verlorene Kronenvolumen binnen zehn Jahren nach dem "
            "Kronenvolumen-Modell auszugleichen. Die Kosten können drei- bis "
            "viermal höher liegen als nach der Baumschutzsatzung.")
    gekuerzt = kuerzen(lang)
    assert len(gekuerzt) <= MAX_ZEICHEN
    assert gekuerzt.endswith("auszugleichen.")

    # Was passt, bleibt unangetastet.
    assert kuerzen("Ein kurzer Satz.") == "Ein kurzer Satz."


def test_abkuerzungen_beenden_keinen_satz():
    """„ca." ist kein Satzende — sonst bliebe von einem 240-Zeichen-Text der
    Anfang „Beantragt sind ca." übrig (dieselbe Falle wie im Bild-Kanal)."""
    from council.social_text import kuerzen

    text = ("Beantragt sind ca. 13,5 Millionen Euro für ein Darlehen der Stadt an das "
            "Klinikum Oldenburg, das damit den Neubau finanziert und die Liquidität "
            "sichert, weil die Bank ohne Bürgschaft nicht zeichnet und der Betrieb "
            "des Krankenhauses sonst gefährdet wäre.")
    gekuerzt = kuerzen(text)
    assert gekuerzt.startswith("Beantragt sind ca. 13,5 Millionen Euro für ein Darlehen")
    assert gekuerzt.endswith(" …")
    # Kein zerschnittenes Wort am Ende.
    assert not gekuerzt.removesuffix(" …").endswith(("zeichne", "Betrie"))
