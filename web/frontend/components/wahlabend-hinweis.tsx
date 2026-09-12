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
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Eye, Trophy, Vote } from "lucide-react";
import { Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { wahlabendZeit, type WahlabendZeit } from "@/lib/wahlabend";
import { cn } from "@/lib/utils";

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

type TippSetup = ApiAntwort<"/tipp/setup">;

/** Ein Weg von zweien auf der Heute-Karte: Zuschauen oder Mittippen. */
function Weg({ href, icon, titel, text, knopf, betont }: {
  href: string; icon: React.ReactNode; titel: string; text: React.ReactNode; knopf: string; betont?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex min-w-0 flex-col gap-2 rounded-xl border p-3.5 transition-[border-color,background-color,transform] duration-fluss ease-out-strong",
        "[@media(hover:hover)]:hover:-translate-y-0.5",
        betont
          ? "border-primary/30 bg-card shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:border-primary/50"
          : "border-border bg-card/60 hover:border-primary/30 hover:bg-card",
      )}
    >
      <p className="flex items-center gap-1.5 font-display text-[15px] font-bold text-foreground">
        <span className="flex h-6 w-6 flex-none items-center justify-center rounded-md bg-primary/10 text-primary [&_svg]:h-3.5 [&_svg]:w-3.5">{icon}</span>
        {titel}
      </p>
      <p className="text-[13px] leading-relaxed text-muted-foreground">{text}</p>
      <span className={cn(
        "mt-auto inline-flex items-center gap-1 self-start text-[13px] font-semibold",
        betont ? "rounded-lg bg-primary px-3 py-1.5 text-primary-foreground" : "text-primary",
      )}>
        {knopf} <ArrowRight className="h-3.5 w-3.5 transition-transform duration-fluss group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

/** Heute: der Hinweis im Slot, ganz vorn in der Reihenfolge — am Wahlabend
 *  gibt es nichts Dringenderes. Mit dem Schalter `tippspiel` wird daraus
 *  eine Karte mit zwei Wegen nebeneinander: zuschauen oder mittippen (Tims
 *  Wunsch 12.09.). Ohne den Schalter bleibt es der eine Weg zum Wahlabend. */
export function WahlabendHinweis() {
  const an = useFeature("wahlabend");
  const tippspielAn = useFeature("tippspiel");
  const zeit = useWahlabendZeit();
  // Der Stand des Spiels („23 Leute dabei", Tippfrist vorbei?) — nur mit
  // Schalter abgefragt, sonst antwortet der Endpunkt 404.
  const tipp = useQuery({
    queryKey: ["tipp", "setup", "heute"],
    queryFn: () => api.get<TippSetup>("/tipp/setup"),
    enabled: !!tippspielAn,
    staleTime: 60_000,
    retry: false,
  });
  if (!an) return null;
  const laeuft = zeit.phase === "laeuft";
  const mitTipp = !!tippspielAn;
  const gesperrt = tipp.data?.locked ?? false;
  const dabei = tipp.data?.player_count ?? 0;

  return (
    <Card className="flex flex-col gap-4 border-primary/25 bg-primary/[0.04] p-4">
      <div className="flex items-start gap-4">
        <Mascot pose="point" decorative className="hidden h-14 w-14 flex-none sm:block" />
        <div className="min-w-0 flex-1">
          <p className={KICKER}>
            Ratswahl · 13. September 2026 · <span suppressHydrationWarning>{zeit.kicker}</span>
          </p>
          <h2 className="mt-0.5 font-display text-base font-bold text-foreground" suppressHydrationWarning>
            {laeuft ? "Der Wahlabend läuft" : `${zeit.wann}: der Wahlabend`}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground" suppressHydrationWarning>
            {mitTipp
              ? "Zwei Wege: Schau zu, wie die Stadt auszählt — oder tippe vorher, wie es ausgeht."
              : laeuft
                ? "Auszählungsstand, Sitze je Liste und Wahlbereich, wer gerade im Rat wäre — live nachgerechnet."
                : "Auszählungsstand, Sitze je Liste und Wahlbereich, wer im Rat wäre — live nachgerechnet, sobald die Wahllokale schließen."}
          </p>
        </div>
      </div>

      {mitTipp ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Weg
            href="/wahlabend"
            icon={<Eye />}
            titel="Zuschauen"
            text={laeuft
              ? "Auszählungsstand, Sitze je Liste und Wahlbereich, wer gerade im Rat wäre — jede Minute neu."
              : "Auszählungsstand, Sitze je Liste und Wahlbereich, wer im Rat wäre — live, sobald die Wahllokale schließen."}
            knopf={laeuft ? "Zum Wahlabend" : "Zur Wahlabend-Seite"}
            betont={gesperrt}
          />
          <Weg
            href={gesperrt ? "/tipp/live" : "/tipp"}
            icon={<Trophy />}
            titel="Mittippen"
            text={gesperrt
              ? "Die Tippfrist ist vorbei — die Rangliste zeigt, wer am nächsten dran liegt."
              : <>52 Sitze auf 16 Wahllisten tippen, ohne Konto. Punkte gegen die Hochrechnung, Rangliste am Abend.
                  {dabei > 0 && <> Schon {dabei} {dabei === 1 ? "Person" : "Leute"} dabei.</>}</>}
            knopf={gesperrt ? "Zur Rangliste" : "Jetzt mitmachen"}
            betont={!gesperrt}
          />
        </div>
      ) : (
        <Link
          href="/wahlabend"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground sm:w-auto sm:self-start"
        >
          <span suppressHydrationWarning>{laeuft ? "Zum Wahlabend" : "Zur Wahlabend-Seite"}</span> <ArrowRight className="h-4 w-4" />
        </Link>
      )}
    </Card>
  );
}
