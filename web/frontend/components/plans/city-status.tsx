// STAND LAUT STADT: was die Stadt selbst über die Umsetzung meldet
// (council/plan_status/*.json; docs/plan-ziele-plaene.md § 3.3a, Baustein 2).
//
// Die Verteilung steht in den Worten der Stadt, je Stufe eine Zeile aus
// Kästchen — ein Kästchen je Maßnahme, wie in der Maßnahmenliste darunter.
// Daneben, was sich seit dem vorigen Bericht bewegt hat, und die Vorbehalte,
// die die Stadt selbst nennt.
//
// Was hier NICHT steht (§ 3.4): keine Quote, kein Fortschrittsbalken, kein
// Rot. Beim Klimaschutzplan wächst die Zählbasis, während „Realisiert“
// sinkt — eine Prozentzahl daraus wäre Scheinpräzision.
//
// Meldet die Stadt mehrere Stände, wählt ein Umschalter das Jahr — und die
// Kästchen WANDERN zwischen den Stufen, statt umzuspringen: Man sieht, wohin
// sich das Gewicht verschoben hat. Die Stadt meldet aber nur Summen je Stufe;
// welches Kästchen wandert, ist gerechnet (lib/plans.ts::squareTokens), und
// das steht dabei. Die Tabelle aller Stände liegt unter einem Aufklapper.

import { useMemo, useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Kicker, STATUS_SQUARE } from "@/components/plans/parts";
import { Segmented } from "@/components/ui/segmented";
import { useFlip } from "@/lib/flip";
import { signed, squareTokens, statusLabels, type PlanCityStatus, type PlanSnapshot, type PlanStatusNorm, type SquareToken } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** Die Verteilung eines Stands: je Stufe eine Zeile aus Kästchen. Die Zeilen sind die Stufen ALLER
 *  Stände — sonst spränge beim Wechsel des Jahres das Raster, in dem die Kästchen wandern sollen. */
function Distribution({ labels, norms, snapshot, tokens }: {
  labels: readonly string[]; norms: ReadonlyMap<string, PlanStatusNorm>; snapshot: PlanSnapshot; tokens: readonly SquareToken[];
}) {
  return (
    <ul className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-2">
      {labels.map((label) => {
        const count = snapshot.counts.find((c) => c.status_raw === label)?.count;
        return (
          <li key={label} className="col-span-3 grid grid-cols-subgrid items-start">
            <span className={cn("max-w-[11rem] break-words text-[14px] leading-snug", count ? "text-foreground" : "text-muted-foreground")}>{label}</span>
            <span aria-hidden className="flex min-h-[18px] flex-wrap gap-[3px] pt-[3px]">
              {tokens.filter((t) => t.label === label).map((t) => (
                <span key={t.id} data-flip={t.id} className={cn("h-3 w-3 rounded-[3px] border", STATUS_SQUARE[norms.get(label) ?? "unclear"])} />
              ))}
            </span>
            {/* Eine Stufe, die es in diesem Stand nicht gab, trägt einen Strich — keine Null. */}
            <span className="text-right font-mono text-meta tabular-nums text-foreground">{count ?? "–"}</span>
          </li>
        );
      })}
    </ul>
  );
}

