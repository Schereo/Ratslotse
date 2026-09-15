"use client";

// Der Verlauf der Stichwahl: EINE Linie über die Uhrzeit — der Anteil der
// einen Kandidatur, denn die andere ist ihr Spiegelbild. Die 50-Prozent-
// Linie ist die Frage des Abends: darüber vorn, darunter hinten. Gestrichelt
// daneben die Hochrechnung, dort wo sie kippt ein Punkt: Führungswechsel.
//
// Vorlage ist `verlauf.tsx` der Ratswahl (Treppe, keine erfundene
// Verbindung; eine Ableseleiste für Zeiger, Finger und Pfeiltasten). Die
// Punkte und die Wechsel kommen aus dem Backend (`history`, `lead_changes`).

import { scaleLinear, scaleTime } from "d3-scale";
import { curveStepAfter, line } from "d3-shape";
import {
  AbleseBeschreibung,
  AbleseFlaeche,
  Ableseleiste,
  useAblesen,
  useAbleseId,
  type AbleseStelle,
} from "@/components/grafik/ablesen";
import { prozent, uhrzeit, zahl } from "@/lib/wahlabend";
import { type Stichwahl, type StichwahlKandidat } from "@/lib/stichwahl";

const W = 480;
const H = 220;
const X0 = 44;
const X1 = W - 12;
const Y0 = H - 26;
const YTOP = 16;
const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** Wessen Anteil die Linie zeigt: wer im ersten Wahlgang vorn lag — das ist
 *  die Reihenfolge, in der Leute die beiden im Kopf haben. */
export function bezugsperson(kandidaten: readonly StichwahlKandidat[]): StichwahlKandidat | undefined {
  return [...kandidaten].sort((a, b) => (b.first_round_pct ?? 0) - (a.first_round_pct ?? 0))[0];
}

