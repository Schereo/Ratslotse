"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api, apiUrl, authHeaders } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { darfAdmin } from "@/lib/rechte";
import { AdminUserDetail, AdminGrowth, AdminRequestFehler, QuizFlagged, EntityAlias, AdminFeedback, PlaceCandidate } from "@/lib/types";
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
type AdminKohorten = ApiAntwort<"/admin/stats/cohorts">;
type AdminSackgasse = ApiAntwort<"/admin/stats/dead-ends">[number];
type AdminEreignisse = ApiAntwort<"/admin/stats/events">;
type AdminSeitenaufrufe = ApiAntwort<"/admin/stats/page-views">;
/** Ein Eintrag des Rollen-Katalogs — aus dem Vertrag, nicht abgetippt. */
type RolleInfo = ApiAntwort<"/admin/roles">[number];
import { Badge, Button, Card, CardListSkeleton, ChartSkeleton, ConfirmDialog, EmptyState, ErrorState, Input, PageHeader, Select, Spinner, TableSkeleton, Textarea, formatDate, formatDateTime, toast } from "@/components/ui";
import { AreaSparkline, MiniBars, StatKicker } from "@/components/admin-charts";
import { Mascot } from "@/components/mascot";
import { cn } from "@/lib/utils";
import type { OrtsbereichCatalog } from "@/lib/districts";
import { clientFarbe, clientKurz, clientLabel, hauptClient } from "@/lib/clients";

