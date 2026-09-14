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
import { useAppConfig, useFeature } from "@/lib/features";
import { datumLang, wahlabendZeit, type WahlabendZeit } from "@/lib/wahlabend";

/** Die Wahl, auf die gerade hingewiesen wird — aus `/api/app-config`.
 *
 *  Welche das ist, entscheidet das Backend (`election.elections.focus`): die
 *  laufende, sonst die nächste anstehende. Bis 09/2026 wusste das Frontend
 *  nur von einer einzigen, fest eincompilierten. */
export function useFokusWahl() {
  return useAppConfig().data?.election ?? null;
}

/** Countdown bis zum Wahlschluss, danach „läuft". Der Client rechnet nach dem
 *  Mounten selbst und jede Minute neu — der Bauzeit-Wert wäre nach ein paar
 *  Tagen falsch (suppressHydrationWarning, wie beim Wahl-Check). */
export function useWahlabendZeit(pollsClose?: string | null): WahlabendZeit {
  const fokus = useFokusWahl();
  const termin = pollsClose ?? fokus?.polls_close ?? null;
  const [zeit, setZeit] = useState(() => wahlabendZeit(termin));
  useEffect(() => {
    setZeit(wahlabendZeit(termin));
    const id = window.setInterval(() => setZeit(wahlabendZeit(termin)), 60_000);
    return () => window.clearInterval(id);
  }, [termin]);
  return zeit;
}

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Was der Einstieg sagt — je nachdem, ob die Wahl noch kommt, gerade läuft
 *  oder vorbei ist.
 *
 *  Die dritte Fassung fehlte bis 09/2026, und weil sie fehlte, stand am
 *  Montagmorgen nach der Wahl „Der Wahlabend läuft" auf der Startseite. Alle
 *  drei stehen hier zusammen: Sechs verstreute Ternaries in zwei Komponenten
 *  laufen auseinander, sobald jemand einen Satz ändert. */
function texte(zeit: WahlabendZeit, name: string): {
  ueberschrift: string;
  kurz: string;
  text: string;
  knopf: string;
} {
  if (zeit.phase === "laeuft") {
    return {
      ueberschrift: "Der Wahlabend, live nachgerechnet.",
      kurz: "Der Wahlabend läuft",
      text: "Auszählungsstand, Sitze je Liste und Wahlbereich, und wer nach dem Kommunalwahlgesetz gerade im Rat "
        + "wäre — aus den Open-Data-Zahlen der Stadt, jede Minute neu. Öffentlich, ohne Konto. Eigene Rechnung, "
        + "kein amtliches Ergebnis.",
      knopf: "Zum Wahlabend",
    };
  }
  if (zeit.phase === "danach") {
    return {
      ueberschrift: `${name}: das Ergebnis, nachgerechnet.`,
      kurz: "Das Ergebnis steht",
      text: "Sitze je Liste und Wahlbereich, wer nach dem Kommunalwahlgesetz in den Rat einzieht und wie knapp es "
        + "war — aus den Open-Data-Zahlen der Stadt. Eigene Rechnung, kein amtliches Ergebnis.",
      knopf: "Zum Ergebnis",
    };
  }
  return {
    ueberschrift: `${zeit.wann}: der Wahlabend, live nachgerechnet.`,
    kurz: `${zeit.wann}: der Wahlabend`,
    text: "Auszählungsstand, Sitze je Liste und Wahlbereich, und wer nach dem Kommunalwahlgesetz im Rat wäre — "
      + `aus den Open-Data-Zahlen der Stadt, jede Minute neu. Öffentlich, ohne Konto. Die Seite steht schon, `
      + `die Zahlen kommen ${zeit.wann.toLowerCase()}.`,
    knopf: "Zur Wahlabend-Seite",
  };
}

/** Landing: ein Streifen in der Anzeigetafel-Fläche, unter dem Hero. */
export function WahlabendBanner() {
  const an = useFeature("wahlabend");
  const wahl = useFokusWahl();
  const zeit = useWahlabendZeit();
  if (!an) return null;
  const t = texte(zeit, wahl?.short_title ?? "Die Wahl");
  return (
    <section aria-label={`Wahlabend: ${wahl?.short_title ?? "die nächste Wahl"}`} className="mx-auto max-w-5xl px-5 pb-2 pt-6">
      <Link
        href={wahl?.path ?? "/wahlabend"}
        className="hh-tafel group flex flex-col items-center gap-5 rounded-2xl px-5 py-6 sm:flex-row sm:gap-7 sm:px-7"
      >
        <Mascot pose="point" decorative className="hidden h-20 w-20 flex-none sm:block" />
        <div className="min-w-0 text-center sm:text-left">
          <p className={KICKER}>
            <Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />
            {wahl?.short_title ?? "Wahlabend"} · {datumLang(wahl?.date)} · <span suppressHydrationWarning>{zeit.kicker}</span>
          </p>
          <h2 className="mt-1.5 font-display text-[22px] font-bold leading-tight tracking-tight sm:text-[24px]" suppressHydrationWarning>
            {t.ueberschrift}
          </h2>
          <p className="mt-1.5 max-w-[62ch] text-sm leading-relaxed text-muted-foreground" suppressHydrationWarning>
            {t.text}
          </p>
        </div>
        <span className="inline-flex flex-none items-center gap-1.5 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform duration-fluss ease-out-strong sm:ml-auto [@media(hover:hover)]:group-hover:-translate-y-0.5">
          <span suppressHydrationWarning>{t.knopf}</span> <ArrowRight className="h-4 w-4" />
        </span>
      </Link>
    </section>
  );
}

/** Heute: der Hinweis im Slot, ganz vorn in der Reihenfolge — am Wahlabend
 *  gibt es nichts Dringenderes. */
export function WahlabendHinweis() {
  const an = useFeature("wahlabend");
  const wahl = useFokusWahl();
  const zeit = useWahlabendZeit();
  if (!an) return null;
  const t = texte(zeit, wahl?.short_title ?? "Die Wahl");
  return (
    <Card className="flex flex-col gap-4 border-primary/25 bg-primary/[0.04] p-4 sm:flex-row sm:items-center">
      <Mascot pose="point" decorative className="hidden h-14 w-14 flex-none sm:block" />
      <div className="min-w-0 flex-1">
        <p className={KICKER}>
          {wahl?.short_title ?? "Wahlabend"} · {datumLang(wahl?.date)} · <span suppressHydrationWarning>{zeit.kicker}</span>
        </p>
        <h2 className="mt-0.5 font-display text-base font-bold text-foreground" suppressHydrationWarning>
          {t.kurz}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground" suppressHydrationWarning>
          {t.text}
        </p>
      </div>
      <Button asChild className="w-full shrink-0 sm:w-auto">
        <Link href={wahl?.path ?? "/wahlabend"}>
          <span suppressHydrationWarning>{t.knopf}</span> <ArrowRight />
        </Link>
      </Button>
    </Card>
  );
}
