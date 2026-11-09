/** Die Uhr der Fortschrittskarte („Gründliche Recherche").
 *
 *  Der Server stempelt jeden Rahmen mit der Laufzeit des Jobs (`elapsed`) und
 *  die Fortschrittsrahmen mit einer Restzeit-Schätzung (`remaining`, Sekunden
 *  bis der Bericht zu erscheinen beginnt). Geschätzt wird dort, weil nur der
 *  Server weiß, wie schnell er gerade ist: Am 09.11.2026 brauchte dieselbe
 *  Recherche auf Prod rund 50 s und auf dev 100 s (`deepresearch.py`,
 *  `remaining_seconds`). Hier wird nur zwischen zwei Rahmen weitergezählt.
 */

export type DeepTiming = {
  /** Geschätzter Start des Jobs in der LOKALEN Uhr (ms). */
  start: number;
  /** Letzte Restzeit-Schätzung des Servers (s) … */
  remaining: number | null;
  /** … und die Laufzeit des Jobs, zu der sie galt (s). */
  remainingAt: number | null;
};

/** Zeitbasis aus einem Rahmen fortschreiben.
 *
 *  Beim Wiederverbinden kommen die bisherigen Rahmen gebündelt noch einmal;
 *  nimmt man ihren Empfang als „jetzt", wirkt der Job jünger, als er ist. Der
 *  früheste Start über alle Rahmen ist deshalb der richtige — ein live
 *  empfangener Rahmen ist höchstens ein paar Millisekunden alt. */
export function nextTiming(
  prev: DeepTiming | undefined,
  elapsed: number,
  remaining: number | null,
  now: number = Date.now(),
): DeepTiming {
  const start = Math.min(prev?.start ?? Infinity, now - elapsed * 1000);
  if (remaining === null) {
    return { start, remaining: prev?.remaining ?? null, remainingAt: prev?.remainingAt ?? null };
  }
  return { start, remaining, remainingAt: elapsed };
}

/** Laufzeit, verbleibende Zeit (kann negativ werden) und Balken in Prozent. */
export function timeline(timing: DeepTiming, now: number = Date.now()) {
  const elapsed = Math.max(0, (now - timing.start) / 1000);
  if (timing.remaining === null || timing.remainingAt === null) {
    return { elapsed, rest: null, percent: null };
  }
  const rest = timing.remaining - (elapsed - timing.remainingAt);
  // Der Balken folgt der Schätzung: verstrichen / (verstrichen + Rest). Er
  // bleibt unter 97 %, bis der Bericht wirklich kommt.
  const percent = Math.min(97, Math.max(4, (elapsed / (elapsed + Math.max(rest, 1))) * 100));
  return { elapsed, rest, percent };
}

/** „0:42" */
export function clock(seconds: number): string {
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Die Restzeit in Worten — gerundet, weil eine Schätzung keine Sekunden
 *  verspricht. Läuft sie deutlich über, sagt die Karte das, statt bei
 *  „gleich fertig" stehenzubleiben. */
export function restLabel(rest: number | null): string {
  if (rest === null) return "dauert etwa eine Minute";
  if (rest < -20) return "dauert länger als sonst";
  if (rest <= 3) return "gleich fertig";
  if (rest >= 55) return `noch ~${Math.max(1, Math.round(rest / 60))} Min`;
  return `noch ~${Math.max(5, Math.round(rest / 5) * 5)} Sek`;
}
