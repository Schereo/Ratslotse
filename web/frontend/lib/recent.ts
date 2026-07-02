// Zuletzt angesehene Beschlüsse — rein client-seitig (localStorage, kein Backend).
// Wird auf der Beschluss-Detailseite geschrieben und auf dem Dashboard sowie in
// der Command-Palette gelesen.

export type RecentDecision = {
  id: number;
  title: string;
  committee: string;
  session_date: string;
  visitedAt: number;
};

const KEY = "ratslotse:recent-decisions";
const MAX = 8;

export function trackRecentDecision(d: Omit<RecentDecision, "visitedAt">): void {
  try {
    const next = [
      { ...d, visitedAt: Date.now() },
      ...getRecentDecisions().filter((r) => r.id !== d.id),
    ].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* Storage voll/gesperrt — Feature ist optional */
  }
}

export function getRecentDecisions(): RecentDecision[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as RecentDecision[]) : [];
  } catch {
    return [];
  }
}
