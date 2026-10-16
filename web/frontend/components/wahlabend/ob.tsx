"use client";

// /wahlabend/ob — der erste Wahlgang der OB-Wahl.
//
// Bis 10/2026 hatte er keine eigene Seite: Am Abend stand die Ratswahl auf
// /wahlabend, zwei Wochen später die Stichwahl auf /wahlabend/stichwahl, und
// in der Übersicht /wahlen war er die einzige gelaufene Wahl ohne Link (Tims
// Befund 16.10.2026). Hier steht er als Ergebnis — eine Rangliste aller
// Kandidaturen, kein Live-Abend: Den gibt es nicht mehr nachzuspielen.
//
// Alles Gerechnete kommt vom Backend (`GET /api/wahlabend/ob`, dieselbe Form
// wie die Stichwahl). Hier steht nur, was die Anzeige daraus macht.

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Mascot } from "@/components/mascot";
import { KICKER } from "@/components/wahlabend/bausteine";
import { Herkunft } from "@/components/wahlabend/stichwahl";
import { ZurueckZuWahlen } from "@/components/wahlen/zurueck";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";
import { datumLang, nachStimmen, type Stichwahl, type StichwahlKandidat } from "@/lib/stichwahl";

type ObWahl = Stichwahl;

function farbe(k: StichwahlKandidat): string {
  return `light-dark(${k.color || "#6b7a8c"}, ${k.color_dark || "#a3b1c2"})`;
}

/** Wer die Kandidatur eingereicht hat. Der Votemanager führt Einzelbewerbungen
 *  unter der „Partei" Einzelwahlvorschlag — „vorgeschlagen von
 *  Einzelwahlvorschlag" wäre Unsinn. */
function vorschlag(k: StichwahlKandidat): string {
  if (!k.party || /einzel/i.test(k.party)) return "Einzelwahlvorschlag";
  return `vorgeschlagen von ${k.party}`;
}

function Zeile({ k, rang, max, stichwahl }: { k: StichwahlKandidat; rang: number; max: number; stichwahl: boolean }) {
  // Der Balken misst gegen die stärkste Kandidatur, nicht gegen 100 %: Bei
  // neun Namen wären sonst sieben davon kaum zu sehen.
  const breite = max > 0 ? Math.max(0, Math.min(1, (k.share_pct ?? 0) / max)) : 0;
  return (
    <li className="py-4 first:pt-0 last:pb-0" data-testid="ob-kandidat" data-slug={k.slug}>
      <div className="flex items-start gap-3">
        <span className="w-5 flex-none pt-0.5 text-right font-mono text-[12px] tabular-nums text-muted-foreground">{rang}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <p className={KICKER}>{vorschlag(k)}</p>
              <h3 className="mt-0.5 font-display text-[17px] font-bold tracking-tight">
                {k.name}
                {stichwahl ? (
                  <span className="ml-2 inline-block rounded-md bg-foreground px-1.5 py-0.5 align-middle font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-background">
                    Stichwahl
                  </span>
                ) : null}
              </h3>
            </div>
            <p className="flex-none font-display text-[22px] font-bold tabular-nums">{prozent(k.share_pct)}</p>
          </div>
          <Herkunft k={k} />
          <div className="mt-2 flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
              <div
                className="h-full w-full origin-left rounded-full"
                style={{ transform: `scaleX(${breite})`, background: farbe(k) }}
              />
            </div>
            <span className="flex-none whitespace-nowrap text-right text-[12.5px] tabular-nums text-muted-foreground">
              {zahl(k.votes)} Stimmen
            </span>
          </div>
        </div>
      </div>
    </li>
  );
}

