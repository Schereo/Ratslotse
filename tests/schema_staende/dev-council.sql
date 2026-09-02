CREATE TABLE agenda_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, ksinr INTEGER NOT NULL, changed_at TEXT NOT NULL, diff_json TEXT NOT NULL);
CREATE TABLE agenda_item_impact (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    impact      INTEGER NOT NULL,
    reason      TEXT,           -- Grund in einfacher Sprache, steht auf der Karte
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);
CREATE TABLE agenda_item_social (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    text        TEXT NOT NULL,
    source      TEXT NOT NULL,  -- was das Modell sah: "vorlage+anlagen", "vorlage", "titel"
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);
CREATE TABLE agenda_item_summaries (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    summary     TEXT NOT NULL,
    agenda_hash TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);
CREATE TABLE agenda_snapshots (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    items_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);
CREATE TABLE committee_notifications ( ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL, agenda_hash TEXT NOT NULL DEFAULT '', sent_at TEXT NOT NULL, PRIMARY KEY(ksinr, owner_id));
CREATE TABLE committee_summaries (
    ksinr       INTEGER NOT NULL,
    agenda_hash TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, agenda_hash)
);
CREATE TABLE committees (
    kgrnr   INTEGER,
    name    TEXT NOT NULL,
    UNIQUE(name)
);
CREATE TABLE "council_agenda_attachments" (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    item_number  TEXT NOT NULL,
    label        TEXT NOT NULL,
    url          TEXT NOT NULL, raw_text TEXT,
    UNIQUE(ksinr, item_number, url)
);
CREATE TABLE council_agenda_items (
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
CREATE TABLE council_alerts_sent (
    ksinr    INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, topic_id)
);
CREATE TABLE council_anlage_embeddings (document_id INTEGER NOT NULL, chunk_idx INTEGER NOT NULL, text_hash TEXT NOT NULL, chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (document_id, chunk_idx));
CREATE TABLE "council_attachments" (document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT, url TEXT, is_motion INTEGER NOT NULL DEFAULT 0, applicants TEXT, raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'listed', is_image INTEGER NOT NULL DEFAULT 0, ocr_model TEXT);
CREATE TABLE council_attendance (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr   INTEGER NOT NULL,
    name    TEXT,
    party   TEXT,
    role    TEXT,                               -- vorsitz|mitglied|verwaltung|protokoll|gast
    note    TEXT
);
CREATE TABLE "council_audit_report_sources" (year INTEGER PRIMARY KEY, label TEXT, url TEXT, n_pages INTEGER, readable INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
CREATE TABLE "council_audit_reports" (year INTEGER NOT NULL, seq INTEGER NOT NULL, mark TEXT NOT NULL, mark_name TEXT NOT NULL, mark_explanation TEXT, text_number TEXT NOT NULL, section TEXT NOT NULL, chain TEXT, page INTEGER, text TEXT NOT NULL, follow_paragraph TEXT, source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (year, seq));
CREATE TABLE "council_balance_sheet" (year INTEGER NOT NULL, role TEXT NOT NULL, page TEXT NOT NULL, level INTEGER NOT NULL, nr TEXT, label TEXT NOT NULL, value REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, role));
CREATE TABLE "council_balance_sheet_notes" (year INTEGER NOT NULL, role TEXT NOT NULL, nr INTEGER NOT NULL, heading TEXT NOT NULL, text TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, role));
CREATE TABLE "council_budget" (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, area TEXT NOT NULL, revenues REAL, expenses REAL, result REAL, is_total INTEGER NOT NULL DEFAULT 0, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, UNIQUE(year, area));
CREATE TABLE "council_budget_amendments" (budget_year INTEGER NOT NULL, list_key TEXT NOT NULL, year INTEGER NOT NULL, seq INTEGER NOT NULL, sub_budget INTEGER, page_draft INTEGER, product TEXT, label TEXT NOT NULL, revenue REAL, expense REAL, document_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, explanation TEXT, author TEXT, PRIMARY KEY (budget_year, list_key, year, seq));
CREATE TABLE "council_budget_amendments_cash" (budget_year INTEGER NOT NULL, list_key TEXT NOT NULL, year INTEGER NOT NULL, seq INTEGER NOT NULL, sub_budget INTEGER, page_draft TEXT, product TEXT, label TEXT NOT NULL, planned_draft REAL, inflow REAL, outflow REAL, commitment_authorizations REAL, planned_new REAL, explanation TEXT, author TEXT, document_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (budget_year, list_key, year, seq));
CREATE TABLE "council_budget_amendments_cash_totals" (budget_year INTEGER NOT NULL, list_key TEXT NOT NULL, year INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, inflows REAL NOT NULL, outflows REAL NOT NULL, balance REAL NOT NULL, commitment_authorizations REAL, own INTEGER NOT NULL DEFAULT 0, document_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (budget_year, list_key, year, kind, label));
CREATE TABLE "council_budget_amendments_totals" (budget_year INTEGER NOT NULL, list_key TEXT NOT NULL, year INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, revenues REAL NOT NULL, expenses REAL NOT NULL, balance REAL NOT NULL, own INTEGER NOT NULL DEFAULT 0, document_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (budget_year, list_key, year, kind, label));
CREATE TABLE "council_budget_bylaw" (year INTEGER NOT NULL, supplement INTEGER NOT NULL DEFAULT 0, version TEXT NOT NULL, ordinary_revenues REAL NOT NULL, ordinary_expenses REAL NOT NULL, extraordinary_revenues REAL NOT NULL, extraordinary_expenses REAL NOT NULL, in_operating REAL NOT NULL, out_operating REAL NOT NULL, in_capital REAL NOT NULL, out_capital REAL NOT NULL, in_financing REAL NOT NULL, out_financing REAL NOT NULL, in_total REAL NOT NULL, out_total REAL NOT NULL, investment_loans REAL, commitment_authorizations REAL, liquidity_loans REAL, property_tax_a_rate INTEGER, property_tax_b_rate INTEGER, trade_tax_rate INTEGER, session_date TEXT, template_number TEXT, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, supplement));
CREATE TABLE council_budget_execution (budget_year INTEGER NOT NULL, as_of TEXT NOT NULL, budget TEXT NOT NULL, sub_budget INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, budgeted REAL, forecast REAL, deviation REAL, carryover REAL, plan_basis TEXT NOT NULL, is_total INTEGER NOT NULL DEFAULT 0, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (budget_year, as_of, budget, sub_budget, kind));
CREATE TABLE council_buergschaften (year INTEGER PRIMARY KEY, balance REAL NOT NULL, exact INTEGER NOT NULL, out_next_year INTEGER NOT NULL, source TEXT NOT NULL, reason TEXT, single_amount REAL, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_business_plans" (enterprise TEXT NOT NULL, year INTEGER NOT NULL, enterprise_name TEXT NOT NULL, template_number TEXT NOT NULL, revenues REAL, expenses REAL, taxes REAL, result REAL NOT NULL, capital_plan REAL, commitments REAL, draft_date TEXT, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, investments REAL, PRIMARY KEY (enterprise, year));
CREATE TABLE "council_cash_flow_statement" (year INTEGER NOT NULL, nr INTEGER NOT NULL, role TEXT, label TEXT NOT NULL, prior_year REAL, budgeted REAL, plan REAL, plan_kind TEXT, result REAL, deviation REAL, authorization REAL, is_total INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, nr));
CREATE TABLE "council_city_comparison" (series TEXT NOT NULL, year INTEGER NOT NULL, key TEXT NOT NULL, city TEXT NOT NULL, indicator TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (series, year, key, indicator));
CREATE TABLE "council_companies" (report_year INTEGER NOT NULL, company TEXT NOT NULL, name TEXT NOT NULL, classification TEXT NOT NULL, page INTEGER, consolidated_key TEXT, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, company));
CREATE TABLE "council_company_indicators" (company TEXT NOT NULL, indicator TEXT NOT NULL, year INTEGER NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, report_year INTEGER NOT NULL, n_reports INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (company, indicator, year));
CREATE TABLE "council_company_owners" (report_year INTEGER NOT NULL, company TEXT NOT NULL, sort_order INTEGER NOT NULL, name TEXT NOT NULL, amount_eur REAL, share_pct REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, company, sort_order));
CREATE TABLE "council_company_people" (report_year INTEGER NOT NULL, company TEXT NOT NULL, sort_order INTEGER NOT NULL, committee TEXT NOT NULL, name TEXT NOT NULL, position TEXT, chair_role TEXT, note TEXT, roles_assignable INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, company, sort_order));
CREATE TABLE "council_company_texts" (report_year INTEGER NOT NULL, company TEXT NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, company, section));
CREATE TABLE "council_daily_finds" (
    day         TEXT PRIMARY KEY,               -- Ausspiel-Datum (ISO)
    decision_id INTEGER NOT NULL,
    kicker      TEXT NOT NULL,                  -- „Heute vor N Jahren" | „Aus dem Archiv"
    story       TEXT NOT NULL,                  -- der eine Satz
    created_at  TEXT NOT NULL
);
CREATE TABLE "council_debt" (year INTEGER PRIMARY KEY, credit_market REAL, special_funds REAL, public_authorities REAL, municipal_enterprises REAL, total REAL NOT NULL, per_capita REAL, breakdown_rejected REAL, revised INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_decision_location_scans (decision_id INTEGER PRIMARY KEY, source_hash TEXT NOT NULL, scanned_at TEXT NOT NULL);
CREATE TABLE council_decision_locations (decision_id INTEGER NOT NULL, location_slug TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT NOT NULL, method TEXT NOT NULL, confidence REAL NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (decision_id, location_slug));
CREATE TABLE council_decision_votes (decision_id INTEGER NOT NULL, faction TEXT NOT NULL, stance TEXT NOT NULL, PRIMARY KEY (decision_id, faction, stance));
CREATE TABLE council_decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    position     INTEGER NOT NULL,
    item_number  TEXT,
    title        TEXT,
    official_text    TEXT,
    outcome      TEXT,                          -- angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss
    vote         TEXT,                          -- einstimmig|mehrheitlich|null
    no_votes INTEGER,
    abstentions INTEGER,
    factions     TEXT,                          -- JSON array
    template_number   TEXT,
    kvonr        INTEGER,
    raw_result   TEXT
, kind TEXT NOT NULL DEFAULT 'decision', parent_item TEXT, policy_field TEXT, policy_tags TEXT, summary TEXT, amount_eur REAL, importance INTEGER, simple_summary TEXT, interest INTEGER, interest_reason TEXT, impact INTEGER, impact_reason TEXT, deviation TEXT);
CREATE VIRTUAL TABLE council_decisions_fts USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE "council_deliberations" (id INTEGER PRIMARY KEY AUTOINCREMENT, kvonr INTEGER NOT NULL, date TEXT, committee TEXT NOT NULL DEFAULT '', top TEXT, is_public INTEGER, result TEXT, ksinr INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_donations" (template_number TEXT PRIMARY KEY, year INTEGER NOT NULL, session_date TEXT NOT NULL, amount REAL NOT NULL, committee TEXT, layout TEXT, second_mention TEXT NOT NULL, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_donations_rejected" (template_number TEXT PRIMARY KEY, session_date TEXT, reason TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_einwohner (year INTEGER PRIMARY KEY, population INTEGER NOT NULL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
CREATE TABLE council_embeddings (
    decision_id INTEGER PRIMARY KEY,
    vector      BLOB NOT NULL
);
CREATE TABLE council_entities (id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT, n INTEGER NOT NULL DEFAULT 0);
CREATE TABLE council_entity_aliases (slug TEXT PRIMARY KEY, canonical_slug TEXT NOT NULL, source TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE council_entity_links (entity_id INTEGER NOT NULL, decision_id INTEGER NOT NULL, PRIMARY KEY (entity_id, decision_id));
CREATE TABLE council_entity_meta (slug TEXT PRIMARY KEY, description TEXT, lat REAL, lon REAL, geojson TEXT, geo_tried INTEGER NOT NULL DEFAULT 0);
CREATE TABLE council_entity_obs (decision_id INTEGER NOT NULL, slug TEXT NOT NULL, name TEXT NOT NULL, kind TEXT, PRIMARY KEY (decision_id, slug));
CREATE TABLE council_entity_related (slug TEXT NOT NULL, neighbor_slug TEXT NOT NULL, rel_type TEXT NOT NULL, rank INTEGER NOT NULL, score REAL NOT NULL, evidence INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (slug, neighbor_slug));
CREATE TABLE council_entity_scanned (decision_id INTEGER PRIMARY KEY);
CREATE TABLE "council_expense_series" (year INTEGER PRIMARY KEY, accounting_system TEXT NOT NULL, amount REAL NOT NULL, source TEXT NOT NULL, probes TEXT NOT NULL, conflict_amount REAL, conflict_source TEXT, revised INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_fee_rates" (year INTEGER NOT NULL, key TEXT NOT NULL, area TEXT NOT NULL, label TEXT NOT NULL, amount REAL NOT NULL, unit TEXT NOT NULL, prior_year REAL, change_pct REAL, template_number TEXT, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, key));
CREATE TABLE "council_fees" (year INTEGER NOT NULL, area TEXT NOT NULL, area_name TEXT NOT NULL, cost_calculation REAL NOT NULL, deductions REAL NOT NULL, costs_to_cover REAL NOT NULL, reference_quantity REAL, reference_unit TEXT, fee REAL, fee_proposed REAL, template_number TEXT, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, area));
CREATE TABLE council_field_recaps (
    policy_field TEXT PRIMARY KEY,
    summary      TEXT NOT NULL,
    n_decisions  INTEGER NOT NULL,
    period_from  TEXT NOT NULL DEFAULT '',
    period_to    TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL
);
CREATE TABLE "council_fixed_assets" (year INTEGER NOT NULL, nr TEXT NOT NULL, label TEXT NOT NULL, n_columns INTEGER NOT NULL, cost_opening REAL, additions REAL, disposals REAL, transfers REAL, cost_closing REAL, depreciation_opening REAL, depreciation REAL, depreciation_releases REAL, write_ups REAL, depreciation_transfers REAL, depreciation_closing REAL, book_value REAL, book_value_prior_year REAL, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, nr));
CREATE TABLE council_goal_links (
    goal        TEXT NOT NULL,
    decision_id INTEGER NOT NULL,
    relevant    INTEGER NOT NULL DEFAULT 0,
    stance      TEXT,                              -- voran|bremst|neutral
    rationale   TEXT,
    PRIMARY KEY (goal, decision_id)
);
CREATE TABLE "council_group_entities" (year INTEGER NOT NULL, kind TEXT NOT NULL, entity_key TEXT NOT NULL, entity TEXT NOT NULL, amount_keur REAL NOT NULL, prior_year_keur REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, kind, entity_key));
CREATE TABLE "council_group_items" (year INTEGER NOT NULL, nr INTEGER NOT NULL, label TEXT NOT NULL, role TEXT, amount REAL NOT NULL, prior_year REAL, is_total INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, nr));
CREATE TABLE "council_income_budget" (plan_budget_year INTEGER NOT NULL, year INTEGER NOT NULL, kind TEXT NOT NULL, nr INTEGER NOT NULL, label TEXT NOT NULL, amount REAL NOT NULL, is_total INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (plan_budget_year, year, nr));
CREATE TABLE "council_income_statement" (year INTEGER NOT NULL, sub_budget_no INTEGER, sub_budget_name TEXT, nr INTEGER NOT NULL, label TEXT NOT NULL, prior_year REAL, budgeted REAL, result REAL, deviation REAL, is_total INTEGER NOT NULL DEFAULT 0, source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, plan REAL, plan_kind TEXT, herkunft_id INTEGER, PRIMARY KEY (year, sub_budget_no, nr));
CREATE TABLE "council_indicator_formulas" (report_year INTEGER NOT NULL, indicator TEXT NOT NULL, version INTEGER NOT NULL, heading TEXT NOT NULL, formula TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, indicator));
CREATE TABLE "council_indicators" (report_year INTEGER NOT NULL, indicator TEXT NOT NULL, year INTEGER NOT NULL, label TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, decimals INTEGER NOT NULL, version INTEGER, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (report_year, indicator, year));
CREATE TABLE "council_integrated_debt" (year INTEGER PRIMARY KEY, ars TEXT NOT NULL, population REAL, total REAL NOT NULL, per_capita REAL, core_budget REAL, extra_budgets REAL, other REAL, extra_under_50 REAL, other_below_50 REAL, change REAL, probes TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_investment_measures" (year INTEGER NOT NULL, level TEXT NOT NULL, sub_budget_no INTEGER NOT NULL DEFAULT 0, code TEXT NOT NULL DEFAULT '', label TEXT NOT NULL, grand_total REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, details TEXT, PRIMARY KEY (year, level, sub_budget_no, code));
CREATE TABLE "council_investments" (year INTEGER NOT NULL, level TEXT NOT NULL, sub_budget_no INTEGER NOT NULL DEFAULT 0, label TEXT NOT NULL, inflows REAL NOT NULL, outflows REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, level, sub_budget_no));
CREATE TABLE "council_investments_actual" (year INTEGER PRIMARY KEY, accounting_system TEXT NOT NULL, total REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_investments_actual_kinds" (year INTEGER NOT NULL, field TEXT NOT NULL, title TEXT NOT NULL, sort_order INTEGER NOT NULL, amount REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, field));
CREATE TABLE "council_investments_actual_rejected" (year INTEGER PRIMARY KEY, accounting_system TEXT NOT NULL, reason TEXT NOT NULL, difference REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_location_districts (location_slug TEXT NOT NULL, district TEXT NOT NULL, place_id TEXT, share REAL NOT NULL DEFAULT 1.0, PRIMARY KEY (location_slug, district));
CREATE TABLE council_locations (slug TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, lat REAL, lon REAL, geojson TEXT, district TEXT, place_id TEXT, local_area_id TEXT, geo_tried INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE council_memberships (id INTEGER PRIMARY KEY AUTOINCREMENT, kpenr INTEGER NOT NULL, kgrnr INTEGER, committee TEXT NOT NULL, role TEXT, valid_from TEXT, valid_until TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE "council_migration_marks" (marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL);
CREATE TABLE council_news_links (
    decision_id INTEGER NOT NULL,
    catalog     INTEGER NOT NULL,
    refid       TEXT NOT NULL,
    title       TEXT,
    pub_date    TEXT,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, catalog, refid)
);
CREATE TABLE council_partei_meinungen_cache (key TEXT PRIMARY KEY, question TEXT, result TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE council_persons (kpenr INTEGER PRIMARY KEY, name TEXT NOT NULL, current_faction TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE council_place_reviews (location_slug TEXT PRIMARY KEY, status TEXT NOT NULL, place_id TEXT, name TEXT, kind TEXT, parent_id TEXT, aliases TEXT NOT NULL DEFAULT '[]', description TEXT, source_url TEXT, quiz_enabled INTEGER NOT NULL DEFAULT 0, canonical_place_id TEXT, note TEXT, updated_by TEXT, updated_at TEXT NOT NULL);
CREATE TABLE "council_press" (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, news_id INTEGER, title TEXT NOT NULL, date TEXT, text TEXT NOT NULL, fetched_at TEXT NOT NULL);
CREATE TABLE "council_press_embeddings" (press_id INTEGER NOT NULL, chunk_idx INTEGER NOT NULL, text_hash TEXT NOT NULL, chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (press_id, chunk_idx));
CREATE VIRTUAL TABLE "council_press_fts" USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE "council_products" (year INTEGER NOT NULL, product_no TEXT NOT NULL, product_name TEXT NOT NULL, sub_budget_no INTEGER, sub_budget_name TEXT, office TEXT, revenues REAL, expenses REAL, result REAL, source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, short_description TEXT, legal_basis TEXT, controllability TEXT, controllability_raw TEXT, scope TEXT, target_group TEXT, herkunft_id INTEGER, PRIMARY KEY (year, product_no));
CREATE TABLE council_protocols (
    ksinr         INTEGER PRIMARY KEY,
    document_id   INTEGER,
    document_url  TEXT,
    protocol_nr   TEXT,
    session_start TEXT,
    session_end   TEXT,
    raw_text      TEXT,
    n_pages       INTEGER,
    model         TEXT,
    extracted_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'ok'   -- ok | failed
, contributions_extracted_at TEXT, page_offsets TEXT);
CREATE TABLE "council_provenance" (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, document_id INTEGER, label TEXT, url TEXT, citation TEXT, page INTEGER, probe TEXT NOT NULL, probe_result TEXT, as_of TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE council_qa_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer_excerpt TEXT, rating TEXT NOT NULL, reason TEXT, user_id INTEGER, created TEXT NOT NULL);
CREATE TABLE council_quiz_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, area_type TEXT NOT NULL, area_key TEXT NOT NULL, category TEXT NOT NULL, difficulty TEXT NOT NULL DEFAULT 'mittel', question TEXT NOT NULL, options TEXT NOT NULL, correct_index INTEGER NOT NULL, explanation TEXT, source_type TEXT, source_ref TEXT, content_hash TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'active', qtype TEXT NOT NULL DEFAULT 'mc', answer_value REAL, answer_unit TEXT, range_min REAL, range_max REAL, generated_at TEXT NOT NULL, detail TEXT, lat REAL, lon REAL, place_label TEXT, image_url TEXT, image_author TEXT, image_license TEXT, image_license_url TEXT, image_source_url TEXT, geojson TEXT, hint TEXT, topic TEXT, chart TEXT);
CREATE TABLE council_scheduled_sessions (
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (committee, session_date, session_time)
);
CREATE TABLE council_sessions (
    ksinr         INTEGER PRIMARY KEY,
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL,
    location      TEXT NOT NULL,
    fetched_at    TEXT NOT NULL
);
CREATE TABLE council_similar (
    decision_id INTEGER NOT NULL,
    neighbor_id INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, neighbor_id)
);
CREATE TABLE "council_speeches" (id INTEGER PRIMARY KEY AUTOINCREMENT, ksinr INTEGER NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL, top TEXT, speaker TEXT, party TEXT, text TEXT NOT NULL, answer TEXT, extracted_at TEXT NOT NULL, page INTEGER);
CREATE TABLE "council_speeches_embeddings" (contribution_id INTEGER PRIMARY KEY, text_hash TEXT NOT NULL, vector BLOB NOT NULL);
CREATE VIRTUAL TABLE "council_speeches_fts" USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE "council_staff_plan" (budget_year INTEGER NOT NULL, part TEXT NOT NULL, row_no INTEGER NOT NULL, kind TEXT NOT NULL, pay_group TEXT, seq_no INTEGER, label TEXT NOT NULL, pay_grade TEXT, positions_planned REAL NOT NULL, positions_prior_year REAL NOT NULL, filled REAL NOT NULL, filled_by_officials REAL, filled_by_employees REAL, vacant REAL NOT NULL, as_of_date TEXT, consistent INTEGER NOT NULL DEFAULT 1, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (budget_year, part, row_no));
CREATE TABLE "council_supplementary_approvals" (template_number TEXT PRIMARY KEY, year INTEGER, title TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, amount REAL, amount_source TEXT, decided INTEGER NOT NULL DEFAULT 0, in_plenary INTEGER NOT NULL DEFAULT 0, council_decision INTEGER NOT NULL DEFAULT 0, decision_id INTEGER, committees TEXT, fulltext_probe INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_supplementary_channels" (year INTEGER NOT NULL, channel TEXT NOT NULL, label TEXT NOT NULL, count_operating INTEGER NOT NULL, amount_operating REAL NOT NULL, count_capital INTEGER NOT NULL, amount_capital REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, channel));
CREATE TABLE "council_supplementary_years" (year INTEGER PRIMARY KEY, total_operating REAL NOT NULL, total_capital REAL NOT NULL, total_per_text REAL, commitments_amount REAL, probe_ok INTEGER NOT NULL DEFAULT 0, probe_text TEXT, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE "council_tax_capacity" (year INTEGER PRIMARY KEY, tax_index REAL, tax_capacity_per_capita REAL, allocations REAL, allocations_per_capita REAL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
CREATE TABLE "council_tax_plan" (year INTEGER NOT NULL, kind TEXT NOT NULL, plan REAL NOT NULL, actual REAL NOT NULL, provisional INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, kind));
CREATE TABLE "council_tax_rates" (year INTEGER NOT NULL, kind TEXT NOT NULL, rate INTEGER NOT NULL, prior_rate INTEGER, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, kind));
CREATE TABLE "council_taxes" (year INTEGER NOT NULL, kind TEXT NOT NULL, amount REAL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (year, kind));
CREATE TABLE "council_template_embeddings" (template_number TEXT NOT NULL, chunk_idx INTEGER NOT NULL, text_hash TEXT NOT NULL, chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (template_number, chunk_idx));
CREATE TABLE "council_templates" (kvonr INTEGER PRIMARY KEY, template_number TEXT, title TEXT, kind TEXT, document_id INTEGER, document_url TEXT, raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ok', attachments_scanned INTEGER NOT NULL DEFAULT 0, office TEXT, climate_impact TEXT, financial_impact TEXT, proposed_decision TEXT);
CREATE TABLE council_topic_vagueness (slug TEXT PRIMARY KEY, name TEXT NOT NULL, vague INTEGER NOT NULL, hint TEXT, suggestion TEXT, checked_at TEXT NOT NULL);
CREATE TABLE "council_trade_tax_statistics" (year INTEGER NOT NULL, key TEXT NOT NULL, city TEXT NOT NULL, cases INTEGER NOT NULL, cases_positive INTEGER NOT NULL, tax_base_eur INTEGER, assessments INTEGER, assessments_positive INTEGER, assessment_tax_base_eur INTEGER, apportionments INTEGER, apportionments_positive INTEGER, apportioned_assessment_eur INTEGER, rate REAL, confidential INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, key));
CREATE TABLE "council_variance_reasons" (year INTEGER NOT NULL, nr INTEGER NOT NULL, label TEXT NOT NULL, delta_meur REAL, percent REAL, text TEXT NOT NULL, source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (year, nr));
CREATE TABLE council_vermoegensgruppen (year INTEGER NOT NULL, group_name TEXT NOT NULL, book_value REAL NOT NULL, book_value_prior_year REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (year, group_name));
CREATE TABLE council_video_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr         INTEGER NOT NULL,
    item_number   TEXT NOT NULL,               -- ohne Ö-/N-Präfix, wie council_decisions
    outcome       TEXT NOT NULL,               -- angenommen|abgelehnt|vertagt|zur_kenntnis|abgesetzt
    vote          TEXT,                        -- einstimmig|mehrheitlich|NULL (nicht belegt → offen)
    no_votes  INTEGER,                     -- nur wenn in der Sitzung ausgesprochen
    abstentions  INTEGER,
    quote         TEXT NOT NULL,               -- wörtlicher Transkript-Beleg
    video_id      TEXT NOT NULL,               -- YouTube-Video-ID
    video_seconds INTEGER,                     -- Fundstelle des Belegs im Video
    model         TEXT NOT NULL,               -- LLM, das gelesen hat
    created_at    TEXT NOT NULL,
    UNIQUE(ksinr, item_number)
);
CREATE TABLE session_followups_sent ( ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY(ksinr, owner_id));
CREATE INDEX idx_agenda_changes_ksinr ON agenda_changes(ksinr);
CREATE INDEX idx_anlagen_kvonr ON "council_attachments"(kvonr);
CREATE INDEX idx_attendance_ksinr ON council_attendance(ksinr);
CREATE INDEX idx_beratungen_kvonr ON "council_deliberations"(kvonr);
CREATE INDEX idx_cs_date ON council_sessions(session_date DESC);
CREATE INDEX idx_decisions_field ON council_decisions(policy_field);
CREATE INDEX idx_decisions_importance ON council_decisions(importance);
CREATE INDEX idx_decisions_ksinr ON council_decisions(ksinr);
CREATE INDEX idx_decloc_slug ON council_decision_locations(location_slug);
CREATE INDEX idx_entalias_canon ON council_entity_aliases(canonical_slug);
CREATE INDEX idx_entlink_dec ON council_entity_links(decision_id);
CREATE INDEX idx_entobs_slug ON council_entity_obs(slug);
CREATE INDEX idx_entrelated_slug ON council_entity_related(slug, rank);
CREATE INDEX idx_ergebnishaushalt_jahr ON "council_income_budget"(year, kind);
CREATE INDEX idx_gesellschaft_kennzahlen_jahr ON "council_company_indicators"(year, indicator);
CREATE INDEX idx_goal_links_goal ON council_goal_links(goal);
CREATE INDEX idx_herkunft_dokument ON "council_provenance"(document_id);
CREATE INDEX idx_invprog_jahr_thh ON "council_investment_measures"(year, sub_budget_no);
CREATE INDEX idx_konzern_posten_rolle ON "council_group_items"(role, year);
CREATE INDEX idx_location_districts_district ON council_location_districts(district);
CREATE INDEX idx_location_districts_place ON council_location_districts(place_id);
CREATE INDEX idx_locations_ortsbereich ON council_locations(local_area_id);
CREATE INDEX idx_locations_place ON council_locations(place_id);
CREATE INDEX idx_memberships_kpenr ON council_memberships(kpenr);
CREATE INDEX idx_news_decision ON council_news_links(decision_id);
CREATE INDEX idx_place_reviews_status ON council_place_reviews(status);
CREATE INDEX idx_produkte_thh ON "council_products"(year, sub_budget_no);
CREATE INDEX idx_pruefberichte_kette ON "council_audit_reports"(chain, year);
CREATE INDEX idx_quiz_area ON council_quiz_questions(area_type, area_key);
CREATE INDEX idx_similar_decision ON council_similar(decision_id);
CREATE INDEX idx_stellenplan_art ON "council_staff_plan"(kind, budget_year);
CREATE INDEX idx_video_results_ksinr ON council_video_results(ksinr);
CREATE INDEX idx_vorlagen_nr ON "council_templates"(template_number);
CREATE INDEX idx_wb_ksinr ON "council_speeches"(ksinr);
