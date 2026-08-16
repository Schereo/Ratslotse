"use client";

// „Bis wann reichen die Zahlen?" — der Datenstand des Haushalts-Bereichs.
//
// Kein Betreiber-Werkzeug, sondern die Antwort auf eine echte Leserfrage:
// Auf /haushalt steht der Plan für 2026, auf /haushalt/plan-ist die
// Abrechnung für 2024, auf /haushalt/pruefung Feststellungen bis 2023 — und
// jede dieser Seiten müsste sonst für sich erklären, warum. Die Ursache ist
// immer dieselbe und liegt bei der Stadt: Der Plan kommt im Oktober für das
// kommende Jahr, die Abrechnung im September für das vorletzte. Zwischen
// September und Oktober liegt für einen Jahrgang deshalb immer nur die eine
// Hälfte vor. Das steht hier einmal, in Sätzen statt in einer Matrix.
//
// Bewusst eine eigene Datei: Der Block hängt an einem eigenen Endpunkt, und
// eine Änderung an den Texten der Übersichtsseite soll ihn nicht anfassen.

import { CalendarClock, Check, Clock } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

export type Datenschicht = {
  key: string;
  label: string;
  was: string;
  jahrgaenge: number[];
  luecken: number[];
  neuester: number | null;
  offen: number[];
  ueberfaellig: number[];
  naechster_jahrgang: number;
  naechster_ab: string;
  erwarteter_monat: number;
  monat: string;
  herkunft: string;
  automatisch: boolean;
};

type Antwort = { heute: string; schichten: Datenschicht[] };

/** „2017–2024" bzw. „2024" — und nichts, wo nichts ist. */
function spanne(jahre: number[]): string | null {
  if (jahre.length === 0) return null;
  const von = jahre[0], bis = jahre[jahre.length - 1];
  return von === bis ? String(von) : `${von}–${bis}`;
}

/** Was als Nächstes ansteht, als Satz.
 *
 *  Zwei Fälle, und der Unterschied ist der ganze Punkt: Ein Jahrgang, dessen
 *  Monat noch bevorsteht, ist keine Lücke — er ist einfach noch nicht
 *  erschienen. Erst danach lohnt der Hinweis, dass er auf sich warten lässt.
 *  „Fehlt" steht deshalb nirgends: Was die Stadt noch nicht veröffentlicht
 *  hat, fehlt uns nicht. */
function ausblick(s: Datenschicht, heute: string): { text: string; wartet: boolean } {
  const jahr = s.naechster_jahrgang;
  const ab = new Date(s.naechster_ab);
  const monatJahr = `${s.monat} ${ab.getFullYear()}`;
  if (s.ueberfaellig.includes(jahr)) {
    return {
      text: `Der Jahrgang ${jahr} wäre seit ${monatJahr} zu erwarten und liegt noch nicht vor.`,
      wartet: true,
    };
  }
  if (new Date(heute) < ab) {
    return { text: `Der Jahrgang ${jahr} wird üblicherweise im ${monatJahr} vorgelegt.`, wartet: false };
  }
  return { text: `Der Jahrgang ${jahr} wird gerade erwartet (üblich: ${monatJahr}).`, wartet: false };
}

export function Datenstand() {
  const { data } = useFetch<Antwort>("/council/haushalt/datenstand");
  // Still bleiben, solange nichts da ist: Ein Skelett für einen Nachtrag am
  // Seitenende wäre mehr Unruhe als Information.
  if (!data || data.schichten.length === 0) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-xl bg-primary/10 text-primary">
          <CalendarClock size={16} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stand der Daten
          </p>
          <h2 className="mt-1 font-display text-[16px] font-bold tracking-tight">
            Bis wann die Zahlen reichen
          </h2>
          <p className="mt-1 max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Die Stadt legt ihre Zahlen zu verschiedenen Zeiten vor: den Plan im Herbst für das
            kommende Jahr, die Abrechnung ein knappes Jahr nach dessen Ende. Deshalb reicht nicht
            jede Seite gleich weit.
          </p>
        </div>
      </div>

      <ul className="mt-3.5 flex flex-col gap-2.5 border-t border-dashed border-border pt-3.5">
        {data.schichten.map((s) => {
          const bereich = spanne(s.jahrgaenge);
          const { text, wartet } = ausblick(s, data.heute);
          return (
            <li key={s.key} className="flex flex-col gap-1">
              {/* Titel und Jahresspanne auf einer Zeile, in jeder Breite: Die
                  Spanne ist die Antwort, die hier jemand sucht. Unter dem Satz
                  stehend (nur `sm:` rechtsbündig) landete sie auf 375 px als
                  Letztes und links — also genau dort, wo niemand hinsieht. */}
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 text-[13px] font-bold leading-snug">{s.label}</span>
                <span className="flex-none font-mono text-[11.5px] font-medium tabular-nums text-foreground/80">
                  {bereich ?? "—"}
                </span>
              </div>
              <span className="text-[12px] leading-relaxed text-muted-foreground">{s.was}</span>
              <span className={cn(
                "flex items-start gap-1.5 text-[11.5px] leading-relaxed",
                wartet ? "text-foreground/80" : "text-muted-foreground",
              )}>
                {wartet
                  ? <Clock size={12} strokeWidth={2} className="mt-[3px] flex-none" />
                  : <Check size={12} strokeWidth={2} className="mt-[3px] flex-none" />}
                <span>
                  {text}
                  {s.luecken.length > 0 && (
                    <> Für {s.luecken.join(", ")} liegen uns keine auswertbaren Zahlen vor.</>
                  )}
                </span>
              </span>
            </li>
          );
        })}
      </ul>

      <p className="mt-3.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Wir tragen neue Jahrgänge automatisch nach, sobald die Stadt sie im
        Ratsinformationssystem veröffentlicht — geprüft wird alle zwei Wochen. Zahlen, die eine
        Rechenprobe des Dokuments nicht bestehen, bleiben draußen; dann steht hier weiter der
        ältere Stand.
      </p>
    </div>
  );
}
