"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft, Gavel, Info, ExternalLink, ChevronDown } from "lucide-react";
import { MemberDetail } from "@/lib/types";
import { Card, DetailSkeleton, EmptyState, formatDate } from "@/components/ui";
import { PartyBadge, partyBrand, AffiliationBadge } from "@/components/decision-ui";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { shortCommittee } from "@/lib/committees";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

type Membership = NonNullable<MemberDetail["ris"]>["memberships"][number];

const yearOf = (d: string | null | undefined): number | null => {
  const y = d ? parseInt(d.slice(0, 4), 10) : NaN;
  return Number.isFinite(y) ? y : null;
};
const isChair = (rolle: string | null) => !!rolle && /vorsitz/i.test(rolle);
const isDeputy = (rolle: string | null) => !!rolle && /(stellv|stv\.)/i.test(rolle);
const initials = (name: string) =>
  name.trim().split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "?";

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[15px] font-bold text-foreground">{title}</h2>
        {aside && <span className="text-xs text-muted-foreground">{aside}</span>}
      </div>
      <div className="mt-2.5">{children}</div>
    </div>
  );
}

/** Aktuelle Ämter als Gantt (Design 17a): Balkenlänge = Amtsdauer, orange =
 *  Vorsitz, „–heute"-Balken laufen bis zum rechten Rand. */
