"""Parser- und Store-Tests für die RIS-Stammdaten (Beratungsfolge, Personen,
Mitgliedschaften). Die HTML-Fixtures spiegeln die echten SessionNet-Strukturen
(an Live-Seiten verifiziert, Stand 2026-07)."""
from __future__ import annotations

from unittest.mock import patch

from bs4 import BeautifulSoup

from council import stammdaten
from council.store import CouncilStore


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class _FakeScraper:
    def __init__(self, html: str):
        self._html = html

    def _get(self, path, **params):
        return _soup(self._html)


# ---- Beratungsfolge (vo0053) -------------------------------------------------

_VO0053 = """
<div class="accordion">
  <div id="smcpanel1" class="card">
    <button data-target="#smcacchead1">10.06.2026 Sportausschuss TOP 8.1 &ouml;ffentlich - Kenntnisnahme
      <span class="smc-badges">1 Dok.</span></button>
    <div id="smcacchead1"><a href="si0057.php?__ksinr=4590&toselect=1">Zur Sitzung ...</a></div>
  </div>
  <div id="smcpanel2" class="card">
    <button data-target="#smcacchead2">29.06.2099 Rat TOP 12.1 &ouml;ffentlich</button>
    <div id="smcacchead2"><a href="si0057.php?__ksinr=9999">Zur Sitzung ...</a></div>
  </div>
  <div id="smcpanel3" class="card">
    <button data-target="#smcacchead3">05.05.2026 Verwaltungsausschuss nicht&ouml;ffentlich - Vorberatung</button>
    <div id="smcacchead3"></div>
  </div>
</div>
"""


def test_beratungsfolge_parses_stations():
    rows = stammdaten.fetch_beratungsfolge(_FakeScraper(_VO0053), 1)
    assert len(rows) == 3
    assert rows[0] == {"datum": "2026-06-10", "gremium": "Sportausschuss", "top": "8.1",
                       "is_public": True, "ergebnis": "Kenntnisnahme", "ksinr": 4590}
    # Geplante Station: kein Ergebnis, Datum in der Zukunft
    assert rows[1]["ergebnis"] is None and rows[1]["ksinr"] == 9999
    assert stammdaten.is_future(rows[1]["datum"])
    # Nichtöffentlich wird erkannt (auch ohne Sitzungs-Link)
    assert rows[2]["is_public"] is False and rows[2]["ksinr"] is None
    assert rows[2]["gremium"] == "Verwaltungsausschuss" and rows[2]["ergebnis"] == "Vorberatung"


# ---- Mandatsträger (kp0041) ---------------------------------------------------

_KP0041 = """
<table><tr><th>Name</th><th>Mitgliedschaft</th><th>bis</th></tr>
<tr><td><a href="pe0051.php?__kpenr=4">Hans-Henning Adler</a></td><td>BSW</td><td></td></tr>
<tr><td>Stadtrat Ohne Link</td><td></td><td></td></tr>
<tr><td><a href="pe0051.php?__kpenr=7">Erika Muster</a></td><td>SPD</td><td>bis 27.11.2023</td></tr>
</table>
"""


def test_mandatstraeger_rows_and_skips_unlinked():
    rows = stammdaten.fetch_mandatstraeger(_FakeScraper(_KP0041))
    assert [r["kpenr"] for r in rows] == [4, 7]
    assert rows[0] == {"kpenr": 4, "name": "Hans-Henning Adler", "fraktion": "BSW", "bis": None}
    assert rows[1]["bis"] == "2023-11-27"


# ---- Mitarbeit (kp0050) -------------------------------------------------------

_KP0050 = """
<table>
<tr><th>Gremium</th><th>Mitgliedschaft</th><th>Art der Mitarbeit</th><th>von</th><th>bis</th></tr>
<tr><td colspan="5">vom Rat</td></tr>
<tr><td><a href="kp0040.php?__kgrnr=22">Rat</a></td><td>BSW</td><td>Ratsmitglied</td>
    <td>01.11.1996</td><td>31.10.2021</td><td>von 01.11.1996 bis 31.10.2021</td></tr>
<tr><td>Verwaltungsausschuss</td><td>BSW</td><td>Beigeordnete/r</td>
    <td>13.11.2001</td><td></td><td>von 13.11.2001</td></tr>
</table>
"""


def test_person_mitarbeit_parses_memberships():
    rows = stammdaten.fetch_person_mitarbeit(_FakeScraper(_KP0050), 4)
    assert len(rows) == 2
    assert rows[0] == {"kgrnr": 22, "gremium": "Rat", "rolle": "Ratsmitglied",
                       "von": "1996-11-01", "bis": "2021-10-31"}
    # Gremium ohne eigene Seite: kein kgrnr, laufend (bis=None)
    assert rows[1]["kgrnr"] is None and rows[1]["bis"] is None
    assert rows[1]["rolle"] == "Beigeordnete/r"


# ---- Store: Beratungen + Personen ---------------------------------------------

