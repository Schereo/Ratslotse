CREATE TABLE agenda_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, ksinr INTEGER NOT NULL, changed_at TEXT NOT NULL, diff_json TEXT NOT NULL);
CREATE TABLE agenda_item_impact (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    impact      INTEGER NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY(ksinr, item_number)
);
CREATE TABLE agenda_item_social (
    ksinr       INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    text        TEXT NOT NULL,
    quelle      TEXT NOT NULL,  -- was das Modell sah: "vorlage+anlagen", "vorlage", "titel"
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
CREATE TABLE council_abweichungsgruende (jahr INTEGER NOT NULL, nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL, delta_mio REAL, prozent REAL, text TEXT NOT NULL, quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (jahr, nr));
CREATE TABLE council_agenda_anlagen (
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
    vorlage_nr   TEXT,
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
CREATE TABLE council_anlagen (document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT, url TEXT, is_antrag INTEGER NOT NULL DEFAULT 0, antragsteller TEXT, raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'listed', bild INTEGER NOT NULL DEFAULT 0, ocr_modell TEXT);
CREATE TABLE council_anlagenspiegel (jahr INTEGER NOT NULL, nr TEXT NOT NULL, bezeichnung TEXT NOT NULL, spalten INTEGER NOT NULL, ahk_anfang REAL, zugaenge REAL, abgaenge REAL, umbuchungen REAL, ahk_ende REAL, abschr_anfang REAL, abschreibung REAL, aufloesungen REAL, zuschreibungen REAL, abschr_umbuchungen REAL, abschr_ende REAL, buchwert REAL, buchwert_vorjahr REAL, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, nr));
CREATE TABLE council_attendance (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr   INTEGER NOT NULL,
    name    TEXT,
    party   TEXT,
    role    TEXT,                               -- vorsitz|mitglied|verwaltung|protokoll|gast
    note    TEXT
);
CREATE TABLE council_ausgabenreihe (jahr INTEGER PRIMARY KEY, regelwerk TEXT NOT NULL, betrag REAL NOT NULL, quelle TEXT NOT NULL, proben TEXT NOT NULL, konflikt_betrag REAL, konflikt_quelle TEXT, revidiert INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_beratungen (id INTEGER PRIMARY KEY AUTOINCREMENT, kvonr INTEGER NOT NULL, datum TEXT, gremium TEXT NOT NULL DEFAULT '', top TEXT, is_public INTEGER, ergebnis TEXT, ksinr INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_beteiligungen (id INTEGER PRIMARY KEY AUTOINCREMENT, titel TEXT NOT NULL, ort TEXT, schritt TEXT, von TEXT, bis TEXT, url TEXT NOT NULL, plan_nrs TEXT NOT NULL, fetched_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'laufend', beendet_am TEXT);
CREATE TABLE council_bilanz (jahr INTEGER NOT NULL, rolle TEXT NOT NULL, seite TEXT NOT NULL, ebene INTEGER NOT NULL, nr TEXT, bezeichnung TEXT NOT NULL, wert REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, rolle));
CREATE TABLE council_bilanz_erlaeuterungen (jahr INTEGER NOT NULL, rolle TEXT NOT NULL, nr INTEGER NOT NULL, ueberschrift TEXT NOT NULL, text TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, rolle));
CREATE TABLE council_buergschaften (jahr INTEGER PRIMARY KEY, bestand REAL NOT NULL, genau INTEGER NOT NULL, aus_folgejahr INTEGER NOT NULL, quelle TEXT NOT NULL, grund TEXT, einzelbetrag REAL, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_decision_location_scans (decision_id INTEGER PRIMARY KEY, source_hash TEXT NOT NULL, scanned_at TEXT NOT NULL);
CREATE TABLE council_decision_locations (decision_id INTEGER NOT NULL, location_slug TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT NOT NULL, method TEXT NOT NULL, confidence REAL NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (decision_id, location_slug));
CREATE TABLE council_decision_votes (decision_id INTEGER NOT NULL, faction TEXT NOT NULL, stance TEXT NOT NULL, PRIMARY KEY (decision_id, faction, stance));
CREATE TABLE council_decisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ksinr        INTEGER NOT NULL,
    position     INTEGER NOT NULL,
    item_number  TEXT,
    title        TEXT,
    beschluss    TEXT,
    outcome      TEXT,                          -- angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss
    vote         TEXT,                          -- einstimmig|mehrheitlich|null
    gegenstimmen INTEGER,
    enthaltungen INTEGER,
    factions     TEXT,                          -- JSON array
    vorlage_nr   TEXT,
    kvonr        INTEGER,
    raw_result   TEXT
, kind TEXT NOT NULL DEFAULT 'decision', parent_item TEXT, policy_field TEXT, policy_tags TEXT, summary TEXT, amount_eur REAL, importance INTEGER, simple_summary TEXT, interest INTEGER, interest_reason TEXT, impact INTEGER, impact_reason TEXT, abweichung TEXT);
CREATE VIRTUAL TABLE council_decisions_fts USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE council_einwohner (jahr INTEGER PRIMARY KEY, einwohner INTEGER NOT NULL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
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
CREATE TABLE council_ergebnishaushalt (plan_jahrgang INTEGER NOT NULL, jahr INTEGER NOT NULL, art TEXT NOT NULL, nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL, betrag REAL NOT NULL, ist_summe INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (plan_jahrgang, jahr, nr));
CREATE TABLE council_ergebnisrechnung (jahr INTEGER NOT NULL, thh_nr INTEGER, thh_name TEXT, nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL, vorjahr REAL, ansatz REAL, ergebnis REAL, abweichung REAL, ist_summe INTEGER NOT NULL DEFAULT 0, quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, plan REAL, plan_art TEXT, herkunft_id INTEGER, PRIMARY KEY (jahr, thh_nr, nr));
CREATE TABLE council_field_recaps (
    policy_field TEXT PRIMARY KEY,
    summary      TEXT NOT NULL,
    n_decisions  INTEGER NOT NULL,
    period_from  TEXT NOT NULL DEFAULT '',
    period_to    TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL
);
CREATE TABLE council_finanzrechnung (jahr INTEGER NOT NULL, nr INTEGER NOT NULL, rolle TEXT, bezeichnung TEXT NOT NULL, vorjahr REAL, ansatz REAL, plan REAL, plan_art TEXT, ergebnis REAL, abweichung REAL, ermaechtigung REAL, ist_summe INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, nr));
CREATE TABLE council_fundstuecke (
    day         TEXT PRIMARY KEY,               -- Ausspiel-Datum (ISO)
    decision_id INTEGER NOT NULL,
    kicker      TEXT NOT NULL,                  -- „Heute vor N Jahren" | „Aus dem Archiv"
    story       TEXT NOT NULL,                  -- der eine Satz
    created_at  TEXT NOT NULL
);
CREATE TABLE council_gebuehren (jahr INTEGER NOT NULL, bereich TEXT NOT NULL, bereich_name TEXT NOT NULL, kostenkalkulation REAL NOT NULL, abzuege REAL NOT NULL, zu_deckende_kosten REAL NOT NULL, bezugsmenge REAL, bezugseinheit TEXT, gebuehr REAL, gebuehrenvorschlag REAL, vorlage_nr TEXT, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, bereich));
CREATE TABLE council_gebuehrensaetze (jahr INTEGER NOT NULL, schluessel TEXT NOT NULL, bereich TEXT NOT NULL, bezeichnung TEXT NOT NULL, betrag REAL NOT NULL, einheit TEXT NOT NULL, vorjahr REAL, veraenderung_prozent REAL, vorlage_nr TEXT, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, schluessel));
CREATE TABLE council_gesellschaft_eigentuemer (bericht_jahr INTEGER NOT NULL, gesellschaft TEXT NOT NULL, reihenfolge INTEGER NOT NULL, name TEXT NOT NULL, betrag_eur REAL, anteil_prozent REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, gesellschaft, reihenfolge));
CREATE TABLE council_gesellschaft_kennzahlen (gesellschaft TEXT NOT NULL, kennzahl TEXT NOT NULL, jahr INTEGER NOT NULL, wert REAL NOT NULL, einheit TEXT NOT NULL, bericht_jahr INTEGER NOT NULL, berichte INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (gesellschaft, kennzahl, jahr));
CREATE TABLE council_gesellschaft_personen (bericht_jahr INTEGER NOT NULL, gesellschaft TEXT NOT NULL, reihenfolge INTEGER NOT NULL, gremium TEXT NOT NULL, name TEXT NOT NULL, funktion TEXT, vorsitz TEXT, hinweis TEXT, funktionen_zuordenbar INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, gesellschaft, reihenfolge));
CREATE TABLE council_gesellschaft_texte (bericht_jahr INTEGER NOT NULL, gesellschaft TEXT NOT NULL, abschnitt TEXT NOT NULL, text TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, gesellschaft, abschnitt));
CREATE TABLE council_gesellschaften (bericht_jahr INTEGER NOT NULL, gesellschaft TEXT NOT NULL, name TEXT NOT NULL, gliederung TEXT NOT NULL, seite INTEGER, konzern_key TEXT, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, gesellschaft));
CREATE TABLE council_gewerbesteuerstatistik (jahr INTEGER NOT NULL, schluessel TEXT NOT NULL, stadt TEXT NOT NULL, faelle INTEGER NOT NULL, faelle_positiv INTEGER NOT NULL, messbetrag_eur INTEGER, festsetzungen INTEGER, festsetzungen_positiv INTEGER, festsetzung_messbetrag_eur INTEGER, zerlegungen INTEGER, zerlegungen_positiv INTEGER, zerlegung_messbetrag_eur INTEGER, hebesatz REAL, gesperrt INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, schluessel));
CREATE TABLE council_goal_links (
    goal        TEXT NOT NULL,
    decision_id INTEGER NOT NULL,
    relevant    INTEGER NOT NULL DEFAULT 0,
    stance      TEXT,                              -- voran|bremst|neutral
    rationale   TEXT,
    PRIMARY KEY (goal, decision_id)
);
CREATE TABLE council_haushalt (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, bereich TEXT NOT NULL, ertraege REAL, aufwendungen REAL, ergebnis REAL, is_summe INTEGER NOT NULL DEFAULT 0, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, UNIQUE(year, bereich));
CREATE TABLE council_haushalt_aenderungen (jahrgang INTEGER NOT NULL, liste TEXT NOT NULL, jahr INTEGER NOT NULL, lfd INTEGER NOT NULL, thh INTEGER, seite_entwurf INTEGER, produkt TEXT, bezeichnung TEXT NOT NULL, ertrag REAL, aufwand REAL, erlaeuterung TEXT, dokument_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, urheber TEXT, PRIMARY KEY (jahrgang, liste, jahr, lfd));
CREATE TABLE council_haushalt_aenderungen_summen (jahrgang INTEGER NOT NULL, liste TEXT NOT NULL, jahr INTEGER NOT NULL, typ TEXT NOT NULL, label TEXT NOT NULL, ertraege REAL NOT NULL, aufwendungen REAL NOT NULL, saldo REAL NOT NULL, eigene INTEGER NOT NULL DEFAULT 0, dokument_id INTEGER NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahrgang, liste, jahr, typ, label));
CREATE TABLE council_haushaltssatzung (jahr INTEGER NOT NULL, nachtrag INTEGER NOT NULL DEFAULT 0, fassung TEXT NOT NULL, ordentliche_ertraege REAL NOT NULL, ordentliche_aufwendungen REAL NOT NULL, ao_ertraege REAL NOT NULL, ao_aufwendungen REAL NOT NULL, ein_laufend REAL NOT NULL, aus_laufend REAL NOT NULL, ein_invest REAL NOT NULL, aus_invest REAL NOT NULL, ein_finanz REAL NOT NULL, aus_finanz REAL NOT NULL, ein_gesamt REAL NOT NULL, aus_gesamt REAL NOT NULL, kredite_investitionen REAL, verpflichtungsermaechtigungen REAL, liquiditaetskredite REAL, hebesatz_grundsteuer_a INTEGER, hebesatz_grundsteuer_b INTEGER, hebesatz_gewerbesteuer INTEGER, sitzung_am TEXT, vorlage_nr TEXT, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, nachtrag));
CREATE TABLE council_hebesaetze (jahr INTEGER NOT NULL, art TEXT NOT NULL, hebesatz INTEGER NOT NULL, vorheriger INTEGER, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, art));
CREATE TABLE council_herkunft (id INTEGER PRIMARY KEY AUTOINCREMENT, schluessel TEXT NOT NULL UNIQUE, art TEXT NOT NULL, dokument_id INTEGER, label TEXT, url TEXT, fundstelle TEXT, seite INTEGER, probe TEXT NOT NULL, probe_ergebnis TEXT, stand TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE council_integrierte_schulden (jahr INTEGER PRIMARY KEY, ars TEXT NOT NULL, bevoelkerung REAL, insgesamt REAL NOT NULL, je_einwohner REAL, kernhaushalt REAL, extrahaushalte REAL, sonstige REAL, extra_unter_50 REAL, sonstige_unter_50 REAL, veraenderung REAL, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_investitionen (jahr INTEGER NOT NULL, ebene TEXT NOT NULL, thh_nr INTEGER NOT NULL DEFAULT 0, bezeichnung TEXT NOT NULL, einzahlungen REAL NOT NULL, auszahlungen REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, ebene, thh_nr));
CREATE TABLE council_investitionen_ist (jahr INTEGER PRIMARY KEY, regelwerk TEXT NOT NULL, insgesamt REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_investitionen_ist_arten (jahr INTEGER NOT NULL, feld TEXT NOT NULL, titel TEXT NOT NULL, reihenfolge INTEGER NOT NULL, betrag REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, feld));
CREATE TABLE council_investitionen_ist_verworfen (jahr INTEGER PRIMARY KEY, regelwerk TEXT NOT NULL, grund TEXT NOT NULL, differenz REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_investitionsmassnahmen (jahr INTEGER NOT NULL, ebene TEXT NOT NULL, thh_nr INTEGER NOT NULL DEFAULT 0, code TEXT NOT NULL DEFAULT '', bezeichnung TEXT NOT NULL, gesamtsumme REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, details TEXT, PRIMARY KEY (jahr, ebene, thh_nr, code));
CREATE TABLE council_kennzahl_formeln (bericht_jahr INTEGER NOT NULL, kennzahl TEXT NOT NULL, fassung INTEGER NOT NULL, ueberschrift TEXT NOT NULL, formel TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, kennzahl));
CREATE TABLE council_kennzahlen (bericht_jahr INTEGER NOT NULL, kennzahl TEXT NOT NULL, jahr INTEGER NOT NULL, label TEXT NOT NULL, wert REAL NOT NULL, einheit TEXT NOT NULL, stellen INTEGER NOT NULL, fassung INTEGER, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (bericht_jahr, kennzahl, jahr));
CREATE TABLE council_konzern_posten (jahr INTEGER NOT NULL, nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL, rolle TEXT, betrag REAL NOT NULL, vorjahr REAL, ist_summe INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, nr));
CREATE TABLE council_konzern_traeger (jahr INTEGER NOT NULL, art TEXT NOT NULL, traeger_key TEXT NOT NULL, traeger TEXT NOT NULL, betrag_teur REAL NOT NULL, vorjahr_teur REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, art, traeger_key));
CREATE TABLE council_locations (slug TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, lat REAL, lon REAL, geojson TEXT, stadtteil TEXT, geo_tried INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, place_id TEXT, ortsbereich_id TEXT);
CREATE TABLE council_memberships (id INTEGER PRIMARY KEY AUTOINCREMENT, kpenr INTEGER NOT NULL, kgrnr INTEGER, gremium TEXT NOT NULL, rolle TEXT, von TEXT, bis TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE council_nachbewilligung_jahre (jahr INTEGER PRIMARY KEY, summe_konsumtiv REAL NOT NULL, summe_investiv REAL NOT NULL, text_gesamt REAL, verpflichtungen_betrag REAL, probe_ok INTEGER NOT NULL DEFAULT 0, probe_text TEXT, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_nachbewilligung_kanaele (jahr INTEGER NOT NULL, kanal TEXT NOT NULL, label TEXT NOT NULL, anzahl_konsumtiv INTEGER NOT NULL, betrag_konsumtiv REAL NOT NULL, anzahl_investiv INTEGER NOT NULL, betrag_investiv REAL NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, kanal));
CREATE TABLE council_nachbewilligungen (vorlage_nr TEXT PRIMARY KEY, jahr INTEGER, titel TEXT NOT NULL, art TEXT NOT NULL, kategorie TEXT NOT NULL, betrag REAL, betrag_quelle TEXT, beschlossen INTEGER NOT NULL DEFAULT 0, im_rat INTEGER NOT NULL DEFAULT 0, ratsentscheidung INTEGER NOT NULL DEFAULT 0, beschluss_id INTEGER, gremien TEXT, volltextprobe INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_news_links (
    decision_id INTEGER NOT NULL,
    catalog     INTEGER NOT NULL,
    refid       TEXT NOT NULL,
    title       TEXT,
    pub_date    TEXT,
    score       REAL NOT NULL,
    PRIMARY KEY (decision_id, catalog, refid)
);
CREATE TABLE council_partei_meinungen_cache (schluessel TEXT PRIMARY KEY, frage TEXT, ergebnis TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE council_persons (kpenr INTEGER PRIMARY KEY, name TEXT NOT NULL, fraktion_aktuell TEXT, fetched_at TEXT NOT NULL);
CREATE TABLE council_place_reviews (location_slug TEXT PRIMARY KEY, status TEXT NOT NULL, place_id TEXT, name TEXT, kind TEXT, parent_id TEXT, aliases TEXT NOT NULL DEFAULT '[]', description TEXT, source_url TEXT, quiz_enabled INTEGER NOT NULL DEFAULT 0, canonical_place_id TEXT, note TEXT, updated_by TEXT, updated_at TEXT NOT NULL);
CREATE TABLE council_presse (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, news_id INTEGER, titel TEXT NOT NULL, datum TEXT, text TEXT NOT NULL, fetched_at TEXT NOT NULL);
CREATE TABLE council_presse_embeddings (presse_id INTEGER NOT NULL, chunk_idx INTEGER NOT NULL, text_hash TEXT NOT NULL, chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (presse_id, chunk_idx));
CREATE VIRTUAL TABLE council_presse_fts USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE council_produkte (jahr INTEGER NOT NULL, produkt_nr TEXT NOT NULL, produkt_name TEXT NOT NULL, thh_nr INTEGER, thh_name TEXT, amt TEXT, ertraege REAL, aufwendungen REAL, ergebnis REAL, kurzbeschreibung TEXT, auftragsgrundlage TEXT, beeinflussbarkeit TEXT, beeinflussbarkeit_roh TEXT, wirkungskreis TEXT, zielgruppe TEXT, quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (jahr, produkt_nr));
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
, wortbeitraege_extracted_at TEXT, page_offsets TEXT);
CREATE TABLE council_pruefbericht_quellen (jahr INTEGER PRIMARY KEY, label TEXT, url TEXT, n_pages INTEGER, lesbar INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
CREATE TABLE council_pruefberichte (jahr INTEGER NOT NULL, lfd INTEGER NOT NULL, marke TEXT NOT NULL, marke_name TEXT NOT NULL, marke_erlaeuterung TEXT, textziffer TEXT NOT NULL, abschnitt TEXT NOT NULL, kette TEXT, seite INTEGER, text TEXT NOT NULL, folgeabsatz TEXT, quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (jahr, lfd));
CREATE TABLE council_qa_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, frage TEXT NOT NULL, antwort_auszug TEXT, bewertung TEXT NOT NULL, grund TEXT, user_id INTEGER, created TEXT NOT NULL);
CREATE TABLE council_quiz_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, area_type TEXT NOT NULL, area_key TEXT NOT NULL, category TEXT NOT NULL, difficulty TEXT NOT NULL DEFAULT 'mittel', question TEXT NOT NULL, options TEXT NOT NULL, correct_index INTEGER NOT NULL, explanation TEXT, source_type TEXT, source_ref TEXT, content_hash TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'active', qtype TEXT NOT NULL DEFAULT 'mc', answer_value REAL, answer_unit TEXT, range_min REAL, range_max REAL, generated_at TEXT NOT NULL, detail TEXT, lat REAL, lon REAL, place_label TEXT, image_url TEXT, image_author TEXT, image_license TEXT, image_license_url TEXT, image_source_url TEXT, geojson TEXT, hint TEXT, topic TEXT, chart TEXT);
CREATE TABLE council_scheduled_sessions (
    committee     TEXT NOT NULL,
    session_date  TEXT NOT NULL,
    session_time  TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    fetched_at    TEXT NOT NULL,
    PRIMARY KEY (committee, session_date, session_time)
);
CREATE TABLE council_schulden (jahr INTEGER PRIMARY KEY, kreditmarkt REAL, sondermittel REAL, gebietskoerperschaften REAL, eigenbetriebe REAL, insgesamt REAL NOT NULL, je_einwohner REAL, aufteilung_verworfen REAL, revidiert INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
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
CREATE TABLE council_spenden (vorlage_nr TEXT PRIMARY KEY, jahr INTEGER NOT NULL, sitzung TEXT NOT NULL, betrag REAL NOT NULL, gremium TEXT, layout TEXT, zweitstelle TEXT NOT NULL, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_spenden_verworfen (vorlage_nr TEXT PRIMARY KEY, sitzung TEXT, grund TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL);
CREATE TABLE council_staedtevergleich (reihe TEXT NOT NULL, jahr INTEGER NOT NULL, schluessel TEXT NOT NULL, stadt TEXT NOT NULL, kennzahl TEXT NOT NULL, wert REAL NOT NULL, einheit TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (reihe, jahr, schluessel, kennzahl));
CREATE TABLE council_stellenplan (jahrgang INTEGER NOT NULL, teil TEXT NOT NULL, zeile INTEGER NOT NULL, art TEXT NOT NULL, gruppe TEXT, lfd_nr INTEGER, bezeichnung TEXT NOT NULL, besoldung TEXT, stellen_plan REAL NOT NULL, stellen_vorjahr REAL NOT NULL, besetzt REAL NOT NULL, besetzt_beamte REAL, besetzt_arbeitnehmer REAL, nicht_besetzt REAL NOT NULL, stichtag TEXT, stimmig INTEGER NOT NULL DEFAULT 1, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahrgang, teil, zeile));
CREATE TABLE council_steuerkraft (jahr INTEGER PRIMARY KEY, messzahl REAL, messzahl_je_ew REAL, zuweisungen REAL, zuweisungen_je_ew REAL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER);
CREATE TABLE council_steuern (jahr INTEGER NOT NULL, art TEXT NOT NULL, betrag REAL, source_url TEXT, fetched_at TEXT NOT NULL, herkunft_id INTEGER, PRIMARY KEY (jahr, art));
CREATE TABLE council_steuerplan (jahr INTEGER NOT NULL, art TEXT NOT NULL, plan REAL NOT NULL, ist REAL NOT NULL, vorlaeufig INTEGER NOT NULL DEFAULT 0, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, art));
CREATE TABLE council_topic_vagueness (slug TEXT PRIMARY KEY, name TEXT NOT NULL, vague INTEGER NOT NULL, hint TEXT, suggestion TEXT, checked_at TEXT NOT NULL);
CREATE TABLE council_vermoegensgruppen (jahr INTEGER NOT NULL, gruppe TEXT NOT NULL, buchwert REAL NOT NULL, buchwert_vorjahr REAL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, gruppe));
CREATE TABLE council_vorlage_embeddings (vorlage_nr TEXT NOT NULL, chunk_idx INTEGER NOT NULL, text_hash TEXT NOT NULL, chunk_text TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (vorlage_nr, chunk_idx));
CREATE TABLE council_vorlagen (kvonr INTEGER PRIMARY KEY, vorlage_nr TEXT, title TEXT, art TEXT, document_id INTEGER, document_url TEXT, raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ok', anlagen_scanned INTEGER NOT NULL DEFAULT 0, amt TEXT, klima_check TEXT, finanz_check TEXT, beschlussvorschlag TEXT);
CREATE TABLE council_wirtschaftsplaene (betrieb TEXT NOT NULL, jahr INTEGER NOT NULL, betrieb_name TEXT NOT NULL, vorlage_nr TEXT NOT NULL, ertraege REAL, aufwendungen REAL, steuern REAL, ergebnis REAL NOT NULL, vermoegensplan REAL, investitionen REAL, verpflichtungen REAL, entwurf_vom TEXT, proben TEXT NOT NULL, herkunft_id INTEGER, fetched_at TEXT NOT NULL, PRIMARY KEY (betrieb, jahr));
CREATE TABLE council_wortbeitraege (id INTEGER PRIMARY KEY AUTOINCREMENT, ksinr INTEGER NOT NULL, position INTEGER NOT NULL, art TEXT NOT NULL, top TEXT, sprecher TEXT, partei TEXT, text TEXT NOT NULL, antwort TEXT, extracted_at TEXT NOT NULL, seite INTEGER);
CREATE TABLE council_wortbeitraege_embeddings (wb_id INTEGER PRIMARY KEY, text_hash TEXT NOT NULL, vector BLOB NOT NULL);
CREATE VIRTUAL TABLE council_wortbeitraege_fts USING fts5(content, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE session_followups_sent ( ksinr INTEGER NOT NULL, owner_id INTEGER NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY(ksinr, owner_id));
CREATE INDEX idx_agenda_changes_ksinr ON agenda_changes(ksinr);
CREATE INDEX idx_anlagen_kvonr ON council_anlagen(kvonr);
CREATE INDEX idx_attendance_ksinr ON council_attendance(ksinr);
CREATE INDEX idx_beratungen_kvonr ON council_beratungen(kvonr);
CREATE UNIQUE INDEX idx_beteiligung_url_schritt ON council_beteiligungen(url, schritt);
CREATE INDEX idx_cs_date ON council_sessions(session_date DESC);
CREATE INDEX idx_decisions_field ON council_decisions(policy_field);
CREATE INDEX idx_decisions_importance ON council_decisions(importance);
CREATE INDEX idx_decisions_ksinr ON council_decisions(ksinr);
CREATE INDEX idx_decloc_slug ON council_decision_locations(location_slug);
CREATE INDEX idx_entalias_canon ON council_entity_aliases(canonical_slug);
CREATE INDEX idx_entlink_dec ON council_entity_links(decision_id);
CREATE INDEX idx_entobs_slug ON council_entity_obs(slug);
CREATE INDEX idx_entrelated_slug ON council_entity_related(slug, rank);
CREATE INDEX idx_ergebnishaushalt_jahr ON council_ergebnishaushalt(jahr, art);
CREATE INDEX idx_gesellschaft_kennzahlen_jahr ON council_gesellschaft_kennzahlen(jahr, kennzahl);
CREATE INDEX idx_goal_links_goal ON council_goal_links(goal);
CREATE INDEX idx_herkunft_dokument ON council_herkunft(dokument_id);
CREATE INDEX idx_invprog_jahr_thh ON council_investitionsmassnahmen(jahr, thh_nr);
CREATE INDEX idx_konzern_posten_rolle ON council_konzern_posten(rolle, jahr);
CREATE INDEX idx_locations_ortsbereich ON council_locations(ortsbereich_id);
CREATE INDEX idx_locations_place ON council_locations(place_id);
CREATE INDEX idx_memberships_kpenr ON council_memberships(kpenr);
CREATE INDEX idx_news_decision ON council_news_links(decision_id);
CREATE INDEX idx_place_reviews_status ON council_place_reviews(status);
CREATE INDEX idx_produkte_thh ON council_produkte(jahr, thh_nr);
CREATE INDEX idx_pruefberichte_kette ON council_pruefberichte(kette, jahr);
CREATE INDEX idx_quiz_area ON council_quiz_questions(area_type, area_key);
CREATE INDEX idx_similar_decision ON council_similar(decision_id);
CREATE INDEX idx_stellenplan_art ON council_stellenplan(art, jahrgang);
CREATE INDEX idx_vorlagen_nr ON council_vorlagen(vorlage_nr);
CREATE INDEX idx_wb_ksinr ON council_wortbeitraege(ksinr);
