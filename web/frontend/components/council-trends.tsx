"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight, Briefcase, Bus, ChevronDown, Cog, Construction, Euro as EuroIcon, Globe,
  GraduationCap, HeartHandshake, Leaf, Shield, Tag, Trophy, type LucideIcon,
} from "lucide-react";
import { FieldRecap } from "@/lib/types";
import { Card, CardListSkeleton, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

// Ein Icon je Themenfeld — der visuelle Anker, der die Karten unterscheidbar
// macht, ohne zwölf konkurrierende Farben einzuführen.
const FIELD_ICON: Record<string, LucideIcon> = {
  verkehr: Bus,
  klima_umwelt: Leaf,
  bauen_wohnen: Construction,
  soziales_gesundheit: HeartHandshake,
  bildung: GraduationCap,
  finanzen: EuroIcon,
  kultur_sport: Trophy,
  wirtschaft: Briefcase,
  sicherheit_ordnung: Shield,
  verwaltung_digital: Cog,
  migration_integration: Globe,
  sonstiges: Tag,
};

// Aufklapp-Zustand je Themenfeld (Design 15a) — geräteweit gemerkt.
const RECAP_OPEN_KEY = "trends:recapOpen";
const CHIP_LIMIT = 6;  // sichtbare Themenfeld-Chips vor „+N"

/** Neues Recap-Format: Zeile 1 = Kernaussage, danach "- "-Stichpunkte.
 *  Ältere Rückblicke in der DB sind noch Fließtext → Prosa-Fallback. */
function parseRecap(summary: string): { lead: string; bullets: string[] } | null {
  const lines = summary.split("\n").map((l) => l.trim()).filter(Boolean);
  const bullets = lines.filter((l) => /^[-–•]\s+/.test(l)).map((l) => l.replace(/^[-–•]\s+/, ""));
  if (bullets.length < 2) return null;
  const lead = lines.filter((l) => !/^[-–•]\s+/.test(l)).join(" ");
  return { lead, bullets };
}

/** Ersten Teilsatz („Kern") eines Stichpunkts abtrennen — bis zum ersten
 *  Trenner (Doppelpunkt, Gedankenstrich oder Komma). Der Kern wird gefettet
 *  und führt beim Scannen das Auge (Design 15a). */
function splitBullet(b: string): { head: string; rest: string } {
  const m = b.match(/^(.{3,}?)(:\s|\s[–—-]\s|,\s)(.*)$/);
  if (m) return { head: m[1], rest: m[2] + m[3] };
  // Kein Trenner: kurze Punkte ganz fetten, lange gar nicht (statt eines
  // hässlichen Fettbruchs mitten im Satz).
  return b.length <= 55 ? { head: b, rest: "" } : { head: "", rest: b };
}

function RecapChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={cn("shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors",
        active ? "bg-primary text-primary-foreground" : "border border-input bg-card text-foreground hover:bg-accent")}>
      {children}
    </button>
  );
}

/** Themenfeld-Karte (Design 15a): standardmäßig nur Kernaussage + Zahl; die
 *  Stichpunkte klappen auf — ein Klick/Tipp irgendwo auf die Karte reicht
 *  (Touch + Desktop), der Chevron ist die tastatur-/screenreader-Steuerung. */
