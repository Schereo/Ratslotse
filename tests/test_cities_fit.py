"""Der Annotator ``fit``: Hat Oldenburg das schon, und lohnt es sich?

Der Unterschied zu ``classify`` ist nicht das Modell, sondern die Disziplin:
Ohne Belege wird nicht gefragt, und ohne nachprüfbare Beleg-Kennung wird nicht
gespeichert. Genau das halten diese Tests fest — das Modell selbst ist
gemockt, ein Test, der es wirklich fragt, misst OpenRouter.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from council.cities import fit as fit_modul
from council.cities.annotators import OldenburgFit, get
from council.cities.evidence import evidence_for, kvonr_aus
from council.cities.model import Batch, Body, File, FileRole, Paper
from council.cities.store import CitiesStore
from council.store import CouncilStore

MODELL = "test-mini"


@pytest.fixture()
def rats(tmp_path):
    """Oldenburg hat einen Wärmeplan — mit Beschluss, Ergebnis und Kurzfassung."""
    store = CouncilStore(tmp_path / "council.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (7, 'Rat', '2025-11-20', '16:00', 'PFL', '2025-11-21')")
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr, simple_summary) VALUES (1, 7, 1, 'decision', '4', "
            "  'Kommunale Wärmeplanung', 'accepted', 4711, "
            "  'Der Rat beschließt den kommunalen Wärmeplan.')")
        store._conn.execute(
            "INSERT INTO council_templates (kvonr, template_number, title, fetched_at, "
            "  status, attachments_scanned) VALUES (4711, '25/0001', 'Wärmeplanung', "
            "  '2025-11-21', 'ok', 0)")
    store.save_field_recap("klima_umwelt", "Oldenburg arbeitet am Wärmeplan.", 12,
                           "2025-01-01", "2026-01-01", "2026-01-02")
    yield store
    store.close()


@pytest.fixture()
def cities(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    s.upsert_batch(Batch(
        papers=[
            Paper("oldenburg:paper:4711", "oldenburg", "Kommunale Wärmeplanung",
                  date="2025-11-20"),
            Paper("os:p:1", "osnabrueck", "Wärmenetz-Ausbau beschließen",
                  date="2026-05-01", paper_type_raw="Beschlussvorlage", kind="proposal"),
            Paper("os:p:2", "osnabrueck", "Bebauungsplan Nr. 674",
                  date="2026-05-02", kind="proposal"),
        ],
        files=[File("os:f:1", "osnabrueck", FileRole.MAIN, paper_id="os:p:1")]))
    s.put_text("os:f:1", "pypdf", "1", "Der Rat möge den Ausbau des Wärmenetzes beschließen.",
               1, "ok")
    for pid, transfer, instrument in (("os:p:1", "adaptable", "Wärmenetz ausbauen"),
                                      ("os:p:2", "local", None)):
        s.put_annotation("paper", pid, "classify", "2",
                         {"field": "klima_umwelt", "transfer": transfer,
                          "competence": "council", "instrument": instrument,
                          "summary": "Zusammenfassung."}, "h" + pid)
    s.fts_upsert("oldenburg:paper:4711", "oldenburg", "Kommunale Wärmeplanung",
                 None, "Wärmenetz und Wärmeplanung für Oldenburg", None)
    s.replace_neighbors(MODELL, "paper", "os:p:1",
                        [("paper", "oldenburg:paper:4711", 0.84)])
    yield s
    s.close()


def _antwort(nutzlast: dict, kosten: float = 0.0001):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(nutzlast)))],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=120, cost=kosten))


URTEIL = {"status": "partial", "evidence": ["oldenburg:paper:4711"],
          "reason": "Oldenburg hat den Plan, nicht den Ausbau.",
          "worth": "yes", "why_worth": "Der Ausbau ist der nächste Schritt.",
          "obstacles": None, "confidence": "high"}


# ------------------------------------------------------------------- Belege

def test_kvonr_aus_der_kennung():
    assert kvonr_aus("oldenburg:paper:28119") == 28119
    # Anträge aus Anlagen tragen keine Vorlagen-Id.
    assert kvonr_aus("oldenburg:paper:att:99") is None
    assert kvonr_aus("os:p:1") is None
    assert kvonr_aus("") is None


def test_belege_kommen_aus_drei_quellen(cities, rats):
    papier = cities.paper("os:p:1")
    klasse = cities.annotation("paper", "os:p:1", "classify", "2")["payload"]
    belege = evidence_for(cities, rats, papier, klasse, MODELL)
    arten = [b.kind for b in belege]
    assert "neighbor" in arten and "recap" in arten
    # Der Nachbar trägt, was die RATS-Datenbank weiß — Ergebnis und Kurzfassung
    # stehen nicht im Städte-Speicher.
    nachbar = next(b for b in belege if b.kind == "neighbor")
    assert nachbar.id == "oldenburg:paper:4711"
    assert nachbar.outcome == "accepted"
    assert "Wärmeplan" in nachbar.text


def test_belege_sind_eindeutig(cities, rats):
    """Dasselbe Papier als Nachbar UND als Volltexttreffer zählt einmal."""
    papier = cities.paper("os:p:1")
    klasse = cities.annotation("paper", "os:p:1", "classify", "2")["payload"]
    belege = evidence_for(cities, rats, papier, klasse, MODELL)
    assert len({b.id for b in belege}) == len(belege)


def test_zu_ferne_nachbarn_belegen_nichts(cities, rats):
    """Der Median der Ähnlichkeit zweier beliebiger Verwaltungstexte liegt bei
    0,70. Was darunter liegt, ist kein Beleg — es sieht nur so aus."""
    cities.replace_neighbors(MODELL, "paper", "os:p:1",
                             [("paper", "oldenburg:paper:4711", 0.41)])
    papier = cities.paper("os:p:1")
    klasse = cities.annotation("paper", "os:p:1", "classify", "2")["payload"]
    belege = evidence_for(cities, rats, papier, klasse, MODELL)
    assert not [b for b in belege if b.kind == "neighbor"]


def test_die_tragenden_woerter_stehen_vorn():
    """Im Deutschen ist das lange Wort das spezifische: „Qualitätshandbuch"
    trennt, „einführen" nicht."""
    from council.cities.evidence import _woerter
    assert _woerter("Qualitätshandbuch und Fallanalysen für ASD einführen")[0] == "Qualitätshandbuch"
    # Bindestriche und Schrägstriche sind für FTS5 Syntax — hier zerlegt.
    assert set(_woerter("Sozial-gerechte Bodennutzung")) == {"Bodennutzung", "gerechte", "Sozial"}
    assert _woerter("") == []


