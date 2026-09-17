"use client";

import { useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, CircleAlert, Mail } from "lucide-react";
import { api } from "@/lib/api";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { mailAnlaesse, mailVerlauf } from "@/lib/admin-mail";
import { Button, Card, ChartSkeleton, ErrorState, Select, Spinner, formatDateTime } from "@/components/ui";
import { AdminVerlauf } from "@/components/grafik/admin-verlauf";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";
import { AbschnittKopf } from "./primitives";

const LABEL: Record<string, string> = {
  n1_tagesordnung: "Tagesordnung", n1_aenderung: "Änderung an der Tagesordnung",
  n2_thema: "Treffer zu einem Thema", n3_result: "Ergebnis einer Abstimmung",
  n4_vorgang: "Neue Station einer Vorlage", n5_vorabend: "Erinnerung am Vorabend",
  n6_woche: "Wochenvorschau", n7_news: "Neu bei Ratslotse", bundel: "Sammelmeldung",
  verify_email: "E-Mail bestätigen", password_reset: "Passwort zurücksetzen",
  email_change: "Neue Adresse bestätigen", email_change_info: "Hinweis zum Adresswechsel",
  setup_reminder: "Erinnerung an die Einrichtung", feedback_reply: "Antwort auf eine Rückmeldung",
  account_activated: "Konto freigeschaltet", account_deleted: "Konto gelöscht",
  probe: "Testmail", admin_fyi: "FYI an die Admins", alarm: "Betriebsalarm", andere: "Sonstige",
};
const anlassLabel = (key: string) => LABEL[key] ?? key;
const kanal = (channel: string) => channel === "both" ? "Push + E-Mail" : channel === "push" ? "Push" : channel === "off" ? "Aus" : "E-Mail";
const MAIL_PAGE_SIZE = 20;

function MailMetric({ label, value, note, alert = false, decimals = 0 }: { label: string; value: number; note: string; alert?: boolean; decimals?: number }) {
  return <div className="min-w-0 rounded-xl border border-border bg-card p-4">
    <p className="text-sm font-medium text-muted-foreground">{label}</p>
    <p className={cn("mt-2 font-display text-3xl font-bold tabular-nums", alert && value > 0 && "text-amber-800 dark:text-amber-300")}>{deZahl(value, decimals)}</p>
    <p className="mt-2 text-sm text-muted-foreground">{note}</p>
  </div>;
}

