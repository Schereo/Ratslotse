"""Antragsteller ≠ Fraktion mit einem Änderungsantrag im selben TOP.

Befund 03.10.2026: Die Stadionvergabe (Beschluss 20947, Verwaltungsvorlage
26/0396) trug ``factions = ["CDU"]`` nur wegen des CDU-Änderungsantrags 20948.
Die Beschluss-Seite zeigte „Antrag von: CDU", Frag den Rat schrieb „beruhte auf
einem CDU-Antrag". Gemessen am Prod-Abzug vom 01.10.: 162 Hauptbeschlüsse
betroffen, 141 davon ganz ohne echte Antragstellerin.
"""
from __future__ import annotations

import json

from council import qa
from council.applicants import applicants_named, faction_named_in_title, main_item_factions
from council.store import CouncilStore

STADION = "Stadion Oldenburg GmbH & Co. KG: Stadionneubau Maastrichter Straße - Beschluss"


# ---- reine Regeln -----------------------------------------------------------

def test_aenderungsantrag_macht_keine_antragstellerin():
    assert main_item_factions(["CDU"], STADION, ["CDU", "SPD", "BSW"]) == []


def test_eigener_antrag_bleibt_auch_mit_eigenem_aenderungsantrag():
    titel = "Städtepartnerschaft mit Machatschkala (CDU-Fraktion vom 08.11.2023)"
    assert main_item_factions(["CDU"], titel, ["CDU"]) == ["CDU"]


def test_nur_die_fraktionen_der_teilabstimmungen_fallen_weg():
    titel = "Haushaltssatzung 2025"
    alt = ["BSW", "CDU", "Bündnis 90/Die Grünen", "Verwaltung"]
    assert main_item_factions(alt, titel, ["CDU", "Grüne"]) == ["BSW", "Verwaltung"]


def test_schreibweisen_derselben_fraktion_gelten_als_gleich():
    assert main_item_factions(["CDU-Fraktion"], STADION, ["CDU"]) == []
    assert main_item_factions(["Bündnis 90/Die Grünen"], "x", ["Fraktion Grüne"]) == []


def test_ohne_teilabstimmung_bleibt_alles_stehen():
    assert main_item_factions(["Grüne"], "Bewohnerparkzone Haarenesch", []) == ["Grüne"]
    assert main_item_factions(["Grüne"], "Bewohnerparkzone Haarenesch", None) == ["Grüne"]


def test_zweiter_lauf_aendert_nichts():
    einmal = main_item_factions(["CDU", "SPD"], STADION, ["CDU"])
    assert main_item_factions(einmal, STADION, ["CDU"]) == einmal == ["SPD"]


def test_titel_nennt_fraktion():
    assert faction_named_in_title("Bündnis 90/Die Grünen",
                                  "Fahrradstraße (Fraktion Bündnis 90/Die Grünen vom 1.2.2024)")
    assert faction_named_in_title("Lokale Agenda 21", "Trinkwasserbrunnen - Antrag Lokale Agenda 21")
    assert not faction_named_in_title("CDU", STADION)
    assert not faction_named_in_title("Für Oldenburg", "Lachgas-Verbot")


def test_antrag_von_nur_wenn_der_titel_jede_fraktion_nennt():
    assert applicants_named(["CDU"], "Brücke Tweelbäke (CDU-Fraktion vom 30.08.2024)")
    assert not applicants_named(["CDU", "SPD"], "Brücke Tweelbäke (CDU-Fraktion vom 30.08.2024)")
    assert not applicants_named(["Grüne"], "Bewohnerparkzone Haarenesch")
    assert not applicants_named([], "egal")


# ---- Import, Bestand, Ausgabe ---------------------------------------------

def _session(store, ksinr=4692):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
            "fetched_at) VALUES (?, 'Rat', '2026-06-01', '17:00', '', '')", (ksinr,))


def _stadion_protokoll():
    return [{
        "item_number": "6.1", "title": STADION, "outcome": "accepted",
        "factions": ["CDU"], "template_number": "26/0396",
        "sub_votes": [{"description": "Änderungsantrag der CDU-Fraktion", "outcome": "rejected",
                       "factions": ["CDU"]}],
    }]


def test_import_traegt_den_aenderungsantrag_nur_an_der_teilabstimmung(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _session(store)
    store.save_protocol(4692, {"document_id": 1, "url": "u"}, {}, "Protokoll", 1, "m",
                        decisions=_stadion_protokoll(), attendance=[])
    haupt, teil = store.get_decisions(4692)
    assert haupt["kind"] == "decision" and haupt["factions"] == [] and haupt["parties"] == []
    assert haupt["applicants_named"] is False
    assert teil["kind"] == "subvote" and teil["factions"] == ["CDU"]
    # Die Partei-Auswertung zählt die Verwaltungsvorlage nicht als CDU-Antrag.
    assert haupt["id"] not in store.decision_ids_for_party("CDU")
    store.close()


def test_bestand_wird_einmal_bereinigt(tmp_path):
    """Gewachsene Datenbank: die Zeilen tragen noch den alten Stand, die Marke
    fehlt. Der nächste Start bereinigt sie — und genau einmal."""
    pfad = tmp_path / "c.sqlite"
    store = CouncilStore(pfad)
    _session(store)
    with store._conn:
        for pos, (kind, parent, title, fac) in enumerate([
            ("decision", None, STADION, ["CDU"]),
            ("subvote", "6.1", "Änderungsantrag der CDU-Fraktion", ["CDU"]),
        ]):
            store._conn.execute(
                "INSERT INTO council_decisions (ksinr, position, kind, parent_item, item_number, "
                "title, factions) VALUES (4692, ?, ?, ?, '6.1', ?, ?)",
                (pos, kind, parent, title, json.dumps(fac)))
        store._conn.execute("DELETE FROM council_migration_marks "
                            "WHERE marke = 'antragsteller_ohne_aenderungen_2026_10'")
    store.close()

    store = CouncilStore(pfad)
    fac = dict(store._conn.execute("SELECT kind, factions FROM council_decisions").fetchall())
    assert fac == {"decision": "[]", "subvote": '["CDU"]'}
    # Ein späterer Eintrag (etwa von Hand) wird beim nächsten Start nicht mehr angefasst.
    with store._conn:
        store._conn.execute("UPDATE council_decisions SET factions = '[\"CDU\"]' WHERE kind = 'decision'")
    store.close()
    store = CouncilStore(pfad)
    assert store._conn.execute(
        "SELECT factions FROM council_decisions WHERE kind = 'decision'").fetchone()[0] == '["CDU"]'
    store.close()


def test_frag_den_rat_schreibt_nur_belegtes_als_antrag():
    stadion = {"id": 20947, "title": STADION, "factions": ["SPD"], "outcome": "accepted"}
    eigen = {"id": 18256, "title": "Städtepartnerschaft (CDU-Fraktion vom 08.11.2023)",
             "factions": '["CDU"]', "outcome": "rejected"}
    kontext = qa._build_context([stadion, eigen])
    zeile_stadion, zeile_eigen = kontext.splitlines()
    assert "Antrag von" not in zeile_stadion
    assert "Anträge im TOP von (Antrag oder Änderungsantrag): SPD" in zeile_stadion
    assert "— Antrag von: CDU" in zeile_eigen
