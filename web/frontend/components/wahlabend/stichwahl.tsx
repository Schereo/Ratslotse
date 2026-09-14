"use client";

// /wahlabend/stichwahl — die Stichwahl um das Oberbürgermeisteramt.
//
// Warum eine eigene Seite und kein Reiter auf /wahlabend: Es ist eine andere
// Wahl, zwei Wochen später, mit einer anderen Frage. Auf /wahlabend steht
// weiter die Ratswahl — die bleibt auch am 27. September das, was Leute dort
// suchen.
//
// Alles Gerechnete kommt vom Backend (`GET /api/wahlabend/stichwahl`): Zahlen,
// Auszählungsstand, der Vergleich mit dem ersten Wahlgang. Hier steht nur, was
// die Anzeige daraus macht.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Mascot } from "@/components/mascot";
import { Kopf } from "@/components/wahlabend/kopf";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { useTween } from "@/lib/use-tween";
import { cn } from "@/lib/utils";
import { prozent, uhrzeit, zahl } from "@/lib/wahlabend";
import {
  abfragePfad,
  abstandStimmen,
  datumLang,
  fuehrend,
  nachStimmen,
  verschiebung,
  vorsprung,
  zeitlage,
  type Stichwahl,
  type StichwahlKandidat,
} from "@/lib/stichwahl";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Die Farbe der Liste — oder ein neutraler Ton, wenn die Kandidatur zu
 *  keiner gehört. Zwei Farbwerte, weil der Hellmodus einen dunkleren braucht. */
function farbe(k: StichwahlKandidat): { hell: string; dunkel: string } {
  return { hell: k.color || "#6b7a8c", dunkel: k.color_dark || "#a3b1c2" };
}

/* ── Anzeigetafel ───────────────────────────────────────────────────────── */

