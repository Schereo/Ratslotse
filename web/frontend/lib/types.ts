import type { components } from "./api-schema";

/** Kurzform für die generierten Antwortformen aus `api-schema.ts`.
 *
 *  WARUM DAS HIER STEHT. Bis 09/2026 schrieb diese Datei 63 Antworttypen von
 *  Hand aus. Eine Abschrift ist eine zweite Wahrheit neben dem Backend: Sie
 *  veraltet lautlos, und zwar in jedem Frontend einzeln. Nachgemessen, bevor
 *  die Umstellung begann: Die Vereinigung für den Konto-Status führte hier
 *  „pending | active" — den dritten Wert `blocked` gibt es seit jeher, er
 *  fehlte nur.
 *
 *  Ein abgeleiteter Typ kann das nicht: Er ändert sich mit dem Vertrag, und
 *  wo eine Seite das nicht verkraftet, bricht der Übersetzer. */
type S = components["schemas"];

/** Wohin Benachrichtigungen gehen — „off" heißt: gar nicht. */
export type DeliveryChannel = "email" | "both" | "push" | "off";

export type User = S["UserOut"];

export type CouncilSession = S["SessionRow"];

/** Ein Tagesordnungspunkt, wie ihn die Textsuche zurückgibt — fünf Spalten,
 *  ohne Anlagen, Kurzfassung und Kartentext. */
export type MatchedAgendaItem = S["MatchedAgendaItem"];

/** Was eine Tagesordnungszeile WIRKLICH braucht.
 *
 *  Dieselbe Zeile rendert zwei Herkünfte: den vollen Punkt der Sitzungsseite
 *  und den schmalen Treffer der Suche. Bis 09/2026 stand an der Stelle der
 *  volle Typ — die Suchtreffer passten nie dazu, und die Zeile las vier
 *  Felder, die es dort gar nicht gibt. Sie fragt sie ohnehin ab (`?.` und
 *  Wahrheitsprüfung), es war nur nicht aufgeschrieben. */
export type AgendaRowItem = MatchedAgendaItem & Partial<AgendaItem>;

export type AgendaItem = S["AgendaItemRow"];

export type DecisionOutcome =
  | "accepted" | "rejected" | "postponed" | "noted" | "no_decision";

export interface DecisionLocationMatch {
  name: string;
  district: string;
  place_id?: string | null;
  local_area_id?: string | null;
  source: "title" | "official_text" | "template";
  evidence: string;
  method: string;
  confidence: number;
  lat?: number | null;
  lon?: number | null;
}

export interface CouncilDecision {
  id: number;
  ksinr: number;
  kind: "decision" | "subvote";
  parent_item: string | null;
  item_number: string | null;
  title: string | null;
  official_text: string | null;
  outcome: DecisionOutcome | null;
  vote: string | null;
  no_votes: number | null;
  abstentions: number | null;
  factions: string[];
  parties: string[];
  template_number: string | null;
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
  /** Regex-Ernte: Wie stark weicht der Beschluss vom Verwaltungsvorschlag ab? */
  deviation?: "unchanged" | "slight" | "strong" | null;
  /** Beim Ortsfilter: konkrete Treffer samt Fundstelle zur manuellen Prüfung. */
  location_matches?: DecisionLocationMatch[];
}

export type PolicyField = S["PolicyField"];

export interface QaSource {
  id: number; title: string | null; summary: string | null;
  policy_field: string | null; outcome: DecisionOutcome | null;
  session_date: string; committee: string; score?: number;
  /** Ratsgespräch-Bausteine (RG-04/05): Betrag und Antragsteller-Fraktionen,
   *  deterministisch aus den Beschluss-Metadaten. */
  amount_eur?: number | null;
  /** Kostenentwicklung: gleiche Vorlagen-Familie = belegbares Delta. */
  template_number?: string | null;
  factions?: string[];
  /** Bei Ortsfragen: konkrete, quellenbelegte Zuordnung zum gefragten Ort. */
  location_matches?: DecisionLocationMatch[];
  /** 5a/I-10: verortete Entität für die Mini-Karte unter der Antwort. */
  ort_name?: string | null;
  lat?: number | null;
  lon?: number | null;
}

export interface QaAnswer {
  answer: string;
  mode?: string;
  sources: QaSource[];
}

export interface GoalSummary {
  key: string; label: string; description: string;
  advances: number; hinders: number; neutral: number; total: number;
}

export interface GoalDecision {
  id: number; title: string | null; summary: string | null;
  policy_field: string | null; outcome: DecisionOutcome | null;
  session_date: string; committee: string; stance: string; rationale: string | null;
}

