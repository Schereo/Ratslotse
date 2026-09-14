"use client";

// Die Wahlbereiche EINER Liste in ihrer Rangfolge — nach absoluten Stimmen.
//
// Tims Befund am Abend nach der Wahl: Die sechs Karten darunter standen in
// Wahlbereichs-Reihenfolge (I…VI) und führten den Prozentwert als größte
// Zahl. Beides beantwortet die Frage nicht, die man vor ihnen hat — „wo holt
// diese Liste ihre Stimmen?". Die Sitze folgen den Stimmen (§ 37 Abs. 3),
// nicht den Prozenten, und die beiden Achsen fallen wirklich auseinander:
// Bei sieben der sechzehn Listen von 2026 ist der stimmenstärkste Wahlbereich
// nicht der prozentstärkste (die SPD holt in III mehr Stimmen als in II, bei
// kleinerem Anteil — III hat mehr Wahlberechtigte).
//
// Der „Zugriff": Über den letzten Sitz einer Liste entscheidet kein ganzer
// Stimmenblock, sondern der größte Rest nach Hare/Niemeyer. Welcher
// Wahlbereich ihn bekommen hat und welcher als Nächster dran wäre, rechnet
// das Backend mit (`election/seats.py::hare_niemeyer_detail`) — hier stehen
// nur die zwei Etiketten.

import { ChevronRight } from "lucide-react";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { useTween } from "@/lib/use-tween";
import { cn } from "@/lib/utils";
import { prozent, zahl, type Wahlabend, type WahlabendPartei } from "@/lib/wahlabend";

type Zeile = WahlabendPartei["areas"][number];

/** Die Kennung der zugehörigen Karte — gemeinsam mit `BereichKarte`, damit
 *  ein Klick in der Rangfolge dort landet. */
export function bereichAnker(nummer: number): string {
  return `wb-${nummer}`;
}

function Balken({ zeile, max, aktiv }: { zeile: Zeile; max: number; aktiv: boolean }) {
  if (zeile.votes === null || max <= 0) return null;
  return (
    <span aria-hidden className="relative block h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
      <span
        className={cn("gb-balken-auf block h-full rounded-full", aktiv ? "bg-primary" : "bg-foreground/35")}
        style={{ width: `${Math.max(1.5, (100 * zeile.votes) / max)}%`, animationDelay: `${zeile.rank * 40}ms` }}
      />
    </span>
  );
}

function Zugriff({ zeile }: { zeile: Zeile }) {
  if (!zeile.took_last_seat && !zeile.next_seat) return null;
  const text = zeile.took_last_seat ? "letzter Sitz" : "nächster Sitz";
  const titel = zeile.took_last_seat
    ? "Der letzte Sitz dieser Liste ging hierhin — er hing am größten Rest (§ 37 Abs. 3 NKWG)."
    : "Hierhin ginge der nächste Sitz dieser Liste: der größte Rest, der gerade nicht mehr gereicht hat.";
  return (
    <span
      title={titel}
      className={cn(
        "whitespace-nowrap font-mono text-[10px] font-medium uppercase tracking-[0.08em]",
        zeile.took_last_seat ? "text-signal" : "text-muted-foreground",
      )}
    >
      {text}
    </span>
  );
}

function RangZeile({ zeile, max, partei, hochrechnung, waehle }: {
  zeile: Zeile;
  max: number;
  partei: WahlabendPartei;
  hochrechnung: boolean;
  waehle: () => void;
}) {
  const stimmen = useTween(zeile.votes);
  const sitze = zeile.seats ?? 0;
  return (
    <li>
      <button
        type="button"
        onClick={waehle}
        className="flex w-full items-center gap-3 rounded-lg px-1.5 py-2 text-left transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="w-4 flex-none font-mono text-[11px] text-muted-foreground tabular-nums">{zeile.rank}</span>
        <span className="w-[8.5rem] flex-none">
          <span className="flex items-center gap-1.5">
            <Punkt color={partei.color} dark={partei.color_dark} />
            <span className="text-[13px] font-semibold">{zeile.roman}</span>
            {sitze > 0 ? (
              <span className="text-[11.5px] text-muted-foreground">
                {sitze} {sitze === 1 ? "Sitz" : "Sitze"}
              </span>
            ) : null}
          </span>
          <span className="block truncate text-[11.5px] text-muted-foreground">{zeile.name}</span>
          {/* Auf dem Handy gibt es keinen Balken, unter den das Etikett
              passen könnte — dort steht es beim Namen. Eine eigene Zeile
              darunter sah aus, als gehörte sie zur nächsten Zeile. */}
          <span className="mt-0.5 block sm:hidden"><Zugriff zeile={zeile} /></span>
        </span>
        <span className="hidden min-w-0 flex-1 sm:block">
          <Balken zeile={zeile} max={max} aktiv={sitze > 0} />
          <span className="mt-1 block"><Zugriff zeile={zeile} /></span>
        </span>
        <span className="flex-none text-right">
          {/* Die absolute Zahl ist die große: nach ihr verteilt das Gesetz die
              Sitze, und nach ihr fragt man. Der Anteil steht klein darunter —
              er beantwortet eine andere Frage (wie stark ist sie DORT). */}
          <span className="block font-display text-[17px] font-bold leading-none tabular-nums">
            {zeile.votes === null ? "–" : zahl(stimmen === null ? null : Math.round(stimmen))}
          </span>
          <span className="mt-1 block text-[11px] text-muted-foreground tabular-nums">
            {prozent(zeile.share_pct)}
            {hochrechnung && zeile.projected_seats !== null ? <> · Hochr. {zeile.projected_seats}</> : null}
          </span>
        </span>
        <ChevronRight aria-hidden className="h-4 w-4 flex-none text-muted-foreground/60" />
      </button>
    </li>
  );
}

export function Rangfolge({ partei, daten }: { partei: WahlabendPartei; daten: Wahlabend }) {
  const zeilen = partei.areas;
  if (!zeilen.length) return null;
  const max = Math.max(0, ...zeilen.map((z) => z.votes ?? 0));
  const vorher = daten.phase === "before" || max === 0;

  function springe(nummer: number) {
    document.getElementById(bereichAnker(nummer))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <section className="mt-4 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <p className={KICKER}>Wo {partei.short} stark ist</p>
      <h3 className="mt-0.5 font-display text-[15px] font-bold tracking-tight">
        {vorher ? "Die sechs Wahlbereiche" : "Die Wahlbereiche nach Stimmen"}
      </h3>
      <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
        {vorher
          ? "Sobald ausgezählt wird, stehen die Wahlbereiche hier nach den Stimmen dieser Liste — und dazu, wo ihr letzter Sitz hängt."
          : "Nach absoluten Stimmen, nicht nach Prozent: Danach verteilt das Kommunalwahlgesetz die Sitze einer Liste auf die Wahlbereiche. Ein Wahlbereich antippen springt zu seiner Karte."}
      </p>
      <ol className="mt-2 divide-y divide-border/70">
        {zeilen.map((z) => (
          <RangZeile
            key={z.area}
            zeile={z}
            max={max}
            partei={partei}
            hochrechnung={daten.phase === "counting"}
            waehle={() => springe(z.area)}
          />
        ))}
      </ol>
    </section>
  );
}
