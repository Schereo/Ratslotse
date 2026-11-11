"""„Kurs der Sitzung" — Etappen, Art, Piktogramm, wichtig, vertagt.

Plan: ``docs/plan-sitzungsseite-kurs.md``, Schritt 1. Die Regeln stehen in
``council/course.py``, die Datenbank fasst ``CouncilStore.session_course`` an.

Die vier Tagesordnungen unten sind ECHT (Abzug von dev, 08.11.2026) — genau
die, nach denen der Entwurf gezeichnet ist: Verkehrsausschuss 08.06.2026
(4652, „nach der Sitzung") und 21.09.2026 (4654, „vor der Sitzung"),
Sportausschuss 07.10.2026 (4593, „wenige Punkte"), Rat 31.08.2026 (4702,
„viele Punkte"). Ausgedachte Tagesordnungen hätten die Fälle nicht, an denen
die Regeln hängen: Protokolle mit Unterpunkten, „beratendes Mitglied Herr …"
statt einer Fraktion, Ausschuss-Abschnitte im Rat, ein Dringlichkeitsantrag
hinter dem nichtöffentlichen Teil.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_type_hints

import pytest

from council import course
from council.store import CouncilStore

WURZEL = Path(__file__).resolve().parents[1]

# (Nummer, Titel, Vorlage, Vorlagenart, öffentlich, Behandlung an dem Tag)
SITZUNGEN = {
    4652: ('Verkehrsausschuss', '2026-06-08', '17:03', [
        ('Ö 1', 'Feststellung der Beschlussfähigkeit', None, None, 1, None),
        ('Ö 2', 'Genehmigung der Tagesordnung (öffentlicher Teil)', None, None, 1, None),
        ('Ö 3', 'Genehmigung des Protokolls Nr. 04/26 (öffentlicher Teil) vom 11.05.2026', None, None, 1, None),
        ('Ö 4', 'Einwohnerfragestunde', None, None, 1, None),
        ('Ö 5', 'Untere Nadorster Straße - Bericht zur Baumbesichtigung', '26/0442', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 6', 'Verkehr und Wasser GmbH (VWG): Technologieentscheidung im Rahmen der Antriebswende - Beschluss', '26/0414', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 7', 'Teileinziehung der Straße "Junkerstraße" - Beschluss', '26/0426', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 8', 'Umgestaltung des Oldenburger Bahnhofsvorplatzes - Beschluss', '26/0445', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 9', 'Umgestaltung des Uhlhornsweg im Bereich der Universität - Beschluss', '26/0454', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 10', 'Widmung "Hannah-Arendt-Straße" - Beschluss', '26/0427', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 11', 'Widmung "Dr.-Hans-Klüber-Straße" -Beschluss', '26/0428', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 12', 'Straßenbenennung "Hahnenkampsmoor" - Beschluss', '26/0434', 'Beschlussvorlage', 1, 'Vorberatung'),
        ('Ö 13', 'Straßenbenennungen in der Stadt Oldenburg - Bericht', '26/0052', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 14', 'Fußgängerbrücke Krusenbusch (Variantenuntersuchung) - Bericht', '26/0429', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 15', 'Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder', None, None, 1, None),
        ('Ö 15.1', 'Umsetzung der Pflasterung am Rathausmarkt und Julius-Mosen-Platz (SPD-Fraktion vom 11.03.2026) - Beschlussantrag', '26/0329', 'Berichtsvorlage', 1, 'Vorberatung'),
        ('Ö 15.2', 'Bahnübergang Am Stadtrand - Planungsalternative (beratendes Mitglied Herr Pieper vom 20.05.2026) - Berichtsantrag', None, None, 1, None),
        ('Ö 15.3', 'Weißenmoorstraße (beratendes Mitglied Herr Pieper vom 22.05.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 15.4', 'Verkehrsunfall mit Radfahrer (beratendes Mitglied Herr Pieper vom 02.06.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 16', 'Anfragen und Anregungen', None, None, 1, None),
        ('N 17', 'gesperrte Information', None, None, 0, None),
        ('N 18', 'gesperrte Information', None, None, 0, None),
        ('N 19', 'gesperrte Information', None, None, 0, None),
        ('N 19.1', 'gesperrte Information', None, None, 0, None),
        ('N 20', 'gesperrte Information', None, None, 0, None),
    ]),
    4654: ('Verkehrsausschuss', '2026-09-21', '17:00', [
        ('Ö 1', 'Feststellung der Beschlussfähigkeit', None, None, 1, None),
        ('Ö 2', 'Genehmigung der Tagesordnung (öffentlicher Teil)', None, None, 1, None),
        ('Ö 3', 'Genehmigung der Protokolle (öffentlicher Teil)', None, None, 1, None),
        ('Ö 3.1', 'Genehmigung des Protokolls Nr. 05/26 (öffentlicher Teil) vom 08.06.2026', None, None, 1, None),
        ('Ö 3.2', 'Genehmigung des Protokolls Nr. 06/26 (öffentlicher Teil) vom 24.08.2026', None, None, 1, None),
        ('Ö 4', 'Einwohnerfragestunde', None, None, 1, None),
        ('Ö 5', 'Widmung der Straße "Pellwormer Weg" - Beschluss', '26/0654', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 6', 'Widmung "Fuß- und Radweg am Pophankenweg" - Beschluss', '26/0673', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 7', 'Widmung der Straße "Am Pulverturm" - Beschluss', '26/0689', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 8', 'Markierung von Radverkehrsanlagen in der Kreyenstraße - Bericht', '26/0562', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 9', 'Soziales D-Ticket in Oldenburg - Bericht', '26/0719', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 10', 'Geschwindigkeitsmessung - Gegenüberstellung der Messgeräte: Telraam vs. geeichte Geräte - Bericht', '26/0720', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 11', 'Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder', None, None, 1, None),
        ('Ö 11.1', 'Weißenmoorstraße (beratendes Mitglied Herr Pieper vom 22.05.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 11.2', 'Parken auf Sicherheitstrennstreifen zwischen Parkständen und Radwegen (beratendes Mitglied Herrn Lüdke vom 08.08.2026) - Beschlussantrag mit Bericht der Verwaltung', '26/0658', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 11.3', 'Anschluss der oldenburgischen, verkehrsrechtlichen Ausnahmegenehmigung für Handwerksbetriebe an den Handwerkerparkausweis des Kommunalverbunds Niedersachsen-Bremen (FDP-Fraktion vom 07.09.2026) - Beschlussantrag mit Bericht der Verwaltung', '26/0745', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 12', 'Anfragen und Anregungen', None, None, 1, None),
        ('N 13', 'gesperrte Information', None, None, 0, None),
        ('N 14', 'gesperrte Information', None, None, 0, None),
        ('N 14.1', 'gesperrte Information', None, None, 0, None),
        ('N 14.2', 'gesperrte Information', None, None, 0, None),
        ('N 15', 'gesperrte Information', None, None, 0, None),
    ]),
    4593: ('Sportausschuss', '2026-10-07', '17:00', [
        ('Ö 1', 'Feststellung der Beschlussfähigkeit', None, None, 1, None),
        ('Ö 2', 'Genehmigung der Tagesordnung (öffentlicher Teil)', None, None, 1, None),
        ('Ö 3', 'Genehmigung des Protokolls Nr. 05/26 (öffentlicher Teil) vom 09.09.2026', None, None, 1, None),
        ('Ö 4', 'Einwohnerfragestunde', None, None, 1, None),
        ('Ö 5', 'Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder', None, None, 1, None),
        ('Ö 5.1', 'Zweifeldausbau Hundsmühler Höhe (CDU-Fraktion vom 03.07.2026) - Berichtsantrag', '26/0755', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 5.2', 'Aktualisierung Sanierungsplan von Sportstätten in Oldenburg (Fraktion Bündnis 90/Die Grünen vom 08.09.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 6', 'Anfragen und Anregungen', None, None, 1, None),
        ('N 7', 'gesperrte Information', None, None, 0, None),
        ('N 8', 'gesperrte Information', None, None, 0, None),
        ('N 9', 'gesperrte Information', None, None, 0, None),
    ]),
    4702: ('Rat', '2026-08-31', '18:00', [
        ('Ö 1', 'Feststellung der Beschlussfähigkeit', None, None, 1, None),
        ('Ö 2', 'Genehmigung der Tagesordnung (öffentlicher Teil)', None, None, 1, None),
        ('Ö 3', 'Genehmigung des Protokolls Nr. 06/26 (öffentlicher Teil) vom 29.06.2026', None, None, 1, None),
        ('Ö 4', 'Mitteilungen des Oberbürgermeisters', None, None, 1, None),
        ('Ö 5', 'Einwohnerfragestunde', None, None, 1, None),
        ('Ö 6', 'Ausschuss für Stadtgrün, Umwelt und Klima vom 13.08.2026', None, None, 1, None),
        ('Ö 6.1', 'Kompensation bei städtischen Baumfällungen im Rahmen von Eingriffsvorhaben - Beschluss', '26/0446', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 6.2', 'Änderung der Richtlinie über die Gewährung von Zuschüssen für Regentonnen und Flächenentsiegelungen zur Starkregenvorsorge - Beschluss', '26/0644', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 7', 'Jugendhilfeausschuss vom 19.08.2026', None, None, 1, None),
        ('Ö 7.1', 'Berufung Beratendes Mitglied im Jugendhilfeausschuss – Vertreterin der Mädchenarbeit - Beschluss', '26/0551', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 7.2', 'Änderung der Satzung des Jugendamtes - Beschluss', '26/0539', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 8', 'Verkehrsausschuss vom 24.08.2026', None, None, 1, None),
        ('Ö 8.1', 'VBN-Tarifanpassung 2027 - Beschluss', '26/0622', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 8.2', 'Überarbeitung des städtischen Vorbehaltsnetzes - Beschluss', '26/0623', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9', 'Ausschuss für Stadtplanung und Bauen vom 27.08.2026', None, None, 1, None),
        ('Ö 9.1', 'Sachlicher Teilflächennutzungsplan Windenergie - Feststellungsbeschluss', '26/0583', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.2', 'Änderung 84 des Flächennutzungsplanes 1996 (nördlich Eßkamp/östlich Südbäke) - Prüfung der Abwägungsvorschläge - Feststellungsbeschluss', '26/0591', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.3', 'Bebauungsplan 837 (nördlich Eßkamp/östlich Südbäke) - Prüfung der Abwägungsvorschläge - Satzungsbeschluss', '26/0592', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.4', 'Verlängerung der Veränderungssperre 96 - (Vergnügungsstätten Nadorster Straße / Kreyenstraße) - Satzungsbeschluss', '26/0486', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.5', 'Verlängerung der Veränderungssperre 95 (Vergnügungsstätten Bürgerstraße/Donnerschweer Straße/Junkerstraße) - Satzungsbeschluss', '26/0491', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.6', 'Verlängerung der Veränderungssperre 94 (Vergnügungsstätten Bremer Heerstraße Mitte) - Satzungsbeschluss', '26/0490', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 9.7', 'Studie zur mehrfachen Innenentwicklung in der Stadt Oldenburg - Bericht', '26/0351/1', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 9.8', 'Bauvorhaben am Helmsweg / Storchweg - Anwendung des Bau-Turbo nach § 246e Baugesetzbuch - Beschluss', '26/0590', 'Beschlussvorlage', 1, 'Entscheidung'),
        ('Ö 10', 'Anträge der Fraktionen, Gruppen und Ratsmitglieder', None, None, 1, None),
        ('Ö 10.1', 'Umsetzung Aufwertung und Bewerbung von P + R Standorten (SPD-Fraktion vom 10.06.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 10.2', 'Änderung der Verkehrsführung Herbartstr./Cäcilienstr./Cäcilienplatz (Fraktion Bündnis 90/Die Grünen und Ratsherr Lükermann vom 10.08.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 10.3', 'Einführung einer Grundsteuer C zur Vermeidung von Bodenspekulation (BSW-Fraktion vom 11.08.2026) - Beschlussantrag mit Bericht der Verwaltung', '26/0666', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 10.4', 'Änderung der Geschäftsordnung: Transparente Dokumentation des Abstimmungsverhaltens bei Ratsbeschlüssen im Rats- und Bürgerinformationssystem (Gruppe für Oldenburg vom 17.08.2026) - Beschlussantrag mit Bericht der Verwaltung', '26/0679', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 10.5', 'Untersuchung einer festgestellten PAK-Belastung in der Flugplatzbäke im Bereich (Gruppe Für Oldenburg vom 27.08.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 10.6', 'Ermittlungen Abfallentsorgung Fliegerhorst (CDU-Fraktion vom 14.07.2026) - Beschlussantrag mit Bericht der Verwaltung', '26/0604', 'Berichtsvorlage', 1, 'Kenntnisnahme'),
        ('Ö 10.7', 'Umsetzung der Ratsbeschlüsse zum Fliegerhorst (FDP-Fraktion vom 28.07.2026) - Beschlussantrag', None, None, 1, None),
        ('Ö 11', 'Anfragen und Anregungen', None, None, 1, None),
        ('N 12', 'gesperrte Information', None, None, 0, None),
        ('N 13', 'gesperrte Information', None, None, 0, None),
        ('N 14', 'gesperrte Information', None, None, 0, None),
        ('N 14.1', 'gesperrte Information', None, None, 0, None),
        ('N 15', 'gesperrte Information', None, None, 0, None),
        ('DZT 1', 'Dringlichkeitsantrag: festgestellte PAK-Belastung', None, None, 1, None),
    ]),
}


def _store(tmp_path, ksinrs=(4652, 4654, 4593, 4702)) -> CouncilStore:
    store = CouncilStore(tmp_path / "kurs.sqlite")
    kvonr = 1000
    with store._conn:
        for ksinr in ksinrs:
            gremium, datum, zeit, punkte = SITZUNGEN[ksinr]
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
                "fetched_at) VALUES (?, ?, ?, ?, '', datetime('now'))", (ksinr, gremium, datum, zeit))
            for nr, titel, vorlage, art, oeff, behandlung in punkte:
                kv = None
                if vorlage:
                    kvonr += 1
                    kv = kvonr
                    store._conn.execute(
                        "INSERT INTO council_templates (kvonr, template_number, title, kind, fetched_at) "
                        "VALUES (?, ?, ?, ?, datetime('now'))", (kv, vorlage, titel, art))
                    if behandlung:
                        store._conn.execute(
                            "INSERT INTO council_deliberations (kvonr, date, committee, result, fetched_at) "
                            "VALUES (?, ?, ?, ?, datetime('now'))", (kv, datum, gremium, behandlung))
                store._conn.execute(
                    "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, kvonr, "
                    "is_public) VALUES (?, ?, ?, ?, ?, ?)", (ksinr, nr, titel, vorlage or "", kv, oeff))
    return store


@pytest.fixture
def store(tmp_path):
    s = _store(tmp_path)
    yield s
    s.close()


def _zellen(stufe: dict) -> list[str]:
    return [z["label"] for z in stufe["cells"]]


# ---- Etappen -------------------------------------------------------------

def test_vor_der_sitzung_wie_im_entwurf(store):
    """4654 ist die Sitzung, nach der „vor der Sitzung" gezeichnet ist. Jede
    Zahl hier steht so im Bild: „17 öffentlich · 5 nichtöffentlich", „3 von
    9", „Ö 1 – Ö 4 · 6 Punkte", „Ö 11 · 3 Anträge", „N 13–15"."""
    k = store.session_course(4654)
    assert (k["start"], k["public_count"], k["closed_count"], k["substantive_count"]) == ("17:00", 17, 5, 9)
    assert [s["kind"] for s in k["stages"]] == ["start", "content", "motions", "end", "closed"]
    start, inhalt, antraege, schluss, zu = k["stages"]
    assert (start["name"], start["name_short"], start["range"], start["count"]) == ("Zum Start", "Start", "Ö 1 – Ö 4", 6)
    # Die Formalien samt Protokoll-Unterpunkten sind EINE Boje.
    assert _zellen(start) == ["Ö 1–3", "Ö 4"]
    assert start["cells"][0]["title"] == "Formalien"
    assert start["cells"][0]["items"] == ["Ö 1", "Ö 2", "Ö 3", "Ö 3.1", "Ö 3.2"]
    assert (inhalt["name"], inhalt["name_short"], inhalt["range"], inhalt["count"]) == (
        "Beschlüsse und Berichte", "Beschlüsse", "Ö 5 – Ö 10", 6)
    assert (antraege["name"], antraege["range"], antraege["count"]) == ("Anträge", "Ö 11", 3)
    assert antraege["subtitle"] == "der Fraktionen, Gruppen, Rats- und Ausschussmitglieder"
    assert _zellen(antraege) == ["Ö 11.1", "Ö 11.2", "Ö 11.3"]
    assert _zellen(schluss) == ["Ö 12"]
    assert (zu["name"], zu["range"], zu["count"], _zellen(zu)) == (
        "Nichtöffentlicher Teil", "N 13 – N 15", 5, ["N 13–15"])
    assert zu["cells"][0]["items"] == []          # nichtöffentlich: keine Punkte, nur die Zahl
    # Überschriften und nichtöffentliche Zeilen sind keine Punkte des Kurses.
    assert "Ö 11" not in k["items"] and "N 13" not in k["items"]


def test_nach_der_sitzung_wie_im_entwurf(store):
    k = store.session_course(4652)
    assert (k["public_count"], k["closed_count"], k["substantive_count"]) == (20, 5, 14)
    assert [s["kind"] for s in k["stages"]] == ["start", "content", "motions", "end", "closed"]
    assert [s["count"] for s in k["stages"]] == [4, 10, 4, 1, 5]
    assert k["stages"][-1]["cells"][0]["label"] == "N 17–20"


def test_wenige_punkte_ohne_beschluesse_und_berichte(store):
    """Der Sportausschuss hat nur Anträge — eine leere Etappe gibt es nicht."""
    k = store.session_course(4593)
    assert [s["kind"] for s in k["stages"]] == ["start", "motions", "end", "closed"]
    assert k["substantive_count"] == 2
    assert k["stages"][-1]["cells"][0]["label"] == "N 7–9"


def test_rat_gliedert_nach_ausschuessen(store):
    """Im Rat eröffnet jeder Ausschuss-Abschnitt eine Etappe; der Dringlich-
    keitsantrag steht in der Tagesordnung HINTER dem nichtöffentlichen Teil,
    verhandelt wird er vorn."""
    k = store.session_course(4702)
    assert [s["kind"] for s in k["stages"]] == [
        "start", "urgent", "section", "section", "section", "section", "motions", "end", "closed"]
    assert _zellen(k["stages"][0]) == ["Ö 1–3", "Ö 4", "Ö 5"]
    assert _zellen(k["stages"][1]) == ["DZT 1"]
    abschnitte = [(s["name"], s["name_medium"], s["name_short"], s["count"]) for s in k["stages"][2:6]]
    assert abschnitte == [
        ("Stadtgrün & Klima", "Stadtgrün", "Grün", 2),
        ("Jugendhilfe", "Jugendhilfe", "Jugend", 2),
        ("Verkehr", "Verkehr", "Verkehr", 2),
        ("Stadtplanung & Bauen", "Stadtplanung", "Bauen", 8),
    ]
    assert k["stages"][2]["subtitle"] == "Ausschuss für Stadtgrün, Umwelt und Klima vom 13.08.2026"
    assert k["stages"][6]["count"] == 7
    assert k["stages"][-1]["cells"][0]["label"] == "N 12–15"
    dzt = k["items"]["DZT 1"]
    assert dzt["type"] == "motion" and dzt["short_title"] == "festgestellte PAK-Belastung"


def test_vorhaben_ist_eine_gruppe_keine_etappe(tmp_path):
    """„Bauleitplanung Meerweg" benennt ein Vorhaben. Der Bauausschuss vom
    27.08.2026 trug elf solche Überschriften — als Etappen wären es elf Bänder
    mit zwei Bojen geworden. Die Punkte bleiben im Inhalt und tragen die Gruppe."""
    SITZUNGEN[1] = ("Ausschuss für Stadtplanung und Bauen", "2026-08-27", "17:00", [
        ("Ö 1", "Feststellung der Beschlussfähigkeit", None, None, 1, None),
        ("Ö 2", "Bebauungsplan 847 (südlich Rohdenweg) - Beschluss zur Veröffentlichung des Entwurfs",
         "26/0593", "Beschlussvorlage", 1, "Entscheidung"),
        ("Ö 3", "Bauleitplanung Meerweg", None, None, 1, None),
        ("Ö 3.1", "Änderung 5 des Bebauungsplanes 534 (Meerweg) -Aufstellungsbeschluss",
         "26/0576", "Beschlussvorlage", 1, "Vorberatung"),
        ("Ö 3.2", "Änderung 5 des Bebauungsplanes 534 (Meerweg) - Grundzüge der Planung - Information",
         "26/0577", "Berichtsvorlage", 1, "Kenntnisnahme"),
        ("Ö 4", "Anfragen und Anregungen", None, None, 1, None),
    ])
    try:
        s = _store(tmp_path, ksinrs=(1,))
        k = s.session_course(1)
        s.close()
    finally:
        del SITZUNGEN[1]
    assert [st["kind"] for st in k["stages"]] == ["start", "content", "end"]
    assert _zellen(k["stages"][1]) == ["Ö 2", "Ö 3.1", "Ö 3.2"]
    assert k["items"]["Ö 3.1"]["group"] == "Ö 3" and k["items"]["Ö 2"]["group"] is None
    assert (k["items"]["Ö 3.1"]["type"], k["items"]["Ö 3.2"]["type"]) == ("preliminary", "report")


def test_unklare_tagesordnung_wird_eine_etappe():
    """Lieber schlicht als falsch gegliedert: Steht ein öffentlicher Punkt
    hinter dem nichtöffentlichen Teil, stimmt „Anker bis Schloss" nicht."""
    zeilen = [
        {"item_number": "Ö 1", "title": "Feststellung der Beschlussfähigkeit", "template_number": "", "is_public": 1},
        {"item_number": "N 2", "title": "gesperrte Information", "template_number": "", "is_public": 0},
        {"item_number": "Ö 3", "title": "Radweg am Ring - Bericht", "template_number": "26/1", "is_public": 1},
    ]
    stufen = course.build_stages(zeilen, set(), set())
    assert [s["kind"] for s in stufen] == ["agenda", "closed"]
    assert [z["label"] for z in stufen[0]["cells"]] == ["Ö 1", "Ö 3"]


