"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AdminUserDetail, AdminGrowth, QuizFlagged, EntityAlias, AdminFeedback, PlaceCandidate } from "@/lib/types";
// Aus dem API-Vertrag statt von Hand: Diese drei Formen stehen im Backend
// vollständig, ein umbenanntes Feld bricht damit hier den Build.
import { vertrag, type ApiAntwort } from "@/lib/vertrag";

// `last` ist im Vertrag bewusst offen: Es ist eine `SELECT *`-Zeile aus
// `job_runs`, und eine Aufzählung im Backend würde beim nächsten `ALTER TABLE`
// still Felder abschneiden. Das Frontend darf sie enger sehen als der Vertrag —
// das ist das Muster für alle durchgereichten Nutzlasten.
type JobLauf = {
  started_at: string; finished_at: string | null; status: string;
  duration_s: number | null; stats: Record<string, number | string> | null;
  error: string | null;
};
type AdminJob = Omit<ApiAntwort<"/admin/jobs">[number], "last"> & { last: JobLauf | null };
type AdminUserRow = ApiAntwort<"/admin/users">[number];
type AdminQuizStats = ApiAntwort<"/admin/quiz/stats">;
import { Badge, Button, Card, ChartSkeleton, ConfirmDialog, ErrorState, Input, PageHeader, Select, Spinner, TableSkeleton, Textarea, formatDate, formatDateTime, toast } from "@/components/ui";
import { AreaSparkline, MiniBars, StatKicker } from "@/components/admin-charts";
import { cn } from "@/lib/utils";
import type { OrtsbereichCatalog } from "@/lib/districts";
import { clientFarbe, clientKurz, clientLabel, hauptClient } from "@/lib/clients";

