"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Search, ExternalLink, ChevronDown, ChevronRight, Scale, SlidersHorizontal, Users, Sparkles, X } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { decisionHref } from "@/lib/routes";
import { useDebounce } from "@/lib/use-debounce";
import {
  CouncilSession, SessionDetail, AgendaItem, CouncilDecision, DecisionOutcome, PolicyField,
} from "@/lib/types";
import {
  Badge, Button, Card, CardListSkeleton, DateField, EmptyState, Input, PageHeader, Pagination, Segmented, Select,
  Sheet, SheetContent, SheetTitle, SheetTrigger, Spinner, formatDate, toast,
} from "@/components/ui";
import { OutcomeBadge, FieldBadge, formatEuro, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { AnalysisTab } from "@/components/council-analysis";
import { EntitiesTab } from "@/components/council-entities";
import { QaTab } from "@/components/council-qa";
import { cn } from "@/lib/utils";

type Scope = "all" | "upcoming" | "recent";
type Tab = "sessions" | "decisions" | "themen" | "analysis";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

function itemMatches(it: AgendaItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return it.title.toLowerCase().includes(q) || (it.vorlage_nr?.toLowerCase().includes(q) ?? false);
}

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q || !text) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-amber-200 px-0.5 text-foreground dark:bg-amber-700/60">
        {text.slice(idx, idx + q.length)}
      </mark>
      {text.slice(idx + q.length)}
    </>
  );
}

function VoteLine({ d }: { d: CouncilDecision }) {
  // Defensiv: Ein einzelner kaputter Datensatz (factions kein Array — der Store
  // json.dumps't unbesehen) darf nie die ganze Seite in die Error-Boundary reißen.
  const factions = Array.isArray(d.factions) ? d.factions : [];
  const parts: string[] = [];
  if (d.vote) parts.push(d.vote);
  if (d.gegenstimmen) parts.push(`${d.gegenstimmen} ${d.gegenstimmen === 1 ? "Gegenstimme" : "Gegenstimmen"}`);
  if (d.enthaltungen) parts.push(`${d.enthaltungen} ${d.enthaltungen === 1 ? "Enthaltung" : "Enthaltungen"}`);
  if (parts.length === 0 && factions.length === 0) return null;
  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
      {parts.length > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Scale className="h-3.5 w-3.5" /> {parts.join(" · ")}
        </span>
      )}
      {factions.length > 0 && (
        <span
          className="inline-flex flex-wrap items-center gap-1.5"
          title="Fraktion(en), die zu diesem Punkt einen Antrag oder eine Änderungsliste eingebracht haben"
        >
          <span className="text-xs text-muted-foreground">
            {d.kind === "subvote" ? "Antrag von:" : "Anträge von:"}
          </span>
          {factions.map((f) => (
            <span key={f} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{f}</span>
          ))}
        </span>
      )}
    </div>
  );
}

function DecisionCard({ d, query }: { d: CouncilDecision; query: string }) {
  const isSub = d.kind === "subvote";
  return (
    <Link href={decisionHref(d.id)} className="block">
      <Card className={cn("card-interactive group flex items-center gap-3 p-4", isSub && "border-l-2 border-l-border bg-muted/30")}>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
              {!isSub && <FieldBadge field={d.policy_field} />}
              <span>{isSub ? `Teilabstimmung · TOP ${d.parent_item}` : `${d.committee} · ${formatDate(d.session_date)}`}</span>
              {!isSub && d.amount_eur != null && (
                <span className="rounded bg-emerald-500/10 px-1.5 font-semibold tabular-nums text-emerald-700 dark:text-emerald-400" title="Im Beschlusstext genannter Betrag">
                  {formatEuro(d.amount_eur)}
                </span>
              )}
            </div>
            <OutcomeBadge outcome={d.outcome} />
          </div>
          <div className="mt-1.5 hyphens-auto font-medium text-foreground">
            {!isSub && d.item_number && <span className="text-muted-foreground">TOP {d.item_number} · </span>}
            <Highlight text={d.title ?? ""} query={query} />
          </div>
          {d.beschluss && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
              <Highlight text={d.beschluss} query={query} />
            </p>
          )}
          <VoteLine d={d} />
        </div>
        <ChevronRight className="h-5 w-5 shrink-0 self-center text-muted-foreground/40 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
      </Card>
    </Link>
  );
}

