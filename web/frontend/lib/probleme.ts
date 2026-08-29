import type { ProblemFrequency, PublicProblem } from "@/lib/types";

/** Sichtbare Produktbezeichnung; interne Domänenbegriffe und URLs bleiben stabil. */
export const PROBLEM_ANGEBOT = {
  name: "Probleme in Oldenburg",
  navigation: "Probleme",
} as const;

export const PROBLEM_KATEGORIEN = {
  mobility: "Mobilität & Verkehr",
  public_space: "Öffentlicher Raum",
  education: "Schule & Bildung",
  childcare: "Kinderbetreuung",
  housing: "Wohnen",
  environment: "Umwelt & Grün",
  accessibility: "Barrierefreiheit",
  administration: "Verwaltung",
  other: "Sonstiges kommunales Thema",
} as const;

export const PROBLEM_STATUS = {
  new: { label: "Neu", color: "slate" as const },
  multiple_reports: { label: "Mehrfach gemeldet", color: "blue" as const },
  verified: { label: "Geprüft", color: "blue" as const },
  persists: { label: "Weiterhin vorhanden", color: "slate" as const },
  apparently_resolved: { label: "Offenbar behoben", color: "slate" as const },
} as const;

export const PROBLEM_CONFIDENCE = {
  unconfirmed: "Noch unbestätigt",
  supported: "Durch mehrere Beobachtungen gestützt",
  verified: "Von Ratslotse geprüft",
} as const;

export const PROBLEM_SCOPE = {
  point: "Punkt",
  facility: "Einrichtung",
  route: "Route",
  area: "Gebiet",
  citywide: "Stadtweit",
} as const;

export type MeldeHaeufigkeit = ProblemFrequency;

export const MELDE_HAEUFIGKEIT: Record<ProblemFrequency, string> = {
  once: "einmal gemeldet",
  several: "mehrfach gemeldet",
  many: "häufig gemeldet",
  very_many: "sehr häufig gemeldet",
};

/** Grobe Häufigkeit für lokale Vorschau-Daten. Die API liefert sie bereits. */
export function unabhaengigeMeldungen(anzahl: number): string {
  return `${anzahl} unabhängige ${anzahl === 1 ? "Meldung" : "Meldungen"}`;
}

export function meldeHaeufigkeit(uniqueReporters: number): ProblemFrequency {
  if (uniqueReporters < 1) throw new Error("Veröffentlichte Probleme benötigen mindestens eine Meldung.");
  if (uniqueReporters === 1) return "once";
  if (uniqueReporters <= 4) return "several";
  if (uniqueReporters <= 9) return "many";
  return "very_many";
}

/**
 * Ausschließlich für Vercel-Preview-Deployments: frei erfundene Datensätze,
 * damit die erste Kartenoberfläche ohne passenden Preview-Backend-Branch
 * visuell und auf Touch-Geräten geprüft werden kann.
 */
