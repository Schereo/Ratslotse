"use client";

/* „Was der Haushaltsentwurf zeigt“ auf der Punkt-Seite (Schalter
   `haushaltsentwurf-befunde`, `council/budget_findings.py`). Tim, 23.11.2026:
   „die grafiken aus dem haushaltsentwurf analysieren und spannende effekte
   erläutern und anzeigen“ — nach dem Prototyp „die grafiken gefallen mir gut,
   gerne bauen“.

   Je Befund: Titel, die eine Zahl, ein Satz, die neu gezeichnete Grafik und
   der Weg zur Stelle im Vorbericht. Jede Zahl hat der Server gegen die Grafik
   im PDF geprüft, jede Deutung ein zweites Modell; die Art jeder Säule (Ist,
   Prognose, Plan, Finanzplanung) setzt der Server, nicht die Seite. Die
   ersten vier stehen offen, der Rest auf Knopfdruck — zehn Grafiken am Stück
   schoben „Frag den Rat“ zu weit nach unten. */

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Bruecke } from "@/components/grafik/bruecke";
import { deZahl } from "@/components/grafik/format";
import { RanglisteSchiene } from "@/components/grafik/rangliste-schiene";
import { ArtLegende, VorzeichenSaeulen } from "@/components/grafik/vorzeichen-saeulen";
import { KiStern } from "@/components/ki-stern";
import { KARTENTITEL, META, ZITAT } from "@/components/session/unterlagen-typo";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";

export type HaushaltsBefunde = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["budget_findings"]>;
type Befund = HaushaltsBefunde["findings"][number];

const OFFEN = 4;
const HINWEIS = "Automatisch aus den Grafiken des Vorberichts erstellt: jede Zahl gegen die Grafik geprüft, jede Deutung von einem zweiten Modell. Verbindlich ist der Vorbericht im Ratsinfo.";

function nachkomma(v: number) {
  return Number.isInteger(v) || Math.abs(v) >= 1000 ? 0 : 1;
}

function Grafik({ b }: { b: Befund }) {
  const v = b.visual;
  const satz = `${b.title}. ${b.text}`;
  if (v.type === "columns" && v.categories && v.series) {
    const kinds = v.kinds ?? [];
    // Die Legende in der Schiefer-Rampe nur, wenn ALLE Säulen unter null stehen —
    // eine gemischte Reihe beginnt fast immer mit Überschüssen.
    const werte = v.series.flatMap((r) => r.values.filter((x): x is number => x != null));
    const minus = werte.length > 0 && werte.every((x) => x <= 0);
    return (
      <>
        <VorzeichenSaeulen categories={v.categories} kinds={kinds} series={v.series} stacked={v.stacked}
          highlight={v.highlight} unit={v.unit} label={satz} />
        <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <ArtLegende kinds={kinds} minus={minus} />
          {v.series.length > 1 && <span className={META}>{v.series.map((r) => r.name).join(" · ")}</span>}
          <span className={cn(META, "ml-auto")}>in {v.unit}</span>
        </div>
      </>
    );
  }
  if (v.type === "bridge" && v.start && v.end && v.steps) {
    return (
      <>
        <Bruecke start={v.start} steps={v.steps} end={v.end} unit={v.unit} label={satz} />
        <p className={cn(META, "mt-1 text-right")}>in {v.unit}</p>
      </>
    );
  }
  if (v.type === "bars" && v.rows?.length) {
    const negativ = v.rows.some((r) => r.value < 0);
    const werte = v.rows.map((r) => r.value);
    return (
      <RanglisteSchiene unit={v.unit} nachkomma={1}
        schiene={negativ ? [Math.min(0, ...werte), Math.max(0, ...werte)] : "null-bis-max"}
        zeilen={v.rows.map((r) => ({
          label: r.label, value: r.value,
          zusatz: r.change != null ? `Veränderung ${r.change > 0 ? "+" : ""}${deZahl(r.change, 1)} ${v.unit}` : undefined,
        }))} />
    );
  }
  return null;
}

function BefundKarte({ b, url }: { b: Befund; url: string | null }) {
  const k = b.key_figure;
  const stelle = [b.chart && `Grafik ${b.chart}`, b.page && `Vorbericht, S. ${b.page}`].filter(Boolean).join(" · ");
  const ziel = url && b.page ? `${url}#page=${b.page}` : url;
  return (
    <li className="border-t border-border pt-5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <h3 className="min-w-0 flex-1 basis-64 font-display text-base font-semibold leading-snug text-foreground [text-wrap:balance]">
          {b.title}
        </h3>
        <p className="sm:text-right">
          <span className="block font-display text-[26px] font-bold leading-none tabular-nums text-foreground">
            {deZahl(k.value, nachkomma(k.value))}
            <span className="ml-1 font-sans text-sm font-medium text-muted-foreground">{k.unit}</span>
          </span>
          {k.label && <span className={cn(META, "mt-1 block")}>{k.label}</span>}
        </p>
      </div>
      <p className="mt-2 text-lese text-foreground">{b.text}</p>
      <div className="mt-3">
        <Grafik b={b} />
      </div>
      {b.quote && (
        <blockquote className={cn(ZITAT, "mt-3")}>
          „{b.quote}“
          {b.quote_page && b.quote_page !== b.page && <span className={cn(META, "ml-1.5 whitespace-nowrap")}>S. {b.quote_page}</span>}
        </blockquote>
      )}
      {stelle && (
        <p className={cn(META, "mt-2")}>
          {ziel ? (
            <a href={ziel} target="_blank" rel="noreferrer"
              className="inline-flex min-h-8 items-center gap-1 underline decoration-dashed underline-offset-2 hover:text-foreground">
              {stelle} <ExternalLink className="h-3 w-3 flex-none" aria-hidden />
            </a>
          ) : stelle}
        </p>
      )}
    </li>
  );
}

export function HaushaltsentwurfBefunde({ befunde }: { befunde?: HaushaltsBefunde | null }) {
  const [alle, setAlle] = useState(false);
  if (!befunde?.findings.length) return null;
  const vorne = befunde.findings.slice(0, OFFEN);
  const rest = befunde.findings.slice(OFFEN);
  return (
    <section aria-labelledby="haushaltsentwurf" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h2 id="haushaltsentwurf" className={cn(KARTENTITEL, "flex items-center gap-1")}>
        Was der Haushaltsentwurf zeigt
        <KiStern text={HINWEIS} />
      </h2>
      <p className={cn(META, "mt-1")}>
        {befunde.findings.length === 1 ? "Ein Befund" : `${befunde.findings.length} Befunde`} aus den Grafiken des
        Vorberichts{befunde.budget_year ? ` zum Haushalt ${befunde.budget_year}` : ""}, neu gezeichnet.
      </p>
      <ul className="mt-5 flex flex-col gap-5">
        {vorne.map((b, i) => <BefundKarte key={`${b.chart}-${i}`} b={b} url={befunde.url} />)}
      </ul>
      {rest.length > 0 && (
        <>
          <Aufklapp offen={alle}>
            <ul className="mt-5 flex flex-col gap-5 border-t border-border pt-5">
              {rest.map((b, i) => <BefundKarte key={`${b.chart}-${i}`} b={b} url={befunde.url} />)}
            </ul>
          </Aufklapp>
          <button type="button" onClick={() => setAlle((a) => !a)} aria-expanded={alle}
            className="mt-3 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", alle && "rotate-180")} aria-hidden />
            {alle ? "Weniger zeigen" : `Weitere Befunde`} {!alle && <span className="text-muted-foreground">{rest.length}</span>}
          </button>
        </>
      )}
    </section>
  );
}
