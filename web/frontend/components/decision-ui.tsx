import { CouncilDecision, DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

// Short labels for the policy-field badge (full labels come from /council/fields).
// Mirrors council.topics.POLICY_FIELDS.
export const POLICY_FIELD_LABELS: Record<string, string> = {
  verkehr: "Verkehr",
  klima_umwelt: "Klima & Umwelt",
  bauen_wohnen: "Bauen & Wohnen",
  soziales_gesundheit: "Soziales",
  bildung: "Bildung",
  finanzen: "Finanzen",
  kultur_sport: "Kultur & Sport",
  wirtschaft: "Wirtschaft",
  sicherheit_ordnung: "Sicherheit",
  verwaltung_digital: "Verwaltung",
  migration_integration: "Migration",
  sonstiges: "Sonstiges",
};

export function FieldBadge({ field, className }: { field: string | null; className?: string }) {
  if (!field) return null;
  return (
    <span className={cn("inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground", className)}>
      {POLICY_FIELD_LABELS[field] ?? field}
    </span>
  );
}

export const OUTCOME_META: Record<DecisionOutcome, { label: string; cls: string }> = {
  angenommen: { label: "Angenommen", cls: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300" },
  abgelehnt: { label: "Abgelehnt", cls: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
  vertagt: { label: "Vertagt", cls: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300" },
  zur_kenntnis: { label: "Zur Kenntnis", cls: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300" },
  kein_beschluss: { label: "Kein Beschluss", cls: "bg-muted text-muted-foreground" },
};

export function OutcomeBadge({ outcome }: { outcome: DecisionOutcome | null }) {
  if (!outcome) return null;
  const m = OUTCOME_META[outcome] ?? OUTCOME_META.kein_beschluss;
  return (
    <span className={cn("shrink-0 whitespace-nowrap rounded-md px-2.5 py-0.5 text-xs font-medium", m.cls)}>
      {m.label}
    </span>
  );
}

/** Aggregate vote visualisation. The protocols record totals (Gegenstimmen /
 *  Enthaltungen), not per-party votes, so "Mehrheit" is the unlabelled rest. */
export function VoteBar({ d, presentCount }: { d: CouncilDecision; presentCount?: number }) {
  const gegen = d.gegenstimmen ?? 0;
  const enth = d.enthaltungen ?? 0;
  const unanimous = d.vote === "einstimmig" || (gegen === 0 && enth === 0);

  if (unanimous) {
    return (
      <div>
        <div className="h-3 rounded-full bg-green-500/80" />
        <p className="mt-1.5 text-xs text-muted-foreground">Einstimmig</p>
      </div>
    );
  }
  // No per-vote roll-call → approximate the majority block so the bar is readable.
  const ja = presentCount && presentCount > gegen + enth ? presentCount - gegen - enth : (gegen + enth) * 3;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full">
        <div className="bg-green-500/80" style={{ flexGrow: Math.max(ja, 1) }} />
        {gegen > 0 && <div className="bg-red-500/80" style={{ flexGrow: gegen }} />}
        {enth > 0 && <div className="bg-amber-500/80" style={{ flexGrow: enth }} />}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><Dot cls="bg-green-500/80" /> Mehrheit</span>
        {gegen > 0 && <span className="inline-flex items-center gap-1.5"><Dot cls="bg-red-500/80" /> {gegen} Gegenstimmen</span>}
        {enth > 0 && <span className="inline-flex items-center gap-1.5"><Dot cls="bg-amber-500/80" /> {enth} Enthaltungen</span>}
      </div>
    </div>
  );
}

function Dot({ cls }: { cls: string }) {
  return <span className={cn("inline-block h-2 w-2 rounded-sm", cls)} />;
}