function Tafel({ daten }: { daten: Stichwahl }) {
  const zeit = zeitlage(daten.election.polls_close);
  const beteiligung = useTween(daten.turnout_pct);
  const anteil = daten.reports_expected > 0 ? Math.round((daten.reports_received / daten.reports_expected) * 100) : 0;
  const phase =
    daten.phase === "before"
      ? "Noch nichts ausgezählt"
      : daten.phase === "complete"
        ? "Alle Wahlbezirke ausgezählt"
        : `${zahl(daten.reports_received)} von ${zahl(daten.reports_expected)} Wahlbezirken ausgezählt`;
  return (
    <section className="hh-tafel mt-5 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        {/* `basis` statt nur `flex-1`: Auf 400 px schiebt sich die
            Kennzahlen-Spalte sonst NEBEN die Überschrift und drückt sie auf
            ein Wort je Zeile zusammen. Mit einer Mindestbreite bricht die
            Zeile stattdessen um — gemessen an einem iPhone-Ausschnitt. */}
        <div className="min-w-0 flex-1 basis-[18rem]">
          <p className={KICKER}>
            Oldenburg · {datumLang(daten.election.date)} ·{" "}
            <span suppressHydrationWarning>{daten.dataset === "probe" ? "Generalprobe" : zeit.kicker}</span>
          </p>
          <h1 className="mt-1 font-display text-[28px] font-bold leading-none tracking-tight sm:text-[32px]">Stichwahl</h1>
          <p className="mt-3 text-[14px] text-foreground">
            <strong className="font-semibold">{phase}</strong>
            {daten.fetched_at ? <span className="text-muted-foreground"> · Stand {uhrzeit(daten.fetched_at) ?? "–"} Uhr</span> : null}
          </p>
          <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-foreground/10">
            <div className="h-full rounded-full bg-primary transition-[width] duration-weg" style={{ width: `${anteil}%` }} />
          </div>
          <p className="mt-2 text-[11.5px] text-muted-foreground">
            {daten.dataset === "probe"
              ? "Geprobt wird mit den Zahlen des ersten Wahlgangs — live fragt die Seite jede Minute nach."
              : daten.ok
                ? zeit.phase === "laeuft"
                  ? "Die Seite fragt jede Minute nach."
                  : `Ab ${zeit.tage === 0 ? "heute" : "Sonntag"} 18 Uhr fragt die Seite jede Minute nach.`
                : (daten.error ?? "Der Votemanager antwortet gerade nicht.")}
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-left sm:text-right">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{prozent(beteiligung)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{zahl(daten.valid_votes)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

/* ── Die beiden ─────────────────────────────────────────────────────────── */

/** Was der Parteiname über dem Namen NICHT sagt: ob die Person Mitglied ist,
 *  und wer sie sonst noch unterstützt.
 *
 *  Beides steht nicht in der amtlichen Bekanntmachung — das Backend liefert
 *  es nur mit eigener Quelle, und die steht hier als Beleg daneben. Ohne
 *  Angaben bleibt die Zeile weg; sie ist kein Platzhalter. */
function Herkunft({ k }: { k: StichwahlKandidat }) {
  const teile = [
    k.independent ? "parteilos" : null,
    k.supported_by.length ? `unterstützt von ${k.supported_by.join(", ")}` : null,
  ].filter(Boolean);
  if (!teile.length) return null;
  return (
    <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
      {teile.join(" · ")}
      {k.note_source ? (
        <>
          {" "}
          <a
            href={k.note_source}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            Beleg ↗
          </a>
        </>
      ) : null}
    </p>
  );
}

function Person({ k, fuehrt, fertig, probe }: { k: StichwahlKandidat; fuehrt: boolean; fertig: boolean; probe: boolean }) {
  const c = farbe(k);
  const anteil = useTween(k.share_pct);
  const stimmen = useTween(k.votes);
  const diff = verschiebung(k);
  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-card p-5 transition-colors sm:p-6",
        fuehrt ? "border-foreground/25 shadow-sm" : "border-border",
      )}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-1.5"
        style={{ background: `light-dark(${c.hell}, ${c.dunkel})` }}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* „vorgeschlagen von", nicht bloß der Parteiname: Auf dem
              Stimmzettel steht je Kandidatur genau eine Liste, und wer sie
              aufgestellt hat, muss weder ihr Mitglied sein noch ihre einzige
              Unterstützung haben (Tims Hinweis 14.09.2026 zu Jascha Rohr). */}
          <p className={KICKER}>
            {k.party ? `vorgeschlagen von ${k.party}` : "Einzelwahlvorschlag"}
          </p>
          <h2 className="mt-1 truncate font-display text-[22px] font-bold tracking-tight sm:text-[26px]">{k.name}</h2>
          <Herkunft k={k} />
        </div>
        {fuehrt ? (
          <span className="flex-none rounded-md bg-foreground px-2 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-background">
            {fertig && !probe ? "Gewählt" : "Vorn"}
          </span>
        ) : null}
      </div>

      <p className="mt-4 font-display text-[44px] font-bold leading-none tabular-nums sm:text-[56px]">{prozent(anteil)}</p>
      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-foreground/10">
        <div
          className="h-full rounded-full transition-[width] duration-weg"
          style={{ width: `${Math.max(0, Math.min(100, k.share_pct ?? 0))}%`, background: `light-dark(${c.hell}, ${c.dunkel})` }}
        />
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-[13px]">
        <div>
          <dt className={KICKER}>Stimmen</dt>
          <dd className="mt-0.5 font-semibold tabular-nums">{zahl(stimmen)}</dd>
        </div>
        <div>
          <dt className={KICKER}>1. Wahlgang</dt>
          <dd className="mt-0.5 tabular-nums text-muted-foreground">
            {prozent(k.first_round_pct)}
            {diff !== null ? (
              <span className="ml-1.5 font-mono text-[11px] text-signal">
                {diff > 0 ? "+" : diff < 0 ? "−" : "±"}
                {Math.abs(diff).toFixed(1).replace(".", ",")}
              </span>
            ) : null}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function Abstand({ daten }: { daten: Stichwahl }) {
  const punkte = vorsprung(daten.candidates);
  const stimmen = abstandStimmen(daten.candidates);
  if (punkte === null || stimmen === null || daten.phase === "before") return null;
  const vorn = fuehrend(daten.candidates);
  const name = daten.candidates.find((k) => k.slug === vorn)?.name;
  return (
    <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
      {name ? (
        <>
          <strong className="font-semibold text-foreground">{name}</strong> liegt {zahl(stimmen)} Stimmen vorn — das sind{" "}
          {punkte.toFixed(1).replace(".", ",")} Prozentpunkte.
        </>
      ) : (
        <>Beide liegen gleichauf. Bei Stimmengleichheit entscheidet das Los (§ 45c Abs. 2 NKWG).</>
      )}
    </p>
  );
}

/* ── Zustände ohne Zahlen ───────────────────────────────────────────────── */

