import type { ApiAntwort } from "./vertrag";

export type PrivateReport = ApiAntwort<"/meldungen/{report_id}">;
export type ReportCategory = PrivateReport["category"];
export type ReportScope = PrivateReport["scope_kind"];

export type ReportContent = {
  text: string;
  category: ReportCategory | "";
  scope_kind: ReportScope | null;
  observed_on: string;
  location_label: string;
  latitude: number | null;
  longitude: number | null;
};

export type ReportStage = "scope" | "location" | "date" | "category" | "description" | "review";

export type ProblemReportSession = {
  version: 1;
  ownerId: number;
  savedAt: number;
  stage: ReportStage;
  idempotencyKey: string;
  reportId: number | null;
  content: ReportContent;
};

export const PROBLEM_REPORT_SESSION_KEY = "ratslotse:private-problemmeldung:v1";
export const PROBLEM_REPORT_SESSION_TTL_MS = 30 * 60 * 1_000;

const STAGES: ReportStage[] = ["scope", "location", "date", "category", "description", "review"];
const SCOPES: ReportScope[] = ["point", "facility", "route", "area", "citywide"];
const CATEGORIES: ReportCategory[] = [
  "mobility",
  "public_space",
  "education",
  "childcare",
  "housing",
  "environment",
  "accessibility",
  "administration",
  "other",
];
const IDEMPOTENCY_KEY = /^[A-Za-z0-9._:-]{8,128}$/;

function finiteCoordinate(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}

function isContent(value: unknown): value is ReportContent {
  if (!value || typeof value !== "object") return false;
  const content = value as Partial<ReportContent>;
  return (
    typeof content.text === "string"
    && content.text.length <= 4000
    && (content.category === "" || CATEGORIES.includes(content.category as ReportCategory))
    && (content.scope_kind === null || SCOPES.includes(content.scope_kind as ReportScope))
    && typeof content.observed_on === "string"
    && content.observed_on.length <= 10
    && typeof content.location_label === "string"
    && content.location_label.length <= 200
    && (content.latitude === null || finiteCoordinate(content.latitude, 53.05, 53.24))
    && (content.longitude === null || finiteCoordinate(content.longitude, 8.08, 8.33))
  );
}

function clearStoredSession(): void {
  try {
    sessionStorage.removeItem(PROBLEM_REPORT_SESSION_KEY);
  } catch {
    // Private browsing may make web storage unavailable. Recovery is optional.
  }
}

export function loadProblemReportSession(
  ownerId: number,
  now = Date.now(),
): ProblemReportSession | null {
  try {
    const raw = sessionStorage.getItem(PROBLEM_REPORT_SESSION_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Partial<ProblemReportSession>;
    const valid = (
      saved.version === 1
      && saved.ownerId === ownerId
      && typeof saved.savedAt === "number"
      && now >= saved.savedAt
      && now - saved.savedAt <= PROBLEM_REPORT_SESSION_TTL_MS
      && typeof saved.stage === "string"
      && STAGES.includes(saved.stage as ReportStage)
      && typeof saved.idempotencyKey === "string"
      && IDEMPOTENCY_KEY.test(saved.idempotencyKey)
      && (saved.reportId === null || (typeof saved.reportId === "number" && Number.isSafeInteger(saved.reportId) && saved.reportId > 0))
      && isContent(saved.content)
    );
    if (!valid) {
      clearStoredSession();
      return null;
    }
    return saved as ProblemReportSession;
  } catch {
    clearStoredSession();
    return null;
  }
}

export function saveProblemReportSession(session: ProblemReportSession): void {
  try {
    sessionStorage.setItem(PROBLEM_REPORT_SESSION_KEY, JSON.stringify(session));
  } catch {
    // The report still works without optional browser recovery.
  }
}

export function clearProblemReportSession(): void {
  clearStoredSession();
}

export function scheduleProblemReportSessionExpiry(savedAt: number): () => void {
  const delay = Math.max(0, savedAt + PROBLEM_REPORT_SESSION_TTL_MS - Date.now());
  const timeout = window.setTimeout(clearStoredSession, delay);
  return () => window.clearTimeout(timeout);
}
