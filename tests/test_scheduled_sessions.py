"""Terminierte Sitzungen ohne veröffentlichte Tagesordnung (RIS-Kalender).

SessionNet verlinkt eine Sitzung erst, wenn ihre Tagesordnung online ist —
vorher steht sie nur als Text im Kalender (kein __ksinr im HTML). Diese Tests
sichern das Kalender-Parsing und den Merge in upcoming_sessions ab.
"""
from __future__ import annotations

from datetime import date, timedelta

from bs4 import BeautifulSoup

from council.scraper import (
    AgendaItem,
    CouncilSession,
    _extract_rss_scheduled,
    _extract_scheduled,
    _extract_session_ids,
)
from council.store import CouncilStore

# Reales Markup von buergerinfo.oldenburg.de/si0040.php (21.07.2026), gekürzt:
# eine Zeile ohne Link (Tagesordnung folgt), eine mit Link (veröffentlicht).
CALENDAR_HTML = """
<table>
<tr>
  <td class="smc-table-cell-block-991 smc-table-cell-heading smc_fct_day_991"><span class="weekday">13</span> <a title="Donnerstag" class="weekday">Do</a></td>
  <td class="smc-t-cn991 smc_fct_day"><span class="weekday">13</span></td>
  <td class="smc-t-cn991 smc_fct_daytext"><a title="Donnerstag" class="weekday">Do</a></td>
  <td data-label="Sitzung" class="smc-t-cl991 silink"><div class="smc-el-h ">Ausschuss f&uuml;r Stadtgr&uuml;n, Umwelt und Klima<!--SMCINFO:si.bi --></div><ul class="list-inline smc-detail-list"><li class="list-inline-item">17:00&nbsp;Uhr</li><li class="list-inline-item">Alte Fleiwa, Industriestra&szlig;e 1d, Sitzungssaal 1/2</li></ul></td>
  <td data-label="Mandant" class="smc-t-cl991 pagel pagel3"></td>
  <td data-label="Dokumente" class="smc-t-cl991 sidocs"></td>
</tr>
<tr>
  <td class="smc-t-cn991 smc_fct_day"><span class="weekday">27</span></td>
  <td class="smc-t-cn991 smc_fct_daytext"><a title="Donnerstag" class="weekday">Do</a></td>
  <td data-label="Sitzung" class="smc-t-cl991 silink"><div class="smc-el-h "><a href="si0057.php?__ksinr=4711">Rat der Stadt</a></div><ul class="list-inline smc-detail-list"><li class="list-inline-item">16:00&nbsp;Uhr</li><li class="list-inline-item">Kulturzentrum PFL, Peterstra&szlig;e 3</li></ul></td>
</tr>
</table>
"""


def test_extract_scheduled_parses_rows_without_links():
    soup = BeautifulSoup(CALENDAR_HTML, "html.parser")
    rows = _extract_scheduled(soup, 2026, 8)
    assert len(rows) == 2
    first = rows[0]
    assert first.committee == "Ausschuss für Stadtgrün, Umwelt und Klima"
    assert first.session_date == "2026-08-13"
    assert first.session_time == "17:00"
    assert first.location == "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2"
    # Zeile MIT Link wird ebenfalls erfasst (Merge dedupliziert später).
    assert rows[1].committee == "Rat der Stadt"
    assert rows[1].session_date == "2026-08-27"
    # Verlinkte IDs kommen weiterhin aus den hrefs.
    assert _extract_session_ids(soup) == [4711]


# Reales Format des RIS-RSS-Feeds (rssfeed.php?filter=s, 21.07.2026) — er
# listet auch nichtöffentliche Gremien, die die Kalenderansicht auslässt.
RSS_XML = """<?xml version="1.0" encoding="UTF-8"?> <rss version="0.91"> <channel>
<title>Ratsinformationen der Stadt Oldenburg</title>
<item> <title>Sitzung: Verwaltungsausschuss 17.08.2026</title>
<description>Gremium: Verwaltungsausschuss Datum: 17.08.2026 Zeit: 17:00 Uhr Ort: Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2</description>
<category>Sitzungen</category> </item>
<item> <title>Vorlage: 26/0815</title> <description>Irgendeine Vorlage</description> </item>
</channel> </rss>"""


