export type DeliveryChannel = "email" | "both" | "push";

export interface User {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "pending" | "active";
  delivery_channel: DeliveryChannel;
  email_verified: boolean;
  // Sign in with Apple (RL-1002): verknüpft? Hat das Konto ein eigenes Passwort?
  apple_linked?: boolean;
  has_password?: boolean;
  // Present only on native-app auth responses; the web relies on the cookie.
  access_token?: string | null;
  display_name?: string | null;
}

export interface CouncilSession {
  // null = terminierte Sitzung aus dem RIS-Kalender, Tagesordnung noch
  // nicht veröffentlicht (dann gibt es weder Detailseite noch TOPs).
  ksinr: number | null;
  committee: string;
  session_date: string;
  session_time: string;
  location: string;
  n_items: number;
  // Present on text search: the agenda items that matched the query.
  matched_items?: AgendaItem[];
  // RL-902: TOPs dieser Sitzung, die zu eigenen Themen passen.
  my_topic_items?: { item_number: string; topic_name: string }[];
}

export interface AgendaItem {
  item_number: string;
  title: string;
  vorlage_nr: string | null;
  kvonr: number | null;
  is_public: number;
}

export type DecisionOutcome =
  | "angenommen" | "abgelehnt" | "vertagt" | "zur_kenntnis" | "kein_beschluss";

export interface CouncilDecision {
  id: number;
  ksinr: number;
  kind: "decision" | "subvote";
  parent_item: string | null;
  item_number: string | null;
  title: string | null;
  beschluss: string | null;
  outcome: DecisionOutcome | null;
  vote: string | null;
  gegenstimmen: number | null;
  enthaltungen: number | null;
  factions: string[];
  parties: string[];
  vorlage_nr: string | null;
  raw_result: string | null;
  committee: string;
  session_date: string;
  protocol_url: string | null;
  policy_field: string | null;
  policy_tags: string[];
  summary: string | null;
  amount_eur: number | null;
  /** Wichtigkeits-Score 0–100 (council.importance); null = noch nicht berechnet. */
  importance?: number | null;
  /** „Lotti erklärt's einfach" (RL-904): 2–3 bürgernahe Sätze, per Backfill. */
  simple_summary?: string | null;
  /** Design 23a: kompakte Zusammenfassung der Änderungsanträge (subvotes),
   *  die zu diesem Beschluss gehören — für die Unterzeile in der Trefferliste. */
  subvote_summary?: { count: number; factions: string[]; outcomes: string[] } | null;
}

export interface PolicyField {
  key: string;
  label: string;
  count: number;
}

export interface QaSource {
  id: number; title: string | null; summary: string | null;
  policy_field: string | null; outcome: DecisionOutcome | null;
  session_date: string; committee: string; score?: number;
}

export interface QaAnswer {
  answer: string;
  mode?: string;
  sources: QaSource[];
}

export interface GoalSummary {
  key: string; label: string; description: string;
  voran: number; bremst: number; neutral: number; total: number;
}

export interface GoalDecision {
  id: number; title: string | null; summary: string | null;
  policy_field: string | null; outcome: DecisionOutcome | null;
  session_date: string; committee: string; stance: string; rationale: string | null;
}

export interface GoalDetail {
  key: string; label: string; description: string;
  summary: { voran: number; bremst: number; neutral: number; total: number };
  decisions: GoalDecision[];
}

export interface MoneyDriver {
  id: number; title: string; eur: number;
}

export interface Trends {
  quarters: string[];
  fields: string[];
  by_field: Record<string, number[]>;
  money: number[];
  money_drivers: (MoneyDriver | null)[];
  emerging: { tag: string; n: number }[];
  field_labels: Record<string, string>;
}

export interface FinanceData {
  decisions: CouncilDecision[];
  by_field: { field: string; total: number; n: number }[];
  field_labels: Record<string, string>;
}

export interface PartyAnalysis {
  coverage: { with_factions: number; total: number };
  topic_matrix: {
    parties: string[];
    fields: string[];
    matrix: Record<string, Record<string, number>>;
  };
  success_rates: {
    party: string; motions: number;
    angenommen: number; abgelehnt: number; vertagt: number; rate: number | null;
  }[];
  contention: { field: string; total: number; contested: number; contested_rate: number }[];
  alliances: { a: string; b: string; count: number }[];
  field_labels: Record<string, string>;
  /** Erfolgsquoten der eingereichten Antrags-Dokumente (Anlagen-Ingestion). */
  antrag_stats?: {
    parties: { party: string; n: number; angenommen: number; abgelehnt: number }[];
    n_antraege: number;
    n_mit_beschluss: number;
  } | null;
}

