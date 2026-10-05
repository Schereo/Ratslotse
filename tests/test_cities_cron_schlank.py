"""Der Städte-Cron schlank wieder an — und was dafür an den Daten stimmen muss.

Vom 20.09. bis 10/2026 war ``check_cities`` pausiert; neue Oldenburger
Beschlüsse bekamen kein „Anderswo". Wieder an heißt: täglich Oldenburg ohne
Modell, sonntags alles, EINE Kostengrenze für den ganzen Lauf, feste Nummern
für die Ideen-Gruppen (an ihnen hängen die Urteile), keine doppelten Ideen
mit wortgleicher Überschrift und keine Gegenanträge in der Bilanz der Idee.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from council.cities import clusters
from council.cities.index import EMBED_MODEL
from council.cities.model import Batch, Paper
from council.cities.store import CitiesStore
from kern.stopp import Stopp, aus_umgebung

# ------------------------------------------------------------ Kostengrenze


def test_die_kostengrenze_stoppt_wie_ein_deploy(tmp_path):
    stopp = Stopp(tmp_path, max_kosten=1.0)
    stopp.ausgeben(0.6)
    assert stopp.grund() is None
    stopp.ausgeben(0.5)
    grund = stopp.grund()
    assert grund is not None and grund.schluessel == "kosten"
    assert stopp.kosten == pytest.approx(1.1)


def test_ohne_kostengrenze_wird_nur_gezaehlt(tmp_path):
    stopp = Stopp(tmp_path)
    stopp.ausgeben(100.0)
    assert stopp.grund() is None and stopp.kosten == 100.0


def test_die_kostengrenze_kommt_aus_der_umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("CITIES_MAX_USD", "0,5")   # Tippfehler: Komma
    stopp = aus_umgebung(tmp_path, "X_FRIST", None, kosten_variable="CITIES_MAX_USD",
                         kosten_vorgabe=2.0)
    assert stopp.max_kosten is None, "ein unlesbarer Wert heißt keine Grenze, nicht null"
    monkeypatch.setenv("CITIES_MAX_USD", "0.5")
    assert aus_umgebung(tmp_path, "X_FRIST", None, kosten_variable="CITIES_MAX_USD",
                        kosten_vorgabe=2.0).max_kosten == 0.5
    monkeypatch.delenv("CITIES_MAX_USD")
    assert aus_umgebung(tmp_path, "X_FRIST", None, kosten_variable="CITIES_MAX_USD",
                        kosten_vorgabe=2.0).max_kosten == 2.0


def test_jede_stufe_mit_modell_meldet_ihre_kosten():
    """Eine Grenze, die eine Stufe nicht kennt, deckelt nichts."""
    from pathlib import Path

    for datei in ("fit.py", "annotate.py", "idea_fit.py", "clusters.py", "reasons.py"):
        quelle = Path("council/cities", datei).read_text()
        assert "ausgeben(" in quelle, f"{datei} meldet seine Kosten nicht an `stopp`"


# ------------------------------------------------------------ feste Nummern


def test_eine_gruppe_behaelt_ihre_nummer():
    alte = {"a": 7, "b": 7, "c": 9, "d": 9}
    # Neu: eine Vorlage dazu, und die Reihenfolge der Größe hat sich gedreht.
    nummern = clusters.stabile_nummern([["c", "d", "e", "f"], ["a", "b"]], alte, 9)
    assert nummern == [9, 7]


def test_eine_neue_gruppe_bekommt_nie_eine_vergebene_nummer():
    """Auch nicht die einer verschwundenen — unter ihr liegt noch ein Urteil."""
    nummern = clusters.stabile_nummern([["x", "y"]], {"a": 3}, hoechste=12)
    assert nummern == [13]


def test_wachsen_zwei_zusammen_erbt_die_mit_mehr_mitgliedern():
    alte = {"a": 22, "b": 22, "c": 22, "d": 168}
    assert clusters.stabile_nummern([["a", "b", "c", "d"]], alte, 168) == [22]


def test_zerfaellt_eine_behaelt_der_groessere_teil_die_nummer():
    alte = {"a": 5, "b": 5, "c": 5, "d": 5, "e": 5}
    assert clusters.stabile_nummern([["d", "e"], ["a", "b", "c"]], alte, 5) == [6, 5]


# ---------------------------------------------- gleiche Überschrift, eine Idee


def _vektor(*werte: float) -> np.ndarray:
    v = np.array(werte, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_zwei_gruppen_mit_gleicher_ueberschrift_werden_eine():
    """„Zweckentfremdungssatzung erlassen" stand als Idee 22 UND 168 da."""
    matrix = np.vstack([_vektor(1, 0.1, 0), _vektor(1, 0.12, 0),       # Gruppe A
                        _vektor(1, 0, 0.3), _vektor(1, 0, 0.32),        # Gruppe B
                        _vektor(0, 1, 0), _vektor(0, 1, 0.05)])         # anderes Thema
    instrumente = ["zweckentfremdungssatzung erlassen", "satzung gegen zweckentfremdung",
                   "zweckentfremdungssatzung erlassen", "wohnraumschutz",
                   "zweckentfremdungssatzung erlassen", "tempo 30"]
    vereint = clusters.gleiche_ideen_vereinen([[0, 1], [2, 3], [4, 5]], matrix, instrumente)
    assert sorted(map(sorted, vereint)) == [[0, 1, 2, 3], [4, 5]], (
        "wortgleich UND nah: eins; wortgleich, aber fern: bleibt getrennt")


