"""Dringlichkeitsanträge werden ein eigener Punkt.

Die Labels in diesen Tests sind ECHT — erhoben an 40 Ratssitzungen von Juli
2022 bis August 2026. Zwölf davon hatten einen Dringlichkeitsantrag (30 %),
elfmal als Dokument an „Ö 2 Genehmigung der Tagesordnung".
"""
from __future__ import annotations

import pytest

from council import dringlichkeit
from council.dringlichkeit import titel_aus_label, zusatz_punkte
from council.scraper import AgendaItem


@pytest.fixture(autouse=True)
def ohne_netz(monkeypatch):
    """Kein Test lädt ein PDF. Was der Griff ins Netz bringt, prüft
    test_das_pdf_wandert_in_die_bewertung mit gesetztem Text."""
    monkeypatch.setattr(dringlichkeit, "_pdf_text_leise", lambda url: "")


def _formalie(anlagen):
    return AgendaItem(item_number="Ö 2",
                      title="Genehmigung der Tagesordnung (öffentlicher Teil)",
                      anlagen=anlagen)


def test_titel_aus_den_echten_labels():
    """Die Labels sind uneinheitlich — Datumsstempel vorn, Sitzungsdatum
    hinten, mal „Antrag Dringlichkeit", mal „Dringlichkeitsantrag"."""
    assert titel_aus_label("Dringlichkeitsantrag festegestellte PAK Belastung 31.08.2026") \
        == "Dringlichkeitsantrag: festgestellte PAK-Belastung"
    assert titel_aus_label("250523 Antrag Dringlichkeit Fliegerhorst-Fraktionen") \
        == "Dringlichkeitsantrag: Fliegerhorst-Fraktionen"
    assert titel_aus_label("TV Dringlichkeitsantrag  Resolution Iran") \
        == "Dringlichkeitsantrag: Resolution Iran"
    assert titel_aus_label("Dringlichkeitsantrag CDU Anwohnerparken") \
        == "Dringlichkeitsantrag: CDU Anwohnerparken"
    assert titel_aus_label("2025-09-04 Dringlichkeitsantrag Schutz der Platanen") \
        == "Dringlichkeitsantrag: Schutz der Platanen"


def test_label_ohne_thema_erfindet_keines():
    """Am 15.04.2024 hieß das Dokument schlicht „Dringlichkeitsantrag". Eine
    ehrliche Zeile ohne Thema ist besser als ein erfundenes."""
    assert titel_aus_label("Dringlichkeitsantrag") == "Dringlichkeitsantrag"
    assert titel_aus_label("") == "Dringlichkeitsantrag"


def test_dokument_an_der_formalie_wird_ein_punkt():
    anlage = {"label": "Dringlichkeitsantrag Rat Lachgas",
              "url": "https://buergerinfo.oldenburg.de/getfile.php?id=1&type=do"}
    neu = zusatz_punkte([_formalie([anlage])])

    assert len(neu) == 1
    assert neu[0].title == "Dringlichkeitsantrag: Rat Lachgas"
    # Keine Ö-Nummer: Der Punkt ist abgeleitet, nicht amtlich — das soll man
    # ihm ansehen. „DZT" ist die Marke des Ratsinformationssystems selbst.
    assert neu[0].item_number == "DZT 1"
    # Das Dokument reist mit, sonst fänden Bewertung und Kartentext das PDF
    # nicht — samt Platz für seinen Text.
    assert neu[0].anlagen[0]["url"] == anlage["url"]
    assert neu[0].anlagen[0]["label"] == anlage["label"]
    assert "raw_text" in neu[0].anlagen[0]


def test_an_einem_inhaltlichen_punkt_entsteht_nichts():
    """Hängt der Antrag an einem echten Thema, ist dieses Thema längst
    sichtbar — ein zweiter Punkt wäre dieselbe Sache doppelt (kam am
    17.03.2025 und am 26.06.2025 vor)."""
    anlage = {"label": "250303 Dringlichkeitsantrag Fliegerhorst", "url": "x"}
    inhaltlich = AgendaItem(item_number="Ö 10.4",
                            title="Illegal entsorgtes, belastetes Abbruchmaterial",
                            anlagen=[anlage])
    assert zusatz_punkte([inhaltlich]) == []


