// RL-U10 (Design 10a): „Live" = Startzeit erreicht, Ende noch nicht — rein aus
// den vorhandenen Kalenderdaten. Welcher TOP gerade dran ist, weiß das
// Ratsinfo nicht; Ergebnisse folgen wie gehabt mit dem Protokoll. O1
// (oldenburg eins) überträgt ausschließlich Ratssitzungen.
//
// **Das Ende rechnet der Server** und liefert es je Sitzung als `live_until`
// (`council/live.py`): entweder die nächste Sitzung desselben Tages — an
// Ratstagen tagen 16:00 Ausschuss für Allgemeine Angelegenheiten, 16:30
// Verwaltungsausschuss und 18:00 Rat NACHEINANDER im selben Haus, sie warten
// aufeinander (Tims Befund 31.08.2026) — oder ein Deckel ab Beginn: drei
// Stunden für Ausschüsse, vier für den Rat.
//
// Hier bleibt nur der Uhrenvergleich (die Uhr der Nutzerin kennt der Server
// nicht) und derselbe Deckel als Rückfall für Antworten, die `live_until`
// noch nicht kennen — etwa eine aus dem Cache.

export const O1_STREAM_URL = "https://oeins.de/tv-stream/";
export const LIVE_CAP_HOURS = 3;
export const LIVE_CAP_HOURS_COUNCIL = 4;

/** Was zum Beurteilen des Live-Fensters reicht. */
export type LiveSession = {
  committee?: string | null;
  session_time?: string | null;
  /** Ende des Live-Fensters ("HH:MM"), vom Server gerechnet. */
  live_until?: string | null;
};

/** Nur der Stadtrat läuft im O1-Stream — und tagt am längsten.
 *  Die Schreibweisen decken sich mit `council.live._COUNCIL_NAMES`: im
 *  Bestand steht schlicht „Rat", der Kalender kennt auch „Rat der Stadt". */
export const isStadtrat = (committee: string | null | undefined) =>
  /^((stadt)?rat|rat der stadt( oldenburg)?)$/i.test((committee ?? "").trim());

/** Heutiges Datum als lokales ISO (toISOString wäre UTC — nachts falsch). */
export function localTodayISO(now: Date = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

/** „HH:MM" als Zeitpunkt am Tag von `now` — null, wenn unlesbar oder leer. */
export function timeOnDay(hhmm: string | null | undefined, now: Date = new Date()): Date | null {
  if (!hhmm) return null;
  const [h, m] = hhmm.split(":").map(Number);
  if (!Number.isFinite(h)) return null;
  const d = new Date(now);
  d.setHours(h, Number.isFinite(m) ? m : 0, 0, 0);
  return d;
}

/** Läuft diese HEUTIGE Sitzung gerade? */
export function isLive(s: LiveSession, now: Date = new Date()): boolean {
  const start = timeOnDay(s.session_time, now);
  if (!start || now < start) return false;
  const ende = timeOnDay(s.live_until, now);
  // Auf die Minute, ohne Lücke und ohne Überlappung: Um 16:30 ist der
  // Ausschuss aus und der Verwaltungsausschuss an.
  if (ende && ende > start) return now < ende;
  const stunden = isStadtrat(s.committee) ? LIVE_CAP_HOURS_COUNCIL : LIVE_CAP_HOURS;
  return now.getTime() - start.getTime() <= stunden * 3_600_000;
}

/** Minuten seit Sitzungsbeginn (nur sinnvoll, wenn live). */
export function minutesSinceTime(sessionTime: string, now: Date = new Date()): number {
  const start = timeOnDay(sessionTime, now);
  if (!start) return 0;
  return Math.max(0, Math.floor((now.getTime() - start.getTime()) / 60_000));
}

/** Laufzeit als Text: „7 Minuten", „1 Stunde", „2,5 Stunden".
 *
 * Ab einer Stunde wird umgerechnet, sonst riss die Zeile um: „Live · seit 134
 * Minuten" brauchte zwei Zeilen und schob den Ort aus der Flucht (Tims Befund
 * 19.08.26). Halbe Stunden reichen als Auflösung — auf die Minute genau
 * interessiert es niemanden, und „2,5 Stunden" bleibt kurz.
 */
export function runningTimeText(sessionTime: string, now: Date = new Date()): string {
  const mins = minutesSinceTime(sessionTime, now);
  if (mins < 60) return `${mins} ${mins === 1 ? "Minute" : "Minuten"}`;
  const halbe = Math.round(mins / 30) / 2;      // 1, 1.5, 2, 2.5 …
  if (halbe === 1) return "1 Stunde";
  return `${String(halbe).replace(".", ",")} Stunden`;
}

/** Läuft diese Sitzung (Datum + Startzeit) gerade? */
export function isLiveNow(
  s: { session_date: string } & LiveSession,
  now: Date = new Date(),
): boolean {
  if (String(s.session_date).slice(0, 10) !== localTodayISO(now)) return false;
  return isLive(s, now);
}

/** Die Sitzung EINES Tages, die gerade läuft — höchstens eine.
 *
 * Bei mehreren Kandidatinnen gewinnt die zuletzt begonnene: Sie hat die
 * vorige abgelöst. Das greift auch, wenn `live_until` fehlt (ältere
 * API-Antwort aus dem Cache) — dann steht im Banner wenigstens die richtige
 * von beiden.
 */
export function currentSession<T extends LiveSession>(
  sessions: T[] | undefined,
  now: Date = new Date(),
): T | undefined {
  let laufend: T | undefined;
  let begonnen = -Infinity;
  for (const s of sessions ?? []) {
    if (!isLive(s, now)) continue;
    const start = timeOnDay(s.session_time, now)?.getTime() ?? -Infinity;
    if (start > begonnen) [laufend, begonnen] = [s, start];
  }
  return laufend;
}

/** Wie `currentSession`, aber über eine Liste mit Sitzungen mehrerer Tage. */
export function currentSessionToday<T extends { session_date: string } & LiveSession>(
  sessions: T[] | undefined,
  now: Date = new Date(),
): T | undefined {
  const heute = localTodayISO(now);
  return currentSession((sessions ?? []).filter((s) => String(s.session_date).slice(0, 10) === heute), now);
}