function Hinweis({ titel, text }: { titel: string; text: string }) {
  return (
    <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
      <Mascot pose="sleep" className="h-28 w-28" decorative />
      <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">{titel}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

export function ObWahlView() {
  const frei = useFeature("wahlabend");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["wahlabend-ob"],
    queryFn: () => api.get<ObWahl>("/wahlabend/ob"),
    enabled: frei,
    staleTime: 5 * 60_000,
  });

  if (!frei || (isError && !data)) {
    return (
      <div className="mx-auto w-full max-w-3xl pb-6">
        <ZurueckZuWahlen />
        <Hinweis titel="Das Ergebnis ist gerade nicht abrufbar" text="Die Zahlen kommen vom Votemanager der Stadt. Versuch es in ein paar Minuten noch einmal." />
      </div>
    );
  }
  if (isLoading || !data) {
    return (
      <div className="mx-auto w-full max-w-3xl pb-6">
        <ZurueckZuWahlen />
        <div className="mt-10 h-72 animate-pulse rounded-2xl bg-muted" />
      </div>
    );
  }

  const kandidaten = nachStimmen(data.candidates);
  const max = Math.max(0, ...kandidaten.map((k) => k.share_pct ?? 0));
  const inStichwahl = new Set(data.runoff);
  const namen = kandidaten.filter((k) => inStichwahl.has(k.slug)).map((k) => k.name);
  const gewaehlt = data.elected ? kandidaten.find((k) => k.slug === data.elected) : undefined;
  const fertig = data.phase === "complete";

  return (
    <div className="mx-auto w-full max-w-3xl pb-6">
      <ZurueckZuWahlen />
      <header className="mt-4">
        <p className={KICKER}>Erster Wahlgang · {datumLang(data.election.date)}</p>
        {/* Der amtliche Titel („Wahl der Oberbürgermeisterin / Wahl des
            Oberbürgermeisters - Stadt Oldenburg") ist für eine Überschrift zu lang. */}
        <h1 className="mt-1 font-display text-[26px] font-bold tracking-tight sm:text-[30px]">
          Oberbürgermeisterwahl {data.election.date.slice(0, 4)}
        </h1>
        <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-[13px]">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{prozent(data.turnout_pct)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{zahl(data.valid_votes)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Kandidaturen</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{kandidaten.length}</dd>
          </div>
        </dl>
      </header>

      {namen.length ? (
        <section className="mt-6 rounded-2xl border border-border bg-card p-5" data-testid="ob-stichwahl-hinweis">
          <p className="text-[14px] leading-relaxed">
            <strong className="font-semibold">Niemand erreichte mehr als die Hälfte der Stimmen.</strong> In die Stichwahl
            gingen {namen.join(" und ")}.
          </p>
          <Link href="/wahlabend/stichwahl" className="mt-2 inline-block text-sm font-medium text-primary">
            Zum Ergebnis der Stichwahl →
          </Link>
        </section>
      ) : gewaehlt ? (
        <section className="mt-6 rounded-2xl border border-border bg-card p-5">
          <p className="text-[14px] leading-relaxed">
            <strong className="font-semibold">Gewählt ist {gewaehlt.name}</strong> mit {prozent(gewaehlt.share_pct)}.
          </p>
        </section>
      ) : null}

      <section className="mt-6 rounded-2xl border border-border bg-card p-5 sm:p-6" aria-labelledby="ob-rangliste">
        <h2 id="ob-rangliste" className={cn(KICKER, "mb-4")}>
          Alle Kandidaturen nach Stimmen
        </h2>
        <ol className="divide-y divide-border">
          {kandidaten.map((k, i) => (
            <Zeile key={k.slug} k={k} rang={i + 1} max={max} stichwahl={inStichwahl.has(k.slug)} />
          ))}
        </ol>
      </section>

      <p className="mt-4 text-[12.5px] leading-relaxed text-muted-foreground">
        Über jedem Namen steht die Partei oder Wählergruppe, die den Wahlvorschlag eingereicht hat. Das sagt nicht
        automatisch aus, ob die kandidierende Person dort Mitglied ist oder von welchen weiteren Parteien sie unterstützt
        wird.
      </p>

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
          Stadt Oldenburg.{" "}
          {fertig ? "Das amtliche Endergebnis stellt der Wahlausschuss fest. " : "Die Auszählung läuft noch. "}
          <a href={data.election.presentation_url} className="font-medium text-primary" target="_blank" rel="noopener noreferrer">
            Zur amtlichen Ergebnispräsentation
          </a>
        </p>
      </footer>
    </div>
  );
}