def test_extract_rss_scheduled():
    rows = _extract_rss_scheduled(RSS_XML)
    assert len(rows) == 1
    assert rows[0].committee == "Verwaltungsausschuss"
    assert rows[0].session_date == "2026-08-17"
    assert rows[0].session_time == "17:00"
    assert rows[0].location == "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2"


def _scheduled(committee: str, day_offset: int, time_: str = "17:00"):
    from council.scraper import ScheduledSession
    return ScheduledSession(
        committee=committee,
        session_date=(date.today() + timedelta(days=day_offset)).isoformat(),
        session_time=time_,
        location="Alte Fleiwa",
    )


def test_upcoming_sessions_merges_scheduled(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    future = (date.today() + timedelta(days=30)).isoformat()
    store.save_session(CouncilSession(
        ksinr=100, committee="Verkehrsausschuss", session_date=future,
        session_time="17:00", location="Fleiwa",
        agenda_items=[AgendaItem(item_number="Ö 1", title="Radweg")],
    ))
    store.replace_scheduled_sessions([
        _scheduled("Kulturausschuss", 20),
        # Gleiches Gremium + Datum wie die echte Sitzung → wird verdeckt.
        _scheduled("Verkehrsausschuss", 30),
    ])

    rows = store.upcoming_sessions()
    assert [(r["committee"], r["ksinr"], r["n_items"]) for r in rows] == [
        ("Kulturausschuss", None, 0),
        ("Verkehrsausschuss", 100, 1),
    ]
    store.close()


def test_replace_scheduled_sessions_is_full_swap(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store.replace_scheduled_sessions([_scheduled("Kulturausschuss", 10)])
    store.replace_scheduled_sessions([_scheduled("Jugendhilfeausschuss", 12)])
    rows = store.upcoming_sessions()
    assert [r["committee"] for r in rows] == ["Jugendhilfeausschuss"]
    # Vergangene Termine tauchen nicht auf.
    store.replace_scheduled_sessions([_scheduled("Kulturausschuss", -3)])
    assert store.upcoming_sessions() == []
    store.close()


# ---- „Diese Woche im Rat" als Vorschau (Design 11d/12, 12.08.26) ----------

def _vorschau_store(tmp_path):
    """Eine Sitzung nächste Woche mit gemischter Tagesordnung."""
    store = CouncilStore(tmp_path / "v.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (1, 'Umweltausschuss', date('now','+2 day'), "
            "'17:00', '', datetime('now'))")
        punkte = [
            ("Ö 1", "Feststellung der Beschlussfähigkeit", None, None),
            ("Ö 2", "Genehmigung des Protokolls Nr. 03/26", None, None),
            ("Ö 3", "Umsetzung der Ratsbeschlüsse zum Fliegerhorst (FDP-Fraktion vom 28.07.2026)", "26/1", 100),
            ("Ö 4", "Aktionswochen - Bericht", "26/2", 200),
            ("Ö 5", "Änderung der Satzung des Jugendamtes - Beschluss", "26/3", 300),
            ("Ö 6", "Berufung Beratendes Mitglied im Ausschuss", "26/4", 400),
        ]
        store._conn.executemany(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, kvonr, is_public) "
            "VALUES (1, ?, ?, ?, ?, 1)", punkte)
        store._conn.execute(
            "INSERT INTO council_entities (id, slug, name, kind, n) "
            "VALUES (1, 'fliegerhorst', 'Fliegerhorst', 'ort', 166)")
        # Behandlungsart je Punkt aus der Beratungsfolge
        store._conn.executemany(
            "INSERT INTO council_deliberations (kvonr, date, committee, result, fetched_at) "
            "VALUES (?, date('now','+2 day'), 'Umweltausschuss', ?, datetime('now'))",
            [(200, "Kenntnisnahme"), (300, "Entscheidung"), (400, "Entscheidung")])
    return store


def test_wochenvorschau_waehlt_nach_wichtigkeit(tmp_path):
    """Die Karte trägt fünf Zeilen, die Woche bringt gut dreißig inhaltliche
    Punkte — „hat eine Kurzfassung" ist als Auswahl zu wenig (Tims Befund
    12.08.). Gewichtet wird nach Behandlungsart (als Schranke), Bindungswirkung,
    Gremium und Fraktionsantrag; Gremien-Personalien werden gedämpft."""
    store = _vorschau_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=99)
        title = [p["title"][:30] for p in d["items"]]
        # Formalien fliegen raus.
        assert not any("Beschlussfähigkeit" in t for t in title)
        assert not any("Genehmigung des Protokolls" in t for t in title)

        rang = {p["title"][:12]: p["rang"] for p in d["items"]}
        # Die Satzungsänderung (Entscheidung, bindend) schlägt den
        # Fraktionsantrag zu einem bekannten Thema — genau andersherum als
        # bis zum 15.08.2026. Damals sammelte ein Bericht über Nebensignale
        # (Antrag + bekannter Name) mehr Punkte als eine Entscheidung; auf der
        # Karte stand deshalb ein Museumsbericht über einer Satzungsänderung.
        assert rang["Änderung der"] > rang["Umsetzung de"]
        # Die Behandlungsart ist eine Schranke: Ein Bericht zur Kenntnis kommt
        # nicht über den Deckel, auch wenn er alle Nebensignale einsammelt
        # (Fraktionsantrag, bekanntes Thema, Kurzfassung, Vorlage) — das war
        # der Weg, auf dem der Museumsbericht nach oben rutschte.
        bericht = [{"title": "Bildende Kunst im Stadtmuseum (CDU-Fraktion vom 07.07.2026)",
                    "behandlung": "Kenntnisnahme", "vorgeschichte": 1,
                    "summary": "Ein Satz dazu.", "template_number": "26/9",
                    "committee": "Kulturausschuss"}]
        store._punkte_bewerten(bericht)
        assert bericht[0]["rang"] <= 2.5
        assert bericht[0]["wichtig"] <= store.WICHTIG_MINDEST
        # Unter der Schwelle bleiben draußen: der reine Kenntnisnahme-Bericht
        # und die Gremien-Personalie (formal „Entscheidung", aber Routine).
        assert not any("Aktionswochen" in t for t in title)
        assert not any("Berufung" in t for t in title)
        # Ohne die Dämpfung stünde die Personalie gleichauf mit der Satzung —
        # das war der Befund, der die Dämpfung ausgelöst hat.
        roh = [{"title": "Berufung Beratendes Mitglied im Ausschuss",
                "behandlung": "Entscheidung", "vorgeschichte": 0,
                "summary": None, "template_number": "26/4"}]
        store._punkte_bewerten(roh)
        assert roh[0]["wichtig"] < store.WICHTIG_MINDEST
    finally:
        store.close()


