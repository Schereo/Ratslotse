"""Das Urteil je IDEE über Oldenburg (``idea_fit``, Plan PR 48).

Vier Zusagen: Eine Kennung, die dem Modell nicht vorlag, fliegt raus — auch
unter „verwandt". Bei Gleichstand gewinnt die schwächere Behauptung. Die
Voraussetzungsfrage aus #1404 steht wörtlich im Prompt. Und ein Urteil hängt
an seiner Fassung: Eine neue Fassung urteilt neu.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from council.cities import clusters
from council.cities import idea_fit
from council.cities.annotators import IdeaVerdict
from council.cities.annotators import get as get_annotator
from council.cities.index import EMBED_MODEL
from council.cities.model import Batch, Paper
from council.cities.store import CitiesStore
from council.store import CouncilStore
from kern import prompts


def _urteil(**kw) -> IdeaVerdict:
    grund = {"status": "missing", "situation": "Nichts.", "evidence": [],
             "related": [], "confidence": "medium"}
    return IdeaVerdict.model_validate({**grund, **kw})


# --------------------------------------------------------------- Prüfung


def test_fremde_kennung_fliegt_raus_auch_unter_verwandt():
    erlaubt = {"oldenburg:paper:1", "oldenburg:paper:2"}
    assert idea_fit.pruefe(_urteil(related=["oldenburg:paper:9"]), erlaubt) \
        .startswith("hallucinated_evidence")
    assert idea_fit.pruefe(_urteil(status="present", evidence=["oldenburg:paper:9"]),
                           erlaubt).startswith("hallucinated_evidence")
    assert idea_fit.pruefe(_urteil(related=["oldenburg:paper:2"]), erlaubt) is None


def test_behauptung_braucht_beleg():
    assert idea_fit.pruefe(_urteil(status="partial"), set()) == "claim_without_evidence"
    assert idea_fit.pruefe(_urteil(status="not_applicable"), set()) is None


def test_beleg_ohne_behauptung_wird_verwandt():
    """Bei „fehlt" ist ein Beleg ein Formfehler, kein falsches Urteil."""
    u = idea_fit.bereinigen(_urteil(evidence=["a"], related=["b"]))
    assert u.evidence == [] and u.related == ["a", "b"]


def test_keine_kennung_in_beiden_listen():
    u = idea_fit.bereinigen(_urteil(status="partial", evidence=["a"], related=["a", "b"]))
    assert u.evidence == ["a"] and u.related == ["b"]


def test_gleichstand_geht_an_die_schwaechere_behauptung():
    stimmen = [_urteil(status="missing"),
               _urteil(status="not_applicable"),
               _urteil(status="partial", evidence=["a"])]
    ergebnis, einig = idea_fit.majority(stimmen)
    assert ergebnis.status == "missing" and einig == "1/3"


def test_verwandt_nur_was_zwei_stimmen_nennen():
    stimmen = [_urteil(related=["a", "b"]), _urteil(related=["a"]), _urteil(related=["c"])]
    ergebnis, _ = idea_fit.majority(stimmen)
    assert ergebnis.related == ["a"]


def test_zu_langer_satz_wird_gekuerzt():
    assert len(_urteil(situation="x" * 400).situation) == 300


# ----------------------------------------------------------------- Prompt


def test_der_prompt_stellt_die_voraussetzungsfrage_woertlich():
    """Die Trennlinie aus #1404, aus dem `fit`-Prompt GESCHNITTEN."""
    text = prompts.render("cities_idea_fit_system", steckbrief="S",
                          regel_nicht_anwendbar=prompts.REGEL_NICHT_ANWENDBAR)
    assert "Könnte der Oldenburger Rat diese" in text
    assert "Jugendparlament" in text, "die JA-Seite der Abgrenzung fehlt"
    assert prompts.REGEL_NICHT_ANWENDBAR in prompts.get("cities_fit_system"), \
        "die Regel ist nicht mehr wörtlich dieselbe wie bei `fit`"
    assert "gehört unter \"related\"" in text