def test_ohne_tagesordnung_kein_kurs(tmp_path):
    s = CouncilStore(tmp_path / "leer.sqlite")
    with s._conn:
        s._conn.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                        "location, fetched_at) VALUES (9, 'Rat', '2026-12-01', '', '', datetime('now'))")
    assert s.session_course(9) is None
    assert s.session_course(999) is None
    s.close()


# ---- Art, Antragsteller, Piktogramm --------------------------------------

def test_art_und_antragsteller(store):
    k = store.session_course(4654)["items"]
    assert [k[n]["type"] for n in ("Ö 1", "Ö 4", "Ö 5", "Ö 8", "Ö 11.1", "Ö 12")] == [
        "formality", "question_time", "decision", "report", "motion", "inquiries"]
    # Ein Antrag bleibt ein Antrag, auch mit Berichtsvorlage der Verwaltung.
    assert k["Ö 11.2"]["type"] == "motion" and k["Ö 11.2"]["type_label"] == "Antrag"
    # Absender ohne Fraktion, ohne Klammer im Kurztitel.
    assert k["Ö 11.1"]["short_title"] == "Weißenmoorstraße"
    assert k["Ö 11.1"]["applicant"] == "beratendes Mitglied Herr Pieper"
    assert k["Ö 11.3"]["applicant"] == "FDP-Fraktion"
    assert k["Ö 8"]["applicant"] is None
    # Gleichartige Formalakte hintereinander teilen sich in der Liste eine Karte.
    assert [k[n]["formal_act"] for n in ("Ö 5", "Ö 6", "Ö 7", "Ö 8")] == [True, True, True, False]
    # Eine Beschlussvorlage, über die ein anderes Gremium entscheidet, ist Vorberatung.
    vorher = store.session_course(4652)["items"]
    assert vorher["Ö 6"]["type"] == "preliminary" and vorher["Ö 6"]["type_label"] == "Vorberatung"