def test_wochenvorschau_liefert_weitere_punkte_zum_aufklappen(tmp_path):
    """„x weitere Punkte" klappt in der Karte auf statt wegzunavigieren (Tims
    Wunsch 18.08.) — dafür liefert die Vorschau die übrigen relevanten Punkte
    je Sitzung mit, nach Rang sortiert und ohne die schon gezeigten."""
    store = _vorschau_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=1)
        assert len(d["items"]) == 1
        weitere = d["further_per_session"].get(1, [])
        gezeigt = {(p["ksinr"], p["item_number"]) for p in d["items"]}
        assert weitere, "über der Schwelle liegt mehr als ein Punkt"
        assert all((w["ksinr"], w["item_number"]) not in gezeigt for w in weitere)
        assert all(w["title"] for w in weitere)
        # Ohne Deckel wandern dieselben Punkte in die Auswahl — nichts doppelt.
        voll = store.wochenvorschau(max_punkte=99)
        assert not voll["further_per_session"].get(1)
    finally:
        store.close()


def test_wochenvorschau_deckelt_strassen_formalakte(tmp_path):
    """Die Widmung „Im Technologiepark" stand als „wichtig" auf der Karte —
    der Formalakt-Deckel greift lesezeitig, auch über gespeicherte
    Tragweite-Bewertungen hinweg."""
    store = _vorschau_store(tmp_path)
    try:
        with store._conn:
            store._conn.execute(
                "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, kvonr, is_public) "
                "VALUES (1, 'Ö 7', 'Widmung der Straße \"Im Technologiepark\"', '26/7', 700, 1)")
            # Gespeicherte LLM-Fehlbewertung: 70 von 100.
            store.save_agenda_impact(1, "Ö 7", 70, "Klingt nach Infrastruktur")
        d = store.wochenvorschau(max_punkte=99)
        widmung = [p for p in d["items"] if "Widmung" in p["title"]]
        assert not widmung, "Formalakt darf nicht in die Auswahl"
        assert not any("Widmung" in w["title"]
                       for w in d["further_per_session"].get(1, []))
    finally:
        store.close()


