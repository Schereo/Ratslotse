"""Das Schema der Rats-Datenbank und sein Umbau über die Zeit.

**Warum getrennt.** ``_migrate`` allein war 2.458 Zeilen — ein Viertel von
``store.py`` in EINER Methode. Sie läuft bei jedem Öffnen der Datenbank und
holt jeden Stand seit 2023 auf den heutigen: neue Spalten, umbenannte
Tabellen, umgeschriebene Werte. Wer eine Abfrage suchte, scrollte an ihr
vorbei; wer sie ändern wollte, fand sie zwischen den Abfragen.

**Warum das kein Widerspruch zur Regel ist.** In ``council/CLAUDE.md`` steht,
dass Schema und Migrationen der Datenbank als Ganzem gehören und nicht in eine
Fach-Ecke wandern. Das gilt weiter — dies hier ist keine Ecke, sondern
dieselbe Sache in einer eigenen Datei. Die Reihenfolge der Schritte ist
unverändert; verschoben sind nur Zeilen.

**Was hier liegt.** Das ``SCHEMA`` selbst (die ``CREATE TABLE``-Anweisungen,
die vor jeder Migration laufen), die vier Spalten-Vokabulare des großen
Umbenennungs-Umbaus von 08/2026, die Tabellen-Umbenennungen — und die
Migration mit ihren sieben Helfern.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from kern.dbfehler import tabelle_fehlt


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
    -- Die Überschrift für die Karte (seit 09/2026): sagt, WORUM es geht, wo
    -- der amtliche Titel nur sagt, WER wann etwas eingereicht hat
    -- („Änderungsantrag der CDU-Fraktion vom 10.06.2026"). Entsteht im
    -- selben Aufruf wie der Text; NULL bei Zeilen von vor der Spalte — der
    -- Nachtlauf holt sie nach.
    headline    TEXT,
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


class SchemaMixin:
    """Schema und Migration von :class:`council.store.CouncilStore`.

    Nur zum Mitvererben; ``self._conn`` kommt von dort.
    """

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

        # agenda_item_social bekam 09/2026 die Karten-Überschrift dazu.
        social_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(agenda_item_social)")}
        if social_cols and "headline" not in social_cols:
            with self._conn:
                self._conn.execute("ALTER TABLE agenda_item_social ADD COLUMN headline TEXT")

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
