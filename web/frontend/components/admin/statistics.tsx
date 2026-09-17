"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { Card, CardListSkeleton, ChartSkeleton, ErrorState, TableSkeleton, formatDate } from "@/components/ui";
import { StatKicker } from "@/components/admin-charts";
import { AdminVerlauf } from "@/components/grafik/admin-verlauf";
import { Mascot } from "@/components/mascot";
import { cn } from "@/lib/utils";
import { clientFarbe, clientLabel } from "@/lib/clients";
import { KohortenSection } from "./cohorts";
import { AbschnittKopf, Basis, KennzahlCard, Veraenderung } from "./primitives";

export type AdminGrowth = ApiAntwort<"/admin/stats/growth">;
export type AdminKohorten = ApiAntwort<"/admin/stats/cohorts">;
type AdminSackgasse = ApiAntwort<"/admin/stats/dead-ends">[number];
export type AdminEreignisse = ApiAntwort<"/admin/stats/events">;
export type AdminSeitenaufrufe = ApiAntwort<"/admin/stats/page-views">;
export type AdminAnmeldungen = ApiAntwort<"/admin/stats/signups">;
type JobLauf = {
  started_at: string; finished_at: string | null; status: string;
  duration_s: number | null; stats: Record<string, number | string> | null;
  error: string | null;
};
export type AdminJob = Omit<ApiAntwort<"/admin/jobs">[number], "last"> & { last: JobLauf | null };