def test_wochenvorschau_ohne_sitzungen_ist_ehrlich_leer(tmp_path):
    """Sommerpause: keine Sitzung, keine Ausgabe — die Karte fällt weg, statt
    einen Leerzustand zu zeigen."""
    store = CouncilStore(tmp_path / "leer.sqlite")
    try:
        d = store.wochenvorschau()
        assert d["found"] is False and d["items"] == [] and d["sessions"] == []
    finally:
        store.close()


# ---- „Die Woche im Rat" — eine Karte statt zwei (Design 14, 14.08.26) ------

def test_woche_traegt_jede_sitzung_mit_ort_und_punktzahl(tmp_path):
    """Design 14: Die Karte ersetzt auch „Nächste Sitzungen". Dafür braucht
    jede Sitzung eine Zeile — mit Ort (Desktop) und der Punktzahl, aus der die
    ruhige Zeile „nicht öffentlich" ableitet."""
    store = _vorschau_store(tmp_path)
    try:
        with store._conn:
            # Eine zweite Sitzung ganz ohne öffentliche Punkte.
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, "
                "session_time, location, fetched_at) VALUES (2, 'Verwaltungsausschuss', "
                "date('now','+3 day'), '18:00', 'Kleiner Saal', datetime('now'))")
            store._conn.execute(
                "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
                "VALUES (2, 'N 1', 'Grundstück', 0)")
        d = store.wochenvorschau()
        nach_ksinr = {s["ksinr"]: s for s in d["sessions"]}
        assert set(nach_ksinr) == {1, 2}
        assert nach_ksinr[2]["location"] == "Kleiner Saal"
        # Nicht öffentlich = kein einziger öffentlicher Punkt.
        assert nach_ksinr[2]["n_items"] == 0
        # Die Karte hat Inhalt, sobald eine Sitzung ansteht — auch wenn diese
        # zweite gar keinen relevanten Punkt beisteuert.
        assert d["found"] is True
    finally:
        store.close()


def test_eigenes_thema_schlaegt_die_rang_schwelle(tmp_path):
    """Wer ein eigenes Thema trifft, ist relevant — auch wenn die allgemeine
    Bewertung den Punkt aussortiert hätte. „Aktionswochen - Bericht" fällt
    sonst als reine Kenntnisnahme durch (s. Test oben)."""
    store = _vorschau_store(tmp_path)
    try:
        ohne = store.wochenvorschau()
        assert not any("Aktionswochen" in p["title"] for p in ohne["items"])

        mit = store.wochenvorschau(meine={1: [{"item_number": "Ö 4", "topic_name": "Radverkehr"}]})
        treffer = [p for p in mit["items"] if "Aktionswochen" in p["title"]]
        assert len(treffer) == 1
        assert treffer[0]["topic_name"] == "Radverkehr"
        # Und er steht vorn: eigenes Thema schlägt jeden Fremdpunkt.
        assert treffer[0]["top"] is True
        assert mit["matches_total"] == 1
    finally:
        store.close()


