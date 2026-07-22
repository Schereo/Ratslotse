"use client";

import { useEffect, useRef, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, ExternalLink, ChevronDown, ChevronRight, Scale, SlidersHorizontal, Users, Sparkles, Split, X } from "lucide-react";
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
import { OutcomeBadge, OutcomeDot, ImportanceBadge, OUTCOME_META, formatEuro, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { CommitteeName } from "@/components/committee-name";
import { shortCommittee, hasShortCommittee } from "@/lib/committees";
import { isLiveNow } from "@/lib/live";
import { reportBadgeEvent } from "@/components/badges";
import { ChipPopover, DateRangeChip } from "@/components/filter-chips";
import { SitzungspauseBanner } from "@/components/sitzungspause-banner";
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

/** Fußzeile der Beschlusskarte (Design 22a, Zone 3): Abstimmung + Antrag links,
 *  Betrag als betonter rechter Anker mit „im Beschluss"-Mini-Label. Jeder Teil
 *  fällt bei fehlendem Wert weg; ist alles leer, rendert die Fußzeile nicht —
 *  so bleibt die Zonenstruktur stabil, statt dass Elemente nachrutschen. */
function CardFooter({ d }: { d: CouncilDecision }) {
  // Defensiv: factions kann bei kaputten Daten ein String sein (Store json.dumps't
  // unbesehen) — nie die ganze Seite in die Error-Boundary reißen.
  const factions = Array.isArray(d.factions) ? d.factions : [];
  const parts: string[] = [];
  if (d.vote) parts.push(d.vote);
  if (d.gegenstimmen) parts.push(`${d.gegenstimmen} dagegen`);
  if (d.enthaltungen) parts.push(`${d.enthaltungen} Enth.`);
  const hasAmount = d.kind !== "subvote" && d.amount_eur != null;
  if (parts.length === 0 && factions.length === 0 && !hasAmount) return null;
  return (
    <div className="mt-3 flex items-end justify-between gap-3">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        {parts.length > 0 && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Scale className="h-3.5 w-3.5 shrink-0" /> {parts.join(" · ")}
          </span>
        )}
        {factions.length > 0 && (
          <span
            className="inline-flex flex-wrap items-center gap-1.5"
            title="Fraktion(en), die zu diesem Punkt einen Antrag oder eine Änderungsliste eingebracht haben"
          >
            <span className="text-xs text-muted-foreground">Antrag:</span>
            {factions.map((f) => (
              <span key={f} className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{f}</span>
            ))}
          </span>
        )}
      </div>
      {hasAmount && (
        <div className="shrink-0 text-right" title="Im Beschlusstext genannter Betrag">
          <div className="text-base font-bold leading-none tabular-nums text-foreground">{formatEuro(d.amount_eur!)}</div>
          <div className="mt-0.5 text-[10px] font-medium text-muted-foreground">im Beschluss</div>
        </div>
      )}
    </div>
  );
}

/** Text der Änderungsantrags-Unterzeile (Design 23a): „n Änderungsantrag ·
 *  Fraktion · Ergebnis". Das Ergebnis nur, wenn alle Anträge gleich ausgingen. */
function subvoteLabel(s: NonNullable<CouncilDecision["subvote_summary"]>): string {
  const parts = [`${s.count} ${s.count === 1 ? "Änderungsantrag" : "Änderungsanträge"}`];
  if (s.factions.length > 0) parts.push(s.factions.join(", "));
  if (s.outcomes.length === 1) parts.push(OUTCOME_META[s.outcomes[0] as DecisionOutcome]?.label.toLowerCase() ?? s.outcomes[0]);
  return parts.join(" · ");
}