const GROWTH_RANGES: [string, string][] = [["30d", "30 Tage"], ["90d", "90 Tage"], ["12m", "12 Monate"], ["all", "Maximal"]];

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
export function ClientCard({ clients, both, signup }: {
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
          <span className="text-sm text-muted-foreground">30 Tage · Konten</span>
        </div>
        <ClientBalken werte={nutzung.map((c) => ({ client: c.client, n: c.users }))}
          leer="Noch nichts gemessen." />
        {/* Ohne diese Zeile liest sich der Balken so, als benutzte jede:r genau
            eins. Jedes Konto steht dort unter seinem meistgenutzten Client —
            wie viele überhaupt wechseln, sagt erst die Zahl hier. */}
        {both > 0 && (
          <p className="mt-2.5 text-sm text-muted-foreground">
            Jedes Konto zählt einmal, unter dem Weg, den es am häufigsten
            nimmt. {both === 1 ? "Ein Konto nutzt" : `${both} Konten nutzen`} beides.
          </p>
        )}
      </Card>
      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <StatKicker>Womit registriert</StatKicker>
          <span className="text-sm text-muted-foreground">gesamter Bestand</span>
        </div>
        <ClientBalken werte={wege} leer="Noch kein Konto seit Einführung der Messung." />
        {ungemessen > 0 && (
          <p className="mt-2.5 text-sm text-muted-foreground">
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
  if (!gesamt) return <p className="mt-3 text-sm text-muted-foreground">{leer}</p>;
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
            <span className="inline-flex items-center gap-2 text-sm text-foreground">
              <span className={cn("h-2 w-2 shrink-0 rounded-full", clientFarbe(w.client))} />
              {clientLabel(w.client)}
            </span>
            <span className="text-sm text-muted-foreground">
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

function GrowthCard({ kicker, total, delta, series, days }: { kicker: string; total: number; delta: number; series: number[]; days: string[] }) {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <StatKicker>{kicker}</StatKicker>
          <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">{total.toLocaleString("de-DE")}</p>
        </div>
        <span className="text-sm text-muted-foreground">+{delta} im Zeitraum</span>
      </div>
      <AdminVerlauf values={series} days={days} label={kicker} mode="line" height={160} />
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
          <span key={t.label} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
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
        <ErrorState title="Die Seitenaufrufe konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  if (data.total === 0) {
    return (
      <div className="@container space-y-3 pt-2">
        <AbschnittKopf titel="Seitenaufrufe" rechts="anonym · ohne Kennung" />
        <Card className="flex flex-wrap items-center gap-4 p-4">
          <Mascot pose="search" className="h-14 w-14 shrink-0" />
          <p className="text-sm text-muted-foreground">
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
    <div className="@container space-y-3 pt-2">
      <AbschnittKopf titel="Seitenaufrufe" rechts={`${data.days} Tage · anonym, ohne Kennung`}>
        Ein „Besuch" ist der erste Aufruf in einem Browser-Tab. Wiedererkennung gibt es nicht — deshalb steht hier nirgends eine Zahl von Besucher*innen.
      </AbschnittKopf>

      <div className="grid grid-cols-1 items-start gap-3 @3xl:grid-cols-[1.5fr_1fr]">
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
          <AdminVerlauf values={data.series.map((d) => d.n)} days={data.series.map((d) => d.day)} label="Aufrufe" extras={[{ label: "Besuche", values: data.series.map((d) => d.sessions) }]} />
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
          <span className="font-mono text-xs text-muted-foreground">Aufrufe · Anteil</span>
        </div>
        <div className="mt-3.5 flex flex-col gap-2">
          {data.pages.map((seite) => (
            <div key={seite.route} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 @3xl:grid-cols-[13rem_minmax(0,1fr)_7rem]">
              <div className="min-w-0">
                <p className="text-sm text-foreground">{seitenName(seite.route)}</p>
                <p className="truncate font-mono text-xs text-muted-foreground">{seite.route}</p>
              </div>
              <div className="hidden h-2.5 overflow-hidden rounded-full bg-muted @3xl:block" aria-hidden>
                <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(2, Math.round((seite.n / spitze) * 100))}%` }} />
              </div>
              <span className="whitespace-nowrap text-right text-sm tabular-nums">
                <span className="font-semibold text-foreground">{seite.n.toLocaleString("de-DE")}</span>
                <span className="font-mono text-xs text-muted-foreground"> · {Math.round((seite.n / data.total) * 100)} %</span>
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm leading-snug text-muted-foreground">
          Detailseiten tragen ihre Kennung in der Query, und die wird nicht gemeldet —
          „Beschluss-Seite" heißt also „irgendein Beschluss", nie welcher.
        </p>
      </Card>
    </div>
  );
}

/** Warum eine Registrierung abgewiesen wurde — nur für die Anzeige.
 *  Die Werte selbst bleiben englisch (kern.store.SIGNUP_REJECTION_REASONS). */
const ABWEISUNG_LABEL: Record<string, string> = {
  rate_limit: "Bremse",
  disposable_email: "Wegwerf-Adresse",
  duplicate_email: "Adresse schon vergeben",
};

/** Neue Konten — und wer es versucht hat, ohne durchzukommen.
 *
 *  Warum beides in einem Bild: Die FYI-Mail an die Admins geht erst raus, wenn
 *  jemand seine Adresse BESTÄTIGT hat. Ein Skript, das Konten anlegt und nie
 *  einen Link klickt, löst keine einzige Mail aus — und wer an der Bremse oder
 *  am Wegwerf-Riegel abprallt, hinterließ bis 09/2026 gar keine Spur. „Es hat
 *  niemand versucht" war damit von „es haben 500 versucht" nicht zu
 *  unterscheiden.
 *
 *  Die Abweisungen tragen weder Adresse noch Domain noch Netzadresse — nur
 *  Tag, Grund und Anzahl. Wer einen Einzelfall braucht, findet die Domain im
 *  Server-Log.
 */
function AnmeldungenSection() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "signups"],
    queryFn: () => api.get<AdminAnmeldungen>("/admin/stats/signups?days=30"),
  });

  if (isPending) return <div className="pt-2"><ChartSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Registrierungen konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  const unbestaetigt = data.created - data.verified;
  const abgewiesen = data.reasons.filter((r) => r.n > 0);

  return (
    <div className="@container space-y-3 pt-2">
      <AbschnittKopf titel="Registrierungen" rechts={`${data.days} Tage`}>
        Abgewiesene Versuche tragen nur Tag, Grund und Anzahl — keine Adresse, keine Domain, keine Netzadresse. Der tägliche Herzschlag meldet sich per E-Mail, sobald hier ungewöhnlich viel zusammenkommt.
      </AbschnittKopf>

      <div className="grid grid-cols-1 items-start gap-3 @3xl:grid-cols-[1.5fr_1fr]">
        <Card className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <StatKicker>Neue Konten</StatKicker>
              <p className="mt-1.5 font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">
                {data.created.toLocaleString("de-DE")}
              </p>
            </div>
            <div className="text-right">
              <StatKicker>Adresse bestätigt</StatKicker>
              <p className="mt-1.5 font-display text-[22px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">
                {data.verified.toLocaleString("de-DE")}
                {unbestaetigt > 0 && (
                  <span className="ml-1.5 font-mono text-xs font-normal text-muted-foreground">
                    · {unbestaetigt.toLocaleString("de-DE")} offen
                  </span>
                )}
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">Anmeldetag der Konten. Die Bestätigung zeigt den heutigen Stand, nicht den Stand am Anmeldetag.</p>
          <AdminVerlauf values={data.series.map((d) => d.created)} days={data.series.map((d) => d.day)} label="neue Konten" extras={[{ label: "davon bestätigt", values: data.series.map((d) => d.verified) }, { label: "Versuche abgewiesen", values: data.series.map((d) => d.rejected) }]} />
        </Card>

        <Card className="flex flex-col gap-4 p-4">
          <div>
            <StatKicker>Abgewiesen</StatKicker>
            <p className="mt-1.5 font-display text-[22px] font-extrabold leading-none tracking-tight tabular-nums text-foreground">
              {data.rejected.toLocaleString("de-DE")}
            </p>
          </div>
          {abgewiesen.length > 0 ? (
            <>
              <div>
                <StatKicker>Woran</StatKicker>
                <div className="mt-2.5">
                  <AnteilBalken teile={abgewiesen.map((r, i) => ({
                    label: ABWEISUNG_LABEL[r.reason] ?? r.reason,
                    n: r.n,
                    ton: i === 0 ? "bg-signal/70" : i === 1 ? "bg-primary" : "bg-primary/30",
                  }))} />
                </div>
              </div>
              <p className="mt-auto text-sm leading-snug text-muted-foreground">
                „Adresse schon vergeben“ ist meist harmlos — wer sein Konto vergessen hat,
                landet dort genauso. Nur die beiden anderen lösen eine Mail aus.
              </p>
            </>
          ) : (
            <p className="text-sm leading-snug text-muted-foreground">
              Niemand ist an der Bremse oder am Wegwerf-Riegel hängengeblieben. Gezählt
              wird ab dem Deploy dieser Version; frühere Versuche lassen sich nicht
              nachtragen.
            </p>
          )}
        </Card>
      </div>
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
function EreignisSection({ qualityOnly = false }: { qualityOnly?: boolean }) {
  const [sort, setSort] = useState("users");
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "events"],
    queryFn: () => api.get<AdminEreignisse>("/admin/stats/events?days=30"),
  });

  if (isPending) return <div className="pt-2"><ChartSkeleton /></div>;
  if (isError || !data) {
    return (
      <div className="pt-2">
        <ErrorState title="Die Ereignisse konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  const zugriffe = data.events.find((e) => e.key === "session");
  const fragen = data.events.find((e) => e.key === "ai_question");
  const zeilen = data.events.filter((e) => e.key !== "session").sort((a, b) => sort === "users" ? b.users - a.users || b.n - a.n : b.n - a.n);
  const spitze = Math.max(1, ...zeilen.map((e) => sort === "users" ? e.users : e.n));
  const chipN = data.events.find((e) => e.key === "ai_question_chip")?.n ?? 0;
  const leerN = data.events.find((e) => e.key === "ai_answer_empty")?.n ?? 0;

  return (
    <div className="@container space-y-3 pt-2">
      <AbschnittKopf titel={qualityOnly ? "Fragen und Quellen" : "Welche Funktionen werden genutzt?"}
        rechts={zugriffe ? `${zugriffe.n.toLocaleString("de-DE")} Zugriffe · ${zugriffe.users} Konten · ${data.days} Tage` : `${data.days} Tage`}>
        Jede Zeile mit Konten-Zahl und Veränderung gegen die {data.days} Tage davor.
      </AbschnittKopf>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card className="p-3.5">
          <StatKicker>Fragen aus einem Vorschlag</StatKicker>
          <div className="mt-1.5 flex items-end justify-between gap-2">
            <p className={cn("font-display text-[28px] font-extrabold leading-none tracking-tight tabular-nums", data.chip_share == null ? "text-muted-foreground" : "text-foreground")}>
              {data.chip_share == null ? "–" : `${Math.round(data.chip_share * 100)} %`}
            </p>
            <Veraenderung jetzt={data.chip_share} vorher={data.previous_chip_share} prozent />
          </div>
          <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="text-sm text-muted-foreground">{data.chip_share == null ? "noch keine Fragen im Zeitraum" : "der Rest wurde ins Feld getippt"}</span>
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
            <span className="text-sm text-muted-foreground">{data.empty_share == null ? "noch keine Fragen im Zeitraum" : "jede davon ist eine Sackgasse"}</span>
            {fragen && data.empty_share != null && <Basis n={leerN} von={fragen.n} was="Antworten" />}
          </div>
        </Card>
      </div>

      {!qualityOnly && <Card className="p-4">
        <label className="mb-4 flex flex-wrap items-center gap-2 text-sm">Sortieren nach<select value={sort} onChange={(e) => setSort(e.target.value)} className="min-h-11 min-w-0 max-w-full rounded-lg border border-border bg-card px-3"><option value="users">Anzahl der Konten</option><option value="n">Anzahl der Aktionen</option></select></label>
        <div className="flex flex-col gap-2">
          {zeilen.map((e) => (
            <div key={e.key} className="grid grid-cols-1 items-center gap-x-3 gap-y-1 border-b border-border py-2 last:border-0 @3xl:grid-cols-[13rem_minmax(0,1fr)_12rem]">
              <span className={cn("text-sm", e.n === 0 ? "text-muted-foreground" : "text-foreground")}>{e.label}</span>
              <div className="hidden h-2.5 overflow-hidden rounded-full bg-muted @3xl:block" aria-hidden>
                <div className={cn("h-full rounded-full", e.n === 0 ? "bg-transparent" : "bg-primary")} style={{ width: `${Math.min(100, Math.round(((sort === "users" ? e.users : e.n) / spitze) * 100))}%` }} />
              </div>
              <span className="flex flex-wrap items-baseline justify-start gap-2 tabular-nums @3xl:justify-end">
                <Veraenderung jetzt={e.n} vorher={e.previous} klein />
                <span className="text-sm">
                  <span className={cn("font-semibold", e.n === 0 ? "text-muted-foreground" : "text-foreground")}>{e.n.toLocaleString("de-DE")}</span>
                  <span className="font-mono text-xs text-muted-foreground"> · {e.users} {e.users === 1 ? "Konto" : "Konten"}</span>
                </span>
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm leading-snug text-muted-foreground">
          Die zweite Zahl ist die der Konten. Eine große Zahl aus einem einzigen Konto
          ist etwas anderes als dieselbe Zahl aus zwanzig.
        </p>
      </Card>}
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
        <ErrorState title="Die Liste konnte nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  return (
    <div className="@container space-y-3 pt-2">
      <AbschnittKopf titel="Fragen ohne Antwort"
        rechts={`${data.length} ${data.length === 1 ? "Frage" : "Fragen"} · 30 Tage · gespeicherte Gespräche`}>
        Woran es scheitert — ohne Konto und ohne Gesprächs-id, denn eine Liste mit Kennung neben der Frage wäre ein Leseprotokoll.
      </AbschnittKopf>

      {data.length === 0 ? (
        <Card className="flex flex-wrap items-center gap-4 p-4">
          <Mascot pose="wave" className="h-14 w-14 shrink-0" />
          <p className="text-sm text-muted-foreground">
            Keine in den letzten 30 Tagen. Entweder fand alles etwas — oder es gab keine gespeicherten Gespräche im Zeitraum.
          </p>
        </Card>
      ) : (
        <Card className="divide-y divide-border p-0">
          {data.map((s, i) => (
            <div key={`${s.created}-${i}`} className="grid gap-x-4 gap-y-1 p-4 sm:grid-cols-[5.5rem_minmax(0,1fr)]">
              <span className="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground sm:pt-1">
                {formatDate(s.created.slice(0, 10))}
              </span>
              <div className="min-w-0">
                <p className="text-[14px] font-semibold leading-snug text-foreground">{s.question}</p>
                <p className="mt-1 text-sm italic leading-snug text-muted-foreground">{s.answer}</p>
              </div>
            </div>
          ))}
        </Card>
      )}
      <p className="text-sm leading-snug text-muted-foreground">
        Die vollständige Zahl steht oben unter „Antworten ohne Quelle" — diese Liste zeigt nur die Fälle, die ohnehin gespeichert sind.
      </p>
    </div>
  );
}

export function StatsTab({ view }: { view: string }) {
  if (view === "konten") return <div className="space-y-8"><KohortenSection /><AnmeldungenSection /></div>;
  if (view === "reichweite") return <SeitenaufrufeSection />;
  if (view === "antworten") return <div className="space-y-6"><QualityMetrics /><EreignisSection qualityOnly /><SackgassenSection /></div>;
  return <ActivityTab />;
}

function QualityMetrics() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "cohorts"], queryFn: () => api.get<AdminKohorten>("/admin/stats/cohorts?weeks=8"),
  });
  if (isPending) return <ChartSkeleton />;
  if (isError || !data) return <ErrorState title="Der Vergleich konnte nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;
  return <div className="space-y-3">
    <AbschnittKopf titel="Finden Fragen eine belegte Antwort?">Die Ereigniszählung umfasst alle erfassten Fragen. Die 90-Tage-Quote darunter bezieht sich nur auf gespeicherte Gespräche.</AbschnittKopf>
    <KennzahlCard label="Ohne Quelle · gespeicherte Gespräche" hint="90 Tage; Vergleich mit den 90 Tagen davor" wert={data.kennzahlen.sackgassen_quote} vorher={data.previous.sackgassen_quote} basis={data.basis.sackgassen} anteil invers />
  </div>;
}

function ActivityTab() {
  const [range, setRange] = useState("90d");
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "growth", range],
    queryFn: () => api.get<AdminGrowth>(`/admin/stats/growth?range=${range}`),
    placeholderData: (previous) => previous,
  });
  if (isPending) return <ChartSkeleton />;
  if (isError || !data) return <ErrorState title="Die Nutzungsdaten konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;
  return <div className="space-y-6">
    <AbschnittKopf titel="Wie regelmäßig wird Ratslotse genutzt?">Aktive Konten, genutzte Funktionen und die Entwicklung des Bestands.</AbschnittKopf>
    <WeeklyActivity data={data} />
    <EreignisSection />
    <ClientCard clients={data.clients} both={data.clients_both} signup={data.signup_clients} />
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-lg font-bold">Wie wächst der Bestand?</h3>
        <div role="group" aria-label="Zeitraum für den Bestand" className="inline-flex flex-wrap gap-1 rounded-xl bg-muted p-1">
          {GROWTH_RANGES.map(([v, label]) => <button key={v} aria-pressed={range === v} onClick={() => setRange(v)} className={cn("min-h-11 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", range === v ? "bg-card font-semibold text-primary shadow-sm" : "text-muted-foreground hover:text-foreground")}>{label}</button>)}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">Kumulierter Bestand einschließlich Betreiber-/Testkonten. Der Zeitraum gilt für diese beiden Verläufe. „Maximal“ zeigt bis zu 366 Tage.{isFetching && " Wird aktualisiert…"}</p>
      <div className={cn("@container", isFetching && "liste-laedt")} aria-busy={isFetching}>
        <div className="grid gap-4 @3xl:grid-cols-2">
          <GrowthCard kicker="Registrierte Konten" total={data.users.total} delta={data.users.delta} series={data.users.series} days={data.users.days} />
          <GrowthCard kicker="Angelegte Themen" total={data.topics.total} delta={data.topics.delta} series={data.topics.series} days={data.topics.days} />
        </div>
      </div>
    </section>
  </div>;
}

export function WeeklyActivity({ data }: { data: AdminGrowth }) {
  return <Card className="p-5">
    <AbschnittKopf titel="Aktive Konten" rechts="8 Wochen">
      Jedes Konto zählt je Siebentageszeitraum einmal, auch bei mehreren Besuchen. Betreiber-/Testkonten sind enthalten.
    </AbschnittKopf>
    <AdminVerlauf values={data.wau} days={data.wau_days} label="aktive Konten" weekly />
  </Card>;
}

export function OperationsTab() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "growth", "90d"], queryFn: () => api.get<AdminGrowth>("/admin/stats/growth?range=90d"),
  });
  const c = data?.council;
  return <div className="space-y-6">
    <AbschnittKopf titel="Kommen die Daten an?">Import, Hintergrundaufgaben und der letzte bekannte Stand.</AbschnittKopf>
    {isPending ? <ChartSkeleton /> : isError || !c ? <ErrorState title="Der Importstatus konnte nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} /> : <Card className="p-5">
      <h3 className="font-display text-lg font-bold">Ratsinfo-Import</h3>
      <dl className="mt-4 grid gap-4 sm:grid-cols-3">
        {([["Sitzungen", c.sessions], ["Tagesordnungspunkte", c.agenda_items], ["Beschlüsse mit KI-Feldern", c.decisions_with_ki]] as const).map(([label, value]) => <div key={label}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="mt-1 font-display text-2xl font-bold tabular-nums">{value.toLocaleString("de-DE")}</dd></div>)}
      </dl>
      <div className="mt-5 flex items-start gap-2 border-t border-border pt-4 text-sm">
        <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", fetchTone(c.hours_since_fetch))} />
        <div><p>{c.last_fetch ? `Letzter Scraper-Lauf: ${formatDate(c.last_fetch.slice(0, 10))}` : "Noch kein Lauf"}{c.hours_since_fetch != null && ` · vor ${fetchAge(c.hours_since_fetch)}`}</p>
          <p className="mt-1 text-muted-foreground">{c.last_session_import ? `Neueste Tagesordnung: ${formatDate(c.last_session_import.slice(0, 10))}` : "Noch keine Tagesordnung"}{c.next_session && ` · nächste Sitzung ${formatDate(c.next_session)}`}</p>
        </div>
      </div>
    </Card>}
    <JobsSection />
  </div>;
}

const JOB_STATE: Record<AdminJob["state"], { dot: string; label: string }> = {
  ok: { dot: "bg-green-500", label: "läuft" },
  stale: { dot: "bg-amber-500", label: "überfällig" },
  error: { dot: "bg-red-500", label: "fehlgeschlagen" },
  unknown: { dot: "bg-muted-foreground/40", label: "noch kein Lauf erfasst" },
};

/** Cron-Übersicht: was läuft wann, wie lange, und was kam dabei heraus. */
export function JobsSection() {
  const [filter, setFilter] = useState("all");
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
        <ErrorState title="Die Cron-Übersicht konnte nicht geladen werden"
          onRetry={() => void refetch()} busy={isFetching} />
      </div>
    );
  }

  const auffaellig = data.filter((j) => j.state === "error" || j.state === "stale");
  const ohneLauf = data.filter((j) => j.state === "unknown");
  const order = { error: 0, stale: 1, unknown: 2, ok: 3 };
  const sichtbar = [...(filter === "issues" ? auffaellig : filter === "unknown" ? ohneLauf : data)].sort((a, b) => order[a.state] - order[b.state]);
  return (
    <div className="@container space-y-3 pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg font-bold text-foreground">Cron-Jobs</h3>
        <span className="text-sm text-muted-foreground">Erfassung ab dem jeweils nächsten Lauf</span>
      </div>
      <div role="group" aria-label="Cron-Jobs filtern" className="flex flex-wrap gap-2">
        {([["all", `Alle (${data.length})`], ["issues", `Auffällig (${auffaellig.length})`], ["unknown", `Ohne Lauf (${ohneLauf.length})`]] as const).map(([value, label]) => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)} className={cn("min-h-11 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", filter === value ? "bg-primary/10 font-semibold text-primary" : "bg-muted text-muted-foreground hover:text-foreground")}>{label}</button>)}
      </div>
      {sichtbar.length === 0 && <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">{filter === "issues" ? "Keine fehlgeschlagenen oder überfälligen Jobs." : "Keine Jobs in dieser Auswahl."}</p>}
      <div className="grid grid-cols-1 items-start gap-3 @3xl:grid-cols-2">
        {sichtbar.map((job) => {
          const tone = JOB_STATE[job.state];
          const stats = job.last?.stats ?? null;
          return (
            <Card key={job.key} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn("h-2 w-2 shrink-0 rounded-full", tone.dot)} />
                    <p className="text-sm font-semibold text-foreground">{job.label}</p>
                  </div>
                  <p className="mt-1 pl-4 text-sm text-muted-foreground">{tone.label} · {job.schedule}</p>
                </div>
                <span className="shrink-0 whitespace-nowrap text-sm text-muted-foreground">
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
                    <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-sm text-muted-foreground">
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
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-muted-foreground">
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
            <span className="min-w-0 flex-1 truncate text-sm text-foreground">{s.name}</span>
            <span aria-hidden className="hidden h-1 w-16 shrink-0 overflow-hidden rounded-full bg-border sm:block">
              <span className="block h-full rounded-full bg-primary/45"
                style={{ width: `${Math.round(((s.duration_s ?? 0) / laengster) * 100)}%` }} />
            </span>
            {/* Feste Breite, rechtsbündig: Ohne sie schiebt die unterschiedlich
                breite Zeitangabe („8 s" vs. „31 min") den Balken davor hin und
                her — und eine Balkenspalte, die nicht fluchtet, taugt nicht
                zum Vergleichen, wozu sie allein da ist. */}
            <span className="w-12 shrink-0 text-right tabular-nums text-xs text-muted-foreground">
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