def test_piktogramme_der_vier_sitzungen(store):
    k = store.session_course(4654)["items"]
    assert {n: k[n]["icon"] for n in ("Ö 1", "Ö 4", "Ö 5", "Ö 8", "Ö 9", "Ö 10", "Ö 11.1", "Ö 11.2", "Ö 12")} == {
        "Ö 1": "formalities", "Ö 4": "citizen_question", "Ö 5": "sign", "Ö 8": "bike", "Ö 9": "ticket",
        "Ö 10": "speed", "Ö 11.1": "route", "Ö 11.2": "parking", "Ö 12": "inquiries"}
    for ksinr in SITZUNGEN:
        for it in store.session_course(ksinr)["items"].values():
            assert it["icon"] in course.ICONS


@pytest.mark.parametrize("titel, erwartet", [
    # Jede Zeile ein Fehltreffer, den die Reihenfolge der Regeln abfängt.
    ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen", "money"),
    ("Besetzung des Schulausschusses", "personnel"),
    ("Bäderbetriebsgesellschaft Oldenburg mbH (BBGO): Jahresabschluss 2025", "money"),
    ("Ausfallbürgschaft der Stadt für den Geschäftsbereich Wasser der VWG", "money"),
    ("Parken auf Sicherheitstrennstreifen zwischen Parkständen und Radwegen", "parking"),
    ("Änderung 1 des Bebauungsplanes 435 (Etzhorner Weg/Ekernstraße/Haselriege)", "plan"),
    ("Ersatzneubau Brücke Tweelbäker See", "route"),
    ("Weißenmoorstraße", "route"),
    ("Satzung zur Änderung der Satzung über die Entschädigung der Mitglieder", "statute"),
    ("Die Oldenburger Gymnasien stellen sich vor", "school"),
    ("Sachstandsbericht Park&Ride", "parking"),
    ("Untersuchung einer festgestellten PAK-Belastung in der Flugplatzbäke", "airfield"),
    ("Teileinziehung der Straße \"Junkerstraße\"", "closure"),
])
def test_piktogramm_regeln(titel, erwartet):
    assert course.icon(titel, "decision") == erwartet