# ------------------------------------------------ Gegenanträge in der Bilanz


@pytest.fixture()
def gruppe(tmp_path):
    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper("bs/1", "braunschweig", "Klimawirkungsprüfung", date="2024-10-09", kind="motion"),
            Paper("md/1", "magdeburg", "Klimarelevanzprüfung", date="2023-05-11", kind="motion"),
            Paper("md/2", "magdeburg", "Klimarelevanzprüfung streichen!", date="2024-10-07",
                  kind="motion"),
            Paper("po/1", "potsdam", "Klimacheck", date="2025-01-01", kind="motion"),
        ]))
        for pid, inst in (("bs/1", "Klimawirkungsprüfung einführen"),
                          ("md/1", "Klimarelevanzprüfung einführen"),
                          ("md/2", "Klimarelevanzprüfung einstellen"),
                          ("po/1", "Klimacheck einführen")):
            s.put_annotation("paper", pid, "classify", "2",
                             {"field": "klima_umwelt", "transfer": "direct",
                              "competence": "own", "instrument": inst, "summary": inst},
                             "h", "m", 0.0)
        s.replace_idea_clusters(EMBED_MODEL, "1", [
            (EMBED_MODEL, "1", 48, pid, 0.9) for pid in ("bs/1", "md/1", "md/2", "po/1")])
        for pid, haltung in (("bs/1", "for"), ("md/1", "for"), ("md/2", "against"),
                             ("po/1", "review")):
            s.put_annotation("paper", pid, "stance", "1", {"stance": haltung, "reason": ""},
                             "h", "m", 0.0)
        yield s


def test_ein_gegenantrag_zaehlt_nicht_fuer_die_idee(gruppe, monkeypatch):
    """Magdeburgs „Klimarelevanzprüfung streichen!" angenommen ist keine
    Zustimmung zur Klimawirkungsprüfung."""
    monkeypatch.setattr(gruppe, "outcome_for_paper",
                        lambda pid: {"outcome": "accepted" if pid == "md/2" else "rejected"})
    clusters.rebuild_idea_groups(gruppe)
    g = gruppe.idea_group(EMBED_MODEL, "1", 48)
    assert json.loads(g["outcomes"]) == {"rejected": 3}
    assert "md/2" not in {p["paper_id"] for p in json.loads(g["timeline"])}
    assert g["cities"] == 3 and g["members"] == 3


def test_sind_alle_dagegen_ist_die_gegenrichtung_die_sache(gruppe):
    for pid in ("bs/1", "md/1", "po/1"):
        gruppe.put_annotation("paper", pid, "stance", "1",
                              {"stance": "against", "reason": ""}, "h", "m", 0.0)
    clusters.rebuild_idea_groups(gruppe)
    assert gruppe.idea_group(EMBED_MODEL, "1", 48)["members"] == 4


def test_die_richtung_wird_schon_ab_zwei_staedten_gefragt():
    """258 von 905 Vorlagen auf der Ideen-Liste hatten keine Richtung — alle in
    Ideen aus zwei Städten (gemessen 03.10.2026)."""
    assert clusters.STANCE_AB_STAEDTEN == 2


# ------------------------------------------------------ Einordnen im Fenster