def test_andere_anlagen_an_der_formalie_bleiben_liegen():
    """Nur „Dringlichkeit" macht einen Punkt — nicht jedes Dokument an Ö 2."""
    assert zusatz_punkte([_formalie([{"label": "Anlage", "url": "x"},
                                     {"label": "Tagesordnung", "url": "y"}])]) == []


def test_zwei_antraege_bekommen_zwei_nummern():
    neu = zusatz_punkte([_formalie([
        {"label": "Dringlichkeitsantrag Lachgas", "url": "a"},
        {"label": "Dringlichkeitsantrag Platanen", "url": "b"}])])
    assert [p.item_number for p in neu] == ["DZT 1", "DZT 2"]


def test_der_punkt_ueberlebt_die_wochenvorschau(tmp_path):
    """Der ganze Weg: Ein DZT-Punkt darf nicht als Formalie oder als
    Unterpunkt der Formalie wieder herausfliegen.

    Die Rang-Schwelle gilt für ihn wie für jeden anderen Punkt — er bekommt
    also eine Tragweite wie alle. Genau das ist der Sinn der Übung: Er soll
    nicht bevorzugt werden, sondern überhaupt erst bewertet werden können.
    """
    from datetime import date, timedelta

    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        tag = (date.today() + timedelta(days=3)).isoformat()
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, "
            "session_time, location, fetched_at) VALUES (1, 'Rat', ?, '18:00', 'PFL', 'x')",
            (tag,))
        for nr, title in (("Ö 2", "Genehmigung der Tagesordnung (öffentlicher Teil)"),
                          ("DZT 1", "Dringlichkeitsantrag: festegestellte PAK Belastung"),
                          ("Ö 9.1", "Sachlicher Teilflächennutzungsplan Windenergie")):
            store._conn.execute(
                "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
                "VALUES (1, ?, ?, 1)", (nr, title))
        for nr, value in (("DZT 1", 70), ("Ö 9.1", 85)):
            store._conn.execute(
                "INSERT INTO agenda_item_impact (ksinr, item_number, impact, reason, "
                "created_at) VALUES (1, ?, ?, 'Grund', 'x')", (nr, value))
        store._conn.commit()

        punkte = store.wochenvorschau(tage=10, max_punkte=40)["items"]
        nummern = [p["item_number"] for p in punkte]
        assert "DZT 1" in nummern
        assert "Ö 2" not in nummern            # die Formalie bleibt draußen
        dzt = next(p for p in punkte if p["item_number"] == "DZT 1")
        assert dzt["title"].startswith("Dringlichkeitsantrag:")
    finally:
        store.close()

    # Auch OHNE LLM-Bewertung steht er da: Der Boden greift lesezeitig
    # (Tims Entscheidung 30.08.26). Ein gewöhnlicher unbewerteter Punkt
    # bleibt dagegen draußen — der Boden gilt nur für Dringlichkeitsanträge.
    store2 = CouncilStore(tmp_path / "ohne.sqlite")
    try:
        tag = (date.today() + timedelta(days=3)).isoformat()
        store2._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, "
            "session_time, location, fetched_at) VALUES (1, 'Rat', ?, '18:00', 'PFL', 'x')",
            (tag,))
        for nr, title in (("DZT 1", "Dringlichkeitsantrag: Lachgas"),
                          ("Ö 7", "Bericht über den Stand der Digitalisierung")):
            store2._conn.execute(
                "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
                "VALUES (1, ?, ?, 1)", (nr, title))
        store2._conn.commit()
        nummern = [p["item_number"]
                   for p in store2.wochenvorschau(tage=10, max_punkte=40)["items"]]
        assert nummern == ["DZT 1"]
    finally:
        store2.close()