type Tab = "stats" | "fehler" | "feedback" | "llm" | "users" | "quiz" | "orte" | "themen" | "live" | "news";

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("stats");

  if (loading) return <Spinner />;
  if (!user || !darfAdmin(user)) {
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
          ["fehler", "Fehler"],
          ["feedback", "Feedback"],
          ["llm", "LLM-Kosten"],
          ["users", "Web-Nutzer*innen"],
          ["quiz", "Quiz"],
          ["orte", "Ortskandidaten"],
          ["themen", "Themen-Dubletten"],
          ["live", "Live-Probe"],
          ["news", "Neuigkeiten"],
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
        {tab === "fehler" && <FehlerTab />}
        {tab === "feedback" && <FeedbackTab />}
        {tab === "llm" && <LlmUsageTab />}
        {tab === "users" && <UsersTab currentUserId={user.id} />}
        {tab === "quiz" && <QuizModerationTab />}
        {tab === "orte" && <PlaceCandidatesTab />}
        {tab === "themen" && <EntityAliasTab />}
        {tab === "live" && <LiveProbeTab />}
        {tab === "news" && <NewsTab />}
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

/** Die vier neuen Statistik-Abschnitte (Plan „Sehen und Zurückholen", Teil A).
 *
 *  Gemeinsamer Grundsatz nach Tims Rückmeldung vom 09.09.: Jede Zahl sagt,
 *  **woraus** sie besteht (Zähler und Nenner) und **wie sie sich verändert**
 *  hat (gegen dieselbe Spanne davor). Ein Stand allein — „43 %" — sagt weder,
 *  ob das 3 von 7 sind, noch ob es letzte Woche 60 % waren. Die Veränderung
 *  trägt Signal-Orange, wie jedes Delta in der Designsprache (§ 2, § 5 RG-04);
 *  Ampelfarben auf Balken sind raus, sie beantworteten eine andere Frage als
 *  die Balkenlänge und brauchten eine Legende, um nicht falsch gelesen zu werden.
 */

/** Zähler und Nenner in Mono — „6 von 14". */
function Basis({ n, von, was }: { n: number; von: number; was?: string }) {
  return (
    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
      {n.toLocaleString("de-DE")} von {von.toLocaleString("de-DE")}{was ? ` ${was}` : ""}
    </span>
  );
}

/** Die Veränderung gegen den Vorzeitraum — als Chip in Signal-Orange.
 *
 *  `prozent`: beide Werte sind Anteile, die Differenz steht in Punkten.
 *  `invers`: klein ist gut (Antworten ohne Quelle). Die Farbe sagt nicht
 *  „gut/schlecht", sondern nur „hat sich bewegt" — die Richtung trägt der
 *  Pfeil, die Bewertung der Kontext. Ohne Vergleichswert: „kein Vergleich",
 *  nie eine erfundene Null. */
function Veraenderung({ jetzt, vorher, prozent, invers, klein }: {
  jetzt: number | null; vorher: number | null | undefined; prozent?: boolean; invers?: boolean; klein?: boolean;
}) {
  const groesse = klein ? "text-[10.5px] px-1.5 py-px" : "text-[11px] px-2 py-0.5";
  if (jetzt == null || vorher == null) {
    return <span className={cn("inline-flex items-center rounded-full border border-dashed border-border font-mono text-muted-foreground/70", groesse)}>kein Vergleich</span>;
  }
  const d = prozent ? Math.round((jetzt - vorher) * 100) : jetzt - vorher;
  if (d === 0) {
    return <span className={cn("inline-flex items-center rounded-full bg-muted font-mono text-muted-foreground", groesse)}>unverändert</span>;
  }
  const besser = invers ? d < 0 : d > 0;
  const text = prozent ? `${d > 0 ? "+" : "−"}${Math.abs(d)} Pkt.` : `${d > 0 ? "+" : "−"}${Math.abs(d).toLocaleString("de-DE")}`;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full bg-signal/[0.10] font-mono font-semibold text-signal", groesse)}
      title={besser ? "besser als im Zeitraum davor" : "schlechter als im Zeitraum davor"}>
      <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        {d > 0 ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
      </svg>
      {text}
    </span>
  );
}

function AbschnittKopf({ titel, rechts, children }: { titel: string; rechts?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-x-6 gap-y-1">
      <div className="min-w-0">
        <h3 className="font-display text-[15px] font-bold text-foreground">{titel}</h3>
        {children && <p className="mt-0.5 max-w-[62ch] text-[12px] text-muted-foreground">{children}</p>}
      </div>
      {rechts && <span className="shrink-0 pt-1 text-right font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">{rechts}</span>}
    </div>
  );
}

/** Der Trichter je Registrierungswoche — wo neue Konten abreißen.
 *
 *  Die eine Regel, die diese Ansicht trägt: **erreicht IMMER gegen erreichbar**.
 *  Ein Konto von gestern kann „kam binnen 30 Tagen wieder" noch nicht geschafft
 *  haben; zeigte man nur die erreichte Zahl, läse sich jede frische Woche als
 *  Totalausfall. Der Balken hat deshalb drei Lagen: alle Anmeldungen (Spur),
 *  die schon alt genug sind (heller Teil), die es geschafft haben (dunkler
 *  Teil) — dieselbe Skala für alle drei, keine Farbe, die etwas anderes meint.
 */
function KohortenSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "cohorts"],
    queryFn: () => api.get<AdminKohorten>("/admin/stats/cohorts?weeks=8"),
  });

  if (isPending) return <div className="pt-2"><ChartSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Der Trichter kam nicht durch" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  const k = data.kennzahlen;
  const v = data.previous;
  const b = data.basis;
  const start = data.total.find((s) => s.key === "registriert")?.n ?? 0;

  return (
    <div className="space-y-3 pt-2">
      <AbschnittKopf titel="Neue Konten: was daraus wird"
        rechts={`${data.weeks} Wochen · davor ${b.vorher_n} ${b.vorher_n === 1 ? "Konto" : "Konten"}`}>
        {data.excluded === 1 ? "Ein Betreiber-/Testkonto ist nicht gezählt." : `${data.excluded} Betreiber-/Testkonten sind nicht gezählt.`}
        {" "}Veränderung jeweils gegen dieselbe Spanne davor.
      </AbschnittKopf>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KennzahlCard label="Haken-Quote" hint="Thema oder Gremium am ersten Tag" wert={k.haken_quote} vorher={v.haken_quote} basis={b.haken} anteil vergleichbar={b.vorher_n >= 3} />
        <KennzahlCard label="Kam wieder" hint="binnen sieben Tagen" wert={k.tag7} vorher={v.tag7} basis={b.tag7} anteil vergleichbar={b.vorher_n >= 3} />
        <KennzahlCard label="Ohne Quelle" hint="Antworten, 90 Tage" wert={k.sackgassen_quote} vorher={v.sackgassen_quote} basis={b.sackgassen} anteil invers />
        <KennzahlCard label="Fragen je Konto" hint="Median aktiver Konten, 7 Tage" wert={k.fragen_median} vorher={v.fragen_median} />
      </div>

      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <StatKicker>Trichter</StatKicker>
          <span className="font-mono text-[10.5px] text-muted-foreground">{start} Anmeldungen</span>
        </div>
        <div className="mt-3.5 flex flex-col gap-2">
          {data.total.map((stufe, i) => (
            <TrichterZeile key={stufe.key} stufe={stufe} start={start} davor={i > 0 ? data.total[i - 1] : null} />
          ))}
        </div>
        <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-5 rounded-sm bg-primary" /> hat die Stufe erreicht</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-5 rounded-sm bg-primary/25" /> ist alt genug, um sie zu erreichen</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-5 rounded-sm bg-muted" /> alle Anmeldungen</span>
        </div>
      </Card>

      {data.cohorts.length > 0 && (
        <Card className="p-4">
          <div className="flex items-baseline justify-between">
            <StatKicker>Je Registrierungswoche</StatKicker>
            <span className="font-mono text-[10.5px] text-muted-foreground">erreicht / alt genug</span>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-border text-left font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">Woche ab</th>
                  <th className="pb-2 pr-3 text-right font-medium">Neu</th>
                  <th className="pb-2 pr-3 text-right font-medium">Haken</th>
                  <th className="pb-2 pr-3 text-right font-medium">2. Tag</th>
                  <th className="pb-2 pr-3 text-right font-medium">7 Tage</th>
                  <th className="pb-2 text-right font-medium">30 Tage</th>
                </tr>
              </thead>
              <tbody>
                {[...data.cohorts].reverse().map((kohorte, i) => (
                  <tr key={kohorte.week} className={cn("border-b border-border/60 last:border-0", i === 0 && "bg-primary/[0.04]")}>
                    <td className="py-2 pr-3 text-foreground">
                      {formatDate(kohorte.week)}
                      {i === 0 && <span className="ml-2 font-mono text-[10px] uppercase tracking-[0.08em] text-primary">läuft</span>}
                    </td>
                    <td className="py-2 pr-3 text-right font-semibold tabular-nums text-foreground">{kohorte.n}</td>
                    {(["haken", "tag2", "tag7", "tag30"] as const).map((key) => {
                      const st = kohorte.stages.find((x) => x.key === key);
                      return (
                        <td key={key} className="py-2 pr-3 text-right font-mono tabular-nums last:pr-0">
                          {!st || st.eligible === 0 ? (
                            <span className="text-muted-foreground/50" title="Noch keine dieser Anmeldungen ist alt genug">–</span>
                          ) : (
                            <ZellenAnteil n={st.n} von={st.eligible} />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2.5 text-[11.5px] text-muted-foreground">
            „–" heißt: noch nicht messbar. Ein Konto von gestern kann „30 Tage" weder geschafft noch verfehlt haben.
          </p>
        </Card>
      )}
    </div>
  );
}

/** Eine Tabellenzelle „2 / 4" mit einem Füllstand dahinter — so liest man die
 *  Spalte auf einen Blick, statt jeden Bruch im Kopf zu rechnen. */
function ZellenAnteil({ n, von }: { n: number; von: number }) {
  const anteil = von > 0 ? n / von : 0;
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className="hidden h-1.5 w-10 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
        <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.round(anteil * 100)}%` }} />
      </span>
      <span className="text-foreground">{n}<span className="text-muted-foreground"> / {von}</span></span>
    </span>
  );
}

/** Eine Stufe als dreilagiger Balken — alle, alt genug, erreicht. */
function TrichterZeile({ stufe, start, davor }: {
  stufe: AdminKohorten["total"][number]; start: number; davor: AdminKohorten["total"][number] | null;
}) {
  const offen = stufe.eligible === 0;
  const pct = (x: number) => (start > 0 ? Math.round((x / start) * 100) : 0);
  // Der Abriss zur Stufe davor — die Zahl, die man wissen will: WO reißt es?
  const abriss = davor && !offen && davor.n > stufe.n ? davor.n - stufe.n : 0;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:grid-cols-[13.5rem_minmax(0,1fr)_7.5rem]">
      <span className="truncate text-[13px] text-foreground">{stufe.label}</span>
      <div className="relative hidden h-3 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
        <div className="absolute inset-y-0 left-0 rounded-full bg-primary/25" style={{ width: `${pct(stufe.eligible)}%` }} />
        <div className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${pct(stufe.n)}%` }} />
      </div>
      <span className="flex items-baseline justify-end gap-2 whitespace-nowrap text-right tabular-nums">
        {offen ? (
          <span className="font-mono text-[11px] text-muted-foreground/70">noch offen</span>
        ) : (
          <>
            {abriss > 0 && <span className="font-mono text-[10.5px] text-signal">−{abriss}</span>}
            <span className="text-[12.5px]"><span className="font-semibold text-foreground">{stufe.n}</span><span className="text-muted-foreground"> von {stufe.eligible}</span></span>
          </>
        )}
      </span>
    </div>
  );
}

/** Eine Kennzahl: die Zahl, woraus sie besteht, und wie sie sich bewegt hat.
 *  `null` heißt „keine Aussage", nicht „0 %". */
function KennzahlCard({ label, hint, wert, vorher, basis, anteil, invers, vergleichbar = true }: {
  label: string; hint: string; wert: number | null; vorher: number | null;
  basis?: [number, number] | readonly [number, number]; anteil?: boolean; invers?: boolean;
  /** Ein Vorzeitraum mit ein, zwei Konten ist kein Vergleich, sondern Rauschen —
   *  dann steht „kein Vergleich" da, nicht „−57 Pkt.". */
  vergleichbar?: boolean;
}) {
  const text = wert == null ? "–" : anteil ? `${Math.round(wert * 100)} %` : wert.toLocaleString("de-DE");
  return (
    <Card className="p-3.5">
      <StatKicker>{label}</StatKicker>
      <p className={cn("mt-1.5 whitespace-nowrap font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums", wert == null ? "text-muted-foreground" : "text-foreground")}>
        {text}
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <Veraenderung jetzt={wert} vorher={vergleichbar ? vorher : null} prozent={anteil} invers={invers} klein />
        {basis && wert != null && <Basis n={basis[0]} von={basis[1]} />}
      </div>
      <p className="mt-1.5 text-[11.5px] leading-snug text-muted-foreground">{wert == null ? "noch keine Grundlage" : hint}</p>
    </Card>
  );
}

/** Lesbare Namen für die Seitenmuster — der Pfad bleibt als Zweitzeile stehen,
 *  weil er die Wahrheit ist; der Name ist die Übersetzung. Die vier Reiter der
 *  Ratsinfo-Seite tragen ihren Bereich, sonst sähen sie aus wie vier Seiten. */
const SEITEN_NAMEN: Record<string, string> = {
  "/": "Startseite", "/login": "Anmelden", "/register": "Registrieren", "/forgot-password": "Passwort vergessen",
  "/reset-password": "Passwort zurücksetzen", "/verify-email": "E-Mail bestätigen", "/hilfe": "Hilfe",
  "/impressum": "Impressum", "/datenschutz": "Datenschutz", "/barrierefreiheit": "Barrierefreiheit",
  "/changelog": "Changelog", "/g": "Geteilte Antwort", "/kommunalwahl": "Kommunalwahl", "/wahlabend": "Wahlabend",
  "/council": "Ratsinfo", "/council?tab=decisions": "Ratsinfo · Suche", "/council?tab=sessions": "Ratsinfo · Sitzungen",
  "/council?tab=themen": "Ratsinfo · Themen", "/council?tab=analysis": "Ratsinfo · Analyse",
  "/council/decision": "Beschluss-Seite", "/council/sitzung": "Sitzungs-Seite", "/council/thema": "Themen-Seite",
  "/council/person": "Personen-Seite", "/council/ort": "Orts-Seite", "/council/ideen": "Ideen",
  "/dashboard": "Heute", "/fragen": "Fragen", "/karte": "Stadtkarte", "/viertel": "Mein Viertel",
  "/topics": "Meine Themen", "/abos": "Abos", "/bookmarks": "Merkliste", "/quiz": "Quiz", "/quiz/stats": "Quiz-Statistik",
  "/account": "Konto", "/admin": "Admin", "/haushalt": "Haushalt", "/andere": "Sonstiges",
};
function seitenName(route: string): string {
  if (SEITEN_NAMEN[route]) return SEITEN_NAMEN[route];
  if (route.startsWith("/haushalt/")) return "Haushalt · " + route.slice("/haushalt/".length);
  if (route.startsWith("/kommunalwahl/")) return "Kommunalwahl · " + route.slice("/kommunalwahl/".length).replace("/{slug}", "");
  return route;
}

/** Zwei Anteile als EIN Balken — ergibt zusammen immer die ganze Breite. */
function AnteilBalken({ teile }: { teile: { label: string; n: number; ton: string }[] }) {
  const summe = Math.max(1, teile.reduce((a, t) => a + t.n, 0));
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
        {teile.map((t) => <span key={t.label} className={t.ton} style={{ width: `${(t.n / summe) * 100}%` }} />)}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
        {teile.map((t) => (
          <span key={t.label} className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", t.ton)} />
            {t.label} <span className="font-mono tabular-nums text-foreground">{Math.round((t.n / summe) * 100)} %</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Anonyme Seitenaufrufe — die Nutzung, die vorher gar nicht sichtbar war.
 *
 *  Die Ansicht sagt bewusst „Aufrufe" und „Besuche", nie „Besucher": Ohne
 *  Wiedererkennung gibt es keine eindeutigen Personen, und eine Zahl, die so
 *  tut, wäre gelogen. Ein „Besuch" ist der erste Aufruf in einem Browser-Tab.
 */
function SeitenaufrufeSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "page-views"],
    queryFn: () => api.get<AdminSeitenaufrufe>("/admin/stats/page-views?days=30"),
  });

  if (isPending) return <div className="pt-2"><ChartSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Seitenaufrufe kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  if (data.total === 0) {
    return (
      <div className="space-y-3 pt-2">
        <AbschnittKopf titel="Seitenaufrufe" rechts="anonym · ohne Kennung" />
        <Card className="flex items-center gap-4 p-4">
          <Mascot pose="search" className="h-14 w-14 shrink-0" />
          <p className="text-[13px] text-muted-foreground">
            Noch nichts gezählt. Die Zählung läuft ab dem Deploy dieser Version — vorher
            aufgerufene Seiten lassen sich nicht nachtragen.
          </p>
        </Card>
      </div>
    );
  }

  const angemeldet = data.total - data.anonymous;
  const spitze = data.pages[0]?.n ?? 1;

  return (
    <div className="space-y-3 pt-2">
      <AbschnittKopf titel="Seitenaufrufe" rechts={`${data.days} Tage · anonym, ohne Kennung`}>
        Ein „Besuch" ist der erste Aufruf in einem Browser-Tab. Wiedererkennung gibt es nicht — deshalb steht hier nirgends eine Zahl von Besucher*innen.
      </AbschnittKopf>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.5fr_1fr]">
        <Card className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <StatKicker>Aufrufe je Tag</StatKicker>
              <div className="mt-1.5 flex items-end gap-2">
                <p className="font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{data.total.toLocaleString("de-DE")}</p>
                <Veraenderung jetzt={data.total} vorher={data.previous_total} />
              </div>
            </div>
            <div className="text-right">
              <StatKicker>Besuche</StatKicker>
              <div className="mt-1.5 flex items-end justify-end gap-2">
                <p className="font-display text-[22px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{data.sessions.toLocaleString("de-DE")}</p>
                <Veraenderung jetzt={data.sessions} vorher={data.previous_sessions} klein />
              </div>
            </div>
          </div>
          <MiniBars values={data.series.length ? data.series.map((d) => d.n) : [0]} days={data.series.map((d) => d.day)} height={64} className="mt-4" />
        </Card>
        <Card className="flex flex-col gap-4 p-4">
          <div>
            <StatKicker>Angemeldet oder nicht</StatKicker>
            <div className="mt-2.5">
              <AnteilBalken teile={[
                { label: "ohne Anmeldung", n: data.anonymous, ton: "bg-primary/30" },
                { label: "angemeldet", n: angemeldet, ton: "bg-primary" },
              ]} />
            </div>
          </div>
          {data.clients.length > 1 && (
            <div>
              <StatKicker>Womit</StatKicker>
              <div className="mt-2.5">
                <AnteilBalken teile={data.clients.map((c, i) => ({
                  label: clientLabel(c.client), n: c.n, ton: i === 0 ? "bg-primary" : i === 1 ? "bg-signal/70" : "bg-primary/30",
                }))} />
              </div>
            </div>
          )}
        </Card>
      </div>

      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <StatKicker>Meistgesehene Seiten</StatKicker>
          <span className="font-mono text-[10.5px] text-muted-foreground">Aufrufe · Anteil</span>
        </div>
        <div className="mt-3.5 flex flex-col gap-2">
          {data.pages.map((seite) => (
            <div key={seite.route} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:grid-cols-[15rem_minmax(0,1fr)_7rem]">
              <div className="min-w-0">
                <p className="truncate text-[13px] text-foreground">{seitenName(seite.route)}</p>
                <p className="truncate font-mono text-[10.5px] text-muted-foreground">{seite.route}</p>
              </div>
              <div className="hidden h-2.5 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
                <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(2, Math.round((seite.n / spitze) * 100))}%` }} />
              </div>
              <span className="whitespace-nowrap text-right text-[12.5px] tabular-nums">
                <span className="font-semibold text-foreground">{seite.n.toLocaleString("de-DE")}</span>
                <span className="font-mono text-[10.5px] text-muted-foreground"> · {Math.round((seite.n / data.total) * 100)} %</span>
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11.5px] leading-snug text-muted-foreground">
          Detailseiten tragen ihre Kennung in der Query, und die wird nicht gemeldet —
          „Beschluss-Seite" heißt also „irgendein Beschluss", nie welcher.
        </p>
      </Card>
    </div>
  );
}

/** Welche Handlungen wie oft vorkommen — und die zwei Anteile dahinter.
 *
 *  Neben jeder Zahl steht, aus wie vielen KONTEN sie stammt, und wie sie sich
 *  gegen die Spanne davor bewegt hat. Das ist der Unterschied zwischen
 *  „hundert Fragen" und „hundert Fragen von einer Person, halb so viele wie
 *  im Monat davor".
 */
function EreignisSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "events"],
    queryFn: () => api.get<AdminEreignisse>("/admin/stats/events?days=30"),
  });

  if (isPending) return <div className="pt-2"><ChartSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Ereignisse kamen nicht durch" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  const zugriffe = data.events.find((e) => e.key === "session");
  const fragen = data.events.find((e) => e.key === "ai_question");
  const zeilen = data.events.filter((e) => e.key !== "session");
  const spitze = Math.max(1, ...zeilen.map((e) => e.n));
  const chipN = data.events.find((e) => e.key === "ai_question_chip")?.n ?? 0;
  const leerN = data.events.find((e) => e.key === "ai_answer_empty")?.n ?? 0;

  return (
    <div className="space-y-3 pt-2">
      <AbschnittKopf titel="Was gemacht wird"
        rechts={zugriffe ? `${zugriffe.n.toLocaleString("de-DE")} Zugriffe · ${zugriffe.users} Konten · ${data.days} Tage` : `${data.days} Tage`}>
        Jede Zeile mit Konten-Zahl und Veränderung gegen die {data.days} Tage davor.
      </AbschnittKopf>

      <div className="grid grid-cols-2 gap-3">
        <Card className="p-3.5">
          <StatKicker>Fragen aus einem Vorschlag</StatKicker>
          <div className="mt-1.5 flex items-end justify-between gap-2">
            <p className={cn("font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums", data.chip_share == null ? "text-muted-foreground" : "text-foreground")}>
              {data.chip_share == null ? "–" : `${Math.round(data.chip_share * 100)} %`}
            </p>
            <Veraenderung jetzt={data.chip_share} vorher={data.previous_chip_share} prozent />
          </div>
          <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="text-[11.5px] text-muted-foreground">{data.chip_share == null ? "noch keine Fragen im Zeitraum" : "der Rest wurde ins Feld getippt"}</span>
            {fragen && data.chip_share != null && <Basis n={chipN} von={fragen.n} was="Fragen" />}
          </div>
        </Card>
        <Card className="p-3.5">
          <StatKicker>Antworten ohne Quelle</StatKicker>
          <div className="mt-1.5 flex items-end justify-between gap-2">
            <p className={cn("font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums", data.empty_share == null ? "text-muted-foreground" : "text-foreground")}>
              {data.empty_share == null ? "–" : `${Math.round(data.empty_share * 100)} %`}
            </p>
            <Veraenderung jetzt={data.empty_share} vorher={data.previous_empty_share} prozent invers />
          </div>
          <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="text-[11.5px] text-muted-foreground">{data.empty_share == null ? "noch keine Fragen im Zeitraum" : "jede davon ist eine Sackgasse"}</span>
            {fragen && data.empty_share != null && <Basis n={leerN} von={fragen.n} was="Antworten" />}
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="flex flex-col gap-2">
          {zeilen.map((e) => (
            <div key={e.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:grid-cols-[15rem_minmax(0,1fr)_11rem]">
              <span className={cn("truncate text-[13px]", e.n === 0 ? "text-muted-foreground" : "text-foreground")}>{e.label}</span>
              <div className="hidden h-2.5 overflow-hidden rounded-full bg-muted sm:block" aria-hidden>
                <div className={cn("h-full rounded-full", e.n === 0 ? "bg-transparent" : "bg-primary")} style={{ width: `${Math.min(100, Math.round((e.n / spitze) * 100))}%` }} />
              </div>
              <span className="flex items-baseline justify-end gap-2 whitespace-nowrap text-right tabular-nums">
                <Veraenderung jetzt={e.n} vorher={e.previous} klein />
                <span className="text-[12.5px]">
                  <span className={cn("font-semibold", e.n === 0 ? "text-muted-foreground" : "text-foreground")}>{e.n.toLocaleString("de-DE")}</span>
                  <span className="font-mono text-[10.5px] text-muted-foreground"> · {e.users} {e.users === 1 ? "Konto" : "Konten"}</span>
                </span>
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11.5px] leading-snug text-muted-foreground">
          Die zweite Zahl ist die der Konten. Eine große Zahl aus einem einzigen Konto
          ist etwas anderes als dieselbe Zahl aus zwanzig.
        </p>
      </Card>
    </div>
  );
}

/** Fragen, auf die es keine belegte Antwort gab — die Liste hinter der Quote.
 *
 *  Eine Quote sagt „9 % scheitern", diese Liste sagt woran. Der bekannteste
 *  Fall stand am 09.08.2026 im Bestand: zweimal „Giftmüll am Fliegerhorst",
 *  zweimal „keine Informationen" — weil die Unterlagen „Sondermüll" und
 *  „Schießanlage" sagen. Ein Blick hierher hätte das am selben Tag gezeigt.
 */
function SackgassenSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "dead-ends"],
    queryFn: () => api.get<AdminSackgasse[]>("/admin/stats/dead-ends?days=30"),
  });

  if (isPending) return <div className="pt-2"><CardListSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Liste kam nicht durch" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-2">
      <AbschnittKopf titel="Fragen ohne Antwort"
        rechts={`${data.length} ${data.length === 1 ? "Frage" : "Fragen"} · 30 Tage · gespeicherte Gespräche`}>
        Woran es scheitert — ohne Konto und ohne Gesprächs-id, denn eine Liste mit Kennung neben der Frage wäre ein Leseprotokoll.
      </AbschnittKopf>

      {data.length === 0 ? (
        <Card className="flex items-center gap-4 p-4">
          <Mascot pose="wave" className="h-14 w-14 shrink-0" />
          <p className="text-[13px] text-muted-foreground">
            Keine in den letzten 30 Tagen. Entweder fand alles etwas — oder es gab keine gespeicherten Gespräche im Zeitraum.
          </p>
        </Card>
      ) : (
        <Card className="divide-y divide-border p-0">
          {data.map((s, i) => (
            <div key={`${s.created}-${i}`} className="grid gap-x-4 gap-y-1 p-4 sm:grid-cols-[5.5rem_minmax(0,1fr)]">
              <span className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground sm:pt-1">
                {formatDate(s.created.slice(0, 10))}
              </span>
              <div className="min-w-0">
                <p className="text-[14px] font-semibold leading-snug text-foreground">{s.question}</p>
                <p className="mt-1 text-[12.5px] italic leading-snug text-muted-foreground">{s.answer}</p>
              </div>
            </div>
          ))}
        </Card>
      )}
      <p className="text-[11.5px] leading-snug text-muted-foreground">
        Die vollständige Zahl steht oben unter „Antworten ohne Quelle" — diese Liste zeigt nur die Fälle, die ohnehin gespeichert sind.
      </p>
    </div>
  );
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

      <KohortenSection />

      <SeitenaufrufeSection />

      <EreignisSection />

      <SackgassenSection />

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

              <JobSchritte steps={job.steps} />

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

/** Die Unterschritte eines Sammel-Jobs, aufklappbar unter seiner Karte.
 *
 *  **Wozu.** `weekly_enrich` läuft sonntags 18 Schritte durch und stand im
 *  Panel als EINE Kachel mit „Schritte gesamt 18 · davon fehlgeschlagen 0".
 *  Welcher Schritt zwei Stunden brauchte und welcher stumm nichts tat, wusste
 *  nur das Log auf dem Server — obwohl der Lauf es die ganze Zeit mitschrieb.
 *  16 der 18 Schritte rufen kein `run_guarded` und haben deshalb auch keine
 *  eigene Kachel, unter der man nachsehen könnte.
 *
 *  Natives `<details>`: Tastatur und Screenreader können das ohne Zutun, und
 *  eine Liste, die nur beim Nachsehen aufgeht, kostet zugeklappt nichts. */
function JobSchritte({ steps }: { steps: AdminJob["steps"] }) {
  if (!steps.length) return null;
  const fehler = steps.filter((s) => s.status === "error").length;
  // Der längste Schritt setzt den Maßstab der Balken. Sie sind der eigentliche
  // Gewinn dieser Liste: Wo die Zeit hingeht, sieht man in einer Spalte
  // Sekundenzahlen erst beim Durchlesen, im Balken sofort.
  const laengster = Math.max(...steps.map((s) => s.duration_s ?? 0), 1);
  return (
    <details className="group mt-2.5">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <ChevronDown className="h-3.5 w-3.5 shrink-0 transition-transform duration-fluss ease-out-strong group-open:rotate-180" />
        {steps.length} Schritte
        {fehler > 0
          ? <span className="font-semibold text-destructive">· {fehler} fehlgeschlagen</span>
          : <span>· alle durchgelaufen</span>}
      </summary>
      <ul className="mt-1.5 space-y-px border-l-2 border-border pl-2.5">
        {steps.map((s, i) => (
          <li key={`${s.script}-${i}`} className="flex items-center gap-2 py-0.5">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full",
              s.status === "ok" ? "bg-green-500" : "bg-red-500")} />
            <span className="min-w-0 flex-1 truncate text-[11.5px] text-foreground">{s.name}</span>
            <span aria-hidden className="hidden h-1 w-16 shrink-0 overflow-hidden rounded-full bg-border sm:block">
              <span className="block h-full rounded-full bg-primary/45"
                style={{ width: `${Math.round(((s.duration_s ?? 0) / laengster) * 100)}%` }} />
            </span>
            {/* Feste Breite, rechtsbündig: Ohne sie schiebt die unterschiedlich
                breite Zeitangabe („8 s" vs. „31 min") den Balken davor hin und
                her — und eine Balkenspalte, die nicht fluchtet, taugt nicht
                zum Vergleichen, wozu sie allein da ist. */}
            <span className="w-12 shrink-0 text-right tabular-nums text-[11px] text-muted-foreground">
              {s.duration_s != null ? formatDuration(s.duration_s) : "—"}
            </span>
          </li>
        ))}
      </ul>
    </details>
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
  cities_classify: "Fremde Ratsvorlage einordnen",
  cities_fit: "Hat Oldenburg das schon?",
  cities_evidence_terms: "Städtevergleich: Oldenburger Suchwörter",
  cities_effort: "Städtevergleich: Was kostet die Idee?",
  cities_stance: "Städtevergleich: Wollte der Rat die Idee?",
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
    return <ErrorState title="Die Fehlerliste kam nicht durch"
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
  // Der Rollen-Katalog kommt vom Server (Namen, Beschriftung, Rechte). Er
  // steht hier und nicht als Liste im Code, damit eine neue Rolle in
  // `kern/roles.py` im Panel erscheint, ohne dass jemand das Frontend anfasst.
  const { data: rollenKatalog = [] } = useQuery({
    queryKey: ["admin", "roles"],
    queryFn: () => vertrag.get("/admin/roles"),
    staleTime: 60 * 60 * 1000,  // ändert sich nur mit einem Deploy
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
                    {/* Ein Abzeichen JE Rolle: Seit ein Konto mehrere tragen
                        kann, verschwiege ein einzelnes „admin" das Ratsmandat
                        daneben. Die Beschriftung kommt aus dem Katalog, damit
                        eine neue Rolle hier ohne Codeänderung auftaucht. */}
                    {(u.roles ?? []).map((r) => (
                      <span key={r} className="shrink-0 rounded bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
                        {rollenKatalog.find((k) => k.key === r)?.label ?? r}
                      </span>
                    ))}
                    {u.status !== "active" && <span className="shrink-0 rounded bg-amber-500/15 px-1.5 text-[10px] font-semibold text-amber-700 dark:text-amber-500">{u.status === "disabled" ? "gesperrt" : "wartet"}</span>}
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
        ? <UserDetailPanel userId={selected} isSelf={selected === currentUserId}
                           rollenKatalog={rollenKatalog} onClose={() => setSelected(null)} />
        : <Card className="hidden p-8 text-center text-sm text-muted-foreground lg:block">Nutzer*in wählen, um Details zu sehen.</Card>}
    </div>
  );
}

function UserDetailPanel({ userId, isSelf, rollenKatalog, onClose }: {
  userId: number; isSelf: boolean; rollenKatalog: RolleInfo[]; onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  };
  // Die VOLLSTÄNDIGE Liste geht raus, nicht ein Delta: Ein PUT mit dem
  // gewünschten Endzustand ist idempotent und kann sich nicht mit dem Klick
  // eines zweiten Admins überkreuzen.
  const rollenMutation = useMutation({
    mutationFn: (roles: string[]) => api.put(`/admin/users/${userId}/roles`, { roles }),
    onSuccess: () => { toast.success("Rollen aktualisiert."); invalidate(); },
    onError: () => toast.error("Rollen konnten nicht geändert werden."),
  });
  const statusMutation = useMutation({
    mutationFn: (status: "active" | "disabled") => api.put(`/admin/users/${userId}/status`, { status }),
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

      {/* Rollen. Bis 09/2026 stand hier ein Umschalt-Knopf „Zu Admin" — der
          ging nur, solange es zwei Rollen gab. Jetzt trägt ein Konto mehrere,
          und jede ist ein eigener Schalter. */}
      <StatKickerSpaced>Rollen</StatKickerSpaced>
      <div className="mt-2 flex flex-col gap-1.5">
        {rollenKatalog.filter((r) => r.assignable).map((r) => {
          const an = (data.roles ?? []).includes(r.key);
          // Sich selbst die Adminrechte zu nehmen ist der eine Fehler ohne
          // Undo: Danach kommt niemand mehr ins Panel. Der Server weist es
          // ohnehin ab (400) — hier steht der Schalter gar nicht erst zur
          // Verfügung, statt einen Klick anzubieten, der scheitert.
          const gesperrt = isSelf && r.key === "admin" && an;
          return (
            <button
              key={r.key}
              type="button"
              disabled={gesperrt || rollenMutation.isPending}
              aria-pressed={an}
              onClick={() => rollenMutation.mutate(
                an ? (data.roles ?? []).filter((x) => x !== r.key) : [...(data.roles ?? []), r.key])}
              className={cn(
                "flex items-start gap-3 rounded-[10px] border px-3 py-2.5 text-left transition-colors",
                an ? "border-primary/40 bg-primary/[0.06]" : "border-border bg-card hover:bg-accent",
                gesperrt && "cursor-not-allowed opacity-60",
              )}
            >
              <span className={cn(
                "mt-px flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border",
                an ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background",
              )} aria-hidden>
                {an && (
                  <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor"
                       strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><path d="m5 13 4 4L19 7" /></svg>
                )}
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold text-foreground">{r.label}</span>
                <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
                  {gesperrt ? "Du kannst dir die Adminrechte nicht selbst entziehen." : r.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {!isSelf && (
        <div className="mt-4 flex gap-2 border-t border-border pt-4">
          <Button variant="secondary" size="sm"
            onClick={() => statusMutation.mutate(data.status === "active" ? "disabled" : "active")}>
            {data.status === "active" ? "Sperren" : "Freischalten"}
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
    return <ErrorState title="Die Ausgaben kamen nicht durch"
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
