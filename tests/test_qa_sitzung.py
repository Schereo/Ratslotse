"""Sitzungs-Fragetyp der KI-Frage (25.08.26): deterministische Erkennung von
Sitzungsdatum und Gremium, Auflösung über die Sitzungstabelle, Kontext-Block.

Anlass war eine echte Nutzerfrage vom 25.08.26: „Was hat der
Jugendhilfeausschuss am 17.06.2026 beschlossen?" — die Ähnlichkeitssuche fand
nur die drei Kita-TOPs und ließ die halbe Tagesordnung weg, darunter einen
echten Beschluss (Richtlinien Jugendarbeit, angenommen).
"""
import json
from datetime import date, timedelta

from council import qa
from council.store import CouncilStore


# ---- Datums-Erkennung -------------------------------------------------------

def test_datum_in_frage_formate():
    f = qa._datum_in_frage
    assert f("Was hat der JHA am 17.06.2026 beschlossen?") == ("2026-06-17", None)
    assert f("Was war am 17.6.26?") == ("2026-06-17", None)
    assert f("Was wurde am 17. Juni 2026 entschieden?") == ("2026-06-17", None)
    assert f("Was wurde am 3. März 2025 entschieden?") == ("2025-03-03", None)
    # Ohne Jahr: Monatstag zurück, Jahr löst finde_sitzungen am Bestand auf.
    assert f("Was war in der Sitzung am 17.06.?") == (None, "-06-17")
    assert f("Was war am 17. Juni?") == (None, "-06-17")


def test_datum_in_frage_relative_tage():
    """„Um was geht es im Bauausschuss MORGEN?" (echte Nutzerfrage 26.08.,
    am Vorabend einer echten Sitzung) blieb ohne diese Auflösung eine
    Themen-Frage — die Antwort strickte aus alten Beschlüssen verschiedener
    Jahre eine „voraussichtlich"-Prognose zusammen."""
    f = qa._datum_in_frage
    heute = date.today()
    tag = lambda d: (heute + timedelta(days=d)).isoformat()  # noqa: E731
    assert f("Um was geht es im Bauausschuss morgen?") == (tag(1), None)
    assert f("Was steht morgen früh im Rat an?") == (tag(1), None)
    assert f("Was hat der Rat gestern beschlossen?") == (tag(-1), None)
    assert f("Tagt heute ein Ausschuss?") == (tag(0), None)
    assert f("Was läuft übermorgen im Sozialausschuss?") == (tag(2), None)
    assert f("Und vorgestern im Schulausschuss?") == (tag(-2), None)
    # Gruß und Tageszeit sind kein Datum.
    assert f("Guten Morgen, was hat der Rat beschlossen?") == (None, None)
    assert f("Was wurde am Morgen entschieden?") == (None, None)
    # Ein explizites Datum schlägt das relative Wort.
    assert f("Was war am 17.06.2026, nicht heute?") == ("2026-06-17", None)
    # „bis heute"/„seit gestern" sind Zeitspannen, keine Sitzungstermine.
    assert f("Was hat der Rat bis heute zum Stadion beschlossen?") == (None, None)
    assert f("Was ist seit gestern passiert?") == (None, None)
    # Adjektiv-Formen: Die Frage-Analyse kondensiert „morgen" gern zu
    # „am morgigen Tag" — genau diese Fassung fiel beim zweiten Anlauf
    # durchs Raster (dev-Probe 26.08.).
    assert f("Themen des Bauausschusses am morgigen Tag") == (tag(1), None)
    assert f("Was stand in der gestrigen Ratssitzung an?") == (tag(-1), None)
    assert f("Die heutige Tagesordnung des Sozialausschusses?") == (tag(0), None)
    # „morgens" ist eine Tageszeit, kein Tag.
    assert f("Was passiert morgens im Rathaus?") == (None, None)


def test_datum_in_frage_zeitraum_und_muell():
    f = qa._datum_in_frage
    # Zeitspannen sind keine Sitzungstermine.
    assert f("Was wurde seit dem 01.01.2024 zum Stadion beschlossen?") == (None, None)
    assert f("Alle Beschlüsse bis zum 31.12.2025 bitte") == (None, None)
    # Beträge und Uhrzeiten sind keine Daten.
    assert f("Was kostet das, 3.5 Millionen?") == (None, None)
    assert f("Die Sitzung begann um 18 Uhr") == (None, None)
    assert f("Was wurde beschlossen?") == (None, None)
    # Unsinnige Tage/Monate fallen durch.
    assert f("am 45.13.2026") == (None, None)


