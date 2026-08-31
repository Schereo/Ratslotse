"""Der Weg eines Haushalts durch den Rat (``CouncilStore.haushalt_weg``).

Die Fälle sind keine erfundenen Kunststücke — jeder steht so im Bestand:

- Die Vorlagen eines Jahrgangs heißen nicht einheitlich („Haushalt 2026",
  „Haushaltsentwurf 2024", „HH 2020"). Wer nur nach einer Schreibweise sucht,
  verliert stillschweigend einen Fachausschuss.
- Zwei Vorlagen tragen die **falsche** Jahreszahl im Titel: 22/0824 heißt
  „Haushalt 2022 …", wurde aber im November 2022 beraten und gehört zur Runde
  2023. Ohne die Fensterregel zieht so ein Ausreißer den Zeitraum der
  Fachausschuss-Runde um ein volles Jahr auf.
- Das Ergebnis steht als Suffix am Tagesordnungspunkt („… Beschluss: geändert
  beschlossen"), mal mit angehängter Stimmenzählung, mal ohne.
"""
import pytest

from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(str(tmp_path / "council.sqlite"))
    yield s
    s.close()


def sitzung(store, ksinr, gremium, datum, tops):
    """Eine Sitzung samt Tagesordnung. `tops` = [(nummer, titel, kvonr)]."""
    store.save_session(CouncilSession(
        ksinr=ksinr, committee=gremium, session_date=datum,
        session_time="17:00", location="Rathaus",
        agenda_items=[AgendaItem(item_number=n, title=t, kvonr=k) for n, t, k in tops],
    ))


def vorlage(store, kvonr, nr, titel):
    store.save_vorlage({"kvonr": kvonr, "template_number": nr, "title": titel})


def beratung(store, kvonr, datum, gremium, rolle, ksinr, top):
    store.save_beratungen(kvonr, [{"datum": datum, "gremium": gremium, "top": top,
                                   "is_public": True, "result": rolle, "ksinr": ksinr}])


def runde_2026(store):
    """Die Runde des Haushalts 2026, so wie sie im Bestand liegt: Entwurf im
    Oktober, ein Fachausschuss, zweimal vertagt, Beschluss erst im Februar."""
    vorlage(store, 100, "25/0580", "Haushalt 2026 - Verwaltungsentwurf")
    vorlage(store, 101, "25/0637", "Haushalt 2026 - Verwaltungsentwurf - Teilhaushalt 12 Schule")
    vorlage(store, 102, "25/0667", "Haushalt 2026 -Beschluss")

    sitzung(store, 1, "Ausschuss für Finanzen und Beteiligungen", "2025-10-01",
            [("Ö 5", "Haushalt 2026 - Verwaltungsentwurf Beschluss: zur Kenntnis genommen", 100)])
    sitzung(store, 2, "Schulausschuss", "2025-11-11",
            [("Ö 4", "Teilhaushalt 12 Beschluss: zur Kenntnis genommen", 101)])
    sitzung(store, 3, "Rat", "2025-12-15",
            [("Ö 5", "Haushalt 2026 - Beschluss Beschluss: zurückgestellt/abgesetzt", 102)])
    sitzung(store, 4, "Rat", "2026-02-09",
            [("Ö 6", "Haushalt 2026 -Beschluss Beschluss: geändert beschlossen "
                     "Abstimmung: Ja: 30, Nein: 20", 102)])

    beratung(store, 100, "2025-10-01", "Ausschuss für Finanzen und Beteiligungen",
             "Kenntnisnahme", 1, "5")
    beratung(store, 101, "2025-11-11", "Schulausschuss", "Kenntnisnahme", 2, "4")
    store.save_beratungen(102, [
        {"datum": "2025-12-15", "gremium": "Rat", "top": "5", "is_public": True,
         "result": "Entscheidung", "ksinr": 3},
        {"datum": "2026-02-09", "gremium": "Rat", "top": "6", "is_public": True,
         "result": "Entscheidung", "ksinr": 4},
    ])


def test_runde_hat_einbringung_fachausschuesse_und_stationen(store):
    runde_2026(store)
    [r] = store.haushalt_weg()

    assert r["year"] == 2026
    assert r["template_number"] == "25/0667"

    # Die Einbringung ist die früheste Beratung einer Entwurfs-Vorlage.
    assert r["einbringung"]["datum"] == "2025-10-01"
    assert r["einbringung"]["gremium"] == "Ausschuss für Finanzen und Beteiligungen"
    # Die TOP-Nummer kommt vollständig aus der Tagesordnung („Ö 5", nicht „5“) —
    # sonst zeigt der Link auf der Sitzungsseite auf den falschen Punkt.
    assert r["einbringung"]["top"] == "Ö 5"

    assert r["fachausschuesse"] == {
        "von": "2025-11-11", "bis": "2025-11-11", "count": 1,
        "gremien": ["Schulausschuss"],
    }

    assert [(s["datum"], s["gremium"], s["result"]) for s in r["stationen"]] == [
        ("2025-12-15", "Rat", "zurückgestellt/abgesetzt"),
        ("2026-02-09", "Rat", "geändert beschlossen"),
    ]


def test_ergebnis_ohne_die_angehaengte_stimmenzaehlung(store):
    """Am TOP hängt mal eine Zählung, mal nicht — sie gehört nicht ins Ergebnis."""
    runde_2026(store)
    [r] = store.haushalt_weg()
    assert r["stationen"][-1]["result"] == "geändert beschlossen"