def test_das_pdf_wandert_in_die_bewertung(tmp_path, monkeypatch):
    """Der Kern der Sache: Bewertung und Kartentext sehen DASSELBE.

    Vorher las nur der Kartentext das PDF; die Tragweite bewertete den
    Dateinamen und gab dem PAK-Antrag 55 von 100 — Platz 8 von 17, an den
    Karten vorbei. Im PDF stand eine Schadstoffbelastung eines Gewässers.
    """
    from datetime import date, timedelta

    from council import dringlichkeit
    from council.scraper import CouncilSession
    from council.store import CouncilStore

    monkeypatch.setattr(dringlichkeit, "_pdf_text_leise",
                        lambda url: "Die Gruppe beantragt eine sofortige Prüfung der "
                                    "PAK-Belastung in der Flugplatzbäke.")
    anlage = {"label": "Dringlichkeitsantrag PAK", "url": "https://example.org/x.pdf"}
    zusatz = dringlichkeit.zusatz_punkte([_formalie([anlage])])

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        tag = (date.today() + timedelta(days=3)).isoformat()
        store.save_session(CouncilSession(
            ksinr=1, committee="Rat", session_date=tag, session_time="18:00",
            location="PFL", agenda_items=[_formalie([anlage]), *zusatz]))

        gespeichert = store._conn.execute(
            "SELECT raw_text FROM council_agenda_attachments WHERE item_number = 'DZT 1'"
        ).fetchone()[0]
        assert "Flugplatzbäke" in gespeichert

        # Und die Bewertung findet ihn als „sachverhalt" — ohne Vorlage.
        offen = store.agenda_items_needing_impact()
        dzt = next(p for p in offen if p["item_number"] == "DZT 1")
        assert "Flugplatzbäke" in (dzt["sachverhalt"] or "")
    finally:
        store.close()


def test_der_boden_hebt_an_ohne_zu_senken():
    """Die Rubrik misst Tragweite, nicht Aktualität. Ein Boden gleicht das
    aus — und ein Boden ist keine Addition: Er hebt eine zu niedrige
    Bewertung an und lässt eine hohe in Ruhe."""
    from council.impact import DRINGLICHKEIT_MIN, dringlichkeits_boden

    assert dringlichkeits_boden("DZT 1") == DRINGLICHKEIT_MIN
    assert dringlichkeits_boden("DZT 2") == DRINGLICHKEIT_MIN
    # Gewöhnliche Punkte fasst er nicht an — auch nicht, wenn „Dringlichkeit"
    # im Titel steht; erkannt wird an der Kennung, nicht am Wortlaut.
    assert dringlichkeits_boden("Ö 10.4") is None
    assert dringlichkeits_boden(None) is None


def test_der_boden_wirkt_in_der_wochenvorschau(tmp_path):
    """Der ganze Weg: Ein mit 55 bewerteter Antrag steht mit 65 in der
    Vorschau — genau der Fall vom 31.08.2026 (PAK-Belastung, Platz 8 von 17
    Ratspunkten und damit an den Karten vorbei)."""
    from datetime import date, timedelta

    from council.impact import DRINGLICHKEIT_MIN
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        tag = (date.today() + timedelta(days=3)).isoformat()
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, "
            "session_time, location, fetched_at) VALUES (1, 'Rat', ?, '18:00', 'PFL', 'x')",
            (tag,))
        for nr, title, value in (
                ("DZT 1", "Dringlichkeitsantrag: festegestellte PAK Belastung", 55),
                ("DZT 2", "Dringlichkeitsantrag: Resolution Iran", 80),
                ("Ö 9.1", "Sachlicher Teilflächennutzungsplan Windenergie", 85)):
            store._conn.execute(
                "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
                "VALUES (1, ?, ?, 1)", (nr, title))
            store._conn.execute(
                "INSERT INTO agenda_item_impact (ksinr, item_number, impact, reason, "
                "created_at) VALUES (1, ?, ?, 'Ein Grund', 'x')", (nr, value))
        store._conn.commit()

        nach_nr = {p["item_number"]: p
                   for p in store.wochenvorschau(tage=10, max_punkte=40)["items"]}
        assert nach_nr["DZT 1"]["wichtig"] == DRINGLICHKEIT_MIN     # 55 → 65
        assert nach_nr["DZT 2"]["wichtig"] == 80                    # bleibt oben
        assert nach_nr["Ö 9.1"]["wichtig"] == 85                    # unberührt
        # Die Begründung des Modells bleibt stehen — sie war richtig, sie wog
        # nur die Kurzfristigkeit nicht mit.
        assert nach_nr["DZT 1"]["wichtig_grund"] == "Ein Grund"
    finally:
        store.close()


