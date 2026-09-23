"use client";

import Link from "next/link";
import { ArrowLeft, ChevronRight, Vote } from "lucide-react";
import { cn } from "@/lib/utils";
import { isDarkNow } from "@/lib/theme";
import {
  anteilIn, bezirkeIn, deckkraft, farbe, fuehrungText, lageSatz, prozent, punkte, werNachSlug,
  type Wahlkarte, type WahlkarteBezirk, type WahlkarteWer,
} from "@/lib/wahlkarte";

/** Die Tafel-Seite der Ebene „Wahlergebnis" (docs/plan-viertel-wahlkarte.md).
 *
 *  Auf der Karte trägt die Fläche die Parteifarbe (Designsprache § 2, die
 *  zweite Ausnahme); hier in der Spalte bleibt sie, was sie überall ist: ein
 *  Punkt neben dem Namen. Drei Bausteine, einer je Stufe:
 *
 *  - `WahlStadtTafel`   — die Legende der Stadt: wer in wie vielen Bezirken vorn lag.
 *  - `WahlViertelTafel` — die Bezirke, die den Ortsbereich berühren.
 *  - `WahlBezirkTafel`  — ein Bezirk mit allen Listen.
 */

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

function Punkt({ wer, className }: { wer: WahlkarteWer | undefined; className?: string }) {
  return (
    <span aria-hidden className={cn("inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-inset ring-black/10", className)}
      style={{ background: farbe(wer, isDarkNow()) }} />
  );
}

function datum(iso: string): string {
  const [j, m, t] = iso.split("-").map(Number);
  return new Date(j, m - 1, t).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
}

/** Die Wahl-Chips unter dem Ebenen-Chip: Ratswahl · OB-Wahl · Stichwahl. */
export function WahlChips({ daten, onWahl }: { daten: Wahlkarte; onWahl: (slug: string) => void }) {
  if (daten.elections.length < 2) return null;
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Welche Wahl">
      {daten.elections.map((w) => {
        const an = w.slug === daten.election.slug;
        return (
          <button key={w.slug} type="button" aria-pressed={an} onClick={() => onWahl(w.slug)}
            className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium shadow-sm backdrop-blur transition-colors",
              an ? "border-foreground bg-foreground text-background" : "border-border/70 bg-card/80 text-muted-foreground hover:text-foreground")}>
            {w.label}
          </button>
        );
      })}
    </div>
  );
}

/** Die Leiste „knapp ↔ deutlich" — was die Deckkraft bedeutet. */
function Deckkraftleiste({ wer }: { wer: WahlkarteWer | undefined }) {
  const c = farbe(wer, isDarkNow());
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
      <span>knapp</span>
      <span className="flex h-2.5 flex-1 overflow-hidden rounded-full" aria-hidden>
        {[0, 4, 8, 12, 16, 20].map((m) => (
          <span key={m} className="h-full flex-1" style={{ background: c, opacity: deckkraft(m) }} />
        ))}
      </span>
      <span>20 Pkt. Vorsprung</span>
    </div>
  );
}

function BriefwahlSatz({ daten }: { daten: Wahlkarte }) {
  if (daten.postal_share_pct == null) return null;
  const anteil = daten.postal_share_pct.toLocaleString("de-DE", { maximumFractionDigits: 0 });
  return (
    <p className="text-[12px] leading-relaxed text-muted-foreground">
      Farben nach den Wahllokalen. {anteil} % der Stimmen kamen per Brief — sie haben keinen Ort auf der Karte und stehen je Wahlbereich im Bezirk.
    </p>
  );
}