export interface GoalDetail {
  key: string; label: string; description: string;
  summary: { advances: number; hinders: number; neutral: number; total: number };
  decisions: GoalDecision[];
}

export type MoneyDriver = S["MoneyDriver"];

/** `field_labels` fehlte bis 02.09.2026 in der Antwortform — FastAPI hat es
 *  deshalb aus der Antwort ENTFERNT, obwohl die Route es berechnet. Hier stand
 *  es trotzdem als Pflichtfeld, der Übersetzer war zufrieden, und
 *  `d.field_labels[f]` lief im Browser auf `undefined`. Abgeleitet kann das
 *  nicht mehr passieren. */
export type Trends = S["TrendData"];

export type FinanceData = S["Finances"];

export interface PartyAnalysis {
  coverage: { with_factions: number; total: number };
  topic_matrix: {
    parties: string[];
    fields: string[];
    matrix: Record<string, Record<string, number>>;
  };
  success_rates: {
    party: string; motions: number;
    accepted: number; rejected: number; postponed: number; rate: number | null;
  }[];
  contention: { field: string; total: number; contested: number; contested_rate: number }[];
  alliances: { a: string; b: string; count: number }[];
  field_labels: Record<string, string>;
  /** Erfolgsquoten der eingereichten Antrags-Dokumente (Anlagen-Ingestion). */
  antrag_stats?: {
    parties: { party: string; n: number; accepted: number; rejected: number }[];
    n_antraege: number;
    n_mit_beschluss: number;
  } | null;
}

export type Attendee = S["Attendance"];

/** Vorläufiges Abstimmungsergebnis aus der O1-Videoaufzeichnung — LLM-gelesen
 *  aus den YouTube-Untertiteln, ausdrücklich unter Vorbehalt. Erscheint nur
 *  an TOPs, die noch keinen Protokoll-Beschluss haben. */
export interface VideoResult {
  item_number: string;
  outcome: "accepted" | "rejected" | "postponed" | "noted" | "removed";
  /** Nur gesetzt, wo der Wortlaut es trägt — sonst offen (null). */
  vote: "unanimous" | "majority" | null;
  no_votes: number | null;
  abstentions: number | null;
  quote: string;
  video_id: string;
  /** Fundstelle des Belegs im Video (Sekunden) — für den Sprung-Link. */
  video_seconds: number | null;
}

export interface SessionDetail extends CouncilSession {
  agenda_items: AgendaItem[];
  decisions?: CouncilDecision[];
  attendance?: Attendee[];
  has_protocol?: boolean;
  url: string;
  /** „Zuletzt geändert"-Chronik der Tagesordnung, neueste zuerst — Ziel der
   *  Änderungs-Push; ältere Sitzungen (vor der Chronik) haben keine. */
  agenda_changes?: AgendaAenderung[];
  video_results?: VideoResult[];
}

export type BookmarkKind = "session" | "agenda_item" | "decision";
export type BookmarkState = "upcoming" | "waiting" | "protocol" | "decided" | "saved" | "unavailable" | "group";

/** Persönlicher Merkeintrag, serverseitig gegen den aktuellen Ratsbestand
 *  aufgelöst. Ein agenda_item bekommt automatisch `decision`, sobald das
 *  Protokoll verarbeitet wurde. */
export type BookmarkEntry = S["BookmarkEntry"];

export interface AgendaAenderungZeile {
  art: "new" | "changed" | "moved" | "template" | "attachments" | "removed";
  label: string;
  title: string;
  nichtoeffentlich: boolean;
  detail: string | null;
}

export type AgendaAenderung = S["AgendaChange"];

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

export interface Entity {
  slug: string; name: string; kind: string; n: number;
  /** Datum der letzten Sitzung mit Beschluss zu diesem Thema. */
  last_date?: string | null;
  /** Beschlüsse der letzten 12 Monate — Basis der „gerade aktiv"-Priorisierung. */
  n_recent?: number;
}

export interface EntityMapPoint {
  slug: string; name: string; kind: string; n: number; lat: number; lon: number;
  target?: "thema" | "ort" | "location";
  place_id?: string | null;
  location_slug?: string | null;
  local_area_id?: string | null;
}

export interface PlaceCandidateEvidence {
  id: number; title: string | null; session_date: string;
  evidence: string; method: string; confidence: number;
}

