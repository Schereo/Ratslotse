"use client";

// Der Haushaltsvollzug: was die Verwaltung im laufenden Jahr erwartet.
//
// Der Bereich zeigte bis 02.09.2026 den Plan für das kommende Jahr und den
// Abschluss von vorvorletztem — dazwischen nichts. Genau dazwischen berichtet
// die Stadt vierteljährlich (§ 31 KomHKVO): zum 30.06., 30.09. und 31.12.,
// was sie bis zum Jahresende erwartet. Dieser Baustein zeigt das, wo es
// hingehört — auf „Geplant und geworden", VOR den abgeschlossenen Jahren:
// erst die Erwartung, dann das Ergebnis.
//
// Drei Regeln, aus dem Modul und dem Endpunkt übernommen:
//   * Prognose heißt Prognose. Die Hantel sagt „geplant → erwartet", nie
//     „tatsächlich" — was am Ende herauskam, steht im Jahresabschluss weiter
//     unten, und der kommt zwei Jahre später.
//   * Die Ansatz-Basis wechselt 2021 (bis dahin mit Ermächtigungsübertragung).
//     Wo ein Jahrgang die alte Basis führt, steht der Satz dazu an der Zahl.
//   * Nur die Kernverwaltung, kein Ist zum Stichtag, kein erstes Quartal —
//     die Grenzen stehen als Einordnung dabei, nicht im Kleingedruckten.

import { useMemo, useState } from "react";
import { Segmented } from "@/components/ui";
import { Hantel, type HantelZeile } from "@/components/grafik/hantel";
import { Einordnung } from "@/components/grafik/einordnung";
import { deMio } from "@/lib/haushalt";
import {
  bereiche, deMioSigned, deStichtag, deStichtagKurz, ergebnisWort, stichtageDesJahres,
  summe, verlauf, type VollzugDaten, type VollzugHaushalt,
} from "@/lib/haushalt-vollzug";
import { cn } from "@/lib/utils";