def test_genau_ein_punkt_ist_hervorgehoben(tmp_path):
    """Design 14a hebt EINEN Punkt der ganzen Karte hervor und gibt ihm die
    Kurzbegründung — nicht einen je Sitzung."""
    store = _vorschau_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=99)
        assert sum(1 for p in d["items"] if p["top"]) == 1
    finally:
        store.close()


def test_relevant_je_sitzung_zaehlt_vor_dem_deckel(tmp_path):
    """Prinzip ② der Dichte-Matrix: verkürzen ja, verschweigen nein. Das
    Abzeichen („3 für dich") und die Restzeile („1 weiterer Punkt") brauchen
    die Zahl VOR dem Anzeige-Deckel."""
    store = _vorschau_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=1)
        assert len(d["items"]) == 1
        # Gezählt wird, was relevant IST — nicht, was gezeigt wird. Genau aus
        # dieser Differenz entsteht die Restzeile „n weitere Punkte".
        assert d["relevant_per_session"][1] > len(d["items"])
    finally:
        store.close()


def test_bericht_der_verwaltung_ist_nur_allein_eine_formalie(tmp_path):
    """„- Bericht der Verwaltung" ist ein ZUSATZ, kein Punkt: Er hängt an den
    spannendsten Titeln der Woche. Ein aufs Zeilenende verankertes Muster warf
    neun inhaltliche Punkte weg, darunter fast alle Fraktionsanträge
    (gemessen 12.08., Tims Nachfrage nach weiteren Kandidaten)."""
    store = CouncilStore(tmp_path / "f.sqlite")
    try:
        formalie = store._FORMALIE_RE
        # Der alleinstehende Sammelpunkt bleibt Formalie …
        assert formalie.search("Bericht der Verwaltung")
        assert formalie.search("  Berichte der Verwaltung  ")
        # … der Zusatz an einem echten Punkt nicht.
        for title in (
            "Ermittlungen Abfallentsorgung Fliegerhorst (CDU-Fraktion vom 14.07.2026) - Bericht der Verwaltung",
            "Bekämpfung des Rattenbefalls in der Stadt Oldenburg (FDP-Fraktion) - Bericht der Verwaltung",
            "Vorhabenbezogener Bebauungsplan Nr. 81: Vorstellung - Bericht der Verwaltung",
        ):
            assert not formalie.search(title), title
    finally:
        store.close()


# ---- Vorlagenart, Unterpunkt-Bündelung, Themen-Zählung (19.08.26) ---------

def _gruppen_store(tmp_path):
    """Eine Sitzung mit BEIDEN Sorten Überschrift: einem echten Vorhaben mit
    zwei Stationen und einer Sammel-Rubrik mit unabhängigen Anträgen."""
    store = CouncilStore(tmp_path / "g.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (7, 'Bauausschuss', date('now','+2 day'), "
            "'17:00', '', datetime('now'))")
        punkte = [
            ("Ö 1", "Feststellung der Beschlussfähigkeit", None, None),
            # Echtes Vorhaben: „Meerweg" steht in beiden Unterpunkten.
            ("Ö 5", "Bauleitplanung Meerweg", None, None),
            ("Ö 5.1", "Änderung 5 des Bebauungsplanes 534 (Meerweg) - Aufstellungsbeschluss", "26/1", 101),
            ("Ö 5.2", "Änderung 5 des Bebauungsplanes 534 (Meerweg) - Grundzüge der Planung", "26/2", 102),
            # Sammel-Rubrik: die Anträge haben nichts miteinander zu tun.
            ("Ö 6", "Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder", None, None),
            ("Ö 6.1", "Ersatzneubau Brücke Tweelbäker See (CDU-Fraktion vom 16.07.2026)", "26/3", 103),
            ("Ö 6.2", "Ausbau der Fahrradabstellanlagen (SPD-Fraktion vom 10.06.2026)", "26/4", 104),
        ]
        store._conn.executemany(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, kvonr, is_public) "
            "VALUES (7, ?, ?, ?, ?, 1)", punkte)
        store._conn.executemany(
            "INSERT INTO council_templates (kvonr, template_number, title, kind, fetched_at) "
            "VALUES (?, ?, '', ?, datetime('now'))",
            [(101, "26/1", "Beschlussvorlage"), (102, "26/2", "Berichtsvorlage"),
             (103, "26/3", "Beschlussvorlage"), (104, "26/4", "Beschlussvorlage")])
        store._conn.executemany(
            "INSERT INTO council_deliberations (kvonr, date, committee, result, fetched_at) "
            "VALUES (?, date('now','+2 day'), 'Bauausschuss', ?, datetime('now'))",
            [(101, "Vorberatung"), (102, "Kenntnisnahme"),
             (103, "Vorberatung"), (104, "Vorberatung")])
    return store


