"use client";

// Der Verlauf des Abends: links der Stimmenanteil einer Liste, rechts der
// Auszählungsstand — beide über die Uhrzeit, beide als Treppe, denn zwischen
// zwei Meldungen ändert sich nichts (Grafik-Baukasten: `curveStepAfter`,
// keine erfundene Verbindung). Eine Ableseleiste für beide Bilder; Zeiger,
// Finger oder Pfeiltasten wechseln die Stelle in beiden zugleich.

import { scaleLinear, scaleTime } from "d3-scale";
import { area, curveStepAfter, line } from "d3-shape";
import {
  AbleseBeschreibung,
  AbleseFlaeche,
  Ableseleiste,
  useAblesen,
  useAbleseId,
  type AbleseStelle,
} from "@/components/grafik/ablesen";
import { prozent, uhrzeit, zahl, type Wahlabend, type WahlabendPartei } from "@/lib/wahlabend";

const W = 480;
const H = 200;
const X0 = 40;
const X1 = W - 12;
const Y0 = H - 26;
const YTOP = 14;
const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

type Punkt = Wahlabend["history"][number];

function Bild({
  titel,
  werte,
  x,
  yMax,
  einheit,
  flaeche,
  steuerung,
  stellen,
  id,
  zeitTicks,
}: {
  titel: string;
  werte: number[];
  x: (i: number) => number;
  yMax: number;
  einheit: (v: number) => string;
  flaeche: boolean;
  steuerung: ReturnType<typeof useAblesen>;
  stellen: AbleseStelle[];
  id: string;
  zeitTicks: { x: number; label: string }[];
}) {
  const y = scaleLinear().domain([0, yMax]).range([Y0, YTOP]).nice();
  const ticks = y.ticks(3);
  const pfad = line<number>()
    .x((_, i) => x(i))
    .y((v) => y(v))
    .curve(curveStepAfter)(werte) ?? "";
  const fl = area<number>()
    .x((_, i) => x(i))
    .y0(Y0)
    .y1((v) => y(v))
    .curve(curveStepAfter)(werte) ?? "";
  return (
    <div>
      <p className={KICKER}>{titel}</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 block w-full" role="group" aria-describedby={id}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={X0} y1={y(t)} x2={X1} y2={y(t)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(t) + 4} textAnchor="end" fontSize={10} className="fill-muted-foreground font-mono">
              {einheit(t)}
            </text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />
        {zeitTicks.map((t) => (
          <text
            key={t.label}
            x={t.x}
            y={H - 8}
            textAnchor={t.x > X1 - 18 ? "end" : t.x < X0 + 18 ? "start" : "middle"}
            fontSize={10}
            className="fill-muted-foreground font-mono"
          >
            {t.label}
          </text>
        ))}
        {flaeche ? <path d={fl} className="fill-primary/10" /> : null}
        <path
          d={pfad}
          fill="none"
          className="gb-zeichnen stroke-primary"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          pathLength={1}
        />
        <AbleseFlaeche
          stellen={stellen}
          steuerung={steuerung}
          x={x}
          xVon={X0}
          xBis={X1}
          yVon={YTOP}
          hoehe={Y0 - YTOP}
          fangHoehe={H - YTOP}
          marken={(i) => [{ y: y(werte[i] ?? 0), farbe: "hsl(var(--primary))" }]}
          gruppe="Stände des Abends"
        />
      </svg>
    </div>
  );
}

export function Verlauf({ daten, liste }: { daten: Wahlabend; liste: string | null }) {
  const punkte: Punkt[] = daten.history ?? [];
  const partei: WahlabendPartei | undefined =
    daten.parties.find((p) => p.slug === liste) ??
    [...daten.parties].sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0))[0];
  const steuerung = useAblesen(punkte.length, Math.max(punkte.length - 1, 0));
  const id = useAbleseId();
  if (punkte.length < 2 || !partei) {
    return (
      <section className="mt-6 rounded-2xl border border-dashed border-border p-4">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Der Verlauf des Abends</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Füllt sich, sobald die ersten Wahlbezirke gemeldet sind: Anteil der gewählten Liste und Auszählungsstand über die
          Uhrzeit.
        </p>
      </section>
    );
  }
  const zeiten = punkte.map((p) => new Date(p.at));
  const xSkala = scaleTime().domain([zeiten[0], zeiten[zeiten.length - 1]]).range([X0, X1]);
  const x = (i: number) => xSkala(zeiten[i]);
  const anteile = punkte.map((p) => p.shares[partei.slug] ?? 0);
  const sitze = punkte.map((p) => p.seats[partei.slug] ?? 0);
  const gezaehlt = punkte.map((p) => p.districts_counted);
  const gesamt = daten.progress.districts_total;
  const stellen: AbleseStelle[] = punkte.map((p, i) => ({
    title: uhrzeit(p.at) ? `${uhrzeit(p.at)} Uhr` : p.at,
    werte: [
      { label: `Anteil ${partei.short}`, value: prozent(anteile[i]), farbe: partei.color },
      { label: "Sitze", value: String(sitze[i]) },
      { label: "Ausgezählt", value: `${zahl(gezaehlt[i])} von ${zahl(gesamt)}` },
    ],
    vorlesen: `${uhrzeit(p.at)} Uhr: ${partei.short} ${prozent(anteile[i])}, ${sitze[i]} Sitze, ${gezaehlt[i]} von ${gesamt} Wahlbezirken ausgezählt.`,
  }));
  const zeitTicks = xSkala.ticks(4).map((t) => ({ x: xSkala(t), label: uhrzeit(t.toISOString()) ?? "" }));
  return (
    <section className="mt-6 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] @container">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Der Verlauf des Abends</h2>
        <span className={KICKER}>
          {punkte.length} Stände · {uhrzeit(punkte[0].at)}–{uhrzeit(punkte[punkte.length - 1].at)} Uhr
        </span>
      </div>
      <AbleseBeschreibung id={id}>
        Zwei Treppenlinien über die Uhrzeit: der Stimmenanteil von {partei.short} und die Zahl der ausgezählten Wahlbezirke,{" "}
        {punkte.length} Stände.
      </AbleseBeschreibung>
      <div className="mt-3 grid gap-4 @3xl:grid-cols-2">
        <Bild
          titel={`Anteil ${partei.short}`}
          werte={anteile}
          x={x}
          yMax={Math.max(1, ...anteile) * 1.15}
          einheit={(v) => `${v.toFixed(v < 10 ? 1 : 0).replace(".", ",")} %`}
          flaeche={false}
          steuerung={steuerung}
          stellen={stellen}
          id={id}
          zeitTicks={zeitTicks}
        />
        <Bild
          titel="Ausgezählte Wahlbezirke"
          werte={gezaehlt}
          x={x}
          yMax={gesamt}
          einheit={(v) => String(Math.round(v))}
          flaeche
          steuerung={steuerung}
          stellen={stellen}
          id={id}
          zeitTicks={zeitTicks}
        />
      </div>
      <Ableseleiste stelle={stellen[steuerung.aktiv]} steuerung={steuerung} className="mt-3" haftet={false} />
    </section>
  );
}
