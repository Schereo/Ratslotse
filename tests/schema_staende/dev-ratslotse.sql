CREATE TABLE bookmarks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id           INTEGER NOT NULL,
    kind               TEXT NOT NULL,
    target_key         TEXT NOT NULL,
    ksinr              INTEGER,
    item_number        TEXT,
    decision_id        INTEGER,
    kvonr              INTEGER,
    template_number         TEXT NOT NULL DEFAULT '',
    title              TEXT NOT NULL DEFAULT '',
    subtitle           TEXT NOT NULL DEFAULT '',
    notify_result      INTEGER NOT NULL DEFAULT 0,
    result_notified_at TEXT,
    created_at         TEXT NOT NULL,
    UNIQUE(owner_id, target_key)
);
CREATE TABLE committee_subscriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id       INTEGER NOT NULL,
    committee_name TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE(owner_id, committee_name)
);
CREATE TABLE council_agenda_classified (
  owner_id      INTEGER NOT NULL,
  ksinr         INTEGER NOT NULL,
  agenda_hash   TEXT NOT NULL,
  classified_at TEXT NOT NULL,
  PRIMARY KEY (owner_id, ksinr)
);
CREATE TABLE council_agenda_matches (
  owner_id    INTEGER NOT NULL,
  ksinr       INTEGER NOT NULL,
  topic_id    INTEGER NOT NULL,
  item_number TEXT NOT NULL,
  matched_at  TEXT NOT NULL,
  PRIMARY KEY (owner_id, ksinr, topic_id, item_number)
);
CREATE TABLE council_results_sent (
    ksinr    INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY (ksinr, owner_id)
);
CREATE TABLE council_topic_match_meta (
    topic_id   INTEGER NOT NULL PRIMARY KEY,
    owner_id   INTEGER NOT NULL,
    gedeckelt  INTEGER NOT NULL DEFAULT 0,
    kandidaten INTEGER NOT NULL DEFAULT 0,
    matched_at TEXT NOT NULL
);
CREATE TABLE council_topic_matches (
    topic_id    INTEGER NOT NULL,
    owner_id    INTEGER NOT NULL,
    decision_id INTEGER NOT NULL,
    score       REAL NOT NULL,
    matched_at  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (topic_id, decision_id)
);
CREATE TABLE deep_research_jobs (
    id       TEXT PRIMARY KEY,      -- unerratbares Token
    user_id  INTEGER NOT NULL,
    question    TEXT NOT NULL,
    status   TEXT NOT NULL,         -- laeuft | fertig | teilbericht | gestoppt | abgebrochen | fehler
    report  TEXT,                  -- fertiger Berichtstext (Markdown mit [id]-Fußnoten)
    sources  TEXT,                  -- JSON {sources, presse, debatten, planungen, cited, facetten, gelesen, zeitraum}
    seen  INTEGER NOT NULL DEFAULT 0,  -- Client hat den fertigen Bericht gerendert
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
);
CREATE TABLE email_verification_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id   INTEGER NOT NULL,
    email      TEXT,                  -- Adresse zum Zeitpunkt des Absendens
    kind       TEXT NOT NULL,         -- feature | bug | other
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at    TEXT                   -- NULL = ungelesen
);
CREATE TABLE job_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT NOT NULL,
    started_at  TEXT NOT NULL,           -- ISO, UTC
    finished_at TEXT,
    status      TEXT NOT NULL,           -- ok | error
    duration_s  REAL,
    stats       TEXT,                    -- JSON-Objekt oder NULL
    error       TEXT
);
CREATE TABLE llm_usage (id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT (datetime('now')), feature TEXT NOT NULL, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, cost_usd REAL);
CREATE TABLE "migration_marks" (marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL);
CREATE TABLE notification_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL,
    kind          TEXT NOT NULL,
    title         TEXT NOT NULL,
    body_html     TEXT NOT NULL,
    url           TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    deliver_after TEXT NOT NULL,
    sent_at       TEXT,
    bundled       INTEGER NOT NULL DEFAULT 0,
    -- Fehlgeschlagene Zustellversuche. Solange der Versandweg klemmt (Resend
    -- down, Adresse abgelehnt), bleibt die Meldung mit sent_at IS NULL liegen
    -- und wird erneut versucht — bis MAX_VERSUCHE, damit eine dauerhaft
    -- unzustellbare Adresse die Warteschlange nicht ewig blockiert.
    attempts      INTEGER NOT NULL DEFAULT 0