def test_piktogramm_rueckfall_nach_art_und_feld():
    """Ohne Treffer zuerst das Politikfeld des Beschlusses (nach der Sitzung),
    dann ein Zeichen nach Art — jeder Punkt trägt eines."""
    assert course.icon("Vermarktung eines Investorengrundstücks", "decision") == "building"
    assert course.icon("Orte für alle", "report") == "report"
    assert course.icon("Orte für alle", "report", "soziales_gesundheit") == "social"
    assert course.icon("Aufgaben und Ressourcen", "motion") == "motion"
    assert course.icon("Aufgaben und Ressourcen", "decision") == "statute"
    # Rahmenpunkte tragen immer ihr festes Zeichen, egal was im Titel steht.
    assert course.icon("Mitteilungen zur Radverkehrsplanung", "announcement") == "announcement"


def test_jeder_schluessel_hat_ein_zeichen():
    schluessel = ({k for k, _ in course.ICON_RULES} | set(course.POLICY_ICONS.values())
                  | set(course.FALLBACK_ICONS.values()) | {"statute"})
    assert schluessel <= set(course.ICONS), sorted(schluessel - set(course.ICONS))


def test_piktogramme_stehen_im_plan():
    """Anhang A des Plans und ``ICONS`` sind EINE Liste an zwei Orten — der
    Plan sagt: wachsen darf sie nur an beiden zugleich."""
    plan = (WURZEL / "docs" / "plan-sitzungsseite-kurs.md").read_text()
    anhang = plan.split("## Anhang A", 1)[1].split("## Anhang B", 1)[0]
    im_plan = dict(re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*`([a-z0-9-]+)`\s*\|", anhang, re.MULTILINE))
    assert im_plan == course.ICONS, (
        "Anhang A in docs/plan-sitzungsseite-kurs.md und council/course.py::ICONS "
        f"weichen ab: nur im Plan {sorted(set(im_plan) - set(course.ICONS))}, "
        f"nur im Code {sorted(set(course.ICONS) - set(im_plan))}")


def test_gremien_kurzformen_wie_im_web():
    """Dieselbe Tabelle wie ``SHORT`` in ``web/frontend/lib/committees.ts`` —
    sonst hieße eine Etappe im Rat anders als das Gremium überall sonst."""
    ts = (WURZEL / "web" / "frontend" / "lib" / "committees.ts").read_text()
    block = ts.split("const SHORT: Record<string, string> = {", 1)[1].split("};", 1)[0]
    im_web = dict(re.findall(r'^\s*"([^"]+)":\s*\n?\s*"([^"]+)",', block, re.MULTILINE))
    assert im_web == course.COMMITTEE_SHORT, (
        "council/course.py::COMMITTEE_SHORT an lib/committees.ts angleichen: "
        f"fehlt {sorted(set(im_web) - set(course.COMMITTEE_SHORT))}, "
        f"zu viel {sorted(set(course.COMMITTEE_SHORT) - set(im_web))}")
    assert course.short_committee("Ausschuss für Finanzen und Beteiligungen") == "Finanzen & Beteiligungen"
    assert course.short_committee("Ausschuss für Stadtplanung und Bauen und Verkehrsausschuss") == (
        "Stadtplanung & Bauen & Verkehrsausschuss")
    assert course.short_committee("Feuerwehrausschuss") == "Feuerwehr"
    for kurz in course.COMMITTEE_STAGE_NAMES:
        assert kurz in course.COMMITTEE_SHORT.values(), kurz


# ---- wichtig -------------------------------------------------------------

def test_wichtig_vor_dem_protokoll_ist_die_auswahl_der_sitzungsliste(store):
    """Kein neues Maß: Derselbe Punkt darf in Liste und Seite nicht verschieden
    wichtig heißen. Höchstens drei (Tims Entscheidung 10.11.2026)."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO agenda_item_impact (ksinr, item_number, impact, reason, created_at) "
            "VALUES (4654, ?, ?, ?, datetime('now'))",
            [("Ö 8", 70, "Grund 8"), ("Ö 9", 80, "Grund 9"), ("Ö 10", 65, "Grund 10"),
             ("Ö 11.2", 75, "Grund 11.2"), ("Ö 11.3", 10, None)])
    k = store.session_course(4654)["items"]
    wichtig = {n: it["important_reason"] for n, it in k.items() if it["important"]}
    erwartet = {p["item_number"]: p["wichtig_grund"]
                for p in store.sitzungs_highlights([4654], max_je_sitzung=3)[4654]}
    assert wichtig == erwartet == {"Ö 8": "Grund 8", "Ö 9": "Grund 9", "Ö 11.2": "Grund 11.2"}
    assert all(it["important_reason"] is None for it in k.values() if not it["important"])


def test_wichtig_nach_dem_protokoll_sind_die_wichtigsten_beschluesse(store):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_protocols (ksinr, extracted_at, status) VALUES (4652, datetime('now'), 'ok')")
        store._conn.executemany(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome, importance, "
            "impact_reason) VALUES (4652, ?, 'decision', ?, 't', 'accepted', ?, ?)",
            [(1, "6", 90, "Warum 6"), (2, "7", 40, None), (3, "8", 70, "Warum 8"),
             (4, "9", 55, "Warum 9"), (5, "Ö15.1", 20, "zu klein")])
    k = store.session_course(4652)["items"]
    wichtig = {n: it["important_reason"] for n, it in k.items() if it["important"]}
    # Die drei höchsten über der Schwelle; „Ö15.1" ohne Leerzeichen findet trotzdem seinen Punkt.
    assert wichtig == {"Ö 6": "Warum 6", "Ö 8": "Warum 8", "Ö 9": "Warum 9"}
    assert k["Ö 15.1"]["important"] is False


# ---- vertagt -------------------------------------------------------------

def _frueher(store, ksinr, gremium, datum, zeilen):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (?, ?, ?, '17:00', '', datetime('now'))", (ksinr, gremium, datum))
        store._conn.executemany(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, is_public) "
            "VALUES (?, ?, ?, ?, 1)", [(ksinr, *z) for z in zeilen])


def test_vertagt_aus_titel_und_beschluss(store):
    """Zwei Belege: der Zusatz „zurückgestellt/abgesetzt" im Titel (ohne
    Protokoll sofort da) und ein vertagter Beschluss. Gezählt wird nur im
    selben Gremium, Sitzungen statt Zeilen."""
    weissenmoor = next(z[1] for z in SITZUNGEN[4654][3] if z[0] == "Ö 11.1")
    assert weissenmoor.startswith("Weißenmoorstraße (beratendes Mitglied Herr Pieper vom 22.05.2026)")
    _frueher(store, 1, "Verkehrsausschuss", "2026-08-24", [
        ("Ö 16.1", weissenmoor + " Beschluss: zurückgestellt/abgesetzt", ""),
        ("Ö 16.9", "Parken auf Sicherheitstrennstreifen - Beschluss", "26/0658"),
        # Formalien stehen jedes Mal mit demselben datierten Titel da — nie gelb.
        ("Ö 3", "Genehmigung des Protokolls Nr. 05/26 (öffentlicher Teil) vom 08.06.2026 "
                "Beschluss: zurückgestellt/abgesetzt", ""),
    ])
    _frueher(store, 2, "Verkehrsausschuss", "2026-06-08", [("Ö 15.3", weissenmoor, "")])
    # Anderes Gremium: zählt nicht.
    _frueher(store, 3, "Rat", "2026-08-31", [("Ö 8.9", weissenmoor + " Beschluss: zurückgestellt/abgesetzt", "")])
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome) "
            "VALUES (?, ?, 'decision', ?, 't', 'postponed')", [(1, 1, "16.9"), (2, 1, "15.3")])
    k = store.session_course(4654)["items"]
    assert k["Ö 11.1"]["postponed"] == 2       # 24.08. per Titel, 08.06. per Beschluss
    assert k["Ö 11.2"]["postponed"] == 1       # über die Vorlage 26/0658
    assert k["Ö 11.3"]["postponed"] == 0
    assert k["Ö 3.1"]["postponed"] == 0


def test_antrag_ohne_vorlage_nur_mit_datum():
    """Ohne Vorlage nur, wenn der Titel ein Datum trägt — „Bericht der
    Verwaltung" wiederholt sich jede Sitzung und ist doch nicht derselbe Punkt."""
    jetzt = [{"item_number": "Ö 5", "title": "Sachstand Radverkehr - Bericht", "template_number": ""},
             {"item_number": "Ö 6", "title": "Weg X (SPD-Fraktion vom 01.02.2026) - Antrag", "template_number": ""}]
    frueher = [{"ksinr": 1, "item_number": "Ö 5", "template_number": "",
                "title": "Sachstand Radverkehr - Bericht Beschluss: zurückgestellt/abgesetzt"},
               {"ksinr": 1, "item_number": "Ö 7", "template_number": "",
                "title": "Weg X (SPD-Fraktion vom 01.02.2026) - Antrag Beschluss: zurückgestellt/abgesetzt"}]
    assert course.postponed_counts(jetzt, frueher, set()) == {"Ö 5": 0, "Ö 6": 1}


