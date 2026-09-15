"use client";

// Alle Wahlbezirke aus der Sicht EINER Liste, mit Rang — „wo hat meine Liste
// in den Wahllokalen der Stadt wie gut abgeschnitten?" (Tims Bekannter,
// FDP, 15.09.2026). Die Karte darüber zeigt dasselbe als Tönung; hier steht
// es als Zahl, sortierbar nach Anteil oder Stimmen. Sortierung und Rang
// rechnet der Server (`/api/wahlabend/wahlbezirke/rangliste`).
//
// Die Briefwahlbezirke stehen dazwischen wie alle anderen — sie sind ein
// Drittel der Stimmen — und tragen ihren Wahlbereich ausdrücklich: 921 ist
// der zweite Briefwahlbezirk von Wahlbereich II. Die Nummer sagt es (9xy:
// x = Wahlbereich), aber niemand soll das im Kopf entschlüsseln müssen.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Segmented } from "@/components/ui/segmented";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  bezirksRanglistePfad,
  prozent,
  zahl,
  type BezirksRangliste,
  type BezirksSortierung,
  type WahlabendPartei,
} from "@/lib/wahlabend";

const SORTIERUNGEN: { value: BezirksSortierung; label: string }[] = [
  { value: "share", label: "Anteil" },
  { value: "votes", label: "Stimmen" },
];

export function BezirksRangliste({ partei, bereich, bereichName, probe, counted, rueckblick, gewaehlt, onWaehlen, className }: {
  partei: WahlabendPartei;
  /** Nur dieser Wahlbereich — `null` = ganze Stadt. Folgt dem Fokus der Karte. */
  bereich: number | null;
  bereichName?: string;
  probe: string | null;
  counted: string | null;
  rueckblick: string | null;
  gewaehlt: number | null;
  /** Eine Zeile antippen hebt den Bezirk auf der Karte hervor. */
  onWaehlen: (nr: number) => void;
  className?: string;
}) {
  const [sortierung, setSortierung] = useState<BezirksSortierung>("share");
  const pfad = bezirksRanglistePfad(probe, counted, rueckblick, partei.slug, sortierung, bereich);
  const abfrage = useQuery({
    queryKey: ["wahlbezirke-rangliste", pfad],
    queryFn: () => api.get<BezirksRangliste>(pfad),
    staleTime: rueckblick ? Infinity : 60_000,
    placeholderData: (alt) => alt,
  });
  const daten = abfrage.data;
  const max = Math.max(0, ...(daten?.rows ?? []).map((z) => (sortierung === "share" ? z.share_pct ?? 0 : z.votes ?? 0)));

  return (
    <section className={cn("mt-4", className)} data-testid="bezirks-rangliste">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className={KICKER}>Rangliste</p>
          <h4 className="mt-0.5 font-display text-[15px] font-bold tracking-tight">
            <span className="inline-flex items-center gap-1.5">
              <Punkt color={partei.color} dark={partei.color_dark} />
              {partei.short} in {bereich === null ? "allen Wahlbezirken der Stadt" : `Wahlbereich ${bereichName ?? bereich}`}
            </span>
          </h4>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">
            {daten
              ? `${zahl(daten.counted)} von ${zahl(daten.total)} Bezirken gezählt · Briefwahlbezirke heißen 9xy — x ist der Wahlbereich, 921 ist also der zweite Briefwahlbezirk von II.`
              : "Wird geladen …"}
          </p>
        </div>
        <Segmented value={sortierung} onChange={setSortierung} options={SORTIERUNGEN} className="flex-none" />
      </div>

      {daten ? (
        <ol className={cn("mt-2 divide-y divide-border/60 border-t border-border/60", abfrage.isPlaceholderData && "opacity-60 transition-opacity")}>
          {daten.rows.map((z) => {
            const wert = sortierung === "share" ? z.share_pct : z.votes;
            const aktiv = gewaehlt === z.number;
            return (
              <li key={z.number}>
                <button
                  type="button"
                  onClick={() => onWaehlen(z.number)}
                  aria-pressed={aktiv}
                  className={cn(
                    "-mx-1 flex w-full items-center gap-2.5 rounded-md px-1 py-1.5 text-left transition-colors hover:bg-muted/40",
                    aktiv && "bg-primary/[0.06]",
                  )}
                >
                  <span className="w-7 flex-none text-right font-mono text-[11px] text-muted-foreground tabular-nums">{z.rank ?? "–"}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex min-w-0 items-baseline gap-1.5">
                      <span className={cn("truncate text-[13px]", z.counted ? "font-medium" : "text-muted-foreground")}>{z.name}</span>
                      {/* Der Wahlbereich steht bei jeder Zeile der Stadtliste; bei
                          der Briefwahl IMMER, weil die Nummer allein ihn versteckt
                          (der Name sagt schon „Briefwahl", das steht nicht doppelt). */}
                      {bereich === null || z.postal ? (
                        <span className="flex-none whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground" data-postal={z.postal ? "1" : undefined}>
                          WB {z.area_roman}
                        </span>
                      ) : null}
                    </span>
                    <span aria-hidden className="mt-1 block h-1 w-full overflow-hidden rounded-full bg-foreground/10">
                      <span
                        className={cn("block h-full rounded-full", z.counted ? "bg-primary/70" : "bg-transparent")}
                        style={{ width: max > 0 && wert ? `${Math.max(1.5, (100 * wert) / max)}%` : "0%" }}
                      />
                    </span>
                  </span>
                  <span className="w-16 flex-none text-right text-[13px] font-semibold tabular-nums">
                    {z.counted ? (sortierung === "share" ? prozent(z.share_pct) : zahl(z.votes)) : <span className="font-normal text-muted-foreground">offen</span>}
                  </span>
                  <span className="hidden w-16 flex-none text-right text-[11px] text-muted-foreground tabular-nums sm:block">
                    {z.counted ? (sortierung === "share" ? zahl(z.votes) : prozent(z.share_pct)) : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      ) : abfrage.isError ? (
        <p className="mt-2 text-[12.5px] text-muted-foreground">Die Rangliste ließ sich gerade nicht laden.</p>
      ) : null}
    </section>
  );
}