function OfficesGantt({ current }: { current: Membership[] }) {
  const thisYear = new Date().getFullYear();
  const starts = current.map((m) => yearOf(m.von)).filter((y): y is number => y != null);
  const minYear = starts.length ? Math.min(...starts) : thisYear - 4;
  const span = Math.max(1, thisYear - minYear);
  const midYear = minYear + Math.round(span / 2);
  const rows = [...current].sort((a, b) => {
    const ca = isChair(a.rolle) ? 0 : 1, cb = isChair(b.rolle) ? 0 : 1;
    return ca !== cb ? ca - cb : (yearOf(a.von) ?? minYear) - (yearOf(b.von) ?? minYear);
  });
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-2.5">
        {rows.map((m, i) => {
          const chair = isChair(m.rolle);
          const vy = yearOf(m.von) ?? minYear;
          const leftPct = Math.min(90, Math.max(0, ((vy - minYear) / span) * 100));
          const showLabel = 100 - leftPct >= 26 && m.von;
          return (
            // Schmal (< sm) stapelt sich die Zeile: Name über dem Balken, Jahr
            // rechts daneben. Zweispaltig fraß die Namensspalte auf dem Handy
            // die halbe Breite — Ämter wurden abgeschnitten („Wirtschaft & Dig…")
            // und junge Ämter schrumpften zum Punkt. Ab sm bleibt der Gantt.
            <div key={`${m.gremium}-${i}`}
              className="flex flex-wrap items-center gap-x-1.5 gap-y-1 sm:grid sm:grid-cols-[14rem_1fr] sm:gap-3">
              <span className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto">
                {chair
                  ? <Gavel className="h-3.5 w-3.5 shrink-0 text-signal" />
                  : <span className="w-3.5 shrink-0" aria-hidden />}
                <span className={cnEllipsis(chair)} title={m.gremium}>
                  {shortCommittee(m.gremium)}
                  {/* nowrap nur schmal, wo der Name umbrechen darf: sonst landet
                      der Trenner allein am Zeilenende und „Stellv." rutscht in
                      die nächste. Ab sm wird ohnehin gekürzt statt umgebrochen. */}
                  {isDeputy(m.rolle) && <span className="ml-1 text-[11px] font-normal text-muted-foreground max-sm:whitespace-nowrap">· Stellv.</span>}
                </span>
                {/* Das Jahr steht schmal IMMER in der Namenszeile — im Balken
                    wäre es bei kurzer Amtszeit unlesbar oder ganz weg. */}
                {m.von && (
                  <span className={`ml-auto shrink-0 text-[11px] font-semibold tabular-nums sm:hidden ${chair ? "text-signal" : "text-primary"}`}>
                    seit {vy}
                  </span>
                )}
              </span>
              {/* Schmal mit Spur hinterlegt, damit die gemeinsame Skala sichtbar
                  bleibt und man Startjahre vergleichen kann. */}
              <span className="relative block h-2 w-full rounded-full bg-muted sm:h-4 sm:w-auto sm:rounded-none sm:bg-transparent">
                <span className={`absolute inset-y-0 rounded-full sm:inset-y-[2px] ${chair ? "bg-signal" : "bg-primary"}`}
                  style={{ left: `${leftPct}%`, right: 0 }} />
                {showLabel && (
                  <span className="absolute top-1/2 hidden -translate-y-1/2 text-[10.5px] font-semibold text-white sm:inline"
                    style={{ left: `calc(${leftPct}% + 8px)` }}>
                    seit {vy}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {/* Jahresachse — nur ab sm: schmal ist unter jedem Balken schon eine
          Spur, die Spanne steht kompakt in der Legende. */}
      <div className="relative mt-3 hidden h-4 border-t border-border sm:ml-[14rem] sm:block">
        <span className="absolute left-0 top-1 text-[10px] text-muted-foreground">{minYear}</span>
        {span > 6 && <span className="absolute left-1/2 top-1 -translate-x-1/2 text-[10px] text-muted-foreground">{midYear}</span>}
        <span className="absolute right-0 top-1 text-[10px] text-muted-foreground">heute</span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-signal" /> Vorsitz<span className="hidden sm:inline"> / stellv. Vorsitz</span></span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-primary" /> Mitglied</span>
        <span className="ml-auto tabular-nums sm:hidden">{minYear} → heute</span>
      </div>
    </div>
  );
}

/** Schmal darf der Gremienname umbrechen — er hat dort die volle Zeile für sich
 *  und wird nicht mehr von einer Balkenspalte beschnitten. Erst ab sm, wo er in
 *  einer festen 14rem-Spalte sitzt, wird wieder gekürzt. */
function cnEllipsis(chair: boolean) {
  return `min-w-0 text-[13px] sm:truncate ${chair ? "font-semibold text-foreground" : "text-foreground"}`;
}

function PersonInner() {
  const slug = useSearchParams().get("slug");
  const router = useRouter();
  const { data, loading } = useFetch<MemberDetail>(slug ? `/council/person/${slug}` : null);
  const [pastOpen, setPastOpen] = useState(false);

  if (loading) return <DetailSkeleton />;
  if (!data) return <EmptyState mascot="confused" title="Ratsmitglied nicht gefunden" hint="Zu diesem Namen gibt es keine Anwesenheitsdaten." />;

  const brand = data.party ? partyBrand(data.party) : null;
  // Aktuelle Zugehörigkeit = letzte Phase der Zeitreihe (gruppen-bewusst).
  const currentAffiliation = data.faction_timeline.length ? data.faction_timeline[data.faction_timeline.length - 1] : null;
  const memberships = data.ris?.memberships ?? [];
  const current = memberships.filter((m) => !m.bis);
  const past = memberships.filter((m) => m.bis);
  const nChairs = data.committees.filter((c) => c.chair).length;
  const maxPresence = Math.max(1, ...data.committees.map((c) => c.n));

  const pastFrom = past.map((m) => yearOf(m.von)).filter((y): y is number => y != null);
  const pastTo = past.map((m) => yearOf(m.bis)).filter((y): y is number => y != null);
  const pastSpan = pastFrom.length && pastTo.length ? `${Math.min(...pastFrom)}–${Math.max(...pastTo)}` : null;

  return (
    <Card className="mx-auto max-w-3xl p-5 sm:p-6">
      <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Zurück
      </button>

      {/* Kopf: Avatar + Name + Kennzahlen */}
      <div className="mt-3.5 flex items-center gap-4">
        <span className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-full font-display text-xl font-bold shadow-sm", !brand && "bg-muted text-muted-foreground")}
          style={brand ? { backgroundColor: brand.bg, color: brand.fg } : undefined}>
          {initials(data.name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">{data.name}</h1>
            {currentAffiliation
              ? <AffiliationBadge label={currentAffiliation.label} kind={currentAffiliation.kind} parties={currentAffiliation.parties} />
              : data.party && <PartyBadge party={data.party} />}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-[13px] text-muted-foreground">
            <span><strong className="font-bold tabular-nums text-foreground">{data.n_sessions}</strong> Sitzungen besucht</span>
            {data.active_from && (
              <>
                <span className="text-border" aria-hidden>·</span>
                <span>aktiv seit <strong className="font-semibold text-foreground">{yearOf(data.active_from)}</strong></span>
              </>
            )}
            {nChairs > 0 && (
              <>
                <span className="text-border" aria-hidden>·</span>
                <span className="inline-flex items-center gap-1 font-semibold text-signal">
                  <Gavel className="h-3 w-3" /> {nChairs} {nChairs === 1 ? "Vorsitz" : "Vorsitze"}
                </span>
              </>
            )}
          </div>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <button type="button" className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent sm:inline-flex">
              <Info className="h-3.5 w-3.5" /> Wie erfasst?
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-72 max-w-[calc(100vw-2rem)] text-xs leading-relaxed text-muted-foreground">
            Aus den Anwesenheitslisten der Protokolle (erfasst ab 2018), ergänzt um die offiziellen Gremien-Zeiträume
            aus dem Ratsinformationssystem (zurück bis 2001). Präsenz zeigt Aktivität, nicht das Stimmverhalten —
            Protokolle nennen namentliche Einzelstimmen nur selten.
          </PopoverContent>
        </Popover>
      </div>

      {/* Aktuelle Ämter als Gantt */}
      {current.length > 0 && (
        <Section title="Aktuelle Ämter" aside={<>{current.length} laufend · Balken = Amtszeit</>}>
          <OfficesGantt current={current} />
        </Section>
      )}

      {/* Frühere Ämter eingeklappt */}
      {past.length > 0 && (
        <div className="mt-3 overflow-hidden rounded-xl border border-border bg-card">
          <button type="button" onClick={() => setPastOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left">
            <span className="text-[13.5px] font-semibold text-foreground">
              Frühere Ämter <span className="font-normal text-muted-foreground">· {past.length} beendet{pastSpan ? ` (${pastSpan})` : ""}</span>
            </span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${pastOpen ? "rotate-180" : ""}`} />
          </button>
          {pastOpen && (
            <div className="border-t border-border px-4 py-3">
              <div className="space-y-1.5">
                {past.map((m, i) => (
                  <div key={`${m.gremium}-${i}`} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <span className="min-w-0 text-[13px] text-foreground" title={m.gremium}>
                      {shortCommittee(m.gremium)}
                      {isChair(m.rolle) && <span className="ml-1.5 text-[11px] font-medium text-signal">{isDeputy(m.rolle) ? "stellv. Vorsitz" : "Vorsitz"}</span>}
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {m.von ? yearOf(m.von) : "?"} – {m.bis ? yearOf(m.bis) : "heute"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fraktions- & Gruppen-Verlauf */}
      {data.faction_timeline.length > 0 && (
        <Section title="Zugehörigkeit im Zeitverlauf" aside="Fraktion · Gruppe · parteilos">
          <div className="flex flex-wrap items-center gap-2">
            {data.faction_timeline.map((f, i) => (
              <div key={`${f.label}-${f.first}`} className="flex items-center gap-2">
                {i > 0 && <span className="text-muted-foreground/50">→</span>}
                <span className="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5">
                  <AffiliationBadge label={f.label} kind={f.kind} parties={f.parties} />
                  <span className="text-[11.5px] tabular-nums text-muted-foreground">
                    {formatDate(f.first)} – {formatDate(f.last)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Präsenz je Gremium als Balken */}
      {data.committees.length > 0 && (
        <Section title="Präsenz je Gremium" aside="besuchte Sitzungen">
          <div className="space-y-2">
            {data.committees.map((c) => (
              // Gleiche Stapelung wie beim Ämter-Gantt: schmal ist für eine
              // Namensspalte kein Platz („Betrieb Gebäudewirtschaft" bräuchte
              // 164 px, bekam 70). Name samt Zahl oben, Balken darunter.
              <div key={c.committee}
                className="flex flex-wrap items-center gap-x-1.5 gap-y-1 sm:grid sm:grid-cols-[14rem_1fr_3rem] sm:gap-3">
                <span className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto">
                  <span className="min-w-0 text-[13px] text-foreground sm:truncate" title={c.committee}>{shortCommittee(c.committee)}</span>
                  {c.chair && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-signal/10 px-1.5 py-0.5 text-[10px] font-semibold text-signal">
                      <Gavel className="h-2.5 w-2.5" /> Vorsitz
                    </span>
                  )}
                  <span className="ml-auto shrink-0 text-xs font-semibold tabular-nums text-muted-foreground sm:hidden">{c.n}</span>
                </span>
                <span className="block h-2 w-full overflow-hidden rounded-full bg-muted sm:w-auto">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${(c.n / maxPresence) * 100}%` }} />
                </span>
                <span className="hidden text-right text-xs tabular-nums text-muted-foreground sm:block">{c.n}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Zuletzt anwesend */}
      {data.recent.length > 0 && (
        <Section title="Zuletzt anwesend">
          <div className="flex flex-col">
            {data.recent.map((r, i) => (
              <a key={`${r.ksinr}-${r.session_date}`} href={sessionUrl(r.ksinr)} target="_blank" rel="noreferrer"
                className={`group flex items-center justify-between gap-3 py-2.5 text-[13.5px] ${i > 0 ? "border-t border-border" : ""}`}>
                <span className="min-w-0 truncate text-foreground" title={r.committee}>{shortCommittee(r.committee)}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                  {formatDate(r.session_date)}
                  <ExternalLink className="h-3 w-3 text-muted-foreground/40 group-hover:text-primary" />
                </span>
              </a>
            ))}
          </div>
        </Section>
      )}
    </Card>
  );
}

export default function PersonPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PersonInner />
    </Suspense>
  );
}