export interface PlaceCandidate {
  slug: string; name: string; kind: string; lat: number | null; lon: number | null;
  district: string | null; local_area_id: string | null;
  status: "pending" | "concrete" | "approved" | "alias" | "rejected";
  decision_count: number; last_date: string; avg_confidence: number;
  review_place_id?: string | null; review_name?: string | null;
  review_kind?: string | null; parent_id?: string | null; aliases?: string[];
  description?: string | null; source_url?: string | null;
  quiz_enabled?: boolean; canonical_place_id?: string | null; note?: string | null;
  evidence: PlaceCandidateEvidence[];
}

export type EntityGeo = S["EntityGeo"];

/** Ein verwandtes Thema (vorberechnet, council.related).
 *  `belegt` = kommt gemeinsam in Beschlüssen vor (`evidence` = in wie vielen),
 *  `aehnlich` = semantischer Nachbar aus den Embeddings, füllt nur auf. */
export type RelatedEntity = S["RelatedEntity"];

export interface EntityDetail {
  entity: Entity;
  description: string | null;
  geo: EntityGeo | null;
  decisions: CouncilDecision[];
  money: number;
  parties: string[];
  fields: { field: string; n: number }[];
  field_labels: Record<string, string>;
  related?: RelatedEntity[];
}

export interface Member {
  slug: string; name: string; party: string | null;
  /** „rat" = Ratsmandat (im Plenum geführt oder im RIS als Ratsmitglied),
   *  „beratend" = beratendes Mitglied eines Ausschusses (Verband, Beirat,
   *  Fachperson) — dem Rat gehört es nicht an. */
  art: "council" | "advisory";
  /** Entsendende Organisation der beratenden Mitglieder („Behindertenbeirat"). */
  organisation: string | null;
  /** Werte, unter denen die Person im Fraktions-Filter erscheint. Meist die
   *  eine Fraktion; ein verbliebenes Zusammenschluss-Label („Die Linke/
   *  Piraten") zählt für beide Parteien, damit niemand aus dem Filter fällt. */
  filter_parteien: string[];
  n: number; committees: number; first: string | null; last: string | null;
  /** Die belegten Schreibweisen dieser Person aus den Anwesenheitslisten —
   *  meist nur eine, gelegentlich zwei Namensformen. Nicht zur Anzeige
   *  gedacht: Die Suche im Verzeichnis findet damit auch, wer die ältere Form
   *  eintippt, ohne dass die Seite eine Behauptung über den Menschen aufstellt. */
  formen?: string[];
}

export interface MemberDetail {
  /** Fehlt bei älteren gecachten Antworten — dann als "rat" behandeln. */
  type?: "council";
  name: string; slug: string; party: string | null;
  /** Zugehörigkeit für den Seitenkopf — wie im Verzeichnis aufgelöst
   *  („FDP/Volt" → FDP, wo es belegt ist). Die Zeitreihe darunter bleibt
   *  quellentreu. */
  current_affiliation: { label: string; kind: "party" | "group" | "independent"; parties: string[] } | null;
  /** Wie `Member.art` im Verzeichnis — bei „beratend" bleibt `faction_timeline` leer. */
  kind: "council" | "advisory";
  organisation: string | null;
  n_sessions: number; active_from: string | null; active_to: string | null;
  /** Fraktions-/Gruppen-Verlauf aus der Anwesenheit: Phasen je Zugehörigkeit,
   *  älteste zuerst. `kind` unterscheidet Partei / (Rats-)Gruppe / parteilos;
   *  `parties` sind bei einer Gruppe ihre Mitglieds-Parteien. */
  faction_timeline: {
    label: string;
    kind: "party" | "group" | "independent";
    parties: string[];
    first: string;
    last: string;
    n: number;
  }[];
  /** Offizielle Stammdaten aus dem Ratsinfo (falls die Person dort verlinkt ist). */
  ris: {
    kpenr: number;
    name: string;
    current_faction: string | null;
    memberships: { kgrnr: number | null; committee: string; role: string | null; von: string | null; bis: string | null }[];
  } | null;
  committees: { committee: string; n: number; chair: boolean }[];
  recent: { ksinr: number; committee: string; session_date: string }[];
  /** Erste Seite der Wortbeiträge (volle Paraphrase); weitere holt
   *  /council/person/{slug}/speeches. */
  speeches?: { kind: string; agenda_item: string | null; text: string;
    committee: string | null; session_date: string }[];
  /** Wie viele Beiträge die Person insgesamt hat — die erste Seite ist ein
   *  Ausschnitt davon. */
  speeches_total?: number;
  /** Gremien mit Beitrags-Anzahl, Futter für den Filter. */
  speeches_committees?: { committee: string; n: number }[];
}