export function StichwahlVerlauf({ daten }: { daten: Stichwahl }) {
  const punkte = daten.history ?? [];
  const wer = bezugsperson(daten.candidates);
  const andere = daten.candidates.find((k) => k.slug !== wer?.slug);
  const steuerung = useAblesen(punkte.length, Math.max(punkte.length - 1, 0));
  const id = useAbleseId();
  if (punkte.length < 2 || !wer) {
    return (
      <section className="mt-5 rounded-2xl border border-dashed border-border p-4" data-testid="verlauf-leer">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Der Verlauf des Abends</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Füllt sich, sobald die ersten Wahlbezirke gemeldet sind: der Anteil über die Uhrzeit, die 50-Prozent-Linie und
          jeder Führungswechsel.
        </p>
      </section>
    );
  }
  const zeiten = punkte.map((p) => new Date(p.at));
  const xSkala = scaleTime().domain([zeiten[0], zeiten[zeiten.length - 1]]).range([X0, X1]);
  const x = (i: number) => xSkala(zeiten[i]);
  const ist = punkte.map((p) => p.shares[wer.slug] ?? null);
  const hoch = punkte.map((p) => p.projected_shares[wer.slug] ?? null);
  const alle = [...ist, ...hoch].filter((v): v is number => v !== null);
  const spanne = Math.max(6, ...alle.map((v) => Math.abs(v - 50))) + 2;
  const y = scaleLinear().domain([50 - spanne, 50 + spanne]).range([Y0, YTOP]);
  const ticks = y.ticks(4);
  const pfad = (werte: (number | null)[]) =>
    line<number | null>()
      .defined((v) => v !== null)
      .x((_, i) => x(i))
      .y((v) => y(v ?? 50))
      .curve(curveStepAfter)(werte) ?? "";
  const wechsel = (daten.lead_changes ?? [])
    .map((w) => ({ ...w, i: punkte.findIndex((p) => p.at === w.at) }))
    .filter((w) => w.i >= 0);
  const stellen: AbleseStelle[] = punkte.map((p, i) => ({
    title: uhrzeit(p.at) ? `${uhrzeit(p.at)} Uhr` : p.at,
    werte: [
      { label: wer.name, value: prozent(ist[i]), farbe: wer.color || undefined },
      ...(andere ? [{ label: andere.name, value: prozent(p.shares[andere.slug] ?? null), farbe: andere.color || undefined }] : []),
      { label: "Hochrechnung", value: hoch[i] === null ? "–" : prozent(hoch[i]) },
      { label: "Chance", value: p.chance_pct === null ? "–" : `${p.chance_pct} %` },
      { label: "Bezirke", value: `${zahl(p.reports_received)} von ${zahl(daten.reports_expected)}` },
    ],
    vorlesen: `${uhrzeit(p.at)} Uhr: ${wer.name} ${prozent(ist[i])}, Hochrechnung ${hoch[i] === null ? "noch keine" : prozent(hoch[i])}, ${p.reports_received} von ${daten.reports_expected} Wahlbezirken.`,
    anmerkung: wechsel.find((w) => w.i === i)
      ? `Führungswechsel — ${daten.candidates.find((k) => k.slug === wechsel.find((w) => w.i === i)?.leader)?.name ?? ""} liegt jetzt vorn.`
      : undefined,
  }));
  const zeitTicks = xSkala.ticks(4).map((t) => ({ x: xSkala(t), label: uhrzeit(t.toISOString()) ?? "" }));
  const farbe = wer.color ? `light-dark(${wer.color}, ${wer.color_dark || wer.color})` : "hsl(var(--primary))";
  return (
    <section className="mt-5 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]" data-testid="verlauf">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Der Verlauf des Abends</h2>
        <span className={KICKER}>
          {punkte.length} Stände · {uhrzeit(punkte[0].at)}–{uhrzeit(punkte[punkte.length - 1].at)} Uhr
          {wechsel.length > 0 ? ` · ${wechsel.length} Führungswechsel` : ""}
        </span>
      </div>
      <p className={`mt-1 ${KICKER}`}>
        Anteil {wer.name} · über 50 % vorn · gestrichelt die Hochrechnung
      </p>
      <AbleseBeschreibung id={id}>
        Eine Treppenlinie über die Uhrzeit: der Stimmenanteil von {wer.name}, dazu gestrichelt die Hochrechnung und die
        50-Prozent-Linie. {punkte.length} Stände, {wechsel.length} Führungswechsel.
      </AbleseBeschreibung>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 block w-full" role="group" aria-describedby={id}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={X0} y1={y(t)} x2={X1} y2={y(t)} className={t === 50 ? "stroke-foreground/50" : "stroke-border/60"} />
            <text x={X0 - 6} y={y(t) + 4} textAnchor="end" fontSize={10} className="fill-muted-foreground font-mono">
              {`${t.toFixed(0)} %`}
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
        <path d={pfad(hoch)} fill="none" stroke={farbe} strokeWidth={1.5} strokeDasharray="4 3" strokeOpacity={0.6} strokeLinejoin="round" />
        <path
          d={pfad(ist)}
          fill="none"
          className="gb-zeichnen"
          stroke={farbe}
          strokeWidth={2.25}
          strokeLinejoin="round"
          strokeLinecap="round"
          pathLength={1}
        />
        {wechsel.map((w) => (
          <g key={w.at} data-testid="fuehrungswechsel">
            <circle cx={x(w.i)} cy={y(ist[w.i] ?? 50)} r={5} className="fill-signal stroke-card" strokeWidth={2} />
          </g>
        ))}
        <AbleseFlaeche
          stellen={stellen}
          steuerung={steuerung}
          x={x}
          xVon={X0}
          xBis={X1}
          yVon={YTOP}
          hoehe={Y0 - YTOP}
          fangHoehe={H - YTOP}
          marken={(i) => (ist[i] === null ? [] : [{ y: y(ist[i] ?? 50), farbe }])}
          gruppe="Stände des Abends"
        />
      </svg>
      <Ableseleiste stelle={stellen[steuerung.aktiv]} steuerung={steuerung} className="mt-3" haftet={false} />
    </section>
  );
}