function Movement({ movement }: { movement: NonNullable<PlanCityStatus["movement"]> }) {
  const moved = movement.counts.filter((c) => c.delta !== 0);
  if (moved.length === 0 && movement.total_delta === 0) {
    return <p className="text-hinweis text-muted-foreground">Seit {movement.since_label} unverändert.</p>;
  }
  return (
    <div className="min-w-0">
      <Kicker>Seit {movement.since_label}</Kicker>
      <ul className="mt-1.5 space-y-1 text-[14px] leading-snug text-foreground">
        {movement.total_delta !== 0 && (
          <li>
            Zählbasis: <span className="tabular-nums">{movement.total_before} → {movement.total_before + movement.total_delta}</span> Maßnahmen
          </li>
        )}
        {moved.map((c) => (
          <li key={c.status_raw}>
            {c.status_raw}: <span className="tabular-nums">{c.before} → {c.count}</span>{" "}
            <span className="font-mono text-meta tabular-nums text-muted-foreground">({signed(c.delta)})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Series({ status }: { status: PlanCityStatus }) {
  const labels = statusLabels(status.series);
  return (
    <div className="min-w-0">
      <div className="overflow-x-auto pb-1">
        <table className="w-full min-w-[24rem] border-collapse text-left text-meta tabular-nums">
          <thead>
            <tr className="border-b border-border/70 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
              <th scope="col" className="py-1.5 pr-3 font-normal">Stand</th>
              {status.series.map((s) => <th key={s.as_of} scope="col" className="py-1.5 pl-3 text-right font-normal">{s.as_of_label}</th>)}
            </tr>
          </thead>
          <tbody>
            {labels.map((label) => (
              <tr key={label} className="border-b border-border/40">
                <th scope="row" className="py-1.5 pr-3 font-normal text-foreground">{label}</th>
                {status.series.map((s) => (
                  <td key={s.as_of} className="py-1.5 pl-3 text-right text-foreground">
                    {s.counts.find((c) => c.status_raw === label)?.count ?? "–"}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row" className="py-1.5 pr-3 font-medium text-foreground">Maßnahmen</th>
              {status.series.map((s) => <td key={s.as_of} className="py-1.5 pl-3 text-right font-medium text-foreground">{s.total}</td>)}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CityStatus({ status }: { status: PlanCityStatus }) {
  const series = status.series;
  const several = series.length > 1;
  // Der jüngste Stand zuerst — das ist die Frage, mit der man herkommt.
  const [asOf, setAsOf] = useState(series[series.length - 1]?.as_of ?? status.as_of);
  const [showTable, setShowTable] = useState(false);
  const { root, capture } = useFlip<HTMLDivElement>(asOf, "buehne");
  const { labels, norms, tokens } = useMemo(() => {
    const norms = new Map<string, PlanStatusNorm>();
    for (const s of series) for (const c of s.counts) norms.set(c.status_raw, c.status_norm);
    return { labels: statusLabels(series), norms, tokens: squareTokens(series) };
  }, [series]);
  const at = Math.max(0, series.findIndex((s) => s.as_of === asOf));
  const snapshot = series[at];
  if (!snapshot) return null;
  const counted = snapshot.counts.reduce((n, c) => n + c.count, 0);
  const latest = at === series.length - 1;
  return (
    <section aria-labelledby="plan-city-status" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-city-status">Stand laut Stadt</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">{status.origin_label} · Stand {snapshot.as_of_label}</p>
      </div>
      <p className="mb-3 max-w-[76ch] text-hinweis text-muted-foreground">
        {counted >= snapshot.total
          ? `So ${latest ? "ordnet" : "ordnete"} die Stadt ihre ${snapshot.total} Maßnahmen selbst ein.`
          : `Die Stadt ${latest ? "ordnet" : "ordnete"} ${counted} von ${snapshot.total} Maßnahmen ein; für die übrigen ${latest ? "nennt" : "nannte"} sie keinen Stand.`}
      </p>
      {several && (
        <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Segmented value={asOf} tone="primary" className="w-fit max-w-full overflow-x-auto"
            onChange={(next) => { capture(); setAsOf(next); }}
            options={series.map((s) => ({ value: s.as_of, label: s.as_of_label }))} />
          <span className="text-meta text-muted-foreground">Stand wählen</span>
        </div>
      )}
      <div ref={root}><Distribution labels={labels} norms={norms} snapshot={snapshot} tokens={tokens[at] ?? []} /></div>
      {several && (
        <div className="mt-5 border-t border-border/70 pt-4">
          {snapshot.movement
            ? <Movement movement={snapshot.movement} />
            : <p className="text-hinweis text-muted-foreground">Der erste Stand, den die Stadt meldet.</p>}
          <p className="mt-3 max-w-[76ch] text-hinweis text-muted-foreground">
            Die Stadt meldet je Stand nur Summen.
          </p>
          <button type="button" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}
            className="mt-1 inline-flex min-h-11 items-center gap-1 text-left text-[13px] font-medium text-primary hover:underline">
            <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-weg ease-in-out-strong", showTable && "rotate-180")} aria-hidden />
            Alle Stände als Tabelle
          </button>
          <Aufklapp offen={showTable}><Series status={status} /></Aufklapp>
        </div>
      )}
      {status.notes.length > 0 && (
        <ul className="mt-4 max-w-[76ch] space-y-1 text-hinweis text-muted-foreground">
          {status.notes.map((note) => <li key={note.text}>{note.text}</li>)}
        </ul>
      )}
      <p className="mt-3 text-meta text-muted-foreground">
        Quelle:{" "}
        {status.source_url ? (
          <a href={status.source_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {status.source_label}
            <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px" aria-hidden />
          </a>
        ) : status.source_label}
        {status.template_number && (
          <span>
            {status.confirmed ? " · dieselben Zahlen im Bericht an den Rat " : " · "}
            <span className="font-mono">{status.template_number}</span>
          </span>
        )}
      </p>
    </section>
  );
}