# ---- Vertrag -------------------------------------------------------------

def test_form_ist_die_des_vertrags(store):
    """Nicht gegen eine eigene Kopie prüfen: Die Schlüssel kommen aus den
    Antwortformen, die das Backend zusagt."""
    sys.path.insert(0, str(WURZEL / "web" / "backend"))
    from app.antworten import CourseCell, CourseItem, CourseStage, CourseStation, SessionCourse

    for ksinr in SITZUNGEN:
        k = store.session_course(ksinr)
        assert set(k) == set(get_type_hints(SessionCourse))
        for st in k["stages"]:
            assert set(st) == set(get_type_hints(CourseStage))
            for z in st["cells"]:
                assert set(z) == set(get_type_hints(CourseCell))
        for it in k["items"].values():
            assert set(it) == set(get_type_hints(CourseItem))
            assert it["type_label"] == course.TYPE_LABELS[it["type"]]
            for station in it["journey"]:
                assert set(station) == set(get_type_hints(CourseStation))
        # Jeder Punkt in einer Boje hat Angaben, und es gibt keine ohne Boje.
        in_zellen = {nr for st in k["stages"] for z in st["cells"] for nr in z["items"]}
        assert in_zellen == set(k["items"])


def test_gesperrter_unterpunkt_einer_oeffentlichen_rubrik():
    """Finanzausschuss 02.09.2026: Unter „Ö 17 Anträge …" hing nur „N 17.1",
    danach kam „Ö 18 Anfragen". Das ist kein öffentlicher Punkt hinter dem
    nichtöffentlichen Teil — die Gliederung bleibt, die leere Rubrik fällt weg."""
    def z(nr, titel, oeff=1, vorlage=""):
        return {"item_number": nr, "title": titel, "template_number": vorlage, "is_public": oeff}
    zeilen = [
        z("Ö 1", "Feststellung der Beschlussfähigkeit"),
        z("Ö 2", "Liquiditätsstand - Bericht", vorlage="26/1"),
        z("Ö 3", "Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder"),
        z("N 3.1", "gesperrte Information", 0),
        z("Ö 4", "Anfragen und Anregungen"),
        z("N 5", "gesperrte Information", 0),
        z("N 6", "gesperrte Information", 0),
    ]
    stufen = course.build_stages(zeilen, set(), set())
    assert [s["kind"] for s in stufen] == ["start", "content", "end", "closed"]
    assert (stufen[-1]["range"], stufen[-1]["count"], stufen[-1]["cells"][0]["label"]) == ("N 5 – N 6", 3, "N 5–6")


