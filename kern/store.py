from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Iterable


logger = logging.getLogger("kern.store")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    username   TEXT NOT NULL DEFAULT '',
    added_at   TEXT NOT NULL
);

-- `owner_id` (= web_users.id) is the canonical owner of topics, matches and
-- subscriptions. A Telegram chat is only a *delivery target* now, resolved via
-- web_users.telegram_chat_id. `topics.chat_id` is kept for backward-compat /
-- rollback; it is no longer used for ownership queries.
CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL DEFAULT 0,
    chat_id     INTEGER NOT NULL DEFAULT 0,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS committee_subscriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id       INTEGER NOT NULL,
    committee_name TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE(owner_id, committee_name)
);

-- „Diesen Vorgang verfolgen" (Design 28a/W1). Themen und Ausschuss-Abos sind
-- breite Netze; wer EINE konkrete Vorlage durch die Gremien begleiten will —
-- die Schule im eigenen Viertel, das Stadion — hatte bisher keinen Weg dazu
-- außer regelmäßig selbst nachzusehen. Ein Follow hängt an der kvonr (der
-- stabilen Vorlagen-Id des Ratsinfo); template_number und title sind eine Kopie
-- fürs Anzeigen, weil sie in der anderen Datenbank liegen (kein Join möglich).
-- `stations` hält den zuletzt GEMELDETEN Stand der Beratungsfolge: Der Cron
-- vergleicht dagegen und schickt nur, was wirklich dazugekommen ist.
CREATE TABLE IF NOT EXISTS vorlage_follows (
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
CREATE INDEX IF NOT EXISTS idx_vorlage_follows_kvonr ON vorlage_follows(kvonr);

-- Persönliche Merkliste: eine gemeinsame Ablage für Sitzungen, einzelne TOPs
-- und gefasste Beschlüsse. `target_key` ist die technische Identität beim
-- Merken; die übrigen Felder sind ein Snapshot und erlauben, einen TOP nach
-- einer Nummernverschiebung über kvonr/Vorlage/Titel wiederzufinden.
-- `notify_result` ist bewusst getrennt vom Merken: Eine Ablage ist noch kein
-- Benachrichtigungs-Abo.
CREATE TABLE IF NOT EXISTS bookmarks (
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
CREATE INDEX IF NOT EXISTS idx_bookmarks_owner ON bookmarks(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookmarks_result ON bookmarks(ksinr, notify_result, result_notified_at);

-- Warteschlange für Benachrichtigungen (Design 30a). Alle Anlässe reihen hier
-- ein statt direkt zu senden; kern/notify.py stellt zu und hält dabei die zwei
-- harten Grenzen ein: höchstens zwei am Tag (gebündelt statt gestapelt) und
-- Nachtruhe von 21 bis 7 Uhr. `deliver_after` trägt das Ergebnis der
-- Nachtruhe-Rechnung, `bundled` merkt, dass ein Posten nur als Teil einer
-- Sammelmeldung rausging (für die Statistik, nicht für die Logik).
CREATE TABLE IF NOT EXISTS notification_queue (
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
    -- Eigener Kurztext für die Push-Vorschau; NULL = aus body_html ableiten.
    push_text     TEXT,
    -- Fehlgeschlagene Zustellversuche. Solange der Versandweg klemmt (Resend
    -- down, Adresse abgelehnt), bleibt die Meldung mit sent_at IS NULL liegen
    -- und wird erneut versucht — bis MAX_VERSUCHE, damit eine dauerhaft
    -- unzustellbare Adresse die Warteschlange nicht ewig blockiert.
    attempts      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notify_offen ON notification_queue(owner_id, sent_at, deliver_after);

-- N3 „Es ist entschieden" (Design 30a): je Sitzung und Konto einmal. Eigene
-- Tabelle statt council_alerts_sent, weil die in der anderen Datenbank liegt
-- und keine owner-Spalte hat.
CREATE TABLE IF NOT EXISTS council_results_sent (
    ksinr    INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY (ksinr, owner_id)
);

-- Semantic matches between a user topic and council decisions (computed offline by
-- scripts/match_topics_decisions.py from the precomputed decision embeddings).
CREATE TABLE IF NOT EXISTS council_topic_matches (
    topic_id    INTEGER NOT NULL,
    owner_id    INTEGER NOT NULL,
    decision_id INTEGER NOT NULL,
    score       REAL NOT NULL,
    matched_at  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (topic_id, decision_id)
);
CREATE INDEX IF NOT EXISTS idx_ctm_topic ON council_topic_matches(topic_id);

-- Was der Matching-Lauf über SEINEN EIGENEN Lauf weiß — je Thema eine Zeile.
-- `gedeckelt` = es gab mehr Beschlüsse über der Relevanzschwelle als der Lauf
-- speichern durfte. Ohne diese Zeile kann die Oberfläche nicht unterscheiden,
-- ob „40 Beschlüsse" das Ergebnis oder der Deckel ist — und genau das hat sie
-- bis zum 15.08.2026 als Tatsache behauptet („25 Beschlüsse insgesamt" bei
-- JEDEM Thema, weil top-k 25 war). `kandidaten` ist die Zahl der geprüften
-- Beschlüsse: nur damit lässt sich ein „0 Treffer" später als „nichts
-- Passendes gefunden" statt „Lauf ist nie gelaufen" lesen.
CREATE TABLE IF NOT EXISTS council_topic_match_meta (
    topic_id   INTEGER NOT NULL PRIMARY KEY,
    owner_id   INTEGER NOT NULL,
    gedeckelt  INTEGER NOT NULL DEFAULT 0,
    kandidaten INTEGER NOT NULL DEFAULT 0,
    matched_at TEXT NOT NULL
);

-- Web frontend accounts. delivery_channel ∈ {email, push, both, off}.
-- 'off' heißt: gar keine Benachrichtigungen. Kein eigenes Feld, weil es
-- dieselbe Frage beantwortet wie die anderen drei — wohin? — nur eben mit
-- „nirgendwohin". kern.notify.gewuenscht() liest den Wert mit, damit bei 'off'
-- nichts erst in der Warteschlange landet.
-- `telegram_chat_id` is a legacy column retained for backward-compatible data
-- (older rows that were once migrated from the removed Telegram bot); it is no
-- longer written to and can be dropped in a future schema migration.
CREATE TABLE IF NOT EXISTS web_users (
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
    -- Design 30a: welche der sechs Anlässe gewünscht sind, als JSON
    -- {"n1_tagesordnung": true, …}. NULL = alles auf Vorgabe (NOTIFY_DEFAULTS).
    -- Eigene Spalte statt der onboarding-/badges-JSON, damit sich die drei
    -- nicht gegenseitig überschreiben.
    notify_prefs     TEXT,
    -- Wann die Themen-Übersicht zuletzt offen war. Der Zähler an „Meine
    -- Themen" zeigt nur, was SEITDEM dazukam; NULL = noch nie nachgesehen.
    topics_seen_at   TEXT,
    created_at       TEXT NOT NULL
);

-- Single-use password-reset tokens (only the sha256 hash is stored) with expiry.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);

-- Single-use email-verification tokens (only the sha256 hash is stored) with expiry.
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);

-- Native-app push device tokens (APNs on iOS, FCM on Android). One row per
-- device; the platform push `token` is the primary key so re-registering the
-- same device is an upsert. owner_id = web_users.id.
CREATE TABLE IF NOT EXISTS push_tokens (
    token      TEXT PRIMARY KEY,
    owner_id   INTEGER NOT NULL,
    platform   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_push_tokens_owner ON push_tokens(owner_id);

-- Quiz-Antworten (Punkte je Konto). Gebiet + Kategorie sind DENORMALISIERT,
-- weil die Fragen in council.sqlite liegen (kein DB-übergreifender Join) — so
-- aggregiert die Statistik ohne Zugriff auf die Fragen-DB.
CREATE TABLE IF NOT EXISTS topic_hits_seen (
  owner_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  decision_id INTEGER NOT NULL,
  seen_at TEXT NOT NULL,
  PRIMARY KEY (owner_id, topic_id, decision_id)
);
CREATE INDEX IF NOT EXISTS idx_topic_hits_seen_owner ON topic_hits_seen(owner_id, topic_id);

-- Treffer der Tagesordnungs-Klassifikation (kommende Sitzungen ↔ eigene
-- Themen) — Grundlage der „n TOPs zu deinen Themen"-Chips (RL-902). Die
-- Sitzungen liegen in council.sqlite (kein DB-übergreifender Join), daher
-- referenziert ksinr nur numerisch.
CREATE TABLE IF NOT EXISTS council_agenda_matches (
  owner_id    INTEGER NOT NULL,
  ksinr       INTEGER NOT NULL,
  topic_id    INTEGER NOT NULL,
  item_number TEXT NOT NULL,
  matched_at  TEXT NOT NULL,
  PRIMARY KEY (owner_id, ksinr, topic_id, item_number)
);
CREATE INDEX IF NOT EXISTS idx_cam_owner ON council_agenda_matches(owner_id, ksinr);

-- Merkt je Nutzer*in + Sitzung, welcher Tagesordnungs-Stand (Hash) schon
-- klassifiziert wurde — die LLM-Klassifikation läuft nur bei Änderungen.
CREATE TABLE IF NOT EXISTS council_agenda_classified (
  owner_id      INTEGER NOT NULL,
  ksinr         INTEGER NOT NULL,
  agenda_hash   TEXT NOT NULL,
  classified_at TEXT NOT NULL,
  PRIMARY KEY (owner_id, ksinr)
);

-- „Meine Gespräche" (5a/I-04 + Design 6a): KI-Verläufe am Konto, nur mit
-- ausdrücklicher Einwilligung (web_users.qa_speichern = 1). user_id steht
-- denormalisiert auch an den Turns, damit die Konto-Löschung über
-- USER_OWNED_TABLES beide Tabellen ohne Waisen abräumt.
CREATE TABLE IF NOT EXISTS qa_gespraeche (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    title    TEXT NOT NULL,
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qa_gespraeche_user ON qa_gespraeche(user_id, updated DESC);

CREATE TABLE IF NOT EXISTS qa_gespraech_turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    sources         TEXT,               -- JSON {sources, cited}
    created         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qa_turns_gespraech ON qa_gespraech_turns(conversation_id);

-- Geteilte „Frag den Rat"-Antworten (Task 31): bewusste Einzel-
-- Veröffentlichung per Klick — unabhängig vom „Gespräche speichern"-Opt-in.
-- token ist der öffentliche Schlüssel (unerratbar); user_id nur intern für
-- die Konto-Löschung (USER_OWNED_TABLES), nie in der öffentlichen Antwort.
CREATE TABLE IF NOT EXISTS qa_shares (
    token    TEXT PRIMARY KEY,
    user_id  INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer   TEXT NOT NULL,
    sources  TEXT,                  -- JSON [{id, title, session_date, committee, outcome}]
    created  TEXT NOT NULL,
    extras   TEXT                   -- JSON {debatten, presse, anlagen, parteien}
);

-- „Gründliche Recherche" (RG-10): server-seitige Recherche-Jobs. Der Job
-- läuft im Backend-Thread weiter, wenn der Client die Verbindung verliert
-- (Tab-Wechsel, App-Navigation); diese Zeile ist die persistente Wahrheit —
-- der fertige Bericht ist so auch nach App- oder Server-Neustart abrufbar.
-- Kontingent (5/Tag je Konto) zählt nur laeuft+fertig: Abbruch, Teilbericht
-- und Fehler kosten laut Design nichts.
CREATE TABLE IF NOT EXISTS deep_research_jobs (
    id       TEXT PRIMARY KEY,      -- unerratbares Token
    user_id  INTEGER NOT NULL,
    question TEXT NOT NULL,
    status   TEXT NOT NULL,         -- laeuft | fertig | teilbericht | gestoppt | abgebrochen | fehler
    report   TEXT,                  -- fertiger Berichtstext (Markdown mit [id]-Fußnoten)
    sources  TEXT,                  -- JSON {sources, presse, debatten, planungen, cited, facetten, gelesen, zeitraum}
    seen     INTEGER NOT NULL DEFAULT 0,  -- Client hat den fertigen Bericht gerendert
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deep_jobs_user ON deep_research_jobs(user_id, created DESC);

CREATE TABLE IF NOT EXISTS quiz_answers (
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
CREATE INDEX IF NOT EXISTS idx_quiz_answers_owner ON quiz_answers(owner_id, area_type, area_key);

-- Nutzer-Bewertung einer Frage (Qualitäts-Kreislauf → schlechte ausmustern).
CREATE TABLE IF NOT EXISTS quiz_ratings (
    owner_id    INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    verdict     TEXT NOT NULL,          -- gut | schlecht
    comment     TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (owner_id, question_id)
);

-- Abgeschlossene Tages-Challenge je Nutzer & Tag (für Ergebnis + Serie).
CREATE TABLE IF NOT EXISTS quiz_daily (
    owner_id     INTEGER NOT NULL,
    day          TEXT NOT NULL,          -- YYYY-MM-DD (UTC)
    correct      INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    points       INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, day)
);

-- Eigene Quizfragen (RL-U14): privat je Konto, zum Üben — geben bewusst
-- KEINE Punkte und fließen nicht in Statistik/Abzeichen ein. Der Übungs-
-- Fortschritt lebt als Zähler direkt an der Frage („3× geübt, 100 %").
CREATE TABLE IF NOT EXISTS user_quiz_questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL,
    question      TEXT NOT NULL,
    options       TEXT NOT NULL,         -- JSON-Array, 2–4 Einträge (leer bei estimate)
    correct_index INTEGER NOT NULL,
    district      TEXT,                  -- NULL = stadtweit
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
CREATE INDEX IF NOT EXISTS idx_user_quiz_owner ON user_quiz_questions(owner_id);

-- Aktivitäts-Log für die Admin-Statistik (Design 20a): ein Eintrag je
-- Konto/Tag/Feature mit Zähler — kompakt (max. 1 Zeile pro Nutzer/Tag/Feature),
-- speist WAU (DISTINCT owner je Woche), „zuletzt aktiv“ (MAX day) und die
-- Feature-Nutzung im Nutzer-Detail. Nur eigene App-Aktivität, kein Tracking
-- darüber hinaus.
CREATE TABLE IF NOT EXISTS user_activity (
    owner_id INTEGER NOT NULL,
    day      TEXT NOT NULL,           -- YYYY-MM-DD
    feature  TEXT NOT NULL,           -- session | ki_frage | suche | quiz | thema | analyse | karte
    count    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (owner_id, day, feature)
);
CREATE INDEX IF NOT EXISTS idx_user_activity_day ON user_activity(day);
CREATE INDEX IF NOT EXISTS idx_user_activity_owner ON user_activity(owner_id);

-- Ein Eintrag je Cron-Lauf, geschrieben von run_guarded (kern/alerts.py).
-- Bis hierhin war der einzige Ops-Blick ins System die Fehler-Mail und die
-- Logdateien auf dem Server; damit sieht das Admin-Panel, ob ein Job läuft,
-- wie lange er braucht und was er verarbeitet hat. `stats` ist ein JSON-Objekt,
-- das der Job selbst zurückgibt (sprechende Schlüssel → direkt anzeigbar).
CREATE TABLE IF NOT EXISTS job_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT NOT NULL,
    started_at  TEXT NOT NULL,           -- ISO, UTC
    finished_at TEXT,
    status      TEXT NOT NULL,           -- ok | error
    duration_s  REAL,
    stats       TEXT,                    -- JSON-Objekt oder NULL
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_runs_job ON job_runs(job, started_at DESC);

-- Nutzer-Feedback. Ging bisher nur per Mail raus; die Kopie hier macht es im
-- Admin-Panel sicht- und abarbeitbar. `read_at` ist absichtlich global (nicht
-- je Admin): Es geht um „ist das erledigt?", nicht um „habe ich das gesehen?".
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id   INTEGER NOT NULL,
    email      TEXT,                  -- Adresse zum Zeitpunkt des Absendens
    kind       TEXT NOT NULL,         -- feature | bug | other
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at    TEXT                   -- NULL = ungelesen
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
"""

# Alle Tabellen, die an einem Konto hängen — Grundlage von `delete_web_user`
# (DSGVO Art. 17, Recht auf Löschung). Die Liste steht bewusst explizit hier
# statt zur Laufzeit aus dem Schema geraten zu werden; damit sie vollständig
# BLEIBT, prüft `test_delete_web_user_covers_every_user_table` sie gegen das
# Schema. Wer eine neue nutzerbezogene Tabelle anlegt, trägt sie hier ein —
# sonst schlägt der Test fehl und nennt die fehlende Tabelle.
USER_OWNED_TABLES: tuple[tuple[str, str], ...] = (
    ("topics", "owner_id"),
    ("committee_subscriptions", "owner_id"),
    ("vorlage_follows", "owner_id"),
    ("bookmarks", "owner_id"),
    ("notification_queue", "owner_id"),
    ("council_results_sent", "owner_id"),
    ("topic_hits_seen", "owner_id"),
    ("council_topic_matches", "owner_id"),
    ("council_topic_match_meta", "owner_id"),
    ("council_agenda_matches", "owner_id"),
    ("council_agenda_classified", "owner_id"),
    ("push_tokens", "owner_id"),
    ("qa_gespraeche", "user_id"),
    ("qa_gespraech_turns", "user_id"),
    ("qa_shares", "user_id"),
    ("deep_research_jobs", "user_id"),
    ("quiz_answers", "owner_id"),
    ("quiz_ratings", "owner_id"),
    ("quiz_daily", "owner_id"),
    ("user_quiz_questions", "owner_id"),
    ("user_activity", "owner_id"),
    # Feedback wird mitgelöscht: Es ist eine Nachricht dieser Person. Die
    # Betreiber-Kopie liegt ohnehin als E-Mail außerhalb der Datenbank, es
    # geht also keine Erkenntnis verloren.
    ("feedback", "owner_id"),
    ("password_reset_tokens", "user_id"),
    ("email_verification_tokens", "user_id"),
)


@dataclass
class TopicRow:
    id: int
    owner_id: int
    chat_id: int
    name: str
    description: str
    created_at: str



def _tagesbeginn_utc() -> str:
    """Beginn des heutigen Tages in Oldenburg, als UTC-Zeitstempel im Format
    der gespeicherten `created`-Spalte (datetime.utcnow().isoformat())."""
    try:
        from zoneinfo import ZoneInfo
        jetzt = datetime.now(ZoneInfo("Europe/Berlin"))
    except Exception:  # noqa: BLE001 — ohne tzdata bleibt es beim UTC-Tag
        jetzt = datetime.now(timezone.utc)
    start = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _umzug_von_nwz(ziel: Path) -> None:
    """Benennt eine noch vorhandene ``ratslotse.sqlite`` einmalig in den neuen Namen um.

    Bis 08/2026 hieß diese Datenbank ``ratslotse.sqlite`` — ein Rest aus der Zeit des
    Zeitungs-Scrapers. Der Name ist unsichtbar, und genau das macht ihn
    gefährlich: Ein Umstellen ohne Umzug hieße „App startet mit leerer
    Datenbank" (CLAUDE.md warnte davor). Deshalb zieht der Start die Datei
    selbst um, statt sich auf eine Handreichung auf dem Server zu verlassen.

    Vorher wird der WAL eingecheckt: Nur so ist die Hauptdatei vollständig und
    die Begleitdateien (``-wal``/``-shm``) sind entbehrlich.
    """
    if ziel.name == "nwz.sqlite":
        return
    alt = ziel.with_name("nwz.sqlite")
    if ziel.exists():
        # Eine LEERE Zieldatei ist kein Umzug, sondern ein Stolperstein: Sie
        # entsteht, sobald irgendetwas den neuen Pfad einmal öffnet, ohne zu
        # schreiben — und blockiert danach den Umzug für immer. Der Start
        # fände dann eine Datenbank ohne Tabellen vor, legte das Schema neu an
        # und die App käme mit LEEREN Konten hoch, während die echten Daten
        # unberührt unter dem alten Namen liegen. Genau davor warnt CLAUDE.md.
        #
        # Auf Prod stand am 01.09.2026 eine solche 0-Byte-Datei neben einer
        # 37-MB-`nwz.sqlite` mit 22 Konten. Deshalb: 0 Byte heißt „nicht da".
        if ziel.stat().st_size or not alt.exists() or not alt.stat().st_size:
            if ziel.stat().st_size and alt.exists() and alt.stat().st_size:
                # Beide gefüllt — das kann keine Maschine entscheiden.
                logging.getLogger("kern.store").warning(
                    "Zwei gefüllte Datenbanken nebeneinander: %s (%d Bytes) und %s "
                    "(%d Bytes). Es wird %s benutzt; die andere bitte von Hand "
                    "prüfen und wegräumen.",
                    ziel.name, ziel.stat().st_size, alt.name, alt.stat().st_size, ziel.name)
            return
        ziel.unlink()
        logging.getLogger("kern.store").warning(
            "Leere %s entfernt — sie hätte den Umzug von %s blockiert.",
            ziel.name, alt.name)
    if not alt.exists():
        return
    try:
        conn = sqlite3.connect(alt, timeout=15)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        alt.rename(ziel)
        for endung in ("-wal", "-shm"):
            rest = alt.with_name(alt.name + endung)
            if rest.exists():
                rest.unlink()
        logging.getLogger("kern.store").warning(
            "Datenbank umgezogen: %s → %s", alt.name, ziel.name)
    except Exception:  # noqa: BLE001 — lieber am alten Ort weiterarbeiten als abstürzen
        logging.getLogger("kern.store").exception(
            "Umzug von %s nach %s fehlgeschlagen — die App nutzt weiter den alten Pfad",
            alt, ziel)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _umzug_von_nwz(self.path)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # SQLites eingebautes lower() kennt nur ASCII — „Cäcilienbrücke" bliebe
        # damit groß-A-Ä-blind. Für Titel-Suchen (qa_gespraeche) rechnet Python.
        self._conn.create_function("unicode_lower", 1,
                                   lambda t: t.lower() if isinstance(t, str) else t)
        # WAL allows concurrent readers/writer (bot + cron + web API share this
        # file); busy_timeout lets writers wait instead of failing immediately.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()
        self._zeitungsreste_entfernen()

    def _werte_umschreiben(self, tabelle: str, spalte: str,
                           paare: list[tuple[str, str]]) -> None:
        """Schreibt gespeicherte WERTE um — idempotent.

        Das Gegenstück zu :meth:`_spalten_umbenennen`: Manche Begriffe stehen
        nicht als Spaltenname, sondern als Inhalt einer Zeile
        (``quiz_answers.category = 'geschichte'``). Wird nur die Spalte
        migriert, findet jede Abfrage danach nichts mehr.
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if spalte not in vorhanden:
            return
        for alt, neu in paare:
            cur = self._conn.execute(
                f"UPDATE {tabelle} SET {spalte} = ? WHERE {spalte} = ?", (neu, alt))
            if cur.rowcount:
                self._conn.commit()
                logging.getLogger("kern.store").warning(
                    "Werte umgeschrieben: %s.%s %r → %r (%d Zeilen)",
                    tabelle, spalte, alt, neu, cur.rowcount)

    def _spalten_umbenennen(self, tabelle: str, paare: list[tuple[str, str]]) -> None:
        """Benennt Spalten um, sofern sie noch alt heißen — idempotent.

        SQLite zieht Indizes und Fremdschlüssel dabei selbst nach (geprüft:
        ``idx_qa_turns_gespraech`` zeigt nach dem Lauf auf die neue Spalte).
        Läuft bei jedem Start; nach dem ersten Mal ist es ein PRAGMA und sonst
        nichts.
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if not vorhanden:                      # Tabelle gibt es (noch) nicht
            return
        for alt, neu in paare:
            if alt in vorhanden and neu not in vorhanden:
                with self._conn:
                    self._conn.execute(
                        f"ALTER TABLE {tabelle} RENAME COLUMN {alt} TO {neu}")
                logging.getLogger("kern.store").warning(
                    "Spalte umbenannt: %s.%s → %s", tabelle, alt, neu)

    def _tote_spalten_entfernen(self, tabelle: str, spalten: list[str]) -> None:
        """Entfernt Spalten, die nirgends mehr gelesen werden — idempotent.

        Braucht SQLite ≥ 3.35 (Prod und Dev: 3.45). Eine Spalte, die noch in
        einem Index steckt, ließe sich nicht entfernen — diese drei tun das
        nicht (geprüft).
        """
        vorhanden = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        for spalte in spalten:
            if spalte in vorhanden:
                with self._conn:
                    self._conn.execute(f"ALTER TABLE {tabelle} DROP COLUMN {spalte}")
                logging.getLogger("kern.store").warning(
                    "Tote Spalte entfernt: %s.%s", tabelle, spalte)

    def _prompts_tabelle_entfernen(self) -> None:
        """Die Tabelle der Prompt-Overrides fallen lassen — mit Protokoll."""
        vorhanden = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prompts'").fetchone()
        if not vorhanden:
            return
        log = logging.getLogger("kern.store")
        for key, content in self._conn.execute("SELECT key, content FROM prompts"):
            log.warning("Prompt-Override wird verworfen: %s — %r", key, (content or "")[:400])
        with self._conn:
            self._conn.execute("DROP TABLE prompts")
        log.warning("Tabelle `prompts` entfernt (Prompt-Overrides ausgebaut).")

    #: JSON-Schlüssel, die in gespeicherten Blobs mit umgezogen sind. NUR
    #: diese — `haltung`, `einig`, `auszug`, `top`, `art` und die Blocknamen
    #: (`debatten`, `presse`, `anlagen`, `parteien`) bleiben, wie sie sind.
    _JSON_SCHLUESSEL = {
        "sprecher": "speaker", "partei": "party", "datum": "date", "titel": "title",
        "hinweis": "note", "quellen": "sources", "bericht": "report",
        "frage": "question", "antwort": "answer", "wert": "value",
        "einheit": "unit", "grund": "reason", "stand": "as_of",
        "gremium": "committee", "fassung": "version", "schluessel": "key",
    }

    def _json_schluessel_umbenennen(self, tabelle: str, spalte: str, marke: str) -> None:
        """Die Schlüssel INNERHALB eines JSON-Blobs nachziehen — einmalig.

        Die Spalten sind längst englisch, ihr INHALT nicht: Ein gespeicherter
        Gesprächsverlauf trägt seine Debattenzeilen mit `sprecher`/`partei`/
        `datum`. Die Oberfläche liest sie neuerdings englisch und zeigte
        deshalb leere Namen. Eine Marke sorgt dafür, dass der Umbau genau
        einmal läuft und frisch geschriebene Zeilen nicht noch einmal trifft.
        """
        import json as _js
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS migrationsmarken ("
                "marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL)")
        if self._conn.execute(
                "SELECT 1 FROM migrationsmarken WHERE marke = ?", (marke,)).fetchone():
            return
        spalten = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tabelle})")}
        if spalte not in spalten:
            return

        def um(x):
            if isinstance(x, dict):
                return {self._JSON_SCHLUESSEL.get(k, k): um(v) for k, v in x.items()}
            if isinstance(x, list):
                return [um(v) for v in x]
            return x

        geaendert = []
        for rid, roh in self._conn.execute(f"SELECT rowid, {spalte} FROM {tabelle} "
                                           f"WHERE {spalte} IS NOT NULL"):
            try:
                daten = _js.loads(roh)
            except (ValueError, TypeError):
                continue
            neu = _js.dumps(um(daten), ensure_ascii=False)
            if neu != roh:
                geaendert.append((neu, rid))
        with self._conn:
            if geaendert:
                self._conn.executemany(
                    f"UPDATE {tabelle} SET {spalte} = ? WHERE rowid = ?", geaendert)
            self._conn.execute(
                "INSERT INTO migrationsmarken (marke, gesetzt_am) VALUES (?, datetime('now'))",
                (marke,))
        if geaendert:
            logging.getLogger("kern.store").warning(
                "JSON-Schlüssel nachgezogen: %s.%s (%d Zeilen)", tabelle, spalte, len(geaendert))

    def _migrate(self) -> None:
        # 08/2026: Die Prompt-Overrides sind ausgebaut — die Prompt-Texte leben
        # nur noch als Code in `kern/prompts.py` (Tims Entscheidung,
        # 31.08.2026). Die Tabelle darf mit; gemessen war sie auf dev leer und
        # auf Prod gar nicht angelegt. Sollte in einer unbekannten Umgebung
        # doch etwas darin stehen, landet es vorher im Log — ein stillschweigend
        # gelöschter, von Hand geschriebener Prompttext wäre ein schlechter Tausch.
        self._prompts_tabelle_entfernen()
        for tabelle, spalte in (("qa_gespraech_turns", "sources"),
                                ("qa_shares", "extras"),
                                ("deep_research_jobs", "sources")):
            self._json_schluessel_umbenennen(tabelle, spalte, f"json_englisch_{tabelle}_{spalte}")
        # 08/2026: Reste der NWZ-Abo-Prüfung. Seit der Ausgliederung des
        # Zeitungs-Scrapers liest sie kein Code mehr; auf Tims Anweisung
        # (30.08.2026) verschwinden sie samt Inhalt. Backup lag vor.
        self._tote_spalten_entfernen("web_users", [
            "nwz_username", "nwz_verified_at", "nwz_fulltext_allowed"])
        # Die Schnittstelle spricht Englisch, die Spalten ziehen nach.
        self._spalten_umbenennen("qa_gespraeche", [("titel", "title")])
        # Der ALTE Name ist die Quelle der Migration — in #859 hatte ein
        # Suchen-und-Ersetzen ihn mitgenommen und den Schritt wirkungslos
        # gemacht. Bestehende Datenbanken wären deutsch geblieben.
        self._spalten_umbenennen("user_quiz_questions", [("stadtteil", "district")])
        self._spalten_umbenennen("qa_shares", [
            ("frage", "question"), ("antwort", "answer"), ("quellen", "sources")])
        self._spalten_umbenennen("deep_research_jobs", [
            ("frage", "question"), ("bericht", "report"),
            ("quellen", "sources"), ("gesehen", "seen")])
        for tabelle in ("vorlage_follows", "bookmarks"):
            self._spalten_umbenennen(tabelle, [("vorlage_nr", "template_number")])
        self._spalten_umbenennen("qa_gespraech_turns", [
            ("gespraech_id", "conversation_id"), ("frage", "question"),
            ("antwort", "answer"), ("quellen", "sources")])
        # Die Quiz-Kategorien stehen als Daten in den Zeilen, in der
        # Antwort-Historie wie in den selbst gestellten Fragen.
        QUIZ_KATEGORIEN = [
            ("geschichte", "history"), ("orte", "places"), ("menschen", "people"),
            ("ratspolitik", "council_politics"), ("schaetzen", "estimation"),
        ]
        self._werte_umschreiben("quiz_answers", "category", QUIZ_KATEGORIEN)
        self._werte_umschreiben("user_quiz_questions", "category", QUIZ_KATEGORIEN)
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(topics)").fetchall()}
        if "chat_id" not in cols:
            admin = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE topics ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0"
                )
                if admin:
                    self._conn.execute("UPDATE topics SET chat_id = ?", (admin,))
                    now = datetime.utcnow().isoformat(timespec="seconds")
                    self._conn.execute(
                        "INSERT OR IGNORE INTO users (chat_id, username, added_at) VALUES (?, ?, ?)",
                        (admin, "admin", now),
                    )
        # Reassign orphaned topics (chat_id=0) to admin — covers topics added
        # before chat_id was properly set in add_topic().
        orphan_count = self._conn.execute(
            "SELECT COUNT(*) FROM topics WHERE chat_id = 0"
        ).fetchone()[0]
        if orphan_count > 0:
            admin = int(os.environ.get("TELEGRAM_CHAT_ID", 0))
            if admin:
                with self._conn:
                    self._conn.execute(
                        "UPDATE topics SET chat_id = ? WHERE chat_id = 0", (admin,)
                    )
        # web_users gained status / NWZ-verification columns after the first cut.
        wu_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(web_users)").fetchall()}
        if wu_cols:
            with self._conn:
                if "status" not in wu_cols:
                    # Existing accounts predate approval — treat them as active.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
                if "token_version" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
                if "topics_seen_at" not in wu_cols:
                    # NULL heißt „noch nie nachgesehen" — bestehende Konten
                    # behalten ihre Bubble, bis sie die Übersicht öffnen.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN topics_seen_at TEXT")
                if "email_verified" not in wu_cols:
                    # Existing accounts predate email verification — treat them as
                    # verified so the new gate never locks anyone out.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
                    self._conn.execute("UPDATE web_users SET email_verified = 1")
                if "onboarding" not in wu_cols:
                    # Onboarding-Fortschritt geräteübergreifend am Konto
                    # (JSON: {"steps": [...], "celebrated": bool}).
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN onboarding TEXT")
                # Sign in with Apple (RL-1002): stabile Apple-User-ID +
                # Kennzeichen, ob je ein eigenes Passwort gesetzt wurde.
                if "apple_sub" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN apple_sub TEXT")
                if "display_name" not in wu_cols:
                    # Anzeigename für die persönliche Ansprache (Dashboard, Mails).
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN display_name TEXT")
                if "badges" not in wu_cols:
                    # Lotsen-Abzeichen (RL-U12): JSON {"earned": [...],
                    # "map_places": [...], "flags": [...]} — eigene Spalte
                    # neben dem Onboarding, damit sich beide nicht überschreiben.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN badges TEXT")
                if "password_set" not in wu_cols:
                    self._conn.execute(
                        "ALTER TABLE web_users ADD COLUMN password_set INTEGER NOT NULL DEFAULT 1"
                    )
                if "notify_prefs" not in wu_cols:
                    # Design 30a: die sechs Anlass-Schalter als JSON.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN notify_prefs TEXT")
                if "qa_speichern" not in wu_cols:
                    # 6a①②: NULL = noch nie gefragt (Erstnutzungs-Karte),
                    # 1 = Gespräche speichern, 0 = bewusst aus.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN qa_speichern INTEGER")
                if "deep_limit" not in wu_cols:
                    # Admin-steuerbare Frage-Limits je Konto (10.08.26):
                    # deep_limit = Recherchen/Tag (NULL = Standard,
                    # 0 = unbegrenzt, N = eigenes Limit); limits_frei = 1
                    # überspringt die Rate-Limiter der Frage-Endpoints.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN deep_limit INTEGER")
                    self._conn.execute(
                        "ALTER TABLE web_users ADD COLUMN limits_frei INTEGER NOT NULL DEFAULT 0")
                # Einrichtungs-Assistent (Design 26a): welcher Schritt zuletzt
                # erreicht wurde. Eigene Spalten statt der onboarding-JSON —
                # die gehört der „Erste Schritte"-Tour, und der Erinnerungs-Cron
                # will ohnehin per SQL filtern statt JSON zu parsen.
                if "setup_step" not in wu_cols:
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN setup_step INTEGER")
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN setup_started_at TEXT")
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN setup_updated_at TEXT")
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN setup_done_at TEXT")
                    # Wann die eine Erinnerungsmail rausging — verhindert, dass
                    # jemand sie zweimal bekommt.
                    self._conn.execute("ALTER TABLE web_users ADD COLUMN setup_reminded_at TEXT")
        # Schätzfrage-Slider für eigene Fragen (RL-U14-Erweiterung): Zahl-Felder
        # zur seit RL-U14 bestehenden Tabelle nachziehen.
        uq_cols = self._table_cols("user_quiz_questions")
        if uq_cols:
            with self._conn:
                for col, ddl in (("qtype", "TEXT NOT NULL DEFAULT 'mc'"), ("answer_value", "REAL"),
                                 ("answer_unit", "TEXT"), ("range_min", "REAL"), ("range_max", "REAL")):
                    if col not in uq_cols:
                        self._conn.execute(f"ALTER TABLE user_quiz_questions ADD COLUMN {col} {ddl}")
        # Geteilte Antworten tragen seit dem Bausteine-Nachtrag auch Debatten,
        # Presse, Anlagen und Parteien-Positionen — alte Zeilen bleiben ohne.
        qs_cols = self._table_cols("qa_shares")
        if qs_cols and "extras" not in qs_cols:
            with self._conn:
                self._conn.execute("ALTER TABLE qa_shares ADD COLUMN extras TEXT")
        # Zustellversuche der Warteschlange (30a-Nachtrag): bestehende
        # Installationen haben die Spalte noch nicht.
        nq_cols = self._table_cols("notification_queue")
        if nq_cols and "attempts" not in nq_cols:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE notification_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
                )
        # Eigener Kurztext für die Push-Vorschau (Tims Wunsch 18.08.): Der
        # plattgeklopfte Mail-Text taugt dort nicht (Datum, Ort, dann erst
        # die Sache). NULL = wie bisher aus body_html ableiten.
        if nq_cols and "push_text" not in nq_cols:
            with self._conn:
                self._conn.execute("ALTER TABLE notification_queue ADD COLUMN push_text TEXT")
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_web_users_apple_sub "
            "ON web_users(apple_sub) WHERE apple_sub IS NOT NULL"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topics_chat ON topics(chat_id)"
        )
        self._conn.commit()
        self._migrate_owner_id()
        self._treffer_datum_reparieren()

    def _treffer_datum_reparieren(self) -> None:
        """Einmalige Reparatur: ``council_topic_matches.matched_at`` im Bestand.

        Bis zum 17.08.2026 löschte ``save_topic_decision_matches`` vor jedem
        Lauf alle Treffer eines Themas und legte sie neu an — im Bestand trägt
        deshalb JEDE Zeile das Datum des letzten wöchentlichen Matchings (am
        17.08. gemessen: alle 919 Zeilen der Prod-DB auf denselben Tag). Ohne
        diese Reparatur meldete der nächste Wochenüberblick denselben
        vollständigen Bestand noch einmal als Neuigkeit der Woche — der Fehler
        wäre behoben und die Meldung käme trotzdem.

        Leeres ``matched_at`` ist der Vorgabewert der Spalte und heißt „schon
        bekannt": Genau das ist der Bestand. ``PRAGMA user_version`` merkt sich,
        dass es erledigt ist — sonst liefe die Reparatur bei jedem Start und
        machte echte neue Treffer wieder unsichtbar.
        """
        if self._conn.execute("PRAGMA user_version").fetchone()[0] >= 1:
            return
        with self._conn:
            self._conn.execute("UPDATE council_topic_matches SET matched_at = ''")
        self._conn.execute("PRAGMA user_version = 1")
        self._conn.commit()

    def _table_cols(self, table: str) -> set[str]:
        return {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _migrate_owner_id(self) -> None:
        """Move ownership from Telegram chat_id to a canonical owner_id (=web_users.id).

        Idempotent: each step is guarded on whether its target column exists.
        Telegram-only chat_ids (no web account) get a synthetic web_users row so
        every owner has a stable id. The chat_id stays only as a delivery target
        (web_users.telegram_chat_id) and on topics for rollback.
        """
        wu_cols = self._table_cols("web_users")
        if not wu_cols:
            return  # web_users not created yet (shouldn't happen — SCHEMA runs first)

        with self._conn:
            # 1. delivery_channel column on web_users.
            if "delivery_channel" not in wu_cols:
                self._conn.execute(
                    "ALTER TABLE web_users ADD COLUMN delivery_channel TEXT NOT NULL DEFAULT 'email'"
                )

            # 2. Synthetic web_users for every chat_id that owns something but has
            #    no web account yet (incl. the admin from TELEGRAM_CHAT_ID).
            now = datetime.utcnow().isoformat(timespec="seconds")
            linked = {
                r[0] for r in self._conn.execute(
                    "SELECT telegram_chat_id FROM web_users WHERE telegram_chat_id IS NOT NULL"
                ).fetchall()
            }
            # Only chat_ids that actually own something need a synthetic owner.
            # The admin (TELEGRAM_CHAT_ID) is covered implicitly via users/topics
            # once they own data; a fresh DB creates no synthetic accounts.
            chat_ids: set[int] = set()
            chat_ids.update(r[0] for r in self._conn.execute("SELECT DISTINCT chat_id FROM users").fetchall())
            chat_ids.update(r[0] for r in self._conn.execute("SELECT DISTINCT chat_id FROM topics").fetchall())
            if "chat_id" in self._table_cols("committee_subscriptions"):
                chat_ids.update(r[0] for r in self._conn.execute(
                    "SELECT DISTINCT chat_id FROM committee_subscriptions").fetchall())
            chat_ids.discard(0)  # 0 = orphan / no owner
            for cid in sorted(chat_ids - linked):
                # password_hash '!' can never match a bcrypt verify → no login.
                self._conn.execute(
                    "INSERT OR IGNORE INTO web_users "
                    "(email, password_hash, role, status, telegram_chat_id, delivery_channel, created_at) "
                    "VALUES (?, '!', 'user', 'active', ?, 'telegram', ?)",
                    (f"tg-{cid}@local", cid, now),
                )

            # 3. topics.owner_id (ADD COLUMN — no constraint change needed).
            if "owner_id" not in self._table_cols("topics"):
                self._conn.execute("ALTER TABLE topics ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0")
            self._conn.execute(
                "UPDATE topics SET owner_id = COALESCE("
                "  (SELECT id FROM web_users WHERE telegram_chat_id = topics.chat_id), 0) "
                "WHERE owner_id = 0"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_topics_owner ON topics(owner_id)")

            # 4. Rebuild the constrained tables so their PK/UNIQUE is on owner_id.
            #    (chat_id is dropped here; it is recoverable via web_users.)
            if "owner_id" not in self._table_cols("committee_subscriptions"):
                self._conn.execute(
                    "CREATE TABLE committee_subscriptions_new ("
                    " id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL,"
                    " committee_name TEXT NOT NULL, created_at TEXT NOT NULL,"
                    " UNIQUE(owner_id, committee_name))"
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO committee_subscriptions_new (id, owner_id, committee_name, created_at) "
                    "SELECT cs.id, wu.id, cs.committee_name, cs.created_at FROM committee_subscriptions cs "
                    "JOIN web_users wu ON wu.telegram_chat_id = cs.chat_id"
                )
                self._conn.execute("DROP TABLE committee_subscriptions")
                self._conn.execute("ALTER TABLE committee_subscriptions_new RENAME TO committee_subscriptions")

            # Die beiden Zeitungs-Tabellen (article_topic_matches,
            # topic_classified_editions) hatten hier ebenfalls eine
            # chat_id→owner_id-Migration. Sie sind mit dem NWZ-Ausbau
            # entfallen; _zeitungsreste_entfernen räumt die leeren Hüllen weg.

    #: Tabellen aus der Zeitungs-Zeit. Der Scraper ist mit der NWZ-Ausgliederung
    #: entfallen, die Inhalte hat scripts/purge_nwz_data.py gelöscht — die leeren
    #: Hüllen wurden aber bei JEDEM Start neu angelegt und schleppten drei
    #: Alt-Migrationen mit sich.
    _ZEITUNGSRESTE = ("articles_fts", "articles", "editions",
                      "article_topic_matches", "topic_classified_editions")

    def _zeitungsreste_entfernen(self) -> None:
        """Leere Zeitungs-Tabellen aus Bestands-Datenbanken werfen.

        Nur LEERE: Fände sich wider Erwarten noch eine Zeile, bleibt die Tabelle
        stehen und meldet sich im Log. Löschen wäre hier der teurere Irrtum —
        die Hülle kostet nichts, verlorene Daten wären weg. Neue Datenbanken
        legen sie ohnehin nicht mehr an.
        """
        for tabelle in self._ZEITUNGSRESTE:
            try:
                da = self._conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = ?", (tabelle,)).fetchone()
                if not da:
                    continue
                n = self._conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
                if n:
                    logger.warning("Zeitungs-Tabelle %s hat noch %d Zeile(n) — bleibt stehen. "
                                   "Erst scripts/purge_nwz_data.py laufen lassen.", tabelle, n)
                    continue
                with self._conn:
                    self._conn.execute(f"DROP TABLE IF EXISTS {tabelle}")
                logger.info("leere Zeitungs-Tabelle %s entfernt", tabelle)
            except sqlite3.Error:  # noqa: PERF203 — Aufräumen darf nie den Start kippen
                logger.warning("Zeitungs-Tabelle %s ließ sich nicht prüfen/entfernen",
                               tabelle, exc_info=True)

    def close(self) -> None:
        self._conn.close()

    # ---- web accounts ----

    def create_web_user(self, email: str, password_hash: str, role: str = "user",
                        status: str = "pending", email_verified: bool = False,
                        display_name: str | None = None) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO web_users (email, password_hash, role, status, email_verified, created_at, display_name) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (email.lower().strip(), password_hash, role, status, 1 if email_verified else 0, now,
                 (display_name or "").strip()[:60] or None),
            )
        return cur.lastrowid

    def set_display_name(self, user_id: int, display_name: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET display_name = ? WHERE id = ?",
                ((display_name or "").strip()[:60] or None, user_id),
            )

    def get_web_user_by_apple_sub(self, apple_sub: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM web_users WHERE apple_sub = ?", (apple_sub,)
        ).fetchone()
        return dict(row) if row else None

    def link_apple_sub(self, user_id: int, apple_sub: str, *, password_set: bool | None = None) -> None:
        """Apple-ID mit einem Konto verknüpfen (RL-1002). password_set=False
        markiert frisch per Apple erstellte Konten ohne eigenes Passwort."""
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET apple_sub = ? WHERE id = ?", (apple_sub, user_id)
            )
            if password_set is not None:
                self._conn.execute(
                    "UPDATE web_users SET password_set = ? WHERE id = ?",
                    (1 if password_set else 0, user_id),
                )

    def set_web_user_status(self, user_id: int, status: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE web_users SET status = ? WHERE id = ?", (status, user_id))

    def set_delivery_channel(self, owner_id: int, channel: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET delivery_channel = ? WHERE id = ?", (channel, owner_id)
            )

    def get_delivery_channel(self, owner_id: int) -> str:
        """Der Zustellweg eines Kontos — ``email`` | ``push`` | ``both`` | ``off``.

        Schlanker als ``get_web_user_by_id``, weil ``kern.notify.gewuenscht()``
        das bei jedem einzelnen Einreihen wissen muss. Ein unbekanntes Konto
        gilt als ``email`` (die Vorgabe der Spalte) — nie als ``off``: Ein
        Lesefehler darf niemanden stillschweigend abmelden.
        """
        row = self._conn.execute(
            "SELECT delivery_channel FROM web_users WHERE id = ?", (owner_id,)).fetchone()
        return (row[0] if row and row[0] else "email")

    def get_onboarding(self, user_id: int) -> dict:
        """Onboarding-Fortschritt des Kontos: {"steps": [...], "celebrated": bool}.
        Am Konto statt im localStorage, damit er auf jedem Gerät derselbe ist."""
        row = self._conn.execute(
            "SELECT onboarding FROM web_users WHERE id = ?", (user_id,)
        ).fetchone()
        raw = row[0] if row else None
        if raw:
            try:
                data = json.loads(raw)
                steps = [s for s in data.get("steps", []) if isinstance(s, str)]
                return {"steps": steps, "celebrated": bool(data.get("celebrated"))}
            except (TypeError, ValueError):
                pass
        return {"steps": [], "celebrated": False}

    def get_badge_state(self, user_id: int) -> dict:
        """Roh-Zustand der Lotsen-Abzeichen (RL-U12): {"earned": [ids],
        "map_places": [slugs], "flags": ["sitzung", "tour", "frage", ...]}."""
        row = self._conn.execute(
            "SELECT badges FROM web_users WHERE id = ?", (user_id,)
        ).fetchone()
        raw = row[0] if row else None
        if raw:
            try:
                data = json.loads(raw)
                return {
                    "earned": [s for s in data.get("earned", []) if isinstance(s, str)],
                    "map_places": [s for s in data.get("map_places", []) if isinstance(s, str)],
                    "flags": [s for s in data.get("flags", []) if isinstance(s, str)],
                }
            except (TypeError, ValueError):
                pass
        return {"earned": [], "map_places": [], "flags": []}

    def save_badge_state(self, user_id: int, state: dict) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET badges = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), user_id),
            )

    def update_onboarding(
        self, user_id: int, steps: list[str] | None = None, celebrated: bool | None = None
    ) -> dict:
        """Schritte idempotent dazumergen und/oder das Abschluss-Flag setzen."""
        cur = self.get_onboarding(user_id)
        for s in steps or []:
            if s not in cur["steps"]:
                cur["steps"].append(s)
        if celebrated is not None:
            cur["celebrated"] = bool(celebrated)
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET onboarding = ? WHERE id = ?",
                (json.dumps(cur, ensure_ascii=False), user_id),
            )
        return cur

    # ---- Einrichtungs-Assistent (Design 26a) -------------------------------
    def set_setup_step(self, user_id: int, step: int, done: bool = False) -> None:
        """Erreichten Schritt am Konto festhalten.

        Am Konto statt nur im Gerät: So überlebt der Stand eine Neuinstallation,
        gilt auf jedem Gerät — und der Erinnerungs-Cron kann überhaupt erst
        erkennen, wer angefangen und nicht zu Ende gebracht hat.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET setup_step = ?, "
                "setup_started_at = COALESCE(setup_started_at, ?), "
                "setup_updated_at = ?, "
                "setup_done_at = CASE WHEN ? THEN ? ELSE setup_done_at END "
                "WHERE id = ?",
                (step, now, now, 1 if done else 0, now, user_id),
            )

    def get_setup(self, user_id: int) -> dict:
        row = self._conn.execute(
            "SELECT setup_step, setup_started_at, setup_done_at FROM web_users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return {"step": 0, "started_at": None, "done_at": None}
        return {"step": row["setup_step"] or 0, "started_at": row["setup_started_at"],
                "done_at": row["setup_done_at"]}

    def setups_to_remind(self, older_than_hours: int = 48, limit: int = 200) -> list[dict]:
        """Konten, die die Einrichtung angefangen und liegen gelassen haben.

        Bedingungen bewusst streng — die Mail geht genau einmal und nur an
        Menschen, die sie einordnen können: mindestens Schritt 1 erreicht (wer
        beim Gruß abbricht, hat nichts angefangen), nichts abgeschlossen, seit
        ``older_than_hours`` keine Bewegung, noch nie erinnert, Konto aktiv,
        E-Mail bestätigt — und Benachrichtigungen nicht abgeschaltet. Letzteres
        ist die Probe aufs Exempel: Ein Aus-Schalter, den die freundlich
        gemeinte Erinnerung übergeht, ist keiner.
        """
        cutoff = (datetime.utcnow() - timedelta(hours=older_than_hours)).isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT id, email, display_name, setup_step, setup_started_at FROM web_users "
            "WHERE setup_started_at IS NOT NULL "
            "  AND COALESCE(setup_updated_at, setup_started_at) <= ? "
            "  AND setup_done_at IS NULL AND setup_reminded_at IS NULL "
            "  AND COALESCE(setup_step, 0) >= 1 "
            "  AND status = 'active' AND email_verified = 1 "
            "  AND COALESCE(delivery_channel, 'email') <> 'off' "
            "ORDER BY setup_started_at LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_setup_reminded(self, user_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET setup_reminded_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(timespec="seconds"), user_id),
            )

    # ---- Quiz: Antworten (Punkte je Gebiet) + Bewertungen ----

    def record_quiz_answer(self, owner_id: int, question_id: int, area_type: str,
                           area_key: str, category: str, correct: bool, points: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO quiz_answers (owner_id, question_id, area_type, area_key, "
                "category, correct, points, answered_at) VALUES (?,?,?,?,?,?,?,?)",
                (owner_id, question_id, area_type, area_key, category, int(correct), points, now),
            )

    def quiz_answered_ids(self, owner_id: int) -> list[int]:
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT question_id FROM quiz_answers WHERE owner_id = ?", (owner_id,)).fetchall()]

    def quiz_stats(self, owner_id: int) -> dict:
        """Fortschritt je Gebiet: Punkte, beantwortet, richtig, zuletzt gespielt —
        plus Gesamtsumme. Grundlage des „meine Schwächen"-Dashboards."""
        rows = self._conn.execute(
            "SELECT area_type, area_key, "
            "  SUM(points) points, COUNT(*) answered, SUM(correct) correct, "
            "  MAX(answered_at) last_at "
            "FROM quiz_answers WHERE owner_id = ? GROUP BY area_type, area_key", (owner_id,)).fetchall()
        by_area = [{"area_type": r["area_type"], "area_key": r["area_key"],
                    "points": r["points"] or 0, "answered": r["answered"],
                    "correct": r["correct"] or 0, "last_at": r["last_at"]} for r in rows]
        tot = self._conn.execute(
            "SELECT COALESCE(SUM(points),0) points, COUNT(*) answered, COALESCE(SUM(correct),0) correct "
            "FROM quiz_answers WHERE owner_id = ?", (owner_id,)).fetchone()
        return {"by_area": by_area,
                "total": {"points": tot["points"], "answered": tot["answered"], "correct": tot["correct"]}}

    def quiz_points_by_area(self, owner_id: int) -> dict:
        """{(area_type, area_key): points} — für die Gebiets-Kacheln der Auswahl."""
        return {(r["area_type"], r["area_key"]): r["points"] or 0 for r in self._conn.execute(
            "SELECT area_type, area_key, SUM(points) points FROM quiz_answers "
            "WHERE owner_id = ? GROUP BY area_type, area_key", (owner_id,)).fetchall()}

    def quiz_wrong_question_ids(self, owner_id: int) -> list[int]:
        """Der „Meine Fehler"-Stapel: Fragen, deren JÜNGSTE Antwort dieses
        Nutzers falsch war. Wird die Frage später richtig beantwortet, fällt sie
        raus (id = letzter Versuch). Für den Wiederhol-/Lernmodus."""
        return [r[0] for r in self._conn.execute(
            "SELECT question_id FROM quiz_answers a "
            "WHERE owner_id = ? AND correct = 0 AND question_id > 0 AND id = ("
            "  SELECT MAX(id) FROM quiz_answers "
            "  WHERE owner_id = a.owner_id AND question_id = a.question_id) "
            "ORDER BY id DESC", (owner_id,)).fetchall()]

    def quiz_streak(self, owner_id: int) -> int:
        """Aktuelle Serie: aufeinanderfolgende Kalendertage (UTC) mit mindestens
        einer beantworteten Frage, die heute oder gestern endet (sonst 0)."""
        days = [r[0] for r in self._conn.execute(
            "SELECT DISTINCT substr(answered_at,1,10) d FROM quiz_answers "
            "WHERE owner_id = ? ORDER BY d DESC", (owner_id,)).fetchall()]
        if not days:
            return 0
        from datetime import date
        today = datetime.utcnow().date()
        cur = date.fromisoformat(days[0])
        if (today - cur).days > 1:      # letzte Aktivität älter als gestern → Serie gerissen
            return 0
        streak = 1
        for prev in days[1:]:
            p = date.fromisoformat(prev)
            if (cur - p).days == 1:
                streak += 1
                cur = p
            else:
                break
        return streak

    def record_quiz_daily(self, owner_id: int, day: str, correct: int, total: int,
                          points: int) -> None:
        """Ergebnis der Tages-Challenge festhalten (idempotent, eins je Tag)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO quiz_daily (owner_id, day, correct, total, points, completed_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(owner_id, day) DO UPDATE SET "
                "correct=excluded.correct, total=excluded.total, points=excluded.points, "
                "completed_at=excluded.completed_at",
                (owner_id, day, correct, total, points, now))

    def quiz_daily_result(self, owner_id: int, day: str) -> dict | None:
        """Mein Ergebnis der Tages-Challenge eines Tages (oder None)."""
        r = self._conn.execute(
            "SELECT day, correct, total, points, completed_at FROM quiz_daily "
            "WHERE owner_id = ? AND day = ?", (owner_id, day)).fetchone()
        return {"day": r["day"], "correct": r["correct"], "total": r["total"],
                "points": r["points"], "completed_at": r["completed_at"]} if r else None

    def rate_quiz_question(self, owner_id: int, question_id: int, verdict: str,
                           comment: str | None = None) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO quiz_ratings (owner_id, question_id, verdict, comment, created_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(owner_id, question_id) DO UPDATE SET "
                "verdict=excluded.verdict, comment=excluded.comment, created_at=excluded.created_at",
                (owner_id, question_id, verdict, comment, now),
            )

    def quiz_flagged_questions(self, min_bad: int = 1) -> list[dict]:
        """Fragen mit mindestens ``min_bad`` Schlecht-Bewertungen, schlechteste
        zuerst — für die Admin-Sichtung. Cross-DB: liefert Ids + Zähler + die
        (optionalen) Begründungen; die Fragentexte holt der Router aus
        council.sqlite."""
        rows = self._conn.execute(
            "SELECT question_id, "
            "  SUM(verdict='schlecht') bad, SUM(verdict='gut') good, "
            "  group_concat(CASE WHEN verdict='schlecht' AND comment IS NOT NULL "
            "    AND trim(comment) != '' THEN comment END, ' • ') comments "
            "FROM quiz_ratings GROUP BY question_id "
            "HAVING bad >= ? ORDER BY bad DESC, good ASC", (min_bad,)).fetchall()
        return [{"question_id": r["question_id"], "bad": r["bad"], "good": r["good"],
                 "comments": r["comments"]} for r in rows]

    def quiz_admin_kennzahlen(self) -> dict:
        """Admin-Quiz-Kennzahlen (Design 21a): ⌀ Trefferquote über alle
        gespielten Antworten (%) und Anzahl aktuell gemeldeter Fragen (≥ 1×
        „schlecht“)."""
        row = self._conn.execute(
            "SELECT COUNT(*) n, COALESCE(AVG(correct), 0) acc FROM quiz_answers"
        ).fetchone()
        gemeldet = self._conn.execute(
            "SELECT COUNT(*) FROM (SELECT question_id FROM quiz_ratings "
            "GROUP BY question_id HAVING SUM(verdict='schlecht') >= 1)"
        ).fetchone()[0]
        return {"antworten": row["n"], "avg_accuracy": round(row["acc"] * 100), "gemeldet": gemeldet}

    # ---- Quiz: eigene Fragen (RL-U14, privat je Konto) ----

    @staticmethod
    def _user_quiz_row(r) -> dict:
        keys = r.keys()
        return {"id": r["id"], "question": r["question"],
                "options": json.loads(r["options"]), "correct_index": r["correct_index"],
                "district": r["district"], "category": r["category"],
                "explanation": r["explanation"], "practiced": r["practiced"],
                "correct_count": r["correct_count"], "created_at": r["created_at"],
                "qtype": (r["qtype"] if "qtype" in keys else None) or "mc",
                "answer_value": r["answer_value"] if "answer_value" in keys else None,
                "unit": r["answer_unit"] if "answer_unit" in keys else None,
                "range_min": r["range_min"] if "range_min" in keys else None,
                "range_max": r["range_max"] if "range_max" in keys else None}

    def list_user_quiz_questions(self, owner_id: int) -> list[dict]:
        """Alle eigenen Fragen eines Kontos, neueste zuerst — samt Übungs-
        Zählern („3× geübt, 100 %")."""
        rows = self._conn.execute(
            "SELECT * FROM user_quiz_questions WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,)).fetchall()
        return [self._user_quiz_row(r) for r in rows]

    def get_user_quiz_question(self, owner_id: int, question_id: int) -> dict | None:
        r = self._conn.execute(
            "SELECT * FROM user_quiz_questions WHERE owner_id = ? AND id = ?",
            (owner_id, question_id)).fetchone()
        return self._user_quiz_row(r) if r else None

    def save_user_quiz_question(self, owner_id: int, data: dict,
                                question_id: int | None = None) -> int | None:
        """Eigene Frage anlegen (``question_id=None``) oder aktualisieren.
        Beim Bearbeiten werden die Übungs-Zähler zurückgesetzt — die Frage ist
        dann inhaltlich eine andere. Gibt die id zurück (None, wenn die zu
        bearbeitende Frage nicht dem Konto gehört)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        opts = json.dumps(data["options"], ensure_ascii=False)
        est = (data.get("qtype", "mc"), data.get("answer_value"), data.get("unit"),
               data.get("range_min"), data.get("range_max"))
        with self._conn:
            if question_id is None:
                cur = self._conn.execute(
                    "INSERT INTO user_quiz_questions (owner_id, question, options, "
                    "correct_index, district, category, explanation, qtype, answer_value, "
                    "answer_unit, range_min, range_max, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (owner_id, data["question"], opts, data["correct_index"],
                     data.get("district"), data["category"], data.get("explanation"),
                     *est, now))
                return int(cur.lastrowid)
            cur = self._conn.execute(
                "UPDATE user_quiz_questions SET question=?, options=?, correct_index=?, "
                "district=?, category=?, explanation=?, qtype=?, answer_value=?, "
                "answer_unit=?, range_min=?, range_max=?, practiced=0, correct_count=0 "
                "WHERE owner_id = ? AND id = ?",
                (data["question"], opts, data["correct_index"], data.get("district"),
                 data["category"], data.get("explanation"), *est, owner_id, question_id))
            return question_id if cur.rowcount else None

    def delete_user_quiz_question(self, owner_id: int, question_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM user_quiz_questions WHERE owner_id = ? AND id = ?",
                (owner_id, question_id))
        return cur.rowcount > 0

    def user_quiz_round(self, owner_id: int, n: int) -> list[dict]:
        """Übungsrunde: nie geübte zuerst, dann die mit der schwächsten
        Trefferquote — innerhalb der Gruppen zufällig gemischt."""
        rows = self._conn.execute(
            "SELECT * FROM user_quiz_questions WHERE owner_id = ? "
            "ORDER BY (practiced = 0) DESC, "
            "  CAST(correct_count AS REAL) / MAX(practiced, 1) ASC, RANDOM() LIMIT ?",
            (owner_id, n)).fetchall()
        return [self._user_quiz_row(r) for r in rows]

    def record_user_quiz_practice(self, owner_id: int, question_id: int, correct: bool) -> None:
        """Übungs-Zähler fortschreiben — bewusst OHNE quiz_answers-Eintrag
        (eigene Fragen geben keine Punkte und zählen nicht für Abzeichen)."""
        with self._conn:
            self._conn.execute(
                "UPDATE user_quiz_questions SET practiced = practiced + 1, "
                "correct_count = correct_count + ? WHERE owner_id = ? AND id = ?",
                (1 if correct else 0, owner_id, question_id))

    # ---- native-app push device tokens ----

    def add_push_token(self, owner_id: int, token: str, platform: str) -> None:
        """Register (or refresh) a device push token for an owner. Re-registering
        the same token upserts owner/platform/last_seen — covers OS token rotation
        and a device being handed to a different account."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO push_tokens (token, owner_id, platform, created_at, last_seen) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(token) DO UPDATE SET owner_id = excluded.owner_id, "
                "platform = excluded.platform, last_seen = excluded.last_seen",
                (token, owner_id, platform, now, now),
            )

    def remove_push_token(self, token: str) -> None:
        """Drop a device token (logout on device, or APNs/FCM reported it stale)."""
        with self._conn:
            self._conn.execute("DELETE FROM push_tokens WHERE token = ?", (token,))

    def get_push_tokens_for_owner(self, owner_id: int) -> list[dict]:
        """Return [{token, platform}] for all of an owner's registered devices."""
        rows = self._conn.execute(
            "SELECT token, platform FROM push_tokens WHERE owner_id = ?", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def _attach_push_tokens(self, by_owner: dict[int, dict]) -> None:
        """Fill each owner dict's ``push_tokens`` list in a single query. Used by
        the digest/subscription delivery-target helpers so ``kern.delivery`` can
        reach registered devices without its own DB handle."""
        for o in by_owner.values():
            o.setdefault("push_tokens", [])
        if not by_owner:
            return
        placeholders = ",".join("?" * len(by_owner))
        for pr in self._conn.execute(
            f"SELECT owner_id, token, platform FROM push_tokens WHERE owner_id IN ({placeholders})",
            tuple(by_owner.keys()),
        ).fetchall():
            o = by_owner.get(pr["owner_id"])
            if o is not None:
                o["push_tokens"].append({"token": pr["token"], "platform": pr["platform"]})

    # ---- Ergebnis-Meldung N3 (Design 30a) ----

    def owners_with_agenda_match(self, ksinr: int) -> list[int]:
        """Konten, denen zu dieser Sitzung schon ein TOP gemeldet wurde.

        Genau die bekommen später das Ergebnis: Der Vorgang, den sie kennen,
        bekommt seinen Abschluss — wer nie etwas dazu gehört hat, wird nicht
        nachträglich behelligt.
        """
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT owner_id FROM council_agenda_matches WHERE ksinr = ? ORDER BY owner_id",
            (ksinr,))]

    def owners_subscribed_to(self, committee: str) -> list[int]:
        """Konten mit Abo auf dieses Gremium (Design 30a, N5)."""
        return [r[0] for r in self._conn.execute(
            "SELECT owner_id FROM committee_subscriptions WHERE committee_name = ? ORDER BY owner_id",
            (committee,))]

    def owners_with_topic_matches_since(self, seit: str) -> list[int]:
        """Konten mit neuen Beschluss-Treffern seit ``seit`` (Design 30a, N6).
        JOIN topics wie überall: Treffer eines gelöschten Themas zählen nicht."""
        return [r[0] for r in self._conn.execute(
            """SELECT DISTINCT m.owner_id FROM council_topic_matches m
               JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
               WHERE m.matched_at >= ? ORDER BY m.owner_id""", (seit,))]

    def topic_match_decision_ids_since(self, owner_id: int, seit: str) -> list[int]:
        return [r[0] for r in self._conn.execute(
            """SELECT DISTINCT m.decision_id FROM council_topic_matches m
               JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
               WHERE m.owner_id = ? AND m.matched_at >= ?""", (owner_id, seit))]

    def result_already_sent(self, ksinr: int, owner_id: int) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM council_results_sent WHERE ksinr = ? AND owner_id = ?",
            (ksinr, owner_id)).fetchone() is not None

    def mark_result_sent(self, ksinr: int, owner_id: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO council_results_sent (ksinr, owner_id, sent_at) VALUES (?,?,?)",
                (ksinr, owner_id, now))

    # ---- Anlass-Schalter (Design 30a/E) ----

    def get_notify_prefs(self, owner_id: int) -> dict:
        """Die gespeicherten Schalter eines Kontos. Leeres dict = alles auf
        Vorgabe; kern.notify.gewuenscht() legt die Vorgabewerte darüber."""
        import json as _json

        row = self._conn.execute(
            "SELECT notify_prefs FROM web_users WHERE id = ?", (owner_id,)).fetchone()
        if not row or not row[0]:
            return {}
        try:
            value = _json.loads(row[0])
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def set_notify_prefs(self, owner_id: int, prefs: dict) -> dict:
        """Schalter setzen. Gespeichert wird nur, was bekannt ist — so wächst
        die Spalte nicht mit Müll, wenn jemand am Client herumreicht."""
        import json as _json

        from kern.notify import NOTIFY_DEFAULTS

        sauber = {k: bool(v) for k, v in prefs.items() if k in NOTIFY_DEFAULTS}
        with self._conn:
            self._conn.execute("UPDATE web_users SET notify_prefs = ? WHERE id = ?",
                               (_json.dumps(sauber), owner_id))
        return sauber

    # ---- Benachrichtigungs-Warteschlange (Design 30a) ----

    def enqueue_notification(self, owner_id: int, kind: str, title: str, body_html: str,
                             url: str, created_at: str, deliver_after: str,
                             push_text: str | None = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO notification_queue "
                "(owner_id, kind, title, body_html, url, created_at, deliver_after, push_text) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (owner_id, kind, title, body_html, url, created_at, deliver_after, push_text),
            )
        return cur.lastrowid

    #: Nach so vielen erfolglosen Anläufen gilt eine Meldung als unzustellbar.
    #: Sie bleibt als Beleg in der Tabelle stehen (``sent_at`` bleibt NULL),
    #: wird aber nicht mehr ausgewählt — sonst würde eine tote Adresse jeden
    #: Lauf aufs Neue beschäftigen.
    MAX_ZUSTELLVERSUCHE = 3

    def owners_with_due_notifications(self, jetzt_iso: str) -> list[int]:
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT owner_id FROM notification_queue "
            "WHERE sent_at IS NULL AND attempts < ? AND deliver_after <= ? ORDER BY owner_id",
            (self.MAX_ZUSTELLVERSUCHE, jetzt_iso))]

    def due_notifications(self, owner_id: int, jetzt_iso: str) -> list[dict]:
        """Offene, fällige Posten — älteste zuerst, damit das Bündel am Ende die
        jüngsten trägt und die wichtigste Einzelmeldung vorne bleibt."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, kind, title, body_html, url, created_at, push_text FROM notification_queue "
            "WHERE owner_id = ? AND sent_at IS NULL AND attempts < ? AND deliver_after <= ? "
            "ORDER BY id",
            (owner_id, self.MAX_ZUSTELLVERSUCHE, jetzt_iso))]

    def bump_notification_attempts(self, ids: list[int]) -> None:
        """Einen erfolglosen Zustellversuch vermerken.

        ``sent_at`` bleibt bewusst NULL: Die Meldung ist nicht zugestellt, also
        soll sie beim nächsten Lauf wieder drankommen. Erst
        ``MAX_ZUSTELLVERSUCHE`` beendet die Wiederholung.
        """
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        with self._conn:
            self._conn.execute(
                f"UPDATE notification_queue SET attempts = attempts + 1 WHERE id IN ({ph})",
                tuple(ids),
            )

    def drop_pending_notifications(self, owner_id: int) -> int:
        """Alles Unzugestellte dieses Kontos verwerfen. Gibt die Anzahl zurück.

        Gedacht für den Moment, in dem jemand Benachrichtigungen abschaltet:
        Was noch wartet, war für ein Einverständnis gedacht, das gerade
        widerrufen wurde. Bliebe es liegen, käme es beim Wiedereinschalten als
        Nachlieferung aus der Zeit, in der ausdrücklich nichts gewollt war.

        Bereits Zugestelltes (``sent_at`` gesetzt) bleibt unangetastet — das ist
        die Historie, keine offene Post.
        """
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM notification_queue WHERE owner_id = ? AND sent_at IS NULL",
                (owner_id,))
        return cur.rowcount or 0

    def undeliverable_notifications(self, limit: int = 50) -> list[dict]:
        """Aufgegebene Meldungen — fürs Admin-Panel und die Fehlersuche."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, owner_id, kind, title, created_at, attempts FROM notification_queue "
            "WHERE sent_at IS NULL AND attempts >= ? ORDER BY id DESC LIMIT ?",
            (self.MAX_ZUSTELLVERSUCHE, limit))]

    def notifications_sent_on(self, owner_id: int, tag: str,
                              kinds: Iterable[str] | None = None, *,
                              ohne: bool = False) -> int:
        """Wie viele Zustellungen dieses Konto an diesem Kalendertag schon hatte.

        Ein Bündel zählt als EINE Zustellung, nicht als seine Einzelposten —
        sonst wäre die Grenze nach dem ersten Bündel sofort erschöpft.

        ``kinds`` zählt nur diese Anlässe, mit ``ohne=True`` alles außer ihnen.
        Damit haben die termingebundenen Anlässe ihr eigenes Tageskontingent
        (``kern.notify.TERMINGEBUNDEN``). Tragfähig ist der Filter nur, weil
        ``notify._zustellen_fuer`` je Sorte bündelt: Ein gemischtes Bündel wäre
        in beiden Kontingenten eine Zustellung.
        """
        filt, args = "", ()
        if kinds:
            kinds = sorted(kinds)
            ph = ",".join("?" * len(kinds))
            filt = f" AND kind {'NOT ' if ohne else ''}IN ({ph})"
            args = tuple(kinds)
        einzeln = self._conn.execute(
            "SELECT COUNT(*) FROM notification_queue "
            f"WHERE owner_id = ? AND bundled = 0 AND sent_at LIKE ?{filt}",
            (owner_id, f"{tag}%", *args)
        ).fetchone()[0]
        buendel = self._conn.execute(
            "SELECT COUNT(DISTINCT sent_at) FROM notification_queue "
            f"WHERE owner_id = ? AND bundled = 1 AND sent_at LIKE ?{filt}",
            (owner_id, f"{tag}%", *args)
        ).fetchone()[0]
        return einzeln + buendel

    def mark_notification_sent(self, ids: list[int], jetzt_iso: str, bundled: bool = False) -> None:
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        with self._conn:
            self._conn.execute(
                f"UPDATE notification_queue SET sent_at = ?, bundled = ? WHERE id IN ({ph})",
                (jetzt_iso, 1 if bundled else 0, *ids),
            )

    def get_owner_delivery(self, owner_id: int) -> dict | None:
        """Zustell-Ziele eines Kontos: Kanal, Adresse, Geräte — das, was
        kern.delivery braucht, ohne Themen oder Abos drumherum."""
        r = self._conn.execute(
            "SELECT id AS owner_id, delivery_channel, email, display_name "
            "FROM web_users WHERE id = ? AND status = 'active'", (owner_id,)).fetchone()
        if not r:
            return None
        owner = dict(r)
        by = {owner_id: owner}
        self._attach_push_tokens(by)
        return owner

    def get_web_user_by_email(self, email: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM web_users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None

    def get_web_user_by_id(self, user_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM web_users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_web_user_limits(self, user_id: int, deep_limit: int | None,
                            limits_frei: bool) -> None:
        """Admin-steuerbare Frage-Limits je Konto: Recherche-Tageslimit
        (None = Standard, 0 = unbegrenzt) + Rate-Limit-Befreiung."""
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET deep_limit = ?, limits_frei = ? WHERE id = ?",
                (deep_limit, 1 if limits_frei else 0, user_id))

    def list_web_users(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, email, role, status, email_verified, created_at "
            "FROM web_users ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_web_user_role(self, user_id: int, role: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE web_users SET role = ? WHERE id = ?", (role, user_id))

    def increment_token_version(self, user_id: int) -> int:
        """Bump token_version so all existing JWTs for this user become invalid."""
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET token_version = token_version + 1 WHERE id = ?", (user_id,)
            )
        row = self._conn.execute("SELECT token_version FROM web_users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else 0

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        with self._conn:
            self._conn.execute(
                # Wer ein Passwort setzt (auch per Reset-Link), hat danach eines —
                # relevant für Apple-only-Konten (password_set war dort 0).
                "UPDATE web_users SET password_hash = ?, password_set = 1 WHERE id = ?",
                (password_hash, user_id),
            )

    def create_password_reset(self, user_id: int, token_hash: str, expires_at: str) -> None:
        """Store a single-use password-reset token (only its sha256 hash). Drops the
        user's prior unused tokens so requesting a new link invalidates old ones."""
        with self._conn:
            self._conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
            self._conn.execute(
                "INSERT INTO password_reset_tokens(token_hash, user_id, expires_at, used) VALUES (?,?,?,0)",
                (token_hash, user_id, expires_at),
            )

    def consume_password_reset(self, token_hash: str, now: str) -> int | None:
        """Validate + burn a reset token: returns the user_id if it exists, is unused and
        not expired (then marks it used); otherwise None."""
        row = self._conn.execute(
            "SELECT user_id, expires_at, used FROM password_reset_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if not row or row["used"] or row["expires_at"] <= now:
            return None
        with self._conn:
            self._conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE token_hash = ?", (token_hash,))
        return int(row["user_id"])

    def set_email_verified(self, user_id: int, verified: bool = True) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE web_users SET email_verified = ? WHERE id = ?",
                (1 if verified else 0, user_id),
            )

    def create_email_verification(self, user_id: int, token_hash: str, expires_at: str) -> None:
        """Store a single-use email-verification token (only its sha256 hash). Drops the
        user's prior unused tokens so requesting a new link invalidates old ones."""
        with self._conn:
            self._conn.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
            self._conn.execute(
                "INSERT INTO email_verification_tokens(token_hash, user_id, expires_at, used) VALUES (?,?,?,0)",
                (token_hash, user_id, expires_at),
            )

    def consume_email_verification(self, token_hash: str, now: str) -> int | None:
        """Validate + burn a verification token: returns the user_id if it exists, is
        unused and not expired (then marks it used); otherwise None."""
        row = self._conn.execute(
            "SELECT user_id, expires_at, used FROM email_verification_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if not row or row["used"] or row["expires_at"] <= now:
            return None
        with self._conn:
            self._conn.execute(
                "UPDATE email_verification_tokens SET used = 1 WHERE token_hash = ?", (token_hash,)
            )
        return int(row["user_id"])

    def delete_web_user(self, user_id: int) -> None:
        """Hard-delete a web account and everything keyed to it (GDPR: right to erasure).

        Räumt jede Tabelle aus ``USER_OWNED_TABLES`` ab — die Liste wird von
        einem Test gegen das Schema geprüft, damit hier nichts liegen bleibt,
        wenn später eine nutzerbezogene Tabelle dazukommt.
        """
        with self._conn:
            for table, column in USER_OWNED_TABLES:
                self._conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (user_id,))
            self._conn.execute("DELETE FROM web_users WHERE id = ?", (user_id,))

    # ---- „Meine Gespräche" (5a/I-04 + Design 6a) ---------------------------

    def get_qa_speichern(self, user_id: int) -> int | None:
        """Einwilligung: None = nie gefragt, 1 = speichern, 0 = bewusst aus."""
        row = self._conn.execute(
            "SELECT qa_speichern FROM web_users WHERE id = ?", (user_id,)).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def set_qa_speichern(self, user_id: int, an: bool) -> None:
        """Schalter umlegen. Löscht bewusst NICHTS — was mit bestehenden
        Gesprächen passiert, entscheidet der Ausschalt-Dialog getrennt."""
        with self._conn:
            self._conn.execute("UPDATE web_users SET qa_speichern = ? WHERE id = ?",
                               (1 if an else 0, user_id))

    def qa_share_anlegen(self, user_id: int, question: str, answer: str,
                         quellen: list[dict] | None,
                         extras: dict | None = None) -> str:
        """Snapshot einer geteilten Antwort (Task 31) → öffentliches Token.
        Bewusste Einzel-Veröffentlichung — unabhängig vom Gespräche-Opt-in.
        `extras` hält die Bausteine neben den Beschlüssen (Debatten, Presse,
        Anlagen, Parteien-Positionen), damit die geteilte Seite dieselbe
        Antwort zeigt wie das Gespräch — und nicht nur deren Textkern."""
        import secrets

        token = secrets.token_urlsafe(16)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO qa_shares (token, user_id, question, answer, sources, created, extras) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (token, user_id, question[:300], answer[:8000],
                 json.dumps(quellen or [], ensure_ascii=False), now,
                 json.dumps(extras, ensure_ascii=False) if extras else None))
        return token

    def qa_share_get(self, token: str) -> dict | None:
        """Öffentliche Sicht eines Snapshots — OHNE user_id."""
        row = self._conn.execute(
            "SELECT question, answer, sources, created, extras FROM qa_shares WHERE token = ?",
            (token,)).fetchone()
        if not row:
            return None
        try:
            quellen = json.loads(row["sources"] or "[]")
        except (ValueError, TypeError):
            quellen = []
        # Vor dem Bausteine-Nachtrag geteilte Antworten haben keine extras —
        # die Seite zeigt sie dann wie bisher nur mit den Beschlüssen.
        try:
            extras = json.loads(row["extras"] or "{}")
        except (ValueError, TypeError):
            extras = {}
        return {"question": row["question"], "answer": row["answer"],
                "sources": quellen, "created": row["created"],
                "debatten": extras.get("debatten") or [],
                "presse": extras.get("presse") or [],
                "anlagen": extras.get("anlagen") or [],
                "parteien": extras.get("parteien") or [],
                # Die Grafik zur Antwort — vor diesem Nachtrag geteilte
                # Antworten haben keine; die Seite zeigt dann keine.
                "grafik": extras.get("grafik")}

    def qa_share_owner_id(self, token: str) -> int | None:
        """Interne Zuordnung für Moderation; nie Teil der öffentlichen API."""
        row = self._conn.execute(
            "SELECT user_id FROM qa_shares WHERE token = ?", (token,)
        ).fetchone()
        return int(row[0]) if row else None

    def qa_share_delete(self, token: str) -> bool:
        """Einen gemeldeten öffentlichen Snapshot sofort unzugänglich machen."""
        with self._conn:
            cur = self._conn.execute("DELETE FROM qa_shares WHERE token = ?", (token,))
        return (cur.rowcount or 0) > 0

    # ---- „Gründliche Recherche" (RG-10, Task 34) ---------------------------

    def deep_job_anlegen(self, user_id: int, question: str) -> str:
        """Neuen Recherche-Job registrieren → unerratbare Job-ID."""
        import secrets

        job_id = secrets.token_urlsafe(12)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO deep_research_jobs (id, user_id, question, status, created, updated) "
                "VALUES (?, ?, ?, 'laeuft', ?, ?)", (job_id, user_id, question[:300], now, now))
        return job_id

    def deep_job_update(self, job_id: str, status: str, bericht: str | None = None,
                        quellen_json: str | None = None) -> None:
        """Endzustand (oder Statuswechsel) des Jobs persistieren."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE deep_research_jobs SET status = ?, "
                "report = COALESCE(?, report), sources = COALESCE(?, sources), "
                "updated = ? WHERE id = ?", (status, bericht, quellen_json, now, job_id))

    def deep_job_get(self, job_id: str, user_id: int) -> dict | None:
        """Job-Zeile — nur für den Eigentümer."""
        row = self._conn.execute(
            "SELECT id, question, status, report, sources, seen, created, updated "
            "FROM deep_research_jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id)).fetchone()
        return dict(row) if row else None

    def deep_job_aktuell(self, user_id: int) -> dict | None:
        """Der jüngste Job des Kontos — damit der Client nach Navigation oder
        App-Neustart einen laufenden Job (oder frisch fertigen Bericht)
        wiederfindet, ohne sich die ID gemerkt haben zu müssen."""
        row = self._conn.execute(
            "SELECT id, question, status, seen, created, updated "
            "FROM deep_research_jobs WHERE user_id = ? ORDER BY created DESC, id LIMIT 1",
            (user_id,)).fetchone()
        return dict(row) if row else None

    def deep_jobs_heute(self, user_id: int) -> int:
        """Kontingent-Zählung: heutige Jobs, die zählen (laeuft + fertig).
        Gestoppte, abgebrochene und fehlgeschlagene kosten nichts (RG-10).

        „Heute" ist der Tag in OLDENBURG, nicht in UTC. Vorher verglich die
        Abfrage `date(created) = date('now')` — beides UTC —, das Kontingent
        sprang also im Sommer erst um 2 Uhr nachts um. Die Oberfläche sagt
        „ab Mitternacht wieder"; damit das stimmt, beginnt der Tag hier an
        der lokalen Mitternacht (als UTC-Zeitstempel gerechnet, denn genau so
        liegt `created` in der Tabelle).
        """
        row = self._conn.execute(
            "SELECT COUNT(*) FROM deep_research_jobs WHERE user_id = ? "
            "AND status IN ('laeuft', 'fertig') AND created >= ?",
            (user_id, _tagesbeginn_utc())).fetchone()
        return int(row[0])

    def deep_job_gesehen(self, job_id: str, user_id: int) -> None:
        """Bericht wurde gerendert — nicht erneut ungefragt einblenden."""
        with self._conn:
            self._conn.execute(
                "UPDATE deep_research_jobs SET seen = 1 WHERE id = ? AND user_id = ?",
                (job_id, user_id))

    def deep_jobs_verwaiste_beenden(self) -> int:
        """Beim Backend-Start: Jobs, die laut DB noch laufen, deren Thread aber
        mit dem alten Prozess gestorben ist, ehrlich als Fehler markieren —
        der Client bietet dann „Fortsetzen" an (kostet kein Kontingent)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "UPDATE deep_research_jobs SET status = 'fehler', updated = ? "
                "WHERE status = 'laeuft'", (now,))
            return cur.rowcount

    def qa_gespraech_start(self, user_id: int, title: str) -> int | None:
        """None, wenn es das Konto (nicht mehr) gibt — schließt das Fenster,
        in dem eine Konto-Löschung zwischen Einwilligungs-Check und Insert
        verwaiste Gesprächsdaten hinterließe (Review-Befund B3)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            if not self._conn.execute("SELECT 1 FROM web_users WHERE id = ?", (user_id,)).fetchone():
                return None
            cur = self._conn.execute(
                "INSERT INTO qa_gespraeche (user_id, title, created, updated) VALUES (?, ?, ?, ?)",
                (user_id, (title or "Gespräch").strip()[:120], now, now))
            return int(cur.lastrowid)

    def qa_turn_speichern(self, gespraech_id: int, user_id: int, question: str,
                          answer: str, quellen_json: str | None) -> bool:
        """Turn anhängen — nur ins eigene Gespräch (user_id doppelt geprüft)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            ok = self._conn.execute(
                "SELECT 1 FROM qa_gespraeche WHERE id = ? AND user_id = ?",
                (gespraech_id, user_id)).fetchone()
            if not ok:
                return False
            self._conn.execute(
                "INSERT INTO qa_gespraech_turns (conversation_id, user_id, question, answer, sources, created) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (gespraech_id, user_id, question[:600], answer[:8000], quellen_json, now))
            self._conn.execute("UPDATE qa_gespraeche SET updated = ? WHERE id = ?",
                               (now, gespraech_id))
            return True

    @staticmethod
    def _titel_muster(suche: str | None) -> str | None:
        """LIKE-Muster für die Titel-Suche — oder None, wenn nicht gesucht wird.
        `%` und `_` im Suchwort sind Text, keine Platzhalter (ESCAPE-Zeichen
        ist der Backslash, s. Aufrufer)."""
        begriff = (suche or "").strip().lower()
        if not begriff:
            return None
        for zeichen in ("\\", "%", "_"):
            begriff = begriff.replace(zeichen, "\\" + zeichen)
        return f"%{begriff}%"

    def qa_gespraeche(self, user_id: int, limit: int = 30, offset: int = 0,
                      suche: str | None = None) -> list[dict]:
        """Eine Seite der Gesprächsliste, neueste zuerst.

        Bis 08/2026 lieferte diese Abfrage hart die letzten 50 Zeilen — wer
        mehr Gespräche hatte, kam an die älteren gar nicht mehr heran (Tims
        Befund 30.08.). Jetzt blättert der Aufrufer; die Gesamtzahl steht in
        `qa_gespraeche_anzahl`, damit die Anzeige nicht die Seitenlänge zählt.

        Sortiert wird nach `updated` UND `id`: `updated` hat nur
        Sekundenauflösung, zwei Gespräche derselben Sekunde stünden sonst in
        beliebiger Reihenfolge — beim Blättern über OFFSET erschiene eines
        doppelt und eines gar nicht.
        """
        muster = self._titel_muster(suche)
        filt = " AND unicode_lower(g.title) LIKE ? ESCAPE '\\'" if muster else ""
        werte: list = [user_id] + ([muster] if muster else []) + [max(0, limit), max(0, offset)]
        rows = self._conn.execute(
            f"""SELECT g.id, g.title, g.updated,
                      (SELECT COUNT(*) FROM qa_gespraech_turns t WHERE t.conversation_id = g.id) AS n_turns
               FROM qa_gespraeche g WHERE g.user_id = ?{filt}
               ORDER BY g.updated DESC, g.id DESC LIMIT ? OFFSET ?""", werte).fetchall()
        return [dict(r) for r in rows]

    def qa_gespraeche_anzahl(self, user_id: int, suche: str | None = None) -> int:
        """Wie viele Gespräche das Konto hat (optional: passend zur Suche)."""
        muster = self._titel_muster(suche)
        filt = " AND unicode_lower(title) LIKE ? ESCAPE '\\'" if muster else ""
        werte: list = [user_id] + ([muster] if muster else [])
        return self._conn.execute(
            f"SELECT COUNT(*) FROM qa_gespraeche WHERE user_id = ?{filt}",
            werte).fetchone()[0]

    def qa_gespraech(self, gespraech_id: int, user_id: int) -> dict | None:
        g = self._conn.execute(
            "SELECT id, title, updated FROM qa_gespraeche WHERE id = ? AND user_id = ?",
            (gespraech_id, user_id)).fetchone()
        if not g:
            return None
        turns = self._conn.execute(
            "SELECT question, answer, sources FROM qa_gespraech_turns "
            "WHERE conversation_id = ? ORDER BY id",
            (gespraech_id,)).fetchall()
        return {**dict(g), "turns": [dict(t) for t in turns]}

    def qa_gespraech_umbenennen(self, gespraech_id: int, user_id: int, title: str) -> bool:
        """Titel ändern — nur am eigenen Gespräch (Design 9a②: Wisch links →
        Umbenennen). ``updated`` bleibt unberührt: Umbenennen ist Pflege, kein
        Gesprächsfortschritt, und soll die Liste nicht umsortieren."""
        title = " ".join((title or "").split())[:120]
        if not title:
            return False
        with self._conn:
            cur = self._conn.execute(
                "UPDATE qa_gespraeche SET title = ? WHERE id = ? AND user_id = ?",
                (title, gespraech_id, user_id))
            return (cur.rowcount or 0) > 0

    def qa_gespraech_loeschen(self, gespraech_id: int, user_id: int) -> bool:
        with self._conn:
            self._conn.execute(
                "DELETE FROM qa_gespraech_turns WHERE conversation_id = ? AND user_id = ?",
                (gespraech_id, user_id))
            cur = self._conn.execute(
                "DELETE FROM qa_gespraeche WHERE id = ? AND user_id = ?",
                (gespraech_id, user_id))
            return (cur.rowcount or 0) > 0

    def qa_gespraeche_loeschen(self, user_id: int) -> int:
        """Alle Gespräche eines Kontos löschen (Ausschalt-Dialog „Alle löschen")."""
        with self._conn:
            self._conn.execute("DELETE FROM qa_gespraech_turns WHERE user_id = ?", (user_id,))
            cur = self._conn.execute("DELETE FROM qa_gespraeche WHERE user_id = ?", (user_id,))
            return cur.rowcount or 0

    # ---- Feedback ----------------------------------------------------------

    def add_feedback(self, owner_id: int, email: str | None, kind: str, message: str) -> int:
        """Nutzer-Feedback ablegen. Gibt die id zurück."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO feedback (owner_id, email, kind, message, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (owner_id, email, kind, message, now),
            )
        return int(cur.lastrowid or 0)

    def list_feedback(self, limit: int = 100, only_unread: bool = False) -> list[dict]:
        """Neueste zuerst — so steht Unerledigtes oben."""
        where = "WHERE read_at IS NULL" if only_unread else ""
        rows = self._conn.execute(
            f"SELECT id, owner_id, email, kind, message, created_at, read_at"
            f" FROM feedback {where} ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_unread_feedback(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM feedback WHERE read_at IS NULL").fetchone()
        return int(row[0]) if row else 0

    def set_feedback_read(self, feedback_id: int, read: bool) -> bool:
        """Als erledigt markieren (oder zurücksetzen). False = es gab die id nicht."""
        now = datetime.utcnow().isoformat(timespec="seconds") if read else None
        with self._conn:
            cur = self._conn.execute(
                "UPDATE feedback SET read_at = ? WHERE id = ?", (now, feedback_id))
        return cur.rowcount > 0

    def get_topic_for_owner(self, owner_id: int, topic_id: int) -> TopicRow | None:
        """Fetch a single topic belonging to owner_id — O(1) vs scanning all topics."""
        row = self._conn.execute(
            "SELECT id, owner_id, chat_id, name, description, created_at FROM topics WHERE id = ? AND owner_id = ?",
            (topic_id, owner_id),
        ).fetchone()
        return TopicRow(**dict(row)) if row else None

    # ---- Cron-Läufe ----
    def record_job_run(
        self, job: str, started_at: str, finished_at: str, status: str,
        duration_s: float, stats: dict | None = None, error: str | None = None,
    ) -> None:
        """Einen Cron-Lauf protokollieren (aus run_guarded). Best-effort: ein
        Schreibfehler darf den Job selbst nie zum Scheitern bringen."""
        import json
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO job_runs (job, started_at, finished_at, status, duration_s, stats, error)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (job, started_at, finished_at, status, duration_s,
                     json.dumps(stats, ensure_ascii=False) if stats else None, error),
                )
        except Exception:  # noqa: BLE001 — Protokollierung ist Beiwerk
            pass

    def job_runs(self, job: str | None = None, limit: int = 200) -> list[dict]:
        """Cron-Läufe, neueste zuerst; `stats` bereits als dict."""
        import json
        sql = "SELECT * FROM job_runs"
        params: tuple = ()
        if job:
            sql += " WHERE job = ?"
            params = (job,)
        # id als zweites Kriterium: started_at hat Sekunden-Auflösung, zwei
        # Läufe in derselben Sekunde sortierten sonst beliebig.
        sql += " ORDER BY started_at DESC, id DESC LIMIT ?"
        rows = self._conn.execute(sql, (*params, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["stats"] = json.loads(d["stats"]) if d["stats"] else None
            except (ValueError, TypeError):
                d["stats"] = None
            out.append(d)
        return out

    # ---- Aktivitäts-Tracking + Wachstum (Admin 20a) ----
    def record_activity(self, owner_id: int, feature: str = "session") -> None:
        """Ein Feature-Nutzungsereignis je Konto/Tag zählen (best-effort, nie
        load-bearing). ‚session‘ wird bei jedem eingeloggten Request gesetzt
        (throttled durch den Tages-PK)."""
        from datetime import date
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO user_activity (owner_id, day, feature, count) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(owner_id, day, feature) DO UPDATE SET count = count + 1",
                    (owner_id, date.today().isoformat(), feature),
                )
        except Exception:  # noqa: BLE001 — Aktivitäts-Log darf nie einen Request brechen
            pass

    def wau_series(self, weeks: int = 8) -> list[dict]:
        """Aktive Konten je Woche (DISTINCT owner_id), älteste zuerst — 20a-WAU.
        Je Woche ``{"day": Enddatum, "n": Konten}``; das Datum beschriftet die
        x-Achse im Frontend (Serverdatum, damit die Achse nicht clientseitig
        geraten wird)."""
        from datetime import date, timedelta
        today = date.today()
        out: list[dict] = []
        for w in range(weeks):
            end = today - timedelta(days=(weeks - 1 - w) * 7)
            start = end - timedelta(days=6)
            n = self._conn.execute(
                "SELECT COUNT(DISTINCT owner_id) FROM user_activity WHERE day BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat())).fetchone()[0]
            out.append({"day": end.isoformat(), "n": n})
        return out

    def admin_growth(self, days: int | None = 90) -> dict:
        """Wachstums-Daten für den Statistik-Tab (20a): kumulierte Verläufe für
        registrierte Konten und angelegte Themen + Δ im Zeitraum + WAU. Jede
        Serie führt ihre Datumsachse (``days``) mit — bei „Alles“ ist die Spanne
        je Serie unterschiedlich lang."""
        from datetime import date, timedelta

        def dates_of(table: str) -> list[str]:
            return [r[0][:10] for r in self._conn.execute(
                f"SELECT created_at FROM {table} WHERE created_at IS NOT NULL ORDER BY created_at").fetchall()]

        def series(ds: list[str]) -> tuple[list[int], int, list[str]]:
            today = date.today()
            span = days
            if span is None:
                first = date.fromisoformat(ds[0]) if ds else today
                span = max((today - first).days + 1, 1)
            span = max(1, min(span, 366))  # Sparkline-Punkte deckeln
            axis = [(today - timedelta(days=span - 1 - i)).isoformat() for i in range(span)]
            out = [sum(1 for x in ds if x <= day) for day in axis]
            delta = sum(1 for x in ds if x >= axis[0])
            return out, delta, axis

        u = dates_of("web_users")
        t = dates_of("topics")
        u_series, u_delta, u_days = series(u)
        t_series, t_delta, t_days = series(t)
        wau = self.wau_series(8)
        return {
            "users": {"total": len(u), "series": u_series, "delta": u_delta, "days": u_days},
            "topics": {"total": len(t), "series": t_series, "delta": t_delta, "days": t_days},
            "wau": [w["n"] for w in wau],
            "wau_days": [w["day"] for w in wau],
        }

    def admin_user_rows(self) -> list[dict]:
        """Nutzer-Liste mit Aktivitätssignalen (Design 20a): je Konto Themen-,
        Abo-, Quiz- und KI-Frage-Zahl + letzter Aktivitätstag. Alles in
        ratslotse.sqlite, ein Query."""
        rows = self._conn.execute(
            """SELECT u.id, u.email, u.role, u.status, u.created_at, u.apple_sub,
                      (SELECT COUNT(*) FROM topics t WHERE t.owner_id = u.id) n_topics,
                      (SELECT COUNT(*) FROM committee_subscriptions s WHERE s.owner_id = u.id) n_abos,
                      (SELECT COUNT(DISTINCT question_id) FROM quiz_answers q WHERE q.owner_id = u.id) n_quiz,
                      (SELECT COALESCE(SUM(count), 0) FROM user_activity a
                         WHERE a.owner_id = u.id AND a.feature = 'ki_frage') n_ki,
                      (SELECT MAX(day) FROM user_activity a WHERE a.owner_id = u.id) last_seen
               FROM web_users u ORDER BY u.created_at DESC"""
        ).fetchall()
        return [{"id": r["id"], "email": r["email"], "role": r["role"], "status": r["status"],
                 "created_at": r["created_at"], "apple_linked": bool(r["apple_sub"]),
                 "n_topics": r["n_topics"], "n_abos": r["n_abos"], "n_quiz": r["n_quiz"],
                 "n_ki": r["n_ki"], "last_seen": r["last_seen"]} for r in rows]

    def admin_user_detail(self, uid: int) -> dict | None:
        """Nutzer-Detail (Design 20a): Feature-Nutzung, Angelegtes, 30-Tage-
        Aktivitätsverlauf. Nur eigene App-Aktivität, kein Dritt-Tracking."""
        from datetime import date, timedelta
        u = self.get_web_user_by_id(uid)
        if not u:
            return None
        feats = {r["feature"]: r["c"] for r in self._conn.execute(
            "SELECT feature, SUM(count) c FROM user_activity WHERE owner_id = ? GROUP BY feature", (uid,))}
        n_quiz = self._conn.execute(
            "SELECT COUNT(DISTINCT question_id) FROM quiz_answers WHERE owner_id = ?", (uid,)).fetchone()[0]
        topics = [r["name"] for r in self._conn.execute(
            "SELECT name FROM topics WHERE owner_id = ? ORDER BY created_at DESC", (uid,)).fetchall()]
        abos = [r["committee_name"] for r in self._conn.execute(
            "SELECT committee_name FROM committee_subscriptions WHERE owner_id = ?", (uid,)).fetchall()]
        since = (date.today() - timedelta(days=29)).isoformat()
        by_day = {r["day"]: r["c"] for r in self._conn.execute(
            "SELECT day, SUM(count) c FROM user_activity WHERE owner_id = ? AND day >= ? GROUP BY day",
            (uid, since)).fetchall()}
        verlauf_days = [(date.today() - timedelta(days=29 - i)).isoformat() for i in range(30)]
        verlauf = [by_day.get(d, 0) for d in verlauf_days]
        return {
            "id": u["id"], "email": u["email"], "role": u["role"], "status": u["status"],
            "created_at": u["created_at"],
            "last_seen": self._conn.execute(
                "SELECT MAX(day) FROM user_activity WHERE owner_id = ?", (uid,)).fetchone()[0],
            "apple_linked": bool(u.get("apple_sub")), "has_password": bool(u.get("password_set", 1)),
            "delivery_channel": u.get("delivery_channel", "email"),
            # Einwilligung „Gespräche speichern": None = nie gefragt, 1 = an, 0 = aus.
            "qa_speichern": u.get("qa_speichern"),
            # Admin-steuerbare Frage-Limits (10.08.26) — fürs Formular im Detail.
            "deep_limit": u.get("deep_limit"), "limits_frei": bool(u.get("limits_frei")),
            "features": {"ki_frage": feats.get("ki_frage", 0), "suche": feats.get("suche", 0),
                         "quiz": n_quiz, "analyse": feats.get("analyse", 0), "karte": feats.get("karte", 0)},
            "topics": topics, "abos": abos, "verlauf": verlauf, "verlauf_days": verlauf_days,
        }

    # ---- topics ----

    def get_topics(self, owner_id: int) -> list[TopicRow]:
        rows = self._conn.execute(
            "SELECT id, owner_id, chat_id, name, description, created_at FROM topics WHERE owner_id = ? ORDER BY id",
            (owner_id,),
        ).fetchall()
        return [TopicRow(**dict(r)) for r in rows]

    def save_topic_decision_matches(self, topic_id: int, owner_id: int, matches: list[tuple],
                                    *, gedeckelt: bool = False, kandidaten: int = 0,
                                    als_neu: bool = True) -> int:
        """Replace a topic's matched council decisions. ``matches`` = [(decision_id, score)].

        Was ein Treffer ist, entscheidet ``council.topic_intel.treffer`` — die
        eine Definition, an der auch das Bearbeiten-Blatt im Web rechnet. Hier
        wird sie nur noch abgelegt.

        **Bestehende Treffer behalten ihr ``matched_at``.** Nur die Zeilen, die
        es vorher nicht gab, tragen den Zeitpunkt dieses Laufs; weggefallene
        verschwinden. Vorher warf der Lauf erst alles weg und legte es neu an —
        damit trug nach jedem wöchentlichen Matching (sonntags 3 Uhr) JEDER
        Treffer das Datum von heute, und der Wochenüberblick am selben Abend
        meldete den kompletten Bestand als Neuigkeit der Woche („Diese Woche:
        119 Beschlüsse zu deinen Themen", Tims Befund 17.08.2026 — am Bestand
        gemessen trugen alle 919 Zeilen dasselbe Datum).

        ``als_neu=False`` ist für Reparaturläufe (``--ohne-meldungen``): Nach
        einer Neu-Extraktion tragen dieselben Beschlüsse neue IDs, also sind
        formal ALLE Treffer neu. Die frischen Zeilen bekommen dann ein leeres
        ``matched_at`` (der Vorgabewert der Spalte) und gelten damit nirgends
        als Neuigkeit.

        ``gedeckelt`` sagt, ob der Lauf mehr relevante Beschlüsse gefunden als
        gespeichert hat, ``kandidaten``, wie viele er geprüft hat. Beides
        wandert nach ``council_topic_match_meta`` — die Oberfläche kann eine
        gedeckelte Liste dann als „40+" ausweisen, statt den Deckel als
        Ergebnis auszugeben. Dieses „+" gehört an JEDE Stelle, die die Zahl
        zeigt: Karte, Trefferliste, Bearbeiten-Blatt.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        stempel = now if als_neu else ""
        neu = {int(did): float(sc) for did, sc in matches}
        with self._conn:
            if neu:
                ph = ",".join("?" * len(neu))
                self._conn.execute(
                    f"DELETE FROM council_topic_matches WHERE topic_id = ? "
                    f"AND decision_id NOT IN ({ph})", (topic_id, *neu))
            else:
                self._conn.execute("DELETE FROM council_topic_matches WHERE topic_id = ?",
                                   (topic_id,))
            # DO UPDATE fasst matched_at bewusst nicht an — das ist der Kern
            # der Sache: „seit wann gehört dieser Beschluss zu diesem Thema".
            self._conn.executemany(
                "INSERT INTO council_topic_matches(topic_id, owner_id, decision_id, score, matched_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(topic_id, decision_id) DO UPDATE SET "
                "owner_id = excluded.owner_id, score = excluded.score",
                [(topic_id, owner_id, did, sc, stempel) for did, sc in neu.items()],
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO council_topic_match_meta "
                "(topic_id, owner_id, gedeckelt, kandidaten, matched_at) VALUES (?,?,?,?,?)",
                (topic_id, owner_id, 1 if gedeckelt else 0, int(kandidaten), now),
            )
        return len(matches)

    def topic_match_caps(self, owner_id: int) -> dict[int, bool]:
        """{topic_id: True, wenn die gespeicherte Trefferliste gedeckelt ist}."""
        return {r["topic_id"]: bool(r["gedeckelt"]) for r in self._conn.execute(
            "SELECT topic_id, gedeckelt FROM council_topic_match_meta WHERE owner_id = ?",
            (owner_id,))}

    def topics_mit_gelesen_stand(self) -> set[int]:
        """Themen, deren Trefferliste schon mal jemand angesehen hat.

        Braucht der Reparaturlauf (``--ohne-meldungen``): Nach einer
        Neu-Extraktion tragen dieselben Beschlüsse neue IDs, der Gelesen-Stand
        hängt aber an der alten ID. Ohne diese Unterscheidung stünde nach jedem
        technischen Lauf bei JEDEM Thema wieder „n neu" — eine Neuigkeit, die
        keine ist (Tims Befund 15.08.2026: „warum sind hier überall 25 neu?").
        """
        return {r[0] for r in self._conn.execute(
            "SELECT DISTINCT topic_id FROM topic_hits_seen")}

    def get_topic_decision_matches(self, topic_id: int) -> list[dict]:
        """Matched council decisions for a topic — {decision_id, score}, best first."""
        return [dict(r) for r in self._conn.execute(
            "SELECT decision_id, score FROM council_topic_matches WHERE topic_id = ? ORDER BY score DESC",
            (topic_id,))]

    def unseen_hit_counts(self, owner_id: int) -> dict[int, int]:
        """RL-903: {topic_id: Anzahl noch nicht gesehener Beschluss-Treffer}
        für alle Themen des Kontos — speist Sidebar-Zähler und „n neu"-Badges."""
        # JOIN topics ist Absicht, nicht Zierde: Ohne ihn zählen Treffer eines
        # gelöschten Themas mit, und weil der Zähler in der Seitenleiste über
        # ALLE Themen summiert, stünde dort eine Zahl, die durch nichts mehr
        # kleiner wird — das Thema taucht ja in keiner Liste mehr auf.
        # agenda_matches_for_owner macht es seit jeher richtig.
        rows = self._conn.execute(
            """SELECT m.topic_id, COUNT(*) AS n
               FROM council_topic_matches m
               JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
               LEFT JOIN topic_hits_seen s
                 ON s.owner_id = m.owner_id AND s.topic_id = m.topic_id
                    AND s.decision_id = m.decision_id
               WHERE m.owner_id = ? AND s.decision_id IS NULL
               GROUP BY m.topic_id""",
            (owner_id,),
        ).fetchall()
        return {r["topic_id"]: r["n"] for r in rows}

    def unseen_hit_ids(self, owner_id: int) -> dict[int, set[int]]:
        """{topic_id: {decision_id, …}} der noch nicht gesehenen Treffer.

        Dieselbe Menge, die ``unseen_hit_counts`` zählt — nur eben aufgelöst.
        Die Themen-Karte zeigt seit dem Umbau vom 28.08.2026 ihre jüngsten
        Treffer einzeln und setzt vor die neuen einen Punkt; dafür reicht eine
        Zahl nicht mehr. Bewusst dieselbe Abfrage inklusive ``JOIN topics``:
        Ohne ihn zählten Treffer eines gelöschten Themas mit, und die beiden
        Ansichten (Abzeichen „2 neue" und die Punkte davor) gingen auseinander.
        """
        rows = self._conn.execute(
            """SELECT m.topic_id, m.decision_id
               FROM council_topic_matches m
               JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
               LEFT JOIN topic_hits_seen s
                 ON s.owner_id = m.owner_id AND s.topic_id = m.topic_id
                    AND s.decision_id = m.decision_id
               WHERE m.owner_id = ? AND s.decision_id IS NULL""",
            (owner_id,),
        ).fetchall()
        out: dict[int, set[int]] = {}
        for r in rows:
            out.setdefault(r["topic_id"], set()).add(r["decision_id"])
        return out

    def neue_treffer_seit_uebersicht(self, owner_id: int) -> int:
        """Zahl der Treffer, die seit dem letzten Besuch der Themen-Übersicht
        dazugekommen sind — der Zähler an „Meine Themen" (Seitenleiste und
        Punkt in der Tab-Leiste).

        Bewusst NICHT dieselbe Zahl wie ``unseen_hit_counts``: Die Bubble ist
        eine Ankündigung („da ist was Neues"), kein Aufgaben-Zähler. Sie
        verstummt, sobald man einmal nachgesehen hat (Tims Wunsch 18.08.);
        WELCHES Thema neue Treffer hat, sagt weiterhin das „n neu" auf der
        Übersicht — das hängt am Öffnen des Themas und bleibt unberührt.

        Ein leeres ``matched_at`` ist der Vorgabewert der Spalte und heißt
        „schon lange bekannt" (s. ``_reparatur_matched_at``); nach dem ersten
        Besuch zählen solche Zeilen deshalb nicht mehr mit.
        """
        as_of = self._conn.execute(
            "SELECT topics_seen_at FROM web_users WHERE id = ?", (owner_id,)).fetchone()
        seit = as_of["topics_seen_at"] if as_of else None
        sql = """SELECT COUNT(*) FROM council_topic_matches m
                 JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
                 LEFT JOIN topic_hits_seen s
                   ON s.owner_id = m.owner_id AND s.topic_id = m.topic_id
                      AND s.decision_id = m.decision_id
                 WHERE m.owner_id = ? AND s.decision_id IS NULL"""
        params: list = [owner_id]
        if seit:
            sql += " AND m.matched_at > ?"
            params.append(seit)
        return self._conn.execute(sql, params).fetchone()[0]

    def topics_uebersicht_gesehen(self, owner_id: int) -> None:
        """Merkt sich, dass die Themen-Übersicht gerade offen war — ab hier
        zählt für die Bubble nur noch, was danach dazukommt."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("UPDATE web_users SET topics_seen_at = ? WHERE id = ?",
                               (now, owner_id))

    def mark_topic_hits_seen(self, owner_id: int, topic_id: int) -> int:
        """Alle aktuellen Treffer eines Themas als gesehen markieren (RL-903).
        Idempotent (INSERT OR IGNORE); Rückgabe = neu markierte Zeilen."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO topic_hits_seen (owner_id, topic_id, decision_id, seen_at)
                   SELECT ?, m.topic_id, m.decision_id, ?
                   FROM council_topic_matches m
                   WHERE m.topic_id = ? AND m.owner_id = ?""",
                (owner_id, now, topic_id, owner_id),
            )
        return cur.rowcount

    def mark_topic_hit_seen(self, owner_id: int, topic_id: int, decision_id: int) -> bool:
        """EINEN Treffer als gesehen markieren — Rückgabe: war er es noch nicht?

        Seit dem 28.08.2026 stehen die Treffer direkt auf der Karte, man klickt
        also einzelne an. Aus „2 neue" soll dann „1 neuer" werden, nicht
        „gelesen" für alles (Tims Wunsch). Idempotent wie
        ``mark_topic_hits_seen`` — nur eben punktuell.

        Das ``SELECT`` aus ``council_topic_matches`` ist die Zugangsprüfung:
        Nur was wirklich ein Treffer DIESES Themas DIESER Nutzer:in ist, darf
        eine Zeile bekommen. Ohne den Umweg ließe sich die Tabelle über einen
        direkten API-Aufruf mit beliebigen decision_ids füllen.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO topic_hits_seen (owner_id, topic_id, decision_id, seen_at)
                   SELECT ?, m.topic_id, m.decision_id, ?
                   FROM council_topic_matches m
                   WHERE m.topic_id = ? AND m.owner_id = ? AND m.decision_id = ?""",
                (owner_id, now, topic_id, owner_id, decision_id),
            )
        return cur.rowcount > 0

    def agenda_classified_hash(self, owner_id: int, ksinr: int) -> str | None:
        """Hash des zuletzt für diese Nutzer*in klassifizierten
        Tagesordnungs-Stands — None, wenn noch nie klassifiziert (RL-902)."""
        row = self._conn.execute(
            "SELECT agenda_hash FROM council_agenda_classified WHERE owner_id = ? AND ksinr = ?",
            (owner_id, ksinr),
        ).fetchone()
        return row["agenda_hash"] if row else None

    def replace_agenda_matches(
        self, owner_id: int, ksinr: int, agenda_hash: str, matches: dict[int, list[str]]
    ) -> None:
        """Treffer einer Sitzung für eine Nutzer*in komplett ersetzen und den
        klassifizierten Stand festhalten. matches: {topic_id: [item_numbers]}.
        Voller Austausch, damit bei geänderter Tagesordnung keine veralteten
        Treffer stehen bleiben (RL-902)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_agenda_matches WHERE owner_id = ? AND ksinr = ?",
                (owner_id, ksinr),
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_matches
                   (owner_id, ksinr, topic_id, item_number, matched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (owner_id, ksinr, topic_id, item_number, now)
                    for topic_id, item_numbers in matches.items()
                    for item_number in item_numbers
                ],
            )
            self._conn.execute(
                """INSERT OR REPLACE INTO council_agenda_classified
                   (owner_id, ksinr, agenda_hash, classified_at) VALUES (?, ?, ?, ?)""",
                (owner_id, ksinr, agenda_hash, now),
            )

    def has_agenda_match(self, owner_id: int, ksinr: int) -> bool:
        """Hat diese Nutzer*in für diese Sitzung schon einen Themen-Treffer?

        Design 30a: „Themen-Treffer gewinnt" — wer bereits gehört hat, WELCHER
        Tagesordnungspunkt ihn betrifft, braucht daneben nicht die Meldung, dass
        das Gremium überhaupt tagt.
        """
        return self._conn.execute(
            "SELECT 1 FROM council_agenda_matches WHERE owner_id = ? AND ksinr = ? LIMIT 1",
            (owner_id, ksinr),
        ).fetchone() is not None

    def agenda_matches_for_owner(self, owner_id: int, ksinrs: list[int]) -> dict[int, list[dict]]:
        """{ksinr: [{item_number, topic_name}]} für die „n TOPs zu deinen
        Themen"-Chips — nur eigene Themen, sortiert nach TOP-Nummer."""
        if not ksinrs:
            return {}
        placeholders = ",".join("?" for _ in ksinrs)
        rows = self._conn.execute(
            f"""SELECT m.ksinr, m.item_number, t.name AS topic_name
                FROM council_agenda_matches m
                JOIN topics t ON t.id = m.topic_id AND t.owner_id = m.owner_id
                WHERE m.owner_id = ? AND m.ksinr IN ({placeholders})
                ORDER BY m.ksinr, m.item_number""",
            (owner_id, *ksinrs),
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["ksinr"], []).append(
                {"item_number": r["item_number"], "topic_name": r["topic_name"]}
            )
        return out

    def purge_stale_topic_matches(self, gueltige_ids: set[int]) -> int:
        """Treffer UND Gelesen-Marken wegräumen, deren Beschluss es nicht mehr gibt.

        Beschlüsse bekommen bei einer Neu-Extraktion neue IDs; die hier
        gespeicherten Verweise zeigen danach ins Leere. Auf Prod waren am
        15.08.2026 ALLE gespeicherten Treffer tot — der Zähler zeigte acht,
        die Suche fand null. Aufgeräumt wird beim Matching-Lauf, der ohnehin
        beide Datenbanken offen hat.

        `topic_hits_seen` muss mit: Diese Tabelle wurde nie aufgeräumt, also
        sammelte sie Marken auf gelöschte IDs — sie wuchs unbegrenzt und
        markierte nichts mehr. Wer sie stehen lässt, räumt nur die eine Hälfte
        des Problems weg und wundert sich, dass der „neu"-Zähler trotzdem
        springt.
        """
        alle = {r[0] for r in self._conn.execute(
            "SELECT DISTINCT decision_id FROM council_topic_matches")}
        alle |= {r[0] for r in self._conn.execute(
            "SELECT DISTINCT decision_id FROM topic_hits_seen")}
        tot = [d for d in alle if d not in gueltige_ids]
        if not tot:
            return 0
        with self._conn:
            for i in range(0, len(tot), 500):
                part = tot[i : i + 500]
                ph = ",".join("?" * len(part))
                self._conn.execute(
                    f"DELETE FROM council_topic_matches WHERE decision_id IN ({ph})", part)
                self._conn.execute(
                    f"DELETE FROM topic_hits_seen WHERE decision_id IN ({ph})", part)
        return len(tot)

    def topic_decision_counts(self, owner_id: int) -> dict[int, int]:
        """{topic_id: number of matched council decisions} for an owner's topics."""
        rows = self._conn.execute(
            "SELECT topic_id, COUNT(*) AS n FROM council_topic_matches WHERE owner_id = ? GROUP BY topic_id",
            (owner_id,)).fetchall()
        return {r["topic_id"]: r["n"] for r in rows}

    def get_all_owner_topics(self) -> dict[int, list[TopicRow]]:
        """Return {owner_id: [topics]} for all owners that have at least one topic."""
        rows = self._conn.execute(
            "SELECT id, owner_id, chat_id, name, description, created_at FROM topics ORDER BY owner_id, id"
        ).fetchall()
        result: dict[int, list[TopicRow]] = {}
        for r in rows:
            t = TopicRow(**dict(r))
            result.setdefault(t.owner_id, []).append(t)
        return result

    def get_all_owner_digests(self) -> list[dict]:
        """Zustell-Ziele für den Sitzungs-Cron: je Konto ein dict mit Kanal,
        Adressen und Themen.

        [{owner_id, delivery_channel, telegram_chat_id, email, display_name,
          push_tokens: [{token, platform}], topics: [TopicRow]}]

        Gremien-Abos stehen bewusst NICHT hier: Die bedient
        ``scripts/check_committees.py`` mit eigener Entprellung. Zwei Leser für
        dieselbe Sache hießen zwei Meldungen zur selben Sitzung.

        ``status = 'active'``: Ein gesperrtes oder noch unbestätigtes Konto
        bekommt keine Post — vorher lief die Zustellung auch dorthin.
        """
        rows = self._conn.execute(
            """SELECT wu.id AS owner_id, wu.delivery_channel, wu.telegram_chat_id,
                      wu.email, wu.display_name,
                      t.id, t.owner_id AS t_owner, t.chat_id, t.name, t.description, t.created_at
               FROM web_users wu
               JOIN topics t ON t.owner_id = wu.id
               WHERE wu.status = 'active'
               ORDER BY wu.id, t.id"""
        ).fetchall()
        owners: dict[int, dict] = {}
        for r in rows:
            o = owners.get(r["owner_id"])
            if o is None:
                o = {
                    "owner_id": r["owner_id"],
                    "delivery_channel": r["delivery_channel"],
                    "telegram_chat_id": r["telegram_chat_id"],
                    "email": r["email"],
                    "display_name": r["display_name"],
                    "push_tokens": [],
                    "topics": [],
                }
                owners[r["owner_id"]] = o
            o["topics"].append(TopicRow(
                id=r["id"], owner_id=r["t_owner"], chat_id=r["chat_id"],
                name=r["name"], description=r["description"], created_at=r["created_at"],
            ))
        self._attach_push_tokens(owners)  # each owner's registered push devices
        return list(owners.values())

    def add_topic(self, owner_id: int, name: str, description: str) -> TopicRow:
        now = datetime.utcnow().isoformat(timespec="seconds")
        # chat_id kept in sync as the owner's current Telegram target (0 if none),
        # purely for backward-compat; ownership is via owner_id.
        chat_row = self._conn.execute(
            "SELECT telegram_chat_id FROM web_users WHERE id = ?", (owner_id,)
        ).fetchone()
        chat_id = (chat_row[0] if chat_row and chat_row[0] is not None else 0)
        cur = self._conn.execute(
            "INSERT INTO topics (owner_id, chat_id, name, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (owner_id, chat_id, name.strip(), description.strip(), now),
        )
        self._conn.commit()
        return TopicRow(id=cur.lastrowid, owner_id=owner_id, chat_id=chat_id,
                        name=name, description=description, created_at=now)

    # Alles, was an EINEM Thema hängt. Wird ein Thema gelöscht, muss das hier
    # mit weg — sonst zählt der ungelesen-Zähler in der Seitenleiste Treffer
    # eines Themas weiter, das in keiner Liste mehr steht: Es gibt dann keine
    # Oberfläche mehr, über die man sie als gesehen markieren könnte, und die
    # Zahl bleibt für immer stehen. (Die Konto-Löschung war nie betroffen, die
    # geht über USER_OWNED_TABLES.)
    TOPIC_OWNED_TABLES: tuple[str, ...] = (
        "council_topic_matches",
        "council_topic_match_meta",
        "topic_hits_seen",
        "council_agenda_matches",
    )

    def delete_topic(self, topic_id: int) -> None:
        with self._conn:
            for table in self.TOPIC_OWNED_TABLES:
                self._conn.execute(f"DELETE FROM {table} WHERE topic_id = ?", (topic_id,))
            self._conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))

    def purge_orphaned_topic_rows(self) -> dict[str, int]:
        """Zeilen aufräumen, deren Thema es nicht mehr gibt — Altlast aus der
        Zeit, als `delete_topic` nur die Themenzeile entfernte. Idempotent."""
        weg: dict[str, int] = {}
        with self._conn:
            for table in self.TOPIC_OWNED_TABLES:
                cur = self._conn.execute(
                    f"DELETE FROM {table} WHERE topic_id NOT IN (SELECT id FROM topics)"
                )
                if cur.rowcount:
                    weg[table] = cur.rowcount
        return weg

    def update_topic(self, topic_id: int, name: str, description: str) -> None:
        self._conn.execute(
            "UPDATE topics SET name = ?, description = ? WHERE id = ?",
            (name.strip(), description.strip(), topic_id),
        )
        self._conn.commit()

    # ---- committee subscriptions ----

    def subscribe(self, owner_id: int, committee_name: str) -> bool:
        now = datetime.utcnow().isoformat(timespec="seconds")
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO committee_subscriptions (owner_id, committee_name, created_at) VALUES (?, ?, ?)",
                    (owner_id, committee_name, now),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def unsubscribe(self, owner_id: int, committee_name: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM committee_subscriptions WHERE owner_id = ? AND committee_name = ?",
                (owner_id, committee_name),
            )
        return cur.rowcount > 0

    def get_subscriptions(self, owner_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT committee_name FROM committee_subscriptions WHERE owner_id = ? ORDER BY committee_name",
            (owner_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def get_all_subscriptions(self) -> dict[int, list[str]]:
        """Return {owner_id: [committee_name]} for all owners with subscriptions."""
        rows = self._conn.execute(
            "SELECT owner_id, committee_name FROM committee_subscriptions ORDER BY owner_id, committee_name"
        ).fetchall()
        result: dict[int, list[str]] = {}
        for r in rows:
            result.setdefault(r[0], []).append(r[1])
        return result

    def get_subscription_targets(self) -> dict[int, dict]:
        """Return {owner_id: {delivery_channel, telegram_chat_id, email, push_tokens}}
        for all owners that have ≥1 committee subscription — delivery info for the crons."""
        rows = self._conn.execute(
            """SELECT DISTINCT wu.id AS owner_id, wu.delivery_channel,
                      wu.telegram_chat_id, wu.email
               FROM committee_subscriptions cs JOIN web_users wu ON wu.id = cs.owner_id"""
        ).fetchall()
        targets = {r["owner_id"]: dict(r) for r in rows}
        self._attach_push_tokens(targets)
        return targets

    # ---- persönliche Merkliste --------------------------------------------

    def add_bookmark(self, owner_id: int, *, kind: str, target_key: str,
                     ksinr: int | None = None, item_number: str | None = None,
                     decision_id: int | None = None, kvonr: int | None = None,
                     template_number: str = "", title: str = "", subtitle: str = "") -> dict:
        """Einen öffentlichen Ratsinhalt merken und den aktuellen Snapshot ablegen.

        Ein erneuter Klick ist idempotent. Anzeige-Felder werden dabei
        nachgezogen, ``created_at`` und ein bereits gesetzter Ergebnis-Schalter
        bleiben erhalten.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                """INSERT INTO bookmarks
                   (owner_id, kind, target_key, ksinr, item_number, decision_id,
                    kvonr, template_number, title, subtitle, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner_id, target_key) DO UPDATE SET
                     kind=excluded.kind, ksinr=excluded.ksinr,
                     item_number=excluded.item_number,
                     decision_id=COALESCE(excluded.decision_id, bookmarks.decision_id),
                     kvonr=COALESCE(excluded.kvonr, bookmarks.kvonr),
                     template_number=excluded.template_number, title=excluded.title,
                     subtitle=excluded.subtitle""",
                (owner_id, kind, target_key, ksinr, item_number, decision_id,
                 kvonr, template_number or "", title or "", subtitle or "", now),
            )
        row = self._conn.execute(
            "SELECT * FROM bookmarks WHERE owner_id = ? AND target_key = ?",
            (owner_id, target_key),
        ).fetchone()
        return dict(row)

    def get_bookmarks(self, owner_id: int) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM bookmarks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()]

    def get_bookmark_for_owner(self, owner_id: int, bookmark_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM bookmarks WHERE id = ? AND owner_id = ?",
            (bookmark_id, owner_id),
        ).fetchone()
        return dict(row) if row else None

    def delete_bookmark(self, owner_id: int, bookmark_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM bookmarks WHERE id = ? AND owner_id = ?",
                (bookmark_id, owner_id),
            )
        return cur.rowcount > 0

    def set_bookmark_result_notification(self, owner_id: int, bookmark_id: int,
                                         enabled: bool) -> dict | None:
        """Ergebnis-Hinweis separat vom Merken schalten.

        Nur TOPs akzeptiert der Router dafür; die Store-Schicht hält die
        Operation absichtlich allgemein und eigentümergesichert.
        """
        with self._conn:
            cur = self._conn.execute(
                "UPDATE bookmarks SET notify_result = ? WHERE id = ? AND owner_id = ?",
                (1 if enabled else 0, bookmark_id, owner_id),
            )
        return self.get_bookmark_for_owner(owner_id, bookmark_id) if cur.rowcount else None

    def update_bookmark_snapshot(self, bookmark_id: int, *, item_number: str | None,
                                 decision_id: int | None, kvonr: int | None,
                                 template_number: str, title: str, subtitle: str) -> None:
        """Aufgelöste aktuelle Kennungen zurückschreiben.

        So muss eine spätere Nummernverschiebung nur einmal über Titel/Vorlage
        erkannt werden; danach zeigt der Snapshot wieder auf den aktuellen TOP.
        """
        with self._conn:
            self._conn.execute(
                """UPDATE bookmarks SET item_number=?, decision_id=?,
                   kvonr=COALESCE(?, kvonr), template_number=?, title=?, subtitle=?
                   WHERE id=?""",
                (item_number, decision_id, kvonr, template_number or "", title or "",
                 subtitle or "", bookmark_id),
            )

    def bookmark_result_targets(self, ksinr: int) -> list[dict]:
        """Noch nicht abgeschlossene, ausdrücklich abonnierte TOP-Merker."""
        return [dict(r) for r in self._conn.execute(
            """SELECT b.* FROM bookmarks b
               JOIN web_users u ON u.id = b.owner_id
               WHERE b.kind = 'agenda_item' AND b.ksinr = ?
                 AND b.notify_result = 1 AND b.result_notified_at IS NULL
                 AND u.status = 'active'
               ORDER BY b.owner_id, b.id""",
            (ksinr,),
        ).fetchall()]

    def pending_bookmark_ksinrs(self) -> list[int]:
        """Sitzungen mit noch offenem Ergebnis-Abo — auch jenseits des
        normalen 90-Tage-Protokollfensters."""
        return [r[0] for r in self._conn.execute(
            """SELECT DISTINCT ksinr FROM bookmarks
               WHERE kind = 'agenda_item' AND notify_result = 1
                 AND result_notified_at IS NULL AND ksinr IS NOT NULL"""
        ).fetchall()]

    def mark_bookmark_results_notified(self, bookmark_ids: list[int]) -> None:
        if not bookmark_ids:
            return
        now = datetime.utcnow().isoformat(timespec="seconds")
        ph = ",".join("?" * len(bookmark_ids))
        with self._conn:
            self._conn.execute(
                f"UPDATE bookmarks SET result_notified_at = ? WHERE id IN ({ph})",
                (now, *bookmark_ids),
            )

    # ---- verfolgte Vorgänge (Design 28a/W1) ----

    def follow_vorlage(self, owner_id: int, kvonr: int, *, template_number: str = "",
                       title: str = "", stations: str = "[]") -> bool:
        """Vorgang abonnieren. True = neu angelegt, False = folgte schon.

        `stations` ist der Stand BEIM ABONNIEREN: Was heute schon in der
        Beratungsfolge steht, ist keine Neuigkeit — sonst käme direkt nach dem
        Klick eine Meldung über Stationen, die man gerade selbst gelesen hat.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO vorlage_follows "
                "(owner_id, kvonr, template_number, title, stations, created_at) VALUES (?,?,?,?,?,?)",
                (owner_id, kvonr, template_number or "", title or "", stations, now),
            )
        return cur.rowcount > 0

    def unfollow_vorlage(self, owner_id: int, kvonr: int) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM vorlage_follows WHERE owner_id = ? AND kvonr = ?", (owner_id, kvonr)
            )
        return cur.rowcount > 0

    def get_vorlage_follows(self, owner_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, kvonr, template_number, title, created_at, notified_at "
            "FROM vorlage_follows WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def is_following_vorlage(self, owner_id: int, kvonr: int) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM vorlage_follows WHERE owner_id = ? AND kvonr = ?", (owner_id, kvonr)
        ).fetchone() is not None

    def get_vorlage_follow_targets(self) -> list[dict]:
        """Alle Follows samt Zustellinfo — Grundlage von check_vorlage_follows.py.

        Eine Zeile je Follow (nicht je Konto): Der Cron holt die Beratungsfolge
        einmal je kvonr und meldet dann jedem folgenden Konto einzeln. Gesperrte
        Konten bleiben draußen — sie sollen keine Post bekommen.
        """
        rows = self._conn.execute(
            """SELECT f.id, f.owner_id, f.kvonr, f.template_number, f.title, f.stations,
                      wu.delivery_channel, wu.email, wu.display_name
               FROM vorlage_follows f JOIN web_users wu ON wu.id = f.owner_id
               WHERE wu.status = 'active'
               ORDER BY f.kvonr"""
        ).fetchall()
        out = [dict(r) for r in rows]
        owners: dict[int, dict] = {o["owner_id"]: {} for o in out}
        self._attach_push_tokens(owners)
        for o in out:
            o["push_tokens"] = owners[o["owner_id"]].get("push_tokens", [])
        return out

    def mark_vorlage_follow_notified(self, follow_id: int, stations: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE vorlage_follows SET stations = ?, notified_at = ? WHERE id = ?",
                (stations, now, follow_id),
            )
