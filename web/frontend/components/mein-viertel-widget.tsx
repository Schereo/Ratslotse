"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, MapPinned } from "lucide-react";
import { HeuteWidget, useWidgetDetail, type WidgetSize } from "@/components/heute-widget";
import { Badge, Button, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { shortCommittee } from "@/lib/committees";
import { decisionHref, sessionHref, viertelHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { Topic } from "@/lib/types";
import { naechsteViertelBeratung, STAND, viertelVorhaben, WEG_SCHRITTE, wegStufe, ZEITPLAN, type ViertelTafel } from "@/lib/viertel-einblick";
import { STAND_FARBE } from "@/components/viertel-zeichner";
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
  const vorhaben = viertelVorhaben(query.data?.projects ?? []);
  const [index, setIndex] = useState(0);
  // Die Tafel kann beim Nachladen kürzer werden — dann nicht ins Leere zeigen.
  const i = Math.min(index, Math.max(vorhaben.length - 1, 0));
  const projekt = vorhaben[i];
  const termin = naechsteViertelBeratung(query.data?.upcoming ?? [], heuteIso);

  return <article aria-label={viertel.name} className={cn("min-w-0", detail === "expanded" ? "flex flex-col" : "py-4 first:pt-0 last:pb-0")}>
    <div className="mb-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
      <h3 className="text-meta font-semibold uppercase tracking-[0.04em] text-primary">{viertel.name}</h3>
      {vorhaben.length > 1
        ? <Blaettern index={i} anzahl={vorhaben.length} onIndex={setIndex} />
        : <span className="text-meta text-muted-foreground">{viertel.count} Vorhaben</span>}
    </div>
    {query.isPending && <p role="status" className="py-3 text-hinweis text-muted-foreground">Einblick wird geladen.</p>}
    {query.isError && <div role="alert" className="text-hinweis text-muted-foreground">
      Der Einblick konnte nicht {query.data ? "aktualisiert" : "geladen"} werden.
      <Button variant="ghost" className="h-auto min-h-11 whitespace-normal" onClick={() => query.refetch()} disabled={query.isFetching}>Erneut versuchen</Button>
    </div>}
    {query.data && <div className="flex-1">
      {/* Eine Beratung in den nächsten 14 Tagen hat Vorrang: Sie steht oben
          und führt direkt zum Tagesordnungspunkt. Die Vorhaben bleiben darunter. */}
      {termin && <Link href={sessionHref(termin.ksinr, termin.item_number ? [termin.item_number] : undefined)}
        className={cn(linkStil, "mb-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2.5")}>
        <span className="mb-1 flex items-center gap-1.5 text-meta font-medium text-primary">
          <CalendarDays className="h-3.5 w-3.5" aria-hidden /> Am {formatDate(termin.session_date)} im Rat
          {termin.session_time ? ` · ${termin.session_time.slice(0, 5)} Uhr` : ""}
        </span>
        <p className="line-clamp-2 text-hinweis font-medium leading-snug text-foreground transition-colors group-hover:text-primary">{termin.title}</p>
        {termin.committee && <p className="mt-1 text-meta text-muted-foreground">{shortCommittee(termin.committee)}</p>}
      </Link>}
      {projekt ? <VorhabenEinblick key={projekt.id} projekt={projekt} placeId={viertel.place_id} />
        : !termin && <p className="text-hinweis text-muted-foreground">Noch keine Vorhaben oder nächsten Beratungen in den Ratsunterlagen erfasst.</p>}
    </div>}
    <Link href={viertelHref(viertel.place_id)} className="group mt-2 inline-flex min-h-11 items-center gap-1.5 self-start text-hinweis font-medium text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
      Viertel auf der Karte <ArrowRight className="h-3.5 w-3.5 transition-transform motion-safe:group-hover:translate-x-0.5" aria-hidden />
    </Link>
  </article>;
}

/** „‹ 1 von 2 ›“ — stille runde Pfeile (§ 6), am Anschlag gedimmt
 *  statt versteckt, damit der Zähler nicht springt. Die Trefferfläche ist
 *  44 px, der sichtbare Kreis 28 px. */
function Blaettern({ index, anzahl, onIndex }: { index: number; anzahl: number; onIndex: (i: number) => void }) {
  return <div role="group" aria-label="Vorhaben blättern" className="-mr-2.5 flex items-center">
    <Pfeil richtung="zurueck" aus={index === 0} onClick={() => onIndex(index - 1)} />
    {/* Sichtbar nur „1 von 2“ — dass es um Vorhaben geht, sagt der Inhalt
        darunter (Tim 08.11.2026); der Screenreader bekommt das Wort dazu. */}
    <span className="min-w-[3.5em] text-center text-meta tabular-nums text-muted-foreground" aria-live="polite">
      {index + 1} von {anzahl}<span className="sr-only"> Vorhaben</span>
    </span>
    <Pfeil richtung="vor" aus={index >= anzahl - 1} onClick={() => onIndex(index + 1)} />
  </div>;
}

function Pfeil({ richtung, aus, onClick }: { richtung: "zurueck" | "vor"; aus: boolean; onClick: () => void }) {
  const Icon = richtung === "vor" ? ChevronRight : ChevronLeft;
  return <button type="button" onClick={onClick} disabled={aus} aria-label={richtung === "vor" ? "Nächstes Vorhaben" : "Vorheriges Vorhaben"}
    className="group/pf -my-2 inline-flex h-11 w-11 items-center justify-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-default">
    <span className={cn("flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-sm transition-colors",
      aus ? "opacity-40" : "group-hover/pf:border-primary/40 group-hover/pf:text-primary")}>
      <Icon className="h-4 w-4" aria-hidden />
    </span>
  </button>;
}

function VorhabenEinblick({ projekt, placeId }: { projekt: ViertelTafel["projects"][number]; placeId: string }) {
  const detail = useWidgetDetail();
  const stand = STAND[projekt.stage];
  const stufe = wegStufe(projekt.stage);
  const update = projekt.latest_update;
  const ratsdatum = projekt.last_date ?? projekt.first_date;
  const zeitplan = projekt.schedule ? ZEITPLAN[projekt.schedule] : undefined;
  const farbe = STAND_FARBE[projekt.stage] ?? STAND_FARBE.planning;
  return <div className="inhalt-auf @container/weg">
    <Link href={viertelHref(placeId, projekt.id)} className={linkStil}>
      <p className="text-quelle font-semibold leading-snug text-foreground transition-colors group-hover:text-primary">{projekt.name}</p>
      {projekt.what && <p className={cn("mt-1.5 text-hinweis text-muted-foreground", detail === "expanded" ? "line-clamp-3" : "line-clamp-2")}>{projekt.what}</p>}
    </Link>

    {/* Wo das Vorhaben auf seinem Weg steht. „Abgelehnt“ liegt neben dem
        Weg und bekommt nur sein Abzeichen. Die fünf Beschriftungen brauchen
        24 rem eigene Breite (drei Viertel nebeneinander schnitten
        „Beschluss“ ab); darunter nennt die Zeile nur die erreichte Stufe. */}
    <div className="mt-3">
      {stufe >= 0 ? <ol className="grid grid-cols-5 gap-1" aria-label={`Stand: ${stand?.label ?? projekt.stage}`}>
        {WEG_SCHRITTE.map((s, k) => <li key={s.stage} className="min-w-0" aria-current={k === stufe ? "step" : undefined}>
          <span className={cn("block h-1.5 rounded-full", k > stufe && "bg-border")} style={k <= stufe ? { background: farbe, opacity: k === stufe ? 1 : 0.45 } : undefined} />
          <span className={cn("mt-1 hidden truncate text-meta @sm/weg:block", k === stufe ? "font-semibold text-foreground" : "text-muted-foreground")}>{s.label}</span>
        </li>)}
      </ol> : stand && <Badge color={stand.color}><span className="text-meta">{stand.label}</span></Badge>}
      {(stufe >= 0 || projekt.when || zeitplan) && <p className={cn("mt-1 text-meta text-muted-foreground", !projekt.when && !zeitplan && "@sm/weg:hidden")}>
        {stufe >= 0 && <span className="@sm/weg:hidden">
          <span className="font-semibold text-foreground">{stand?.label}</span>{projekt.when || zeitplan ? " · " : ""}
        </span>}
        {projekt.when && <>Zeitraum: {projekt.when}</>}
        {projekt.when && zeitplan && " · "}
        {zeitplan && <span className="font-medium text-amber-800 dark:text-amber-300">{zeitplan}</span>}
      </p>}
    </div>

    {/* „Zuletzt im Rat" allein sagt nicht, WAS dort war — der jüngste
        Beschluss mit seinem Kernsatz, verlinkt auf die Beschlussseite. */}
    {update ? <Link href={decisionHref(update.decision_id)} className={cn(linkStil, "mt-3 rounded-lg bg-muted/60 px-3 py-2.5")}>
      <span className="block text-meta text-muted-foreground">
        Zuletzt im Rat · {formatDate(update.date)}{update.committee ? ` · ${shortCommittee(update.committee)}` : ""}
      </span>
      <p className="mt-0.5 line-clamp-3 text-hinweis leading-snug text-foreground transition-colors group-hover:text-primary">{update.summary ?? update.title}</p>
    </Link> : <p className="mt-3 text-meta text-muted-foreground">{ratsdatum ? `Zuletzt im Rat: ${formatDate(ratsdatum)}` : "Ratsdatum nicht hinterlegt"}</p>}
  </div>;
}