def test_falsch_betitelte_vorlage_verschiebt_den_zeitraum_nicht(store):
    """22/0824 heißt „Haushalt 2022 …" und wurde im November 2022 beraten.

    Ohne die Fensterregel (Einbringung … letzte Beschluss-Station) risse dieser
    eine Ausreißer den Zeitraum der Fachausschuss-Runde 2026 um ein Jahr auf.
    """
    runde_2026(store)
    vorlage(store, 199, "26/0824", "Haushalt 2026 - Verwaltungsentwurf - Teilhaushalt 12 Schule")
    sitzung(store, 9, "Schulausschuss", "2026-11-08", [("Ö 3", "Teilhaushalt 12", 199)])
    beratung(store, 199, "2026-11-08", "Schulausschuss", "Kenntnisnahme", 9, "3")

    [r] = store.haushalt_weg()
    assert r["fachausschuesse"]["bis"] == "2025-11-11"
    assert r["fachausschuesse"]["count"] == 1


@pytest.mark.parametrize("titel", [
    "Haushalt 2026 - Verwaltungsentwurf - Teilhaushalt 12 Schule",
    "Haushaltsentwurf 2026 Verwaltungsentwurf -Teilhaushalt 02 Personal",
    "HH 2026– Verwaltungsentwurf THH 12 Schule und Bildung - Bericht",
])
def test_schreibweisen_des_titels(store, titel):
    """Drei Schreibweisen, ein Jahrgang — alle drei stehen so im Bestand."""
    runde_2026(store)
    store._conn.execute("UPDATE council_vorlagen SET title = ? WHERE kvonr = 101", (titel,))
    [r] = store.haushalt_weg()
    assert r["fachausschuesse"]["gremien"] == ["Schulausschuss"]


def test_haushaltsplan_einer_stiftung_ist_keine_runde(store):
    """„Haushaltsplan der Klävemann-Stiftung 2026" fängt zwar mit „Haushalt" an,
    trägt hinter dem Wort aber keine Jahreszahl — und ist kein Jahrgang."""
    runde_2026(store)
    vorlage(store, 300, "25/0900", "Haushaltsplan der Klävemann-Stiftung 2026 - Beschluss")
    sitzung(store, 11, "Rat", "2026-02-09", [("Ö 6.1", "Klävemann Beschluss: ungeändert beschlossen", 300)])
    beratung(store, 300, "2026-02-09", "Rat", "Entscheidung", 11, "6.1")

    assert [r["year"] for r in store.haushalt_weg()] == [2026]


def test_ohne_sammelvorlage_keine_runde(store):
    """Das Haushaltsjahr 2018 wurde vor dem Beginn unseres Bestands beschlossen:
    Es gibt einen Entwurf, aber keine Beschlussvorlage — also keine Runde."""
    vorlage(store, 400, "17/0500", "Haushalt 2018 - Verwaltungsentwurf")
    sitzung(store, 20, "Ausschuss für Finanzen und Beteiligungen", "2017-10-04",
            [("Ö 5", "Entwurf", 400)])
    beratung(store, 400, "2017-10-04", "Ausschuss für Finanzen und Beteiligungen",
             "Kenntnisnahme", 20, "5")

    assert store.haushalt_weg() == []


def test_votum_kommt_aus_dem_kernhaushalts_beschluss(store):
    """Die Sammelvorlage bündelt Stiftungen und Eigenbetriebe mit; abgestimmt
    wird über die Haushaltssatzung. Der Beschluss trägt den Jahrgang im Titel
    und ist deshalb über die Sitzung zuzuordnen — ohne TOP-Nummern zu raten."""
    runde_2026(store)
    store._conn.execute(
        "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, "
        "outcome, vote, no_votes) VALUES (4, 5, 'decision', '6.5', "
        "'Haushaltssatzung und Haushaltsplan 2026 (Kernhaushalt)', 'angenommen', "
        "'mehrheitlich', 20)")
    store._conn.commit()

    [r] = store.haushalt_weg()
    assert r["stationen"][0]["votum"] is None            # die vertagte Sitzung
    assert r["stationen"][-1]["votum"]["outcome"] == "angenommen"
    assert r["stationen"][-1]["votum"]["no_votes"] == 20


def test_fremdes_haushaltsjahr_im_votum_zaehlt_nicht(store):
    """Ein Beschluss zum Haushalt 2025 in derselben Sitzung darf nicht als
    Votum der Runde 2026 durchgehen."""
    runde_2026(store)
    store._conn.execute(
        "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome) "
        "VALUES (4, 5, 'decision', '6.4', "
        "'Haushaltssatzung und Haushaltsplan 2025 (Kernhaushalt)', 'angenommen')")
    store._conn.commit()

    [r] = store.haushalt_weg()
    assert r["stationen"][-1]["votum"] is None


def test_jahr_grenzt_ein(store):
    runde_2026(store)
    vorlage(store, 500, "24/0762", "Haushalt 2025 -Beschluss")
    sitzung(store, 30, "Rat", "2024-12-16",
            [("Ö 5", "Haushalt 2025 Beschluss: geändert beschlossen", 500)])
    beratung(store, 500, "2024-12-16", "Rat", "Entscheidung", 30, "5")

    assert [r["year"] for r in store.haushalt_weg()] == [2025, 2026]
    assert [r["year"] for r in store.haushalt_weg(2026)] == [2026]