export function WahlStadtTafel({ daten, className, style }: { daten: Wahlkarte; className?: string; style?: React.CSSProperties }) {
  const wer = werNachSlug(daten);
  const gleich = daten.ties;
  const max = Math.max(1, ...daten.wins.map((w) => w.districts));
  return (
    <section aria-labelledby="wahlkarte-stadt" className={cn("flex flex-col gap-3 rounded-2xl border border-border bg-card p-4", className)} style={style}>
      <div>
        <p className={KICKER}><Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />{daten.election.label} · {datum(daten.election.date)}</p>
        <h2 id="wahlkarte-stadt" className="mt-0.5 font-display text-base font-bold text-foreground">
          {daten.counted === 0 ? "Noch kein Wahllokal gezählt" : "Wer in den Wahllokalen vorn lag"}
        </h2>
        <p className="mt-0.5 text-[12px] text-muted-foreground">
          {daten.counted === daten.total ? `alle ${daten.total} Urnenbezirke` : `${daten.counted} von ${daten.total} Urnenbezirken gezählt`}
        </p>
      </div>
      {daten.wins.length > 0 && (
        <ol className="flex flex-col gap-1.5">
          {daten.wins.map((w) => (
            <li key={w.slug} className="flex items-center gap-2.5 text-sm">
              <Punkt wer={wer.get(w.slug)} />
              <span className="min-w-0 flex-1 truncate font-medium text-foreground" title={wer.get(w.slug)?.name}>{wer.get(w.slug)?.short ?? w.slug}</span>
              <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
                <span className="block h-full rounded-full bg-primary/70" style={{ width: `${(100 * w.districts) / max}%` }} />
              </span>
              <span className="w-24 shrink-0 text-right font-mono text-[12px] tabular-nums text-foreground">
                vorn in {w.districts}
              </span>
            </li>
          ))}
          {gleich > 0 && (
            <li className="flex items-center gap-2.5 text-sm text-muted-foreground">
              <span aria-hidden className="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-dashed border-muted-foreground" />
              <span className="flex-1">Gleichstand</span>
              <span className="w-24 shrink-0 text-right font-mono text-[12px] tabular-nums">{gleich}</span>
            </li>
          )}
        </ol>
      )}
      <Deckkraftleiste wer={daten.wins[0] ? wer.get(daten.wins[0].slug) : daten.contestants[0]} />
      <BriefwahlSatz daten={daten} />
      <p className="text-[12px] text-muted-foreground">Tippe einen Stadtteil an, um seine Wahlbezirke zu sehen.</p>
      <Link href="/wahlabend" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
        Zum Wahlabend: Sitze, Mehrheiten, Verlauf →
      </Link>
    </section>
  );
}