def test_ausschuss_abschnitt_mit_anderem_namen():
    assert course.section_committee("Betriebsausschuss des Abfallwirtschaftsbetriebes der Stadt Oldenburg") == (
        "Abfallwirtschaft")
    assert course.section_committee("Verkehrsausschuss") == "Verkehr"


def test_piktogramme_im_web():
    """``lib/course-icons.ts`` ordnet jedem Schlüssel sein Lucide-Zeichen zu —
    dieselbe Tabelle wie ``ICONS``. Ein Schlüssel, der dort fehlt, fiele im
    Kurs still auf das Dokument zurück."""
    ts = (WURZEL / "web" / "frontend" / "lib" / "course-icons.ts").read_text()
    block = ts.split("COURSE_ICONS: Record<string, LucideIcon> = {", 1)[1].split("};", 1)[0]
    im_web = dict(re.findall(r"^\s*([a-z_]+):\s*([A-Za-z0-9]+),", block, re.MULTILINE))
    pascal = {k: "".join(t.capitalize() for t in v.split("-")) for k, v in course.ICONS.items()}
    assert im_web == pascal, (
        "lib/course-icons.ts an council/course.py::ICONS angleichen: "
        f"fehlt {sorted(set(pascal) - set(im_web))}, zu viel {sorted(set(im_web) - set(pascal))}, "
        f"anders {sorted(k for k in im_web if k in pascal and im_web[k] != pascal[k])}")


# ---- Satz zur Sitzung, Weg der Vorlage, wie es weitergeht (Schritt 3) ----

def test_satz_vor_dem_protokoll_sagt_was_ansteht(store):
    """Die Sitzungen der Fixtur sind gewesen, ihr Protokoll fehlt — das sagt
    der Satz dazu. Ohne wichtige Punkte zählt er nach Art."""
    _frueher(store, 1, "Verkehrsausschuss", "2026-08-24", [
        ("Ö 16.9", "Parken auf Sicherheitstrennstreifen - Beschluss Beschluss: zurückgestellt/abgesetzt", "26/0658"),
    ])
    k = store.session_course(4654)
    assert k["summary"] == ("Auf der Tagesordnung: 3 Entscheidungen, 3 Berichte und 3 Anträge. "
                            "Einer stand schon einmal hier und wurde vertagt. "
                            "Das Protokoll liegt noch nicht vor.")
    assert store.session_course(4593)["summary"] == (
        "Auf der Tagesordnung: 2 Anträge. Das Protokoll liegt noch nicht vor.")


def test_satz_vorher_nennt_die_wichtigen_beim_namen():
    """Tims Befund 11.11.2026: „21 Punkte zur Beratung“ sagt nichts. Die
    wichtigen Punkte stehen beim Namen vorn, der Rest nach Art gezählt."""
    def p(t, typ, wichtig=False):
        return {"type": typ, "short_title": t, "important": wichtig, "postponed": 0}
    items = {"Ö 1": p("Genehmigung der Tagesordnung", "formality"),
             "Ö 5": p("Geschäftsordnung", "decision", True),
             "Ö 6": p("Bildung des Verwaltungsausschusses", "decision", True),
             **{f"Ö 7.{i}": p(f"Wahl {i}", "decision") for i in range(1, 13)},
             **{f"Ö 8.{i}": p(f"Antrag {i}", "motion") for i in range(1, 6)},
             "Ö 9": p("Bericht", "report"), "Ö 10": p("Sonstiges", "other")}
    assert course.summary_sentence(items, {}, {}, rat=True) == (
        "Im Mittelpunkt: „Geschäftsordnung“ und „Bildung des Verwaltungsausschusses“. "
        "Dazu 12 Entscheidungen, 5 Anträge, 1 Bericht und 1 weiterer Punkt.")
    # Drei wichtige: zwei beim Namen, der dritte gezählt.
    items["Ö 11"] = p("Haushalt 2027", "decision", True)
    assert course.summary_sentence(items, {}, {}, rat=True).startswith(
        "Im Mittelpunkt: „Geschäftsordnung“, „Bildung des Verwaltungsausschusses“ und ein weiterer wichtiger Punkt. ")
    # Nur Formalien: kein Satz.
    assert course.summary_sentence({"Ö 1": items["Ö 1"]}, {}, {}, rat=True) is None


def test_satz_nach_dem_protokoll_sagt_was_herauskam(store):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_protocols (ksinr, extracted_at, status) VALUES (4652, datetime('now'), 'ok')")
        # Ö 6–12 sind Beschlussvorlagen; zwei wichtige darunter, Ö 15.3 vertagt.
        store._conn.executemany(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome, vote, importance) "
            "VALUES (4652, ?, 'decision', ?, 't', ?, ?, ?)",
            [(i, str(i), "accepted", "unanimous", 90 if i in (6, 7) else 10) for i in range(6, 13)]
            + [(20, "15.3", "postponed", None, 10), (21, "5", "noted", None, 10)])
    k = store.session_course(4652)
    assert k["summary"] == (
        "Der Ausschuss hat alle sieben Beschlussvorlagen einstimmig angenommen, darunter "
        "„Verkehr und Wasser GmbH (VWG): Technologieentscheidung im Rahmen der Antriebswende“ und "
        "„Teileinziehung der Straße ‚Junkerstraße‘“. Vertagt wurde „Weißenmoorstraße“.")


