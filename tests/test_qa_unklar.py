"""Rückfrage statt Antwort, wenn die Frage keinen Gegenstand nennt.

Der Anlass ist eine echte Eingabe vom 10.09.2026: „Was hast du?" — und die
Antwort war eine ordentlich belegte Auskunft darüber, woran der Stadtrat
gerade arbeitet. Die Pipeline kann gar nicht anders; die Suche findet immer
etwas, und das Antwort-Modell schreibt daraus etwas Plausibles. Eine Antwort
auf eine nicht gestellte Frage ist teurer als keine Antwort: Sie sieht richtig
aus.

Der teurere der beiden Fehler bleibt aber die falsche Rückfrage — eine
beantwortbare Frage abzuweisen ist schlimmer, als eine unklare zu beantworten.
Deshalb steht hier vor allem, was das Urteil des Modells ÜBERSTIMMT.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from council import qa  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    c = TestClient(app)
    c.post("/api/auth/register", json={"display_name": "Testkonto", "email": "admin@test.de", "password": "password123"})
    grant_admin("admin@test.de", RATSLOTSE_DB)
    return c


def _ereignisse(client, frage: str, analyse: dict, monkeypatch) -> list[dict]:
    """Eine Frage durch ``/ask`` schicken und die SSE-Ereignisse einsammeln."""
    from council import qa as qa_mod

    monkeypatch.setattr(qa_mod, "analyse_query", lambda *a, **k: analyse)
    with client.stream("POST", "/api/council/ask", json={"question": frage}) as antwort:
        assert antwort.status_code == 200
        roh = "".join(antwort.iter_text())
    return [json.loads(z[6:]) for z in roh.splitlines() if z.startswith("data: ")]


def _analyse(frage: str, **rest) -> dict:
    return {"question": frage, "terms": frage, "kind": "topic", "party": None,
            "variants": [], "eng": False, **rest}


# ---- Das Urteil aus dem Analyse-Call ----------------------------------------

def test_unklar_reist_im_analyse_call_mit(monkeypatch):
    """Kein zweiter Aufruf: Das Urteil kostet weder Zeit noch Geld extra."""
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **kw: _antwort(
        {"question": "Was hast du?", "terms": "", "kind": "topic", "unklar": True}))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Was hast du?")["unklar"] is True


def test_ohne_feld_gilt_die_frage_als_klar(monkeypatch):
    """Ein Modell, das das Feld nicht liefert, darf nichts abweisen."""
    monkeypatch.setattr(qa.llm, "chat_complete", lambda **kw: _antwort(
        {"question": "Was wurde zum Hafen beschlossen?", "terms": "Hafen", "kind": "topic"}))
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Was wurde zum Hafen beschlossen?")["unklar"] is False


def test_bei_einem_providerfehler_gilt_die_frage_als_klar(monkeypatch):
    """Der Fallback trägt das alte Verhalten — ein Ausfall des Analyse-Calls
    darf keine Frage in die Rückfrage schicken."""
    def kaputt(**kw):
        raise RuntimeError("Provider weg")

    monkeypatch.setattr(qa.llm, "chat_complete", kaputt)
    qa._ANALYSE_CACHE.clear()
    assert qa.analyse_query("Irgendeine Frage?")["unklar"] is False


def _antwort(daten: dict):
    class _Msg:
        content = json.dumps(daten, ensure_ascii=False)

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    return _Resp()


# ---- Die Vorschläge zur Rückfrage -------------------------------------------

class FakeStore:
    """Ein Bestand aus wenigen Zeilen — wie in ``test_ausweg_fragen.py``."""

    def __init__(self, zeilen=None, volltext=None, sitzungen=None):
        self._zeilen = zeilen or {}
        self._volltext = volltext or {}
        self._sitzungen = sitzungen or []

    def search_decisions_fts(self, query: str, limit: int = 40):
        return [(i, 1.0, "") for i in self._volltext.get(query.lower(), [])][:limit]

    def get_decisions_by_ids(self, ids):
        return [{"id": i, "title": self._zeilen[i]} for i in ids if i in self._zeilen]

    def juengste_sitzungen_mit_beschluessen(self, limit: int = 2, mindest_tops: int = 1):
        return [s for s in self._sitzungen if (s.get("n") or 0) >= mindest_tops][:limit]


def test_traegt_ein_wort_der_frage_einen_anker_gewinnt_der():
    """Wer das Thema getroffen und nur die Frage verfehlt hat, bekommt seins
    zurück — nicht irgendeine frische Sitzung."""
    store = FakeStore(
        {1: "Sanierung der Sporthalle Kreyenbrück"},
        {"sporthalle": [1]},
        [{"top_titel": "Haushaltssatzung 2027", "committee": "Rat",
          "session_date": "2026-09-08"}],
    )
    fragen = qa.rueckfrage_vorschlaege(store, "Sporthalle und so?", limit=1)
    assert fragen == ["Was wurde zu „Sanierung der Sporthalle Kreyenbrück“ entschieden?"]


def test_ohne_anker_kommen_die_juengsten_sitzungen():
    """„Was hast du?" trägt kein einziges Wort — dann muss der Vorschlag aus
    dem Bestand kommen, damit er garantiert beantwortbar ist."""
    store = FakeStore(sitzungen=[
        {"top_titel": "Neubau der Grundschule Bümmerstede", "n": 12},
        {"top_titel": "Kurz", "n": 9},
        {"top_titel": "Gebührensatzung für die Abfallwirtschaft", "n": 7},
    ])
    fragen = qa.rueckfrage_vorschlaege(store, "Was hast du?")
    # Der zu kurze Titel fällt raus — ein nichtssagender Vorschlag ist keiner.
    assert fragen == ["Was wurde zu „Neubau der Grundschule Bümmerstede“ entschieden?",
                      "Was wurde zu „Gebührensatzung für die Abfallwirtschaft“ entschieden?"]


def test_eine_sitzung_mit_einem_einzigen_punkt_taugt_nicht(tmp_path):
    """Ihr „wichtigster Beschluss" ist zwangsläufig der, der da ist — und das
    ist typischerweise Verfahrenskram. Am 10.09.2026 stand deshalb „Was wurde
    zu ‚Beratung von nichtöffentlichen Tagesordnungspunkten im …' entschieden?"
    als Beispielfrage auf der leeren Seite. Kein Titel-Putz repariert das; die
    Zeile ist ungekürzt genauso wertlos. Die AUSWAHL muss stimmen.

    Deshalb gegen eine echte Datenbank: Die Schranke sitzt im SQL, und ein
    Attrappen-Store prüfte nur die Attrappe."""
    from council.scraper import CouncilSession
    from council.store import CouncilStore

    cs = CouncilStore(tmp_path / "council.sqlite")
    cs.save_session(CouncilSession(1, "Ausschuss für Allgemeine Angelegenheiten",
                                   "2026-08-17", "17:00", "Rathaus"))
    cs.save_session(CouncilSession(2, "Rat", "2026-06-29", "17:00", "Rathaus"))
    with cs._conn:
        cs._conn.execute(
            "INSERT INTO council_decisions (id,ksinr,position,item_number,title,kind,importance)"
            " VALUES (1,1,1,'1','Beratung von nichtöffentlichen Tagesordnungspunkten',"
            "'decision',10)")
        for i in range(5):
            cs._conn.execute(
                "INSERT INTO council_decisions (id,ksinr,position,item_number,title,kind,importance)"
                " VALUES (?,2,?,?,?,'decision',?)",
                (10 + i, i, str(i), f"Sanierung der Cäcilienbrücke {i}", 50 - i))

    ohne = cs.juengste_sitzungen_mit_beschluessen(limit=2)
    mit = cs.juengste_sitzungen_mit_beschluessen(limit=2, mindest_tops=5)
    cs.close()

    assert ohne[0]["top_titel"].startswith("Beratung von nichtöffentlichen")
    assert [z["top_titel"] for z in mit] == ["Sanierung der Cäcilienbrücke 0"]


def test_der_gegenstand_wird_vom_verwaltungsapparat_befreit():
    """Amtliche Titel tragen ihren Vorgang mit. In einem Chip, der eine Zeile
    hat, verdrängt jedes Wort Apparat ein Wort Inhalt."""
    assert qa.vorschlags_gegenstand(
        "Neubau Sechsfeldhalle am Standort Kennedystraße (Fraktionen SPD, "
        "Bündnis 90/Die Grünen, CDU und FDP vom 31.03.2026)"
    ) == "Neubau Sechsfeldhalle am Standort Kennedystraße"
    assert qa.vorschlags_gegenstand(
        "Bebauungsplan 810 (Krugweg) mit örtlichen Bauvorschriften - "
        "Prüfung der Stellungnahmen - Satzungsbeschluss"
    ) == "Bebauungsplan 810 (Krugweg) mit örtlichen Bauvorschriften"
    # Das „(Oldb)" hinter dem Stadtnamen trägt null Information.
    assert qa.vorschlags_gegenstand(
        "Richtlinien der Stadt Oldenburg (Oldb) zur Jugendarbeit"
    ) == "Richtlinien der Stadt Oldenburg zur Jugendarbeit"
    # Und ein Titel, der schon ein Gegenstand ist, bleibt einer.
    assert qa.vorschlags_gegenstand("Sanierung der Cäcilienbrücke") == (
        "Sanierung der Cäcilienbrücke")


def test_die_rueckfrage_ist_als_solche_markiert(client, monkeypatch):
    """Ohne die Marke sähe sie aus wie eine Antwort ohne Treffer — und bekäme
    deren Angebote: „Als Thema anlegen" mit „Was hast du?" als Themennamen."""
    from app.routers import council as council_router

    monkeypatch.setattr(council_router, "_qa_retrieve", _nie_suchen)
    ereignisse = _ereignisse(client, "Was hast du?",
                             _analyse("Was hast du?", unklar=True), monkeypatch)

    assert next(e for e in ereignisse if e["type"] == "done")["unclear"] is True


def test_ein_kaputter_bestand_laesst_die_rueckfrage_stehen():
    """Vorschläge sind Zusatz, nie Blocker."""
    class Kaputt:
        def search_decisions_fts(self, *a, **k):
            raise RuntimeError("DB weg")

        def juengste_sitzungen_mit_beschluessen(self, *a, **k):
            raise RuntimeError("DB weg")

    assert qa.rueckfrage_vorschlaege(Kaputt(), "Was hast du?") == []


# ---- Die Regel selbst --------------------------------------------------------

def test_ein_harter_anker_ueberstimmt_das_urteil():
    """Person, Katalogort und Sitzung sind Stammdaten-Treffer, kein
    Modell-Urteil. Wer einen nennt, hat einen Gegenstand genannt."""
    unklar = {"unklar": True}
    assert qa.rueckfrage_noetig(unklar) is True
    assert qa.rueckfrage_noetig(unklar, person={"nachname": "Ellberg"}) is False
    assert qa.rueckfrage_noetig(unklar, ort={"id": "eversten"}) is False
    assert qa.rueckfrage_noetig(unklar, sitzungen=[{"ksinr": 1}]) is False
    assert qa.rueckfrage_noetig(unklar, einfach=True) is False
    assert qa.rueckfrage_noetig({"unklar": False}) is False
    assert qa.rueckfrage_noetig({}) is False


# ---- Der Kurzschluss im Router ----------------------------------------------

def test_unklare_frage_bekommt_die_rueckfrage_statt_einer_antwort(client, monkeypatch):
    """Der Anlassfall. Gesucht wird gar nicht erst."""
    from app.routers import council as council_router

    monkeypatch.setattr(council_router, "_qa_retrieve", _nie_suchen)
    ereignisse = _ereignisse(client, "Was hast du?",
                             _analyse("Was hast du?", unklar=True), monkeypatch)

    token = [e for e in ereignisse if e["type"] == "token"]
    assert token and token[0]["text"] == qa.RUECKFRAGE_TEXT
    fertig = next(e for e in ereignisse if e["type"] == "done")
    assert fertig["cited"] == []
    # Ohne `sources`-Ereignis zeigt kein Client eine leere Beleg-Leiste.
    assert not [e for e in ereignisse if e["type"] == "sources"]


def _nie_suchen(*args, **kwargs):
    raise AssertionError("Für eine unklare Frage darf nicht gesucht werden.")


def test_die_rueckfrage_bietet_einen_weg_weiter(client, monkeypatch):
    """Über das vorhandene `suggestions`-Ereignis — beide Clients rendern es
    bereits, der Strom-Vertrag bleibt unangetastet."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    monkeypatch.setattr(council_router, "_qa_retrieve", _nie_suchen)
    monkeypatch.setattr(qa_mod, "rueckfrage_vorschlaege",
                        lambda *a, **k: ["Was wurde zu „Hafen“ entschieden?"])
    ereignisse = _ereignisse(client, "Was hast du?",
                             _analyse("Was hast du?", unklar=True), monkeypatch)

    vorschlag = next(e for e in ereignisse if e["type"] == "suggestions")
    assert vorschlag["questions"] == ["Was wurde zu „Hafen“ entschieden?"]