/** Die Bezirke eines Ortsbereichs — größter Anteil zuerst; ein Tipp wählt ihn. */
export function WahlViertelTafel({ daten, ort, onBezirk, className, style }: {
  daten: Wahlkarte;
  ort: string;
  onBezirk: (nr: number) => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  const wer = werNachSlug(daten);
  const bezirke = bezirkeIn(daten, ort);
  return (
    <section aria-labelledby="wahlkarte-viertel" className={cn("flex flex-col gap-3 rounded-2xl border border-border bg-card p-4", className)} style={style}>
      <div>
        <p className={KICKER}><Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />{daten.election.label} · {datum(daten.election.date)}</p>
        <h2 id="wahlkarte-viertel" className="mt-0.5 font-display text-base font-bold text-foreground">
          {bezirke.length === 1 ? "Ein Wahlbezirk" : `${bezirke.length} Wahlbezirke`} in {ort}
        </h2>
        <p className="mt-0.5 text-[12px] text-muted-foreground">Die Stadt schneidet Wahlbezirke nicht nach Stadtteilen — manche liegen nur zum Teil hier.</p>
      </div>
      <ul className="-mx-1 flex flex-col">
        {bezirke.map((d) => {
          const a = anteilIn(d, ort);
          return (
            <li key={d.number}>
              <button type="button" onClick={() => onBezirk(d.number)} data-bezirk={d.number}
                className="group flex w-full items-center gap-2.5 rounded-lg px-1 py-2 text-left transition-colors hover:bg-accent">
                <span className="w-9 shrink-0 font-mono text-[12px] font-bold tabular-nums text-foreground">{d.number}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">{d.name}</span>
                  <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                    {d.leader && <Punkt wer={wer.get(d.leader)} className="h-2 w-2" />}
                    {fuehrungText(d, wer)}{d.leader ? ` · ${punkte(d.margin_pct)}` : ""}
                    {a < 0.8 && <span className="ml-1">· {Math.round(a * 100)} % hier</span>}
                  </span>
                </span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
              </button>
            </li>
          );
        })}
      </ul>
      <BriefwahlSatz daten={daten} />
    </section>
  );
}

/** Ein Bezirk mit ALLEN Listen — und der Wahlbereich mit Briefwahl daneben. */
export function WahlBezirkTafel({ daten, bezirk, ort, onZurueck }: {
  daten: Wahlkarte;
  bezirk: WahlkarteBezirk;
  ort: string | null;
  onZurueck: () => void;
}) {
  const wer = werNachSlug(daten);
  const bereich = daten.areas.find((a) => a.number === bezirk.area);
  const lage = lageSatz(bezirk, ort);
  const bereichAnteil = new Map((bereich?.parties ?? []).map((p) => [p.slug, p.share_pct]));
  const zeilen = bezirk.parties.filter((p) => (p.votes ?? 0) > 0 || !bezirk.counted);
  return (
    <section aria-labelledby="wahlkarte-bezirk" className="flex flex-col gap-3" data-testid="wahl-bezirk-tafel">
      <button type="button" onClick={onZurueck} className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" aria-hidden /> {ort ?? "Oldenburg"}
      </button>
      <div>
        <p className={KICKER}><Vote className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />{daten.election.label} · Wahlbezirk {bezirk.number}</p>
        <h2 id="wahlkarte-bezirk" className="mt-0.5 font-display text-xl font-bold text-foreground">{bezirk.name}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {!bezirk.counted ? "Noch nicht gezählt."
            : bezirk.leader ? <>Vorn: <b className="font-semibold text-foreground">{(daten.election.kind === "council" ? wer.get(bezirk.leader)?.short : wer.get(bezirk.leader)?.name) ?? bezirk.leader}</b>, {punkte(bezirk.margin_pct)} vor {wer.get(bezirk.runner_up ?? "")?.short ?? "Platz 2"}.</>
            : "Gleichstand an der Spitze."}
          {bezirk.turnout_pct != null && <> Beteiligung {prozent(bezirk.turnout_pct)}.</>}
        </p>
        {lage && <p className="mt-1 text-[12px] text-muted-foreground">{lage}</p>}
      </div>
      {bezirk.counted && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="border-b border-border bg-muted/50 px-3 py-2 text-[11px] font-medium text-muted-foreground">{daten.election.kind === "council" ? "Liste" : "Kandidatur"}</th>
                <th scope="col" className="border-b border-l border-border bg-muted/50 px-3 py-2 text-right text-[11px] font-medium text-muted-foreground">Anteil</th>
                <th scope="col" className="border-b border-l border-border bg-muted/50 px-3 py-2 text-right text-[11px] font-medium text-muted-foreground">Stimmen</th>
                <th scope="col" className="border-b border-l border-border bg-muted/50 px-3 py-2 text-right text-[11px] font-medium text-muted-foreground" title={`Wahlbereich ${bereich?.roman ?? ""} mit Briefwahl`}>WB {bereich?.roman}</th>
              </tr>
            </thead>
            <tbody>
              {zeilen.map((p, i) => {
                const c = wer.get(p.slug);
                const rand = i < zeilen.length - 1 ? "border-b border-border" : "";
                return (
                  <tr key={p.slug}>
                    <td className={cn("px-3 py-1.5", rand)}>
                      <span className="flex items-center gap-2">
                        <Punkt wer={c} />
                        <span className="min-w-0 truncate font-medium text-foreground" title={c?.name}>{c?.short ?? p.slug}</span>
                      </span>
                    </td>
                    <td className={cn("border-l border-border whitespace-nowrap px-3 py-1.5 text-right font-mono text-[12px] tabular-nums text-foreground", rand)}>{prozent(p.share_pct)}</td>
                    <td className={cn("border-l border-border whitespace-nowrap px-3 py-1.5 text-right font-mono text-[12px] tabular-nums text-muted-foreground", rand)}>{p.votes?.toLocaleString("de-DE") ?? "–"}</td>
                    <td className={cn("border-l border-border whitespace-nowrap px-3 py-1.5 text-right font-mono text-[12px] tabular-nums text-muted-foreground", rand)}>{prozent(bereichAnteil.get(p.slug))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {bereich && (
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          „WB {bereich.roman}" ist der ganze Wahlbereich {bereich.roman} mit Briefwahl — die Briefstimmen lassen sich keinem Wahllokal zuordnen.
        </p>
      )}
      <div className="flex flex-col gap-1">
        {daten.election.kind === "council" && bezirk.leader && (
          <Link href={`/wahlabend?liste=${encodeURIComponent(bezirk.leader)}`} className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            {wer.get(bezirk.leader)?.short} in allen Bezirken →
          </Link>
        )}
        <Link href={daten.election.label === "Stichwahl" ? "/wahlabend/stichwahl" : "/wahlabend"} className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
          Zum Wahlabend →
        </Link>
      </div>
    </section>
  );
}
