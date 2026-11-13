"use client";

/* Das Umfeld eines Punkts (Schalter `punkt-umfeld`, `council/punkt_umfeld.py`):
   wo es ist, was ähnlich schon beschlossen wurde, wo man es in der
   Aufzeichnung sieht, ob gerade eine Beteiligung läuft. Alles aus vorhandenen
   Daten und ohne Modell — deshalb ohne KI-Stern. Jeder Baustein erscheint
   nur, wenn es etwas zu zeigen gibt. */

import dynamic from "next/dynamic";
import Link from "next/link";
import { ExternalLink, MapPin, Play } from "lucide-react";
import { formatDate } from "@/components/ui";
import { OUTCOME_DOT_CLS, OUTCOME_WORD } from "@/components/decision-ui";
import { formatTimestamp } from "@/components/video-result";
import { shortCommittee } from "@/lib/committees";
import { decisionHref, karteHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

// Leaflet kennt kein `window` — nur im Browser laden.
const OrteKarte = dynamic(() => import("@/components/qa-orte-karte"), { ssr: false });

export type Umfeld = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["surroundings"]>;

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";

/** Läuft zu diesem Plan eine Beteiligung, ist die Stellungnahme das Eine, was
 *  Bürger*innen JETZT tun können — deshalb über allem anderen (wie auf der
 *  Beschluss-Seite). Eine beendete steht ruhiger da: als Auskunft, nicht als Aufruf. */
export function BeteiligungsHinweis({ b }: { b: Umfeld["participation"] }) {
  if (!b) return null;
  const laeuft = b.status === "laufend";
  return (
    <a href={b.url} target="_blank" rel="noreferrer"
      className={cn("mb-4 flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors",
        laeuft ? "border-primary/30 bg-primary/5 hover:bg-primary/10" : "border-border bg-card hover:bg-muted/50")}>
      <ExternalLink className={cn("mt-0.5 h-4 w-4 shrink-0", laeuft ? "text-primary" : "text-muted-foreground")} aria-hidden />
      <span className="min-w-0">
        <span className="font-medium text-foreground">{laeuft ? "Bürgerbeteiligung läuft: " : "Bürgerbeteiligung beendet: "}</span>
        {b.step ?? b.title}
        {laeuft && b.valid_until ? ` — Stellungnahme bis ${formatDate(b.valid_until)}` : ""}
        {!laeuft && b.ended_at ? ` — bis ${formatDate(b.ended_at)}` : ""}
        <span className="text-muted-foreground"> (oldenburg.planungsbeteiligung.de)</span>
      </span>
    </a>
  );
}

/** Sprung in die Aufzeichnung — nur Ratssitzungen werden übertragen. Die
 *  Zeitmarke ist die Stelle, an der das Ergebnis festgestellt wird
 *  (`council_video_results`), nicht der Aufruf des Punkts: deshalb „Abstimmung“. */
export function VideoSprung({ video }: { video: Umfeld["video"] }) {
  if (!video) return null;
  const t = video.seconds != null ? `&t=${Math.max(0, video.seconds - 5)}s` : "";
  return (
    <a href={`https://www.youtube.com/watch?v=${video.video_id}${t}`} target="_blank" rel="noreferrer"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-accent">
      <Play className="h-4 w-4 text-primary" aria-hidden />
      Abstimmung in der Aufzeichnung ansehen
      {video.seconds != null && <span className="font-normal tabular-nums text-muted-foreground">bei {formatTimestamp(video.seconds)}</span>}
    </a>
  );
}

export function WoDasIst({ orte }: { orte: Umfeld["places"] }) {
  if (!orte.length) return null;
  const pins = orte.map((o, i) => ({ id: i, nummer: i + 1, name: o.name, lat: o.lat, lon: o.lon }));
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm" aria-labelledby="wo-das-ist">
      <h2 id="wo-das-ist" className="px-4 pt-4 font-display text-base font-semibold text-foreground">Wo das ist</h2>
      <div className="mt-3 border-y border-border">
        <OrteKarte pins={pins} onPin={() => {}} label="Karte der Orte dieses Punkts" />
      </div>
      <ol className="divide-y divide-border/60 px-4">
        {orte.map((o, i) => (
          <li key={o.slug} className="flex min-h-11 items-center gap-2.5 py-2 text-sm">
            <span aria-hidden className="flex h-5 w-5 flex-none items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="font-medium text-foreground [overflow-wrap:anywhere]">{o.name}</span>
              {o.district && o.district !== o.name && <span className="text-muted-foreground"> · {o.district}</span>}
            </span>
          </li>
        ))}
      </ol>
      <Link href={karteHref()} className="flex min-h-11 items-center gap-1.5 border-t border-border px-4 text-sm font-medium text-primary hover:underline">
        <MapPin className="h-4 w-4" aria-hidden /> Auf der Karte der Stadt ansehen
      </Link>
    </section>
  );
}

export function AehnlicheBeschluesse({ liste }: { liste: Umfeld["similar"] }) {
  if (!liste.length) return null;
  return (
    <section className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-labelledby="aehnliche">
      <h2 id="aehnliche" className="font-display text-base font-semibold text-foreground">Ähnliche frühere Beschlüsse</h2>
      <ul className="mt-2 divide-y divide-border/60">
        {liste.map((d) => {
          const ergebnis = d.outcome as DecisionOutcome | null;
          return (
            <li key={d.id}>
              <Link href={decisionHref(d.id)} className="group flex min-h-11 flex-col gap-0.5 py-2.5">
                <span className={KICKER}>
                  {[d.session_date ? formatDate(d.session_date) : null, shortCommittee(d.committee)].filter(Boolean).join(" · ")}
                </span>
                <span className="text-sm font-medium text-foreground group-hover:underline [overflow-wrap:anywhere]">{d.title}</span>
                {ergebnis && OUTCOME_WORD[ergebnis] && (
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                    <span aria-hidden className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS[ergebnis])} /> {OUTCOME_WORD[ergebnis]}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