def test_eine_genannte_ratsperson_ueberstimmt_das_urteil(client, monkeypatch):
    """Wer eine Person aus den Stammdaten nennt, hat einen Gegenstand genannt —
    dann wird gesucht, auch wenn das Modell die Frage für unklar hält."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    monkeypatch.setattr(qa_mod, "finde_person",
                        lambda *a, **k: {"nachname": "Ellberg", "name": "Bernhard Ellberg"})
    gesucht: list[bool] = []

    def fake_retrieve(*a, **k):
        gesucht.append(True)
        return [], "semantisch"

    monkeypatch.setattr(council_router, "_qa_retrieve", fake_retrieve)
    ereignisse = _ereignisse(client, "Und Ellberg?",
                             _analyse("Und Ellberg?", unklar=True), monkeypatch)

    assert gesucht, "Die Personen-Erkennung muss das Modell überstimmen."
    assert qa.RUECKFRAGE_TEXT not in "".join(
        e.get("text", "") for e in ereignisse if e["type"] == "token")


def test_einfacher_erklaeren_ist_keine_unklare_frage(client, monkeypatch):
    """Der Knopf schickt einen Wunsch, keine Frage — er sieht gegenstandslos
    aus und meint die vorige Antwort."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    gesucht: list[bool] = []

    def fake_retrieve(*a, **k):
        gesucht.append(True)
        return [], "semantisch"

    monkeypatch.setattr(council_router, "_qa_retrieve", fake_retrieve)
    monkeypatch.setattr(qa_mod, "will_vereinfachung", lambda *a, **k: True)
    _ereignisse(client, "Erklär mir das einfacher",
                _analyse("Erklär mir das einfacher", unklar=True), monkeypatch)

    assert gesucht, 'Der Vereinfachen-Knopf darf nie in die Rückfrage laufen.'