def test_der_quell_hash_haengt_an_der_fassung():
    ann = get_annotator("idea_fit")
    gruppe = {"label": "Hitzeaktionsplan"}
    mitglieder = [{"id": "ha/1"}, {"id": "ms/1"}]
    a = idea_fit.source_hash(gruppe, mitglieder, [], ann)
    from dataclasses import replace
    b = idea_fit.source_hash(gruppe, mitglieder, [], replace(ann, version="99"))
    c = idea_fit.source_hash(gruppe, [*mitglieder, {"id": "po/1"}], [], ann)
    assert len({a, b, c}) == 3


# ------------------------------------------------------------------- Lauf


@pytest.fixture()
def staende(tmp_path):
    rats = CouncilStore(tmp_path / "council.sqlite")
    with CitiesStore(tmp_path / "c.sqlite") as s:
        s.upsert_batch(Batch(papers=[
            Paper("ha/1", "hannover", "Hitzeaktionsplan", date="2024-01-01", kind="motion"),
            Paper("ms/1", "muenster", "Hitzeschutz", date="2025-01-01", kind="motion"),
            Paper("oldenburg:paper:7", "oldenburg", "Hitze-Info Oldenburg",
                  date="2023-06-01", kind="motion"),
        ]))
        for pid, inst in (("ha/1", "Hitzeaktionsplan aufstellen"),
                          ("ms/1", "Hitzeaktionsplan erstellen"),
                          ("oldenburg:paper:7", "Hitzeinformation")):
            s.put_annotation("paper", pid, "classify", "2",
                             {"field": "klima_umwelt", "transfer": "direct",
                              "competence": "own", "instrument": inst,
                              "summary": inst}, "h", "m", 0.0)
        s.put_annotation("paper", "ha/1", "fit", "5",
                         {"status": "missing", "evidence": [], "reason": "fehlt",
                          "confidence": "low"}, "h", "m", 0.0)
        s.replace_idea_clusters(EMBED_MODEL, "1", [
            (EMBED_MODEL, "1", 1, pid, sc) for pid, sc in
            (("ha/1", 0.9), ("ms/1", 0.8), ("oldenburg:paper:7", 0.7))])
        clusters.rebuild_idea_groups(s)
        yield s, rats
    rats.close()


def _antwort(daten: dict):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(daten)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.001))


def test_ein_lauf_schreibt_ein_urteil_und_dann_keins_mehr(staende, monkeypatch):
    main, rats = staende
    gesehen: list[str] = []

    def antwort(**kw):
        gesehen.append(kw["messages"][1]["content"])
        return _antwort({"status": "partial", "situation": "Oldenburg informiert über Hitze.",
                         "evidence": ["oldenburg:paper:7"], "related": [],
                         "confidence": "medium"})

    monkeypatch.setattr(idea_fit.llm, "chat_complete", antwort)
    stand = idea_fit.run(main, rats, EMBED_MODEL, suche=False)
    assert stand["annotated"] == 1 and stand["votes"] == 3
    assert abs(stand["cost_usd"] - 0.003) < 1e-9
    urteil = main.annotation("cluster", "1:1", "idea_fit", "1")["payload"]
    assert urteil["status"] == "partial" and urteil["evidence"] == ["oldenburg:paper:7"]
    assert "Hannover" in gesehen[0] or "hannover" in gesehen[0]
    assert "fehlt" in gesehen[0], "die Einzelurteile stehen als Hinweis im Prompt"
    assert "oldenburg:paper:7" in gesehen[0], "Oldenburgs Mitglied ist ein Beleg"

    zeilen, gesamt = main.idea_groups(EMBED_MODEL, "1", oldenburg=("partial",))
    assert gesamt == 1

    stand = idea_fit.run(main, rats, EMBED_MODEL, suche=False)
    assert stand["annotated"] == 0 and stand["unchanged"] == 1, \
        "unverändert heißt: kein zweiter Modellaufruf"


def test_eine_erfundene_kennung_schreibt_nichts(staende, monkeypatch):
    main, rats = staende
    monkeypatch.setattr(idea_fit.llm, "chat_complete", lambda **kw: _antwort(
        {"status": "present", "situation": "…", "evidence": ["oldenburg:paper:999"],
         "related": [], "confidence": "high"}))
    stand = idea_fit.run(main, rats, EMBED_MODEL, suche=False)
    assert stand["annotated"] == 0 and stand["hallucinated_evidence"] == 3
    assert main.annotation("cluster", "1:1", "idea_fit", "1") is None