def test_store_beratungen_roundtrip_and_replace(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_beratungen(10, [
        {"datum": "2026-06-25", "gremium": "Betriebsausschuss", "top": "5",
         "is_public": True, "ergebnis": "Vorberatung", "ksinr": 4679},
        {"datum": "2099-06-29", "gremium": "Rat", "top": "12.1",
         "is_public": True, "ergebnis": None, "ksinr": None},
    ])
    rows = store.get_beratungen(10)
    assert [r["gremium"] for r in rows] == ["Betriebsausschuss", "Rat"]
    assert rows[0]["ergebnis"] == "Vorberatung" and rows[1]["ergebnis"] is None
    # Replace-Semantik: erneutes Speichern ersetzt vollständig
    store.save_beratungen(10, [{"datum": "2099-06-29", "gremium": "Rat", "top": "12.1",
                                "is_public": True, "ergebnis": "Entscheidung", "ksinr": 4695}])
    rows = store.get_beratungen(10)
    assert len(rows) == 1 and rows[0]["ergebnis"] == "Entscheidung"
    # Rescan-Kandidaten: offene künftige Station → kvonr taucht auf
    assert 10 in store.kvonrs_for_beratungen_rescan()
    store.close()


def test_store_persons_memberships_and_slug_match(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_person(4, "Hans-Henning Adler", "BSW")
    store.save_memberships(4, [
        {"kgrnr": 22, "gremium": "Rat", "rolle": "Ratsmitglied", "von": "1996-11-01", "bis": "2021-10-31"},
        {"kgrnr": 22, "gremium": "Rat", "rolle": "Ratsmitglied", "von": "2022-12-19", "bis": None},
    ])
    # Slug-Match über Titel-Varianten hinweg (Anwesenheit schreibt teils "Dr. ...")
    p = store.person_stammdaten_for_names(["Dr. Hans-Henning Adler"])
    assert p and p["kpenr"] == 4 and p["fraktion_aktuell"] == "BSW"
    # Laufende Mitgliedschaft zuerst
    assert p["memberships"][0]["bis"] is None
    assert store.person_stammdaten_for_names(["Unbekannte Person"]) is None
    stats = store.stammdaten_stats()
    assert stats["personen"] == 1 and stats["mitgliedschaften"] == 2
    store.close()


def test_member_detail_faction_timeline(tmp_path):
    """Fraktions-Verlauf aus der Anwesenheit: Linke→BSW ergibt zwei Phasen,
    ein einzelner Ausreißer dazwischen wird geglättet."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        sessions = [(1, "2023-01-01"), (2, "2023-06-01"), (3, "2024-01-01"),
                    (4, "2024-06-01"), (5, "2024-09-01")]
        for ksinr, d in sessions:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                "VALUES (?, 'Rat', ?, '18:00', '', '')", (ksinr, d))
        parties = ["Die Linke", "Die Linke", "SPD", "BSW", "BSW"]  # SPD = Protokoll-Ausreißer? nein: echter Wechselpunkt-Test unten
        for (ksinr, _), p in zip(sessions, parties):
            store._conn.execute(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, 'Hans-Henning Adler', ?, 'mitglied', NULL)", (ksinr, p))
    detail = store.member_detail(store._person_slug("Hans-Henning Adler"))
    tl = detail["faction_timeline"]
    # Ausreißer (eine einzelne SPD-Sitzung) liegt zwischen zwei VERSCHIEDENEN
    # Fraktionen → bleibt stehen; Phasenfolge Linke → SPD → BSW
    assert [t["party"] for t in tl] == ["Die Linke", "SPD", "BSW"]
    # Glättung: einzelner Falschschrieb ZWISCHEN zwei gleichen Phasen fliegt raus
    with store._conn:
        store._conn.execute("UPDATE council_attendance SET party='Die Linke' WHERE ksinr=4")
        store._conn.execute("UPDATE council_attendance SET party='Die Linke' WHERE ksinr=5")
    detail = store.member_detail(store._person_slug("Hans-Henning Adler"))
    tl = detail["faction_timeline"]
    assert [t["party"] for t in tl] == ["Die Linke"]
    assert tl[0]["first"] == "2023-01-01" and tl[0]["last"] == "2024-09-01"
    store.close()


def test_member_party_is_latest_not_most_frequent(tmp_path):
    """Der Lükermann-Fall: mehr FDP-Sitzungen früher, weniger Volt-Sitzungen
    zuletzt → angezeigt wird die LETZTE aktive Fraktion (Volt), nicht die
    häufigste (FDP) — in der Personen-Liste UND im Detail."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        sessions = [(1, "2022-01-01"), (2, "2022-06-01"), (3, "2023-01-01"),
                    (4, "2023-06-01"), (5, "2024-01-01"), (6, "2024-06-01")]
        for ksinr, d in sessions:
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                "VALUES (?, 'Rat', ?, '18:00', '', '')", (ksinr, d))
        parties = ["FDP", "FDP", "FDP", "FDP", "Volt", "Volt"]  # 4× FDP > 2× Volt
        for (ksinr, _), p in zip(sessions, parties):
            store._conn.execute(
                "INSERT INTO council_attendance (ksinr, name, party, role, note) "
                "VALUES (?, 'Jens Lükermann', ?, 'mitglied', NULL)", (ksinr, p))
    [m] = store.list_members()
    assert m["party"] == "Volt"
    detail = store.member_detail(store._person_slug("Jens Lükermann"))
    assert detail["party"] == "Volt"
    # Sitzung ohne Fraktionsangabe NACH dem Wechsel ändert nichts (kein Rückfall):
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (7, 'Rat', '2024-09-01', '18:00', '', '')")
        store._conn.execute(
            "INSERT INTO council_attendance (ksinr, name, party, role, note) "
            "VALUES (7, 'Jens Lükermann', NULL, 'mitglied', NULL)")
    [m] = store.list_members()
    assert m["party"] == "Volt"
