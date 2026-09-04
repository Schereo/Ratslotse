"use client";

import { Suspense } from "react";
import { notFound, useSearchParams } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import type { SessionDetail } from "@/lib/types";
import { Badge, Card, DetailSkeleton, formatDate } from "@/components/ui";
import { CommitteeName } from "@/components/committee-name";
import { VideoResultsNotice } from "@/components/video-result";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import {
  AenderungenSection, AgendaRow, AttendanceSection, CalendarButton, DateTile, DringlichkeitsBlock, LiveChip,
  ergebnisseJeTop, hasAgendaChildren, sessionUrl, topDomId, topKey, useTopSprung, useTopsAusLink, videoKey,
} from "@/components/tagesordnung";
import { sitzungHref, sessionHref } from "@/lib/routes";
import { isLiveNow } from "@/lib/live";
import { useFetch } from "@/lib/use-fetch";
import { useHeute } from "@/lib/use-heute";
import { useZurueck } from "@/lib/zurueck";
import { relativerTag, wochentagKurz } from "@/lib/utils";

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
  const naehe = relativerTag(data.session_date, heute);
  const wochentag = wochentagKurz(data.session_date);

  return (
    <div className="mx-auto max-w-4xl">
      {/* „Zurück" nur für Angemeldete: Für Gäste führt jedes Ziel entweder aus
          der Seite heraus oder an die Anmeldewand (s. lib/zurueck.ts). */}
      {zeigeZurueck && (
        <button onClick={() => zurueck(sessionHref(ksinr))}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4 shrink-0" /> Zurück zu den Sitzungen
        </button>
      )}

      <div className="mt-3 flex items-start gap-3">
        <DateTile iso={data.session_date} />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
            {naehe ? `${naehe[0].toUpperCase()}${naehe.slice(1)}` : wochentag}
            {" · "}{formatDate(data.session_date)}
            {data.session_time && ` · ${data.session_time} Uhr`}
          </p>
          <h1 className="mt-0.5 font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">
            <CommitteeName name={data.committee} />
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            {isLiveNow(data) && <LiveChip />}
            <Badge color="blue">{items.length} {items.length === 1 ? "TOP" : "TOPs"}</Badge>
            {data.location && <span className="min-w-0 truncate">{data.location}</span>}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <ShareButton path={sitzungHref(ksinr)} label="Sitzung teilen"
          title={`${data.committee} am ${formatDate(data.session_date)}`} />
        <CalendarButton session={data} agenda={items.map((it) => `${it.item_number} ${it.title}`)} />
        <BookmarkButton target={{ kind: "session", ksinr }} />
        <a href={sessionUrl(ksinr)} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
          Ratsinfo <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>

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
