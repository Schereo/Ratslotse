export const PROBLEM_REPORT_DRAFT_STORAGE = "ratslotse:private-problemmeldung";
const MAX_AGE_MS = 30 * 60 * 1_000;
let expiryTimer: ReturnType<typeof setTimeout> | null = null;

export function clearProblemReportDraft(): void {
  if (expiryTimer !== null) {
    clearTimeout(expiryTimer);
    expiryTimer = null;
  }
  try { sessionStorage.removeItem(PROBLEM_REPORT_DRAFT_STORAGE); } catch { /* optional */ }
}

/** Keep expiry active while navigating elsewhere in the same app/tab. */
export function scheduleProblemReportDraftExpiry(): void {
  if (typeof window === "undefined") return;
  if (expiryTimer !== null) clearTimeout(expiryTimer);
  expiryTimer = null;
  try {
    const raw = sessionStorage.getItem(PROBLEM_REPORT_DRAFT_STORAGE);
    if (!raw) return;
    const savedAt = Number((JSON.parse(raw) as { savedAt?: unknown }).savedAt);
    const remaining = MAX_AGE_MS - (Date.now() - savedAt);
    if (!Number.isFinite(savedAt) || remaining <= 0) {
      clearProblemReportDraft();
      return;
    }
    expiryTimer = setTimeout(clearProblemReportDraft, remaining);
  } catch {
    clearProblemReportDraft();
  }
}