# ---- Gremiums-Erkennung -----------------------------------------------------

def _store_mit_sitzungen(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for ksinr, committee, tag in (
                (1, "Jugendhilfeausschuss", "2026-06-17"),
                (2, "Sozialausschuss", "2026-06-17"),
                (3, "Ausschuss für Stadtplanung und Bauen", "2026-06-04"),
                (4, "Rat", "2026-06-29")):
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, "
                "session_time, location, fetched_at) VALUES (?, ?, ?, '16:00', 'Rathaus', '')",
                (ksinr, committee, tag))
        for ksinr, pos, title in ((1, 0, "Krippengruppe"), (1, 1, "Kita-Bericht"),
                                  (1, 2, "Richtlinien Jugendarbeit"),
                                  (2, 0, "Sozialbericht"), (3, 0, "B-Plan"),
                                  (4, 0, "Stadionneubau")):
            store._conn.execute(
                "INSERT INTO council_decisions (ksinr, position, item_number, kind, title, outcome) "
                "VALUES (?, ?, ?, 'decision', ?, 'accepted')", (ksinr, pos, str(pos + 1), title))
        # Subvotes zählen nicht als eigene Tagesordnungspunkte.
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, title) "
            "VALUES (1, 9, 'subvote', 'Änderungsantrag')")
    return store


def test_gremium_in_frage_vollname_alias_und_rat(tmp_path):
    store = _store_mit_sitzungen(tmp_path)
    g = qa._gremium_in_frage
    assert g(store, "Was hat der Jugendhilfeausschuss beschlossen?") == "jugendhilfeausschuss"
    # Kurzform aus der Alias-Tabelle → Fragment des amtlichen Namens.
    assert g(store, "Was hat der Bauausschuss entschieden?") == "stadtplanung und bauen"
    # Plenum nur als eigenes Wort — „Rathaus" oder „Beirat" zählen nicht.
    assert g(store, "Was hat der Rat am 29.06. beschlossen?") == "rat"
    assert g(store, "Wann ist die nächste Ratssitzung?") == "rat"
    assert g(store, "Was ist im Rathaus passiert?") is None
    assert g(store, "Was wurde zum Stadion beschlossen?") is None
    store.close()


# ---- Sitzungs-Auflösung -----------------------------------------------------

def test_finde_sitzungen_mit_datum_und_gremium(tmp_path):
    store = _store_mit_sitzungen(tmp_path)
    s = qa.finde_sitzungen(store, "Was hat der Jugendhilfeausschuss am 17.06.2026 beschlossen?")
    assert len(s) == 1 and s[0]["committee"] == "Jugendhilfeausschuss"
    # Beschluss-ids in Tagesordnungs-Reihenfolge, ohne den Subvote.
    rows = store.get_decisions_by_ids(s[0]["beschluss_ids"])
    assert [r["title"] for r in rows] == ["Krippengruppe", "Kita-Bericht",
                                         "Richtlinien Jugendarbeit"]
    # Datum ohne Gremium meint den TAG: beide Sitzungen des 17.06.
    s = qa.finde_sitzungen(store, "Was wurde am 17.06.2026 beschlossen?")
    assert {x["committee"] for x in s} == {"Jugendhilfeausschuss", "Sozialausschuss"}
    # Datum ohne Jahr: jüngste vergangene Sitzung an diesem Monatstag.
    s = qa.finde_sitzungen(store, "Was hat der Jugendhilfeausschuss am 17.06. beschlossen?")
    assert [x["session_date"] for x in s] == ["2026-06-17"]
    store.close()


def test_finde_sitzungen_braucht_einen_anlass(tmp_path):
    store = _store_mit_sitzungen(tmp_path)
    # Ein Datum allein macht keine Sitzungsfrage — der Brief vom 17.06. ist keine.
    assert qa.finde_sitzungen(store, "Der Brief vom 17.06.2026 nennt Zahlen, stimmen die?") == []
    # Ohne Datum und ohne Sitzungs-Phrase passiert nichts, auch mit Gremium.
    assert qa.finde_sitzungen(store, "Was macht der Jugendhilfeausschuss eigentlich?") == []
    # Zeitspanne bleibt Zeitspanne.
    assert qa.finde_sitzungen(store, "Was wurde seit dem 01.01.2026 beschlossen?") == []
    store.close()


