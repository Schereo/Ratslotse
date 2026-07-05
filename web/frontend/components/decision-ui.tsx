"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, Flame } from "lucide-react";
import { CouncilDecision, DecisionOutcome, ImportanceBreakdown } from "@/lib/types";
import { Card, formatDate } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

/** Format a euro amount compactly: 563.000 € / 3,4 Mio. €. */
export function formatEuro(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio. €`;
  return `${Math.round(n).toLocaleString("de-DE")} €`;
}

/** Compact clickable card linking to a decision's detail page — shared by the
 *  Q&A sources, "Ähnliche Beschlüsse" and goal decision lists. */
export function DecisionLinkCard({ id, title, committee, session_date, field, leading, sub, score, amount }: {
  id: number;
  title: string | null;
  committee: string;
  session_date: string;
  field?: string | null;
  leading?: React.ReactNode;
  sub?: string | null;
  score?: number;
  amount?: number | null;
}) {
  return (
    <Link href={decisionHref(id)} className="block">
      <Card className="card-interactive group flex items-start gap-3 p-3">
        {leading}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {field !== undefined && <FieldBadge field={field} />}
            <span className="text-xs text-muted-foreground">{committee} · {formatDate(session_date)}</span>
            {score !== undefined && (
              <span className="rounded bg-muted px-1.5 text-xs font-medium tabular-nums text-muted-foreground" title="Ähnlichkeit zur Frage">
                {Math.round(score * 100)}%
              </span>
            )}
            {amount != null && (
              <span className="rounded bg-emerald-500/10 px-1.5 text-xs font-semibold tabular-nums text-emerald-700 dark:text-emerald-400" title="Im Beschlusstext genannter Betrag">
                {formatEuro(amount)}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm font-medium text-foreground">{title}</p>
          {sub && <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{sub}</p>}
        </div>
        <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 self-center text-muted-foreground/40 group-hover:text-primary" />
      </Card>
    </Link>
  );
}

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
  const router = useRouter();
  if (!field) return null;
  return (
    <button
      type="button"
      title="Beschlüsse dieses Themenfelds"
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); router.push(`/council?tab=decisions&field=${field}`); }}
      className={cn("inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary/70", className)}
    >
      {POLICY_FIELD_LABELS[field] ?? field}
    </button>
  );
}

export const IMPORTANCE_HINT =
  "Geschätzte Wichtigkeit für die Stadt — aus Geldbetrag, Umstrittenheit (Gegenstimmen), Verbindlichkeit & Gremien-Ebene und Länge des Beratungswegs.";

/** Kompakter „Wichtig"-Chip für Listen — nur ab einer Schwelle sichtbar, damit
 *  nur wirklich bedeutende Beschlüsse hervorstechen (statt jede Karte zu füllen). */
export function ImportanceBadge({ score, minShow = 55, className }: {
  score?: number | null; minShow?: number; className?: string;
}) {
  if (score == null || score < minShow) return null;
  const strong = score >= 70;
  return (
    <span
      title={`Wichtigkeit ${score}/100 — ${IMPORTANCE_HINT}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold",
        strong ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
               : "bg-amber-500/10 text-amber-700/80 dark:text-amber-300/70",
        className,
      )}
    >
      <Flame className="h-3 w-3" /> Wichtig
    </span>
  );
}

const IMPORTANCE_SIGNAL_LABEL: Record<keyof ImportanceBreakdown["signals"], string> = {
  geld: "Geldbetrag", umstritten: "Umstrittenheit",
  verbindlich: "Verbindlichkeit & Ebene", aufwand: "Beratungsaufwand",
};

/** Ausführliche Wichtigkeits-Anzeige auf der Beschluss-Seite: Score + welche
 *  Signale ihn treiben — beantwortet transparent „woran macht man das fest?". */
