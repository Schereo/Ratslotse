"use client";

// „Was die Verwaltung zu diesem Bereich schreibt" — Karte im Überblick von
// /haushalt/bereich (Plan Haushalt-Datenquellen, PR 5).
//
// Quelle: der Vorbericht des Haushaltsplans (Anlage 001), Abschnitte 2.4.2.x
// (Ergebnishaushalt) und 3.2.2.x (Investitionen) je Teilhaushalt.
//
// WORTLAUT, NIE ZUSAMMENGEFASST (dieselbe Regel wie <Warum>): Eine
// Zusammenfassung wäre ein Text, den niemand geschrieben und niemand
// beschlossen hat. Gekürzt wird die DARSTELLUNG — die ersten beiden Absätze
// sichtbar, der Rest hinter einem Auslöser (H4-A: weglassen heißt hinter
// einen Auslöser, nie ersatzlos).

import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { Beleg } from "@/components/haushalt/source";
import { cn } from "@/lib/utils";

type Antwort = ApiAntwort<"/council/budget/notes">;
type Abschnitt = Antwort["notes"][number];

const SICHTBAR = 2;

function Wortlaut({ titel, a }: { titel: string; a: Abschnitt }) {
  const [offen, setOffen] = useState(false);
  const absaetze = a.text.split("\n\n").filter(Boolean);
  const zeigen = offen ? absaetze : absaetze.slice(0, SICHTBAR);
  return (
    <div className="flex flex-col gap-2">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {titel}
      </p>
      {zeigen.map((t, i) => (
        <p key={i} className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">{t}</p>
      ))}
      {absaetze.length > SICHTBAR && (
        <button type="button" onClick={() => setOffen((o) => !o)}
          className="inline-flex w-fit items-center gap-1 text-[12.5px] font-semibold text-primary">
          {offen ? "Weniger zeigen" : absaetze.length - SICHTBAR === 1
            ? "Ganzen Wortlaut zeigen (1 weiterer Absatz)"
            : `Ganzen Wortlaut zeigen (${absaetze.length - SICHTBAR} weitere Absätze)`}
          <ChevronDown aria-hidden className={cn("h-3.5 w-3.5 transition-transform", offen && "rotate-180")} />
        </button>
      )}
    </div>
  );
}

export function VorberichtBereich({ subBudget }: { subBudget: number }) {
  const { data } = useFetch<Antwort>(`/council/budget/notes?sub_budget=${subBudget}`);
  const jahre = useMemo(
    () => [...new Set((data?.notes ?? []).map((n) => n.budget_year))].sort((a, b) => b - a),
    [data]);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const jahr = gewaehlt ?? jahre[0];
  if (!jahr) return null;
  const im = (kind: string) => data?.notes.find((n) => n.budget_year === jahr && n.kind === kind);
  const ergebnis = im("result");
  const invest = im("investments");

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-[70ch]">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Vorbericht zum Haushaltsplan {jahr} · Wortlaut
          </p>
          <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
            Was die Verwaltung zu diesem Bereich schreibt<Beleg q="budget_notes" />
          </h2>
        </div>
        {jahre.length > 1 && (
          <div role="group" aria-label="Haushaltsplan wählen" className="flex flex-wrap gap-1">
            {jahre.map((j) => (
              <button key={j} type="button" onClick={() => setGewaehlt(j)}
                aria-pressed={j === jahr}
                className={cn(
                  "min-h-[28px] rounded-full border px-2.5 font-mono text-[11px] tabular-nums",
                  j === jahr ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-primary/40")}>
                {j}
              </button>
            ))}
          </div>
        )}
      </div>
      {ergebnis && <Wortlaut key={`e${jahr}`} titel="Zum Ergebnis" a={ergebnis} />}
      {invest && (
        <div className="border-t border-dashed border-border pt-3">
          <Wortlaut key={`i${jahr}`} titel="Zu den Investitionen" a={invest} />
        </div>
      )}
      <p className="text-[11.5px] leading-relaxed text-muted-foreground">
        Der Text steht so im Vorbericht des Verwaltungsentwurfs (Anlage 001,{" "}
        {[ergebnis?.page, invest?.page].filter(Boolean).length > 1
          ? `Seiten ${ergebnis?.page} und ${invest?.page}` : `Seite ${ergebnis?.page ?? invest?.page}`}).
        Tabellen und Grafiken des Originals sind nicht wiedergegeben; wo der Text auf sie verweist
        („wie folgt“), stehen sie im Dokument.
      </p>
    </section>
  );
}