def test_finde_sitzungen_letzte_sitzung_mit_protokoll_verzug(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    heute = date.today()
    juengst = (heute - timedelta(days=7)).isoformat()
    aelter = (heute - timedelta(days=40)).isoformat()
    with store._conn:
        for ksinr, tag in ((1, aelter), (2, juengst)):
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, "
                "session_time, location, fetched_at) VALUES (?, 'Sportausschuss', ?, '', '', '')",
                (ksinr, tag))
        # Nur die ÄLTERE Sitzung hat schon Beschlüsse (Protokoll-Verzug!).
        store._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, title) "
            "VALUES (1, 0, 'decision', 'Sportstättenkonzept')")
        store._conn.execute(
            "INSERT INTO council_agenda_items (ksinr, item_number, title) "
            "VALUES (2, '1', 'Bäderbericht')")
    s = qa.finde_sitzungen(store, "Was hat der Sportausschuss in seiner letzten Sitzung beschlossen?")
    # Jüngste zuerst (ehrlich: noch kein Protokoll, Tagesordnung liegt bei),
    # dazu die letzte MIT Beschlüssen.
    assert [x["session_date"] for x in s] == [juengst, aelter]
    assert s[0]["beschluss_ids"] == [] and s[0]["agenda"][0]["title"] == "Bäderbericht"
    assert len(s[1]["beschluss_ids"]) == 1
    store.close()


def test_finde_sitzungen_morgen(tmp_path):
    """Tims Frage vom 26.08. wortwörtlich: „morgen" + Gremium löst die
    Sitzung von morgen auf — mit Tagesordnung statt Prognose-Halluzination."""
    store = CouncilStore(tmp_path / "c.sqlite")
    morgen = (date.today() + timedelta(days=1)).isoformat()
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, "
            "session_time, location, fetched_at) "
            "VALUES (11, 'Ausschuss für Stadtplanung und Bauen', ?, '17:00', '', '')",
            (morgen,))
        store._conn.execute(
            "INSERT INTO council_agenda_items (ksinr, item_number, title) "
            "VALUES (11, 'Ö 5', 'Bebauungsplan N-777')")
    s = qa.finde_sitzungen(store, "Um was geht es im Bauausschuss morgen?")
    assert len(s) == 1 and s[0]["session_date"] == morgen
    assert s[0]["kuenftig"] is True
    assert s[0]["agenda"][0]["title"] == "Bebauungsplan N-777"
    # Ohne Gremium und ohne Sitzungswort bleibt „morgen" folgenlos —
    # „Was kostet das morgen?" ist keine Sitzungsfrage.
    assert qa.finde_sitzungen(store, "Was kostet das morgen?") == []
    store.close()


def test_finde_sitzungen_naechste_sitzung(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    bald = (date.today() + timedelta(days=5)).isoformat()
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, "
            "session_time, location, fetched_at) VALUES (9, 'Verkehrsausschuss', ?, '17:00', '', '')",
            (bald,))
        store._conn.execute(
            "INSERT INTO council_agenda_items (ksinr, item_number, title) "
            "VALUES (9, '5', 'Radweg Alexanderstraße')")
    s = qa.finde_sitzungen(store, "Was steht auf der Tagesordnung der nächsten Sitzung des Verkehrsausschusses?")
    assert len(s) == 1 and s[0]["kuenftig"] is True
    assert s[0]["agenda"] == [{"item_number": "5", "title": "Radweg Alexanderstraße",
                               "summary": None}]
    assert qa.finde_sitzungen(store, "Wann tagt der Verkehrsausschuss?")[0]["session_date"] == bald
    store.close()


# ---- Kontext-Block, Leer-Text, Prompt-Regeln --------------------------------