def test_satz_im_rat_und_ohne_zahlwort_bei_grossen_zahlen():
    items = {f"Ö {i}": {"type": "decision", "short_title": f"T{i}", "important": False, "postponed": 0}
             for i in range(1, 15)}
    outcomes = {nr: "accepted" for nr in items}
    outcomes["Ö 14"] = "rejected"
    assert course.summary_sentence(items, outcomes, {}, rat=True) == (
        "Der Rat hat 13 von 14 Beschlussvorlagen angenommen. Abgelehnt wurde „T14“.")
    assert course.summary_sentence({}, {}, {}, rat=False) is None


def test_weg_der_vorlage_und_wie_es_weitergeht(store):
    """Der Weg einer Vorlage nennt jede Station mit Ergebnis — aus dem
    Protokoll, sonst aus dem Titel-Zusatz. Ein hier vertagter Punkt nennt die
    nächste Tagesordnung desselben Gremiums, auf der er wieder steht."""
    tn = next(z[2] for z in SITZUNGEN[4652][3] if z[0] == "Ö 6")
    _frueher(store, 1, "Ausschuss für Finanzen und Beteiligungen", "2026-06-03", [
        ("Ö 7", "VWG: Technologieentscheidung - Beschluss Beschluss: ungeändert beschlossen", tn)])
    weissenmoor = next(z[1] for z in SITZUNGEN[4652][3] if z[0] == "Ö 15.3")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_protocols (ksinr, extracted_at, status) VALUES (4652, datetime('now'), 'ok')")
        store._conn.executemany(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome) "
            "VALUES (4652, ?, 'decision', ?, 't', ?)", [(1, "6", "accepted"), (2, "15.3", "postponed")])
    k = store.session_course(4652)
    weg = k["items"]["Ö 6"]["journey"]
    assert [(w["committee"], w["session_date"], w["outcome"]) for w in weg] == [
        ("Ausschuss für Finanzen und Beteiligungen", "2026-06-03", "accepted"),
        ("Verkehrsausschuss", "2026-06-08", "accepted"),
    ]
    assert k["items"]["Ö 15.3"]["journey"] == []          # Antrag ohne Vorlage
    # 4654 (21.09.) ist die nächste Sitzung des Verkehrsausschusses im Fixture.
    assert k["items"]["Ö 15.3"]["next_on_agenda"] == {
        "ksinr": 4654, "session_date": "2026-09-21", "item_number": "Ö 11.1"}
    assert weissenmoor in {z[1] for z in SITZUNGEN[4654][3]}
    assert k["items"]["Ö 6"]["next_on_agenda"] is None
    assert k["next_session"] == {"ksinr": 4654, "session_date": "2026-09-21", "session_time": "17:00",
                                 "location": None, "has_agenda": True}
    assert store.session_course(4654)["next_session"] is None


def test_ergebnis_aus_dem_titel():
    assert course.outcome_from_title("X - Beschluss Beschluss: ungeändert beschlossen") == "accepted"
    assert course.outcome_from_title("X Beschluss: zur Kenntnis genommen") == "noted"
    assert course.outcome_from_title("X Beschluss: zurückgestellt/abgesetzt") == "postponed"
    assert course.outcome_from_title("X Beschluss: an Fachausschuss (zurück-)verwiesen") is None
    assert course.outcome_from_title("X - Beschluss") is None


# ---- Punkt-Seite (Schritt 4) ----------------------------------------------

def test_punkt_seite_mit_vorgeschichte_und_nachbarn(store):
    """Ein Antrag ohne Vorlage: Seine Vorgeschichte sind die früheren Auftritte
    desselben datierten Antrags im selben Gremium — die Stationen, die im
    Entwurf unter „Vorgeschichte“ stehen."""
    weissenmoor = next(z[1] for z in SITZUNGEN[4654][3] if z[0] == "Ö 11.1")
    _frueher(store, 1, "Verkehrsausschuss", "2026-08-24", [("Ö 16.1", weissenmoor + " Beschluss: zurückgestellt/abgesetzt", "")])
    p = store.session_item(4654, "Ö 11.1")
    assert p["committee"] == "Verkehrsausschuss" and p["decision_id"] is None
    assert [(s["session_date"], s["outcome"], s["current"]) for s in p["history"]] == [
        ("2026-06-08", None, False), ("2026-08-24", "postponed", False), ("2026-09-21", None, True)]
    assert p["previous"]["item_number"] == "Ö 10" and p["next"]["item_number"] == "Ö 11.2"
    assert (p["position"], p["count"]) == (13, 16)
    assert p["course_item"]["type"] == "motion"
    # Nichtöffentlich, Überschrift, Unbekanntes: keine Seite.
    assert store.session_item(4654, "N 13") is None
    assert store.session_item(4654, "Ö 11") is None
    assert store.session_item(4654, "Ö 99") is None
    assert store.session_item(99999, "Ö 1") is None


def test_punkt_mit_beschluss_und_unterlagen(store):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome) "
            "VALUES (4652, 1, 'decision', '6', 't', 'accepted')")
        store._conn.execute("UPDATE council_agenda_items SET kvonr = 777 WHERE ksinr = 4652 AND item_number = 'Ö 6'")
    p = store.session_item(4652, "Ö 6")
    assert p["decision_id"] is not None
    assert p["documents"][0] == {"kind": "template", "label": f"Vorlage {p['item']['template_number']}",
                                 "url": "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=777", "date": None}
    s = store.agenda_item_subject(4652, "Ö 6")
    assert s["decision_id"] == p["decision_id"]
    s9 = store.agenda_item_subject(4654, "Ö 9")
    assert s9["decision_id"] is None and s9["title"].startswith("Soziales D-Ticket")
    assert store.agenda_item_subject(4654, "N 13") is None


def test_gegenstand_regel_nennt_den_punkt():
    """Ohne Beschluss nennt der Prompt den Tagesordnungspunkt beim Namen (Plan
    3.10) — sonst meint „das“ den ähnlichsten älteren Beschluss."""
    from council import qa
    regel = qa.gegenstand_regel({"agenda_item": {
        "item_number": "Ö 9", "title": "Soziales D-Ticket in Oldenburg - Bericht", "template_number": "26/0719",
        "committee": "Verkehrsausschuss", "session_date": "2026-09-21", "decision_id": None}})
    assert "Tagesordnungspunkt „Soziales D-Ticket in Oldenburg - Bericht“ (Ö 9, Verkehrsausschuss am 2026-09-21, Vorlage 26/0719)" in regel
    assert qa.gegenstand_regel({}) == ""


# ---- Argumente und Fraktionen (Schritt 6) ----------------------------------

