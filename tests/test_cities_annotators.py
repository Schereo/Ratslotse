"""Annotator-Registry, Antwort-Parser und der Lauf — ohne Netz.

Der Parser ist der Teil, der im Probelauf am meisten Ärger gemacht hat:
Modelle antworten mal mit Code-Zaun, mal mit führendem Leerzeichen, mal mit
Vorrede — und manchmal gar nicht, weil sie ihr Token-Budget beim Denken
verbraucht haben (Status 200, leerer Inhalt).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from council.cities import annotate
from council.cities.annotators import (
    ANNOTATORS, COMPETENCE_VALUES, TRANSFER_VALUES, USABLE, PaperClassification,
    active_annotators, get,
)
from council.cities.model import Batch, File, FileRole, Paper
from council.cities.store import CitiesStore
from council.topics import POLICY_FIELDS
from kern import prompts

WURZEL = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ Registry

def test_jeder_annotator_ist_vollstaendig():
    for ann in ANNOTATORS.values():
        assert prompts.get(ann.prompt_system), f"{ann.key}: Prompt fehlt"
        assert prompts.get(ann.prompt_user)
        assert ann.applies_to and all(k in ("paper", "agenda_item", "meeting")
                                      for k in ann.applies_to)
        assert ann.version, f"{ann.key}: ohne Fassung ist keine zweite möglich"
        assert ann.batch_size >= 1 and ann.max_tokens >= 4000
        assert ann.gut_wenn, (
            f"{ann.key}: ohne `gut_wenn` weiß niemand, wann die Fassung reif ist "
            f"— dieselbe Regel wie `fertig_wenn` bei den Feature-Schaltern.")


def test_jeder_aktive_annotator_hat_ein_golden_set():
    """Ohne Maßstab ist eine Prompt-Änderung ein Bauchgefühl."""
    for ann in active_annotators():
        treffer = list((WURZEL / "eval").glob(f"cases_cities_{ann.key}*.json")) + \
                  list((WURZEL / "eval").glob("cases_cities_transfer*.json"))
        assert treffer, (
            f"{ann.key}: kein Golden Set in eval/. Ein Annotator ohne Maßstab "
            f"lässt sich nicht verbessern, nur verändern.")


def test_der_prompt_kennt_dieselben_themenfelder_wie_oldenburg():
    """Eine eigene Liste für fremde Städte wäre der sichere Weg, den Vergleich
    unmöglich zu machen."""
    text = prompts.render("cities_classify_system", fields=annotate.field_list())
    for schluessel in POLICY_FIELDS:
        assert schluessel in text, f"Themenfeld {schluessel} fehlt im Prompt"


def test_der_prompt_zaehlt_die_pflichtgeschaefte_auf():
    """Die zweite Fassung unterscheidet sich genau darin von der ersten —
    und das war der Sprung von 73 auf rund 90 Prozent."""
    text = prompts.get("cities_classify_system")
    for wort in ("Haushaltsvollzug", "Jahresabschl", "Gebührenkalkulation",
                 "Stellenplan", "Dienstreisen"):
        assert wort in text, f"{wort} fehlt — ist das noch Fassung 2?"


def test_payload_laesst_nur_bekannte_werte_zu():
    gut = PaperClassification(field="verkehr", transfer="adaptable",
                              competence="council", summary="Ein Satz.")
    assert gut.usable is True
    assert PaperClassification(field="verkehr", transfer="local",
                               competence="council").usable is False
    with pytest.raises(ValidationError):
        PaperClassification(field="gibt_es_nicht", transfer="adaptable", competence="council")
    with pytest.raises(ValidationError):
        PaperClassification(field="verkehr", transfer="vielleicht", competence="council")


def test_die_wertelisten_passen_zusammen():
    assert set(USABLE) <= set(TRANSFER_VALUES)
    assert "council" in COMPETENCE_VALUES


# -------------------------------------------------------------------- Parser

@pytest.mark.parametrize("antwort,erwartet", [
    ('{"results": [{"id": "a"}]}', 1),
    (' {"results": [{"id": "a"}]}', 1),                       # führendes Leerzeichen
    ('```json\n{"results": [{"id": "a"}]}\n```', 1),          # Code-Zaun
    ('```\n{"results": [{"id": "a"}]}\n```', 1),
    ('Gern! {"results": [{"id": "a"}]} Viel Erfolg.', 1),     # Vorrede
])
def test_parse_json_kommt_mit_allen_formen_klar(antwort, erwartet):
    assert len(annotate.parse_json(antwort)["results"]) == erwartet


def test_parse_json_gibt_immer_ein_objekt_zurueck():
    """Eine Liste an der Wurzel ist gültiges JSON — der Aufrufer greift gleich
    danach mit `.get` zu und stürbe an einer Stelle, die nichts mehr über die
    Ursache weiß. Steckt ein Objekt im Text, wird es geborgen; sonst fliegt
    ein ValueError mit dem Anfang der Antwort darin."""
    assert annotate.parse_json('[{"results": []}]') == {"results": []}
    assert annotate.parse_json('[1,2] danach {"results": []}') == {"results": []}
    with pytest.raises(ValueError, match="unlesbar"):
        annotate.parse_json('[1, 2, 3]')
    with pytest.raises(ValueError, match="unlesbar"):
        annotate.parse_json('"nur ein String"')


def test_parse_json_nennt_die_leere_antwort_beim_namen():
    """Sie kommt mit Status 200 und ist der häufigste Fehler bei
    Reasoning-Modellen mit zu knappem Budget."""
    with pytest.raises(ValueError, match="leere Antwort"):
        annotate.parse_json("")
    with pytest.raises(ValueError, match="unlesbar"):
        annotate.parse_json("kein JSON weit und breit")


# ---------------------------------------------------------------- source_hash

def test_source_hash_reagiert_auf_das_was_zaehlt():
    ann = get("classify")
    papier = {"name": "Mehrweg fördern", "date": "2026-06-30", "paper_type_raw": "Antrag"}
    basis = annotate.source_hash(papier, "Text", ann)
    assert annotate.source_hash(papier, "Text", ann) == basis
    assert annotate.source_hash(dict(papier, name="Anders"), "Text", ann) != basis
    assert annotate.source_hash(papier, "Anderer Text", ann) != basis
    # Text jenseits des Fensters ändert nichts — sonst rechnete jeder Lauf neu.
    lang = "T" * (ann.input_chars + 500)
    assert annotate.source_hash(papier, lang, ann) == \
           annotate.source_hash(papier, lang + "Anhang", ann)


# ----------------------------------------------------------------------- Lauf

@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_batch(Batch(
        papers=[Paper(f"p{i}", "osnabrueck", f"Vorlage {i}", date="2026-06-01",
                      paper_type_raw="Antrag") for i in range(3)],
        files=[File(f"f{i}", "osnabrueck", FileRole.MAIN, paper_id=f"p{i}") for i in range(3)]))
    for i in range(3):
        s.put_text(f"f{i}", "pypdf", "1", f"Der Rat möge beschließen, Sache {i}.", 1, "ok")
    yield s
    s.close()


def _antwort(ids, **felder):
    inhalt = json.dumps({"results": [
        dict({"id": i, "field": "verkehr", "transfer": "adaptable",
              "competence": "council", "summary": "Ein Satz."}, **felder) for i in ids]})
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, cost=0.0001))


def test_lauf_schreibt_annotationen(store, monkeypatch):
    monkeypatch.setattr(annotate.llm, "chat_complete",
                        lambda **kw: _antwort(["p0", "p1", "p2"]))
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 3 and stand["errors"] == 0
    eintrag = store.annotation("paper", "p0", "classify", "2")
    assert eintrag["payload"]["transfer"] == "adaptable"
    assert eintrag["model"] == get("classify").model


def test_zweiter_lauf_rechnet_nichts_neu(store, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(annotate.llm, "chat_complete",
                        lambda **kw: (aufrufe.append(1), _antwort(["p0", "p1", "p2"]))[1])
    annotate.run(store, get("classify"), workers=1)
    vorher = len(aufrufe)
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 0
    assert len(aufrufe) == vorher, "ein zweiter Lauf darf kein Modell mehr fragen"


def test_geaenderter_text_wird_neu_eingeordnet(store, monkeypatch):
    monkeypatch.setattr(annotate.llm, "chat_complete",
                        lambda **kw: _antwort(["p0", "p1", "p2"]))
    annotate.run(store, get("classify"), workers=1)
    store.put_text("f0", "pypdf", "1", "Ein ganz anderer Sachverhalt.", 1, "ok")
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] >= 1, "der source_hash muss die Änderung bemerken"


def test_ausgelassene_werden_einzeln_nachgereicht(store, monkeypatch):
    """Modelle lassen in Batches Einträge aus — im Probelauf bis zu einem Viertel."""
    gesehen = []

    def antwort(**kw):
        text = kw["messages"][1]["content"]
        ids = [i for i in ("p0", "p1", "p2") if f"id {i}\n" in text]
        gesehen.append(tuple(ids))
        # Beim ersten (großen) Batch fehlt p2; einzeln kommt er dann.
        return _antwort([i for i in ids if not (len(ids) > 1 and i == "p2")])

    monkeypatch.setattr(annotate.llm, "chat_complete", antwort)
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 3
    assert ("p2",) in gesehen, "der Nachlauf muss den Ausgelassenen einzeln fragen"


def test_ergebnisse_die_keine_objekte_sind_kippen_den_lauf_nicht(store, monkeypatch):
    """Gemessen am Bestandslauf: Ein Batch kam als Liste von STRINGS zurück.
    Der Zugriff warf im Arbeitsthread, `pool.map` reichte das weiter — und
    riss den Lauf nach 520 von 619 Batches um."""
    def antwort(**kw):
        text = kw["messages"][1]["content"]
        ids = [i for i in ("p0", "p1", "p2") if f"id {i}\n" in text]
        if len(ids) > 1:            # der große Batch antwortet Unsinn
            inhalt = json.dumps({"results": ["p0", "p1", "p2"]})
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.0))
        return _antwort(ids)        # einzeln nachgereicht klappt es

    monkeypatch.setattr(annotate.llm, "chat_complete", antwort)
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 3, "der Nachlauf muss alle drei nachreichen"


def test_results_als_objekt_statt_liste_wirft_nicht(store, monkeypatch):
    """Dieselbe Klasse Fehler eine Ebene höher."""
    inhalt = json.dumps({"results": {"id": "p0"}})
    monkeypatch.setattr(annotate.llm, "chat_complete", lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.0)))
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 0


def test_kaputter_batch_kippt_den_lauf_nicht(store, monkeypatch):
    def antwort(**kw):
        raise RuntimeError("Provider überlastet")

    monkeypatch.setattr(annotate.llm, "chat_complete", antwort)
    stand = annotate.run(store, get("classify"), workers=1)
    assert stand["annotated"] == 0 and stand["errors"] >= 1


def test_halluzinierte_kennung_wird_verworfen(store, monkeypatch):
    monkeypatch.setattr(annotate.llm, "chat_complete",
                        lambda **kw: _antwort(["p0", "gibt-es-nicht"]))
    annotate.run(store, get("classify"), workers=1)
    assert store.annotation("paper", "gibt-es-nicht", "classify", "2") is None


def test_antwort_ausserhalb_der_form_wird_verworfen(store, monkeypatch):
    """Ein erfundenes Themenfeld darf nicht in die Datenbank."""
    monkeypatch.setattr(annotate.llm, "chat_complete",
                        lambda **kw: _antwort(["p0"], field="voelkerrecht"))
    annotate.run(store, get("classify"), workers=1)
    assert store.annotation("paper", "p0", "classify", "2") is None


def test_die_aufwandsklasse_laeuft_nach_der_einordnung():
    """`only_usable` heißt: Der Annotator BRAUCHT die Einordnung.

    Beide laufen im selben Durchgang (`needs_index=False`), und welcher zuerst
    drankommt, entscheidet die Reihenfolge in der Registry. Steht `effort` vor
    `classify`, sieht es im ersten Lauf einer neuen Stadt gar keine Kandidaten
    und schweigt — ohne Fehler, ohne Zeile im Log, einfach nichts. Deshalb
    steht die Reihenfolge hier als Zusage.
    """
    from council.cities.annotators import ANNOTATORS

    reihenfolge = list(ANNOTATORS)
    for key, ann in ANNOTATORS.items():
        if not ann.only_usable:
            continue
        assert reihenfolge.index("classify") < reihenfolge.index(key), (
            f"{key} braucht die Einordnung und muss NACH classify stehen")


def test_nur_uebertragbares_kostet_ein_viertel():
    """Die Aufwandsklasse fragt nur, wo die Frage Sinn ergibt.

    An einem Bebauungsplan stellt sich „was würde das den Rat kosten?" nicht —
    er ist nicht übertragbar, und das ist richtig so. Der Filter spart drei
    Viertel der Kosten (1.511 übertragbare von 24.591 Papieren, 08.09.2026).
    """
    from council.cities.annotators import get

    assert get("effort").only_usable is True
    assert get("classify").only_usable is False, \
        "die Einordnung entscheidet ERST, was übertragbar ist"