export interface Attendee {
  name: string | null;
  party: string | null;
  role: string | null;
  note: string | null;
}

export interface SessionDetail extends CouncilSession {
  agenda_items: AgendaItem[];
  decisions?: CouncilDecision[];
  attendance?: Attendee[];
  has_protocol?: boolean;
  url: string;
}

export interface VorlageStop {
  ksinr: number;
  committee: string;
  session_date: string;
  item_number: string;
}

export interface SimilarDecision {
  id: number; title: string | null; summary: string | null;
  policy_field: string | null; outcome: DecisionOutcome | null;
  session_date: string; committee: string; score: number;
}

export interface NewsLink {
  catalog: number; refid: string; title: string | null; pub_date: string | null; score: number;
}

export interface Entity {
  slug: string; name: string; kind: string; n: number;
  /** Datum der letzten Sitzung mit Beschluss zu diesem Thema. */
  last_date?: string | null;
  /** Beschlüsse der letzten 12 Monate — Basis der „gerade aktiv"-Priorisierung. */
  n_recent?: number;
}

export interface EntityMapPoint {
  slug: string; name: string; kind: string; n: number; lat: number; lon: number;
}

export interface EntityGeo {
  lat: number;
  lon: number;
  geojson: { type: string; coordinates: unknown } | null;
}

export interface EntityDetail {
  entity: Entity;
  description: string | null;
  geo: EntityGeo | null;
  decisions: CouncilDecision[];
  money: number;
  parties: string[];
  fields: { field: string; n: number }[];
  field_labels: Record<string, string>;
}

export interface Member {
  slug: string; name: string; party: string | null;
  n: number; committees: number; first: string | null; last: string | null;
}

export interface MemberDetail {
  name: string; slug: string; party: string | null;
  n_sessions: number; active_from: string | null; active_to: string | null;
  /** Fraktions-/Gruppen-Verlauf aus der Anwesenheit: Phasen je Zugehörigkeit,
   *  älteste zuerst. `kind` unterscheidet Partei / (Rats-)Gruppe / parteilos;
   *  `parties` sind bei einer Gruppe ihre Mitglieds-Parteien. */
  faction_timeline: {
    label: string;
    kind: "partei" | "gruppe" | "parteilos";
    parties: string[];
    first: string;
    last: string;
    n: number;
  }[];
  /** Offizielle Stammdaten aus dem Ratsinfo (falls die Person dort verlinkt ist). */
  ris: {
    kpenr: number;
    name: string;
    fraktion_aktuell: string | null;
    memberships: { kgrnr: number | null; gremium: string; rolle: string | null; von: string | null; bis: string | null }[];
  } | null;
  committees: { committee: string; n: number; chair: boolean }[];
  recent: { ksinr: number; committee: string; session_date: string }[];
}

/** Eine Station der offiziellen Beratungsfolge einer Vorlage. */
export interface Beratung {
  datum: string | null;
  gremium: string;
  top: string | null;
  is_public: number | null;
  ergebnis: string | null;
  ksinr: number | null;
  future: boolean;
}

export interface ImportanceBreakdown {
  /** Endwert: Mittel aus `base_score` und `impact` (oder `base_score` allein). */
  score: number;
  /** Heuristik allein (die vier Signale) — vor der Mischung mit der Tragweite. */
  base_score?: number;
  /** RL-U16: KI-Tragweite 0–100 (fehlt, solange der Backfill sie nicht hat). */
  impact?: number | null;
  /** 0–1 je Signal, null wenn das Signal für diesen Beschluss fehlt. */
  signals: { geld: number | null; umstritten: number | null; verbindlich: number | null; aufwand: number | null };
  /** Gewichteter Punkte-Beitrag je Signal; Summe = `base_score`. */
  contributions?: { geld: number | null; umstritten: number | null; verbindlich: number | null; aufwand: number | null };
  /** RL-U16: 1-Satz-Begründung des Tragweite-Scores (fehlt vor dem Backfill). */
  impact_reason?: string | null;
}

