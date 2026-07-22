"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight, Briefcase, Bus, ChevronDown, Cog, Construction, Euro as EuroIcon, Globe,
  GraduationCap, HeartHandshake, Leaf, Shield, Tag, Trophy, type LucideIcon,
} from "lucide-react";
import { Trends, FieldRecap } from "@/lib/types";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { POLICY_FIELD_LABELS, formatEuro } from "@/components/decision-ui";
import { decisionHref } from "@/lib/routes";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { ChartExplainer } from "@/components/chart-explainer";

// Distinct, dark-mode-safe series colours for the top policy fields —
// abgeleitet aus der Markenpalette (Hafenblau, Signal-Orange, Gold der Mütze).
const COLORS = ["#1c86c8", "#f66623", "#0d9488", "#f2b441", "#8b6ce8", "#e4577e"];

function qLabel(q: string) {
  // "2024-Q3" → "Q3 '24"
  const [y, quarter] = q.split("-");
  return `${quarter} '${y.slice(2)}`;
}

// "2024-Q3" → calendar date range for deep-linking into the decisions list.
const Q_START: Record<number, string> = { 1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01" };
const Q_END: Record<number, string> = { 1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31" };
function quarterRange(q: string): { from: string; to: string } {
  const [y, qq] = q.split("-Q");
  const qi = Math.min(4, Math.max(1, parseInt(qq, 10) || 1));
  return { from: `${y}-${Q_START[qi]}`, to: `${y}-${Q_END[qi]}` };
}

function Block({ title, hint, explain, children }: { title: string; hint?: string; explain?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hint && <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
      {explain && <ChartExplainer>{explain}</ChartExplainer>}
      <div className="mt-4">{children}</div>
    </Card>
  );
}

function StackedDecisions({ d, onQuarter }: { d: Trends; onQuarter: (q: string) => void }) {
  const totals = d.quarters.map((_, qi) => d.fields.reduce((s, f) => s + (d.by_field[f]?.[qi] ?? 0), 0));
  const max = Math.max(1, ...totals);
  const label = (f: string) => d.field_labels[f] ?? POLICY_FIELD_LABELS[f] ?? f;
  return (
    <div>
      {/* Screenreader-Fassung: die Balken selbst tragen ihre Zahlen nur im title. */}
      <table className="sr-only">
        <caption>Beschlüsse je Quartal</caption>
        <thead><tr><th scope="col">Quartal</th><th scope="col">Beschlüsse</th></tr></thead>
        <tbody>
          {d.quarters.map((q, qi) => (
            <tr key={q}><th scope="row">{qLabel(q)}</th><td>{totals[qi]}</td></tr>
          ))}
        </tbody>
      </table>
      <div aria-hidden className="flex items-end gap-1.5" style={{ height: 190 }}>
        {d.quarters.map((q, qi) => (
          <button key={q} type="button" onClick={() => onQuarter(q)}
            className="group flex h-full flex-1 flex-col justify-end rounded-sm transition-colors hover:bg-muted/50"
            title={`${qLabel(q)}: ${totals[qi]} Beschlüsse — klicken für die Beschlüsse dieses Quartals`}>
            <div className="flex flex-col-reverse overflow-hidden rounded-sm opacity-90 transition-opacity group-hover:opacity-100"
              style={{ height: `${(totals[qi] / max) * 100}%`, minHeight: totals[qi] > 0 ? 3 : 0 }}>
              {d.fields.map((f, fi) => {
                const v = d.by_field[f]?.[qi] ?? 0;
                return v ? <div key={f} style={{ height: `${(v / totals[qi]) * 100}%`, background: COLORS[fi % COLORS.length] }} /> : null;
              })}
            </div>
          </button>
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[10px] text-muted-foreground">
        {d.quarters.map((q) => <span key={q} className="flex-1 text-center">{qLabel(q)}</span>)}
      </div>
      <div className="mt-3.5 flex flex-wrap gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        {d.fields.map((f, fi) => (
          <span key={f} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[fi % COLORS.length] }} />
            {label(f)}
          </span>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground/70">Balken anklicken, um die Beschlüsse eines Quartals zu öffnen.</p>
    </div>
  );
}

function MoneyBars({ d, onQuarter }: { d: Trends; onQuarter: (q: string) => void }) {
  const max = Math.max(1, ...d.money);
  const drivers = d.money_drivers ?? [];
  // The single largest recognised item across the shown quarters — a concrete
  // anchor for "what is this money?".
  let topI = -1;
  drivers.forEach((dr, i) => { if (dr && (topI < 0 || dr.eur > (drivers[topI]?.eur ?? 0))) topI = i; });
  const top = topI >= 0 ? drivers[topI] : null;
  return (
    <div>
      {/* Screenreader-Fassung der Quartals-Summen. */}
      <table className="sr-only">
        <caption>Erkanntes Finanzvolumen je Quartal</caption>
        <thead><tr><th scope="col">Quartal</th><th scope="col">Summe</th></tr></thead>
        <tbody>
          {d.quarters.map((q, qi) => (
            <tr key={q}><th scope="row">{qLabel(q)}</th><td>{formatEuro(d.money[qi])}</td></tr>
          ))}
        </tbody>
      </table>
      <div aria-hidden className="flex items-end gap-1.5" style={{ height: 130 }}>
        {d.quarters.map((q, qi) => {
          const dr = drivers[qi];
          const tip = `${qLabel(q)}: ${formatEuro(d.money[qi])}`
            + (dr ? ` · größter Posten: ${dr.title} (${formatEuro(dr.eur)})` : "");
          return (
            <button key={q} type="button" onClick={() => onQuarter(q)}
              className="group flex h-full flex-1 flex-col justify-end rounded-sm transition-colors hover:bg-muted/50"
              title={tip}>
              <div className="rounded-sm bg-emerald-500/70 transition-colors group-hover:bg-emerald-500"
                style={{ height: `${(d.money[qi] / max) * 100}%`, minHeight: d.money[qi] > 0 ? 2 : 0 }} />
            </button>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-1.5 text-[10px] text-muted-foreground">
        {d.quarters.map((q) => <span key={q} className="flex-1 text-center">{qLabel(q)}</span>)}
      </div>
      {top && (
        <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">
          Größter erkannter Einzelposten:{" "}
          <Link href={decisionHref(top.id)} className="font-medium text-foreground hover:text-primary hover:underline">
            {top.title}
          </Link>{" "}
          <span className="whitespace-nowrap text-muted-foreground/80">— {formatEuro(top.eur)} ({qLabel(d.quarters[topI])})</span>
        </p>
      )}
    </div>
  );
}

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
          Die {r.n_decisions} Beschlüsse dahinter <ArrowRight className="h-3 w-3" />
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
              {r.n_decisions} Beschlüsse <ArrowRight className="h-3 w-3" />
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

function FieldRecaps() {
  const { data } = useFetch<{ recaps: FieldRecap[] }>("/council/field-recaps");
  const recaps = data?.recaps ?? [];
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

  if (recaps.length === 0) return null;

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
            KI-Kurzfassung der neuesten Beschlüsse — was den Rat zuletzt beschäftigt hat.
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

export function TrendsView() {
  const { data, loading } = useFetch<Trends>("/council/trends");
  const router = useRouter();

  if (loading) return <div className="py-10"><Spinner /></div>;
  if (!data || data.quarters.length === 0) {
    return <EmptyState mascot="sleep" title="Noch keine Trends" hint="Es sind noch nicht genug datierte, klassifizierte Beschlüsse vorhanden." />;
  }
  const onQuarter = (q: string) => {
    const { from, to } = quarterRange(q);
    router.push(`/council?tab=decisions&date_from=${from}&date_to=${to}`);
  };
  return (
    <div className="space-y-4">
      <FieldRecaps />
      <Block
        title="Beschlüsse je Quartal"
        hint="Wie viel der Rat entscheidet — und in welchen Themenfeldern. Balken anklicken für das Quartal."
        explain={
          <>
            Jede Säule ist ein Quartal, die Farben stapeln die Themenfelder. Hohe Säulen sind
            entscheidungsreiche Monate (oft vor der Sommerpause), die Farbanteile verraten, welche Themen
            gerade dominieren. Ein Klick auf eine Säule öffnet alle Beschlüsse dieses Quartals.
          </>
        }
      >
        <StackedDecisions d={data} onQuarter={onQuarter} />
      </Block>
      <Block
        title="Erkanntes Finanzvolumen je Quartal"
        hint="Summe der im Beschlusstext genannten Beträge (ohne Jahresabschlüsse/Haushaltspläne — grobe Größenordnung)."
        explain={
          <>
            Wie viel Geld die Beschlüsse eines Quartals bewegt haben — summiert aus den im Text erkannten
            Beträgen. Ein einzelnes Großprojekt kann eine Säule dominieren; der „größte Einzelposten“
            darunter ordnet das ein.
          </>
        }
      >
        <MoneyBars d={data} onQuarter={onQuarter} />
      </Block>
      {data.emerging.length > 0 && (
        <Block title="Aktuell aufkommende Themen" hint="Häufigste Schlagworte der letzten zwei Quartale.">
          <div className="flex flex-wrap gap-2">
            {data.emerging.map((e) => (
              <button key={e.tag} onClick={() => router.push(`/council?tab=decisions&q=${encodeURIComponent(e.tag)}`)}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-foreground transition-colors hover:bg-muted">
                {e.tag}<span className="text-muted-foreground">{e.n}</span>
              </button>
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}