def test_die_rueckfrage_zaehlt_getrennt_von_den_sackgassen(client, monkeypatch):
    """`ai_answer_empty` zählt Fragen, die nichts GEFUNDEN haben. Hier wurde
    gar nicht gesucht — die beiden zusammenzuzählen verdürbe beide Zahlen."""
    from app.routers import council as council_router

    monkeypatch.setattr(council_router, "_qa_retrieve", _nie_suchen)
    _ereignisse(client, "Was hast du?", _analyse("Was hast du?", unklar=True), monkeypatch)

    store = Store(RATSLOTSE_DB)
    zaehler = {z["key"]: z["n"] for z in store.ereignisse()["events"]}
    store.close()
    assert zaehler["ai_question_unclear"] == 1
    assert zaehler["ai_answer_empty"] == 0


def test_der_turn_landet_im_gespraech(client, monkeypatch):
    """Sonst klafft im Transkript eine Lücke (Review-Befund B4 zur leeren
    Antwort — für die Rückfrage gilt dasselbe)."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    monkeypatch.setattr(council_router, "_qa_retrieve", _nie_suchen)
    monkeypatch.setattr(qa_mod, "analyse_query",
                        lambda *a, **k: _analyse("Was hast du?", unklar=True))
    client.post("/api/council/conversations/setting", json={"an": True})
    with client.stream("POST", "/api/council/ask",
                       json={"question": "Was hast du?", "conversation_id": None}) as antwort:
        roh = "".join(antwort.iter_text())
    ereignisse = [json.loads(z[6:]) for z in roh.splitlines() if z.startswith("data: ")]
    fertig = next(e for e in ereignisse if e["type"] == "done")

    assert fertig["conversation_id"] is not None
    gespraech = client.get(f"/api/council/conversations/{fertig['conversation_id']}").json()
    turn = gespraech["turns"][0]
    assert turn["answer"] == qa.RUECKFRAGE_TEXT
    # Auch im Schnappschuss: Sonst sähe der Turn beim Wiederöffnen aus wie
    # eine Antwort ohne Treffer und bekäme wieder deren Angebote.
    assert turn["sources"]["unclear"] is True


# ---- Und derselbe Riegel vor der gründlichen Recherche -----------------------

def test_die_recherche_startet_auf_eine_unklare_frage_gar_nicht(client, monkeypatch):
    """Ein Job zerlegt die Frage in Facetten, sucht zu jeder, liest Dokumente
    und schreibt einen Bericht — eine halbe Minute und ein Vielfaches einer
    normalen Antwort, für eine Frage, die niemand gestellt hat."""
    from council import qa as qa_mod
    from app import deepresearch

    monkeypatch.setattr(qa_mod, "analyse_query",
                        lambda *a, **k: _analyse("Was hast du?", unklar=True))
    monkeypatch.setattr(deepresearch, "start_job", _nie_starten)
    antwort = client.post("/api/council/deep-research", json={"question": "Was hast du?"})

    assert antwort.status_code == 400
    leib = antwort.json()
    # Ein STRING, kein Objekt: Die ausgelieferte App zeigt genau dieses Feld
    # als Fehlertext des Turns — sie bekommt so die Rückfrage im Wortlaut.
    assert leib["detail"] == qa.RUECKFRAGE_TEXT
    assert leib["unclear"] is True
    assert isinstance(leib["questions"], list)


def _nie_starten(*args, **kwargs):
    raise AssertionError("Für eine unklare Frage darf kein Job starten.")


def test_die_abgewiesene_recherche_kostet_kein_kontingent(client, monkeypatch):
    """Das Kontingent zählt ANGELEGTE Jobs — eine Rückfrage darf also gar
    keinen anlegen, sonst kostet das Nichtstun eine der fünf Recherchen."""
    from council import qa as qa_mod
    from app import deepresearch

    monkeypatch.setattr(qa_mod, "analyse_query",
                        lambda *a, **k: _analyse("Was hast du?", unklar=True))
    monkeypatch.setattr(deepresearch, "start_job", _nie_starten)
    client.post("/api/council/deep-research", json={"question": "Was hast du?"})

    store = Store(RATSLOTSE_DB)
    uid = store._conn.execute("SELECT id FROM web_users LIMIT 1").fetchone()["id"]
    heute = store.deep_jobs_heute(uid)
    zaehler = {z["key"]: z["n"] for z in store.ereignisse()["events"]}
    store.close()
    assert heute == 0
    # Und sie zählt auch nicht als Recherche.
    assert zaehler["research"] == 0
    assert zaehler["ai_question_unclear"] == 1


def test_eine_klare_frage_startet_die_recherche_weiterhin(client, monkeypatch):
    from council import qa as qa_mod
    from app import deepresearch

    gestartet: list = []
    monkeypatch.setattr(qa_mod, "analyse_query", lambda *a, **k: _analyse(
        "Wie ist der Stand bei der Cäcilienbrücke?", unklar=False))
    monkeypatch.setattr(deepresearch, "start_job", lambda *a, **k: gestartet.append(a))
    antwort = client.post("/api/council/deep-research",
                          json={"question": "Wie ist der Stand bei der Cäcilienbrücke?"})

    assert antwort.status_code == 201
    assert antwort.json()["job_id"]
    assert gestartet