const PAGE_SIZE = 50;

const SORTS: { value: string; label: string }[] = [
  { value: "date_desc", label: "Neueste zuerst" },
  { value: "date_asc", label: "Älteste zuerst" },
  { value: "faction", label: "Nach Fraktion" },
];

const OUTCOME_CHIPS: { value: string; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "angenommen", label: "Angenommen" },
  { value: "abgelehnt", label: "Abgelehnt" },
  { value: "vertagt", label: "Vertagt" },
];

function FilterField({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={className}>
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

/** Aktiver Filter als entfernbarer Chip (mobile Ansicht). */
function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-primary/10 py-1 pl-2.5 pr-1 text-xs font-medium text-primary">
      <span className="truncate">{label}</span>
      <button
        type="button"
        onClick={onClear}
        aria-label={`Filter „${label}“ entfernen`}
        className="rounded-full p-0.5 transition-colors hover:bg-primary/15"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

function DecisionsTab({ committees, modeToggle }: { committees: string[]; modeToggle?: React.ReactNode }) {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [outcome, setOutcome] = useState("");
  const [sort, setSort] = useState("date_desc");
  const [fields, setFields] = useState<PolicyField[]>([]);
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [decisions, setDecisions] = useState<CouncilDecision[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const debouncedQ = useDebounce(q, 350);

  // Field + party live in the URL so the analysis and badges can deep-link to a filtered list.
  const sp = useSearchParams();
  const router = useRouter();

  // ?q= aus der URL übernehmen (Deep-Link aus der Command-Palette) — einmalig
  // nach dem Mount, um keinen Hydration-Mismatch im Input zu erzeugen.
  useEffect(() => {
    const urlQ = sp.get("q");
    if (urlQ) setQ(urlQ);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const field = sp.get("field") ?? "";
  const party = sp.get("party") ?? "";
  // Date range also lives in the URL so the Trends quarter bars can deep-link here.
  const dateFrom = sp.get("date_from") ?? "";
  const dateTo = sp.get("date_to") ?? "";
  // Beschlüsse (votes) / Berichte (reports) / Alle (both) — in the URL so the
  // Themenfeld-Rückblicke can deep-link to the combined "Alle" view.
  const catParam = sp.get("cat");
  const mode: "vote" | "report" | "all" = catParam === "report" || catParam === "all" ? catParam : "vote";
  // Mehrere Params in EINEM replace ändern — zwei Aufrufe nacheinander würden
  // sich gegenseitig überschreiben (beide bauen auf demselben sp-Snapshot auf).
  const setUrlParams = (entries: Record<string, string>) => {
    const params = new URLSearchParams(sp.toString());
    params.set("tab", "decisions");
    for (const [key, val] of Object.entries(entries)) {
      if (val) params.set(key, val); else params.delete(key);
    }
    router.replace(`/council?${params.toString()}`, { scroll: false });
    setPage(1);
  };
  const setUrlParam = (key: string, val: string) => setUrlParams({ [key]: val });

  useEffect(() => {
    api.get<{ fields: PolicyField[] }>("/council/fields").then((d) => setFields(d.fields)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ total: number; decisions: CouncilDecision[] }>(
        `/council/decisions${qs({
          q, committee, category: mode === "all" ? "" : mode, sort, field, party,
          outcome: mode === "vote" ? outcome : "",
          date_from: dateFrom, date_to: dateTo,
          limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE,
        })}`,
      );
      setDecisions(data.decisions);
      setTotal(data.total);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, committee, mode, outcome, sort, field, party, dateFrom, dateTo, page]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, mode, outcome, sort, field, party, dateFrom, dateTo, page]);

  const query = q.trim();
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isReport = mode === "report";
  const noun = mode === "all"
    ? (total === 1 ? "Vorgang" : "Vorgänge")
    : isReport ? (total === 1 ? "Bericht" : "Berichte") : (total === 1 ? "Beschluss" : "Beschlüsse");

  // Zeitraum zählt als EIN Filter; Sortierung ist eine Einstellung, kein Filter.
  const activeFilterCount = [outcome, field, committee, dateFrom || dateTo].filter(Boolean).length;

  // Ein JSX-Baum, zwei Einbauorte: Desktop inline in der Karte, mobil im Bottom-Sheet.
  const refineFilters = (
    <div className="space-y-3">
      {mode === "vote" && (
        <FilterField label="Ergebnis">
          <Segmented
            className="overflow-x-auto"
            value={outcome}
            onChange={(o) => { setOutcome(o); setPage(1); }}
            options={OUTCOME_CHIPS.map((o) => ({ value: o.value, label: o.label }))}
          />
        </FilterField>
      )}
      <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-3">
        {fields.length > 0 && (
          <FilterField label="Themenfeld">
            <Select value={field} onChange={(e) => setUrlParam("field", e.target.value)}>
              <option value="">Alle Themenfelder</option>
              {fields.map((f) => <option key={f.key} value={f.key}>{f.label} ({f.count})</option>)}
            </Select>
          </FilterField>
        )}
        <FilterField label="Ausschuss">
          <Select value={committee} onChange={(e) => { setCommittee(e.target.value); setPage(1); }}>
            <option value="">Alle Ausschüsse</option>
            {committees.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </FilterField>
        <FilterField label="Sortierung">
          <Select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </Select>
        </FilterField>
      </div>
      <FilterField label="Zeitraum">
        <div className="grid grid-cols-2 gap-2">
          <DateField value={dateFrom} onChange={(v) => setUrlParam("date_from", v)} />
          <DateField value={dateTo} onChange={(v) => setUrlParam("date_to", v)} />
        </div>
      </FilterField>
    </div>
  );

  return (
    <div>
      <Card className="mt-3 p-4">
        {/* Tier 0 — Suchen/KI-Frage wohnt IN der Karte statt als eigene Ebene
            darüber: spart auf dem Handy eine Zeile + Abstand vor dem Inhalt. */}
        {modeToggle && <div className="mb-3">{modeToggle}</div>}
        {/* Tier 1 — primary: what am I looking at + free-text search. */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Segmented
            className="shrink-0"
            tone="primary"
            value={mode}
            onChange={(m) => { setUrlParam("cat", m === "vote" ? "" : m); setOutcome(""); }}
            options={[
              { value: "vote", label: "Beschlüsse" },
              { value: "report", label: "Berichte" },
              { value: "all", label: "Alle" },
            ]}
          />
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-search
              data-tour="beschluss-suche"
              className="pl-9"
              placeholder={isReport ? "Berichte durchsuchen…" : "Suchen (z. B. Haushalt, Radwege)…"}
              value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }}
            />
          </div>
        </div>

        {/* Tier 2 — refine: Desktop inline; mobil hinter „Filter“-Button im Bottom-Sheet. */}
        <div className="mt-4 hidden border-t border-border pt-4 md:block">{refineFilters}</div>
        <div className="mt-3 border-t border-border pt-3 md:hidden">
          <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
            <SheetTrigger asChild>
              <Button variant="secondary" size="sm" className="w-full">
                <SlidersHorizontal /> Filter & Sortierung{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="p-5">
              <SheetTitle>Filter & Sortierung</SheetTitle>
              <p className="pb-4 pr-8 font-display text-lg font-semibold text-foreground" aria-hidden>
                Filter & Sortierung
              </p>
              {refineFilters}
              <Button className="mt-5 w-full" onClick={() => setFiltersOpen(false)}>
                {loading ? "Ergebnisse anzeigen" : `${total} ${noun} anzeigen`}
              </Button>
            </SheetContent>
          </Sheet>
          {activeFilterCount > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {outcome && (
                <FilterChip
                  label={`Ergebnis: ${OUTCOME_CHIPS.find((o) => o.value === outcome)?.label ?? outcome}`}
                  onClear={() => { setOutcome(""); setPage(1); }}
                />
              )}
              {field && (
                <FilterChip
                  label={fields.find((f) => f.key === field)?.label ?? field}
                  onClear={() => setUrlParam("field", "")}
                />
              )}
              {committee && <FilterChip label={committee} onClear={() => { setCommittee(""); setPage(1); }} />}
              {(dateFrom || dateTo) && (
                <FilterChip
                  label={`${dateFrom ? formatDate(dateFrom) : "…"} – ${dateTo ? formatDate(dateTo) : "heute"}`}
                  onClear={() => setUrlParams({ date_from: "", date_to: "" })}
                />
              )}
            </div>
          )}
        </div>
      </Card>

      {party && (
        <div className="mt-4 flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Anträge von:</span>
          <button
            type="button"
            onClick={() => setUrlParam("party", "")}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            {party} <X className="h-3 w-3" />
          </button>
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : decisions.length === 0 ? (
          <EmptyState mascot="search" title={`Keine ${isReport ? "Berichte" : "Beschlüsse"} gefunden`} hint="Andere Suche/Filter — oder das Protokoll ist noch nicht veröffentlicht." />
        ) : (
          <div className="space-y-2.5">
            <p className="text-sm font-medium text-muted-foreground">{total} {noun}</p>
            {decisions.map((d) => <DecisionCard key={d.id} d={d} query={query} />)}
            <Pagination page={page} totalPages={totalPages} onChange={setPage} className="pt-2" />
          </div>
        )}
      </div>
    </div>
  );
}

function AgendaRow({ it, query, outcome }: { it: AgendaItem; query: string; outcome?: DecisionOutcome | null }) {
  const hit = itemMatches(it, query);
  return (
    <li className={cn("flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-2", hit && "bg-amber-50 dark:bg-amber-950/40")}>
      <span className="shrink-0 text-xs font-medium text-muted-foreground">{it.item_number}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground"><Highlight text={it.title} query={query} /></p>
        {it.vorlage_nr && <p className="text-xs text-muted-foreground">Vorlage <Highlight text={it.vorlage_nr} query={query} /></p>}
      </div>
      {outcome ? <OutcomeBadge outcome={outcome} /> : !it.is_public ? <Badge color="amber">nichtöffentlich</Badge> : null}
    </li>
  );
}

function AttendanceSection({ detail }: { detail: SessionDetail }) {
  const att = detail.attendance ?? [];
  if (att.length === 0) return null;
  const byParty: Record<string, number> = {};
  for (const a of att) {
    if (a.role === "verwaltung" || a.role === "protokoll" || a.role === "gast") continue;
    const p = normalizeParty(a.party || "—");
    byParty[p] = (byParty[p] ?? 0) + 1;
  }
  return (
    <div className="mt-4 border-t border-border pt-3">
      <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Users className="h-4 w-4" /> Anwesenheit ({att.length})
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Object.entries(byParty).sort((a, b) => b[1] - a[1]).map(([p, n]) => (
          <PartyAttendanceBadge key={p} party={p} n={n} />
        ))}
      </div>
    </div>
  );
}

function SessionsTab({ committees }: { committees: string[] }) {
  const [q, setQ] = useState("");
  const [committee, setCommittee] = useState("");
  const [scope, setScope] = useState<Scope>("upcoming");
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [detail, setDetail] = useState<Record<number, SessionDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<number, boolean>>({});
  const debouncedQ = useDebounce(q, 350);

  const load = useCallback(async () => {
    setLoading(true);
    setHasSearched(true);
    setExpanded({});
    try {
      const effectiveScope = q || committee ? "all" : scope;
      const data = await api.get<{ sessions: CouncilSession[] }>(
        `/council/sessions${qs({ q, committee, scope: effectiveScope, limit: 100 })}`,
      );
      setSessions(data.sessions);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, committee, scope]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, scope]);

  const toggle = async (s: CouncilSession) => {
    const willExpand = !expanded[s.ksinr];
    setExpanded((prev) => ({ ...prev, [s.ksinr]: willExpand }));
    if (willExpand && !detail[s.ksinr]) {
      setDetailLoading((prev) => ({ ...prev, [s.ksinr]: true }));
      try {
        const d = await api.get<SessionDetail>(`/council/session/${s.ksinr}`);
        setDetail((prev) => ({ ...prev, [s.ksinr]: d }));
      } catch {
        toast.error("Sitzung konnte nicht geladen werden.");
        setExpanded((prev) => ({ ...prev, [s.ksinr]: false }));
      } finally {
        setDetailLoading((prev) => ({ ...prev, [s.ksinr]: false }));
      }
    }
  };

  const query = q.trim();

  return (
    <div>
      <Card className="mt-4 p-4">
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input data-search className="pl-9" placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={committee} onChange={(e) => setCommittee(e.target.value)}>
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Segmented
              tone="primary"
              value={q || committee ? undefined : scope}
              onChange={(s) => { setScope(s); setQ(""); setCommittee(""); }}
              options={[
                { value: "upcoming", label: "Kommend" },
                { value: "recent", label: "Vergangen" },
                { value: "all", label: "Alle" },
              ]}
            />
          </div>
        </div>
      </Card>

      <div className="mt-6">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : sessions.length === 0 ? (
          <EmptyState mascot="search" title={hasSearched ? "Keine Sitzungen gefunden" : "Noch keine Sitzungen vorhanden"} hint={hasSearched ? "Versuche andere Suchbegriffe oder Filter." : undefined} />
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground">{sessions.length} {sessions.length === 1 ? "Sitzung" : "Sitzungen"}</p>
            {sessions.map((s) => {
              const isExpanded = !!expanded[s.ksinr];
              const matched = s.matched_items ?? [];
              const d = detail[s.ksinr];
              const outcomeByItem: Record<string, DecisionOutcome | null> = {};
              for (const dec of d?.decisions ?? []) {
                if (dec.kind === "decision" && dec.item_number) outcomeByItem[dec.item_number] = dec.outcome;
              }
              return (
                <Card key={s.ksinr} className="overflow-hidden p-0">
                  <button type="button" onClick={() => toggle(s)} className="group flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/40">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-foreground">{s.committee}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">{formatDate(s.session_date)} · {s.session_time} Uhr · {s.location}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge color="blue">{s.n_items} {s.n_items === 1 ? "TOP" : "TOPs"}</Badge>
                      <ChevronDown className={cn("h-5 w-5 text-muted-foreground/50 transition-transform", isExpanded && "rotate-180 text-primary")} />
                    </div>
                  </button>

                  {(query || isExpanded) && (
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      {isExpanded ? (
                        detailLoading[s.ksinr] ? (
                          <div className="py-2"><Spinner /></div>
                        ) : (
                          <>
                            <ul className="space-y-0.5">
                              {(d?.agenda_items ?? []).map((it, i) => (
                                <AgendaRow key={i} it={it} query={query} outcome={outcomeByItem[it.item_number]} />
                              ))}
                            </ul>
                            {d && <AttendanceSection detail={d} />}
                          </>
                        )
                      ) : query ? (
                        matched.length > 0 ? (
                          <>
                            <p className="mb-1 px-2 text-xs font-medium text-muted-foreground">{matched.length} Treffer in der Tagesordnung</p>
                            <ul className="space-y-0.5">{matched.map((it, i) => <AgendaRow key={i} it={it} query={query} />)}</ul>
                          </>
                        ) : (
                          <p className="px-2 text-sm text-muted-foreground">Kein Tagesordnungspunkt enthält „{query}" — Treffer im Ausschussnamen.</p>
                        )
                      ) : null}

                      <div className="mt-3 flex items-center gap-4 px-2">
                        <button type="button" onClick={() => toggle(s)} className="text-sm font-medium text-primary hover:underline">
                          {isExpanded ? "Weniger anzeigen" : `Alle ${s.n_items} TOPs anzeigen`}
                        </button>
                        <a href={sessionUrl(s.ksinr)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
                          Ratsinfo <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// The combined "Suche" tab: keyword search (DecisionsTab) and the AI question mode
// (QaTab) as two lenses on the same decisions, switched by ?mode. Both render the
// same decision cards, so it reads as one search rather than two features.
function SearchTab({ committees }: { committees: string[] }) {
  const sp = useSearchParams();
  const router = useRouter();
  const mode: "suchen" | "fragen" = sp.get("mode") === "fragen" ? "fragen" : "suchen";
  const setMode = (m: "suchen" | "fragen") => {
    const params = new URLSearchParams(sp.toString());
    params.set("tab", "decisions");
    if (m === "suchen") params.delete("mode"); else params.set("mode", m);
    router.replace(`/council?${params.toString()}`, { scroll: false });
  };
  const modeToggle = (
    <Segmented
      className="sm:w-fit"
      value={mode}
      onChange={setMode}
      options={[
        { value: "suchen", label: "Suchen", icon: Search },
        { value: "fragen", label: "KI-Frage", icon: Sparkles, tour: "ki-frage-tab" },
      ]}
    />
  );
  // Beide Modi zeigen den Umschalter oben IN ihrer weißen Karte — identische
  // Optik, kein Layout-Sprung beim Wechsel zwischen Suchen und KI-Frage.
  return mode === "suchen" ? (
    <DecisionsTab committees={committees} modeToggle={modeToggle} />
  ) : (
    <QaTab modeToggle={modeToggle} />
  );
}

// Navigation between these views now lives in the left sidebar (Ratsinfo section),
// so the page only needs a per-view title/description instead of an in-page tab bar.
const TAB_META: Record<Tab, { title: string; description: string }> = {
  decisions: { title: "Beschlüsse", description: "Beschlüsse durchsuchen oder dem Rat eine KI-Frage stellen." },
  sessions: { title: "Sitzungen", description: "Sitzungen und Tagesordnungen von Rat und Ausschüssen." },
  themen: { title: "Themen", description: "Wiederkehrende Orte, Projekte und Organisationen — als Liste oder Karte." },
  analysis: { title: "Analyse", description: "Parteien, Personen, Finanzen, Trends und Ziele im Überblick." },
};

function CouncilInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  // Tab lives in the URL (?tab=…) so the browser back button from a decision detail
  // page returns to the right tab. The combined search is the default landing.
  const param = searchParams.get("tab");
  const tab: Tab =
    param === "ask" ? "decisions"                              // QA is now the "KI-Frage" mode of Suche
    : param === "trends" || param === "goals" ? "analysis"     // now Analyse sub-tabs
    : param === "sessions" || param === "themen" || param === "analysis" ? param
    : "decisions";
  const [committees, setCommittees] = useState<string[]>([]);

  // Keep old standalone-tab links working by redirecting them to their new home.
  useEffect(() => {
    if (param === "ask") router.replace("/council?tab=decisions&mode=fragen", { scroll: false });
    else if (param === "goals") router.replace("/council?tab=analysis&sub=ziele", { scroll: false });
    else if (param === "trends") router.replace("/council?tab=analysis&sub=trends", { scroll: false });
  }, [param, router]);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

  const meta = TAB_META[tab];
  return (
    <div>
      <PageHeader title={meta.title} description={meta.description} />
      {/* Bewusst KEINE eigene Tab-Leiste hier: Sitzungen/Themen/Analyse sind mobil
          übers Burger-Menü erreichbar — eine dritte Navigation (neben Burger und
          Bottom-Nav) verwirrte mehr, als sie half. */}
      {tab === "decisions" ? <SearchTab committees={committees} />
        : tab === "sessions" ? <SessionsTab committees={committees} />
        : tab === "themen" ? <EntitiesTab />
        : <AnalysisTab />}
    </div>
  );
}

export default function CouncilPage() {
  return (
    <Suspense>
      <CouncilInner />
    </Suspense>
  );
}