def test_volltextsuche_geht_von_streng_nach_nachsichtig(cities):
    """Gemessen: Eine reine ODER-Anfrage lieferte unter „Qualitätshandbuch und
    Fallanalysen für ASD einführen" die Oldenburger Vorlage „Warnung und
    Information der Bevölkerung — sie teilt das Wort „einführen" und sonst
    nichts. Solche Belege laden ein, „vorhanden" zu sagen, wo nichts ist."""
    from council.cities.evidence import fts_treffer
    cities.upsert_batch(Batch(papers=[
        Paper("oldenburg:paper:900", "oldenburg", "Warnung der Bevölkerung"),
        Paper("oldenburg:paper:901", "oldenburg", "Wärmenetz-Ausbau")]))
    cities.fts_upsert("oldenburg:paper:900", "oldenburg", "Warnung der Bevölkerung",
                      None, "Ein Frühwarnsystem einführen", None)
    cities.fts_upsert("oldenburg:paper:901", "oldenburg", "Wärmenetz-Ausbau",
                      None, "Das Wärmenetz ausbauen und einführen", None)
    # Beide teilen „einführen"; nur eines teilt auch das spezifische Wort.
    treffer = [t["paper_id"] for t in fts_treffer(cities, "Wärmenetz einführen", 5)]
    assert treffer == ["oldenburg:paper:901"]
    # Findet die strenge Stufe nichts, wird gelockert statt aufgegeben.
    assert fts_treffer(cities, "Frühwarnsystem Bevölkerung", 5)
    assert fts_treffer(cities, "", 5) == []


# ------------------------------------------------------------ Beleg-Disziplin

