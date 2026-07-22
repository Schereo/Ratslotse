"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";
import { isLiveNow, isStadtrat, minutesSinceTime, O1_STREAM_URL } from "@/lib/live";

type Session = {
  ksinr: number | null;
  committee: string;
  session_date: string;
  session_time: string;
  location?: string | null;
  n_items: number;
  my_topic_items?: { item_number: string; topic_name: string }[];
};

/**
 * RL-U10 (Design 10a/11a): Live-Karte auf „Heute" — sitzt im Slot des
 * Pause-Banners (Live und Pause schließen sich zeitlich aus). „Live" heißt
 * nur: Startzeit erreicht, seit weniger als 4 h — kein TOP-Tracking. Der
 * O1-Stream-Knopf erscheint ausschließlich beim Stadtrat (einziges
 * übertragenes Gremium). Teilt die Query mit „Nächste Sitzungen".
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
    queryFn: () => api.get<{ sessions: Session[] }>("/council/sessions?scope=upcoming&limit=3"),
  });
  const live = (data?.sessions ?? []).find((s) => isLiveNow(s, now));
  if (!live) return null;

  const mins = minutesSinceTime(live.session_time, now);
  const myCount = new Set((live.my_topic_items ?? []).map((m) => m.item_number)).size;
  const stadtrat = isStadtrat(live.committee);

  return (
    <div
      role="status"
      className="mt-6 rounded-2xl border border-red-500/25 bg-gradient-to-br from-red-500/5 to-transparent p-4"
    >
      <div className="flex items-center gap-2.5">
        <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
          <span className="absolute inset-0 rounded-full bg-red-500 motion-safe:animate-ping" />
          <span className="relative h-2.5 w-2.5 rounded-full bg-red-500" />
        </span>
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-red-700 dark:text-red-400">
          Live · seit {mins} {mins === 1 ? "Minute" : "Minuten"}
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
              {" "}· {live.n_items} TOPs
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
        <p className="mt-1 text-[11px] text-muted-foreground">
          Welcher TOP gerade dran ist, weiß das Ratsinfo nicht — Ergebnisse folgen mit dem Protokoll.
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-2">
        <Button size="sm" asChild>
          <Link href={live.ksinr ? `/council?tab=sessions&ksinr=${live.ksinr}` : "/council?tab=sessions"}>
            Tagesordnung
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
