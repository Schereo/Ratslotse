/**
 * Wie eine Vorlage in ihrem Rat ausging — die acht Ergebnisse des
 * Städte-Speichers als Pille.
 *
 * Nicht `OutcomeBadge` aus `decision-ui.tsx`: Das kennt Oldenburgs fünf
 * Werte, die Städte liefern acht (geändert beschlossen, verwiesen,
 * zurückgezogen kommen dazu). Die Töne sind dieselben Semantik-Tints, über
 * `lib/zeitleiste.ts` an dieselbe Stufe gebunden wie der Punkt auf der
 * Zeitleiste — Pille und Punkt können nicht auseinanderlaufen.
 */
import { cn } from "@/lib/utils";
import { type Stufe, stufe } from "@/lib/zeitleiste";

export const ERGEBNIS_TEXT: Record<string, string> = {
  accepted: "Beschlossen",
  amended: "Geändert beschlossen",
  rejected: "Abgelehnt",
  postponed: "Vertagt",
  referred: "Verwiesen",
  noted: "Zur Kenntnis",
  withdrawn: "Zurückgezogen",
  none: "Ohne Ergebnis",
};

const TON: Record<Stufe, string> = {
  ok: "border-transparent bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300",
  no: "border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300",
  wait: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300",
  neu: "border-transparent bg-muted text-muted-foreground",
  open: "border-dashed border-border bg-transparent text-muted-foreground",
};

export function ErgebnisPille({ outcome, className }: { outcome: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        TON[stufe(outcome)],
        className,
      )}
    >
      {ERGEBNIS_TEXT[outcome] ?? ERGEBNIS_TEXT.none}
    </span>
  );
}
