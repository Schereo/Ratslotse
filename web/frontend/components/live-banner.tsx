"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";
import {
  currentSessionToday, isStadtrat, runningTimeText, O1_STREAM_URL,
  liveAgoText, liveSpeakerText, liveStateFresh, liveTopLabel, type LiveState,
} from "@/lib/live";

type Session = {
  ksinr: number | null;
  committee: string;
  session_date: string;
  session_time: string;
  live_until?: string | null;
  live_state?: LiveState;
  location?: string | null;
  n_items: number;
  my_topic_items?: { item_number: string; topic_name: string }[];
};

/**
 * RL-U10 (Design 10a/11a): Live-Karte auf „Heute" — sitzt im Slot des
 * Pause-Banners (Live und Pause schließen sich zeitlich aus). „Live" heißt:
 * Startzeit erreicht, Nachfolgerin noch nicht dran. Beim Stadtrat kommt seit
 * 09/2026 der Stand aus der Übertragung dazu (`live_state`, s. `lib/live`):
 * welcher TOP gerade läuft und wer spricht — ehrlich beschriftet als
 * Übertragungsstand mit Verzug, denn er hinkt dem Saal rund 2,5 Minuten
 * hinterher. Der O1-Stream-Knopf erscheint ausschließlich beim Stadtrat
 * (einziges übertragenes Gremium).
 *
 * Das `limit` deckt den längsten Sitzungstag ab (Ratstage bringen drei
 * Gremien nacheinander, s. `lib/live`): Wer knapper lädt, hat die laufende
 * Sitzung womöglich gar nicht in der Hand.
 */
export function LiveBanner() {
  // Minütlich neu bewerten — die Karte erscheint/verschwindet von selbst.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const { data } = useQuery({
    queryKey: ["upcoming-sessions"],
    queryFn: () => api.get<{ sessions: Session[] }>("/council/sessions?scope=upcoming&limit=6"),
    // Der Übertragungsstand wechselt alle zwei Minuten — die Karte holt ihn
    // im Minutentakt nach, solange sie steht (sonst zeigte sie den TOP vom
    // Seitenaufruf, bis jemand neu lädt).
    refetchInterval: 60_000,
  });
  const live = currentSessionToday(data?.sessions, now);
  if (!live) return null;

  const laufzeit = runningTimeText(live.session_time, now);
  const myCount = new Set((live.my_topic_items ?? []).map((m) => m.item_number)).size;
  const stadtrat = isStadtrat(live.committee);
  const state = live.live_state;
  const stand = state && liveStateFresh(state, now) ? state : null;
  const topLabel = stand ? liveTopLabel(stand) : null;

  return (
    <div
      role="status"
      className="rounded-2xl border border-red-500/25 bg-gradient-to-br from-red-500/5 to-transparent p-4"
    >
      <div className="flex items-center gap-2.5">
        <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
          <span className="absolute inset-0 rounded-full bg-red-500 motion-safe:animate-ping" />
          <span className="relative h-2.5 w-2.5 rounded-full bg-red-500" />
        </span>
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-red-700 dark:text-red-400">
          Live · seit {laufzeit}
        </span>
        {live.location && <span className="ml-auto truncate text-[11px] text-muted-foreground">{live.location}</span>}
      </div>

      <p className="mt-2.5 font-display text-lg font-bold text-foreground">
        {stadtrat ? "Der Stadtrat tagt gerade" : `${live.committee} tagt gerade`}
      </p>

      <div className="mt-2.5 rounded-xl bg-muted/60 px-3 py-2.5">
        <p className="text-sm text-foreground">
          Begonnen um {live.session_time} Uhr
          {live.n_items > 0 && (
            <>
              {" "}· {live.n_items} {live.n_items === 1 ? "TOP" : "TOPs"}
              {myCount > 0 && (
                <>
                  {" "}— darunter{" "}
                  <span className="inline-flex rounded-full bg-signal/10 px-2 py-px text-[11px] font-bold text-signal">
                    {myCount} zu deinen Themen
                  </span>
                </>
              )}
            </>
          )}
        </p>
        {stand && topLabel ? (
          <div className="mt-2 border-t border-border/60 pt-2" data-testid="live-stand">
            <p className="text-sm text-foreground">
              <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-red-700 dark:text-red-400">
                Gerade
              </span>
              {" "}<span className="font-semibold">{topLabel}</span>
              {stand.item_title && <> · {stand.item_title}</>}
            </p>
            {liveSpeakerText(stand) && (
              <p className="mt-0.5 text-sm text-foreground">{liveSpeakerText(stand)}</p>
            )}
            <p className="mt-1 text-[11px] text-muted-foreground">
              Aus der Live-Übertragung, Stand {liveAgoText(stand.as_of, now)} — rund 2 Min. Verzug.
            </p>
          </div>
        ) : state?.finished ? (
          <p className="mt-1 text-[11px] text-muted-foreground">
            Der öffentliche Teil ist laut Übertragung beendet — Ergebnisse folgen in Kürze.
          </p>
        ) : (
          <p className="mt-1 text-[11px] text-muted-foreground">
            {stadtrat
              ? "Welcher TOP gerade dran ist, meldet die Karte, sobald die Übertragung läuft — Ergebnisse folgen mit dem Protokoll."
              : "Welcher TOP gerade dran ist, weiß das Ratsinfo nicht — Ergebnisse folgen mit dem Protokoll."}
          </p>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-2">
        <Button size="sm" asChild>
          {/* Ohne ksinr gibt es keine Tagesordnung — das trifft genau die
              nichtöffentlichen Gremien (Verwaltungsausschuss), die nur als
              Kalendertermin bekannt sind. Dann führt der Knopf dorthin,
              wohin er wirklich führt. */}
          <Link href={live.ksinr ? `/council?tab=sessions&ksinr=${live.ksinr}` : "/council?tab=sessions"}>
            {live.ksinr ? "Tagesordnung" : "Sitzungskalender"}
          </Link>
        </Button>
        {stadtrat && (
          <>
            <Button size="sm" variant="secondary" asChild>
              <a href={O1_STREAM_URL} target="_blank" rel="noreferrer">
                <ExternalLink /> O1-Livestream
              </a>
            </Button>
            <span className="basis-full text-[11px] text-muted-foreground">
              O1 (oldenburg eins) überträgt nur die Ratssitzungen.
            </span>
          </>
        )}
      </div>
    </div>
  );
}
