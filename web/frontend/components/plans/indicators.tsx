// KENNZAHL: was ein Plan messbar erreichen will, und was gemessen wurde
// (council/plan_indicators/*.json; docs/plan-ziele-plaene.md § 3.2 Nr. 5).
//
// Soll und Ist stehen je Jahr nebeneinander, jede Zahl mit ihrer Vorlage. Die
// Kennzahl steht NEBEN dem Plan, nicht als sein Ergebnis (§ 3.4 Nr. 4): Die
// Treibhausgasbilanz misst die Stadt, und der Bericht selbst nennt den
// bundesweiten Strommix als erste Ursache. Darum stehen die Vorbehalte des
// Berichts direkt unter der Tabelle, nicht in einer Fußnote.

import { Kicker } from "@/components/plans/parts";
import { formatAmount, formatChange, type PlanIndicator } from "@/lib/plans";

function Indicator({ indicator }: { indicator: PlanIndicator }) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="text-[15px] font-semibold leading-snug text-foreground">{indicator.label}</h3>
        <p className="font-mono text-meta text-muted-foreground">in {indicator.unit}</p>
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[26rem] border-collapse text-left text-meta tabular-nums">
          <thead>
            <tr className="border-b border-border/70 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
              <th scope="col" className="py-1.5 pr-3 font-normal">Jahr</th>
              <th scope="col" className="py-1.5 pl-3 text-right font-normal">Ziel</th>
              <th scope="col" className="py-1.5 pl-3 text-right font-normal">Gemessen</th>
              <th scope="col" className="py-1.5 pl-3 text-right font-normal">gegenüber {indicator.baseline_year}</th>
              <th scope="col" className="py-1.5 pl-3 text-right font-normal">Vorlage</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border/40">
              <th scope="row" className="py-1.5 pr-3 font-normal text-foreground">{indicator.baseline_year}</th>
              <td className="py-1.5 pl-3 text-right text-muted-foreground">–</td>
              <td className="py-1.5 pl-3 text-right text-foreground">{formatAmount(indicator.baseline_value)}</td>
              <td className="py-1.5 pl-3 text-right text-muted-foreground">Ausgangswert</td>
              <td className="py-1.5 pl-3 text-right font-mono text-muted-foreground">{indicator.baseline_template ?? "–"}</td>
            </tr>
            {indicator.rows.map((row) => (
              <tr key={row.year} className="border-b border-border/40 last:border-b-0">
                <th scope="row" className="py-1.5 pr-3 font-normal text-foreground">{row.year}</th>
                <td className="py-1.5 pl-3 text-right text-muted-foreground">
                  {row.target != null ? (
                    <>
                      {formatAmount(row.target)}
                      {row.target_change != null && <span className="block text-[11px]">{formatChange(row.target_change)}</span>}
                    </>
                  ) : "–"}
                </td>
                <td className="py-1.5 pl-3 text-right font-medium text-foreground">{row.actual != null ? formatAmount(row.actual) : "–"}</td>
                <td className="py-1.5 pl-3 text-right text-foreground">{row.actual_change != null ? formatChange(row.actual_change) : "–"}</td>
                <td className="py-1.5 pl-3 text-right font-mono text-muted-foreground">{row.template_number ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-meta text-muted-foreground">{indicator.baseline_label}.</p>
      {indicator.notes.length > 0 && (
        <ul className="mt-2 max-w-[76ch] space-y-1 text-hinweis text-muted-foreground">
          {indicator.notes.map((note) => (
            <li key={note.text}>
              {note.text}
              {note.template_number && <span className="font-mono"> ({note.template_number})</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Indicators({ indicators }: { indicators: readonly PlanIndicator[] }) {
  if (indicators.length === 0) return null;
  return (
    <section aria-labelledby="plan-indicators" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-indicators">Kennzahl</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">Nach Angaben der Verwaltung</p>
      </div>
      <p className="mb-4 max-w-[76ch] text-hinweis text-muted-foreground">
        Was der Plan messbar erreichen will, und was die Stadt gemessen hat.
      </p>
      <div className="space-y-6">
        {indicators.map((indicator) => <Indicator key={indicator.key} indicator={indicator} />)}
      </div>
    </section>
  );
}
