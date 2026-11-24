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
   schoben „Frag den Rat“ zu weit nach unten.

   Darüber seit 24.11.2026 ein Abriss (Tim: „vorher allgemein ein paar Sachen
   zum Haushaltsentwurf sagen … wofür ist der Haushaltsentwurf überhaupt da …
   dass die Stadt in die Haushaltskonsolidierung rutscht“): wozu es einen
   Haushalt gibt (fester Text vom Server), das Gesamtbild in belegten Sätzen
   und drei, vier Eckzahlen. Fachwörter wie „Haushaltssicherung“ erklärt das
   Glossar am Wort. */

import { useState, type CSSProperties } from "react";
import { ChevronDown } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Bruecke } from "@/components/grafik/bruecke";
import { deZahl } from "@/components/grafik/format";
import { RanglisteSchiene } from "@/components/grafik/rangliste-schiene";
import { ArtLegende, VorzeichenSaeulen } from "@/components/grafik/vorzeichen-saeulen";
import { KiStern } from "@/components/ki-stern";
import { ErklaerBereich, Erklaert } from "@/components/session/begriffe";
import { Beleg, type BelegDaten } from "@/components/session/dossier";
import { ABSCHNITT, KARTENTITEL, META } from "@/components/session/unterlagen-typo";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";

export type HaushaltsBefunde = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["budget_findings"]>;
type Befund = HaushaltsBefunde["findings"][number];
type Gesamtbild = NonNullable<HaushaltsBefunde["overview"]>;
type Hinweis = NonNullable<HaushaltsBefunde["notice"]>;

const OFFEN = 4;
const HINWEIS = "Automatisch aus den Grafiken des Vorberichts erstellt: jede Zahl gegen die Grafik geprüft, jede Deutung von einem zweiten Modell. Verbindlich ist der Vorbericht im Ratsinfo.";

/** Ein Verweis in den Vorbericht — Nummer am Satz, der Tipp zeigt Grafik,
 *  Seite, Zitat und springt ins PDF. Alle Verweise der Karte tragen diese
 *  eine Form, durchnummeriert (Tim, 24.11.2026: „warum können nicht alles
 *  die zahlen referenzen sein?“). */
function verweis(url: string | null, n: number, page: number | null, chart?: string | null,
                 quote?: string | null): BelegDaten {
  return {
    list_no: n, page, quote,
    doc_label: chart ? `Vorbericht, Grafik ${chart}` : "Vorbericht",
    url: url ? (page ? `${url}#page=${page}` : url) : null,
  };
}

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

function BefundKarte({ b, url, n }: { b: Befund; url: string | null; n: number }) {
  const k = b.key_figure;
  // Steht das Zitat auf einer anderen Seite als die Grafik, trägt es eine eigene Nummer.
  const zitatEigen = !!b.quote && !!b.quote_page && b.quote_page !== b.page;
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
      <ErklaerBereich className="mt-2">
        <p className="text-lese text-foreground">
          <Erklaert text={b.text} />
          <Beleg a={verweis(url, n, b.page, b.chart, zitatEigen ? null : b.quote)} />
          {zitatEigen && <Beleg a={verweis(url, n + 1, b.quote_page ?? null, null, b.quote)} />}
        </p>
      </ErklaerBereich>
      <div className="mt-3">
        <Grafik b={b} />
      </div>
    </li>
  );
}

/** Die Nummern der Verweise, in der Folge der Karte: Hinweis, Gesamtbild,
 *  Eckzahlen, dann je Befund eine (zwei, wenn sein Zitat woanders steht). */
function nummern(b: HaushaltsBefunde) {
  let n = 1;
  const hinweis = b.notice ? n++ : 0;
  const saetze = (b.overview?.statements ?? []).map(() => n++);
  const zahlen = (b.overview?.facts ?? []).map(() => n++);
  const befunde = b.findings.map((f) => {
    const eigen = n;
    n += f.quote && f.quote_page && f.quote_page !== f.page ? 2 : 1;
    return eigen;
  });
  return { hinweis, saetze, zahlen, befunde };
}