/** Schmaler Steckbrief für Verwaltungsleute mit erkanntem Amt (Tims Wunsch
 *  19.08.) — bewusst kein Nachbau von MemberDetail: kein Mandat, also keine
 *  Fraktions-Zeitleiste, kein Vorsitz-Zähler, keine Gremien-Präsenz. `von`/
 *  `bis` sind Jahre der Protokoll-Erwähnung, keine amtliche Amtszeit. */
export interface VerwaltungDetail {
  type: "administration";
  name: string; slug: string; role: string | null;
  aktiv: boolean; von: string | null; bis: string | null;
  speeches?: MemberDetail["speeches"];
  speeches_total?: number;
  speeches_committees?: { committee: string; n: number }[];
}

export type PersonProfil = MemberDetail | VerwaltungDetail;

/** Eine Station der offiziellen Beratungsfolge einer Vorlage. */
export type Beratung = S["DeliberationStation"];

export type ImportanceBreakdown = S["ImportanceBreakdown"];

export interface DecisionDetail {
  decision: CouncilDecision;
  /** Aufschlüsselung, warum der Beschluss als wichtig gilt. */
  importance_breakdown?: ImportanceBreakdown | null;
  attendance: Attendee[];
  present_parties: string[];
  sub_votes: CouncilDecision[];
  template_journey: VorlageStop[];
  /** Offizielle Beratungsfolge aus dem Ratsinfo — mit Ergebnis je Station und
   *  geplanten künftigen Beratungen. Fehlt, solange sie nicht gescrapt ist. */
  deliberation_path?: Beratung[];
  /** Design 28a/W1: Verfolgt dieses Konto den Vorgang? Fehlt, wenn der
   *  Beschluss zu keiner eingelesenen Vorlage gehört — dann gibt es nichts,
   *  woran ein Abo hängen könnte. */
  follow?: { kvonr: number; following: boolean };
  /** Stufe 3b: Läuft zu diesem Bauleitplan gerade eine Bürgerbeteiligung?
   *  Kommt von oldenburg.planungsbeteiligung.de, gematcht über die Plan-Nummer. */
  participation?: { title: string; schritt: string; valid_from: string | null;
                  valid_until: string | null; url: string;
                  /** "laufend" oder "beendet": Abgeschlossene Verfahren
                   *  loescht das Portal der Stadt spurlos — bei uns bleiben
                   *  sie als Beleg stehen (Historie seit 13.08.). */
                  status?: string; beendet_am?: string | null } | null;
  similar: SimilarDecision[];
  entities: Entity[];
  ratsinfo_url: string;
  template_url?: string | null;
  /** Eingelesener Vorlagen-Text (Sachverhalt/Begründung) zum Beschluss. */
  template?: {
    template_number: string | null;
    title: string | null;
    kind: string | null;
    document_url: string | null;
    n_pages: number | null;
    excerpt: string | null;
    /** Regex-Ernte: federführendes Amt aus dem Vorlagen-Kopf. */
    office?: string | null;
    /** Regex-Ernte: Klima-Check der Verwaltung („Auswirkungen: b) Klima"). */
    climate_impact?: string | null;
    klima_relevant?: boolean | null;
    /** „Finanzielle Auswirkungen" aus der Vorlage (amtlicher Wortlaut). */
    financial_impact?: string | null;
  } | null;
  /** Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht — belegt über
   *  eine echte Verknüpfung, nicht über eine Textsuche.
   *
   *  `null` heißt „nirgends nachweisbar", und die Seite lässt die Karte dann
   *  weg. Der pauschale Verweis auf `/haushalt` steht für jeden Beschluss
   *  gleich da und ist deshalb für keinen eine Auskunft; diese Karte gibt es
   *  nur, wo sie etwas sagt. */
  budget_link?: {
    art: "nachbewilligung" | "buergschaft";
    href: string;
    title: string;
    template_number: string;
    year?: number | null;
    amount?: number | null;
  } | null;
  /** P1: document_id der gerenderten Planzeichnung — B-Plan-Beschlüsse
   *  zeigen sie als Bild statt nur als Anlagen-Download. */
  plan_image?: number | null;
  /** Anlagen der Vorlage (Anträge zuerst, mit erkannten Antragstellern). */
  anlagen?: {
    document_id: number;
    label: string | null;
    url: string | null;
    is_motion: number;
    applicants: string[];
    status: string;
    /** 1 = Planzeichnung gerendert (scripts/render_plaene.py). */
    bild?: number;
  }[];
}

export type Topic = S["TopicOut"];

export type TopicHit = S["TopicHitOut"];

