import type { ReactNode } from "react";
import type { ProblemFrequency } from "@/lib/probleme";

/**
 * Gemeinsamer Rahmen der Ranglisten-Grafik. Die Seite liefert den Beleg,
 * weil nur sie die Herkunft ihrer Daten kennt; das Grafikmodul hält ihn als
 * sichtbare Quellenzeile unmittelbar bei allen Balken (GB-00).
 */
export function MeldeRanglisteGrafik({
  children,
  beleg,
}: {
  children: ReactNode;
  beleg: ReactNode;
}) {
  return (
    <figure>
      <ol className="space-y-2.5" aria-label="Meistgemeldete ungelöste Probleme">
        {children}
      </ol>
      <figcaption className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        {beleg}
      </figcaption>
    </figure>
  );
}

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