function Abriss({ about, gesamt, hinweis, url, nr }: {
  about: string; gesamt?: Gesamtbild | null; hinweis?: Hinweis | null; url: string | null;
  nr: ReturnType<typeof nummern>;
}) {
  return (
    <div className="mt-2">
      <p className={META}>
        <span className={cn(ABSCHNITT, "mr-1.5")}>Worum es geht</span>{about}
      </p>
      {/* Wörtlich aus dem Vorbericht, ohne Modell — darum in
          Anführungszeichen (council/budget_findings.py::notice). */}
      {hinweis && (
        <ErklaerBereich className="mt-4">
          <blockquote className="rounded-lg border-l-[3px] border-primary bg-primary/[0.07] px-3 py-2.5 text-lese text-foreground">
            „<Erklaert text={hinweis.text} />“
            <Beleg a={verweis(url, nr.hinweis, hinweis.page)} />
          </blockquote>
        </ErklaerBereich>
      )}
      {gesamt && (
        <>
          <h3 className={cn(ABSCHNITT, "mt-5")}>Das Gesamtbild</h3>
          {/* Belege wie im Dossier: eine Nummer am Satz, der Tipp zeigt das
              wörtliche Zitat und springt ins PDF — keine Seitenzahl im Lesetext
              (Tim, 24.11.2026: „sehen irgendwie komisch aus“). */}
          <ul className="mt-2 flex list-disc flex-col gap-1.5 pl-5 marker:text-muted-foreground">
            {gesamt.statements.map((s, i) => (
              <li key={i} className="text-lese text-foreground">
                <ErklaerBereich>
                  <Erklaert text={s.text} />
                  <Beleg a={verweis(url, nr.saetze[i], s.page, null, s.quote)} />
                </ErklaerBereich>
              </li>
            ))}
          </ul>
          {gesamt.facts.length > 0 && (
            // So viele Spalten wie Eckzahlen (zwei bis vier) — vier feste Spalten
            // ließen bei zwei Zahlen die halbe Zeile leer.
            <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-[repeat(var(--n),minmax(0,1fr))]"
              style={{ "--n": Math.max(2, gesamt.facts.length) } as CSSProperties}>
              {gesamt.facts.map((f, i) => (
                <li key={i} className="flex flex-col rounded-xl border border-border bg-muted/40 p-3">
                  <span className="font-display text-[22px] font-bold leading-none tabular-nums text-foreground">
                    {deZahl(f.value, nachkomma(f.value))}
                    <span className="ml-1 font-sans text-xs font-medium text-muted-foreground">{f.unit}</span>
                  </span>
                  <span className="mt-1.5 text-meta leading-snug text-foreground">
                    {f.label}
                    <Beleg a={verweis(url, nr.zahlen[i], f.page, f.chart, f.quote)} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

export function HaushaltsentwurfBefunde({ befunde }: { befunde?: HaushaltsBefunde | null }) {
  const [alle, setAlle] = useState(false);
  if (!befunde?.findings.length) return null;
  const nr = nummern(befunde);
  const vorne = befunde.findings.slice(0, OFFEN);
  const rest = befunde.findings.slice(OFFEN);
  return (
    <section aria-labelledby="haushaltsentwurf" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h2 id="haushaltsentwurf" className={cn(KARTENTITEL, "flex items-center gap-1")}>
        Was der Haushaltsentwurf zeigt
        <KiStern text={HINWEIS} />
      </h2>
      <Abriss about={befunde.about} gesamt={befunde.overview} hinweis={befunde.notice} url={befunde.url} nr={nr} />
      <h3 className={cn(ABSCHNITT, "mt-6 border-t border-border pt-5")}>Aus den Grafiken</h3>
      <ul className="mt-4 flex flex-col gap-5">
        {vorne.map((b, i) => <BefundKarte key={`${b.chart}-${i}`} b={b} url={befunde.url} n={nr.befunde[i]} />)}
      </ul>
      {rest.length > 0 && (
        <>
          <Aufklapp offen={alle}>
            <ul className="mt-5 flex flex-col gap-5 border-t border-border pt-5">
              {rest.map((b, i) => <BefundKarte key={`${b.chart}-${i}`} b={b} url={befunde.url} n={nr.befunde[OFFEN + i]} />)}
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