def test_tippfehler_der_stadt_werden_geglaettet():
    """Der Titel kommt aus einem Dateinamen, und der ist getippt wie jeder
    andere auch: „festegestellte" (Antrag vom 31.08.2026). Tims Vorgabe
    30.08.26: auch die Fehler der Stadt korrigieren.

    Korrigiert wird nur, was zweifelsfrei ein Verschreiber ist — der Titel
    wird nicht umformuliert. Wer den Antrag im Ratsinformationssystem sucht,
    findet ihn über den Link der Anlage, nicht über diese Zeile.
    """
    assert titel_aus_label("Dringlichkeitsantrag festegestellte PAK Belastung") \
        == "Dringlichkeitsantrag: festgestellte PAK-Belastung"
    # Abkürzung + Grundwort wird zum Kompositum: „PAK Belastung" ist eines.
    assert titel_aus_label("Dringlichkeitsantrag PFAS Werte") \
        == "Dringlichkeitsantrag: PFAS-Werte"


def test_parteikuerzel_bleiben_ein_eigenes_wort():
    """„CDU Anwohnerparken" sagt, WER den Antrag stellt, nicht worum es geht.
    Ein Bindestrich machte daraus ein Kompositum, das es nicht gibt."""
    assert titel_aus_label("Dringlichkeitsantrag CDU Anwohnerparken") \
        == "Dringlichkeitsantrag: CDU Anwohnerparken"
    assert titel_aus_label("Dringlichkeitsantrag SPD Radwege") \
        == "Dringlichkeitsantrag: SPD Radwege"


def test_die_sitzungsansicht_erkennt_den_antrag_und_traegt_den_kartentext(tmp_path):
    """Was die Tagesordnung im Web zeigt, entscheidet der Server.

    Zwei Felder je Punkt: ``dringlich`` (damit Web UND App denselben Punkt
    hervorheben, statt jede Oberfläche die Kennung selbst zu deuten) und
    ``social_text`` (der Satz aus Vorlage und Anlagen — die Anzeige zieht ihn
    der titelbasierten Kurzfassung vor).
    """
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (1, 'Rat', '2026-08-31', '18:00', 'PFL', 'x')")
        store._conn.executemany(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
            "VALUES (1, ?, ?, 1)",
            [("Ö 2", "Genehmigung der Tagesordnung"),
             ("DZT 1", "Dringlichkeitsantrag: festgestellte PAK-Belastung")])
        store._conn.execute(
            "INSERT INTO agenda_item_summaries (ksinr, item_number, summary, agenda_hash, "
            "created_at) VALUES (1, 'DZT 1', 'Der Rat berät über einen Antrag.', 'h', 'x')")
        store._conn.commit()
        store.save_social_text(1, "DZT 1", "Beantragt ist, die PAK-Belastung der "
                                           "Flugplatzbäke untersuchen zu lassen.", "anlage")

        nach_nr = {i["item_number"]: i for i in store.agenda_items(1)}
        assert nach_nr["DZT 1"]["dringlich"] is True
        assert nach_nr["Ö 2"]["dringlich"] is False
        assert nach_nr["DZT 1"]["social_text"].startswith("Beantragt ist")
        # Die Kurzfassung bleibt daneben stehen — sie ist der Rückfall, nicht
        # ersetzt: Für Punkte ohne Kartentext ist sie alles, was es gibt.
        assert nach_nr["DZT 1"]["summary"] == "Der Rat berät über einen Antrag."
        assert nach_nr["Ö 2"]["social_text"] is None
    finally:
        store.close()
