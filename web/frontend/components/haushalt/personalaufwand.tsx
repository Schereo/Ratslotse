"use client";

// Der Personalaufwand als Zahl — auf der Seite, die bis dahin nur behauptete,
// Personal sei „der größte Aufwandsbereich der Stadt". Gemessen stimmt das
// nicht einmal: 2024 lagen die Transferaufwendungen (323,7 Mio. €) vor den
// Personalaufwendungen (184,8 Mio. €). Deshalb rechnet dieser Baustein den
// Rang aus den Posten 13–19 der Ergebnisrechnung, statt ihn zu schreiben.
//
// Drei Zahlen, drei Quellen, keine Mischung:
//   * das Ist des jüngsten Jahresabschlusses (Posten 13, Kernverwaltung),
//     dazu der Anteil an allen ordentlichen Aufwendungen (Posten 20),
//   * der Ansatz des jüngsten Haushaltsplans (Gesamtergebnishaushalt, nur der
//     Ansatz für das eigene Planjahr — nie die Finanzplanung),
//   * Plan gegen Ist je abgeschlossenem Jahr als Hantel, mit der
//     Bezugsgröße des Jahrgangs im Fähnchen (2018 und 2020 rechnet der
//     Abschluss gegen den fortgeschriebenen Plan, nicht den Ansatz).
//
// Die Versorgungsaufwendungen (Posten 14, Pensionen) stehen bewusst daneben
// und nicht in der Zahl: Der Abschluss führt sie als eigenen Posten, und wer
// beides addiert, verliert den Anschluss an die Kennzahl „Personalintensität"
// des Rechenschaftsberichts, die genau diese Trennung macht.

import { Hantel, type HantelZeile } from "@/components/grafik/hantel";
import { Einordnung } from "@/components/grafik/einordnung";
import {
  PLAN_ART_LABEL, amount, deMio,
  type ErgebnishaushaltZeile, type ErgebnisPosten,
} from "@/lib/haushalt";

const PERSONAL = 13;
const VERSORGUNG = 14;
const TRANSFER = 18;
const SUMME_AUFWAND = 20;

