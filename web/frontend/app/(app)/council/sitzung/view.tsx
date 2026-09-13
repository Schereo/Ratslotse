"use client";

import { Suspense } from "react";
import { notFound, useSearchParams } from "next/navigation";
import { ArrowLeft, CalendarDays, ExternalLink, MapPin } from "lucide-react";
import type { SessionDetail } from "@/lib/types";
import { Card, DetailSkeleton, formatDate } from "@/components/ui";
import { shortCommittee } from "@/lib/committees";
import { VideoResultsNotice } from "@/components/video-result";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import {
  AenderungenSection, AgendaRow, AttendanceSection, CalendarButton, DringlichkeitsBlock, LiveChip,
  ergebnisseJeTop, hasAgendaChildren, sessionUrl, topDomId, topKey, useTopSprung, useTopsAusLink, videoKey,
} from "@/components/tagesordnung";
import { sitzungHref, sessionHref } from "@/lib/routes";
import { isLiveNow } from "@/lib/live";
import { useFetch } from "@/lib/use-fetch";
import { useHeute } from "@/lib/use-heute";
import { useZurueck } from "@/lib/zurueck";

const KOPF_AKTION = "min-h-11 h-auto min-w-0 justify-start gap-2 whitespace-normal rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-fluss hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0";

/** Eine Sitzung für sich — die Seite hinter jedem geteilten Ausschuss-Link.
 *
 *  Warum es sie neben der Sitzungsliste gibt: Wer „guck mal, was am Donnerstag
 *  drankommt" weiterreicht, schickt den Link an Leute ohne Konto. Die Liste
 *  verlangt eines (Filter, Merkliste, eigene Themen hängen daran), diese Seite
 *  nicht — sie steht in `OEFFENTLICHE_PFADE` und holt ihre Tagesordnung vom
 *  ohnehin offenen `/council/session/{ksinr}`. Ohne Anmeldung rahmt die
 *  `PublicShell` sie ein und lädt am Fuß zum Konto ein (s. app/(app)/layout.tsx).
 *
 *  Die Tagesordnung selbst ist dieselbe wie in der Liste — Zeilen, Ergebnis-
 *  Punkte und der Sprung zum verlinkten TOP kommen aus
 *  `components/tagesordnung.tsx`, damit die beiden Orte nicht auseinanderlaufen.
 */
export default function SitzungPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <SitzungInner />
    </Suspense>
  );
}

