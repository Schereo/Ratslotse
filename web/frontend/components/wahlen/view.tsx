"use client";

// /wahlen — alle Wahlen, die wir zeigen: oben als Bühne die, auf die gerade
// alles zeigt, darunter die gelaufenen mit ihrem Ergebnis.
//
// Warum es diese Seite gibt: `/wahlabend` ist der Name EINES Abends. Für die
// 51 Wochen dazwischen stimmt er nicht, und für einen Rückblick auch nicht.
// Welche Wahl gerade dran ist, entscheidet das Backend (`elections.focus`);
// diese Seite zeigt es nur.
//
// Lotti steht hier als Beobachterin (Designsprache § 1), und jede Regung
// hängt an einem Zustand: winkt = die Wahl kommt noch, staunt = es wird
// ausgezählt, hebt den Pokal = das Ergebnis steht, hat eine Idee = der
// Hinweis aufs Tippspiel. Nichts davon passiert zufällig.

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Lock, Trophy } from "lucide-react";
import { Lotti, type LottiRegung } from "@/components/lotti";
import { Mascot } from "@/components/mascot";
import { Reveal } from "@/components/reveal";
import { STAFFEL, staffelStil } from "@/components/staffel";
import { Kopf } from "@/components/wahlabend/kopf";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import { datumLang, wahlabendZeit, type WahlabendZeit } from "@/lib/wahlabend";
import { geteilt, gesperrtesTippspiel, nachJahren, type Wahlliste, type Wahlpunkt, type Wahlzeile } from "@/lib/wahlen";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Parteifarben nur als 8-px-Punkt, nie als Fläche (Designsprache § 2). Helle
 *  Farben (FDP) bekommen den Inset-Ring, sonst verschwinden sie auf Weiß. */
function Punkt({ p, gross = false }: { p: Wahlpunkt; gross?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block flex-none rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]", gross ? "h-2.5 w-2.5" : "h-2 w-2")}
      style={{ background: `light-dark(${p.color}, ${p.color_dark})` }}
    />
  );
}

/** „Grüne 13 · SPD 12 · CDU 7" mit Punkten — die Ergebniszeile, die man auf
 *  einen Blick liest. Bei einer Mehrheitswahl stehen Prozente statt Sitze. */