function Hinweisbild({ pose, titel, text }: { pose: "sleep" | "wave" | "confused"; titel: string; text: string }) {
  return (
    <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
      <Mascot pose={pose} className="h-28 w-28" decorative />
      <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">{titel}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

/* ── Seite ──────────────────────────────────────────────────────────────── */

export function StichwahlView() {
  const params = useSearchParams();
  const probe = params.get("probe");
  const counted = params.get("counted");
  const frei = useFeature("wahlabend");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["stichwahl", probe, counted],
    queryFn: () => api.get<Stichwahl>(abfragePfad(probe, counted)),
    enabled: frei,
    refetchInterval: 60_000,
    retry: 1,
  });

  if (!frei || isError) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
          <Hinweisbild
            pose="sleep"
            titel="Die Stichwahl ist noch nicht offen"
            text="Diese Seite zeigt ab dem 27. September ab 18 Uhr den Auszählungsstand. Bis dahin gibt es hier nichts zu sehen."
          />
        </main>
      </>
    );
  }
  if (isLoading || !data) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
          <div className="mt-10 h-40 animate-pulse rounded-2xl bg-muted" />
        </main>
      </>
    );
  }

  const sortiert = nachStimmen(data.candidates);
  const vorn = fuehrend(data.candidates);
  const fertig = data.phase === "complete";

  return (
    <>
      <Kopf label="Stichwahl" />
      <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
        {data.dataset === "probe" ? (
          <p className="mt-4 rounded-xl border border-amber-300/50 bg-amber-50 px-4 py-2.5 text-[13px] text-amber-900 dark:border-amber-700/40 dark:bg-amber-900/25 dark:text-amber-100">
            <strong className="font-semibold">Generalprobe.</strong> Die Zahlen sind die des ersten Wahlgangs vom
            13. September, umgerechnet auf die beiden verbliebenen Namen. Nichts davon ist ein Ergebnis vom 27. September.
          </p>
        ) : null}

        <Tafel daten={data} />

        <section className="mt-5 grid gap-4 sm:grid-cols-2">
          {sortiert.map((k) => (
            <Person key={k.slug} k={k} fuehrt={k.slug === vorn} fertig={fertig} probe={data.dataset === "probe"} />
          ))}
        </section>
        <Abstand daten={data} />

        {/* Einmal für beide, statt an einer Karte: Die Angabe über dem Namen
            ist der Wahlvorschlag. Wer das nicht weiß, liest sie als
            Parteibuch. */}
        <p className="mt-4 text-[12.5px] leading-relaxed text-muted-foreground">
          Über jedem Namen steht, wer die Kandidatur <strong className="font-semibold text-foreground">vorgeschlagen</strong> hat.
          Auf dem Stimmzettel ist je Kandidatur genau eine Liste zugelassen — wer dort steht, muss weder deren Mitglied
          sein noch ihre einzige Unterstützung haben.
        </p>

        {data.phase === "before" ? (
          <p className="mt-6 rounded-xl border border-border bg-muted/40 px-4 py-3 text-[13.5px] leading-relaxed text-muted-foreground">
            Am 13. September hat niemand die absolute Mehrheit erreicht. Am {datumLang(data.election.date)} entscheidet
            deshalb die Stichwahl zwischen den beiden Bestplatzierten. Die Zahlen erscheinen hier, sobald die Stadt die
            ersten Wahlbezirke meldet.
          </p>
        ) : null}

        {data.notes.length > 0 ? (
          <ul className="mt-5 space-y-1.5 text-[12.5px] text-muted-foreground">
            {data.notes.map((n: string) => (
              <li key={n}>· {n}</li>
            ))}
          </ul>
        ) : null}

        <footer className="mt-10 border-t border-border pt-4 text-[12.5px] leading-relaxed text-muted-foreground">
          <p className="max-w-[76ch]">
            <strong className="font-semibold text-foreground">Quelle:</strong> Ergebnisdarstellung des Votemanagers der
            Stadt Oldenburg, jede Minute abgerufen. Die Stichwahl hat — anders als die Ratswahl — keine
            Open-Data-Datei. Kein amtliches Ergebnis; das stellt der Wahlausschuss fest.{" "}
            <a href={data.election.presentation_url} className="font-medium text-primary" target="_blank" rel="noopener noreferrer">
              Zur amtlichen Ergebnispräsentation
            </a>
          </p>
          <p className="mt-2">
            <Link href="/wahlabend" className="font-medium text-primary">
              ← Zum Wahlabend der Ratswahl
            </Link>
          </p>
        </footer>
      </main>
    </>
  );
}