def test_erfundene_kennung_macht_das_urteil_ungueltig():
    nutzlast = OldenburgFit(status="present", evidence=["oldenburg:paper:9999"],
                            worth="no", confidence="high")
    grund = fit_modul.pruefe(nutzlast, {"oldenburg:paper:4711"})
    assert grund and grund.startswith("hallucinated_evidence")


def test_behauptung_ohne_beleg_wird_verworfen():
    """„Oldenburg hat das" ist eine Aussage über Oldenburg — sie braucht eine
    Kennung. Bei `missing` ist die leere Liste dagegen die Aussage."""
    for status in ("present", "partial"):
        nutzlast = OldenburgFit(status=status, evidence=[], worth="no", confidence="low")
        assert fit_modul.pruefe(nutzlast, {"oldenburg:paper:4711"}) == "claim_without_evidence"
    leer = OldenburgFit(status="missing", evidence=[], worth="yes", confidence="low")
    assert fit_modul.pruefe(leer, {"oldenburg:paper:4711"}) is None


# ------------------------------------------------------------------- Auswahl

def test_nur_uebertragbare_vorlagen_werden_beurteilt(cities):
    """Für einen Bebauungsplan ist „fehlt Oldenburg das?" keine sinnvolle
    Frage — er fehlt, und das ist richtig so."""
    ids = [p["id"] for p in fit_modul.candidates_for(cities)]
    assert ids == ["os:p:1"]


def test_oldenburg_beurteilt_sich_nicht_selbst(cities):
    assert all(not i["id"].startswith("oldenburg:")
               for i in fit_modul.candidates_for(cities))


# ---------------------------------------------------------------------- Lauf

def test_lauf_schreibt_ein_urteil(cities, rats, monkeypatch):
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 1 and stand["errors"] == 0
    eintrag = cities.annotation("paper", "os:p:1", "fit", "1")
    assert eintrag["payload"]["status"] == "partial"
    assert eintrag["payload"]["evidence"] == ["oldenburg:paper:4711"]
    assert eintrag["payload"]["worth"] == "yes"


def test_ohne_belege_wird_gar_nicht_erst_gefragt(cities, rats, monkeypatch):
    """Ein Urteil ohne Grundlage ist eine Behauptung. Der Rückblick allein
    trägt sie nicht — er sagt, was die Stadt beschäftigt, nicht ob sie dieses
    Instrument hat."""
    cities.replace_neighbors(MODELL, "paper", "os:p:1", [])
    cities._conn.execute("DELETE FROM papers_fts")
    aufrufe = []
    monkeypatch.setattr(fit_modul.llm, "chat_complete",
                        lambda **kw: (aufrufe.append(1), _antwort(URTEIL))[1])
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert not aufrufe, "ohne tragenden Beleg darf kein Modell gefragt werden"
    assert stand["skipped_no_evidence"] == 1 and stand["annotated"] == 0


def test_erfundene_kennung_wird_nicht_gespeichert(cities, rats, monkeypatch):
    kaputt = dict(URTEIL, evidence=["oldenburg:paper:12345"])
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(kaputt))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 0 and stand["hallucinated_evidence"] == 1
    assert cities.annotation("paper", "os:p:1", "fit", "1") is None


def test_kaputte_antwort_kippt_den_lauf_nicht(cities, rats, monkeypatch):
    """Dieselbe Lehre wie beim Einordnungslauf: Ein Batch aus Unsinn darf
    nicht 500 gute Urteile mitreißen."""
    monkeypatch.setattr(fit_modul.llm, "chat_complete",
                        lambda **kw: _antwort({"status": "irgendwas"}))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 0 and stand["errors"] == 1


