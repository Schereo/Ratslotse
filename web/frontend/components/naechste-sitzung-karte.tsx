"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays } from "lucide-react";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { HeuteWidget, type WidgetSize } from "@/components/heute-widget";
import { shortCommittee } from "@/lib/committees";

type Sitzungen = ApiAntwort<"/council/sessions">;

/** „Die Woche im Rat" ohne Woche: Tagt in den nächsten sieben Tagen nichts,
 *  fiel die Karte bis 10/2026 einfach weg — und oben auf „Heute" standen nur
 *  noch ein leerer Rückblick und eine Null. Dabei ist das Nächste bekannt.
 *  Diese Karte nennt es: den nächsten Sitzungstag, wie weit er weg ist, und
 *  wer dann tagt. */
export function NaechsteSitzungKarte({ size, heute }: { size?: WidgetSize; heute: Date | null }) {
  const { data } = useQuery({
    queryKey: ["sitzungen", "naechste"],
    queryFn: () => api.get<Sitzungen>("/council/sessions?scope=upcoming&limit=12"),
    staleTime: 60 * 60 * 1000,
  });
  const alle = data?.sessions ?? [];
  if (alle.length === 0) return null;
  const tag = alle[0].session_date;
  const amTag = alle.filter((s) => s.session_date === tag);
  const datum = new Date(`${tag}T12:00:00`);
  const inTagen = heute
    ? Math.round((Date.UTC(datum.getFullYear(), datum.getMonth(), datum.getDate())
        - Date.UTC(heute.getFullYear(), heute.getMonth(), heute.getDate())) / 86_400_000)
    : null;
  const wann = inTagen === null ? "" : inTagen <= 0 ? "heute" : inTagen === 1 ? "morgen" : `in ${inTagen} Tagen`;
  const ohneTagesordnung = amTag.every((s) => !s.n_items);

  return (
    <HeuteWidget id="naechste-sitzung" title="Nächste Sitzung" icon={CalendarDays} size={size}
      meta={wann || undefined}
      footer={
        <Link href="/council?tab=sessions" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
          Alle anstehenden Sitzungen <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      }>
      <div className="inhalt-auf">
        <p className="font-display text-[28px] font-bold leading-none tracking-tight text-foreground">
          {datum.toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "long" })}
        </p>
        <ul className="mt-3 space-y-1.5">
          {amTag.map((s, i) => (
            <li key={`${s.committee}|${i}`} className="flex items-baseline gap-2.5 text-[13.5px]">
              <span className="w-11 shrink-0 font-mono text-xs tabular-nums text-muted-foreground">{s.session_time ?? ""}</span>
              <span className="min-w-0 text-foreground">{shortCommittee(s.committee)}</span>
            </li>
          ))}
        </ul>
        {ohneTagesordnung && (
          <p className="mt-3 text-hinweis text-muted-foreground">
            Die Tagesordnungen erscheinen etwa eine Woche vorher — wer Ausschüsse abonniert hat, bekommt sie dann.
          </p>
        )}
      </div>
    </HeuteWidget>
  );
}