function RecapCard({ r, open, onToggle }: { r: FieldRecap; open: boolean; onToggle: (open: boolean) => void }) {
  const Icon = FIELD_ICON[r.policy_field] ?? Tag;
  const parsed = parseRecap(r.summary);
  const href = `/council?tab=decisions&field=${r.policy_field}&cat=all${r.period_from ? `&date_from=${r.period_from}` : ""}${r.period_to ? `&date_to=${r.period_to}` : ""}`;

  // Alt-Fließtext ohne Stichpunkte: nichts aufzuklappen → statische Karte.
  if (!parsed) {
    return (
      <div className="flex flex-col rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </span>
          <h4 className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{r.field_label}</h4>
          <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground" title="ausgewertete Beschlüsse">
            {r.n_decisions}
          </span>
        </div>
        <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{r.summary}</p>
        <Link href={href}
          className="mt-3 inline-flex w-fit items-center gap-1 border-t border-border pt-2.5 text-xs font-medium text-muted-foreground transition-colors hover:text-primary">
          {r.n_decisions === 1 ? "Der Beschluss dahinter" : `Die ${r.n_decisions} Beschlüsse dahinter`}{" "}
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    );
  }

  // Klick/Tipp auf die Karte klappt auf/zu — außer der Nutzer hat gerade Text
  // markiert (Auswahl nicht wegklicken); der Beschlüsse-Link navigiert eigen
  // (stopPropagation), der Chevron trägt die Tastatur-/SR-Semantik.
  const toggle = () => {
    if (typeof window !== "undefined" && window.getSelection()?.toString()) return;
    onToggle(!open);
  };

  return (
    <div onClick={toggle}
      className={cn("flex cursor-pointer select-text flex-col rounded-xl border bg-card p-4 transition-colors",
        // Hover-Optik nur auf Zeigegeräten — sonst „klebt" der Tint nach dem Tippen.
        open ? "border-primary/30 shadow-sm" : "border-border [@media(hover:hover)]:hover:border-primary/40 [@media(hover:hover)]:hover:bg-accent/40")}>
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </span>
        <h4 className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{r.field_label}</h4>
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground" title="ausgewertete Beschlüsse">
          {r.n_decisions}
        </span>
        <button type="button" aria-expanded={open} aria-label={open ? "Kernpunkte einklappen" : "Kernpunkte aufklappen"}
          onClick={(e) => { e.stopPropagation(); onToggle(!open); }}
          className="-mr-1 shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
        </button>
      </div>

      <p className="mt-3 text-sm font-semibold leading-snug text-foreground">{parsed.lead}</p>

      {open ? (
        <>
          <ul className="mt-2.5 space-y-2">
            {parsed.bullets.map((b, i) => {
              const { head, rest } = splitBullet(b);
              return (
                <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-muted-foreground">
                  <span className="mt-[0.45rem] h-[5px] w-[5px] shrink-0 rounded-full bg-primary" aria-hidden />
                  <span><strong className="font-semibold text-foreground">{head}</strong>{rest}</span>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5">
            <span className="text-xs font-medium text-muted-foreground">Einklappen</span>
            <Link href={href} onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              {r.n_decisions} {r.n_decisions === 1 ? "Beschluss" : "Beschlüsse"} <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </>
      ) : (
        <p className="mt-3 border-t border-border pt-2.5 text-xs font-medium text-primary">
          {parsed.bullets.length} Kernpunkte anzeigen
        </p>
      )}
    </div>
  );
}

function FieldRecaps({ recaps }: { recaps: FieldRecap[] }) {
  const [filter, setFilter] = useState<string | null>(null);
  const [showAllChips, setShowAllChips] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  // Gemerkten Aufklapp-Zustand einmalig laden.
  useEffect(() => {
    try {
      const s = JSON.parse(localStorage.getItem(RECAP_OPEN_KEY) || "{}");
      if (s && typeof s === "object") setOpen(s);
    } catch { /* privater Modus o. ä. */ }
  }, []);
  const persist = (next: Record<string, boolean>) => {
    setOpen(next);
    try { localStorage.setItem(RECAP_OPEN_KEY, JSON.stringify(next)); } catch { /* egal */ }
  };

  const shown = filter ? recaps.filter((r) => r.policy_field === filter) : recaps;
  const allExpanded = shown.length > 0 && shown.every((r) => open[r.policy_field]);
  const toggleAll = () => {
    const next = { ...open };
    shown.forEach((r) => { next[r.policy_field] = !allExpanded; });
    persist(next);
  };
  const chipFields = showAllChips ? recaps : recaps.slice(0, CHIP_LIMIT);
  const overflow = recaps.length - chipFields.length;

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">Rückblick je Themenfeld</h3>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            Automatische Kurzfassung der neuesten Beschlüsse — was den Rat zuletzt beschäftigt hat.
          </p>
        </div>
        <button type="button" onClick={toggleAll}
          className="shrink-0 rounded-full border border-input bg-card px-3 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent">
          {allExpanded ? "Alle einklappen" : "Alle ausklappen"}
        </button>
      </div>

      {/* Filter-Chips: mobil horizontal scrollbar, ab sm umbrechend. */}
      <div className="mt-3.5 flex gap-1.5 overflow-x-auto pb-0.5 sm:flex-wrap sm:overflow-visible sm:pb-0">
        <RecapChip active={filter === null} onClick={() => setFilter(null)}>Alle {recaps.length}</RecapChip>
        {chipFields.map((r) => (
          <RecapChip key={r.policy_field} active={filter === r.policy_field}
            onClick={() => setFilter((f) => (f === r.policy_field ? null : r.policy_field))}>
            {r.field_label}
          </RecapChip>
        ))}
        {overflow > 0 && (
          <button type="button" onClick={() => setShowAllChips(true)}
            className="shrink-0 whitespace-nowrap rounded-full border border-input bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent">
            +{overflow}
          </button>
        )}
      </div>

      <div className="mt-3.5 grid grid-cols-1 items-start gap-3 sm:grid-cols-2">
        {shown.map((r) => (
          <RecapCard key={r.policy_field} r={r} open={!!open[r.policy_field]}
            onToggle={(o) => persist({ ...open, [r.policy_field]: o })} />
        ))}
      </div>
    </Card>
  );
}

/** „Trends" ist seit 09/2026 nur noch der Rückblick je Themenfeld: Die
 *  Quartalsgrafiken (Beschlüsse, Finanzvolumen) und die Schlagwort-Wolke
 *  „Aktuell aufkommende Themen" zeigten einen veralteten Stand und sind raus. */
export function TrendsView() {
  const { data, loading } = useFetch<{ recaps: FieldRecap[] }>("/council/field-recaps");
  const recaps = data?.recaps ?? [];

  if (loading) return <CardListSkeleton rows={4} />;
  if (recaps.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Trends" hint="Die Rückblicke je Themenfeld werden erstellt, sobald genug klassifizierte Beschlüsse vorliegen." />;
  }
  return (
    <div className="space-y-4">
      <FieldRecaps recaps={recaps} />
    </div>
  );
}
