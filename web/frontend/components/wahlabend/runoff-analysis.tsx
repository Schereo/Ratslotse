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
import { ChartLegend } from "@/components/grafik/chart-legend";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fixed, prozent, uhrzeit, zahl } from "@/lib/wahlabend";
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
        <h2 className={H2}>Die beiden Wahlgänge im Vergleich</h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
          {surname(winner)} erhielt in der Stichwahl {zahl(gained(winner))} Stimmen mehr als im ersten Wahlgang, {surname(loser)}{" "}
          {zahl(gained(loser))} mehr. Gleichzeitig beteiligten sich {zahl(city.voters_first - city.voters_runoff)} Menschen weniger
          als am 13. September.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[30rem] border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className={KICKER}>
                <th className="border-b border-border pb-2 text-left font-medium" />
                <th className="border-b border-border pb-2 text-right font-medium">1. Wahlgang</th>
                <th className="border-b border-border pb-2 text-right font-medium">Stichwahl</th>
                <th className="border-b border-border pb-2 text-right font-medium">Veränderung</th>
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
                <td className="border-b border-border/60 py-2.5 pr-3 text-muted-foreground">
                  Übrige {analysis.eliminated.length} Kandidaturen
                </td>
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
          {analysis.eliminated.map((e) => `${e.name} ${zahl(e.votes)}`).join(" · ")}. Die Prozentwerte in dieser Tabelle sind
          die amtlichen Anteile an allen gültigen Stimmen. In den folgenden Vergleichen werden nur die Stimmen für die beiden
          Stichwahlkandidaten betrachtet, damit sich beide Wahlgänge vergleichen lassen.
        </p>
      </section>

      {urn && postal ? (
        <section className={CARD}>
          <h2 className={H2}>Urnen- und Briefwahl im Vergleich</h2>
          <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
            Bei den Briefwahlstimmen lag {surname(winner)} bereits im ersten Wahlgang vor {surname(loser)}. Sein Anteil an den
            Stimmen für beide Stichwahlkandidaten stieg bei der Urnenwahl von {prozent(urn.share_first_pct[winner.slug])} auf{" "}
            {prozent(urn.share_runoff_pct[winner.slug])} und bei der Briefwahl von {prozent(postal.share_first_pct[winner.slug])}
            auf {prozent(postal.share_runoff_pct[winner.slug])}.
          </p>
          <DumbbellLegend winner={winner} className="mt-3" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[urn, postal].map((p) => (
              <div key={p.key} className="rounded-xl border border-border/70 p-3.5">
                <p className={KICKER}>{p.label} · {p.districts} Bezirke</p>
                <ShareShift first={p.share_first_pct[winner.slug]} runoff={p.share_runoff_pct[winner.slug]} winner={winner} />
                <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">
                  Stimmenzahl seit dem ersten Wahlgang: {surname(winner)} {growthText(p.growth[winner.slug])}, {surname(loser)}{" "}
                  {growthText(p.growth[loser.slug])} · Wählende: {zahl(p.voters_first)} → {zahl(p.voters_runoff)}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
            Der Faktor ×1,00 bedeutet: genauso viele Stimmen wie im ersten Wahlgang. Der Anteil der Briefwählenden an allen
            Wählenden stieg von {prozent((100 * postal.voters_first) / city.voters_first, 0)} auf{" "}
            {prozent((100 * postal.voters_runoff) / city.voters_runoff, 0)}. Deshalb werden Urnen- und Briefwahl getrennt
            ausgewertet; sonst könnte allein diese Verschiebung das Ergebnis verzerren.
          </p>
        </section>
      ) : null}

      {weakest && strongest ? (
        <section className={CARD}>
          <h2 className={H2}>Größere Zugewinne in zuvor schwachen Bezirken</h2>
          <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
            Die {analysis.quintiles.reduce((s, q) => s + q.districts, 0)} Urnenbezirke sind nach {surname(winner)}s Anteil an den
            Stimmen für beide Stichwahlkandidaten im ersten Wahlgang in fünf möglichst gleich große Gruppen geordnet. In der
            Gruppe mit seinem niedrigsten Ausgangsanteil stieg dieser von {prozent(weakest.share_first_pct)} auf{" "}
            {prozent(weakest.share_runoff_pct)}, in der Gruppe mit seinem höchsten von {prozent(strongest.share_first_pct)} auf{" "}
            {prozent(strongest.share_runoff_pct)}.
          </p>
          <DumbbellLegend winner={winner} className="mt-3" />
          <ol className="mt-4 space-y-2.5">
            {analysis.quintiles.map((q) => (
              <li key={q.rank} className="grid grid-cols-[8.5rem_1fr_3.5rem] items-center gap-3 text-[13px]">
                <span className="text-muted-foreground">
                  {q.rank === 1
                    ? "1. Fünftel · niedrig"
                    : q.rank === analysis.quintiles.length
                      ? "5. Fünftel · hoch"
                      : `${q.rank}. Fünftel`}
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
            Der hohle Punkt zeigt {surname(winner)}s Anteil an den Stimmen für beide Kandidaten im ersten Wahlgang, der volle
            Punkt den Anteil in der Stichwahl.
            {analysis.catch_up_r !== null
              ? ` Der Korrelationswert über alle Urnenbezirke beträgt r = ${fixed(analysis.catch_up_r, 2).replace("-", "−")}. Der negative Wert bedeutet: Je niedriger der Ausgangsanteil war, desto größer war tendenziell der Zugewinn. Das belegt keine Ursache.`
              : ""}
          </p>
        </section>
      ) : null}

      <section className={CARD}>
        <h2 className={H2}>In welchen Bezirken die Führung wechselte</h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
          Im ersten Wahlgang lag {surname(winner)} in {leadFirst} von {city.districts} Bezirken vor {surname(loser)}, in der
          Stichwahl in {leadRunoff}. In {flippedToWinner} Bezirken wechselte die Führung von {surname(loser)} zu {surname(winner)}
          {flippedToLoser > 0
            ? `; in ${flippedToLoser === 1 ? "einem Bezirk" : `${flippedToLoser} Bezirken`} wechselte sie von ${surname(winner)} zu ${surname(loser)}`
            : ""}.
        </p>
        <button
          type="button"
          onClick={showDistricts}
          className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border px-3.5 py-1.5 text-[13px] font-medium text-primary hover:bg-primary/5"
        >
          Alle Bezirke nach Zugewinn sortiert
        </button>
      </section>

      <Limits resultStatus={analysis.result_status} />
    </div>
  );
}

function Limits({ resultStatus }: { resultStatus: RunoffAnalysis["result_status"] }) {
  return (
    <section className="mt-5 rounded-2xl border border-dashed border-border p-4 sm:p-5">
      <h2 className={H2}>Was diese Zahlen nicht hergeben</h2>
      <ul className="mt-2 space-y-2 text-[13.5px] leading-relaxed text-muted-foreground @container sm:grid sm:grid-cols-2 sm:gap-x-6 sm:space-y-0">
        <li>
          <strong className="font-semibold text-foreground">Wer wen im zweiten Wahlgang gewählt hat.</strong> Ob Menschen, die
          zuvor Boldt gewählt haben, in der Stichwahl Rohr oder Prange wählten oder zu Hause blieben, steht in keinem
          Bezirksergebnis. Berechnete Wechsel zwischen den Kandidaturen wären daher nicht belastbar.
        </li>
        <li>
          <strong className="font-semibold text-foreground">Wo Briefwählende wohnen.</strong> Briefwahlbezirke lassen sich nur
          einem Wahlbereich, aber keiner Straße zuordnen. Der Vergleich nach Fünfteln berücksichtigt deshalb nur Urnenbezirke.
        </li>
        <li>
          <strong className="font-semibold text-foreground">Das amtliche Endergebnis.</strong> Das stellt der Wahlausschuss fest.
          {resultStatus === "amtlich"
            ? " Hier wird das amtlich festgestellte Ergebnis ausgewertet."
            : " Hier werden die vorläufigen Zahlen aus der Ergebnisdarstellung des Wahlabends ausgewertet."}
        </li>
        <li>
          <strong className="font-semibold text-foreground">Die Gründe für Veränderungen.</strong> Die Zahlen zeigen, wo sich
          Anteile verändert haben, aber nicht, warum Menschen anders oder gar nicht gewählt haben.
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

/** Was die beiden Punkte einer Hantel bedeuten — gezeichnet wie im Bild. */
function DumbbellLegend({ winner, className }: { winner: Candidate; className?: string }) {
  const color = `light-dark(${winner.color || "#6b7a8c"}, ${winner.color_dark || winner.color || "#a3b1c2"})`;
  return (
    <ChartLegend
      className={className}
      items={[
        { mark: "ring", color, label: "1. Wahlgang" },
        { mark: "dot", color, label: "Stichwahl" },
        { mark: "rule", label: "50 %" },
      ]}
    />
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
  const bestChange = pointsText(best.swing_pts).replace(/^\+/, "");
  return (
    <div data-testid="stichwahl-bereiche" className="@container">
      <p className="mt-5 text-[14px] leading-relaxed text-muted-foreground">
        {allUp
          ? `${surname(winner)}s Anteil an den Stimmen für beide Stichwahlkandidaten stieg in allen sechs Wahlbereichen. Am stärksten war der Anstieg in ${best.label} mit ${bestChange} Prozentpunkten.`
          : `Die größte Veränderung gab es in ${best.label}: ${pointsText(best.swing_pts)} Prozentpunkte.`}{" "}
        Jeder Wahlbereich umfasst seine Urnen- und Briefwahlbezirke. Bei der Wahlbeteiligung werden die Briefwählenden dem
        jeweiligen Wahlbereich zugerechnet. Die Faktoren bei „Stimmenzahl“ vergleichen mit dem ersten Wahlgang; ×1,00 bedeutet
        unverändert.
      </p>
      <DumbbellLegend winner={winner} className="mt-3" />
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
                  <dt className="text-muted-foreground">Anteil</dt>
                  <dd className={cn("font-semibold tabular-nums", sign(a.swing_pts))}>{pointsText(a.swing_pts)} Pkt.</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Stimmenzahl</dt>
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
                <span>{ahead ? `${surname(winner)} erhielt mehr Stimmen` : `${surname(loser)} erhielt mehr Stimmen`}</span>
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
  { value: "share", label: "Stichwahl-Anteil" },
  { value: "swing", label: "Veränderung" },
  { value: "turnout", label: "Rückgang der Beteiligung" },
  { value: "number", label: "Bezirksnummer" },
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
    share: `Wahlbezirke mit dem höchsten Stichwahl-Anteil für ${surname(winner)}.`,
    swing: `Wahlbezirke, in denen ${surname(winner)}s Anteil an den Stimmen für beide Kandidaten gegenüber dem ersten Wahlgang am stärksten stieg.`,
    turnout: "Wahlbezirke mit dem stärksten Rückgang der Wahlbeteiligung. Für Briefwahlbezirke weist die Stadt keine eigenen Wahlberechtigten aus; sie stehen deshalb am Ende.",
    number: "Wahlbezirke in der amtlichen Nummernfolge.",
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
              <th className="border-b border-border pb-2 pr-2 text-right font-medium">Rang</th>
              <th className="border-b border-border pb-2 text-left font-medium">Wahlbezirk</th>
              <th className="border-b border-border pb-2 text-right font-medium">{surname(winner)}</th>
              <th className="border-b border-border pb-2 text-right font-medium">1. Wahlgang</th>
              <th className="border-b border-border pb-2 text-right font-medium">Veränd.</th>
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
        Die Anteile beziehen sich in beiden Wahlgängen nur auf die Stimmen für {surname(winner)} und {surname(loser)}.
        „Führung wechselte“ bedeutet: Im ersten Wahlgang lag dort der andere Kandidat vorn.
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
            Führung wechselte zu {surname(turnedTo)}
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
        <h2 className={H2}>So wurde die Hochrechnung berechnet</h2>
        <ol className="mt-3 space-y-3 text-[14px] leading-relaxed">
          <li>
            <strong className="font-semibold">Ausgangspunkt war das Ergebnis jedes einzelnen Wahlbezirks.</strong>{" "}
            <span className="text-muted-foreground">
              Für alle 133 Wahlbezirke lagen die Ergebnisse des ersten Wahlgangs vor. Sobald ein Bezirk ausgezählt war, verglich
              das Modell dessen Stichwahlergebnis mit dem Ergebnis vom 13. September.
            </span>
          </li>
          <li>
            <strong className="font-semibold">Die ausgezählten Bezirke bestimmten den aktuellen Trend.</strong>{" "}
            <span className="text-muted-foreground">
              Das Modell ermittelte getrennt für Urnen- und Briefwahlbezirke, wie sich Stimmenanteile und Stimmenzahlen seit dem
              ersten Wahlgang verändert hatten. Diese durchschnittlichen Veränderungen übertrug es auf die noch offenen Bezirke.
              Dadurch konnte die Hochrechnung von der laufenden Auszählung abweichen, wenn zunächst vor allem Bezirke meldeten,
              in denen einer der Kandidaten besonders stark war.
            </span>
          </li>
          <li>
            <strong className="font-semibold">Die angezeigte Wahrscheinlichkeit berücksichtigte die Streuung.</strong>{" "}
            <span className="text-muted-foreground">
              Je stärker die Ergebnisse der ausgezählten Bezirke vom Durchschnitt abwichen, desto unsicherer war die
              Hochrechnung. Eine Wahrscheinlichkeit zeigte das Modell erst ab {review?.min_districts ?? 15} ausgezählten
              Bezirken und höchstens mit {review?.chance_cap ?? 99} %, solange das Ergebnis nicht rechnerisch feststand.
            </span>
          </li>
          <li>
            <strong className="font-semibold">„Rechnerisch entschieden“ war keine Hochrechnung.</strong>{" "}
            <span className="text-muted-foreground">
              Dieser Hinweis erschien erst, wenn der tatsächliche Vorsprung größer war als die höchstmögliche Zahl aller noch
              offenen Stimmen.
            </span>
          </li>
        </ol>
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
          Das Modell wurde vor der Wahl festgelegt und anhand der Stichwahl 2021 mit denselben 133 Bezirken geprüft — auch mit
          rechnerisch knapperen Endständen. Es kann nicht erkennen, wie einzelne Menschen zwischen den Wahlgängen entschieden
          haben; es vergleicht ausschließlich Ergebnisse auf Bezirksebene.
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
      label: `nannte die Hochrechnung ${surname(winner)} als voraussichtlichen Sieger — und blieb bis zum Endstand bei dieser Aussage`,
    },
    {
      value: review.counted_right_from === null ? "–" : `ab Bezirk ${review.counted_right_from}`,
      label: `lag ${surname(winner)} auch in der laufenden Auszählung vorn — nach ${review.counted_lead_changes} Führungswechseln`,
    },
    {
      value:
        review.max_error_after_min_pts === null
          ? "–"
          : `${fixed(review.max_error_after_min_pts, 2)} Prozentpunkte`,
      label: `wich die Hochrechnung höchstens vom Endergebnis ab, nachdem sie erstmals eine Wahrscheinlichkeit anzeigte`,
    },
    {
      value: review.first_chance ? `${review.first_chance.chance_pct} %` : "–",
      label: review.first_chance
        ? `betrug die erste angezeigte Wahrscheinlichkeit nach ${review.first_chance.reports_received} Bezirken — ${review.chance_always_winner ? `sie bezog sich wie alle späteren auf ${surname(winner)}` : "später bezog sie sich zeitweise auf den anderen Kandidaten"}`
        : "es wurde keine Wahrscheinlichkeit angezeigt",
    },
  ];
  return (
    <section className={CARD}>
      <h2 className={H2}>Wie genau war die Hochrechnung?</h2>
      <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
        Endergebnis für {surname(winner)}: {prozent(review.final_share_pct)}.
        {first && first.projected_share_pct !== null
          ? ` Nach dem ersten gemeldeten Bezirk um ${uhrzeit(first.at)} Uhr erwartete das Modell ${prozent(first.projected_share_pct)}. Damit sah es bereits den Kandidaten vorn, der am Ende die meisten Stimmen erhielt; der erwartete Stimmenanteil änderte sich im weiteren Verlauf.`
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
        Ein einzelner Wahlabend reicht nicht aus, um die Zuverlässigkeit solcher Wahrscheinlichkeiten zu beurteilen. In der
        Prüfung vor der Wahl gewann der vom Modell mit 99 % bevorzugte Kandidat in 999 von 1.000 nachgestellten Auszählungen.
        Bei angezeigten Werten zwischen 90 und 98 % waren es 93 von 100.
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
      { label: "Ausgezählter Stand", value: prozent(p.counted_share_pct) },
      { label: "Hochrechnung", value: prozent(p.projected_share_pct) },
      { label: "Abweichung vom Endergebnis", value: p.error_pts === null ? "–" : pointsText(p.error_pts) },
      { label: "Wahrscheinlichkeit", value: p.chance_pct === null ? "–" : `${p.chance_pct} %` },
    ],
    vorlesen: `${p.reports_received} Bezirke, ${uhrzeit(p.at)} Uhr: ausgezählt ${prozent(p.counted_share_pct)}, Hochrechnung ${prozent(p.projected_share_pct)}.`,
  }));
  return (
    <div className="mt-5">
      <p className={KICKER}>Anteil für {surname(winner)} nach ausgezählten Bezirken</p>
      <ChartLegend
        className="mt-1.5"
        items={[
          { mark: "line-faint", color, label: "Zwischenstand" },
          { mark: "dashed", color, label: "Hochrechnung" },
          { mark: "rule", color: "hsl(var(--primary))", label: `Endergebnis ${prozent(review.final_share_pct)}` },
        ]}
      />
      <AbleseBeschreibung id={id}>
        Nach Zahl der ausgezählten Bezirke: der jeweilige Stimmenanteil von {winner.name} als Treppenlinie, die Hochrechnung
        gestrichelt und das Endergebnis von {prozent(review.final_share_pct)} als waagerechte Linie.
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
          gruppe="Zwischenstände des Abends"
        />
      </svg>
      <Ableseleiste stelle={stellen[control.aktiv]} steuerung={control} className="mt-3" haftet={false} />
    </div>
  );
}
