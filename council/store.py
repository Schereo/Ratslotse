from __future__ import annotations

import contextlib
import logging
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sqlite3
from council import geld as _geld

from .parties import order_key, parties_for_faction
from . import importance as _importance
from council.kontaktdaten import maskieren
from kern.dbfehler import tabelle_fehlt
from council.store_helfer import _dedup_keys, _int_or_none
from council.store_fundstuecke import FundstueckeMixin
from council.store_haushalt import HaushaltMixin
from council.store_orte import CONCRETE_LOCATION_KINDS, OrteMixin
from council.store_personen import PersonenMixin
from council.store_presse import PresseMixin
from council.store_quiz import QuizMixin
from council.store_sitzungen import SitzungenMixin
from council.store_themen import ThemenMixin
from council.store_wortbeitraege import WortbeitraegeMixin










SCHEMA = """
CREATE TABLE IF NOT EXISTS council_sessions (
    ksinr         INTEGER PRIMARY KEY,
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL,
    location      TEXT NOT NULL,
    fetched_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cs_date ON council_sessions(session_date DESC);

CREATE TABLE IF NOT EXISTS council_agenda_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    item_number  TEXT NOT NULL,
    title        TEXT NOT NULL,
    template_number   TEXT,
    kvonr        INTEGER,
    is_public    INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ksinr, item_number),
    FOREIGN KEY(ksinr) REFERENCES council_sessions(ksinr)
);

-- Dokument-Anhänge je TOP von der Sitzungsseite (Tims Befund 12.08.):
-- Fraktions-Anträge ohne Vorlage hängen NUR hier.
CREATE TABLE IF NOT EXISTS council_agenda_attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    item_number  TEXT NOT NULL,
    label        TEXT NOT NULL,
    url          TEXT NOT NULL,
    -- Nur für Dringlichkeitsanträge gefüllt (council/dringlichkeit.py): Sie
    -- haben keine Vorlage, ihr ganzer Inhalt steht in DIESEM PDF. Alle
    -- anderen Zeilen-Dokumente bleiben leer — sie hängen an einem Punkt, der
    -- seine Vorlage hat, und ein Download je Anlage bei jedem Scrape wäre
    -- teuer für nichts.
    raw_text     TEXT,
    UNIQUE(ksinr, item_number, url)
);

-- Terminierte Sitzungen aus dem Sitzungskalender, noch ohne veröffentlichte
-- Tagesordnung (und damit ohne ksinr — SessionNet verlinkt erst bei
-- Veröffentlichung). Wird bei jedem Scrape komplett ersetzt; abgesagte
-- Termine verschwinden so von selbst.
CREATE TABLE IF NOT EXISTS council_scheduled_sessions (
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (committee, session_date, session_time)
);

CREATE TABLE IF NOT EXISTS council_alerts_sent (
    ksinr    INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, topic_id)
);

CREATE TABLE IF NOT EXISTS committee_notifications (
    ksinr        INTEGER NOT NULL,
    owner_id     INTEGER NOT NULL,
    agenda_hash  TEXT NOT NULL DEFAULT '',
    sent_at      TEXT NOT NULL,
    PRIMARY KEY(ksinr, owner_id)
);

CREATE TABLE IF NOT EXISTS committees (
    kgrnr   INTEGER,
    name    TEXT NOT NULL,
    UNIQUE(name)
);

-- Verwaist seit dem NWZ-Rückbau: Der Sitzungs-Nachbericht
-- (scripts/session_followup.py) ist weg, die Leser dieser Tabelle sind es
-- inzwischen auch. Sie bleibt trotzdem stehen — `_migrate_owner_id` prüft sie
-- zusammen mit committee_notifications (die weiter benutzt wird), und ohne die
-- Tabelle liefe diese Migration auf bestehenden Datenbanken ins Leere.
CREATE TABLE IF NOT EXISTS session_followups_sent (
    ksinr    INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, owner_id)
);

CREATE TABLE IF NOT EXISTS committee_summaries (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);

-- Kurze KI-Zusammenfassung je TOP (Tims Wunsch 12.08.) — dieselben Sätze,
-- die auch in der Tagesordnungs-Mail stehen; hier je Punkt statt als
-- HTML-Block, damit die App sie unter dem Titel zeigen kann.
CREATE TABLE IF NOT EXISTS agenda_item_summaries (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    summary     TEXT NOT NULL,
    agenda_hash TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);

-- Tragweite eines Tagesordnungspunkts (0–100), dieselbe Rubrik wie bei den
-- Beschlüssen (council/impact.py). Eigene Tabelle statt Spalte, weil
-- save_session die Items einer Sitzung ERSETZT — eine Spalte wäre bei jeder
-- Tagesordnungs-Änderung weg und müsste neu bezahlt werden.
CREATE TABLE IF NOT EXISTS agenda_item_impact (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    impact      INTEGER NOT NULL,
    reason      TEXT,           -- Grund in einfacher Sprache, steht auf der Karte
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);

-- Kartentext für Social Media je TOP. Eigene Tabelle aus zwei Gründen:
-- save_session ERSETZT die Items einer Sitzung (eine Spalte wäre bei jeder
-- Tagesordnungs-Änderung weg und müsste neu bezahlt werden, genau wie bei
-- agenda_item_impact), und der Text hat einen anderen Auftrag als die
-- beiden vorhandenen Felder.
--
-- Warum überhaupt ein dritter Text (Tims Vorgabe 30.08.26):
--   agenda_item_summaries.summary entsteht ALLEIN AUS DEM TITEL („Du kennst
--     nur den Titel des Punktes" steht wörtlich in seinem Prompt) — er kann
--     die Überschrift nur umformulieren.
--   agenda_item_impact.reason kennt die Vorlage, begründet aber eine
--     RANGFOLGE und wertet deshalb („Trägt ein hohes finanzielles Risiko").
--     Zum Sortieren richtig; unter einem eigenen Absender auf Instagram wird
--     daraus eine Meinung des Absenders zur Sache.
-- Dieser Text bekommt Vorlage UND Anlagen und darf nicht werten.
CREATE TABLE IF NOT EXISTS agenda_item_social (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    text        TEXT NOT NULL,
    source      TEXT NOT NULL,  -- was das Modell sah: "template+attachments", "template", "title"
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);

-- Tagesordnungs-Stand je (Sitzung, Hash) — die Vergleichsbasis der
-- Änderungs-Meldung (Tims Wunsch 12.08.): save_session ERSETZT die Items,
-- der alte Stand wäre sonst weg, sobald sich die Tagesordnung ändert.
CREATE TABLE IF NOT EXISTS agenda_snapshots (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    items_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);

-- Parsed public session protocols (Niederschriften). One row per session.
CREATE TABLE IF NOT EXISTS council_protocols (
    ksinr         INTEGER PRIMARY KEY,
    document_id   INTEGER,
    document_url  TEXT,
    protocol_nr   TEXT,
    session_start TEXT,
    session_end   TEXT,
    raw_text      TEXT,
    n_pages       INTEGER,
    -- Zeichen-Offsets der PDF-Seitenanfänge im raw_text (JSON-Liste) — die
    -- Grundlage der seitengenauen Protokoll-Links. NULL im Altbestand
    -- (Backfill: scripts/backfill_protokoll_seiten.py).
    page_offsets  TEXT,
    model         TEXT,
    extracted_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'ok'   -- ok | failed
);

-- One row per decision / agenda item extracted from a protocol.
CREATE TABLE IF NOT EXISTS council_decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    position     INTEGER NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'decision', -- decision | subvote
    parent_item  TEXT,                          -- TOP number a subvote belongs to
    item_number  TEXT,
    title        TEXT,
    official_text    TEXT,
    outcome      TEXT,                          -- accepted|rejected|postponed|noted|no_decision
    vote         TEXT,                          -- unanimous|majority|null
    no_votes INTEGER,
    abstentions INTEGER,
    factions     TEXT,                          -- JSON array
    template_number   TEXT,
    kvonr        INTEGER,
    raw_result   TEXT,
    policy_field TEXT,                          -- one key from council.topics.POLICY_FIELDS
    policy_tags  TEXT,                          -- JSON array of finer-grained tags
    summary      TEXT,                          -- one-line neutral summary
    amount_eur   REAL,                          -- largest € amount in the text (council.money)
    importance   INTEGER,                       -- Wichtigkeits-Score 0–100 (council.importance), per Backfill
    simple_summary TEXT,                        -- „Lotti erklärt's einfach": 2–3 bürgernahe Sätze (RL-904)
    interest     INTEGER,                       -- Interessantheit 0–100 (council.interest, LLM), per Backfill
    interest_reason TEXT                        -- 1-Satz-Begründung des Interest-Scores
);
CREATE INDEX IF NOT EXISTS idx_decisions_ksinr ON council_decisions(ksinr);
-- NB: the policy_field index is created in _migrate(), not here — on an existing
-- DB this whole SCHEMA runs (via executescript) BEFORE the migration adds the
-- column, so indexing policy_field here would fail with "no such column".

-- Vorläufige Abstimmungsergebnisse aus der O1-Videoaufzeichnung (YouTube-
-- Untertitel, LLM-gelesen) — die Brücke über die 1–2 Monate bis zum
-- amtlichen Protokoll. Eigene Tabelle statt council_decisions: Das Protokoll
-- bleibt die einzige Quelle dort; diese Zeilen sind ausdrücklich „unter
-- Vorbehalt" und werden im Frontend nur gezeigt, solange der TOP keinen
-- Protokoll-Beschluss hat.
CREATE TABLE IF NOT EXISTS council_video_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr         INTEGER NOT NULL,
    item_number   TEXT NOT NULL,               -- ohne Ö-/N-Präfix, wie council_decisions
    outcome       TEXT NOT NULL,               -- accepted|rejected|postponed|noted|removed
    vote          TEXT,                        -- unanimous|majority|NULL (nicht belegt → offen)
    no_votes      INTEGER,                     -- nur wenn in der Sitzung ausgesprochen
    abstentions   INTEGER,
    quote         TEXT NOT NULL,               -- wörtlicher Transkript-Beleg
    video_id      TEXT NOT NULL,               -- YouTube-Video-ID
    video_seconds INTEGER,                     -- Fundstelle des Belegs im Video
    model         TEXT NOT NULL,               -- LLM, das gelesen hat
    created_at    TEXT NOT NULL,
    UNIQUE(ksinr, item_number)
);
CREATE INDEX IF NOT EXISTS idx_video_results_ksinr ON council_video_results(ksinr);

-- Fundstück des Tages (RL-U11): je Ausspiel-Tag EIN kuratierter Archiv-Fund
-- mit 1-Satz-Story — vorab generiert von scripts/generate_fundstuecke.py.
CREATE TABLE IF NOT EXISTS council_daily_finds (
    day         TEXT PRIMARY KEY,               -- Ausspiel-Datum (ISO)
    decision_id INTEGER NOT NULL,
    kicker      TEXT NOT NULL,                  -- „Heute vor N Jahren" | „Aus dem Archiv"
    story       TEXT NOT NULL,                  -- der eine Satz
    created_at  TEXT NOT NULL
);

-- One row per attendee per session.
CREATE TABLE IF NOT EXISTS council_attendance (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr   INTEGER NOT NULL,
    name    TEXT,
    party   TEXT,
    role    TEXT,                               -- chair|member|administration|minutes|guest
    note    TEXT
);
CREATE INDEX IF NOT EXISTS idx_attendance_ksinr ON council_attendance(ksinr);

-- Goal tracking: which decisions concern an overarching city goal, and whether
-- they advance / hinder / are neutral toward it (council.goals).
CREATE TABLE IF NOT EXISTS council_goal_links (
    goal        TEXT NOT NULL,
    decision_id INTEGER NOT NULL,
    relevant    INTEGER NOT NULL DEFAULT 0,
    stance      TEXT,                              -- advances|hinders|neutral
    rationale   TEXT,
    PRIMARY KEY (goal, decision_id)
);
CREATE INDEX IF NOT EXISTS idx_goal_links_goal ON council_goal_links(goal);

-- Precomputed nearest neighbours per decision (semantic embeddings, council.embeddings).
CREATE TABLE IF NOT EXISTS council_similar (
    decision_id INTEGER NOT NULL,
    neighbor_id INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, neighbor_id)
);
CREATE INDEX IF NOT EXISTS idx_similar_decision ON council_similar(decision_id);

-- Raw decision embedding vectors (float32 blob) for query-time semantic search.
CREATE TABLE IF NOT EXISTS council_embeddings (
    decision_id INTEGER PRIMARY KEY,
    vector      BLOB NOT NULL
);

-- Auto-generated LLM recap per policy field ("Was bewegte den Rat im Bereich X?",
-- council.recaps). One row per field, replaced when regenerated (≈ monthly via cron).
CREATE TABLE IF NOT EXISTS council_field_recaps (
    policy_field TEXT PRIMARY KEY,
    summary      TEXT NOT NULL,
    n_decisions  INTEGER NOT NULL,
    period_from  TEXT NOT NULL DEFAULT '',
    period_to    TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL
);

"""


#: Tabellen dieser Datenbank, die an einem Konto hängen.
#:
#: Die Konto-Löschung wohnt in ``kern.store`` und räumte lange nur die dortigen
#: Tabellen ab — der Wächter-Test (``test_account_deletion``) prüfte ebenfalls
#: nur jenes Schema und konnte diese Lücke also gar nicht sehen. Hier liegen
#: aber Verhaltensspuren: *welche* Sitzungen jemandem gemeldet wurden. Das ist
#: personenbezogen und muss beim Löschen mit weg (DSGVO, Recht auf Löschung).
COUNCIL_USER_OWNED_TABLES: tuple[tuple[str, str], ...] = (
    ("committee_notifications", "owner_id"),
    ("session_followups_sent", "owner_id"),
    # KI-Feedback (5a/I-03): Frage und Grund sind Freitext und können
    # Persönliches tragen — beim Konto-Löschen mit weg, kein Sonderfall.
    ("council_qa_feedback", "user_id"),
)


#: Das Geld-Vokabular je Tabelle: (alt, neu). Steht bewusst als Literal-
#: Tabelle NEBEN dem Code, damit ein Suchen-und-Ersetzen über die Datei
#: die alten Namen nicht mitnimmt — siehe Kommentar in :meth:`_migrate`.
_GELD_SPALTEN: list[tuple[str, list[tuple[str, str]]]] = [
    ("council_fixed_assets", [
        ("buchwert", "book_value"), ("buchwert_vorjahr", "book_value_prior_year")]),
    ("council_expense_series", [("betrag", "amount"), ("konflikt_betrag", "conflict_amount")]),
    ("council_deliberations", [("ergebnis", "result")]),
    ("council_buergschaften", [
        ("aus_folgejahr", "out_next_year"), ("einzelbetrag", "single_amount")]),
    ("council_income_budget", [("betrag", "amount"), ("ist_summe", "is_total")]),
    ("council_income_statement", [
        ("vorjahr", "prior_year"), ("ergebnis", "result"), ("ist_summe", "is_total")]),
    ("council_cash_flow_statement", [
        ("vorjahr", "prior_year"), ("ergebnis", "result"), ("ist_summe", "is_total")]),
    ("council_fees", [("abzuege", "deductions")]),
    ("council_fee_rates", [
        ("betrag", "amount"), ("vorjahr", "prior_year"),
        ("veraenderung_prozent", "change_pct")]),
    ("council_company_owners", [
        ("betrag_eur", "amount_eur"), ("anteil_prozent", "share_pct")]),
    ("council_budget", [
        ("ertraege", "revenues"), ("aufwendungen", "expenses"), ("ergebnis", "result"),
        ("is_summe", "is_total")]),
    ("council_budget_amendments", [("ertrag", "revenue"), ("aufwand", "expense")]),
    ("council_budget_amendments_cash", [
        ("soll_entwurf", "planned_draft"), ("einzahlung", "inflow"), ("auszahlung", "outflow"),
        ("soll_neu", "planned_new")]),
    ("council_budget_amendments_cash_totals", [
        ("einzahlungen", "inflows"), ("auszahlungen", "outflows"), ("saldo", "balance")]),
    ("council_budget_amendments_totals", [
        ("ertraege", "revenues"), ("aufwendungen", "expenses"), ("saldo", "balance")]),
    ("council_budget_bylaw", [
        ("ordentliche_ertraege", "ordinary_revenues"),
        ("ordentliche_aufwendungen", "ordinary_expenses"),
        ("ao_ertraege", "extraordinary_revenues"),
        ("ao_aufwendungen", "extraordinary_expenses"), ("ein_laufend", "in_operating"),
        ("aus_laufend", "out_operating"), ("ein_invest", "in_capital"),
        ("ein_finanz", "in_financing"), ("aus_finanz", "out_financing"),
        ("ein_gesamt", "in_total"), ("aus_gesamt", "out_total")]),
    ("council_provenance", [("probe_ergebnis", "probe_result")]),
    ("council_integrated_debt", [("veraenderung", "change")]),
    ("council_investments", [("einzahlungen", "inflows"), ("auszahlungen", "outflows")]),
    ("council_investments_actual_kinds", [("betrag", "amount")]),
    ("council_investments_actual_rejected", [("differenz", "difference")]),
    ("council_investment_measures", [("gesamtsumme", "grand_total")]),
    ("council_group_items", [
        ("betrag", "amount"), ("vorjahr", "prior_year"), ("ist_summe", "is_total")]),
    ("council_group_entities", [
        ("betrag_teur", "amount_keur"), ("vorjahr_teur", "prior_year_keur")]),
    ("council_supplementary_years", [
        ("summe_konsumtiv", "total_operating"), ("summe_investiv", "total_capital"),
        ("verpflichtungen_betrag", "commitments_amount")]),
    ("council_supplementary_channels", [
        ("anzahl_konsumtiv", "count_operating"), ("betrag_konsumtiv", "amount_operating"),
        ("anzahl_investiv", "count_capital"), ("betrag_investiv", "amount_capital")]),
    ("council_supplementary_approvals", [("betrag", "amount"), ("betrag_quelle", "amount_source")]),
    ("council_partei_meinungen_cache", [("ergebnis", "result")]),
    ("council_products", [
        ("ertraege", "revenues"), ("aufwendungen", "expenses"), ("ergebnis", "result")]),
    ("council_donations", [("betrag", "amount")]),
    ("council_staff_plan", [("stellen_vorjahr", "positions_prior_year")]),
    ("council_taxes", [("betrag", "amount")]),
    ("council_vermoegensgruppen", [
        ("buchwert", "book_value"), ("buchwert_vorjahr", "book_value_prior_year")]),
    ("council_business_plans", [
        ("ertraege", "revenues"), ("aufwendungen", "expenses"), ("ergebnis", "result")]),
]


#: Struktur- und Belegbegriffe je Tabelle: (alt, neu). Wie bei
#: :data:`_GELD_SPALTEN` steht links der ALTE Name — er ist die
#: Quelle der Migration und darf bei künftigen Umbenennungen nicht mitwandern.
_STRUKTUR_SPALTEN: list[tuple[str, list[tuple[str, str]]]] = [
    ("council_variance_reasons", [
        ("bezeichnung", "label"), ("quelle_label", "source_label"),
        ("quelle_url", "source_url")]),
    ("council_attachments", [("ocr_modell", "ocr_model")]),
    ("council_fixed_assets", [("bezeichnung", "label"), ("proben", "probes")]),
    ("council_expense_series", [
        ("proben", "probes"), ("konflikt_quelle", "conflict_source"), ("revidiert", "revised")]),
    ("council_balance_sheet", [("seite", "page"), ("ebene", "level"), ("bezeichnung", "label")]),
    ("council_balance_sheet_notes", [("ueberschrift", "heading")]),
    ("council_buergschaften", [("genau", "exact"), ("proben", "probes")]),
    ("council_income_budget", [
        ("plan_jahrgang", "plan_budget_year"), ("bezeichnung", "label")]),
    ("council_income_statement", [
        ("thh_nr", "sub_budget_no"), ("thh_name", "sub_budget_name"), ("bezeichnung", "label"),
        ("quelle_label", "source_label"), ("quelle_url", "source_url")]),
    ("council_cash_flow_statement", [("bezeichnung", "label"), ("ermaechtigung", "authorization")]),
    ("council_fees", [
        ("bereich", "area"), ("bereich_name", "area_name"), ("proben", "probes")]),
    ("council_fee_rates", [
        ("bereich", "area"), ("bezeichnung", "label"), ("proben", "probes")]),
    ("council_company_owners", [
        ("bericht_jahr", "report_year"), ("reihenfolge", "sort_order")]),
    ("council_company_indicators", [
        ("kennzahl", "indicator"), ("bericht_jahr", "report_year")]),
    ("council_company_people", [
        ("bericht_jahr", "report_year"), ("reihenfolge", "sort_order"), ("hinweis", "note")]),
    ("council_company_texts", [("bericht_jahr", "report_year"), ("abschnitt", "section")]),
    ("council_companies", [
        ("bericht_jahr", "report_year"), ("gliederung", "classification"), ("seite", "page")]),
    ("council_budget", [("bereich", "area")]),
    ("council_budget_amendments", [
        ("jahrgang", "budget_year"), ("lfd", "seq"), ("thh", "sub_budget"),
        ("seite_entwurf", "page_draft"), ("produkt", "product"), ("bezeichnung", "label"),
        ("erlaeuterung", "explanation"), ("dokument_id", "document_id")]),
    ("council_budget_amendments_cash", [
        ("jahrgang", "budget_year"), ("lfd", "seq"), ("thh", "sub_budget"),
        ("seite_entwurf", "page_draft"), ("produkt", "product"), ("bezeichnung", "label"),
        ("erlaeuterung", "explanation"), ("dokument_id", "document_id")]),
    ("council_budget_amendments_cash_totals", [
        ("jahrgang", "budget_year"), ("dokument_id", "document_id")]),
    ("council_budget_amendments_totals", [
        ("jahrgang", "budget_year"), ("dokument_id", "document_id")]),
    ("council_budget_bylaw", [("nachtrag", "supplement"), ("proben", "probes")]),
    ("council_provenance", [
        ("dokument_id", "document_id"), ("fundstelle", "citation"), ("seite", "page")]),
    ("council_integrated_debt", [("proben", "probes")]),
    ("council_investments", [
        ("ebene", "level"), ("thh_nr", "sub_budget_no"), ("bezeichnung", "label")]),
    ("council_investments_actual_kinds", [("reihenfolge", "sort_order")]),
    ("council_investment_measures", [
        ("ebene", "level"), ("thh_nr", "sub_budget_no"), ("bezeichnung", "label")]),
    ("council_indicator_formulas", [
        ("bericht_jahr", "report_year"), ("kennzahl", "indicator"),
        ("ueberschrift", "heading")]),
    ("council_indicators", [("bericht_jahr", "report_year"), ("kennzahl", "indicator")]),
    ("council_group_items", [("bezeichnung", "label")]),
    ("council_supplementary_approvals", [
        ("kategorie", "category"), ("volltextprobe", "fulltext_probe")]),
    ("council_products", [
        ("produkt_nr", "product_no"), ("produkt_name", "product_name"),
        ("thh_nr", "sub_budget_no"), ("thh_name", "sub_budget_name"), ("amt", "office"),
        ("kurzbeschreibung", "short_description"), ("auftragsgrundlage", "legal_basis"),
        ("beeinflussbarkeit", "controllability"),
        ("beeinflussbarkeit_roh", "controllability_raw"), ("wirkungskreis", "scope"),
        ("zielgruppe", "target_group"), ("quelle_label", "source_label"),
        ("quelle_url", "source_url")]),
    ("council_audit_report_sources", [("lesbar", "readable")]),
    ("council_audit_reports", [
        ("lfd", "seq"), ("marke", "mark"), ("marke_name", "mark_name"),
        ("marke_erlaeuterung", "mark_explanation"), ("textziffer", "text_number"),
        ("abschnitt", "section"), ("seite", "page"), ("folgeabsatz", "follow_paragraph"),
        ("quelle_label", "source_label"), ("quelle_url", "source_url")]),
    ("council_debt", [("revidiert", "revised")]),
    ("council_donations", [("proben", "probes")]),
    ("council_city_comparison", [("kennzahl", "indicator")]),
    ("council_staff_plan", [
        ("jahrgang", "budget_year"), ("lfd_nr", "seq_no"), ("bezeichnung", "label"),
        ("stichtag", "as_of_date"), ("stimmig", "consistent")]),
    ("council_tax_plan", [("vorlaeufig", "provisional")]),
    ("council_templates", [("amt", "office")]),
    ("council_business_plans", [("proben", "probes")]),
    ("council_speeches", [("seite", "page")]),
]


#: Fachbegriffe des Haushalts- und Beteiligungsteils. Die vier Wörter am
#: Ende (`beschlossen`, `besetzt`, `gesellschaft`, `stadt`) stehen zugleich
#: mitten in deutschen Regexen, Sperrlisten und — bei `stadt` — als WERT in
#: `council_provenance.source_type`, `art` und der Personen-Art. Sie sind
#: deshalb Stück für Stück von Hand umgestellt worden, nicht im Ersetzungs-
#: lauf. Offen bleiben `taxes` und `population`: Beide sind zusätzlich
#: BLOCKNAMEN der Haushalts-Antwort (`?felder=…,population`) und gehören in
#: den Schnitt, der diese Namen umstellt. Links steht wie immer der ALTE Name.
_FACH_SPALTEN: list[tuple[str, list[tuple[str, str]]]] = [
    ("council_attachments", [("is_antrag", "is_motion"), ("antragsteller", "applicants")]),
    ("council_fixed_assets", [("abschreibung", "depreciation")]),
    ("council_fees", [("kostenkalkulation", "cost_calculation"), ("gebuehr", "fee")]),
    ("council_company_indicators", [("berichte", "n_reports")]),
    ("council_trade_tax_statistics", [
        ("faelle", "cases"), ("festsetzungen", "assessments"), ("hebesatz", "rate")]),
    ("council_budget_amendments", [("urheber", "author")]),
    ("council_budget_amendments_cash", [
        ("ve", "commitment_authorizations"), ("urheber", "author")]),
    ("council_budget_amendments_cash_totals", [("ve", "commitment_authorizations")]),
    ("council_budget_bylaw", [
        ("aus_invest", "out_capital"), ("hebesatz_grundsteuer_a", "property_tax_a_rate"),
        ("hebesatz_grundsteuer_b", "property_tax_b_rate"),
        ("hebesatz_gewerbesteuer", "trade_tax_rate")]),
    ("council_tax_rates", [("hebesatz", "rate")]),
    ("council_integrated_debt", [("je_einwohner", "per_capita"), ("kernhaushalt", "core_budget")]),
    ("council_supplementary_approvals", [("ratsentscheidung", "council_decision")]),
    ("council_protocols", [("wortbeitraege_extracted_at", "contributions_extracted_at")]),
    ("council_qa_feedback", [("bewertung", "rating")]),
    ("council_debt", [("je_einwohner", "per_capita")]),
    ("council_tax_capacity", [("messzahl", "tax_index")]),
    ("council_templates", [
        ("klima_check", "climate_impact"), ("finanz_check", "financial_impact"),
        ("beschlussvorschlag", "proposed_decision")]),
    ("council_business_plans", [
        ("betrieb", "enterprise"), ("betrieb_name", "enterprise_name"),
        ("vermoegensplan", "capital_plan"), ("verpflichtungen", "commitments"),
        ("entwurf_vom", "draft_date")]),
]


#: Der unauffällige Rest: Spalten, die eine Risikoprüfung einzeln
#: freigegeben hat — kein Wert-Doppelgänger, kein deutscher Regex, keine
#: öffentliche Adresse. Links steht wie immer der ALTE Name.
_REST_SPALTEN: list[tuple[str, list[tuple[str, str]]]] = [
    ("council_variance_reasons", [("delta_mio", "delta_meur")]),
    ("council_fixed_assets", [
        ("ahk_anfang", "cost_opening"), ("zugaenge", "additions"), ("abgaenge", "disposals"),
        ("umbuchungen", "transfers"), ("ahk_ende", "cost_closing"),
        ("abschr_anfang", "depreciation_opening"), ("aufloesungen", "depreciation_releases"),
        ("zuschreibungen", "write_ups"), ("abschr_umbuchungen", "depreciation_transfers"),
        ("abschr_ende", "depreciation_closing")]),
    ("council_fees", [
        ("zu_deckende_kosten", "costs_to_cover"), ("bezugsmenge", "reference_quantity"),
        ("bezugseinheit", "reference_unit"), ("gebuehrenvorschlag", "fee_proposed")]),
    ("council_company_people", [("funktionen_zuordenbar", "roles_assignable")]),
    ("council_companies", [("konzern_key", "consolidated_key")]),
    ("council_trade_tax_statistics", [
        ("faelle_positiv", "cases_positive"), ("messbetrag_eur", "tax_base_eur"),
        ("festsetzungen_positiv", "assessments_positive"),
        ("festsetzung_messbetrag_eur", "assessment_tax_base_eur"),
        ("zerlegungen", "apportionments"), ("zerlegungen_positiv", "apportionments_positive"),
        ("zerlegung_messbetrag_eur", "apportioned_assessment_eur")]),
    ("council_budget_bylaw", [
        ("kredite_investitionen", "investment_loans"),
        ("verpflichtungsermaechtigungen", "commitment_authorizations"),
        ("liquiditaetskredite", "liquidity_loans"), ("sitzung_am", "session_date")]),
    ("council_tax_rates", [("vorheriger", "prior_rate")]),
    ("council_integrated_debt", [
        ("bevoelkerung", "population"), ("extrahaushalte", "extra_budgets"),
        ("extra_unter_50", "extra_under_50"), ("sonstige_unter_50", "other_below_50")]),
    ("council_supplementary_years", [("text_gesamt", "total_per_text")]),
    ("council_supplementary_approvals", [("im_rat", "in_plenary"), ("beschluss_id", "decision_id")]),
    ("council_press_embeddings", [("presse_id", "press_id")]),
    ("council_debt", [
        ("kreditmarkt", "credit_market"), ("sondermittel", "special_funds"),
        ("gebietskoerperschaften", "public_authorities"),
        ("eigenbetriebe", "municipal_enterprises"),
        ("aufteilung_verworfen", "breakdown_rejected")]),
    ("council_staff_plan", [
        ("besoldung", "pay_grade"), ("stellen_plan", "positions_planned"),
        ("besetzt_beamte", "filled_by_officials"),
        ("besetzt_arbeitnehmer", "filled_by_employees"), ("nicht_besetzt", "vacant"),
        ("besetzt", "filled")]),
    ("council_supplementary_approvals", [("beschlossen", "decided")]),
    ("council_company_owners", [("gesellschaft", "company")]),
    ("council_company_indicators", [("gesellschaft", "company")]),
    ("council_company_people", [("gesellschaft", "company")]),
    ("council_company_texts", [("gesellschaft", "company")]),
    ("council_companies", [("gesellschaft", "company")]),
    ("council_trade_tax_statistics", [("stadt", "city")]),
    ("council_city_comparison", [("stadt", "city")]),
    ("council_einwohner", [("einwohner", "population")]),
    ("council_variance_reasons", [("prozent", "percent")]),
    ("council_trade_tax_statistics", [("gesperrt", "confidential")]),
    ("council_attachments", [("bild", "is_image")]),
    ("council_income_statement", [("plan_art", "plan_kind")]),
    ("council_cash_flow_statement", [("plan_art", "plan_kind")]),
    ("council_budget_amendments", [("liste", "list_key")]),
    ("council_budget_amendments_cash", [("liste", "list_key")]),
    ("council_budget_amendments_totals", [("liste", "list_key"), ("typ", "kind")]),
    ("council_budget_amendments_cash_totals", [("liste", "list_key"), ("typ", "kind")]),
    ("council_fixed_assets", [("spalten", "n_columns")]),
    ("council_income_statement", [("ansatz", "budgeted")]),
    ("council_cash_flow_statement", [("ansatz", "budgeted")]),
    ("council_income_budget", [("ansatz", "budgeted")]),
    ("council_indicators", [("stellen", "decimals")]),
    ("council_memberships", [("von", "valid_from"), ("bis", "valid_until")]),
    ("council_donations", [("sitzung", "session_date")]),
    ("council_donations_rejected", [("sitzung", "session_date")]),
    ("council_staff_plan", [("gruppe", "pay_group")]),
    ("council_tax_plan", [("ist", "actual")]),
    ("council_vermoegensgruppen", [("gruppe", "group_name")]),
    ("council_business_plans", [("investitionen", "investments")]),
    ("council_buergschaften", [("bestand", "balance")]),
    ("council_budget_amendments_cash_totals", [("eigene", "own")]),
    ("council_budget_amendments_totals", [("eigene", "own")]),
    ("council_integrated_debt", [("insgesamt", "total"), ("sonstige", "other")]),
    ("council_video_results", [("gegenstimmen", "no_votes"),
                               ("enthaltungen", "abstentions")]),
    ("council_investments_actual", [("insgesamt", "total")]),
    ("council_investments_actual_kinds", [("feld", "field")]),
    ("council_indicator_formulas", [("formel", "formula")]),
    ("council_audit_reports", [("kette", "chain")]),
    ("council_qa_feedback", [("antwort_auszug", "answer_excerpt")]),
    ("council_debt", [("insgesamt", "total")]),
    ("council_staff_plan", [("teil", "part")]),
    ("council_speeches", [("sprecher", "speaker"), ("antwort", "answer")]),
    ("council_deliberations", [("gremium", "committee")]),
    ("council_buergschaften", [("grund", "reason")]),
    ("council_fee_rates", [("einheit", "unit")]),
    ("council_company_indicators", [("einheit", "unit")]),
    ("council_company_people", [("gremium", "committee")]),
    ("council_budget_bylaw", [("fassung", "version")]),
    ("council_investments_actual_rejected", [("grund", "reason")]),
    ("council_indicator_formulas", [("fassung", "version")]),
    ("council_indicators", [("einheit", "unit"), ("fassung", "version")]),
    ("council_memberships", [("gremium", "committee")]),
    ("council_qa_feedback", [("grund", "reason")]),
    ("council_donations", [("gremium", "committee")]),
    ("council_donations_rejected", [("grund", "reason")]),
    ("council_city_comparison", [("einheit", "unit")]),
    ("agenda_item_social", [("quelle", "source")]),
    ("council_expense_series", [("quelle", "source")]),
    ("council_balance_sheet", [("wert", "value")]),
    ("council_buergschaften", [("quelle", "source")]),
    ("council_fee_rates", [("schluessel", "key")]),
    ("council_company_indicators", [("wert", "value")]),
    ("council_trade_tax_statistics", [("schluessel", "key")]),
    ("council_provenance", [("schluessel", "key")]),
    ("council_indicators", [("wert", "value")]),
    ("council_partei_meinungen_cache", [("schluessel", "key")]),
    ("council_city_comparison", [("schluessel", "key"), ("wert", "value")]),
    ("council_deliberations", [("datum", "date")]),
    ("council_provenance", [("stand", "as_of")]),
    ("council_investments_actual_kinds", [("titel", "title")]),
    ("council_supplementary_approvals", [("titel", "title")]),
    ("council_partei_meinungen_cache", [("frage", "question")]),
    ("council_press", [("datum", "date"), ("titel", "title")]),
    ("council_qa_feedback", [("frage", "question")]),
    ("council_staff_plan", [("zeile", "row_no")]),
    ("council_speeches", [("partei", "party")]),
    ("council_beteiligungen", [("titel", "title"), ("von", "valid_from"), ("bis", "valid_until")]),
    ("council_business_plans", [("steuern", "taxes")]),
    ("council_tax_capacity", [
        ("messzahl_je_ew", "tax_capacity_per_capita"), ("zuweisungen", "allocations"),
        ("zuweisungen_je_ew", "allocations_per_capita")]),
    ("council_templates", [("anlagen_scanned", "attachments_scanned")]),
    ("council_speeches_embeddings", [("wb_id", "contribution_id")]),
]


#: Die deutschen Tabellennamen und ihre englischen Nachfolger (01.09.2026).
#:
#: Nach Länge sortiert anwenden — sonst frisst `council_budget` das
#: `council_budget_amendments_cash_totals`. Die FTS5-Schattentabellen
#: (`…_fts_content`, `…_fts_data`, …) stehen bewusst NICHT hier: Sie wandern
#: mit ihrer Haupttabelle, und sie einzeln umzubenennen zerlegte den Index.
TABELLEN_UMBENANNT: list[tuple[str, str]] = [
    ("council_haushalt_aenderungen_fhh_summen", "council_budget_amendments_cash_totals"),
    ("council_haushalt_aenderungen_fhh", "council_budget_amendments_cash"),
    ("council_haushalt_aenderungen_summen", "council_budget_amendments_totals"),
    ("council_haushalt_aenderungen", "council_budget_amendments"),
    ("council_investitionen_ist_verworfen", "council_investments_actual_rejected"),
    ("council_investitionen_ist_arten", "council_investments_actual_kinds"),
    ("council_investitionen_ist", "council_investments_actual"),
    ("council_investitionsmassnahmen", "council_investment_measures"),
    ("council_investitionen", "council_investments"),
    ("council_gesellschaft_eigentuemer", "council_company_owners"),
    ("council_gesellschaft_kennzahlen", "council_company_indicators"),
    ("council_gesellschaft_personen", "council_company_people"),
    ("council_gesellschaft_texte", "council_company_texts"),
    ("council_gesellschaften", "council_companies"),
    ("council_gewerbesteuerstatistik", "council_trade_tax_statistics"),
    ("council_wortbeitraege_embeddings", "council_speeches_embeddings"),
    ("council_wortbeitraege_fts", "council_speeches_fts"),
    ("council_wortbeitraege", "council_speeches"),
    ("council_nachbewilligung_kanaele", "council_supplementary_channels"),
    ("council_nachbewilligung_jahre", "council_supplementary_years"),
    ("council_nachbewilligungen", "council_supplementary_approvals"),
    ("council_bilanz_erlaeuterungen", "council_balance_sheet_notes"),
    ("council_integrierte_schulden", "council_integrated_debt"),
    ("council_abweichungsgruende", "council_variance_reasons"),
    ("council_pruefbericht_quellen", "council_audit_report_sources"),
    ("council_presse_embeddings", "council_press_embeddings"),
    ("council_presse_fts", "council_press_fts"),
    ("council_presse", "council_press"),
    ("council_vorlage_embeddings", "council_template_embeddings"),
    ("council_wirtschaftsplaene", "council_business_plans"),
    ("council_ergebnishaushalt", "council_income_budget"),
    ("council_ergebnisrechnung", "council_income_statement"),
    ("council_staedtevergleich", "council_city_comparison"),
    ("council_migrationsmarken", "council_migration_marks"),
    ("council_haushaltssatzung", "council_budget_bylaw"),
    ("council_spenden_verworfen", "council_donations_rejected"),
    ("council_gebuehrensaetze", "council_fee_rates"),
    ("council_kennzahl_formeln", "council_indicator_formulas"),
    ("council_finanzrechnung", "council_cash_flow_statement"),
    ("council_anlagenspiegel", "council_fixed_assets"),
    ("council_konzern_traeger", "council_group_entities"),
    ("council_konzern_posten", "council_group_items"),
    ("council_ausgabenreihe", "council_expense_series"),
    ("council_agenda_anlagen", "council_agenda_attachments"),
    ("council_pruefberichte", "council_audit_reports"),
    ("council_fundstuecke", "council_daily_finds"),
    ("council_steuerkraft", "council_tax_capacity"),
    ("council_stellenplan", "council_staff_plan"),
    ("council_beratungen", "council_deliberations"),
    ("council_kennzahlen", "council_indicators"),
    ("council_hebesaetze", "council_tax_rates"),
    ("council_steuerplan", "council_tax_plan"),
    ("council_gebuehren", "council_fees"),
    ("council_herkunft", "council_provenance"),
    ("council_haushalt", "council_budget"),
    ("council_produkte", "council_products"),
    ("council_vorlagen", "council_templates"),
    ("council_schulden", "council_debt"),
    ("council_anlagen", "council_attachments"),
    ("council_spenden", "council_donations"),
    ("council_steuern", "council_taxes"),
    ("council_bilanz", "council_balance_sheet"),
]

# Die Store-Mixins der Modul-Facetten (council/geld/): je Facette eine
# Methode `(woerter, year=None)`, die mit `_conn`, `_trifft` und `_beleg`
# arbeitet. Der Stern ist Absicht — wer eine Facette baut, fasst diese
# Datei nicht an.
class CouncilStore(FundstueckeMixin, HaushaltMixin, OrteMixin, PersonenMixin,
                   PresseMixin, QuizMixin, SitzungenMixin, ThemenMixin,
                   WortbeitraegeMixin, *_geld.MIXINS):
    def __init__(self, path: str | Path, ratslotse_db_path: str | Path | None = None):
        self._path = path
        # Sibling ratslotse.sqlite holds the chat_id→owner_id map for the migration.
        if ratslotse_db_path is None and isinstance(path, (str, Path)) and str(path) != ":memory:":
            ratslotse_db_path = Path(path).parent / "ratslotse.sqlite"
        self._ratslotse_db_path = ratslotse_db_path
        # check_same_thread=False wie im Konten-Store: FastAPI führt sync-Dependencies
        # und Endpoint in (potenziell verschiedenen) Threadpool-Threads aus — die
        # Verbindung wandert also zwischen Threads. Sicher, weil jede Anfrage ihre
        # eigene Store-Instanz bekommt (keine parallele Nutzung EINER Verbindung).
        self._conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Kontaktdaten aus dem Text nehmen, der in einen SUCHINDEX geht — als
        # SQLite-Funktion, damit `rebuild_fts()` eine einzige INSERT-SELECT
        # bleibt und nicht zu einer Schleife in Python wird
        # (`council/kontaktdaten.py`). Gespeichert wird weiterhin alles.
        self._conn.create_function("ohne_kontaktdaten", 1, maskieren,
                                   deterministic=True)
        # WAL + busy_timeout: scraper cron and the web API share this file.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        # VOR dem Schema: Sonst legt `CREATE TABLE IF NOT EXISTS` die neue,
        # englische Tabelle leer an, der Zielname ist belegt, und die
        # Umbenennung unterbleibt für immer — die Daten lägen weiter unter dem
        # alten Namen, unsichtbar. Genau so ist am 01.09.2026 die Einwilligung
        # in `web_users` verschwunden, nur eben spaltenweise.
        self._tabellen_umbenennen()
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()
        #: Läuft gerade eine geklammerte Transaktion (siehe ``transaktion``)?
        self._sammelt = False
        #: Zwischenspeicher für ``personen_kanon`` — je Instanz, also je Anfrage.
        self._kanon: dict[str, str] | None = None
        # Namensvarianten derselben Person (s. _personen_varianten): einmal je
        # Store-Instanz gebaut, also einmal je Web-Anfrage.
        self._varianten_cache: dict[str, str] | None = None
        self._runtime_places_cache: tuple | None = None
        self._place_aliases_cache: dict[str, str] | None = None

    @contextlib.contextmanager
    def transaktion(self):
        """Mehrere ``save_*``-Aufrufe zu **einer** Transaktion klammern.

        Ohne die Klammer committet jeder Aufruf für sich. Für einen
        Jahresabschluss sind das 1 + n + 1 Transaktionen (Gesamtrechnung, je
        Teilhaushalt eine, Erläuterungen) — bricht der Lauf dazwischen ab,
        bleibt der Jahrgang halb in der Datenbank stehen. Genau das darf einem
        unbeaufsichtigten Cron nicht passieren, der einen halben Jahrgang
        anschließend für erledigt hält.

        Verschachtelung ist erlaubt und tut nichts: Die innerste Klammer
        überlässt Commit und Rollback der äußersten. Die ``save_*``-Methoden
        benutzen sie deshalb selbst — ein Aufruf ohne äußere Klammer verhält
        sich wie vorher."""
        if self._sammelt:
            yield  # schon geklammert — die äußere Klammer committet
            return
        self._sammelt = True
        try:
            with self._conn:
                yield
        finally:
            self._sammelt = False
    def _spalten_umbenennen(self, tabelle: str, paare: list[tuple[str, str]]) -> None:
        """Benennt Spalten um, sofern sie noch alt heißen — idempotent.

        SQLite zieht Indizes und Fremdschlüssel selbst nach. Läuft bei jedem
        Start; nach dem ersten Mal ist es ein PRAGMA und sonst nichts.
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if not vorhanden:
            return
        for alt, neu in paare:
            if alt in vorhanden and neu not in vorhanden:
                with self._conn:
                    self._conn.execute(
                        f"ALTER TABLE {tabelle} RENAME COLUMN {alt} TO {neu}")
                logging.getLogger("ratslotse.council.store").warning(
                    "Spalte umbenannt: %s.%s → %s", tabelle, alt, neu)

    def _werte_umschreiben(self, tabelle: str, spalte: str,
                           paare: list[tuple[str, str]]) -> None:
        """Schreibt gespeicherte WERTE um — idempotent.

        Anders als bei Spalten reicht ein Schema-Wechsel hier nicht: Die
        deutschen Bezeichner stehen als Daten in den Zeilen (``area_type =
        'district'``). Ein UPDATE je Wert, das beim zweiten Lauf nichts mehr
        findet.
        """
        info = list(self._conn.execute(f"PRAGMA table_info({tabelle})"))
        vorhanden = {r[1] for r in info}
        if spalte not in vorhanden:
            # Tabelle fehlt oder trägt die Spalte (noch) nicht — beides ist
            # normal, etwa in einer frisch angelegten Datenbank.
            return
        log = logging.getLogger("ratslotse.council.store")
        for alt, neu in paare:
            try:
                cur = self._conn.execute(
                    f"UPDATE {tabelle} SET {spalte} = ? WHERE {spalte} = ?", (neu, alt))
            except sqlite3.IntegrityError:
                # Der neue Wert steht schon da: Ein Ingest mit neuem Code hat
                # ihn geschrieben, während die alten Zeilen liegen blieben —
                # so lag `council_taxes` am 02.09.2026 auf dev mit `insgesamt`
                # UND `total` für dieselben Jahre, und jeder Store-Start
                # brach hier ab (Crons, Ingests, nach dem nächsten Neustart
                # auch die API). Wo der Wert Teil des Primärschlüssels ist,
                # weicht die alte Zeile der neuen: gleicher Schlüssel, und
                # die neue trägt den jüngeren Ingest. Ohne Schlüsselwissen
                # bleibt der Fehler ein Fehler — raten wäre schlimmer.
                pk = [r[1] for r in sorted((r for r in info if r[5] > 0), key=lambda r: r[5])]
                if spalte not in pk:
                    raise
                gleich = " AND ".join(
                    f"t2.{c} = {tabelle}.{c}" for c in pk if c != spalte) or "1 = 1"
                weg = self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE {spalte} = ? AND EXISTS ("
                    f"SELECT 1 FROM {tabelle} AS t2 WHERE t2.{spalte} = ? AND {gleich})",
                    (alt, neu)).rowcount
                log.warning(
                    "Werte-Konflikt aufgelöst: %s.%s %r stand neben %r — %d alte Zeilen "
                    "gelöscht, die neuen bleiben", tabelle, spalte, alt, neu, weg)
                cur = self._conn.execute(
                    f"UPDATE {tabelle} SET {spalte} = ? WHERE {spalte} = ?", (neu, alt))
            if cur.rowcount:
                self._conn.commit()
                log.warning(
                    "Werte umgeschrieben: %s.%s %r → %r (%d Zeilen)",
                    tabelle, spalte, alt, neu, cur.rowcount)

    #: Die Eimer eines Tagesordnungs-Diffs. NUR die oberste Ebene — `anlagen`
    #: ist dort ein Eimer, INNERHALB eines Punktes aber dessen Anlagenliste,
    #: und die heißt weiter so.
    _DIFF_EIMER = {
        "neu": "new", "entfernt": "removed", "verschoben": "moved",
        "umformuliert": "reworded", "vorlage": "template", "anlagen": "attachments",
    }


    def _listenwerte_umschreiben(self, tabelle: str, spalte: str,
                                 paare: list[tuple[str, str]]) -> None:
        """Wie :meth:`_werte_umschreiben`, aber für KOMMAGETRENNTE Listen.

        Die Probennamen stehen nicht einzeln in der Zeile: Eine Zahl besteht
        oft zwei Proben, und beide zu nennen ist ehrlicher, als sich für eine
        zu entscheiden (``spenden_zweitstelle,spenden_protokollabgleich``).
        Ein Gleichheits-UPDATE träfe genau die 693 einwertigen Zellen und
        ließe die 413 mehrwertigen stehen — halb umgezogen ist schlimmer als
        gar nicht.
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if spalte not in vorhanden:
            return
        karte = dict(paare)
        geaendert = []
        for rid, roh in self._conn.execute(
                f"SELECT rowid, {spalte} FROM {tabelle} WHERE {spalte} IS NOT NULL"):
            teile = [t.strip() for t in str(roh).split(",")]
            neu = ",".join(karte.get(t, t) for t in teile)
            if neu != roh:
                geaendert.append((neu, rid))
        if not geaendert:
            return
        with self._conn:
            self._conn.executemany(
                f"UPDATE {tabelle} SET {spalte} = ? WHERE rowid = ?", geaendert)
        logging.getLogger("ratslotse.council.store").warning(
            "Listenwerte umgeschrieben: %s.%s (%d Zeilen)", tabelle, spalte, len(geaendert))

    def _doppelte_bildspalte_aufloesen(self) -> None:
        """`council_attachments` trug eine Zeit lang `bild` UND `is_image`.

        Die Umbenennung lief in `_migrate`, und das Nachrüsten weiter unten
        legte die deutsche Spalte gleich wieder an — leer. Jeder Leser hing
        seither an der leeren. Wo `bild` doch einen Wert trägt (ein
        Renderer-Lauf dazwischen), wandert er herüber; danach fällt sie weg.
        """
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_attachments)")}
        if "bild" not in cols or "is_image" not in cols:
            return
        with self._conn:
            n = self._conn.execute(
                "UPDATE council_attachments SET is_image = bild "
                "WHERE bild != 0 AND (is_image IS NULL OR is_image = 0)").rowcount
            self._conn.execute("ALTER TABLE council_attachments DROP COLUMN bild")
        logging.getLogger("ratslotse.council.store").warning(
            "Doppelte Bildspalte aufgelöst: %d Werte übernommen, `bild` entfernt", n)

    def _herkunft_schluessel_neu(self, marke: str) -> None:
        """Die Fingerabdrücke in `council_provenance` einmalig neu rechnen.

        `Herkunft.key()` hasht `json.dumps(felder(), sort_keys=True)` — und
        `felder()` liefert die SPALTENNAMEN mit. Nach `stand`→`as_of` ergibt
        derselbe Inhalt einen anderen Hash: Der nächste Ingest fände seine
        Zeile nicht wieder und legte sie ein zweites Mal an. Einmalig neu
        rechnen hält `id` stabil — und damit jeden `herkunft_id`-Verweis.

        `marke` benennt den Umzug, der das nötig macht, und steht deshalb beim
        AUFRUF, nicht hier: Die Umbenennung passierte in Schnitten, und jeder
        Schnitt braucht seinen eigenen Lauf. Stünde die Marke als Konstante in
        dieser Funktion, würde der erste Aufruf sie setzen und jeder spätere
        still zurückkehren — die Fingerabdrücke wären dann auf dem Stand VOR
        dem letzten Umzug, und der nächste Ingest legte jede Quelle ein zweites
        Mal an. Genau das soll die Marke verhindern.
        """
        import hashlib as _hl
        import json as _js
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS council_migration_marks ("
                "marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL)")
        if self._conn.execute(
                "SELECT 1 FROM council_migration_marks WHERE marke = ?", (marke,)).fetchone():
            return
        spalten = {r[1] for r in self._conn.execute("PRAGMA table_info(council_provenance)")}
        if "as_of" not in spalten or "key" not in spalten:
            return
        rows = self._conn.execute(
            "SELECT id, kind, document_id, label, url, citation, page, probe, "
            "probe_result, as_of FROM council_provenance").fetchall()
        neu = []
        for r in rows:
            felder = {"kind": r[1], "document_id": r[2], "label": r[3], "url": r[4],
                      "citation": r[5], "page": r[6], "probe": str(r[7]),
                      "probe_result": r[8], "as_of": r[9]}
            roh = _js.dumps(felder, sort_keys=True, ensure_ascii=False)
            neu.append((_hl.sha256(roh.encode("utf-8")).hexdigest(), r[0]))
        with self._conn:
            self._conn.executemany("UPDATE council_provenance SET key = ? WHERE id = ?", neu)
            self._conn.execute(
                "INSERT INTO council_migration_marks (marke, gesetzt_am) "
                "VALUES (?, datetime('now'))", (marke,))
        if neu:
            logging.getLogger("ratslotse.council.store").warning(
                "Herkunfts-Fingerabdrücke neu gerechnet: %d Zeilen", len(neu))

    def _cache_leeren_einmalig(self, tabelle: str, marke: str) -> None:
        """Einen CACHE einmalig leeren und die Marke festhalten.

        Für Tabellen, die die ROHE Modellantwort als JSON halten. Deren
        Schlüssel mit einem JSON-Umbau nachzuziehen wäre teuer und
        fehleranfällig — ein Cache darf man wegwerfen. Die Marke steht in
        `council_migration_marks`, damit der Wurf genau einmal passiert und
        nicht bei jedem Start die frisch gefüllten Zeilen trifft.
        """
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS council_migration_marks ("
                "marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL)")
        if self._conn.execute(
                "SELECT 1 FROM council_migration_marks WHERE marke = ?", (marke,)).fetchone():
            return
        vorhanden = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (tabelle,)).fetchone()
        n = 0
        with self._conn:
            if vorhanden:
                n = self._conn.execute(f"DELETE FROM {tabelle}").rowcount
            self._conn.execute(
                "INSERT INTO council_migration_marks (marke, gesetzt_am) "
                "VALUES (?, datetime('now'))", (marke,))
        if n:
            logging.getLogger("ratslotse.council.store").warning(
                "Cache geleert: %s (%d Zeilen, Marke %s)", tabelle, n, marke)

    #: `art` → `kind` in zehn Tabellen. Steht GANZ VORNE in `_migrate`, weil
    #: mehrere Wert-Migrationen weiter unten auf der Spalte arbeiten
    #: (`council_group_entities`, `council_taxes`, `council_tax_plan`):
    #: Liefe die Umbenennung später, fänden sie ihre Spalte nicht und kehrten
    #: still zurück — die Werte blieben deutsch, ohne dass etwas auffiele.
    _ART_TABELLEN = (
        "council_income_budget", "council_tax_rates", "council_provenance",
        "council_group_entities", "council_supplementary_approvals", "council_staff_plan",
        "council_taxes", "council_tax_plan", "council_templates",
        "council_speeches",
    )

    def _tabellen_umbenennen(self) -> None:
        """Die deutschen Tabellennamen auf ihre englischen bringen — einmalig.

        Läuft als EINZIGE Migration **vor** ``executescript(SCHEMA)``. Der
        Grund steht am Aufruf: Danach hätte das Schema die neue Tabelle längst
        leer angelegt, der Zielname wäre belegt, und die gewachsene Datenbank
        behielte ihre Daten unter dem alten Namen — ohne Fehlermeldung.

        Drei Fälle:

        * **Nur die alte da** — schlichtes ``RENAME TO``. SQLite zieht Indizes,
          Trigger und Fremdschlüssel selbst nach, und bei FTS5 wandern die fünf
          Schattentabellen (``_content``/``_data``/``_idx``/``_docsize``/
          ``_config``) mit; der Index trifft danach weiter (nachgemessen).
        * **Beide da, die neue LEER** — der Zustand nach einem Start mit
          halbfertigem Code. Die leere fällt weg, dann wird umbenannt.
        * **Beide da, beide gefüllt** — das kann keine Maschine entscheiden.
          Es bleibt, wie es ist, und beide Zeilenzahlen gehen als WARNING ins
          Log.

        Schattentabellen stehen bewusst NICHT in der Karte: Sie einzeln
        umzubenennen zerlegte den Index.
        """
        log = logging.getLogger("ratslotse.council.store")
        vorhanden = {r[0] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not vorhanden:                      # frische Datei — nichts zu tun
            return

        def zeilen(tabelle: str) -> int:
            try:
                return self._conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]
            except sqlite3.OperationalError as fehler:
                if not tabelle_fehlt(fehler):
                    raise
                return 0

        for alt, neu in TABELLEN_UMBENANNT:
            if alt not in vorhanden:
                continue
            if neu in vorhanden:
                if zeilen(neu):
                    log.warning(
                        "Zwei gefüllte Tabellen nebeneinander: %s (%d Zeilen) und %s "
                        "(%d Zeilen) — bitte von Hand prüfen, es wird nichts angefasst.",
                        alt, zeilen(alt), neu, zeilen(neu))
                    continue
                with self._conn:
                    self._conn.execute(f"DROP TABLE {neu}")
                log.warning("Leere %s entfernt — sie hätte den Umzug blockiert.", neu)
            with self._conn:
                self._conn.execute(f"ALTER TABLE {alt} RENAME TO {neu}")
            vorhanden.discard(alt)
            vorhanden.add(neu)
            log.warning("Tabelle umbenannt: %s → %s", alt, neu)

    def _migrate(self) -> None:
        # Die letzte deutsche Spalte der Rats-Datenbank (01.09.2026). VOR allem
        # anderen, weil die Migrationen darunter sie schon unter dem neuen Namen
        # lesen — und der ADD-COLUMN-Guard oben prüft den NEUEN Namen, sonst
        # entstünde die alte Spalte leer daneben (#917).
        self._spalten_umbenennen("council_locations", [("ortsbereich_id", "local_area_id")])
        for tabelle in self._ART_TABELLEN:
            self._spalten_umbenennen(tabelle, [("art", "kind")])
        # `jahr` → `year`: derselbe Begriff in 43 Tabellen, deshalb aus einer
        # Liste statt 43 Zeilen. Die Namen stehen bewusst als Literale hier —
        # ein Suchen-und-Ersetzen über die Datei darf sie nicht mitnehmen.
        for tabelle in (
                "council_taxes", "council_income_statement", "council_cash_flow_statement",
                "council_variance_reasons", "council_balance_sheet", "council_balance_sheet_notes",
                "council_income_budget", "council_investments", "council_investment_measures",
                "council_audit_report_sources", "council_products", "council_audit_reports",
                "council_einwohner", "council_tax_capacity", "council_group_items",
                "council_group_entities", "council_company_indicators", "council_city_comparison",
                "council_trade_tax_statistics", "council_debt", "council_investments_actual",
                "council_investments_actual_kinds", "council_investments_actual_rejected", "council_expense_series",
                "council_fees", "council_fee_rates", "council_budget_bylaw",
                "council_budget_amendments", "council_budget_amendments_totals", "council_budget_amendments_cash",
                "council_budget_amendments_cash_totals", "council_business_plans", "council_buergschaften",
                "council_fixed_assets", "council_vermoegensgruppen", "council_indicators",
                "council_integrated_debt", "council_supplementary_approvals", "council_supplementary_years",
                "council_supplementary_channels", "council_donations", "council_tax_plan",
                "council_tax_rates",
        ):
            # Der ALTE Name steht hier als Literal — er ist die Quelle der
            # Migration und darf bei künftigen Umbenennungen nicht mitwandern.
            self._spalten_umbenennen(tabelle, [("jahr", "year")])
        # Ortskatalog: Spalte und die `kind`-Werte tragen denselben Begriff.
        self._spalten_umbenennen("council_locations", [("stadtteil", "district")])
        self._werte_umschreiben("council_locations", "kind", [("stadtteil", "district")])
        # Gebietstypen des Quiz stehen als Daten in den Zeilen, nicht im Schema.
        self._werte_umschreiben("council_quiz_questions", "area_type", [
            ("wahlbereich", "electoral_district"), ("stadtteil", "district"),
            ("thema", "topic")])
        # 08/2026: Der Code spricht Englisch, die Spalten ziehen nach. Ohne
        # das bräuchte jede Abfrage einen Alias — und genau die wollen wir
        # nicht (Tims Vorgabe „ohne Mappings").
        self._spalten_umbenennen("council_decisions", [
            ("beschluss", "official_text"), ("gegenstimmen", "no_votes"),
            ("enthaltungen", "abstentions"), ("abweichung", "deviation"),
            ("vorlage_nr", "template_number")])
        for tabelle in ("council_income_statement", "council_cash_flow_statement"):
            self._spalten_umbenennen(tabelle, [("abweichung", "deviation")])
        for tabelle in ("council_agenda_items", "council_templates", "council_fees",
                        "council_fee_rates", "council_budget_bylaw",
                        "council_business_plans", "council_supplementary_approvals",
                        "council_donations", "council_donations_rejected",
                        "council_template_embeddings"):
            self._spalten_umbenennen(tabelle, [("vorlage_nr", "template_number")])

        # 08/2026, Geld-Vokabular: Beträge, Erträge, Aufwendungen, Salden.
        # ACHTUNG bei künftigen Umbenennungen: Links steht der ALTE Name. Er
        # ist die Quelle der Migration; wandert er mit, wird das Paar still
        # wirkungslos und nur BESTEHENDE Datenbanken bleiben deutsch — frische
        # legen ohnehin das neue Schema an, kein Test schlägt an.
        # `tests/test_api_vertrag.py::test_keine_wirkungslosen_migrationspaare`
        # ist genau dafür da.
        for tabelle, paare in _GELD_SPALTEN:
            self._spalten_umbenennen(tabelle, paare)
        # ZUERST die Spalte, DANN ihre Werte: `_werte_umschreiben` prüft auf
        # die Spalte und kehrt still zurück, wenn sie noch anders heißt. Stünde
        # diese Umbenennung weiter unten, liefen alle `role`-Wertmigrationen
        # darüber ins Leere — genau so ist es beim ersten Anlauf passiert.
        # In `council_memberships` bleiben die WERTE deutsch: Das sind
        # Rollennamen aus dem Ratsinformationssystem („Ratsmitglied"),
        # Anzeigetext, kein Schlüsselwort.
        for tabelle in ("council_balance_sheet", "council_balance_sheet_notes",
                        "council_cash_flow_statement", "council_group_items",
                        "council_memberships"):
            self._spalten_umbenennen(tabelle, [("rolle", "role")])
        self._spalten_umbenennen("council_supplementary_channels",
                                 [("kanal", "channel")])
        self._spalten_umbenennen("council_expense_series", [("regelwerk", "accounting_system")])
        self._spalten_umbenennen("council_company_people", [("funktion", "position")])
        self._spalten_umbenennen(
            "council_investments_actual", [("regelwerk", "accounting_system")])
        self._spalten_umbenennen(
            "council_investments_actual_rejected", [("regelwerk", "accounting_system")])
        self._spalten_umbenennen(
            "council_group_entities", [("traeger_key", "entity_key"), ("traeger", "entity")])
        self._spalten_umbenennen("council_supplementary_approvals", [("gremien", "committees")])
        self._spalten_umbenennen("council_persons", [("fraktion_aktuell", "current_faction")])
        self._spalten_umbenennen("council_donations", [("zweitstelle", "second_mention")])
        self._spalten_umbenennen("council_city_comparison", [("reihe", "series")])
        # Im Konzernabschluss stehen dieselben Begriffe auch als WERT in der
        # Zeile — die Spalte umzubenennen allein reichte nicht, die Abfrage
        # nach 'expenses' fände dann nichts.
        self._werte_umschreiben("council_group_entities", "kind", [
            ("ertraege", "revenues"), ("aufwendungen", "expenses")])
        self._werte_umschreiben("council_group_items", "role", [
            ("ertraege_summe", "revenues_total"),
            ("aufwendungen_summe", "expenses_total")])
        for tabelle, paare in _STRUKTUR_SPALTEN:
            self._spalten_umbenennen(tabelle, paare)
        # Dieselben Begriffe stehen auch als WERT in den Zeilen. Der
        # Geld-Schnitt hat die Spalten umbenannt und diese drei Stellen
        # übersehen — der Code schrieb danach `balance_operating`, in der
        # Datenbank stand weiter `saldo_verwaltung`, und jede Abfrage danach
        # fand nichts. Gefunden hat das `scripts/pruefe_wertreste.py`.
        self._werte_umschreiben("council_cash_flow_statement", "role", [
            ("summe_ein_verwaltung", "total_in_operating"),
            ("summe_aus_verwaltung", "total_out_operating"),
            ("saldo_verwaltung", "balance_operating"),
            ("summe_ein_investition", "total_in_capital"),
            ("summe_aus_investition", "total_out_capital"),
            ("saldo_investition", "balance_capital"),
            ("saldo_finanzierung", "balance_financing"),
            ("saldo_haushaltsunwirksam", "balance_non_budgetary")])
        self._werte_umschreiben("council_group_items", "role", [
            ("ao_ertraege", "extraordinary_revenues"),
            ("ao_aufwendungen", "extraordinary_expenses")])
        self._werte_umschreiben("council_cash_flow_statement", "role", [
            ("anfangsbestand", "opening_balance"), ("endbestand", "closing_balance"),
            ("finanzmittel", "cash_surplus"), ("finanzmittelveraenderung", "cash_change")])
        self._werte_umschreiben("council_group_items", "role", [
            ("ord_ergebnis", "ordinary_result"), ("ao_ergebnis", "extraordinary_result"),
            ("gesamtergebnis", "total_result"), ("personalaufwand", "personnel_expenses"),
            ("zinsaufwand", "interest_expenses"), ("steuern", "taxes")])
        self._werte_umschreiben("council_supplementary_channels", "channel", [
            ("eilentscheidung", "urgent_decision"), ("fachdienst200", "department_200"),
            ("oberbuergermeister", "mayor"), ("rat", "council")])
        self._werte_umschreiben("council_donations", "second_mention", [
            ("identisch", "identical"), ("zerlegung", "split")])
        # Die Herkunft eines Ortsbezugs steht als WERT in der Zeile und trug
        # denselben Begriff wie die Spalte `beschluss`, die zu `official_text`
        # wurde. `council/locations.py` lässt nur noch {title, official_text,
        # vorlage} durch — alles andere fällt auf "vorlage" zurück. Ohne diese
        # Migration wären auf dev 1.681 Ortsbezüge falsch beschriftet.
        self._werte_umschreiben("council_decision_locations", "source", [
            ("beschluss", "official_text")])
        for tabelle, paare in _REST_SPALTEN:
            self._spalten_umbenennen(tabelle, paare)
        for tabelle, paare in _FACH_SPALTEN:
            self._spalten_umbenennen(tabelle, paare)
        # Die Rollen der Anwesenheitsliste. Sie stehen NUR als Wert in der
        # Zeile — geschrieben vom Protokoll-Modell, gelesen von jeder
        # Mitglieder-Abfrage. Ohne diese Migration fände `role IN
        # ('member','chair')` in einem gewachsenen Bestand null Zeilen, und
        # das Personen-Verzeichnis wäre über Nacht leer.
        self._werte_umschreiben("council_attendance", "role", [
            ("vorsitz", "chair"), ("mitglied", "member"),
            ("verwaltung", "administration"), ("protokoll", "minutes"),
            ("gast", "guest"), ("beratend", "advisory")])
        self._spalten_umbenennen("council_company_people", [("vorsitz", "chair_role")])
        self._werte_umschreiben("council_company_people", "chair_role", [
            ("vorsitz", "chair"), ("stellvertretung", "deputy")])
        # ZUERST die Spalte, DANN ihr Wert — `amount_source` nennt seit dem
        # Umbenennen von `beschlussvorschlag` die neue Spalte.
        self._werte_umschreiben("council_supplementary_approvals", "amount_source", [
            ("beschlussvorschlag", "proposed_decision"), ("titel", "title")])
        self._werte_umschreiben("agenda_item_social", "source", [("titel", "title")])
        # ZUERST die Spalten (oben), DANN ihre Werte: `_werte_umschreiben`
        # prüft auf den Spaltennamen und kehrt still zurück, wenn er noch
        # anders heißt.
        for tabelle in ("council_budget_amendments", "council_budget_amendments_cash",
                        "council_budget_amendments_totals",
                        "council_budget_amendments_cash_totals"):
            self._werte_umschreiben(tabelle, "list_key", [
                ("verwaltung_1", "administration_1"), ("verwaltung_2", "administration_2"),
                ("verwaltung_3", "administration_3"), ("afb_beschlossen", "fc_decided")])
        for tabelle in ("council_budget_amendments_totals",
                        "council_budget_amendments_cash_totals"):
            self._werte_umschreiben(tabelle, "kind", [
                ("entwurf", "draft"), ("liste", "list"), ("endsumme", "final_total")])
        for tabelle in ("council_income_statement", "council_cash_flow_statement"):
            self._werte_umschreiben(tabelle, "plan_kind", [
                ("ansatz_nachtrag", "supplementary_budget"),
                ("gesamtermaechtigung", "total_authorization"),
                ("ansatz", "budget")])
        # Die Aufzählungen der `kind`-Spalten. ZUERST die Werte, DANN die
        # Fingerabdrücke: `council_provenance.kind` geht in den Hash ein.
        self._werte_umschreiben("council_speeches", "kind", [
            ("rede", "speech"), ("anfrage", "inquiry"),
            ("zusage", "pledge"), ("einwohnerfrage", "citizen_question")])
        self._werte_umschreiben("council_staff_plan", "kind", [
            ("posten", "item"), ("gruppe", "group"), ("gesamt", "total")])
        self._werte_umschreiben("council_supplementary_approvals", "kind", [
            ("bewilligung", "approval"), ("schwelle", "threshold"),
            ("verpflichtungsermaechtigung", "commitment_authorization")])
        self._werte_umschreiben("council_income_budget", "kind", [
            ("ansatz", "budget"), ("finanzplanung", "financial_plan")])
        # `ris`, `opendata` und `lsn` sind Kürzel und bleiben.
        self._werte_umschreiben("council_provenance", "kind", [("stadt", "city")])
        # Marken zuvor: …_as_of (#880) und …_kind (#886).
        self._herkunft_schluessel_neu("herkunft_key_city")
        self._doppelte_bildspalte_aufloesen()
        self._agenda_diff_schluessel_neu()
        # Der Parteien-Cache hält die ROHE Modellantwort als JSON; sie trug
        # bis zum Umbau den Schlüssel `partei`. Ein Cache darf man wegwerfen —
        # die nächste Frage baut ihn neu, und zwar mit `party`.
        self._cache_leeren_einmalig("council_partei_meinungen_cache", "partei_meinungen_englisch")
        # Zweites Mal: Der Prompt schreibt dem Modell jetzt `stance`/`unanimous`
        # statt `haltung`/`einig` vor, und der Parser liest es so. Ein Eintrag
        # von vorher trüge die alten Schlüssel — die Haltung fiele still auf
        # den Vorgabewert. Eigene Marke, sonst greift der Lauf nicht.
        self._cache_leeren_einmalig("council_partei_meinungen_cache", "partei_meinungen_stance")
        # Die Summenzeile der Steuertabelle ist UNSERE Marke, kein Steuername
        # aus der Quelle — die deutschen Steuerarten daneben bleiben deshalb.
        self._werte_umschreiben("council_taxes", "kind", [("insgesamt", "total")])
        self._werte_umschreiben("council_tax_plan", "kind", [("insgesamt", "total")])
        # Die Einheiten der Kennzahlen-Reihen.
        for tabelle in ("council_city_comparison", "council_company_indicators",
                        "council_indicators"):
            self._werte_umschreiben(tabelle, "unit", [
                ("prozent", "percent"), ("anzahl", "count")])
        # Das Ergebnis-Vokabular der Beschlüsse. Angezeigt wird weiter deutsch —
        # die Beschriftungen hängen jetzt an den englischen Schlüsseln.
        self._werte_umschreiben("council_decisions", "outcome", [
            ("angenommen", "accepted"), ("abgelehnt", "rejected"),
            ("vertagt", "postponed"), ("zur_kenntnis", "noted"),
            ("kein_beschluss", "no_decision")])
        self._werte_umschreiben("council_decisions", "vote", [
            ("einstimmig", "unanimous"), ("mehrheitlich", "majority")])
        self._werte_umschreiben("council_decisions", "deviation", [
            ("unveraendert", "unchanged"), ("leicht", "slight"), ("stark", "strong")])
        # Die Ortsarten. `anlage`, `bauwerk` und `verkehrsweg` gibt es nur als
        # Prüf-Entscheidung im Admin-Panel, sie stehen aber in derselben Spalte.
        ORTSARTEN = [
            ("strasse", "street"), ("platz", "square"), ("gebaeude", "building"),
            ("gebiet", "area"), ("gewaesser", "water"), ("sonstiges", "other"),
            ("anlage", "facility"), ("bauwerk", "structure"), ("verkehrsweg", "route"),
        ]
        self._werte_umschreiben("council_locations", "kind", ORTSARTEN)
        self._werte_umschreiben("council_place_reviews", "kind", ORTSARTEN)
        # Die GEBIETSARTEN des Ortskatalogs. Sie stehen in derselben Spalte wie
        # die Ortsarten darüber, aber nur an `status='approved'`-Zeilen — die
        # beiden Wertemengen sind disjunkt, ein Aufruf je Liste reicht also.
        GEBIETSARTEN = [
            ("ortsbereich", "local_area"), ("quartier", "neighborhood"),
            ("wohngebiet", "residential_area"), ("sanierungsgebiet", "redevelopment_area"),
            ("entwicklungsgebiet", "development_area"), ("schutzgebiet", "protected_area"),
            ("sportgebiet", "sports_area"),
        ]
        self._werte_umschreiben("council_place_reviews", "kind", GEBIETSARTEN)
        # Die Abschnitte des Beteiligungsberichts (§ 151 NKomVG).
        self._werte_umschreiben("council_company_texts", "section", [
            ("gegenstand", "business_purpose"),
            ("beteiligungsverhaeltnisse", "ownership_structure"),
            ("aufsichtsorgane", "supervisory_bodies"),
            ("beteiligungen", "own_shareholdings"), ("haushalt", "budget_impact")])
        # Die Art einer Entität. `organisation` ist schon englisch.
        # Die Probennamen (council/herkunft.py::PROBEN). Sie stehen KOMMA-
        # GETRENNT — eine Zahl besteht oft zwei Proben —, deshalb der
        # Listen-Helfer statt `_werte_umschreiben`.
        PROBEN_NAMEN = [
            # `anlagen_buchwert` stand zuvor als Gleichheits-UPDATE daneben.
            # Das traf nur `council_provenance` und nur EINWERTIGE Zellen — auf
            # dev blieb er in `council_fixed_assets.probes` und in den
            # mehrwertigen Zellen stehen. Als Probenname gehört er hierher.
            ("anlagen_buchwert", "assets_book_value"),
            ("abweichungstext", "variance_text"), ("aenderungsliste_erlaeuterungen", "amendment_list_explanations"),
            ("aenderungsliste_fhh_zeilen", "amendment_list_cash_budget_rows"), ("aenderungsliste_positionen", "amendment_list_items"),
            ("aenderungsliste_summen", "amendment_list_totals"), ("aenderungsliste_urheber", "amendment_list_proposers"),
            ("anlagen_abschreibungskette", "assets_depreciation_chain"), ("anlagen_ahk_kette", "assets_cost_chain"),
            ("anlagen_gegen_bilanz", "assets_vs_balance_sheet"), ("anlagen_umbuchungssaldo", "assets_transfer_balance"),
            ("ausgabenreihe_jahresabschluss", "expense_series_annual_accounts"), ("ausgabenreihe_prokopf", "expense_series_per_capita"),
            ("ausgabenreihe_zweitquelle", "expense_series_second_source"), ("beteiligung_anteilsprobe", "shareholding_share_check"),
            ("beteiligung_bilanzprobe", "shareholding_balance_sheet_check"), ("beteiligung_ergebnisprobe", "shareholding_result_check"),
            ("beteiligung_seitenprobe", "shareholding_page_check"), ("beteiligung_spaltenprobe", "shareholding_column_check"),
            ("beteiligung_ueberlappung", "shareholding_overlap"), ("bilanz_ausgleich", "balance_sheet_equality"),
            ("bilanz_erlaeuterung", "balance_sheet_notes"), ("bilanz_kassenprobe", "balance_sheet_cash_check"),
            ("bilanz_vorjahreskette", "balance_sheet_prior_year_chain"), ("bilanzsumme_gedruckt", "balance_sheet_total_printed"),
            ("buergschaft_kette", "guarantee_chain"), ("buergschaft_tabelle", "guarantee_table"),
            ("eingangsformel", "preamble_scope"), ("ergebnishaushalt_planspalte", "income_budget_plan_column"),
            ("ergebnishaushalt_summenzeilen", "income_budget_total_rows"), ("finanz_bestandskette", "cash_balance_chain"),
            ("finanz_ermaechtigungen", "cash_flow_authorizations"), ("finanzkaskade", "cash_flow_cascade"),
            ("gebuehren_division", "fee_division"), ("gebuehren_kaskade", "fee_cascade"),
            ("gebuehrensaetze_anzahl", "fee_rate_count"), ("gebuehrensaetze_eckwerte", "fee_rate_benchmarks"),
            ("gebuehrensaetze_vorjahresvergleich", "fee_rate_prior_year_comparison"), ("gewst_blattprobe", "trade_tax_sheet_check"),
            ("gewst_hebesatzprobe", "trade_tax_assessment_rate_check"), ("gewst_summenprobe", "trade_tax_sum_check"),
            ("hebesatz_spaltenkopf", "assessment_rate_column_header"), ("hebesatz_sprungjahr", "assessment_rate_step_year"),
            ("hebesatz_treppe", "assessment_rate_change_years"), ("integrierte_schulden_kernhaushalt", "integrated_debt_core_budget"),
            ("investitionen_ist_zeilensumme", "investments_actual_row_total"), ("investitionen_summenzeile", "investments_total_row"),
            ("investitionsprogramm_abschnitt", "capital_programme_section_total"), ("investitionsprogramm_kopftabelle", "capital_programme_summary_table"),
            ("investitionsprogramm_wiederholung", "capital_programme_repeated_total"), ("kassenkette", "cash_carryover_chain"),
            ("kennzahlen_gegen_bilanz", "indicators_vs_balance_sheet"), ("kennzahlen_ueberlappung", "indicators_overlap"),
            ("kennzahlen_vermoegensprobe", "indicators_assets_check"), ("kfa_jahrbuchabgleich", "fiscal_equalisation_yearbook_match"),
            ("kfa_komponentenprobe", "fiscal_equalisation_components"), ("konzern_ausserordentlich", "group_extraordinary_result"),
            ("konzern_ergebnisprobe", "group_ordinary_result"), ("konzern_gesamtergebnis", "group_total_result"),
            ("konzern_querprobe", "group_cross_check"), ("konzern_traegersumme", "group_entity_total"),
            ("konzern_zeilenprobe", "group_row_change"), ("legende_und_verzeichnis", "legend_and_index"),
            ("lsn_dreijahresmittel", "lsn_three_year_average"), ("lsn_hebesatzprobe", "lsn_assessment_rate_check"),
            ("lsn_zweijahresueberlappung", "lsn_two_year_overlap"), ("nachbewilligung_ratsabgleich", "supplementary_approval_council_match"),
            ("nachbewilligung_tabellenprobe", "supplementary_approval_table_check"), ("nachbewilligung_volltext", "supplementary_approval_fulltext"),
            ("produktzeile", "product_row"), ("rueckstellungs_gliederung", "provisions_breakdown"),
            ("satzung_finanzhaushalt", "bylaw_cash_budget"), ("satzung_hebesatz", "bylaw_assessment_rate"),
            ("schulden_prokopf", "debt_per_capita"), ("schulden_summenzeile", "debt_total_row"),
            ("spenden_protokollabgleich", "donation_minutes_match"), ("spenden_zweitstelle", "donation_second_mention"),
            ("stellenplan_besetzung", "staffing_plan_occupancy"), ("stellenplan_gesamtsumme", "staffing_plan_grand_total"),
            ("stellenplan_gruppensummen", "staffing_plan_group_totals"), ("stellenplan_spaltenprobe", "staffing_plan_columns"),
            ("steuerplan_anteilsprobe", "tax_budget_share_check"), ("steuerplan_istabgleich", "tax_budget_actuals_match"),
            ("steuerplan_summenzeile", "tax_budget_total_row"), ("strukturprobe", "structure_check"),
            ("summenprobe", "sub_budget_sum_check"), ("summenzeile", "total_row"),
            ("textextrakt", "text_layer"), ("unbekannt", "unknown"),
            ("ungeprueft", "unverified"), ("vorjahreskette", "prior_year_chain"),
            ("wirtschaftsplan_erfolgsplan", "business_plan_profit_loss"), ("wirtschaftsplan_investitionen", "business_plan_investments"),
            ("wirtschaftsplan_jahr", "business_plan_year"), ("wirtschaftsplan_kernzahl", "business_plan_key_figure"),
            ("wirtschaftsplan_prosa", "business_plan_prose"), ("wirtschaftsplan_spalten", "business_plan_columns"),
        ]
        self._listenwerte_umschreiben("council_provenance", "probe", PROBEN_NAMEN)
        for tabelle in ("council_expense_series", "council_donations", "council_buergschaften",
                        "council_integrated_debt", "council_fixed_assets",
                        "council_business_plans", "council_budget_bylaw",
                        "council_fees", "council_fee_rates"):
            self._listenwerte_umschreiben(tabelle, "probes", PROBEN_NAMEN)
        # `Herkunft.key()` hasht die Probe mit — nach dem Umzug stimmt kein
        # Fingerabdruck mehr, und der nächste Ingest legte jede Quelle ein
        # zweites Mal an. Neu rechnen, unter einer eigenen Marke.
        self._herkunft_schluessel_neu("herkunft_key_probes")
        # Die neunzehn Bilanz-Positionen (council/bilanz.py::ROLLEN). `liabilities`
        # und `provisions` sind Geschwister auf Ebene 1 der Passivseite, keine
        # Verschachtelung — die `level`-Spalte trägt das.
        BILANZ_ROLLEN = [
            ("immaterielles_vermoegen", "intangible_assets"),
            ("sachvermoegen", "tangible_assets"),
            ("infrastrukturvermoegen", "infrastructure_assets"),
            ("finanzvermoegen", "financial_assets"),
            ("liquide_mittel", "cash_and_equivalents"),
            ("aktive_rap", "prepaid_expenses"), ("nettoposition", "net_position"),
            ("ruecklagen_gesamt", "reserves_total"),
            ("ueberschussruecklage_ordentlich", "ordinary_surplus_reserve"),
            ("jahresergebnis_bilanz", "annual_result_balance_sheet"),
            ("sonderposten", "special_items"), ("schulden", "liabilities"),
            ("geldschulden", "financial_liabilities"), ("rueckstellungen", "provisions"),
            ("pensionen_gesamt", "pension_and_similar_provisions"),
            ("pensionsrueckstellungen", "pension_provisions"),
            ("beihilferueckstellungen", "healthcare_allowance_provisions"),
            ("buergschaftsrueckstellung", "guarantee_provisions"),
            ("passive_rap", "deferred_income"),
        ]
        for tabelle in ("council_balance_sheet", "council_balance_sheet_notes"):
            self._werte_umschreiben(tabelle, "role", BILANZ_ROLLEN)
        # Die Gebührenbereiche. Die Migration MUSS nach `_STRUKTUR_SPALTEN`
        # stehen — dort heißt `bereich` erst `area`, und vorher fände
        # `_werte_umschreiben` die Spalte nicht und kehrte still zurück.
        self._werte_umschreiben("council_fees", "area", [
            ("abfallbehandlung", "waste_treatment"), ("abfallsammlung", "waste_collection"),
            ("strassenreinigung", "street_cleaning")])
        self._werte_umschreiben("council_fee_rates", "area", [
            ("abfallbehandlung", "waste_treatment"), ("abfallsammlung", "waste_collection"),
            ("strassenreinigung", "street_cleaning")])
        self._werte_umschreiben("council_fee_rates", "key", [
            ("abfallbehandlung_mg", "waste_treatment_per_mg"), ("grundgebuehr", "base_fee"),
            ("litergebuehr", "per_litre_fee"), ("biogrundmenge_60l", "organic_base_volume_60l"),
            ("sperrmuellkarte", "bulky_waste_card"), ("gruengutkarte", "green_waste_card"),
            ("sperrmuell_1m3", "bulky_waste_1m3"), ("sperrmuell_2m3", "bulky_waste_2m3"),
            ("gruengut_05m3", "green_waste_05m3"), ("gruengut_1m3", "green_waste_1m3"),
            ("gruengut_2m3", "green_waste_2m3"),
            ("strassenreinigung_qw", "street_cleaning_per_metre")])
        # Der Städtevergleich. `steuerkraft` und `finanzausgleich` hat der Code
        # schon seit #876 englisch gelesen — die Zeilen standen seither still
        # daneben, `staedtevergleich_kontext()` lieferte None.
        self._werte_umschreiben("council_city_comparison", "series", [
            ("steuerkraft", "tax_capacity"), ("finanzausgleich", "fiscal_equalization"),
            ("realsteuern", "real_taxes")])
        # Der Einwohner-Indikator derselben Tabelle: Der Parser schreibt seit
        # dem Umbau `population` (tests/test_staedtevergleich.py), der Bestand
        # trug noch `einwohner` — das Frontend fand ihn nicht, und die
        # Steuerkraft je Einwohner*in blieb auf /haushalt/vergleich leer.
        self._werte_umschreiben("council_city_comparison", "indicator", [
            ("einwohner", "population")])
        # Die Auszahlungsarten der Ist-Investitionen, je Regelwerk eigene.
        self._werte_umschreiben("council_investments_actual_kinds", "field", [
            ("darlehen", "loans_granted"), ("grundvermoegen", "real_property"),
            ("baumassnahmen_k", "construction_cameral"),
            ("bewegliches_k", "movable_assets_cameral"),
            ("zuwendungen", "capitalizable_grants"),
            ("grundstuecke", "land_and_buildings"), ("baumassnahmen", "construction"),
            ("bewegliches", "movable_assets"),
            ("finanzanlagen", "financial_assets_acquired"),
            ("sonstige", "other_investing")])
        for tabelle in ("council_entities", "council_entity_obs"):
            self._werte_umschreiben(tabelle, "kind", [
                ("projekt", "project"), ("ort", "place")])
        # Woher der Ort stammt und wie er gefunden wurde.
        self._werte_umschreiben("council_decision_locations", "source",
                                [("vorlage", "template")])
        self._werte_umschreiben("council_decision_locations", "method", [
            ("stadtteilliste", "district_list"), ("ortskatalog", "place_catalog"),
            ("gebaeudemuster", "building_pattern")])
        # Die Ebenen des Investitionsprogramms.
        self._werte_umschreiben("council_investments", "level", [
            ("teilhaushalt", "sub_budget"), ("investitionen", "investments"),
            ("finanzhaushalt", "financial_budget")])
        self._werte_umschreiben("council_investment_measures", "level", [
            ("massnahme", "measure"), ("teilhaushalt", "sub_budget"), ("gesamt", "total")])
        # Im Ratsinformationssystem liegen nur Entwürfe der Haushaltssatzung.
        self._werte_umschreiben("council_budget_bylaw", "version", [
            ("entwurf", "draft"), ("unbekannt", "unknown")])
        # Welcher Abschnitt der Vorlage die Zweitstelle der Spende trug.
        self._werte_umschreiben("council_donations", "layout", [("neu", "new"), ("alt", "old")])
        # Über- oder außerplanmäßig (§ 117 NKomVG) — oder beides in einer Vorlage.
        self._werte_umschreiben("council_supplementary_approvals", "category", [
            ("ueberplanmaessig", "excess"), ("ausserplanmaessig", "unbudgeted"),
            ("beides", "both")])
        # Was das Modell beim Schreiben des Social-Texts vor sich hatte.
        self._werte_umschreiben("agenda_item_social", "source", [
            ("vorlage+anlagen", "template+attachments"), ("vorlage", "template")])
        # Quiz: Kategorie und Schwierigkeit. `mittel` steht in beiden Spalten,
        # meint aber zweierlei — deshalb je Spalte ein eigener Aufruf.
        self._werte_umschreiben("council_quiz_questions", "category", [
            ("geschichte", "history"), ("orte", "places"), ("menschen", "people"),
            ("ratspolitik", "council_politics"), ("schaetzen", "estimation")])
        self._werte_umschreiben("council_quiz_questions", "difficulty", [
            ("leicht", "easy"), ("mittel", "medium"), ("schwer", "hard")])
        # Das vorläufige Ergebnis aus der Videoaufzeichnung. Dasselbe Vokabular
        # wie `council_decisions` — nur `removed` gibt es hier zusätzlich: Ein
        # abgesetzter Punkt hinterlässt im Protokoll gar keinen Beschluss.
        self._werte_umschreiben("council_video_results", "outcome", [
            ("angenommen", "accepted"), ("abgelehnt", "rejected"),
            ("vertagt", "postponed"), ("zur_kenntnis", "noted"),
            ("abgesetzt", "removed")])
        self._werte_umschreiben("council_video_results", "vote", [
            ("einstimmig", "unanimous"), ("mehrheitlich", "majority")])
        # Wie eine Fraktion abgestimmt hat, und wie ein Beschluss auf ein Ziel wirkt.
        self._werte_umschreiben("council_decision_votes", "stance", [
            ("dagegen", "against"), ("enthaltung", "abstention")])
        self._werte_umschreiben("council_goal_links", "stance", [
            ("voran", "advances"), ("bremst", "hinders")])
        # Wie zwei Entitäten zusammenhängen: gemeinsam belegt oder nur ähnlich.
        self._werte_umschreiben("council_entity_related", "rel_type", [
            ("belegt", "documented"), ("aehnlich", "similar")])
        # Woher eine Quizfrage stammt. `ratsinfo` und `wikipedia` sind Namen.
        self._werte_umschreiben("council_quiz_questions", "source_type", [("stadt", "city")])
        # Der Spielraum, den die Stadt sich bei einem Produkt selbst zuschreibt.
        # Der Wortlaut des Plans steht daneben in `controllability_raw`.
        self._werte_umschreiben("council_products", "controllability", [
            ("niedrig", "low"), ("mittel", "medium"), ("hoch", "high")])

        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        if "agenda_hash" not in cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE committee_notifications ADD COLUMN agenda_hash TEXT NOT NULL DEFAULT ''"
                )
        # council_decisions gained sub-vote columns (kind / parent_item).
        dec_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_decisions)").fetchall()}
        if dec_cols:
            with self._conn:
                if "kind" not in dec_cols:
                    self._conn.execute(
                        "ALTER TABLE council_decisions ADD COLUMN kind TEXT NOT NULL DEFAULT 'decision'"
                    )
                if "parent_item" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN parent_item TEXT")
                # Topic classification (council.topics) — additive.
                for col in ("policy_field", "policy_tags", "summary"):
                    if col not in dec_cols:
                        self._conn.execute(f"ALTER TABLE council_decisions ADD COLUMN {col} TEXT")
                if "amount_eur" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN amount_eur REAL")
                # Wichtigkeits-Score (council.importance) — additiv, per Backfill befüllt.
                if "importance" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN importance INTEGER")
                # „Lotti erklärt's einfach" (RL-904) — additiv, per Backfill befüllt.
                if "simple_summary" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN simple_summary TEXT")
                # Interessantheit (RL-U11, council.interest) — LLM-Score fürs Fundstück.
                if "interest" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN interest INTEGER")
                if "interest_reason" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN interest_reason TEXT")
                # Tragweite (RL-U16, council.impact) — LLM-Score für die Priorität;
                # fließt 50/50 in den Wichtig-Wert ein, sobald befüllt.
                if "impact" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN impact INTEGER")
                if "impact_reason" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN impact_reason TEXT")
                # Abweichung des Beschlusses vom Beschlussvorschlag der Verwaltung
                # (Regex-Ernte, council.ernte): unchanged | slight | strong.
                if "deviation" not in dec_cols:
                    self._conn.execute("ALTER TABLE council_decisions ADD COLUMN deviation TEXT")
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_field ON council_decisions(policy_field)"
                )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_decisions_importance ON council_decisions(importance)"
                )
        # Full-text index for hybrid (BM25 + vector) retrieval. rowid = decision id;
        # diacritics folded so "Radweg"/"radweg" and German umlauts match. Populated by
        # scripts/build_decisions_fts.py (and the daily cron).
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_decisions_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        # Named entities (projects/places/organizations) and their decision links —
        # the basis for the entity ("Themen-") pages. Rebuilt by scripts/extract_entities.py.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entities ("
            "id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, "
            "kind TEXT, n INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_links ("
            "entity_id INTEGER NOT NULL, decision_id INTEGER NOT NULL, "
            "PRIMARY KEY (entity_id, decision_id))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entlink_dec ON council_entity_links(decision_id)")
        # Per-entity enrichment (LLM description + geocoding) keyed by *slug* so it
        # survives the full rebuild of council_entities by extract_entities.py.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_meta ("
            "slug TEXT PRIMARY KEY, description TEXT, "
            "lat REAL, lon REAL, geojson TEXT, geo_tried INTEGER NOT NULL DEFAULT 0)"
        )
        # Raw, append-only entity observations (one row per slug×decision) — the
        # source of truth so incremental NER runs (scripts/extract_entities.py) can
        # re-derive council_entities/links with the min-n threshold WITHOUT re-scanning
        # old decisions, and so an entity seen once now + again later still crosses the
        # threshold (its early observation is retained). council_entity_scanned records
        # every decision already passed through the LLM (incl. those yielding no entity)
        # so it is never re-scanned.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_obs ("
            "decision_id INTEGER NOT NULL, slug TEXT NOT NULL, name TEXT NOT NULL, "
            "kind TEXT, PRIMARY KEY (decision_id, slug))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entobs_slug ON council_entity_obs(slug)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_scanned (decision_id INTEGER PRIMARY KEY)"
        )
        # Eigene Ortsdaten statt Themen-Entitäten zu überladen: Auch einmalige
        # Straßen bleiben erhalten, mehrere Orte je Beschluss sind erlaubt und
        # die Fundstelle/Qualität der Zuordnung bleibt nachprüfbar.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_locations ("
            "slug TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, "
            "lat REAL, lon REAL, geojson TEXT, district TEXT, "
            "place_id TEXT, local_area_id TEXT, "
            "geo_tried INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)"
        )
        location_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_locations)").fetchall()}
        if "place_id" not in location_cols:
            self._conn.execute("ALTER TABLE council_locations ADD COLUMN place_id TEXT")
        if "local_area_id" not in location_cols:
            self._conn.execute("ALTER TABLE council_locations ADD COLUMN local_area_id TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_locations_place ON council_locations(place_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_locations_ortsbereich ON council_locations(local_area_id)")
        # Ein Ort kann in MEHREREN Ortsbereichen liegen. ``council_locations.district``
        # trägt weiterhin genau einen — den überwiegenden, für die Anzeige. Wo ein
        # Ort tatsächlich hingehört, steht hier: Die Alexanderstraße läuft durch
        # fünf Ortsbereiche, und wer nach Ziegelhof filtert, will sie sehen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_location_districts ("
            "location_slug TEXT NOT NULL, district TEXT NOT NULL, place_id TEXT, "
            "share REAL NOT NULL DEFAULT 1.0, "
            "PRIMARY KEY (location_slug, district))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_location_districts_place "
            "ON council_location_districts(place_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_location_districts_district "
            "ON council_location_districts(district)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_locations ("
            "decision_id INTEGER NOT NULL, location_slug TEXT NOT NULL, "
            "source TEXT NOT NULL, evidence TEXT NOT NULL, method TEXT NOT NULL, "
            "confidence REAL NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY (decision_id, location_slug))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decloc_slug "
            "ON council_decision_locations(location_slug)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_location_scans ("
            "decision_id INTEGER PRIMARY KEY, source_hash TEXT NOT NULL, scanned_at TEXT NOT NULL)"
        )
        # Redaktionelle Schicht über den automatisch extrahierten Ortsnamen.
        # Die Rohbeobachtung bleibt dabei unangetastet: Admins können einen
        # Kandidaten als eigenen Katalogort freigeben, einem bestehenden Ort
        # als Alias zuordnen oder für öffentliche Flächen verwerfen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_place_reviews ("
            "location_slug TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "place_id TEXT, name TEXT, kind TEXT, parent_id TEXT, "
            "aliases TEXT NOT NULL DEFAULT '[]', description TEXT, source_url TEXT, "
            "quiz_enabled INTEGER NOT NULL DEFAULT 0, canonical_place_id TEXT, note TEXT, "
            "updated_by TEXT, updated_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_place_reviews_status "
            "ON council_place_reviews(status)"
        )
        # Entity duplicates (council.aliases): the NER names the same thing differently
        # from batch to batch ("Bäderbetrieb Oldenburg" / "Bäderbetrieb der Stadt
        # Oldenburg"), producing several Themen pages for one subject. This maps the
        # alias slug onto the canonical one; rebuild_entities_from_obs applies it when
        # deriving council_entities. Keyed by *slug* (like council_entity_meta) so it
        # survives the rebuild. Reversible: the raw council_entity_obs stay untouched,
        # so deleting a row and re-deriving restores the previous state.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_aliases ("
            "slug TEXT PRIMARY KEY, canonical_slug TEXT NOT NULL, source TEXT NOT NULL, "
            "reason TEXT, created_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entalias_canon "
            "ON council_entity_aliases(canonical_slug)"
        )
        # Vagheits-Urteil je Themen-Vorschlag (Design 26a). Die Prüfung ist ein
        # LLM-Aufruf — ungecacht würde jeder Aufruf der Themen-Seite ein Dutzend
        # davon auslösen. Ergebnis hält, bis der Name sich ändert; keyed by
        # *slug*, überlebt also den Entitäten-Rebuild.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_topic_vagueness ("
            "slug TEXT PRIMARY KEY, name TEXT NOT NULL, vague INTEGER NOT NULL, "
            "hint TEXT, suggestion TEXT, checked_at TEXT NOT NULL)"
        )
        # Related entities ("Hängt zusammen mit…") — precomputed by council.related
        # via scripts/build_entity_relations.py. rel_type separates the two sources:
        # 'belegt' = co-occurrence in shared decisions (evidence = how many),
        # 'aehnlich' = embedding neighbour used only to fill up to top-K. Keyed by
        # *slug* (like council_entity_meta) so it survives the entity rebuild.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_entity_related ("
            "slug TEXT NOT NULL, neighbor_slug TEXT NOT NULL, rel_type TEXT NOT NULL, "
            "rank INTEGER NOT NULL, score REAL NOT NULL, evidence INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (slug, neighbor_slug))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entrelated_slug ON council_entity_related(slug, rank)"
        )
        # Vorlagen full text (council.vorlagen): the Sachverhalt/Begründung behind a
        # decision. Keyed by kvonr (the SessionNet document id); template_number is the
        # human number ("26/0330") decisions/agenda items reference.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_templates ("
            "kvonr INTEGER PRIMARY KEY, template_number TEXT, title TEXT, kind TEXT, "
            "document_id INTEGER, document_url TEXT, raw_text TEXT, n_pages INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'ok', "  # ok | empty | no_pdf | failed
            "attachments_scanned INTEGER NOT NULL DEFAULT 0)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_vorlagen_nr ON council_templates(template_number)")
        # anlagen_scanned kam nach dem ersten Deploy der Tabelle dazu.
        vcols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_templates)").fetchall()}
        if "attachments_scanned" not in vcols:
            self._conn.execute(
                "ALTER TABLE council_templates ADD COLUMN attachments_scanned INTEGER NOT NULL DEFAULT 0"
            )
        # Regex-Ernte aus dem Volltext (council.ernte): federführendes Amt,
        # Auswirkungen-Abschnitte, Beschlussvorschlag der Verwaltung.
        for col in ("office", "climate_impact", "financial_impact", "proposed_decision"):
            if col not in vcols:
                self._conn.execute(f"ALTER TABLE council_templates ADD COLUMN {col} TEXT")
        # Nutzer-Feedback zu KI-Antworten (5a/I-03) — der einzige Qualitäts-
        # messer außerhalb der Eval-Gold-Fälle. Bewusst schlank: Frage,
        # Antwort-Anfang, Daumen, optionaler Freitext-Grund.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_qa_feedback ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, "
            "answer_excerpt TEXT, rating TEXT NOT NULL, reason TEXT, "
            "user_id INTEGER, created TEXT NOT NULL)"
        )
        # Anlagen zu Vorlagen: alle als Label+Link, Fraktions-Anträge zusätzlich mit
        # PDF-Text und erkannten Antragstellern (council.vorlagen/_build_anlage_rows).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_attachments ("
            "document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT, "
            "url TEXT, is_motion INTEGER NOT NULL DEFAULT 0, applicants TEXT, "
            "raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'listed')"  # listed | ok | empty | failed | ocr
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_anlagen_kvonr ON council_attachments(kvonr)")
        # Gerenderte Planzeichnung (scripts/render_plaene.py): 0 = offen,
        # 1 = Bild liegt unter data/plaene/<document_id>.jpg, -1 = fehlgeschlagen.
        aacols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_agenda_attachments)").fetchall()}
        if aacols and "raw_text" not in aacols:
            self._conn.execute("ALTER TABLE council_agenda_attachments ADD COLUMN raw_text TEXT")

        acols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_attachments)").fetchall()}
        if "is_image" not in acols:
            self._conn.execute(
                "ALTER TABLE council_attachments ADD COLUMN is_image INTEGER NOT NULL DEFAULT 0")
        # Welches Sehmodell den Text gelesen hat (scripts/backfill_anlagen_ocr.py).
        # NULL heißt „aus der Textebene des PDF", also gar nicht geraten.
        #
        # `status='ocr'` IST KEINE BUCHHALTUNG, SONDERN EINE SPERRE: Jede Anlage
        # mit `status='ok'` zieht `anlagen_missing_embeddings()` in die
        # Chunk-Vektoren und damit in die Gründliche Recherche und in
        # Nutzerantworten. Für OCR-Text ist das die falsche Voreinstellung —
        # er ist eine schwächere Quelle als eine echte Textebene, und ein Teil
        # der betroffenen Dokumente sind Förderanträge von Vereinen mit Namen,
        # Anschriften und Unterschriften darauf. Die Finanz-Parser lesen
        # trotzdem mit: `finanzquellen.Erkennung.where()` filtert bewusst NICHT
        # auf den Status. Wer den Text später auch durchsuchbar machen will,
        # setzt ihn gezielt auf 'ok' — eine Entscheidung, kein Nebeneffekt.
        if "ocr_model" not in acols:
            self._conn.execute(
                "ALTER TABLE council_attachments ADD COLUMN ocr_model TEXT")
        # `status='ocr'` gab es genau einen Tag lang (20.08.2026). Solange galt
        # gelesener Scan-Text als grundsätzlich nicht durchsuchbar — eine
        # Sperre gegen die HERKUNFT des Textes statt gegen das, was darin
        # steht, und sie schloss den AWB-Wirtschaftsplan und den Prüfbericht
        # gleich mit aus. Die Sperre sitzt jetzt an der Index-Grenze
        # (`council/kontaktdaten.py`), und diese Zeilen sind ganz normaler
        # Anlagentext. `ocr_model` sagt weiterhin, wie sie entstanden sind.
        #
        # Gehoben statt neu gelesen: Der Text ist in Ordnung, nur sein Status
        # war es nicht. Ein erneuter OCR-Lauf kostete Geld für nichts.
        self._conn.execute(
            "UPDATE council_attachments SET status = 'ok' WHERE status = 'ocr'")
        # Beratungsfolge je Vorlage (council.stammdaten): die offiziellen
        # Stationen einer Vorlage durch die Gremien — inkl. geplanter künftiger
        # Beratungen (ergebnis dann NULL). Je kvonr komplett ersetzt, weil
        # Stationen dazukommen und Ergebnisse nachgetragen werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_deliberations ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, kvonr INTEGER NOT NULL, "
            "date TEXT, committee TEXT NOT NULL DEFAULT '', top TEXT, "
            "is_public INTEGER, result TEXT, ksinr INTEGER, "
            "fetched_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_beratungen_kvonr ON council_deliberations(kvonr)")
        # Mandatsträger + Gremien-Mitgliedschaften (council.stammdaten). Die
        # Fraktion ist nur der AKTUELLE RIS-Stand — SessionNet überschreibt
        # Fraktionen rückwirkend; die Historie liefert council_attendance.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_persons ("
            "kpenr INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "current_faction TEXT, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_memberships ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, kpenr INTEGER NOT NULL, "
            "kgrnr INTEGER, committee TEXT NOT NULL, role TEXT, "
            "valid_from TEXT, valid_until TEXT, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_kpenr ON council_memberships(kpenr)")
        # Quizfragen (council.quiz): generierte Multiple-Choice-Fragen je Gebiet
        # (Stadtteil/Wahlbereich/Thema), gegroundet in Wikipedia/Stadt-Website/
        # Ratsdaten. status='retired' fliegt aus den Runden (schlecht bewertet).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_quiz_questions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "area_type TEXT NOT NULL, area_key TEXT NOT NULL, "  # district|electoral_district|topic
            "category TEXT NOT NULL, "                            # history|places|people|council_politics|estimation
            "difficulty TEXT NOT NULL DEFAULT 'mittel', "         # leicht|mittel|schwer
            "question TEXT NOT NULL, options TEXT NOT NULL, "     # options = JSON-Array (4); [] bei estimate
            "correct_index INTEGER NOT NULL, explanation TEXT, "
            "source_type TEXT, source_ref TEXT, "                # wikipedia|stadt|ratsinfo · URL/id
            "content_hash TEXT UNIQUE, "                          # Dedup
            "status TEXT NOT NULL DEFAULT 'active', "             # active|retired
            "qtype TEXT NOT NULL DEFAULT 'mc', "                  # mc | estimate (Schätzfrage-Slider)
            "answer_value REAL, answer_unit TEXT, "              # estimate: richtige Zahl + Einheit
            "range_min REAL, range_max REAL, "                   # estimate: Slider-Grenzen
            "detail TEXT, hint TEXT, topic TEXT, chart TEXT, "     # „Mehr dazu" + Tipp + Beschluss-Stichwort + Diagramm (JSON)
            "lat REAL, lon REAL, place_label TEXT, geojson TEXT, "  # Locator-Karte (Punkt, Linie oder Gebiets-Polygon)
            "image_url TEXT, image_author TEXT, image_license TEXT, "  # Foto (Wikimedia Commons)
            "image_license_url TEXT, image_source_url TEXT, "    # Bildnachweis
            "generated_at TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_area ON council_quiz_questions(area_type, area_key)")
        # Stadt-Haushalt (council.haushalt): Ergebnishaushalt je Teilhaushalt und
        # Jahr, geparst aus den offiziellen Haushaltsplan-PDFs (oldenburg.de).
        # Grundlage der Haushalts-Quizfragen samt Diagramm.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "year INTEGER NOT NULL, "
            "area TEXT NOT NULL, "                             # Teilhaushalt-Name; 'Summe' = Gesamtzeile
            "revenues REAL, expenses REAL, result REAL, "  # ordentlich, in Euro
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "source_url TEXT, fetched_at TEXT NOT NULL, "
            "UNIQUE(year, area))"
        )
        # Ist-Steuereinnahmen je Steuerart und Jahr (Open-Data-Portal der Stadt,
        # seit 1998) — Grundlage der Steuer-Steckbriefe im Haushalts-Bereich.
        # Langformat: eine Zeile je (Jahr, Steuerart), 'insgesamt' als eigene Art.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_taxes ("
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "       # z. B. 'Gewerbesteuer (-umlage)', 'insgesamt'
            "amount REAL, "              # Euro, Ist (nicht Plan!)
            "source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, kind))"
        )
        # Ergebnisrechnung aus den Jahresabschlüssen (RIS-Anlagen): Ansatz UND
        # Ergebnis je Posten — die Grundlage für „geplant gegen tatsächlich"
        # und für die Aufschlüsselung der Erträge nach Arten.
        # thh_nr trennt die Ebenen: NULL = Kernverwaltung gesamt, 1–13 = der
        # jeweilige Teilhaushalt. Beide Ebenen teilen sich die Tabelle, weil
        # sie dieselben Posten tragen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_income_statement ("
            "year INTEGER NOT NULL, "
            "sub_budget_no INTEGER, sub_budget_name TEXT, "     # NULL = Gesamtrechnung
            "nr INTEGER NOT NULL, "               # Postennummer der Tabelle (1–24)
            "label TEXT NOT NULL, "
            "prior_year REAL, budgeted REAL, result REAL, deviation REAL, "
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, sub_budget_no, nr))"
        )
        # Die Tabelle kam mit der Vorversion ohne thh_nr; SQLite kann den
        # Primärschlüssel nicht per ALTER TABLE erweitern. Neu anlegen ist
        # hier gefahrlos: Der Inhalt stammt vollständig aus council_attachments
        # und wird von scripts/ingest_finanzberichte.py in Sekunden wieder
        # hergestellt — es geht keine Quelle verloren.
        spalten = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_income_statement)")}
        if spalten and "sub_budget_no" not in spalten:
            self._conn.execute("DROP TABLE council_income_statement")
            self._conn.execute(
                "CREATE TABLE council_income_statement ("
                "year INTEGER NOT NULL, sub_budget_no INTEGER, sub_budget_name TEXT, "
                "nr INTEGER NOT NULL, label TEXT NOT NULL, "
                "prior_year REAL, budgeted REAL, result REAL, deviation REAL, "
                "is_total INTEGER NOT NULL DEFAULT 0, "
                "source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, "
                "PRIMARY KEY (year, sub_budget_no, nr))"
            )
        # „Plan" heißt nicht in jedem Jahrgang dasselbe: 2018 ist die
        # Bezugsgröße der Abweichung die Gesamtermächtigung, 2020 der Ansatz
        # samt Nachtrag (27 Mio. Unterschied!), sonst der nackte Ansatz.
        # Deshalb steht in `ansatz` weiter der ursprüngliche Haushaltsansatz,
        # in `plan` die Bezugsgröße und in `plan_kind`, welche davon gemeint
        # ist. Ohne das letzte Feld wäre eine Mehrjahres-Kurve still falsch.
        # Nachrüsten per ALTER: Der Primärschlüssel bleibt, nichts geht verloren.
        for spalte, typ in (("plan", "REAL"), ("plan_kind", "TEXT")):
            if spalte not in spalten:
                try:
                    self._conn.execute(
                        f"ALTER TABLE council_income_statement ADD COLUMN {spalte} {typ}")
                except sqlite3.OperationalError:
                    pass  # frisch angelegt — Spalte ist schon da
        # Finanzrechnung der Kernverwaltung (Abschnitt 4.1 desselben
        # Jahresabschlusses): nicht was gebucht, sondern was **gezahlt** wurde.
        # Die Ergebnisrechnung darüber weist für 2024 einen Überschuss von
        # 6,1 Mio. € aus, die Finanzrechnung im selben Heft einen
        # Finanzmittel-Fehlbetrag von 22,4 Mio. € — beides stimmt, und ohne
        # die zweite Zahl entsteht ein falscher Eindruck.
        #
        # `nr` ist die Nummer, die das Dokument vergibt; sie verschiebt sich
        # zwischen den Jahrgängen um eins (2017–2020 hat die Tabelle 42
        # Zeilen, ab 2021 nur 41). Deshalb steht daneben `role` — der stabile
        # Name aus `finanzberichte.ROLLEN`, an dem Frontend und Proben hängen.
        # `authorization` ist die Spalte „Ermächtigungen aus Haushalts-
        # vorjahren": Geld aus früheren Jahren, das noch ausgegeben werden
        # durfte. Sie ist NULL, wo der Jahrgang sie nicht führt oder wo ihre
        # eigene Summenprobe gerissen ist.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_cash_flow_statement ("
            "year INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "               # Zeilennummer DES DOKUMENTS
            "role TEXT, "                        # stabiler Name, NULL = Einzelzeile
            "label TEXT NOT NULL, "         # Wortlaut des Dokuments
            "prior_year REAL, budgeted REAL, plan REAL, plan_kind TEXT, "
            "result REAL, deviation REAL, authorization REAL, "
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, nr))"
        )
        # Warum ein Posten vom Plan abweicht, in den Worten der Verwaltung:
        # Abschnitt 6.3.1 des Jahresabschlusses, je Posten. Übernommen wird
        # nur, was die Rechenprobe besteht (siehe finanzberichte).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_variance_reasons ("
            "year INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "                # Postennummer der Tabelle
            "label TEXT NOT NULL, "          # so, wie der Abschnitt sie nennt
            "delta_meur REAL, percent REAL, "       # laut Überschrift des Blocks
            "text TEXT NOT NULL, "
            "source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, nr))"
        )
        # Die Bilanz der Stadt (Abschnitt 2.1 desselben Jahresabschlusses):
        # nicht was die Stadt einnimmt oder schuldet, sondern was sie **hat**
        # — und was davon schon vergeben ist. Der größte Passivposten sind
        # die Pensionsrückstellungen (2024: 311,79 Mio. € einschließlich
        # Beihilfe, 266,26 Mio. € ohne), ein Vielfaches der 43,69 Mio. €
        # Kreditschulden (council/bilanz.py).
        #
        # `role` ist der Schlüssel, nicht `nr`: Die Gliederungsnummer ist ab
        # 2021 auf beiden Bilanzseiten dieselbe („1.1" gibt es zweimal), und
        # bis 2020 war sie römisch. Der Name, den das Dokument der Zeile
        # gibt, ist das einzig Stabile — deshalb steht er in `label`
        # im Wortlaut daneben.
        #
        # Kein `value_prior_year`: Die zweite Spalte der Bilanz ist der Stichtag
        # davor, und der ist ein **eigener Jahrgang** in dieser Tabelle. Sie
        # zusätzlich an der Zeile zu führen hieße, denselben Stand zweimal zu
        # speichern — mit der Aussicht, dass die beiden eines Tages
        # auseinanderlaufen. Gebraucht wird sie beim Einlesen (als
        # Vorjahres-Kette über Dokumentgrenzen) und beim ältesten Jahrgang,
        # der ausschließlich aus ihr stammt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_balance_sheet ("
            "year INTEGER NOT NULL, "             # Bilanzstichtag 31.12.year
            "role TEXT NOT NULL, "               # stabiler Name (bilanz.ROLLEN)
            "page TEXT NOT NULL, "               # 'aktiva' | 'passiva'
            "level INTEGER NOT NULL, "            # 1 = Hauptposten der Bilanzsumme
            "nr TEXT, "                           # Gliederungsnummer DES DOKUMENTS
            "label TEXT NOT NULL, "         # Wortlaut des Dokuments
            "value REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, role))"
        )
        # Was die Verwaltung zu jedem Hauptposten schreibt: Anhang 6.2.1–6.2.9
        # desselben Dokuments, ein Abschnitt je Bilanzposition.
        #
        # Diese Tabelle ist keine Zierde, sondern eine Auflage. Die Bilanz
        # 2024 weist Schulden von 207,1 Mio. € aus nach 84,4 Mio. € im
        # Vorjahr; ohne 6.2.7 läse sich das als Verdreifachung. Der Abschnitt
        # sagt, dass es eine Bilanzverlängerung aus dem Cash-Pooling ist,
        # 138,2 Mio. €, mit Gegenposten auf der Aktivseite. **Die Zahl darf
        # ohne diesen Text nicht angezeigt werden** — dieselbe Bauart wie
        # `council_variance_reasons` für die Ergebnisrechnung.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_balance_sheet_notes ("
            "year INTEGER NOT NULL, "
            "role TEXT NOT NULL, "               # dieselbe Marke wie council_balance_sheet
            "nr INTEGER NOT NULL, "               # 6.2.N
            "heading TEXT NOT NULL, "        # Wortlaut der Abschnittsüberschrift
            "text TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, role))"
        )
        # Gesamtergebnishaushalt aus den Haushaltsplänen (RIS-Anlage 005):
        # dieselbe Postengliederung wie die Ergebnisrechnung, aber für Jahre,
        # die noch gar keinen Jahresabschluss haben (council/ergebnishaushalt.py).
        #
        # DREI SPALTEN, DIE ZUSAMMENGEHÖREN — und deren Trennung der ganze
        # Zweck dieser Tabelle ist:
        #
        # `year`          Für welches Jahr die Zahl gilt.
        # `art`           `ansatz` = das Jahr, für das dieser Plan DER Haushalt
        #                 ist. `finanzplanung` = mittelfristige Vorausschau
        #                 nach § 8 NKomVG. Das Dokument nennt beides „Ansatz";
        #                 das ist Haushaltsrecht, aber keine Beschlusslage.
        #                 Wer die Unterscheidung wegwirft, behauptet für 2029
        #                 einen Plan. (Und auch `ansatz` ist der Stand der
        #                 Einbringung, nicht der Beschluss des Rates — die
        #                 Herkunft sagt es je Zeile, die Messwerte dazu stehen
        #                 im Kopf von council/ergebnishaushalt.py.)
        # `plan_budget_year` Aus welchem Haushalt die Zahl stammt. Sie steht im
        #                 Schlüssel, weil dasselbe Jahr in mehreren Plänen
        #                 vorkommt: 2027 ist im Haushalt 2026 die erste
        #                 Finanzplanungsstufe, im Haushalt 2027 der Ansatz.
        #                 Und die Finanzplanung wird jedes Jahr neu
        #                 geschrieben — von 23 Posten stimmen zwischen zwei
        #                 aufeinanderfolgenden Plänen 0 bis 2 überein.
        #
        # Ohne `plan_budget_year` im Schlüssel überschriebe der jüngste Plan
        # stillschweigend, was der ältere für dasselbe Jahr sagte. Mit ihm
        # ist beides nachlesbar, und die Frage „was war der Ansatz für 2026?"
        # hat genau eine Antwort: kind='budget'.
        #
        # Herkunft ausschließlich über `herkunft_id` — die Tabelle ist neu und
        # hat keinen Altbestand (s. council/herkunft.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_income_budget ("
            "plan_budget_year INTEGER NOT NULL, "     # Haushalt, aus dem die Zahl stammt
            "year INTEGER NOT NULL, "              # Jahr, für das sie gilt
            "kind TEXT NOT NULL, "                 # budget | financial_plan
            "nr INTEGER NOT NULL, "                # Postennummer 1–24, wie im Abschluss
            "label TEXT NOT NULL, "
            "amount REAL NOT NULL, "
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (plan_budget_year, year, nr))"
        )
        # Der Lesepfad fragt „welcher Ansatz gilt für Jahr X?" — nicht „was
        # stand im Plan Y?". Deshalb der Index auf (year, art).
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ergebnishaushalt_jahr "
            "ON council_income_budget(year, kind)")
        # Der Stellenplan (Anlage 21/22 des Haushaltsplans, council/stellenplan.py):
        # wie viele Stellen die Stadt vorhält, wie viele davon besetzt sind
        # und wie viele nicht.
        #
        # `part`  A = Beamtinnen und Beamte, B = Arbeitnehmerinnen und
        #         Arbeitnehmer. Zwei Tabellen im Dokument, zwei Spaltensätze,
        #         zwei Rechenproben — und sie kommen einzeln herein: Im
        #         Stellenplan 2026 ist Teil B im Textextrakt Glyphen-Salat,
        #         Teil A steht sauber da. Ohne `part` im Schlüssel wäre dieser
        #         Jahrgang entweder ganz draußen oder still halb drin.
        # `art`   posten | gruppe | gesamt — die drei Stufen der Summenzeilen.
        #         Die Summen stehen als eigene Zeilen in der Tabelle, weil sie
        #         im Dokument stehen: Eine Seite, die „815 Stellen" zeigt, soll
        #         die Zahl der Stadt zeigen und nicht unsere Addition.
        # `row_no` Laufende Nummer innerhalb von (jahrgang, teil, art) —
        #         nicht die Lfd.Nr. des Plans. Die taugt nicht als Schlüssel:
        #         Die Summenzeilen tragen keine, und zwei Teile fangen beide
        #         bei 1 an. Sie steht daneben in `seq_no`.
        # `consistent` 0 heißt: In dieser Zeile ergeben besetzt + nicht besetzt
        #         nicht die Stellen des Vorjahres — so steht es im Plan. Zwei
        #         Zeilen im Bestand sind das (Begründung in
        #         `council/stellenplan.besetzungsprobe`).
        #
        # `filled_by_officials`/`filled_by_employees` gibt es nur in Teil A: Eine
        # Beamtenstelle darf mit Tarifbeschäftigten besetzt werden, und der
        # Plan weist das getrennt aus. Teil B kennt die Unterscheidung nicht
        # und lässt beide Spalten leer; `besetzt` trägt in beiden Teilen die
        # Gesamtbesetzung.
        #
        # Herkunft ausschließlich über `herkunft_id` — neue Tabelle, kein
        # Altbestand (s. council/herkunft.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_staff_plan ("
            "budget_year INTEGER NOT NULL, "          # Haushaltsjahr des Plans
            "part TEXT NOT NULL, "                 # A | B
            "row_no INTEGER NOT NULL, "          # Reihenfolge im Dokument
            "kind TEXT NOT NULL, "                 # item | group | total
            "pay_group TEXT, "                     # Laufbahngruppe 2, Beschäftigte TVöD …
            "seq_no INTEGER, "                     # Nummer im Plan (Summen: NULL)
            "label TEXT NOT NULL, "
            "pay_grade TEXT, "                     # A 13, S 08 a, 15 …
            "positions_planned REAL NOT NULL, "         # Stellen im Haushaltsjahr
            "positions_prior_year REAL NOT NULL, "      # Stellen im Vorjahr
            "filled REAL NOT NULL, "              # am Stichtag besetzt
            "filled_by_officials REAL, "                # davon mit Beamt*innen (Teil A)
            "filled_by_employees REAL, "          # davon mit Tarifbeschäftigten (Teil A)
            "vacant REAL NOT NULL, "
            "as_of_date TEXT, "                      # auf welchen Tag sich die Besetzung bezieht
            "consistent INTEGER NOT NULL DEFAULT 1, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, part, row_no))"
        )
        # Die Seite fragt fast immer „gib mir die Summen aller Jahrgänge" —
        # eine Handvoll Zeilen aus rund tausend.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stellenplan_art "
            "ON council_staff_plan(kind, budget_year)")
        # Die Investitionen des Finanzhaushalts (council/investitionen.py) —
        # was die Stadt bauen und kaufen will, je Teilhaushalt. Die andere
        # Hälfte des Haushaltsplans: Im Ergebnishaushalt darüber steht keine
        # einzige Investition.
        #
        # `level` trennt drei Dinge, die verschieden weit reichen:
        #   `teilhaushalt`  eine der 13 Zeilen (thh_nr 1–13)
        #   `investitionen` die Summenzeile der Datei — das ZIEL der
        #                   Rechenprobe, nicht unsere Addition
        #   `finanzhaushalt` der Gesamtbetrag ALLER Ein-/Auszahlungen, also
        #                   samt laufender Verwaltungstätigkeit. Bezugsgröße,
        #                   von keiner Probe der Datei gedeckt und deshalb mit
        #                   eigener Herkunft (herkunft.UNGEPRUEFT).
        #
        # `sub_budget_no` ist 0 auf den beiden Summenzeilen — sie tragen keine
        # Teilhaushaltsnummer. Bewusst 0 statt NULL: SQLite lässt NULL in einer
        # PRIMARY KEY zu und hält zwei NULL-Zeilen für verschieden, der
        # Schlüssel wäre dort also gar keiner.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investments ("
            "year INTEGER NOT NULL, "              # Haushaltsjahr (Plan)
            "level TEXT NOT NULL, "                # sub_budget|investments|financial_budget
            "sub_budget_no INTEGER NOT NULL DEFAULT 0, "  # 0 = Summenzeile
            "label TEXT NOT NULL, "
            "inflows REAL NOT NULL, "
            "outflows REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, level, sub_budget_no))"
        )
        # Die einzelnen Vorhaben aus Anlage 004 des Haushaltsplans
        # (council/investitionsprogramm.py) — die Ebene unter
        # `council_investments`: nicht „Schule und Bildung: 8,3 Mio. €",
        # sondern „BBS Haarentor: Ausstattung".
        #
        # `level` trennt drei Zeilenarten, die zusammen aus einem Dokument
        # kommen und einander stützen:
        #   massnahme     — ein Vorhaben, mit IPSP-Element als `code`
        #   teilhaushalt  — die Gesamtsumme des Abschnitts (Ziel der Probe)
        #   gesamt        — die Gesamtsumme des Investitionsprogramms
        #
        # Gespeichert wird ausschließlich die **Gesamtinvestitionssumme**. Die
        # Jahresraten der Tabelle sind aus dem Textextrakt nicht sicher zu
        # holen, weil leere Zellen darin ersatzlos wegfallen — die Begründung
        # steht im Kopf von council/investitionsprogramm.py.
        #
        # `code` ist '' auf den beiden Summenebenen und `sub_budget_no` 0 auf
        # `gesamt` — bewusst leer statt NULL, aus demselben Grund wie bei
        # `council_investments`: SQLite hielte zwei NULL-Zeilen für
        # verschieden, der Primärschlüssel wäre dort keiner.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investment_measures ("
            "year INTEGER NOT NULL, "              # Haushaltsjahrgang (Plan)
            "level TEXT NOT NULL, "                # measure|sub_budget|total
            "sub_budget_no INTEGER NOT NULL DEFAULT 0, "
            "code TEXT NOT NULL DEFAULT '', "      # IPSP-Element
            "label TEXT NOT NULL, "
            "grand_total REAL NOT NULL, "
            "details TEXT, "                       # Sachkonto-Detailnamen, " · "-getrennt
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, level, sub_budget_no, code))"
        )
        # `details` kam am 26.08.2026 dazu (Namen der Sachkonto-Detailzeilen,
        # council/investitionsprogramm.py) — additiv, füllt der nächste Ingest.
        inv_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_investment_measures)").fetchall()}
        if inv_cols and "details" not in inv_cols:
            self._conn.execute(
                "ALTER TABLE council_investment_measures ADD COLUMN details TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invprog_jahr_thh "
            "ON council_investment_measures(year, sub_budget_no)")
        # Schlussberichte des Rechnungsprüfungsamts — nur die **Fundstelle**,
        # nicht der Inhalt: „Das Rechnungsprüfungsamt hat diesen Abschluss
        # geprüft → Schlussbericht". Eine Zeile je Jahrgang.
        # `readable` = 0 heißt, der Volltext des PDFs ist unbrauchbar (2024).
        #
        # Der Name trägt bewusst „_quellen": Die einzelnen
        # Prüfungsfeststellungen aus denselben Berichten (Beanstandung,
        # Wiederholte Beanstandung, Hinweis) sind eine andere Ebene mit einer
        # Zeile je Feststellung und gehören in eine eigene Tabelle.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_audit_report_sources ("
            "year INTEGER PRIMARY KEY, "
            "label TEXT, url TEXT, n_pages INTEGER, "
            "readable INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL)"
        )
        # Produktebene aus den Teilhaushalts-Plänen: was einzelne Aufgaben
        # kosten, mit Produktnummer und zuständigem Amt — dazu der Steckbrief,
        # den die Pläne zu jedem Produkt führen (was die Aufgabe umfasst, auf
        # welchem Gesetz sie beruht, wie viel Spielraum die Stadt bei ihr hat).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_products ("
            "year INTEGER NOT NULL, "
            "product_no TEXT NOT NULL, "          # z. B. P10.111023
            "product_name TEXT NOT NULL, "
            "sub_budget_no INTEGER, sub_budget_name TEXT, office TEXT, "
            "revenues REAL, expenses REAL, result REAL, "
            "short_description TEXT, legal_basis TEXT, "
            "controllability TEXT, "            # normalisiert: niedrig|mittel|hoch
            "controllability_raw TEXT, "        # Wortlaut des Plans
            "scope TEXT, target_group TEXT, "
            "source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, product_no))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_produkte_thh ON council_products(year, sub_budget_no)")
        # Prüfungsfeststellungen aus den Schlussberichten des Rechnungs-
        # prüfungsamts (RIS-Anlagen): die einzige regelmäßige, förmliche
        # Kontrolle der Verwaltung durch eine eigene Stelle.
        #
        # `mark` ist die Randmarke des Berichts (B/WB/H/K), `mark_name` und
        # `mark_explanation` sind die Legende DIESES Jahrgangs — nicht unsere
        # Formulierung. Sie stehen bewusst je Zeile statt in einer zweiten
        # Tabelle: Die Legende ändert sich zwischen den Jahrgängen (2023 kennt
        # kein K mehr), und ein Bericht ohne seine eigene Legende wäre gar
        # nicht erst eingelesen worden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_audit_reports ("
            "year INTEGER NOT NULL, "              # geprüfter Jahresabschluss
            "seq INTEGER NOT NULL, "               # Reihenfolge im Dokument
            "mark TEXT NOT NULL, "                # B | WB | H | K
            "mark_name TEXT NOT NULL, "           # 'Wiederholte Beanstandung'
            "mark_explanation TEXT, "            # Legendentext des Jahrgangs
            "text_number TEXT NOT NULL, "           # Fundstelle, z. B. '4.5.2'
            "section TEXT NOT NULL, "            # Überschrift der Textziffer
            "chain TEXT, "                         # Schlüssel für WB-Ketten
            "page INTEGER, "                      # Seite im Bericht
            "text TEXT NOT NULL, "
            "follow_paragraph TEXT, "                   # was im Bericht direkt folgt
            "source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, seq))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pruefberichte_kette "
            "ON council_audit_reports(chain, year)")
        # Einwohnerzahl je Haushaltsjahr (Open-Data, Stichtag 31.12. des
        # Vorjahres) — Bezugsgröße für Pro-Kopf-Einordnungen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_einwohner ("
            "year INTEGER PRIMARY KEY, population INTEGER NOT NULL, "
            "source_url TEXT, fetched_at TEXT NOT NULL)"
        )
        # Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr (Open-Data,
        # seit 1993) — zeigt die NFAG-Mechanik: mehr Steuerkraft, weniger
        # Zuweisungen. Pflichtwissen für jede ehrliche Hebesatz-Simulation.
        # `year` ist das Ausgleichsjahr, nicht die Jahreszahl aus der Quelle:
        # Der Datensatz 1106 beschriftet um ein Jahr zu früh, wir rücken beim
        # Einlesen (Beleg in `council/haushalt._STEUERKRAFT_VERSATZ`). Die
        # beiden `*_je_ew`-Spalten bleiben deshalb leer — sie tragen die
        # Pro-Kopf-Rechnung der Quelle und damit deren falsches Bezugsjahr.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_tax_capacity ("
            "year INTEGER PRIMARY KEY, "
            "tax_index REAL, tax_capacity_per_capita REAL, "          # Euro bzw. Euro/Einwohner
            "allocations REAL, allocations_per_capita REAL, "    # Anordnungssoll
            "source_url TEXT, fetched_at TEXT NOT NULL)"
        )
        # Herkunft der Finanzzahlen — ein Datensatz je Dokument-und-Abschnitt,
        # auf den die Datenzeilen per `herkunft_id` zeigen. Warum eine eigene
        # Tabelle statt Spalten in jeder Zieltabelle, steht ausführlich im
        # Modulkopf von `council/herkunft.py`; kurz: Eine Zieltabelle trägt
        # Zeilen aus mehreren Dokumenten (bei den Beteiligungen der
        # Normalfall), ein neues Herkunftsfeld darf nicht neun ALTER TABLE
        # kosten, und ein Jahrgang schriebe dieselbe Angabe sonst 200-mal.
        #
        # `key` ist der Fingerabdruck über alle Inhaltsfelder und macht
        # das Eintragen idempotent — `fetched_at` steht bewusst NICHT darin
        # (s. Herkunft.schluessel), sonst wüchse die Tabelle mit der Zahl der
        # Läufe statt mit der Zahl der Quellen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_provenance ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key TEXT NOT NULL UNIQUE, "
            "kind TEXT NOT NULL, "                 # ris | opendata | city
            "document_id INTEGER, "                # council_attachments.document_id
            "label TEXT, url TEXT, "
            "citation TEXT, page INTEGER, "     # wo IM Dokument
            "probe TEXT NOT NULL, probe_result TEXT, "  # womit abgesichert
            "as_of TEXT, "                         # Stichtag des Inhalts
            "fetched_at TEXT NOT NULL)"            # zuletzt bestätigt
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_herkunft_dokument "
            "ON council_provenance(document_id)")
        # Der Konzern Stadt Oldenburg aus dem konsolidierten Gesamtabschluss
        # (council/konzernabschluss.py). Zwei Ebenen, zwei Tabellen:
        #
        # `council_group_items` = die Gesamtergebnisrechnung des Konzerns,
        # Posten für Posten. `role` ist der Grund, warum es diese Spalte gibt:
        # Bis 2018 ist Posten 15 die Summe der ordentlichen Erträge, ab 2019
        # ist es Posten 13. Wer über Jahre hinweg nach `nr` fragt, bekommt ab
        # 2019 stillschweigend die Versorgungsaufwendungen. Gefragt wird
        # deshalb nach der Rolle; die Nummer steht nur noch als Fundstelle
        # daneben.
        #
        # BEIDE TABELLEN FÜHREN IHRE HERKUNFT AUSSCHLIESSLICH ÜBER
        # `herkunft_id` — kein `source_label`, kein `source_url`. Die neun
        # älteren Finanztabellen tragen ihre Altspalten weiter, weil ein
        # Umbau dort neun Lesepfade anfasste (s. council/herkunft.py). Diese
        # zwei sind neu und haben keinen Altbestand; sie hier trotzdem
        # anzulegen hieße, dieselbe Angabe von Anfang an doppelt zu führen —
        # mit der bekannten Folge, dass eine der beiden irgendwann veraltet.
        # Die Spalte selbst rüstet `_migrate_herkunft` über
        # `herkunft.HERKUNFT_TABELLEN` nach; sie steht hier nur mit, damit
        # eine frische Datenbank sie sofort trägt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_group_items ("
            "year INTEGER NOT NULL, "
            "nr INTEGER NOT NULL, "                # Postennummer DIESES Jahrgangs
            "label TEXT NOT NULL, "
            "role TEXT, "                         # ertraege_summe, zinsaufwand, …
            "amount REAL NOT NULL, prior_year REAL, "  # Euro; vorjahr NULL = Spalte unlesbar
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, nr))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_konzern_posten_rolle "
            "ON council_group_items(role, year)")
        # `council_group_entities` = wer den Konzern ausmacht: dieselben
        # Summen, aufgeteilt auf Kernverwaltung, Eigenbetriebe und
        # Beteiligungen, plus die Zeile „Konsolidierung" (die Verrechnung der
        # Geschäfte untereinander).
        #
        # Die Beträge stehen in **Tausend Euro**, so wie der Bericht sie
        # ausweist, und die Spalten heißen auch so. Sie in Euro umzurechnen
        # hieße, sechs Stellen Genauigkeit zu behaupten, die das Dokument
        # nicht hergibt — und niemand sähe es der Spalte `amount` später an.
        #
        # Eigene `herkunft_id` je Zeile, nicht je Jahrgang: Diese Aufstellung
        # steht in einem anderen Abschnitt des Berichts als die Posten (4.1.1
        # statt 3.2) und ist durch andere Proben gedeckt. Und sobald die
        # Beteiligungen einmal aus ihren Einzelabschlüssen kommen, sitzen in
        # derselben Tabelle Zeilen aus verschiedenen Dokumenten — genau der
        # Fall, für den die Herkunft eine eigene Tabelle ist.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_group_entities ("
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "                 # 'revenues' | 'expenses'
            "entity_key TEXT NOT NULL, "          # stadt, klinikum, egh, konsolidierung, …
            "entity TEXT NOT NULL, "
            "amount_keur REAL NOT NULL, prior_year_keur REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, kind, entity_key))"
        )
        # Der Beteiligungsbericht nach § 151 NKomVG
        # (council/beteiligungsbericht.py). Drei Tabellen, weil hier drei
        # verschiedene Dinge zusammenkommen — und weil sie verschieden oft
        # ihren Wert wechseln.
        #
        # ACHTUNG, NAMENSFALLE: `council_beteiligungen` ist etwas ganz
        # anderes. Dort stehen die **Bürgerbeteiligungen** an Bauleitplänen
        # (oldenburg.planungsbeteiligung.de, s. `council/beteiligung.py`).
        # Gesellschaften heißen hier deshalb Gesellschaften.
        #
        # `council_companies` = die Stammdaten je Bericht: Wie die
        # Gesellschaft heißt, an welcher Stelle sie im Bericht steht, auf
        # welcher Seite. Je Berichtsjahr eine Zeile, weil sich alles davon
        # ändern kann — die Gliederungsnummer tut es regelmäßig, sobald eine
        # Beteiligung dazukommt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_companies ("
            "report_year INTEGER NOT NULL, "      # Berichtsjahr des Dokuments
            "company TEXT NOT NULL, "         # stabiler Schlüssel: egh, vwg, …
            "name TEXT NOT NULL, "
            "classification TEXT NOT NULL, "           # '2.4.9'
            "page INTEGER, "                      # gedruckte Seite im Bericht
            "consolidated_key TEXT, "                   # → council_group_entities
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, company))"
        )
        # `council_company_texts` = die beschreibenden Abschnitte.
        # Langformat, nicht fünf Spalten: Der Bericht führt acht Abschnitte,
        # gespeichert werden fünf, und welche das sind, ist eine Entscheidung
        # über den Nutzen — keine über das Schema. Ein sechster kostet so
        # keine Migration.
        #
        # Diese Zeilen tragen `herkunft.UNGEPRUEFT`, und das ist die ehrliche
        # Angabe: Fließtext lässt sich gegen nichts rechnen. Sie stehen
        # trotzdem mit Dokument, Fundstelle und Seite da.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_company_texts ("
            "report_year INTEGER NOT NULL, "
            "company TEXT NOT NULL, "
            "section TEXT NOT NULL, "            # business_purpose, supervisory_bodies, …
            "text TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, company, section))"
        )
        # `council_company_people` = wer in den Aufsichtsorganen sitzt.
        #
        # Das steht auch im Abschnittstext, und trotzdem ist es keine
        # Doppelung: Der Text ist der zweispaltige PDF-Extrakt — erst fünfzehn
        # Namen, dann fünfzehn Ämter —, und was da nebeneinander gehört,
        # entscheidet eine Rechenprobe (`beteiligungsbericht.aufsichtsorgane`).
        # Hier steht das Ergebnis dieser Probe; der Text bleibt daneben stehen,
        # damit ein Mensch nachlesen kann.
        #
        # `roles_assignable` ist die Probe selbst und steht bewusst an
        # JEDER Zeile, obwohl sie je Gesellschaft gilt: Wer die Personen liest,
        # muss ohne zweite Abfrage wissen, ob das Amt daneben gedeckt ist.
        # Ist sie 0, sind ALLE `position` dieser Gesellschaft NULL — nicht
        # „die meisten". Ein falsch zugeordnetes Amt wäre eine Falschaussage
        # über eine namentlich genannte Person.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_company_people ("
            "report_year INTEGER NOT NULL, "
            "company TEXT NOT NULL, "
            "sort_order INTEGER NOT NULL, "   # Position im Bericht
            "committee TEXT NOT NULL, "          # Betriebsausschuss, Aufsichtsrat, …
            "name TEXT NOT NULL, "
            "position TEXT, "                  # NULL, wenn die Probe riss
            "chair_role TEXT, "                # chair | deputy | NULL
            "note TEXT, "                   # „bis 30. Juni 2022"
            "roles_assignable INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, company, sort_order))"
        )
        # `council_company_owners` = wem die Gesellschaft gehört.
        #
        # Ohne die Summenzeile: „Stammkapital 22.000.000,00 100,0" sieht im
        # Extrakt aus wie ein Gesellschafter und ist die Probe, gegen die die
        # Anteile laufen. Stünde sie hier, hielte die Stadt an ihrem eigenen
        # Eigenbetrieb die Hälfte und ein „Stammkapital" die andere.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_company_owners ("
            "report_year INTEGER NOT NULL, "
            "company TEXT NOT NULL, "
            "sort_order INTEGER NOT NULL, "
            "name TEXT NOT NULL, "
            "amount_eur REAL, "                # NULL, wo der Bericht nur % nennt
            "share_pct REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, company, sort_order))"
        )
        # `council_company_indicators` = die Zeitreihe.
        #
        # SCHLÜSSEL IST DAS BEZUGSJAHR DER KENNZAHL, NICHT DER BERICHT. Jeder
        # Bericht führt vier bis fünf Jahre; dasselbe Jahr steht also in bis
        # zu drei Berichten. Als (Bericht, Jahr) abgelegt läge es dreimal da
        # und jede Auswertung müsste sich entscheiden — mit dem Bezugsjahr als
        # Schlüssel ist es eine Zeile, und die Frage „stimmen die Berichte
        # überein?" ist beim Schreiben beantwortet statt beim Lesen.
        #
        # `n_reports` hält fest, wie viele Berichte den Wert übereinstimmend
        # nennen. Das ist keine Statistik, sondern das Ergebnis der
        # Überlappungsprobe: 1 heißt „steht bisher nur in einem Bericht" und
        # damit „durch eine Dokumentprobe gedeckt, nicht durch die
        # Überlappung". Die Seite sagt es so auch.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_company_indicators ("
            "company TEXT NOT NULL, "
            "indicator TEXT NOT NULL, "             # jahresergebnis|bilanzsumme|…
            "year INTEGER NOT NULL, "              # Bezugsjahr der Kennzahl
            "value REAL NOT NULL, "
            "unit TEXT NOT NULL, "              # eur | prozent
            "report_year INTEGER NOT NULL, "      # jüngster Bericht mit diesem Wert
            "n_reports INTEGER NOT NULL, "          # wie viele Berichte ihn nennen
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (company, indicator, year))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gesellschaft_kennzahlen_jahr "
            "ON council_company_indicators(year, indicator)")
        # Städtevergleich aus der amtlichen Statistik des Landesamts für
        # Statistik Niedersachsen (council/staedtevergleich.py). Langformat —
        # eine Zeile je Stadt, Jahr und Kennzahl.
        #
        # WARUM LANGFORMAT: Die beiden Quellen haben verschiedene Zuschnitte.
        # Der Finanzausgleich liefert je Stadt zwei Zahlen für EIN Jahr, der
        # Realsteuervergleich Hebesätze für das Berichtsjahr UND eine
        # Steuereinnahmekraft-Reihe über drei Jahre. Als Spaltensatz bräuchte
        # das entweder zwei Tabellen oder eine mit lauter leeren Feldern; so
        # ist es eine, und eine neunte Kennzahl kostet keine Migration.
        #
        # `year` ist das Bezugsjahr DER KENNZAHL, nicht der Datei: Der
        # Realsteuervergleich 2025 führt auch 2023 und 2024. Alles unter dem
        # Dateijahr abzulegen machte aus drei Jahren eines.
        #
        # UND DIE WICHTIGE ABGRENZUNG ZU `council_tax_capacity`: Beide Tabellen
        # führen Steuerkraftmesszahlen, und sie sind NICHT dasselbe. Unser
        # Open-Data-Datensatz 1106 trägt dieselben Beträge wie das LSN, aber
        # unter einer um ein Jahr verschobenen Beschriftung (drei Wertepaare
        # geprüft, zwei unabhängige Wege). Welche stimmt, ist offen. Deshalb
        # eine eigene Tabelle mit der Jahresangabe des LSN — und deshalb darf
        # kein Lesepfad die beiden zu einer Reihe mischen, solange das nicht
        # geklärt ist. Er plottete zwei Jahre gegeneinander, die nicht dasselbe
        # meinen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_city_comparison ("
            "series TEXT NOT NULL, "                # 'steuerkraft' | 'realsteuern'
            "year INTEGER NOT NULL, "              # Bezugsjahr der Kennzahl (LSN)
            "key TEXT NOT NULL, "           # amtliche Schlüsselnr., 6-stellig
            "city TEXT NOT NULL, "
            "indicator TEXT NOT NULL, "
            "value REAL NOT NULL, "
            "unit TEXT NOT NULL, "              # teur | anzahl | prozent | eur_je_ew
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (series, year, key, indicator))"
        )
        # Gewerbesteuerstatistik des LSN (council/gewerbesteuerstatistik.py) —
        # wie viele Betriebe die Gewerbesteuer überhaupt aufbringen.
        #
        # WARUM SPALTEN UND NICHT LANGFORMAT wie beim Städtevergleich daneben:
        # Diese neun Zahlen sind EINE Aussage über eine Stadt in einem Jahr,
        # und sie hängen rechnerisch aneinander (reine Festsetzungen +
        # Zerlegungen = insgesamt, dreimal). Im Langformat stünde jede Zahl in
        # einer eigenen Zeile, und die Probe, die sie zusammenhält, wäre beim
        # Lesen nicht mehr nachvollziehbar, ohne neun Zeilen wieder
        # einzusammeln. Der Städtevergleich hat den umgekehrten Zuschnitt: dort
        # kommen die Kennzahlen aus zwei verschieden gebauten Quellen.
        #
        # `tax_base_eur` und die beiden Teilbeträge sind NULL-bar, die
        # Anzahlen nicht. Das ist der Fall der GEHEIMHALTUNG: Wo ein einzelner
        # Zahler die Gemeinde dominiert, druckt das Landesamt statt des Betrags
        # ein „g" (2021 bei Salzgitter und Wolfsburg) — die Anzahlen stehen
        # trotzdem da. NULL heißt hier also „gesperrt", nicht „null Euro", und
        # `confidential` sagt es noch einmal ausdrücklich, damit eine Anzeige den
        # Unterschied nicht raten muss. Wo eine Stadt vollständig gesperrt ist
        # (Jahrgang 2020), kommt sie gar nicht erst herein.
        #
        # ABGRENZUNG, OHNE DIE DIE ZAHLEN IRREFÜHREN: Der Steuermessbetrag ist
        # die VERANLAGUNG des Erhebungsjahres, nicht das Aufkommen des
        # Kalenderjahres in `council_taxes`. Messbetrag mal Hebesatz lag in
        # den drei prüfbaren Jahren zwischen 13 % unter und 27 % über dem
        # kassenmäßigen Ist. Kein Lesepfad darf die beiden zu einer Reihe
        # verbinden (ausführlich im Modulkopf).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_trade_tax_statistics ("
            "year INTEGER NOT NULL, "              # Erhebungsjahr der Veranlagung
            "key TEXT NOT NULL, "           # amtliche Schlüsselnr., 6-stellig
            "city TEXT NOT NULL, "
            "cases INTEGER NOT NULL, "            # Betriebe und Betriebsstätten
            "cases_positive INTEGER NOT NULL, "    # davon mit positivem Messbetrag
            "tax_base_eur INTEGER, "             # NULL = Geheimhaltung
            "assessments INTEGER, "              # reine Festsetzungen
            "assessments_positive INTEGER, "
            "assessment_tax_base_eur INTEGER, "
            "apportionments INTEGER, "                # zerlegte Betriebsstätten
            "apportionments_positive INTEGER, "
            "apportioned_assessment_eur INTEGER, "
            "rate REAL, "                      # nachrichtlich, aus Blatt 6.2
            "confidential INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, key))"
        )
        # Schuldenstand je Jahr (Tabelle 1108 des Statistischen Jahrbuchs,
        # seit 1995). Beträge in Euro; die Quelle rechnet in Tausend Euro und
        # ist damit auf Tausend genau — mehr behauptet auch diese Tabelle nicht.
        #
        # DIE ABGRENZUNG STEHT IM MODULKOPF VON `council/schulden.py` und ist
        # die wichtigste Angabe der ganzen Schicht: Gezählt wird die Stadt als
        # RECHTSTRÄGER, also Kernhaushalt UND Eigenbetriebe — nicht der Konzern
        # mit seinen rechtlich selbstständigen Beteiligungen. Beide Zahlen
        # heißen „die Schulden der Stadt" und unterscheiden sich um ein
        # Vielfaches; kein Lesepfad darf sie zu einer Reihe mischen.
        #
        # Die vier Artenspalten sind NULL-bar, `total` nicht. Das ist kein
        # Schönheitsfehler, sondern der Fall 2022: Dort ergeben die Arten im
        # Dokument selbst 1,078 Mio. € mehr als die Summe daneben. Die Summe
        # trägt die unabhängige Pro-Kopf-Gegenprobe, die Aufteilung trägt
        # nichts — also kommt die Summe herein und die Aufteilung nicht.
        # `breakdown_rejected` hält fest, wie groß die Lücke war, damit die
        # Seite den leeren Balken erklären kann statt ihn zu verschweigen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_debt ("
            "year INTEGER PRIMARY KEY, "
            "credit_market REAL, "               # Schulden aus Kreditmarktmitteln
            "special_funds REAL, "              # aus öffentlichen Sondermitteln
            "public_authorities REAL, "    # bei Gebietskörperschaften
            "municipal_enterprises REAL, "             # Eigenbetriebe + innere Darlehen
            "total REAL NOT NULL, "        # die ausgewiesene Summe
            "per_capita REAL, "              # Euro je Einwohner*in
            "breakdown_rejected REAL, "      # Lücke der Summenprobe, sonst NULL
            "revised INTEGER NOT NULL DEFAULT 0, "   # „r" der Quelle
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Was die Stadt in einem Jahr WIRKLICH investiert hat — Tabellen 1107
        # (2003–2009) und 1107-1 (2010–2025) des Statistischen Jahrbuchs.
        # Beträge in Euro; die Quelle rechnet in Tausend Euro.
        #
        # NICHT ZU VERWECHSELN mit `council_investments`: Das sind die
        # PLANZAHLEN aus dem Finanzhaushalt des Haushaltsplans, gegliedert nach
        # Teilhaushalten. Hier stehen die Rechnungsergebnisse, gegliedert nach
        # Auszahlungsarten. Die beiden Summen sind verschieden abgegrenzt und
        # dürfen nicht voneinander abgezogen werden — die Begründung steht im
        # Kopf von `council/investitionen_ist.py`.
        #
        # `accounting_system` ist der Grund für die eigene Spalte statt einer stillen
        # Annahme: Zum 01.01.2010 stellte die Stadt von kameraler auf doppische
        # Buchführung um, und das Dokument trennt seine beiden Tabellen genau
        # dort — mit eigener Fußnote. Eine Kurve, die über 2009/2010 hinweg
        # durchzieht, behauptet eine Vergleichbarkeit, die die Quelle bestreitet.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investments_actual ("
            "year INTEGER PRIMARY KEY, "
            "accounting_system TEXT NOT NULL, "        # kameral | doppik
            "total REAL NOT NULL, "        # die ausgewiesene Summenspalte
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die Aufteilung nach Auszahlungsart — eigene Tabelle, weil die Zahl
        # der Arten vom Regelwerk abhängt (kameral vier, doppisch sechs) und
        # eine gemeinsame Spalte für „bewegliches Vermögen" zwei Begriffe aus
        # zwei Rechnungswesen unter einen Namen zwänge.
        #
        # `title` reist mit der Zeile, statt im Frontend zu stehen: Die
        # Legende soll nicht in zwei Sprachen existieren, und die Überschrift
        # ist eine Angabe der Quelle wie der Betrag selbst.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investments_actual_kinds ("
            "year INTEGER NOT NULL, "
            "field TEXT NOT NULL, "             # Schlüssel aus investitionen_ist.SPALTEN
            "title TEXT NOT NULL, "            # die Überschrift der Quelle
            "sort_order INTEGER NOT NULL, "   # Spaltenfolge der Tabelle
            "amount REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, field))"
        )
        # Die Jahrgänge, die es NICHT in den Bestand geschafft haben — mit
        # dem, was an ihnen gemessen wurde.
        #
        # Dieselbe Rolle wie `breakdown_rejected` in `council_debt`, nur
        # eine Tabelle weiter: Dort trägt die gerettete Zeile ihre Lücke in
        # einer eigenen Spalte, hier gibt es keine Zeile, die sie tragen
        # könnte (die Probe reißt, eine zweite gibt es nicht, also fällt der
        # ganze Jahrgang — s. `council/investitionen_ist.py`).
        #
        # `difference` ist der Grund für diese Tabelle: Ohne sie stünde die
        # gemessene Lücke nur als Fließtext im `reason` und wäre für die Seite
        # nicht mehr zu haben, ohne einen Satz zurückzuparsen. `NULL`, wo
        # nichts zu messen war (eine Zeile, die sich nicht zerlegen ließ) —
        # eine Null behauptete dort „es passte genau".
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_investments_actual_rejected ("
            "year INTEGER PRIMARY KEY, "
            "accounting_system TEXT NOT NULL, "        # kameral | doppik
            "reason TEXT NOT NULL, "            # der Satz aus dem Parser
            "difference REAL, "                 # Arten minus Summe, in Euro
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die lange Ausgabenreihe — Datensatz 1102, ein Betrag je Jahr seit
        # 1972 (council/ausgabenreihe.py). Beträge in Euro; die Quelle rechnet
        # in Tausend Euro.
        #
        # `accounting_system` trennt die beiden Größen an der Naht 2009/2010, genau
        # wie in `council_investments_actual` und aus derselben Fußnote
        # derselben Quelle: Links steht das Anordnungssoll des
        # Verwaltungshaushalts, rechts die ordentlichen Aufwendungen der
        # Gesamtergebnisrechnung.
        #
        # WAS HIER BEWUSST NICHT STEHT: die Einwohnerzahl und der Betrag je
        # Einwohner*in, obwohl beide Quellen sie führen und die Pro-Kopf-Probe
        # sie braucht. Sie bleiben im Parser. Der Grund ist keine Sparsamkeit,
        # sondern eine Sperre: Läge der Divisor in dieser Tabelle, wäre die
        # naheliegendste Grafik der Seite „Ausgaben pro Kopf seit 1972" — und
        # die wäre falsch, weil die Einwohnerreihe zwei Zensus-Brüche hat
        # (2011 und 2022, s. die Fußnote auf /haushalt/schulden). Was die API
        # nicht liefern kann, kann das Frontend nicht versehentlich zeichnen.
        #
        # `conflict_amount` ist der Betrag, den die ANDERE Quelle für dieses
        # Jahr nennt — gefüllt nur, wo PDF und CSV sich widersprechen (2021).
        # Dieselbe Rolle wie `difference` in
        # `council_investments_actual_rejected`: Er macht aus „hier gab es
        # einen Widerspruch" eine Zahl, die die Seite anschreiben kann.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_expense_series ("
            "year INTEGER PRIMARY KEY, "
            "accounting_system TEXT NOT NULL, "        # kameral | doppik
            "amount REAL NOT NULL, "           # in Euro
            "source TEXT NOT NULL, "           # pdf | csv — wer den Wert lieferte
            "probes TEXT NOT NULL, "           # bestandene Proben, kommagetrennt
            "conflict_amount REAL, "           # was die andere Quelle sagt
            "conflict_source TEXT, "
            "revised INTEGER NOT NULL DEFAULT 0, "   # „r" der Quelle
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Der Bürgschaftsbestand aus dem Jahresabschluss (council/
        # buergschaften.py) — wofür die Stadt geradesteht, nicht was sie
        # schuldet. 2024: 220,3 Mio. € gegen 43,7 Mio. € eigene Geldschulden.
        #
        # `exact` und `out_next_year` sind keine Technik, sondern Angaben über
        # die Zahl: Die Quelle nennt den Betrag 2019/2020 auf den Cent und ab
        # 2022 nur noch gerundet („rd. 220,3 Millionen"), und 2021 nennt sie
        # ihn überhaupt nicht — dieser Wert steht allein im Dokument des
        # Folgejahres. Ohne beide Spalten sähen sechs verschieden belegte
        # Jahrgänge in der Anzeige gleich aus.
        # Die Gebührenbedarfsberechnung (`council/fees.py`) — die
        # Rechnung, aus der die Abfall- und Straßenreinigungsgebühren
        # entstehen. Von allen Zahlen des Haushalts landet keine so direkt im
        # Portemonnaie.
        #
        # `fee` und `reference_quantity` sind NULLBAR, und das ist eine Aussage:
        # Die Abfallsammlung erhebt eine Grundgebühr UND eine Gebühr je Liter
        # Behältervolumen, dort gibt es keine einzelne Division. Eine 0 wäre
        # dort eine Behauptung, und eine erfundene Division wäre schlimmer als
        # keine. Die Kaskade ist trotzdem geprüft — welche Proben liefen,
        # steht je Zeile in `probes`.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_fees ("
            "year INTEGER NOT NULL, "
            "area TEXT NOT NULL, "          # Kürzel aus gebuehren.BEREICHE
            "area_name TEXT NOT NULL, "
            "cost_calculation REAL NOT NULL, "
            "deductions REAL NOT NULL, "          # negativ
            "costs_to_cover REAL NOT NULL, "
            "reference_quantity REAL, "
            "reference_unit TEXT, "
            "fee REAL, "                   # die errechnete, 3 Nachkommast.
            "fee_proposed REAL, "        # die gerundete an den Rat
            "template_number TEXT, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, area))"
        )
        # Die zwölf konkreten Verwaltungsvorschläge aus Anlage 4. Eine eigene
        # Tabelle ist nötig, weil die Abfallsammlung nicht EINEN Satz hat:
        # Grundgebühr, Litergebühr, Karten und Anlieferungsmengen dürfen nicht
        # in eine erfundene Durchschnittsgebühr gepresst werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_fee_rates ("
            "year INTEGER NOT NULL, "
            "key TEXT NOT NULL, "
            "area TEXT NOT NULL, "
            "label TEXT NOT NULL, "
            "amount REAL NOT NULL, "
            "unit TEXT NOT NULL, "
            "prior_year REAL, "
            "change_pct REAL, "
            "template_number TEXT, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, key))"
        )

        # Die Haushaltssatzung — der Rahmen, den der Haushaltsplan bekommt
        # (`council/budget_bylaw.py`). Drei Größen standen bis 08/2026
        # nirgends im Bereich: die Kreditermächtigung (§ 2), der Höchstbetrag
        # für Liquiditätskredite (§ 4) und der Finanzhaushalt als Ganzes
        # (§ 1.2) — bisher wurden daraus nur die Investitionen gelesen.
        #
        # `version` IST KEIN TECHNIKFELD. Alle Satzungen im
        # Ratsinformationssystem sind **Verwaltungsentwürfe**; die beschlossene
        # Fassung erscheint im Amtsblatt. Eine Anzeige, die das wegließe,
        # machte aus einem Vorschlag der Verwaltung einen Ratsbeschluss.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_bylaw ("
            "year INTEGER NOT NULL, "
            "supplement INTEGER NOT NULL DEFAULT 0, "   # 0 = die Satzung selbst
            "version TEXT NOT NULL, "                 # draft | unknown
            "ordinary_revenues REAL NOT NULL, "
            "ordinary_expenses REAL NOT NULL, "
            "extraordinary_revenues REAL NOT NULL, "
            "extraordinary_expenses REAL NOT NULL, "
            "in_operating REAL NOT NULL, out_operating REAL NOT NULL, "
            "in_capital REAL NOT NULL, out_capital REAL NOT NULL, "
            "in_financing REAL NOT NULL, out_financing REAL NOT NULL, "
            # Die beiden „Nachrichtlich"-Zeilen. Sie stehen NICHT nur als
            # Bequemlichkeit hier: Sie sind die Probe, an der die sechs Zeilen
            # darüber hängen, und wer sie mitspeichert, kann sie nachrechnen,
            # ohne das PDF noch einmal zu holen.
            "in_total REAL NOT NULL, out_total REAL NOT NULL, "
            # Nullbar, weil ein fehlender Paragraph etwas anderes ist als eine
            # Null: `investment_loans = 0` heißt „nicht veranschlagt" (so
            # steht es dort in jedem gelesenen Jahrgang), NULL hieße „die
            # Satzung sagt dazu nichts".
            "investment_loans REAL, "
            "commitment_authorizations REAL, "
            "liquidity_loans REAL, "
            # Ab dem Jahrgang 2025 nennt § 5 nur noch die Gewerbesteuer und
            # verweist für die Grundsteuer auf eine eigene Satzung.
            "property_tax_a_rate INTEGER, "
            "property_tax_b_rate INTEGER, "
            "trade_tax_rate INTEGER, "
            "session_date TEXT, "                       # NULL bei „xx.xx.JJJJ"
            "template_number TEXT, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, supplement))"
        )

        # Der Haushaltsvollzug (`council/budget_execution.py`) — die
        # vierteljährlichen Finanz- und Leistungsberichte an den Ausschuss für
        # Finanzen und Beteiligungen. Die Schicht, die die Lücke zwischen Plan
        # (kommendes Jahr) und Jahresabschluss (vorvorletztes Jahr) schließt.
        #
        # `sub_budget = 0` IST KEINE TEILHAUSHALTS-NUMMER, sondern die
        # gedruckte Summenzeile. Ein NULL wäre ehrlicher, taugt in SQLite aber
        # nicht als Teil eines Primärschlüssels — dort gelten zwei NULL als
        # verschieden, und derselbe Bericht ließe sich beliebig oft einfügen.
        # `is_total` sagt dasselbe noch einmal für Abfragen, die die Null nicht
        # kennen.
        #
        # `plan_basis` IST KEIN TECHNIKFELD. Bis 2020 rechnet die Ansatz-Spalte
        # des Ergebnisses die Ermächtigungsübertragungen aus dem Vorjahr mit
        # ein, ab 2021 nicht mehr. Eine Zeitreihe, die das nicht mitführt,
        # vergleicht über den Schnitt hinweg zwei verschiedene Größen — für
        # 2018 einen Überschuss von 5,4 statt der 8,8 Millionen des Plans.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_execution ("
            "budget_year INTEGER NOT NULL, "
            "as_of TEXT NOT NULL, "            # Stichtag, ISO (2025-06-30)
            "budget TEXT NOT NULL, "           # result | cash
            "sub_budget INTEGER NOT NULL, "    # 1..13; 0 = Summenzeile
            "kind TEXT NOT NULL, "             # revenue/expense/result bzw.
            "label TEXT NOT NULL, "            #   inflow/outflow/result
            "budgeted REAL, "                  # Ansatz
            "forecast REAL, "                  # Prognose zum 31.12.
            "deviation REAL, "                 # gedruckte Abweichung
            # „nachrichtlich: Ermächtigungsübertragungen" — nur an der
            # Aufwands- bzw. Auszahlungszeile, denn genau dazu ermächtigen sie
            # (§ 20 KomHKVO). Anderswo NULL statt 0: Der Bericht sagt dort
            # nichts, und eine erfundene Null sähe aus wie eine Auskunft.
            "carryover REAL, "
            "plan_basis TEXT NOT NULL, "       # budget | budget_plus_carryover
            "is_total INTEGER NOT NULL DEFAULT 0, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, "
            "fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, as_of, budget, sub_budget, kind))"
        )

        # Die Änderungslisten zum Haushalt (council/aenderungslisten.py) —
        # was am Verwaltungsentwurf im Verfahren noch geändert wurde, Position
        # für Position. Je Zeile EIN Planjahr: Dieselbe Maßnahme steht im
        # Dokument je betroffenem Jahr noch einmal, mit eigenem Betrag.
        #
        # `sub_budget` ist NULLBAR, und das ist eine Aussage: Der 2019er-Jahrgang
        # führt pauschale Minderausgaben über „alle" Teilhaushalte.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_amendments ("
            "budget_year INTEGER NOT NULL, "      # Haushaltsjahrgang der Liste
            "list_key TEXT NOT NULL, "         # administration_1..3 | fc_decided
            "year INTEGER NOT NULL, "          # Planjahr der Position
            "seq INTEGER NOT NULL, "
            "sub_budget INTEGER, "                    # NULL = „alle" (pauschal)
            "page_draft INTEGER, "
            "product TEXT, "
            "label TEXT NOT NULL, "
            "revenue REAL, "                    # Euro; NULL = kein Betrag in
            "expense REAL, "                   # dieser Spalte (Vermerke: beide)
            "explanation TEXT, "              # die Erläuterungs-Spalte des PDFs
            # WER die Position vorgeschlagen hat — „Verw. I“, „SPD/ BÜNDNIS
            # 90/DIE GRÜNEN“. NULL, wo das Dokument die Spalte „Vorschlag
            # von“ nicht führt; das sind 17 der 18 EHH-Dokumente.
            "author TEXT, "
            "document_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, list_key, year, seq))"
        )
        # Erläuterungs- (26.08.2026) und Urheber-Spalte (30.08.2026) kamen
        # nach dem ersten Ingest dazu — additiv, gefüllt werden sie vom
        # nächsten Ingest-Lauf (der je (jahrgang, liste) ohnehin löscht und
        # neu schreibt).
        aend_cols = {r[1] for r in self._conn.execute(
            "PRAGMA table_info(council_budget_amendments)").fetchall()}
        for spalte in ("explanation", "author"):
            if aend_cols and spalte not in aend_cols:
                self._conn.execute(
                    f"ALTER TABLE council_budget_amendments ADD COLUMN {spalte} TEXT")
        # Die „Zusammenstellung der Veränderungen" derselben Dokumente — der
        # Rahmen, an dem jede Positionsliste bewiesen wurde. Sie trägt auch,
        # was NUR hier steht: die politisch beschlossene Änderung mit ihrem
        # Urheber-Label („SPD/CDU/FDP  0 / −218.299") in den AFB-Dateien.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_amendments_totals ("
            "budget_year INTEGER NOT NULL, "
            "list_key TEXT NOT NULL, "         # das DOKUMENT, aus dem sie stammt
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "             # draft | list | final_total
            "label TEXT NOT NULL, "            # „Änderungsliste Verw. I", „SPD/CDU/FDP" …
            "revenues REAL NOT NULL, "
            "expenses REAL NOT NULL, "
            "balance REAL NOT NULL, "
            # 1 = diese Zeile summiert die Positionen ihres Dokuments („die
            # eigene"); bei kumulierten Dokumenten trägt keine Zeile die 1 —
            # dort summieren die Positionen auf ALLE Listen zusammen.
            "own INTEGER NOT NULL DEFAULT 0, "
            "document_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, list_key, year, kind, label))"
        )

        # Dieselben Änderungslisten, aber für den FINANZhaushalt
        # (council/aenderungslisten_fhh.py). EIGENE Tabellen statt einer
        # Spalte „haushalt“ in den beiden darüber: Die Zeilen haben eine
        # andere Form — fünf Betragsspalten statt zwei, dazu der
        # Investitionscode. In einer gemeinsamen Tabelle wären beide Seiten
        # zur Hälfte NULL, und jede Abfrage müsste erst filtern, welche
        # Spalten sie überhaupt lesen darf.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_amendments_cash ("
            "budget_year INTEGER NOT NULL, "
            "list_key TEXT NOT NULL, "         # administration_1..3 | fc_decided
            "year INTEGER NOT NULL, "          # Planjahr der Position
            "seq INTEGER NOT NULL, "
            "sub_budget INTEGER, "
            # TEXT, nicht INTEGER: Die Spalte „Seite im HH-Entwurf“ trägt auch
            # „neu“ — dann steht die Position im Entwurf noch gar nicht.
            "page_draft TEXT, "
            # Der Investitionscode des Programms („I10.089904.500“). Er ist
            # der Anschluss an council_investment_measures: Über ihn lässt
            # sich sagen, WELCHES Vorhaben im Verfahren geändert wurde.
            "product TEXT, "
            "label TEXT NOT NULL, "
            # Die fünf Betragsspalten. NULL = Zelle leer (reine
            # Haushaltsvermerke tragen gar keine), 0 = Gedankenstrich, also
            # eine ausdrückliche Null.
            "planned_draft REAL, "
            "inflow REAL, "
            "outflow REAL, "
            "commitment_authorizations REAL, "                        # Verpflichtungsermächtigungen
            "planned_new REAL, "
            "explanation TEXT, "
            "author TEXT, "
            "document_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, list_key, year, seq))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_budget_amendments_cash_totals ("
            "budget_year INTEGER NOT NULL, "
            "list_key TEXT NOT NULL, "
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "             # draft | list | final_total
            "label TEXT NOT NULL, "
            "inflows REAL NOT NULL, "
            "outflows REAL NOT NULL, "
            "balance REAL NOT NULL, "
            # NULL, wo das Dokument keine VE-Spalte führt (die
            # Beschluss-Dateien). Sie zählt NICHT in den Saldo.
            "commitment_authorizations REAL, "
            "own INTEGER NOT NULL DEFAULT 0, "
            "document_id INTEGER NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (budget_year, list_key, year, kind, label))"
        )

        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_business_plans ("
            "enterprise TEXT NOT NULL, "          # Kürzel aus wirtschaftsplan.BETRIEBE
            "year INTEGER NOT NULL, "          # Haushaltsjahr, nicht Jahr der Vorlage
            "enterprise_name TEXT NOT NULL, "
            "template_number TEXT NOT NULL, "
            # Nullbar seit 20.08.2026: Nicht jede Quelle gibt das volle Tripel.
            # Beschlusstext (EGH) und Erfolgsplan-Tabelle (AWB) liefern Erträge,
            # Aufwendungen UND Ergebnis; bei Bäderbetriebsgesellschaft, Stadion
            # und Bäderbetrieb nennt nur die **Kernzahl** eine geprüfte Zahl —
            # das Jahresergebnis, das der Rat beschließt. Eine 0 dort wäre eine
            # Behauptung, ein NULL ist die Auskunft „diese Quelle sagt es nicht".
            "revenues REAL, "                  # Erfolgsplan, in Euro
            "expenses REAL, "
            "taxes REAL, "                   # bis 2020 keine eigene Zeile → 0
            "result REAL NOT NULL, "         # als einziges immer da
            "capital_plan REAL, "            # Ein- = Auszahlungen, eine Zahl
            # NICHT dasselbe wie `capital_plan`, und die Verwechslung wäre
            # teuer: Der Vermögensplan ist die Gesamtsumme (Ein- = Auszahlungen),
            # `investitionen` ein POSTEN darin — daneben stehen dort etwa
            # Tilgungsleistungen. Der Beschlusstext des Bäderbetriebs nennt nur
            # diesen Posten („Der Vermögensplan weist Investitionen in Höhe von
            # 10.752.000 Euro aus"), der des EGH nur die Summe. Zwei Spalten,
            # weil es zwei Angaben sind.
            "investments REAL, "
            "commitments REAL, "           # Verpflichtungsermächtigungen
            "draft_date TEXT, "               # Stand des Verwaltungsentwurfs
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            # Ein Betrieb, ein Haushaltsjahr, ein Plan. Der Schlüssel ist
            # bewusst NICHT die Vorlagen-Nummer: Zu einem Jahr kann es eine
            # Anpassung geben (eine zweite Vorlage), und die soll den Stand
            # ersetzen und nicht danebenstehen.
            "PRIMARY KEY (enterprise, year))"
        )
        # Bestände, die vor dem 20.08.2026 angelegt wurden, tragen `revenues`
        # und `expenses` noch als NOT NULL. SQLite kann eine Spalte nicht
        # nachträglich nullbar machen — die Tabelle muss neu gebaut und der
        # Inhalt umkopiert werden. Erkannt wird der Altstand am Schema selbst
        # (`PRAGMA table_info`, Spalte `notnull`), nicht an einer Versionsnummer:
        # So läuft der Umbau genau einmal und auf jedem Bestand von allein.
        wp_spalten = self._conn.execute(
            "PRAGMA table_info(council_business_plans)").fetchall()
        # `investitionen` kam am 21.08.2026 dazu (Tim: „da stehen ja ganz, ganz
        # viele Zahlen drin" — die Karte des Bäderbetriebs zeigte nur eine Null).
        # Ein schlichtes ADD COLUMN reicht: Die Spalte ist nullbar, und NULL ist
        # hier die richtige Auskunft für jeden Bestand, der sie noch nicht kennt.
        if not any(s[1] == "investments" for s in wp_spalten):
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE council_business_plans ADD COLUMN investments REAL")
            wp_spalten = self._conn.execute(
                "PRAGMA table_info(council_business_plans)").fetchall()
        if any(s[1] == "revenues" and s[3] == 1 for s in wp_spalten):
            # `with self._conn` und nicht `self.transaktion()`: Diese Migration
            # läuft aus `_migrate()` heraus, also noch während `__init__` — der
            # Sammel-Zustand der Transaktionshilfe existiert da noch nicht.
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE council_business_plans RENAME TO _wp_alt")
                self._conn.execute(
                    "CREATE TABLE council_business_plans ("
                    "enterprise TEXT NOT NULL, year INTEGER NOT NULL, "
                    "enterprise_name TEXT NOT NULL, template_number TEXT NOT NULL, "
                    "revenues REAL, expenses REAL, taxes REAL, "
                    "result REAL NOT NULL, capital_plan REAL, "
                    "commitments REAL, draft_date TEXT, probes TEXT NOT NULL, "
                    "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
                    "PRIMARY KEY (enterprise, year))")
                # Spaltenweise benannt und nicht `SELECT *`: Eine später
                # ergänzte Spalte in der Altfassung würde die Reihenfolge
                # verschieben, und dann landeten Beträge in Textfeldern.
                self._conn.execute(
                    "INSERT INTO council_business_plans "
                    "(enterprise, year, enterprise_name, template_number, revenues, expenses, "
                    " taxes, result, capital_plan, commitments, draft_date, "
                    " probes, herkunft_id, fetched_at) "
                    "SELECT enterprise, year, enterprise_name, template_number, revenues, "
                    " expenses, taxes, result, capital_plan, commitments, "
                    " draft_date, probes, herkunft_id, fetched_at FROM _wp_alt")
                alt_n = self._conn.execute("SELECT COUNT(*) FROM _wp_alt").fetchone()[0]
                neu_n = self._conn.execute(
                    "SELECT COUNT(*) FROM council_business_plans").fetchone()[0]
                if alt_n != neu_n:  # pragma: no cover — Notbremse
                    raise RuntimeError(
                        f"Umbau von council_business_plans: {alt_n} Zeilen vorher, "
                        f"{neu_n} nachher — nichts wird verworfen")
                self._conn.execute("DROP TABLE _wp_alt")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_buergschaften ("
            "year INTEGER PRIMARY KEY, "
            "balance REAL NOT NULL, "          # in Euro
            "exact INTEGER NOT NULL, "         # 1 = auf den Cent belegt
            "out_next_year INTEGER NOT NULL, " # 1 = Anfangsbestand des Folgejahrs
            "source TEXT NOT NULL, "           # anhang | tabelle
            "reason TEXT, "                     # Begründung im Wortlaut der Stadt
            "single_amount REAL, "              # die im Grund genannte Zahl (2022)
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Der Anlagenspiegel (council/anlagenspiegel.py): was aus Investitionen
        # wird. Je Jahr und Vermögensposition eine Zeile mit dreizehn Werten —
        # Anschaffungswerte, Abschreibungen, Buchwerte.
        #
        # `spalten` steht bewusst DRIN, obwohl es eine Eigenschaft der Vorlage
        # ist und keine der Zahlen: Bis 2020 fehlt dem Abschreibungs-Block die
        # Umbuchungs-Spalte, und ohne diese Angabe sähe eine Zeile, deren
        # Abschreibungskette gar nicht schließen KANN, aus wie eine, die es
        # nicht tut. Die Anzeige darf den Unterschied benennen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_fixed_assets ("
            "year INTEGER NOT NULL, "
            "nr TEXT NOT NULL, "               # Gliederung: 1, 1.1, 2, 2.3 …
            "label TEXT NOT NULL, "
            "n_columns INTEGER NOT NULL, "     # 12 (bis 2020) oder 13
            "cost_opening REAL, additions REAL, disposals REAL, "
            "transfers REAL, cost_closing REAL, "
            "depreciation_opening REAL, depreciation REAL, depreciation_releases REAL, "
            "write_ups REAL, depreciation_transfers REAL, depreciation_closing REAL, "
            "book_value REAL, book_value_prior_year REAL, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, nr))"
        )
        # Die Untergliederung des Infrastrukturvermögens — Straßen, Brücken,
        # Gleisanlagen. Sie steht NICHT im Anlagenspiegel (der führt
        # Infrastruktur als eine Zeile), sondern in den Erläuterungen, und erst
        # ab 2022 in dieser Form. Eigene Tabelle statt einer Spalte: andere
        # Quelle im selben Dokument, andere Abdeckung.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_vermoegensgruppen ("
            "year INTEGER NOT NULL, "
            "group_name TEXT NOT NULL, "
            "book_value REAL NOT NULL, "
            "book_value_prior_year REAL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, group_name))"
        )
        # Die dreizehn Kennzahlen (council/kennzahlen.py): die Anlage, mit der
        # jeder Rechenschaftsbericht seinen Jahresabschluss zusammenfasst.
        #
        # `report_year` STEHT IM SCHLÜSSEL, und das ist der Kern der Tabelle:
        # Jeder Bericht druckt fünf Jahre, die Jahrgänge stehen also mehrfach
        # da — und nicht immer gleich. Die Steuerquote 2021 heißt im Bericht
        # 2021 45,90 %, im Bericht 2022 49,05 % und im Bericht 2023 wieder
        # 45,92 %. Ohne den Bericht im Schlüssel überschriebe der jüngere
        # Stand den älteren still, und die Korrektur — die eigentliche
        # Nachricht — wäre weg.
        #
        # `stellen` ist die Zahl der GEDRUCKTEN Nachkommastellen. 2019 steht
        # „48%", ab 2021 „53,15%"; ohne diese Angabe meldete der Vergleich
        # zweier Berichte reihenweise Abweichungen, die nur Rundung sind.
        #
        # `version` nummeriert den gedruckten Rechenweg. Wechselt er, darf
        # über die Stelle keine Linie laufen: Aus „Aufwand für Personal
        # (inklusive Versorgung)" wurde „Aufwendungen für aktives Personal",
        # und die Quote fällt dadurch um rund einen Prozentpunkt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_indicators ("
            "report_year INTEGER NOT NULL, "
            "indicator TEXT NOT NULL, "
            "year INTEGER NOT NULL, "
            "label TEXT NOT NULL, "
            "value REAL NOT NULL, "
            "unit TEXT NOT NULL, "          # prozent | eur | anzahl
            "decimals INTEGER NOT NULL, "
            "version INTEGER, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, indicator, year))"
        )
        # Die gedruckten Rechenwege — „Ermittlung: Sachvermögen * 100 /
        # Bilanzsumme". Eigene Tabelle, weil sie je Bericht einmal gelten und
        # nicht je Jahrgang; und weil sie den Text tragen, den die Seite
        # zitiert, statt einer Formel, die wir uns ausgedacht hätten.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_indicator_formulas ("
            "report_year INTEGER NOT NULL, "
            "indicator TEXT NOT NULL, "
            "version INTEGER NOT NULL, "
            "heading TEXT NOT NULL, "
            "formula TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (report_year, indicator))"
        )
        # Die dritte Schuldenzahl (council/integrierte_schulden.py): was der
        # ganze „Konzern Stadt" schuldet, anteilig nach Beteiligungshöhe —
        # 31.12.2024 rund 740,3 Mio. € gegen 294,9 Mio. € der Jahrbuch-Reihe.
        #
        # EIN STICHTAG JE AUSGABE, bewusst keine Zeitreihe: Welche Unternehmen
        # mitgerechnet werden, wechselt zwischen den Ausgaben, und die
        # Statistischen Ämter raten selbst davon ab, Jahrgänge zu vergleichen.
        # Die Tabelle kann trotzdem mehrere Jahre führen — sie darf nur nicht
        # als Kurve gezeichnet werden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_integrated_debt ("
            "year INTEGER PRIMARY KEY, "
            "ars TEXT NOT NULL, "              # Regionalschlüssel, nie der Name
            "population REAL, "
            "total REAL NOT NULL, per_capita REAL, "
            "core_budget REAL, extra_budgets REAL, other REAL, "
            # Die Aufteilung nach Beteiligungshöhe — daraus rechnet sich der
            # Anteil, der KEINE Haftung begründet (2024: 58 %).
            "extra_under_50 REAL, other_below_50 REAL, "
            # Die Veränderung, die der Band selbst ausweist. Angabe der Quelle,
            # nicht unsere Rechnung — deshalb gespeichert statt abgeleitet.
            "change REAL, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Nachbewilligungen nach § 117 NKomVG (council/nachbewilligungen.py).
        # Drei Tabellen, weil hier zwei verschiedene Quellen dieselbe Sache
        # beschreiben und niemals vermischt werden dürfen:
        #
        #   council_supplementary_approvals        — was der Rat beschloss (RIS)
        #   council_supplementary_years    — was der Rechenschaftsbericht
        #                                      fürs Jahr insgesamt ausweist
        #   council_supplementary_channels  — dessen vier Entscheidungswege
        #
        # Die Aufteilung der beiden letzten folgt `council_investments_actual`
        # und `..._arten`: Die Summe steht in der einen, die Aufteilung in der
        # anderen. Sie hier zusammenzuziehen hieße, die Summenzeile des
        # Dokuments viermal zu wiederholen — und die Probe, dass die Teile sie
        # ergeben, hätte nichts mehr, wogegen sie prüfen könnte.
        #
        # `amount` ist NULL, wo der Titel nur eine Wertgrenze nennt (die neun
        # Sammelberichte). Eine 0 stünde dort für „nichts nachbewilligt" und
        # wäre falsch; NULL heißt „diese Zeile trägt keinen Betrag".
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_supplementary_approvals ("
            "template_number TEXT PRIMARY KEY, "
            "year INTEGER, "                   # aus der Vorlagen-Nummer
            "title TEXT NOT NULL, "
            "kind TEXT NOT NULL, "             # approval|commitment_auth…|threshold
            "category TEXT NOT NULL, "        # excess|unbudgeted|both
            "amount REAL, "                    # NULL bei kind='threshold'
            "amount_source TEXT, "             # title | proposed_decision
            "decided INTEGER NOT NULL DEFAULT 0, "
            # Zwei Spalten, weil es zwei verschiedene Fragen sind:
            # `in_plenary` = das Plenum hat abgestimmt (die wörtliche Auskunft,
            # die auf der Seite steht). `council_decision` = der
            # Rechenschaftsbericht bucht es als „Beschluss des Rates" —
            # einschließlich der Fälle, die der Finanzausschuss abschließend
            # entscheidet. Nur die zweite darf in einen Rats-Anteil; die erste
            # liegt 2024 um 28 % daneben (s. council/nachbewilligungen.py).
            "in_plenary INTEGER NOT NULL DEFAULT 0, "
            "council_decision INTEGER NOT NULL DEFAULT 0, "
            # Für den Link auf die vorhandene Beschluss-Seite
            # (/council/decision?id=). Der maßgebliche Beschluss ist der des
            # Rates, sonst der jüngste — dieselbe Ordnung wie anderswo.
            "decision_id INTEGER, "
            "committees TEXT, "                   # JSON: wo sie beraten wurde
            "fulltext_probe INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_supplementary_years ("
            "year INTEGER PRIMARY KEY, "
            # Was die Summenzeile der Tabelle selbst ausweist …
            "total_operating REAL NOT NULL, "
            "total_capital REAL NOT NULL, "
            # … und was der Fließtext darüber behauptet. Beides wird
            # gespeichert, gerade WEIL es 2022 auseinanderfällt: Wer nur eine
            # der beiden Zahlen behielte, hätte den Widerspruch weggeräumt.
            "total_per_text REAL, "
            "commitments_amount REAL, "
            # Das Ergebnis der Tabellenprobe im Klartext — es steht auf der
            # Seite, nicht nur im Log.
            "probe_ok INTEGER NOT NULL DEFAULT 0, "
            "probe_text TEXT, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_supplementary_channels ("
            "year INTEGER NOT NULL, "
            "channel TEXT NOT NULL, "            # rat|oberbuergermeister|…
            "label TEXT NOT NULL, "            # der Wortlaut der Stadt
            "count_operating INTEGER NOT NULL, "
            "amount_operating REAL NOT NULL, "
            "count_capital INTEGER NOT NULL, "
            "amount_capital REAL NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, channel))"
        )
        # Angenommene Zuwendungen je Ratsvorlage (council/spenden.py). Eine
        # Zeile je Vorlage, nicht je Jahr: Der Jahreswert entsteht erst beim
        # Lesen, und die Vorlagen-Nummer ist der Weg zur Beschluss-Seite.
        #
        # Was hier bewusst FEHLT: eine Spalte für die Gebenden. Die Namen
        # stehen nur in der Anlage „Zuwendungsliste", die nicht im Bestand ist
        # — und was die Tabelle nicht führen kann, kann die API nicht liefern
        # und das Frontend nicht versehentlich zeigen. Das ist keine
        # Sparsamkeit, sondern die Grenze: Der Ratsbeschluss macht die Summe
        # öffentlich, nicht die Liste dahinter.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_donations ("
            "template_number TEXT PRIMARY KEY, "
            "year INTEGER NOT NULL, "          # Jahr der Sitzung
            "session_date TEXT NOT NULL, "     # ISO-Datum
            "amount REAL NOT NULL, "           # in Euro, wie beschlossen
            "committee TEXT, "                   # Rat | Verwaltungsausschuss
            "layout TEXT, "                    # new | old — welcher Abschnitt trug
            "second_mention TEXT NOT NULL, "      # identisch | zerlegung
            "probes TEXT NOT NULL, "           # bestandene Proben, kommagetrennt
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Und die Gegenprobe: die Zeilen ohne Zweitstelle, mit dem Satz, warum.
        # Eine Lücke ist eine Auskunft — sie steht auf der Seite, statt still
        # aus der Summe zu fehlen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_donations_rejected ("
            "template_number TEXT PRIMARY KEY, "
            "session_date TEXT, "
            "reason TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die Marken der Skriptläufe des Datenstand-Crons (check_finanzdaten):
        # je Datenart die Dokumentmarke, bei der ihr Ingest-Skript zuletzt
        # lief — der Cron ruft es erst wieder, wenn ein neueres Dokument da ist.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_ingest_marks ("
            "key TEXT PRIMARY KEY, "
            "marke INTEGER NOT NULL, "
            "ran_at TEXT NOT NULL, "
            "ok INTEGER NOT NULL, "
            "summary TEXT)"
        )
        # Der Liquiditätsstand (council/liquidity.py): je Monatsende der Stand
        # in Euro, aus den Grafiken der monatlichen Vorlagen — jüngster Beleg
        # je Monat, `confirmations` = in wie vielen Grafiken der Wert steht.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_liquidity ("
            "month TEXT PRIMARY KEY, "           # YYYY-MM
            "year INTEGER NOT NULL, "
            "amount REAL NOT NULL, "             # Euro
            "as_of TEXT NOT NULL, "              # Stichtag der Grafik, ISO
            "confirmations INTEGER NOT NULL DEFAULT 1, "
            "revised_from REAL, "                # der verdrängte Wert einer Korrektur
            "document_id INTEGER, url TEXT, template_number TEXT, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        # Die Jahresabschlüsse der Eigenbetriebe (council/eigenbetriebe_abschluss.py):
        # je Betrieb, Jahr und Kennzahl EINE Zahl — aus dem jüngsten Bericht,
        # der sie nennt, bezeugt von den Vorjahresspalten der folgenden.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_enterprise_accounts ("
            "enterprise TEXT NOT NULL, "          # Kürzel aus wirtschaftsplan.BETRIEBE
            "year INTEGER NOT NULL, "
            "metric TEXT NOT NULL, "             # eigenbetriebe_abschluss.METRIKEN
            "value REAL NOT NULL, "              # Euro (Stück bei employees)
            "unit TEXT NOT NULL, "               # TEUR | EUR | Stück — wie gedruckt
            "report_year INTEGER NOT NULL, "     # der Bericht, aus dem die Zahl stammt
            "confirmations INTEGER NOT NULL DEFAULT 1, "
            "conflicts INTEGER NOT NULL DEFAULT 0, "
            "document_id INTEGER, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (enterprise, year, metric))"
        )
        # Kredite und Zinsen (council/loans.py): die Unterrichtungen des Rates
        # nach der Kreditrichtlinie — je Vorlage eine Zeile mit Berichts-
        # zeitraum und Zinsersparnis, je nummeriertem Posten eine Zeile mit
        # Art, Schuldner, Betrag, Zinssatz, Zinsbindung. Beträge in Euro.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_loan_notices ("
            "template_number TEXT PRIMARY KEY, "
            "year INTEGER NOT NULL, "            # Jahr des Berichtszeitraums
            "period_from TEXT NOT NULL, "        # YYYY-MM
            "period_to TEXT NOT NULL, "
            "document_date TEXT, "               # ISO
            "none_reported INTEGER NOT NULL DEFAULT 0, "  # „keine Kredite …"
            "items INTEGER NOT NULL DEFAULT 0, "
            "interest_saving REAL, "             # Zinsersparnis der Umschuldung
            "saving_from TEXT, saving_to TEXT, "
            "document_id INTEGER, document_url TEXT, "
            "probes TEXT NOT NULL, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_loan_items ("
            "template_number TEXT NOT NULL, "
            "seq INTEGER NOT NULL, "
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "               # loan | refinancing | prolongation | disbursement | lending | other
            "borrower TEXT, "                    # NULL = Grundgeschäfte der Stadt samt Betrieben
            "heading TEXT NOT NULL, "
            "amount REAL, "
            "rate_pct REAL, "
            "fixed_years INTEGER, fixed_until TEXT, "
            "decided_at TEXT, "
            "summary TEXT, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (template_number, seq))"
        )
        # Was je Steuerart geplant war und was daraus wurde — Tabelle 1103 des
        # Statistischen Jahrbuchs (council/steuertabellen.py). Beträge in Euro;
        # die Quelle rechnet in Tausend Euro.
        #
        # `kind` trägt GENAU die Schreibweise aus `council_taxes.kind`, und das
        # ist keine Kosmetik: Der Ist-Wert dieser Tabelle muss sich dort
        # wiederfinden, sonst kommt der Jahrgang nicht herein (Probe
        # `steuerplan_istabgleich`). Zwei Schreibweisen für dieselbe Steuer
        # hießen, dass der Abgleich still ins Leere liefe.
        #
        # `provisional` ist die Angabe der Quelle über sich selbst: Die jüngste
        # Spalte heißt dort „vorläufiges Rechnungsergebnis" statt
        # „Rechnungsergebnis". Eine Zahl, die noch revidiert werden kann, soll
        # das an sich tragen und nicht nur im Fließtext einer Seite.
        #
        # WAS HIER BEWUSST NICHT STEHT: die Zeile „insgesamt" und die
        # „Finanzzuweisungen". Beide stehen in derselben Tabelle und tragen die
        # Summenprobe mit — aber sie haben in `council_taxes` keine
        # Entsprechung, gegen die sich ihre Jahresbeschriftung prüfen ließe.
        # Was die Probe nicht erreicht, wird nicht gespeichert. (Bei den
        # Finanzzuweisungen kommt hinzu, dass sie NICHT dasselbe sind wie die
        # Schlüsselzuweisungen in `council_tax_capacity` — zwei Abgrenzungen,
        # ein ähnlicher Name.)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_tax_plan ("
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "             # = council_taxes.kind
            "plan REAL NOT NULL, "             # in Euro
            "actual REAL NOT NULL, "           # in Euro
            "provisional INTEGER NOT NULL DEFAULT 0, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, kind))"
        )
        # Die Realsteuer-Hebesätze seit 1980 — Tabelle 1105 desselben Blatts.
        #
        # Neun Zeilen für 45 Jahre: Die Tabelle führt nur die Jahre, in denen
        # sich etwas geändert hat. Ein Satz gilt bis zur nächsten Änderung, und
        # deshalb ist das eine TREPPE und keine Kurve — zwischen zwei Stufen
        # wird nichts interpoliert, weder hier noch im Frontend
        # (`components/grafik/zeitreihe.tsx`, Modus `treppe`).
        #
        # `prior_rate` ist der Satz, der bis zu diesem Jahr galt — NULL in der
        # ersten Zeile. Er steht mit in der Tabelle, weil die Aussage der Zeile
        # die Änderung ist und nicht der Stand: „445 → 539" ist das, was ein
        # Rat beschließt. Ihn beim Lesen aus der Vorzeile zu rechnen ginge auch,
        # aber nur, solange niemand einen Ausschnitt der Reihe abfragt.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_tax_rates ("
            "year INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "             # Grundsteuer A | B | Gewerbesteuer
            "rate INTEGER NOT NULL, "      # Prozentpunkte
            "prior_rate INTEGER, "
            "herkunft_id INTEGER, fetched_at TEXT NOT NULL, "
            "PRIMARY KEY (year, kind))"
        )
        # Vorlagen-Volltexte semantisch auffindbar machen: je Vorlage mehrere
        # Chunk-Vektoren (Sachverhalt/Begründung), die die Hybrid-Suche auf die
        # zugehörigen Beschlüsse abbildet. text_hash = SHA-256 des Volltexts —
        # macht das Embedding-Skript idempotent (nur Geändertes wird neu embedded).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_template_embeddings ("
            "template_number TEXT NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "   # der Reranker bekommt die FUNDSTELLE zu sehen
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (template_number, chunk_idx))"
        )
        # Anlagen-Chunks (Task 33): Gutachten, Konzepte, Stellungnahmen — die
        # Volltexte lädt scripts/backfill_anlagen_texte.py, die Vektoren baut
        # scripts/embed_anlagen.py. Der schnelle Fragepfad lädt diese Matrix
        # nur bei explizitem Dokumentenbedarf, Deep Research grundsätzlich.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_anlage_embeddings ("
            "document_id INTEGER NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (document_id, chunk_idx))"
        )
        # Pressemitteilungen der Stadt (council/presse.py): Volltext intern für
        # Suche/Embedding, angezeigt werden Titel/Datum/Auszug/Link. Dazu ein
        # eigener FTS-Index und Chunk-Vektoren analog den Vorlagen.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_press ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "url TEXT NOT NULL UNIQUE, "
            "news_id INTEGER, "
            "title TEXT NOT NULL, "
            "date TEXT, "
            "text TEXT NOT NULL, "
            "fetched_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_press_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_press_embeddings ("
            "press_id INTEGER NOT NULL, "
            "chunk_idx INTEGER NOT NULL, "
            "text_hash TEXT NOT NULL, "
            "chunk_text TEXT NOT NULL, "
            "vector BLOB NOT NULL, "
            "PRIMARY KEY (press_id, chunk_idx))"
        )
        # Wortbeiträge aus den Protokollen (Task 16): Redebeiträge, „Anfragen
        # und Anregungen", Einwohnerfragestunde und Zusagen der Verwaltung —
        # die Debatten-Substanz, die in den Beschluss-Floskeln fehlt
        # (Fliegerhorst-Befund). Jeder Beitrag ist sein eigener Such-Chunk.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_speeches ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ksinr INTEGER NOT NULL, "
            "position INTEGER NOT NULL, "
            "kind TEXT NOT NULL, "           # speech | inquiry | citizen_question | pledge
            "top TEXT, "
            "speaker TEXT, "
            "party TEXT, "
            "text TEXT NOT NULL, "
            "answer TEXT, "                 # Verwaltungsantwort bei Anfragen
            "extracted_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wb_ksinr ON council_speeches(ksinr)")
        # Chronik der Tagesordnungs-Änderungen (Tims Wunsch 18.08.): Die Push
        # sagt nur noch den Satz — WAS sich geändert hat, zeigt die
        # Sitzungsseite aus dieser Tabelle. Eine Zeile je neuem Stand,
        # unabhängig davon, wer wann benachrichtigt wurde.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS agenda_changes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ksinr INTEGER NOT NULL, "
            "changed_at TEXT NOT NULL, "
            "diff_json TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agenda_changes_ksinr ON agenda_changes(ksinr)")
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS council_speeches_fts "
            "USING fts5(content, tokenize=\"unicode61 remove_diacritics 2\")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_speeches_embeddings ("
            "contribution_id INTEGER PRIMARY KEY, "
            "text_hash TEXT NOT NULL, "
            "vector BLOB NOT NULL)"
        )
        # Server-Cache des Parteien-Bausteins (Task 30): Schlüssel ist der Hash
        # der verdichteten Beitrags-IDs — verschieden formulierte Fragen zum
        # selben Thema treffen denselben Eintrag, ein NEUER Beitrag zum Thema
        # ändert den Hash und erzwingt die Nachverdichtung von selbst.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_partei_meinungen_cache ("
            "key TEXT PRIMARY KEY, question TEXT, result TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        # Erledigt-Marker der Wortbeitrags-Extraktion am Protokoll: auch ein
        # leeres Ergebnis (Formalien-Niederschrift) zählt als erledigt — ohne
        # den Marker fräße jedes davon dauerhaft einen nächtlichen LLM-Call.
        wcols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_protocols)").fetchall()}
        if "contributions_extracted_at" not in wcols:
            self._conn.execute(
                "ALTER TABLE council_protocols ADD COLUMN contributions_extracted_at TEXT")
        if "page_offsets" not in wcols:
            # Seitengenaue Protokoll-Links (18.08.2026): Offsets der PDF-
            # Seitenanfänge im raw_text; Altbestand bleibt NULL bis zum
            # Backfill (scripts/backfill_protokoll_seiten.py).
            self._conn.execute("ALTER TABLE council_protocols ADD COLUMN page_offsets TEXT")
        wb_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_speeches)")}
        if wb_cols and "page" not in wb_cols:
            # PDF-Seite der Fundstelle (über Sprecher-Anker aufgelöst);
            # NULL = nicht eindeutig gefunden → Link ohne #page.
            self._conn.execute("ALTER TABLE council_speeches ADD COLUMN page INTEGER")
        # Aus raw_result geparste Teilvoten: welche Fraktion stimmte laut
        # Protokoll dagegen / enthielt sich. faction steht wie protokolliert
        # (Gruppen nicht aufgelöst — Fraktion≠Partei, siehe council/parties.py).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS council_decision_votes ("
            "decision_id INTEGER NOT NULL, "
            "faction TEXT NOT NULL, "
            "stance TEXT NOT NULL, "                    # against | abstention
            "PRIMARY KEY (decision_id, faction, stance))"
        )
        self._migrate_quiz_estimate()
        self._migrate_quiz_media()
        self._migrate_quiz_hint()
        self._migrate_produkt_steckbrief()
        self._migrate_herkunft()
        self._migrate_owner_id()

    def _migrate_quiz_estimate(self) -> None:
        """Schätzfrage-Slider: numerische Felder für qtype='estimate' in
        bestehende Quiz-Tabellen nachrüsten (idempotent)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        adds = [("qtype", "TEXT NOT NULL DEFAULT 'mc'"), ("answer_value", "REAL"),
                ("answer_unit", "TEXT"), ("range_min", "REAL"), ("range_max", "REAL")]
        with self._conn:
            for name, decl in adds:
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} {decl}")

    def _migrate_quiz_media(self) -> None:
        """„Reichere Antworten": Detailtext, Locator-Karte und Bild (mit
        Bildnachweis) in bestehende Quiz-Tabellen nachrüsten (idempotent)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        adds = [("detail", "TEXT"), ("lat", "REAL"), ("lon", "REAL"), ("place_label", "TEXT"),
                ("geojson", "TEXT"),
                ("image_url", "TEXT"), ("image_author", "TEXT"), ("image_license", "TEXT"),
                ("image_license_url", "TEXT"), ("image_source_url", "TEXT")]
        with self._conn:
            for name, decl in adds:
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} {decl}")

    def _migrate_quiz_hint(self) -> None:
        """„Tipp" (vor dem Auflösen) + „topic" (Such-Stichwort für „Beschlüsse
        dazu") + „chart" (Diagramm-JSON der Auflösung) — idempotent in
        bestehende Quiz-Tabellen nachgerüstet."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_quiz_questions)").fetchall()}
        with self._conn:
            for name in ("hint", "topic", "chart"):
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_quiz_questions ADD COLUMN {name} TEXT")

    def _migrate_produkt_steckbrief(self) -> None:
        """Produkt-Steckbrief (Kurzbeschreibung, Rechtsgrundlage, Spielraum,
        Wirkungskreis, Zielgruppe) in bestehende Produkt-Tabellen nachrüsten.

        Anders als bei ``council_income_statement`` reicht hier ALTER TABLE:
        Der Primärschlüssel (year, produkt_nr) bleibt, wie er ist — es kommen
        nur Spalten dazu. Die Werte füllt der nächste Lauf von
        ``scripts/ingest_finanzberichte.py`` nach; bis dahin sind sie NULL und
        die Oberfläche zeigt den Steckbrief schlicht nicht an."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(council_products)").fetchall()}
        with self._conn:
            for name in ("short_description", "legal_basis", "controllability",
                         "controllability_raw", "scope", "target_group"):
                if name not in cols:
                    self._conn.execute(f"ALTER TABLE council_products ADD COLUMN {name} TEXT")

    #: Wie eine Tabelle ihre Herkunft bisher führte: (Label-Spalte,
    #: URL-Spalte, Quellenart). Drei Schreibweisen für dieselbe Sache — genau
    #: das war der Anlass für `council/herkunft.py`.
    #:
    #: Die Quellenart steht hier nur, wo sie aus der Tabelle folgt. Bei
    #: `council_budget` folgt sie das nicht: Ein Jahrgang kam als PDF von
    #: oldenburg.de, ein anderer als CSV aus dem Open-Data-Portal — dort
    #: entscheidet die URL (s. `_herkunft_art_aus_url`).
    _HERKUNFT_ALTFELDER: dict[str, tuple[str | None, str, str | None]] = {
        "council_budget":             (None, "source_url", None),
        "council_taxes":              (None, "source_url", "opendata"),
        "council_tax_capacity":          (None, "source_url", "opendata"),
        "council_einwohner":            (None, "source_url", "opendata"),
        "council_income_statement":     ("source_label", "source_url", "ris"),
        # Neu mit der Kassensicht, ohne Altbestand — nichts nachzutragen.
        "council_cash_flow_statement":       (None, None, "ris"),
        # Ebenso die Bilanz und ihre Erläuterungen: erst mit der Herkunft
        # entstanden, keine Altspalten.
        "council_balance_sheet":               (None, None, "ris"),
        "council_balance_sheet_notes": (None, None, "ris"),
        "council_variance_reasons":   ("source_label", "source_url", "ris"),
        "council_audit_report_sources": ("label", "url", "ris"),
        "council_products":             ("source_label", "source_url", "ris"),
        "council_audit_reports":        ("source_label", "source_url", "ris"),
        # Die beiden Konzern-Tabellen sind erst mit der Herkunft entstanden
        # und tragen gar keine Altspalten. Sie stehen hier trotzdem, weil
        # `_herkunft_nachtragen` jede Tabelle aus `HERKUNFT_TABELLEN`
        # nachschlägt; ohne URL-Spalte kehrt es sofort zurück, ohne etwas zu
        # tun. Ein Eintrag „nichts nachzutragen" ist billiger als eine
        # Ausnahme im Nachrüst-Weg.
        "council_group_items":       (None, "source_url", "ris"),
        "council_group_entities":      (None, "source_url", "ris"),
        # Ebenso der Städtevergleich: erst mit der Herkunft entstanden, keine
        # Altspalten, nichts nachzutragen.
        "council_city_comparison":     (None, "source_url", "lsn"),
        # Und die Gewerbesteuerstatistik, ebenfalls vom Landesamt.
        "council_trade_tax_statistics": (None, "source_url", "lsn"),
        # Und die Planjahre aus dem Gesamtergebnishaushalt.
        "council_income_budget":     (None, "source_url", "ris"),
        # Ebenso die Investitionen des Finanzhaushalts: neu, ohne Altspalten,
        # Herkunft ausschließlich über `herkunft_id`.
        "council_investments":        (None, "source_url", "opendata"),
        # Und die Maßnahmen aus Anlage 004: ebenfalls neu, ebenfalls ohne
        # Altspalten. Der Eintrag muss trotzdem stehen — `_herkunft_nachtragen`
        # schlägt hier nach, bevor es merkt, dass es nichts nachzutragen gibt.
        "council_investment_measures": (None, "source_url", "ris"),
        # Das Ist-Gegenstück aus dem Statistischen Jahrbuch — anders als Plan
        # und Programm kommt es weder vom Portal noch aus dem RIS, sondern von
        # oldenburg.de.
        "council_investments_actual":       (None, "source_url", "city"),
        "council_investments_actual_kinds": (None, "source_url", "city"),
        "council_investments_actual_rejected": (None, "source_url", "city"),
        # Der Stellenplan — ebenfalls neu und ohne Altbestand.
        "council_staff_plan":          (None, "source_url", "ris"),
        # Und die Schuldenzeitreihe aus dem Statistischen Jahrbuch.
        "council_debt":             (None, "source_url", "city"),
        # Die lange Ausgabenreihe: zwei Quellen — das Jahrbuch der Stadt und
        # das Open-Data-Portal —, deshalb keine feste Art. Nachzutragen ist
        # ohnehin nichts, die Tabelle ist neu.
        "council_expense_series":        (None, "source_url", None),
        # Der Bürgschaftsbestand: eine Quelle, der Jahresabschluss als Anlage
        # im Ratsinformationssystem.
        "council_buergschaften":        (None, "source_url", "ris"),
        "council_fixed_assets":       (None, "source_url", "ris"),
        # Die Kennzahlen und ihre Rechenwege: Anlage des Rechenschaftsberichts,
        # also ebenfalls ein Dokument im Ratsinformationssystem.
        "council_indicators":           (None, "source_url", "ris"),
        "council_indicator_formulas":     (None, "source_url", "ris"),
        "council_vermoegensgruppen":    (None, "source_url", "ris"),
        # Die dritte Schuldenzahl: Tabellenband der Statistischen Ämter,
        # also weder Stadt noch Ratsinformationssystem — eigene Art "lsn"
        # wie beim Städtevergleich.
        "council_integrated_debt": (None, "source_url", "lsn"),
        # Die Nachbewilligungen: neu, ohne Altspalten. Beide Quellen liegen im
        # Ratsinformationssystem — die Vorlagen selbst und der
        # Rechenschaftsbericht als Anlage zum Jahresabschluss.
        "council_supplementary_approvals":        (None, "source_url", "ris"),
        "council_supplementary_years":    (None, "source_url", "ris"),
        "council_supplementary_channels":  (None, "source_url", "ris"),
        # Die Zuwendungen: Quelle sind Ratsvorlagen im Bürgerinfo, also „ris".
        # Nachzutragen ist nichts, beide Tabellen sind neu.
        "council_donations":              (None, "source_url", "ris"),
        "council_donations_rejected":    (None, "source_url", "ris"),
        # Die beiden Steuertabellen des Jahrbuchs — neu, ohne Altbestand.
        "council_tax_plan":           (None, "source_url", "city"),
        "council_tax_rates":           (None, "source_url", "city"),
        # Gebührenbedarf und Anlage-4-Tarife sind neu mit Herkunft entstanden;
        # sie haben keine doppelten Altspalten, die nachzutragen wären.
        "council_fees":            (None, "source_url", "ris"),
        "council_fee_rates":      (None, "source_url", "ris"),
        # Der Beteiligungsbericht: ebenfalls erst mit der Herkunft entstanden.
        # Seine Dokumente kommen von oldenburg.de, nicht aus dem Bürgerinfo.
        "council_companies":            (None, "source_url", "city"),
        "council_company_texts":        (None, "source_url", "city"),
        "council_company_indicators":   (None, "source_url", "city"),
        "council_company_people":     (None, "source_url", "city"),
        "council_company_owners":  (None, "source_url", "city"),
        # Der Haushaltsvollzug: neu, ohne Altbestand, ohne Altspalten. Der
        # Eintrag muss trotzdem stehen — `_herkunft_nachtragen` schlägt hier
        # nach, bevor es merkt, dass es nichts nachzutragen gibt.
        "council_budget_execution": (None, "source_url", "ris"),
        "council_liquidity": (None, "url", "ris"),
    "council_enterprise_accounts": (None, None, "ris"),
        # Kredite und Zinsen: neu, ohne Altbestand — derselbe Platzhalter.
        "council_loan_notices": (None, "document_url", "ris"),
        "council_loan_items": (None, "document_url", "ris"),
    }

    @staticmethod
    def _herkunft_art_aus_url(url: str | None) -> str | None:
        """Quellenart aus einer gespeicherten URL — abgeleitet, nicht geraten.

        Entschieden wird an Zeichenketten, die wörtlich in der URL stehen —
        das Portal, die Stadt-Domain, das Bürgerinfo. Alles andere (etwa ein
        ``file:``-Pfad aus einem Lauf mit ``--pdf``) bleibt ohne Herkunft,
        statt eine Art zu erfinden; ``herkunft_luecken()`` zeigt es dann an."""
        if not url:
            return None
        if "opendata.oldenburg.de" in url:
            return "opendata"
        if "oldenburg.de" in url:
            return "city"
        if "buergerinfo" in url or "/getfile" in url:
            return "ris"
        return None

    def _migrate_herkunft(self) -> None:
        """Herkunfts-Fundament nachrüsten: `herkunft_id` an jede Zieltabelle,
        und was in den alten Feldern steht, in `council_provenance` überführen.

        Rein additiv. Die alten Spalten (`source_label`, `source_url`,
        `source_url`, `fetched_at`) bleiben unangetastet — sie zu entfernen
        hieße, neun Tabellen neu zu schreiben, darunter vier, deren Inhalt nur
        über einen Download von oldenburg.de wiederzubeschaffen wäre. Deshalb
        genügt hier durchgehend ALTER TABLE, und kein bestehender Wert ändert
        sich.

        **Übernommen wird, was in den Daten steht: Label, URL und — neu — die
        `document_id`, die sich über die URL in `council_attachments` eindeutig
        auflösen lässt. Fundstelle und Probe bleiben leer bzw. tragen
        `unbekannt`:** Der Altbestand sagt nicht, an welchem Abschnitt er
        gelesen wurde und welche Probe er bestanden hat. Das zu erfinden wäre
        genau die Sorte Angabe, die diese Umstellung abschaffen soll. Der
        nächste Ingest-Lauf trägt beides nach, weil er den Jahrgang ohnehin
        ersetzt."""
        from council import herkunft as _h

        with self._conn:
            for tabelle in _h.HERKUNFT_TABELLEN:
                cols = {r[1] for r in self._conn.execute(
                    f"PRAGMA table_info({tabelle})")}
                if not cols:
                    continue  # Tabelle gibt es in dieser DB (noch) nicht
                if "herkunft_id" not in cols:
                    self._conn.execute(
                        f"ALTER TABLE {tabelle} ADD COLUMN herkunft_id INTEGER")
                self._herkunft_nachtragen(tabelle)

    def _herkunft_nachtragen(self, tabelle: str) -> int:
        """Zeilen einer Tabelle ohne `herkunft_id` aus ihren Altfeldern
        versorgen. Idempotent: Wer schon eine hat, wird nicht angefasst."""
        from council import herkunft as _h

        label_spalte, url_spalte, feste_art = self._HERKUNFT_ALTFELDER[tabelle]
        cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if url_spalte not in cols:
            return 0
        gelesen = [label_spalte, url_spalte] if label_spalte in cols else [url_spalte]
        # Je *Kombination* aus Label und URL ein Herkunfts-Datensatz — das ist
        # die Granularität, in der der Altbestand seine Quelle kennt.
        auswahl = ", ".join(gelesen)
        gruppen = self._conn.execute(
            f"SELECT {auswahl}, MAX(fetched_at) AS zuletzt FROM {tabelle} "
            f"WHERE herkunft_id IS NULL GROUP BY {auswahl}").fetchall()
        getroffen = 0
        for g in gruppen:
            url = g[url_spalte]
            label = g[label_spalte] if label_spalte in cols else None
            art = feste_art or self._herkunft_art_aus_url(url)
            if not art or not url:
                # Ohne Verweis keine Herkunft. Lieber eine leere Spalte als
                # ein Datensatz, der auf nichts zeigt.
                continue
            hid = self.merke_herkunft(
                _h.Herkunft(kind=art, probe=_h.UNBEKANNT, label=label, url=url,
                            document_id=self._dokument_zu_url(url)),
                fetched_at=g["zuletzt"])
            bedingung = f"{url_spalte} IS ?"
            args: list = [url]
            if label_spalte in cols:
                bedingung += f" AND {label_spalte} IS ?"
                args.append(label)
            cur = self._conn.execute(
                f"UPDATE {tabelle} SET herkunft_id = ? "
                f"WHERE herkunft_id IS NULL AND {bedingung}", [hid, *args])
            getroffen += cur.rowcount
        return getroffen

    def _dokument_zu_url(self, url: str | None) -> int | None:
        """Die `council_attachments.document_id` zu einer Anlagen-URL.

        Der stabile Anker, den der Altbestand nicht mitführte. Nur bei einem
        **eindeutigen** Treffer — zwei Anlagen unter derselben URL wären ein
        Fall für einen Blick, nicht für eine Vermutung."""
        if not url:
            return None
        try:
            treffer = self._conn.execute(
                "SELECT document_id FROM council_attachments WHERE url = ? LIMIT 2",
                (url,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return treffer[0][0] if len(treffer) == 1 else None

    def _migrate_owner_id(self) -> None:
        """Re-key the per-recipient dedup tables from Telegram chat_id to the
        canonical owner_id (=web_users.id). The map lives in the sibling
        ratslotse.sqlite; existing rows are backfilled via it. Idempotent."""
        cn_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(committee_notifications)").fetchall()}
        sf_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(session_followups_sent)").fetchall()}
        if "owner_id" in cn_cols and "owner_id" in sf_cols:
            return  # already migrated

        # Build chat_id -> owner_id from kern.sqlite if available.
        chat_to_owner: dict[int, int] = {}
        ratslotse_path = self._ratslotse_db_path
        if ratslotse_path is not None and Path(str(ratslotse_path)).exists():
            try:
                src = sqlite3.connect(str(ratslotse_path), timeout=15)
                chat_to_owner = {
                    r[0]: r[1] for r in src.execute(
                        "SELECT telegram_chat_id, id FROM web_users WHERE telegram_chat_id IS NOT NULL"
                    ).fetchall()
                }
                src.close()
            except sqlite3.Error:
                chat_to_owner = {}

        with self._conn:
            if "owner_id" not in cn_cols:
                old = self._conn.execute(
                    "SELECT ksinr, chat_id, agenda_hash, sent_at FROM committee_notifications"
                ).fetchall()
                self._conn.execute("DROP TABLE committee_notifications")
                self._conn.execute(
                    "CREATE TABLE committee_notifications ("
                    " ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL,"
                    " agenda_hash TEXT NOT NULL DEFAULT '', sent_at TEXT NOT NULL,"
                    " PRIMARY KEY(ksinr, owner_id))"
                )
                for r in old:
                    owner = chat_to_owner.get(r[1])
                    if owner is not None:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) "
                            "VALUES (?, ?, ?, ?)", (r[0], owner, r[2], r[3])
                        )
            if "owner_id" not in sf_cols:
                old = self._conn.execute(
                    "SELECT ksinr, chat_id, sent_at FROM session_followups_sent"
                ).fetchall()
                self._conn.execute("DROP TABLE session_followups_sent")
                self._conn.execute(
                    "CREATE TABLE session_followups_sent ("
                    " ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL, sent_at TEXT NOT NULL,"
                    " PRIMARY KEY(ksinr, owner_id))"
                )
                for r in old:
                    owner = chat_to_owner.get(r[1])
                    if owner is not None:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO session_followups_sent (ksinr, owner_id, sent_at) "
                            "VALUES (?, ?, ?)", (r[0], owner, r[2])
                        )

    def delete_owner_data(self, owner_id: int) -> int:
        """Alles aus dieser Datenbank löschen, was an einem Konto hängt.

        Gegenstück zu ``Store.delete_web_user``: Die Konto-Löschung muss beide
        Datenbanken abräumen, es gibt zwischen ihnen keine Fremdschlüssel, die
        das von allein täten. Gibt die Zahl gelöschter Zeilen zurück.
        """
        n = 0
        with self._conn:
            for tabelle, spalte in COUNCIL_USER_OWNED_TABLES:
                cur = self._conn.execute(f"DELETE FROM {tabelle} WHERE {spalte} = ?", (owner_id,))
                n += cur.rowcount or 0
        return n

    def close(self) -> None:
        self._conn.close()

    def admin_stats(self) -> dict:
        """Council counts for the admin dashboard (read-only)."""
        c = self._conn

        def one(sql: str, *p):
            row = c.execute(sql, p).fetchone()
            return row[0] if row else 0

        # „Läuft der Scraper?“ ist eine andere Frage als „gab es neue Sitzungen?“:
        # council_sessions wird nur beschrieben, wenn eine Sitzung mit
        # veröffentlichter Tagesordnung im Kalender steht — in der sitzungsfreien
        # Zeit also wochenlang gar nicht. Der Terminplan dagegen wird bei jedem
        # Lauf neu geschrieben und ist damit der verlässliche Puls.
        last_session_import = one("SELECT MAX(fetched_at) FROM council_sessions") or None
        last_scheduled = one("SELECT MAX(fetched_at) FROM council_scheduled_sessions") or None
        last_fetch = max([t for t in (last_session_import, last_scheduled) if t], default=None)
        return {
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "upcoming": one("SELECT COUNT(*) FROM council_sessions WHERE session_date >= date('now')"),
            "agenda_items": one("SELECT COUNT(*) FROM council_agenda_items"),
            "committees": one("SELECT COUNT(*) FROM committees"),
            # Design 20a — Ratsinfo-Import-Karte:
            "decisions": one("SELECT COUNT(*) FROM council_decisions"),
            "decisions_with_ki": one("SELECT COUNT(*) FROM council_decisions WHERE policy_field IS NOT NULL"),
            "last_fetch": last_fetch,
            # Stunden seit dem letzten Lauf — die Ampel darf nicht „heute schon
            # gelaufen?“ fragen, sonst steht sie jeden Morgen vor dem 8-Uhr-Cron
            # auf Rot, obwohl alles läuft (Läufe: 8 und 14 Uhr → max. ~18 h).
            "hours_since_fetch": (
                round((datetime.utcnow() - datetime.fromisoformat(last_fetch)).total_seconds() / 3600, 1)
                if last_fetch else None),
            "last_session_import": last_session_import,
            "next_session": one(
                "SELECT MIN(session_date) FROM ("
                " SELECT session_date FROM council_sessions WHERE session_date >= date('now')"
                " UNION ALL"
                " SELECT session_date FROM council_scheduled_sessions WHERE session_date >= date('now'))") or None,
            "fetched_today": one(
                "SELECT (SELECT COUNT(*) FROM council_sessions WHERE substr(fetched_at,1,10) = date('now'))"
                " + (SELECT COUNT(*) FROM council_scheduled_sessions WHERE substr(fetched_at,1,10) = date('now'))"),
        }

    def public_stats(self) -> dict:
        """Headline aggregate counts for the public landing page (no content)."""
        c = self._conn

        def one(sql: str) -> int:
            row = c.execute(sql).fetchone()
            return row[0] if row else 0

        return {
            "decisions": one("SELECT COUNT(*) FROM council_decisions WHERE kind = 'decision'"),
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "entities": one("SELECT COUNT(*) FROM council_entities"),
        }

    def alert_already_sent(self, ksinr: int, topic_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM council_alerts_sent WHERE ksinr = ? AND topic_id = ?",
            (ksinr, topic_id),
        ).fetchone()
        return row is not None

    def mark_alert_sent(self, ksinr: int, topic_id: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO council_alerts_sent (ksinr, topic_id, sent_at) VALUES (?,?,?)",
                (ksinr, topic_id, now),
            )

    # Kommende Sitzungen kommen aus ZWEI Quellen: echten Sitzungen mit
    # Tagesordnung und bloß terminierten aus dem Kalender. Liste und Zählung
    # müssen dieselbe Menge meinen — deshalb steht die Bedingung genau einmal
    # hier und wird von beiden benutzt.
    _UPCOMING_FROM = """
        FROM (
            SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                   COUNT(ci.id) AS n_items
            FROM council_sessions cs
            LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
            WHERE cs.session_date >= ?
            GROUP BY cs.ksinr
            UNION ALL
            SELECT NULL AS ksinr, ss.committee, ss.session_date, ss.session_time, ss.location,
                   0 AS n_items
            FROM council_scheduled_sessions ss
            WHERE ss.session_date >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM council_sessions cs2
                  WHERE cs2.committee = ss.committee AND cs2.session_date = ss.session_date
              )
        )
    """





    #: Tagesordnungspunkte, die in jeder Sitzung stehen und niemanden
    #: interessieren. Am Bestand gemessen: 20 von 53 kommenden TOPs.
    #: „- Bericht der Verwaltung" ist ein ZUSATZ, kein Punkt: Er hängt an den
    #: spannendsten Titeln der Woche („Ermittlungen Abfallentsorgung
    #: Fliegerhorst (CDU-Fraktion) - Bericht der Verwaltung"). Ein auf das
    #: Zeilenende verankertes Muster warf davon neun weg, darunter fast alle
    #: Fraktionsanträge — deshalb greift die Formalie nur, wenn der Punkt
    #: NICHTS ANDERES ist als diese Floskel.
    _FORMALIE_RE = re.compile(
        r"Beschlussf[äa]higkeit|Genehmigung der Tagesordnung|Genehmigung des Protokolls|"
        r"Einwohnerfragestunde|^Mitteilungen|Anfragen und Anregungen|Verschiedenes|"
        r"^\s*Bericht(?:e)? der Verwaltung\s*$|Wahl der Schriftf[üu]hrung",
        re.IGNORECASE)

    #: „(CDU-Fraktion vom 10.06.2026)", „(Fraktionen BSW und SPD)", „(FDP-Fraktion …)"
    _ANTRAG_RE = re.compile(r"\(\s*(?:die\s+)?(?:Fraktion(?:en)?|Gruppe|Ratsherr|Ratsfrau)\b|"
                            r"[A-ZÄÖÜ][\wÄÖÜäöüß/. ]{1,24}-Fraktion\b", re.IGNORECASE)

    _PERSONALIE_RE = re.compile(
        r"Berufung|Umbesetzung|Bestellung\s+(?:eines|einer)|"
        r"Wahl\s+(?:des|der|eines|einer)\s+(?:stellv|Vorsitz|Schriftf)|"
        r"beratende[sn]?\s+Mitglied", re.IGNORECASE)

    #: Bindende Gegenstände: Was hier greift, wirkt über den Tag hinaus —
    #: Satzungen, Gebühren, Haushalt, Bauleitplanung, Verträge, Grundsätze.
    #: Genau die Rubrik „Bindungswirkung" des Tragweite-Prompts, nur als Regel.
    _BINDEND_RE = re.compile(
        r"Satzung|Geb[üu]hren|Beitrags|Entgelt|Haushalt|Nachtragshaushalt|"
        r"Bebauungsplan|Fl[äa]chennutzungsplan|Bauleitplan|Grundsatzbeschluss|"
        r"Vertrag|Vereinbarung|Konzession|Verordnung|Richtlinie", re.IGNORECASE)

    #: Wo entschieden wird, wiegt schwerer als wo vorberaten wird. Der Rat und
    #: der Verwaltungsausschuss binden die Stadt, ein Fachausschuss bereitet vor.
    _GREMIUM_GEWICHT = ((("stadtrat", "rat der stadt"), 1.5), (("verwaltungsausschuss",), 1.0))

    #: Ab hier gilt ein Punkt als Schwerpunkt der Woche und wird hervorgehoben.
    #: Darunter zeigt die Karte ihre Zeilen ohne Hervorhebung — lieber kein
    #: Schwerpunkt als ein behaupteter.
    TOP_MINDEST = 60

    #: Mehr als zwei Hervorhebungen entwerten sich gegenseitig.
    TOP_MAX = 2

    #: Unter diesem Wert kommt ein Punkt gar nicht auf die Karte. Skala ist die
    #: Tragweite (0–100, s. council/impact.py): 20 ≈ Bericht zur Kenntnis,
    #: 35 ≈ Maßnahme an einer Einrichtung. Darunter lohnt keine Zeile.
    WICHTIG_MINDEST = 30

    #: Alte Heuristik-Schwelle — nur noch für die Umrechnung relevant.
    RANG_MINDEST = 1.5

    #: Lazy geladener Wiederkehr-Zähler (s. _wiederkehr).
    _wiederkehr_cache: dict[str, int] | None = None

    #: „(CDU-Fraktion vom 14.07.2026)" → Antragsteller „CDU-Fraktion"; der
    #: Zusatz frisst sonst die halbe Zeile auf der Karte (im Browser gesehen).
    _ANTRAGSTELLER_RE = re.compile(
        r"\s*\(\s*(?:die\s+)?(?P<wer>[^)]*?)\s*(?:vom\s+\d{1,2}\.\d{1,2}\.\d{2,4})?\s*\)")
    #: Verfahrens-Anhängsel am Titelende, die auf der Karte nichts erklären.
    _TITEL_ANHANG_RE = re.compile(
        r"\s*[-–]\s*(?:\w*[Aa]ntrag mit Bericht der Verwaltung|Bericht(?:e)? der Verwaltung|"
        r"Beschlussantrag|Berichtsantrag|Antrag|Bericht|Beschluss|Vorlage|Kenntnisnahme)\s*$",
        re.IGNORECASE)

    #: „Ö 11.3" → Präfix „Ö", Nummer „11.3". Das Präfix ist zugleich der
    #: Öffentlichkeitsmarker (Ö/N) und gehört zur Nummer, nicht davor weg.
    _TOP_NUMMER_RE = re.compile(r"^\s*([A-Za-zÖÄÜöäü]+)\s+([\d.]+?)\.?\s*$")

    #: Wörter, die in Tagesordnungs-Überschriften stehen, ohne einen
    #: Gegenstand zu benennen — sie dürfen keine Gruppe begründen.
    _RUBRIK_WORTE = frozenset({
        "antraege", "antrag", "fraktionen", "fraktion", "gruppen", "gruppe",
        "ratsund", "ausschussmitglieder", "mitglieder", "berichte", "bericht",
        "anfragen", "anregungen", "mitteilungen", "verschiedenes", "verwaltung",
        "beschluss", "beschluesse", "vorlagen", "sonstiges", "genehmigung",
        "protokolle", "protokolls", "tagesordnung", "oeffentlicher", "teil",
    })
















    def anlagen_fuer(self, kvonr: int) -> list[dict]:
        """Anlagen einer Vorlage mit Text — Anträge zuerst, dann die kürzeste.

        Die Reihenfolge ist die halbe Miete: Der Antrag einer Fraktion hat
        3.000 Zeichen und sagt, was jemand WILL. Der „Materialband
        Lupenpläne" derselben Vorlage hat 400.000 und ist als OCR-Text eine
        Kartensammlung. Wer nach Länge sortiert, bekommt zuerst das Argument
        und läuft nicht Gefahr, sein Budget mit Planwerk zu füllen.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT label, is_motion, applicants, raw_text FROM council_attachments "
            "WHERE kvonr = ? AND raw_text IS NOT NULL AND length(raw_text) > 0 "
            "ORDER BY is_motion DESC, length(raw_text) ASC", (kvonr,))]


















    # ---- protocols / decisions / attendance ----


    def _insert_decision(self, ksinr, position, kind, parent_item, item_number, title,
                         official_text, outcome, vote, no_votes, abstentions, factions,
                         template_number, kvonr, raw_result) -> None:
        cur = self._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr, position, kind, parent_item, item_number, title, official_text, outcome, "
            " vote, no_votes, abstentions, factions, template_number, kvonr, raw_result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ksinr, position, kind, parent_item, item_number, title, official_text, outcome,
             vote, _int_or_none(no_votes), _int_or_none(abstentions),
             json.dumps(factions or [], ensure_ascii=False),
             template_number, _int_or_none(kvonr), raw_result),
        )
        # Nennt der Abstimmungssatz Fraktionen ausdrücklich (Gegenstimmen/
        # Enthaltungen), landen sie strukturiert in council_decision_votes —
        # neue Protokolle tragen ihre Teilvoten damit ab Import.
        if raw_result:
            from council.votes import parse_raw_result
            parsed = parse_raw_result(raw_result)
            if parsed:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                    "VALUES (?, ?, ?)",
                    [(cur.lastrowid, f, s) for f, s in parsed],
                )

    def save_protocol(
        self,
        ksinr: int,
        document: dict,
        meta: dict,
        raw_text: str,
        n_pages: int,
        model: str,
        decisions: list[dict],
        attendance: list[dict],
        status: str = "ok",
        page_offsets: list[int] | None = None,
    ) -> None:
        """Persist a parsed protocol with its decisions + attendance (replacing any
        prior rows for this session). One transaction."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, protocol_nr, session_start, session_end, "
                " raw_text, n_pages, page_offsets, model, extracted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ksinr, document.get("document_id"), document.get("url"), meta.get("protocol_nr"),
                 meta.get("session_start"), meta.get("session_end"), raw_text, n_pages,
                 json.dumps(page_offsets) if page_offsets else None, model, now, status),
            )
            # Teilvoten hängen an den decision-ids — vor dem Ersetzen der
            # Beschlüsse mitlöschen, sonst bleiben Waisen zurück (dieselbe
            # Falle wie bei den Themen-Treffern, #340).
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id IN "
                "(SELECT id FROM council_decisions WHERE ksinr = ?)", (ksinr,))
            self._conn.execute("DELETE FROM council_decisions WHERE ksinr = ?", (ksinr,))
            self._conn.execute("DELETE FROM council_attendance WHERE ksinr = ?", (ksinr,))
            pos = 0
            for d in decisions:
                self._insert_decision(ksinr, pos, "decision", None,
                                      d.get("item_number"), d.get("title"), d.get("official_text"),
                                      d.get("outcome"), d.get("vote"), d.get("no_votes"),
                                      d.get("abstentions"), d.get("factions"),
                                      d.get("template_number"), d.get("kvonr"), d.get("raw_result"))
                pos += 1
                for sv in d.get("sub_votes") or []:
                    self._insert_decision(ksinr, pos, "subvote", d.get("item_number"),
                                          d.get("item_number"), sv.get("description"), None,
                                          sv.get("outcome"), sv.get("vote"), sv.get("no_votes"),
                                          sv.get("abstentions"), sv.get("factions"),
                                          None, None, sv.get("raw_result"))
                    pos += 1
            for a in attendance:
                self._conn.execute(
                    "INSERT INTO council_attendance (ksinr, name, party, role, note) VALUES (?, ?, ?, ?, ?)",
                    (ksinr, a.get("name"), a.get("party"), a.get("role"), a.get("note")),
                )
            # Regex-Ernte (council.ernte): Sitzungsort aus dem Protokollkopf in die
            # Session übernehmen (der Terminplan liefert ihn leer) und Beschlüsse
            # über die Vorlagen-Nummer an ihre kvonr hängen.
            from council import ernte

            ort = ernte.sitzungsort(raw_text)
            if ort:
                self._conn.execute(
                    "UPDATE council_sessions SET location = ? WHERE ksinr = ? AND location = ''",
                    (ort, ksinr),
                )
            # Auch Revisions-Zitate („22/0348/1") an die Basis-Vorlage
            # („22/0348") hängen — exakter Treffer gewinnt vor dem Präfix
            # (Review-Befund E2: sonst blieben kvonr und deviation NULL,
            # obwohl get_vorlage_by_nr die Vorlage längst auflöst).
            self._conn.execute(
                "UPDATE council_decisions SET kvonr = COALESCE("
                "(SELECT MAX(v.kvonr) FROM council_templates v WHERE v.template_number = council_decisions.template_number), "
                "(SELECT MAX(v.kvonr) FROM council_templates v "
                " WHERE instr(council_decisions.template_number, v.template_number || '/') = 1)) "
                "WHERE ksinr = ? AND kvonr IS NULL AND template_number IS NOT NULL",
                (ksinr,),
            )
        self.refresh_abweichung(ksinr=ksinr)

    def refresh_abweichung(self, ksinr: int | None = None, template_number: str | None = None) -> int:
        """Beschluss ↔ Beschlussvorschlag vergleichen (council.ernte.deviation)
        und das Ergebnis an den Beschlüssen ablegen. Zwei Auslöser, weil Vorlage
        und Protokoll in beliebiger Reihenfolge eintreffen: nach save_protocol
        (per ksinr) und nach save_vorlage (per template_number). Nur angenommene
        Beschlüsse — eine Vertagung oder Ablehnung ist keine Textänderung."""
        from council import ernte

        sql = ("SELECT id, template_number, official_text FROM council_decisions "
               "WHERE kind = 'decision' AND outcome = 'accepted' "
               "AND official_text IS NOT NULL AND template_number IS NOT NULL")
        args: tuple = ()
        if ksinr is not None:
            sql += " AND ksinr = ?"
            args = (ksinr,)
        elif template_number is not None:
            # Auch Beschlüsse, die eine REVISION dieser Nummer zitieren
            # („22/0348/1" bei gespeicherter Basis „22/0348") — der
            # get_vorlage_by_nr-Fallback löst sie ohnehin auf (Befund E2).
            base = "/".join(template_number.split("/")[:2])
            sql += " AND (template_number IN (?, ?) OR template_number LIKE ? || '/%')"
            args = (template_number, base, template_number)
        vorschlaege: dict[str, str | None] = {}
        updates = []
        for did, nr, official_text in self._conn.execute(sql, args).fetchall():
            if nr not in vorschlaege:
                v = self.get_vorlage_by_nr(nr)
                vorschlaege[nr] = (v or {}).get("proposed_decision")
            updates.append((ernte.deviation(vorschlaege[nr], official_text), did))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_decisions SET deviation = ? WHERE id = ?", updates)
        return len(updates)

    def mark_protocol_failed(self, ksinr: int, document: dict) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, extracted_at, status) VALUES (?, ?, ?, ?, 'failed')",
                (ksinr, document.get("document_id"), document.get("url"), now),
            )

    def get_decisions(self, ksinr: int) -> list[dict]:
        # Sitzungs-Spalten mitziehen wie in get_decision(): sonst fehlten
        # committee/session_date/protocol_url ausgerechnet hier, obwohl der
        # Frontend-Typ CouncilDecision sie überall zusichert.
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? ORDER BY d.position""",
            (ksinr,),
        ).fetchall()
        return [self._decision_row(r) for r in rows]


    # ------------------------------------------------------------------
    # Vorläufige Ergebnisse aus der Videoaufzeichnung (council/videos.py)




    @staticmethod
    def _decision_row(r) -> dict:
        d = dict(r)
        for key in ("factions", "policy_tags"):
            try:
                d[key] = json.loads(d.get(key) or "[]")
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        # Normalised Antragsteller parties (real factions only, deduped).
        # Multi-Mapping: ein Gruppen-Label („FDP/Volt") zählt für jede Partei.
        d["parties"] = sorted({p for f in d["factions"] for p in parties_for_faction(f)}, key=order_key)
        return d

    # Outcomes grouped into "real votes" vs "reports / no decision".
    _VOTE_OUTCOMES = ("accepted", "rejected", "postponed")
    _REPORT_OUTCOMES = ("noted", "no_decision")

    def decision_ids_for_party(self, party: str) -> list[int]:
        """IDs of main decisions whose Antragsteller includes ``party`` —
        Gruppen-Labels („FDP/Volt") matchen für jede beteiligte Partei."""
        ids = []
        for row in self._conn.execute("SELECT id, factions FROM council_decisions WHERE kind = 'decision'"):
            try:
                arr = json.loads(row["factions"] or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            if any(party in parties_for_faction(f) for f in arr):
                ids.append(row["id"])
        return ids

    def _decision_where(self, query, committee, outcome, faction, date_from, date_to,
                        kind, category, field="", party_ids=None, include_subvotes=False,
                        only_ids=None, district="", location_slug=""):
        """Build the WHERE clause + params shared by search and count."""
        filters: list[str] = []
        params: list = []
        if only_ids is not None:
            # Design 28a/S4: Vorgegebene Beschluss-Menge (die semantischen Treffer
            # eines Nutzer-Themas). Die Zuordnung liegt in ratslotse.sqlite, also in
            # einer anderen Datei — ein JOIN ist unmöglich, der Router reicht
            # die ids herein. Bewusst getrennt von party_ids, damit sich beide
            # Einschränkungen kombinieren lassen.
            if only_ids:
                filters.append(f"d.id IN ({','.join('?' * len(only_ids))})")
                params += list(only_ids)
            else:
                filters.append("0")  # Thema ohne Treffer
        if party_ids is not None:
            # Restrict to a party's decisions (ids precomputed via normalisation).
            if party_ids:
                filters.append(f"d.id IN ({','.join('?' * len(party_ids))})")
                params += party_ids
            else:
                filters.append("0")  # party given but no matches
        if query:
            filters.append("(d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if field:
            filters.append("d.policy_field = ?")
            params.append(field)
        if district:
            # EXISTS vermeidet doppelte Beschlusszeilen bei mehreren Ortslinks.
            # Primäre Ortsbereiche matchen die geometrisch abgeleitete Eltern-ID,
            # feinere Katalogorte ihre exakte stabile Orts-ID bzw. Alt-Aliase.
            place = self.resolve_place(district)
            if place:
                condition, place_params = self._place_location_condition(place)
                filters.append(
                    "EXISTS (SELECT 1 FROM council_decision_locations dl "
                    "JOIN council_locations l ON l.slug = dl.location_slug "
                    f"WHERE dl.decision_id = d.id AND {condition})"
                )
                params += place_params
            else:
                filters.append("0")
        if location_slug:
            filters.append(
                "EXISTS (SELECT 1 FROM council_decision_locations dl "
                "WHERE dl.decision_id=d.id AND dl.location_slug=?)"
            )
            params.append(location_slug)
        if outcome:
            filters.append("d.outcome = ?")
            params.append(outcome)
        if category == "vote":
            filters.append(f"d.outcome IN ({','.join('?' * len(self._VOTE_OUTCOMES))})")
            params += list(self._VOTE_OUTCOMES)
        elif category == "report":
            filters.append(f"(d.outcome IN ({','.join('?' * len(self._REPORT_OUTCOMES))}) OR d.outcome IS NULL)")
            params += list(self._REPORT_OUTCOMES)
        if kind:
            filters.append("d.kind = ?")
            params.append(kind)
        elif not include_subvotes:
            # Design 23a: Änderungsanträge (kind='subvote') tauchen standardmäßig
            # NICHT als eigene Treffer auf — sie hängen als Kontext am Ursprungs-
            # official_text. include_subvotes=True (Filter „einzeln zeigen") bringt sie
            # zurück; ein expliziter kind-Filter behält Vorrang.
            filters.append("d.kind = 'decision'")
        if faction:
            filters.append("d.factions LIKE ?")
            params.append(f"%{faction}%")
        if date_from:
            filters.append("cs.session_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("cs.session_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return where, params

    def search_decisions(
        self,
        query: str = "",
        committee: str = "",
        outcome: str = "",
        faction: str = "",
        date_from: str = "",
        date_to: str = "",
        kind: str = "",
        category: str = "",
        sort: str = "date_desc",
        field: str = "",
        party: str = "",
        limit: int = 50,
        offset: int = 0,
        include_subvotes: bool = False,
        only_ids: list[int] | None = None,
        district: str = "",
        location_slug: str = "",
    ) -> list[dict]:
        """Search extracted decisions, joined with their session (committee + date).
        ``category`` is "vote" (decided) or "report" (zur Kenntnis / no decision).
        ``field`` filters by policy field, ``party`` by normalised Antragsteller;
        ``sort`` ∈ {date_desc, date_asc, faction, importance}."""
        order = {
            "date_asc": "cs.session_date ASC, d.position",
            # Non-empty factions first ('["…' < '[]'), grouped, newest within.
            "faction": "d.factions ASC, cs.session_date DESC",
            # Wichtigste zuerst — mit Alters-Dämpfung. Ohne sie dominieren die
            # Haushaltsbeschlüsse: Sie haben strukturell die höchste Tragweite
            # und verdrängen alles Aktuelle, egal wie alt sie sind. Der Wert
            # halbiert sich nach 2 Jahren (1 / (1 + Alter/2 Jahre)) — bewusst
            # hyperbolisch statt exponentiell, damit historische Großbeschlüsse
            # nach hinten rutschen, aber nicht völlig verschwinden.
            # MAX(0, …) fängt künftig datierte Sitzungen ab (kein Auftrieb).
            "importance": (
                "d.importance IS NULL, "
                "d.importance / (1.0 + MAX(0.0, julianday('now') - julianday(cs.session_date)) / 730.0) DESC, "
                "cs.session_date DESC"
            ),
            # RL-U15: Unterhaltungs-Sortierung — Gesprächswert statt Priorität.
            "interest": "d.interest IS NULL, d.interest DESC, cs.session_date DESC",
        }.get(sort, "cs.session_date DESC, d.position")
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                              date_from, date_to, kind, category, field, party_ids,
                                              include_subvotes=include_subvotes, only_ids=only_ids,
                                              district=district, location_slug=location_slug)
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def backfill_importance(self, only_missing: bool = False) -> int:
        """(Neu-)Berechnung des Wichtigkeits-Scores (``council.importance``) für
        alle Beschlüsse → Spalte ``council_decisions.importance``. Braucht das
        Gremium (JOIN Sitzung) und die Länge der Beratungsfolge (COUNT über
        ``kvonr``). Idempotent; gibt die Zahl aktualisierter Zeilen zurück.
        Läuft in ``scripts/weekly_enrich.py`` (nach dem Scrapen von Beschlüssen
        und Beratungen) und im Erstlauf-Skript ``scripts/score_importance.py``."""
        from council import importance as _imp
        where = "WHERE d.importance IS NULL" if only_missing else ""
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee,
                       (SELECT COUNT(*) FROM council_deliberations b WHERE b.kvonr = d.kvonr) AS n_beratungen
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                {where}"""
        ).fetchall()
        n = 0
        with self._conn:
            for r in rows:
                d = dict(r)
                score = _imp.importance_score(d, n_beratungen=(d.get("n_beratungen") or None))
                # RL-U16: Tragweite (LLM) mischt 50/50 in den Wichtig-Wert,
                # sobald sie befüllt ist — die Heuristik bleibt der Boden.
                # Vor dem ersten rate_impact-Lauf ändert sich damit nichts.
                if d.get("impact") is not None:
                    score = round((score + int(d["impact"])) / 2)
                self._conn.execute(
                    "UPDATE council_decisions SET importance = ? WHERE id = ?", (score, d["id"]))
                n += 1
        return n

    def count_decisions(
        self, query="", committee="", outcome="", faction="", date_from="", date_to="",
        kind="", category="", field="", party="", include_subvotes=False,
        only_ids: list[int] | None = None, district: str = "", location_slug: str = "",
    ) -> int:
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                             date_from, date_to, kind, category, field, party_ids,
                                             include_subvotes=include_subvotes, only_ids=only_ids,
                                             district=district, location_slug=location_slug)
        row = self._conn.execute(
            f"""SELECT COUNT(*) FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
            params,
        ).fetchone()
        return row[0] if row else 0


    def decisions_needing_simple_summary(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne „einfach erklärt"-Kurzfassung (RL-904): nur echte
        Beschlüsse mit substanziellem Beschlusstext, neueste zuerst — so holt
        ein limitierter Backfill die relevantesten zuerst nach."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.simple_summary IS NULL
                   AND d.official_text IS NOT NULL AND length(d.official_text) >= 200
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_simple_summary(self, decision_id: int, text: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET simple_summary = ? WHERE id = ?",
                (text, decision_id),
            )

    # ---- Interessantheit + Fundstück (RL-U11) --------------------------------

    def decisions_needing_interest(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Interessantheits-Score: nur echte Beschlüsse mit
        Titel, neueste zuerst (ein limitierter Backfill holt die relevantesten
        zuerst nach — wie bei „einfach erklärt")."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.amount_eur,
                        cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.interest IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_interest(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET interest = ?, interest_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    def decisions_needing_impact(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Tragweite-Score (RL-U16), neueste zuerst — mit den
        Struktur-Signalen, die der Prompt neben dem Text sehen soll."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.kind,
                        d.amount_eur, d.vote, d.no_votes, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind IN ('decision', 'subvote') AND d.impact IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    #: Titel auf seinen Kern eindampfen, damit „Annahme von Zuwendungen durch
    #: den Rat - Beschluss (ungeändert beschlossen)" und dieselbe Zeile drei
    #: Sitzungen später als EIN Punkt zählen: Klammern raus, Zahlen zu #,
    #: Ergebniszusatz weg.
    _WIEDERKEHR_UNWICHTIG = re.compile(
        r"\([^)]*\)|\b(?:ungeändert|geändert)\s+beschlossen\b|"
        r"\s+-\s+(?:beschluss|bericht|antrag|vorlage)\b", re.IGNORECASE)





    def save_impact(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET impact = ?, impact_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    #: Gewichte des Fundwerts. Erzählbarkeit zählt etwas mehr als Tragweite
    #: — ein Haushaltsbeschluss ist bedeutend, aber kein Fundstück. Die
    #: Sperren darunter sind der eigentliche Hebel: Ohne sie gewinnt die
    #: Kuriosität, weil sie leichter hohe Interest-Werte erreicht.
    FUND_GEWICHT_INTERESSE = 0.55
    FUND_GEWICHT_TRAGWEITE = 0.45
    FUND_MIN_INTERESSE = 50
    FUND_MIN_TRAGWEITE = 50







    def get_decision(self, decision_id: int) -> dict | None:
        row = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.id = ?""",
            (decision_id,),
        ).fetchone()
        return self._decision_row(row) if row else None

    def get_subvotes(self, ksinr: int, parent_item: str) -> list[dict]:
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? AND d.kind = 'subvote' AND d.parent_item = ?
               ORDER BY d.position""",
            (ksinr, parent_item),
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def subvote_summaries(self, pairs: list[tuple[int, str]]) -> dict[tuple[int, str], dict]:
        """Design 23a: je Ursprungsbeschluss (ksinr, item_number) eine kompakte
        Änderungsantrags-Zusammenfassung für die Trefferliste — Anzahl,
        beteiligte Fraktionen, Ergebnisse. So kann die Karte „n Änderungsantrag ·
        Fraktion · angenommen" als Unterzeile zeigen, ohne die subvotes selbst
        als eigene Treffer zu listen."""
        wanted = {(int(k), str(i)) for k, i in pairs if i}
        if not wanted:
            return {}
        ksinrs = sorted({k for k, _ in wanted})
        ph = ",".join("?" * len(ksinrs))
        rows = self._conn.execute(
            f"SELECT ksinr, parent_item, factions, outcome FROM council_decisions "
            f"WHERE kind = 'subvote' AND ksinr IN ({ph}) ORDER BY position",
            ksinrs,
        ).fetchall()
        out: dict[tuple[int, str], dict] = {}
        for r in rows:
            key = (r["ksinr"], r["parent_item"])
            if key not in wanted:
                continue
            e = out.setdefault(key, {"count": 0, "factions": [], "outcomes": []})
            e["count"] += 1
            try:
                for f in json.loads(r["factions"] or "[]"):
                    if f and f not in e["factions"]:
                        e["factions"].append(f)
            except (ValueError, TypeError):
                pass
            if r["outcome"] and r["outcome"] not in e["outcomes"]:
                e["outcomes"].append(r["outcome"])
        return out

    def vorlage_journey(self, template_number: str) -> list[dict]:
        """All sessions where a Vorlage appears on the agenda — its path through
        the committees and the council, oldest first."""
        rows = self._conn.execute(
            """SELECT DISTINCT cs.ksinr, cs.committee, cs.session_date, ci.item_number
               FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.template_number = ?
               ORDER BY cs.session_date""",
            (template_number,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Vorlagen (full text of proposal documents, council.vorlagen) ----------

    def missing_vorlage_kvonrs(self, limit: int | None = None) -> list[int]:
        """kvonrs referenced by agenda items but not ingested yet, newest sessions
        first (so the daily capped run always covers the current business). Rows
        with status 'failed' count as missing — they get retried."""
        sql = (
            "SELECT ci.kvonr FROM council_agenda_items ci "
            "JOIN council_sessions cs ON cs.ksinr = ci.ksinr "
            "WHERE ci.kvonr IS NOT NULL AND ci.kvonr NOT IN "
            "  (SELECT kvonr FROM council_templates WHERE status != 'failed') "
            "GROUP BY ci.kvonr ORDER BY MAX(cs.session_date) DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def save_vorlage(self, row: dict) -> None:
        from council import ernte

        now = datetime.utcnow().isoformat(timespec="seconds")
        # Regex-Ernte direkt beim Speichern — so tragen neue Vorlagen die
        # Felder automatisch, das Backfill-Skript ist nur für den Bestand.
        text = row.get("raw_text") or ""
        aus = ernte.auswirkungen(text)
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_templates "
                "(kvonr, template_number, title, kind, document_id, document_url, "
                " raw_text, n_pages, fetched_at, status, office, climate_impact, "
                " financial_impact, proposed_decision) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["kvonr"], row.get("template_number"), row.get("title"), row.get("kind"),
                 row.get("document_id"), row.get("document_url"), row.get("raw_text"),
                 row.get("n_pages"), now, row.get("status", "ok"),
                 ernte.federfuehrendes_amt(text), aus["klima"], aus["finanzen"],
                 ernte.proposed_decision(text)),
            )
        if row.get("template_number"):
            self.refresh_abweichung(template_number=row["template_number"])

    def mark_vorlage_failed(self, kvonr: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_templates (kvonr, fetched_at, status) "
                "VALUES (?, ?, 'failed')", (kvonr, now),
            )

    def get_vorlage_by_nr(self, template_number: str) -> dict | None:
        """The Vorlage row for a decision's template_number. Falls back to the base
        number ("22/0348/1" → "22/0348") because protocols sometimes cite a
        revision the agenda linked under its base document."""
        nr = (template_number or "").strip()
        if not nr:
            return None
        base = "/".join(nr.split("/")[:2])
        row = self._conn.execute(
            "SELECT * FROM council_templates WHERE template_number IN (?, ?) "
            "ORDER BY (template_number = ?) DESC, kvonr DESC LIMIT 1",
            (nr, base, nr),
        ).fetchone()
        return dict(row) if row else None

    def get_vorlage(self, kvonr: int) -> dict | None:
        """Die Vorlage zu ihrer Ratsinfo-Id. Gegenstück zu get_vorlage_by_nr —
        für alles, was am Vorgang selbst hängt (Design 28a/W1: verfolgen)."""
        row = self._conn.execute(
            "SELECT * FROM council_templates WHERE kvonr = ?", (kvonr,)
        ).fetchone()
        return dict(row) if row else None

    def vorlage_texts_for(self, vorlage_nrs: list[str]) -> dict[str, str]:
        """Batch raw texts for Q&A context enrichment: exact template_number → text
        (only rows that actually have text). Best-effort — no base-nr fallback."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"SELECT template_number, raw_text FROM council_templates "
            f"WHERE template_number IN ({ph}) AND status = 'ok'", nrs,
        ).fetchall()
        return {r["template_number"]: r["raw_text"] for r in rows if r["raw_text"]}

    # --- Anlagen (documents attached to a Vorlage, incl. fraction motions) -----

    def save_anlagen(self, kvonr: int, rows: list[dict]) -> int:
        """Store the Anlagen of one Vorlage and mark it scanned. Existing
        document_ids are kept (their text was ingested earlier); only new ones
        are inserted — so daily re-scans of recent sessions stay cheap."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        new = 0
        with self._conn:
            for r in rows:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO council_attachments "
                    "(document_id, kvonr, label, url, is_motion, applicants, "
                    " raw_text, n_pages, fetched_at, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r["document_id"], kvonr, r.get("label"), r.get("url"),
                     r.get("is_motion", 0),
                     json.dumps(r.get("applicants") or [], ensure_ascii=False),
                     r.get("raw_text"), r.get("n_pages"), now, r.get("status", "listed")),
                )
                new += cur.rowcount
            self._conn.execute(
                "UPDATE council_templates SET attachments_scanned = 1 WHERE kvonr = ?", (kvonr,)
            )
        return new

    def kvonrs_without_anlagen_scan(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose page has not been scanned for Anlagen yet,
        newest first (kvonr is monotonic enough for that)."""
        sql = ("SELECT kvonr FROM council_templates WHERE attachments_scanned = 0 "
               "ORDER BY kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_anlagen_rescan(self, days_back: int = 45) -> list[dict]:
        """Vorlagen on agendas of recent/upcoming sessions — re-scanned daily
        because Änderungsanträge often land on the page days after the Vorlage.
        Returns ``[{kvonr, known_ids}]`` so the fetcher skips known documents."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?""", (cutoff,),
        ).fetchall()
        out = []
        for r in rows:
            known = [k[0] for k in self._conn.execute(
                "SELECT document_id FROM council_attachments WHERE kvonr = ?", (r[0],)).fetchall()]
            out.append({"kvonr": r[0], "known_ids": known})
        return out

    def anlagen_for_vorlage_nr(self, template_number: str) -> list[dict]:
        """Anlagen for a decision's Vorlage (base-nr fallback like
        ``get_vorlage_by_nr``), motions first, each with parsed Antragsteller."""
        v = self.get_vorlage_by_nr(template_number)
        if not v:
            return []
        rows = self._conn.execute(
            "SELECT document_id, label, url, is_motion, applicants, status, is_image "
            "FROM council_attachments WHERE kvonr = ? ORDER BY is_motion DESC, label",
            (v["kvonr"],),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["applicants"] = json.loads(d.get("applicants") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["applicants"] = []
            out.append(d)
        return out

    # --- Beratungsfolge (official per-Vorlage consultation path) ---------------

    def save_beratungen(self, kvonr: int, rows: list[dict]) -> int:
        """Replace the Beratungsfolge of one Vorlage. Full replace per kvonr —
        stations get added over time and results are filled in afterwards, so a
        merge would leave stale planned rows behind."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_deliberations WHERE kvonr = ?", (kvonr,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_deliberations "
                    "(kvonr, date, committee, top, is_public, result, ksinr, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (kvonr, r.get("date"), r.get("committee") or "", r.get("top"),
                     None if r.get("is_public") is None else int(bool(r.get("is_public"))),
                     r.get("result"), r.get("ksinr"), now),
                )
        return len(rows)

    def get_beratungen(self, kvonr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT date, committee, top, is_public, result, ksinr "
            "FROM council_deliberations WHERE kvonr = ? "
            "ORDER BY date IS NULL, date", (kvonr,),
        ).fetchall()
        return [dict(r) for r in rows]

    def geplante_beratungen_fuer(self, kvonrs: list[int]) -> list[dict]:
        """Künftige Stationen (Datum ab heute) der Vorlagen — der „Wie es
        weitergeht"-Stoff.

        Das Datum entscheidet, NICHT das Ergebnis-Feld. Die erste Fassung
        verlangte zusätzlich ein leeres ``result`` — und lieferte damit
        dauerhaft nichts: Bei künftigen Stationen trägt das Feld die geplante
        BEHANDLUNG („Vorberatung", „Kenntnisnahme"), kein Resultat. Am
        11.08.2026 nachgemessen: 22 Termine ab heute, davon 0 mit leerem
        ``result`` — der Block blieb also immer leer, auch im
        Recherche-Bericht. Die Behandlungsart kommt als ``art`` mit; sie sagt
        dem Leser, was dort passieren soll.
        """
        kvonrs = [k for k in kvonrs if k]
        if not kvonrs:
            return []
        ph = ",".join("?" * len(kvonrs))
        rows = self._conn.execute(
            f"SELECT b.kvonr, b.date, b.committee, b.result AS kind, "
            f"       v.template_number, v.title AS template_title "
            f"FROM council_deliberations b JOIN council_templates v ON v.kvonr = b.kvonr "
            f"WHERE b.kvonr IN ({ph}) AND b.date >= date('now') ORDER BY b.date",
            kvonrs).fetchall()
        return [dict(r) for r in rows]

    #: Wörter, die in fast jeder Frage stehen und jede Tagesordnung treffen
    #: würden. „stand" ist der Klassiker: Als Teilwort-Suche traf es
    #: „Sachstandsbericht" und „Baumstandort" und hängte einer Frage nach der
    #: Cäcilienbrücke einen EU-Verordnungs-Termin an (gemessen 11.08.).
    #: „strasse" (gefaltet) ist derselbe Fehler in Grün: Fragen zu einer
    #: Adresse enthalten das Wort fast immer, und es steckt in jedem zweiten
    #: Vorlagentitel — Straßenwidmungen, B-Plan-Sachstände, Straßenbau. Bei
    #: der Stadion-Frage („Maastrichter Straße") hängte es drei fremde
    #: Verkehrsausschuss-Termine an „Wie es weitergeht" (gemessen 19.08.,
    #: Tims Screenshot-Befund — nur „strasse" traf, kein n>=2 gefordert).
    _AUSBLICK_STOPP = {
        "stand", "sachstand", "aktuell", "beschluss", "beschlusse", "beschluesse",
        "stadt", "oldenburg", "planung", "bericht", "vorlage", "thema", "themen",
        "strasse",
    }

    def kommende_beratungen(self, begriffe: list[str], limit: int = 3) -> list[dict]:
        """Kommende Beratungen, deren Vorlagen-Titel zur Frage passt.

        Der Ausblick über die zitierten Vorlagen allein läuft ins Leere, und
        zwar systematisch: Auf der Tagesordnung stehen die Vorlagen, über die
        noch NICHT entschieden wurde — die Suche findet aber Beschlüsse. Am
        11.08.2026 gemessen: 22 Termine ab heute, keiner davon zu einer
        Vorlage mit vorhandenem Beschluss.

        Deshalb hier der zweite Weg: Titel-Abgleich gegen die Suchbegriffe der
        Frage. Deterministisch (kein Modell, kein Embedding), und die Menge ist
        winzig — es geht nur um die nächsten Sitzungen.
        """
        worte = {self._falte_namen(w) for w in begriffe if len(w) >= 5}
        worte -= self._AUSBLICK_STOPP
        if not worte:
            return []
        rows = self._conn.execute(
            "SELECT b.kvonr, b.date, b.committee, b.result AS kind, "
            "       v.template_number, v.title AS template_title "
            "FROM council_deliberations b JOIN council_templates v ON v.kvonr = b.kvonr "
            "WHERE b.date >= date('now') ORDER BY b.date").fetchall()
        bewertet: dict[int, tuple[int, dict]] = {}
        for r in rows:
            titel_worte = re.split(r"[^a-z0-9]+", self._falte_namen(r["template_title"] or ""))
            n = sum(1 for w in worte if any(tw.startswith(w) for tw in titel_worte if tw))
            if not n:
                continue
            # Je Vorlage nur die nächste Station (nach Datum sortiert gelesen).
            if r["kvonr"] not in bewertet:
                bewertet[r["kvonr"]] = (n, dict(r))
        beste = sorted(bewertet.values(), key=lambda t: (-t[0], t[1]["date"]))
        return [d for _n, d in beste[:limit]]

    def kvonrs_without_beratungen(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose Beratungsfolge has never been fetched,
        newest first."""
        sql = ("SELECT v.kvonr FROM council_templates v "
               "WHERE v.kvonr NOT IN (SELECT DISTINCT kvonr FROM council_deliberations) "
               "ORDER BY v.kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_beratungen_rescan(self, days_back: int = 45, days_ahead: int = 120) -> list[int]:
        """Vorlagen whose Beratungsfolge is likely still moving: on an agenda of
        a recent session OR with a planned/unresolved station (future date or
        missing result) — those get re-fetched daily so nachgetragene
        Ergebnisse und neue Stationen ankommen."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?
               UNION
               SELECT DISTINCT b.kvonr FROM council_deliberations b
               WHERE (b.result IS NULL AND b.date <= ?) OR b.date >= ?""",
            (cutoff, horizon, date.today().isoformat()),
        ).fetchall()
        return [r[0] for r in rows]

    # --- Personen-Stammdaten (Mandatsträger + Mitgliedschaften) ----------------



    def stammdaten_stats(self) -> dict:
        one = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "personen": one("SELECT COUNT(*) FROM council_persons"),
            "mitgliedschaften": one("SELECT COUNT(*) FROM council_memberships"),
            "vorlagen_mit_beratungen": one("SELECT COUNT(DISTINCT kvonr) FROM council_deliberations"),
            "beratungen": one("SELECT COUNT(*) FROM council_deliberations"),
            "geplante_beratungen": one(
                "SELECT COUNT(*) FROM council_deliberations WHERE date > date('now')"),
        }

    # --- Quiz (generierte Fragen je Gebiet) -----------------------------------












    # Themen ohne Entität dahinter (kuratierte Spezial-Gebiete) → Anzeigename.
    _THEMA_LABELS = {"haushalt": "Stadt-Haushalt"}


    # --- Herkunft der Finanzzahlen (council.herkunft) ------------------------

    def merke_herkunft(self, h, fetched_at: str | None = None) -> int:
        """Eine :class:`council.herkunft.Herkunft` eintragen und ihre ID
        liefern — der eine Weg, auf dem Herkunft in die Datenbank kommt.

        Idempotent über den inhaltlichen Fingerabdruck: Derselbe Abschnitt
        desselben Dokuments mit derselben Probe bekommt bei jedem Lauf
        dieselbe ID. Was sich ändert, ist `fetched_at` — „zuletzt bestätigt",
        nicht „zuerst gesehen".

        Der Zeitstempel wandert dabei nur **vorwärts** (``MAX``). Beim
        Nachrüsten teilen sich mehrere Tabellen eine Herkunft und bringen je
        einen eigenen Zeitstempel mit; ohne diese Regel gewönne schlicht die
        zuletzt bearbeitete Tabelle, und „zuletzt bestätigt" stünde auf einem
        älteren Datum als eine Zeile, die darauf zeigt.

        Läuft absichtlich **ohne** eigene Transaktion: Der Aufrufer schreibt
        Herkunft und Datenzeilen zusammen, oder gar nicht."""
        jetzt = fetched_at or datetime.utcnow().isoformat(timespec="seconds")
        key = h.key()
        vorhanden = self._conn.execute(
            "SELECT id FROM council_provenance WHERE key = ?",
            (key,)).fetchone()
        if vorhanden:
            self._conn.execute(
                "UPDATE council_provenance SET fetched_at = MAX(fetched_at, ?) "
                "WHERE id = ?", (jetzt, vorhanden[0]))
            return int(vorhanden[0])
        f = h.felder()
        cur = self._conn.execute(
            "INSERT INTO council_provenance (key, kind, document_id, label, url, "
            " citation, page, probe, probe_result, as_of, fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, f["kind"], f["document_id"], f["label"], f["url"],
             f["citation"], f["page"], f["probe"], f["probe_result"],
             f["as_of"], jetzt))
        return int(cur.lastrowid)

    #: Welcher Beschluss zu einem Dokument der maßgebliche ist. Der Rat zuerst
    #: — eine Vorlage läuft durch mehrere Gremien, aber verabschiedet wird sie
    #: dort. Innerhalb eines Gremiums die jüngste Sitzung: Ein vertagter Punkt
    #: kommt wieder, und es gilt, was zuletzt entschieden wurde. Dieselbe
    #: Ordnung nutzt schon `vorlage_beschluesse` (s. u. „committee LIKE 'Rat%'").
    _BESCHLUSS_ORDNUNG = ("ORDER BY (cs.committee LIKE 'Rat%') DESC, "
                          "cs.session_date DESC, d.id DESC")

    def beschluesse_zu_dokumenten(self, dokument_ids: list[int]) -> dict[int, dict]:
        """Zu jedem Dokument der Ratsbeschluss, der es verabschiedet hat.

        Der Weg ist dreigliedrig und steht so nirgends sonst im Code:
        ``council_provenance.document_id`` → ``council_attachments.kvonr`` (an
        welcher Vorlage die Anlage hängt) → ``council_decisions.kvonr`` (was
        der Rat mit dieser Vorlage gemacht hat).

        Damit wird aus „steht im Jahresabschluss 2024" ein „der Rat hat das am
        16.09.2025 beschlossen" — dieselbe Zahl, aber mit dem Vorgang dahinter
        statt nur mit dem Papier.

        **Das Ergebnis wird mitgeliefert, nicht gefiltert.** Ein Dokument, das
        an einer vertagten Vorlage hängt, ist keine Zahl ohne Beleg — es ist
        eine Zahl, deren Vorgang noch läuft, und genau das soll die Seite
        sagen können. Wer hier auf ``outcome = 'accepted'`` einschränkte,
        ließe die interessanteren Fälle stumm verschwinden.

        Eine Anlage ohne Vorlage im Bestand liefert **keinen** Eintrag; die
        Herkunft bleibt dann bei ihrem Dokument, und der Beleg-Chip zeigt, was
        er hat. Erfundene Vorgänge wären der schlimmere Fehler.
        """
        if not dokument_ids:
            return {}
        platz = ",".join("?" * len(dokument_ids))
        try:
            rows = self._conn.execute(
                "SELECT a.document_id, d.id AS decision_id, d.ksinr, d.item_number, "
                "       d.title, d.outcome, d.vote, d.template_number, a.kvonr, "
                "       cs.committee, cs.session_date "
                "FROM council_attachments a "
                "JOIN council_decisions d ON d.kvonr = a.kvonr "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                f"WHERE a.document_id IN ({platz}) AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG,
                list(dokument_ids)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        # Die Ordnung entscheidet: Der erste Treffer je Dokument gewinnt, alle
        # weiteren sind frühere Stationen derselben Vorlage.
        aus: dict[int, dict] = {}
        for r in rows:
            aus.setdefault(int(r["document_id"]), {
                "id": r["decision_id"], "ksinr": r["ksinr"],
                "kvonr": r["kvonr"], "top": r["item_number"],
                "title": (r["title"] or "").strip() or None,
                "outcome": r["outcome"], "vote": r["vote"],
                "template_number": r["template_number"],
                "committee": r["committee"], "date": r["session_date"],
            })
        return aus

    def get_herkunft(self, ids: list[int] | None = None) -> list[dict]:
        """Herkunfts-Datensätze — alle oder eine Auswahl, mit den Erklärsätzen
        zu ihren Proben.

        Die Sätze kommen aus dem Code (``herkunft.PROBEN``) und nicht aus der
        Datenbank: Sie sind Text für Leserinnen und dürfen sich verbessern,
        ohne dass ein Jahrgang neu eingelesen werden muss."""
        from council import herkunft as _h

        try:
            if ids is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_provenance ORDER BY id").fetchall()
            elif not ids:
                return []
            else:
                platz = ",".join("?" * len(ids))
                rows = self._conn.execute(
                    f"SELECT * FROM council_provenance WHERE id IN ({platz}) ORDER BY id",
                    list(ids)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        aus = []
        for r in rows:
            d = dict(r)
            d.pop("key", None)   # interner Fingerabdruck, kein Lesestoff
            d["probes"] = _h.probe_texte(d.get("probe"))
            aus.append(d)
        # Der Ratsvorgang zu allen Dokumenten in EINER Abfrage — nicht je
        # Datensatz eine. Ein Beleg-Apparat zeigt dreizehn Teilhaushalts-Anlagen
        # nebeneinander; dreizehn Nachschläge daraus zu machen wäre ein N+1 an
        # genau der Stelle, an der die Seite ohnehin am meisten holt.
        beschluesse = self.beschluesse_zu_dokumenten(
            sorted({d["document_id"] for d in aus if d.get("document_id")}))
        for d in aus:
            d["official_text"] = beschluesse.get(d.get("document_id"))
        return aus

    def _herkunft_verweistabellen(self) -> list[str]:
        """Jede Tabelle **dieser Datenbank**, die eine ``herkunft_id`` führt.

        Gefragt wird das Schema und nicht ``herkunft.HERKUNFT_TABELLEN``. Die
        Liste dort ist die Arbeitsanweisung fürs Anlegen der Spalte und fürs
        Nachrüsten aus den Altfeldern; sie wird von Hand gepflegt, und der
        Modulkopf von `council/herkunft.py` nennt das Eintragen ausdrücklich
        als Schritt 3 für einen neuen Parser. Genau dieser Schritt ist der,
        den man vergisst.

        Fürs Aufräumen wäre das teuer: Eine Tabelle, die die Liste nicht
        kennt, hat aus Sicht des DELETE **keine** Verweise. Ihre Herkünfte
        gälten als verwaist und fielen weg — während ihre Zeilen weiter auf
        deren Nummern zeigen. Weil die Nummern danach neu vergeben werden
        können, zeigt so eine Zeile am Ende nicht ins Leere (das fiele auf),
        sondern auf ein **fremdes Dokument**. Und ``herkunft_luecken()``
        schwiege dazu, weil auch sie nur die Liste durchging.

        Das Schema kennt die Tabelle trotzdem. Deshalb entscheidet es."""
        aus: list[str] = []
        for (name,) in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            cols = {r[1] for r in self._conn.execute(f'PRAGMA table_info("{name}")')}
            if "herkunft_id" in cols:
                aus.append(name)
        return aus

    def herkunft_aufraeumen(self) -> int:
        """Herkunfts-Datensätze löschen, auf die keine Zeile mehr zeigt.

        Nötig, weil ein erneuter Einlesen-Lauf einen Jahrgang **ersetzt**: Die
        alten Zeilen verschwinden, ihre Herkunft bliebe sonst liegen. Das
        passiert planmäßig einmal beim Nachrüsten (die `unbekannt`-Datensätze
        des Altbestands werden von den echten abgelöst) und danach immer, wenn
        sich eine Fundstelle oder eine Probe ändert.

        Gefragt wird, wer wirklich zeigt — ``_herkunft_verweistabellen()``
        liest das Schema, nicht die handgepflegte Liste. Dort steht auch,
        warum: Eine vergessene Zieltabelle verlöre hier sonst ihre Herkunft.

        Läuft **nur auf Ansage** aus den Ingest-Skripten, nicht beim Öffnen der
        Datenbank: Aufräumen ist eine Schreiboperation, und die gehört nicht in
        den Startpfad eines Webservers."""
        verweise = [f'SELECT herkunft_id FROM "{t}" WHERE herkunft_id IS NOT NULL'
                    for t in self._herkunft_verweistabellen()]
        if not verweise:
            return 0
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_provenance WHERE id NOT IN ("
                + " UNION ".join(verweise) + ")")
        return cur.rowcount

    def herkunft_luecken(self) -> dict[str, int]:
        """Je Zieltabelle: wie viele Zeilen ohne Herkunft dastehen.

        Das Frühwarnsystem der Umstellung. Eine Tabelle, die eine
        ``herkunft_id`` trägt, sie aber nicht füllt, taucht hier nach jedem
        Lauf auf — und die Ingest-Skripte schreiben es ins Protokoll. Genannt
        werden nur Tabellen mit Lücken; eine leere Antwort heißt „jede Zeile
        weiß, woher sie kommt".

        Der Prüfumfang kommt wie beim Aufräumen aus dem Schema: Eine Tabelle,
        die in ``HERKUNFT_TABELLEN`` vergessen wurde, ist damit **nicht**
        stillgestellt, sondern meldet sich hier — sie ist ja gerade der Fall,
        der eine Meldung verdient."""
        aus: dict[str, int] = {}
        for tabelle in self._herkunft_verweistabellen():
            n = self._conn.execute(
                f'SELECT COUNT(*) FROM "{tabelle}" WHERE herkunft_id IS NULL'
            ).fetchone()[0]
            if n:
                aus[tabelle] = n
        return aus

    #: Welches **Dokument** hinter einer Quelle des Haushalts-Bereichs steht —
    #: je Schlüssel die Tabelle, ihre Jahresspalte, eine Einschränkung und die
    #: Alt-Spalte mit der URL.
    #:
    #: Die Schlüssel sind die des Quellenverzeichnisses im Frontend
    #: (``web/frontend/lib/haushalt-quellen.ts``). Das ist Absicht und der
    #: einzige Grund, warum diese Zuordnung hier steht und nicht dort: Welche
    #: Zeile aus welchem Dokument stammt, weiß die Datenbank — das Frontend
    #: kennt nur den Absatz, der eine ganze Seite beschreibt. Wer einen
    #: Schlüssel dort ergänzt, ergänzt ihn hier; wer ihn hier vergisst,
    #: bekommt keinen kaputten Link, sondern den Rückfall auf die statische
    #: Adresse (und das Frontend schreibt dann „im Ratsinformationssystem
    #: suchen" statt „Dokument öffnen").
    #:
    #: Die Alt-Spalte ist die Rückfallebene für Bestände, die vor der
    #: Herkunfts-Vereinheitlichung (#513) geschrieben wurden: Dort steht die
    #: URL an der Datenzeile, aber noch keine ``herkunft_id``. Die beiden
    #: Konzern-Tabellen haben keine — sie sind erst mit der Herkunft
    #: entstanden (s. ``_HERKUNFT_ALTFELDER``).
    _DOKUMENT_QUELLEN: dict[str, tuple[str, str, str | None, str | None]] = {
        "plan":                 ("council_budget", "year", None, "source_url"),
        # Die zwei Ebenen eines Jahresabschlusses stehen in derselben Tabelle
        # und im selben Dokument, tragen aber verschiedene Herkünfte (eigene
        # Abschnitte, eigene Proben). Beide Schlüssel gibt es im Verzeichnis.
        "jahresabschluss":      ("council_income_statement", "year",
                                 "sub_budget_no IS NULL", "source_url"),
        "ergebnisrechnung_thh": ("council_income_statement", "year",
                                 "sub_budget_no IS NOT NULL", "source_url"),
        # Dritte Ebene desselben Dokuments: Abschnitt 4.1, die Kassensicht.
        "cash_flow_statement":       ("council_cash_flow_statement", "year", None, None),
        # Der Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — dieselbe
        # Postengliederung für Jahre ohne Abschluss.
        #
        # Der Filter auf ``kind = 'budget'`` ist hier PFLICHT und keine
        # Verfeinerung: Ein Dokument trägt sein Planjahr UND drei
        # Finanzplanungsjahre, dieselbe Jahreszahl kommt also in drei
        # Haushaltsplänen vor (2026 im Plan 2024 als Vorausschau, im Plan 2025
        # als Vorausschau, im Plan 2026 als Ansatz). Ohne den Filter stünden an
        # einer Ansatz-Zahl bis zu drei Dokumente, und zwei davon meinen etwas
        # anderes. Mit ihm gilt ``year == plan_budget_year``, und es bleibt genau
        # eines.
        "income_budget":     ("council_income_budget", "year",
                                 "t.kind = 'budget'", None),
        # Vierte Ebene: Abschnitt 2.1, die Bilanz. Der älteste Stichtag (2016)
        # stammt aus der Vorjahresspalte des Abschlusses 2017 — er trägt
        # deshalb dessen Dokument, mit eigener Fundstelle.
        "bilanz":               ("council_balance_sheet", "year", None, None),
        # Der einzige Schlüssel, hinter dem je Jahrgang MEHRERE Dokumente
        # stehen: Ein Produkt-Jahrgang verteilt sich auf zwölf bis dreizehn
        # Teilhaushalts-Anlagen (s. finanzquellen.Finanzquelle).
        "teilhaushalt":         ("council_products", "year", None, "source_url"),
        "pruefbericht":         ("council_audit_report_sources", "year", None, "url"),
        "gesamtabschluss":      ("council_group_items", "year", None, None),
        # Nur die geprüften Zeilen: Die Bezugsgröße „Gesamtbetrag des
        # Finanzhaushaltes" steht in derselben Datei, aber an einer anderen
        # Fundstelle und ohne Probe — ohne diesen Filter stünden je Jahrgang
        # zwei Dokumente im Verzeichnis, wo es eines ist.
        "investitionen":        ("council_investments", "year",
                                 "t.level = 'sub_budget'", None),
        # Alle Zeilen eines Jahrgangs teilen sich eine Herkunft; die
        # `gesamt`-Zeile gibt es genau einmal und steht hier für das Dokument.
        "investitionsprogramm": ("council_investment_measures", "year",
                                 "t.level = 'total'", None),
        # Ein Jahrgang, zwei Herkünfte (Teil A und Teil B im selben PDF, aber
        # unter verschiedenen Proben). Beide zeigen auf dieselbe Datei; die
        # Fundstelle unterscheidet sie, und `DISTINCT` fasst sie deshalb nicht
        # zusammen — genau richtig, denn ein Beleg an einer Beamtenzahl soll
        # „Teil A" sagen und nicht „Stellenplan".
        "stellenplan":          ("council_staff_plan", "budget_year", None, None),
        # Der einzige Schlüssel, dessen Jahresspalte NICHT das Datenjahr ist:
        # Ein Bericht liefert fünf Jahrgänge, gehört aber zu genau einem
        # Dokument — und das ist seines.
        "indicators":           ("council_indicators", "report_year", None, None),
        # Die drei Schichten vom 20.08.2026. Sie standen bis zum 21.08. NICHT
        # hier, und man hat es der Seite angesehen: Unter 33 Wirtschaftsplänen
        # aus sieben Betrieben stand eine einzige Quelle, deren Link auf die
        # Startseite des Ratsinformationssystems führte. Der Eintrag hier ist
        # der ganze Unterschied zwischen „kommt aus dem RIS" und „steht in
        # diesem PDF".
        #
        # Wie ``teilhaushalt`` tragen alle drei je Jahrgang MEHRERE Dokumente,
        # und das ist hier keine Eigenheit, sondern der Kern: Ein Jahrgang
        # Wirtschaftsplan besteht aus sieben Plänen von sieben Betrieben, und
        # jeder ist ein eigenes Papier mit eigener Vorlagennummer.
        "wirtschaftsplan":      ("council_business_plans", "year", None, None),
        # Nachträge tragen eine eigene Satzung und ein eigenes Dokument; der
        # Schlüssel unterscheidet sie nicht, die Fundstelle tut es.
        "budget_bylaw":     ("council_budget_bylaw", "year", None, None),
        "fees":            ("council_fees", "year", None, None),
        # Der Haushaltsvollzug trägt je Jahrgang bis zu ACHT Dokumente (vier
        # Stichtage × zwei Haushalte), und jedes ist ein eigenes Papier mit
        # eigener Vorlagennummer — dieselbe Lage wie beim Wirtschaftsplan.
        # Gefiltert wird auf die Summenzeile, damit der Join nicht jede der
        # 42 Zeilen einer Tabelle anfasst; ihre Herkunft ist dieselbe.
        "budget_execution": ("council_budget_execution", "budget_year",
                             "t.is_total = 1", None),
        # Kredite und Zinsen: je Unterrichtung eine Vorlage mit eigener
        # Herkunft — die Papierliste eines Jahrgangs sind die Berichte des
        # Jahres. `document_url` ist die Rückfallebene der Zeile.
        "loans":            ("council_loan_notices", "year", None, "document_url"),
        # Der Liquiditätsstand: je Monat die Grafik, aus der der Wert zuletzt
        # bestätigt wurde — die Papierliste eines Jahrgangs sind die Grafiken.
        "liquidity":        ("council_liquidity", "year", None, "url"),
        # Die Jahresabschlüsse der Eigenbetriebe: je Jahrgang bis zu vier
        # Prüfberichte (ein Betrieb, ein Papier), jede Kennzahl zeigt auf den
        # jüngsten Bericht, der sie nennt.
        "enterprise_accounts": ("council_enterprise_accounts", "year", None, None),
        # Die Änderungslisten zum Haushalt. Wie `wirtschaftsplan` stehen je
        # Jahrgang MEHRERE Papiere dahinter (Verw. I–III und die
        # Beschluss-Datei des AFB) — die Summen-Tabelle trägt je Dokument
        # eine Herkunft, DISTINCT macht daraus die Papierliste des Jahrgangs.
        "aenderungsliste":      ("council_budget_amendments_totals",
                                 "budget_year", None, None),
    }

    #: Jahresquellen, die KEIN Dokument im Ratsinformationssystem haben und
    #: deshalb nicht in ``_DOKUMENT_QUELLEN`` stehen — Downloads von
    #: oldenburg.de, Open Data und die Landesstatistik. Für die Frage „welche
    #: Jahrgänge deckt diese Quelle ab?" zählen sie genauso.
    _WEITERE_JAHRESQUELLEN: dict[str, tuple[str, str, str | None]] = {
        "taxes":     ("council_taxes", "year", None),
        "tax_capacity": ("council_tax_capacity", "year", None),
        "population":   ("council_einwohner", "year", None),
        "schulden":    ("council_debt", "year", None),
        "gebaut":      ("council_investments_actual", "year", None),
        "expense_series": ("council_expense_series", "year", None),
        "buergschaften": ("council_buergschaften", "year", None),
        "anlagenspiegel": ("council_fixed_assets", "year", None),
        "vermoegensgruppen": ("council_vermoegensgruppen", "year", None),
        "integrierte_schulden": ("council_integrated_debt", "year", None),
        "donations":     ("council_donations", "year", None),
        "loans":         ("council_loan_notices", "year", None),
        "liquidity":     ("council_liquidity", "year", None),
        "enterprise_accounts": ("council_enterprise_accounts", "year", None),
        "tax_plan":  ("council_tax_plan", "year", None),
        "tax_rates":  ("council_tax_rates", "year", None),
    }



    # --- Stadt-Haushalt (council.haushalt) -----------------------------------

    def save_haushalt(self, year: int, rows: list[dict], herkunft) -> int:
        """Ergebnishaushalt eines Jahres speichern — ersetzt den bisherigen
        Stand des Jahres komplett (Re-Ingest idempotent).

        ``herkunft`` ist eine :class:`council.herkunft.Herkunft` und hat den
        früheren ``source_url``-String abgelöst: Eine URL allein sagt nicht,
        an welcher Stelle eines 300-Seiten-PDFs gelesen wurde und was die
        Zahlen absichert. ``source_url`` steht weiter in der Tabelle und wird
        aus derselben Angabe gefüllt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_budget WHERE year = ?", (year,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_budget (year, area, revenues, expenses, "
                    " result, is_total, source_url, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (year, r["area"], r.get("revenues"), r.get("expenses"),
                     r.get("result"), int(r.get("is_total", 0)),
                     herkunft.url, now, hid))
        return len(rows)



    def save_steuereinnahmen(self, rows: list[dict], herkunft) -> int:
        """Ist-Steuereinnahmen (year, art, betrag) ersetzen — Re-Ingest idempotent."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_taxes "
                "(year, kind, amount, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?)",
                [(r["year"], r["kind"], r.get("amount"), herkunft.url, now, hid)
                 for r in rows])
        return len(rows)


    def save_steuerkraft(self, rows: list[dict], herkunft) -> int:
        """Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr ersetzen.

        Anders als die Nachbar-Methoden räumt diese auch auf: Der Datensatz
        1106 liefert die **ganze** Reihe bei jedem Lauf, und seit der
        Jahres-Korrektur (``haushalt._STEUERKRAFT_VERSATZ``) trägt jede Zeile
        ein anderes Jahr als beim letzten Mal. Ein reines INSERT OR REPLACE
        ließe genau einen Jahrgang als Leiche zurück — den ältesten, den es
        nach dem Rücken nicht mehr gibt. Der stünde dann mit den Beträgen
        seines Nachfolgers in der Tabelle, und niemand käme je darauf.

        Eine leere Lieferung räumt **nichts** ab: Ein misslungener Download
        darf den Bestand nicht löschen. Der Ingest bricht in dem Fall ohnehin
        vorher ab, aber die Methode soll das auch allein aushalten.
        """
        if not rows:
            return 0
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_capacity "
                "(year, tax_index, tax_capacity_per_capita, allocations, allocations_per_capita, "
                " source_url, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?)",
                [(r["year"], r.get("tax_index"), r.get("tax_capacity_per_capita"),
                  r.get("allocations"), r.get("allocations_per_capita"),
                  herkunft.url, now, hid) for r in rows])
            years = [r["year"] for r in rows]
            self._conn.execute(
                "DELETE FROM council_tax_capacity WHERE year NOT IN "
                f"({','.join('?' * len(years))})", years)
        return len(rows)

    def save_einwohner(self, rows: list[dict], herkunft) -> int:
        """Einwohnerzahlen je Jahr ersetzen (idempotent)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_einwohner "
                "(year, population, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?)",
                [(r["year"], r["population"], herkunft.url, now, hid) for r in rows])
        return len(rows)


    def save_ergebnisrechnung(self, year: int, posten: list[dict], herkunft,
                              sub_budget_no: int | None = None, sub_budget_name: str | None = None,
                              ersetzen: bool = True) -> int:
        """Ergebnisrechnung einer Ebene speichern — ohne ``sub_budget_no`` die
        Gesamtrechnung, sonst der jeweilige Teilhaushalt.

        ``ersetzen`` löscht vorher die betroffene Ebene dieses Jahres; beim
        Einlesen mehrerer Teilhaushalte nacheinander bleibt es an.

        ``herkunft`` steht, wo früher ``label, url`` standen. Die beiden
        Ebenen dieses Dokuments bekommen bewusst **verschiedene** Herkünfte:
        Sie stehen an verschiedenen Stellen des Jahresabschlusses und sind
        durch verschiedene Proben gedeckt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            if ersetzen:
                if sub_budget_no is None:
                    self._conn.execute(
                        "DELETE FROM council_income_statement WHERE year = ? AND sub_budget_no IS NULL",
                        (year,))
                else:
                    self._conn.execute(
                        "DELETE FROM council_income_statement WHERE year = ? AND sub_budget_no = ?",
                        (year, sub_budget_no))
            self._conn.executemany(
                "INSERT INTO council_income_statement (year, sub_budget_no, sub_budget_name, nr, label, "
                " prior_year, budgeted, plan, plan_kind, result, deviation, is_total, "
                " source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                # `plan` fällt auf `ansatz` zurück, wenn der Aufrufer keine
                # eigene Bezugsgröße mitbringt — und zwar auch bei
                # ausdrücklichem ``None``. `p.get("plan", …)` täte das nicht:
                # Der Vorgabewert greift nur bei fehlendem Schlüssel. Dieselbe
                # Falle stand im Lesepfad (s. `get_plan_ist.plan_von`).
                [(year, sub_budget_no, sub_budget_name, p["nr"], p["label"], p.get("prior_year"),
                  p.get("budgeted"),
                  p.get("budgeted") if p.get("plan") is None else p.get("plan"),
                  p.get("plan_kind"),
                  p.get("result"), p.get("deviation"),
                  p.get("is_total", 0), herkunft.label, herkunft.url, now, hid)
                 for p in posten])
        return len(posten)

    def save_abweichungsgruende(self, year: int, gruende: list[dict], herkunft) -> int:
        """Erläuterungen zu den Plan/Ist-Abweichungen eines Jahrgangs
        ersetzen. Übergeben wird nur, was die Rechenprobe bestanden hat."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_variance_reasons WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_variance_reasons (year, nr, label, "
                " delta_meur, percent, text, source_label, source_url, fetched_at, "
                " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(year, g["nr"], g["label"], g.get("delta_meur"), g.get("percent"),
                  g["text"], herkunft.label, herkunft.url, now, hid) for g in gruende])
        return len(gruende)


    def save_pruefbericht_quelle(self, year: int, herkunft,
                                 n_pages: int | None, readable: bool) -> None:
        """Fundstelle des RPA-Schlussberichts eines Jahrgangs merken."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_audit_report_sources "
                "(year, label, url, n_pages, readable, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (year, herkunft.label, herkunft.url, n_pages,
                 1 if readable else 0, now, hid))


    def get_plan_ist(self, year: int) -> dict:
        """„Geplant und geworden" eines Jahres: die Summenzeilen (Erträge 12,
        Aufwendungen 20) für die Kernverwaltung und je Teilhaushalt.

        Liefert ``{gesamt: {...}, bereiche: [...]}`` — die Bereiche nach
        geplanten Aufwendungen absteigend, damit die größten oben stehen."""
        rows = [dict(r) for r in self._conn.execute(
            "SELECT sub_budget_no, sub_budget_name, nr, budgeted, plan, plan_kind, result, deviation "
            "FROM council_income_statement WHERE year = ? AND nr IN (12, 20) "
            "ORDER BY sub_budget_no, nr", (year,))]

        def plan_von(r: dict):
            """Bezugsgröße der Abweichung — mit Rückfall auf den Ansatz.

            Der Rückfall ist kein Schönheitsfehler, sondern der Normalfall für
            jeden Bestand, der vor #510 geschrieben wurde: `plan` und
            `plan_kind` kamen damals per ALTER TABLE dazu, und ALTER TABLE füllt
            nichts nach — alle vorhandenen Zeilen tragen dort seither NULL,
            obwohl `budgeted` danebensteht und richtig ist. Auf `/haushalt/
            plan-ist` hieß das: „Die Planwerte der Gesamtrechnung konnten wir
            für diesen Jahrgang nicht auslesen" für **jeden** Jahrgang, bis
            jemand von Hand neu einliest.

            Bis 16.08.2026 stand hier ``r.get("plan", r.get("budgeted"))``. Das
            sieht aus wie genau dieser Rückfall und ist keiner: `r` kommt aus
            einem ``SELECT plan, …``, der Schlüssel ist also **immer** da, und
            `dict.get` greift seinen Vorgabewert nur bei fehlendem Schlüssel
            ab — nie bei ``None``. Der Zweig war toter Code."""
            value = r.get("plan")
            return r.get("budgeted") if value is None else value

        def bauen(part: list[dict]) -> dict:
            e = next((r for r in part if r["nr"] == 12), {})
            a = next((r for r in part if r["nr"] == 20), {})
            # `plan` ist die Bezugsgröße der Abweichung, `ansatz` der
            # ursprüngliche Haushaltsansatz — 2018 und 2020 fallen auseinander.
            return {"revenues_planned": plan_von(e),
                    "revenues_budgeted": e.get("budgeted"),
                    "revenues_actual": e.get("result"),
                    "expenses_planned": plan_von(a),
                    "expenses_budgeted": a.get("budgeted"),
                    "expenses_actual": a.get("result"),
                    "plan_kind": a.get("plan_kind") or e.get("plan_kind")}

        gesamt = [r for r in rows if r["sub_budget_no"] is None]
        bereiche = []
        for nr in sorted({r["sub_budget_no"] for r in rows if r["sub_budget_no"] is not None}):
            part = [r for r in rows if r["sub_budget_no"] == nr]
            bereiche.append({"sub_budget_no": nr, "sub_budget_name": part[0]["sub_budget_name"], **bauen(part)})
        bereiche.sort(key=lambda b: -(b["expenses_planned"] or 0))
        return {"year": year, "gesamt": bauen(gesamt) if gesamt else None, "bereiche": bereiche}




    # --- Finanzrechnung der Kernverwaltung (council.finanzberichte) ----------

    def save_finanzrechnung(self, year: int, zeilen: list[dict], herkunft) -> int:
        """Die Kassensicht eines Jahrgangs ersetzen.

        Übergeben wird nur, was ``finanzberichte.finanzprobe`` durchgelassen
        hat — die Funktion streicht Ketten, die nicht aufgehen, schon vorher
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_cash_flow_statement WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_cash_flow_statement (year, nr, role, label, "
                " prior_year, budgeted, plan, plan_kind, result, deviation, "
                " authorization, is_total, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, z["nr"], z.get("role"), z["label"], z.get("prior_year"),
                  z.get("budgeted"), z.get("plan"), z.get("plan_kind"), z.get("result"),
                  z.get("deviation"), z.get("authorization"),
                  z.get("is_total", 0), hid, now)
                 for z in zeilen])
        return len(zeilen)


    def finanzrechnung_jahre(self) -> list[int]:
        """Jahre mit eingelesener Finanzrechnung (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_cash_flow_statement ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Bilanz der Stadt (council.bilanz) -----------------------------------

    def save_bilanz(self, year: int, posten: list[dict], herkunft) -> int:
        """Einen Bilanzstichtag ersetzen.

        Übergeben wird nur, was ``bilanz.bilanzprobe`` durchgelassen hat —
        eine Bilanz, deren Seiten nicht aufgehen, kommt dort gar nicht erst
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_balance_sheet WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_balance_sheet (year, role, page, level, nr, "
                " label, value, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year, p["role"], p["page"], p["level"], p.get("nr"),
                  p["label"], p["value"], hid, now) for p in posten])
        return len(posten)




    def save_bilanz_erlaeuterungen(self, year: int, abschnitte: list[dict],
                                   herkunft) -> int:
        """Die Erläuterungen des Anhangs zu einem Jahrgang ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_balance_sheet_notes WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_balance_sheet_notes (year, role, nr, "
                " heading, text, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(year, a["role"], a["nr"], a["heading"], a["text"], hid, now)
                 for a in abschnitte])
        return len(abschnitte)



    # --- Gesamtergebnishaushalt (Planjahre, council.ergebnishaushalt) --------

    def save_ergebnishaushalt(self, plan_budget_year: int, zeilen: list[dict],
                              herkunft) -> int:
        """Einen Haushaltsplan-Jahrgang ersetzen — Ansatz und Finanzplanung
        zusammen, weil sie aus **einer** Tabelle eines Dokuments stammen.

        Gelöscht wird nach ``plan_budget_year``, nicht nach ``year``: Was der
        Haushalt 2026 über 2027 sagt, gehört ihm; was der Haushalt 2027 über
        2027 sagt, ist eine andere Zeile und bleibt stehen.

        Übergeben wird nur, was beide Pflicht-Proben bestanden hat — diese
        Methode prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_income_budget WHERE plan_budget_year = ?",
                (plan_budget_year,))
            self._conn.executemany(
                "INSERT INTO council_income_budget (plan_budget_year, year, kind, nr, "
                " label, amount, is_total, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(plan_budget_year, z["year"], z["kind"], z["nr"], z["label"],
                  z["amount"], 1 if z.get("is_total") else 0, now, hid)
                 for z in zeilen])
        return len(zeilen)

    def ergebnishaushalt_jahrgaenge(self) -> list[int]:
        """Haushaltsplan-Jahrgänge, die eingelesen sind (aufsteigend).

        Der **Plan**-Jahrgang, nicht die Jahre darin: Ein Dokument trägt sein
        Planjahr und drei Finanzplanungsjahre, und vollständig ist es erst,
        wenn alle vier dastehen — was ``save_ergebnishaushalt`` zusammen
        schreibt oder gar nicht."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT plan_budget_year FROM council_income_budget "
                "ORDER BY plan_budget_year")]
        except sqlite3.OperationalError:
            return []



    # --- Stellenplan (council.stellenplan) ----------------------------------

    def save_stellenplan(self, budget_year: int, part: str, zeilen: list[dict],
                         herkunft, as_of_date: str | None = None) -> int:
        """Einen Teil eines Stellenplan-Jahrgangs ersetzen.

        Ersetzt wird nach ``(budget_year, part)``, nicht nach Jahrgang: Die
        beiden Teile stehen zwar im selben PDF, kommen aber einzeln durch
        ihre Proben — im Jahrgang 2026 ist Teil B im Textextrakt unlesbar,
        Teil A tadellos. Wer nach Jahrgang löschte, risse mit dem einen den
        anderen mit.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode
        prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_staff_plan WHERE budget_year = ? AND part = ?",
                (budget_year, part))
            self._conn.executemany(
                "INSERT INTO council_staff_plan (budget_year, part, row_no, kind, "
                " pay_group, seq_no, label, pay_grade, positions_planned, "
                " positions_prior_year, filled, filled_by_officials, filled_by_employees, "
                " vacant, as_of_date, consistent, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, part, i, z["kind"], z.get("pay_group"), z.get("seq_no"),
                  z["label"], z.get("pay_grade"), z["positions_planned"],
                  z["positions_prior_year"], z["filled"], z.get("filled_by_officials"),
                  z.get("filled_by_employees"), z["vacant"], as_of_date,
                  1 if z.get("consistent", 1) else 0, now, hid)
                 for i, z in enumerate(zeilen)])
        return len(zeilen)



    # --- Investitionen des Finanzhaushalts (council.investitionen) ----------

    def save_investitionen(self, year: int, zeilen: list[dict], gesamt: dict,
                           herkunft, finanzhaushalt: dict | None = None,
                           herkunft_finanzhaushalt=None) -> int:
        """Einen Jahrgang Investitionen ersetzen — Teilhaushalte und
        Summenzeile zusammen, weil sie aus **einer** Tabelle stammen und die
        Summenzeile das Ziel der Rechenprobe ist.

        Zwei Herkünfte, weil es zwei verschiedene Aussagen sind: Die
        Investitionen sind durch die Summenprobe der Datei gedeckt, der
        *Gesamtbetrag des Finanzhaushaltes* ist es nicht (er zählt die laufende
        Verwaltungstätigkeit mit, und nichts in der Datei summiert sich auf
        ihn). Eine gemeinsame Herkunft behauptete für ihn eine Probe, die es
        nicht gibt.

        Übergeben wird nur, was die Probe bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investments WHERE year = ?", (year,))
            werte = [(year, "sub_budget", z["sub_budget_no"], z["label"],
                      z["inflows"], z["outflows"], now, hid)
                     for z in zeilen]
            werte.append((year, "investments", 0, gesamt["label"],
                          gesamt["inflows"], gesamt["outflows"], now, hid))
            if finanzhaushalt:
                hid_fh = (self.merke_herkunft(herkunft_finanzhaushalt, fetched_at=now)
                          if herkunft_finanzhaushalt is not None else hid)
                werte.append((year, "financial_budget", 0,
                              finanzhaushalt["label"],
                              finanzhaushalt["inflows"],
                              finanzhaushalt["outflows"], now, hid_fh))
            self._conn.executemany(
                "INSERT INTO council_investments (year, level, sub_budget_no, label, "
                " inflows, outflows, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)", werte)
        return len(werte)



    # --- Investitionsprogramm (Anlage 004 des Haushaltsplans) ---------------

    def save_investitionsprogramm(self, year: int, gelesen: dict,
                                  herkunft) -> int:
        """Einen Jahrgang Investitionsmaßnahmen ersetzen.

        Maßnahmen und beide Summenebenen zusammen, weil sie aus **einem**
        Dokument stammen und die Summen die Ziele der Rechenproben sind. Eine
        Herkunft für alles: Anders als beim Finanzhaushalt gibt es hier keine
        Zeile, die von den Proben nicht gedeckt wäre — was nicht aufgeht, kommt
        gar nicht erst herein (``investitionsprogramm.lies``).

        Übergeben wird nur, was die Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investment_measures WHERE year = ?",
                (year,))
            werte = []
            for nr, a in sorted(gelesen["abschnitte"].items()):
                for m in a["massnahmen"]:
                    werte.append((year, "measure", nr, m["code"],
                                  m["label"], m["grand_total"],
                                  " · ".join(m.get("details") or []) or None,
                                  now, hid))
                werte.append((year, "sub_budget", nr, "", a["name"],
                              a["summe"], None, now, hid))
            werte.append((year, "total", 0, "", "Gesamtinvestitionsprogramm",
                          gelesen["kopfsumme"], None, now, hid))
            self._conn.executemany(
                "INSERT INTO council_investment_measures "
                "(year, level, sub_budget_no, code, label, grand_total, "
                " details, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                werte)
        return len(werte)



    # --- Konzern Stadt Oldenburg (konsolidierter Gesamtabschluss) -----------

    def save_konzern_jahrgang(self, year: int, posten: list[dict],
                              entity: list[dict], herkunft,
                              herkunft_traeger=None) -> dict:
        """Einen Jahrgang des Gesamtabschlusses ersetzen — beide Ebenen.

        Zusammen, weil sie aus **einem** Dokument stammen und ein halb
        geschriebener Jahrgang für den nächsten Lauf wie ein fertiger aussähe.
        Aber mit **zwei** Herkünften: Die Posten stehen in Abschnitt 3.2, die
        Trägeraufstellung in 4.1.1, und sie sind durch verschiedene Proben
        gedeckt. Fehlt ``herkunft_traeger``, gilt dieselbe für beide.

        Übergeben wird nur, was die Proben bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            hid_traeger = (self.merke_herkunft(herkunft_traeger, fetched_at=now)
                           if herkunft_traeger is not None else hid)
            self._conn.execute("DELETE FROM council_group_items WHERE year = ?", (year,))
            self._conn.execute("DELETE FROM council_group_entities WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_group_items (year, nr, label, role, "
                " amount, prior_year, is_total, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year, p["nr"], p["label"], p.get("role"), p["amount"],
                  p.get("prior_year"), 1 if p.get("is_total") else 0, now, hid)
                 for p in posten])
            self._conn.executemany(
                "INSERT INTO council_group_entities (year, kind, entity_key, entity, "
                " amount_keur, prior_year_keur, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(year, t["kind"], t["entity_key"], t["entity"], t["amount_keur"],
                  t.get("prior_year_keur"), now, hid_traeger) for t in entity])
        return {"posten": len(posten), "entity": len(entity)}




    # --- Beteiligungsbericht (§ 151 NKomVG) ---------------------------------

    def save_beteiligungsbericht(self, stammdaten: list[dict], texte: list[dict],
                                 indicators: list[dict],
                                 personen: list[dict] | None = None,
                                 eigentuemer: list[dict] | None = None) -> dict:
        """Den **ganzen** Bestand des Beteiligungsberichts ersetzen.

        Ungewöhnlich für diesen Store, und mit Grund: Die Überlappungsprobe
        spannt sich über mehrere Berichte. Ob der Wert für 2022 gilt,
        entscheidet nicht der Bericht 2022 allein, sondern sein Vergleich mit
        2023 und 2024 — und `n_reports` (in wie vielen er steht) ändert sich,
        sobald ein neuer Jahrgang dazukommt. Jahrgangsweise zu schreiben
        hieße, diese Zahl in jeder zweiten Zeile veralten zu lassen.

        Das Einlesen liest deshalb immer alle vorhandenen Berichte und
        übergibt das Ergebnis in einem Stück. Übergeben wird nur, was die
        Proben bestanden hat — diese Methode prüft nichts nach, sie schreibt.

        Jede Liste bringt ihre eigene ``herkunft`` je Zeile mit: Die Kennzahlen
        eines Jahres stammen aus einem anderen Bericht als die Texte daneben,
        und die Probe ist eine andere."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for tabelle in ("council_company_indicators",
                            "council_company_texts",
                            "council_company_people",
                            "council_company_owners",
                            "council_companies"):
                self._conn.execute(f"DELETE FROM {tabelle}")
            for z in stammdaten:
                self._conn.execute(
                    "INSERT INTO council_companies (report_year, company, "
                    " name, classification, page, consolidated_key, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["name"], z["classification"],
                     z.get("page"), z.get("consolidated_key"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in texte:
                self._conn.execute(
                    "INSERT INTO council_company_texts (report_year, "
                    " company, section, text, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["section"], z["text"],
                     now, self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in indicators:
                self._conn.execute(
                    "INSERT INTO council_company_indicators (company, "
                    " indicator, year, value, unit, report_year, n_reports, "
                    " fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (z["company"], z["indicator"], z["year"], z["value"],
                     z["unit"], z["report_year"], z["n_reports"], now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in personen or []:
                self._conn.execute(
                    "INSERT INTO council_company_people (report_year, "
                    " company, sort_order, committee, name, position, "
                    " chair_role, note, roles_assignable, fetched_at, "
                    " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["sort_order"],
                     z["committee"], z["name"], z.get("position"), z.get("chair_role"),
                     z.get("note"), int(bool(z["roles_assignable"])), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in eigentuemer or []:
                self._conn.execute(
                    "INSERT INTO council_company_owners (report_year, "
                    " company, sort_order, name, amount_eur, "
                    " share_pct, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["sort_order"],
                     z["name"], z.get("amount_eur"), z.get("share_pct"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
        return {"gesellschaften": len(stammdaten), "texte": len(texte),
                "indicators": len(indicators), "personen": len(personen or []),
                "eigentuemer": len(eigentuemer or [])}









    # --- Schuldenstand (Tabelle 1108 des Statistischen Jahrbuchs) ------------

    def save_schulden(self, zeilen: list[dict], herkunft) -> int:
        """Schuldenjahrgänge ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen. Wer wirklich aufräumen will, tut das von Hand.

        Übergeben wird nur, was seine Probe bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Was die Aufteilung verloren hat
        (Fall 2022, s. ``council/schulden.py``), kommt hier mit ``None`` in
        den vier Artenspalten an und bleibt auch so stehen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_debt "
                "(year, credit_market, special_funds, public_authorities, "
                " municipal_enterprises, total, per_capita, breakdown_rejected, "
                " revised, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z.get("credit_market"), z.get("special_funds"),
                  z.get("public_authorities"), z.get("municipal_enterprises"),
                  z["total"], z.get("per_capita"),
                  z.get("breakdown_rejected"), int(bool(z.get("revised"))),
                  hid, now) for z in zeilen])
        return len(zeilen)


    # --- Lange Ausgabenreihe (Datensatz 1102, seit 1972) --------------------

    def save_ausgabenreihe(self, zeilen: list[dict], herkunft) -> int:
        """Jahrgänge der langen Ausgabenreihe ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an einer Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (dieselbe Regel wie bei ``save_schulden``).

        Übergeben wird nur, was seine Proben bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Welche Proben das waren, kommt als
        Liste in ``probes`` an und wird kommagetrennt gespeichert; die Namen
        stehen in ``council/herkunft.PROBEN``.

        Aufgerufen wird sie einmal je Herkunfts-Gruppe, nicht einmal für die
        ganze Reihe: Ein Jahrgang von 1974 steht nur im Open-Data-Portal, einer
        von 2024 zusätzlich im Jahrbuch und im Jahresabschluss — das sind
        verschiedene Belege, und jeder soll für seine Zeilen gelten."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_expense_series "
                "(year, accounting_system, amount, source, probes, conflict_amount, "
                " conflict_source, revised, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z["accounting_system"], z["amount"], z["source"],
                  ",".join(z.get("probes") or []), z.get("conflict_amount"),
                  z.get("conflict_source"), int(bool(z.get("revised"))),
                  hid, now) for z in zeilen])
        return len(zeilen)


    # --- Bürgschaften: wofür die Stadt geradesteht --------------------------

    def save_wirtschaftsplan(self, plan, herkunft) -> int:
        """Einen Wirtschaftsplan speichern — ein Betrieb, ein Haushaltsjahr.

        Aufgerufen wird sie **je Plan** und nicht für eine ganze Lieferung:
        Jeder Jahrgang steht in seiner eigenen Ratsvorlage, also hat jeder
        seine eigene Herkunft. Ein gemeinsamer Beleg wäre für sieben von acht
        Zeilen der falsche — dieselbe Überlegung wie bei
        ``save_buergschaften``.

        ``plan`` ist ein :class:`council.wirtschaftsplan.Wirtschaftsplan`; die
        Proben stehen dort und werden nicht hier noch einmal gerechnet.
        """
        # Die Proben kommen aus der HERKUNFT und stehen nicht hier: Welche
        # gelaufen sind, weiß der Parser, und es sind je nach Quelle andere —
        # der Beschlusstext prüft anders als der Erfolgsplan einer Anlage. Eine
        # feste Liste an dieser Stelle behauptete für jede Zeile dieselben.
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_business_plans "
                "(enterprise, year, enterprise_name, template_number, revenues, expenses, "
                " taxes, result, capital_plan, investments, commitments, "
                " draft_date, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan.enterprise, plan.year, plan.enterprise_name, plan.template_number,
                 plan.revenues, plan.expenses, plan.taxes, plan.result,
                 plan.capital_plan, plan.investments, plan.commitments,
                 plan.draft_date, probes, hid, now))
        return 1

    def save_gebuehrenbedarf(self, bedarf, herkunft) -> int:
        """Einen Gebührenbereich eines Jahrgangs speichern.

        Je Bereich und Jahr eine Zeile, und je Zeile eine eigene Herkunft: Die
        drei Bereiche stehen in drei Anlagen und prüfen sich einzeln — ein
        gemeinsamer Beleg wäre für zwei von drei der falsche.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_fees "
                "(year, area, area_name, cost_calculation, deductions, "
                " costs_to_cover, reference_quantity, reference_unit, fee, "
                " fee_proposed, template_number, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bedarf.year, bedarf.area, bedarf.area_name,
                 bedarf.cost_calculation, bedarf.deductions,
                 bedarf.costs_to_cover, bedarf.reference_quantity,
                 bedarf.reference_unit, bedarf.fee,
                 bedarf.fee_proposed, bedarf.template_number,
                 probes, hid, now))
        return 1


    def save_gebuehrensaetze(self, saetze, herkuenfte) -> int:
        """Die vollständigen zwölf Tarife eines Vorschlagsjahres ersetzen."""
        saetze, herkuenfte = list(saetze), list(herkuenfte)
        if len(saetze) != len(herkuenfte):
            raise ValueError("Jeder Gebührensatz braucht genau eine Herkunft")
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for satz, herkunft in zip(saetze, herkuenfte, strict=True):
                probes = herkunft.probe
                if not isinstance(probes, str):
                    probes = ",".join(probes)
                hid = self.merke_herkunft(herkunft, fetched_at=now)
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_fee_rates "
                    "(year, key, area, label, amount, unit, "
                    " prior_year, change_pct, template_number, probes, "
                    " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (satz.year, satz.key, satz.area, satz.label,
                     satz.amount, satz.unit, satz.prior_year,
                     satz.change_pct, satz.template_number, probes, hid, now))
        return len(saetze)


    def gebuehren_jahre(self) -> list[int]:
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_fees ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def save_haushalt_aenderungen(self, document_id: int, liste: str,
                                  result, herkunft) -> int:
        """Eine geprüfte Änderungsliste speichern — Positionen und Summen.

        Ersetzt wird je ``(budget_year, liste)``: Ein Jahrgang hat genau ein
        Verw.-I-Dokument usw. Ob zwei ANLAGEN dasselbe Dokument sind (die
        2021er-Beschlussdatei liegt doppelt im Bestand), entscheidet der
        Ingest VOR dem Speichern — diese Methode prüft nichts nach, sie
        schreibt, was seine Proben bestanden hat (council/aenderungslisten.py).
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        budget_year = result.budget_year
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_budget_amendments",
                            "council_budget_amendments_totals"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE budget_year = ? AND list_key = ?",
                    (budget_year, liste))
            self._conn.executemany(
                "INSERT INTO council_budget_amendments (budget_year, list_key, "
                " year, seq, sub_budget, page_draft, product, label, "
                " revenue, expense, explanation, author, document_id, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, z.year, z.seq, z.sub_budget, z.page_draft,
                  z.product, z.label, z.revenue, z.expense,
                  z.explanation, z.author, document_id, hid, now)
                 for z in result.zeilen])
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_totals (budget_year, "
                " list_key, year, kind, label, revenues, expenses, balance, "
                " own, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, s.year, s.typ, s.label, s.revenues,
                  s.expenses, s.balance,
                  1 if result.eigene_zeile.get(s.year) == s.label else 0,
                  document_id, hid, now) for s in result.summen])
        return len(result.zeilen)

    def save_haushalt_aenderungen_fhh(self, document_id: int, liste: str,
                                      result, herkunft) -> int:
        """Eine FHH-Änderungsliste speichern — Positionen und Zusammenstellung.

        Wie beim Ergebnishaushalt: Die Proben liefen im Parser
        (council/aenderungslisten_fhh.py), hier wird nur geschrieben. Je
        (Jahrgang, Liste) wird gelöscht und neu geschrieben, ein zweiter Lauf
        ersetzt den Stand also gefahrlos.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        budget_year = result.budget_year
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_budget_amendments_cash",
                            "council_budget_amendments_cash_totals"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE budget_year = ? AND list_key = ?",
                    (budget_year, liste))
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_cash (budget_year, "
                " list_key, year, seq, sub_budget, page_draft, product, label, "
                " planned_draft, inflow, outflow, commitment_authorizations, planned_new, "
                " explanation, author, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, z.year, z.seq, z.sub_budget, z.page_draft,
                  z.product, z.label, z.planned_draft, z.inflow,
                  z.outflow, z.commitment_authorizations, z.planned_new, z.explanation, z.author,
                  document_id, hid, now) for z in result.zeilen])
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_cash_totals (budget_year, "
                " list_key, year, kind, label, inflows, outflows, balance, "
                " commitment_authorizations, own, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, s.year, s.typ, s.label, s.inflows,
                  s.outflows, s.balance, s.commitment_authorizations,
                  1 if result.eigene_zeile.get(s.year) == s.label else 0,
                  document_id, hid, now) for s in result.summen])
        return len(result.zeilen)



    def save_haushaltssatzung(self, satzung, herkunft) -> int:
        """Eine Haushaltssatzung speichern — ein Jahrgang, eine Fassung.

        Wie bei den Wirtschaftsplänen kommen die Proben aus der HERKUNFT und
        werden hier nicht noch einmal behauptet: Ob der Hebesatz gegen das
        Statistische Jahrbuch geprüft werden konnte, hängt daran, ob dessen
        Tabelle diesen Jahrgang schon trägt — der Parser weiß das, der Store
        nicht.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_budget_bylaw "
                "(year, supplement, version, ordinary_revenues, "
                " ordinary_expenses, extraordinary_revenues, extraordinary_expenses, "
                " in_operating, out_operating, in_capital, out_capital, "
                " in_financing, out_financing, in_total, out_total, "
                " investment_loans, commitment_authorizations, "
                " liquidity_loans, property_tax_a_rate, "
                " property_tax_b_rate, trade_tax_rate, session_date, "
                " template_number, probes, herkunft_id, fetched_at) "
                "VALUES (" + ",".join("?" * 26) + ")",
                (satzung.year, satzung.supplement, satzung.version,
                 satzung.ordinary_revenues, satzung.ordinary_expenses,
                 satzung.extraordinary_revenues, satzung.extraordinary_expenses,
                 satzung.in_operating, satzung.out_operating,
                 satzung.in_capital, satzung.out_capital,
                 satzung.in_financing, satzung.out_financing,
                 satzung.in_total, satzung.out_total,
                 satzung.investment_loans,
                 satzung.commitment_authorizations,
                 satzung.liquidity_loans,
                 satzung.property_tax_a_rate, satzung.property_tax_b_rate,
                 satzung.trade_tax_rate, satzung.session_date,
                 satzung.template_number, probes, hid, now))
        return 1


    def haushaltssatzung_jahre(self) -> list[int]:
        """Jahrgänge, für die eine Satzung vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_budget_bylaw ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Haushaltsvollzug (council.budget_execution) ------------------------

    def save_haushaltsvollzug(self, bericht, herkunft) -> int:
        """Eine Übersichtstabelle eines Finanz- und Leistungsberichts ersetzen.

        Ersetzt wird nach ``(budget_year, as_of, budget)`` — der Einheit, die
        EIN Lauf liefert. Nicht nach Jahrgang und nicht nach Stichtag: Ein
        Dokument trägt beide Haushalte, und sie kommen einzeln durch ihre
        Proben. Im Bericht zum 30.06.2024 fällt der Ergebnishaushalt an einem
        Fehler im Dokument durch, der Finanzhaushalt nicht — wer nach Stichtag
        löschte, risse den mit.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode
        prüft nichts nach, sie schreibt.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_budget_execution "
                "WHERE budget_year = ? AND as_of = ? AND budget = ?",
                (bericht.budget_year, bericht.as_of, bericht.budget))
            self._conn.executemany(
                "INSERT INTO council_budget_execution ("
                " budget_year, as_of, budget, sub_budget, kind, label, "
                " budgeted, forecast, deviation, carryover, plan_basis, "
                " is_total, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(bericht.budget_year, bericht.as_of, bericht.budget,
                  p.sub_budget, p.kind, p.label, p.budgeted, p.forecast,
                  p.deviation, p.carryover, bericht.plan_basis,
                  1 if p.is_total else 0, probes, hid, now)
                 for p in bericht.positionen])
        return len(bericht.positionen)

    def haushaltsvollzug_einheiten(self) -> set[tuple]:
        """Welche ``(Jahrgang, Stichtag, Haushalt)`` im Bestand stehen.

        Die Einheit ist die Tabelle und nicht der Jahrgang: Ein Haushaltsjahr
        besteht aus bis zu vier Stichtagen mit je zwei Haushalten. Wer je
        Jahrgang buchführt, hält 2025 nach dem Bericht zum 31. März für
        erledigt und zieht die drei folgenden Quartale nie nach."""
        try:
            return {(r[0], r[1], r[2]) for r in self._conn.execute(
                "SELECT DISTINCT budget_year, as_of, budget "
                "FROM council_budget_execution")}
        except sqlite3.OperationalError:
            return set()




    def wirtschaftsplan_jahre(self, enterprise: str) -> list[int]:
        """Haushaltsjahre, für die ein Plan dieses Betriebs vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_business_plans WHERE enterprise = ? "
                "ORDER BY year", (enterprise,))]
        except sqlite3.OperationalError:
            return []

    def save_buergschaften(self, zeilen: list[dict], herkunft) -> int:
        """Bürgschafts-Jahrgänge ersetzen — je Jahr eine Zeile.

        Wie bei ``save_ausgabenreihe`` wird nur ersetzt, was die Lieferung
        mitbringt: Ein Lauf, dem ein Jahrgang durchgefallen ist, räumt den
        vorher gespeicherten Stand dieses Jahrgangs nicht mit weg.

        Aufgerufen wird sie **je Herkunfts-Gruppe**, nicht einmal für die
        ganze Reihe — jeder Jahrgang steht in seinem eigenen Jahresabschluss,
        und 2021 steht sogar in dem des Folgejahres. Ein gemeinsamer Beleg
        wäre für fünf von sechs Zeilen der falsche."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_buergschaften "
                "(year, balance, exact, out_next_year, source, reason, "
                " single_amount, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z["balance"], int(bool(z.get("exact"))),
                  int(bool(z.get("out_next_year"))), z["source"], z.get("reason"),
                  z.get("single_amount"), ",".join(z.get("probes") or []),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def save_kennzahlen(self, report_year: int, zeilen: list[dict],
                        formeln: list[dict], herkunft) -> int:
        """Einen Rechenschaftsbericht ersetzen — Werte und Rechenwege zusammen.

        Ersetzt wird genau **dieser Bericht**, nicht die Jahrgänge, die er
        zeigt. Der Bericht 2024 druckt 2020–2024; wer nach Datenjahr löschte,
        risse dem Bericht 2021 vier seiner fünf Spalten heraus — und mit ihnen
        die Vergleichsstände, aus denen die Korrekturen sichtbar werden.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_indicators WHERE report_year = ?",
                               (report_year,))
            self._conn.execute("DELETE FROM council_indicator_formulas WHERE report_year = ?",
                               (report_year,))
            self._conn.executemany(
                "INSERT INTO council_indicators "
                "(report_year, indicator, year, label, value, unit, decimals, "
                " version, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(report_year, z["indicator"], z["year"], z["label"], z["value"],
                  z["unit"], z["decimals"], z.get("version"), hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT INTO council_indicator_formulas "
                "(report_year, indicator, version, heading, formula, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(report_year, f["indicator"], f.get("version") or 1,
                  f["heading"], f["formula"], hid, now) for f in formeln])
        return len(zeilen)

    def get_kennzahlen(self) -> list[dict]:
        """Alle Stände aller Berichte — die Belegkette, nicht die Anzeigereihe.

        Wer die Reihe will, nimmt ``council.indicators.neueste``; wer die
        Korrekturen zeigen will, braucht alle Stände.
        """
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_indicators ORDER BY indicator, year, report_year")]
        except sqlite3.OperationalError:
            return []

    def get_kennzahl_formeln(self) -> list[dict]:
        """Die gedruckten Rechenwege, ältester Bericht zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_indicator_formulas ORDER BY indicator, report_year")]
        except sqlite3.OperationalError:
            return []

    def save_anlagenspiegel(self, year: int, zeilen: list[dict], herkunft) -> int:
        """Den Anlagenspiegel eines Jahrgangs ersetzen.

        Je Jahrgang ein Aufruf mit einem Beleg: Die Tabelle steht in genau
        einem Dokument, anders als bei den Bürgschaften, wo ein Jahrgang im
        Abschluss des Folgejahres stehen kann.

        Ersetzt wird nur DIESER Jahrgang — ein Lauf, dem ein anderer
        durchgefallen ist, räumt dessen Stand nicht mit weg.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_fixed_assets WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_fixed_assets "
                "(year, nr, label, n_columns, cost_opening, additions, disposals, "
                " transfers, cost_closing, depreciation_opening, depreciation, depreciation_releases, "
                " write_ups, depreciation_transfers, depreciation_closing, book_value, "
                " book_value_prior_year, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, z["nr"], z["label"], z["n_columns"],
                  z["cost_opening"], z["additions"], z["disposals"], z["transfers"],
                  z["cost_closing"], z["depreciation_opening"], z["depreciation"],
                  z["depreciation_releases"], z["write_ups"], z["depreciation_transfers"],
                  z["depreciation_closing"], z["book_value"], z["book_value_prior_year"],
                  ",".join(z.get("probes") or []), hid, now) for z in zeilen])
        return len(zeilen)


    def save_vermoegensgruppen(self, year: int, gruppen: list[dict], herkunft) -> int:
        """Die Untergliederung des Infrastrukturvermögens eines Jahrgangs."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_vermoegensgruppen WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_vermoegensgruppen "
                "(year, group_name, book_value, book_value_prior_year, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(year, g["group_name"], g["book_value"], g.get("book_value_prior_year"), hid, now)
                 for g in gruppen])
        return len(gruppen)



    def save_integrierte_schulden(self, row: dict, herkunft) -> int:
        """Einen Stichtag der integrierten Schulden ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_integrated_debt "
                "(year, ars, population, total, per_capita, core_budget, "
                " extra_budgets, other, extra_under_50, other_below_50, "
                " change, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["year"], row["ars"], row.get("population"),
                 row["total"], row.get("per_capita"),
                 row.get("core_budget"), row.get("extra_budgets"),
                 row.get("other"), row.get("extra_under_50"),
                 row.get("other_below_50"), row.get("insgesamt_change"),
                 ",".join(row.get("probes") or []), hid, now))
        return 1


    # --- Nachbewilligungen nach § 117 NKomVG --------------------------------

    def anlage_text(self, document_id: int) -> str | None:
        """Der Volltext einer Anlage — oder ``None``, wenn keiner da ist.

        „Kein Text" ist der Normalfall und kein Fehler: Der Bestand führt
        Anlagen, die noch nie geladen wurden (``scripts/backfill_anlagen_texte
        .py``), und solche, die als Scan gar keinen Text hergeben. Beide
        sollen den Aufrufer nicht in einen Fehlerpfad zwingen, sondern in die
        Meldung „für dieses Jahr liegt die Quelle nicht vor"."""
        try:
            row = self._conn.execute(
                "SELECT raw_text FROM council_attachments WHERE document_id = ?",
                (document_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return (row["raw_text"] or None) if row else None

    def nachbewilligungs_vorlagen(self) -> tuple[list[dict], dict[str, list[dict]]]:
        """Die Rohdaten für ``council/supplementary_approvals.aus_vorlagen``.

        → ``(vorlagen, beschluesse)`` — **erst die Vorlagen, dann die nach
        Vorlagen-Nummer gruppierten Beschlusszeilen**, genau in der
        Reihenfolge, die der Parser erwartet.

        Der Filter läuft über den **Titel**, nicht über eine Vorlagenart:
        ``art`` heißt hier „Beschlussvorlage" oder „Berichtsvorlage" und sagt
        nichts über den Inhalt. Vorgefiltert wird nur grob (SQL kennt unser
        Muster nicht); die Feinentscheidung trifft
        ``supplementary_approvals.ist_nachbewilligung``.

        **Der Join läuft über ``template_number``, nicht über ``kvonr``.** Das ist
        keine Stilfrage: ``council_decisions.kvonr`` ist im gesamten Bestand
        ``NULL`` (8.369 von 8.369 Zeilen). Ein Join darüber liefert
        schweigend null Treffer — und eine Seite, die behauptet, der Rat habe
        nie über eine Nachbewilligung entschieden."""
        try:
            vorlagen = [dict(r) for r in self._conn.execute(
                "SELECT template_number, title, proposed_decision, raw_text "
                "FROM council_templates "
                "WHERE template_number IS NOT NULL "
                "  AND (title LIKE '%planmäßig%' OR title LIKE '%planmässig%')"
            )]
            rows = [dict(r) for r in self._conn.execute(
                "SELECT d.id, d.template_number, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.template_number IS NOT NULL AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG
            )]
        except sqlite3.OperationalError:
            return [], {}
        beschluesse: dict[str, list[dict]] = {}
        for r in rows:
            beschluesse.setdefault(str(r["template_number"]), []).append(r)
        return vorlagen, beschluesse

    def save_nachbewilligungen(self, zeilen: list[dict], herkunft) -> int:
        """Die RIS-Serie ersetzen — je Vorlage eine Zeile.

        Wie bei ``save_schulden`` wird nur ersetzt, was die Lieferung
        mitbringt. Übergeben wird, was der Parser gelesen hat; diese Methode
        prüft nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_supplementary_approvals "
                "(template_number, year, title, kind, category, amount, "
                " amount_source, decided, in_plenary, council_decision, "
                " decision_id, committees, "
                " fulltext_probe, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z.get("year"), z["title"], z["kind"],
                  z["category"], z.get("amount"), z.get("amount_source"),
                  int(bool(z.get("decided"))), int(bool(z.get("in_plenary"))),
                  int(bool(z.get("council_decision"))),
                  z.get("decision_id"),
                  json.dumps(z.get("committees") or [], ensure_ascii=False),
                  int(bool(z.get("fulltext_probe"))), hid, now)
                 for z in zeilen])
        return len(zeilen)

    def save_nachbewilligung_jahr(self, year: dict, channels: list[dict],
                                  herkunft) -> int:
        """Ein Jahrgang aus Kapitel 3 des Rechenschaftsberichts.

        Jahreszeile und Kanäle wandern zusammen in **eine** Transaktion: Ein
        Bestand, in dem die Summenzeile eines Jahres steht und seine vier
        Wege fehlen, wäre genau der Zustand, den die Tabellenprobe unmöglich
        machen soll."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_supplementary_years "
                "(year, total_operating, total_capital, total_per_text, "
                " commitments_amount, probe_ok, probe_text, herkunft_id, "
                " fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (year["year"], year["total_operating"], year["total_capital"],
                 year.get("total_per_text"), year.get("commitments_amount"),
                 int(bool(year.get("probe_ok"))), year.get("probe_text"),
                 hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_supplementary_channels "
                "(year, channel, label, count_operating, amount_operating, "
                " count_capital, amount_capital, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year["year"], k["channel"], k["label"], k["count_operating"],
                  k["amount_operating"], k["count_capital"],
                  k["amount_capital"], hid, now) for k in channels])
        return len(channels)



    def ausgabenreihe_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes
        vor dem Schreiben (``council/finanzquellen.bestandsschutz``)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_expense_series ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Zuwendungen an die Stadt (aus den Ratsbeschlüssen) ----------------

    def save_spenden(self, zeilen: list[dict], verworfen: list[dict],
                     herkunft) -> int:
        """Die geprüfte Spendenreihe schreiben — je Vorlage eine Zeile.

        Anders als bei den übrigen Schichten bringt **jede Zeile ihre eigene
        Herkunft mit** (``row["herkunft"]``): Jede Vorlage ist ein eigenes
        PDF mit eigener Dokument-ID. ``herkunft`` ist die Rückfallebene für
        die verworfenen Zeilen und für Zeilen ohne eigenen Anker — sie
        beschreibt den Lauf, nicht ein Dokument.

        ``INSERT OR REPLACE``, kein ``DELETE FROM``: Eine Teillieferung
        (etwa nach einem abgebrochenen Volltext-Lauf) ersetzt nur, was sie
        mitbringt, und räumt den Bestand nicht ab."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_donations "
                "(template_number, year, session_date, amount, committee, layout, second_mention, "
                " probes, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z["year"], z["session_date"], z["amount"], z.get("committee"),
                  z.get("layout"), z["second_mention"], ",".join(z["probes"]),
                  self.merke_herkunft(z["herkunft"], fetched_at=now)
                  if z.get("herkunft") else rueck, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_donations_rejected "
                "(template_number, session_date, reason, herkunft_id, fetched_at) VALUES (?,?,?,?,?)",
                [(v["template_number"], v.get("session_date"), v["reason"], rueck, now)
                 for v in verworfen])
        return len(zeilen)

    # --- Marken der Skriptläufe (scripts/check_finanzdaten.py) --------------

    def ingest_marke(self, key: str) -> dict | None:
        """Bei welcher Dokumentmarke das Skript dieser Datenart zuletzt lief."""
        try:
            r = self._conn.execute(
                "SELECT key, marke, ran_at, ok, summary FROM council_ingest_marks WHERE key = ?",
                (key,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(r) if r else None

    def setze_ingest_marke(self, key: str, marke: int, ok: bool, summary: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_ingest_marks (key, marke, ran_at, ok, summary) "
                "VALUES (?,?,?,?,?)",
                (key, int(marke), datetime.utcnow().isoformat(timespec="seconds"), int(ok), summary[:2000]))

    # --- Liquiditätsstand (council/liquidity.py) ----------------------------

    def liquiditaetsanlagen(self) -> list[dict]:
        """Die Anlagen der Liquiditätsstand-Vorlagen — mit oder ohne Text.

        Über ``kvonr``, nicht über ein Label-Muster: Bis 2021 heißt die
        Anlage schlicht „Anlage", erst danach trägt sie den Titel der
        Grafik."""
        try:
            return [dict(r) for r in self._conn.execute(
                """SELECT t.template_number, a.document_id, a.label, a.url, a.raw_text,
                          a.status, a.n_pages
                     FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr
                    WHERE t.title LIKE 'Liquiditätsstand%'
                    ORDER BY t.template_number, a.document_id""")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def anlagentext_nachtragen(self, document_id: int, text: str, n_pages: int) -> None:
        """Den heruntergeladenen Text einer Anlage ablegen — damit der nächste
        Lauf (und die KI-Frage) ihn haben, ohne noch einmal zu laden."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_attachments SET raw_text = ?, n_pages = ?, status = 'ok', "
                "fetched_at = datetime('now') WHERE document_id = ?", (text, n_pages, document_id))

    def save_liquidity(self, rows: list[dict], herkunft) -> int:
        """Die Monatsreihe schreiben — je Zeile ihre Herkunft (``row["herkunft"]``),
        sonst die des Laufs. ``INSERT OR REPLACE`` je Monat."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for r in rows:
                hid = self.merke_herkunft(r["herkunft"], fetched_at=now) if r.get("herkunft") else rueck
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_liquidity (month, year, amount, as_of, confirmations, "
                    " revised_from, document_id, url, template_number, probes, herkunft_id, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["month"], r["year"], r["amount"], r["as_of"], r.get("confirmations", 1),
                     r.get("revised_from"), r.get("document_id"), r.get("url"), r.get("template_number"),
                     ",".join(r.get("probes") or []), hid, now))
        return len(rows)


    def liquidity_einheiten(self) -> set[tuple]:
        """``(Jahr, Monat)`` je Zeile — die Einheiten des Datenstands."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT year, CAST(substr(month, 6, 2) AS INTEGER) FROM council_liquidity")}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return set()

    # --- Jahresabschlüsse der Eigenbetriebe (council/eigenbetriebe_abschluss.py) --

    def eigenbetrieb_abschluss_anlagen(self) -> list[dict]:
        """Die Anlagen der Jahresabschluss-Vorlagen der Eigenbetriebe — mit
        Titel der Vorlage, denn Betrieb und Jahr stehen dort, nicht im Label."""
        from council.eigenbetriebe_abschluss import TITEL_MUSTER, TITEL_SQL
        try:
            return [dict(r) for r in self._conn.execute(
                f"""SELECT t.kvonr, t.template_number, t.title, a.document_id, a.label,
                           a.url, a.raw_text, a.n_pages, a.status
                      FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr
                     WHERE {TITEL_SQL}
                     ORDER BY t.template_number, a.document_id""", list(TITEL_MUSTER))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def save_enterprise_accounts(self, rows: list[dict], herkunft) -> int:
        """Die Kennzahlen schreiben — je Zeile ihre Herkunft (``row["herkunft"]``)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for r in rows:
                hid = self.merke_herkunft(r["herkunft"], fetched_at=now) if r.get("herkunft") else rueck
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_enterprise_accounts (enterprise, year, metric, "
                    " value, unit, report_year, confirmations, conflicts, document_id, probes, "
                    " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["enterprise"], r["year"], r["metric"], r["value"], r["unit"],
                     r["report_year"], r.get("confirmations", 1), r.get("conflicts", 0),
                     r.get("document_id"), ",".join(r.get("probes") or []), hid, now))
        return len(rows)


    def enterprise_account_einheiten(self) -> set[tuple]:
        """``(Jahr, Betrieb)`` je Zeile — die Einheiten des Datenstands."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT DISTINCT year, enterprise FROM council_enterprise_accounts")}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return set()

    # --- Kredite und Zinsen (council/loans.py) ------------------------------

    def kreditunterrichtungen(self) -> list[dict]:
        """Die Rohzeilen für ``council.loans.lies()``: Vorlagen samt Volltext.

        Breit gefasst — das Aussieben macht ``loans.erkenne()``."""
        from council.loans import TITEL_SQL
        try:
            return [dict(r) for r in self._conn.execute(
                f"""SELECT kvonr, template_number, title, raw_text, document_id, document_url
                     FROM council_templates
                    WHERE {TITEL_SQL}
                    ORDER BY template_number""")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def save_loan_notices(self, notices: list[dict], items: list[dict], herkunft) -> int:
        """Die Unterrichtungen und ihre Posten schreiben — je Vorlage ihre
        eigene Herkunft (``row["herkunft"]``), sonst die des Laufs.

        ``INSERT OR REPLACE`` je Vorlage; die Posten einer Vorlage werden
        vorher gelöscht, damit ein neu gelesener Bericht keine alten Posten
        neben den neuen stehen lässt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for n in notices:
                hid = (self.merke_herkunft(n["herkunft"], fetched_at=now)
                       if n.get("herkunft") else rueck)
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_loan_notices "
                    "(template_number, year, period_from, period_to, document_date, "
                    " none_reported, items, interest_saving, saving_from, saving_to, "
                    " document_id, document_url, probes, herkunft_id, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (n["template_number"], n["year"], n["period_from"], n["period_to"],
                     n.get("document_date"), int(bool(n.get("none_reported"))), n.get("items", 0),
                     n.get("interest_saving"), n.get("saving_from"), n.get("saving_to"),
                     n.get("document_id"), n.get("document_url"), ",".join(n.get("probes") or []),
                     hid, now))
                self._conn.execute("DELETE FROM council_loan_items WHERE template_number = ?",
                                   (n["template_number"],))
                for it in (i for i in items if i["template_number"] == n["template_number"]):
                    self._conn.execute(
                        "INSERT OR REPLACE INTO council_loan_items "
                        "(template_number, seq, year, kind, borrower, heading, amount, rate_pct, "
                        " fixed_years, fixed_until, decided_at, summary, herkunft_id, fetched_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (it["template_number"], it["seq"], it["year"], it["kind"], it.get("borrower"),
                         it["heading"], it.get("amount"), it.get("rate_pct"), it.get("fixed_years"),
                         it.get("fixed_until"), it.get("decided_at"), it.get("summary"), hid, now))
        return len(notices)





    def spenden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_donations ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def zuwendungsbeschluesse(self) -> list[dict]:
        """Die Rohzeilen für ``council.donations.lies()``.

        Absichtlich breit gefasst (``Annahme%Zuwendung%``): Das Aussieben
        macht ``donations.erkenne()``, damit die Regel an einer Stelle steht und
        nicht halb in SQL."""
        return [dict(r) for r in self._conn.execute(
            """SELECT d.template_number, d.title AS title, d.official_text, d.outcome,
                      s.session_date AS session_date, s.committee AS gremiensitzung,
                      v.raw_text, v.document_id AS document_id,
                      v.document_url AS dokument_url
                 FROM council_decisions d
                 LEFT JOIN council_sessions s ON s.ksinr = d.ksinr
                 LEFT JOIN council_templates v ON v.template_number = d.template_number
                WHERE d.kind = 'decision' AND d.title LIKE 'Annahme%Zuwendung%'
                ORDER BY s.session_date, d.template_number""")]

    # --- Steuertabellen des Jahrbuchs (1103 und 1105) -----------------------

    def save_steuerplan(self, zeilen: list[dict], herkunft) -> int:
        """Plan neben Ist je Steuerart — ersetzt, was die Lieferung mitbringt.

        Nicht die ganze Tabelle: Jede Ausgabe von 1103 führt nur **drei**
        Jahrgänge, und der Lauf legt mehrere Ausgaben nacheinander ab. Ein
        ``DELETE`` vor dem Schreiben löschte deshalb genau das, wofür das
        Archiv gebaut wurde — die Jahrgänge, die nur noch in einer älteren
        Ausgabe stehen.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_plan "
                "(year, kind, plan, actual, provisional, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [(z["year"], z["kind"], z["plan"], z["actual"],
                  int(bool(z.get("provisional"))), hid, now) for z in zeilen])
        return len(zeilen)


    def steuerplan_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_tax_plan ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def save_hebesaetze(self, zeilen: list[dict], herkunft) -> int:
        """Die Hebesatz-Treppe — je Änderungsjahr und Steuerart eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_rates "
                "(year, kind, rate, prior_rate, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(z["year"], z["kind"], z["rate"], z.get("prior_rate"),
                  hid, now) for z in zeilen])
        return len(zeilen)


    def hebesatz_jahre(self) -> list[int]:
        """Welche Änderungsjahre im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_tax_rates ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Ist-Investitionen (Tabellen 1107/1107-1 des Jahrbuchs) -------------

    def save_investitionen_ist(self, zeilen: list[dict], herkunft,
                               verworfen: list[dict] | None = None) -> int:
        """Investitions-Jahrgänge ersetzen — je Jahr eine Zeile plus ihre Arten.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (derselbe Grund wie bei ``save_schulden``).

        Die Arten eines Jahrgangs werden vorher gelöscht statt nur überschrieben:
        Wechselte die Quelle ihren Spaltenschnitt, bliebe eine abgeschaffte Art
        sonst als Karteileiche stehen und die Aufteilung summierte sich auf
        mehr als die Summe daneben.

        ``verworfen`` sind die Jahrgänge, die die Probe **nicht** bestanden
        haben (``lies()["verworfen"]``): Grund und gemessene ``difference``
        werden mitgeschrieben, damit die Seite ihre Lücke beziffern kann
        statt sie nur zu behaupten. Ein Jahrgang, der jetzt durchkommt,
        verliert dabei seinen alten Lücken-Eintrag — sonst stünde er in
        beiden Tabellen und die Seite zeigte eine Lücke, die es nicht mehr
        gibt.

        Übergeben wird an ``zeilen`` nur, was seine Probe bestanden hat —
        diese Methode prüft nichts nach, sie schreibt."""
        from council import investitionen_ist as _ii

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual "
                "(year, accounting_system, total, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?)",
                [(z["year"], z["accounting_system"], z["total"], hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "DELETE FROM council_investments_actual_kinds WHERE year = ?",
                [(z["year"],) for z in zeilen])
            arten = []
            for z in zeilen:
                spalten = _ii.SPALTEN[z["accounting_system"]]
                for i, (field, title) in enumerate(spalten[:-1]):
                    if z.get(field) is None:
                        continue
                    arten.append((z["year"], field, title, i, z[field], hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual_kinds "
                "(year, field, title, sort_order, amount, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)", arten)
            # Ein übernommener Jahrgang ist keine Lücke mehr.
            self._conn.executemany(
                "DELETE FROM council_investments_actual_rejected WHERE year = ?",
                [(z["year"],) for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual_rejected "
                "(year, accounting_system, reason, difference, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(v["year"], v["accounting_system"], v["reason"], v.get("difference"),
                  hid, now) for v in (verworfen or [])])
        return len(zeilen)



    def investitionen_ist_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — der Bestandsschutz vergleicht
        gegen diese Zahl, bevor ein Lauf sie überschreibt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_investments_actual ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def investitionen_ist_kontext(self, year: int | None = None) -> dict | None:
        """Was die Stadt zuletzt wirklich investiert hat — für die KI-Frage.

        Wenige Zeilen statt Bestand, wie bei allen Geld-Bausteinen: der
        jüngste Jahrgang mit seiner Aufteilung, das Vorjahr als Maßstab und
        der höchste Stand der doppischen Reihe.

        **Nur die doppische Reihe.** Die kameralen Jahrgänge bis 2009 zählen
        etwas anderes (s. ``council/investitionen_ist.py``); in einem
        Prompt-Baustein nebeneinander wären sie eine Einladung, sie zu einer
        Reihe zu addieren.
        """
        from council import investitionen_ist as _ii

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments_actual "
                "WHERE accounting_system = 'doppik' ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        idx = next((i for i, r in enumerate(rows) if r["year"] == year), len(rows) - 1)
        abweicht = year is not None and rows[idx]["year"] != year
        rows_bis = rows[:idx + 1]
        neu = rows[idx]
        try:
            arten = [(r["title"], r["amount"]) for r in self._conn.execute(
                "SELECT title, amount FROM council_investments_actual_kinds "
                "WHERE year = ? ORDER BY sort_order", (neu["year"],))]
        except sqlite3.OperationalError:
            arten = []
        hoch = max(rows, key=lambda r: r["total"])
        # Welche Jahre die Quelle ankündigt, aber nicht belegt — die Lücke
        # gehört in den Kontext, sonst liest ein Modell die Reihe als
        # lückenlos und rechnet Durchschnitte über ein Loch.
        fehlend = [j for j in range(rows[0]["year"], neu["year"] + 1)
                   if j not in {r["year"] for r in rows}]
        return {
            "year": neu["year"],
            "total": neu["total"],
            "arten": arten,
            "davor": ({"year": rows_bis[-2]["year"], "total": rows_bis[-2]["total"]}
                      if len(rows_bis) > 1 else None),
            "hoch": ({"year": hoch["year"], "total": hoch["total"]}
                     if hoch["year"] != neu["year"] else None),
            "reihe_ab": rows[0]["year"],
            "fehlend": fehlend,
            "abgrenzung": _ii.ABGRENZUNG,
            "beleg": self._beleg(neu.get("herkunft_id")),
            **({"year_asked": year} if abweicht else {}),
        }

    def schulden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_debt ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def einwohner_je_jahr(self) -> dict[int, int]:
        """Alle bekannten Einwohnerzahlen als ``{year: zahl}``.

        Der Divisor der Pro-Kopf-Gegenprobe (``council/schulden.py``). Bewusst
        die ganze Reihe und nicht nur der jüngste Wert wie bei
        ``einwohner_aktuell``: Geprüft wird jeder Jahrgang gegen die
        Einwohnerzahl **seines** Jahres, nicht gegen die von heute."""
        try:
            return {r[0]: r[1] for r in self._conn.execute(
                "SELECT year, population FROM council_einwohner")}
        except sqlite3.OperationalError:
            return {}

    # --- Städtevergleich (amtliche Statistik des LSN) ------------------------

    def save_staedtevergleich(self, series: str, zeilen: list[dict], herkunft) -> int:
        """Eine Reihe des Städtevergleichs ersetzen — ``tax_capacity`` oder
        ``realsteuern``.

        Ersetzt wird **je Reihe und je betroffenem Jahr**, nicht die ganze
        Tabelle: Die beiden Reihen kommen aus verschiedenen Dateien, die zu
        verschiedenen Zeiten im Jahr erscheinen. Ein Lauf, der nur den
        Realsteuervergleich neu einliest, darf die Steuerkraft-Reihe nicht
        mitnehmen — sonst hinge der Bestand davon ab, in welcher Reihenfolge
        jemand die beiden Ingests anstößt.

        Übergeben wird nur, was seine Probe bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        years = {int(z["year"]) for z in zeilen}
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for year in sorted(years):
                self._conn.execute(
                    "DELETE FROM council_city_comparison WHERE series = ? AND year = ?",
                    (series, year))
            self._conn.executemany(
                "INSERT INTO council_city_comparison (series, year, key, "
                " city, indicator, value, unit, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(series, z["year"], z["key"], z["city"], z["indicator"],
                  z["value"], z["unit"], hid, now) for z in zeilen])
        return len(zeilen)


    def save_gewerbesteuerstatistik(self, zeilen: list[dict], herkunft) -> int:
        """Einen Erhebungsjahrgang der Gewerbesteuerstatistik ersetzen.

        Ersetzt wird **je Jahr**, nicht die ganze Tabelle: Die Jahrgänge kommen
        aus je eigenen Berichten, und ein Lauf, der 2021 nachträgt, darf 2017
        bis 2020 nicht mitnehmen. Ein Jahrgang wird dagegen vollständig
        ersetzt — das LSN gibt korrigierte Fassungen heraus (der Jahrgang 2020
        wurde am 11.02.2026 nachgebessert), und eine Korrektur, die alte Zeilen
        stehen ließe, wäre keine.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        years = {int(z["year"]) for z in zeilen}
        spalten = ("year", "key", "city", "cases", "cases_positive",
                   "tax_base_eur", "assessments", "assessments_positive",
                   "assessment_tax_base_eur", "apportionments",
                   "apportionments_positive", "apportioned_assessment_eur",
                   "rate", "confidential")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for year in sorted(years):
                self._conn.execute(
                    "DELETE FROM council_trade_tax_statistics WHERE year = ?",
                    (year,))
            self._conn.executemany(
                f"INSERT INTO council_trade_tax_statistics "
                f"({', '.join(spalten)}, herkunft_id, fetched_at) "
                f"VALUES ({', '.join('?' * len(spalten))},?,?)",
                [tuple(z.get(s) for s in spalten) + (hid, now) for z in zeilen])
        return len(zeilen)


    def save_produkte(self, year: int, produkte: list[dict], herkunft) -> int:
        """Produkte eines Jahres einfügen/aktualisieren. Bewusst KEIN Löschen
        des Jahrgangs: Die Produkte eines Jahres verteilen sich auf mehrere
        Teilhaushalts-Dokumente, die nacheinander eingelesen werden.

        ``INSERT OR REPLACE`` ersetzt bei gleichem ``(year, product_no)`` die
        **ganze** Zeile, samt Herkunft — wer zuletzt schreibt, gewinnt. Das ist
        hier nur deshalb ungefährlich, weil der Aufrufer dafür sorgt, dass ein
        Teilhaushalt genau einmal geschrieben wird: Sechs (Jahrgang,
        Teilhaushalt)-Paare liegen doppelt im Anlagenbestand, und welches der
        beiden Dokumente in der Zeile steht, soll keine Frage der
        Sortierreihenfolge sein. Die Regel und die Messung dazu stehen in
        ``council.finanzquellen.lies_teilhaushalte``. Wer einen zweiten
        Schreibweg zu dieser Tabelle baut, braucht dieselbe Vorentscheidung —
        die Tabelle selbst kann sie nicht treffen, sie sieht nur eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_products (year, product_no, product_name, "
                " sub_budget_no, sub_budget_name, office, revenues, expenses, result, "
                " short_description, legal_basis, controllability, "
                " controllability_raw, scope, target_group, "
                " source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, p["product_no"], p["product_name"], p.get("sub_budget_no"), p.get("sub_budget_name"),
                  p.get("office"), p.get("revenues"), p.get("expenses"), p.get("result"),
                  p.get("short_description"), p.get("legal_basis"),
                  p.get("controllability"), p.get("controllability_raw"),
                  p.get("scope"), p.get("target_group"),
                  herkunft.label, herkunft.url, now, hid) for p in produkte])
        return len(produkte)






    def save_pruefbericht(self, year: int, feststellungen: list[dict], herkunft) -> int:
        """Prüfungsfeststellungen eines Schlussberichts speichern.

        Der Jahrgang wird vorher geleert: Ein Bericht ist ein Dokument, und
        ein erneuter Ingest liest dasselbe Dokument neu — Zeilen von früheren
        Läufen stehen zu lassen hieße, alte Parser-Stände zu konservieren.

        Die ``citation`` der Herkunft bleibt hier bewusst grob („Randmarken
        des Berichts"): Die genaue Fundstelle einer Feststellung ist ihre
        **Textziffer** und ihre **Seite**, und die stehen je Zeile in der
        Tabelle. Die Herkunft beschreibt das Dokument, nicht die Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_audit_reports WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_audit_reports (year, seq, mark, mark_name, "
                " mark_explanation, text_number, section, chain, page, text, "
                " follow_paragraph, source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, f["seq"], f["mark"], f["mark_name"], f.get("mark_explanation"),
                  f["text_number"], f["section"], f.get("chain"), f.get("page"),
                  f["text"], f.get("follow_paragraph"), herkunft.label, herkunft.url, now, hid)
                 for f in feststellungen])
        return len(feststellungen)






    def top_amount_since(self, date_from: str) -> dict | None:
        """Größter im Beschlusstext erkannter Betrag seit ``date_from`` — die
        „Zahl der Woche" fürs Heute-Briefing (RL-905)."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.amount_eur, s.session_date
               FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ? AND d.amount_eur IS NOT NULL
                 AND d.kind = 'decision'
               ORDER BY d.amount_eur DESC LIMIT 1""",
            (date_from,),
        ).fetchone()
        return dict(row) if row else None

    def count_decisions_since(self, date_from: str) -> int:
        """Anzahl Beschlüsse seit ``date_from`` (Fallback der Zahl der Woche)."""
        return int(self._conn.execute(
            """SELECT COUNT(*) FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ?""",
            (date_from,),
        ).fetchone()[0])

    def antrag_stats(self) -> dict:
        """Erfolgsquoten der Fraktions-Anträge: Antrag-Anlage → Vorlage → deren
        Beschlüsse. Gezählt wird je Antragsteller-Partei der KLARE Endstand der
        Vorlage — bevorzugt der Beschluss des Rats selbst, sonst der letzte
        Ausschuss-Beschluss mit angenommen/abgelehnt. Mehrparteien-Anträge zählen
        für jede Partei. Methodik entspricht bewusst politik-vor-ort (Rat zuerst,
        nur klare Outcomes), aber über unsere volle Historie."""
        from council.parties import CANONICAL_ORDER, order_key

        antraege = self._conn.execute(
            """SELECT a.document_id, a.applicants, v.template_number
               FROM council_attachments a JOIN council_templates v ON v.kvonr = a.kvonr
               WHERE a.is_motion = 1 AND a.applicants != '[]'
                 AND v.template_number IS NOT NULL AND v.template_number != ''""",
        ).fetchall()

        per_party: dict[str, dict] = {}
        n_mit_beschluss = 0
        for row in antraege:
            base = "/".join(row["template_number"].split("/")[:2])
            # Trägt eine Vorlage mehrere Antrag-Anlagen (Änderungsanträge mehrerer
            # Parteien), zählt der Vorlagen-Endstand für jeden dieser Anträge.
            decision = self._conn.execute(
                """SELECT d.outcome, cs.committee FROM council_decisions d
                   JOIN council_sessions cs ON cs.ksinr = d.ksinr
                   WHERE d.kind = 'decision' AND d.outcome IN ('accepted','rejected')
                     AND (d.template_number = ? OR d.template_number LIKE ?)
                   ORDER BY (cs.committee LIKE 'Rat%') DESC, cs.session_date DESC
                   LIMIT 1""", (base, base + "/%"),
            ).fetchone()
            if not decision:
                continue
            n_mit_beschluss += 1
            try:
                parties = json.loads(row["applicants"] or "[]")
            except (json.JSONDecodeError, TypeError):
                parties = []
            for p in parties:
                # Nur anerkannte Parteien zählen — in älteren Anlagen-Zeilen
                # können inzwischen entfernte Labels (z. B. WFO/LKR) stehen.
                if p not in CANONICAL_ORDER:
                    continue
                s = per_party.setdefault(p, {"party": p, "n": 0, "accepted": 0, "rejected": 0})
                s["n"] += 1
                s[decision["outcome"]] += 1

        stats = sorted(per_party.values(), key=lambda s: (-s["n"], order_key(s["party"])))
        return {
            "parties": stats,
            "n_antraege": len(antraege),
            "n_mit_beschluss": n_mit_beschluss,
        }

    def get_unclassified_decisions(self, limit: int | None = None) -> list[dict]:
        """Decisions without a policy field yet — for the classification backfill/cron.
        Returns id + the fields the classifier needs (title, official_text, committee)."""
        sql = ("SELECT d.id, d.title, d.official_text, cs.committee "
               "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
               "WHERE d.policy_field IS NULL ORDER BY d.id")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(sql).fetchall()]

    def set_classifications(self, results: dict) -> int:
        """Bulk-write classification results: id -> {field, tags, summary}."""
        rows = [
            (r["field"], json.dumps(r.get("tags") or [], ensure_ascii=False), r.get("summary"), did)
            for did, r in results.items()
        ]
        with self._conn:
            self._conn.executemany(
                "UPDATE council_decisions SET policy_field = ?, policy_tags = ?, summary = ? WHERE id = ?",
                rows,
            )
        return len(rows)

    def reset_classifications(self) -> None:
        """Clear all topic classifications — for a full re-classify (e.g. taxonomy change)."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET policy_field = NULL, policy_tags = NULL, summary = NULL"
            )

    def rebuild_fts(self) -> int:
        """(Re)build the full-text index from all main decisions (title + official_text +
        summary + the first chunk of the Vorlage text + the first chunk of attached
        motion texts, so Sachverhalt AND original Antrag wording are findable). The
        joins are grouped because distinct kvonrs can in theory share a template_number —
        duplicate rowids would break the FTS insert."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decisions_fts")
            self._conn.execute(
                "INSERT INTO council_decisions_fts(rowid, content) "
                "SELECT d.id, REPLACE(COALESCE(d.title,'') || ' ' || COALESCE(d.official_text,'') || ' ' "
                "|| COALESCE(d.summary,'') || ' ' || COALESCE(sv.stext,'') || ' ' "
                "|| COALESCE(v.vtext,'') || ' ' || COALESCE(an.atext,''), "
                "'ß', 'ss') "  # unicode61 folds ä/ö/ü but not ß
                "FROM council_decisions d "
                "LEFT JOIN (SELECT template_number, ohne_kontaktdaten("
                "             substr(MAX(raw_text), 1, 8000)) AS vtext "
                "           FROM council_templates WHERE status = 'ok' GROUP BY template_number) v "
                "  ON v.template_number = d.template_number "
                # `ohne_kontaktdaten()` ist eine SQLite-Funktion (s.
                # `_verbinden`): Sie nimmt Kontonummern, Telefonnummern,
                # E-Mail-Adressen und Anschriften aus dem Text, BEVOR er in
                # den Volltextindex geht. Gespeichert bleibt er vollständig.
                "LEFT JOIN (SELECT cv.template_number, ohne_kontaktdaten("
                "             substr(GROUP_CONCAT(a.raw_text, ' '), 1, 4000)) AS atext "
                "           FROM council_attachments a JOIN council_templates cv ON cv.kvonr = a.kvonr "
                "           WHERE a.is_motion = 1 AND a.status = 'ok' GROUP BY cv.template_number) an "
                "  ON an.template_number = d.template_number "
                # Teilabstimmungen (Änderungsanträge) haben keine eigene FTS-Zeile —
                # ihre Titel zählen zum Haupt-TOP, damit „Änderungsantrag der X zu Y"
                # den zitierfähigen Hauptbeschluss findet (Design 23a: subvote-Inhalt
                # steht im title, official_text ist immer NULL).
                "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' '), 1, 2000) AS stext "
                "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
                "           GROUP BY ksinr, parent_item) sv "
                "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
                "WHERE d.kind = 'decision'"
            )
        return self._conn.execute("SELECT COUNT(*) FROM council_decisions_fts").fetchone()[0]

    def search_decisions_fts(self, query: str, limit: int = 40) -> list[tuple]:
        """BM25 keyword search → ``[(decision_id, score, snippet)]`` (larger = better).
        Terms are OR-combined for recall; returns ``[]`` on an empty or invalid query.

        Das FTS5-``snippet()`` liefert die FUNDSTELLE im indexierten Text — bei
        Treffern tief im Vorlagen-Volltext ist das der Kontext, den der Reranker
        sehen muss (der Textanfang verrät dort nichts über den Match)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss")) if len(t) >= 3][:12]
        if not terms:
            return []
        match = " OR ".join(terms)
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank, snippet(council_decisions_fts, 0, '', '', ' … ', 16) "
                "FROM council_decisions_fts WHERE council_decisions_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        # FTS5 rank is negative (more negative = better); flip so larger = better.
        return [(r[0], -float(r[1]), r[2] or "") for r in rows]







    # ---- Explizite Ortszuordnungen je Beschluss ---------------------------

    def decision_location_batches(self, *, batch_size: int = 12,
                                  pending_only: bool = True,
                                  limit: int | None = None):
        """Beschlüsse samt Vorlage speicherschonend in Batches liefern.

        Im Tageslauf kommen nur ungescannte Vorgänge oder solche mit einer
        später geladenen Vorlage zurück. ``pending_only=False`` ist der
        bewusste Voll-Backfill nach dem Leeren der Scan-Tabelle.
        """
        inner = """SELECT d.id, d.title, d.official_text, d.template_number,
                      COALESCE(
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1)
                      ) AS vorlage_text,
                      COALESCE(
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1),
                        ''
                      ) AS vorlage_fetched_at,
                      s.source_hash AS existing_source_hash,
                      s.scanned_at
               FROM council_decisions d
               LEFT JOIN council_decision_location_scans s ON s.decision_id = d.id
               WHERE d.kind = 'decision'"""
        sql = f"SELECT * FROM ({inner}) q"
        if pending_only:
            sql += (" WHERE existing_source_hash IS NULL OR "
                    "(vorlage_fetched_at != '' AND "
                    "datetime(vorlage_fetched_at) > datetime(scanned_at))")
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {max(0, int(limit))}"
        cursor = self._conn.execute(sql)
        while True:
            rows = cursor.fetchmany(max(1, int(batch_size)))
            if not rows:
                break
            yield [dict(r) for r in rows]

    def decisions_for_location_extraction(self) -> list[dict]:
        """Kompatible Listenansicht; große Backfills nutzen die Batch-Methode."""
        return [row for batch in self.decision_location_batches(pending_only=False)
                for row in batch]

    def location_scan_hashes(self) -> dict[int, str]:
        return {r["decision_id"]: r["source_hash"] for r in self._conn.execute(
            "SELECT decision_id, source_hash FROM council_decision_location_scans")}

    def place_observations_for_decisions(self, ids: list[int]) -> dict[int, list[dict]]:
        """Einmalige alte NER-Orte als günstige Startbasis übernehmen."""
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT decision_id, name FROM council_entity_obs "
            f"WHERE kind = 'place' AND decision_id IN ({ph})", ids).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append({
                "name": r["name"], "kind": "other", "source": "official_text",
                "evidence": r["name"], "method": "entity_obs", "confidence": 0.86,
            })
        return out

    # ---- gemeinsamer, redaktionell erweiterbarer Ortskatalog -----------------







    def location_candidates(self, status_filter: str = "pending", *, limit: int = 200,
                            min_decisions: int = 3) -> list[dict]:
        """Häufige, noch nicht statisch katalogisierte Ortsnamen samt Belegen."""
        status_filter = status_filter if status_filter in {
            "pending", "concrete", "approved", "alias", "rejected", "all"
        } else "pending"
        # Auch zur Laufzeit freigegebene Katalogorte zählen als bekannt. So
        # verschwinden nach dem Backfill nicht nur statische Stadtteile,
        # sondern ebenso Schreibvarianten neuer redaktioneller Orte aus
        # der offenen Kandidatenliste.
        known_ids = sorted(place.id for place in self.all_places())
        review_where = ""
        review_params: list = []
        if status_filter == "pending":
            review_where = "AND r.status IS NULL"
        elif status_filter != "all":
            review_where = "AND r.status = ?"
            review_params.append(status_filter)
        known_placeholders = ",".join("?" for _ in known_ids)
        known_where = (
            f"AND (r.status IS NOT NULL OR l.place_id IS NULL "
            f"OR l.place_id NOT IN ({known_placeholders}))"
            if known_ids else ""
        )
        # Die offene Liste ist eine Prioritätenliste, kein Dump aller einmalig
        # erwähnten Namen. Bereits geprüfte Einträge müssen dagegen auch dann
        # sichtbar bleiben, wenn sie nur in einem Beschluss vorkommen.
        effective_min = max(1, int(min_decisions)) if status_filter == "pending" else 1
        rows = self._conn.execute(
            f"""SELECT l.*, r.status AS review_status, r.place_id AS review_place_id,
                      r.name AS review_name, r.kind AS review_kind, r.parent_id,
                      r.aliases, r.description, r.source_url, r.quiz_enabled,
                      r.canonical_place_id, r.note, r.updated_by, r.updated_at AS reviewed_at,
                      COUNT(DISTINCT dl.decision_id) AS decision_count,
                      MAX(cs.session_date) AS last_date,
                      AVG(dl.confidence) AS avg_confidence
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.kind IN ('district','area','other') {review_where} {known_where}
               GROUP BY l.slug
               HAVING COUNT(DISTINCT dl.decision_id) >= ?
               ORDER BY decision_count DESC, last_date DESC, l.name
               LIMIT ?""", (*review_params, *known_ids, effective_min,
                              max(1, min(int(limit), 500)))
        ).fetchall()
        out = []
        for row in rows:
            state = row["review_status"] or "pending"
            evidence = self._conn.execute(
                """SELECT d.id,d.title,cs.session_date,dl.evidence,dl.method,dl.confidence
                   FROM council_decision_locations dl
                   JOIN council_decisions d ON d.id=dl.decision_id
                   JOIN council_sessions cs ON cs.ksinr=d.ksinr
                   WHERE dl.location_slug=? AND d.kind='decision'
                   ORDER BY cs.session_date DESC,d.id DESC LIMIT 3""",
                (row["slug"],),
            ).fetchall()
            item = dict(row)
            item["status"] = state
            try:
                item["aliases"] = json.loads(row["aliases"] or "[]")
            except (TypeError, json.JSONDecodeError):
                item["aliases"] = []
            item["evidence"] = [dict(sample) for sample in evidence]
            out.append(item)
        return out

    def review_location_candidate(self, location_slug: str, *, status: str,
                                  place_id: str | None = None, name: str | None = None,
                                  kind: str | None = None, parent_id: str | None = None,
                                  aliases: list[str] | None = None,
                                  description: str | None = None,
                                  source_url: str | None = None,
                                  quiz_enabled: bool = False,
                                  canonical_place_id: str | None = None,
                                  note: str | None = None,
                                  updated_by: str | None = None) -> dict:
        """Redaktionelles Urteil speichern und stabile IDs an Rohorte schreiben."""
        from council import places
        from council.locations import location_slug as slugify

        if status not in {"concrete", "approved", "alias", "rejected"}:
            raise ValueError("Unbekannter Prüfstatus")
        observed = self._conn.execute(
            "SELECT * FROM council_locations WHERE slug=?", (location_slug,)).fetchone()
        if not observed:
            raise KeyError(location_slug)
        allowed_kinds = {key for key in places.catalog()["kinds"] if key != "local_area"}
        if status == "approved":
            place_id = slugify(place_id or name or observed["name"])
            name = (name or observed["name"]).strip()
            kind = kind or "neighborhood"
            if not place_id or not name or kind not in allowed_kinds:
                raise ValueError("Freigegebener Ort braucht Name, gültige ID und Ortstyp")
            if not (source_url or "").startswith(("https://", "http://")):
                raise ValueError("Freigegebener Ort braucht eine Quellen-URL")
            if places.resolve(place_id) or any(p.id == place_id for p in self._reviewed_places()
                                                if p.id != observed["place_id"]):
                raise ValueError("Orts-ID ist bereits vergeben")
            parent = places.resolve(parent_id) if parent_id else None
            if parent_id and (not parent or not parent.is_primary):
                raise ValueError("Elternort muss ein primärer Ortsbereich sein")
        elif status == "concrete":
            name = (name or observed["name"]).strip()
            if not name or kind not in CONCRETE_LOCATION_KINDS:
                raise ValueError("Konkreter Ort braucht Name und gültigen Ortstyp")
            # Konkrete Punkte bleiben exakte Fundorte und werden absichtlich
            # nicht Teil des flächigen Ortskatalogs.
            place_id = None
            canonical_place_id = None
            parent_id = observed["local_area_id"]
            source_url = None
            quiz_enabled = False
        elif status == "alias":
            target = self.resolve_place(canonical_place_id)
            if not target:
                raise ValueError("Alias-Ziel ist unbekannt")
            canonical_place_id = target.id
            parents = self.primary_parents(target)
            parent_id = parents[0].id if len(parents) == 1 else None
            place_id = target.id
        else:
            place_id = None
            parent_id = None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        clean_aliases = list(dict.fromkeys(value.strip() for value in (aliases or []) if value.strip()))
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_place_reviews
                   (location_slug,status,place_id,name,kind,parent_id,aliases,description,
                    source_url,quiz_enabled,canonical_place_id,note,updated_by,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(location_slug) DO UPDATE SET
                    status=excluded.status,place_id=excluded.place_id,name=excluded.name,
                    kind=excluded.kind,parent_id=excluded.parent_id,aliases=excluded.aliases,
                    description=excluded.description,source_url=excluded.source_url,
                    quiz_enabled=excluded.quiz_enabled,
                    canonical_place_id=excluded.canonical_place_id,note=excluded.note,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (location_slug, status, place_id, name, kind, parent_id,
                 json.dumps(clean_aliases, ensure_ascii=False), description, source_url,
                 int(quiz_enabled), canonical_place_id, note, updated_by, now),
            )
            if status == "concrete":
                self._conn.execute(
                    "UPDATE council_locations SET place_id=NULL,updated_at=? WHERE slug=?",
                    (now, location_slug),
                )
            else:
                self._conn.execute(
                    "UPDATE council_locations SET place_id=?,local_area_id=?,updated_at=? WHERE slug=?",
                    (place_id, parent_id, now, location_slug),
                )
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        return next(item for item in self.location_candidates("all", limit=500)
                    if item["slug"] == location_slug)

    def delete_location_review(self, location_slug: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_place_reviews WHERE location_slug=?", (location_slug,))
        if not cur.rowcount:
            return False
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        self.backfill_location_place_ids()
        return True

    def save_decision_locations(self, decision_id: int, rows: list[dict],
                                source_hash: str | None) -> int:
        """Zuordnungen eines Beschlusses atomar ersetzen und ggf. Scanstand merken.

        ``source_hash=None`` speichert sichere Regex-/Bestandsfunde nach einem
        LLM-Fehler, markiert den Vorgang aber nicht als fertig: der nächste
        inkrementelle Lauf versucht die semantische Ergänzung erneut.
        """
        from council.locations import location_slug

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        by_slug: dict[str, dict] = {}
        for row in rows:
            slug = row.get("slug") or location_slug(row.get("name") or "")
            if not slug:
                continue
            if slug not in by_slug or float(row.get("confidence") or 0) > float(by_slug[slug].get("confidence") or 0):
                by_slug[slug] = row
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_locations WHERE decision_id = ?", (decision_id,))
            for slug, row in by_slug.items():
                place = self.resolve_place(row.get("name"))
                parents = self.primary_parents(place)
                primary = parents[0] if len(parents) == 1 else None
                self._conn.execute(
                    "INSERT INTO council_locations"
                    "(slug,name,kind,district,place_id,local_area_id,updated_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                    "place_id=COALESCE(excluded.place_id,council_locations.place_id), "
                    "local_area_id=COALESCE(excluded.local_area_id,council_locations.local_area_id), "
                    "district=COALESCE(excluded.district,council_locations.district), "
                    "updated_at=excluded.updated_at",
                    (slug, place.name if place else row["name"],
                     "district" if place and place.is_primary else row.get("kind") or "other",
                     primary.name if primary else None, place.id if place else None,
                     primary.id if primary else None, now),
                )
                self._conn.execute(
                    "INSERT INTO council_decision_locations "
                    "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (decision_id, slug, row.get("source") or "official_text",
                     (row.get("evidence") or row["name"])[:500], row.get("method") or "llm",
                     max(0.0, min(1.0, float(row.get("confidence") or 0))), now),
                )
            if source_hash is not None:
                self._conn.execute(
                    "INSERT INTO council_decision_location_scans(decision_id,source_hash,scanned_at) "
                    "VALUES (?,?,?) ON CONFLICT(decision_id) DO UPDATE SET "
                    "source_hash=excluded.source_hash, scanned_at=excluded.scanned_at",
                    (decision_id, source_hash, now),
                )
        return len(by_slug)

    def reset_decision_location_scans(self) -> None:
        """Vollständigen Neu-Lauf erlauben; Geocodes der Orte bleiben erhalten."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decision_locations")
            self._conn.execute("DELETE FROM council_decision_location_scans")

    def decision_locations(self, decision_id: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT l.*, dl.source, dl.evidence, dl.method, dl.confidence
               FROM council_decision_locations dl
               JOIN council_locations l ON l.slug = dl.location_slug
               WHERE dl.decision_id = ?
               ORDER BY dl.confidence DESC, l.name""", (decision_id,)).fetchall()
        return [dict(r) for r in rows]



    def decision_location_district_stats(self) -> list[dict]:
        """Kompatible Statistik der 31 primären Ortsbereiche."""
        primary_ids = {place.id for place in self.all_places() if place.is_primary}
        return [{key: value for key, value in row.items() if key != "place_id"}
                for row in self.decision_location_place_stats()
                if row["place_id"] in primary_ids]


    def decision_ids_for_place(self, place_id: str, limit: int | None = None) -> list[int]:
        """Beschlüsse mit belegtem Bezug zu einem Katalogort, neueste zuerst."""
        place = self.resolve_place(place_id)
        if not place:
            return []
        condition, params = self._place_location_condition(place)
        sql = f"""SELECT DISTINCT dl.decision_id
                  FROM council_decision_locations dl
                  JOIN council_locations l ON l.slug = dl.location_slug
                  JOIN council_decisions d ON d.id = dl.decision_id
                  JOIN council_sessions cs ON cs.ksinr = d.ksinr
                  WHERE {condition} AND d.kind = 'decision'
                  ORDER BY cs.session_date DESC, dl.decision_id DESC"""
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        return [row[0] for row in self._conn.execute(sql, params).fetchall()]




    #: Ab welchem Anteil der Stützpunkte ein Ortsbereich als berührt gilt.
    #: Zehn Prozent von bis zu 60 Punkten sind ein echtes Straßenstück, keine
    #: angeschnittene Ecke — und die zusätzliche Mindestzahl fängt sehr kurze
    #: Geometrien ab, bei denen ein einzelner Punkt schon 10 % wäre.
    ORTSBEREICH_ANTEIL = 0.10
    ORTSBEREICH_MINDESTPUNKTE = 2











    def trending_tags(self, days_back: int = 180, limit: int = 12) -> list[dict]:
        """Häufigste policy_tags der letzten Monate — Futter für anklickbare
        Themen-Vorschläge („was gerade den Rat beschäftigt")."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT je.value AS tag, COUNT(*) AS n
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr, json_each(d.policy_tags) je
               WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                 AND cs.session_date >= ?
               GROUP BY je.value ORDER BY n DESC, tag LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [{"tag": r["tag"], "n": r["n"]} for r in rows]

    def most_interesting_recent(self, days_back: int = 7) -> dict | None:
        """RL-U15 (13a-A): der interessanteste Beschluss der letzten Tage —
        füllt auf „Heute" den Treffer-Leerzustand („Diese Woche im Rat")."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.outcome, d.interest_reason, cs.committee, cs.session_date
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision' AND d.interest IS NOT NULL
                 AND cs.session_date >= date('now', ?)
               ORDER BY d.interest DESC, cs.session_date DESC LIMIT 1""",
            (f"-{int(days_back)} days",),
        ).fetchone()
        return dict(row) if row else None


    #: Ab wie vielen Ortsbereichen eine Entität als stadtweit gilt. Auf dem
    #: Prod-Bestand (01.09.2026) trennt 4 sauber: „Startchancen-Programm" (8),
    #: „Lärmaktionsplan" (7), „Mobilitätsplan Oldenburg 2030" (6) und „Housing
    #: First" (5) fallen raus, alles Ortsgebundene bleibt.
    CITYWIDE_FROM_DISTRICTS = 4

    #: Ab wie vielen Beschlüssen im Fenster ein bloßer Straßenname als
    #: Vorschlag taugt. Darunter ist er eine Adresse aus einem Bebauungsplan.
    STRASSE_MINDESTENS = 5

    #: Was nach Adresse klingt statt nach Vorhaben. Starke Straßen bleiben
    #: (s. STRASSE_MINDESTENS) — und rutschen hinter alles andere.
    _STRASSE = re.compile(r"(stra(ß|ss)e|str\.|weg|allee|ring|damm|chaussee|gasse|pfad|steig)$",
                          re.IGNORECASE)
    _STRASSE_VORNE = re.compile(r"^(am|an der|an den|auf dem|auf der|zum|zur|im|in der)\s",
                                re.IGNORECASE)





    def location_by_slug(self, slug: str) -> dict | None:
        row = self._conn.execute(
            "SELECT slug,name,kind,lat,lon,place_id,local_area_id FROM council_locations WHERE slug=?",
            (slug,),
        ).fetchone()
        return dict(row) if row else None












    # --- Entitäts-Anker der Suche (Akkuratheits-Paket, 10.08.26) -------------




    def neueste_stationen_fuer(self, kvonrs: list[int],
                               vorlage_basen: list[str]) -> list[dict]:
        """Alle Beschlüsse (id, kvonr, template_number, session_date, committee) der
        genannten Vorlagen-Familien — Grundlage für den „ältere Station"-Marker:
        derselbe Text durchläuft mehrere Gremien (gleiches kvonr), Revisionen
        hängen ein Suffix an die Vorlagen-Nummer (26/0100 → 26/0100-1)."""
        kvonrs = sorted({k for k in kvonrs if k})
        basen = sorted({(b or "").strip() for b in vorlage_basen if b and str(b).strip()})
        if not kvonrs and not basen:
            return []
        teile, params = [], []
        if kvonrs:
            teile.append(f"d.kvonr IN ({','.join('?' * len(kvonrs))})")
            params += kvonrs
        for b in basen[:60]:
            teile.append("d.template_number = ? OR d.template_number LIKE ?")
            params += [b, b + "-%"]
        rows = self._conn.execute(
            "SELECT d.id, d.kvonr, d.template_number, cs.session_date, cs.committee "
            "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
            "WHERE " + " OR ".join(teile), params).fetchall()
        return [dict(r) for r in rows]








    def decision_texts(self) -> list[dict]:
        """(id, text) per decision for the text match — title + Beschluss + summary."""
        rows = self._conn.execute(
            "SELECT id, title, official_text, summary FROM council_decisions").fetchall()
        return [{"id": r["id"],
                 "text": " ".join(x for x in (r["title"], r["official_text"], r["summary"]) if x)}
                for r in rows]







    # --- Personen-Paket (10.08.26): Stammdaten für Auflösung + Fragetyp -----

    # Vertretungs- und Zeit-Notizen sind keine Ämter („Für Oberbürgermeister
    # Krogmann", „bis TOP 8.2") — nur echte Amtsbezeichnungen zählen.
    _ROLLEN_RE = re.compile(
        r"(?i)^(erste[rn]?\s+)?(oberbürgermeister(in)?|stadtkämmer(er|in)|"
        r"stadtbaur(at|ätin)|stadtr(at|ätin))$")


    #: Funktionsangabe des Beteiligungsberichts, die „diese Person sitzt im
    #: Stadtrat" behauptet — mit optionalem Klammerzusatz, wie ihn der Bericht
    #: auch anderswo führt („1. Kreisrat (Vorsitzender)").
    _FUNKTION_RATSMITGLIED = re.compile(r"(?i)^ratsmitglied(\s*\(.*\))?$")

    @staticmethod
    def _ein_buchstabe_abstand(a: str, b: str) -> bool:
        """Unterscheiden sich die beiden Zeichenketten um höchstens einen
        Buchstaben (Levenshtein ≤ 1)? Gleichheit zählt mit."""
        if abs(len(a) - len(b)) > 1:
            return False
        if len(a) == len(b):
            return sum(x != y for x, y in zip(a, b)) <= 1
        kurz, lang = (a, b) if len(a) < len(b) else (b, a)
        i = 0
        while i < len(kurz) and kurz[i] == lang[i]:
            i += 1
        return kurz[i:] == lang[i + 1:]   # ein Zeichen im langen übersprungen










    # --- Council members (from attendance: who sits on the council) ------------------
    #: Das ganze Rollen-Vokabular der Anwesenheitsliste. `advisory` vergibt
    #: der Protokoll-Prompt nicht mehr (er nennt fünf Rollen); die Zeilen aus
    #: seiner früheren Fassung tragen den Wert weiter und sollen dabei
    #: richtig einsortiert bleiben — deshalb steht er hier.
    ATTENDANCE_ROLES = ("chair", "member", "administration", "minutes", "guest", "advisory")
    _MEMBER_ROLES = ("member", "chair")   # der Rest ist kein Mandat



    # --- Eine Person, zwei Namensformen (council.namensformen) ----------------





    #: Name des Plenar-Gremiums in den Sitzungsdaten. Es ist der Prüfstein für
    #: ein Ratsmandat (s. list_members) — die Ausschüsse führen daneben
    #: beratende Mitglieder, die dem Rat nicht angehören.
    PLENUM = "Rat"

    #: Wörter, die im Fraktions-Feld nur die ROLLE beschreiben („Beratendes
    #: Mitglied", „beratend", „Verwaltung") — sie benennen keine entsendende
    #: Organisation und taugen deshalb nicht als Herkunfts-Label.
    _ROLLEN_LABEL = re.compile(
        r"^(beratend\w*|beratende[sr]?\s+mitglied\w*|gast|gäste|verwaltung|"
        r"protokoll\w*|stellv\w*|vertretung|mitglied\w*)$", re.IGNORECASE)











    def decisions_for_amount(self, only_missing: bool = False) -> list[dict]:
        """Main decisions with their text, for the € extraction backfill."""
        sql = "SELECT id, title, official_text FROM council_decisions WHERE kind = 'decision'"
        if only_missing:
            sql += " AND amount_eur IS NULL"
        return [dict(r) for r in self._conn.execute(sql)]

    def set_amounts(self, rows: list[tuple]) -> int:
        """Bulk-write amount_eur. rows = (amount_or_None, decision_id)."""
        with self._conn:
            self._conn.executemany("UPDATE council_decisions SET amount_eur = ? WHERE id = ?", rows)
        return len(rows)

    # Titles excluded from the "largest" view: accounting / whole-budget reports
    # (balance totals, not a discrete decision) and treasury operations (debt
    # refinancing / credit reporting) — neither is "the city spends X on Y".
    #
    # Die Liste lebt in `council/importance.py` (Blatt-Modul, kein Zirkel) und
    # wird hier nur weitergereicht. Vorher stand sie ausschließlich hier — mit
    # der Folge, dass die drei Geld-Ansichten filterten, das Geld-Signal des
    # Wichtig-Werts aber nicht.
    _NON_SPENDING_TITLES = _importance.NON_SPENDING_TITLES

    def activity_trends(self, quarters: int = 12) -> dict:
        """Council activity over time for the trends view: decisions and recognised €
        volume per quarter (split by the busiest policy fields), plus the most active
        tags in the recent quarters."""
        from collections import Counter

        q_expr = ("substr(cs.session_date,1,4) || '-Q' || "
                  "((CAST(substr(cs.session_date,6,2) AS INTEGER)+2)/3)")
        rows = self._conn.execute(
            f"""SELECT {q_expr} AS q, d.policy_field AS field, COUNT(*) AS n
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND cs.session_date IS NOT NULL
                      AND d.policy_field IS NOT NULL
                GROUP BY q, field"""
        ).fetchall()
        all_q = sorted({r["q"] for r in rows})[-quarters:]
        qset = set(all_q)
        per_field: dict[str, dict] = {}
        for r in rows:
            if r["q"] not in qset:
                continue
            per_field.setdefault(r["field"], {q: 0 for q in all_q})[r["q"]] = r["n"]
        top_fields = sorted(per_field, key=lambda f: -sum(per_field[f].values()))[:6]

        # Recognised € per quarter — exclude accounting/treasury docs (Haushaltsplan,
        # Jahresabschluss …) so the bars reflect actual spending, not budget volumes.
        mclauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        mparams = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        money = {q: 0.0 for q in all_q}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, COALESCE(SUM(d.amount_eur), 0) AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                GROUP BY q""",
            mparams,
        ):
            if r["q"] in qset:
                money[r["q"]] = r["eur"] or 0

        # Procedural tags aren't "topics" — keep them out of the emerging list.
        procedural = {"bericht", "annahme", "vertagung", "kenntnisnahme", "beschluss",
                      "antrag", "anfrage", "mitteilung", "vorlage", "abstimmung", "resolution"}
        recent = set(all_q[-2:])
        tagc: Counter = Counter()
        for r in self._conn.execute(
            f"""SELECT d.policy_tags AS tags, {q_expr} AS q
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                      AND cs.session_date IS NOT NULL"""
        ):
            if r["q"] in recent:
                try:
                    for t in json.loads(r["tags"] or "[]"):
                        t = str(t).strip()
                        if t and t.lower() not in procedural:
                            tagc[t] += 1
                except (ValueError, TypeError):
                    pass

        # Biggest single financial decision per quarter (excl. accounting, reusing the
        # filter above) — the factual "what drove this quarter" behind the money bars.
        drivers: dict[str, dict] = {}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, d.id AS id, d.title AS title, d.amount_eur AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                ORDER BY d.amount_eur DESC""",
            mparams,
        ):
            if r["q"] in qset and r["q"] not in drivers:
                drivers[r["q"]] = {"id": r["id"], "title": r["title"], "eur": round(r["eur"] or 0)}

        return {
            "quarters": all_q,
            "fields": top_fields,
            "by_field": {f: [per_field[f][q] for q in all_q] for f in top_fields},
            "money": [round(money[q]) for q in all_q],
            "money_drivers": [drivers.get(q) for q in all_q],
            "emerging": [{"tag": t, "n": c} for t, c in tagc.most_common(12) if c >= 2],
        }

    def largest_financial_decisions(self, limit: int = 25) -> list[dict]:
        """Decisions with the largest recognised € amount, deduped across committees
        (same Vorlage decided in Ausschuss + Rat → one entry) and excluding
        accounting/treasury items."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC LIMIT 300""",
            params,
        ).fetchall()
        seen: set = set()
        out: list[dict] = []
        for r in rows:
            # Collapse the same matter (shared Vorlage across committees/revisions) and
            # recurring series (same title, different Vorlage). Rows are amount-desc, so
            # the kept entry is the largest.
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(self._decision_row(r))
            if len(out) >= limit:
                break
        return out

    def money_by_field(self) -> list[dict]:
        """Recognised € volume per policy field (excl. accounting/treasury), deduped
        like the largest-list so the same matter across committees/revisions isn't
        double-counted. For the 'Wofür fließt das Geld?' breakdown."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.template_number, d.policy_field AS field, d.amount_eur AS eur
                FROM council_decisions d
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND d.policy_field IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC""",
            params,
        ).fetchall()
        seen: set = set()
        agg: dict[str, dict] = {}
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            a = agg.setdefault(r["field"], {"field": r["field"], "total": 0.0, "n": 0})
            a["total"] += r["eur"] or 0
            a["n"] += 1
        out = sorted(agg.values(), key=lambda x: -x["total"])
        for a in out:
            a["total"] = round(a["total"])
        return out

    def policy_field_stats(self) -> list[dict]:
        """Count of classified decisions per policy field, most frequent first."""
        rows = self._conn.execute(
            "SELECT policy_field AS field, COUNT(*) AS count FROM council_decisions "
            "WHERE policy_field IS NOT NULL GROUP BY policy_field ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def party_analysis(self, top_parties: int = 8) -> dict:
        """Aggregate party behaviour from motions (Antragsteller = the ``factions``
        on a decision): a party × policy-field heatmap, per-party success rates,
        per-field contention and party co-sponsorships. Only ~13 % of decisions name
        an Antragsteller, so this reflects *active motions*, not every vote."""
        from collections import Counter
        from itertools import combinations

        from council.parties import order_key, parties_for_faction

        rows = self._conn.execute(
            "SELECT factions, policy_field, outcome, no_votes, abstentions "
            "FROM council_decisions WHERE kind = 'decision'"
        ).fetchall()

        party_field: dict[str, Counter] = {}
        party_outcome: dict[str, Counter] = {}
        party_total: Counter = Counter()
        field_motion: Counter = Counter()      # motions per field (heatmap columns)
        field_total: Counter = Counter()       # decided votes per field (contention)
        field_contested: Counter = Counter()
        pairs: Counter = Counter()
        with_factions = 0

        for fac, field, outcome, gegen, enth in rows:
            if field and outcome in ("accepted", "rejected", "postponed"):
                field_total[field] += 1
                if (gegen or 0) > 0 or (enth or 0) > 0:
                    field_contested[field] += 1
            try:
                arr = json.loads(fac or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            # Multi-Mapping: „Gruppe FDP/Volt" zählt für FDP UND Volt.
            parties = sorted({p for x in arr for p in parties_for_faction(x)}, key=order_key)
            if not parties:
                continue
            with_factions += 1
            for p in parties:
                party_total[p] += 1
                if field:
                    party_field.setdefault(p, Counter())[field] += 1
                    field_motion[field] += 1
                if outcome:
                    party_outcome.setdefault(p, Counter())[outcome] += 1
            for a, b in combinations(parties, 2):
                pairs[(a, b)] += 1

        top = sorted((p for p, _ in party_total.most_common(top_parties)), key=order_key)
        fields_present = [f for f, _ in field_motion.most_common()]
        matrix = {p: {f: party_field.get(p, Counter()).get(f, 0) for f in fields_present} for p in top}

        success = []
        for p in party_total:
            oc = party_outcome.get(p, Counter())
            decided = oc["accepted"] + oc["rejected"]
            success.append({
                "party": p, "motions": party_total[p],
                "accepted": oc["accepted"], "rejected": oc["rejected"], "postponed": oc["postponed"],
                "rate": round(oc["accepted"] / decided, 3) if decided else None,
            })
        success.sort(key=lambda s: s["motions"], reverse=True)

        contention = [
            {"field": f, "total": field_total[f], "contested": field_contested[f],
             "contested_rate": round(field_contested[f] / field_total[f], 3)}
            for f in sorted(field_total, key=lambda f: field_total[f], reverse=True)
        ]
        alliances = [{"a": a, "b": b, "count": c} for (a, b), c in pairs.most_common(12)]

        return {
            "coverage": {"with_factions": with_factions, "total": len(rows)},
            "topic_matrix": {"parties": top, "fields": fields_present, "matrix": matrix},
            "success_rates": success,
            "contention": contention,
            "alliances": alliances,
        }

    # --- Goal tracking ------------------------------------------------------
    def get_goal_candidates(self, keywords: list[str], limit: int = 400,
                            exclude_goal: str | None = None) -> list[dict]:
        """Decisions whose text/tags match any of a goal's keywords (candidates
        for LLM relevance + stance assessment). With ``exclude_goal`` set, skips
        decisions already linked to that goal — for the incremental daily cron."""
        if not keywords:
            return []
        clause = " OR ".join(
            ["d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ? OR d.policy_tags LIKE ?"] * len(keywords)
        )
        params: list = []
        for kw in keywords:
            p = f"%{kw}%"
            params += [p, p, p, p]
        exclude_sql = ""
        if exclude_goal:
            exclude_sql = " AND d.id NOT IN (SELECT decision_id FROM council_goal_links WHERE goal = ?)"
            params.append(exclude_goal)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.official_text, d.summary, d.outcome, cs.session_date
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND ({clause}){exclude_sql}
                ORDER BY cs.session_date DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def save_goal_links(self, goal: str, results: dict) -> int:
        """Upsert assessment results for a goal: id -> {relevant, stance, grund}."""
        rows = [(goal, did, 1 if r.get("relevant") else 0, r.get("stance"), r.get("reason"))
                for did, r in results.items()]
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_goal_links (goal, decision_id, relevant, stance, rationale) "
                "VALUES (?, ?, ?, ?, ?)", rows,
            )
        return len(rows)

    def clear_goal_links(self, goal: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM council_goal_links WHERE goal = ?", (goal,))

    def linked_decision_ids(self, goal: str) -> set:
        """Decision ids already linked to a goal (any relevance) — for incremental runs."""
        return {r[0] for r in self._conn.execute(
            "SELECT decision_id FROM council_goal_links WHERE goal = ?", (goal,))}

    def goal_summary(self) -> dict:
        """Per goal: counts of relevant decisions by stance."""
        agg: dict[str, dict] = {}
        for goal, stance, c in self._conn.execute(
            "SELECT goal, stance, COUNT(*) FROM council_goal_links WHERE relevant = 1 GROUP BY goal, stance"
        ):
            g = agg.setdefault(goal, {"advances": 0, "hinders": 0, "neutral": 0, "total": 0})
            g[stance] = c
            g["total"] += c
        return agg

    def goal_detail(self, goal: str) -> list[dict]:
        """Relevant decisions linked to a goal, newest first, with stance + rationale."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, gl.stance, gl.rationale
               FROM council_goal_links gl
               JOIN council_decisions d ON d.id = gl.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE gl.goal = ? AND gl.relevant = 1
               ORDER BY cs.session_date DESC""",
            (goal,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Semantic similarity (precomputed offline) --------------------------
    def decisions_for_embedding(self) -> list[dict]:
        """All main decisions with a short text for embedding (id + text).

        Teilabstimmungs-Titel (Änderungsanträge, Design 23a) zählen zum Text des
        Haupt-TOPs — sie tragen oft die konkreten Begriffe („Änderungsantrag der
        Fraktion X: Tempo 30 auf …"), die im knappen Hauptbeschluss fehlen."""
        rows = self._conn.execute(
            "SELECT d.id, d.title, d.summary, d.official_text, sv.stext FROM council_decisions d "
            "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' · '), 1, 400) AS stext "
            "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
            "           GROUP BY ksinr, parent_item) sv "
            "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
            "WHERE d.kind = 'decision'"
        ).fetchall()
        out = []
        for r in rows:
            text = f"{r['title'] or ''}. {r['summary'] or r['official_text'] or ''}".strip()[:500]
            if r["stext"]:
                text = f"{text} · {r['stext']}"[:800]
            out.append({"id": r["id"], "text": text})
        return out

    def set_similar(self, rows: list[tuple]) -> int:
        """Replace all similarity links. ``rows`` = (decision_id, neighbor_id, rank, score)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_similar")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_similar (decision_id, neighbor_id, rank, score) "
                "VALUES (?, ?, ?, ?)", rows,
            )
        return len(rows)

    def save_embeddings(self, rows: list[tuple]) -> int:
        """Replace all decision vectors. ``rows`` = (decision_id, float32 bytes)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_embeddings")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_embeddings (decision_id, vector) VALUES (?, ?)", rows,
            )
        return len(rows)

    def get_embeddings(self) -> list:
        """All (decision_id, vector-blob) rows — caller rebuilds the matrix."""
        return self._conn.execute(
            "SELECT decision_id, vector FROM council_embeddings ORDER BY decision_id"
        ).fetchall()

    def embeddings_version(self) -> tuple:
        """Billiger Versionsschlüssel des Embedding-Bestands. Der Matrix-Cache in
        council/embeddings.py lädt neu, sobald sich der Wert ändert — ohne den
        früher nötigen Service-Neustart nach embed_decisions.py. ``data_version``
        deckt dabei auch ein Re-Embedding ab, das Anzahl und ids unverändert
        lässt (Modellwechsel): Es zählt hoch, sobald ein *anderer* Prozess die
        DB-Datei geschrieben hat."""
        count, max_id = self._conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(decision_id), 0) FROM council_embeddings"
        ).fetchone()
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, max_id, data_version)

    # ---- Vorlagen-Chunk-Embeddings (semantische Suche im Sachverhalt) ----

    def vorlagen_missing_embeddings(self) -> list[dict]:
        """Vorlagen (mit Text, an ≥1 Beschluss hängend), deren Chunk-Vektoren
        fehlen oder deren Text sich seit dem letzten Embedding geändert hat.
        Der Abgleich läuft über den SHA-256 des Volltexts (text_hash)."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT template_number, MIN(text_hash) FROM council_template_embeddings GROUP BY template_number"
        ).fetchall())
        rows = self._conn.execute(
            "SELECT v.template_number, MAX(v.raw_text) AS raw_text FROM council_templates v "
            "WHERE v.status = 'ok' AND v.template_number IN "
            "  (SELECT DISTINCT template_number FROM council_decisions "
            "   WHERE kind = 'decision' AND template_number IS NOT NULL AND template_number != '') "
            "GROUP BY v.template_number"
        ).fetchall()
        out = []
        for r in rows:
            text = r["raw_text"] or ""
            if not text.strip():
                continue
            h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["template_number"]) != h:
                out.append({"template_number": r["template_number"], "raw_text": text, "text_hash": h})
        return out

    def replace_vorlage_embeddings(self, template_number: str, text_hash: str,
                                   chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Vorlage komplett ersetzen (alte Chunk-Anzahl
        kann abweichen, deshalb erst löschen)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_template_embeddings WHERE template_number = ?", (template_number,))
            self._conn.executemany(
                "INSERT INTO council_template_embeddings "
                "(template_number, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(template_number, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_vorlage_embeddings(self) -> list:
        """Alle (template_number, chunk_text, vector)-Zeilen — der Aufrufer baut die Matrix."""
        return self._conn.execute(
            "SELECT template_number, chunk_text, vector FROM council_template_embeddings "
            "ORDER BY template_number, chunk_idx"
        ).fetchall()

    def vorlage_embeddings_version(self) -> tuple:
        """Versionsschlüssel analog embeddings_version(), für den Chunk-Matrix-Cache."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_template_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    # ---- Anlagen-Embeddings (Task 33, Dokumentenkanal) ---------------------

    def anlagen_missing_embeddings(self, limit: int | None = None) -> list[dict]:
        """Anlagen mit Text, deren Chunk-Vektoren fehlen oder deren Text sich
        geändert hat (SHA-256-Abgleich wie bei den Vorlagen). Neueste zuerst —
        frisches Material zuerst durchsuchbar."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT document_id, MIN(text_hash) FROM council_anlage_embeddings "
            "GROUP BY document_id").fetchall())
        # `status = 'ok'` schließt nur ungelesene und kaputte Anlagen aus. Wie
        # der Text entstanden ist — Textebene oder Sehmodell — steht in
        # `ocr_model` und ist hier KEIN Kriterium: Ein gescannter
        # Wirtschaftsplan ist so durchsuchbar wie ein getippter.
        rows = self._conn.execute(
            "SELECT a.document_id, a.label, a.raw_text, v.template_number, "
            "       v.title AS template_title FROM council_attachments a "
            "LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()
        out = []
        for r in rows:
            # HIER wird maskiert und nicht beim Speichern: `raw_text` bleibt
            # vollständig (die Parser brauchen ihn), aber was in die
            # Chunk-Vektoren und damit in Antworten der KI-Frage geht, trägt
            # keine Kontonummern, Telefonnummern, E-Mail-Adressen und
            # Anschriften mehr (`council/kontaktdaten.py`).
            text = maskieren(r["raw_text"])
            # v2 nimmt Metadaten in Hash und Vektor auf. Ohne Vorlagentitel
            # waren gleichnamige Umweltberichte verschiedener Baugebiete kaum
            # zu unterscheiden. Der Hash verwendet den maskierten Text: In
            # Vektoren und Antwortfundstellen gelangen weiterhin keine
            # Kontaktdaten.
            material = "\0".join(("anlage-v2", r["label"] or "",
                                  r["template_number"] or "", r["template_title"] or "",
                                  text))
            h = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
            if stored.get(r["document_id"]) != h:
                out.append({"document_id": r["document_id"], "label": r["label"],
                            "template_number": r["template_number"],
                            "template_title": r["template_title"],
                            "raw_text": text, "text_hash": h})
                if limit and len(out) >= limit:
                    break
        return out

    def replace_anlage_embeddings(self, document_id: int, text_hash: str,
                                  chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Anlage komplett ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_anlage_embeddings WHERE document_id = ?", (document_id,))
            self._conn.executemany(
                "INSERT INTO council_anlage_embeddings "
                "(document_id, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(document_id, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_anlage_embeddings(self) -> list:
        """Alle (document_id, chunk_text, vector)-Zeilen für die Matrix."""
        return self._conn.execute(
            "SELECT document_id, chunk_text, vector FROM council_anlage_embeddings "
            "ORDER BY document_id, chunk_idx"
        ).fetchall()

    def anlage_embeddings_version(self) -> tuple:
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_anlage_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    def anlagen_by_ids(self, document_ids: list[int]) -> list[dict]:
        """Anzeige-Zeilen der Anlagen-Treffer, Reihenfolge der ids bleibt:
        Label, PDF-Link und die Vorlage (Nummer + Titel), zu der sie gehören."""
        if not document_ids:
            return []
        ph = ",".join("?" * len(document_ids))
        rows = self._conn.execute(
            f"SELECT a.document_id, a.label, a.url, a.kvonr, "
            f"       v.template_number, v.title AS template_title "
            f"FROM council_attachments a LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            f"WHERE a.document_id IN ({ph})", document_ids).fetchall()
        by_id = {r["document_id"]: dict(r) for r in rows}
        return [by_id[i] for i in document_ids if i in by_id]

    def anlagen_metadata_rows(self) -> list[dict]:
        """Kleine Metadatenliste für den lexikalischen Anlagen-Sicherungsweg.

        Volltexte und Vektoren bleiben in ihren spezialisierten Tabellen; für
        exakte Angaben wie „Bodengutachten Kaiserstraße/Bleicherstraße“ reichen
        Label, Vorlagennummer und -titel. Rund 5.000 kompakte Zeilen sind
        billiger als ein zweiter großer Suchindex.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT a.document_id, a.label, v.template_number, "
            "       v.title AS template_title FROM council_attachments a "
            "LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()]

    def decision_ids_for_vorlagen(self, vorlage_nrs: list[str]) -> dict[str, list[int]]:
        """template_number → Beschluss-ids (alle Beratungsstationen), neueste zuerst.
        Bildet Vorlagen-Chunk-Treffer der semantischen Suche auf zitierbare
        Beschlüsse ab."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"""SELECT d.template_number, d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.template_number IN ({ph})
                ORDER BY cs.session_date DESC, d.id DESC""",
            nrs,
        ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["template_number"], []).append(r["id"])
        return out

    # ---- Laufende Bauleitplan-Beteiligungen (council/beteiligung.py) ----



    # ---- Haushalt als Geldfragen-Quelle (Tim, 09.08.) ----

    #: Themenwörter, die auf einen Teilhaushalt zeigen, ohne dessen Namen zu
    #: teilen. „Kongresshalle" und „Kultur, Museen, Sport" haben keinen
    #: gemeinsamen Wortstamm — rein lexikalisch ist die Zuordnung nicht zu
    #: finden, obwohl sie eindeutig ist. Bewusst knapp gehalten: Jede Zeile
    #: ist eine Behauptung darüber, wo etwas im Haushalt steht.
    HAUSHALTS_SYNONYME = {
        "verkehr": ("mobilität", "radverkehr", "fahrrad", "bus", "parken",
                    "parkgebühren", "straßenbahn", "fußverkehr", "damm"),
        "kultur": ("veranstaltung", "kongress", "halle", "museum", "theater",
                   "bibliothek", "stadion", "schwimmbad", "bäder"),
        "klima": ("baum", "baumschutz", "grünfläche", "natur",
                  "naturschutz", "umweltschutz", "emission"),
        "stadtplanung": ("bebauungsplan", "sanierungsgebiet", "stadtentwicklung",
                         "isek", "flächennutzungsplan", "wohnraum", "leerstand"),
        "schule": ("bildung", "schulbau", "ganztag"),
        "jugend": ("kita", "kindertagesstätte", "krippe", "jugendhilfe",
                   "spielplatz", "familie"),
        # Gemessen 02.09.2026 an der Live-Antwort: „Was stand 2022 im Haushalt
        # für die Feuerwehr?" fand keinen Teilhaushalt — die Feuerwehr heißt
        # dort „Sicherheit und Ordnung", und das sagt kein Fragewortlaut.
        "sicherheit": ("feuerwehr", "brandschutz", "rettungsdienst",
                       "katastrophenschutz", "ordnungsamt", "bürgeramt",
                       "ordnungsdienst"),
        "soziales": ("sozialhilfe", "grundsicherung", "wohngeld", "pflege",
                     "asyl", "geflüchtete", "obdachlos", "gesundheitsamt"),
        "finanzmanagement": ("kämmerei", "stadtkasse", "steuern"),
    }

    @staticmethod
    def _bereich_passt(area: str, woerter: list[str]) -> bool:
        """Trifft eines der Suchwörter diesen Teilhaushalt?

        Der frühere Test lief in die falsche Richtung: ``wort in area``
        findet „Verkehr" in „Verkehr und Straßenbau", aber nicht
        „Radverkehr" — und deutsche Suchbegriffe sind fast immer die
        längeren Komposita. Gemessen am 20.08.2026: „Verkehr" traf, aber
        „Mobilitätsplan", „Radverkehr", „Kongresshalle" und
        „Baumschutzsatzung" lieferten allesamt null Zeilen, obwohl es für
        jedes einen passenden Bereich gibt.

        Deshalb wird der Bereichsname in Wortmarken zerlegt und beidseitig
        geprüft — ein Kompositum trägt sein Grundwort am Ende („Radverkehr"),
        eine Ableitung am Anfang („Mobilitätsplan").
        """
        marken = [t for t in re.split(r"[^a-zäöüß]+", area.lower()) if len(t) >= 4]
        for wort in woerter:
            for mark in marken:
                if wort == mark:
                    return True
                kurz, lang = sorted((wort, mark), key=len)
                # Nur Anfang oder Ende: „Transport" enthält zwar „sport",
                # aber eben nicht am Rand.
                if len(kurz) >= 5 and (lang.startswith(kurz) or lang.endswith(kurz)):
                    return True
                for kopf, synonyme in CouncilStore.HAUSHALTS_SYNONYME.items():
                    if mark.startswith(kopf) and any(
                            wort.startswith(s) or wort.endswith(s) for s in synonyme):
                        return True
        return False

    def haushalt_fuer_begriffe(self, begriffe: list[str], limit: int = 3,
                               year: int | None = None) -> list[dict]:
        """Teilhaushalts-Zeilen des neuesten Jahres, deren Bereich zu einem der
        Suchbegriffe passt („Radverkehr" → „Verkehr und Straßenbau"); fragt
        jemand nach dem Haushalt insgesamt, kommt die Summenzeile. Für den
        Geld-Kontext der KI-Frage — Plan-Zahlen, klar getrennt von Beschlüssen."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_budget", "year", gefragt)
        if not year:
            return []
        # 16 statt 10: Die Begriffe der Gründlichen Recherche kommen aus
        # mehreren Facetten, das treffende Wort steht dort oft weiter hinten.
        woerter = [w.lower() for w in begriffe if len(w) >= 4][:16]
        rows = self._conn.execute(
            "SELECT year, area, revenues, expenses, result, is_total "
            "FROM council_budget WHERE year = ?", (year,)).fetchall()
        out = []
        for r in rows:
            if r["is_total"]:
                if any(w in ("haushalt", "gesamthaushalt", "haushaltsplan") for w in woerter):
                    out.append(dict(r))
                continue
            if self._bereich_passt(r["area"] or "", woerter):
                out.append(dict(r))
        out = out[:limit]
        if abweicht:
            for r in out:
                r["year_asked"] = gefragt
        # Entwicklung mitgeben: derselbe Bereich im ältesten vorhandenen Jahr.
        # Nur bei EXAKT gleichem Namen — die Teilhaushalts-Zuschnitte ändern
        # sich über die Jahre, ein Vergleich über Zuschnittgrenzen wäre falsch.
        if out:
            frueh = self._conn.execute("SELECT MIN(year) FROM council_budget").fetchone()[0]
            if frueh and frueh != year:
                namen = [r["area"] for r in out]
                platz = ",".join("?" * len(namen))
                alt = {
                    r["area"]: r for r in self._conn.execute(
                        f"SELECT area, revenues, expenses FROM council_budget "
                        f"WHERE year = ? AND area IN ({platz})", (frueh, *namen))
                }
                for r in out:
                    a = alt.get(r["area"])
                    if a:
                        r["year_before"] = frueh
                        r["expenses_before"] = a["expenses"]
                        r["revenues_before"] = a["revenues"]
        return out

    #: Suchbegriffe → Steuerart, wie sie im Open-Data-CSV heißt. Bewusst
    #: kuratiert statt Substring-Suche: „Steuer" allein trifft sonst jede Art,
    #: und „Grundsteuer" steckt in „Grundsteuer A+B".
    _STEUER_SYNONYME = {
        "gewerbesteuer": "Gewerbesteuer (-umlage)",
        "gewerbe": "Gewerbesteuer (-umlage)",
        "grundsteuer": "Grundsteuer A+B",
        "grundbesitz": "Grundsteuer A+B",
        "einkommensteuer": "Einkommensteueranteil",
        "einkommenssteuer": "Einkommensteueranteil",
        "umsatzsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "mehrwertsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "vergnügungssteuer": "Vergnügungssteuer",
        "vergnuegungssteuer": "Vergnügungssteuer",
        "getränkesteuer": "Getränkesteuer",
    }

    def steuern_fuer_begriffe(self, begriffe: list[str],
                              year: int | None = None) -> list[dict]:
        """IST-Steuereinnahmen zu den gefragten Steuerarten: neuester Wert plus
        der Wert von vor zehn Jahren (Entwicklung), je Art. Fragt jemand
        allgemein nach „Steuern"/„Einnahmen", kommt die Gesamtsumme.

        Klar getrennt vom Haushalt: Das hier sind ABRECHNUNGSZAHLEN, keine
        Planwerte — der Prompt-Baustein muss das benennen."""
        woerter = {w.lower().strip(".,;:!?") for w in begriffe}
        arten: list[str] = []
        for w in woerter:
            art = self._STEUER_SYNONYME.get(w)
            if art and art not in arten:
                arten.append(art)
        if not arten and woerter & {"steuern", "steuereinnahmen", "steuer",
                                    "einnahmen", "steuerkraft"}:
            arten = ["total"]
        if not arten:
            return []
        neuestes, abweicht = _geld.jahrgang(self._conn, "council_taxes", "year", year)
        if not neuestes:
            return []
        out: list[dict] = []
        for art in arten[:3]:
            rows = self._conn.execute(
                "SELECT year, amount FROM council_taxes WHERE kind = ? AND year IN (?, ?)",
                (art, neuestes, neuestes - 10)).fetchall()
            werte = {r["year"]: r["amount"] for r in rows}
            if neuestes not in werte:
                continue
            out.append({"kind": art, "year": neuestes, "amount": werte[neuestes],
                        "year_before": neuestes - 10 if (neuestes - 10) in werte else None,
                        "amount_before": werte.get(neuestes - 10),
                        **({"year_asked": year} if abweicht else {})})
        return out

    def steuerkraft_kontext(self, year: int | None = None) -> dict | None:
        """Steuerkraftmesszahl + Schlüsselzuweisungen der beiden jüngsten Jahre.

        Für Fragen nach Hebesätzen und „mehr Steuern einnehmen": Steigt die
        eigene Steuerkraft, sinken die Zuweisungen des Landes (NFAG) — ohne
        diesen Kontext klingt jede Mehreinnahme nach vollem Gewinn."""
        wo = "tax_index IS NOT NULL AND allocations IS NOT NULL"
        gewaehlt, abweicht = _geld.jahrgang(self._conn, "council_tax_capacity", "year", year, wo)
        if gewaehlt is None:
            return None
        rows = self._conn.execute(
            f"SELECT year, tax_index, allocations FROM council_tax_capacity WHERE {wo} "
            "AND year <= ? ORDER BY year DESC LIMIT 2", (gewaehlt,)).fetchall()
        if len(rows) < 2:
            return None
        neu, alt = dict(rows[0]), dict(rows[1])
        return {"year": neu["year"], "tax_index": neu["tax_index"], "allocations": neu["allocations"],
                "year_before": alt["year"], "tax_index_before": alt["tax_index"],
                "zuweisungen_davor": alt["allocations"],
                **({"year_asked": year} if abweicht else {})}

    # ---- Der Haushalts-Bestand als Quelle der KI-Frage (Tim, 16.08.) -------
    #
    # Bis hierher kannte die KI-Frage drei Geld-Quellen: Plan (council_budget),
    # Ist-Steuern (council_taxes) und die NFAG-Mechanik (council_tax_capacity).
    # Der Bestand darunter — Jahresabschlüsse, Produktebene, Prüfberichte,
    # Konzern, Städtevergleich — war für sie unsichtbar.
    #
    # ZWEI REGELN GELTEN FÜR ALLE METHODEN HIER:
    #
    # 1. Jede liefert wenige Zeilen, nicht den Bestand. Der Antwort-Prompt hat
    #    ein Zeichenbudget; ein Baustein, der 377 Produkte anhängt, verdrängt
    #    die Beschlüsse, nach denen gefragt wurde.
    # 2. Jede liefert ihren **Beleg** mit (`_beleg`). Eine Zahl ohne Fundstelle
    #    ist in diesem Bereich keine Zahl, sondern eine Behauptung — und der
    #    Prompt kann nur zitieren, was im Kontext steht.

    @staticmethod
    def _falte_wort(wort: str) -> str:
        """Kleingeschrieben, Umlaute ausgeschrieben, Satzzeichen ab."""
        w = wort.lower().strip(".,;:!?\"'()[]")
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            w = w.replace(a, b)
        return w

    @classmethod
    def _stamm(cls, wort: str) -> str:
        """Grober Wortstamm für den Begriffs-Abgleich — auf 6 Zeichen gekappt.

        Die Kappung ist der ganze Zweck. „Gewerbesteuer" und „Steuern und
        ähnliche Abgaben" haben kein gemeinsames Wort und in der einen
        Richtung auch keine gemeinsame Teilzeichenkette
        (``"steuern" not in "gewerbesteuer"``) — wohl aber denselben Stamm
        ``steuer``. Ohne ihn findet „Warum kam mehr Gewerbesteuer rein?" die
        zugehörige Erläuterung des Jahresabschlusses nicht."""
        return cls._falte_wort(wort)[:6]

    @classmethod
    def _trifft(cls, text: str | None, begriffe: list[str]) -> int:
        """Wie viele Suchbegriffe stecken in ``text``? 0 = kein Treffer.

        BEIDE RICHTUNGEN, und das ist nötig: Der Begriff kann im Text stecken
        („Feuerwehr" in „Brandschutz und Feuerwehr") und der Text im Begriff
        („Steuern" in „Gewerbesteuer"). Eine Richtung allein verfehlt je einen
        der beiden Fälle, und beide kommen im Bestand vor."""
        if not text:
            return 0
        worte = [w for w in re.split(r"[^\wÄÖÜäöüß]+", text) if w]
        text_voll = " ".join(cls._falte_wort(w) for w in worte)
        text_staemme = [s for s in (cls._stamm(w) for w in worte) if len(s) >= 4]
        n = 0
        for b in begriffe:
            b_voll = cls._falte_wort(b)
            b_stamm = cls._stamm(b)
            if len(b_stamm) < 4:
                continue
            if b_stamm in text_voll or any(s in b_voll for s in text_staemme):
                n += 1
        return n

    def _beleg(self, herkunft_id: int | None) -> dict | None:
        """Fundstelle einer Zahl: Dokument, Stelle darin, Stichtag.

        Bewusst ohne die Erklärsätze zu den Proben (``get_herkunft``): Die
        gehören auf die Haushalts-Seiten, wo Platz für sie ist. Im Prompt
        zählt, was die Antwort zitieren können muss — Dokument und Stelle."""
        if herkunft_id is None:
            return None
        try:
            r = self._conn.execute(
                "SELECT label, citation, page, as_of, url FROM council_provenance "
                "WHERE id = ?", (herkunft_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(r) if r else None

    def gebuehren_fuer_begriffe(self, begriffe: list[str],
                                limit_jahre: int = 4, year: int | None = None) -> dict | None:
        """Gebührenbedarfsberechnungen passend zur Frage, jüngste zuerst.

        Die Tabelle enthält drei getrennte Kalkulationen. Eine Müllfrage
        braucht beide Abfallbereiche, eine Frage zur Straßenreinigung nur
        deren Anlage; bei einer allgemeinen Gebührenfrage kommen alle drei.
        Jede Zeile trägt ihren eigenen Beleg, weil die Bereiche aus
        unterschiedlichen Anlagen stammen.
        """
        worte = {self._falte_wort(w) for w in begriffe if w}
        text = " ".join(sorted(worte))
        bereiche: list[str] = []
        if any(w in text for w in ("abfall", "muell", "tonne", "behaelter",
                                   "restmuell", "biomuell")):
            bereiche.extend(("waste_treatment", "waste_collection"))
        if any(w in text for w in ("strassenreinig", "kehrgeb", "kehrdienst")):
            bereiche.append("street_cleaning")
        if not bereiche and any(w in text for w in ("gebuehr", "gebuehrenbedarf")):
            bereiche = ["waste_treatment", "waste_collection", "street_cleaning"]
        bereiche = list(dict.fromkeys(bereiche))
        if not bereiche:
            return None
        try:
            platz = ",".join("?" for _ in bereiche)
            rows = [dict(r) for r in self._conn.execute(
                "SELECT year, area, area_name, cost_calculation, deductions, "
                "costs_to_cover, reference_quantity, reference_unit, fee, "
                "fee_proposed, template_number, herkunft_id "
                f"FROM council_fees WHERE area IN ({platz}) "
                "ORDER BY area, year DESC", bereiche)]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        gruppen: list[dict] = []
        # Das gefragte Jahr zuerst, wenn der Bereich es führt — sonst bleibt
        # die Reihenfolge „jüngste zuerst", und der Baustein sagt, dass das
        # gefragte Jahr fehlt.
        vorhanden = {r["year"] for r in rows}
        abweicht = year is not None and year not in vorhanden
        for area in bereiche:
            werte = [r for r in rows if r["area"] == area]
            if year in vorhanden:
                werte = ([r for r in werte if r["year"] == year]
                         + [r for r in werte if r["year"] != year])
            werte = werte[:limit_jahre]
            if not werte:
                continue
            for r in werte:
                r["beleg"] = self._beleg(r.get("herkunft_id"))
            gruppen.append({"area": area,
                            "area_name": werte[0]["area_name"],
                            "werte": werte})
        if not gruppen:
            return None
        return {"bereiche": gruppen, **({"year_asked": year} if abweicht else {})}

    def result_actual_for_terms(self, begriffe: list[str], limit: int = 2,
                                year: int | None = None) -> dict | None:
        """„Geplant und tatsächlich" aus dem jüngsten Jahresabschluss.

        Der Unterschied zu ``haushalt_fuer_begriffe`` ist das ganze Anliegen:
        Dort stehen Planwerte, hier steht, was daraus geworden ist. Geliefert
        werden die Summenzeilen der Gesamtrechnung (Erträge 12, Aufwendungen
        20) und — wenn die Frage einen Bereich nennt — bis zu ``limit``
        Teilhaushalte.

        ``plan_kind`` reist mit: „Plan" heißt 2018 Gesamtermächtigung und 2020
        Ansatz samt Nachtrag. Eine Abweichung ohne ihre Bezugsgröße zu nennen,
        wäre in genau den zwei Jahrgängen falsch, in denen es darauf ankommt."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_income_statement", "year",
                                        gefragt, "result IS NOT NULL")
        if not year:
            return None
        # Die Gesamtrechnung mit ALLEN Posten, die Teilhaushalte nur mit ihren
        # Summen: „Was kostet das Personal?" braucht Posten 13 der Gesamt-
        # rechnung — bis 09/2026 lieferte diese Methode nur die Summen 12/20,
        # und die Antwort kannte den Personalaufwand nicht, obwohl er dastand.
        rows = [dict(r) for r in self._conn.execute(
            "SELECT sub_budget_no, sub_budget_name, nr, label, budgeted, plan, plan_kind, "
            " result, deviation, herkunft_id FROM council_income_statement "
            "WHERE year = ? AND (sub_budget_no IS NULL OR nr IN (12, 20)) "
            "ORDER BY sub_budget_no, nr", (year,))]
        if not rows:
            return None

        def paar(part: list[dict]) -> dict:
            e = next((r for r in part if r["nr"] == 12), {})
            a = next((r for r in part if r["nr"] == 20), {})
            # `plan` fällt auf `ansatz` zurück — Zeilen von vor #510 tragen
            # dort NULL (ALTER TABLE füllt nichts nach), s. get_plan_ist.
            return {
                "name": (a.get("sub_budget_name") or e.get("sub_budget_name")),
                "revenues_planned": e.get("budgeted") if e.get("plan") is None else e.get("plan"),
                "revenues_actual": e.get("result"),
                "expenses_planned": a.get("budgeted") if a.get("plan") is None else a.get("plan"),
                "expenses_actual": a.get("result"),
                "plan_kind": a.get("plan_kind") or e.get("plan_kind"),
                "herkunft_id": a.get("herkunft_id") or e.get("herkunft_id"),
            }

        gesamt_rows = [r for r in rows if r["sub_budget_no"] is None]
        gesamt = paar(gesamt_rows)

        def wert(r: dict) -> tuple:
            return (r.get("budgeted") if r.get("plan") is None else r.get("plan"), r.get("result"))

        # Die Ergebniszeilen (21 ordentlich, 24 außerordentlich) immer: „Wie
        # war das Jahresergebnis?" ist die schlichteste Frage an den Abschluss,
        # und die Summen 12/20 beantworten sie nur über eine Rechnung, die
        # das Modell nicht anstellen soll.
        ergebnis = {}
        for r in gesamt_rows:
            if r["nr"] == 21:
                ergebnis["ordentlich"] = wert(r)
            elif r["nr"] == 24:
                ergebnis["ausserordentlich"] = wert(r)
        # Die einzelnen Posten NUR bei Begriffstreffer (Personal, Zinsen,
        # Transfer, Abschreibungen …) — sonst wären es 22 Zeilen je Frage.
        posten: list[dict] = []
        if begriffe:
            kandidaten = [r for r in gesamt_rows if r["nr"] not in (12, 20, 21, 24)]
            bewertet = [(self._trifft(r.get("label"), begriffe), r) for r in kandidaten]
            posten = [{"nr": r["nr"], "label": r["label"], "planned": wert(r)[0],
                       "actual": r.get("result"), "deviation": r.get("deviation")}
                      for n, r in sorted(bewertet,
                                         key=lambda x: (-x[0], -abs(x[1].get("deviation") or 0)))
                      if n][:3]
        bereiche: list[dict] = []
        if begriffe:
            nach_thh: dict[int, list[dict]] = {}
            for r in rows:
                if r["sub_budget_no"] is not None:
                    nach_thh.setdefault(r["sub_budget_no"], []).append(r)
            bewertet = [(self._trifft(t[0].get("sub_budget_name"), begriffe), paar(t))
                        for t in nach_thh.values()]
            bereiche = [b for n, b in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        return {"year": year, "gesamt": gesamt, "bereiche": bereiche,
                "posten": posten, "ergebnis": ergebnis,
                "beleg": self._beleg(gesamt.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def abweichungsgruende_fuer_begriffe(self, begriffe: list[str],
                                         limit: int = 3, year: int | None = None) -> list[dict]:
        """Das *Warum* zu den Abweichungen, in den Worten der Verwaltung.

        Passt kein Begriff, kommen die **größten** Abweichungen: Wer „Warum
        wich der Haushalt ab?" fragt, meint die, über die es sich zu reden
        lohnt — und der Fragetyp-Filter davor sorgt dafür, dass diese Methode
        gar nicht erst läuft, wenn es nicht um Geld geht."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_variance_reasons", "year", gefragt)
        if not year:
            return []
        rows = [dict(r) for r in self._conn.execute(
            "SELECT year, nr, label, delta_meur, percent, text, herkunft_id "
            "FROM council_variance_reasons WHERE year = ? ORDER BY nr", (year,))]
        treffer = [(self._trifft(f"{r['label']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(treffer, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: -abs(r.get("delta_meur") or 0))[:limit]
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
            if abweicht:
                r["year_asked"] = gefragt
        return passend

    def pruefberichte_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                                    year: int | None = None) -> dict | None:
        """Feststellungen des Rechnungsprüfungsamts zum jüngsten geprüften
        Jahrgang.

        Ohne Begriffs-Treffer kommen die **wiederholten** Beanstandungen
        zuerst: Etwas, das der Prüfer zum wiederholten Mal aufschreibt, ist der
        Kern der Frage „Was wurde beanstandet?" — eine einmalige Randnotiz
        nicht."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_audit_reports", "year", gefragt)
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT year, mark, mark_name, text_number, section, chain, page, text, "
            " herkunft_id FROM council_audit_reports WHERE year = ? ORDER BY seq", (year,))]
        if not rows:
            return None
        rang = {"WB": 0, "B": 1, "H": 2, "K": 3}
        bewertet = [(self._trifft(f"{r['section']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: rang.get(r["mark"], 9))[:limit]
        # Wie viele Feststellungen es insgesamt gibt, gehört dazu: Ohne die
        # Zahl liest sich eine Auswahl von vier wie der ganze Bericht.
        zaehl: dict[str, int] = {}
        for r in rows:
            zaehl[r["mark_name"]] = zaehl.get(r["mark_name"], 0) + 1
        return {"year": year, "feststellungen": passend, "gesamt": len(rows),
                "nach_marke": zaehl, "beleg": self._beleg(rows[0].get("herkunft_id"))}

    def produkte_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                               year: int | None = None) -> dict | None:
        """Aufgaben der Stadt mit Kosten, Amt, **Rechtsgrundlage** und der
        Spielraum-Selbstauskunft des Plans.

        Die Rechtsgrundlage ist der Grund, warum diese Quelle in der KI-Frage
        etwas kann, das keine andere kann: „Muss die Stadt das Theater
        betreiben?" beantwortet kein Beschluss und keine Haushaltszeile —
        ``legal_basis`` schon.

        Anders als ``get_produkte(suche=…)`` verlangt diese Suche **nicht**,
        dass jeder Begriff trifft: Die Suchbegriffe kommen aus der
        Query-Expansion und enthalten Synonyme, die absichtlich nicht alle
        passen. Sortiert wird nach Trefferzahl, dann nach Zuschussbedarf."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_products", "year", gefragt)
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT product_no, product_name, office, expenses, result, "
            " short_description, legal_basis, controllability, herkunft_id "
            "FROM council_products WHERE year = ?", (year,))]
        bewertet = [(self._trifft(f"{r['product_name']} {r.get('office') or ''} "
                                  f"{r.get('short_description') or ''}", begriffe), r)
                    for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: (-x[0], x[1].get("result") or 0))
                   if n][:limit]
        if not passend:
            return None
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
        return {"year": year, "produkte": passend,
                **({"year_asked": gefragt} if abweicht else {})}

    def konzern_kontext(self, year: int | None = None) -> dict | None:
        """Der Konzern Stadt: Erträge, Aufwendungen und die größten Träger.

        Dazu die Kernverwaltung desselben Jahres aus dem Jahresabschluss — die
        Differenz ist der ganze Punkt. „Was kostet die Stadt?" beantwortet der
        Kernhaushalt zu klein, weil Klinikum, Eigenbetriebe und Beteiligungen
        nicht darin stehen."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_group_items", "year", gefragt)
        if not year:
            return None
        # Über die ROLLE, nicht über die Nummer: Posten 15 ist bis 2018 die
        # Ertragssumme und ab 2019 der Versorgungsaufwand (s. Schema-Kommentar).
        summen = {r["role"]: dict(r) for r in self._conn.execute(
            "SELECT role, label, amount, herkunft_id FROM council_group_items "
            "WHERE year = ? AND role IN ('revenues_total', 'expenses_total')", (year,))}
        entity = [dict(r) for r in self._conn.execute(
            "SELECT kind, entity, amount_keur FROM council_group_entities "
            "WHERE year = ? AND kind = 'expenses' AND entity_key != 'konsolidierung' "
            "ORDER BY amount_keur DESC LIMIT 5", (year,))]
        if not summen and not entity:
            return None
        revenues = summen.get("revenues_total") or {}
        expense = summen.get("expenses_total") or {}
        return {"year": year, "revenues": revenues.get("amount"),
                "expenses": expense.get("amount"), "entity": entity,
                "kern": self.kernverwaltung_ist().get(year) or {},
                "beleg": self._beleg(expense.get("herkunft_id")
                                     or revenues.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def staedtevergleich_kontext(self, series: str = "tax_capacity",
                                 year: int | None = None) -> dict | None:
        """Die jüngste Kennzahl einer Reihe für alle acht kreisfreien Städte.

        Eine Kennzahl, nicht alle: Der Vergleich soll die Antwort einordnen
        („Oldenburg liegt auf Platz 5 von 8"), nicht eine Tabelle in den
        Prompt schreiben."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_city_comparison", "year", gefragt,
                                        f"series = '{series}'")
        if not year:
            return None
        indicator = self._conn.execute(
            "SELECT indicator FROM council_city_comparison WHERE series = ? AND year = ? "
            "GROUP BY indicator ORDER BY COUNT(*) DESC, indicator LIMIT 1",
            (series, year)).fetchone()
        if not indicator:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT city, value, unit, herkunft_id FROM council_city_comparison "
            "WHERE series = ? AND year = ? AND indicator = ? ORDER BY value DESC",
            (series, year, indicator[0]))]
        if not rows:
            return None
        return {"year": year, "series": series, "indicator": indicator[0],
                "unit": rows[0].get("unit"), "staedte": rows,
                "beleg": self._beleg(rows[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def ansatz_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                             year: int | None = None,
                             frage: list[str] | None = None) -> dict | None:
        """Einnahme- und Ausgabearten des jüngsten **Planjahres** aus dem
        Gesamtergebnishaushalt.

        Nur ``kind='budget'``: Die Finanzplanungsjahre desselben Dokuments sind
        eine Vorausschau nach § 8 NKomVG und kein beschlossener Haushalt. Sie
        in einen Antwort-Kontext zu legen hieße, dem Modell einen Plan für
        2029 anzubieten, den nie jemand aufgestellt hat."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_income_budget", "year", gefragt,
                                        "kind = 'budget'")
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT nr, label, amount, is_total, herkunft_id "
            "FROM council_income_budget WHERE year = ? AND kind = 'budget' ORDER BY nr",
            (year,))]
        if not rows:
            return None
        bewertet = [(self._trifft(r["label"], begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        # `treffer` sagt dem Aufrufer, ob die Begriffe einen Posten getroffen
        # haben: Dann ist der Baustein die Antwort (Personalaufwendungen,
        # Zinsen, Transfer) und gehört in den Kontext, auch wenn `council_budget`
        # schon einen Teilhaushalt liefert.
        # Gemessen am ROHEN Fragewortlaut, wenn er mitkommt: Die expandierten
        # Begriffe sind zum Finden gut und zum Entscheiden zu weit.
        treffer = bool(passend) and (frage is None or any(
            self._trifft(r["label"], frage) for r in passend))
        # Zu jedem getroffenen Posten das jüngste Ist derselben Nummer aus der
        # Ergebnisrechnung: „Personalaufwendungen: Ansatz 2026 209,4 Mio. €,
        # zuletzt abgerechnet 2024: 184,8 Mio. €". Die Facette `ist` feuert bei
        # „Was kostet das Personal?" nicht (kein Ist-Wort), und ohne diese
        # Spalte bliebe die Antwort beim Plan — die Live-Messung vom 02.09.
        # zeigte genau das.
        if treffer:
            for r in passend:
                try:
                    z = self._conn.execute(
                        "SELECT year, result FROM council_income_statement "
                        "WHERE sub_budget_no IS NULL AND nr = ? AND result IS NOT NULL "
                        "ORDER BY year DESC LIMIT 1", (r["nr"],)).fetchone()
                except sqlite3.OperationalError:
                    z = None
                if z:
                    r["actual_year"], r["actual"] = z["year"], z["result"]
        if not passend:
            # Ohne Treffer die Summenzeilen — sie beantworten „was nimmt die
            # Stadt ein, was gibt sie aus" und sind nie daneben.
            passend = [r for r in rows if r["is_total"]][:limit]
        if not passend:
            return None
        return {"year": year, "posten": passend, "treffer": treffer,
                "beleg": self._beleg(passend[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    # ---- Vier Schichten, die die KI-Frage nicht kannte (Tim, 17.08.) -------
    #
    # Der Bestand ist seit der Runde oben um vier Schichten gewachsen, und die
    # KI-Frage beantwortete deren Fragen mit den Quellen, die sie schon kannte
    # — also falsch:
    #
    #   „Wie viel Schulden hat Oldenburg?"      → Ergebnishaushalt. Schulden
    #        sind ein BESTAND am Stichtag, kein Jahresverlauf; in der
    #        Ergebnisrechnung stehen sie überhaupt nicht.
    #   „Was wird gebaut?"                      → Ergebnishaushalt, in dem
    #        keine einzige Investition steht (ein Schulneubau taucht dort nur
    #        als Abschreibung auf, verteilt über Jahrzehnte).
    #   „Wie viele Stellen sind unbesetzt?"     → Personalaufwendungen in Euro.
    #   „Wer wollte den Haushalt ändern?"       → gar nichts, obwohl 664
    #        Änderungslisten im Bestand liegen.
    #
    # Es gelten dieselben zwei Regeln wie für den Abschnitt darüber: wenige
    # Zeilen statt Bestand, und jede Zahl mit ihrem Beleg.

    def schulden_kontext(self, year: int | None = None) -> dict | None:
        """Der Schuldenstand: jüngstes Jahr, Vorjahr, höchster Stand der Reihe.

        Ein **Bestand**, kein Jahresverlauf — und genau deshalb eine eigene
        Quelle. Der Haushaltsplan sagt, was die Stadt in einem Jahr einnimmt
        und ausgibt; was am 31.12. an Krediten offen ist, sagt er nicht.

        Die Abgrenzung reist als Feld mit (``council.schulden.ABGRENZUNG``)
        und ist nicht schmückendes Beiwerk: Gezählt wird die Stadt als
        Rechtsträger — Kernhaushalt und Eigenbetriebe, ohne die rechtlich
        selbstständigen Beteiligungen. Die Konzern-Zahl heißt genauso und ist
        ein Vielfaches; ohne den Satz daneben ist „337 Mio. €" eine von zwei
        Zahlen, die beide so heißen.

        Die vier Artenspalten dürfen NULL sein (Fall 2022, s.
        ``council/schulden.py``) — dann kommt die Aufteilung nicht mit, und
        ``breakdown_rejected`` sagt, warum.
        """
        from council import schulden as _schulden

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_debt ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        # Das gefragte Jahr, wenn die Reihe es führt — sonst das jüngste, und
        # der Baustein sagt, dass es nicht das gefragte ist.
        idx = next((i for i, r in enumerate(rows) if r["year"] == year), len(rows) - 1)
        abweicht = year is not None and rows[idx]["year"] != year
        rows_bis = rows[:idx + 1]
        neu = rows[idx]
        arten = [(title, neu[field]) for field, title in _schulden.SPALTEN
                 if field not in ("total", "per_capita")
                 and neu.get(field) is not None]
        # Der höchste Stand der Reihe ist eine Angabe der Daten, keine
        # Bewertung: Er sagt, ob die jüngste Zahl im historischen Vergleich
        # oben oder unten liegt — sonst schwebt sie ohne jeden Maßstab.
        hoch = max(rows, key=lambda r: r["total"])
        return {
            "year": neu["year"],
            "total": neu["total"],
            "per_capita": neu.get("per_capita"),
            "arten": arten,
            "breakdown_rejected": neu.get("breakdown_rejected"),
            "revised": bool(neu.get("revised")),
            "davor": ({"year": rows_bis[-2]["year"], "total": rows_bis[-2]["total"]}
                      if len(rows_bis) > 1 else None),
            "hoch": ({"year": hoch["year"], "total": hoch["total"]}
                     if hoch["year"] != neu["year"] else None),
            "reihe_ab": rows[0]["year"],
            "abgrenzung": _schulden.ABGRENZUNG,
            **({"year_asked": year} if abweicht else {}),
            "beleg": self._beleg(neu.get("herkunft_id")),
            "weitere": self._schulden_abgrenzungen(),
            "buergschaften": self._buergschafts_kontext(),
        }

    def haushalts_anschluss(self, decision_id: int, template_number: str | None) -> dict | None:
        """Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht.

        Die Beschluss-Seite verweist seit H-21 auf den Haushalt — aber
        pauschal („wie sich das im Gesamthaushalt ausnimmt"). Das ist für
        jeden Beschluss derselbe Satz und deshalb für keinen eine Auskunft.

        Hier steht nur, was **belegt** ist. Zwei Fälle gibt es im Bestand, und
        beide hängen an einer echten Verknüpfung, nicht an einer Textsuche:

        * **Nachbewilligung** — ``council_supplementary_approvals.decision_id``
          zeigt auf genau diese Zeile. Der Betrag steht dann in der
          Jahressumme, die ``/haushalt/plan-ist`` zeigt.
        * **Bürgschaft** — die Vorlage steht im Zeitstrahl auf
          ``/haushalt/schulden``.

        Trifft keiner der beiden zu, kommt ``None`` — und die Seite lässt die
        Karte weg, statt einen Satz zu zeigen, der überall gleich stünde.
        """
        try:
            r = self._conn.execute(
                "SELECT template_number, title, amount, year FROM council_supplementary_approvals "
                "WHERE decision_id = ? LIMIT 1", (decision_id,)).fetchone()
        except sqlite3.OperationalError:
            r = None
        if r:
            return {"art": "nachbewilligung", "href": "/haushalt/plan-ist",
                    "year": r["year"], "amount": r["amount"],
                    "title": r["title"], "template_number": r["template_number"]}

        if template_number:
            try:
                b = self._conn.execute(
                    "SELECT title FROM council_templates "
                    "WHERE template_number = ? AND title LIKE '%bürgschaft%'",
                    (template_number,)).fetchone()
            except sqlite3.OperationalError:
                b = None
            if b:
                return {"art": "buergschaft", "href": "/haushalt/schulden",
                        "title": b["title"], "template_number": template_number}
        return None


    def _schulden_abgrenzungen(self) -> list[dict]:
        """Die ANDEREN beiden Zahlen, die auch „die Schulden der Stadt" heißen.

        Es gibt drei, sie unterscheiden sich um das Siebzehnfache, und jede
        ist für ihre Abgrenzung richtig (Stand 31.12.2024):

        * **43,7 Mio. €** — die Geldschulden des Kernhaushalts allein, wie sie
          in der Bilanz des Jahresabschlusses stehen.
        * **294,9 Mio. €** — die Stadt als Rechtsträger, also mit ihren
          Eigenbetrieben. Das ist die Reihe des Statistischen Jahrbuchs, die
          Zahl im Block darüber.
        * **740,3 Mio. €** — der ganze „Konzern Stadt", anteilig nach
          Beteiligungshöhe, aus dem Tabellenband der Statistischen Ämter.

        Ohne diese Liste beantwortet die KI-Frage „Wie hoch sind die Schulden?"
        mit **einer** Zahl, und welche das ist, entscheidet der Zufall der
        Facette. Die drei nebeneinander sind die ehrliche Antwort — addiert
        werden dürfen sie nie, sie enthalten einander.
        """
        aus: list[dict] = []
        try:
            r = self._conn.execute(
                "SELECT year, value FROM council_balance_sheet WHERE role = 'financial_liabilities' "
                "ORDER BY year DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Kernhaushalt (nur Geldschulden)", "year": r["year"],
                            "amount": r["value"],
                            "source": "Bilanz des Jahresabschlusses"})
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            pass
        try:
            r = self._conn.execute(
                "SELECT year, total FROM council_integrated_debt "
                "ORDER BY year DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Konzern Stadt (anteilig, mit Beteiligungen)",
                            "year": r["year"], "amount": r["total"],
                            "source": "Integrierte Schulden der Statistischen Ämter"})
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            pass
        return aus

    def bilanz_kontext(self, year: int | None = None) -> dict | None:
        """Was der Stadt gehört und wem es zusteht — der jüngste Stichtag.

        Die Bilanz ist die einzige Quelle des Bereichs, die einen **Stichtag**
        zählt und kein Jahr. Ihre Beträge mit Erträgen oder Aufwendungen zu
        verrechnen wäre der Fehler, gegen den diese Methode gebaut ist: „Die
        Stadt hat 1,48 Mrd. €" und „die Stadt gibt 799 Mio. € aus" sind zwei
        Sätze über zwei verschiedene Dinge.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_balance_sheet", "year", gefragt)
        if year is None:
            return None
        posten = {r["role"]: r["value"] for r in self._conn.execute(
            "SELECT role, value FROM council_balance_sheet WHERE year = ? AND role IS NOT NULL",
            (year,))}
        aktiva = ("intangible_assets", "tangible_assets", "financial_assets",
                  "cash_and_equivalents", "prepaid_expenses")
        summe = sum(posten[r] for r in aktiva if r in posten) or None
        beleg = self._conn.execute(
            "SELECT herkunft_id FROM council_balance_sheet WHERE year = ? LIMIT 1",
            (year,)).fetchone()
        return {
            "year": year,
            "bilanzsumme": summe,
            "posten": [(r, posten[r]) for r in
                       ("tangible_assets", "infrastructure_assets", "financial_assets",
                        "cash_and_equivalents", "net_position", "special_items",
                        "provisions", "pension_provisions", "liabilities")
                       if r in posten],
            "beleg": self._beleg(beleg["herkunft_id"] if beleg else None),
            **({"year_asked": gefragt} if abweicht else {}),
        }

    def kassensicht_kontext(self, year: int | None = None) -> dict | None:
        """Was tatsächlich geflossen ist — die Finanzrechnung (Abschnitt 4.1).

        Die zweite Rechnung desselben Jahresabschlusses, und sie kann der
        ersten scheinbar widersprechen: Für 2024 weist die Ergebnisrechnung
        einen Überschuss aus und die Finanzrechnung einen Fehlbetrag an
        Finanzmitteln. Beides stimmt — die eine bucht, wenn ein Anspruch
        entsteht, die andere, wenn Geld fließt. Ohne die zweite Zahl entsteht
        ein falscher Eindruck, und zwar in beide Richtungen.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_cash_flow_statement", "year", gefragt)
        if year is None:
            return None
        zeilen = [dict(r) for r in self._conn.execute(
            "SELECT nr, label, result, role, herkunft_id "
            "FROM council_cash_flow_statement WHERE year = ? ORDER BY nr", (year,))]
        if not zeilen:
            return None
        # Nur die Summenzeilen: Die Einzelposten sind die Ertragsarten und
        # stehen schon im Ergebnisrechnungs-Block.
        summen = [z for z in zeilen if z.get("role")]
        return {"year": year,
                "zeilen": [(z["label"], z["result"], z["role"]) for z in summen],
                "beleg": self._beleg(zeilen[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def nachbewilligungen_kontext(self, year: int | None = None) -> dict | None:
        """Was beschlossen wurde, NACHDEM der Haushalt beschlossen war (§ 117).

        Die Zahl, die der Haushaltsplan nicht kennt und der Jahresabschluss
        nur als Summe zeigt. Sie ist außerdem die einzige Stelle, an der
        sichtbar wird, wie viel der Rat selbst entschieden hat: 2022 waren es
        89 % der Nachbewilligungen, 2024 nur noch 73 %.
        """
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_supplementary_years ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        row = next((r for r in rows if r["year"] == year), rows[-1])
        abweicht = year is not None and row["year"] != year
        channels = []
        try:
            channels = [(r["channel"], r["amount_operating"], r["amount_capital"])
                       for r in self._conn.execute(
                           "SELECT channel, amount_operating, amount_capital "
                           "FROM council_supplementary_channels WHERE year = ?",
                           (row["year"],))]
        except sqlite3.OperationalError:
            pass
        return {"year": row["year"],
                "konsumtiv": row.get("total_operating"),
                "investiv": row.get("total_capital"),
                "gesamt": (row.get("total_operating") or 0)
                          + (row.get("total_capital") or 0),
                "commitments": row.get("commitments_amount"),
                "channels": channels,
                "probe_text": row.get("probe_text") if not row.get("probe_ok") else None,
                "beleg": self._beleg(row.get("herkunft_id")),
                **({"year_asked": year} if abweicht else {})}

    def kennzahlen_kontext(self, limit: int = 13, year: int | None = None) -> dict | None:
        """Die dreizehn Kennzahlen — jeweils der jüngste Stand, mit Rechenweg.

        Die einzige Quelle des Bereichs, die ihre eigenen Formeln mitliefert.
        Deshalb darf die Antwort eine Quote nennen, ohne sie zu erfinden — und
        deshalb steht der Rechenweg im Kontext, nicht nur der Wert.

        ``korrekturen`` sind die Stellen, an denen ein späterer Bericht eine
        Zahl still geändert hat. Wer nach der Steuerquote 2021 fragt, soll
        nicht die erste gedruckte Fassung bekommen, ohne dass jemand sagt,
        dass es eine zweite gab.
        """
        from council import indicators as _kz

        staende = self.get_kennzahlen()
        if not staende:
            return None
        series = _kz.neueste(staende)
        _, funde = _kz.ueberlappungsprobe(staende)
        formeln = {}
        for f in self.get_kennzahl_formeln():
            formeln[f["indicator"]] = f["formula"]
        jahre = {z["year"] for z in series}
        juengstes = year if year in jahre else max(jahre)
        abweicht = year is not None and juengstes != year
        aktuell = [z for z in series if z["year"] == juengstes][:limit]
        label = {k.key: k.label for k in _kz.KENNZAHLEN}
        unit = {k.key: k.unit for k in _kz.KENNZAHLEN}
        return {
            "year": juengstes,
            "werte": [(label.get(z["indicator"], z["indicator"]), z["value"],
                       unit.get(z["indicator"], "eur"), z["decimals"],
                       formeln.get(z["indicator"]))
                      for z in aktuell],
            # Mit Einheit, damit der Prompt-Baustein „45,90 %" schreiben kann
            # und nicht „45.9" — im deutschen Fließtext ist das ein Zahlwort
            # mit falschem Trennzeichen und ohne Einheit.
            "korrekturen": [(label.get(f["indicator"], f["indicator"]), f["year"],
                             f["alt"], f["alt_bericht"], f["neu"], f["neu_bericht"],
                             unit.get(f["indicator"], "eur"))
                            for f in funde if f["art"] == "revision"],
            "beleg": self._beleg(aktuell[0].get("herkunft_id") if aktuell else None),
            **({"year_asked": year} if abweicht else {}),
        }

    def _buergschafts_kontext(self) -> dict | None:
        """Wofür die Stadt geradesteht — die Zahl, die in keiner Schuldenreihe steht.

        Eine Bürgschaft kostet nichts, solange sie nicht gezogen wird, und
        taucht deshalb in keiner der drei Schuldenzahlen auf. Ende 2024 waren
        es 220,3 Mio. € — das Fünffache der eigenen Geldschulden des
        Kernhaushalts. Wer nach den Schulden fragt, bekommt das dazu, aber
        ausdrücklich als **eigene** Größe: Eine Bürgschaft ist keine Schuld.
        """
        try:
            r = self._conn.execute(
                "SELECT year, balance, reason, herkunft_id FROM council_buergschaften "
                "ORDER BY year DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not r:
            return None
        rueck = None
        try:
            z = self._conn.execute(
                "SELECT value FROM council_balance_sheet WHERE role = 'guarantee_provisions' "
                "AND year = ?", (r["year"],)).fetchone()
            rueck = z["value"] if z else None
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            pass
        return {"year": r["year"], "balance": r["balance"], "reason": r["reason"],
                "rueckstellung": rueck, "beleg": self._beleg(r["herkunft_id"])}

    def investitionen_fuer_begriffe(self, begriffe: list[str],
                                    limit: int = 3, year: int | None = None) -> dict | None:
        """Was die Stadt bauen und kaufen will — Summenzeile und die
        Teilhaushalte, die zur Frage passen.

        Die andere Hälfte des Haushaltsplans. Sie mit dem Ergebnishaushalt in
        einem Satz zu verrechnen wäre der Fehler, gegen den diese Methode
        gebaut ist: Es sind zwei Haushalte mit zwei Zahlenwerken.

        Geliefert wird die **Summenzeile der Datei** (``level``
        ``investitionen``) — das Ziel der Rechenprobe, nicht unsere Addition.
        Der *Gesamtbetrag des Finanzhaushaltes* (``level``
        ``finanzhaushalt``) bleibt bewusst draußen: Er zählt die laufende
        Verwaltungstätigkeit mit, ist von keiner Probe der Datei gedeckt und
        stünde im Prompt direkt neben einer geprüften Zahl.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_investments", "year", gefragt,
                                        "level = 'investments'")
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT level, sub_budget_no, label, inflows, outflows, herkunft_id "
            "FROM council_investments WHERE year = ? AND level IN "
            "('investments', 'sub_budget') ORDER BY sub_budget_no", (year,))]
        gesamt = next((r for r in rows if r["level"] == "investments"), None)
        if not gesamt:
            return None
        teile = [r for r in rows if r["level"] == "sub_budget"]
        bewertet = [(self._trifft(r["label"], begriffe), r) for r in teile]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            # Ohne Begriffs-Treffer die größten Brocken: „Was wird gebaut?"
            # meint die, über die zu reden sich lohnt.
            passend = sorted(teile, key=lambda r: -(r["outflows"] or 0))[:limit]
        return {"year": year, "gesamt": gesamt, "teilhaushalte": passend,
                "beleg": self._beleg(gesamt.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def stellenplan_kontext(self, budget_year: int | None = None) -> dict | None:
        """Die Gesamtzeilen des Stellenplans — Stellen, filled, nicht besetzt.

        Die einzige Schicht des Haushalts, die nicht in Euro rechnet. Auf
        „Wie viele Stellen sind unbesetzt?" antwortet keine Euro-Zahl.

        DREI DINGE, DIE MITREISEN MÜSSEN, weil die Zahlen sonst falsch gelesen
        werden:

        1. Die Besetzungszahlen gehören zur **Vorjahresspalte**, nicht zum
           Haushaltsjahr — geplant wird vorwärts, gezählt werden kann nur
           rückwärts (``as_of_date`` sagt, auf welchen Tag). ``positions_planned``
           minus ``besetzt`` mischt zwei Stichtage und steht in keinem
           Dokument; ``vacant`` steht dort, und zwar als eigene Spalte.
        2. Teil A und Teil B sind zwei Tabellen mit zwei Rechenproben, und sie
           kommen einzeln herein. ``fehlend`` sagt, welcher Teil eines
           Jahrgangs **nicht** vorliegt — ohne das sähe ein halber Jahrgang
           wie ein ganzer aus.
        3. Es gibt im Plan keine Zeile „Stellen insgesamt". Diese Methode
           bildet auch keine: Was hier steht, steht so im Dokument.
        """
        gefragt = budget_year
        budget_year, abweicht = _geld.jahrgang(self._conn, "council_staff_plan", "budget_year",
                                               gefragt, "kind = 'total'")
        if not budget_year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT part, label, positions_planned, positions_prior_year, filled, "
            " vacant, as_of_date, herkunft_id FROM council_staff_plan "
            "WHERE budget_year = ? AND kind = 'total' ORDER BY part", (budget_year,))]
        if not rows:
            return None
        from council import stellenplan as _stellenplan

        for r in rows:
            r["teil_name"] = _stellenplan.TEIL_NAMEN.get(r["part"], r["part"])
        fehlend = [t for t in sorted(_stellenplan.TEIL_NAMEN)
                   if t not in {r["part"] for r in rows}]
        return {
            "budget_year": budget_year,
            "as_of_date": next((r["as_of_date"] for r in rows if r.get("as_of_date")), None),
            "teile": rows,
            "fehlend": [_stellenplan.TEIL_NAMEN[t] for t in fehlend],
            "beleg": self._beleg(rows[0].get("herkunft_id")),
            **({"year_asked": gefragt} if abweicht else {}),
        }

    def haushaltsantraege_kontext(self, year: int | None = None,
                                  limit: int = 8) -> dict | None:
        """Wer wollte am Haushalt etwas ändern — und kam damit durch?

        Die leichte Schwester von ``haushalt_streit``: dieselben Anker, aber
        ohne Debatte und ohne Protokoll-Volltext. Die Wortbeiträge kommen im
        Antwort-Prompt ohnehin über ``_debatten_block``; das Zerlegen jedes
        Protokolls kostete in einem Web-Request mehr, als es dort einbrächte.

        Gezählt statt aufgezählt: Ein Jahrgang bringt es auf mehrere Dutzend
        Änderungslisten, und „CDU: 9 Listen, 2 angenommen, 7 abgelehnt" sagt
        dasselbe wie neun Titelzeilen, die alle „Änderungsliste der
        CDU-Fraktion zum Ergebnishaushalt" heißen.

        ``year`` ist das **Haushaltsjahr**, nicht das Sitzungsjahr: Der
        Haushalt 2026 wurde im Februar 2026 beschlossen, der Haushalt 2023 im
        Dezember 2022. Ohne Angabe kommt der jüngste Jahrgang.

        WAS DIESE QUELLE NICHT WEISS, und was der Baustein dazu deshalb
        ausdrücklich sagt: den **Inhalt** einer Änderungsliste. Welche Position
        um welchen Betrag — das liegt in den Anlagen-PDFs der Vorlage, die
        nicht als Volltext im Bestand sind.
        """
        from council import haushaltsdebatte as hd

        try:
            rows = self._conn.execute(
                "SELECT d.ksinr, d.item_number, d.title, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.kind = 'decision' AND (d.title LIKE 'Haushaltssatzung und Haushaltsplan%' "
                "   OR d.title LIKE 'Haushalt 2%')").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        anker: dict[int, dict[int, dict]] = {}
        for r in rows:
            title = (r["title"] or "").strip()
            satzung = self._STREIT_SATZUNG.match(title)
            sammel = self._STREIT_SAMMEL.match(title)
            if not satzung and not sammel:
                continue
            j = int((satzung or sammel).group(1))
            st = anker.setdefault(j, {}).setdefault(r["ksinr"], {
                "ksinr": r["ksinr"], "committee": r["committee"],
                "date": r["session_date"], "top": None, "official_text": None})
            if sammel:
                # Der Sammelpunkt selbst ist die verlässlichste Angabe.
                st["top"] = (r["item_number"] or "").strip() or st["top"]
            else:
                if not st["top"]:
                    st["top"] = self._streit_oberpunkt(r["item_number"])
                st["official_text"] = {"outcome": r["outcome"], "vote": r["vote"]}
        if not anker:
            return None
        gewaehlt = year if year in anker else max(anker)
        abweicht = year is not None and gewaehlt != year

        stationen = []
        for st in sorted(anker[gewaehlt].values(),
                         key=lambda s: (s["date"], s["committee"] == "Rat", s["ksinr"])):
            if not st["top"]:
                continue
            praefix = st["top"] + "."
            entity: dict[str, dict] = {}
            verwaltung = gesamt = 0
            for r in self._conn.execute(
                    "SELECT ksinr, item_number, title, outcome, vote FROM council_decisions "
                    "WHERE ksinr = ? AND kind = 'subvote' ORDER BY position",
                    (st["ksinr"],)).fetchall():
                nr = (r["item_number"] or "").strip()
                if nr != st["top"] and not nr.startswith(praefix):
                    continue
                antrag = hd.antrag_aus_zeile(dict(r))
                if not antrag:
                    continue
                gesamt += 1
                if antrag.ist_verwaltung:
                    verwaltung += 1
                    continue
                # Gemeinsame Listen zählen für ALLE Beteiligten — „SPD/Grüne"
                # ist keine Fraktion, sondern zwei, die sich zusammengetan
                # haben. Sie unter einem Kunstnamen zu führen ließe die Frage
                # „Wie viele Anträge stellte die SPD?" ins Leere laufen.
                for name in (antrag.author or "").split(" / "):
                    if not name:
                        continue
                    e = entity.setdefault(name, {"name": name, "count": 0,
                                                  "accepted": 0, "rejected": 0})
                    e["count"] += 1
                    if antrag.outcome == "accepted":
                        e["accepted"] += 1
                    elif antrag.outcome == "rejected":
                        e["rejected"] += 1
            if not gesamt:
                continue
            stationen.append({
                "committee": st["committee"], "date": st["date"],
                "author": sorted(entity.values(), key=lambda u: (-u["count"], u["name"]))[:limit],
                "verwaltung": verwaltung, "gesamt": gesamt,
                "official_text": st["official_text"],
            })
        if not stationen:
            return None
        # Die LETZTEN beiden Stationen, nicht die ersten: In Oldenburg sind das
        # der Ausschuss für Finanzen und Beteiligungen und der Rat, und der Rat
        # tagt zuletzt. Käme je eine dritte Station dazu, fiele damit die
        # früheste heraus — nie die entscheidende.
        return {"year": gewaehlt, "years": sorted(anker),
                "stationen": stationen[-2:],
                **({"year_asked": year} if abweicht else {})}

    # ---- Teilvoten aus raw_result (welche Fraktion stimmte wie) ----

    def save_decision_votes(self, decision_id: int, votes: list[tuple[str, str]]) -> None:
        """Geparste (faction, stance)-Zeilen eines Beschlusses ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id = ?", (decision_id,))
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                "VALUES (?, ?, ?)",
                [(decision_id, f, s) for f, s in votes],
            )

    def decision_votes_for(self, decision_ids: list[int]) -> dict[int, list[dict]]:
        """decision_id → [{faction, stance}] für Anzeige/Auswertung."""
        if not decision_ids:
            return {}
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT decision_id, faction, stance FROM council_decision_votes "
            f"WHERE decision_id IN ({ph}) ORDER BY faction", decision_ids,
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append(
                {"faction": r["faction"], "stance": r["stance"]})
        return out

    def decisions_with_raw_result(self) -> list[dict]:
        """Alle Beschlüsse mit Abstimmungssatz — Eingabe für den Teilvoten-Backfill."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, raw_result FROM council_decisions "
            "WHERE raw_result IS NOT NULL AND raw_result != ''"
        ).fetchall()]

    # ---- Pressemitteilungen der Stadt (council/presse.py) ----









    # ---- field recaps (auto-generated LLM summaries per policy field) ----




    def get_similar(self, decision_id: int, limit: int = 5) -> list[dict]:
        """The most similar decisions to ``decision_id`` (precomputed), best first.
        Near-duplicate twins (the same matter in another committee, or a recurring
        series) are collapsed via the normalised title, so the neighbours shown are
        genuinely distinct rather than the Ausschuss/Rat copy of this very decision."""
        base = self._conn.execute(
            "SELECT title, template_number FROM council_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, sl.score
               FROM council_similar sl
               JOIN council_decisions d ON d.id = sl.neighbor_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE sl.decision_id = ? ORDER BY sl.rank LIMIT ?""",
            (decision_id, limit * 5),
        ).fetchall()
        seen = set(_dedup_keys(base["title"], base["template_number"], decision_id)) if base else set()
        out: list[dict] = []
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(dict(r))
            if len(out) >= limit:
                break
        return out

    def orte_fuer_decisions(self, ids: list[int]) -> dict[int, dict]:
        """Bestbelegter Ort je Beschluss für die Mini-Karte.

        Die explizite Orts-Pipeline gewinnt; alte Themen-Entitäten bleiben als
        Fallback, solange der historische Backfill noch nicht vollständig ist.
        """
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        direct = self._conn.execute(
            f"""SELECT dl.decision_id, l.name, l.lat, l.lon
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                WHERE dl.decision_id IN ({ph}) AND l.lat IS NOT NULL
                  AND l.district IS NOT NULL AND l.district != ''
                ORDER BY dl.confidence DESC, l.name""", ids).fetchall()
        out: dict[int, dict] = {}
        for r in direct:
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
        rows = self._conn.execute(
            f"""SELECT l.decision_id, e.name, m.lat, m.lon
                FROM council_entity_links l
                JOIN council_entities e ON e.id = l.entity_id
                JOIN council_entity_meta m ON m.slug = e.slug
                WHERE l.decision_id IN ({ph}) AND m.lat IS NOT NULL
                  AND e.kind = 'place'
                ORDER BY e.n DESC""",
            ids,
        ).fetchall()
        from council import geo

        for r in rows:
            # Alte Entitäts-Geocodes entstanden vor der expliziten
            # Orts-Pipeline und können Vergleichsorte außerhalb Oldenburgs
            # enthalten. Nur Koordinaten innerhalb eines Ratslotse-
            # Ortsbereichspolygons dürfen als Karten-Pin erscheinen.
            if not geo.ortsbereich_for(r["lat"], r["lon"]):
                continue
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
        return out

    # ---- Wortbeiträge aus Protokollen (Task 16) ----------------------------











    def replace_protocol_text(self, ksinr: int, raw_text: str, n_pages: int,
                              page_offsets: list[int]) -> None:
        """Backfill: Volltext + Seiten-Offsets gemeinsam ersetzen — die
        Offsets gelten exakt für DIESEN Text, getrennt gespeichert wären
        sie wertlos."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_protocols SET raw_text = ?, n_pages = ?, page_offsets = ? "
                "WHERE ksinr = ?",
                (raw_text, n_pages, json.dumps(page_offsets), ksinr))

    def protokoll_urls_fuer(self, ksinrs: list[int | None]) -> dict[int, str]:
        """ksinr → getfile-URL des öffentlichen Protokoll-PDFs. Macht die
        Wortbeitrags-Belege der KI-Frage nachlesbar: Jeder Beitrag stammt aus
        genau einem Protokoll, und dessen URL steht längst in der DB."""
        ids = sorted({int(k) for k in ksinrs if k})
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT ksinr, document_url FROM council_protocols "
            f"WHERE ksinr IN ({ph}) AND document_url IS NOT NULL", ids).fetchall()
        return {r["ksinr"]: r["document_url"] for r in rows}

    # Sammel-TOPs: Hier landet alles, was sonst nirgends hingehört. Ein Treffer
    # darauf koppelt keine Debatte ZUR SACHE, sondern eine Wundertüte.
    _SAMMEL_TOPS = ("anfragen und anregungen", "einwohnerfragestunde",
                    "genehmigung der tagesordnung", "mitteilungen",
                    "verschiedenes", "niederschrift")







    def partei_meinungen_cache_get(self, key: str, max_age_days: int = 14):
        row = self._conn.execute(
            "SELECT result FROM council_partei_meinungen_cache "
            "WHERE key = ? AND created_at >= datetime('now', ?)",
            (key, f"-{int(max_age_days)} days")).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (ValueError, TypeError):
            return None

    def partei_meinungen_cache_set(self, key: str, question: str, result) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_partei_meinungen_cache "
                "(key, question, result, created_at) VALUES (?, ?, ?, datetime('now'))",
                (key, question[:300], json.dumps(result, ensure_ascii=False)))
            # Alt-Einträge räumen sich beim Schreiben mit weg (klein halten).
            self._conn.execute(
                "DELETE FROM council_partei_meinungen_cache "
                "WHERE created_at < datetime('now', '-30 days')")


    def save_qa_feedback(self, question: str, answer_excerpt: str | None,
                         rating: str, reason: str | None,
                         user_id: int | None = None) -> None:
        """Daumen hoch/runter zu einer KI-Antwort (5a/I-03).

        Ein Konto hat je Frage **eine** Stimme: Der nachgereichte Grund und die
        korrigierte Bewertung (Daumen runter → hoch) überschreiben die frühere
        Zeile, statt sich als widersprüchliches Paar in der Tabelle zu stapeln —
        sonst zählte jede Meinungsänderung doppelt. Anonyme Rückmeldungen haben
        keinen Schlüssel und werden weiterhin angehängt.
        """
        if rating not in ("up", "down"):
            raise ValueError(f"rating muss up/down sein, nicht {rating!r}")
        now = datetime.utcnow().isoformat(timespec="seconds")
        werte = (question[:300], (answer_excerpt or "")[:500] or None, rating,
                 (reason or "").strip()[:500] or None, user_id, now)
        with self._conn:
            if user_id is not None:
                vorher = self._conn.execute(
                    "SELECT id FROM council_qa_feedback WHERE user_id = ? AND question = ? "
                    "ORDER BY id DESC LIMIT 1", (user_id, werte[0])).fetchone()
                if vorher:
                    self._conn.execute(
                        "UPDATE council_qa_feedback SET answer_excerpt = ?, rating = ?, "
                        "reason = ?, created = ? WHERE id = ?",
                        (werte[1], rating, werte[3], now, vorher[0]))
                    return
            self._conn.execute(
                "INSERT INTO council_qa_feedback (question, answer_excerpt, rating, reason, user_id, created) "
                "VALUES (?, ?, ?, ?, ?, ?)", werte,
            )


    def get_decisions_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch decisions by id, preserving the given order (for Q&A citations).

        Liefert auch Abstimmung (vote/no_votes/abstentions/raw_result) und
        amount_eur mit: raw_result geht bei strittigen Beschlüssen in den
        QA-Kontext (dort stehen oft die Fraktionen der Gegenstimmen), und die
        Fallback-Folgefragen in council/qa.py prüfen no_votes/amount_eur —
        ohne diese Felder liefen die Zweige ins Leere."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.summary, d.official_text, d.template_number,
                       d.kvonr,
                       -- ksinr + item_number: Adresse der Station in der
                       -- Sitzung — darüber koppelt wortbeitraege_zu_beschluessen
                       -- die Aussprache an den Beschluss.
                       d.ksinr, d.item_number,
                       d.policy_field, d.outcome, d.impact, d.impact_reason,
                       d.vote, d.no_votes, d.abstentions, d.raw_result,
                       d.amount_eur, d.factions, d.deviation,
                       v.office, v.climate_impact,
                       cs.session_date, cs.committee
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_templates v ON v.kvonr = d.kvonr
                WHERE d.id IN ({ph})""",
            ids,
        ).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def antrag_decision_ids(self, party: str, terms: str = "", limit: int = 12) -> list[int]:
        """Beschluss-ids, bei denen die Fraktion/Gruppe ``party`` als Antragsteller
        auftritt — aus dem factions-Feld des Protokolls ODER über eine als Antrag
        erkannte Anlage der Vorlage. Mit ``terms`` wird thematisch eingegrenzt
        (Schnitt mit der FTS-Trefferliste), sonst kommen die neuesten zuerst.
        Für das Fragetyp-Routing der KI-Frage (typ=partei)."""
        like = f'%{party.strip()}%'
        rows = self._conn.execute(
            """SELECT DISTINCT d.id FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_templates v ON v.template_number = d.template_number
               LEFT JOIN council_attachments a ON a.kvonr = v.kvonr AND a.is_motion = 1
               WHERE d.kind = 'decision'
                 AND (d.factions LIKE ? OR a.applicants LIKE ?)
               ORDER BY cs.session_date DESC, d.id DESC LIMIT 400""",
            (like, like),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if terms:
            fts = {i for i, *_ in self.search_decisions_fts(terms, limit=250)}
            thematisch = [i for i in ids if i in fts]
            # Thematischer Schnitt zuerst; ohne Schnitt-Treffer die neuesten Anträge
            # der Fraktion — besser als gar kein Partei-Signal im Kandidaten-Pool.
            ids = thematisch or ids
        return ids[:limit]

    def find_decision_ids(self, *, template_number: str | None = None, committee: str | None = None,
                          session_date: str | None = None, title_like: str | None = None) -> list[int]:
        """Beschluss-ids über natürliche Schlüssel statt AUTOINCREMENT-ids.

        Für DB-portable Eval-Gold-Cases (eval/cases_qa.json): Vorlagen-Nummer,
        Sitzungsdatum und Titel sind auf jeder Kopie der Datenbank gleich, die
        ids nicht. Filter sind UND-verknüpft, mindestens einer ist Pflicht;
        Teilabstimmungen bleiben außen vor (nicht eigenständig zitierbar)."""
        conds, params = ["d.kind = 'decision'"], []
        if template_number:
            conds.append("d.template_number = ?"); params.append(str(template_number).strip())
        if committee:
            conds.append("cs.committee LIKE ?"); params.append(f"%{committee.strip()}%")
        if session_date:
            conds.append("cs.session_date = ?"); params.append(str(session_date).strip())
        if title_like:
            conds.append("d.title LIKE ?"); params.append(f"%{title_like.strip()}%")
        if len(conds) == 1:
            raise ValueError("find_decision_ids braucht mindestens einen Filter")
        rows = self._conn.execute(
            f"""SELECT d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE {' AND '.join(conds)}
                ORDER BY cs.session_date DESC, d.id DESC""",
            params,
        ).fetchall()
        return [r["id"] for r in rows]

    def get_protocols_raw(self) -> list[dict]:
        """All stored protocols with their raw text — for re-extraction without
        re-downloading the PDFs."""
        rows = self._conn.execute(
            "SELECT ksinr, document_id, document_url, raw_text, n_pages "
            "FROM council_protocols WHERE raw_text IS NOT NULL AND raw_text != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Der Weg eines Haushalts durch den Rat (A6, 08/2026) ---------------
    #
    # Gebaut aus dem, was das Ratsinformationssystem ohnehin führt: der
    # Beratungsfolge (`council_deliberations`), den Tagesordnungen
    # (`council_agenda_items`) und den Protokoll-Beschlüssen
    # (`council_decisions`). Kein eigener Datenbestand, kein Cron.
    #
    # `council_attachments.fetched_at` ist hier KEINE Quelle: Bei allen
    # Finanzdokumenten steht dort der 10.08.2026 — der Tag unseres
    # Volltext-Backfills, nicht der Tag der Veröffentlichung. Das Datum einer
    # Station kommt ausschließlich aus `council_sessions.session_date`.

    #: Ein Haushaltsjahr trägt drei Sorten Vorlagen, und sie heißen nicht
    #: einheitlich. Die Jahreszahl steht immer vorn, das Wort davor variiert
    #: („Haushalt 2026", „Haushaltsentwurf 2024", „HH 2020").
    _HH_TITEL = re.compile(r"^(?:Haushaltsentwurf|Haushalt|HH)\s*(\d{4})")

    #: Woran ein Verwaltungsentwurf als Teilhaushalts-Bericht erkennbar ist —
    #: er geht in den jeweiligen Fachausschuss, nicht in den Finanzausschuss.
    _HH_TEILBERICHT = ("Teilhaushalt", "THH", "Budget", "Stiftung")





    # ---- Der Streit ums Geld (08/2026) ------------------------------------
    #
    # Die Zahlen des Haushalts stehen in den Finanzdokumenten; dass über sie
    # gestritten wurde, steht nur im Protokoll. Diese Methode setzt beides
    # zusammen, was die Ratsdaten dazu hergeben: welche Änderungslisten zur
    # Abstimmung standen (`council_decisions` mit `kind='subvote'`), was in
    # der Debatte gesagt wurde (`council_protocols.raw_text`, zerlegt in
    # `council.haushaltsdebatte`) und wie am Ende abgestimmt wurde.
    #
    # Kein eigener Datenbestand und kein Cron: Alles wird beim Lesen aus dem
    # gerechnet, was der Protokoll-Import ohnehin schreibt. Damit kann die
    # Seite nicht veralten, und ein nachgetragenes Protokoll erscheint ohne
    # Backfill.

    #: Die Schlussabstimmung trägt in jedem Jahrgang denselben Titel; die
    #: Jahreszahl darin ist das HAUSHALTSJAHR, nicht das Sitzungsjahr (der
    #: Haushalt 2023 wurde im Dezember 2022 beschlossen, der Haushalt 2026
    #: erst im Februar 2026).
    _STREIT_SATZUNG = re.compile(r"^Haushaltssatzung und Haushaltsplan\s+(\d{4})")
    #: Der Sammelpunkt, unter dem die Debatte geführt wird. Er steht nicht in
    #: jedem Protokoll als eigene Beschlusszeile — wo er fehlt, wird der
    #: Oberpunkt aus der Nummer der Schlussabstimmung abgeleitet.
    _STREIT_SAMMEL = re.compile(r"^Haushalt\s+(\d{4})\s*$")