def _beitraege(store, ksinr, zeilen):
    """(top, speaker, party, text, page) als Wortbeiträge einer Sitzung."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_speeches (ksinr, position, kind, top, speaker, party, text, extracted_at, page) "
            "VALUES (?, ?, 'speech', ?, ?, ?, ?, datetime('now'), ?)",
            [(ksinr, i, *z) for i, z in enumerate(zeilen, start=1)])


def test_stoff_ueber_alle_stationen_der_vorlage(store):
    """Der Stoff eines Punkts sind die Wortbeiträge ALLER Stationen seiner
    Vorlage — zugeordnet über die Nummer oder, wo die Extraktion nur den Titel
    schreibt, über den Titel. Ein Unterpunkt (6.1) und ein Sammel-TOP zählen
    nicht mit."""
    tn = next(z[2] for z in SITZUNGEN[4652][3] if z[0] == "Ö 6")
    _frueher(store, 1, "Ausschuss für Finanzen und Beteiligungen", "2026-06-03", [
        ("Ö 7", "VWG: Technologieentscheidung im Rahmen der Antriebswende - Beschluss", tn),
        ("Ö 9", "Anfragen und Anregungen", "")])
    _beitraege(store, 1, [
        ("7 VWG: Technologieentscheidung", "Adler", "BSW-Fraktion", "Batterie ist billiger.", 4),
        ("Anfragen und Anregungen", "Baak", "CDU", "Wann kommt der Radweg?", 9),
    ])
    _beitraege(store, 4652, [
        ("6 Verkehr und Wasser GmbH", "Klein", "SPD", "Wasserstoff ist zu teuer.", 3),
        ("Verkehr und Wasser GmbH (VWG): Technologieentscheidung im Rahmen der Antriebswende",
         "Niederstein", "Bündnis 90/ Die Grünen", "Ein Mix ist sicherer.", 3),
        ("6.1 Etwas anderes", "Paul", "AfD", "Gehört nicht hierher.", 5),
    ])
    m = store.item_argument_material(4652, "Ö 6")
    assert m["subject_key"] == f"tn:{tn}"
    assert [s["speaker"] for s in m["speeches"]] == ["Adler", "Klein", "Niederstein"]
    assert m["template"]["template_number"] == tn
    # Rahmen der Sitzung und Nichtöffentliches haben keinen Stoff.
    assert store.item_argument_material(4652, "Ö 3") is None
    assert store.item_argument_material(4652, "Ö 4") is None
    assert store.item_argument_material(4652, "N 17") is None


def test_argumente_aus_der_ablage_mit_fraktionen(store, monkeypatch):
    """Fraktionen rechnet die Seite ohne Modell; Argumente kommen aus der
    Ablage und tragen eine Fundstelle mit Adresse. Kommen danach Beiträge
    dazu, gilt die Auswertung als veraltet — gezeigt wird sie trotzdem."""
    from council import arguments

    _beitraege(store, 4652, [
        ("6 VWG", "Klein", "SPD", "Wasserstoff ist zu teuer.", 3),
        ("6 VWG", "Niederstein", "Bündnis 90/ Die Grünen", "Ein Mix ist sicherer.", 3),
        ("6 VWG", "Atzler", "VWG", "Der Betrieb braucht Planbarkeit.", 4),
        ("6 VWG", "Woltmann", "CDU", "Die Kosten sind tragbar.", 4),
    ])
    with store._conn:
        store._conn.execute("INSERT INTO council_protocols (ksinr, extracted_at, status, document_url) "
                            "VALUES (4652, datetime('now'), 'ok', 'https://example.org/p.pdf')")
    m = store.item_argument_material(4652, "Ö 6")
    ids = [s["id"] for s in m["speeches"]]
    quellen = {f"W{s['id']}": {**s, "kind": "speech"} for s in m["speeches"]}
    roh = {"issues": [{"question": "Was kostet es?",
                       "pro": [{"source": f"W{ids[3]}", "text": "Tragbar."}, {"source": f"W{ids[1]}", "text": "Sicherer."}],
                       "contra": [{"source": f"W{ids[0]}", "text": "Zu teuer."}, {"source": f"W{ids[2]}", "text": "Planbarkeit fehlt."}]}],
           "further": {"pro": [], "contra": []}}
    payload = arguments.parse(__import__("json").dumps(roh), quellen)
    store.save_item_arguments(m["subject_key"], arguments.sources_hash(ids, m["template_number"]), "test", payload)

    v = store.item_arguments_view(4652, "Ö 6")
    assert v["show_arguments"] and (v["pro_count"], v["contra_count"]) == (2, 2)
    assert v["stale"] is False
    erste = v["issues"][0]["pro"][0]
    assert (erste["speaker"], erste["party"], erste["body"]) == ("Woltmann", "CDU", "Verkehrsausschuss")
    assert erste["source"] == {"kind": "speech", "id": ids[3], "page": 4, "url": "https://example.org/p.pdf#page=4"}
    # Fraktionen: einheitliche Labels, der Verkehrsbetrieb ist keine Fraktion.
    assert v["show_factions"] and sorted(f["party"] for f in v["factions"]) == ["CDU", "Grüne", "SPD"]

    _beitraege(store, 4652, [("6 VWG", "Pfeiffer", "FDP", "Später entscheiden.", 5)])
    assert store.item_arguments_view(4652, "Ö 6")["stale"] is True


def test_ohne_genug_stoff_kein_reiter(store):
    _beitraege(store, 4652, [("6 VWG", "Klein", "SPD", "Zu teuer.", 3)])
    assert store.item_arguments_view(4652, "Ö 6") is None


def test_fraktion_aus_der_anwesenheitsliste_der_eigenen_sitzung(store):
    """Beiträge ohne Partei bekommen die Fraktion aus der Anwesenheitsliste
    ihrer Sitzung — mit dem Label von damals, je Sitzung. Verwaltung bleibt
    ohne; was das Protokoll nennt, bleibt, wie es ist."""
    tn = next(z[2] for z in SITZUNGEN[4652][3] if z[0] == "Ö 6")
    _frueher(store, 1, "Ausschuss für Finanzen und Beteiligungen", "2024-06-03", [
        ("Ö 7", "VWG: Technologieentscheidung im Rahmen der Antriebswende - Beschluss", tn)])
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role) VALUES (?, ?, ?, ?)",
            [(1, "Hans-Henning Adler", "Gruppe DIE LINKE./Piratenpartei", "member"),
             (4652, "Hans-Henning Adler", "BSW", "member"),
             (4652, "Michael Wenzel", "Bündnis 90/Die Grünen", "chair"),
             (4652, "Holger Denckmann", "Verwaltung", "administration")])
    _beitraege(store, 1, [("7 VWG", "Adler", None, "Batterie ist billiger.", 4)])
    _beitraege(store, 4652, [
        ("6 VWG", "Ratsherr Adler", None, "Wasserstoff ist zu teuer.", 3),
        ("6 VWG", "Wenzel", "", "Ein Mix ist sicherer.", 3),
        ("6 VWG", "Stadtrat Denckmann", None, "Die Verwaltung empfiehlt Batterie.", 3),
        ("6 VWG", "Klein", "SPD", "Gehört der SPD.", 4),
    ])
    m = store.item_argument_material(4652, "Ö 6")
    assert [(s["speaker"], s["party"], s.get("party_source")) for s in m["speeches"]] == [
        ("Adler", "Gruppe DIE LINKE./Piratenpartei", "attendance"),
        ("Ratsherr Adler", "BSW", "attendance"),
        ("Wenzel", "Bündnis 90/Die Grünen", "attendance"),
        ("Stadtrat Denckmann", None, None),
        ("Klein", "SPD", None),
    ]
