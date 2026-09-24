"""Lottis Seitenkontext auf den Rats-Seiten (``council/page_context.py``).

Anlass: die Fakten-Eval vom 23.09.2026 (``docs/fakten-eval.md``). Auf Sitzungs-,
Personen-, Orts- und Themenseiten bekam Lotti einen Namen oder ein Datum,
während die Seite Tagesordnung, Ausschüsse und Beschlüsse zeigte — 17
Kontextfehler, die kein Modell beheben kann. Jeder Test hier hält eine Zusage
aus dem Modul: Was die Seite zeigt, steht im Prompt; was sie nicht zeigt,
nicht.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from council import assistant as lotti
from council import page_context as pc


class _Rat:
    """Ein Ratsspeicher mit je einem Gegenstand jeder Seitenart."""

    def get_session(self, ksinr):
        return {"ksinr": ksinr, "committee": "Rat", "session_date": "2026-09-28",
                "session_time": "18:00", "location": "Kulturzentrum PFL, Peterstraße 3"}

    def agenda_items(self, ksinr):
        return [
            {"item_number": "Ö 6", "title": "Ausschuss für Finanzen vom 02.09.2026", "is_public": 1},
            {"item_number": "Ö 6.3", "title": "Überplanmäßige Bewilligung von 9.512.500 Euro",
             "is_public": 1},
            {"item_number": "Ö 6.5", "title": "Klinikum Oldenburg AöR: Ausfallbürgschaft - "
                                               "Beschluss Beschluss: ungeändert beschlossen",
             "is_public": 1},
            {"item_number": "N 14", "title": "gesperrte Information", "is_public": 0},
            {"item_number": "N 15", "title": "gesperrte Information", "is_public": 0},
        ]

    def get_decisions(self, ksinr):
        return [{"id": 8677, "kind": "decision", "item_number": "6.3", "outcome": "accepted"},
                {"id": 8678, "kind": "subvote", "item_number": "6.3", "outcome": "rejected"},
                {"id": 9999, "kind": "decision", "item_number": "14", "outcome": "accepted"}]

    def get_attendance(self, ksinr):
        return [{"name": "Anne Vorsitz", "role": "chair"}, {"name": "Bert", "role": "member"}]

    def get_video_results(self, ksinr):
        return []

    def member_detail(self, slug):
        return {"name": "Renke Beispiel", "party": "SPD", "kind": "council", "n_sessions": 40,
                "active_from": "2021-11-22", "active_to": "2026-06-29",
                "faction_timeline": [{"label": "SPD", "first": "2021-11-22", "last": "2026-06-29"}],
                "ris": {"current_faction": "SPD", "memberships": [
                    {"committee": "Verkehrsausschuss", "role": "Ausschussvorsitzende/r",
                     "valid_from": "2021-11-01", "valid_until": None},
                    {"committee": "Rat", "role": "Ratsmitglied", "valid_from": "2011-11-08",
                     "valid_until": None},
                    {"committee": "Sportausschuss", "role": "Ausschussmitglied",
                     "valid_from": "2016-11-01", "valid_until": "2021-10-31"}]},
                "committees": [], "speeches_total": 12}

    def resolve_place(self, place_id):
        return SimpleNamespace(id=place_id, name="Alte Fleiwa", kind="neighborhood",
                               description="Quartier auf dem Gelände der Fleischwarenfabrik.")

    def count_decisions(self, district=""):
        return 17

    def search_decisions(self, district="", field="", limit=50, **kw):
        return [{"id": 9319, "title": "Bebauungsplan 855 – Satzungsbeschluss",
                 "committee": "Rat", "session_date": "2026-06-01", "outcome": "accepted"}]

    def entity_detail(self, slug):
        if slug != "fliegerhorst":
            return None
        return {"entity": {"slug": slug, "name": "Fliegerhorst", "kind": "project"},
                "description": "Ehemaliger Militärflugplatz, heute Wohnquartier.",
                "money": 0,
                "decisions": [{"id": 8541, "title": "Bebauungsplan N-777 G", "committee": "Rat",
                               "session_date": "2026-04-13", "outcome": "accepted"}]}

    def field_recaps_by_key(self):
        return {"verkehr": {"summary": "Der Rat treibt den Radverkehr voran.",
                            "period_from": "2026-04-13", "period_to": "2026-06-18"}}

    def get_decision(self, i):
        return {"id": i, "title": "Unterstützung Schwimmbad BTB", "committee": "Rat",
                "session_date": "2026-06-01", "outcome": "accepted", "vote": "majority",
                "abstentions": 9, "raw_result": "- einstimmig bei neun Enthaltungen -",
                "template_number": "26/0353",
                "official_text": "Das Schwimmbad wird weiterhin unterstützt."}

    def get_vorlage_by_nr(self, nr):
        return {"financial_impact": "2026: 173.000,00 Euro 2027: 177.500,00 Euro"}


def _block(route: str, **refs) -> str:
    return lotti._record_block(_Rat(), lotti.Screen(route=route, refs=refs))


# --- Sitzung ---------------------------------------------------------------

def test_die_sitzung_nennt_ort_und_uhrzeit():
    """Fall ``lotti-sitzung-2809-wann-wo``: Der Ort stand nie im Prompt."""
    block = _block("/council/sitzung", ksinr=4705)
    assert "28. September 2026, 18:00 Uhr" in block
    assert "Kulturzentrum PFL" in block


def test_die_sitzung_traegt_ihre_tagesordnung_samt_ergebnis():
    zeilen = pc.session_lines(_Rat(), 4705, heute=date(2026, 9, 1))
    text = "\n".join(zeilen)
    assert "Ö 6.3 Überplanmäßige Bewilligung von 9.512.500 Euro — angenommen (Nr. 8677)" in text
    # Der Änderungsantrag hängt am Hauptbeschluss, er ist nicht das Ergebnis des Punkts.
    assert "8678" not in text


def test_nichtoeffentliche_punkte_stehen_nur_als_zahl():
    """Wie auf der Seite: kein Ergebnis für einen nichtöffentlichen Punkt —
    auch nicht, wenn der Bestand eins kennt."""
    text = "\n".join(pc.session_lines(_Rat(), 4705))
    assert "gesperrte Information" not in text
    assert "9999" not in text
    assert "Nichtöffentlicher Teil: 2 Punkte" in text


def test_das_ris_ergebnis_im_titel_wird_abgetrennt():
    """Das Ratsinformationssystem hängt das Ergebnis an den Titel — gekürzt
    würde genau dieses Stück abgeschnitten."""
    text = "\n".join(pc.session_lines(_Rat(), 4705))
    assert "Ausfallbürgschaft - Beschluss — laut Ratsinformationssystem: ungeändert beschlossen" in text


def test_eine_kuenftige_sitzung_sagt_dass_es_keine_ergebnisse_gibt():
    """Fall ``lotti-nd-sitzung-ergebnisse``."""
    text = "\n".join(pc.session_lines(_Rat(), 4705, heute=date(2026, 9, 23)))
    assert "ZUKUNFT" in text
    text = "\n".join(pc.session_lines(_Rat(), 4705, heute=date(2026, 10, 1)))
    assert "bereits stattgefunden" in text


def test_die_sitzung_nennt_den_vorsitz():
    assert "Vorsitz laut Anwesenheitsliste: Anne Vorsitz" in _block("/council/sitzung", ksinr=1)


# --- Person ----------------------------------------------------------------

def test_die_person_nennt_fraktion_und_laufende_gremien():
    """Fälle ``lotti-person-*``: Der Block trug nur den Namen."""
    block = _block("/council/person", slug="renke-beispiel")
    assert "Renke Beispiel — Ratsmitglied, heute SPD" in block
    assert "Aktuelle Mitgliedschaften (Ratsinformationssystem): Verkehrsausschuss " \
           "(Ausschussvorsitzende/r, seit 2021-11); Rat (seit 2011-11)" in block
    assert "Frühere Mitgliedschaften: Sportausschuss (2016-11 bis 2021-10)" in block


def test_die_person_bringt_keine_wortbeitraege_im_wortlaut():
    block = _block("/council/person", slug="renke-beispiel")
    assert "Wortbeiträge in den Protokollen: 12" in block


# --- Ort, Thema, Themenfeld -------------------------------------------------

def test_der_ort_nennt_seine_juengsten_beschluesse():
    """Fall ``lotti-ort-alte-fleiwa``: Die Seite listet sie, der Block nicht."""
    block = _block("/council/ort", place_id="alte-fleiwa")
    assert "Beschlüsse, deren Text diesen Ort nennt: 17" in block
    assert "1. Juni 2026, Rat: „Bebauungsplan 855 – Satzungsbeschluss“ — angenommen (Nr. 9319)" in block


def test_die_themen_seite_ist_eine_entitaet():
    """``themaHref`` führt auf ``/council/entity/{slug}`` — kein Themenfeld."""
    block = _block("/council/thema", slug="fliegerhorst")
    assert "Das Thema auf dieser Seite: Fliegerhorst (Projekt) — 1 Beschlüsse" in block
    assert "Bebauungsplan N-777 G" in block


def test_ein_feld_schluessel_bringt_rueckblick_und_beschluesse():
    block = _block("/council/thema", slug="verkehr")
    assert "Verkehr & Mobilität" in block
    assert "Der Rat treibt den Radverkehr voran." in block
    assert "Nr. 9319" in block


# --- Beschluss --------------------------------------------------------------

def test_der_beschluss_bringt_protokollwortlaut_und_kosten():
    """Fälle ``lotti-schulbezirke-gegenstimmen`` (Protokoll sagt „einstimmig“,
    ``vote`` sagt „mehrheitlich“) und ``lotti-btb-betrag`` (Beträge nur in der
    Vorlage)."""
    block = _block("/council/decision", decision_id=9316)
    assert "Im Protokoll steht zur Abstimmung wörtlich: „einstimmig bei neun Enthaltungen“" in block
    assert "Finanzielle Auswirkungen laut Vorlage 26/0353: 2026: 173.000,00 Euro 2027: 177.500,00 Euro" in block


# --- Fremdtext und dünne Stores ---------------------------------------------

def test_der_ganze_gegenstand_steht_zwischen_markern():
    """Titel und Wortlaut stammen aus Ratsunterlagen — Daten, keine Anweisungen."""
    block = _block("/council/sitzung", ksinr=4705)
    assert block.index("<<<AKTEN") < block.index("Kulturzentrum PFL") < block.index("\nAKTEN")


def test_ein_duenner_store_kippt_nichts():
    """Die Attrappen der übrigen Tests kennen drei Methoden — dann fällt weg,
    was fehlt, statt die Erklärung zu kippen."""

    class _Duenn:
        def get_session(self, ksinr):
            return {"committee": "Rat", "session_date": "2026-06-01"}

    text = "\n".join(pc.session_lines(_Duenn(), 1))
    assert "Rat am 1. Juni 2026" in text
    assert "Tagesordnung: liegt noch nicht vor." in text
    assert pc.person_lines(_Duenn(), "x") == []
    assert pc.place_lines(_Duenn(), "x") == []
    assert pc.entity_lines(_Duenn(), "x") == []
