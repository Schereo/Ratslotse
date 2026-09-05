"use client";

import { Fragment, useEffect, useMemo, useRef, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, ExternalLink, ChevronDown, ChevronRight, Scale, SlidersHorizontal, Users, Sparkles, Split, X, Flame, History, CalendarPlus, Paperclip, MapPin } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { fragenHref, decisionHref, ortHref, sitzungHref } from "@/lib/routes";
import { STAFFEL, staffelStil } from "@/components/staffel";
import { Aufklapp } from "@/components/aufklapp";
import { useDebounce } from "@/lib/use-debounce";
import { clearRecentSearches, getRecentSearches, pushRecentSearch } from "@/lib/recent-searches";
import { offerIcs } from "@/lib/ics";
import {
  AgendaAenderung, AgendaRowItem, CouncilSession, SessionDetail, AgendaItem, CouncilDecision, DecisionOutcome,
  PolicyField, Topic, VideoResult,
} from "@/lib/types";
import { VideoResultChip, VideoResultsNotice } from "@/components/video-result";
import {
  Badge, Button, Card, CardListSkeleton, DateField, EmptyState, Input, PageHeader, Pagination, Segmented, Select,
  Sheet, SheetContent, SheetTitle, SheetTrigger, Spinner, formatDate, toast,
} from "@/components/ui";
import { OutcomeBadge, OutcomeDot, ImportanceBadge, OUTCOME_META, voteLabel, formatEuro, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { CommitteeName } from "@/components/committee-name";
import { shortCommittee, hasShortCommittee, committeeIcon } from "@/lib/committees";
import { isLiveNow, liveItemKeys, liveStateFresh } from "@/lib/live";
import { reportBadgeEvent } from "@/components/badges";
import { ChipPopover, DateRangeChip } from "@/components/filter-chips";
import { SitzungspauseBanner } from "@/components/sitzungspause-banner";
import { AnalysisTab } from "@/components/council-analysis";
import { EntitiesTab } from "@/components/council-entities";
import { cn, relativerTag, wochentagKurz } from "@/lib/utils";
import { useHeute } from "@/lib/use-heute";
import { useMerker } from "@/lib/use-merker";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import {
  AenderungenSection, AgendaRow, AttendanceSection, DringlichkeitsBlock, Highlight, agendaNumber,
  CalendarButton, DateTile, LiveChip, ergebnisseJeTop, hasAgendaChildren, itemMatches, sessionUrl, topDomId, topKey,
  useTopSprung, videoKey,
  useTopsAusLink,
} from "@/components/tagesordnung";

type Scope = "all" | "upcoming" | "recent";
type Tab = "sessions" | "decisions" | "themen" | "analysis";


/** Fußzeile der Beschlusskarte (Design 22a, Zone 3): Abstimmung + Antrag links,
 *  Betrag als betonter rechter Anker mit „im Beschluss"-Mini-Label. Jeder Teil
 *  fällt bei fehlendem Wert weg; ist alles leer, rendert die Fußzeile nicht —
 *  so bleibt die Zonenstruktur stabil, statt dass Elemente nachrutschen. */
function CardFooter({ d }: { d: CouncilDecision }) {
  // Defensiv: factions kann bei kaputten Daten ein String sein (Store json.dumps't
  // unbesehen) — nie die ganze Seite in die Error-Boundary reißen.
  const factions = Array.isArray(d.factions) ? d.factions : [];
  const parts: string[] = [];
  if (d.vote) parts.push(voteLabel(d.vote));
  if (d.no_votes) parts.push(`${d.no_votes} dagegen`);
  if (d.abstentions) parts.push(`${d.abstentions} Enth.`);
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

function DecisionCard({ d, query, rang = 0 }: { d: CouncilDecision; query: string; rang?: number }) {
  const isSub = d.kind === "subvote";
  const sub = d.subvote_summary;
  const locationMatches = d.location_matches ?? [];
  const primaryLocation = locationMatches[0];
  const locationProfileId = primaryLocation?.place_id ?? primaryLocation?.local_area_id;
  const router = useRouter();
  const sp = useSearchParams();
  // 5a/I-08: aus der Trefferkarte direkt ins Ratsgespräch — die Frage steht
  // vorbefüllt im Composer, gesendet wird bewusst erst per Hand.
  const dazuFragen = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    router.push(fragenHref({ q: `Erzähl mir mehr zu „${d.title ?? ""}".` }));
  };
  return (
    // Die Treffer laufen der Reihe nach ein, statt als Block dazustehen — bei
    // einer neuen Suche oder einer neuen Seite montiert React sie ohnehin neu
    // (`key` ist die Beschluss-ID), die Bewegung läuft also genau dann, wenn
    // sich die Liste wirklich ändert.
    <Link href={decisionHref(d.id)} className={cn("block", STAFFEL)} style={staffelStil(rang)}>
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
            <span className="flex shrink-0 items-center gap-1">
              <button type="button" onClick={dazuFragen} title="Im Ratsgespräch dazu fragen"
                aria-label={`Im Ratsgespräch zu „${d.title ?? ""}" fragen`}
                className="rounded-md p-1 text-muted-foreground opacity-60 transition-opacity hover:bg-muted hover:text-primary focus:opacity-100 sm:opacity-0 sm:group-hover:opacity-100">
                <Sparkles className="h-4 w-4" aria-hidden />
              </button>
              <ChevronRight className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </span>
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
          {d.official_text && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
              <Highlight text={d.official_text} query={query} />
            </p>
          )}
          {primaryLocation && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-primary/5 px-2.5 py-2 text-xs">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
              <div className="min-w-0">
                <p className="text-foreground">
                  <span className="font-medium">Ortsbezug:</span>{" "}
                  {locationMatches.slice(0, 2).map((match) => match.name).join(", ")}
                  {locationMatches.length > 2 ? ` +${locationMatches.length - 2}` : ""}
                  <span className="text-muted-foreground"> · {primaryLocation.district}</span>
                  {locationProfileId && (
                    <button type="button" onClick={(event) => {
                      event.preventDefault(); event.stopPropagation(); router.push(ortHref(locationProfileId));
                    }} className="ml-1 font-medium text-primary hover:underline">
                      Ortsprofil
                    </button>
                  )}
                </p>
                <p className="mt-0.5 line-clamp-1 text-muted-foreground">
                  Fundstelle: „{primaryLocation.evidence}“
                </p>
              </div>
            </div>
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
  // Wichtigkeit mit Alters-Dämpfung (siehe CouncilStore.search_decisions) —
  // sonst stehen hier nur alte Haushaltsbeschlüsse.
  { value: "importance", label: "Wichtigste zuerst", sub: "Wichtigkeit & Aktualität", icon: Flame },
  { value: "faction", label: "Nach Fraktion" },
];

const OUTCOME_CHIPS: { value: string; label: string }[] = [
  { value: "", label: "Alle" },
  { value: "accepted", label: "Angenommen" },
  { value: "rejected", label: "Abgelehnt" },
  { value: "postponed", label: "Vertagt" },
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
  value, onChange, placeholder, large = false, tour, withHistory = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  large?: boolean;
  tour?: string;
  /** Design 28a/R6: Verlauf + Vorschläge beim Fokus auf leerem Feld. */
  withHistory?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<string[]>([]);

  // Der Verlauf liegt in localStorage — erst beim Öffnen lesen, damit ein
  // Eintrag aus derselben Sitzung sofort auftaucht (und der Server-Render
  // nichts vom Gerät weiß).
  const openPanel = () => {
    if (!withHistory) return;
    setHistory(getRecentSearches());
    setOpen(true);
  };

  const suggestions = useQuery({
    queryKey: ["topic-suggestions"],
    queryFn: () =>
      api.get<{ suggestions: { name: string }[] }>("/topics/suggestions").then((d) => d.suggestions),
    // Nur laden, wenn das Panel wirklich offen ist: Der Endpoint prüft
    // Vorschläge notfalls per LLM — er gehört nicht in jeden Seitenaufruf.
    enabled: withHistory && open && !value.trim(),
    staleTime: 30 * 60 * 1000,
  });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const pick = (v: string) => {
    onChange(v);
    pushRecentSearch(v);
    setOpen(false);
    ref.current?.focus();
  };

  const vorschlaege = (suggestions.data ?? []).map((s) => s.name).slice(0, 5);
  const showPanel = open && !value.trim() && (history.length > 0 || vorschlaege.length > 0);

  return (
    <div className="relative" ref={wrapRef}>
      <Search className={cn(
        "pointer-events-none absolute top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground",
        large ? "left-4" : "left-3",
      )} />
      <Input
        ref={ref}
        data-search
        data-tour={tour}
        enterKeyHint="search"
        // Der eigene Verlauf (28a/R6) und die Browser-Autovervollständigung
        // legten sich sonst übereinander — zwei Listen, eine davon mit fremden
        // Einträgen. Rechtschreibprüfung im Suchfeld unterkringelt außerdem
        // jeden Straßennamen.
        autoComplete="off"
        spellCheck={false}
        className={cn(large ? "h-12 rounded-[14px] pl-11 pr-12 text-base" : "pl-9 pr-11")}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={openPanel}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
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

      {showPanel && (
        // onMouseDown verhindern: sonst verliert das Feld den Fokus, bevor der
        // Klick auf einen Vorschlag ankommt.
        <div
          onMouseDown={(e) => e.preventDefault()}
          className="absolute inset-x-0 top-full z-30 mt-1.5 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-lifted"
        >
          {history.length > 0 && (
            <>
              <p className="flex items-center justify-between gap-2 px-2 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
                Zuletzt gesucht
                <button
                  type="button"
                  onClick={() => { clearRecentSearches(); setHistory([]); }}
                  className="rounded px-1 py-0.5 text-[11px] normal-case tracking-normal transition-colors hover:text-foreground"
                >
                  Löschen
                </button>
              </p>
              {history.map((h) => (
                <button
                  key={h} type="button" onClick={() => pick(h)}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-foreground transition-colors hover:bg-accent"
                >
                  <History className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
                  <span className="truncate">{h}</span>
                </button>
              ))}
            </>
          )}
          {vorschlaege.length > 0 && (
            <>
              <p className="px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
                Gerade im Rat
              </p>
              {vorschlaege.map((s) => (
                <button
                  key={s} type="button" onClick={() => pick(s)}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-foreground transition-colors hover:bg-accent"
                >
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-signal" />
                  <span className="truncate">{s}</span>
                </button>
              ))}
            </>
          )}
        </div>
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
  const [q, setQ] = useMerker("suche:q", "");
  const [committee, setCommittee] = useMerker("suche:committee", "");
  const [outcome, setOutcome] = useMerker("suche:result", "");
  const [sort, setSort] = useState("date_desc");
  const [fields, setFields] = useState<PolicyField[]>([]);
  const [districts, setDistricts] = useState<{
    place_id: string; name: string; kind: string; kind_label: string; parent_ids: string[];
    count: number; vote_count: number; report_count: number;
  }[]>([]);
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [decisions, setDecisions] = useState<CouncilDecision[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const debouncedQ = useDebounce(q, 350);

  // Design 28a/R6: erst die beruhigte Eingabe merken, nicht jeden Tastendruck.
  // Zwischenstände wie „rad" auf dem Weg zu „radwege" räumt pushRecentSearch
  // selbst wieder ab (Präfixe des neuen Begriffs fliegen raus).
  useEffect(() => { pushRecentSearch(debouncedQ); }, [debouncedQ]);

  // Field + party live in the URL so the analysis and badges can deep-link to a filtered list.
  const sp = useSearchParams();
  const router = useRouter();
  /* Design 28a/S4: ?topic= schränkt auf die Treffer eines eigenen Themas ein —
     der Ersatz für den früheren Trefferdialog. Steht in der URL, ist also
     teilbar und überlebt Zurück; den Namen holen wir für den Chip aus der
     Themenliste, die ohnehin gecacht ist. */
  const topicId = sp.get("topic") ?? "";
  const { data: myTopics } = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
    enabled: !!topicId,
  });
  const myTopic = myTopics?.find((t) => String(t.id) === topicId);
  const topicName = myTopic?.name ?? "";
  /* Hat der Matching-Lauf mehr Treffer gefunden, als er speichern durfte, ist
     JEDE Zahl hier eine Untergrenze — auch eine zusätzlich gefilterte. Dann
     steht dasselbe „+" wie auf der Themen-Karte davor, statt eine Endzahl zu
     behaupten, die keine ist. */
  const topicCapped = !!topicId && !!myTopic?.decision_count_capped;

  // ?q= aus der URL übernehmen (Deep-Link aus der Command-Palette) — einmalig
  // nach dem Mount, um keinen Hydration-Mismatch im Input zu erzeugen.
  useEffect(() => {
    const urlQ = sp.get("q");
    if (urlQ) setQ(urlQ);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const field = sp.get("field") ?? "";
  const party = sp.get("party") ?? "";
  const district = sp.get("district") ?? "";
  // Exakter, von einem Kartenpunkt gesetzter Beschlussort. Anders als der
  // Katalogfilter `district` meint dies genau eine Straße/ein Gebäude.
  const location = sp.get("location") ?? "";
  const locationName = sp.get("location_name") ?? location;
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
  /* Ohne ?cat= gilt „nur Beschlüsse" — außer die Liste gehört zu einem eigenen
     Thema. Dessen Trefferliste enthält beides, und die Voreinstellung schnitt
     davon still die Berichte weg: Die Karte sagte „40+", die Liste zeigte 25
     (Tim, Build 12). Ein Thema bringt seine Menge selbst mit; sie zu filtern,
     ist eine Entscheidung des Nutzers, keine Voreinstellung. */
  const mode: "vote" | "report" | "all" =
    catParam === "report" || catParam === "all" ? catParam
      : catParam === "vote" ? "vote"
        : topicId ? "all" : "vote";
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
    api.get<{ districts: {
      place_id: string; name: string; kind: string; kind_label: string; parent_ids: string[];
      count: number; vote_count: number; report_count: number;
    }[] }>("/council/districts")
      .then((d) => setDistricts(d.districts)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ total: number; decisions: CouncilDecision[] }>(
        `/council/decisions${qs({
          q, committee, category: mode === "all" ? "" : mode, sort, field, party,
          district, location,
          outcome: mode === "vote" ? outcome : "",
          date_from: dateFrom, date_to: dateTo,
          include_subvotes: showSubvotes ? "1" : "",
          // Design 28a/S4: auf die Treffer eines eigenen Themas eingeschränkt.
          topic: topicId,
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
  }, [q, committee, mode, outcome, sort, field, party, district, location, dateFrom, dateTo, showSubvotes, page, topicId]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, mode, outcome, sort, field, party, district, location, dateFrom, dateTo, showSubvotes, page, topicId]);

  // RL-U02: Seitenwechsel führt zurück zum Listenanfang und setzt den Fokus
  // auf den Listen-Container (bleibt über den Ladewechsel gemountet), damit
  // Screenreader den Kontextwechsel mitbekommen.
  const listRef = useRef<HTMLDivElement>(null);
  // `springen` nur für die UNTERE Leiste: Von dort führt der Weg zurück an den
  // Listenanfang. Die obere Leiste steht schon dort — dieselbe Bewegung
  // verschob die Seite bei jedem Klick um ein paar Pixel (Tims Befund 12.08.:
  // „immer im Wechsel hoch und runter"), weil scrollIntoView den Listenkopf
  // unter den klebenden Seitenkopf zieht. Der Fokus wandert weiterhin auf die
  // Liste, damit Vorleseprogramme den Wechsel mitbekommen.
  const changePage = (p: number, springen = true) => {
    setPage(p);
    requestAnimationFrame(() => {
      if (springen) {
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        listRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      }
      listRef.current?.focus({ preventScroll: true });
    });
  };

  const query = q.trim();
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const isReport = mode === "report";
  const einer = total === 1 && !topicCapped;
  /* Unter einem eigenen Thema heißt dieselbe Menge auch hier „Beschlüsse" —
     so wie auf der Themen-Karte, in der Meldung und im Bearbeiten-Blatt. Das
     Sammelwort „Vorgänge" der freien Suche wäre zwar präziser (die Menge
     enthält auch Berichte), erzeugte aber genau das, was hier abgeschafft
     wird: dieselbe Zahl unter zwei Namen. Wer die Kategorie danach selbst
     umstellt, bekommt wieder die Wörter der Suche. */
  const noun = mode === "all"
    ? (topicId ? (einer ? "Beschluss" : "Beschlüsse") : einer ? "Vorgang" : "Vorgänge")
    : isReport ? (einer ? "Bericht" : "Berichte") : (einer ? "Beschluss" : "Beschlüsse");
  /* „40+" statt „40": s. topicCapped. Steht überall dort, wo die Zahl steht. */
  const totalLabel = `${total}${topicCapped ? "+" : ""}`;
  const districtCount = (item: typeof districts[number]) =>
    mode === "vote" ? item.vote_count : mode === "report" ? item.report_count : item.count;
  const primaryPlaces = districts.filter((item) => item.kind === "local_area");
  const secondaryPlaces = districts.filter((item) => item.kind !== "local_area");
  const districtValue = districts.find((item) => item.place_id === district || item.name === district)?.place_id ?? district;

  // Zeitraum zählt als EIN Filter; Sortierung ist eine Einstellung, kein Filter.
  const activeFilterCount = [outcome, field, committee, district, location, dateFrom || dateTo].filter(Boolean).length;

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
      <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
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
        <FilterField label="Ortsbezug">
          <Select value={districtValue} onChange={(e) => setUrlParam("district", e.target.value)}>
            <option value="">Alle Orte</option>
            <optgroup label="Ortsbereiche">
              {primaryPlaces.map((item) => (
                <option key={item.place_id} value={item.place_id}>{item.name} ({districtCount(item)})</option>
              ))}
            </optgroup>
            {secondaryPlaces.length > 0 && <optgroup label="Quartiere und besondere Gebiete">
              {secondaryPlaces.map((item) => (
                <option key={item.place_id} value={item.place_id}>{item.name} · {item.kind_label} ({districtCount(item)})</option>
              ))}
            </optgroup>}
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
          official_text; Rechercheure können sie hier als eigene Treffer einblenden. */}
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
          withHistory
          tour="beschluss-suche"
          placeholder={isReport ? "Berichte durchsuchen…" : "Suchen (z. B. Haushalt, Radwege)…"}
          value={q}
          onChange={(v) => { setQ(v); setPage(1); }}
        />
      </div>

      <div className="mt-3 hidden flex-wrap items-center gap-2 md:flex">
        {/* „Beschlüsse" räumt den cat-Parameter sonst weg, weil es die
            Voreinstellung ist — unter einem Thema ist die Voreinstellung aber
            „alle", und die Auswahl spränge sofort dorthin zurück. Dort wird
            „vote" deshalb ausgeschrieben; überall sonst bleibt die URL kurz. */}
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
          onChange={(m) => { setUrlParam("cat", m === "vote" && !topicId ? "" : m); setOutcome(""); }}
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
        {location && (
          <FilterChip label={`Beschlussort: ${locationName}`}
            onClear={() => setUrlParams({ location: "", location_name: "" })} />
        )}
        {districts.length > 0 && (
          <ChipPopover
            label="Ortsbezug"
            value={districtValue}
            options={districts.map((item) => ({
              value: item.place_id, label: `${item.name} (${districtCount(item)})`,
              sub: item.kind === "local_area" ? undefined : item.kind_label,
            }))}
            onChange={(value) => setUrlParam("district", value)}
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
              {loading ? "Ergebnisse anzeigen" : `${totalLabel} ${noun} anzeigen`}
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
            {district && <FilterChip label={`Ortsbezug: ${district}`} onClear={() => setUrlParam("district", "")} />}
            {location && <FilterChip label={`Beschlussort: ${locationName}`}
              onClear={() => setUrlParams({ location: "", location_name: "" })} />}
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

      {/* `aria-busy` statt eines Skeletts: Solange schon Treffer dastehen,
          bleiben sie stehen und werden nur leiser (s. `.liste-laedt` in
          globals.css) — sonst springt die Seitenhöhe beim Blättern zweimal.
          Das Skelett bleibt für den Fall, dass es nichts zu halten gibt. */}
      <div
        ref={listRef}
        tabIndex={-1}
        aria-busy={loading || undefined}
        className={cn("mt-6 outline-none", loading && decisions.length > 0 && "liste-laedt")}
      >
        {loading && decisions.length === 0 ? (
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
                onClick={() => router.push(fragenHref(query ? { q: query } : undefined))}
              >
                <Sparkles /> Frag den Rat
              </Button>
            }
          />
        ) : (
          <div className="space-y-2.5">
            {/* Design 29a (P7): Sehende sehen die Zahl — beim Filtern oder
                Blättern wechselte die Liste für Vorleseprogramme lautlos.
                Dieselbe Bauform wie die KI-Antwort (council-qa.tsx): eine
                unsichtbare Zeile, die die Änderung ansagt. */}
            <p className="sr-only" role="status" aria-live="polite">
              {loading
                ? "Beschlüsse werden geladen"
                : `${totalLabel} ${noun} gefunden${query ? ` zu ${query}` : ""}`
                  + (totalPages > 1 ? `, Seite ${page} von ${totalPages}` : "")}
            </p>
            {/* RL-F07: Trefferzeile gleitet bei Filterwechsel neu ein (key-Remount). */}
            <div className="flex flex-wrap items-center gap-2">
              <p key={`${total}|${query}|${outcome}|${field}|${committee}|${district}`} className="animate-fade-up text-sm font-medium text-muted-foreground">
                {totalLabel} {noun}
                {query && <> zu <strong className="font-semibold text-foreground">{query}</strong></>}
              </p>
              {/* Design 28a/S4: sichtbar und abwählbar — sonst wüsste niemand,
                  warum die Liste kürzer ist als sonst. */}
              {topicId && (
                <button
                  type="button"
                  onClick={() => setUrlParam("topic", "")}
                  className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
                >
                  Thema: {topicName || `#${topicId}`}
                  <X className="h-3 w-3" aria-hidden />
                  <span className="sr-only">Themenfilter entfernen</span>
                </button>
              )}
              {/* Blättern klein am rechten Rand der Zählerzeile (Tims Wunsch
                  12.08.) — die große, mittige Leiste oben wirkte wie ein
                  eigener Inhaltsblock. Unten bleibt sie in voller Größe. */}
              <Pagination compact page={page} totalPages={totalPages}
                onChange={(p) => changePage(p, false)} className="ml-auto" />
            </div>
            {decisions.map((d, i) => <DecisionCard key={d.id} d={d} query={query} rang={i} />)}
            <Pagination page={page} totalPages={totalPages} onChange={changePage} className="pt-2" />
          </div>
        )}
      </div>
    </div>
  );
}

/** Jahres-Trenner in der Sitzungsliste.
 *
 *  Die Liste reicht bis 2018 zurück, die Kachel zeigt aber nur „JUN 29". Wer
 *  weit scrollte, sah irgendwann wieder Juni und konnte nicht sagen, ob das
 *  dieses Jahr ist oder 2021. Der Trenner steht am Kopf jeder Gruppe — auch
 *  ganz oben, damit die Antwort nie erst nach dem ersten Wechsel kommt. */
/** Derselbe In-Seiten-Link wie auf der Wochenkarte: Die Liste klappt die
 *  Sitzung auf und hebt den Punkt hervor (`targetKsinr`/`flashTop`). */
function topHref(ksinr: number, itemNumber: string) {
  return `/council?tab=sessions&ksinr=${ksinr}` +
    (itemNumber ? `&top=${encodeURIComponent(itemNumber)}` : "");
}

/** Die wichtigsten Punkte einer Sitzung in der zugeklappten Karte — vom
 *  Server bewertet (`CouncilStore.sitzungs_highlights`, dieselbe Schwelle wie
 *  die Wochenkarte). Ein hervorgehobener Punkt (`top`) trägt seinen Grund;
 *  ein Treffer zum eigenen Thema den Themennamen in Signal-Orange. */
function SessionHighlights({ punkte, ksinr }: { punkte: NonNullable<CouncilSession["highlights"]>; ksinr: number }) {
  return (
    <ul className="space-y-1 border-t border-border px-3 pb-3 pt-2.5">
      {punkte.map((p) => (
        <li key={p.item_number}>
          <Link
            href={topHref(ksinr, p.item_number)}
            className={cn(
              "flex items-start gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent/60",
              p.top && "border border-primary/[0.12] bg-primary/[0.04] hover:bg-primary/[0.07]",
            )}
          >
            <span className={cn(
              "mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full",
              p.topic_name ? "bg-signal" : p.top ? "bg-primary" : "bg-muted-foreground/50",
            )} />
            <span className="min-w-0 flex-1">
              {(p.topic_name || p.top) && (
                <span className={cn(
                  "mb-0.5 block font-mono text-[9px] font-semibold uppercase tracking-[0.11em]",
                  p.topic_name ? "text-signal" : "text-primary/80",
                )}>
                  {p.topic_name ? `Dein Thema · ${p.topic_name}` : p.dringlich ? "Dringlichkeitsantrag" : "Wichtiger Punkt"}
                </span>
              )}
              <span className={cn("block text-[13px] leading-snug text-foreground", p.top && "font-semibold")}>
                {p.titel_kurz || p.title}
              </span>
              {p.top && p.wichtig_grund && (
                <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted-foreground">{p.wichtig_grund}</span>
              )}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Das Lucide-Zeichen des Gremiums als kleine getönte Kachel. */
function CommitteeGlyph({ name }: { name: string }) {
  const Icon = committeeIcon(name);
  return (
    <span aria-hidden className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/[0.09] text-primary">
      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
    </span>
  );
}

function YearDivider({ year }: { year: string }) {
  return (
    <div className="flex items-center gap-3 pt-2 first:pt-0">
      <span className="font-mono text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">{year}</span>
      <span className="h-px flex-1 bg-border" aria-hidden />
    </div>
  );
}


function SessionsTab({ committees }: { committees: string[] }) {
  const heute = useHeute();
  // Lokales Datum als ISO-Tag für String-Vergleiche mit session_date —
  // `heute` selbst ist ein Date, und "2026-08-19" >= Date wäre stets false.
  const heuteTag = heute
    ? `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`
    : null;
  // Filter überleben den Tab-Wechsel (Tims iOS-Befund 12.08.): Wer sucht und
  // kurz woanders nachsieht, will nicht neu tippen.
  const [q, setQ] = useMerker("sitzungen:q", "");
  const [committee, setCommittee] = useMerker("sitzungen:committee", "");
  // RL-F06: ?ksinr=… (Deep-Link von „Heute") — Sitzung aufklappen, sanft
  // hinscrollen und kurz aufblitzen lassen (wie der Fußnoten-Flash der KI).
  const deepSp = useSearchParams();
  const targetKsinr = Number(deepSp.get("ksinr") || 0);
  const deepLinkDone = useRef(false);
  const [flashKsinr, setFlashKsinr] = useState<number | null>(null);
  const [scope, setScope] = useMerker<Scope>("sitzungen:zeitraum", "upcoming");
  const listRef = useRef<HTMLDivElement>(null);
  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  // Aufgeklappte Sitzungen überleben den Tab-Wechsel (Tims Wunsch 12.08.):
  // Wer eine Tagesordnung offen hat und kurz woanders nachsieht, findet sie
  // beim Zurückkommen offen vor — die Details holt der Effekt unten nach.
  const [expanded, setExpanded] = useMerker<Record<number, boolean>>("sitzungen:offen", {});
  const [detail, setDetail] = useState<Record<number, SessionDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<number, boolean>>({});
  const debouncedQ = useDebounce(q, 350);
  // RL-U04: Leerzustand und Pause-Banner sollen miteinander reden — dieselbe
  // Query wie im Banner (React Query dedupliziert, staleTime 1 h).
  const { data: pause } = useQuery({
    queryKey: ["sitzungspause"],
    queryFn: () => api.get<{ active: boolean }>("/council/session-break"),
    staleTime: 60 * 60 * 1000,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setHasSearched(true);
    // Kein Zuklappen mehr beim bloßen Nachladen: Der Effekt läuft auch beim
    // Betreten der Seite, und damit war die gemerkte offene Tagesordnung
    // sofort wieder zu (Tims Wunsch 12.08.). Beim Ändern von Suche, Filter
    // oder Seite räumt der Effekt darunter auf — dort ist es richtig, weil
    // die Liste dann andere Sitzungen zeigt.
    try {
      const effectiveScope = q || committee ? "all" : scope;
      const data = await api.get<{ sessions: CouncilSession[]; total: number }>(
        `/council/sessions${qs({
          q, committee, scope: effectiveScope,
          limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE,
        })}`,
      );
      setSessions(data.sessions);
      setTotal(data.total);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Laden fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, committee, scope, page]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, scope, page]);

  // Jede Änderung an Suche, Ausschuss oder Zeitraum beginnt wieder auf Seite 1 —
  // sonst landet man im Nichts, wenn die neue Menge kürzer ist als die alte.
  // Dabei klappt auch alles zu: Die Liste zeigt danach andere Sitzungen.
  // Verglichen werden die WERTE, nicht „erster Lauf": React ruft Effekte im
  // Entwicklungsmodus doppelt auf, ein verbrauchtes Erstlauf-Flag ließ den
  // zweiten Durchgang alles zuklappen (gemessen).
  const letzteFilter = useRef(`${debouncedQ}|${committee}|${scope}`);
  useEffect(() => {
    const jetzt = `${debouncedQ}|${committee}|${scope}`;
    if (jetzt === letzteFilter.current) return;
    letzteFilter.current = jetzt;
    setPage(1);
    setExpanded({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, committee, scope]);

  useEffect(() => {
    if (!targetKsinr || deepLinkDone.current || loading) return;
    const s = sessions.find((x) => x.ksinr === targetKsinr);
    if (!s) return;
    deepLinkDone.current = true;
    // AUFKLAPPEN, nicht umschalten: Steht die Tagesordnung schon offen (etwa
    // weil sie den Tab-Wechsel überlebt hat, #447), machte `toggle` sie zu —
    // der Sprung landete dann auf einer geschlossenen Karte, und `?top=` fand
    // seine Zeile nie (im Browser reproduziert 12.08.).
    if (!expanded[targetKsinr]) void toggle(s);
    // Bewusst setTimeout und nicht requestAnimationFrame: Beim Antippen einer
    // Benachrichtigung wacht die App gerade erst auf. Ein Fenster, das noch
    // nicht zeichnet, ruft keine Animationsbilder ab — der Sprung wäre still
    // ausgefallen. Zeitgeber laufen auch dann.
    const sprung = setTimeout(() => {
      document.getElementById(`session-${targetKsinr}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
    setFlashKsinr(targetKsinr);
    const t = setTimeout(() => setFlashKsinr(null), 1600);
    return () => { clearTimeout(sprung); clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKsinr, loading, sessions, expanded]);

  /* ?top=… — der Tagesordnungspunkt aus einem geteilten Link oder einer
   *  Benachrichtigung. Der Sprung oben landet am Sitzungs*kopf*; die
   *  Tagesordnung steht weiter unten in der aufgeklappten Karte, und man
   *  musste sie selbst suchen. Sobald die Punkte geladen sind, geht es
   *  deshalb noch einen Schritt weiter zur gemeldeten Zeile — die Mechanik
   *  dafür teilt sich diese Ansicht mit der eigenständigen Sitzungs-Seite
   *  (components/tagesordnung.tsx). */
  const topsAusLink = useTopsAusLink(deepSp.get("top"));
  const flashTop = useTopSprung(targetKsinr, topsAusLink, Boolean(detail[targetKsinr]));

  const toggle = async (s: CouncilSession) => {
    const ksinr = s.ksinr;
    if (ksinr == null) return; // terminierte Sitzung ohne Tagesordnung
    const willExpand = !expanded[ksinr];
    setExpanded({ ...expanded, [ksinr]: willExpand });
    if (willExpand) reportBadgeEvent("sitzung"); // RL-U12: Sitzungsgast
    if (willExpand && !detail[ksinr]) {
      setDetailLoading((prev) => ({ ...prev, [ksinr]: true }));
      try {
        const d = await api.get<SessionDetail>(`/council/session/${ksinr}`);
        setDetail((prev) => ({ ...prev, [ksinr]: d }));
      } catch {
        toast.error("Sitzung konnte nicht geladen werden.");
        setExpanded({ ...expanded, [ksinr]: false });
      } finally {
        setDetailLoading((prev) => ({ ...prev, [ksinr]: false }));
      }
    }
  };

  // Wiederhergestellte offene Sitzungen brauchen ihre Tagesordnung nach —
  // gemerkt ist nur, WAS offen war, nicht der Inhalt.
  useEffect(() => {
    for (const [k, offen] of Object.entries(expanded)) {
      const ksinr = Number(k);
      if (!offen || detail[ksinr] || detailLoading[ksinr]) continue;
      setDetailLoading((prev) => ({ ...prev, [ksinr]: true }));
      api.get<SessionDetail>(`/council/session/${ksinr}`)
        .then((d) => setDetail((prev) => ({ ...prev, [ksinr]: d })))
        .catch(() => { /* stumm: die Karte zeigt dann nur den Kopf */ })
        .finally(() => setDetailLoading((prev) => ({ ...prev, [ksinr]: false })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);


  const query = q.trim();
  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Wie in der Beschluss-Suche (RL-U02): Seitenwechsel führt zurück an den
  // Listenanfang und setzt den Fokus dorthin — sonst steht man nach dem Klick
  // auf „2" mitten in der neuen Liste, weil der Knopf ganz unten liegt.
  // `springen` nur für die UNTERE Leiste: Von dort führt der Weg zurück an den
  // Listenanfang. Die obere Leiste steht schon dort — dieselbe Bewegung
  // verschob die Seite bei jedem Klick um ein paar Pixel (Tims Befund 12.08.:
  // „immer im Wechsel hoch und runter"), weil scrollIntoView den Listenkopf
  // unter den klebenden Seitenkopf zieht. Der Fokus wandert weiterhin auf die
  // Liste, damit Vorleseprogramme den Wechsel mitbekommen.
  const changePage = (p: number, springen = true) => {
    setPage(p);
    requestAnimationFrame(() => {
      if (springen) {
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        listRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      }
      listRef.current?.focus({ preventScroll: true });
    });
  };

  return (
    <div>
      {/* RL-801/402: kompakter Pause-Hinweis direkt über der Liste. */}
      <SitzungspauseBanner compact className="mt-4" />
      <Card className="mt-4 p-4">
        <div className="space-y-3">
          <SearchBox placeholder="In Tagesordnungen suchen …" value={q} onChange={setQ} />
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
                { value: "upcoming", label: "Anstehend" },
                { value: "recent", label: "Vergangen" },
                { value: "all", label: "Alle" },
              ]}
            />
          </div>
        </div>
      </Card>

      <div
        ref={listRef}
        tabIndex={-1}
        aria-busy={loading || undefined}
        className={cn("mt-6 outline-none", loading && sessions.length > 0 && "liste-laedt")}
      >
        {loading && sessions.length === 0 ? (
          <CardListSkeleton rows={5} />
        ) : sessions.length === 0 ? (
          // RL-U04: In der Sitzungspause ist „Anstehend" leer, das Banner darüber
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
            {/* Die Gesamtzahl, nicht die der Seite: Der Bestand reicht bis 2018
                zurück; „100 Sitzungen" las sich vorher wie das Ende der Welt. */}
            <p className="sr-only" role="status" aria-live="polite">
              {`${total} ${total === 1 ? "Sitzung" : "Sitzungen"} gefunden`
                + (totalPages > 1 ? `, Seite ${page} von ${totalPages}` : "")}
            </p>
            <div aria-hidden className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-muted-foreground">
                {total} {total === 1 ? "Sitzung" : "Sitzungen"}
              </p>
              {/* Blättern klein rechts in der Zählerzeile — siehe Beschluss-
                  Suche. Der „Seite X von Y"-Text wäre damit doppelt; für
                  Vorleseprogramme steht er weiter in der sr-only-Zeile. */}
              <Pagination compact page={page} totalPages={totalPages}
                onChange={(p) => changePage(p, false)} className="ml-auto" />
            </div>
            {sessions.map((s, i) => {
              // Jahres-Trenner, sobald sich das Jahr ändert — und immer über
              // dem ersten Eintrag, damit die Einordnung nicht erst nach dem
              // ersten Wechsel kommt (eine Seite kann komplett in einem Jahr
              // liegen).
              const year = s.session_date.slice(0, 4);
              const jahrWechsel = i === 0 || year !== sessions[i - 1].session_date.slice(0, 4);
              const trenner = jahrWechsel ? <YearDivider year={year} /> : null;

              // Terminierte Sitzung aus dem RIS-Kalender: noch keine
              // Tagesordnung veröffentlicht → nichts zum Aufklappen/Verlinken.
              if (s.ksinr == null) {
                return (
                  <Fragment key={`${s.committee}|${s.session_date}|${s.session_time}`}>
                  {trenner}
                  <Card className={cn("p-4", STAFFEL)} style={staffelStil(i)}>
                    {/* Mobil wandert die Badge unter den Text — sonst quetscht
                        sie den Gremiumsnamen auf „Ausschuss …" zusammen. */}
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <DateTile iso={s.session_date} />
                        <div className="min-w-0">
                          <CommitteeName name={s.committee} className="font-display text-base font-bold text-foreground" />
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {/* Auch bei Terminen ohne Tagesordnung: Der
                                Wochentag gehört vor die Uhrzeit. */}
                            {(() => {
                              const r = relativerTag(s.session_date, heute);
                              if (r) return `${r[0].toUpperCase()}${r.slice(1)} · `;
                              const w = wochentagKurz(s.session_date);
                              return w ? `${w} · ` : "";
                            })()}
                            {s.session_time ? `${s.session_time} Uhr` : "Uhrzeit folgt"}
                            {s.location && ` · ${s.location}`}
                          </p>
                        </div>
                      </div>
                      <div className="ml-[62px] flex shrink-0 items-center gap-2 self-start sm:ml-0 sm:self-auto">
                        {isLiveNow(s) && <LiveChip />}
                        <Badge>Tagesordnung folgt</Badge>
                        {/* In DERSELBEN Zeile wie die Badge (Tims Befund
                            12.08.): Als eigene Reihe darunter brach der Link
                            die Gleichmäßigkeit der Karten — rechts sitzt bei
                            den Schwester-Karten schließlich auch die Aktion.
                            Und gerade hier lohnt der Kalender am meisten: Der
                            Termin steht, die Tagesordnung kommt erst noch. */}
                        <CalendarButton session={s} />
                      </div>
                    </div>
                  </Card>
                  </Fragment>
                );
              }
              const isExpanded = !!expanded[s.ksinr];
              const matched = s.matched_items ?? [];
              const d = detail[s.ksinr];
              const { outcomeByItem, decisionByItem, videoByItem } = ergebnisseJeTop(d);
              const videoCount = Object.keys(videoByItem).length;
              // RL-902: TOPs, die zu eigenen Themen passen (TOP → Themenname).
              const myByItem: Record<string, string> = {};
              for (const m of s.my_topic_items ?? []) myByItem[m.item_number] ??= m.topic_name;
              const myCount = Object.keys(myByItem).length;
              // Der Live-Stand aus der Übertragung hängt an der Liste UND am
              // Detail — das Detail ist jünger, wenn es nachgeladen wurde.
              // Beendet oder 20 Minuten still: nichts mehr hervorheben.
              const liveState = d?.live_state ?? s.live_state;
              const liveKeys = liveState && liveStateFresh(liveState) && isLiveNow(s)
                ? liveItemKeys(liveState, (d?.agenda_items ?? []).map((it) => videoKey(it.item_number)))
                : new Set<string>();
              return (
                <Fragment key={s.ksinr}>
                {trenner}
                <Card
                  id={`session-${s.ksinr}`}
                  className={cn(
                    "overflow-hidden p-0 transition-shadow",
                    STAFFEL,
                    flashKsinr === s.ksinr && "ring-2 ring-primary",
                  )}
                  style={staffelStil(i)}
                >
                  <button type="button" onClick={() => toggle(s)} className="group flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-muted/40">
                    <div className="flex min-w-0 items-center gap-3">
                      <DateTile iso={s.session_date} />
                      <div className="min-w-0">
                        {/* Das Zeichen des Gremiums vor dem Namen — dieselbe
                            Tabelle wie im Onboarding und in der App, damit
                            man die Karte erkennt, bevor man sie liest. */}
                        <span className="flex min-w-0 items-center gap-2">
                          <CommitteeGlyph name={s.committee} />
                          <CommitteeName name={s.committee} className="font-display text-base font-bold text-foreground" />
                        </span>
                        {/* „Morgen · 17:00 Uhr" statt nur der Uhrzeit — die
                            Kachel links nennt den Tag, der Kopf benennt die
                            Nähe (Tims Wunsch 12.08.). */}
                        <p className="mt-0.5 truncate text-sm text-muted-foreground">
                          {/* „Heute/Morgen" schlägt den Wochentag — sonst steht
                              er vorn (Tims Wunsch 15.08.): Die Kachel nennt nur
                              Monat und Zahl, ob das ein Montag oder Samstag ist,
                              musste man selbst nachrechnen. */}
                          {(() => {
                            const r = relativerTag(s.session_date, heute);
                            if (r) return `${r[0].toUpperCase()}${r.slice(1)} · `;
                            const w = wochentagKurz(s.session_date);
                            return w ? `${w} · ` : "";
                          })()}
                          {s.session_time} Uhr{s.location && ` · ${s.location}`}
                        </p>
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
                      {/* Solange die Tagesordnung geholt wird, steht hier ein
                          Spinner statt des Pfeils — und der Bereich fährt erst
                          auf, wenn sie da ist (s. `offen` unten). Vorher klappte
                          er sofort auf Spinner-Höhe auf und sprang beim
                          Eintreffen der Punkte ein zweites Mal: gemessen von
                          118 auf 1.262 px in einem Bild. Ein Fortschritt an der
                          Stelle, die man gerade angetippt hat, ist die
                          ehrlichere Antwort (Designsprache § 6). */}
                      {detailLoading[s.ksinr] ? (
                        <span
                          aria-label="Tagesordnung wird geladen"
                          role="status"
                          className="h-5 w-5 animate-spin rounded-full border-2 border-muted border-t-primary [animation-duration:600ms]"
                        />
                      ) : (
                        <ChevronDown className={cn("h-5 w-5 text-muted-foreground/50 transition-transform duration-weg ease-out-strong", isExpanded && "rotate-180 text-primary")} />
                      )}
                    </div>
                  </button>

                  {/* Die wichtigsten Punkte schon in der zugeklappten Karte —
                      dieselbe Bewertung wie „Diese Woche im Rat", jetzt für
                      jede Sitzung (Tims Frage 04.09.2026). Aufgeklappt zeigt
                      die Liste ohnehin alles, bei einer Suche die Treffer. */}
                  {!isExpanded && !query && (s.highlights?.length ?? 0) > 0 && (
                    <SessionHighlights punkte={s.highlights!} ksinr={s.ksinr} />
                  )}
                  {/* Fährt auf und zu, statt zu erscheinen und zu verschwinden.
                      Der Rahmen oben gehört an den inneren Kasten: Am Wrapper
                      stünde er auch im zugefahrenen Zustand als Strich unter
                      der Karte. */}
                  <Aufklapp offen={!!(query || (isExpanded && !detailLoading[s.ksinr]))}>
                    <div className="border-t border-border px-4 pb-4 pt-3">
                      {isExpanded ? (
                        detailLoading[s.ksinr] ? (
                          <div className="py-2"><Spinner /></div>
                        ) : (
                          <>
                            {/* Nur bei anstehenden Sitzungen: Nach der Sitzung
                                ist die Änderungs-Historie Verwaltungsrauschen. */}
                            {heuteTag != null && s.session_date >= heuteTag
                              && (d?.agenda_changes?.length ?? 0) > 0 && (
                              <AenderungenSection aenderungen={d!.agenda_changes!} />
                            )}
                            {/* Vorbehalts-Hinweis EINMAL über der Liste — der
                                Disclaimer hat einen festen Ort, statt an jedem
                                Chip zu kleben (Ehrlichkeit als Designprinzip). */}
                            {videoCount > 0 && (
                              <VideoResultsNotice count={videoCount}
                                videoId={Object.values(videoByItem)[0].video_id} />
                            )}
                            {/* Der Dringlichkeitsantrag zuerst, und außerhalb
                                der Liste: Er hat keine Ö-Nummer und steht in
                                der amtlichen Tagesordnung nicht (s.
                                DringlichkeitsBlock). */}
                            <DringlichkeitsBlock
                              items={(d?.agenda_items ?? []).filter((it) => it.dringlich)}
                              ksinr={s.ksinr ?? undefined}
                              videoByItem={videoByItem} />
                            <ul className="space-y-0.5">
                              {(d?.agenda_items ?? []).filter((it) => !it.dringlich).map((it, i) => (
                                <AgendaRow key={i} it={it} query={query}
                                  ksinr={s.ksinr ?? undefined}
                                  bookmarkable={!hasAgendaChildren(it, d?.agenda_items ?? [])}
                                  outcome={it.is_public ? outcomeByItem[topKey(it.item_number)] : undefined}
                                  decisionId={it.is_public ? decisionByItem[topKey(it.item_number)] : undefined}
                                  videoResult={it.is_public ? videoByItem[videoKey(it.item_number)] : undefined}
                                  myTopic={myByItem[it.item_number]}
                                  live={liveKeys.has(videoKey(it.item_number))}
                                  domId={s.ksinr != null ? topDomId(s.ksinr, it.item_number) : undefined}
                                  flash={s.ksinr != null && flashTop === topDomId(s.ksinr, it.item_number)} />
                              ))}
                            </ul>
                            {d && <AttendanceSection detail={d} />}
                          </>
                        )
                      ) : query ? (
                        matched.length > 0 ? (
                          <>
                            <p className="mb-1 px-2 text-xs font-medium text-muted-foreground">{matched.length} Treffer in der Tagesordnung</p>
                            <ul className="space-y-0.5">{matched.map((it, i) => <AgendaRow key={i} it={it} query={query} ksinr={s.ksinr ?? undefined} bookmarkable={Boolean(d) && !hasAgendaChildren(it, d?.agenda_items ?? [])} myTopic={myByItem[it.item_number]} />)}</ul>
                          </>
                        ) : (
                          <p className="px-2 text-sm text-muted-foreground">Kein Tagesordnungspunkt enthält „{query}" — Treffer im Ausschussnamen.</p>
                        )
                      ) : null}

                      <div className="mt-3 flex items-center gap-4 px-2">
                        <button type="button" onClick={() => toggle(s)} className="text-sm font-medium text-primary hover:underline">
                          {isExpanded ? "Weniger anzeigen" : `Alle ${s.n_items} TOPs anzeigen`}
                        </button>
                        <CalendarButton session={s} agenda={(d?.agenda_items ?? []).map((it) => `${it.item_number} ${it.title}`)} />
                        <BookmarkButton target={{ kind: "session", ksinr: s.ksinr }} />
                        {/* Teilen führt auf die eigenständige Sitzungs-Seite,
                            nicht auf diese Liste: Der Link soll auch ohne Konto
                            aufgehen (s. lib/routes.ts sitzungHref). Je TOP gibt
                            es denselben Knopf an der Zeile. */}
                        <ShareButton still path={sitzungHref(s.ksinr)}
                          title={`${s.committee} am ${formatDate(s.session_date)}`} />
                        <a href={sessionUrl(s.ksinr)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
                          Ratsinfo <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </div>
                  </Aufklapp>
                </Card>
                </Fragment>
              );
            })}
            <Pagination page={page} totalPages={totalPages} onChange={changePage} />
          </div>
        )}
      </div>
    </div>
  );
}

/** Brücke in die Fragen-Seite (Split 12.08.): ersetzt den früheren
 *  Suchen/Fragen-Umschalter im Seitenkopf. QaTab, Gespräche-Knopf und der
 *  Modus-Scroll-Tausch sind mit auf die eigene Seite /fragen umgezogen —
 *  Fragen ist das Headliner-Feature und wohnt nicht mehr als Modus in der
 *  Suche. */
function FragenBruecke() {
  return (
    <Button asChild variant="signal" size="sm">
      <Link href={fragenHref()}>
        <Sparkles /> Fragen
      </Link>
    </Button>
  );
}

// Navigation between these views now lives in the left sidebar (Ratsinfo section),
// so the page only needs a per-view title/description instead of an in-page tab bar.
const TAB_META: Record<Tab, { title: string; description: string }> = {
  decisions: { title: "Suche", description: "Beschlüsse des Stadtrats durchsuchen — nach Stichwort, Ausschuss, Ergebnis und Zeitraum." },
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

  // Keep old links working by redirecting them to their new home. Seit dem
  // Split (12.08.) gilt das vor allem für den früheren Fragen-Modus: Links
  // aus Mails, Push, geteilten Snapshots und Lesezeichen tragen
  // ?mode=fragen (bzw. das ältere tab=ask) — sie landen auf /fragen, die
  // Fracht (q, share) reist mit.
  const umleitungZuFragen = searchParams.get("mode") === "fragen" || param === "ask";
  useEffect(() => {
    if (umleitungZuFragen) {
      const q = searchParams.get("q") ?? undefined;
      const share = searchParams.get("share") ?? undefined;
      router.replace(fragenHref({ q, share }), { scroll: false });
    }
    else if (param === "goals") router.replace("/council?tab=analysis&sub=ziele", { scroll: false });
    else if (param === "trends") router.replace("/council?tab=analysis&sub=trends", { scroll: false });
  }, [umleitungZuFragen, param, searchParams, router]);

  useEffect(() => {
    api.get<{ committees: string[] }>("/council/committees").then((d) => setCommittees(d.committees)).catch(() => {});
  }, []);

  const meta = TAB_META[tab];
  // Während der Umleitung nichts rendern: Die Suche synchronisiert ihre
  // Filter in die URL und überschrieb sonst den Alt-Link, BEVOR der
  // Redirect lief — q und share (Composer-Vorbefüllung, geteilte Antwort)
  // gingen dabei verloren (im Browser gemessen, nicht geraten).
  if (umleitungZuFragen) return null;
  return (
    <div>
      {/* Design 9a: Die mobile Ansichtsleiste (28a/S3) ist wieder weg — ihre
          Ziele stecken jetzt in der Tab-Bar (Sitzungen) bzw. im „Mehr"-Sheet
          (Stadtkarte, Analyse). Drei Nav-Ebenen übereinander (Burger → Pills →
          Suchen/Fragen) waren der Kern von Tims Mobil-Befund. */}
      <PageHeader
        title={meta.title}
        description={meta.description}
        action={tab === "decisions" ? <FragenBruecke /> : undefined}
      />
      {tab === "decisions" ? <DecisionsTab committees={committees} />
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