function SitzungInner() {
  const sp = useSearchParams();
  const ksinr = Number(sp.get("ksinr") || 0);
  const tops = useTopsAusLink(sp.get("top"));
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  const heute = useHeute();
  const { data, loading } = useFetch<SessionDetail>(ksinr > 0 ? `/council/session/${ksinr}` : null);
  // Erst hervorheben, wenn die Punkte im DOM stehen können — die Mechanik
  // dahinter (und ihre drei Fallen) steckt im Hook. Die Markierung bleibt hier
  // stehen: Der geteilte Punkt ist der Grund, warum diese Seite offen ist.
  const flashTop = useTopSprung(ksinr, tops, Boolean(data), true);

  if (ksinr <= 0) notFound();
  if (loading) return <DetailSkeleton />;
  if (!data) notFound();

  const { outcomeByItem, decisionByItem, videoByItem } = ergebnisseJeTop(data);
  const videoCount = Object.keys(videoByItem).length;
  const items = data.agenda_items ?? [];
  const heuteTag = heute
    ? `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`
    : null;
  const kuenftig = heuteTag != null && data.session_date >= heuteTag;
  const kurzname = shortCommittee(data.committee);
  const datum = new Date(data.session_date + "T12:00:00").toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div className="mx-auto max-w-4xl">
      {/* „Zurück" nur für Angemeldete: Für Gäste führt jedes Ziel entweder aus
          der Seite heraus oder an die Anmeldewand (s. lib/zurueck.ts). */}
      {zeigeZurueck && (
        <button onClick={() => zurueck(sessionHref(ksinr))}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
          <ArrowLeft className="h-4 w-4 shrink-0" /> Zurück zu den Sitzungen
        </button>
      )}

      <header aria-labelledby="sitzung-titel" className="mt-3 overflow-hidden rounded-xl border border-border bg-card shadow-sm [overflow-wrap:anywhere]">
        <div className="p-4 sm:p-5">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <p className="font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground">Sitzung</p>
            <div className="flex flex-wrap items-center gap-2 text-meta text-muted-foreground">
              {isLiveNow(data) && <LiveChip />}
              <span>{items.length ? `${items.length} ${items.length === 1 ? "Tagesordnungspunkt" : "Tagesordnungspunkte"}` : "Tagesordnung folgt"}</span>
            </div>
          </div>
          <h1 id="sitzung-titel" className="font-display text-2xl font-bold leading-tight tracking-tight text-foreground [overflow-wrap:anywhere] sm:text-3xl">
            {kurzname}
          </h1>
          {kurzname !== data.committee.trim() && <p className="mt-1 text-meta text-muted-foreground [overflow-wrap:anywhere]">{data.committee}</p>}

          <dl className="mt-5 grid grid-cols-[repeat(auto-fit,minmax(min(100%,16rem),1fr))] gap-4 border-t border-border/60 pt-4 sm:gap-6">
            <div className="min-w-0">
              <dt className="mb-1 flex items-center gap-2 text-meta text-muted-foreground">
                <CalendarDays className="h-4 w-4 shrink-0" aria-hidden /> Termin
              </dt>
              <dd className="text-quelle font-medium text-foreground">
                <time dateTime={data.session_date}>{datum}</time>
                <span className="mt-0.5 block text-hinweis font-normal text-muted-foreground">
                  {data.session_time ? `${data.session_time.slice(0, 5)} Uhr` : "Uhrzeit noch nicht angegeben"}
                </span>
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="mb-1 flex items-center gap-2 text-meta text-muted-foreground">
                <MapPin className="h-4 w-4 shrink-0" aria-hidden /> Ort
              </dt>
              <dd className="text-quelle text-foreground [overflow-wrap:anywhere]">
                {data.location || <span className="text-hinweis text-muted-foreground">Ort noch nicht angegeben</span>}
              </dd>
            </div>
          </dl>
        </div>
        <div role="group" aria-label="Aktionen zur Sitzung" className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,8rem),1fr))] gap-1 border-t border-border/60 bg-muted/20 p-2 sm:flex sm:flex-wrap">
          <CalendarButton session={data} agenda={items.map((it) => `${it.item_number} ${it.title}`)} className={`${KOPF_AKTION} text-foreground`} />
          <BookmarkButton target={{ kind: "session", ksinr }} className={KOPF_AKTION} />
          <ShareButton path={sitzungHref(ksinr)} label="Sitzung teilen" still className={`${KOPF_AKTION} text-foreground`}
            title={`${data.committee} am ${formatDate(data.session_date)}`} />
          <a href={sessionUrl(ksinr)} target="_blank" rel="noreferrer"
            className={`inline-flex items-center ${KOPF_AKTION} text-muted-foreground sm:ml-auto`}>
            Ratsinfo <ExternalLink aria-hidden />
          </a>
        </div>
      </header>

      <Card className="mt-5 p-4">
        {/* Nur bei anstehenden Sitzungen: Nach der Sitzung ist die
            Änderungs-Historie Verwaltungsrauschen. */}
        {kuenftig && (data.agenda_changes?.length ?? 0) > 0 && (
          <AenderungenSection aenderungen={data.agenda_changes!} />
        )}
        {videoCount > 0 && (
          <VideoResultsNotice count={videoCount} videoId={Object.values(videoByItem)[0].video_id} />
        )}
        <DringlichkeitsBlock items={items.filter((it) => it.dringlich)} ksinr={ksinr}
          videoByItem={videoByItem} />
        {items.length === 0 ? (
          <p className="py-2 text-sm text-muted-foreground">
            Für diese Sitzung liegt noch keine Tagesordnung vor. Sobald sie im
            Ratsinformationssystem steht, erscheint sie hier.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {items.filter((it) => !it.dringlich).map((it, i) => (
              <AgendaRow key={i} it={it} query="" ksinr={ksinr}
                bookmarkable={!hasAgendaChildren(it, items)}
                outcome={it.is_public ? outcomeByItem[topKey(it.item_number)] : undefined}
                decisionId={it.is_public ? decisionByItem[topKey(it.item_number)] : undefined}
                videoResult={it.is_public ? videoByItem[videoKey(it.item_number)] : undefined}
                domId={topDomId(ksinr, it.item_number)}
                flash={flashTop === topDomId(ksinr, it.item_number)} />
            ))}
          </ul>
        )}
        <AttendanceSection detail={data} />
      </Card>
    </div>
  );
}