function DecisionCard({ d, query }: { d: CouncilDecision; query: string }) {
  const isSub = d.kind === "subvote";
  const sub = d.subvote_summary;
  return (
    <Link href={decisionHref(d.id)} className="block">
      {/* Design 22a: drei feste Zonen statt verstreuter Elemente — Statuszeile
          (Ergebnis-Punkt + „Wichtig" zusammen, Chevron rechts; Gremium·Datum·TOP
          als ruhige zweite Zeile) → Titel + 2-Zeilen-Auszug → Fußzeile
          (Abstimmung + Antrag links, Betrag als betonter rechter Anker). Subvote
          bleibt ohne Akzent-Border (RL-102), nur „Teilabstimmung"-Zeile + Tönung. */}
      <Card className={cn("card-interactive group overflow-hidden p-0", isSub && "bg-muted/30")}>
        <div className="p-4">
          {/* Zone 1 — Statuszeile */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
              <OutcomeDot outcome={d.outcome} />
              {!isSub && <ImportanceBadge score={d.importance} />}
            </div>
            <ChevronRight className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {isSub
              ? `Teilabstimmung · TOP ${d.parent_item}`
              : `${shortCommittee(d.committee)} · ${formatDate(d.session_date)}${d.item_number ? ` · TOP ${d.item_number}` : ""}`}
          </p>

          {/* Zone 2 — Titel + Auszug */}
          <h3 className="mt-2 hyphens-auto font-medium text-foreground">
            <Highlight text={d.title ?? ""} query={query} />
          </h3>
          {d.beschluss && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
              <Highlight text={d.beschluss} query={query} />
            </p>
          )}

          {/* Zone 3 — Fußzeile */}
          <CardFooter d={d} />
        </div>

        {/* Design 23a: Änderungsanträge hängen als Kontext-Unterzeile am
            Ursprungsbeschluss, statt als eigene Treffer zu erscheinen. */}
        {sub && sub.count > 0 && (
          <div className="flex items-center gap-2 border-t border-border bg-muted/30 px-4 py-2.5 text-sm text-muted-foreground">
            <Split className="h-3.5 w-3.5 shrink-0 -scale-x-100" />
            <span className="min-w-0 flex-1 truncate">{subvoteLabel(sub)}</span>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/40" />
          </div>
        )}
      </Card>
    </Link>
  );
}

const PAGE_SIZE = 50;

