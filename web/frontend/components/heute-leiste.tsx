"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { currentSession, isStadtrat, runningTimeText, timeOnDay, O1_STREAM_URL } from "@/lib/live";
import { cn } from "@/lib/utils";

type HeuteSitzung = {
  committee: string;
  session_time: string;
  /** Startzeit der nächsten Sitzung des Tages — Ende des Live-Fensters. */
  live_until?: string | null;
  tops: string[];
  remaining: number;
};

type Heute =
  | ({ state: "heute"; n_sessions_today: number; sessions?: HeuteSitzung[] } & HeuteSitzung)
  | { state: "naechste"; committee: string; session_date: string; session_time: string }
  | { state: "pause"; label: string | null; until: string | null };

const fmt = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "short" });

/** „Heute im Rat"-Leiste auf der Landing (RL-301, Design 2a): dezente Zeile
 *  unter dem Header mit Mono-Kicker + Punkt. Vier Zustände (LIVE · heute ·
 *  nächste Sitzung · Pause) — die Leiste verschwindet nie; feste Höhe
 *  verhindert Layout-Shift, bis die Daten da sind. LIVE (RL-U10) wird rein
 *  clientseitig aus den Startzeiten des Tages abgeleitet und tickt minütlich;
 *  beim Stadtrat verlinkt sie auf den O1-Stream. */
export function HeuteLeiste() {
  const [data, setData] = useState<Heute | null>(null);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    // Über `lib/api`, nicht per nacktem fetch: Ein relativer Pfad zeigt in der
    // Capacitor-Hülle ins Nichts (das Bundle läuft dort unter
    // capacitor://localhost). Fehler bleiben still — die Leiste hat einen
    // Leerzustand und soll die Landing nicht mit einer Meldung stören.
    api.get<Heute>("/council/heute")
      .then((d) => d && setData(d))
      .catch(() => {});
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  // An Ratstagen tagen drei Gremien NACHEINANDER (16:00 Ausschuss für
  // Allgemeine Angelegenheiten → 16:30 Verwaltungsausschuss → 18:00 Rat, s.
  // `lib/live`). Die Leiste nennt deshalb nicht stur die erste des Tages,
  // sondern die laufende — und vor dem Beginn die nächste, die noch kommt.
  // Der Rückfall auf die Kopf-Felder trägt ältere Antworten aus dem Cache.
  const tagesSitzungen: HeuteSitzung[] =
    data?.state === "heute"
      ? data.sessions ?? [{ committee: data.committee, session_time: data.session_time, tops: data.tops, remaining: data.remaining }]
      : [];
  const laufend = currentSession(tagesSitzungen, now);
  const aktuell =
    laufend ??
    tagesSitzungen.find((s) => {
      const start = timeOnDay(s.session_time, now);
      return start !== null && now < start;
    }) ??
    tagesSitzungen[0];

  const live = Boolean(laufend);
  const heute = Boolean(aktuell) && !live;
  const nTops = aktuell ? aktuell.tops.length + aktuell.remaining : 0;
  const stadtrat = Boolean(aktuell) && isStadtrat(aktuell.committee);

  return (
    <div
      className={cn(
        "border-b border-border",
        live ? "bg-red-500/[0.06]" : heute ? "bg-[hsl(19_92%_55%/0.06)]" : "bg-muted/30",
      )}
      role="status"
    >
      <div className="mx-auto flex min-h-11 max-w-6xl items-center gap-3 px-5 py-2 text-sm">
        {live ? (
          <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
            <span className="absolute inset-0 rounded-full bg-red-500 motion-safe:animate-ping" />
            <span className="relative h-2 w-2 rounded-full bg-red-500" />
          </span>
        ) : (
          <span
            className={cn("h-2 w-2 shrink-0 rounded-full", heute ? "bg-signal" : "bg-muted-foreground/50")}
            aria-hidden
          />
        )}
        <span
          className={cn(
            "shrink-0 font-mono text-[11px] font-medium uppercase tracking-[0.14em]",
            live ? "text-red-700 dark:text-red-400" : "text-muted-foreground",
          )}
        >
          {live ? "Live" : data?.state === "heute" ? "Heute im Rat" : data?.state === "naechste" ? "Nächste Sitzung" : data?.state === "pause" ? "Sitzungspause" : " "}
        </span>
        <span className="min-w-0 flex-1 truncate text-foreground">
          {live && aktuell && (
            <>
              {stadtrat ? "Der Stadtrat tagt" : `${aktuell.committee} tagt`} — seit{" "}
              {runningTimeText(aktuell.session_time, now)}
              {nTops > 0 && <span className="text-muted-foreground">, {nTops} {nTops === 1 ? "TOP" : "TOPs"}</span>}
            </>
          )}
          {heute && aktuell && (
            <>
              {aktuell.committee}, {aktuell.session_time} Uhr
              {aktuell.tops.length > 0 && <span className="text-muted-foreground"> — {aktuell.tops.join(" · ")}</span>}
              {aktuell.remaining > 0 && <span className="text-muted-foreground"> + {aktuell.remaining} weitere</span>}
            </>
          )}
          {data?.state === "naechste" && (
            <>
              {fmt(data.session_date)} · {data.committee}
              {data.session_time && `, ${data.session_time} Uhr`}
            </>
          )}
          {data?.state === "pause" && (
            <>
              {data.label ?? "Gerade keine Sitzungen"}
              {data.until && <span className="text-muted-foreground"> — bis {fmt(data.until)}</span>}
            </>
          )}
        </span>
        {/* RL-F05: jeder Zustand verlinkt — live beim Stadtrat zum O1-Stream,
            heute zur Tagesordnung, sonst dezent in den Sitzungskalender. */}
        {live && stadtrat ? (
          <a
            href={O1_STREAM_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden shrink-0 items-center gap-1 font-medium text-red-700 hover:underline dark:text-red-400 sm:inline-flex"
          >
            Zum O1-Stream <ArrowRight className="h-3.5 w-3.5" />
          </a>
        ) : data ? (
          <Link
            href="/council?tab=sessions"
            className="hidden shrink-0 items-center gap-1 font-medium text-primary hover:underline sm:inline-flex"
          >
            {data.state === "heute" ? "Zur Tagesordnung" : "Kalender"} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        ) : null}
      </div>
    </div>
  );
}
