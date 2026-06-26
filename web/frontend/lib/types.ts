export type DeliveryChannel = "telegram" | "email" | "both";

export interface User {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "pending" | "active";
  telegram_chat_id: number | null;
  linked: boolean;
  delivery_channel: DeliveryChannel;
  nwz_fulltext_allowed: boolean;
}

export interface SearchResult {
  catalog: number;
  refid: string;
  pub_date: string;
  category_name: string;
  title: string;
  subtitle: string;
  authors: string;
  excerpt: string;
  rank: number;
}

export interface Article {
  catalog: number;
  refid: string;
  page: number | null;
  category_name: string;
  title: string;
  subtitle: string;
  authors: string;
  content_text: string;
  content_html: string;
  publication_date: string;
  edition_title: string;
}

export interface CouncilSession {
  ksinr: number;
  committee: string;
  session_date: string;
  session_time: string;
  location: string;
  n_items: number;
  // Present on text search: the agenda items that matched the query.
  matched_items?: AgendaItem[];
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
  committees: { committee: string; n: number; chair: boolean }[];
  recent: { ksinr: number; committee: string; session_date: string }[];
}

export interface DecisionDetail {
  decision: CouncilDecision;
  attendance: Attendee[];
  present_parties: string[];
  sub_votes: CouncilDecision[];
  vorlage_journey: VorlageStop[];
  similar: SimilarDecision[];
  news: NewsLink[];
  entities: Entity[];
  ratsinfo_url: string;
  vorlage_url?: string | null;
}

export interface Topic {
  id: number;
  name: string;
  description: string;
  created_at: string;
  match_count: number;
}

export interface TopicMatch {
  catalog: number;
  refid: string;
  pub_date: string;
  title: string;
  summary: string;
  is_continuation: number;
  matched_at: string;
}

export interface Prompt {
  key: string;
  title: string;
  description: string;
  content: string;
  default: string;
  is_overridden: boolean;
}

export interface WebUser {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "pending" | "active";
  telegram_chat_id: number | null;
  nwz_fulltext_allowed: boolean;
  created_at: string;
}

export interface TelegramUser {
  chat_id: number;
  username: string;
  added_at: string;
  topic_count: number;
}

export interface AdminStats {
  articles: { total: number; editions: number; fts: number; oldest: string | null; newest: string | null };
  categories: { name: string; count: number }[];
  web_users: { total: number; admins: number; active: number; pending: number; nwz_verified: number; linked: number };
  telegram_users: number;
  topics: { total: number; users_with_topics: number; matches: number; classified_editions: number; subscriptions: number };
  council: { sessions: number; upcoming: number; agenda_items: number; committees: number };
}
