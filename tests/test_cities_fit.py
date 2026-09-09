"""Der Annotator ``fit``: Hat Oldenburg das schon, und lohnt es sich?

Der Unterschied zu ``classify`` ist nicht das Modell, sondern die Disziplin:
Ohne Belege wird nicht gefragt, und ohne nachprüfbare Beleg-Kennung wird nicht
gespeichert. Genau das halten diese Tests fest — das Modell selbst ist
gemockt, ein Test, der es wirklich fragt, misst OpenRouter.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import threading

import pytest

from council.cities import fit as fit_modul
from council.cities.annotators import OldenburgStatus, get
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


#: Der Vektor, den `_embed_eins` in diesen Tests für JEDE Vorlage liefert.
#: Vier Zahlen genügen — die Arme rechnen ein Skalarprodukt, keine Semantik.
FRAGE_VEKTOR = (1.0, 0.0, 0.0, 0.0)


@pytest.fixture(autouse=True)
def fester_vektor(monkeypatch):
    """Der Nachbar-Arm rechnet seit 09.09.2026 selbst gegen Oldenburgs Matrix,
    statt die Tabelle `neighbors` zu lesen (siehe `evidence._nachbar_treffer`).
    Damit die Tests eine Ähnlichkeit VORGEBEN können statt sie zu erwürfeln,
    steht die Frage fest; `oldenburger_nachbar` legt die Gegenstücke dazu.
    """
    import numpy as np

    from council.cities import evidence as ev
    monkeypatch.setattr(ev, "_embed_eins",
                        lambda text: np.array(FRAGE_VEKTOR, dtype=np.float32))


def oldenburger_nachbar(store, paper_id: str, naehe: float) -> None:
    """Eine Oldenburger Vorlage mit genau dieser Ähnlichkeit zur Frage.

    Ersetzt das frühere `replace_neighbors`: Die Zahl steht jetzt im Vektor,
    nicht in einer Tabellenspalte — und genau das ist der Punkt der Änderung.
    """
    import math

    import numpy as np
    rest = math.sqrt(max(0.0, 1.0 - naehe * naehe))
    v = np.array([naehe, rest, 0.0, 0.0], dtype=np.float32)
    store.put_object_embedding("paper", paper_id, MODELL, "h:" + paper_id, v.tobytes())


@pytest.fixture(autouse=True)
def feste_suchbegriffe(monkeypatch):
    """Die Belegsuche fragt ein Modell nach Oldenburger Suchwörtern.

    In diesen Tests geht es um die Logik von `fit`, nicht um die Wortwahl
    eines Modells — und ein echter Aufruf würde jede Zählung von
    Modellaufrufen verfälschen. Deshalb fest: die tragenden Wörter des
    Instruments, also genau der Rückfall, den `search_terms` selbst nimmt,
    wenn der Aufruf scheitert.
    """
    from council.cities import evidence as ev
    monkeypatch.setattr(ev, "search_terms",
                        lambda klasse, papier: ev._woerter(klasse.get("instrument") or ""))


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
    oldenburger_nachbar(s, "oldenburg:paper:4711", 0.84)
    yield s
    s.close()


def _antwort(nutzlast: dict, kosten: float = 0.0001):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(nutzlast)))],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=120, cost=kosten))


URTEIL = {"status": "partial", "evidence": ["oldenburg:paper:4711"],
          "reason": "Oldenburg hat den Plan, nicht den Ausbau.",
          "confidence": "high"}


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
    oldenburger_nachbar(cities, "oldenburg:paper:4711", 0.41)
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
    treffer = [t["paper_id"] for t in fts_treffer(cities, ["Wärmenetz", "einführen"], 5)]
    assert treffer == ["oldenburg:paper:901"]
    # Findet die strenge Stufe nichts, wird gelockert statt aufgegeben.
    assert fts_treffer(cities, ["Frühwarnsystem", "Bevölkerung"], 5)
    assert fts_treffer(cities, [], 5) == []


# ------------------------------------------------------------ Beleg-Disziplin

def test_erfundene_kennung_macht_das_urteil_ungueltig():
    nutzlast = OldenburgStatus(status="present", evidence=["oldenburg:paper:9999"], confidence="high")
    grund = fit_modul.pruefe(nutzlast, {"oldenburg:paper:4711"})
    assert grund and grund.startswith("hallucinated_evidence")


def test_behauptung_ohne_beleg_wird_verworfen():
    """„Oldenburg hat das" ist eine Aussage über Oldenburg — sie braucht eine
    Kennung. Bei `missing` ist die leere Liste dagegen die Aussage."""
    for status in ("present", "partial"):
        nutzlast = OldenburgStatus(status=status, evidence=[], confidence="low")
        assert fit_modul.pruefe(nutzlast, {"oldenburg:paper:4711"}) == "claim_without_evidence"
    leer = OldenburgStatus(status="missing", evidence=[], confidence="low")
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
    eintrag = cities.annotation("paper", "os:p:1", "fit", get("fit").version)
    assert eintrag["payload"]["status"] == "partial"
    assert eintrag["payload"]["evidence"] == ["oldenburg:paper:4711"]
    assert "worth" not in eintrag["payload"], (
        "seit Fassung 3 wird das Modell nicht mehr nach dem Nutzen gefragt")
    assert eintrag["payload"]["confidence"] == "high"


def test_ohne_belege_wird_gar_nicht_erst_gefragt(cities, rats, monkeypatch):
    """Ein Urteil ohne Grundlage ist eine Behauptung. Der Rückblick allein
    trägt sie nicht — er sagt, was die Stadt beschäftigt, nicht ob sie dieses
    Instrument hat."""
    cities._conn.execute("DELETE FROM object_embeddings")
    cities._conn.execute("DELETE FROM papers_fts")
    aufrufe = []
    monkeypatch.setattr(fit_modul.llm, "chat_complete",
                        lambda **kw: (aufrufe.append(1), _antwort(URTEIL))[1])
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert not aufrufe, "ohne tragenden Beleg darf kein Modell gefragt werden"
    assert stand["skipped_no_evidence"] == 1 and stand["annotated"] == 0


def test_suchbegriffe_werden_je_vorlage_genau_einmal_geholt(cities, rats, monkeypatch):
    """Der Aufruf, der den Bestandslauf lange gebremst hat, darf sich nicht
    verdoppeln.

    Die Suchwörter (»wie hieße das in Oldenburg?«) werden seit 09.09.2026
    für einen ganzen Block VORAB geholt, nebenläufig — das ist der Grund,
    warum die Belegsammlung über 9.688 Vorlagen sieben statt 73 Minuten
    braucht. Sie gehen danach als ``begriffe`` in ``evidence_for``. Fällt
    dieses Durchreichen weg, holt die Belegsuche sie ein zweites Mal:
    doppelte Kosten, doppelte Wartezeit, **kein roter Test** — die Belege
    kämen ja richtig heraus. Deshalb wird hier gezählt.
    """
    from council.cities import evidence as ev
    geholt: list[str] = []

    def zaehlend(klasse, papier):
        geholt.append(papier["id"])
        return ev._woerter(klasse.get("instrument") or "")

    monkeypatch.setattr(ev, "search_terms", zaehlend)
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert geholt.count("os:p:1") == 1, (
        "die Suchwörter wurden zweimal geholt — `begriffe` kommt nicht "
        "mehr aus dem Vorlauf in `evidence_for` an")


class _MitwissendeVerbindung:
    """Reicht alles an die echte Verbindung durch und merkt sich den Thread.

    Kein Ersatz für die Verbindung, sondern ein Mithörer: `__getattr__`
    reicht durch, die beiden Kontext-Haken müssen ausgeschrieben stehen
    (Python sucht Dunder-Methoden am TYP, nicht über `__getattr__`).
    """

    def __init__(self, conn):
        self._conn = conn
        self.threads: set[str] = set()

    def execute(self, *a, **kw):
        self.threads.add(threading.current_thread().name)
        return self._conn.execute(*a, **kw)

    def executemany(self, *a, **kw):
        self.threads.add(threading.current_thread().name)
        return self._conn.executemany(*a, **kw)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *a):
        return self._conn.__exit__(*a)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_arbeiter_fassen_die_datenbank_nicht_an(cities, rats, monkeypatch):
    """Eine SQLite-Verbindung gehört einem Thread — auch beim LESEN.

    Bis 09.09.2026 stand im Modulkopf nur „geschrieben wird im Hauptthread",
    und der Prompt holte sich den Vorlagentext mit `text_for_paper` aus dem
    Arbeiter. Bei vier Arbeitern fiel das nie auf; beim Bestandslauf mit
    vierzig warf SQLite `InterfaceError: bad parameter or other API misuse`.
    Der Fehler wurde als „eine Vorlage gescheitert" gezählt und
    VERSCHLUCKT — der Lauf lief weiter, die Stimme fehlte.

    Deshalb die schärfere Regel: Was aus der Datenbank kommt, wird vorher
    eingesammelt. Der Arbeiter rechnet und ruft das Modell, sonst nichts.
    """
    horcher = _MitwissendeVerbindung(cities._conn)
    monkeypatch.setattr(cities, "_conn", horcher)
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=4)
    fremde = {t for t in horcher.threads if t != threading.main_thread().name}
    assert not fremde, (
        f"die Datenbank wurde aus {sorted(fremde)} gelesen — alles, was aus "
        "ihr kommt, gehört VOR den Lauf der Arbeiter")


def test_stichprobe_bricht_bei_totem_beleg_arm_ab(cities, rats, monkeypatch):
    """Ein Arm, der nichts mehr liefert, beendet den Lauf — statt ihn zu bezahlen.

    Zweimal am 09.09.2026 lief `fit` über Stunden mit einem stummen Arm
    durch: erst ohne Index (`cluster` und `neighbor` leer), dann mit einer
    Nachbartabelle, die nach dem Index über alle Städte auf fremde Städte
    zeigte. Beide Male gab es keine Fehlermeldung, nur schlechtere Urteile
    und je gut $15.

    Hier steht Oldenburgs Papier-Matrix voll (es GIBT Vektoren), aber der
    Arm findet nichts — der Fall, in dem Weiterlaufen sinnlos ist.
    """
    oldenburger_nachbar(cities, "oldenburg:paper:4711", 0.84)
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    monkeypatch.setattr(fit_modul.beleg_modul, "_nachbar_treffer",
                        lambda *a, **kw: [])
    with pytest.raises(fit_modul.LaufAbbruch, match="neighbor"):
        fit_modul.run(cities, rats, get("fit"), MODELL, workers=1, probe_after=1)


def test_stichprobe_laeuft_durch_wenn_die_arme_liefern(cities, rats, monkeypatch):
    """Die Gegenrichtung: Ein Wächter, der immer anschlägt, ist keiner."""
    oldenburger_nachbar(cities, "oldenburg:paper:4711", 0.84)
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(URTEIL))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1, probe_after=1)
    assert stand["annotated"] == 1
    assert stand["probe"]["neighbor"] >= 1, "der Arm liefert, das muss die Probe sehen"


def test_erfundene_kennung_wird_nicht_gespeichert(cities, rats, monkeypatch):
    """JEDE Stimme wird einzeln geprüft — sonst trüge die Mehrheit die
    Erfindung mit, weil zwei andere Stimmen sie überstimmen."""
    kaputt = dict(URTEIL, evidence=["oldenburg:paper:12345"])
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(kaputt))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 0
    assert stand["hallucinated_evidence"] == fit_modul.VOTES
    assert cities.annotation("paper", "os:p:1", "fit", get("fit").version) is None


def test_kaputte_antwort_kippt_den_lauf_nicht(cities, rats, monkeypatch):
    """Dieselbe Lehre wie beim Einordnungslauf: Ein Batch aus Unsinn darf
    nicht 500 gute Urteile mitreißen."""
    monkeypatch.setattr(fit_modul.llm, "chat_complete",
                        lambda **kw: _antwort({"status": "irgendwas"}))
    stand = fit_modul.run(cities, rats, get("fit"), MODELL, workers=1)
    assert stand["annotated"] == 0 and stand["errors"] == fit_modul.VOTES


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
    oldenburger_nachbar(cities, "oldenburg:paper:5000", 0.81)
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
    nutzlast = OldenburgStatus(status="present", evidence=["recap:klima_umwelt"], confidence="high")
    erlaubt = {"recap:klima_umwelt", "oldenburg:paper:1"}
    assert fit_modul.pruefe(nutzlast, erlaubt, {"oldenburg:paper:1"}) == "claim_only_on_recap"
    # Mit einem tragenden Beleg daneben ist der Rückblick unschädlich.
    mit = OldenburgStatus(status="present", confidence="high",
                       evidence=["recap:klima_umwelt", "oldenburg:paper:1"])
    assert fit_modul.pruefe(mit, erlaubt, {"oldenburg:paper:1"}) is None


def test_zu_langer_freitext_wird_gekuerzt_nicht_verworfen():
    """Die Längen sind Anzeige-Grenzen, keine Zusagen. Im Bestandslauf über
    300 Vorlagen gingen zwei vollständig richtige Urteile verloren, beide weil
    `obstacles` zwanzig Zeichen zu lang war."""
    f = OldenburgStatus(status="missing", confidence="low", reason="y" * 500)
    assert len(f.reason) == 300


def test_die_behauptungen_bleiben_streng():
    """Ein unerwarteter Status ist kein Formfehler, sondern ein Urteil, das
    niemand einordnen kann — das wird verworfen, nicht zurechtgebogen."""
    import pytest as _pytest
    from pydantic import ValidationError as _VE

    for kaputt in ({"status": "vorhanden"},
                   {"confidence": "hoch"}):
        with _pytest.raises(_VE):
            OldenburgStatus(**{"status": "missing",
                            "confidence": "low", **kaputt})


# ------------------------------------------------------- Die vier Beleg-Arme

def test_belege_kommen_aus_vier_quellen(cities, rats):
    """Nachbar, Textabschnitt, Volltext, Beschluss — plus der Rückblick.

    Jeder Arm findet etwas, das die anderen verfehlen: der Nachbar das
    inhaltlich Verwandte, der Chunk die Sache auf Seite elf einer großen
    Vorlage, der Volltext das wörtlich Gleiche, der Beschluss das Ergebnis
    der Abstimmung — das einzige, was der Städte-Speicher für Oldenburg gar
    nicht trägt.
    """
    from council.cities.evidence import evidence_for
    klasse = cities.annotations_for("classify", "2")["os:p:1"]
    belege = evidence_for(cities, rats, cities.paper("os:p:1"), klasse, MODELL)
    arten = {b.kind for b in belege}
    assert "neighbor" in arten, "der nächste Nachbar fehlt"
    assert "recap" in arten, "der Themenfeld-Rückblick fehlt"
    assert all(b.id for b in belege), "ein Beleg ohne Kennung ist nicht zitierbar"
    assert len({b.id for b in belege}) == len(belege), "Belege müssen eindeutig sein"


def test_beschluss_belege_tragen_ihre_eigene_kennung(rats):
    """`oldenburg:decision:<id>` — ein anderer Raum als `oldenburg:paper:<kvonr>`.

    Ein Beschluss ist nicht die Vorlage: Er trägt Ergebnis, Gremium und Datum
    der Sitzung, in der abgestimmt wurde. `kvonr_aus` darf ihn deshalb nicht
    für eine Vorlage halten.
    """
    from council.cities.evidence import _aus_beschluss, kvonr_aus
    assert kvonr_aus("oldenburg:decision:1") is None
    beleg = _aus_beschluss(rats, "oldenburg:decision:1", None)
    assert beleg.kind == "decision"
    assert beleg.title == "Kommunale Wärmeplanung"
    assert beleg.outcome == "accepted", "das Ergebnis ist der Punkt an dieser Quelle"
    assert "Wärmeplan" in beleg.text


def test_beschluss_beleg_traegt_ein_urteil(rats):
    """Ein Beschluss ist der STÄRKSTE Beleg — er muss tragend sein."""
    assert "decision" in fit_modul.TRAGENDE_ARTEN
    assert "chunk" in fit_modul.TRAGENDE_ARTEN
    assert "recap" not in fit_modul.TRAGENDE_ARTEN


def test_suchbegriffe_fallen_auf_die_instrumentwoerter_zurueck(monkeypatch):
    """Scheitert das Modell, bleibt der Stand vor diesem Ausbau — nicht nichts."""
    from council.cities import evidence as ev
    monkeypatch.undo()   # die autouse-Fixture aushebeln, hier geht es um `search_terms`

    def kaputt(**kw):
        raise RuntimeError("Provider weg")

    monkeypatch.setattr(ev.llm, "chat_complete", kaputt)
    begriffe = ev.search_terms({"instrument": "Qualitätshandbuch für ASD einführen"},
                               {"name": "Titel"})
    assert "Qualitätshandbuch" in begriffe
    assert ev.search_terms({}, {}) == [], "ohne Instrument gibt es nichts zu suchen"


def test_rrf_belohnt_was_zwei_arme_finden():
    """Der Kern der Fusion: Vier Arme liefern unvergleichbare Werte, aber jeder
    liefert eine Rangfolge. Ein Papier, das zwei Arme finden, gehört nach oben —
    und das ist genau das Papier, das ein Mensch als Beleg genommen hätte."""
    from council.cities.evidence import _rrf
    punkte = _rrf([["a", "b", "c"], ["c", "d"], ["e"]])
    assert max(punkte, key=lambda k: punkte[k]) == "c", \
        "c steht in zwei Listen und schlägt das a, das nur in einer vorn steht"


# ------------------------------------------------------- Mehrheit aus Stimmen

def _urteil(status="partial", belege=("oldenburg:paper:4711",),
            confidence="high"):
    return OldenburgStatus(status=status, evidence=list(belege),
                           reason="Grund.", confidence=confidence)


def test_die_mehrheit_entscheidet_den_status():
    """Zwei von drei Stimmen tragen das Urteil, und die Einigkeit steht dabei."""
    ergebnis, einigkeit = fit_modul.majority([
        _urteil(status="partial"),
        _urteil(status="missing"),
        _urteil(status="partial"),
    ])
    assert ergebnis.status == "partial"
    assert einigkeit == "2/3"


def test_bei_patt_gewinnt_der_vorsichtigere_wert():
    """„Oldenburg hat das schon" nimmt eine Idee von der Liste — der teurere
    Irrtum. Bei Gleichstand fällt die Wahl deshalb nach unten."""
    ergebnis, _ = fit_modul.majority([
        _urteil(status="present"), _urteil(status="missing"), _urteil(status="partial")])
    assert ergebnis.status == "missing"


def test_nur_belege_die_zwei_stimmen_nennen():
    """Eine Kennung, die nur ein Lauf gesehen hat, trägt kein Urteil."""
    ergebnis, _ = fit_modul.majority([
        _urteil(belege=["oldenburg:paper:1", "oldenburg:paper:2"]),
        _urteil(belege=["oldenburg:paper:1"]),
        _urteil(belege=["oldenburg:paper:1", "oldenburg:paper:3"]),
    ])
    assert ergebnis.evidence == ["oldenburg:paper:1"]


def test_uneinigkeit_senkt_die_zuversicht():
    einig, _ = fit_modul.majority([_urteil(), _urteil(), _urteil()])
    assert einig.confidence == "high", "drei gleiche Stimmen behalten ihre Zuversicht"
    uneinig, _ = fit_modul.majority([
        _urteil(status="present"), _urteil(status="missing"), _urteil(status="partial")])
    assert uneinig.confidence == "low", "ein Patt ist kein sicheres Urteil"


def test_eine_einzelne_stimme_bleibt_gueltig():
    """Verwirft `pruefe` zwei von drei, bleibt die dritte — mit `low`."""
    ergebnis, einigkeit = fit_modul.majority([_urteil(confidence="high")])
    assert ergebnis.status == "partial" and einigkeit == "1/1"
    assert ergebnis.evidence == ["oldenburg:paper:4711"], \
        "bei einer Stimme reicht EINE Nennung, sonst bliebe kein Beleg übrig"


# ------------------------------------------------- Cluster im Prompt und Urteil

def test_der_cluster_ist_ein_tragender_beleg():
    assert "cluster" in fit_modul.TRAGENDE_ARTEN


def test_ohne_cluster_sagt_die_zeile_das_deutlich(cities):
    """Kein Cluster heißt: keine andere Stadt hat etwas Ähnliches — und das
    sagt für sich genommen NICHTS über Oldenburg."""
    from council.cities.evidence import cluster_zeile
    zeile = cluster_zeile(cities, cities.paper("os:p:1"), MODELL)
    assert "keiner" in zeile and "nichts über Oldenburg" in zeile


def test_die_cluster_zeile_nennt_die_fremden_mitglieder(cities):
    """Namentlich, nicht gezählt: An vierzehn gelesenen Clustern waren drei
    falsch gruppiert — ein Modell, das die Titel sieht, kann das erkennen."""
    from council.cities.clusters import CLUSTER_VERSION
    from council.cities.evidence import cluster_zeile
    cities.replace_idea_clusters(MODELL, CLUSTER_VERSION, [
        (MODELL, CLUSTER_VERSION, 1, "os:p:1", 0.9),
        (MODELL, CLUSTER_VERSION, 1, "oldenburg:paper:4711", 0.88),
    ])
    zeile = cluster_zeile(cities, cities.paper("oldenburg:paper:4711"), MODELL)
    assert "osnabrueck" in zeile and "Wärmenetz" in zeile
    assert "Gruppierung irrt" in zeile, "das Modell muss ein schlechtes Mitglied verwerfen können"


def test_der_aufwand_steht_im_vorlagentext():
    """Zwei der drei „lohnt sich"-Bedingungen hängen daran."""
    text = fit_modul.paper_text(
        {"body_id": "osnabrueck", "name": "Titel", "kind": "motion"},
        {"instrument": "Etwas tun"}, None, get("fit"),
        {"effort": "resolution", "addressee": "Bund"})
    assert "resolution" in text and "Bund" in text
    assert "nicht die Stadt selbst" in text
