// RL-U10 (Design 10a): „Live" = Sitzungs-Startzeit erreicht, bis Start + 4 h —
// rein aus den vorhandenen Kalenderdaten. Welcher TOP gerade dran ist, weiß
// das Ratsinfo nicht; Ergebnisse folgen wie gehabt mit dem Protokoll.
// O1 (oldenburg eins) überträgt ausschließlich Ratssitzungen.

export const O1_STREAM_URL = "https://oeins.de/tv-stream/";
export const LIVE_WINDOW_HOURS = 4;

/** Nur der Stadtrat läuft im O1-Stream. */
export const isStadtrat = (committee: string) => /^(stadt)?rat$/i.test(committee.trim());

/** Heutiges Datum als lokales ISO (toISOString wäre UTC — nachts falsch). */
export function localTodayISO(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

/** Läuft eine HEUTIGE Sitzung mit dieser Startzeit ("HH:MM") gerade? */
export function isLiveTodayTime(sessionTime: string | null | undefined, now: Date = new Date()): boolean {
  if (!sessionTime) return false;
  const [h, m] = sessionTime.split(":").map(Number);
  if (!Number.isFinite(h)) return false;
  const start = new Date(now);
  start.setHours(h, Number.isFinite(m) ? m : 0, 0, 0);
  const diff = now.getTime() - start.getTime();
  return diff >= 0 && diff <= LIVE_WINDOW_HOURS * 3_600_000;
}

/** Minuten seit Sitzungsbeginn (nur sinnvoll, wenn live). */
export function minutesSinceTime(sessionTime: string, now: Date = new Date()): number {
  const [h, m] = sessionTime.split(":").map(Number);
  const start = new Date(now);
  start.setHours(h, Number.isFinite(m) ? m : 0, 0, 0);
  return Math.max(0, Math.floor((now.getTime() - start.getTime()) / 60_000));
}

/** Läuft diese Sitzung (Datum + Startzeit) gerade? */
export function isLiveNow(
  s: { session_date: string; session_time?: string | null },
  now: Date = new Date(),
): boolean {
  if (String(s.session_date).slice(0, 10) !== localTodayISO(now)) return false;
  return isLiveTodayTime(s.session_time, now);
}
