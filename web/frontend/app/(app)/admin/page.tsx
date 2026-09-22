"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, apiUrl, authHeaders } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { darfAdmin } from "@/lib/rechte";
import { AdminRequestFehler, QuizFlagged, EntityAlias, AdminFeedback, PlaceCandidate } from "@/lib/types";
// Aus dem API-Vertrag statt von Hand: Diese drei Formen stehen im Backend
// vollständig, ein umbenanntes Feld bricht damit hier den Build.
import { vertrag, type ApiAntwort } from "@/lib/vertrag";

type AdminQuizStats = ApiAntwort<"/admin/quiz/stats">;
import { Badge, Button, Card, CardListSkeleton, ConfirmDialog, Dialog, DialogContent, DialogHeader, DialogTitle, EmptyState, ErrorState, Input, Label, PageHeader, Select, Spinner, TableSkeleton, Textarea, formatDate, formatDateTime, toast } from "@/components/ui";
import { AreaSparkline, StatKicker } from "@/components/admin-charts";
import { cn } from "@/lib/utils";
import type { OrtsbereichCatalog } from "@/lib/districts";

import { AdminNavigation, useAdminView } from "@/components/admin/navigation";
import { UsersTab } from "@/components/admin/users";
import { MailDashboard } from "@/components/admin/mail";
import { AdminOverview } from "@/components/admin/overview";
import { StatsTab, OperationsTab } from "@/components/admin/statistics";
import { LottiTab } from "@/components/admin/lotti";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, route] = useAdminView();

  if (loading) return <Spinner />;
  if (!user || !darfAdmin(user)) {
    if (!loading) router.replace("/dashboard");
    return <Spinner />;
  }

  return (
    <div>
      <PageHeader title="Admin" description="Verstehen, was genutzt wird. Sehen, wo es hakt." />
      <AdminNavigation view={tab} />
      <div className="mt-6 min-w-0">
        {tab === "stats" && <AdminOverview />}
        {(["aktivitaet", "konten", "reichweite", "antworten"] as string[]).includes(tab) && <StatsTab view={tab} />}
        {tab === "lotti" && <LottiTab />}
        {tab === "jobs" && <OperationsTab />}
        {tab === "fehler" && <FehlerTab />}
        {tab === "feedback" && <FeedbackTab />}
        {tab === "llm" && <LlmUsageTab />}
        {tab === "emails" && <MailDashboard />}
        {tab === "users" && <UsersTab currentUserId={user.id} route={route} />}
        {tab === "quiz" && <QuizModerationTab />}
        {tab === "orte" && <PlaceCandidatesTab />}
        {tab === "themen" && <EntityAliasTab />}
        {tab === "live" && <LiveProbeTab />}
        {tab === "news" && <NewsTab />}
      </div>
    </div>
  );
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
  assistant_explain: "Lotti erklärt (Assistentin)",
  cities_classify: "Fremde Ratsvorlage einordnen",
  cities_fit: "Hat Oldenburg das schon?",
  cities_evidence_terms: "Städtevergleich: Oldenburger Suchwörter",
  cities_effort: "Städtevergleich: Was kostet die Idee?",
  cities_stance: "Städtevergleich: Wollte der Rat die Idee?",
  cities_idea_fit: "Städtevergleich: Hat Oldenburg die Idee schon?",
  cities_reason: "Städtevergleich: Warum ging es so aus?",
  cities_cluster_check: "Städtevergleich: Gehört das zusammen?",
  eval_cities_effort: "Prüfstand: Was kostet die Idee?",
  eval_cities_transfer: "Prüfstand: Einordnung fremder Vorlagen",
  eval_cities_fit: "Prüfstand: Hat Oldenburg das schon?",
  attachment_ocr: "Anlagen-Texterkennung",
  committee_summary: "Ausschuss-Zusammenfassung",
  daily_find_story: "Fundstück des Tages",
  decision_places: "Orte eines Beschlusses",
  district_projects: "Mein Viertel — Vorhaben",
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
  live_top_tracker: "Live-Verfolgung (welcher TOP läuft)",
  minutes_extraction: "Protokoll-Extraktion",
  party_opinions: "Haltungen der Fraktionen",
  qa_analysis: "Frag den Rat — Analyse",
  qa_answer: "Frag den Rat — Antwort",
  qa_query_expansion: "Frag den Rat — Suchbegriffe",
  qa_simple: "Frag den Rat — verständlicher erklärt",
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
/** Ein Balkenverlauf der letzten Tage — reines SVG, keine Bibliothek.
 *
 *  Die eine Frage, die man an den Verlauf stellt: seit wann, und wird es mehr
 *  oder weniger? Dafür braucht es keine Achsen und keine Beschriftung, nur
 *  Höhen im Verhältnis zum größten Tag.
 */