def test_eltern_nummer_liest_die_unterebene():
    assert CouncilStore._eltern_nummer("Ö 11.3") == "Ö 11"
    assert CouncilStore._eltern_nummer("N 19.2") == "N 19"
    assert CouncilStore._eltern_nummer("Ö 11.3.1") == "Ö 11.3"
    # Punkte ohne Unterebene haben keinen Elternpunkt.
    assert CouncilStore._eltern_nummer("Ö 11") is None
    assert CouncilStore._eltern_nummer("") is None


def test_stationen_eines_vorhabens_belegen_einen_platz(tmp_path):
    """Vier Stationen derselben Bauleitplanung sind EIN Vorhaben. Vorher
    besetzten sie alle drei Plätze der Sitzung, und die Karte zeigte dreimal
    denselben Bebauungsplan mit unterschiedlichem Verfahrensschritt."""
    store = _gruppen_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=99)
        nummern = [p["item_number"] for p in d["items"]]
        # Genau eine der beiden Meerweg-Stationen kommt durch …
        assert len([n for n in nummern if n.startswith("Ö 5.")]) == 1
        meerweg = next(p for p in d["items"] if p["item_number"].startswith("Ö 5."))
        assert meerweg["gruppe_titel"] == "Bauleitplanung Meerweg"
        assert meerweg["gruppe_stationen"] == 2
        # … und die Überschrift selbst ist kein eigener Punkt.
        assert "Ö 5" not in nummern
    finally:
        store.close()


def test_sammelrubrik_buendelt_nicht(tmp_path):
    """„Anträge der Fraktionen …" ist eine Rubrik, kein Vorhaben: Ihre
    Unterpunkte behandeln verschiedene Themen und müssen einzeln antreten.
    Als Gruppe behandelt käme von elf Anträgen nur einer je auf die Karte."""
    store = _gruppen_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=99)
        antraege = [p for p in d["items"] if p["item_number"].startswith("Ö 6.")]
        assert len(antraege) == 2, "beide Anträge sind eigenständige Themen"
        assert all(p["gruppe_titel"] is None for p in antraege)
    finally:
        store.close()


def test_beschlussvorlage_haelt_die_kenntnisnahme_schranke_auf(tmp_path):
    """Die VBN-Tarifanpassung ist eine Beschlussvorlage, wird im Fachausschuss
    aber als „Kenntnisnahme" geführt, weil der Rat entscheidet. Die Schranke
    drückte sie auf 13 von 100 — unter die Schwelle, während ein Umsatzsteuer-
    Bericht mit 30 auf der Karte stand (Tims Befund 19.08.26)."""
    store = CouncilStore(tmp_path / "s.sqlite")
    try:
        gemeinsam = {"behandlung": "Kenntnisnahme", "vorgeschichte": 0,
                     "summary": "Ein Satz dazu.", "template_number": "26/1",
                     "committee": "Verkehrsausschuss"}
        punkte = [
            {**gemeinsam, "title": "VBN-Tarifanpassung 2027 - Beschluss",
             "kind": "Beschlussvorlage"},
            {**gemeinsam, "title": "Geplante Änderung der Verordnung über Parkgebühren - Bericht",
             "kind": "Berichtsvorlage"},
        ]
        store._punkte_bewerten(punkte)
        official_text, bericht = punkte
        assert official_text["wichtig"] >= store.WICHTIG_MINDEST, "kommt jetzt auf die Karte"
        assert official_text["wichtig"] > bericht["wichtig"], (
            "die Entscheidung schlägt den Bericht — vorher war es umgekehrt")
        # Der Bericht bleibt gedeckelt: Die Schranke gilt weiter, wo sie stimmt.
        assert bericht["rang"] <= 2.5
    finally:
        store.close()