def test_sitzungen_block_rendert_beide_zustaende():
    block = qa._sitzungen_block([
        {"committee": "Jugendhilfeausschuss", "session_date": "2026-06-17",
         "session_time": "16:00", "location": "Rathaus",
         "beschluss_ids": [1, 2, 3], "kuenftig": False},
        {"committee": "Sportausschuss", "session_date": "2026-09-01",
         "kuenftig": True, "beschluss_ids": [],
         "agenda": [{"item_number": "5", "title": "Bäderbericht",
                     "summary": "Sanierung  der   Becken."}]},
    ])
    assert "Jugendhilfeausschuss am 17.06.2026 um 16:00 Uhr (Rathaus)" in block
    assert "Alle 3 Tagesordnungspunkte" in block
    assert "steht noch BEVOR" in block
    assert "TOP 5: Bäderbericht — Sanierung der Becken." in block
    assert "NIE mit [id]" in block
    assert qa._sitzungen_block([]) == "" and qa._sitzungen_block(None) == ""


def test_sitzungen_block_kein_protokoll():
    """Vergangene Sitzung ohne Protokoll: Der Verzug (Wochen bis 1–2 Monate)
    ist der Normalfall — die Antwort muss ihn ausdrücklich als solchen
    erklären, sonst liest sich das Fehlen wie ein Fehler von Ratslotse."""
    block = qa._sitzungen_block([
        {"committee": "Rat", "session_date": "2026-08-20", "kuenftig": False,
         "beschluss_ids": [], "agenda": []}])
    assert "noch kein ausgewertetes Protokoll" in block
    assert "Wochen" in block
    assert "normale Ablauf" in block and "kein Fehler" in block


def test_sitzungs_leer_text():
    kuenftig = qa.sitzungs_leer_text([
        {"committee": "Sportausschuss", "session_date": "2026-09-01", "kuenftig": True,
         "agenda": [{"title": "Feststellung der Beschlussfähigkeit"},
                    {"title": "Bäderbericht"}]}])
    assert "tagt erst am 01.09.2026" in kuenftig and "„Bäderbericht“" in kuenftig
    # Formalien füllen den Anriss nicht (Wochenvorschau-Filter).
    assert "Beschlussfähigkeit" not in kuenftig
    verzug = qa.sitzungs_leer_text([
        {"committee": "Rat", "session_date": "2026-08-20", "kuenftig": False}])
    assert "20.08.2026" in verzug and "Protokoll" in verzug
    # Der Verzug wird als Normalfall erklärt — nicht nur festgestellt.
    assert "Wochen" in verzug and "normale Ablauf" in verzug and "kein Fehler" in verzug
    assert "automatisch" in verzug


def test_analyse_sitzung_setzt_nur_der_router(monkeypatch):
    """Behauptet die LLM-Analyse den Typ „sitzung", fehlt die aufgelöste
    Sitzung — dann gilt „thema", wie bei „person"."""
    from types import SimpleNamespace
    payload = json.dumps({"terms": "Sitzung Juni", "kind": "session"})
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))], usage=None))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Was war in der Sitzung?")["kind"] == "topic"
    qa._ANALYSE_CACHE.clear()


def test_sitzung_regel_und_tokenbudget():
    assert qa._answer_tokens("session") == 1400
    assert qa._answer_tokens("session", gross=True) == 2200
    assert qa._answer_tokens("session", eng=True) == 320
    messages, _ = qa._answer_messages(
        "Was hat der JHA am 17.06.2026 beschlossen?",
        [{"id": 1, "title": "T", "official_text": "B"}], typ="session",
        sitzungen=[{"committee": "Jugendhilfeausschuss", "session_date": "2026-06-17",
                    "beschluss_ids": [1], "kuenftig": False}])
    prompt = messages[0]["content"]
    assert "EINE KONKRETE SITZUNG" in prompt
    assert "ZUR GEFRAGTEN SITZUNG" in prompt
    # Ohne Sitzungs-Fund bleibt der Prompt frei von dem Block.
    messages, _ = qa._answer_messages("Frage?", [], typ="topic")
    assert "ZUR GEFRAGTEN SITZUNG" not in messages[0]["content"]


def test_store_decision_ids_der_sitzung_und_monatstag(tmp_path):
    store = _store_mit_sitzungen(tmp_path)
    assert len(store.decision_ids_der_sitzung(1)) == 3  # ohne Subvote
    assert store.decision_ids_der_sitzung(999) == []
    tage = store.sitzungen_am_monatstag("-06-17")
    assert {r["ksinr"] for r in tage} == {1, 2}
    store.close()