export interface DecisionDetail {
  decision: CouncilDecision;
  /** Aufschlüsselung, warum der Beschluss als wichtig gilt. */
  importance_breakdown?: ImportanceBreakdown | null;
  attendance: Attendee[];
  present_parties: string[];
  sub_votes: CouncilDecision[];
  vorlage_journey: VorlageStop[];
  /** Offizielle Beratungsfolge aus dem Ratsinfo — mit Ergebnis je Station und
   *  geplanten künftigen Beratungen. Fehlt, solange sie nicht gescrapt ist. */
  beratungsfolge?: Beratung[];
  similar: SimilarDecision[];
  news: NewsLink[];
  entities: Entity[];
  ratsinfo_url: string;
  vorlage_url?: string | null;
  /** Eingelesener Vorlagen-Text (Sachverhalt/Begründung) zum Beschluss. */
  vorlage?: {
    vorlage_nr: string | null;
    title: string | null;
    art: string | null;
    document_url: string | null;
    n_pages: number | null;
    excerpt: string | null;
  } | null;
  /** Anlagen der Vorlage (Anträge zuerst, mit erkannten Antragstellern). */
  anlagen?: {
    document_id: number;
    label: string | null;
    url: string | null;
    is_antrag: number;
    antragsteller: string[];
    status: string;
  }[];
}

export interface Topic {
  id: number;
  name: string;
  description: string;
  created_at: string;
  decision_count: number;
  last_hit_id?: number | null;
  last_hit_title?: string | null;
  last_hit_date?: string | null;
  unread_count?: number;
}

export interface TopicDecision {
  id: number;
  title: string;
  committee: string;
  session_date: string;
  policy_field: string | null;
  outcome: string | null;
  score: number;
}

export interface FieldRecap {
  policy_field: string;
  field_label: string;
  summary: string;
  n_decisions: number;
  period_from: string;
  period_to: string;
  generated_at: string;
}