const SORTS: { value: string; label: string; sub?: string; icon?: typeof Sparkles }[] = [
  { value: "date_desc", label: "Neueste zuerst" },
  { value: "date_asc", label: "Älteste zuerst" },
  { value: "importance", label: "Wichtigste zuerst" },
  // RL-U15 (13a-C): Unterhaltungs-Sortierung — klar getrennt von „Wichtigste".
  { value: "interest", label: "Spannendste zuerst", sub: "Gesprächswert — kurios & alltagsnah", icon: Sparkles },
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

/** Suchfeld mit Lupe, Löschen-Taste (RL-U03) und „Suchen"-Enter auf der
 *  iOS-Tastatur. Das ✕ erscheint ab dem ersten Zeichen, leert und fokussiert
 *  neu — volle Feldhöhe als Touch-Ziel. */
function SearchBox({
  value, onChange, placeholder, large = false, tour,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  large?: boolean;
  tour?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="relative">
      <Search className={cn(
        "pointer-events-none absolute top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground",
        large ? "left-4" : "left-3",
      )} />
      <Input
        ref={ref}
        data-search
        data-tour={tour}
        enterKeyHint="search"
        className={cn(large ? "h-12 rounded-[14px] pl-11 pr-12 text-base" : "pl-9 pr-11")}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && (
        <button
          type="button"
          onClick={() => { onChange(""); ref.current?.focus(); }}
          aria-label="Suche leeren"
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      )}
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

function DecisionsTab({ committees }: { committees: string[] }) {
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
  // Design 23a: Änderungsanträge (subvotes) sind standardmäßig aus der Liste
  // ausgeblendet (Kontext am Ursprungsbeschluss). Rechercheure blenden sie
  // optional wieder einzeln ein.
  const showSubvotes = sp.get("subvotes") === "1";
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
          include_subvotes: showSubvotes ? "1" : "",
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
  }, [q, committee, mode, outcome, sort, field, party, dateFrom, dateTo, showSubvotes, page]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, mode, outcome, sort, field, party, dateFrom, dateTo, showSubvotes, page]);

  // RL-U02: Seitenwechsel führt zurück zum Listenanfang und setzt den Fokus
  // auf den Listen-Container (bleibt über den Ladewechsel gemountet), damit
  // Screenreader den Kontextwechsel mitbekommen.
  const listRef = useRef<HTMLDivElement>(null);
  const changePage = (p: number) => {
    setPage(p);
    requestAnimationFrame(() => {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      listRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      listRef.current?.focus({ preventScroll: true });
    });
  };

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
            {committees.map((c) => <option key={c} value={c} title={c}>{shortCommittee(c)}</option>)}
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
      {/* Design 23a: Änderungsanträge hängen normal als Kontext am Ursprungs-
          beschluss; Rechercheure können sie hier als eigene Treffer einblenden. */}
      <FilterField label="Teilabstimmungen">
        <button
          type="button"
          onClick={() => { setUrlParam("subvotes", showSubvotes ? "" : "1"); setPage(1); }}
          aria-pressed={showSubvotes}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
            showSubvotes ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:bg-muted",
          )}
        >
          <Split className="h-3.5 w-3.5 -scale-x-100" /> Änderungsanträge einzeln zeigen
        </button>
      </FilterField>
    </div>
  );

  return (
    <div>
      {/* RL-501: großes Suchfeld über der Liste, Filter als Chip-Zeile
          (Desktop: Popover-Chips; mobil bleibt das Bottom-Sheet). */}
      <div className="mt-3">
        <SearchBox
          large
          tour="beschluss-suche"
          placeholder={isReport ? "Berichte durchsuchen…" : "Suchen (z. B. Haushalt, Radwege)…"}
          value={q}
          onChange={(v) => { setQ(v); setPage(1); }}
        />
      </div>

      <div className="mt-3 hidden flex-wrap items-center gap-2 md:flex">
        <ChipPopover
          label="Beschlüsse"
          clearable={false}
          defaultValue="vote"
          value={mode}
          options={[
            { value: "vote", label: "Beschlüsse" },
            { value: "report", label: "Berichte" },
            { value: "all", label: "Alle Vorgänge" },
          ]}
          onChange={(m) => { setUrlParam("cat", m === "vote" ? "" : m); setOutcome(""); }}
        />
        {fields.length > 0 && (
          <ChipPopover
            label="Themenfeld"
            value={field}
            display={fields.find((f) => f.key === field)?.label}
            options={fields.map((f) => ({ value: f.key, label: `${f.label} (${f.count})` }))}
            onChange={(v) => setUrlParam("field", v)}
          />
        )}
        <ChipPopover
          label="Ausschuss"
          value={committee}
          options={committees.map((c) => ({ value: c, label: shortCommittee(c), sub: hasShortCommittee(c) ? c : undefined }))}
          onChange={(v) => { setCommittee(v); setPage(1); }}
        />
        {mode === "vote" && (
          <ChipPopover
            label="Ergebnis"
            value={outcome}
            options={OUTCOME_CHIPS.filter((o) => o.value !== "")}
            onChange={(v) => { setOutcome(v); setPage(1); }}
          />
        )}
        <DateRangeChip from={dateFrom} to={dateTo} onChange={(f, t) => setUrlParams({ date_from: f, date_to: t })} />
        <div className="ml-auto">
          <ChipPopover
            ghost
            clearable={false}
            label="Sortierung"
            value={sort}
            display={SORTS.find((s) => s.value === sort)?.label}
            options={SORTS}
            onChange={(v) => { setSort(v); setPage(1); }}
          />
        </div>
      </div>

      <div className="mt-3 md:hidden">
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
            {committee && <FilterChip label={shortCommittee(committee)} onClear={() => { setCommittee(""); setPage(1); }} />}
            {(dateFrom || dateTo) && (
              <FilterChip
                label={`${dateFrom ? formatDate(dateFrom) : "…"} – ${dateTo ? formatDate(dateTo) : "heute"}`}
                onClear={() => setUrlParams({ date_from: "", date_to: "" })}
              />
            )}
          </div>
        )}
      </div>

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

      <div ref={listRef} tabIndex={-1} className="mt-6 outline-none">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : decisions.length === 0 ? (
          <EmptyState
            mascot="search"
            title={`Keine ${isReport ? "Berichte" : "Beschlüsse"} gefunden`}
            hint="Andere Suche/Filter — oder frag die KI: Sie sucht semantisch statt wortwörtlich."
            action={
              <Button
                variant="signal"
                size="sm"
                onClick={() => {
                  const params = new URLSearchParams(sp.toString());
                  params.set("tab", "decisions");
                  params.set("mode", "fragen");
                  if (query) params.set("q", query);
                  router.replace(`/council?${params.toString()}`, { scroll: false });
                }}
              >
                <Sparkles /> KI-Frage stellen
              </Button>
            }
          />
        ) : (
          <div className="space-y-2.5">
            {/* RL-F07: Trefferzeile gleitet bei Filterwechsel neu ein (key-Remount). */}
            <p key={`${total}|${query}|${outcome}|${field}|${committee}`} className="animate-fade-up text-sm font-medium text-muted-foreground">
              {total} {noun}
              {query && <> zu <strong className="font-semibold text-foreground">{query}</strong></>}
            </p>
            {decisions.map((d) => <DecisionCard key={d.id} d={d} query={query} />)}
            <Pagination page={page} totalPages={totalPages} onChange={changePage} className="pt-2" />
          </div>
        )}
      </div>
    </div>
  );
}