export function Vollzug({ daten, year, onYear, beleg }: {
  daten: VollzugDaten;
  /** Der gewählte Jahrgang — die Teilhaushalts-Zeilen kommen nur für ihn. */
  year: number;
  onYear: (year: number) => void;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: React.ReactNode;
}) {
  const stichtage = useMemo(() => stichtageDesJahres(daten, year), [daten, year]);
  const [asOfWahl, setAsOf] = useState<string | null>(null);
  const [haushalt, setHaushalt] = useState<VollzugHaushalt>("result");
  // Der jüngste Stichtag des Jahrgangs, solange niemand einen anderen wählt —
  // und nie einer, den es in diesem Jahrgang nicht gibt.
  const asOf = stichtage.some((s) => s.as_of === asOfWahl)
    ? (asOfWahl as string) : stichtage.at(-1)?.as_of ?? null;
  const stichtag = stichtage.find((s) => s.as_of === asOf) ?? null;
  // Führt der Stichtag den gewählten Haushalt nicht (halbes Quartal), fällt
  // die Anzeige auf den anderen zurück und sagt es.
  const budget: VollzugHaushalt = stichtag?.budgets.includes(haushalt)
    ? haushalt : (stichtag?.budgets[0] ?? "result");

  if (!asOf || !stichtag) return null;

  const kern = summe(daten, year, asOf, budget, "result");
  const reihe = verlauf(daten, year, budget);
  const zeilen = bereiche(daten, year, asOf, budget, "result");
  const basisSatz = daten.plan_basis_note[stichtag.plan_basis];
  const alteBasis = stichtag.plan_basis === "budget_plus_carryover";

  const verlaufHantel: HantelZeile[] = reihe.map((z) => ({
    label: deStichtagKurz(z.as_of),
    plan: (z.budgeted as number) / 1e6,
    ist: (z.forecast as number) / 1e6,
    einordnung: null,
  }));
  const bereichHantel: HantelZeile[] = zeilen
    .filter((z) => z.budgeted != null && z.forecast != null)
    .map((z) => ({
      label: z.label,
      plan: (z.budgeted as number) / 1e6,
      ist: (z.forecast as number) / 1e6,
      einordnung: null,
    }));

  const abw = kern && kern.budgeted != null && kern.forecast != null
    ? kern.forecast - kern.budgeted : null;

  return (
    <section id="vollzug" className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Haushaltsvollzug · was die Verwaltung erwartet{beleg}
        </h2>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          Bericht zum {deStichtag(asOf)} · {daten.budget_names[budget]}
        </span>
      </div>

      {/* Jahrgang, Stichtag, Haushalt — drei Umschalter, weil es drei
          verschiedene Dinge sind. Der Jahrgang lädt die Teilhaushalte nach. */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
          <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
            {daten.editions.map((j) => (
              <button key={j} type="button" onClick={() => onYear(j)}
                className={cn("rounded-full px-3 py-1 text-[12.5px]",
                  j === year ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                {j}
              </button>
            ))}
          </div>
        </div>
        {stichtage.length > 1 && (
          <Segmented<string> value={asOf} onChange={setAsOf}
            options={stichtage.map((s) => ({ value: s.as_of, label: `zum ${deStichtagKurz(s.as_of)}` }))} />
        )}
        {stichtag.budgets.length > 1 && (
          <Segmented<VollzugHaushalt> value={budget} onChange={setHaushalt}
            options={[
              { value: "result", label: "Ergebnishaushalt" },
              { value: "cash", label: "Finanzhaushalt" },
            ]} />
        )}
      </div>

      {kern && kern.budgeted != null && kern.forecast != null && (
        <p className="mt-4 max-w-[72ch] text-[15px] leading-relaxed text-foreground">
          Zum <strong>{deStichtag(asOf)}</strong> erwartete die Verwaltung für {year} ein{" "}
          {ergebnisWort(budget)} von{" "}
          <strong className="tabular-nums">{deMioSigned(kern.forecast)}&nbsp;Mio.&nbsp;€</strong>
          {" — "}geplant waren{" "}
          <span className="tabular-nums">{deMioSigned(kern.budgeted)}&nbsp;Mio.&nbsp;€</span>
          {abw != null && Math.abs(abw) >= 50_000 && (
            <>, also{" "}
              <span className={cn("tabular-nums", abw !== 0 && "text-signal")}>
                {deMio(Math.abs(abw) / 1e6)}&nbsp;Mio.&nbsp;€ {abw > 0 ? "mehr" : "weniger"}
              </span>
              {" "}als im Plan</>
          )}.
        </p>
      )}
      {stichtag.budgets.length === 1 && (
        <p className="mt-1.5 text-[12px] text-muted-foreground">
          Für diesen Stichtag liegt nur der {daten.budget_names[budget]} lesbar vor.
        </p>
      )}
      {alteBasis && (
        <p className="mt-1.5 max-w-[72ch] text-[12px] leading-relaxed text-muted-foreground">
          {basisSatz}
        </p>
      )}

      {/* Der Verlauf über die Stichtage: dieselbe Hantel wie unten, nur je
          Stichtag statt je Bereich. Ein Jahrgang mit einem Stichtag braucht
          keinen Verlauf. */}
      {verlaufHantel.length >= 2 && (
        <div className="mt-4 border-t border-dashed border-border pt-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wie sich die Erwartung im Jahr bewegte · {ergebnisWort(budget)}
          </p>
          <div className="mt-2">
            <Hantel zeilen={verlaufHantel} unit="Mio. €" massstab="amount" sortierung="alpha"
              wovon="die Erwartung" istLabel="erwartet"
              keineWertung={
                <>Die Farbe bewertet nicht. Eine Erwartung, die im Jahr besser wird, kann
                  eine vorsichtige Planung sein oder mehr Gewerbesteuer — was es war, steht
                  in den Teilhaushalten darunter.</>
              } />
          </div>
        </div>
      )}

      {bereichHantel.length >= 2 && (
        <div className="mt-4 border-t border-dashed border-border pt-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wo die Erwartung vom Plan abweicht · {zeilen.length} Teilhaushalte · {ergebnisWort(budget)}
          </p>
          <div className="mt-2">
            <Hantel zeilen={bereichHantel} unit="Mio. €" massstab="amount" schwelle={6}
              wovon="der Bereich" istLabel="erwartet"
              keineWertung={
                <>Die Farbe bewertet nicht: Ein Bereich, der mehr erwartet als geplant, hat
                  meist mehr eingenommen (bei „Finanzmanagement und Recht" die Gewerbesteuer)
                  oder weniger ausgegeben; einer, der weniger erwartet, mehr Fälle oder
                  höhere Preise. Die Erwartung ist die der Ämter, nicht unsere.</>
              } />
          </div>
        </div>
      )}

      <div className="mt-3 border-t border-dashed border-border pt-3">
        <Einordnung
          satz={<>{daten.scope_note}</>}
          gemessen={`${stichtage.length} ${stichtage.length === 1 ? "Stichtag" : "Stichtage"} im Jahrgang ${year}`}
          nichtAussagen={[
            "Kein Ist zum Stichtag: Die Berichte nennen nicht, was bis dahin gebucht war, sondern was die Ämter bis zum 31. Dezember erwarten.",
            "Das erste Quartal fehlt: Der Bericht zum 31. März steht als andere Tabelle im Vorlagentext und wird nicht gelesen.",
            "Was am Jahresende wirklich herauskam, steht weiter unten im Jahresabschluss — für jedes Jahr, das einen hat.",
          ]}
        />
      </div>
    </section>
  );
}

/** Die kleine Karte für die Übersicht: der jüngste Stichtag in einem Satz,
 *  mit Sprung zum Baustein. Nur die Summenzeilen — die Übersicht braucht die
 *  Teilhaushalte nicht. */
export function VollzugKarte({ daten }: { daten: VollzugDaten }) {
  const s = daten.reporting_dates.at(-1);
  if (!s) return null;
  const budget: VollzugHaushalt = s.budgets.includes("result") ? "result" : s.budgets[0];
  const kern = summe(daten, s.budget_year, s.as_of, budget, "result");
  if (!kern || kern.budgeted == null || kern.forecast == null) return null;
  const abw = kern.forecast - kern.budgeted;
  return (
    <a href="/haushalt/plan-ist#vollzug"
      className="group block rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
        Zwischenstand {s.budget_year} · Bericht zum {deStichtag(s.as_of)}
      </p>
      <p className="mt-1.5 max-w-[60ch] text-[13.5px] leading-relaxed text-foreground">
        Die Verwaltung erwartet ein {ergebnisWort(budget)} von{" "}
        <strong className="tabular-nums">{deMioSigned(kern.forecast)}&nbsp;Mio.&nbsp;€</strong>
        {" "}statt der geplanten{" "}
        <span className="tabular-nums">{deMioSigned(kern.budgeted)}&nbsp;Mio.&nbsp;€</span>
        {Math.abs(abw) >= 50_000 && (
          <> — <span className="tabular-nums text-signal">{deMio(Math.abs(abw) / 1e6)}&nbsp;Mio.&nbsp;€ {abw > 0 ? "mehr" : "weniger"}</span></>
        )}.
      </p>
      <p className="mt-1.5 text-[12px] font-semibold text-primary group-hover:underline">
        Zum Haushaltsvollzug →
      </p>
    </a>
  );
}