export interface Prompt {
  key: string;
  title: string;
  description: string;
  content: string;
  default: string;
  is_overridden: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface AdminQuizStats {
  fragen_aktiv: number;
  avg_accuracy: number;
  gemeldet: number;
  gebiete_niedrig: { area_type: string; area_key: string; n: number }[];
}

export interface WebUser {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "pending" | "active";
  email_verified: boolean;
  created_at: string;
}

export interface AdminStats {
  web_users: { total: number; admins: number; active: number; pending: number };
  topics: { total: number; users_with_topics: number; subscriptions: number };
  council: { sessions: number; upcoming: number; agenda_items: number; committees: number };
}

export interface AdminUserRow {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "active" | "pending";
  created_at: string;
  apple_linked: boolean;
  n_topics: number;
  n_abos: number;
  n_quiz: number;
  n_ki: number;
  last_seen: string | null;
}

export interface AdminUserDetail {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "active" | "pending";
  created_at: string;
  last_seen: string | null;
  apple_linked: boolean;
  has_password: boolean;
  delivery_channel: string;
  features: { ki_frage: number; suche: number; quiz: number; analyse: number; karte: number };
  topics: string[];
  abos: string[];
  verlauf: number[];
  /** ISO-Datum je Verlaufs-Balken (x-Achse, 30 Tage). */
  verlauf_days: string[];
}

/** Ein Cron-Job in der Admin-Übersicht: Registry-Angaben + letzter Lauf. */
export interface AdminJob {
  key: string;
  label: string;
  description: string;
  schedule: string;
  /** ok = frisch gelaufen · stale = überfällig · error = zuletzt gescheitert · unknown = noch nie erfasst. */
  state: "ok" | "stale" | "error" | "unknown";
  age_h: number | null;
  last: {
    started_at: string; finished_at: string | null; status: string;
    duration_s: number | null; stats: Record<string, number | string> | null; error: string | null;
  } | null;
  history: { started_at: string; status: string; duration_s: number | null }[];
}

export interface AdminGrowth {
  /** `days` = ISO-Datum je Serienpunkt (x-Achse, Serverdatum). */
  users: { total: number; series: number[]; delta: number; days: string[] };
  topics: { total: number; series: number[]; delta: number; days: string[] };
  wau: number[];
  /** Enddatum je WAU-Woche (x-Achse). */
  wau_days: string[];
  council: {
    sessions: number; upcoming: number; agenda_items: number; committees: number;
    decisions: number; decisions_with_ki: number; fetched_today: number;
    /** Puls des Scrapers (auch ohne neue Sitzung) vs. neueste Tagesordnung. */
    last_fetch: string | null; hours_since_fetch: number | null;
    last_session_import: string | null; next_session: string | null;
  };
}

// ---- Quiz ----
export interface QuizAreaEntry {
  key: string;
  label?: string;
  wahlbereiche?: number[];
  stadtteile?: string[];
  /** Themen: Stadtteil des Themen-Orts (RL-U13); null/fehlend = stadtweit. */
  stadtteil?: string | null;
  questions: number;
  points: number;
}
export interface QuizAreas {
  wahlbereiche: QuizAreaEntry[];
  stadtteile: QuizAreaEntry[];
  themen: QuizAreaEntry[];
  categories: string[];
}
/** Eigene Quizfrage (RL-U14) — privat je Konto, mit Übungs-Zählern.
 *  qtype "estimate" (Kategorie „Schätzfrage") nutzt answer_value + Slider-Bereich
 *  statt Optionen. */
export interface UserQuizQuestion {
  id: number;
  question: string;
  options: string[];
  correct_index: number;
  stadtteil: string | null;
  category: string;
  explanation: string | null;
  qtype?: "mc" | "estimate";
  answer_value?: number | null;
  unit?: string | null;
  range_min?: number | null;
  range_max?: number | null;
  practiced: number;
  correct_count: number;
  created_at: string;
}
export interface QuizQuestion {
  id: number;
  area_type: string;
  area_key: string;
  category: string;
  difficulty: string;
  question: string;
  options: string[];
  qtype?: "mc" | "estimate";
  unit?: string | null;
  range_min?: number | null;
  range_max?: number | null;
  /** Optionaler Tipp, der vor dem Auflösen eingeblendet werden kann. */
  hint?: string | null;
  source_type: string | null;
  source_ref: string | null;
}
export interface QuizImageCredit {
  url: string;
  author: string | null;
  license: string | null;
  license_url: string | null;
  source_url: string | null;
}
export interface QuizAnswerResult {
  correct: boolean;
  correct_index: number;
  points: number;
  answer_value?: number | null;
  unit?: string | null;
  explanation: string | null;
  source_type: string | null;
  source_ref: string | null;
  detail?: string | null;
  /** Such-Stichwort für „Beschlüsse dazu" (verlinkt in die Beschluss-Suche). */
  topic?: string | null;
  map?: { lat: number; lon: number; label: string | null; geojson?: object | null } | null;
  image?: QuizImageCredit | null;
  /** Diagramm der Auflösung (Haushalts-Fragen): Balken, Donut oder Trendlinie. */
  chart?: {
    type?: "bars" | "share" | "trend";
    title: string;
    unit: string;
    items: { label: string; value: number; highlight?: boolean }[];
  } | null;
}
export interface QuizBadge {
  key: string;
  label: string;
  tier: "bronze" | "silber" | "gold";
}
export interface QuizStats {
  by_area: { area_type: string; area_key: string; points: number; answered: number; correct: number; last_at: string | null }[];
  total: { points: number; answered: number; correct: number };
  wrong: number;
  streak: number;
  badges: QuizBadge[];
  daily_done: boolean;
}
export interface QuizDailyResult {
  day: string;
  correct: number;
  total: number;
  points: number;
  completed_at: string;
}
export interface QuizDaily {
  day: string;
  done: QuizDailyResult | null;
  questions: QuizQuestion[];
}
export interface QuizFlagged {
  question_id: number;
  bad: number;
  good: number;
  comments: string | null;
  question: string;
  area_type: string;
  area_key: string;
  options: string[];
  correct_index: number;
}

/** Eine zusammengeführte Themen-Dublette (Admin). `alias_name` stammt aus den
 *  Roh-Beobachtungen — das Thema selbst gibt es nach dem Zusammenführen nicht mehr. */
export interface EntityAlias {
  slug: string;
  canonical_slug: string;
  source: "llm" | "manuell" | string;
  reason: string | null;
  created_at: string;
  alias_name: string | null;
  canonical_name: string | null;
  canonical_n: number | null;
}
