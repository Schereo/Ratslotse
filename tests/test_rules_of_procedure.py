"""Die Geschäftsordnung des Rates in „Frag den Rat" (council/rules_of_procedure.py).

Drei Dinge halten diese Tests fest:

1. **Der Wortlaut ist vollständig.** 33 Paragrafen plus § 28a, jeder mit
   Text und Seite — die Datei kommt aus einem PDF-Parser, und ein still
   verschluckter Paragraf fiele sonst niemandem auf.
2. **Die Auslöser treffen in beide Richtungen.** „Wie wird im Rat
   abgestimmt?" meint § 18, „Wie hat der Rat zum Stadion abgestimmt?" nicht.
   Eine Regel, die eine Inhaltsfrage zieht, setzt eine Quellenkarte unter eine
   Antwort, die nichts mit ihr zu tun hat.
3. **Sie gilt für eine Wahlperiode.** Nach deren Ende, oder wenn das Archiv
   einen jüngeren Beschluss kennt, sagt die Antwort das.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import pytest

_WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_WURZEL / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from council import qa  # noqa: E402
from council import rules_of_procedure as rop  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]

IN_DER_WAHLPERIODE = date(2026, 10, 3)
NACH_DER_WAHLPERIODE = date(2026, 11, 5)


def _nummern(frage: str) -> list[str]:
    return [s.number for s in rop.find(frage).sections]


# ---- 1. Der Wortlaut ---------------------------------------------------------

def test_alle_paragrafen_sind_da():
    doc = rop.load()
    erwartet = [str(n) for n in range(1, 29)] + ["28a"] + [str(n) for n in range(29, 34)]
    assert [s.number for s in doc.sections] == erwartet, (
        "Die Geschäftsordnung hat 33 Paragrafen und § 28a. Fehlt einer, hat der "
        "Parser ihn verschluckt — neu erzeugen und den Diff lesen:\n"
        "  python scripts/fetch_rules_of_procedure.py --pdf <datei>")


def test_jeder_paragraf_hat_titel_text_abschnitt_und_seite():
    doc = rop.load()
    seiten = [s.page for s in doc.sections]
    assert seiten == sorted(seiten), "Seiten müssen mit den Paragrafen steigen"
    for s in doc.sections:
        assert s.title and s.text, s.number
        assert s.part in {"Rat", "Verwaltungsausschuss", "Ratsausschüsse", "Schlussbestimmungen"}
        assert 2 <= s.page <= 15, s.number
        # Keine Reste aus dem PDF: Kopfzeilen, Wingdings-Punkte, Silbentrennung.
        assert "Seite " not in s.text and "" not in s.text, s.number
        # („Sozial-, Jugend- und Wohnungshilfe" ist ein echter Bindestrich.)
        assert not re.search(r"[a-zäöü]- (?!und\b|oder\b|bzw)[a-zäöü]", s.text), s.number


def test_stichproben_aus_dem_wortlaut():
    """Gegen das PDF nachgelesen (03.10.2026) — die Zahlen, nach denen
    Menschen fragen."""
    doc = rop.load()
    assert "bis zu fünf Minuten" in doc.section("15").text
    assert "Bei Stimmengleichheit ist ein Antrag abgelehnt." in doc.section("18").text
    assert "spätestens 14 Tage vor der betreffenden Sitzung" in doc.section("23").text
    assert "Die Fragestunde endet nach 60 Minuten." in doc.section("23").text
    assert "spätestens 13 Tage vor dem vorgesehenen Sitzungstermin" in doc.section("3").text
    assert "spätestens um 23 Uhr" in doc.section("3").text
    assert "Die Sitzungen sind nichtöffentlich." in doc.section("25").text
    # Listenpunkte bleiben eigene Zeilen (§ 13 Abs. 1 läuft über den Seitenumbruch).
    assert "\na) Unterbrechung der Sitzung,\nb) Ausschluss" in doc.section("13").text


def test_kopf_traegt_fassung_beschluss_und_wahlperiode():
    doc = rop.load()
    assert doc.version_date == "2021-07-19"
    # Vorlage 21/0741: in der konstituierenden Sitzung unverändert bestätigt.
    assert (doc.adopted_date, doc.adopted_template) == ("2021-11-01", "21/0741")
    assert doc.term_end == "2026-10-31"
    assert doc.source_url.startswith("https://www.oldenburg.de/") and doc.source_url.endswith(".pdf")
    assert doc.page_url(doc.section("15")).endswith("#page=7")


# ---- 2. Die Auslöser ---------------------------------------------------------

@pytest.mark.parametrize("frage, erwartet", [
    ("Wie lange darf ein Ratsmitglied reden?", {"15"}),
    ("Wie oft darf ein Ratsmitglied zu einem Thema reden?", {"15"}),
    ("Wie wird im Rat abgestimmt?", {"18"}),
    ("Was passiert bei Stimmengleichheit?", {"18"}),
    ("Wann wird namentlich abgestimmt?", {"18"}),
    ("Wie funktioniert die Einwohnerfragestunde?", {"23"}),
    ("Bis wann muss ich meine Frage für die Einwohnerfragestunde einreichen?", {"23"}),
    ("Kann ich als Bürger in der Ratssitzung eine Frage stellen?", {"23"}),
    ("Darf ich bei einer Ratssitzung zuhören?", {"4"}),
    ("Warum werden manche Themen nichtöffentlich beraten?", {"4"}),
    ("Wann ist ein Ratsmitglied befangen?", {"6"}),
    ("Wann ist der Rat beschlussfähig?", {"8"}),
    ("Wie läuft eine Ratssitzung ab?", {"9"}),
    ("Wie entsteht ein Ratsbeschluss?", {"10"}),
    ("Was ist ein Dringlichkeitsantrag?", {"11"}),
    ("Über welchen Änderungsantrag wird zuerst abgestimmt?", {"12"}),
    ("Was ist ein GO-Antrag?", {"13"}),
    ("Was bedeutet Vertagung?", {"13"}),
    ("Dürfen Ratsmitglieder Akten einsehen?", {"14"}),
    ("Kann ein Ratsmitglied aus der Sitzung geworfen werden?", {"17"}),
    ("Ist die Wahl im Rat geheim?", {"19"}),
    ("Wer schreibt das Protokoll?", {"20"}),
    ("Was ist der Unterschied zwischen Fraktion und Gruppe?", {"21"}),
    ("Wer legt fest, was auf die Tagesordnung kommt?", {"3"}),
    ("Wie lange dauert eine Ausschusssitzung?", {"28"}),
    ("Antrag nach §28a – was heißt das?", {"28a"}),
    ("Können zwei Ausschüsse gemeinsam tagen?", {"31"}),
])
def test_verfahrensfragen_ziehen_ihren_paragrafen(frage, erwartet):
    assert erwartet <= set(_nummern(frage)), _nummern(frage)


@pytest.mark.parametrize("frage", [
    # Ergebnisse, nicht Regeln — Vergangenheit und ein Gegenstand.
    "Wie hat der Rat zum Stadion abgestimmt?",
    "Wer hat gegen den Haushalt gestimmt?",
    "Welche Mehrheit hat die SPD im Rat?",
    "Kommt das Stadion wieder auf die Tagesordnung?",
    "Was steht auf der Tagesordnung der nächsten Ratssitzung?",
    "Wann ist die nächste öffentliche Ratssitzung?",
    "Was hat der Verkehrsausschuss zum öffentlichen Nahverkehr beschlossen?",
    "Welche Änderungsanträge gab es zum Haushalt 2026?",
    "Was ist mit dem vertagten Antrag zum Stadion?",
    "Muss der Bebauungsplan nochmal in den Ausschuss kommen?",
    "Wann ist die Anhörung zum Bebauungsplan 831?",
    # Andere Parlamente und andere Geschäftsordnungen.
    "Wie lange darf man im Bundestag reden?",
    "Was steht in der Geschäftsordnung des Gestaltungsbeirates?",
    # Ein nacktes „§" ist kein Hinweis auf die Geschäftsordnung.
    "Was sagt § 62 NKomVG?",
    "Was regelt § 15?",
    # Und alles, was mit dem Rat gar nichts zu tun hat.
    "Gibt es eine Go-Kart-Bahn in Oldenburg?",
    "Wie viel kostet die Sanierung der Cäcilienbrücke?",
])
def test_inhaltsfragen_ziehen_nichts(frage):
    sel = rop.find(frage)
    assert not sel, f"{frage!r} zog {[s.label for s in sel.sections]} (Überblick: {sel.overview})"


def test_eval_fragen_ziehen_fast_nie():
    """Die Fragen aus den Eval-Sätzen sind echte Formulierungen über den
    ganzen Bestand. Gemessen am 03.10.2026: eine von 496 zog die
    Geschäftsordnung, und zu Recht („Was ist der Verwaltungsausschuss?")."""
    fragen: set[str] = set()

    def sammle(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("question", "frage") and isinstance(v, str):
                    fragen.add(v.strip())
                else:
                    sammle(v)
        elif isinstance(o, list):
            for x in o:
                sammle(x)

    for datei in sorted((_WURZEL / "eval").glob("cases_*.json")):
        sammle(json.loads(datei.read_text(encoding="utf-8")))
    ziehen = sorted(f for f in fragen if rop.find(f))
    assert len(fragen) > 300
    assert ziehen == ["Was ist der Verwaltungsausschuss?"], (
        "Neue Fehlauslöser in echten Fragen — Auslöser in "
        f"council/rules_of_procedure.py::TRIGGERS enger fassen:\n{ziehen}")


def test_paragraf_mit_geschaeftsordnung_wird_genommen():
    assert _nummern("Was regelt § 23 der Geschäftsordnung?") == ["23"]
    assert _nummern("Was steht in § 15 Abs. 5 GO?") == ["15"]
    # Steht hinter der Nummer ein anderes Gesetz, ist es nicht die
    # Geschäftsordnung — auch wenn die Frage sie nennt.
    frage = "Gilt § 23 NKomVG laut Geschäftsordnung auch im Ausschuss?"
    assert rop._explicit_numbers(frage, rop.fold(frage)) == []


def test_ausschussfrage_bekommt_den_verweis_paragrafen():
    """§ 15 Abs. 4 (nur einmal reden) gilt im Ausschuss NICHT — das steht in
    § 32. Ohne ihn sagte die Antwort das Gegenteil."""
    assert _nummern("Wie lange darf man im Ausschuss reden?") == ["15", "32"]
    assert _nummern("Warum tagt der Verwaltungsausschuss nicht öffentlich?") == ["4", "25", "26"]


def test_die_frage_nach_dem_ganzen_bekommt_das_verzeichnis():
    sel = rop.find("Was steht in der Geschäftsordnung?")
    # Das Verzeichnis und drei Beispiele — mit dem Verzeichnis allein schrieb
    # die Antwort über den Prompt statt über die Geschäftsordnung.
    assert sel.overview and [s.number for s in sel.sections] == ["9", "15", "23"]
    assert "Inhalt: § 1 Einberufung" in rop.prompt_block(sel, IN_DER_WAHLPERIODE)
    karte = rop.card(sel, IN_DER_WAHLPERIODE)
    assert len(karte["contents"]) == 34 and len(karte["sections"]) == 3
    wie = rop.find("Wie funktioniert der Stadtrat?")
    assert wie.overview and [s.number for s in wie.sections] == ["9", "10"]


def test_geltungsfrage_bekommt_paragraf_33():
    assert _nummern("Seit wann gilt die Geschäftsordnung?") == ["33"]
    # „Geschäftsordnungsanträge" sind Anträge NACH der Geschäftsordnung.
    assert _nummern("Welche Geschäftsordnungsanträge wurden 2026 beschlossen?") == ["13"]


def test_hoechstens_vier_paragrafen():
    frage = ("Wie lange darf man reden, wie wird abgestimmt, wer leitet die Sitzung, "
             "wann ist der Rat beschlussfähig und was ist eine persönliche Erklärung?")
    assert len(rop.find(frage).sections) == rop.MAX_SECTIONS


def test_mehrere_fassungen_einer_frage_werden_zusammengelegt():
    """Die rohe Frage und ihre eigenständige Fassung aus der Analyse."""
    sel = rop.find("Und wie lange darf man da reden?",
                   "Wie lange darf man in der Einwohnerfragestunde reden?")
    assert [s.number for s in sel.sections] == ["15", "23"]


def test_jeder_paragraf_ist_erreichbar():
    """Ein Paragraf ohne eigenen Auslöser muss auf anderem Weg erreichbar sein —
    sonst ist er tot. Und jeder Auslöser gehört zu einem Paragrafen, den es gibt."""
    nummern = {s.number for s in rop.load().sections}
    assert set(rop.TRIGGERS) == nummern
    anders_erreichbar = {
        "26": "Wie lange darf man im Verwaltungsausschuss reden?",
        "30": "Wird im Ausschuss namentlich abgestimmt?",
        "33": "Bis wann gilt die Geschäftsordnung?",
    }
    ohne = {nr for nr, t in rop.TRIGGERS.items() if not (t.own or t.with_context)}
    assert ohne == set(anders_erreichbar)
    for nr, frage in anders_erreichbar.items():
        assert nr in _nummern(frage), (nr, frage)


# ---- 3. Gilt die Fassung noch? ----------------------------------------------

def test_in_der_wahlperiode_gilt_sie():
    assert rop.status(IN_DER_WAHLPERIODE)["state"] == "current"
    assert "gilt für die Wahlperiode 2021–2026" in rop.version_line(IN_DER_WAHLPERIODE)
    block = rop.prompt_block(rop.find("Wie lange darf man reden?"), IN_DER_WAHLPERIODE)
    assert "ACHTUNG" not in block
    assert "Fassung vom 19.07.2021" in block and "KEIN Beschluss" in block
    assert "bis zu fünf Minuten" in block


def test_nach_der_wahlperiode_sagt_sie_es():
    assert rop.status(NACH_DER_WAHLPERIODE)["state"] == "term_ended"
    block = rop.prompt_block(rop.find("Wie lange darf man reden?"), NACH_DER_WAHLPERIODE)
    assert "ACHTUNG" in block and "31.10.2026" in block
    karte = rop.card(rop.find("Wie lange darf man reden?"), NACH_DER_WAHLPERIODE)
    assert karte["state"] == "term_ended" and "galt" in karte["version"]


def test_ein_juengerer_beschluss_ueberholt_sie():
    neuer = [{"id": 4711, "session_date": "2026-11-03", "title": "Geschäftsordnung …",
              "outcome": "accepted"}]
    block = rop.prompt_block(rop.find("Wie lange darf man reden?"), NACH_DER_WAHLPERIODE, neuer)
    assert "[4711]" in block and "03.11.2026" in block
    assert rop.card(rop.find("Wie lange darf man reden?"), None, neuer)["state"] == "superseded"


class _FakeStore:
    def __init__(self, rows=None, fehler=False):
        self.rows, self.fehler, self.gefragt = rows or [], fehler, None

    def rules_of_procedure_decisions(self, after):
        if self.fehler:
            raise RuntimeError("DB weg")
        self.gefragt = after
        return self.rows


def test_nur_beschluesse_ueber_die_geschaeftsordnung_selbst_zaehlen():
    store = _FakeStore([
        {"id": 1, "title": "Geschäftsordnungsantrag der BSW-Fraktion auf Vertagung",
         "outcome": "rejected", "session_date": "2026-06-01"},
        {"id": 2, "title": "Geschäftsordnung des Gestaltungsbeirates",
         "outcome": "accepted", "session_date": "2026-06-27"},
        {"id": 3, "title": "Geschäftsordnung für den Rat, den Verwaltungsausschuss und die "
                           "Ratsausschüsse - Beschluss", "outcome": "accepted",
         "session_date": "2026-11-03"},
        {"id": 4, "title": "Änderung der Geschäftsordnung des Rates (SPD-Fraktion)",
         "outcome": "rejected", "session_date": "2026-12-01"},
    ])
    assert [r["id"] for r in rop.newer_adoptions(store)] == [3]
    assert store.gefragt == "2021-11-01"
    assert rop.newer_adoptions(_FakeStore(fehler=True)) == []


def test_store_findet_die_geschaeftsordnungs_beschluesse_des_rates(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for ksinr, gremium, tag in ((1, "Rat", "2021-11-01"), (2, "Rat", "2026-11-03"),
                                    (3, "Ausschuss für Allgemeine Angelegenheiten", "2026-10-20")):
            store._conn.execute(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, ?, ?, '16:00', 'Rathaus', '')",
                (ksinr, gremium, tag))
        for ksinr, titel in ((1, "Geschäftsordnung für den Rat - Beschluss"),
                             (2, "Geschäftsordnung für den Rat - Beschluss"),
                             (2, "Stadionneubau"),
                             (3, "Geschäftsordnung für den Rat - Vorberatung")):
            store._conn.execute(
                "INSERT INTO council_decisions (ksinr, position, kind, title, outcome) "
                "VALUES (?, 0, 'decision', ?, 'accepted')", (ksinr, titel))
    zeilen = store.rules_of_procedure_decisions(after="2021-11-01")
    assert [(z["session_date"], z["title"]) for z in zeilen] == [
        ("2026-11-03", "Geschäftsordnung für den Rat - Beschluss")]
    assert [r["session_date"] for r in rop.newer_adoptions(store)] == ["2026-11-03"]
    store.close()


# ---- Der Prompt --------------------------------------------------------------

def test_ohne_geschaeftsordnung_bleibt_der_prompt_wie_er_war():
    """Regel aus PR 21: Ohne Auslöser ist der Prompt zeichengleich."""
    ohne, _ = qa._answer_messages("Was wurde zum Stadion beschlossen?",
                                  [{"id": 1, "title": "Stadion", "official_text": "B"}])
    leer, _ = qa._answer_messages("Was wurde zum Stadion beschlossen?",
                                  [{"id": 1, "title": "Stadion", "official_text": "B"}],
                                  rules_block="")
    assert ohne == leer
    assert "GESCHÄFTSORDNUNG" not in ohne[0]["content"]


def test_mit_geschaeftsordnung_stehen_regel_und_wortlaut_im_prompt():
    block = rop.prompt_block(rop.find("Wie lange darf man reden?"), IN_DER_WAHLPERIODE)
    messages, _ = qa._answer_messages("Wie lange darf man reden?", [], rules_block=block)
    prompt = messages[0]["content"]
    assert qa.GESCHAEFTSORDNUNG_REGEL in prompt
    assert "§ 15 Redeordnung, Redezeit" in prompt
    # Die Regel steht vor der Frage, der Wortlaut im Kontext dahinter.
    assert prompt.index("GESCHÄFTSORDNUNG:") < prompt.index("FRAGE:") < prompt.index(
        "GESCHÄFTSORDNUNG DES RATES")


@pytest.mark.parametrize("name", ["answer_question", "answer_stream"])
def test_der_wortlaut_erreicht_beide_antwortwege(name, monkeypatch):
    """Beide reichen ihre Argumente an ``_answer_messages`` weiter — ein
    vergessener Parameter war dort schon einmal monatelang tot (``screen``)."""
    gesehen: dict = {}

    def merke(**kw):
        gesehen["prompt"] = kw["messages"][0]["content"]
        raise RuntimeError("stop")

    monkeypatch.setattr(qa.llm, "chat_complete", merke)
    monkeypatch.setattr(qa.llm, "chat_stream", merke)
    block = rop.prompt_block(rop.find("Wie lange darf man reden?"), IN_DER_WAHLPERIODE)
    with pytest.raises(RuntimeError):
        list(getattr(qa, name)("Wie lange darf man reden?", [], rules_block=block) or [])
    assert "bis zu fünf Minuten" in gesehen["prompt"]


def test_eine_regelfrage_ist_keine_unklare_frage():
    assert qa.rueckfrage_noetig({"unklar": True}) is True
    assert qa.rueckfrage_noetig({"unklar": True}, procedure=True) is False


# ---- Durch den Endpunkt ------------------------------------------------------

@pytest.fixture
def client():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    c = TestClient(app)
    c.post("/api/auth/register", json={"display_name": "Testkonto",
                                       "email": "admin@test.de", "password": "password123"})
    grant_admin("admin@test.de", RATSLOTSE_DB)
    return c


def _ask(client, monkeypatch, frage: str, *, unklar: bool = False, treffer=None) -> dict:
    from app.routers import council as council_router

    gesehen: dict = {}

    def fake_stream(question, ctx, **kwargs):
        gesehen["rules_block"] = kwargs.get("rules_block", "")
        gesehen["gross"] = kwargs.get("gross")
        gesehen["typ"] = kwargs.get("typ")
        yield "Nach § 15 Abs. 5 der Geschäftsordnung bis zu fünf Minuten."

    monkeypatch.setattr(council_router, "_qa_retrieve",
                        lambda *a, **k: (list(treffer or []), "semantisch"))
    monkeypatch.setattr(qa, "analyse_query", lambda *a, **k: {
        "question": frage, "terms": frage, "kind": "topic", "party": None,
        "variants": [], "eng": False, "unklar": unklar})
    monkeypatch.setattr(qa, "answer_stream", fake_stream)
    with client.stream("POST", "/api/council/ask",
                       json={"question": frage, "conversation_id": None}) as antwort:
        assert antwort.status_code == 200
        roh = "".join(antwort.iter_text())
    gesehen["events"] = [json.loads(z[6:]) for z in roh.splitlines() if z.startswith("data: ")]
    return gesehen


def test_regelfrage_ohne_beschluss_wird_beantwortet(client, monkeypatch):
    """Kein Beschluss-Treffer, und das Analysemodell hält die Frage für
    gegenstandslos — trotzdem keine Rückfrage und kein „nichts gefunden":
    Die Geschäftsordnung beantwortet sie."""
    gesehen = _ask(client, monkeypatch, "Wie lange darf ein Ratsmitglied reden?", unklar=True)
    typen = [e["type"] for e in gesehen["events"]]
    assert "error" not in typen
    text = "".join(e.get("text", "") for e in gesehen["events"] if e["type"] == "token")
    assert qa.RUECKFRAGE_TEXT not in text and "keine passenden Beschlüsse" not in text
    assert "§ 15 Redeordnung, Redezeit" in gesehen["rules_block"]

    quellen = next(e for e in gesehen["events"] if e["type"] == "sources")
    karte = quellen["rules_of_procedure"]
    assert [s["label"] for s in karte["sections"]] == ["§ 15"]
    assert karte["sections"][0]["url"].endswith("#page=7")
    assert "bis zu fünf Minuten" in karte["sections"][0]["text"]
    # Der Wortlaut IST der Beleg — kein „dünne Beleglage"-Hinweis daneben.
    assert quellen["evidence_level"] == "solide"
    done = next(e for e in gesehen["events"] if e["type"] == "done")
    assert done["records_state"] is None


def test_inhaltsfrage_bleibt_ohne_geschaeftsordnung(client, monkeypatch):
    stadion = {"id": 1, "title": "Stadionneubau", "official_text": "Beschluss",
               "session_date": "2026-06-01", "committee": "Rat", "score": 0.9}
    gesehen = _ask(client, monkeypatch, "Wie hat der Rat zum Stadion abgestimmt?",
                   treffer=[stadion])
    quellen = next(e for e in gesehen["events"] if e["type"] == "sources")
    assert quellen["rules_of_procedure"] is None
    assert gesehen["rules_block"] == ""


def _treffer(n: int) -> list[dict]:
    return [{"id": i, "title": f"Geschäftsordnungsantrag {i}", "official_text": "Vertagung",
             "session_date": f"{2018 + i % 8}-06-01", "committee": "Rat", "score": 0.3}
            for i in range(1, n + 1)]


def test_regelfrage_bekommt_keine_langfassung(client, monkeypatch):
    """30 schwache Treffer über acht Jahre machten sonst „ein umfangreiches
    Thema" daraus — mit „Kurz gesagt" und Zwischentiteln für einen Absatz
    (Messung 03.10.2026, „Warum tagt der Verwaltungsausschuss nicht öffentlich?")."""
    gesehen = _ask(client, monkeypatch, "Warum tagt der Verwaltungsausschuss nicht öffentlich?",
                   treffer=_treffer(30))
    assert gesehen["gross"] is False


def test_regelfrage_ohne_genannte_sitzung_wird_keine_sitzungsfrage(client, monkeypatch):
    """„Rat" und „Tagesordnung" reichen der Sitzungserkennung für „die nächste
    Sitzung" — die Antwort begann dann mit deren Termin."""
    naechste = [{"ksinr": None, "committee": "Rat", "session_date": "2026-10-26",
                 "kuenftig": True, "decision_ids": [], "agenda": []}]
    monkeypatch.setattr(qa, "finde_sitzungen", lambda *a, **k: list(naechste))
    gesehen = _ask(client, monkeypatch,
                   "Kann der Rat über etwas abstimmen, das nicht auf der Tagesordnung steht?")
    quellen = next(e for e in gesehen["events"] if e["type"] == "sources")
    assert quellen["sessions"] == [] and gesehen["typ"] != "session"
    # Nennt die Frage die Sitzung selbst, bleibt sie — als Termin, nicht als
    # Sitzungsfrage: gefragt ist die Frist, nicht jeder Punkt.
    gesehen = _ask(client, monkeypatch,
                   "Bis wann muss eine Fraktion ihren Antrag für die nächste Ratssitzung einreichen?")
    quellen = next(e for e in gesehen["events"] if e["type"] == "sources")
    assert len(quellen["sessions"]) == 1 and gesehen["typ"] != "session"


def test_nennt_sitzung():
    assert qa.nennt_sitzung("Bis wann für die nächste Ratssitzung?")
    assert qa.nennt_sitzung("Was wurde in der letzten Sitzung vertagt?")
    assert qa.nennt_sitzung("Darf ich am 26.10.2026 zuhören?")
    assert not qa.nennt_sitzung("Kann der Rat über etwas abstimmen, das nicht auf der "
                                "Tagesordnung steht?")
    assert qa.nennt_sitzung("Wie lange darf man reden?", "Wie lange darf man in der "
                            "kommenden Ratssitzung reden?")


def test_das_gespeicherte_gespraech_traegt_die_karte(client, monkeypatch):
    """Ein wieder geöffnetes Gespräch zeigt dieselbe Karte wie das Original."""
    store = Store(RATSLOTSE_DB)
    uid = store.get_web_user_by_email("admin@test.de")["id"]
    store.set_qa_speichern(uid, True)
    store.close()
    gesehen = _ask(client, monkeypatch, "Wie funktioniert die Einwohnerfragestunde?")
    gid = next(e for e in gesehen["events"] if e["type"] == "done")["conversation_id"]
    assert gid is not None
    store = Store(RATSLOTSE_DB)
    quellen = json.loads(store.qa_gespraech(gid, uid)["turns"][0]["sources"])
    store.close()
    assert [s["label"] for s in quellen["rules_of_procedure"]["sections"]] == ["§ 23"]


# ---- Der Parser --------------------------------------------------------------

def test_parser_setzt_trennungen_listen_und_seitenumbrueche_zusammen():
    from scripts.fetch_rules_of_procedure import parse

    seiten = [
        "1.02\n\nSeite 1 von 3\n\nG e s c h ä f t s o r d n u n g\n\n"
        "für den Rat der Stadt Oldenburg (Oldb)\nvom 19. Juli 2021\n",
        "1.02\n\nSeite 2 von 3\n\nI. Abschnitt:  R a t\n\n§ 1\n\nEinberufung\n\n"
        "(1)\nDie Oberbürgermeisterin hat den Rat einzuberu-\nfen, per E-\nMail.\n\n"
        "\nPersonalangelegenheiten,\n\n§ 2\n\nLadung\n\n"
        "(1) Anträge auf\na) Unterbrechung der Sitzung,\n",
        "1.02\n\nSeite 3 von 3\n\nb) Vertagung\n- sie nicht beleidigen,\n"
        "- sie nicht wiederholen. Die Ladung erfolgt\n",
    ]
    kopf, paragrafen = parse(seiten)
    assert kopf == {"title": "Geschäftsordnung für den Rat der Stadt Oldenburg (Oldb)",
                    "version_date": "2021-07-19"}
    assert [(p["number"], p["title"], p["part"], p["page"]) for p in paragrafen] == [
        ("1", "Einberufung", "Rat", 2), ("2", "Ladung", "Rat", 2)]
    assert paragrafen[0]["text"] == ("(1) Die Oberbürgermeisterin hat den Rat einzuberufen, "
                                     "per E-Mail.\n– Personalangelegenheiten,")
    assert paragrafen[1]["text"] == ("(1) Anträge auf\na) Unterbrechung der Sitzung,\n"
                                     "b) Vertagung\n– sie nicht beleidigen,\n"
                                     "– sie nicht wiederholen. Die Ladung erfolgt")


# ---- Lotti -------------------------------------------------------------------

def _lotti_prompt(frage: str, route: str = "/council/session") -> str:
    from council import assistant as lotti
    from kern import knowledge

    screen = lotti.Screen(route=route)
    ctx = {"knowledge": knowledge.fuer_route(route), "record": "", "glossary": [],
           "geld": {}, "permissions": frozenset(), "wegweiser": [],
           "rules_of_procedure": rop.find(frage)}
    msgs, _ = lotti.explain_messages(screen, frage, ctx)
    return msgs[0]["content"]


def test_lotti_erklaert_eine_regel_aus_dem_wortlaut():
    """„Was ist ein Antrag zur Geschäftsordnung?" auf einer Sitzungsseite —
    die Antwort steht nicht auf dem Bildschirm, aber auch nicht im Archiv."""
    from kern import prompts

    p = _lotti_prompt("Was ist ein Antrag zur Geschäftsordnung?")
    assert "§ 13 Anträge zur Geschäftsordnung" in p
    assert prompts.GESCHAEFTSORDNUNG_REGEL in p
    assert "keine Zeile „WEITER:" in p


def test_lotti_ohne_regelfrage_bleibt_wie_sie_war():
    from kern import prompts

    p = _lotti_prompt("Was sehe ich hier?")
    assert "GESCHÄFTSORDNUNG" not in p
    assert prompts.GESCHAEFTSORDNUNG_REGEL not in p


def test_lotti_belegt_den_paragrafen_mit_einem_chip():
    from council import assistant as lotti

    belege = lotti.kontext_belege({"rules_of_procedure": rop.find("Wie lange darf man reden?")})
    assert belege == [{"label": "Geschäftsordnung des Rates, § 15 Redeordnung, Redezeit",
                       "year": 2021, "url": rop.load().source_url + "#page=7"}]
    # Ohne einzelnen Paragrafen: das PDF selbst.
    assert lotti.kontext_belege({"rules_of_procedure": rop.Selection(overview=True)})[0][
        "url"] == rop.load().source_url
    assert lotti.kontext_belege({"rules_of_procedure": rop.Selection()}) == []