def test_inhaltlich_je_sitzung_zaehlt_themen_nicht_zeilen(tmp_path):
    """Die Restzeile nannte bisher nur die weiteren RELEVANTEN Punkte („+ 1"),
    obwohl auf der Tagesordnung noch Dutzende Themen standen."""
    store = _gruppen_store(tmp_path)
    try:
        d = store.wochenvorschau(max_punkte=99)
        # Meerweg (2 Stationen → 1 Thema) + zwei eigenständige Anträge = 3.
        # Formalie und beide Überschriften zählen nicht mit.
        assert d["substantive_per_session"][7] == 3
    finally:
        store.close()


def test_top_nummern_sortieren_numerisch():
    """Lexikografisch stand „Ö 16.4" vor „Ö 5" und „Ö 10" vor „Ö 2" — die
    Karte listete ihre Punkte in einer Reihenfolge, die es auf der
    Tagesordnung nicht gibt."""
    nummern = ["Ö 16.4", "Ö 5", "Ö 10", "Ö 2", "Ö 16.10", "Ö 16.2"]
    assert sorted(nummern, key=CouncilStore._top_sortierung) == [
        "Ö 2", "Ö 5", "Ö 10", "Ö 16.2", "Ö 16.4", "Ö 16.10"]


def test_vorlagen_auszug_ueberspringt_den_briefkopf():
    """Die ersten ~300 Zeichen jeder Vorlage sind Briefkopf. Bei der
    Unfallstatistik 26/0602 endete der Auszug deshalb bei „bedauerlic" —
    direkt vor „nicht möglich", und das Modell hielt eine abgesagte
    Berichterstattung für einen Bericht mit Zahlen (Tims Befund 19.08.26)."""
    from council.impact import vorlagen_kern

    roh = ("Ausdruck vom: 17.07.2026\nSeite: 1/2\n \nAmt für Verkehr und Straßenbau "
           "Datum: 17.07.2026\nVorlagen-Nr.: 26/0602 Status: öffentlich\n \n"
           "Verkehrsunfallstatistik 2025 und Unfallhäufungsstellen im \n"
           "Stadtgebiet Oldenburg (FDP-Fraktion vom 19.06.2026)\n \n"
           "Beratungsfolge: Termin:\nVerkehrsausschuss 24.08.2026\n \n"
           "Anlass:\n \nDie FDP-Fraktion bittet mit Antrag vom 19.06.2026 die "
           "Verwaltung zu berichten.\n \nBericht:\n \nAus terminlichen Gründen ist "
           "es der Polizeiinspektion nicht möglich, am 24. August zu informieren.")
    kern = vorlagen_kern(roh)
    assert kern.startswith("Anlass:")
    assert "Ausdruck vom" not in kern and "Vorlagen-Nr." not in kern
    # Der entscheidende Satz liegt jetzt weit innerhalb des Auszugs.
    from council.impact import MAX_EXCERPT_CHARS
    assert "nicht möglich" in kern[:MAX_EXCERPT_CHARS]
    # Ohne erkennbare Überschrift bleibt der Text unangetastet.
    assert vorlagen_kern("Nur ein Fließtext ohne Gliederung") == \
        "Nur ein Fließtext ohne Gliederung"
    assert vorlagen_kern(None) == ""