function Punktzeile({ top, gross = false }: { top: readonly Wahlpunkt[]; gross?: boolean }) {
  if (!top.length) return null;
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", gross ? "text-[15px]" : "text-[13px]")}>
      {top.map((p) => (
        <li key={p.label} className="flex items-center gap-1.5 whitespace-nowrap">
          <Punkt p={p} gross={gross} />
          <span className="font-semibold">{p.label}</span>
          <span className="tabular-nums text-muted-foreground">
            {p.seats !== null ? p.seats : p.pct !== null ? `${p.pct.toFixed(1).replace(".", ",")} %` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Lottis Regung folgt der Phase — nie dem Zufall. */
function regungFuer(zeit: WahlabendZeit): LottiRegung {
  if (zeit.phase === "danach") return "hebt-pokal";
  if (zeit.phase === "laeuft") return "staunt";
  return "winkt";
}

/* ── Die Bühne ──────────────────────────────────────────────────────────── */

function Buehne({ z }: { z: Wahlzeile }) {
  const zeit = wahlabendZeit(z.polls_close);
  const kommt = zeit.phase === "vorher";
  return (
    <section className="relative overflow-hidden rounded-3xl border border-border">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-sky-50 to-transparent dark:from-slate-900/40" aria-hidden />
      <div className="pointer-events-none absolute inset-0 bg-waves opacity-60" aria-hidden />
      <div className="relative z-10 grid items-center gap-6 px-5 py-7 sm:grid-cols-[1fr_auto] sm:px-8 sm:py-9">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-primary">
            {datumLang(z.date)} · <span suppressHydrationWarning>{zeit.kicker}</span>
          </p>
          <h2 className="mt-3 text-balance font-display text-[34px] font-extrabold leading-[1.05] tracking-tight sm:text-[44px]">
            {z.short_title}
          </h2>
          {z.top.length ? (
            <div className="mt-4">
              <Punktzeile top={z.top} gross />
            </div>
          ) : (
            <p className="mt-3 max-w-[48ch] text-[15px] leading-relaxed text-muted-foreground" suppressHydrationWarning>
              {kommt
                ? `${zeit.wann} schließen die Wahllokale. Ab dann rechnet diese Seite jede Minute nach, wer vorn liegt.`
                : "Die Zahlen stehen noch aus — die Seite fragt jede Minute nach."}
            </p>
          )}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            {z.path ? (
              <Link
                href={z.path}
                className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-[opacity,transform] duration-fluss ease-out-strong active:scale-[0.97] [@media(hover:hover)_and_(pointer:fine)]:hover:-translate-y-0.5"
              >
                {kommt ? "Zur Wahlseite" : zeit.phase === "laeuft" ? "Zum Wahlabend" : "Zum Ergebnis"} <ArrowRight className="h-4 w-4" />
              </Link>
            ) : null}
            {z.tipp_path ? (
              <Link
                href={z.tipp_path}
                className="inline-flex items-center gap-1.5 rounded-xl border border-primary/30 bg-card/80 px-5 py-2.5 text-sm font-semibold text-primary backdrop-blur transition-colors duration-fluss hover:bg-primary/5"
              >
                <Trophy className="h-4 w-4" aria-hidden /> {kommt ? "Mittippen" : "Zum Tippspiel"}
              </Link>
            ) : null}
          </div>
        </div>
        <Lotti
          regung={regungFuer(zeit)}
          decorative
          className="mx-auto h-36 w-36 sm:h-48 sm:w-48"
        />
      </div>
    </section>
  );
}

/* ── Der Anreiz ─────────────────────────────────────────────────────────── */

/** Für Anonyme, wenn es ein Tippspiel gibt, das sie nicht sehen: Der eine
 *  Grund, sich hier zu registrieren — konkret, mit Namen der Wahl, statt eines
 *  allgemeinen „Jetzt anmelden". Der Knopf trägt Signal-Orange wie die eine
 *  Signal-Handlung der Startseite. */
function Anreiz({ z }: { z: Wahlzeile }) {
  const zeit = wahlabendZeit(z.polls_close);
  return (
    <Reveal>
      <section className="mt-5 flex flex-col items-center gap-5 rounded-2xl border border-primary/20 bg-primary/[0.05] px-5 py-5 text-center sm:flex-row sm:text-left">
        <Lotti regung="hat-idee" decorative className="h-20 w-20 flex-none" />
        <div className="min-w-0 flex-1">
          <p className={KICKER}>Tippspiel · {z.short_title}</p>
          <h3 className="mt-1 text-balance font-display text-[19px] font-bold leading-tight tracking-tight">
            {/* Der Name bleibt am Stück: „OB-" allein in einer Zeile liest sich als Tippfehler. */}
            Wie geht die <span className="whitespace-nowrap">{z.short_title.replace(/ Oldenburg$/, "")}</span> aus? Tipp mit.
          </h3>
          <p className="mt-1.5 max-w-[56ch] text-[13.5px] leading-relaxed text-muted-foreground" suppressHydrationWarning>
            Zu jeder Wahl gibt es ein Tippspiel — mit Rangliste und Punkten, sobald ausgezählt wird. Dafür brauchst du ein
            Konto: kostenlos, und dein Tipp ist auf jedem Gerät derselbe.
            {zeit.phase === "vorher" ? ` Tippen kannst du bis zur ersten Hochrechnung${zeit.tage > 1 ? ` — noch ${zeit.tage} Tage` : ""}.` : ""}
          </p>
        </div>
        <div className="flex flex-none flex-col items-center gap-2 sm:items-end">
          <Link
            href="/register"
            className="inline-flex items-center gap-1.5 rounded-xl bg-signal px-5 py-2.5 text-sm font-semibold text-signal-foreground shadow-[0_8px_22px_-10px_hsl(19_92%_45%/0.6)] transition-[opacity,transform] duration-fluss ease-out-strong active:scale-[0.97] [@media(hover:hover)_and_(pointer:fine)]:hover:-translate-y-0.5"
          >
            Kostenlos registrieren <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/login" className="text-[13px] font-medium text-primary">
            Schon ein Konto? Anmelden
          </Link>
        </div>
      </section>
    </Reveal>
  );
}

/* ── Die Zeilen ─────────────────────────────────────────────────────────── */

function Zeile({ z, i }: { z: Wahlzeile; i: number }) {
  const kommt = wahlabendZeit(z.polls_close).phase === "vorher";
  const inhalt = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <p className="font-display text-[16px] font-bold tracking-tight">{z.short_title}</p>
          <p className="text-[12.5px] text-muted-foreground">{datumLang(z.date)}</p>
        </div>
        {z.top.length ? (
          <div className="mt-2">
            <Punktzeile top={z.top} />
          </div>
        ) : z.summary ? (
          <p className="mt-1 text-[13px] text-muted-foreground">{z.summary}</p>
        ) : kommt ? (
          <p className="mt-1 text-[13px] text-muted-foreground">Steht noch an.</p>
        ) : null}
      </div>
      <div className="flex flex-none items-center gap-3">
        {/* Auf dem Handy nur das Zeichen — der volle Text quetschte die
            Überschrift der Stichwahl auf zwei Zeilen. */}
        {z.tipp_path ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[11.5px] font-semibold text-primary" title="Tippspiel">
            <Trophy className="h-3 w-3" aria-hidden /> <span className="hidden sm:inline">Tippspiel</span>
            <span className="sr-only sm:hidden">Tippspiel</span>
          </span>
        ) : z.tipp_locked ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-[11.5px] font-medium text-muted-foreground" title="Tippspiel mit Konto">
            <Lock className="h-3 w-3" aria-hidden /> <span className="hidden sm:inline">Tippspiel mit Konto</span>
            <span className="sr-only sm:hidden">Tippspiel mit Konto</span>
          </span>
        ) : null}
        {z.path ? <ArrowRight className="h-4 w-4 text-primary" aria-hidden /> : null}
      </div>
    </>
  );
  const klasse = cn(
    STAFFEL,
    "flex items-center gap-4 rounded-2xl border border-border bg-card px-4 py-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]",
    z.path && "transition-[transform,background-color] duration-fluss ease-out-strong hover:bg-primary/[0.04] [@media(hover:hover)_and_(pointer:fine)]:hover:-translate-y-0.5",
  );
  return z.path ? (
    <li style={staffelStil(i)}>
      <Link href={z.path} className={klasse}>
        {inhalt}
      </Link>
    </li>
  ) : (
    // Ohne Seite kein Link: Von der Ratswahl 2021 liegen die Zahlen im Repo,
    // die Kandidatenlisten aber nicht — ein Link ins Leere wäre schlechter
    // als keiner.
    <li className={klasse} style={staffelStil(i)}>
      {inhalt}
    </li>
  );
}

/* ── Seite ──────────────────────────────────────────────────────────────── */

export function WahlenView() {
  const frei = useFeature("wahlabend");
  const { user, loading } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["wahlen", user?.id ?? null],
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

  const zeilen = data?.elections ?? [];
  const { fokus, weitere } = geteilt(zeilen);
  // Erst drängen, wenn feststeht, dass niemand angemeldet ist — sonst
  // blitzt der Anreiz kurz auf und verschwindet (Designsprache: nichts
  // erscheinen lassen, was gleich wieder weg ist).
  const gesperrt = !loading && !user ? gesperrtesTippspiel(zeilen) : null;

  return (
    <>
      <Kopf label="Wahlen" />
      <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-5 sm:px-6">
        <h1 className="sr-only">Wahlen in Oldenburg</h1>
        {isLoading ? <div className="h-56 animate-pulse rounded-3xl bg-muted" /> : null}
        {fokus ? <Buehne z={fokus} /> : null}
        {gesperrt ? <Anreiz z={gesperrt} /> : null}

        {weitere.length > 0 ? (
          <section className="mt-9">
            <h2 className="font-display text-[17px] font-bold tracking-tight">Weitere Wahlen</h2>
            {nachJahren(weitere).map((g, gi) => (
              <div key={g.jahr} className="mt-4">
                <p className={KICKER}>{g.jahr}</p>
                <ol className="mt-2 flex flex-col gap-2.5">
                  {g.zeilen.map((z, i) => (
                    <Zeile key={z.slug} z={z} i={gi * 3 + i} />
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