def test_einordnen_ueber_alle_staedte_bleibt_im_fenster(tmp_path, monkeypatch):
    """Ohne `body_id` lieferte die Arbeitsliste jede Vorlage ohne Einordnung —
    auch Hannovers Anfragen und alles vor 2023 (03.10.2026: 20.321 statt 1.119)."""
    from council.cities import annotate as annotate_modul
    from council.cities.annotators import get

    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper("ha/alt", "hannover", "Alt", date="2019-01-01", kind="motion"),
            Paper("ha/frage", "hannover", "Anfrage", date="2025-01-01", kind="inquiry"),
            Paper("ha/neu", "hannover", "Neu", date="2025-01-01", kind="motion"),
        ]))
        gefragt: list[str] = []

        def antwort(**kw):
            from types import SimpleNamespace
            inhalt = kw["messages"][1]["content"]
            gefragt.extend(pid for pid in ("ha/alt", "ha/frage", "ha/neu") if pid in inhalt)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"results": []}'))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0))

        monkeypatch.setattr(annotate_modul.llm, "chat_complete", antwort)
        annotate_modul.run(s, get("classify"), workers=1, nur_neu=True)
    assert set(gefragt) == {"ha/neu"}


# ------------------------------------------------------- Links ins Original


def test_somacos_vorlagen_bekommen_ihren_link():
    from council.cities.adapters.session import web_url_for
    assert web_url_for("https://ratsinfo.magdeburg.de/oparl/bodies/0001/papers/vo/240103") \
        == "https://ratsinfo.magdeburg.de/vo0050.asp?__kvonr=240103"
    assert web_url_for("https://oparl.stadt-muenster.de/bodies/0001/papers/vo/2004051320") \
        == ("https://www.stadt-muenster.de/sessionnet/sessionnetbi/"
            "vo0050.php?__kvonr=2004051320")
    # Eine Stadt ohne gemessenes Muster bekommt keinen geratenen Link.
    assert web_url_for("https://oparl.dresden.de/bodies/0001/papers/vo/1") is None


def test_der_link_kommt_beim_normalisieren(tmp_path):
    import json as json_
    from pathlib import Path

    from council.cities.adapters import get_adapter

    roh = json_.loads(Path("tests/fixtures/cities/magdeburg_papers.json").read_text())
    with CitiesStore(tmp_path / "raw.sqlite") as raw:
        for obj in (roh if isinstance(roh, list) else roh.get("data", []))[:3]:
            raw.put_raw_object("magdeburg", "paper", obj["id"], obj)
        batch = get_adapter("session").normalize("magdeburg", raw)
    assert batch.papers and all(p.web and "vo0050.asp?__kvonr=" in p.web
                                for p in batch.papers)


# ------------------------------------------------------------------- Cron


def test_werktags_ohne_netz_und_ohne_modell(monkeypatch, tmp_path):
    """`--nur-oldenburg` holt keine fremde Stadt und ruft kein Sprachmodell."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("check_cities_test",
                                                  Path("scripts/check_cities.py"))
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)

    geholt: list[str] = []
    monkeypatch.setattr(modul.pipeline, "fetch",
                        lambda spec, *a, **k: geholt.append(spec.id) or {})
    monkeypatch.setattr(modul.pipeline, "normalize", lambda *a, **k: {"papers": 0})
    monkeypatch.setattr(modul.pipeline, "extract_inline", lambda *a, **k: 0)
    monkeypatch.setattr(modul.pipeline, "extract", lambda *a, **k: {})
    indiziert: list = []
    monkeypatch.setattr(modul.pipeline, "index_all",
                        lambda main, body_id=None: indiziert.append(body_id) or {})
    for verboten in ("annotate", "cluster_all", "split_protocols"):
        monkeypatch.setattr(modul.pipeline, verboten,
                            lambda *a, _name=verboten, **k: (_ for _ in ()).throw(
                                AssertionError(_name)))
    monkeypatch.setenv("CITIES_DB", str(tmp_path / "c.sqlite"))
    zahlen = modul.main(nur_oldenburg=True)
    assert geholt == ["oldenburg"] and indiziert == ["oldenburg"]
    assert zahlen["mode"] == "oldenburg" and zahlen["cost_usd"] == 0


def test_der_volltextindex_schreibt_nur_was_sich_geaendert_hat(tmp_path):
    """Jeder Lauf schrieb alle 60.000 Zeilen neu — knapp eine Stunde (03.10.2026)."""
    from council.cities.index import build_fts

    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[Paper("a", "hannover", "Erster"),
                                     Paper("b", "hannover", "Zweiter")]))
        assert build_fts(s) == 2
        assert build_fts(s) == 0
        s.upsert_batch(Batch(papers=[Paper("b", "hannover", "Zweiter, neu benannt")]))
        assert build_fts(s) == 1
        assert [t["paper_id"] for t in s.fts_search("benannt")] == ["b"]
