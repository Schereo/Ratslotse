"use client";

// Die Einstiege zum Wahlabend (/wahlabend): ein Streifen auf der Landing und
// ein Hinweis im Slot der Heute-Seite. Beide hängen am Feature-Schalter
// `wahlabend` — ohne ihn rendern sie nichts, denn die Zielseite zeigt dann
// nur einen Hinweis („Ein Gate braucht auch seine Einstiegspunkte",
// web/frontend/CLAUDE.md). Am Wahlabend selbst sind sie der kürzeste Weg zu
// den Zahlen; nach dem amtlichen Endergebnis geht der Schalter aus, und
// beide verschwinden ohne Deploy.

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Vote } from "lucide-react";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useFeature } from "@/lib/features";
import { wahlabendZeit, type WahlabendZeit } from "@/lib/wahlabend";

/** Countdown bis Sonntag 18 Uhr, danach „läuft". Der Client rechnet nach dem
 *  Mounten selbst und jede Minute neu — der Bauzeit-Wert wäre nach ein paar
 *  Tagen falsch (suppressHydrationWarning, wie beim Wahl-Check). */
export function useWahlabendZeit(): WahlabendZeit {
  const [zeit, setZeit] = useState(() => wahlabendZeit());
  useEffect(() => {
    setZeit(wahlabendZeit());
    const id = window.setInterval(() => setZeit(wahlabendZeit()), 60_000);
    return () => window.clearInterval(id);
  }, []);
  return zeit;
}

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Landing: ein Streifen in der Anzeigetafel-Fläche, unter dem Hero. */
export function WahlabendBanner() {
  const an = useFeature("wahlabend");
  const zeit = useWahlabendZeit();
  if (!an) return null;
  const laeuft = zeit.phase === "laeuft";
  return (
    <section aria-label="Wahlabend zur Ratswahl 2026" className="mx-auto max-w-5xl px-5 pb-2 pt-6">
      <Link
        href="/wahlabend"
        className="hh-tafel group flex flex-col items-center gap-5 rounded-2xl px-5 py-6 sm:flex-row sm:gap-7 sm:px-7"
      >
        <Mascot pose="point" decorative className="hidden h-20 w-20 flex-none sm:block" />
        <div className="min-w-0 text-center sm:text-left">
          <p className={KICKER}>
            <Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />
            Ratswahl · 13. September 2026 · <span suppressHydrationWarning>{zeit.kicker}</span>
          </p>
          <h2 className="mt-1.5 font-display text-[22px] font-bold leading-tight tracking-tight sm:text-[24px]" suppressHydrationWarning>
            {laeuft ? "Der Wahlabend, live nachgerechnet." : `${zeit.wann}: der Wahlabend, live nachgerechnet.`}
          </h2>
          <p className="mt-1.5 max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
            Auszählungsstand, Sitze je Liste und Wahlbereich, und wer nach dem Kommunalwahlgesetz gerade im Rat
            wäre — aus den Open-Data-Zahlen der Stadt, jede Minute neu. Öffentlich, ohne Konto.
            {laeuft ? "" : " Die Seite steht schon, die Zahlen kommen ab Sonntag 18 Uhr."} Eigene Rechnung, kein amtliches
            Ergebnis.
          </p>
        </div>
        <span className="inline-flex flex-none items-center gap-1.5 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform duration-fluss ease-out-strong sm:ml-auto [@media(hover:hover)]:group-hover:-translate-y-0.5">
          <span suppressHydrationWarning>{laeuft ? "Zum Wahlabend" : "Zur Wahlabend-Seite"}</span> <ArrowRight className="h-4 w-4" />
        </span>
      </Link>
    </section>
  );
}

/** Heute: der Hinweis im Slot, ganz vorn in der Reihenfolge — am Wahlabend
 *  gibt es nichts Dringenderes. */
export function WahlabendHinweis() {
  const an = useFeature("wahlabend");
  const zeit = useWahlabendZeit();
  if (!an) return null;
  const laeuft = zeit.phase === "laeuft";
  return (
    <Card className="flex flex-col gap-4 border-primary/25 bg-primary/[0.04] p-4 sm:flex-row sm:items-center">
      <Mascot pose="point" decorative className="hidden h-14 w-14 flex-none sm:block" />
      <div className="min-w-0 flex-1">
        <p className={KICKER}>
          Ratswahl · 13. September 2026 · <span suppressHydrationWarning>{zeit.kicker}</span>
        </p>
        <h2 className="mt-0.5 font-display text-base font-bold text-foreground" suppressHydrationWarning>
          {laeuft ? "Der Wahlabend läuft" : `${zeit.wann}: der Wahlabend`}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground" suppressHydrationWarning>
          {laeuft
            ? "Auszählungsstand, Sitze je Liste und Wahlbereich, wer gerade im Rat wäre — live nachgerechnet."
            : "Auszählungsstand, Sitze je Liste und Wahlbereich, wer im Rat wäre — live nachgerechnet, sobald die Wahllokale schließen."}
        </p>
      </div>
      <Button asChild className="w-full shrink-0 sm:w-auto">
        <Link href="/wahlabend">
          <span suppressHydrationWarning>{laeuft ? "Zum Wahlabend" : "Zur Wahlabend-Seite"}</span> <ArrowRight />
        </Link>
      </Button>
    </Card>
  );
}
