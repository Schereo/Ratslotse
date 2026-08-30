/** Wohin Benachrichtigungen gehen — „off" heißt: gar nicht. */
export type DeliveryChannel = "email" | "both" | "push" | "off";

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
  /** Einwilligung „Gespräche merken": 1 = ja, 0 = nein, null = nie gefragt.
   *  Kommt mit dem Konto, damit die Frage-Seite die Erstnutzungs-Karte sofort
   *  richtig setzt statt sie nachzuschieben. */
  qa_speichern?: number | null;
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
  /** Dokument-Anhänge des TOP (RIS-PDFs) — ältere API-Antworten kennen das
   *  Feld nicht. */
  anlagen?: { label: string; url: string }[];
  /** Ein Satz, worum es geht — dieselbe KI-Zusammenfassung wie in der
   *  Tagesordnungs-Mail. Fehlt bei Routine-Punkten und alten Sitzungen. */
  summary?: string | null;
  /** Der bessere der beiden Sätze: aus Vorlage UND Anlagen geschrieben, nicht
   *  nur aus dem Titel (`agenda_item_social`). Deshalb stehen hier Angaben,
   *  die in keiner Überschrift vorkommen — „110 Wohneinheiten auf 8,6 Hektar".
   *  Gibt es nur für kommende Sitzungen; sonst bleibt `summary`. */
  social_text?: string | null;
  /** Ein Dringlichkeitsantrag — im Ratsinformationssystem hat er keinen
   *  eigenen Punkt, sondern hängt als Dokument an „Genehmigung der
   *  Tagesordnung". Der Ratslotse macht daraus eine eigene Zeile mit der
   *  Kennung `DZT n`; das Flag entscheidet der Server, nicht die Anzeige. */
  dringlich?: boolean;
}

export type DecisionOutcome =
  | "angenommen" | "abgelehnt" | "vertagt" | "zur_kenntnis" | "kein_beschluss";

export interface DecisionLocationMatch {
  name: string;
  stadtteil: string;
  place_id?: string | null;
  ortsbereich_id?: string | null;
  source: "title" | "beschluss" | "vorlage";
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
  /** Regex-Ernte: Wie stark weicht der Beschluss vom Verwaltungsvorschlag ab? */
  abweichung?: "unveraendert" | "leicht" | "stark" | null;
  /** Beim Ortsfilter: konkrete Treffer samt Fundstelle zur manuellen Prüfung. */
  location_matches?: DecisionLocationMatch[];
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
  /** Ratsgespräch-Bausteine (RG-04/05): Betrag und Antragsteller-Fraktionen,
   *  deterministisch aus den Beschluss-Metadaten. */
  amount_eur?: number | null;
  /** Kostenentwicklung: gleiche Vorlagen-Familie = belegbares Delta. */
  vorlage_nr?: string | null;
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
  /** „Zuletzt geändert"-Chronik der Tagesordnung, neueste zuerst — Ziel der
   *  Änderungs-Push; ältere Sitzungen (vor der Chronik) haben keine. */
  aenderungen?: AgendaAenderung[];
}

export type BookmarkKind = "session" | "agenda_item" | "decision";
export type BookmarkState = "upcoming" | "waiting" | "protocol" | "decided" | "saved" | "unavailable" | "group";

/** Persönlicher Merkeintrag, serverseitig gegen den aktuellen Ratsbestand
 *  aufgelöst. Ein agenda_item bekommt automatisch `decision`, sobald das
 *  Protokoll verarbeitet wurde. */
export interface BookmarkEntry {
  id: number;
  kind: BookmarkKind;
  target_key: string;
  title: string;
  subtitle: string;
  created_at: string;
  notify_result: boolean;
  result_notified_at: string | null;
  state: BookmarkState;
  url: string;
  ksinr: number | null;
  item_number: string | null;
  is_group: boolean;
  session: CouncilSession | null;
  agenda_item: AgendaItem | null;
  decision: CouncilDecision | null;
}

export interface AgendaAenderungZeile {
  art: "neu" | "geaendert" | "verschoben" | "vorlage" | "anlagen" | "entfernt";
  label: string;
  titel: string;
  nichtoeffentlich: boolean;
  detail: string | null;
}

export interface AgendaAenderung {
  changed_at: string;
  satz: string;
  zeilen: AgendaAenderungZeile[];
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
  ortsbereich_id?: string | null;
}

export interface PlaceCandidateEvidence {
  id: number; title: string | null; session_date: string;
  evidence: string; method: string; confidence: number;
}

export interface PlaceCandidate {
  slug: string; name: string; kind: string; lat: number | null; lon: number | null;
  stadtteil: string | null; ortsbereich_id: string | null;
  status: "pending" | "concrete" | "approved" | "alias" | "rejected";
  decision_count: number; last_date: string; avg_confidence: number;
  review_place_id?: string | null; review_name?: string | null;
  review_kind?: string | null; parent_id?: string | null; aliases?: string[];
  description?: string | null; source_url?: string | null;
  quiz_enabled?: boolean; canonical_place_id?: string | null; note?: string | null;
  evidence: PlaceCandidateEvidence[];
}