type Tab = "stats" | "feedback" | "llm" | "users" | "quiz" | "orte" | "themen";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("stats");

  if (loading) return <Spinner />;
  if (!user || user.role !== "admin") {
    if (!loading) router.replace("/dashboard");
    return <Spinner />;
  }

  return (
    <div>
      <PageHeader title="Admin" description="Web-Nutzer*innen, Moderation und Kennzahlen verwalten." />
      {/* Mobil sind sieben Tabs breiter als der Schirm — die Leiste scrollt
          seitlich (ohne Scrollbalken), statt über den Rand zu laufen. */}
      <div className="scrollbar-none mt-4 flex gap-1 overflow-x-auto border-b border-border [-webkit-overflow-scrolling:touch]">
        {([
          ["stats", "Statistik"],
          ["feedback", "Feedback"],
          ["llm", "LLM-Kosten"],
          ["users", "Web-Nutzer*innen"],
          ["quiz", "Quiz"],
          ["orte", "Ortskandidaten"],
          ["themen", "Themen-Dubletten"],
        ] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`shrink-0 whitespace-nowrap px-4 py-2 text-sm font-medium ${
              tab === t ? "border-b-2 border-primary text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        {tab === "stats" && <StatsTab />}
        {tab === "feedback" && <FeedbackTab />}
        {tab === "llm" && <LlmUsageTab />}
        {tab === "users" && <UsersTab currentUserId={user.id} />}
        {tab === "quiz" && <QuizModerationTab />}
        {tab === "orte" && <PlaceCandidatesTab />}
        {tab === "themen" && <EntityAliasTab />}
      </div>
    </div>
  );
}

const GROWTH_RANGES: [string, string][] = [["30d", "30 T"], ["90d", "90 T"], ["12m", "12 M"], ["all", "Alles"]];

function TrendChip({ delta }: { delta: number }) {
  if (delta <= 0) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-500/[0.12] px-2 py-0.5 text-[11px] font-semibold text-green-700 dark:text-green-400">
      <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7" /><path d="M7 7h10v10" /></svg>
      +{delta}
    </span>
  );
}

/** „App oder Web?" — zwei Balken nebeneinander.
 *
 *  Links die NUTZUNG der letzten 30 Tage, rechts der ANMELDEWEG des gesamten
 *  Bestands. Die beiden zu trennen ist der Punkt: Wer sich im Browser
 *  registriert und danach nur noch die App öffnet, taucht links als App und
 *  rechts als Web auf — genau die Differenz, die man sehen will.
 *
 *  Bei der Nutzung zählen KONTEN, nicht Zugriffe: Ein einzelnes vielbenutztes
 *  Gerät soll nicht wie eine Plattform mit vielen Leuten aussehen.
 */
function ClientCard({ clients, both, signup }: {
  clients: AdminGrowth["clients"];
  both: number;
  signup: AdminGrowth["signup_clients"];
}) {
  // `unknown` fliegt raus: ungemessen ist keine Plattform. Es steht statt-
  // dessen als Fußnote unter dem Anmeldeweg, damit die Summe erklärbar bleibt.
  const nutzung = clients.filter((c) => c.users > 0);
  const wege = signup.filter((c) => c.client !== "unknown" && c.n > 0);
  const ungemessen = signup.find((c) => c.client === "unknown")?.n ?? 0;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <StatKicker>Womit genutzt</StatKicker>
          <span className="text-[11.5px] text-muted-foreground">30 Tage · Konten</span>
        </div>
        <ClientBalken werte={nutzung.map((c) => ({ client: c.client, n: c.users }))}
          leer="Noch nichts gemessen." />
        {/* Ohne diese Zeile liest sich der Balken so, als benutzte jede:r genau
            eins. Jedes Konto steht dort unter seinem meistgenutzten Client —
            wie viele überhaupt wechseln, sagt erst die Zahl hier. */}
        {both > 0 && (
          <p className="mt-2.5 text-[11.5px] text-muted-foreground">
            Jedes Konto zählt einmal, unter dem Weg, den es am häufigsten
            nimmt. {both === 1 ? "Ein Konto nutzt" : `${both} Konten nutzen`} beides.
          </p>
        )}
      </Card>
      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <StatKicker>Womit registriert</StatKicker>
          <span className="text-[11.5px] text-muted-foreground">gesamter Bestand</span>
        </div>
        <ClientBalken werte={wege} leer="Noch kein Konto seit Einführung der Messung." />
        {ungemessen > 0 && (
          <p className="mt-2.5 text-[11.5px] text-muted-foreground">
            Dazu {ungemessen.toLocaleString("de-DE")} {ungemessen === 1 ? "Konto" : "Konten"} von vor
            der Messung (09/2026) — deren Anmeldeweg wurde nie festgehalten.
          </p>
        )}
      </Card>
    </div>
  );
}

/** Ein waagerechter Anteilsbalken plus Legende. Web trägt das Primär-, alles
 *  Native das Signalblau — dieselbe Zuordnung wie im Nutzer-Detail. */
function ClientBalken({ werte, leer }: { werte: { client: string; n: number }[]; leer: string }) {
  const gesamt = werte.reduce((s, w) => s + w.n, 0);
  if (!gesamt) return <p className="mt-3 text-[13px] text-muted-foreground">{leer}</p>;
  const sortiert = werte.slice().sort((a, b) => b.n - a.n);
  return (
    <>
      <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-muted">
        {sortiert.map((w) => (
          <span key={w.client} title={`${clientLabel(w.client)}: ${w.n}`}
            className={cn("h-full", clientFarbe(w.client))}
            style={{ width: `${(w.n / gesamt) * 100}%` }} />
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        {sortiert.map((w) => (
          <div key={w.client} className="flex items-baseline justify-between gap-2">
            <span className="inline-flex items-center gap-2 text-[13px] text-foreground">
              <span className={cn("h-2 w-2 shrink-0 rounded-full", clientFarbe(w.client))} />
              {clientLabel(w.client)}
            </span>
            <span className="text-[13px] text-muted-foreground">
              <span className="font-display text-base font-bold tabular-nums text-foreground">
                {Math.round((w.n / gesamt) * 100)} %
              </span>{" "}
              <span className="tabular-nums">({w.n.toLocaleString("de-DE")})</span>
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

function GrowthCard({ kicker, total, delta, series, days, color }: { kicker: string; total: number; delta: number; series: number[]; days: string[]; color: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <StatKicker>{kicker}</StatKicker>
          <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{total.toLocaleString("de-DE")}</p>
        </div>
        <TrendChip delta={delta} />
      </div>
      <AreaSparkline values={series.length ? series : [0, 0]} days={days} color={color} height={64} className="mt-3" />
    </Card>
  );
}

/** Scraper-Ampel: Läufe um 8 und 14 Uhr, also sind bis zu ~18 h Abstand normal.
 *  Grün bis 26 h, danach ist mindestens ein Lauf ausgefallen. */
function fetchTone(hours: number | null): string {
  if (hours == null) return "bg-muted-foreground/40";
  if (hours < 26) return "bg-green-500";
  return hours < 72 ? "bg-amber-500" : "bg-red-500";
}

function fetchAge(hours: number): string {
  if (hours < 1) return "wenigen Minuten";
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} Tagen`;
}

function StatsTab() {
  const [range, setRange] = useState("90d");
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "growth", range],
    queryFn: () => api.get<AdminGrowth>(`/admin/stats/growth?range=${range}`),
  });

  if (isPending) return <Spinner />;
  if (isError || !data) return <ErrorState title="Die Statistiken kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />;

  const c = data.council;
  return (
    <div className="space-y-4">
      {/* Kopf: „Wachstum“ + Zeitraum-Umschalter (20a). */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-[15px] font-bold text-foreground">Wachstum</h3>
        <div role="group" className="inline-flex gap-0.5 rounded-[10px] bg-muted p-0.5">
          {GROWTH_RANGES.map(([v, label]) => (
            <button
              key={v}
              onClick={() => setRange(v)}
              className={cn(
                "rounded-lg px-3 py-1 text-[12.5px] transition-colors",
                range === v ? "bg-card font-semibold text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Zwei Verlaufs-Karten. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <GrowthCard kicker="Registrierte Nutzer*innen" total={data.users.total} delta={data.users.delta} series={data.users.series} days={data.users.days} color="hsl(var(--primary))" />
        <GrowthCard kicker="Angelegte Themen" total={data.topics.total} delta={data.topics.delta} series={data.topics.series} days={data.topics.days} color="hsl(var(--signal))" />
      </div>

      {/* App oder Web? Zwei getrennte Fragen nebeneinander: womit die Leute
          GERADE arbeiten (30 Tage) und womit sie überhaupt hergekommen sind. */}
      <ClientCard clients={data.clients} both={data.clients_both} signup={data.signup_clients} />

      {/* WAU + Ratsinfo-Import. */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr]">
        <Card className="p-4">
          <div className="flex items-baseline justify-between">
            <StatKicker>Aktive Nutzer*innen je Woche</StatKicker>
            <span className="text-[11.5px] text-muted-foreground">WAU · 8 Wochen</span>
          </div>
          <MiniBars values={data.wau.length ? data.wau : [0]} days={data.wau_days} height={70} className="mt-3.5" />
        </Card>
        <Card className="p-4">
          <StatKicker>Ratsinfo-Import</StatKicker>
          <div className="mt-3 flex flex-col gap-2.5">
            {[["Sitzungen", c.sessions], ["Tagesordnungspunkte", c.agenda_items], ["Beschlüsse mit KI-Feldern", c.decisions_with_ki]].map(([label, val]) => (
              <div key={label as string} className="flex items-baseline justify-between">
                <span className="text-[13px] text-foreground">{label}</span>
                <span className="font-display text-base font-bold tabular-nums text-foreground">{(val as number).toLocaleString("de-DE")}</span>
              </div>
            ))}
            <div className="mt-1 space-y-1.5 border-t border-border pt-2.5">
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 shrink-0 rounded-full", fetchTone(c.hours_since_fetch))} />
                <span className="text-xs text-muted-foreground">
                  {c.last_fetch ? `Letzter Scraper-Lauf: ${formatDate(c.last_fetch.slice(0, 10))}` : "Noch kein Lauf"}
                  {c.hours_since_fetch != null && ` · vor ${fetchAge(c.hours_since_fetch)}`}
                </span>
              </div>
              {/* Getrennt ausweisen: in der sitzungsfreien Zeit stockt die
                  Tagesordnung, während der Scraper weiterläuft. */}
              <p className="pl-4 text-xs text-muted-foreground">
                {c.last_session_import
                  ? `Neueste Tagesordnung: ${formatDate(c.last_session_import.slice(0, 10))}`
                  : "Noch keine Tagesordnung"}
                {c.next_session && ` · nächste Sitzung ${formatDate(c.next_session)}`}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <JobsSection />
    </div>
  );
}

const JOB_STATE: Record<AdminJob["state"], { dot: string; label: string }> = {
  ok: { dot: "bg-green-500", label: "läuft" },
  stale: { dot: "bg-amber-500", label: "überfällig" },
  error: { dot: "bg-red-500", label: "fehlgeschlagen" },
  unknown: { dot: "bg-muted-foreground/40", label: "noch kein Lauf erfasst" },
};

/** Cron-Übersicht: was läuft wann, wie lange, und was kam dabei heraus. */
function JobsSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: () => api.get<AdminJob[]>("/admin/jobs"),   // verfeinertes `last`, s. o.
  });

  // Vorher: `return null` — die Cron-Übersicht verschwand bei einem Ladefehler
  // spurlos, ausgerechnet die Ansicht, die stille Ausfälle sichtbar machen soll.
  if (isPending) return <div className="pt-2"><TableSkeleton rows={5} cols={4} /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Cron-Übersicht kam nicht durch"
          onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-[15px] font-bold text-foreground">Cron-Jobs</h3>
        <span className="text-[11.5px] text-muted-foreground">Erfassung ab dem jeweils nächsten Lauf</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {data.map((job) => {
          const tone = JOB_STATE[job.state];
          const stats = job.last?.stats ?? null;
          return (
            <Card key={job.key} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn("h-2 w-2 shrink-0 rounded-full", tone.dot)} />
                    <p className="truncate text-[13.5px] font-semibold text-foreground">{job.label}</p>
                  </div>
                  <p className="mt-1 pl-4 text-xs text-muted-foreground">{job.schedule}</p>
                </div>
                <span className="shrink-0 whitespace-nowrap text-[11.5px] text-muted-foreground">
                  {job.age_h != null ? `vor ${fetchAge(job.age_h)}` : tone.label}
                  {job.last?.duration_s != null && ` · ${formatDuration(job.last.duration_s)}`}
                </span>
              </div>

              {job.state === "error" && job.last?.error && (
                <p className="mt-2.5 rounded-lg bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
                  {job.last.error}
                </p>
              )}

              {stats && Object.keys(stats).length > 0 ? (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {Object.entries(stats).map(([label, value]) => (
                    <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11.5px] text-muted-foreground">
                      {label}
                      <strong className="font-semibold tabular-nums text-foreground">
                        {typeof value === "number" ? value.toLocaleString("de-DE") : value}
                      </strong>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2.5 text-xs text-muted-foreground">{job.description}</p>
              )}

              {job.history.length > 1 && (
                <div className="mt-3 flex items-end gap-1" aria-hidden>
                  {job.history.map((h, i) => (
                    <span
                      key={i}
                      title={`${formatDate(h.started_at.slice(0, 10))} · ${h.status}`}
                      className={cn("h-1.5 flex-1 rounded-full", h.status === "ok" ? "bg-primary/45" : "bg-destructive/60")}
                    />
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

type LlmFeature = {
  feature: string; calls: number; prompt_tokens: number; completion_tokens: number;
  cost: number; models: string[]; first: string; last: string;
};
type LlmUsage = {
  features: LlmFeature[]; total_cost: number; total_calls: number;
  // Design 21a: Verlauf, Monat + Hochrechnung, Budget-Ampel.
  series: { date: string; cost: number; calls: number }[];
  cost_month: number; projected_month: number;
  calls_30d: number; avg_cost_per_call: number;
  budget_monthly: number; budget_pct: number; budget_level: "ok" | "warn" | "over";
};

/** Die Namen der LLM-Aufrufe, wie `llm_usage.feature` sie zählt — hier auf
 *  Deutsch für die Kostentabelle. Der Schlüssel ist der gespeicherte Wert.
 *
 *  Die Liste war lange unvollständig, und ein fehlender Eintrag fiel nicht
 *  auf, solange der Rückfall den deutschen Schlüssel zeigte. Seit die Werte
 *  englisch sind, stünde dort `attachment_ocr` — deshalb jetzt vollständig.
 *  Wer ein neues `_feature=` einführt, trägt es hier ein. */
const FEATURE_LABELS: Record<string, string> = {
  attachment_ocr: "Anlagen-Texterkennung",
  committee_summary: "Ausschuss-Zusammenfassung",
  daily_find_story: "Fundstück des Tages",
  decision_places: "Orte eines Beschlusses",
  deep_decomposition: "Gründliche Recherche — Zerlegung",
  deep_report: "Gründliche Recherche — Bericht",
  entity_description: "Themen-Beschreibungen",
  entity_duplicates: "Entitäten-Dubletten",
  entity_ner: "Entitäten-Erkennung",
  exp_session_classification: "Experiment: Sitzungs-Klassifikation",
  field_recap: "Themenfeld-Rückblick",
  goal_rating: "Ziel-Bewertung",
  impact_rating: "Tragweite eines Beschlusses",
  impact_rating_agenda: "Tragweite eines Tagesordnungspunkts",
  interest_rating: "Gesprächswert",
  livestream_transcript: "Livestream-Transkript",
  minutes_extraction: "Protokoll-Extraktion",
  party_opinions: "Haltungen der Fraktionen",
  qa_analysis: "Frag den Rat — Analyse",
  qa_answer: "Frag den Rat — Antwort",
  qa_query_expansion: "Frag den Rat — Suchbegriffe",
  qa_simple: "Frag den Rat — einfach erklärt",
  quality_judge: "Eval: Qualitätsurteil",
  quiz_generation: "Quiz-Fragen erzeugen",
  quiz_verify: "Quiz-Fragen prüfen",
  simple_summary: "Lotti erklärt's einfach",
  social_card_text: "Social-Kartentext",
  social_critic: "Social-Kritiker",
  speeches: "Wortbeiträge",
  topic_auto_description: "Themen-Beschreibung (automatisch)",
  topic_classification: "Themenfeld-Klassifikation",
  vagueness_check: "Themen-Vagheitsprüfung",
  video_results: "Abstimmungsergebnisse aus dem Video",
};

const BUDGET_TONE: Record<LlmUsage["budget_level"], { dot: string; text: string; bar: string; ring: string }> = {
  ok:   { dot: "bg-green-500",  text: "text-green-700 dark:text-green-400",   bar: "bg-green-500",  ring: "border-green-500/30 bg-green-500/5" },
  warn: { dot: "bg-amber-500",  text: "text-amber-700 dark:text-amber-400",   bar: "bg-amber-500",  ring: "border-amber-500/35 bg-gradient-to-br from-amber-500/[0.08] to-transparent" },
  over: { dot: "bg-destructive", text: "text-destructive",                    bar: "bg-destructive", ring: "border-destructive/40 bg-destructive/5" },
};

/** Kennzahl-Karte im 20a/21a-Stil: Kicker + große Bricolage-Zahl + Unterzeile. */
const FEEDBACK_KIND: Record<string, { label: string; cls: string }> = {
  feature: { label: "Feature-Vorschlag", cls: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300" },
  bug: { label: "Fehler", cls: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
  other: { label: "Sonstiges", cls: "bg-muted text-muted-foreground" },
  // Kommt nur über das Kontaktformular auf /hilfe herein — und meist von
  // jemandem, der gerade nicht in sein Konto kommt. Deshalb Amber: dringlicher
  // als ein Vorschlag, aber kein Fehlerrot.
  konto: { label: "Konto & Anmeldung", cls: "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300" },
  qa_share: { label: "Geteilter Inhalt", cls: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
};

/** Eingegangenes Nutzer-Feedback. Offene Einträge stehen optisch vorn und
 *  treiben das Zeichen an der Admin-Navigation; „erledigt" ist umkehrbar,
 *  damit ein Fehlklick nichts kostet. */
function FeedbackTab() {
  const qc = useQueryClient();
  const [onlyUnread, setOnlyUnread] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-feedback", onlyUnread],
    queryFn: () => api.get<{ items: AdminFeedback[]; unread: number }>(
      `/admin/feedback?only_unread=${onlyUnread}`),
  });

  const mark = useMutation({
    mutationFn: ({ id, read }: { id: number; read: boolean }) =>
      api.post(`/admin/feedback/${id}/read?read=${read}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-feedback"] });
      // Das Zeichen in der Navigation hängt an einer eigenen Abfrage.
      qc.invalidateQueries({ queryKey: ["admin-feedback-unread"] });
    },
    onError: () => toast.error("Konnte nicht gespeichert werden."),
  });

  const removeShare = useMutation({
    mutationFn: (token: string) => api.del(`/admin/qa-shares/${encodeURIComponent(token)}`),
    onSuccess: () => {
      toast.success("Öffentlichen Link entfernt.");
      qc.invalidateQueries({ queryKey: ["admin-feedback"] });
    },
    onError: () => toast.error("Der geteilte Inhalt konnte nicht entfernt werden."),
  });

  if (isLoading) return <Spinner />;
  const items = data?.items ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {data?.unread ? `${data.unread} offen` : "Alles abgearbeitet"}
          {items.length > 0 && ` · ${items.length} angezeigt`}
        </p>
        <Button variant="secondary" onClick={() => setOnlyUnread((v) => !v)}>
          {onlyUnread ? "Alle anzeigen" : "Nur offene"}
        </Button>
      </div>

      {items.length === 0 ? (
        <Card className="mt-4 p-6 text-center text-sm text-muted-foreground">
          {onlyUnread ? "Kein offenes Feedback." : "Noch kein Feedback eingegangen."}
        </Card>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((f) => {
            const kind = FEEDBACK_KIND[f.kind] ?? { label: f.kind, cls: "bg-muted text-muted-foreground" };
            const open = !f.read_at;
            const shareToken = f.kind === "qa_share"
              ? f.message.match(/^Share-Token:\s*(\S+)$/m)?.[1]
              : undefined;
            return (
              <Card key={f.id} className={cn("p-4", open && "border-l-4 border-l-signal")}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("rounded-md px-1.5 py-0.5 text-xs font-semibold", kind.cls)}>
                    {kind.label}
                  </span>
                  {open && <Badge>offen</Badge>}
                  <span className="text-xs text-muted-foreground">{formatDateTime(f.created_at)}</span>
                  {f.email && (
                    <a href={`mailto:${f.email}`} className="text-xs text-primary hover:underline">
                      {f.email}
                    </a>
                  )}
                  <Button
                    variant="secondary"
                    className="ml-auto"
                    disabled={mark.isPending}
                    onClick={() => mark.mutate({ id: f.id, read: open })}
                  >
                    {open ? "Erledigt" : "Wieder öffnen"}
                  </Button>
                  {shareToken && (
                    <Button variant="danger" disabled={removeShare.isPending}
                      onClick={() => removeShare.mutate(shareToken)}>
                      Öffentlichen Link entfernen
                    </Button>
                  )}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {f.message}
                </p>
              </Card>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function KpiCard({ kicker, value, sub }: { kicker: string; value: string; sub?: React.ReactNode }) {
  return (
    <Card className="p-4">
      <StatKicker>{kicker}</StatKicker>
      <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Card>
  );
}

function LlmUsageTab() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "llm-usage"],
    queryFn: () => api.get<LlmUsage>("/admin/llm-usage"),
  });

  if (isPending) return <Spinner />;
  if (isError || !data) return <ErrorState title="Die LLM-Nutzung kam nicht durch" onRetry={() => void refetch()} busy={isFetching} />;
  if (data.features.length === 0) {
    return <p className="text-sm text-muted-foreground">Noch keine LLM-Nutzung erfasst — die Erfassung beginnt mit dem nächsten Lauf (Klassifikation, Entitäten, Frag den Rat …).</p>;
  }

  const tone = BUDGET_TONE[data.budget_level];
  const maxFeatureCost = Math.max(...data.features.map((f) => f.cost), 0.0001);

  return (
    <div className="space-y-5">
      {/* Drei KPI-Karten: Monat + Hochrechnung · Aufrufe · Budget-Ampel (21a). */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          kicker="Kosten diesen Monat"
          value={`$${data.cost_month.toFixed(2)}`}
          sub={<>Hochrechnung Monat: <strong className="font-semibold text-foreground">${data.projected_month.toFixed(2)}</strong></>}
        />
        <KpiCard
          kicker="Aufrufe (30 T)"
          value={data.calls_30d.toLocaleString("de-DE")}
          sub={`⌀ $${data.avg_cost_per_call.toFixed(3)} je Aufruf`}
        />
        <Card className={cn("border p-4", tone.ring)}>
          <div className="flex items-center justify-between gap-2">
            <StatKicker>Budget ${data.budget_monthly.toFixed(0)}/Mon</StatKicker>
            <span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold", tone.text)}>
              <span className={cn("h-2 w-2 rounded-full", tone.dot)} /> {data.budget_pct} %
            </span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
            <span className={cn("block h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, data.budget_pct)}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Warnung ab 80 %{data.budget_level === "over" && " · Budget überschritten"}</p>
        </Card>
      </div>

      {/* Verlauf + Kostentreiber (21a). */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.5fr_1fr]">
        <Card className="p-4">
          <StatKicker>Täglicher Kostenverlauf (30 T)</StatKicker>
          <AreaSparkline values={data.series.map((d) => d.cost)} days={data.series.map((d) => d.date)} axisTicks={6} color="hsl(var(--primary))" height={110} className="mt-3" />
          <p className="mt-1.5 text-[11px] text-muted-foreground/80">Spitzen = wöchentlicher Enrichment-Lauf (Klassifikation, Interest, Fundstück).</p>
        </Card>
        <Card className="p-4">
          <StatKicker>Kostentreiber — Feature</StatKicker>
          <div className="mt-3 flex flex-col gap-2.5">
            {data.features.slice(0, 5).map((f) => (
              <div key={f.feature}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="truncate text-foreground">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">${f.cost.toFixed(2)}</span>
                </div>
                <div className="mt-1 h-[7px] overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(3, (f.cost / maxFeatureCost) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Feature</th>
              <th className="px-4 py-2.5 text-right font-medium">Aufrufe</th>
              <th className="px-4 py-2.5 text-right font-medium">Input-Tokens</th>
              <th className="px-4 py-2.5 text-right font-medium">Output-Tokens</th>
              <th className="px-4 py-2.5 text-right font-medium">Kosten (gesch.)</th>
            </tr>
          </thead>
          <tbody>
            {data.features.map((f) => (
              <tr key={f.feature} className="border-b border-border last:border-0">
                <td className="px-4 py-2.5">
                  <span className="font-medium text-foreground">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
                  {f.models.length > 0 && <span className="ml-2 text-xs text-muted-foreground">{f.models.join(", ")}</span>}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.calls.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.prompt_tokens.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">{f.completion_tokens.toLocaleString("de-DE")}</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-foreground">${f.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs leading-relaxed text-muted-foreground/70">
        Kosten geschätzt aus den erfassten Token-Zahlen × hinterlegten Modellpreisen. Die Erfassung läuft ab
        Einführung dieser Seite (frühere Läufe sind nicht enthalten). Streaming-Antworten liefern je nach Anbieter
        nicht immer eine Token-Angabe.
      </p>
    </div>
  );
}

/** Aktivitäts-Ampel aus dem letzten Aktivitätstag (Design 20a). */
function activitySignal(lastSeen: string | null): { dot: string; label: string } {
  if (!lastSeen) return { dot: "bg-muted-foreground/40", label: "nie aktiv" };
  const days = Math.round((Date.now() - new Date(lastSeen + "T12:00:00").getTime()) / 86400000);
  if (days <= 0) return { dot: "bg-green-500", label: "heute aktiv" };
  if (days < 7) return { dot: "bg-amber-500", label: `vor ${days} ${days === 1 ? "Tag" : "Tagen"}` };
  const w = Math.round(days / 7);
  return { dot: "bg-muted-foreground/50", label: w <= 1 ? "vor 1 Woche" : `vor ${w} Wochen` };
}

const USER_FEATURE_LABEL: [keyof AdminUserDetail["features"], string][] = [
  ["ki_frage", "KI-Frage"], ["research", "Gründliche Recherche"], ["suche", "Beschluss-Suche"],
  ["quiz", "Quiz"], ["analyse", "Analyse"], ["karte", "Stadtkarte"],
];

function UsersTab({ currentUserId }: { currentUserId: number }) {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const { data: users = [], isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => vertrag.get("/admin/users"),
  });

  if (isPending) return <Spinner />;
  if (isError) return <ErrorState title="Die Nutzer*innen kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />;

  const needle = q.trim().toLowerCase();
  const filtered = needle ? users.filter((u) => u.email.toLowerCase().includes(needle)) : users;

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[1fr_minmax(0,420px)]">
      <Card className="overflow-hidden p-0">
        <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-4 py-3">
          <div className="relative flex-1">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="E-Mail suchen…"
              className="h-9 w-full rounded-[9px] border border-input bg-card pl-9 pr-3 text-base maus:text-[12.5px] text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">{users.length} Nutzer*innen</span>
        </div>
        <div className="divide-y divide-border">
          {filtered.map((u) => {
            const sig = activitySignal(u.last_seen);
            const chips = [
              u.n_topics > 0 && `${u.n_topics} ${u.n_topics === 1 ? "Thema" : "Themen"}`,
              u.n_ki > 0 && `${u.n_ki} KI-Fragen`,
              u.n_subscriptions > 0 && `${u.n_subscriptions} Abos`,
              u.n_quiz > 0 && "Quiz",
            ].filter(Boolean) as string[];
            // Womit gearbeitet wird — steht getrennt von den Inhalts-Chips, weil
            // es eine andere Art Auskunft ist (Kanal, nicht Menge).
            const womit = clientKurz(u.clients);
            return (
              <button key={u.id} onClick={() => setSelected(u.id)}
                className={cn("grid w-full grid-cols-[1fr_auto_auto] items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-accent",
                  selected === u.id && "bg-accent")}>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-[13.5px] font-semibold text-foreground">{u.email}</span>
                    {u.role === "admin" && <span className="shrink-0 rounded bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">admin</span>}
                    {u.status !== "active" && <span className="shrink-0 rounded bg-amber-500/15 px-1.5 text-[10px] font-semibold text-amber-700 dark:text-amber-500">wartet</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {womit && (
                      <span className="rounded bg-primary/10 px-1.5 py-px text-[10px] font-medium text-primary">{womit}</span>
                    )}
                    {chips.length ? chips.map((c) => (
                      <span key={c} className="rounded bg-muted px-1.5 py-px text-[10px] text-muted-foreground">{c}</span>
                    )) : <span className="rounded bg-muted px-1.5 py-px text-[10px] text-muted-foreground">noch nichts angelegt</span>}
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground"><span className={cn("h-[7px] w-[7px] rounded-full", sig.dot)} />{sig.label}</span>
                <svg className="h-4 w-4 text-muted-foreground/50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
              </button>
            );
          })}
          {!filtered.length && <p className="px-4 py-6 text-center text-sm text-muted-foreground">Keine Nutzer*in passt zu „{q}".</p>}
        </div>
      </Card>

      {selected != null
        ? <UserDetailPanel userId={selected} isSelf={selected === currentUserId} onClose={() => setSelected(null)} />
        : <Card className="hidden p-8 text-center text-sm text-muted-foreground lg:block">Nutzer*in wählen, um Details zu sehen.</Card>}
    </div>
  );
}

function UserDetailPanel({ userId, isSelf, onClose }: { userId: number; isSelf: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  };
  const roleMutation = useMutation({
    mutationFn: (role: "user" | "admin") => api.put(`/admin/users/${userId}/role`, { role }),
    onSuccess: () => { toast.success("Rolle aktualisiert."); invalidate(); },
    onError: () => toast.error("Rolle konnte nicht geändert werden."),
  });
  const statusMutation = useMutation({
    mutationFn: (status: "active" | "pending") => api.put(`/admin/users/${userId}/status`, { status }),
    onSuccess: (_, status) => { toast.success(status === "active" ? "Freigeschaltet." : "Gesperrt."); invalidate(); },
    onError: () => toast.error("Status konnte nicht geändert werden."),
  });
  const limitsMutation = useMutation({
    mutationFn: (limits: { deep_limit: number | null; limits_unlocked: boolean }) =>
      api.put(`/admin/users/${userId}/limits`, limits),
    onSuccess: () => { toast.success("Limits aktualisiert."); invalidate(); },
    onError: () => toast.error("Limits konnten nicht gespeichert werden."),
  });

  if (isPending || !data) return <Card className="p-6"><Spinner /></Card>;

  const sig = activitySignal(data.last_seen);
  const login = data.apple_linked ? "Apple-Login" : data.has_password ? "Passwort" : "Apple-Login";
  // „Wie angemeldet" heißt hier zweierlei: mit welchem Verfahren (Apple oder
  // Passwort) und von welchem Client aus. Beides gehört in die Kopfzeile.
  const woher = data.signup_client ? clientLabel(data.signup_client) : null;
  // Nur Gemessenes zeigen. `unknown` sind Zeilen von vor der Messung — sie als
  // eigenen Balken zu führen behauptete eine Plattform, die niemand kennt.
  const nutzung = Object.entries((data.clients ?? {}) as Record<string, number>)
    .filter(([id, n]) => id !== "unknown" && n > 0)
    .sort((a, b) => b[1] - a[1]);
  const nutzungGesamt = nutzung.reduce((s, [, n]) => s + n, 0);
  const fuehrend = hauptClient((data.clients ?? {}) as Record<string, number>);
  return (
    <Card className="bg-muted/20 p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 font-display text-base font-bold text-primary">{data.email[0].toUpperCase()}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-bold text-foreground">{data.email}</p>
          <p className="text-xs text-muted-foreground">
            seit {formatDate(data.created_at.slice(0, 10))} · {sig.label} · {login}
            {woher && <> · über {woher} registriert</>}
          </p>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground lg:hidden" aria-label="Schließen">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      </div>

      {/* Womit gearbeitet wird (Zugriffe je Client). Anteile statt roher
          Zahlen: Die Frage ist „App oder Web?", nicht „wie viele Requests". */}
      <StatKickerSpaced>Womit genutzt</StatKickerSpaced>
      {nutzung.length ? (
        <div className="mt-2 flex flex-col gap-1.5">
          <div className="flex h-2 overflow-hidden rounded-full bg-muted">
            {nutzung.map(([id, n]) => (
              <span key={id} title={`${clientLabel(id)}: ${n}`}
                className={cn("h-full", clientFarbe(id))}
                style={{ width: `${(n / nutzungGesamt) * 100}%` }} />
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {nutzung.map(([id, n]) => (
              <span key={id} className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                <span className={cn("h-2 w-2 rounded-full", clientFarbe(id))} />
                {clientLabel(id)}
                <span className="font-semibold tabular-nums text-foreground">
                  {Math.round((n / nutzungGesamt) * 100)} %
                </span>
              </span>
            ))}
            {nutzung.length > 1 && fuehrend && (
              <span className="inline-flex items-center rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground">
                überwiegend {clientLabel(fuehrend)}
              </span>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          Noch nichts gemessen — die Zuordnung läuft erst seit 09/2026 mit.
        </p>
      )}

      <StatKickerSpaced>Genutzte Features</StatKickerSpaced>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {USER_FEATURE_LABEL.map(([key, label]) => {
          const n = data.features[key];
          const suffix = key === "quiz" ? (n === 1 ? "1 Runde" : `${n} Runden`) : `${n}×`;
          return n > 0
            ? <span key={key} className="rounded-full bg-primary/[0.08] px-2.5 py-1 text-xs font-medium text-primary">{label} · {suffix}</span>
            : <span key={key} className="rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground">{label} · nie</span>;
        })}
      </div>

      <StatKickerSpaced>Angelegt</StatKickerSpaced>
      <div className="mt-2 flex flex-col gap-1.5">
        <DetailRow label={`${data.topics.length} ${data.topics.length === 1 ? "Thema" : "Themen"}`} value={data.topics.slice(0, 4).join(", ") || "—"} />
        <DetailRow label={`${data.subscriptions.length} Ausschuss-${data.subscriptions.length === 1 ? "Abo" : "Abos"}`} value={data.subscriptions.slice(0, 4).join(", ") || "—"} />
        <DetailRow label="Zustellung" value={data.delivery_channel === "both" ? "Push + E-Mail" : data.delivery_channel === "push" ? "Push" : data.delivery_channel === "off" ? "Aus" : "E-Mail"} />
        <DetailRow label="Gespräche speichern" value={data.saves_conversations === 1 ? "An" : data.saves_conversations === 0 ? "Bewusst aus" : "Nie gefragt"} />
      </div>

      <StatKickerSpaced>Aktivität (30 Tage)</StatKickerSpaced>
      <MiniBars values={data.history} days={data.history_days} height={38} highlightLast={false} className="mt-2" />

      {!isSelf && (
        <div className="mt-4 flex gap-2 border-t border-border pt-4">
          <Button variant="secondary" size="sm"
            onClick={() => statusMutation.mutate(data.status === "active" ? "pending" : "active")}>
            {data.status === "active" ? "Sperren" : "Freischalten"}
          </Button>
          <Button variant="secondary" size="sm"
            onClick={() => roleMutation.mutate(data.role === "admin" ? "user" : "admin")}>
            {data.role === "admin" ? "Zu Nutzer*in" : "Zu Admin"}
          </Button>
        </div>
      )}

      {/* Frage-Limits je Konto: Recherche-Tageskontingent (leer = Standard 5,
          0 = unbegrenzt) + Befreiung von den Rate-Limitern der Frage-Endpoints. */}
      <StatKickerSpaced>Frage-Limits</StatKickerSpaced>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-[12.5px]">
          Recherchen/Tag
          <input
            type="number" min={0} max={999}
            defaultValue={data.deep_limit ?? ""}
            placeholder="Standard (5)"
            key={`dl-${data.id}-${data.deep_limit ?? "std"}`}
            id={`deep-limit-${data.id}`}
            className="w-24 rounded-md border border-border bg-background px-2 py-1 text-[12.5px]"
          />
        </label>
        <Button variant="secondary" size="sm"
          onClick={() => {
            const el = document.getElementById(`deep-limit-${data.id}`) as HTMLInputElement | null;
            const roh = (el?.value ?? "").trim();
            const value = roh === "" ? null : Math.max(0, Math.min(999, Number(roh)));
            if (value !== null && Number.isNaN(value)) return;
            limitsMutation.mutate({ deep_limit: value, limits_unlocked: data.limits_unlocked });
          }}>
          Speichern
        </Button>
        <Button variant="secondary" size="sm"
          onClick={() => limitsMutation.mutate({ deep_limit: data.deep_limit, limits_unlocked: !data.limits_unlocked })}>
          {data.limits_unlocked ? "Rate-Limits wieder an" : "Rate-Limits aus"}
        </Button>
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground/70">
        {data.deep_limit === 0 ? "Recherche: unbegrenzt." : data.deep_limit != null
          ? `Recherche: ${data.deep_limit}/Tag.` : "Recherche: Standard (5/Tag)."}
        {" "}0 = unbegrenzt, leer = Standard.
        {data.limits_unlocked && " · Rate-Limits (schnelle Frage, Parteien, Teilen) sind für dieses Konto AUS."}
      </p>
      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground/70">
        Alles server-aggregiert & nur für Admins; nur eigene App-Aktivität, keine Dritt-Analytics.
      </p>
    </Card>
  );
}

function StatKickerSpaced({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground">{children}</p>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2">
      <span className="shrink-0 text-[12.5px] text-foreground">{label}</span>
      <span className="truncate text-[11.5px] text-muted-foreground">{value}</span>
    </div>
  );
}

/** Schlecht bewertete Quizfragen (👎) sichten und ausmustern. Ausgemusterte
 *  Fragen fliegen aus künftigen Runden; der nächste Generierungslauf füllt das
 *  Gebiet wieder auf. Datenquelle: GET /admin/quiz/flagged. */
const AREA_TYPE_LABEL: Record<string, string> = { district: "", electoral_district: "Wahlbereich ", topic: "" };

function QuizModerationTab() {
  const qc = useQueryClient();
  const statsQuery = useQuery({
    queryKey: ["admin", "quiz", "stats"],
    queryFn: () => vertrag.get("/admin/quiz/stats"),
  });
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "quiz", "flagged"],
    queryFn: () => vertrag.get("/admin/quiz/flagged"),
  });

  const retire = useMutation({
    mutationFn: (id: number) => api.post(`/admin/quiz/${id}/retire`),
    onSuccess: () => {
      toast.success("Frage ausgemustert. Der nächste Generierungslauf erzeugt Ersatz.");
      qc.invalidateQueries({ queryKey: ["admin", "quiz", "flagged"] });
      qc.invalidateQueries({ queryKey: ["admin", "quiz", "stats"] });
    },
    onError: () => toast.error("Frage konnte nicht ausgemustert werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <ErrorState title="Die Bewertungen kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />;
  const flagged = data?.flagged ?? [];
  const stats = statsQuery.data;
  const low = stats?.weak_categories ?? [];

  return (
    <div className="space-y-5">
      {/* Kennzahlen (21a). */}
      {stats && (
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.questions_active.toLocaleString("de-DE")}</p><p className="mt-1 text-[11px] text-muted-foreground">Fragen aktiv</p></Card>
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.avg_accuracy} %</p><p className="mt-1 text-[11px] text-muted-foreground">⌀ Trefferquote</p></Card>
          <Card className="p-3.5"><p className="font-display text-xl font-extrabold leading-none tabular-nums">{stats.reported}</p><p className="mt-1 text-[11px] text-muted-foreground">gemeldet 👎</p></Card>
        </div>
      )}

      {/* Gebiets-Warnung (21a). */}
      {low.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold text-amber-700 dark:text-amber-500">{low.length} {low.length === 1 ? "Gebiet" : "Gebiete"} bald leer</p>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {low.slice(0, 6).map((g) => `${AREA_TYPE_LABEL[g.area_type] ?? ""}${g.area_key} (${g.n})`).join(", ")}
              {low.length > 6 && ` … +${low.length - 6}`} offene Fragen. Der nächste Generierungslauf füllt sie auf.
            </p>
          </div>
        </div>
      )}

      {flagged.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">Keine schlecht bewerteten Fragen. 🎉</Card>
      ) : (<>
      <p className="text-sm text-muted-foreground">
        Von Nutzer*innen als „schlecht" markierte Fragen, meist-gemeldete zuerst.
        Ausmustern nimmt die Frage aus künftigen Runden.
      </p>
      <Card className="divide-y divide-border">
        {flagged.map((f) => (
          <div key={f.question_id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color="slate">{f.area_type}: {f.area_key}</Badge>
                <Badge color="red">👎 {f.bad}</Badge>
                {f.good > 0 && <Badge color="green">👍 {f.good}</Badge>}
              </div>
              <p className="mt-1.5 text-sm font-medium text-foreground">{f.question}</p>
              {f.options[f.correct_index] && (
                <p className="mt-0.5 text-xs text-muted-foreground">Richtige Antwort: {f.options[f.correct_index]}</p>
              )}
              {f.comments && (
                <p className="mt-1 text-xs italic text-muted-foreground">„{f.comments}"</p>
              )}
            </div>
            <Button variant="danger" size="sm" className="shrink-0"
                    disabled={retire.isPending}
                    onClick={() => retire.mutate(f.question_id)}>
              Ausmustern
            </Button>
          </div>
        ))}
      </Card>
      </>)}
    </div>
  );
}


type PlaceReviewStatus = "pending" | "concrete" | "approved" | "alias" | "rejected";

const concretePlaceKinds = [
  ["street", "Straße"], ["square", "Platz"],
  ["building", "Gebäude"], ["water", "Gewässer"],
  ["facility", "Anlage oder Gelände"], ["structure", "Bauwerk"],
  ["route", "Verkehrsweg"],
] as const;

function PlaceCandidateCard({ candidate, catalog, busy, onReview, onReopen }: {
  candidate: PlaceCandidate;
  catalog: OrtsbereichCatalog;
  busy: boolean;
  onReview: (slug: string, body: Record<string, unknown>) => void;
  onReopen: (slug: string) => void;
}) {
  const [name, setName] = useState(candidate.review_name ?? candidate.name);
  const [placeId, setPlaceId] = useState(candidate.review_place_id ?? candidate.slug);
  const [kind, setKind] = useState(
    candidate.status === "approved" ? candidate.review_kind ?? "neighborhood" : "neighborhood");
  const [parentId, setParentId] = useState(candidate.parent_id ?? candidate.local_area_id ?? "");
  const [aliases, setAliases] = useState((candidate.aliases ?? []).join(", "));
  const [description, setDescription] = useState(candidate.description ?? "");
  const [sourceUrl, setSourceUrl] = useState(candidate.source_url ?? "");
  const [canonical, setCanonical] = useState(candidate.canonical_place_id ?? "");
  const [quizEnabled, setQuizEnabled] = useState(!!candidate.quiz_enabled);
  const initialConcreteKind = concretePlaceKinds.some(([key]) => key === candidate.review_kind)
    ? candidate.review_kind as typeof concretePlaceKinds[number][0]
    : concretePlaceKinds.some(([key]) => key === candidate.kind)
      ? candidate.kind as typeof concretePlaceKinds[number][0]
      : "street";
  const [concreteKind, setConcreteKind] = useState(initialConcreteKind);
  const primaries = catalog.places.filter((p) => p.kind === "local_area");
  const targets = catalog.places.filter((p) => p.id !== placeId);
  const kinds = Object.entries(catalog.kinds).filter(([key]) => key !== "local_area");
  const payload = {
    place_id: placeId, name, kind, parent_id: parentId || null,
    aliases: aliases.split(",").map((value) => value.trim()).filter(Boolean),
    description: description || null, source_url: sourceUrl || null,
    quiz_enabled: quizEnabled,
  };

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{candidate.name}</p>
            <Badge color="slate">{candidate.kind}</Badge>
            <Badge color={candidate.lat != null ? "green" : "amber"}>
              {candidate.lat != null ? `verortet · ${candidate.district ?? "Oldenburg"}` : "ohne Koordinate"}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {candidate.decision_count} Beschlüsse · ⌀ {Math.round(candidate.avg_confidence * 100)} % Sicherheit
            {candidate.last_date ? ` · zuletzt ${formatDate(candidate.last_date)}` : ""}
          </p>
        </div>
        {candidate.status !== "pending" && (
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => onReopen(candidate.slug)}>
            Erneut prüfen
          </Button>
        )}
      </div>

      <div className="mt-3 rounded-lg bg-muted/55 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Stichproben</p>
        <ul className="mt-1.5 space-y-2">
          {candidate.evidence.map((sample) => (
            <li key={sample.id} className="text-xs leading-relaxed">
              <a className="font-medium text-primary hover:underline" href={`/council/decision?id=${sample.id}`}>
                {sample.title || `Beschluss ${sample.id}`}
              </a>
              <span className="text-muted-foreground"> · {formatDate(sample.session_date)} · „{sample.evidence}“</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-end">
        <label className="min-w-0 flex-1 text-xs text-muted-foreground">Konkreter Ortstyp
          <Select className="mt-1" value={concreteKind}
            onChange={(event) => setConcreteKind(event.target.value as typeof concreteKind)}>
            {concretePlaceKinds.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
        </label>
        <Button variant="secondary" size="sm" disabled={busy}
          onClick={() => onReview(candidate.slug, {
            status: "concrete", name: candidate.name, kind: concreteKind,
          })}>
          Als konkreten Ort bestätigen
        </Button>
      </div>

      <details className="mt-3" open={candidate.status === "pending"}>
        <summary className="cursor-pointer text-xs font-semibold text-primary">Katalog-Zuordnung bearbeiten</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground">Anzeigename
            <Input className="mt-1" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">Stabile ID
            <Input className="mt-1" value={placeId} onChange={(event) => setPlaceId(event.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">Ortstyp
            <Select className="mt-1" value={kind} onChange={(event) => setKind(event.target.value)}>
              {kinds.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </Select>
          </label>
          <label className="text-xs text-muted-foreground">Übergeordneter Ortsbereich
            <Select className="mt-1" value={parentId} onChange={(event) => setParentId(event.target.value)}>
              <option value="">Noch unklar</option>
              {primaries.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </label>
          <label className="text-xs text-muted-foreground sm:col-span-2">Weitere Namen, komma-getrennt
            <Input className="mt-1" value={aliases} onChange={(event) => setAliases(event.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground sm:col-span-2">Beschreibung
            <Textarea className="mt-1 min-h-20" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground sm:col-span-2">Beleg / Quellen-URL (Pflicht bei Freigabe)
            <Input className="mt-1" type="url" required value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={quizEnabled} onChange={(event) => setQuizEnabled(event.target.checked)} />
            Für neue Quizfragen zulassen
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" disabled={busy || !sourceUrl.trim()} onClick={() => onReview(candidate.slug, { status: "approved", ...payload })}>
            Als Katalogort freigeben
          </Button>
          <Button variant="danger" size="sm" disabled={busy}
            onClick={() => onReview(candidate.slug, { status: "rejected" })}>
            Verwerfen
          </Button>
        </div>
        <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1 text-xs text-muted-foreground">Oder als Alias zuordnen
            <Select className="mt-1" value={canonical} onChange={(event) => setCanonical(event.target.value)}>
              <option value="">Zielort wählen</option>
              {targets.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.kind_label}</option>)}
            </Select>
          </label>
          <Button variant="secondary" size="sm" disabled={busy || !canonical}
            onClick={() => onReview(candidate.slug, { status: "alias", canonical_place_id: canonical })}>
            Als Alias speichern
          </Button>
        </div>
      </details>
    </Card>
  );
}

/** Redaktionelle Brücke zwischen automatischer Extraktion und gemeinsamem
 * Ortskatalog. Die Beschluss-Belege stehen direkt am Kandidaten. */
function PlaceCandidatesTab() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<PlaceReviewStatus>("pending");
  const { data: catalog } = useQuery({
    queryKey: ["council", "places"],
    queryFn: () => api.get<OrtsbereichCatalog>("/council/places"),
  });
  const query = useQuery({
    queryKey: ["admin", "place-candidates", statusFilter],
    queryFn: () => api.get<{ candidates: PlaceCandidate[] }>(
      `/admin/place-candidates?status=${statusFilter}&limit=300`),
  });
  const review = useMutation({
    mutationFn: ({ slug, body }: { slug: string; body: Record<string, unknown> }) =>
      api.put(`/admin/place-candidates/${encodeURIComponent(slug)}`, body),
    onSuccess: () => {
      toast.success("Ortsprüfung gespeichert.");
      qc.invalidateQueries({ queryKey: ["admin", "place-candidates"] });
      qc.invalidateQueries({ queryKey: ["council", "places"] });
    },
    onError: () => toast.error("Ortsprüfung konnte nicht gespeichert werden."),
  });
  const reopen = useMutation({
    mutationFn: (slug: string) => api.del(`/admin/place-candidates/${encodeURIComponent(slug)}`),
    onSuccess: () => {
      toast.success("Kandidat ist wieder offen.");
      qc.invalidateQueries({ queryKey: ["admin", "place-candidates"] });
      qc.invalidateQueries({ queryKey: ["council", "places"] });
    },
    onError: () => toast.error("Prüfung konnte nicht geöffnet werden."),
  });

  if (query.isPending || !catalog) return <Spinner />;
  if (query.isError) return <ErrorState title="Die Ortskandidaten kamen nicht durch"
    onRetry={() => void query.refetch()} busy={query.isFetching} />;
  const candidates = query.data?.candidates ?? [];
  const tabs: [PlaceReviewStatus, string][] = [
    ["pending", "Offen"], ["concrete", "Konkrete Orte"], ["approved", "Freigegeben"],
    ["alias", "Aliase"], ["rejected", "Verworfen"],
  ];
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Ortsnamen aus mindestens drei Beschlüssen. Freigegebene Gebiete werden Teil des gemeinsamen
        Ortskatalogs; bestätigte konkrete Orte bleiben exakte Kartenpunkte.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {tabs.map(([value, label]) => (
          <button key={value} type="button" onClick={() => setStatusFilter(value)}
            className={cn("rounded-full border px-3 py-1.5 text-xs font-medium",
              statusFilter === value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}>{label}</button>
        ))}
      </div>
      {candidates.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">In dieser Gruppe gibt es keine Kandidaten.</Card>
      ) : candidates.map((candidate) => (
        <PlaceCandidateCard key={candidate.slug} candidate={candidate} catalog={catalog}
          busy={review.isPending || reopen.isPending}
          onReview={(slug, body) => review.mutate({ slug, body })}
          onReopen={(slug) => reopen.mutate(slug)} />
      ))}
    </div>
  );
}


/** Zusammengeführte Themen-Dubletten: durchsehen und bei Bedarf trennen.
 *  Die Zusammenführung ist umkehrbar — die Roh-Beobachtungen bleiben erhalten,
 *  die Themen werden daraus neu abgeleitet. */
function EntityAliasTab() {
  const qc = useQueryClient();
  const [undoing, setUndoing] = useState<EntityAlias | null>(null);
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "entity-aliases"],
    queryFn: () => api.get<{ aliases: EntityAlias[] }>("/admin/entity-aliases"),
  });

  const undo = useMutation({
    mutationFn: (slug: string) => api.del(`/admin/entity-aliases/${encodeURIComponent(slug)}`),
    onSuccess: () => {
      toast.success("Zusammenführung aufgehoben. Das Thema steht wieder für sich.");
      qc.invalidateQueries({ queryKey: ["admin", "entity-aliases"] });
    },
    onError: () => toast.error("Zusammenführung konnte nicht aufgehoben werden."),
  });

  if (isPending) return <Spinner />;
  if (isError) return <ErrorState title="Die Zusammenführungen kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />;

  const aliases = data?.aliases ?? [];
  const byLlm = aliases.filter((a) => a.source === "llm").length;
  const manual = aliases.filter((a) => a.source === "manuell").length;

  // Nach Ziel-Thema gruppieren: „vier Namen für den Bäderbetrieb“ gehört zusammen.
  const groups = new Map<string, EntityAlias[]>();
  for (const a of aliases) {
    const list = groups.get(a.canonical_slug) ?? [];
    list.push(a);
    groups.set(a.canonical_slug, list);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{groups.size}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">Themen zusammengeführt</p>
        </Card>
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{aliases.length}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">eingesparte Seiten</p>
        </Card>
        <Card className="p-3.5">
          <p className="font-display text-xl font-extrabold leading-none tabular-nums">{manual}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">von Hand · {byLlm} per KI</p>
        </Card>
      </div>

      {aliases.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          Noch keine Zusammenführungen. Der Lauf <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
          scripts/merge_entity_aliases.py</code> sucht Dubletten und legt sie hier ab.
        </Card>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Diese Namen zeigen auf dasselbe Thema, damit Beschlüsse und Beträge an einer Stelle stehen.
            Trennen macht das rückgängig — die Beschlüsse selbst gehen dabei nie verloren.
          </p>
          <div className="space-y-3">
            {sorted.map(([canonicalSlug, list]) => (
              <Card key={canonicalSlug} className="p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-semibold">
                    {list[0].canonical_name ?? canonicalSlug}
                    {list[0].canonical_n != null && (
                      <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">
                        {list[0].canonical_n} Beschlüsse
                      </span>
                    )}
                  </p>
                  <Badge color="slate">{list.length} zusammengeführt</Badge>
                </div>
                <ul className="mt-3 divide-y divide-border/60">
                  {list.map((a) => (
                    <li key={a.slug} className="flex flex-wrap items-start justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="text-sm">
                          <span className="text-muted-foreground line-through">{a.alias_name ?? a.slug}</span>
                          <span className="mx-2 text-muted-foreground">→</span>
                          <span>{a.canonical_name ?? a.canonical_slug}</span>
                        </p>
                        <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                          {a.source === "manuell" ? "von Hand" : "per KI"}
                          {a.reason ? ` · ${a.reason}` : ""}
                          {/* created_at ist ein voller Zeitstempel; formatDate erwartet YYYY-MM-DD. */}
                          {a.created_at ? ` · ${formatDate(a.created_at.slice(0, 10))}` : ""}
                        </p>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => setUndoing(a)}>
                        Trennen
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </>
      )}

      <ConfirmDialog
        open={undoing !== null}
        onOpenChange={(open) => !open && setUndoing(null)}
        title="Zusammenführung aufheben?"
        description={
          undoing
            ? `„${undoing.alias_name ?? undoing.slug}“ bekommt wieder eine eigene Themen-Seite, ` +
              `getrennt von „${undoing.canonical_name ?? undoing.canonical_slug}“. ` +
              `Die Beschlüsse bleiben erhalten und verteilen sich wieder auf beide Seiten.`
            : ""
        }
        confirmLabel="Trennen"
        onConfirm={() => {
          if (undoing) undo.mutate(undoing.slug);
          setUndoing(null);
        }}
      />
    </div>
  );
}