/** RL-U10: kleiner LIVE-Chip an der laufenden Sitzung (Startzeit + 4 h). */
function LiveChip() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-bold text-red-600 dark:text-red-400">
      <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-hidden /> LIVE
    </span>
  );
}

/** Monats/Tages-Kachel 50 px (RL-801, Design 6a-Sitzungen). */
function DateTile({ iso }: { iso: string }) {
  const d = new Date(iso + "T12:00:00");
  return (
    <span className="w-[50px] shrink-0 rounded-lg border border-border bg-muted/40 py-1 text-center">
      <span className="block font-mono text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {d.toLocaleDateString("de-DE", { month: "short" }).replace(".", "")}
      </span>
      <span className="block font-display text-lg font-bold leading-tight text-foreground">{d.getDate()}</span>
    </span>
  );
}

function AgendaRow({ it, query, outcome, myTopic }: { it: AgendaItem; query: string; outcome?: DecisionOutcome | null; myTopic?: string }) {
  const hit = itemMatches(it, query);
  return (
    <li className={cn(
      "flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-2",
      hit ? "bg-amber-50 dark:bg-amber-950/40" : myTopic && "bg-signal/5",
    )}>
      <span className="w-7 shrink-0 text-xs font-medium text-muted-foreground">{it.item_number}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-foreground"><Highlight text={it.title} query={query} /></p>
        {it.vorlage_nr && <p className="text-xs text-muted-foreground">Vorlage <Highlight text={it.vorlage_nr} query={query} /></p>}
        {myTopic && (
          /* RL-902: TOP passt zu einem eigenen Thema. */
          <span className="mt-1 inline-flex rounded-full bg-signal/10 px-2 py-0.5 text-[11px] font-semibold text-signal">
            dein Thema · {myTopic}
          </span>
        )}
      </div>
      {outcome ? <OutcomeDot outcome={outcome} /> : !it.is_public ? <Badge color="amber">nichtöffentlich</Badge> : null}
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
  // RL-F06: ?ksinr=… (Deep-Link von „Heute") — Sitzung aufklappen, sanft
  // hinscrollen und kurz aufblitzen lassen (wie der Fußnoten-Flash der KI).
  const deepSp = useSearchParams();
  const targetKsinr = Number(deepSp.get("ksinr") || 0);
  const deepLinkDone = useRef(false);
  const [flashKsinr, setFlashKsinr] = useState<number | null>(null);
  const [scope, setScope] = useState<Scope>("upcoming");
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [detail, setDetail] = useState<Record<number, SessionDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<number, boolean>>({});
  const debouncedQ = useDebounce(q, 350);
  // RL-U04: Leerzustand und Pause-Banner sollen miteinander reden — dieselbe
  // Query wie im Banner (React Query dedupliziert, staleTime 1 h).
  const { data: pause } = useQuery({
    queryKey: ["sitzungspause"],
    queryFn: () => api.get<{ active: boolean }>("/council/sitzungspause"),
    staleTime: 60 * 60 * 1000,
  });

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

  useEffect(() => {
    if (!targetKsinr || deepLinkDone.current || loading) return;
    const s = sessions.find((x) => x.ksinr === targetKsinr);
    if (!s) return;
    deepLinkDone.current = true;
    void toggle(s);
    requestAnimationFrame(() => {
      document.getElementById(`session-${targetKsinr}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    setFlashKsinr(targetKsinr);
    const t = setTimeout(() => setFlashKsinr(null), 1600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKsinr, loading, sessions]);

  const toggle = async (s: CouncilSession) => {
    const ksinr = s.ksinr;
    if (ksinr == null) return; // terminierte Sitzung ohne Tagesordnung
    const willExpand = !expanded[ksinr];
    setExpanded((prev) => ({ ...prev, [ksinr]: willExpand }));
    if (willExpand) reportBadgeEvent("sitzung"); // RL-U12: Sitzungsgast
    if (willExpand && !detail[ksinr]) {
      setDetailLoading((prev) => ({ ...prev, [ksinr]: true }));
      try {
        const d = await api.get<SessionDetail>(`/council/session/${ksinr}`);
        setDetail((prev) => ({ ...prev, [ksinr]: d }));
      } catch {
        toast.error("Sitzung konnte nicht geladen werden.");
        setExpanded((prev) => ({ ...prev, [ksinr]: false }));
      } finally {
        setDetailLoading((prev) => ({ ...prev, [ksinr]: false }));
      }
    }
  };

  const query = q.trim();

  return (
    <div>
      {/* RL-801/402: kompakter Pause-Hinweis direkt über der Liste. */}
      <SitzungspauseBanner compact className="mt-4" />
      <Card className="mt-4 p-4">
        <div className="space-y-3">
          <SearchBox placeholder="In Tagesordnungen suchen (z. B. Bebauungsplan)…" value={q} onChange={setQ} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={committee} onChange={(e) => setCommittee(e.target.value)}>
              <option value="">Alle Ausschüsse</option>
              {committees.map((c) => <option key={c} value={c} title={c}>{shortCommittee(c)}</option>)}
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
          // RL-U04: In der Sitzungspause ist „Kommend" leer, das Banner darüber
          // nennt den Grund — der Leerzustand greift ihn auf, statt generisch
          // „keine Sitzungen" zu behaupten.
          pause?.active && scope === "upcoming" && !q && !committee ? (
            <EmptyState
              mascot="sleep"
              title="Sitzungspause — der Rat tagt gerade nicht"
              hint="Sobald das Ratsinformationssystem neue Termine veröffentlicht, erscheinen sie hier."
              action={
                <Button variant="secondary" size="sm" onClick={() => setScope("recent")}>
                  Vergangene Sitzungen ansehen
                </Button>
              }
            />
          ) : (
            <EmptyState mascot="search" title={hasSearched ? "Keine Sitzungen gefunden" : "Noch keine Sitzungen vorhanden"} hint={hasSearched ? "Versuche andere Suchbegriffe oder Filter." : undefined} />
          )
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground">{sessions.length} {sessions.length === 1 ? "Sitzung" : "Sitzungen"}</p>
            {sessions.map((s) => {
              // Terminierte Sitzung aus dem RIS-Kalender: noch keine
              // Tagesordnung veröffentlicht → nichts zum Aufklappen/Verlinken.
              if (s.ksinr == null) {
                return (
                  <Card key={`${s.committee}|${s.session_date}|${s.session_time}`} className="p-4">
                    {/* Mobil wandert die Badge unter den Text — sonst quetscht
                        sie den Gremiumsnamen auf „Ausschuss …" zusammen. */}
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <DateTile iso={s.session_date} />
                        <div className="min-w-0">
                          <CommitteeName name={s.committee} className="font-display text-base font-bold text-foreground" />
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {s.session_time ? `${s.session_time} Uhr` : "Uhrzeit folgt"}
                            {s.location && ` · ${s.location}`}
                          </p>
                        </div>
                      </div>
                      <div className="ml-[62px] flex shrink-0 items-center gap-2 self-start sm:ml-0 sm:self-auto">
                        {isLiveNow(s) && <LiveChip />}
                        <Badge>Tagesordnung folgt</Badge>
                      </div>
                    </div>
                  </Card>
                );
              }
              const isExpanded = !!expanded[s.ksinr];
              const matched = s.matched_items ?? [];
              const d = detail[s.ksinr];
              const outcomeByItem: Record<string, DecisionOutcome | null> = {};
              for (const dec of d?.decisions ?? []) {
                if (dec.kind === "decision" && dec.item_number) outcomeByItem[dec.item_number] = dec.outcome;
              }
              // RL-902: TOPs, die zu eigenen Themen passen (TOP → Themenname).
              const myByItem: Record<string, string> = {};
              for (const m of s.my_topic_items ?? []) myByItem[m.item_number] ??= m.topic_name;
              const myCount = Object.keys(myByItem).length;
              return (
                <Card
                  key={s.ksinr}
                  id={`session-${s.ksinr}`}
                  className={cn(
                    "overflow-hidden p-0 transition-shadow",
                    flashKsinr === s.ksinr && "ring-2 ring-primary",
                  )}
                >
                  <button type="button" onClick={() => toggle(s)} className="group flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/40">
                    <div className="flex min-w-0 items-center gap-3">
                      <DateTile iso={s.session_date} />
                      <div className="min-w-0">
                        <CommitteeName name={s.committee} className="font-display text-base font-bold text-foreground" />
                        <p className="mt-0.5 truncate text-sm text-muted-foreground">{s.session_time} Uhr · {s.location}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {isLiveNow(s) && <LiveChip />}
                      {myCount > 0 && (
                        <span className="hidden rounded-full bg-signal/10 px-2 py-0.5 text-[11px] font-semibold text-signal sm:inline-flex">
                          {myCount} zu deinen Themen
                        </span>
                      )}
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
                                <AgendaRow key={i} it={it} query={query} outcome={outcomeByItem[it.item_number]} myTopic={myByItem[it.item_number]} />
                              ))}
                            </ul>
                            {d && <AttendanceSection detail={d} />}
                          </>
                        )
                      ) : query ? (
                        matched.length > 0 ? (
                          <>
                            <p className="mb-1 px-2 text-xs font-medium text-muted-foreground">{matched.length} Treffer in der Tagesordnung</p>
                            <ul className="space-y-0.5">{matched.map((it, i) => <AgendaRow key={i} it={it} query={query} myTopic={myByItem[it.item_number]} />)}</ul>
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
  const mode: "suchen" | "fragen" = sp.get("mode") === "fragen" ? "fragen" : "suchen";
  // RL-U01: Beide Modi bleiben gemountet und werden per `hidden` getauscht —
  // eine gestreamte KI-Antwort überlebt so den Wechsel zu „Suchen" und zurück
  // (Nutzer vergleichen genau so). Abbruch des Streams erst beim Unmount der
  // Seite. Scroll-Position je Modus merken: der Scroll-Container ist #main.
  const prevMode = useRef(mode);
  const scrollPos = useRef<Record<"suchen" | "fragen", number>>({ suchen: 0, fragen: 0 });
  useEffect(() => {
    if (prevMode.current === mode) return;
    const scroller = document.getElementById("main");
    scrollPos.current[prevMode.current] = scroller?.scrollTop ?? 0;
    prevMode.current = mode;
    requestAnimationFrame(() => {
      if (scroller) scroller.scrollTop = scrollPos.current[mode] ?? 0;
    });
  }, [mode]);
  // Umschalter lebt jetzt im Seitenkopf (RL-501, 6a) — die Tabs rendern ohne.
  return (
    <>
      <div hidden={mode !== "suchen"}>
        <DecisionsTab committees={committees} />
      </div>
      <div hidden={mode !== "fragen"}>
        <QaTab />
      </div>
    </>
  );
}

/** „Suchen | KI-Frage"-Umschalter im Seitenkopf (RL-501); qa-glint-Lockruf
 *  bleibt, bis die erste Frage gestellt wurde (Flag setzt council-qa). */
function SearchModeToggle() {
  const sp = useSearchParams();
  const router = useRouter();
  const mode: "suchen" | "fragen" = sp.get("mode") === "fragen" ? "fragen" : "suchen";
  const [qaUsed, setQaUsed] = useState(true);
  useEffect(() => {
    setQaUsed(localStorage.getItem("ratslotse:qa-benutzt") === "1");
  }, [mode]);
  const setMode = (m: "suchen" | "fragen") => {
    const params = new URLSearchParams(sp.toString());
    params.set("tab", "decisions");
    if (m === "suchen") params.delete("mode"); else params.set("mode", m);
    router.replace(`/council?${params.toString()}`, { scroll: false });
  };
  return (
    <Segmented
      className="sm:w-fit"
      value={mode}
      onChange={setMode}
      options={[
        { value: "suchen", label: "Suchen", icon: Search },
        { value: "fragen", label: "KI-Frage", icon: Sparkles, tour: "ki-frage-tab", sparkle: !qaUsed },
      ]}
    />
  );
}

// Navigation between these views now lives in the left sidebar (Ratsinfo section),
// so the page only needs a per-view title/description instead of an in-page tab bar.
const TAB_META: Record<Tab, { title: string; description: string }> = {
  decisions: { title: "Suchen & Fragen", description: "Beschlüsse durchsuchen oder dem Rat eine KI-Frage stellen." },
  sessions: { title: "Sitzungen", description: "Sitzungen und Tagesordnungen von Rat und Ausschüssen." },
  themen: { title: "Themen", description: "Was den Rat wo beschäftigt — auf der Stadtkarte und als Liste." },
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
      <PageHeader
        title={meta.title}
        description={meta.description}
        action={tab === "decisions" ? <SearchModeToggle /> : undefined}
      />
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