export function MailDashboard() {
  const [tage, setTage] = useState(30);
  const [sort, setSort] = useState<"mails" | "gescheitert" | "rueckkehr">("mails");
  const [nurViele, setNurViele] = useState(false);
  const query = useQuery({ queryKey: ["admin", "emails", tage], queryFn: () => vertrag.get(`/admin/stats/emails?tage=${tage}`) });
  const data = query.data;
  const rows = data ? mailAnlaesse(data).sort((a, b) => b[sort] - a[sort] || a.anlass.localeCompare(b.anlass)) : [];
  const max = Math.max(1, ...rows.map((r) => r.mails));
  const verlauf = data ? mailVerlauf(data.je_tag, data.tage) : null;
  const personen = data?.vielempfaenger.filter((u) => !nurViele || u.je_woche >= 7) ?? [];

  return <div className="space-y-6 [overflow-wrap:anywhere]">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="font-mono text-xs text-muted-foreground">KOMMUNIKATION</p><h2 className="mt-1 font-display text-2xl font-bold">Was wird verschickt?</h2>
        <p className="mt-2 max-w-[65ch] text-sm text-muted-foreground">Versandmenge, Anlässe und Nutzung über Mail-Links. Ein Konto öffnen, um die einzelnen Mails nachzusehen.</p></div>
      <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-muted-foreground">Zeitraum
        <Select aria-label="Mail-Zeitraum" value={tage} onChange={(e) => setTage(Number(e.target.value))} className="w-auto max-w-full">
          <option value={7}>Letzte 7 Tage</option><option value={30}>Letzte 30 Tage</option><option value={90}>Letzte 90 Tage</option>
        </Select>
      </label>
    </div>
    {query.isError ? <ErrorState title="Die Mailstatistik konnte nicht geladen werden" onRetry={() => void query.refetch()} busy={query.isFetching} /> : !data ? <ChartSkeleton /> : <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MailMetric label="Verschickt" value={data.verschickt} note={`Erfasste erfolgreiche Versandversuche in ${data.tage} Tagen.`} />
        <MailMetric label="Fehlgeschlagen" value={data.gescheitert} note="Versandversuche mit Fehler. Nach Anlass unten aufschlüsseln." alert />
        <MailMetric label="Aufrufe über Mail-Links" value={data.rueckkehr} note="Anonyme Aufrufe, auch mehrmals durch dieselbe Person möglich." />
      </div>
      <Card className="min-w-0 p-4 sm:p-5">
        <AbschnittKopf titel="Versand im Verlauf" rechts={`${data.tage} Tage`}>Wann häufen sich Mails? Jeden Tag antippen oder mit der Tastatur ablesen.</AbschnittKopf>
        {verlauf && <AdminVerlauf {...verlauf} label="verschickte Mails" />}
        <p className="mt-2 text-xs text-muted-foreground">Kalendertage in UTC; erster und heutiger Tag sind unvollständig. Null heißt: kein erfolgreicher Versand erfasst.</p>
      </Card>
      <Card className="min-w-0 overflow-hidden p-0">
        <div className="flex flex-wrap items-end justify-between gap-3 p-4 sm:p-5">
          <AbschnittKopf titel="Welche Mails führen zu Aufrufen?">Versand und Link-Aufrufe nebeneinander, nach Anlass aufgeschlüsselt.</AbschnittKopf>
          <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm text-muted-foreground">Sortieren nach
            <Select aria-label="Mail-Anlässe sortieren" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} className="w-auto max-w-full">
              <option value="mails">Verschickt</option><option value="gescheitert">Fehlgeschlagen</option><option value="rueckkehr">Link-Aufrufe</option>
            </Select>
          </label>
        </div>
        {rows.length ? <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Mail-Anlässe, horizontal scrollbar">
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="sr-only">Versand und Link-Aufrufe nach Anlass</caption>
            <thead className="bg-muted/50 text-xs text-muted-foreground"><tr>
              <th scope="col" className="px-4 py-3 font-medium">Anlass</th><th scope="col" className="px-3 py-3 text-right font-medium">Verschickt</th>
              <th scope="col" className="px-3 py-3 text-right font-medium">Fehlgeschlagen</th><th scope="col" className="px-3 py-3 text-right font-medium">Konten¹</th>
              <th scope="col" className="px-3 py-3 text-right font-medium">Link-Aufrufe</th><th scope="col" className="px-4 py-3 text-right font-medium">Aufrufe je 100 Mails²</th>
            </tr></thead>
            <tbody>{rows.map((r) => <tr key={r.anlass} className="border-t border-border">
              <th scope="row" className="min-w-48 px-4 py-3 font-medium"><span>{anlassLabel(r.anlass)}</span><div className="mt-2 h-1 w-full rounded-full bg-muted" aria-hidden><div className="h-full rounded-full bg-primary/50" style={{ width: `${r.mails / max * 100}%` }} /></div></th>
              <td className="px-3 py-3 text-right font-semibold">{deZahl(r.mails)}</td>
              <td className={cn("px-3 py-3 text-right", r.gescheitert > 0 ? "font-semibold text-amber-800 dark:text-amber-300" : "text-muted-foreground")}>{deZahl(r.gescheitert)}</td>
              <td className="px-3 py-3 text-right text-muted-foreground">{deZahl(r.konten)}</td>
              <td className="px-3 py-3 text-right">{deZahl(r.rueckkehr)}</td><td className="px-4 py-3 text-right text-muted-foreground">{r.mails ? deZahl(Math.round(r.rueckkehr / r.mails * 100)) : "–"}</td>
            </tr>)}</tbody>
            <tfoot className="border-t border-border bg-muted/40 font-semibold"><tr>
              <th scope="row" className="px-4 py-3">Alle Anlässe</th>
              <td className="px-3 py-3 text-right">{deZahl(data.verschickt)}</td>
              <td className="px-3 py-3 text-right">{deZahl(data.gescheitert)}</td>
              <td className="px-3 py-3 text-right" title="Konten können bei mehreren Anlässen vorkommen; eine eindeutige Gesamtzahl wird nicht erfasst.">–</td>
              <td className="px-3 py-3 text-right">{deZahl(data.rueckkehr)}</td>
              <td className="px-4 py-3 text-right">{data.verschickt ? deZahl(Math.round(data.rueckkehr / data.verschickt * 100)) : "–"}</td>
            </tr></tfoot>
          </table>
        </div> : <p className="px-5 pb-5 text-sm text-muted-foreground">Im Zeitraum sind noch keine Versandversuche oder Link-Aufrufe erfasst.</p>}
        <div className="space-y-2 border-t border-border bg-muted/20 p-4 text-xs leading-relaxed text-muted-foreground sm:px-5">
          <p>¹ Konten mit mindestens einem Versandversuch dieses Anlasses, einschließlich fehlgeschlagener Versuche. Mails ohne Konto zählen nur in der Versandmenge. Konten können bei mehreren Anlässen vorkommen und werden deshalb nicht addiert.</p>
          <p>² Keine Öffnungs- oder Klickquote: Gezählt werden Seitenaufrufe, keine eindeutigen Personen. Aufrufe können von älteren oder weitergeleiteten Mails stammen; deshalb sind auch mehr als 100 möglich. Link-Aufrufe werden nach Kalendertagen erfasst.</p>
        </div>
      </Card>
      <Card className="min-w-0 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <AbschnittKopf titel="Wer bekommt besonders viele Mails?">Die bis zu 20 Konten mit den meisten verschickten Mails im Zeitraum. Ein Klick öffnet die Mailhistorie.</AbschnittKopf>
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={nurViele} onChange={(e) => setNurViele(e.target.checked)} className="h-4 w-4 accent-primary" />Ab 7 Mails pro Woche</label>
        </div>
        <div className="mt-4 divide-y divide-border">
          {personen.map((u) => <a key={u.owner_id} href={`#users?user=${u.owner_id}&detail=emails`} className="group flex min-w-0 flex-wrap items-center gap-3 py-4 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            <span className="min-w-0 flex-1 basis-44"><span className="block text-sm font-semibold">{u.display_name || u.email}</span>{u.display_name && <span className="block text-xs text-muted-foreground">{u.email}</span>}
              <span className="mt-1 block text-xs text-muted-foreground">Häufigster Anlass: {u.haeufigster_anlass ? anlassLabel(u.haeufigster_anlass) : "–"} · Kanal: {kanal(u.delivery_channel)}</span>
              <span className="mt-1 block text-xs text-muted-foreground">Letzte Mail: {u.letzte ? `${formatDateTime(u.letzte)} UTC` : "–"}</span></span>
            <span className="text-right"><strong className="block font-mono text-lg tabular-nums">{deZahl(u.je_woche, 1)} <span className="text-xs font-normal text-muted-foreground">/ Woche</span></strong><span className="text-xs text-muted-foreground">{deZahl(u.mails)} im Zeitraum</span></span>
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          </a>)}
          {!personen.length && <p className="py-5 text-sm text-muted-foreground">{nurViele ? "Keines dieser Konten erreicht 7 Mails pro Woche." : "Noch keine Mails an bestehende Konten im Zeitraum erfasst."}</p>}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">Durchschnitt über den gesamten Zeitraum, auch bei jüngeren Konten. 7 pro Woche ist eine Orientierung für die Sichtung, kein Versandlimit. Der Kanal zeigt die heutige Einstellung.</p>
      </Card>
      <p className="text-xs leading-relaxed text-muted-foreground">Das Protokoll beginnt mit Einführung der Erfassung; ältere Mails fehlen. „Verschickt“ bestätigt den erfolgreichen Versandversuch, nicht die Zustellung oder das Öffnen im Postfach.</p>
    </>}
  </div>;
}