export const VORSCHAU_PROBLEME: PublicProblem[] = [
  {
    id: 9001,
    title: "Beispiel: Dunkler Fußweg am Kanal",
    summary: "Auf einem häufig genutzten Abschnitt fehlt abends eine durchgängige Beleuchtung. Die Beispieldaten zeigen, wie mehrere private Beobachtungen öffentlich zusammengefasst würden.",
    category: "public_space",
    tags: ["Beleuchtung", "Fußweg"],
    scope_kind: "point",
    location_label: "Beispielort · Innenstadt",
    latitude: 53.1399,
    longitude: 8.2148,
    geometry: null,
    status: "multiple_reports",
    frequency: "many",
    confidence: "supported",
    independent_reports: 6,
    last_observed_at: "2026-08-26T18:20:00+00:00",
    published_at: "2026-06-05T12:00:00+00:00",
    updated_at: "2026-08-27T08:00:00+00:00",
    events: [
      { kind: "response", title: "Beispielhafte öffentliche Rückmeldung", detail: "Eine frei erfundene externe Reaktion mit klar gekennzeichneter Rolle und Quelle.", source_kind: "Stadtverwaltung", source_url: "https://example.invalid/fiktive-quelle", event_at: "2026-08-26T18:20:00+00:00" },
      { kind: "published", title: "Problem veröffentlicht", detail: "Aus mehreren privaten Meldungen zusammengefasst.", source_kind: "Ratslotse-Prüfung", source_url: null, event_at: "2026-06-05T12:00:00+00:00" },
    ],
  },
  {
    id: 9002,
    title: "Beispiel: Fahrradständer regelmäßig überfüllt",
    summary: "Zu typischen Pendelzeiten reichen die vorhandenen Abstellplätze nicht aus; Fahrräder werden an Wegen und Geländern abgestellt.",
    category: "mobility",
    tags: ["Fahrrad", "Abstellen"],
    scope_kind: "facility",
    location_label: "Beispielort · Bahnhofsviertel",
    latitude: 53.1434,
    longitude: 8.2227,
    geometry: null,
    status: "verified",
    frequency: "very_many",
    confidence: "verified",
    independent_reports: 11,
    last_observed_at: "2026-08-29T07:45:00+00:00",
    published_at: "2026-05-14T09:30:00+00:00",
    updated_at: "2026-08-29T09:00:00+00:00",
    events: [
      { kind: "verified", title: "Community-Beobachtungen geprüft", detail: "Der Status beschreibt nur die Ratslotse-Prüfung, keine amtliche Bearbeitung.", source_kind: "Ratslotse-Prüfung", source_url: null, event_at: "2026-08-20T09:00:00+00:00" },
    ],
  },
  {
    id: 9003,
    title: "Beispiel: Barrierefreier Zugang zur Haltestelle fehlt",
    summary: "Der Zugang ist im Beispiel durch eine hohe Kante erschwert. Betroffen wären Menschen mit Rollstuhl, Rollator oder Kinderwagen.",
    category: "accessibility",
    tags: ["Haltestelle", "Zugang"],
    scope_kind: "point",
    location_label: "Beispielort · Eversten",
    latitude: 53.136,
    longitude: 8.187,
    geometry: null,
    status: "persists",
    frequency: "several",
    confidence: "supported",
    independent_reports: 4,
    last_observed_at: "2026-08-22T15:10:00+00:00",
    published_at: "2026-04-20T08:15:00+00:00",
    updated_at: "2026-08-23T07:50:00+00:00",
    events: [],
  },
  {
    id: 9005,
    title: "Beispiel: Lücke im Radweg",
    summary: "Auf diesem Beispielabschnitt endet die sichere Radverbindung unvermittelt.",
    category: "mobility",
    tags: ["Radweg", "Route"],
    scope_kind: "route",
    location_label: "Beispielroute · Innenstadt",
    latitude: null,
    longitude: null,
    geometry: {
      type: "LineString",
      coordinates: [[8.197, 53.142], [8.204, 53.143], [8.212, 53.141], [8.219, 53.144]],
    },
    status: "new",
    frequency: "several",
    confidence: "supported",
    independent_reports: 3,
    last_observed_at: "2026-08-27T17:00:00+00:00",
    published_at: "2026-08-21T10:00:00+00:00",
    updated_at: "2026-08-28T08:00:00+00:00",
    events: [],
  },
  {
    id: 9006,
    title: "Beispiel: Hitze im Quartier",
    summary: "Das Beispielgebiet heizt sich an Sommertagen stark auf und bietet wenig Schatten.",
    category: "environment",
    tags: ["Hitze", "Schatten"],
    scope_kind: "area",
    location_label: "Beispielgebiet · Innenstadt",
    latitude: null,
    longitude: null,
    geometry: {
      type: "Polygon",
      coordinates: [[
        [8.205, 53.135], [8.217, 53.135], [8.22, 53.142],
        [8.208, 53.144], [8.205, 53.135],
      ]],
    },
    status: "persists",
    frequency: "many",
    confidence: "supported",
    independent_reports: 7,
    last_observed_at: "2026-08-28T16:00:00+00:00",
    published_at: "2026-07-03T09:00:00+00:00",
    updated_at: "2026-08-28T17:00:00+00:00",
    events: [],
  },
  {
    id: 9004,
    title: "Beispiel: Zu wenig Betreuungsplätze",
    summary: "Dieses stadtweite Beispiel zeigt Probleme, die nicht ehrlich auf einen einzelnen Kartenpunkt reduziert werden können.",
    category: "childcare",
    tags: ["Kita", "Krippe"],
    scope_kind: "citywide",
    location_label: "Gesamtes Stadtgebiet",
    latitude: null,
    longitude: null,
    geometry: null,
    status: "multiple_reports",
    frequency: "very_many",
    confidence: "supported",
    independent_reports: 18,
    last_observed_at: "2026-08-28T13:00:00+00:00",
    published_at: "2026-03-05T10:00:00+00:00",
    updated_at: "2026-08-28T14:00:00+00:00",
    events: [],
  },
];