function Verlauf({ tage }: { tage: { tag: string; n: number }[] }) {
  if (!tage.length) return null;
  const max = Math.max(...tage.map((t) => t.n), 1);
  const breite = 4;
  const luecke = 2;
  return (
    <svg
      role="img"
      aria-label={`Verlauf über ${tage.length} Tage, am stärksten ${max} an einem Tag`}
      width={tage.length * (breite + luecke)}
      height={28}
      className="shrink-0 overflow-visible"
    >
      {tage.map((t, i) => {
        const h = Math.max(2, Math.round((t.n / max) * 26));
        return (
          <rect
            key={t.tag}
            x={i * (breite + luecke)}
            y={28 - h}
            width={breite}
            height={h}
            rx={1}
            className="fill-primary/60"
          >
            <title>{`${t.tag}: ${t.n}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

/** Die Fehlerarten des Web-Backends und des Browsers — das Gegenstück zu den
 *  Cron-Jobs.
 *
 *  Eine Zeile je FEHLERART, nicht je Vorkommen: Gleiche Fehler fallen über
 *  ihren Fingerabdruck zusammen (`kern/fehler.py`), `count` sagt wie oft. Ein
 *  Ausfall füllt die Liste damit nicht zu.
 *
 *  Abhaken heißt „angesehen und behandelt". Taucht der Fehler danach wieder
 *  auf, setzt der Sammler den Haken selbst zurück und meldet erneut.
 */
function FehlerTab() {
  const qc = useQueryClient();
  const [nurOffen, setNurOffen] = useState(true);
  const [offen, setOffen] = useState<number | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin-fehler", nurOffen],
    queryFn: () => api.get<AdminRequestFehler[]>(`/admin/errors?nur_offen=${nurOffen}`),
  });

  const haken = useMutation({
    mutationFn: ({ id, ab }: { id: number; ab: boolean }) =>
      api.post(`/admin/errors/${id}/resolve?abgehakt=${ab}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-fehler"] });
      qc.invalidateQueries({ queryKey: ["admin-fehler-offen"] });
    },
    onError: () => toast.error("Konnte nicht gespeichert werden."),
  });

  if (isLoading) return <CardListSkeleton rows={3} />;
  if (isError || !data) {
    return <ErrorState title="Die Fehlerliste konnte nicht geladen werden"
      onRetry={() => void refetch()} busy={isFetching} />;
  }

  // Die Kennzahlen werden GERECHNET, nicht vom Server geliefert: Sie sind
  // Aussagen über genau die Liste, die gerade dasteht (offen oder alle).
  const heute = new Date().toISOString().slice(0, 10);
  const vorkommen = data.reduce((n, f) => n + f.count, 0);
  const heuteN = data.reduce(
    (n, f) => n + (f.daily.find((t) => t.tag === heute)?.n ?? 0), 0);
  const ausDemBrowser = data.filter((f) => f.quelle === "browser").length;
  const haeufigste = [...data].sort((a, b) => b.count - a.count)[0];

  return (
    // `@container`: Die Kennzahlen richten sich nach der Breite des
    // INHALTSBEREICHS, nicht des Fensters — mit offener Seitenleiste bleibt
    // sonst Platz übrig, den die Karten nicht nutzen.
    <div className="@container">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          Fehler aus dem Backend und aus dem Browser, nach Art zusammengefasst.
          Die erste Begegnung meldet sich per Mail; weitere werden nur gezählt.
        </p>
        <label className="flex shrink-0 items-center gap-2 text-sm">
          <input type="checkbox" checked={nurOffen}
            onChange={(e) => setNurOffen(e.target.checked)} />
          nur offene
        </label>
      </div>

      {data.length > 0 && (
        <div className="mb-5 grid grid-cols-2 gap-3 @2xl:grid-cols-4">
          {([
            ["Fehlerarten", String(data.length), null],
            ["Vorkommen", vorkommen.toLocaleString("de-DE"), null],
            ["heute", String(heuteN), heuteN > 0 ? "warn" : null],
            ["aus dem Browser", String(ausDemBrowser), null],
          ] as [string, string, string | null][]).map(([label, wert, ton]) => (
            <Card key={label} className="p-4">
              <p className={`font-display text-2xl font-bold tabular-nums ${
                ton === "warn" ? "text-signal" : "text-foreground"}`}>{wert}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
            </Card>
          ))}
        </div>
      )}

      {haeufigste && haeufigste.count > 1 && (
        <p className="mb-4 text-sm text-muted-foreground">
          Am häufigsten: <span className="font-medium text-foreground">
            {haeufigste.exc_type}</span> auf <code className="text-xs">
            {haeufigste.route}</code> ({haeufigste.count}&times;).
        </p>
      )}

      {data.length === 0 ? (
        <EmptyState mascot="celebrate" title="Keine offenen Fehler"
          hint="Seit dem letzten Haken ist weder im Backend noch im Browser etwas abgestürzt." />
      ) : (
        <div className="space-y-3">
          {data.map((f) => {
            const auf = offen === f.id;
            return (
              <Card key={f.id} className="overflow-hidden">
                <button type="button" onClick={() => setOffen(auf ? null : f.id)}
                  aria-expanded={auf}
                  className="flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-muted/20">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                    f.resolved_at ? "bg-muted-foreground/40" : "bg-signal"}`} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block">
                      <span className="font-mono text-sm font-semibold text-foreground">
                        {f.exc_type}
                      </span>
                      <span className="ml-2 text-sm text-muted-foreground">
                        {f.method === "BROWSER" ? "Browser" : f.method} {f.route}
                      </span>
                    </span>
                    {f.message && (
                      <span className="mt-0.5 block truncate text-sm text-muted-foreground">
                        {f.message}
                      </span>
                    )}
                    <span className="mt-1 block text-xs text-muted-foreground">
                      zuerst {formatDateTime(f.first_seen)} &middot; zuletzt {formatDateTime(f.last_seen)}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <Verlauf tage={f.daily} />
                    <Badge>{f.count}&times;</Badge>
                  </span>
                </button>

                {auf && (
                  <div className="border-t border-border bg-muted/20 p-4">
                    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs @xl:grid-cols-4">
                      {([
                        ["Herkunft", f.quelle === "browser" ? "Browser" : "Backend"],
                        ["Vorkommen", `${f.count}\u00d7`],
                        ["Tage mit Fehlern", String(f.daily.length)],
                        ["Zustand", f.resolved_at ? "abgehakt" : "offen"],
                      ] as [string, string][]).map(([k, v]) => (
                        <div key={k}>
                          <dt className="text-muted-foreground">{k}</dt>
                          <dd className="font-medium text-foreground">{v}</dd>
                        </div>
                      ))}
                    </dl>

                    {f.trace && (
                      <>
                        <p className="mt-4 text-xs font-medium text-muted-foreground">Spur</p>
                        {/* Breite Spuren scrollen in ihrem eigenen Kasten — die
                            Seite selbst darf sich nicht seitwärts schieben. */}
                        <pre className="mt-1 overflow-x-auto rounded-lg bg-background p-3 text-xs leading-relaxed">
                          {f.trace}
                        </pre>
                      </>
                    )}

                    <div className="mt-4 flex justify-end">
                      <Button variant="secondary" size="sm" disabled={haken.isPending}
                        onClick={() => haken.mutate({ id: f.id, ab: !f.resolved_at })}>
                        {f.resolved_at ? "Wieder öffnen" : "Abhaken"}
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}


/** Arten, zu denen es eine Rückmeldung gibt — dieselbe Liste wie im Backend
 *  (`_RUECKMELDBAR` in routers/admin.py). Eine gemeldete Share-Verletzung ist
 *  eine Meldung ÜBER fremde Inhalte und bekommt nie Post; das Backend weist
 *  sie ohnehin ab, hier bleibt der Knopf gleich ganz weg. */
const RUECKMELDBAR = new Set(["feature", "bug", "other", "konto"]);

function FeedbackTab() {
  const qc = useQueryClient();
  const [onlyUnread, setOnlyUnread] = useState(false);
  // Die Rückmeldung, die gerade verfasst wird (null = kein Dialog offen).
  const [antwortZu, setAntwortZu] = useState<AdminFeedback | null>(null);
  const [antwortText, setAntwortText] = useState("");

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

  const benachrichtigen = useMutation({
    mutationFn: ({ id, message }: { id: number; message: string }) =>
      api.post<{ recipient: string }>(`/admin/feedback/${id}/notify`, { message }),
    onSuccess: (antwort) => {
      // Sagt WOHIN, nicht nur „gesendet": Bei einer Mail an eine fremde
      // Person ist das der Unterschied zwischen Bestätigung und Behauptung.
      toast.success(`Rückmeldung an ${antwort.recipient} verschickt.`);
      setAntwortZu(null);
      setAntwortText("");
      qc.invalidateQueries({ queryKey: ["admin-feedback"] });
      qc.invalidateQueries({ queryKey: ["admin-feedback-unread"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Die Rückmeldung ging nicht raus."),
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
                  {f.notified_at && (
                    <span className="text-xs text-muted-foreground">
                      benachrichtigt {formatDate(f.notified_at.slice(0, 10))}
                    </span>
                  )}
                  <div className="ml-auto flex flex-wrap items-center gap-2">
                    {/* „Bescheid geben" steht neben „Erledigt" und nicht darin:
                        Vieles wird abgehakt, ohne dass es etwas zu berichten
                        gäbe. Der Knopf erscheint nur, wenn es überhaupt geht —
                        passende Art, Adresse da, noch nicht benachrichtigt. */}
                    {RUECKMELDBAR.has(f.kind) && f.email && !f.notified_at && (
                      <Button
                        variant="secondary"
                        onClick={() => { setAntwortZu(f); setAntwortText(""); }}
                      >
                        Erledigt & Bescheid geben
                      </Button>
                    )}
                    <Button
                      variant="secondary"
                      disabled={mark.isPending}
                      onClick={() => mark.mutate({ id: f.id, read: open })}
                    >
                      {open ? "Erledigt" : "Wieder öffnen"}
                    </Button>
                  </div>
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

      <Dialog open={!!antwortZu} onOpenChange={(offen) => !offen && setAntwortZu(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Bescheid geben</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Geht an <span className="font-medium text-foreground">{antwortZu?.email}</span>.
            Die Mail nennt je nach Art den passenden Kernsatz und zitiert die
            ursprüngliche Nachricht.
          </p>
          <div>
            <Label htmlFor="rueckmeldung">Deine Nachricht (optional)</Label>
            <Textarea
              id="rueckmeldung"
              className="mt-1"
              rows={4}
              maxLength={2000}
              value={antwortText}
              onChange={(e) => setAntwortText(e.target.value)}
              placeholder="z. B. „Seit heute unter „Mein Konto“ zu finden.“"
            />
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" onClick={() => setAntwortZu(null)}>
              Abbrechen
            </Button>
            <Button
              disabled={benachrichtigen.isPending}
              onClick={() => antwortZu && benachrichtigen.mutate({
                id: antwortZu.id, message: antwortText,
              })}
            >
              {benachrichtigen.isPending ? "Wird verschickt…" : "Verschicken & erledigen"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
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
  if (isError || !data) return <ErrorState title="Die LLM-Nutzung konnte nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;
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
  if (isError) return <ErrorState title="Die Bewertungen konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;
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
  if (query.isError) return <ErrorState title="Die Ortskandidaten konnten nicht geladen werden"
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
  if (isError) return <ErrorState title="Die Zusammenführungen konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;

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
    <div className="space-y-5 [overflow-wrap:anywhere]">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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


/* ---------------------------------------------------------------- Live-Probe
   Der O1-Stream als Transkript, Äußerung für Äußerung — dieselbe Strecke
   wie in der Ratssitzung (ffmpeg → Gladia → Segment), nur ohne Sitzung.
   Tims Wunsch 06.09.2026: vor dem ersten echten Abend sehen, was ankommt
   und wie schnell. Server-Sent Events, kein Neuladen. */

type ProbeSegment = { start: number; end: number; text: string; wall: number };

function LiveProbeTab() {
  const [seconds, setSeconds] = useState(120);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [segments, setSegments] = useState<ProbeSegment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "nearest" }); }, [segments.length]);

  const stop = () => { abortRef.current?.abort(); abortRef.current = null; setRunning(false); };

  const start = async () => {
    setSegments([]); setError(null); setStatus("verbinde …"); setRunning(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(apiUrl(`/admin/live-probe?seconds=${seconds}`), {
        credentials: "include", signal: ctrl.signal,
        headers: { Accept: "text/event-stream", ...authHeaders() },
      });
      if (!res.ok || !res.body) {
        let msg = `Probe nicht gestartet (${res.status}).`;
        try { const b = await res.json(); if (typeof b?.detail === "string") msg = b.detail; } catch { /* ignore */ }
        throw new Error(msg);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let bytes = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        // Die ersten Bytes sind der Vorspann des Servers — ab hier steht
        // die Leitung, auch wenn noch keine Äußerung da ist.
        if (bytes === 0) setStatus((s) => (s === "verbinde …" ? "Leitung steht — warte auf den Server" : s));
        bytes += value.byteLength;
        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split("\n\n");
        buf = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.replace(/^data: ?/, "").trim();
          if (!line || line.startsWith(":")) continue;
          let msg: { type: string; [k: string]: unknown };
          try { msg = JSON.parse(line); } catch { continue; }
          if (msg.type === "status") setStatus(msg.text as string);
          else if (msg.type === "segment") {
            setStatus(null);
            setSegments((prev) => [...prev, msg as unknown as ProbeSegment]);
          } else if (msg.type === "done") setStatus(`Fertig: ${msg.segments} Äußerungen in ${msg.seconds} s.`);
          else if (msg.type === "error") setError(msg.message as string);
        }
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(e instanceof Error ? e.message : "Probe fehlgeschlagen.");
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  // ffmpeg liefert beim Start erst den HLS-Puffer (10–20 s Audio in zwei
  // Sekunden), danach Echtzeit. `wall - end` wäre anfangs negativ; der
  // größte Vorsprung des Audios vor der Uhr ist dieser Puffer, und um ihn
  // korrigiert ist der Rest der echte Verzug der Transkription.
  const backlog = Math.max(0, ...segments.map((s) => s.end - s.wall));
  const lagOf = (s: ProbeSegment) => s.wall - s.end + backlog;
  const lags = segments.map(lagOf);
  const median = lags.length ? [...lags].sort((a, b) => a - b)[Math.floor(lags.length / 2)] : null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Transkribiert den O1-Stream (was gerade läuft) über denselben Weg wie in der Ratssitzung:
        ffmpeg → Gladia → Äußerung mit Zeitmarke. Kostet rund 0,75 $ je Stunde, deshalb höchstens
        zehn Minuten und nur eine Probe zugleich.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          Dauer
          <select value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} disabled={running}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm">
            {[60, 120, 300, 600].map((s) => <option key={s} value={s}>{s < 120 ? `${s} s` : `${s / 60} min`}</option>)}
          </select>
        </label>
        {running
          ? <Button size="sm" variant="secondary" onClick={stop}>Stopp</Button>
          : <Button size="sm" onClick={() => void start()}>Probe starten</Button>}
        {running && (
          <span className="inline-flex items-center gap-2 text-xs text-red-600 dark:text-red-400">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inset-0 rounded-full bg-red-500 motion-safe:animate-ping" />
              <span className="relative h-2 w-2 rounded-full bg-red-500" />
            </span>
            läuft
          </span>
        )}
        {median != null && (
          <span className="text-xs text-muted-foreground">
            Verzug (Median): <strong className="font-semibold text-foreground">{median.toFixed(1)} s</strong> nach Satzende
          </span>
        )}
      </div>
      {status && <p className="text-sm text-muted-foreground">{status}</p>}
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {segments.length > 0 && (
        <Card className="max-h-[60vh] overflow-y-auto p-0">
          <ol className="divide-y divide-border">
            {segments.map((s, i) => (
              <li key={i} className="flex gap-3 px-4 py-2 text-sm">
                <span className="w-14 shrink-0 font-mono text-[11px] text-muted-foreground">
                  {Math.floor(s.start / 60)}:{String(Math.floor(s.start % 60)).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1 text-foreground">{s.text}</span>
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground" title="Sekunden nach Satzende">
                  +{lagOf(s).toFixed(1)} s
                </span>
              </li>
            ))}
          </ol>
          <div ref={endRef} />
        </Card>
      )}
    </div>
  );
}

/** „Neuigkeiten": die Release-Karten aus `kern/releases.py` und ihr Versand.
 *
 *  Der Text steht als Code im Repo, hier gibt es ihn nicht zu bearbeiten — ein
 *  Editor an dieser Stelle wäre eine zweite Wahrheit neben dem Changelog
 *  (dieselbe Entscheidung wie bei den Prompts, `kern/prompts.py`).
 *
 *  Was es hier gibt, ist die eine Handlung, die Ausliefern von Ankündigen
 *  trennt: verschicken, wenn der Deploy ein paar Tage stabil ist. Davor die
 *  Probe an das eigene Konto — eine Mail an alle ist nicht zurückzuholen.
 */
function NewsTab() {
  const qc = useQueryClient();
  const [fragt, setFragt] = useState<string | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin-news"],
    queryFn: () => vertrag.get("/admin/news"),
  });

  const probe = useMutation({
    mutationFn: (version: string) => api.post<{ sent: string[] }>(`/admin/news/${version}/test`, {}),
    onSuccess: (d) =>
      d.sent.length
        ? toast.success(`Probe raus (${d.sent.join(", ")}).`)
        : toast.error("Nichts verschickt — Zustellweg oder Mail-Schlüssel fehlt."),
    onError: () => toast.error("Die Probe ist nicht rausgegangen."),
  });

  const senden = useMutation({
    mutationFn: (version: string) =>
      api.post<{ recipients: number; queued: number; skipped: number }>(
        `/admin/news/${version}/send`, {}),
    onSuccess: (d) => {
      toast.success(
        d.recipients === 0
          ? "Niemand offen — alle haben die Ausgabe schon."
          : `${d.queued} eingereiht, ${d.skipped} übersprungen (Anlass aus). Zustellung läuft.`);
      void qc.invalidateQueries({ queryKey: ["admin-news"] });
    },
    onError: () => toast.error("Der Versand ist nicht angelaufen."),
  });

  if (isLoading) return <CardListSkeleton rows={2} />;
  if (isError || !data) {
    return <ErrorState title="Die Ausgaben konnten nicht geladen werden"
      onRetry={() => void refetch()} busy={isFetching} />;
  }

  const offeneVersion = fragt;

  return (
    <div className="@container">
      <p className="mb-4 max-w-2xl text-sm text-muted-foreground">
        Die Karte „Neu bei Ratslotse“ erscheint von selbst auf der Übersicht, sobald
        eine Ausgabe ausgeliefert ist. Der Versand per Mail und Push ist der
        zweite, eigene Schritt — am besten ein paar Tage später, wenn kein Hotfix
        mehr kommt. Wer die Karte schon weggeklickt hat, bekommt keine Mail mehr.
        Der Text selbst steht als Code in <code className="font-mono text-xs">kern/releases.py</code>.
      </p>

      {data.releases.length === 0 && (
        <EmptyState title="Noch keine Ausgabe mit Karte"
          hint="Ein Eintrag entsteht im Release-PR, zusammen mit dem Versionsschnitt." />
      )}

      <div className="flex flex-col gap-4">
        {data.releases.map((r) => (
          <Card key={r.version} className="p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <div className="min-w-0">
                <StatKicker>{`Version ${r.version} · ${formatDate(r.date)}`}</StatKicker>
                <h3 className="mt-1 font-display text-lg font-bold text-foreground">{r.title}</h3>
              </div>
              <div className="shrink-0 text-right text-sm">
                <p className="font-semibold tabular-nums text-foreground">
                  {r.open_recipients} offen
                </p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {r.sent_recipients} schon angeschrieben
                </p>
              </div>
            </div>

            <ul className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
              {r.highlights.map((h) => (
                <li key={h.url + h.title} className="text-sm">
                  <span className="font-semibold text-foreground">{h.title}</span>
                  <span className="text-muted-foreground"> — {h.text} </span>
                  <span className="font-mono text-[11px] text-muted-foreground">{h.url}</span>
                </li>
              ))}
            </ul>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button variant="secondary" size="sm" disabled={probe.isPending}
                onClick={() => probe.mutate(r.version)}>
                Probe an mich
              </Button>
              <Button size="sm"
                disabled={senden.isPending || r.open_recipients === 0}
                onClick={() => setFragt(r.version)}>
                {r.open_recipients === 0
                  ? "Alle angeschrieben"
                  : `An ${r.open_recipients} verschicken`}
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={offeneVersion !== null}
        onOpenChange={(o) => { if (!o) setFragt(null); }}
        title={`Ankündigung zu ${offeneVersion ?? ""} verschicken?`}
        description={
          "Geht als Mail und Push an alle, die die Karte noch nicht gesehen und den " +
          "Anlass nicht abgeschaltet haben. Das lässt sich nicht zurückholen — schick " +
          "vorher eine Probe an dich selbst."
        }
        confirmLabel="Verschicken"
        onConfirm={() => { if (offeneVersion) senden.mutate(offeneVersion); }}
      />
    </div>
  );
}