def test_zweiter_lauf_urteilt_nicht_neu(cities, rats, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(fit_modul.llm, "chat_complete",
                        lambda **kw: (aufrufe.append(1), _antwort(URTEIL))[1])
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    vorher = len(aufrufe)
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 0 and len(aufrufe) == vorher


def test_ein_neuer_oldenburger_beleg_macht_das_urteil_alt(cities, rats, monkeypatch):
    """Der Kern des `source_hash` bei `fit`: Das Urteil hängt nicht nur an der
    fremden Vorlage, sondern auch daran, was Oldenburg hat — und das wächst."""
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    cities.upsert_batch(Batch(papers=[
        Paper("oldenburg:paper:5000", "oldenburg", "Wärmenetz Oldenburg", date="2026-02-01")]))
    cities.replace_neighbors(MODELL, "paper", "os:p:1",
                             [("paper", "oldenburg:paper:4711", 0.84),
                              ("paper", "oldenburg:paper:5000", 0.81)])
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 1, "ein neuer Beleg muss das Urteil neu stellen"


def test_der_steckbrief_steht_im_prompt(cities, rats, monkeypatch):
    """Ohne ihn hält das Modell jede fremde Idee für übertragbar — auch was
    dem Land, dem Landkreis oder einem Versorger gehört."""
    gesehen = {}

    def merken(**kw):
        gesehen["system"] = kw["messages"][0]["content"]
        gesehen["user"] = kw["messages"][1]["content"]
        return _antwort(URTEIL)

    monkeypatch.setattr(fit_modul.llm, "chat_complete", merken)
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert "NKomVG" in gesehen["system"] and "OOWV" in gesehen["system"]
    # Und die Belege stehen mit ihrer Kennung im Nutzer-Teil, sonst könnte
    # das Modell sie gar nicht zitieren.
    assert "oldenburg:paper:4711" in gesehen["user"]


# ------------------------------------------------------------------- Reihenfolge

def test_fit_laeuft_nach_dem_index():
    """Es braucht die Nachbarschaften als Belege. Vorher gefragt, urteilte es
    ins Leere — und `needs_index` sagt das dem Cron, statt dass der eine
    Liste pflegt, die auseinanderläuft."""
    assert get("fit").needs_index is True
    assert get("classify").needs_index is False


def test_der_cron_ruft_beide_stellen():
    from pathlib import Path
    quelle = Path("scripts/check_cities.py").read_text()
    vor = quelle.index("pipeline.annotate(")
    index = quelle.index("pipeline.index_all(")
    nach = quelle.index("nach_index=True")
    assert vor < index < nach, (
        "Reihenfolge im Cron: erst einordnen, dann indizieren, dann urteilen")


def test_der_rueckblick_traegt_kein_urteil():
    """Er sagt, was die Stadt beschäftigt — nicht, ob sie dieses eine
    Instrument hat. Beim Bauen des Golden Sets war das der Fall, in dem ich
    selbst versucht war, aus „Oldenburg hat einen Brandbrief gegen Kürzungen
    geschrieben" ein „vorhanden" zu machen."""
    nutzlast = OldenburgFit(status="present", evidence=["recap:klima_umwelt"],
                            worth="no", confidence="high")
    erlaubt = {"recap:klima_umwelt", "oldenburg:paper:1"}
    assert fit_modul.pruefe(nutzlast, erlaubt, {"oldenburg:paper:1"}) == "claim_only_on_recap"
    # Mit einem tragenden Beleg daneben ist der Rückblick unschädlich.
    mit = OldenburgFit(status="present", worth="no", confidence="high",
                       evidence=["recap:klima_umwelt", "oldenburg:paper:1"])
    assert fit_modul.pruefe(mit, erlaubt, {"oldenburg:paper:1"}) is None


def test_zu_langer_freitext_wird_gekuerzt_nicht_verworfen():
    """Die Längen sind Anzeige-Grenzen, keine Zusagen. Im Bestandslauf über
    300 Vorlagen gingen zwei vollständig richtige Urteile verloren, beide weil
    `obstacles` zwanzig Zeichen zu lang war."""
    f = OldenburgFit(status="missing", worth="no", confidence="low",
                     obstacles="x" * 400, reason="y" * 500, why_worth="z" * 500)
    assert len(f.obstacles or "") == 200
    assert len(f.reason) == 300 and len(f.why_worth) == 300


def test_die_behauptungen_bleiben_streng():
    """Ein unerwarteter Status ist kein Formfehler, sondern ein Urteil, das
    niemand einordnen kann — das wird verworfen, nicht zurechtgebogen."""
    import pytest as _pytest
    from pydantic import ValidationError as _VE

    for kaputt in ({"status": "vorhanden"}, {"worth": "vielleicht"},
                   {"confidence": "hoch"}):
        with _pytest.raises(_VE):
            OldenburgFit(**{"status": "missing", "worth": "no",
                            "confidence": "low", **kaputt})
