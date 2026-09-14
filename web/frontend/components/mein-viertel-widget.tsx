"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, MapPinned } from "lucide-react";
import { HeuteWidget, useWidgetDetail, type WidgetSize } from "@/components/heute-widget";
import { Badge, Button, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { sessionHref, viertelHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { Topic } from "@/lib/types";
import { letzterViertelStand, naechsteViertelBeratung, STAND, type ViertelTafel } from "@/lib/viertel-einblick";
import { cn } from "@/lib/utils";

type Uebersicht = ApiAntwort<"/districts/projects">;
type Viertel = Uebersicht["districts"][number];
const linkStil = "group block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary";

export function MeinViertelWidget({ topics, heuteIso, size }: {
  topics: Topic[] | undefined; heuteIso: string; size?: WidgetSize;
}) {
  const an = useFeature("mein-viertel");
  const [alle, setAlle] = useState(false);
  const query = useQuery({
    queryKey: ["viertel-uebersicht"], queryFn: () => api.get<Uebersicht>("/districts/projects"),
    enabled: an, staleTime: 10 * 60_000,
  });
  if (!an) return null;
  const meine = (query.data?.districts ?? []).filter(o =>
    (topics ?? []).some(t => t.name.toLowerCase() === o.name.toLowerCase()),
  ).sort((a, b) => (b.last_date ?? "").localeCompare(a.last_date ?? "") || a.name.localeCompare(b.name));
  return <HeuteWidget id="mein-viertel" title="Mein Viertel" icon={MapPinned} size={size}
    meta={meine.length > 1 ? `${meine.length} Viertel` : undefined}>
    {detail => {
      const limit = detail === "compact" ? 2 : 3;
      return <>
        {query.isError && <div role="alert" className="text-hinweis text-muted-foreground">
          Die Viertel konnten nicht {query.data ? "aktualisiert" : "geladen"} werden.
          <Button variant="ghost" className="h-auto min-h-11 whitespace-normal" onClick={() => query.refetch()} disabled={query.isFetching}>Erneut versuchen</Button>
        </div>}
        {(query.isPending || topics === undefined) && <p role="status" className="text-hinweis text-muted-foreground">Deine Viertel werden geladen.</p>}
        {query.data && topics !== undefined && (meine.length ? <>
          <div className={cn(detail === "expanded" && meine.length > 1
            ? cn("grid gap-x-5 gap-y-5", meine.length === 2 ? "grid-cols-2" : "grid-cols-3") : "divide-y divide-border/60")}>
            {(alle ? meine : meine.slice(0, limit)).map(viertel => <ViertelEinblick key={viertel.place_id} viertel={viertel} heuteIso={heuteIso} />)}
          </div>
          {meine.length > limit && <Button variant="ghost" className="mt-2 h-auto min-h-11 max-w-full whitespace-normal" onClick={() => setAlle(!alle)}>
            {alle ? "Weniger Viertel" : `${meine.length - limit} ${meine.length - limit === 1 ? "weiteres Viertel" : "weitere Viertel"} anzeigen`}
          </Button>}
        </> : <div className="py-1">
          <p className="text-hinweis text-muted-foreground">Wähle dein Viertel, um Vorhaben und nächste Beratungen zu sehen.</p>
          <Link href={viertelHref()} className="mt-2 inline-flex min-h-11 items-center gap-2 text-hinweis font-medium text-primary hover:underline">
            Viertel auswählen <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>)}
      </>;
    }}
  </HeuteWidget>;
}

function ViertelEinblick({ viertel, heuteIso }: { viertel: Viertel; heuteIso: string }) {
  const detail = useWidgetDetail();
  // Derselbe Cache wie auf der Stadtkarte. Erst sichtbare Viertel laden ihre
  // Tafel; das Widget fragt zunächst höchstens drei zusätzliche Endpunkte ab.
  const query = useQuery({
    queryKey: ["viertel", viertel.place_id],
    queryFn: () => api.get<ViertelTafel>(`/districts/${encodeURIComponent(viertel.place_id)}/projects`),
    staleTime: 10 * 60_000,
  });
  const projekt = letzterViertelStand(query.data?.projects ?? []);
  const termin = naechsteViertelBeratung(query.data?.upcoming ?? [], heuteIso);
  const stand = projekt ? STAND[projekt.stage] : undefined;
  const ratsdatum = projekt?.last_date ?? projekt?.first_date;
  return <article aria-label={viertel.name} className={cn("min-w-0", detail === "expanded" ? "flex flex-col" : "py-4 first:pt-0 last:pb-0")}>
    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
      <h3 className="text-meta font-semibold uppercase tracking-[0.04em] text-primary">{viertel.name}</h3>
      <span className="text-meta text-muted-foreground">{viertel.count} Vorhaben</span>
    </div>
    {query.isPending && <p role="status" className="py-3 text-hinweis text-muted-foreground">Einblick wird geladen.</p>}
    {query.isError && <div role="alert" className="text-hinweis text-muted-foreground">
      Der Einblick konnte nicht {query.data ? "aktualisiert" : "geladen"} werden.
      <Button variant="ghost" className="h-auto min-h-11 whitespace-normal" onClick={() => query.refetch()} disabled={query.isFetching}>Erneut versuchen</Button>
    </div>}
    {query.data && <div className="flex-1">
      {termin ? <Link href={sessionHref(termin.ksinr, termin.item_number ? [termin.item_number] : undefined)} className={linkStil}>
        <span className="mb-1.5 flex items-center gap-1.5 text-meta font-medium text-primary">
          <CalendarDays className="h-3.5 w-3.5" aria-hidden /> Am {formatDate(termin.session_date)} im Rat
        </span>
        <p className="text-quelle font-semibold leading-snug text-foreground transition-colors group-hover:text-primary">{termin.title}</p>
        <p className="mt-2 text-meta text-muted-foreground">
          {termin.committee ? shortCommittee(termin.committee) : "Sitzung"}{termin.session_time ? ` · ${termin.session_time.slice(0, 5)} Uhr` : ""}
        </p>
      </Link> : projekt ? <Link href={viertelHref(viertel.place_id, projekt.id)} className={linkStil}>
        <p className="text-quelle font-semibold leading-snug text-foreground transition-colors group-hover:text-primary">{projekt.name}</p>
        {projekt.what && <p className={cn("mt-1.5 text-hinweis text-muted-foreground", detail === "expanded" ? "line-clamp-3" : "line-clamp-2")}>{projekt.what}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta">
          {stand && <Badge color={stand.color}><span className="text-meta">{stand.label}</span></Badge>}
          <span className="text-muted-foreground">{ratsdatum ? `Zuletzt im Rat: ${formatDate(ratsdatum)}` : "Ratsdatum nicht hinterlegt"}</span>
        </div>
      </Link> : <p className="text-hinweis text-muted-foreground">Noch keine Vorhaben oder nächsten Beratungen in den Ratsunterlagen erfasst.</p>}
      {termin && projekt && detail === "expanded" && <Link href={viertelHref(viertel.place_id, projekt.id)}
        className={cn(linkStil, "mt-3 border-t border-border/60 pt-3 text-hinweis text-muted-foreground hover:text-primary")}>
        Außerdem im Viertel: {projekt.name}
      </Link>}
    </div>}
    <Link href={viertelHref(viertel.place_id)} className="group mt-2 inline-flex min-h-11 items-center gap-1.5 self-start text-hinweis font-medium text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
      Viertel auf der Karte <ArrowRight className="h-3.5 w-3.5 transition-transform motion-safe:group-hover:translate-x-0.5" aria-hidden />
    </Link>
  </article>;
}
