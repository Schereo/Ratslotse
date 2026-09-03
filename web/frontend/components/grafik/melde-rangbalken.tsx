import type { ProblemFrequency } from "@/lib/probleme";

/**
 * Proportionale Null-bis-Max-Schiene für die „Meistgemeldet“-Rangliste.
 *
 * Die Fülllänge bleibt immer mathematisch wahr. Insbesondere gibt es keine
 * Mindestbreite, die kleine Werte gegenüber großen optisch aufbläht; die
 * exakte, lesbare Zahl steht in der aufrufenden Rangzeile.
 */
export function MeldeRangbalken({
  wert,
  maximum,
  haeufigkeit,
}: {
  wert: number;
  maximum: number;
  haeufigkeit: ProblemFrequency;
}) {
  const anteil = maximum > 0 ? Math.min(1, Math.max(0, wert / maximum)) : 0;

  return (
    <span className="block h-1.5 overflow-hidden rounded-full bg-primary/8" aria-hidden>
      <span
        className={`problem-rank-bar frequency-${haeufigkeit} block h-full rounded-full bg-[var(--problem-frequency)]`}
        style={{ width: `${anteil * 100}%` }}
      />
    </span>
  );
}
