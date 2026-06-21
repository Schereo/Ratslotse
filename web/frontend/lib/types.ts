export interface User {
  id: number;
  email: string;
  role: "user" | "admin";
  status: "pending" | "active";
  telegram_chat_id: number | null;
  linked: boolean;
  nwz_verified: boolean;
  nwz_username: string | null;
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
}

export interface AgendaItem {
  item_number: string;
  title: string;
  vorlage_nr: string | null;
  kvonr: number | null;
  is_public: number;
}

export interface SessionDetail extends CouncilSession {
  agenda_items: AgendaItem[];
  url: string;
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
  nwz_username: string | null;
  nwz_verified_at: string | null;
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