, push_text TEXT);
CREATE TABLE password_reset_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE push_tokens (
    token      TEXT PRIMARY KEY,
    owner_id   INTEGER NOT NULL,
    platform   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
CREATE TABLE "qa_conversation_turns" (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    question        TEXT NOT NULL,
    answer      TEXT NOT NULL,
    sources      TEXT,                  -- JSON {sources, cited}
    created      TEXT NOT NULL
);
CREATE TABLE "qa_conversations" (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    title    TEXT NOT NULL,
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
);
CREATE TABLE qa_shares (
    token    TEXT PRIMARY KEY,
    user_id  INTEGER NOT NULL,
    question    TEXT NOT NULL,
    answer  TEXT NOT NULL,
    sources  TEXT,                  -- JSON [{id, title, session_date, committee, outcome}]
    created  TEXT NOT NULL,
    extras   TEXT                   -- JSON {debatten, presse, anlagen, parteien}
);
CREATE TABLE quiz_answers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    area_type   TEXT NOT NULL,
    area_key    TEXT NOT NULL,
    category    TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    answered_at TEXT NOT NULL
);
CREATE TABLE quiz_daily (
    owner_id     INTEGER NOT NULL,
    day          TEXT NOT NULL,          -- YYYY-MM-DD (UTC)
    correct      INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    points       INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, day)
);
CREATE TABLE quiz_ratings (
    owner_id    INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    verdict     TEXT NOT NULL,          -- gut | schlecht
    comment     TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (owner_id, question_id)
);
CREATE TABLE "template_follows" (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    kvonr       INTEGER NOT NULL,
    template_number  TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    stations    TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    notified_at TEXT,
    UNIQUE(owner_id, kvonr)
);
CREATE TABLE topic_hits_seen (
  owner_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  decision_id INTEGER NOT NULL,
  seen_at TEXT NOT NULL,
  PRIMARY KEY (owner_id, topic_id, decision_id)
);
CREATE TABLE topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL DEFAULT 0,
    chat_id     INTEGER NOT NULL DEFAULT 0,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE "user_activity" (
                    owner_id INTEGER NOT NULL,
                    day      TEXT NOT NULL,
                    feature  TEXT NOT NULL,
                    client   TEXT NOT NULL DEFAULT 'unknown',
                    count    INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (owner_id, day, feature, client)
                );
CREATE TABLE user_quiz_questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL,
    question      TEXT NOT NULL,
    options       TEXT NOT NULL,         -- JSON-Array, 2–4 Einträge (leer bei estimate)
    correct_index INTEGER NOT NULL,
    district     TEXT,                  -- NULL = stadtweit
    category      TEXT NOT NULL,
    explanation   TEXT,
    qtype         TEXT NOT NULL DEFAULT 'mc',  -- mc | estimate (Schätzfrage-Slider)
    answer_value  REAL,                  -- estimate: richtige Zahl
    answer_unit   TEXT,                  -- estimate: Einheit (optional)
    range_min     REAL,                  -- estimate: Slider-Untergrenze
    range_max     REAL,                  -- estimate: Slider-Obergrenze
    practiced     INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE TABLE users (
    chat_id    INTEGER PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    added_at   TEXT NOT NULL
);
CREATE TABLE web_users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    email            TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'user',
    status           TEXT NOT NULL DEFAULT 'pending',
    telegram_chat_id INTEGER,
    delivery_channel TEXT NOT NULL DEFAULT 'email',
    token_version    INTEGER NOT NULL DEFAULT 0,
    email_verified   INTEGER NOT NULL DEFAULT 0,
    apple_sub        TEXT,                       -- Sign in with Apple: stabile Apple-User-ID (RL-1002)
    password_set     INTEGER NOT NULL DEFAULT 1, -- 0 = Apple-only-Konto ohne selbst gewähltes Passwort
    created_at       TEXT NOT NULL
, onboarding TEXT, display_name TEXT, badges TEXT, notify_prefs TEXT, setup_step INTEGER, setup_started_at TEXT, setup_updated_at TEXT, setup_done_at TEXT, setup_reminded_at TEXT, deep_limit INTEGER, limits_unlocked INTEGER NOT NULL DEFAULT 0, topics_seen_at TEXT, saves_conversations INTEGER, signup_client TEXT);
CREATE INDEX idx_bookmarks_owner ON bookmarks(owner_id, created_at DESC);
CREATE INDEX idx_bookmarks_result ON bookmarks(ksinr, notify_result, result_notified_at);
CREATE INDEX idx_cam_owner ON council_agenda_matches(owner_id, ksinr);
CREATE INDEX idx_ctm_topic ON council_topic_matches(topic_id);
CREATE INDEX idx_deep_jobs_user ON deep_research_jobs(user_id, created DESC);
CREATE INDEX idx_feedback_created ON feedback(created_at DESC);
CREATE INDEX idx_job_runs_job ON job_runs(job, started_at DESC);
CREATE INDEX idx_notify_offen ON notification_queue(owner_id, sent_at, deliver_after);
CREATE INDEX idx_push_tokens_owner ON push_tokens(owner_id);
CREATE INDEX idx_qa_gespraeche_user ON "qa_conversations"(user_id, updated DESC);
CREATE INDEX idx_qa_turns_gespraech ON "qa_conversation_turns"(conversation_id);
CREATE INDEX idx_quiz_answers_owner ON quiz_answers(owner_id, area_type, area_key);
CREATE INDEX idx_topic_hits_seen_owner ON topic_hits_seen(owner_id, topic_id);
CREATE INDEX idx_topics_chat ON topics(chat_id);
CREATE INDEX idx_topics_owner ON topics(owner_id);
CREATE INDEX idx_user_activity_day ON user_activity(day);
CREATE INDEX idx_user_activity_owner ON user_activity(owner_id);
CREATE INDEX idx_user_quiz_owner ON user_quiz_questions(owner_id);
CREATE INDEX idx_vorlage_follows_kvonr ON "template_follows"(kvonr);
CREATE UNIQUE INDEX idx_web_users_apple_sub ON web_users(apple_sub) WHERE apple_sub IS NOT NULL;