export function UserMailHistory({ userId, channel }: { userId: number; channel: string }) {
  const query = useInfiniteQuery({
    queryKey: ["admin", "user", userId, "emails"],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api.get<ApiAntwort<"/admin/users/{user_id}/emails">>(`/admin/users/${userId}/emails?tage=30&limit=${MAIL_PAGE_SIZE + 1}&offset=${pageParam}`),
    getNextPageParam: (last, _pages, offset) => last.rows.length > MAIL_PAGE_SIZE ? offset + MAIL_PAGE_SIZE : undefined,
  });
  if (query.isPending) return <div className="py-8"><Spinner /></div>;
  if (!query.data) return <ErrorState title="Die Mailhistorie konnte nicht geladen werden" onRetry={() => void query.refetch()} busy={query.isFetching} />;
  const summary = query.data.pages[0].summary;
  const rows = query.data.pages.flatMap((page) => page.rows.slice(0, MAIL_PAGE_SIZE));
  return <section aria-label="Mailhistorie" className="mt-5 min-w-0 space-y-5">
    <div className="rounded-xl bg-muted/50 p-4 text-sm">
      <p className="font-medium">Benachrichtigungskanal: {kanal(channel)}</p>
      <p className="mt-1 text-muted-foreground">{channel === "push" || channel === "off" ? "Der aktuelle Kanal sieht keine Benachrichtigungen per E-Mail vor. Frühere Mails und Kontomails, etwa zur Passwortänderung, bleiben im Verlauf sichtbar." : "Der Verlauf enthält Benachrichtigungen und Kontomails, etwa zur Bestätigung der Adresse."}</p>
    </div>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <MailMetric label="Verschickt · 30 Tage" value={summary.zeitraum} note={`${deZahl(summary.gesamt)} seit Beginn der Erfassung.`} />
      <MailMetric label="Pro Woche" value={summary.je_woche} decimals={1} note="Durchschnitt der letzten 30 Tage." />
      <MailMetric label="Fehlgeschlagen · 30 Tage" value={summary.gescheitert} note="Die Versuche stehen im Verlauf." alert />
    </div>
    {Object.keys(summary.je_anlass).length > 0 && <details className="rounded-xl border border-border p-3">
      <summary className="cursor-pointer py-1 text-sm font-medium">Verschickte Mails nach Anlass · 30 Tage</summary>
      <dl className="mt-3 divide-y divide-border text-sm">{Object.entries(summary.je_anlass).map(([anlass, n]) => <div key={anlass} className="flex items-start justify-between gap-3 py-2"><dt>{anlassLabel(anlass)}</dt><dd className="font-mono tabular-nums">{deZahl(n)}</dd></div>)}</dl>
    </details>}
    <div>
      <AbschnittKopf titel="Versandverlauf" rechts={<span role="status">{rows.length} Einträge geladen</span>}>Alle erfassten Zeiträume, neueste Mails zuerst. Betreff und Versandstatus bleiben vollständig lesbar.</AbschnittKopf>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">„Am selben Tag aktiv“ zeigt protokollierte Aktivität am Versanddatum, keinen Klick auf diese Mail. „Verschickt“ ist kein Zustellnachweis. Mailinhalte werden nicht gespeichert.</p>
      <ol className="mt-4 divide-y divide-border" aria-label="Einzelne Mailversuche">
        {rows.map((mail) => <li key={mail.id} className="py-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <time dateTime={mail.sent_at}>{formatDateTime(mail.sent_at)} UTC</time>
            <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-1 font-medium", mail.ok ? "bg-muted text-foreground" : "bg-amber-500/10 text-amber-800 dark:text-amber-300")}>
              {mail.ok ? <Check className="h-3.5 w-3.5" aria-hidden /> : <CircleAlert className="h-3.5 w-3.5" aria-hidden />}{mail.ok ? "Verschickt" : "Fehlgeschlagen"}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold leading-relaxed">{mail.subject || "Ohne Betreff"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{anlassLabel(mail.anlass)} · {mail.besuch_am_tag ? "Am selben Tag aktiv" : "Keine Aktivität am selben Tag erfasst"}</p>
        </li>)}
      </ol>
      {!rows.length && <div className="flex items-start gap-3 rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground"><Mail className="h-5 w-5 shrink-0" aria-hidden /><p>Noch keine Mails für dieses Konto protokolliert. Mails vor Beginn der Erfassung sind hier nicht enthalten.</p></div>}
      {query.isFetchNextPageError && <p role="alert" className="my-3 text-sm text-destructive">Ältere Mails konnten nicht geladen werden. Bitte erneut versuchen.</p>}
      {query.hasNextPage && <Button variant="secondary" className="mt-4 w-full" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Lädt…" : query.isFetchNextPageError ? "Erneut versuchen" : "Ältere Mails laden"}</Button>}
      {!query.hasNextPage && rows.length > 0 && <p className="mt-3 text-center text-xs text-muted-foreground">Alle protokollierten Versandversuche geladen. Mails vor Beginn der Erfassung fehlen.</p>}
    </div>
  </section>;
}
