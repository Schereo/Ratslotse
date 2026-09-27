"use client";

// Die Stichwahl im Rückblick — die Ansichten unter der Tafel, sobald die
// Wahl eingefroren ist (`wahl_einfrieren.py --ob`). Tims Wunsch nach dem
// 27.09.2026: „genauso eine detaillierte Analyse wie für die Stadtratswahl,
// auch mit Vergleich zur ersten OB-Wahl" — und: „wie die Vorhersage
// funktioniert und wie akkurat die war, ich wurde am Abend ein paar Mal
// danach gefragt".
//
// Gerechnet wird alles im Backend (`election/runoff_analysis.py`): Anteile,
// Fünftel, Rangliste, Sortierung, Filter, die Bilanz der Hochrechnung. Hier
// steht nur, was die Anzeige daraus macht — die Sätze setzen die Zahlen
// zusammen, sie rechnen keine neuen.

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { scaleLinear } from "d3-scale";
import { curveStepAfter, line } from "d3-shape";
import {
  AbleseBeschreibung,
  AbleseFlaeche,
  Ableseleiste,
  useAblesen,
  useAbleseId,
  type AbleseStelle,
} from "@/components/grafik/ablesen";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { prozent, uhrzeit, zahl } from "@/lib/wahlabend";
import {
  ROMAN,
  RUNOFF_ANALYSIS_PATH,
  growthText,
  pointsText,
  runoffDistrictsPath,
  type RunoffAnalysis,
  type RunoffDistricts,
  type RunoffDistrictRow,
  type RunoffPot,
  type RunoffProjectionReview,
  type RunoffSort,
} from "@/lib/stichwahl";

type Candidate = RunoffAnalysis["candidates"][number];

const CARD = "mt-5 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] sm:p-5";
const H2 = "font-display text-[16px] font-bold tracking-tight";
/** Richtung, kein Urteil (Zahlentabellen-Bauform): Plus grün, Minus Signal. */
const UP = "text-emerald-700 dark:text-emerald-400";
const DOWN = "text-orange-800 dark:text-orange-300";

function sign(pts: number | null | undefined): string {
  if (pts === null || pts === undefined || Math.abs(pts) < 0.05) return "text-muted-foreground";
  return pts > 0 ? UP : DOWN;
}

function signedVotes(n: number): string {
  return n === 0 ? "±0" : `${n > 0 ? "+" : "−"}${zahl(Math.abs(n))}`;
}

/** „65,3 → 46,3 %" — ein Prozentzeichen für beide Werte. */
function range(from: number | null, to: number | null): string {
  return `${prozent(from).replace(/ %$/, "")} → ${prozent(to)}`;
}

function surname(c: Candidate): string {
  const parts = c.name.split(" ");
  return parts[parts.length - 1] ?? c.name;
}