/** Ein Gremium samt dem, was die Abo-Seite darüber zeigt. `next_date` fehlt,
 *  solange das Ratsinfo keinen Termin führt — dann bleibt die Zeile leer,
 *  statt einen zu erfinden. */
export type CommitteeDetail = S["CommitteeDetail"];

export type TopicDecision = S["TopicDecision"];

export interface FieldRecap {
  policy_field: string;
  field_label: string;
  summary: string;
  n_decisions: number;
  period_from: string;
  period_to: string;
  generated_at: string;
}

export type WebUser = S["WebUserOut"];

export interface AdminStats {
  web_users: { total: number; admins: number; active: number; pending: number };
  topics: { total: number; users_with_topics: number; subscriptions: number };
  council: { sessions: number; upcoming: number; agenda_items: number; committees: number };
}

/** Eingegangenes Nutzer-Feedback im Admin-Panel. `read_at` null = offen. */
export type AdminFeedback = S["AdminFeedbackRow"];

export interface AdminUserDetail {
  id: number;
  email: string;
  /** Die stärkste Rolle. `roles` daneben ist die Wahrheit — das Panel
   *  bearbeitet die Liste, nicht diesen Wert. */
  role: string;
  roles: string[];
  status: "active" | "pending";
  created_at: string;
  last_seen: string | null;
  apple_linked: boolean;
  has_password: boolean;
  delivery_channel: string;
  /** Einwilligung „Gespräche speichern": null = nie gefragt, 1 = an, 0 = bewusst aus. */
  saves_conversations: number | null;
  /** Funktionsnutzung fürs Admin-Panel. Die Feldnamen dieses Blocks sind als
   * einzige noch deutsch, die gespeicherten Werte englisch — siehe
   * `admin_user_detail`. `quiz` zählt beantwortete Fragen, alles andere
   * Aufrufe. */
  features: {
    ki_frage: number; research: number; suche: number;
    quiz: number; analyse: number; karte: number;
  };
  topics: string[];
  subscriptions: string[];
  history: number[];
  /** ISO-Datum je Verlaufs-Balken (x-Achse, 30 Tage). */
  history_days: string[];
  /** Recherchen/Tag: null = Standard (5), 0 = unbegrenzt, sonst eigenes Limit. */
  deep_limit: number | null;
  /** true = Rate-Limits der Frage-Endpoints für dieses Konto aus. */
  limits_unlocked: boolean;
  /** Womit das Konto angelegt wurde (web | ios | android | app). null = vor
   *  Einführung der Messung registriert. */
  signup_client: string | null;
  /** Zugriffe je Client — {"web": 42, "ios": 7}. `unknown` steht für die
   *  Zeilen aus der Zeit vor der Messung und zählt nirgends als Plattform. */
  clients: Record<string, number>;
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
  /** Zugriffe je Client, letzte 30 Tage. `users` = Konten, für die dieser
   *  Client der meistgenutzte ist — jedes Konto zählt genau einmal. */
  clients: { client: string; n: number; users: number }[];
  /** Konten, die im Zeitraum mehrere Clients benutzt haben. */
  clients_both: number;
  /** Womit die vorhandenen Konten angelegt wurden (`users` bleibt hier 0). */
  signup_clients: { client: string; n: number; users: number }[];
}

// ---- Quiz ----
export type QuizAreaEntry = S["QuizArea"];
export type QuizAreas = S["QuizAreas"];
/** Eigene Quizfrage (RL-U14) — privat je Konto, mit Übungs-Zählern.
 *  qtype "estimate" (Kategorie „Schätzfrage") nutzt answer_value + Slider-Bereich
 *  statt Optionen. */
export type UserQuizQuestion = S["UserQuizQuestion"];
/** Eine Quizfrage OHNE Lösung — direkt aus dem API-Vertrag.
 *
 *  `source_type`/`source_ref` sind optional, weil die eigenen Übungsfragen
 *  (`/quiz/own/round`) ohne Quelle gebaut werden. Der frühere Handtyp verlangte
 *  sie und log damit über genau diesen Endpunkt. */
export type QuizQuestion = components["schemas"]["QuizQuestion"];
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
export type QuizStats = S["QuizScore"];
export type QuizDailyResult = S["QuizDailyResult"];
export type QuizDaily = S["QuizDailyRound"];
export type QuizFlagged = S["QuizFlaggedQuestion"];

/** Eine zusammengeführte Themen-Dublette (Admin). `alias_name` stammt aus den
 *  Roh-Beobachtungen — das Thema selbst gibt es nach dem Zusammenführen nicht mehr. */
export type EntityAlias = S["AdminEntityAlias"];
