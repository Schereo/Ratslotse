"use client";

// /wahlen — alle Wahlen, die wir zeigen: oben die, auf die gerade alles
// zeigt, darunter die gelaufenen mit ihrem Ergebnis.
//
// Warum es diese Seite gibt: `/wahlabend` ist der Name EINES Abends. Für die
// 51 Wochen dazwischen stimmt er nicht, und für einen Rückblick auch nicht.
// Welche Wahl gerade dran ist, entscheidet das Backend (`elections.focus`);
// diese Seite zeigt es nur.

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { Kopf } from "@/components/wahlabend/kopf";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import { datumLang, wahlabendZeit } from "@/lib/wahlabend";
import { geteilt, nachJahren, wann, type Wahlliste, type Wahlzeile } from "@/lib/wahlen";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Die Wahl im Fokus — als Anzeigetafel, wie auf dem Wahlabend selbst. */
function Fokus({ z }: { z: Wahlzeile }) {
  const zeit = wahlabendZeit(z.polls_close);
  const kommt = wann(z) === "kommt";
  return (
    <section className="hh-tafel mt-5 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4">
        <div className="min-w-0 flex-1 basis-[18rem]">
          <p className={KICKER}>
            {datumLang(z.date)} · <span suppressHydrationWarning>{zeit.kicker}</span>
          </p>
          <h2 className="mt-1.5 font-display text-[26px] font-bold leading-tight tracking-tight sm:text-[30px]">
            {z.short_title}
          </h2>
          {z.summary ? (
            <p className="mt-2 text-[14px] text-foreground">{z.summary}</p>
          ) : (
            <p className="mt-2 text-[14px] text-muted-foreground" suppressHydrationWarning>
              {kommt ? `${zeit.wann} zeigt diese Seite den Auszählungsstand.` : "Die Zahlen stehen noch aus."}
            </p>
          )}
        </div>
        {z.path ? (
          <Link
            href={z.path}
            className="inline-flex flex-none items-center gap-1.5 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
          >
            {kommt ? "Zur Seite" : "Zum Ergebnis"} <ArrowRight className="h-4 w-4" />
          </Link>
        ) : null}
      </div>
    </section>
  );
}

/** Eine gelaufene (oder weitere kommende) Wahl als Zeile. */
function Zeile({ z }: { z: Wahlzeile }) {
  const inhalt = (
    <>
      <div className="min-w-0 flex-1">
        <p className="truncate font-display text-[15px] font-bold tracking-tight">{z.short_title}</p>
        <p className="mt-0.5 text-[12.5px] text-muted-foreground">
          {datumLang(z.date)}
          {z.summary ? <> · {z.summary}</> : null}
        </p>
      </div>
      {z.path ? <ArrowRight className="h-4 w-4 flex-none text-primary" aria-hidden /> : null}
    </>
  );
  const klasse = cn(
    "flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3",
    z.path && "transition-colors duration-tipp hover:bg-primary/5",
  );
  return z.path ? (
    <li>
      <Link href={z.path} className={klasse}>
        {inhalt}
      </Link>
    </li>
  ) : (
    // Ohne Seite kein Link: Von der Ratswahl 2021 liegen die Zahlen im Repo,
    // die Kandidatenlisten aber nicht — ein Link ins Leere wäre schlechter
    // als keiner.
    <li className={klasse}>{inhalt}</li>
  );
}

export function WahlenView() {
  const frei = useFeature("wahlabend");
  const { data, isLoading } = useQuery({
    queryKey: ["wahlen"],
    queryFn: () => api.get<Wahlliste>("/wahlen"),
    enabled: frei,
    staleTime: 15 * 60_000,
    retry: 1,
  });

  if (!frei) {
    return (
      <>
        <Kopf label="Wahlen" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
          <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
            <Mascot pose="sleep" className="h-28 w-28" decorative />
            <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">Gerade nichts zu wählen</h1>
            <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
              Hier stehen die Wahlen in Oldenburg, sobald eine ansteht.
            </p>
          </div>
        </main>
      </>
    );
  }

  const { fokus, weitere } = geteilt(data?.elections ?? []);

  return (
    <>
      <Kopf label="Wahlen" />
      <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
        <h1 className="sr-only">Wahlen in Oldenburg</h1>
        {isLoading ? <div className="mt-6 h-36 animate-pulse rounded-2xl bg-muted" /> : null}
        {fokus ? <Fokus z={fokus} /> : null}

        {weitere.length > 0 ? (
          <section className="mt-8">
            <h2 className="font-display text-[16px] font-bold tracking-tight">Weitere Wahlen</h2>
            {nachJahren(weitere).map((g) => (
              <div key={g.jahr} className="mt-4">
                <p className={KICKER}>{g.jahr}</p>
                <ol className="mt-2 flex flex-col gap-2">
                  {g.zeilen.map((z) => (
                    <Zeile key={z.slug} z={z} />
                  ))}
                </ol>
              </div>
            ))}
          </section>
        ) : null}

        <footer className="mt-10 border-t border-border pt-4 text-[12.5px] leading-relaxed text-muted-foreground">
          <p className="max-w-[76ch]">
            <strong className="font-semibold text-foreground">Quelle:</strong> Die Zahlen stammen aus den
            Open-Data-Dateien und der Ergebnisdarstellung des Votemanagers der Stadt Oldenburg. Gelaufene Wahlen
            liegen bei uns eingefroren — sie brauchen keinen Abruf mehr. Kein amtliches Ergebnis; das stellt der
            Wahlausschuss fest.
          </p>
        </footer>
      </main>
    </>
  );
}
