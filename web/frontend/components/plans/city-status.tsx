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

import { ExternalLink } from "lucide-react";
import { Kicker, STATUS_SQUARE } from "@/components/plans/parts";
import { signed, statusLabels, type PlanCityStatus } from "@/lib/plans";
import { cn } from "@/lib/utils";

function Distribution({ status }: { status: PlanCityStatus }) {
  return (
    <ul className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-2">
      {status.counts.map((c) => (
        <li key={c.status_raw} className="col-span-3 grid grid-cols-subgrid items-start">
          <span className="max-w-[11rem] break-words text-[14px] leading-snug text-foreground">{c.status_raw}</span>
          <span aria-hidden className="flex min-h-3 flex-wrap gap-[3px] pt-[3px]">
            {Array.from({ length: c.count }, (_, i) => (
              <span key={i} className={cn("h-3 w-3 rounded-[3px] border", STATUS_SQUARE[c.status_norm])} />
            ))}
          </span>
          <span className="text-right font-mono text-meta tabular-nums text-foreground">{c.count}</span>
        </li>
      ))}
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
      <Kicker>Alle Stände</Kicker>
      <div className="mt-1.5 overflow-x-auto">
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
  const counted = status.counts.reduce((n, c) => n + c.count, 0);
  return (
    <section aria-labelledby="plan-city-status" className="@container rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-city-status">Stand laut Stadt</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">{status.origin_label} · Stand {status.as_of_label}</p>
      </div>
      <p className="mb-4 max-w-[76ch] text-hinweis text-muted-foreground">
        {status.complete
          ? `So ordnet die Stadt ihre ${status.total} Maßnahmen selbst ein.`
          : `Die Stadt ordnet ${counted} von ${status.total} Maßnahmen ein; für die übrigen nennt sie keinen Stand.`}
        {" "}Ratslotse rechnet daraus keine Quote und vergibt keine Note.
      </p>
      <Distribution status={status} />
      {(status.movement || status.series.length > 1) && (
        <div className="mt-5 grid gap-5 border-t border-border/70 pt-4 @3xl:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
          {status.movement && <Movement movement={status.movement} />}
          {status.series.length > 1 && <Series status={status} />}
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