export function ImportanceMeter({ score, signals, className }: {
  score: number;
  signals?: ImportanceBreakdown["signals"];
  className?: string;
}) {
  const keys = Object.keys(IMPORTANCE_SIGNAL_LABEL) as (keyof ImportanceBreakdown["signals"])[];
  return (
    <div className={cn("rounded-lg border border-border p-3", className)}>
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Flame className="h-4 w-4 text-amber-500" /> Wichtigkeit
        </span>
        <span className="text-sm font-semibold tabular-nums text-foreground">
          {score}<span className="text-muted-foreground">/100</span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-amber-500 transition-[width] duration-500" style={{ width: `${score}%` }} />
      </div>
      {signals && (
        <ul className="mt-3 space-y-1.5">
          {keys.map((k) => (
            <li key={k} className="flex items-center gap-2 text-xs">
              <span className="w-36 shrink-0 text-muted-foreground">{IMPORTANCE_SIGNAL_LABEL[k]}</span>
              {signals[k] == null ? (
                <span className="italic text-muted-foreground/60">keine Daten</span>
              ) : (
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full bg-amber-500/70" style={{ width: `${Math.round((signals[k] as number) * 100)}%` }} />
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{IMPORTANCE_HINT}</p>
    </div>
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

// Official party brand colours (bg + readable text) — a brand-accurate, logo-like
// chip for each faction. Not the trademarked logo artwork: just the party colour +
// its own short name, which keeps it legally clean and covers every faction. Local
// groups without an established brand colour fall back to the neutral badge.
const PARTY_BRAND: Record<string, { bg: string; fg: string }> = {
  "SPD": { bg: "#E3000F", fg: "#ffffff" },
  "CDU": { bg: "#16181d", fg: "#ffffff" },
  "Grüne": { bg: "#46962b", fg: "#ffffff" },
  "FDP": { bg: "#ffd400", fg: "#1a1a1a" },
  "AfD": { bg: "#009ee0", fg: "#ffffff" },
  "Volt": { bg: "#562883", fg: "#ffffff" },
  "Die Linke": { bg: "#be3075", fg: "#ffffff" },
  "BSW": { bg: "#7a1f2b", fg: "#ffffff" },
  "Piraten": { bg: "#ff7a00", fg: "#ffffff" },
};

// Map a raw or normalised faction name to the canonical short label (mirrors
// backend council.parties; WFO/LKR ist keine Partei und dort entfernt).
// Für Antragsteller-LISTEN liefert das Backend bereits Multi-Mapping
// („FDP/Volt" → beide) — dieses Single-Mapping dient Personen/Badges.
const PARTY_NORM: [string, string][] = [
  ["grün", "Grüne"], ["bsw", "BSW"], ["linke", "Die Linke"], ["piraten", "Piraten"],
  ["für oldenburg", "Für Oldenburg"],
  ["ibo", "IBO/LiVe"], ["spd", "SPD"], ["cdu", "CDU"], ["afd", "AfD"], ["fdp", "FDP"], ["volt", "Volt"],
];

export function normalizeParty(raw: string): string {
  const p = raw.toLowerCase();
  for (const [needle, label] of PARTY_NORM) if (p.includes(needle)) return label;
  return raw;
}

export function partyBrand(party: string): { bg: string; fg: string } | null {
  return PARTY_BRAND[normalizeParty(party)] ?? null;
}

export function PartyBadge({ party, className }: { party: string; className?: string }) {
  const router = useRouter();
  const brand = partyBrand(party);
  return (
    <button
      type="button"
      title={`Beschlüsse: ${party}`}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); router.push(`/council?tab=decisions&party=${encodeURIComponent(party)}`); }}
      style={brand ? { backgroundColor: brand.bg, color: brand.fg } : undefined}
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold transition-opacity hover:opacity-85",
        !brand && "border border-border font-medium text-foreground transition-colors hover:bg-muted",
        className,
      )}
    >
      {party}
    </button>
  );
}

/** Non-interactive faction + count chip (attendance lists), brand-coloured. */
export function PartyAttendanceBadge({ party, n }: { party: string; n: number }) {
  const brand = partyBrand(party);
  return (
    <span
      style={brand ? { backgroundColor: brand.bg, color: brand.fg } : undefined}
      className={cn("rounded-md px-2 py-0.5 text-xs font-medium", !brand && "bg-muted text-muted-foreground")}
    >
      {party} {n}
    </span>
  );
}

/** Aggregate vote visualisation. The protocols record totals (Gegenstimmen /
 *  Enthaltungen), not per-party votes. Colours follow the outcome — green = für
 *  den Antrag, red = dagegen — so the majority block is red for a rejected motion
 *  (its "Gegenstimmen" are then the outvoted minority that voted *for*). */
export function VoteBar({ d, presentCount }: { d: CouncilDecision; presentCount?: number }) {
  const gegen = d.gegenstimmen ?? 0;
  const enth = d.enthaltungen ?? 0;
  const rejected = d.outcome === "abgelehnt";
  const deferred = d.outcome === "vertagt";
  const majColor = rejected ? "bg-red-500/80" : deferred ? "bg-amber-500/80" : "bg-green-500/80";
  const dissentColor = rejected ? "bg-green-500/80" : "bg-red-500/80";
  const unanimous = d.vote === "einstimmig" || (gegen === 0 && enth === 0);

  if (unanimous) {
    return (
      <div>
        <div className={cn("h-3 rounded-full", majColor)} />
        <p className="mt-1.5 text-xs text-muted-foreground">
          {rejected ? "Einstimmig abgelehnt" : deferred ? "Einstimmig vertagt" : "Einstimmig angenommen"}
        </p>
      </div>
    );
  }
  // No per-vote roll-call → approximate the majority block so the bar is readable.
  const majSize = presentCount && presentCount > gegen + enth ? presentCount - gegen - enth : (gegen + enth) * 3;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full">
        <div className={majColor} style={{ flexGrow: Math.max(majSize, 1) }} />
        {gegen > 0 && <div className={dissentColor} style={{ flexGrow: gegen }} />}
        {enth > 0 && <div className="bg-amber-500/80" style={{ flexGrow: enth }} />}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Dot cls={majColor} /> {rejected ? "Mehrheit dagegen" : deferred ? "Mehrheit (vertagt)" : "Mehrheit dafür"}
        </span>
        {gegen > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <Dot cls={dissentColor} /> {rejected ? `${gegen} dafür` : `${gegen} Gegenstimmen`}
          </span>
        )}
        {enth > 0 && <span className="inline-flex items-center gap-1.5"><Dot cls="bg-amber-500/80" /> {enth} Enthaltungen</span>}
      </div>
    </div>
  );
}

function Dot({ cls }: { cls: string }) {
  return <span className={cn("inline-block h-2 w-2 rounded-sm", cls)} />;
}