/** Die Auswertung — `null`, solange es keine gibt (404 vor dem Einfrieren). */
export function useRunoffAnalysis(enabled: boolean) {
  return useQuery({
    queryKey: ["stichwahl-analyse"],
    queryFn: () => api.get<RunoffAnalysis>(RUNOFF_ANALYSIS_PATH),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/* ── Vergleich zum ersten Wahlgang ──────────────────────────────────────── */

export function ComparisonView({ analysis, showDistricts }: {
  analysis: RunoffAnalysis;
  /** Springt in die Rangliste, nach Zugewinn sortiert. */
  showDistricts: () => void;
}) {
  const [winner, loser] = analysis.candidates;
  if (!winner || !loser) return null;
  const city = analysis.city;
  const gained = (c: Candidate) => (c.votes_runoff ?? 0) - (c.votes_first ?? 0);
  const eliminatedVotes = analysis.eliminated.reduce((sum, e) => sum + e.votes, 0);
  const urn = analysis.pots.find((p) => p.key === "urn");
  const postal = analysis.pots.find((p) => p.key === "postal");
  const weakest = analysis.quintiles[0];
  const strongest = analysis.quintiles[analysis.quintiles.length - 1];
  const leadFirst = analysis.lead_districts.first[winner.slug] ?? 0;
  const leadRunoff = analysis.lead_districts.runoff[winner.slug] ?? 0;
  const flippedToWinner = analysis.flipped[winner.slug] ?? 0;
  const flippedToLoser = analysis.flipped[loser.slug] ?? 0;
  return (
    <div data-testid="stichwahl-vergleich">
      <section className={CARD}>
        <h2 className={H2}>Zwei Wahlgänge, zwei Namen</h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
          {surname(winner)} gewann {zahl(gained(winner))} Stimmen dazu, {surname(loser)} {zahl(gained(loser))} — obwohl{" "}
          {zahl(city.voters_first - city.voters_runoff)} Menschen weniger wählten als am 13. September.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[30rem] border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className={KICKER}>
                <th className="border-b border-border pb-2 text-left font-medium" />
                <th className="border-b border-border pb-2 text-right font-medium">1. Wahlgang</th>
                <th className="border-b border-border pb-2 text-right font-medium">Stichwahl</th>
                <th className="border-b border-border pb-2 text-right font-medium">Stimmen</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {analysis.candidates.map((c) => (
                <tr key={c.slug}>
                  <td className="border-b border-border/60 py-2.5 pr-3">
                    <span className="inline-flex items-center gap-2 font-medium">
                      <Punkt color={c.color || "#6b7a8c"} dark={c.color_dark || "#a3b1c2"} />
                      {c.name}
                    </span>
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right">
                    {zahl(c.votes_first)} <span className="text-muted-foreground">· {prozent(c.share_first_pct)}</span>
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right font-semibold">
                    {zahl(c.votes_runoff)} <span className="font-normal text-muted-foreground">· {prozent(c.share_runoff_pct)}</span>
                  </td>
                  <td className={cn("border-b border-border/60 py-2.5 text-right font-semibold", sign(gained(c)))}>
                    {signedVotes(gained(c))}
                  </td>
                </tr>
              ))}
              <tr>
                <td className="border-b border-border/60 py-2.5 pr-3 text-muted-foreground">Die sieben anderen</td>
                <td className="border-b border-border/60 py-2.5 text-right">{zahl(eliminatedVotes)}</td>
                <td className="border-b border-border/60 py-2.5 text-right text-muted-foreground">nicht mehr auf dem Zettel</td>
                <td className="border-b border-border/60 py-2.5" />
              </tr>
              <tr>
                <td className="py-2.5 pr-3 text-muted-foreground">Wählende</td>
                <td className="py-2.5 text-right">
                  {zahl(city.voters_first)} <span className="text-muted-foreground">· {prozent(city.turnout_first_pct)}</span>
                </td>
                <td className="py-2.5 text-right">
                  {zahl(city.voters_runoff)} <span className="text-muted-foreground">· {prozent(city.turnout_runoff_pct)}</span>
                </td>
                <td className={cn("py-2.5 text-right font-semibold", sign(city.voters_runoff - city.voters_first))}>
                  {signedVotes(city.voters_runoff - city.voters_first)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
          Im ersten Wahlgang ausgeschieden:{" "}
          {analysis.eliminated.map((e) => `${e.name} ${zahl(e.votes)}`).join(" · ")}. Prozente in dieser Tabelle: amtlich,
          also im ersten Wahlgang von allen neun. Alle Vergleiche darunter rechnen mit dem Anteil an den beiden.
        </p>
      </section>

      {urn && postal ? (
        <section className={CARD}>
          <h2 className={H2}>Urne und Brief</h2>
          <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
            {surname(winner)} lag per Brief schon im ersten Wahlgang vorn. Gedreht hat er die Wahl an der Urne: dort{" "}
            {pointsText(urn.swing_pts)} Punkte, per Brief {pointsText(postal.swing_pts)}.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[urn, postal].map((p) => (
              <div key={p.key} className="rounded-xl border border-border/70 p-3.5">
                <p className={KICKER}>{p.label} · {p.districts} Bezirke</p>
                <ShareShift first={p.share_first_pct[winner.slug]} runoff={p.share_runoff_pct[winner.slug]} winner={winner} />
                <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">
                  Stimmen {surname(winner)} {growthText(p.growth[winner.slug])}, {surname(loser)}{" "}
                  {growthText(p.growth[loser.slug])} · Wählende {zahl(p.voters_first)} → {zahl(p.voters_runoff)}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
            ×1,00 hieße: genauso viele Stimmen wie im ersten Wahlgang. In der Stichwahl kamen{" "}
            {prozent((100 * postal.voters_runoff) / city.voters_runoff, 0)} der Stimmen per Brief, im ersten Wahlgang{" "}
            {prozent((100 * postal.voters_first) / city.voters_first, 0)} — deshalb getrennt: Zusammen gerechnet sähe die
            Verschiebung zwischen den Töpfen aus wie ein Meinungswandel.
          </p>
        </section>
      ) : null}

      {weakest && strongest ? (
        <section className={CARD}>
          <h2 className={H2}>Aufgeholt, wo er schwach war</h2>
          <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
            Die {analysis.quintiles.reduce((s, q) => s + q.districts, 0)} Urnenbezirke in fünf gleich großen Gruppen, nach{" "}
            {surname(winner)}s Anteil im ersten Wahlgang. Im schwächsten Fünftel legte er {pointsText(weakest.swing_pts)} Punkte
            zu, im stärksten {pointsText(strongest.swing_pts)}.
          </p>
          <ol className="mt-4 space-y-2.5">
            {analysis.quintiles.map((q) => (
              <li key={q.rank} className="grid grid-cols-[8.5rem_1fr_3.5rem] items-center gap-3 text-[13px]">
                <span className="text-muted-foreground">
                  {q.rank === 1 ? "schwächstes" : q.rank === analysis.quintiles.length ? "stärkstes" : `${q.rank}.`} Fünftel
                </span>
                <Dumbbell first={q.share_first_pct} runoff={q.share_runoff_pct} winner={winner} />
                <span className={cn("text-right font-semibold tabular-nums", sign(q.swing_pts))}>{pointsText(q.swing_pts)}</span>
              </li>
            ))}
            <li className="grid grid-cols-[8.5rem_1fr_3.5rem] gap-3" aria-hidden>
              <span />
              <DumbbellAxis />
              <span />
            </li>
          </ol>
          <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
            Hohler Punkt: {surname(winner)}s Anteil an den beiden im ersten Wahlgang, voller Punkt: in der Stichwahl.
            {analysis.catch_up_r !== null
              ? ` Über alle Urnenbezirke hängen beide mit r = ${analysis.catch_up_r.toFixed(2).replace(".", ",").replace("-", "−")} zusammen — erkennbar, aber kein strenger Zusammenhang.`
              : ""}
          </p>
        </section>
      ) : null}

      <section className={CARD}>
        <h2 className={H2}>Gedrehte Bezirke</h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
          Im ersten Wahlgang lag {surname(winner)} in {leadFirst} von {city.districts} Bezirken vor {surname(loser)}, in der
          Stichwahl in {leadRunoff}. {flippedToWinner} Bezirke drehten zu {surname(winner)}
          {flippedToLoser > 0 ? `, ${flippedToLoser} zu ${surname(loser)}` : ""}.
        </p>
        <button
          type="button"
          onClick={showDistricts}
          className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border px-3.5 py-1.5 text-[13px] font-medium text-primary hover:bg-primary/5"
        >
          Alle Bezirke nach Zugewinn
        </button>
      </section>

      <Limits />
    </div>
  );
}

function Limits() {
  return (
    <section className="mt-5 rounded-2xl border border-dashed border-border p-4 sm:p-5">
      <h2 className={H2}>Was diese Zahlen nicht hergeben</h2>
      <ul className="mt-2 space-y-2 text-[13.5px] leading-relaxed text-muted-foreground @container sm:grid sm:grid-cols-2 sm:gap-x-6 sm:space-y-0">
        <li>
          <strong className="font-semibold text-foreground">Wer wohin gewandert ist.</strong> Ob Boldt-Wählende zu Rohr gingen
          oder zu Hause blieben, steht in keinem Bezirksergebnis. Eine Rechnung über die 133 Bezirke liefert hier sogar negative
          Übergänge — also Unsinn. Belastbar sind nur Aussagen über Orte, nicht über Menschen.
        </li>
        <li>
          <strong className="font-semibold text-foreground">Wo die Briefwählenden wohnen.</strong> Briefwahlbezirke haben keine
          Fläche; sie gehören zu einem Wahlbereich, nicht zu einer Straße. Die Fünftel rechnen deshalb nur mit der Urne.
        </li>
        <li>
          <strong className="font-semibold text-foreground">Das amtliche Ergebnis.</strong> Das stellt der Wahlausschuss fest;
          hier stehen die Zahlen der Ergebnisdarstellung vom Wahlabend.
        </li>
        <li>
          <strong className="font-semibold text-foreground">Warum.</strong> Die Zahlen zeigen, wo sich etwas verschoben hat —
          nicht, was die Leute bewegt hat.
        </li>
      </ul>
    </section>
  );
}

/** Anteil des Gewinners an den beiden: erster Wahlgang → Stichwahl. */
function ShareShift({ first, runoff, winner }: { first: number | null; runoff: number | null; winner: Candidate }) {
  return (
    <div className="mt-2">
      <p className="flex items-baseline gap-2">
        <span className="font-display text-[26px] font-bold leading-none tabular-nums">{prozent(runoff)}</span>
        <span className="text-[12.5px] text-muted-foreground">
          {surname(winner)} · vorher {prozent(first)}
        </span>
      </p>
      <Dumbbell first={first} runoff={runoff} winner={winner} className="mt-2.5" />
      <DumbbellAxis />
    </div>
  );
}

/** Zwei Punkte auf einer Achse um 50 %: hohl der erste Wahlgang, voll die
 *  Stichwahl. Die Achse reicht von 30 bis 70 — dort liegt jeder Bezirk
 *  dieser Wahl; ein Wert außerhalb klemmt am Rand. */
function Dumbbell({ first, runoff, winner, className }: {
  first: number | null;
  runoff: number | null;
  winner: Candidate;
  className?: string;
}) {
  const x = (v: number) => Math.min(100, Math.max(0, ((v - 30) / 40) * 100));
  const color = `light-dark(${winner.color || "#6b7a8c"}, ${winner.color_dark || winner.color || "#a3b1c2"})`;
  if (first === null || runoff === null) return <div className={cn("h-3", className)} />;
  const [lo, hi] = first < runoff ? [first, runoff] : [runoff, first];
  return (
    <div className={cn("relative h-3", className)} aria-hidden>
      <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
      <div className="absolute top-0 h-full w-px bg-foreground/40" style={{ left: `${x(50)}%` }} />
      <div
        className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full"
        style={{ left: `${x(lo)}%`, width: `${x(hi) - x(lo)}%`, background: color, opacity: 0.45 }}
      />
      <span
        className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
        style={{ left: `${x(first)}%`, borderColor: color }}
      />
      <span
        className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{ left: `${x(runoff)}%`, background: color }}
      />
    </div>
  );
}

/** Die Beschriftung unter einer Reihe von Hanteln: 30, 50, 70 %. */
function DumbbellAxis() {
  return (
    <div className="relative h-4 font-mono text-[10px] text-muted-foreground">
      <span className="absolute left-0">30 %</span>
      <span className="absolute left-1/2 -translate-x-1/2">50 %</span>
      <span className="absolute right-0">70 %</span>
    </div>
  );
}

/* ── Wahlbereiche ───────────────────────────────────────────────────────── */

export function AreasView({ analysis, showArea }: {
  analysis: RunoffAnalysis;
  /** Springt in die Rangliste dieses Bereichs. */
  showArea: (area: number) => void;
}) {
  const [winner, loser] = analysis.candidates;
  if (!winner || !loser) return null;
  const swings = analysis.areas.map((a) => a.swing_pts ?? 0);
  const allUp = swings.every((s) => s > 0);
  const best = analysis.areas.reduce((a, b) => ((b.swing_pts ?? 0) > (a.swing_pts ?? 0) ? b : a));
  return (
    <div data-testid="stichwahl-bereiche" className="@container">
      <p className="mt-5 text-[14px] leading-relaxed text-muted-foreground">
        {allUp
          ? `${surname(winner)} legte in allen sechs Wahlbereichen zu, am stärksten in ${best.label} (${pointsText(best.swing_pts)} Punkte).`
          : `Am stärksten legte ${surname(winner)} in ${best.label} zu (${pointsText(best.swing_pts)} Punkte).`}{" "}
        Jeder Bereich mit seinen Urnen- und Briefwahlbezirken; die Beteiligung rechnet die Briefwählenden zu ihrem Bereich.
      </p>
      <div className="mt-2 grid gap-4 @2xl:grid-cols-2">
        {analysis.areas.map((a) => {
          const w = a.share_runoff_pct[winner.slug] ?? null;
          const ahead = w !== null && w > 50;
          return (
            <section key={a.number} className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-display text-[15px] font-bold tracking-tight">{a.label}</h3>
                <span className={KICKER}>{a.districts} Bezirke</span>
              </div>
              <ShareShift first={a.share_first_pct[winner.slug] ?? null} runoff={w} winner={winner} />
              <dl className="mt-3 grid grid-cols-3 gap-2 text-[12.5px]">
                <div>
                  <dt className="text-muted-foreground">Zugewinn</dt>
                  <dd className={cn("font-semibold tabular-nums", sign(a.swing_pts))}>{pointsText(a.swing_pts)} Pkt.</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Stimmen</dt>
                  <dd className="tabular-nums">
                    {surname(winner)} {growthText(a.growth[winner.slug])}
                    <br />
                    {surname(loser)} {growthText(a.growth[loser.slug])}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Beteiligung</dt>
                  <dd className="whitespace-nowrap tabular-nums">{range(a.turnout_first_pct, a.turnout_runoff_pct)}</dd>
                </div>
              </dl>
              <p className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[12.5px] text-muted-foreground">
                <span>{ahead ? `${surname(winner)} vorn` : `${surname(loser)} vorn`}</span>
                <button type="button" onClick={() => showArea(a.number)} className="font-medium text-primary">
                  Bezirke in {a.label}
                </button>
              </p>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/* ── Wahlbezirke ────────────────────────────────────────────────────────── */

const SORTS: { value: RunoffSort; label: string }[] = [
  { value: "share", label: "Anteil" },
  { value: "swing", label: "Zugewinn" },
  { value: "turnout", label: "Beteiligung" },
  { value: "number", label: "Nummer" },
];

export function DistrictsView({ analysis, sort, area, pot, onChange }: {
  analysis: RunoffAnalysis;
  sort: RunoffSort;
  area: number | null;
  pot: RunoffPot | null;
  onChange: (next: { sort: RunoffSort; area: number | null; pot: RunoffPot | null }) => void;
}) {
  const path = runoffDistrictsPath(sort, area, pot);
  const query = useQuery({
    queryKey: ["stichwahl-analyse-bezirke", path],
    queryFn: () => api.get<RunoffDistricts>(path),
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
  const [winner, loser] = analysis.candidates;
  if (!winner || !loser) return null;
  const rows = query.data?.rows ?? [];
  const total = query.data?.total ?? analysis.city.districts;
  const explain: Record<RunoffSort, string> = {
    share: `Wo ${surname(winner)} in der Stichwahl am stärksten war.`,
    swing: `Wo ${surname(winner)} gegenüber dem ersten Wahlgang am meisten zulegte — in Punkten seines Anteils an den beiden.`,
    turnout: "Wo die Beteiligung am stärksten zurückging. Briefwahlbezirke haben keine eigenen Wahlberechtigten und stehen am Ende.",
    number: "In der Reihenfolge der Stadt.",
  };
  return (
    <section className={CARD} data-testid="stichwahl-bezirke">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div>
          <h2 className={H2}>
            {area === null && pot === null
              ? `Alle ${total} Wahlbezirke`
              : `${rows.length} von ${total} Wahlbezirken`}
          </h2>
          <p className="mt-1 text-[13px] text-muted-foreground">{explain[sort]}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5" role="group" aria-label="Sortierung">
        <span className="mr-1 text-[12.5px] text-muted-foreground">Sortiert nach</span>
        {SORTS.map((o) => (
          <Chip key={o.value} on={sort === o.value} onClick={() => onChange({ sort: o.value, area, pot })}>
            {o.label}
          </Chip>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter">
        <span className="mr-1 text-[12.5px] text-muted-foreground">Zeige</span>
        <Chip on={area === null && pot === null} onClick={() => onChange({ sort, area: null, pot: null })}>Alle</Chip>
        {[1, 2, 3, 4, 5, 6].map((n) => (
          <Chip key={n} on={area === n} onClick={() => onChange({ sort, area: area === n ? null : n, pot })}>
            {ROMAN[n]}
          </Chip>
        ))}
        <span className="mx-1 w-px self-stretch bg-border" aria-hidden />
        <Chip on={pot === "urn"} onClick={() => onChange({ sort, area, pot: pot === "urn" ? null : "urn" })}>Urne</Chip>
        <Chip on={pot === "postal"} onClick={() => onChange({ sort, area, pot: pot === "postal" ? null : "postal" })}>
          Brief
        </Chip>
      </div>
      <div className={cn("mt-3 overflow-x-auto transition-opacity", query.isFetching && query.isPlaceholderData && "opacity-60")}>
        <table className="w-full min-w-[34rem] border-separate border-spacing-0 text-[13px]">
          <thead>
            <tr className={KICKER}>
              <th className="border-b border-border pb-2 pr-2 text-right font-medium">#</th>
              <th className="border-b border-border pb-2 text-left font-medium">Wahlbezirk</th>
              <th className="border-b border-border pb-2 text-right font-medium">{surname(winner)}</th>
              <th className="border-b border-border pb-2 text-right font-medium">1. Wg.</th>
              <th className="border-b border-border pb-2 text-right font-medium">±</th>
              <th className="border-b border-border pb-2 pl-3 text-right font-medium">Beteiligung</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map((r) => (
              <DistrictRow key={r.number} row={r} winner={winner} loser={loser} />
            ))}
          </tbody>
        </table>
        {query.isError ? <p className="mt-3 text-[13px] text-muted-foreground">Die Liste ließ sich gerade nicht laden.</p> : null}
      </div>
      <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
        {surname(winner)}: Anteil an den Stimmen für beide. „gedreht": Im ersten Wahlgang lag dort der andere vorn.
      </p>
    </section>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-[12.5px] transition-colors",
        on ? "border-primary/40 bg-primary/10 font-semibold text-primary" : "border-border text-foreground/80 hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}

function DistrictRow({ row, winner, loser }: { row: RunoffDistrictRow; winner: Candidate; loser: Candidate }) {
  const turnedTo = row.flipped ? (row.leader_runoff === winner.slug ? winner : loser) : null;
  return (
    <tr>
      <td className="border-b border-border/60 py-2 pr-2 text-right text-muted-foreground">{row.rank}</td>
      <td className="border-b border-border/60 py-2 pr-3">
        <span className="font-medium">
          <span className="mr-1.5 font-mono text-[11.5px] text-muted-foreground">{row.number}</span>
          {row.postal ? "Briefwahl" : row.name}
        </span>
        <span className="ml-1.5 text-[11.5px] text-muted-foreground">WB {ROMAN[row.area] ?? row.area}</span>
        {turnedTo ? (
          <span className="ml-1.5 whitespace-nowrap rounded-full bg-primary/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-primary">
            gedreht zu {surname(turnedTo)}
          </span>
        ) : null}
      </td>
      <td className="border-b border-border/60 py-2 text-right font-semibold">{prozent(row.share_runoff_pct)}</td>
      <td className="border-b border-border/60 py-2 text-right text-muted-foreground">{prozent(row.share_first_pct)}</td>
      <td className={cn("border-b border-border/60 py-2 pl-2 text-right font-semibold", sign(row.swing_pts))}>
        {pointsText(row.swing_pts)}
      </td>
      <td className="border-b border-border/60 py-2 pl-3 text-right">
        {row.turnout_runoff_pct === null ? (
          <span className="text-muted-foreground">–</span>
        ) : (
          <>
            {prozent(row.turnout_runoff_pct)}{" "}
            <span className={cn("text-[11.5px]", sign(row.turnout_change_pts))}>{pointsText(row.turnout_change_pts)}</span>
          </>
        )}
      </td>
    </tr>
  );
}

/* ── Die Hochrechnung: wie sie rechnet, und wie gut sie lag ─────────────── */

export function ProjectionView({ analysis }: { analysis: RunoffAnalysis }) {
  const review = analysis.projection_review;
  const [winner] = analysis.candidates;
  if (!winner) return null;
  return (
    <div data-testid="stichwahl-hochrechnung-rueckblick">
      <section className={CARD}>
        <h2 className={H2}>So rechnet die Hochrechnung</h2>
        <ol className="mt-3 space-y-3 text-[14px] leading-relaxed">
          <li>
            <strong className="font-semibold">Jeder Bezirk hat ein Gedächtnis.</strong>{" "}
            <span className="text-muted-foreground">
              Aus dem ersten Wahlgang kennen wir für alle 133 Wahlbezirke, wie stark die beiden dort waren. Meldet ein Bezirk,
              zählt nicht nur sein Ergebnis, sondern auch, wie sehr es sich gegenüber dem 13. September verschoben hat.
            </span>
          </li>
          <li>
            <strong className="font-semibold">Aus den gemeldeten Bezirken wird ein Trend.</strong>{" "}
            <span className="text-muted-foreground">
              Diese Verschiebung — getrennt für Urne und Briefwahl, weil beide anders schwingen — wird auf die noch offenen
              Bezirke übertragen: Jeder offene Bezirk stimmt wie im ersten Wahlgang, verschoben um den Trend. Deshalb kann die
              Hochrechnung schon richtig liegen, wenn die Auszählung noch den Falschen vorn zeigt: Früh melden oft Bezirke, in
              denen einer ohnehin stark ist.
            </span>
          </li>
          <li>
            <strong className="font-semibold">Die Chance ist die Unsicherheit dieses Trends.</strong>{" "}
            <span className="text-muted-foreground">
              Wie stark die gemeldeten Bezirke um den Trend streuen, sagt, wie weit er danebenliegen kann. Daraus entsteht eine
              Wahrscheinlichkeit — erst ab {review?.min_districts ?? 15} gezählten Bezirken, und nie über{" "}
              {review?.chance_cap ?? 99} %, bis die Arithmetik entschieden hat.
            </span>
          </li>
          <li>
            <strong className="font-semibold">„Rechnerisch entschieden" ist keine Schätzung.</strong>{" "}
            <span className="text-muted-foreground">
              Das steht erst da, wenn der tatsächliche Vorsprung größer ist als alle Stimmen, die in den offenen Bezirken
              höchstens noch kommen können.
            </span>
          </li>
        </ol>
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
          Vor der Wahl eingestellt und geprüft an der Stichwahl 2021 (Krogmann gegen Fuhrhop, dieselben 133 Bezirke), dort auch
          mit künstlich knapp gemachten Ergebnissen. Über die Menschen, die im ersten Wahlgang jemand anderen gewählt haben,
          weiß das Modell nichts — es sieht nur, wie sich die Bezirke bewegen.
        </p>
      </section>
      {review ? <ReviewCard review={review} winner={winner} /> : null}
    </div>
  );
}

function ReviewCard({ review, winner }: { review: RunoffProjectionReview; winner: Candidate }) {
  const first = review.points[0];
  const facts: { value: string; label: string }[] = [
    {
      value: review.projection_right_from === null ? "–" : `ab Bezirk ${review.projection_right_from}`,
      label: `zeigte die Hochrechnung ${surname(winner)} vorn — und blieb dabei`,
    },
    {
      value: review.counted_right_from === null ? "–" : `ab Bezirk ${review.counted_right_from}`,
      label: `zeigte die Auszählung selbst ${surname(winner)} vorn — nach ${review.counted_lead_changes} Führungswechseln`,
    },
    {
      value:
        review.max_error_after_min_pts === null
          ? "–"
          : `${review.max_error_after_min_pts.toFixed(2).replace(".", ",")} Punkte`,
      label: `lag die Hochrechnung höchstens daneben, sobald sie eine Chance nannte (ab ${review.min_districts} Bezirken)`,
    },
    {
      value: review.first_chance ? `${review.first_chance.chance_pct} %` : "–",
      label: review.first_chance
        ? `die erste Chance, bei ${review.first_chance.reports_received} Bezirken — ${review.chance_always_winner ? "jede Chance des Abends galt dem Sieger" : "nicht jede galt dem Sieger"}`
        : "keine Chance genannt",
    },
  ];
  return (
    <section className={CARD}>
      <h2 className={H2}>Wie gut sie lag</h2>
      <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
        Endergebnis {surname(winner)}: {prozent(review.final_share_pct)}.
        {first && first.projected_share_pct !== null
          ? ` Nach dem ersten Bezirk um ${uhrzeit(first.at)} Uhr rechnete die Seite ${prozent(first.projected_share_pct)} hoch — die Richtung stimmte, die Höhe noch nicht.`
          : ""}
      </p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {facts.map((f) => (
          <div key={f.label} className="flex flex-col rounded-xl border border-border/70 p-3.5">
            <dt className="order-2 mt-1.5 text-[12.5px] leading-snug text-muted-foreground">{f.label}</dt>
            <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{f.value}</dd>
          </div>
        ))}
      </dl>
      <ReviewChart review={review} winner={winner} />
      <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Ein Abend ist keine Statistik: Dass „99 %" diesmal stimmte, beweist nicht, dass es immer stimmt. In der Prüfung vor der
        Wahl lag „99 %" in 999 von 1.000 nachgestellten Abenden richtig, „90 bis 98 %" in 93 von 100.
      </p>
    </section>
  );
}

const W = 480;
const H = 220;
const X0 = 40;
const X1 = W - 12;
const Y0 = H - 26;
const YTOP = 12;

/** Über die gezählten Bezirke, nicht über die Uhr: Die Frage ist „wie früh
 *  lag sie richtig", und früh heißt hier „nach wie vielen Bezirken". */
function ReviewChart({ review, winner }: { review: RunoffProjectionReview; winner: Candidate }) {
  const points = review.points;
  const control = useAblesen(points.length, Math.max(points.length - 1, 0));
  const id = useAbleseId();
  if (points.length < 2) return null;
  const maxDistricts = Math.max(...points.map((p) => p.reports_received), 1);
  const x = scaleLinear().domain([0, maxDistricts]).range([X0, X1]);
  const values = points.flatMap((p) => [p.counted_share_pct, p.projected_share_pct]).filter((v): v is number => v !== null);
  const span = Math.max(4, ...values.map((v) => Math.abs(v - 50))) + 1;
  const y = scaleLinear().domain([50 - span, 50 + span]).range([Y0, YTOP]);
  const path = (vals: (number | null)[]) =>
    line<number | null>()
      .defined((v) => v !== null)
      .x((_, i) => x(points[i].reports_received))
      .y((v) => y(v ?? 50))
      .curve(curveStepAfter)(vals) ?? "";
  const color = `light-dark(${winner.color || "#6b7a8c"}, ${winner.color_dark || winner.color || "#a3b1c2"})`;
  const counted = points.map((p) => p.counted_share_pct);
  const projected = points.map((p) => p.projected_share_pct);
  const stellen: AbleseStelle[] = points.map((p) => ({
    title: `${p.reports_received} Bezirke`,
    werte: [
      { label: "ausgezählt", value: prozent(p.counted_share_pct) },
      { label: "Hochrechnung", value: prozent(p.projected_share_pct) },
      { label: "Abstand zum Ende", value: p.error_pts === null ? "–" : pointsText(p.error_pts) },
      { label: "Chance", value: p.chance_pct === null ? "–" : `${p.chance_pct} %` },
    ],
    vorlesen: `${p.reports_received} Bezirke, ${uhrzeit(p.at)} Uhr: ausgezählt ${prozent(p.counted_share_pct)}, Hochrechnung ${prozent(p.projected_share_pct)}.`,
  }));
  return (
    <div className="mt-5">
      <p className={KICKER}>
        Anteil {surname(winner)} nach gezählten Bezirken · durchgezogen ausgezählt · gestrichelt Hochrechnung · blau
        Endergebnis
      </p>
      <AbleseBeschreibung id={id}>
        Über die Zahl der gezählten Bezirke: der ausgezählte Anteil von {winner.name} als Treppe, die Hochrechnung gestrichelt
        und das Endergebnis von {prozent(review.final_share_pct)} als waagerechte Linie.
      </AbleseBeschreibung>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 block w-full" role="group" aria-describedby={id}>
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line x1={X0} y1={y(t)} x2={X1} y2={y(t)} className={t === 50 ? "stroke-foreground/40" : "stroke-border/60"} />
            <text x={X0 - 6} y={y(t) + 4} textAnchor="end" fontSize={10} className="fill-muted-foreground font-mono">
              {`${t} %`}
            </text>
          </g>
        ))}
        {x.ticks(5).map((t) => (
          <text key={t} x={x(t)} y={H - 8} textAnchor="middle" fontSize={10} className="fill-muted-foreground font-mono">
            {t}
          </text>
        ))}
        <line
          x1={X0}
          x2={X1}
          y1={y(review.final_share_pct)}
          y2={y(review.final_share_pct)}
          className="stroke-primary"
          strokeWidth={1.25}
        />
        <path d={path(counted)} fill="none" stroke={color} strokeWidth={2} strokeOpacity={0.55} strokeLinejoin="round" />
        <path d={path(projected)} fill="none" stroke={color} strokeWidth={2.25} strokeDasharray="5 3" strokeLinejoin="round" />
        <AbleseFlaeche
          stellen={stellen}
          steuerung={control}
          x={(i) => x(points[i].reports_received)}
          xVon={X0}
          xBis={X1}
          yVon={YTOP}
          hoehe={Y0 - YTOP}
          fangHoehe={H - YTOP}
          marken={(i) => (projected[i] === null ? [] : [{ y: y(projected[i] ?? 50), farbe: color }])}
          gruppe="Stände des Abends"
        />
      </svg>
      <Ableseleiste stelle={stellen[control.aktiv]} steuerung={control} className="mt-3" haftet={false} />
    </div>
  );
}