def test_weitere_punkte_tragen_ihre_erklaerung_mit(tmp_path):
    """Die Restliste lieferte `summary: None` — für die Website reichte beim
    Aufklappen der Titel. Der Instagram-Bot baut daraus aber ganze Karten, und
    die standen dadurch grundsätzlich ohne Erklärung da (Tims Befund
    19.08.26)."""
    store = _vorschau_store(tmp_path)
    try:
        with store._conn:
            store._conn.execute(
                # Auf „Ö 3", nicht auf den Spitzenpunkt: Mit max_punkte=1
                # steht der beste Punkt in `punkte`, die Restliste beginnt
                # dahinter.
                "INSERT INTO agenda_item_summaries (ksinr, item_number, summary, "
                "agenda_hash, created_at) VALUES (1, 'Ö 3', 'Der Rat soll seine "
                "Beschlüsse zum Fliegerhorst umsetzen.', 'h', datetime('now'))")
        d = store.wochenvorschau(max_punkte=1)
        weitere = d["further_per_session"].get(1, [])
        assert weitere, "über der Schwelle liegt mehr als ein Punkt"
        mit_text = [w for w in weitere if w["summary"]]
        assert mit_text, "mindestens ein Punkt der Restliste hat eine Kurzfassung"
        # Und der Tragweite-Grund ist als Feld vorhanden (Wert je nach Bestand).
        assert all("wichtig_grund" in w for w in weitere)
    finally:
        store.close()


# ---- Highlights je Sitzung für die Sitzungsliste (04.09.2026) ------------

def test_sitzungs_highlights_nutzt_dieselbe_schwelle_wie_die_woche(tmp_path):
    """Die Sitzungsliste sagte bisher nur „13 TOPs"; die Bewertung gab es
    längst, sie lief nur für die kommenden sieben Tage (Tims Frage 04.09.).
    Jetzt liefert der Store sie je Sitzung — gleiche Regeln, gleiche Schwelle,
    Formalien und Personalien bleiben draußen."""
    store = _vorschau_store(tmp_path)
    try:
        punkte = store.sitzungs_highlights([1])[1]
        titel = [p["title"] for p in punkte]
        assert any("Satzung" in t for t in titel)
        assert not any("Beschlussfähigkeit" in t for t in titel)
        assert not any("Berufung" in t for t in titel)
        assert all(p["wichtig"] >= store.WICHTIG_MINDEST for p in punkte)
        for p in punkte:
            assert p["top"] is (p["wichtig"] >= store.TOP_MINDEST)
            # Dieselbe Form wie die Punkte der Wochenvorschau — die Clients
            # decodieren beide mit demselben Typ.
            assert {"ksinr", "item_number", "title", "titel_kurz", "committee",
                    "session_date", "topic_name", "wichtig_grund"} <= set(p)
        # Ein Treffer zum eigenen Thema umgeht die Schwelle und ist hervorgehoben.
        mit = store.sitzungs_highlights(
            [1], meine={1: [{"item_number": "Ö 4", "topic_name": "Aktionswochen"}]})[1]
        eigener = next(p for p in mit if p["item_number"] == "Ö 4")
        assert eigener["top"] is True and eigener["topic_name"] == "Aktionswochen"
        # Reihenfolge innerhalb der Sitzung ist die Tagesordnung, nicht der Rang.
        assert [p["item_number"] for p in mit] == sorted(
            (p["item_number"] for p in mit), key=store._top_sortierung)
        # Deckel je Sitzung.
        assert len(store.sitzungs_highlights([1], max_je_sitzung=1)[1]) == 1
        # Terminierte Sitzungen ohne Nummer und unbekannte Nummern: nichts.
        assert store.sitzungs_highlights([]) == {}
        assert store.sitzungs_highlights([None, 999]) == {}
    finally:
        store.close()


def test_wochenvorschau_und_highlights_bewerten_gleich(tmp_path):
    """Beide Abnehmer teilen sich EINE Bewertung — ein Punkt, der auf der
    Wochenkarte steht, trägt in der Sitzungsliste dieselbe Zahl."""
    store = _vorschau_store(tmp_path)
    try:
        woche = {p["item_number"]: p["wichtig"] for p in store.wochenvorschau(max_punkte=99)["items"]}
        liste = {p["item_number"]: p["wichtig"] for p in store.sitzungs_highlights([1], max_je_sitzung=99)[1]}
        assert liste and all(liste[nr] == woche[nr] for nr in liste)
    finally:
        store.close()