export function Personalaufwand({ statement, budget, beleg, belegPlan }: {
  /** Die Ergebnisrechnung — nur die Kernverwaltung (`sub_budget_no === null`)
   *  wird gelesen; Teilhaushalts-Zeilen dürfen mitkommen und werden ignoriert. */
  statement: ErgebnisPosten[];
  /** Der Gesamtergebnishaushalt aller Planjahre. */
  budget: ErgebnishaushaltZeile[];
  /** Beleg-Chip-Slots (GB-00) — die Seite wählt die Quellen. */
  beleg?: React.ReactNode;
  belegPlan?: React.ReactNode;
}) {
  const kern = statement.filter((z) => z.sub_budget_no === null);
  const posten = (nr: number, year: number) =>
    kern.find((z) => z.nr === nr && z.year === year) ?? null;
  const jahre = [...new Set(
    kern.filter((z) => z.nr === PERSONAL && z.result != null).map((z) => z.year),
  )].sort((a, b) => a - b);
  const letztes = jahre.at(-1);
  if (!letztes) return null;

  const ist = posten(PERSONAL, letztes)!;
  const summe = posten(SUMME_AUFWAND, letztes);
  const versorgung = posten(VERSORGUNG, letztes);
  const anteil = summe?.result ? ((ist.result as number) / summe.result) * 100 : null;

  // Der Rang, gemessen an den Aufwandsposten desselben Abschlusses.
  const aufwand = kern
    .filter((z) => z.year === letztes && z.nr >= PERSONAL && z.nr < SUMME_AUFWAND
      && z.result != null)
    .sort((a, b) => (b.result as number) - (a.result as number));
  const rang = aufwand.findIndex((z) => z.nr === PERSONAL) + 1;
  const vorne = aufwand[0];

  // Der Ansatz des jüngsten Haushalts für sein eigenes Jahr. `kind === "budget"`
  // ist die Sperre gegen die Finanzplanung (siehe Typ-Kommentar).
  const planJahr = budget.reduce(
    (m, b) => (b.kind === "budget" ? Math.max(m, b.plan_budget_year) : m), 0) || null;
  const planZeile = (nr: number) => planJahr
    ? budget.find((b) => b.kind === "budget" && b.plan_budget_year === planJahr
        && b.year === planJahr && b.nr === nr) ?? null
    : null;
  const plan = planZeile(PERSONAL);
  const planSumme = planZeile(SUMME_AUFWAND);
  const planAnteil = plan && planSumme?.amount ? (plan.amount / planSumme.amount) * 100 : null;

  // Beide Enden müssen da sein — eine Hantel mit einem Ende ist ein Punkt.
  const hantel: HantelZeile[] = jahre
    .map((y) => posten(PERSONAL, y)!)
    .filter((z) => z.plan != null && z.plan > 0)
    .map((z) => ({
      label: String(z.year),
      plan: (z.plan as number) / 1e6,
      ist: (z.result as number) / 1e6,
      // Nur die Ausnahme steht an der Zeile: Der nackte Ansatz ist die Regel
      // und steht einmal unter der Grafik — acht gleiche Zeilen „Verglichen
      // wird gegen: Haushaltsansatz" trugen nichts (Durchsicht 02.09.2026).
      einordnung: z.plan_kind && z.plan_kind !== "budget"
        ? `Verglichen wird gegen: ${PLAN_ART_LABEL[z.plan_kind]}.`
        : null,
    }));

  const kern1 = amount(ist.result);

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was das Personal kostet{beleg}
        </h2>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          Jahresabschluss {letztes} · Kernverwaltung
        </span>
      </div>

      <div className="mt-3 grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <p className="font-display text-[30px] font-bold leading-none tabular-nums">
            {kern1.value}<span className="ml-1.5 text-[15px] font-semibold text-muted-foreground">{kern1.unit}</span>
          </p>
          <p className="mt-1.5 max-w-[46ch] text-[12.5px] leading-relaxed text-foreground/85">
            Personalaufwendungen {letztes}
            {anteil != null && summe?.result != null && (
              <> — {deMio(anteil)}&nbsp;% aller ordentlichen Aufwendungen
                ({deMio(summe.result / 1e6)}&nbsp;Mio.&nbsp;€)</>
            )}
            {versorgung?.result != null && (
              <>. Dazu kommen {deMio(versorgung.result / 1e6)}&nbsp;Mio.&nbsp;€
                Versorgungsaufwendungen für Pensionen, die der Abschluss getrennt führt</>
            )}.
          </p>
        </div>
        {plan && (
          <div className="border-t border-dashed border-border pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Plan {planJahr}{belegPlan}
            </p>
            <p className="mt-1 font-display text-[22px] font-bold leading-none tabular-nums">
              {amount(plan.amount).value}<span className="ml-1 text-[13px] font-semibold text-muted-foreground">{amount(plan.amount).unit}</span>
            </p>
            <p className="mt-1.5 max-w-[40ch] text-[12px] leading-relaxed text-muted-foreground">
              Ansatz des Verwaltungsentwurfs{planAnteil != null && planSumme?.amount != null
                ? <> — {deMio(planAnteil)}&nbsp;% der geplanten Aufwendungen
                  ({deMio(planSumme.amount / 1e6)}&nbsp;Mio.&nbsp;€)</>
                : null}. Ein Plan, kein Ergebnis: Was daraus wird, steht erst im
              Jahresabschluss {planJahr}.
            </p>
          </div>
        )}
      </div>

      {hantel.length >= 2 && (
        <div className="mt-4 border-t border-dashed border-border pt-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Geplant und geworden · {hantel[0].label}–{hantel[hantel.length - 1].label}
          </p>
          <div className="mt-2">
            <Hantel
              zeilen={hantel}
              unit="Mio. €"
              sortierung="alpha"
              wovon="der Personalaufwand"
              keineWertung={
                <>Mehr Personalaufwand als geplant kann ein Tarifabschluss sein oder
                  eine Stelle mehr, die besetzt wurde; weniger heißt oft, dass Stellen
                  unbesetzt blieben — wie viele, zeigt die Waffel oben. Die Farbe
                  bewertet nichts.</>
              }
              beleg={beleg}
            />
          </div>
        </div>
      )}

      <div className="mt-3 border-t border-dashed border-border pt-3">
        <Einordnung
          satz={
            rang === 1
              ? <>Der Personalaufwand ist {letztes} der größte Aufwandsposten
                  der Kernverwaltung.</>
              : <>Der Personalaufwand ist {letztes} der {rang}.-größte Aufwandsposten
                  der Kernverwaltung — vorn liegen {vorne.nr === TRANSFER
                    ? <>die Transferaufwendungen ({deMio((vorne.result as number) / 1e6)}&nbsp;Mio.&nbsp;€):
                      Sozialleistungen, Zuschüsse und Umlagen, die die Stadt weitergibt</>
                    : <>{vorne.label} ({deMio((vorne.result as number) / 1e6)}&nbsp;Mio.&nbsp;€)</>}.</>
          }
          gemessen={`Posten 13 bis 19 der Ergebnisrechnung ${letztes}`}
          nichtAussagen={[
            "Was eine einzelne Besoldungs- oder Entgeltgruppe kostet, weist der Jahresabschluss nicht aus — hier steht nur die Summe.",
            "Klinikum, Bäder, Busse und Gebäudewirtschaft zahlen ihr Personal aus eigenen Wirtschaftsplänen; sie stehen hier nicht drin.",
          ]}
        />
      </div>
    </section>
  );
}