export interface EntityGeo {
  lat: number;
  lon: number;
  geojson: { type: string; coordinates: unknown } | null;
}

/** Ein verwandtes Thema (vorberechnet, council.related).
 *  `belegt` = kommt gemeinsam in Beschlüssen vor (`evidence` = in wie vielen),
 *  `aehnlich` = semantischer Nachbar aus den Embeddings, füllt nur auf. */
export interface RelatedEntity {
  slug: string;
  name: string;
  kind: string;
  n: number;
  rel_type: "belegt" | "aehnlich" | string;
  score: number;
  evidence: number;
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
  related?: RelatedEntity[];
}

export interface Member {
  slug: string; name: string; party: string | null;
  /** „rat" = Ratsmandat (im Plenum geführt oder im RIS als Ratsmitglied),
   *  „beratend" = beratendes Mitglied eines Ausschusses (Verband, Beirat,
   *  Fachperson) — dem Rat gehört es nicht an. */
  art: "rat" | "beratend";
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
  typ?: "rat";
  name: string; slug: string; party: string | null;
  /** Zugehörigkeit für den Seitenkopf — wie im Verzeichnis aufgelöst
   *  („FDP/Volt" → FDP, wo es belegt ist). Die Zeitreihe darunter bleibt
   *  quellentreu. */
  current_affiliation: { label: string; kind: "partei" | "gruppe" | "parteilos"; parties: string[] } | null;
  /** s. `Member.art` — bei „beratend" bleibt `faction_timeline` leer. */
  art: "rat" | "beratend";
  organisation: string | null;
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
  /** Erste Seite der Wortbeiträge (volle Paraphrase); weitere holt
   *  /council/person/{slug}/wortbeitraege. */
  wortbeitraege?: { art: string; top: string | null; text: string;
    committee: string | null; session_date: string }[];
  /** Wie viele Beiträge die Person insgesamt hat — die erste Seite ist ein
   *  Ausschnitt davon. */
  wortbeitraege_gesamt?: number;
  /** Gremien mit Beitrags-Anzahl, Futter für den Filter. */
  wortbeitraege_gremien?: { committee: string; n: number }[];
}

/** Schmaler Steckbrief für Verwaltungsleute mit erkanntem Amt (Tims Wunsch
 *  19.08.) — bewusst kein Nachbau von MemberDetail: kein Mandat, also keine
 *  Fraktions-Zeitleiste, kein Vorsitz-Zähler, keine Gremien-Präsenz. `von`/
 *  `bis` sind Jahre der Protokoll-Erwähnung, keine amtliche Amtszeit. */
export interface VerwaltungDetail {
  typ: "verwaltung";
  name: string; slug: string; rolle: string | null;
  aktiv: boolean; von: string | null; bis: string | null;
  wortbeitraege?: MemberDetail["wortbeitraege"];
  wortbeitraege_gesamt?: number;
  wortbeitraege_gremien?: { committee: string; n: number }[];
}

export type PersonProfil = MemberDetail | VerwaltungDetail;

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
  /** Design 28a/W1: Verfolgt dieses Konto den Vorgang? Fehlt, wenn der
   *  Beschluss zu keiner eingelesenen Vorlage gehört — dann gibt es nichts,
   *  woran ein Abo hängen könnte. */
  follow?: { kvonr: number; following: boolean };
  /** Stufe 3b: Läuft zu diesem Bauleitplan gerade eine Bürgerbeteiligung?
   *  Kommt von oldenburg.planungsbeteiligung.de, gematcht über die Plan-Nummer. */
  beteiligung?: { titel: string; schritt: string; von: string | null;
                  bis: string | null; url: string;
                  /** "laufend" oder "beendet": Abgeschlossene Verfahren
                   *  loescht das Portal der Stadt spurlos — bei uns bleiben
                   *  sie als Beleg stehen (Historie seit 13.08.). */
                  status?: string; beendet_am?: string | null } | null;
  similar: SimilarDecision[];
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
    /** Regex-Ernte: federführendes Amt aus dem Vorlagen-Kopf. */
    amt?: string | null;
    /** Regex-Ernte: Klima-Check der Verwaltung („Auswirkungen: b) Klima"). */
    klima_check?: string | null;
    klima_relevant?: boolean | null;
    /** „Finanzielle Auswirkungen" aus der Vorlage (amtlicher Wortlaut). */
    finanz_check?: string | null;
  } | null;
  /** Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht — belegt über
   *  eine echte Verknüpfung, nicht über eine Textsuche.
   *
   *  `null` heißt „nirgends nachweisbar", und die Seite lässt die Karte dann
   *  weg. Der pauschale Verweis auf `/haushalt` steht für jeden Beschluss
   *  gleich da und ist deshalb für keinen eine Auskunft; diese Karte gibt es
   *  nur, wo sie etwas sagt. */
  haushalts_anschluss?: {
    art: "nachbewilligung" | "buergschaft";
    href: string;
    titel: string;
    vorlage_nr: string;
    jahr?: number | null;
    betrag?: number | null;
  } | null;
  /** P1: document_id der gerenderten Planzeichnung — B-Plan-Beschlüsse
   *  zeigen sie als Bild statt nur als Anlagen-Download. */
  plan_bild?: number | null;
  /** Anlagen der Vorlage (Anträge zuerst, mit erkannten Antragstellern). */
  anlagen?: {
    document_id: number;
    label: string | null;
    url: string | null;
    is_antrag: number;
    antragsteller: string[];
    status: string;
    /** 1 = Planzeichnung gerendert (scripts/render_plaene.py). */
    bild?: number;
  }[];
}

