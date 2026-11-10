// Kleine Bausteine, die Übersicht und Detailseite der Pläne teilen.

import { cn } from "@/lib/utils";
import { statusTone, type PlanCard, type PlanStatusNorm } from "@/lib/plans";

export function Kicker({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn("font-mono text-[10.5px] uppercase leading-snug tracking-[0.08em] text-muted-foreground", className)}>
      {children}
    </p>
  );
}

/** „in Arbeit“, „abgelöst durch …“, „Laufzeit vorbei“ — neutral getönt, nie
 *  rot (Plan § 3.4 Regel 5). Ein laufender Plan trägt kein Abzeichen: Das ist
 *  der Normalfall, und der braucht kein Etikett. */
export function StatusBadge({ plan, short = false, className }: {
  plan: Pick<PlanCard, "status" | "status_label" | "successor">;
  /** Nur das Wort, ohne den Namen des Nachfolgers — wo der daneben ohnehin steht. */
  short?: boolean;
  className?: string;
}) {
  const tone = statusTone(plan.status);
  if (tone === "none") return null;
  const text = !short && plan.status === "superseded" && plan.successor
    ? `abgelöst durch ${plan.successor.title}` : plan.status_label;
  return (
    <span className={cn("inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium",
      tone === "primary" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground", className)}>
      {text}
    </span>
  );
}

/** „Beschlossen“ ist nicht „Zur Kenntnis genommen“ (Regel 7): Grün trägt nur
 *  der Beschluss, die Kenntnisnahme den neutralen Tint. */
export function AdoptionBadge({ mode, className }: { mode: "adopted" | "noted" | null; className?: string }) {
  return (
    <span className={cn("inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
      mode === "adopted" ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300"
        : mode === "noted" ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary", className)}>
      {mode === "adopted" ? "Beschlossen" : mode === "noted" ? "Zur Kenntnis genommen" : "Noch nicht beschlossen"}
    </span>
  );
}

/** Tönung eines Maßnahmen-Kästchens je Stufe. Die Stufe dient nur dem Farbton —
 *  das Wort daneben ist immer das der Stadt. Grün trägt nur, was die Stadt
 *  selbst „umgesetzt“ oder „realisiert“ nennt; zurückgestellt ist neutral,
 *  nichts ist rot (Plan § 3.4 Regel 5). `none`: Die Stadt nennt keinen Stand. */
export const STATUS_SQUARE: Record<PlanStatusNorm | "none", string> = {
  open: "border-muted-foreground/40 bg-transparent",
  started: "border-primary/40 bg-primary/10",
  in_progress: "border-primary/60 bg-primary/45",
  done: "border-green-600/60 bg-green-600/70 dark:border-green-500/60 dark:bg-green-500/60",
  paused: "border-muted-foreground/40 bg-muted-foreground/25",
  unclear: "border-dashed border-muted-foreground/50 bg-transparent",
  none: "border-dashed border-muted-foreground/40 bg-transparent",
};

/** Der Stand einer Maßnahme im Wortlaut der Stadt. */
export function StatusChip({ raw, norm, className }: { raw: string; norm: PlanStatusNorm | null; className?: string }) {
  return (
    <span className={cn("inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
      norm === "done" ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300"
        : norm === "in_progress" || norm === "started" ? "bg-primary/10 text-primary"
          : "bg-muted text-muted-foreground", className)}>
      {raw}
    </span>
  );
}
