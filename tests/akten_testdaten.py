"""Gemeinsame Test-Datenbank für die Grundakten- und Akten-Tests.

Kein Testmodul: Beide Testdateien bauen ihre Fixtures hieraus, statt sie
voneinander zu importieren (das hielt ruff für eine Doppeldefinition).
"""
from council import matters
from council.store import CouncilStore


def store_bauen(tmp_path):
    st = CouncilStore(tmp_path / "council.sqlite")
    c = st._conn
    c.executemany(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (?, ?, ?, '', '', '')", [
            (1, "Ausschuss für Stadtgrün, Umwelt und Klima", "2026-04-16"),
            (2, "Rat", "2026-05-04"),
            (3, "Ausschuss für Stadtgrün, Umwelt und Klima", "2026-09-10"),
        ])
    c.executemany(
        "INSERT INTO council_decisions (id, ksinr, position, item_number, title, template_number, "
        "kind, parent_item) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            # Dieselbe Vorlage in Ausschuss und Rat, einmal mit /1
            (10, 1, 1, "7", "Spielleitplanung - Beschluss", "26/0100", "decision", None),
            (11, 2, 1, "5", "Spielleitplanung", "26/0100/1", "decision", None),
            # Teilabstimmung zum Rats-TOP 5
            (12, 2, 2, "5.1", "Änderungsantrag der SPD-Fraktion", None, "subvote", "5"),
            # Antrag ohne Nummer — Antrag und Bericht tragen denselben Kern
            (13, 1, 3, "11.1", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom "
             "17.03.2026) - Antrag", None, "decision", None),
            (14, 3, 1, "4", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom "
             "17.03.2026) - Bericht der Verwaltung", None, "decision", None),
            # Zu allgemein für einen Schlüssel
            (15, 3, 2, "9", "Bericht der Verwaltung", None, "decision", None),
        ])
    c.executemany(
        "INSERT INTO council_templates (kvonr, template_number, title, raw_text, fetched_at) "
        "VALUES (?, ?, ?, ?, '')", [
            (500, "26/0100", "Spielleitplanung", "Bezug: Vorlage 25/0999 zum Schlossplatz."),
            (501, "26/0200", "Heidbrook", "Ohne Verweis."),
        ])
    c.executemany(
        "INSERT INTO council_deliberations (id, kvonr, date, committee, result, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, '')", [
            (900, 500, "2026-04-16", "Ausschuss", "Vorberatung"),
            (901, 501, "2026-10-20", "Rat", "Entscheidung"),   # noch nicht protokolliert
        ])
    c.executemany(
        "INSERT INTO council_agenda_items (id, ksinr, item_number, title, template_number, kvonr) "
        "VALUES (?, ?, ?, ?, ?, ?)", [
            (700, 1, "Ö 7", "Spielleitplanung", "26/0100", 500),
            (701, 1, "Ö 1", "Feststellung der Beschlussfähigkeit", None, None),
            (702, 3, "Ö 4", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom 17.03.2026)",
             None, None),
        ])
    c.executemany(
        "INSERT INTO council_speeches (id, ksinr, position, kind, top, speaker, text, extracted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, '')", [
            # Steht unter TOP 7 „Spielleitplanung“, redet aber vom Schlossplatz
            (800, 1, 1, "speech", "7 Spielleitplanung", "Verwaltung",
             "Auf dem Schlossplatz ist kein Platz für einen Spielplatz."),
            (801, 1, 2, "pledge", "11.1 Trinkwasserspender im Außenbereich", "Verwaltung (Protokollnotiz)",
             "Klärung bis zum Abschluss des KLAK 2027, danach Bau."),
            (802, 1, 3, "inquiry", "Anfragen und Anregungen", "Behrens", "Wann kommt der Radweg?"),
        ])
    c.commit()
    return st


def themen_bauen(store):
    c = store._conn
    c.executemany(
        "INSERT INTO council_decisions (id, ksinr, position, item_number, title, template_number, "
        "kind) VALUES (?, ?, ?, ?, ?, ?, 'decision')", [
            (20, 3, 5, "12", "Spielplatz Schlossplatz - Sachstandsbericht", "26/0300"),
            (21, 2, 9, "8", "Haushalt 2026 - Beschluss", "25/0667"),
            (22, 2, 10, "8.1", "Wirtschaftsplan Abfallwirtschaftsbetrieb 2026", "25/0667"),
            (23, 3, 6, "13", "Klävemann-Stiftung: Haushaltsplan 2026", "25/0667"),
            (24, 3, 7, "14", "Neubau am Fliegerhorst", "26/0400"),
        ])
    c.executemany("INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?, ?, ?, ?, ?)", [
        (1, "schlossplatz", "Schlossplatz", "place", 7),
        (2, "abfallwirtschaftsbetrieb", "Abfallwirtschaftsbetrieb", "organisation", 30),
        (3, "schulausschuss", "Schulausschuss", "organisation", 40),
        (4, "fliegerhorst", "Fliegerhorst", "place", 185),
        (5, "oldenburg-pass", "Oldenburg Pass", "project", 3),
        (6, "peterstrasse", "Peterstraße", "place", 4),
    ])
    c.executemany("INSERT INTO council_entity_obs (decision_id, slug, name, kind) VALUES "
                  "(?, ?, ?, ?)", [(20, "schlossplatz", "Schlossplatz", "place"),
                                   (22, "abfallwirtschaftsbetrieb", "Abfallwirtschaftsbetrieb",
                                    "organisation")])
    c.executemany("INSERT INTO council_entity_links (entity_id, decision_id) VALUES (?, ?)", [
        (1, 20), (2, 22), (3, 10), (4, 24), (4, 10)])
    c.executemany(
        "INSERT INTO council_speeches (id, ksinr, position, kind, top, speaker, text, extracted_at) "
        "VALUES (?, ?, ?, 'speech', ?, ?, ?, '')", [
            (810, 3, 5, "1 Mitteilungen", "A", "Das gehe nur, wenn es zu Oldenburg passt."),
            (811, 3, 6, "1 Mitteilungen", "B", "Der Oldenburg Pass soll günstiger werden."),
            (812, 3, 7, "1 Mitteilungen", "C", "Der Schulausschuss tagt im Mai."),
            (813, 3, 8, "1 Mitteilungen", "D", "Die Pferdemarktplanungen am Schlossplatzrand."),
        ])
    c.executemany(
        "INSERT INTO council_press (id, url, title, date, text, fetched_at) VALUES "
        "(?, ?, ?, ?, ?, '')", [
            (30, "u1", "Spielbereich auf dem Schlossplatz: Ideen gesucht", "2025-11-04", "Kinder…"),
            (31, "u2", "Am Dienstag tagt der Sozialausschuss", "2026-04-20",
             "Die Sitzung findet im Kulturzentrum PFL, Peterstraße 3, statt."),
            (32, "u3", "Neuer Tarif ab Januar", "2026-01-02", "Der Oldenburg Pass wird günstiger."),
        ])
    c.commit()
    matters.build(store)
    return store