export interface Topic {
  id: number;
  name: string;
  description: string;
  created_at: string;
  /** „Beschlüsse zu diesem Thema" — die gespeicherten Treffer des letzten
   *  Matching-Laufs (Definition: `council.topic_intel.treffer`). Dieselbe
   *  Menge, die `/council?tab=decisions&cat=all&topic=<id>` auflistet; wer
   *  die Zahl irgendwo anders herrechnet, baut die nächste Widersprüchlichkeit. */
  decision_count: number;
  /** Es gab mehr passende Beschlüsse, als der Matching-Lauf speichern durfte
   *  — die Karte schreibt dann „40+" statt einer Endzahl, die keine ist. Gilt
   *  genauso für die Trefferliste dahinter (view.tsx: `topicCapped`). */
  decision_count_capped?: boolean;
  /** Wurde für dieses Thema schon einmal abgeglichen? Trennt die zwei Nullen,
   *  die auf der Karte gleich aussahen: „gerechnet, der Rat hat dazu wirklich
   *  nichts entschieden" und „die Zahl steht noch aus". Fehlt das Feld (alte
   *  Antwort aus dem Cache), gilt die vorsichtigere erste Lesart. */
  matched?: boolean;
  last_hit_id?: number | null;
  last_hit_title?: string | null;
  last_hit_date?: string | null;
  unread_count?: number;
  /** Die jüngsten Treffer selbst (neueste zuerst, höchstens fünf). Die Karte
   *  zeigt sie direkt — vorher stand dort eine Zahl und ein einziger Titel,
   *  man musste also jedes Thema öffnen, um zu sehen, was drinsteht. */
  recent_hits?: TopicHit[];
  /** Treffer des letzten halben Jahres — sagt, ob ein Thema gerade läuft
   *  oder ruht. Die Gesamtzahl allein kann beides bedeuten. 30 Tage waren zu
   *  kurz: Die Gremien tagen monatlich, im Sommer gar nicht. */
  hits_6m?: number;
}

export interface TopicHit {
  id: number;
  title: string;
  committee: string;
  session_date: string;
  outcome: DecisionOutcome | null;
  /** Noch nicht gesehen — dieselbe Menge, die das „n neue"-Abzeichen zählt. */
  is_new: boolean;
}

/** Ein Gremium samt dem, was die Abo-Seite darüber zeigt. `next_date` fehlt,
 *  solange das Ratsinfo keinen Termin führt — dann bleibt die Zeile leer,
 *  statt einen zu erfinden. */
export interface CommitteeDetail {
  name: string;
  next_date: string | null;
  next_time: string | null;
  decisions_year: number;
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

/** Eingegangenes Nutzer-Feedback im Admin-Panel. `read_at` null = offen. */
export interface AdminFeedback {
  id: number;
  owner_id: number;
  email: string | null;
  kind: "feature" | "bug" | "other" | string;
  message: string;
  created_at: string;
  read_at: string | null;
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
  /** Einwilligung „Gespräche speichern": null = nie gefragt, 1 = an, 0 = bewusst aus. */
  qa_speichern: number | null;
  features: { ki_frage: number; suche: number; quiz: number; analyse: number; karte: number };
  topics: string[];
  abos: string[];
  verlauf: number[];
  /** ISO-Datum je Verlaufs-Balken (x-Achse, 30 Tage). */
  verlauf_days: string[];
  /** Recherchen/Tag: null = Standard (5), 0 = unbegrenzt, sonst eigenes Limit. */
  deep_limit: number | null;
  /** true = Rate-Limits der Frage-Endpoints für dieses Konto aus. */
  limits_frei: boolean;
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
  /** Stabile ID aus dem gemeinsamen Ratslotse-Ortskatalog. */
  place_id?: string;
  kind?: string;
  kind_label?: string;
  parent_ids?: string[];
  aliases?: string[];
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
