// Kleine Bausteine, die Übersicht und Detailseite der Pläne teilen.

import { cn } from "@/lib/utils";
import { statusTone, type PlanCard } from "@/lib/plans";

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
