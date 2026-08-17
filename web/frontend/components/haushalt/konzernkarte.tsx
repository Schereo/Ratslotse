"use client";

// Konzernkarte (H3-02): Wer gehört zur Stadt — als Formen-Sprache statt
// Organigramm-Grafik.
//
// BEWUSST KEIN FORCE-LAYOUT (GB-15: d3-force bleibt draußen): 15 Knoten mit
// Formen-Chips in drei Gruppen sind lesbarer, deterministisch und
// exportierbar — ein Force-Graph wackelte bei jedem Laden anders. Die
// Gruppen sind die des Berichts selbst (2.2 Eigenbetriebe, 2.3 Anstalten,
// 2.4 privatrechtliche Organisationsformen); die Zuordnung rechnet
// `lib/haushalt-beteiligungen.rechtsform` aus der Gliederungsnummer.
//
// DIE FORM SAGT, WIE NAH EINE EINHEIT DER STADT STEHT (H3-02):
//   ■ Eigenbetrieb — Teil der Stadt, gefülltes Quadrat.
//   ◆ Anstalt öffentlichen Rechts — eigenständig öffentlich, Raute mit Rand.
//   ● GmbH / Co. KG — privatrechtlich, Kreis mit Rand.
// Unterschieden wird über FORM UND FÜLLUNG, nicht über Farbe — so bleibt die
// Karte im Graustufendruck und in beiden Themes lesbar. Alle drei tragen
// denselben Rampenton; keine Form ist „besser" als eine andere.
//
// DIE QUOTE STEHT NEBEN DER FORM, NICHT IN IHR: Seit die
// Gesellschaftertabelle mit Probe gelesen wird (Summe der Prozente = 100 ±
// 0,5 UND Summe der Beträge = Stammkapital), ist der Anteil der Stadt ein
// belegter Wert. Er erscheint als Zahl an der Gesellschaft und — wo die Stadt
// unter 50 % hält — als offener Ring um das Formzeichen. Kein vierter
// Formtyp: Eine GmbH bleibt eine GmbH, auch wenn der Stadt nur ein Drittel
// davon gehört.
//
// Wo der Bericht keine Quote nennt (TGO Besitz führt statt Anteilseignern
// Entsendungsrechte), steht KEINE Zahl — nicht „0 %".
//
// TODO (Datenpfad): Die Beteiligungen UNTER einer Gesellschaft
// (Klinikum → KMO/KSO/…) stehen im Bericht nur als Grafik in Abschnitt 2.1;
// `council/beteiligungsbericht.py` liest sie bewusst nicht aus. Sie stehen
// im Steckbrief als Abschnitt „Woran sie selbst beteiligt ist" im Wortlaut.

import { cn } from "@/lib/utils";
import { deZahl } from "@/components/grafik/format";
import {
  Gesellschaft, RECHTSFORM_TITEL, Rechtsform, istMinderheit, rechtsform,
} from "@/lib/haushalt-beteiligungen";

/** Quote so anschreiben, wie der Bericht sie druckt: „100 %", aber
 *  „16,67 %" — die Nachkommastellen fallen nur weg, wo sie null sind. */
function deProzent(v: number): string {
  return `${deZahl(v, Number.isInteger(v) ? 0 : 2)} %`;
}

/** Das Formen-Zeichen — auch die Karten-Liste und die Filter-Chips nutzen es,
 *  damit „Raute = AöR" überall dieselbe Aussage ist. */
export function FormZeichen({ form, ton: tonProp, minderheit = false, className }: {
  form: Rechtsform;
  /** Eigene Farbe (z. B. `currentColor` auf einem gefüllten Chip) —
   *  Vorgabe ist der Rampenton. */
  ton?: string;
  /** Hält die Stadt weniger als die Hälfte? Dann steht ein offener Ring um
   *  das Zeichen — gestrichelt, weil „nicht ganz herum" hier die Aussage
   *  ist. Das ist ein zweites Zeichen neben der Form, keine Bewertung: Ein
   *  Minderheitsanteil ist nicht schlechter als ein voller, er bedeutet nur
   *  andere Einflussmöglichkeiten. */
  minderheit?: boolean;
  className?: string;
}) {
  const ton = tonProp ?? "var(--hh-ein-0)";
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true"
      className={cn("h-3.5 w-3.5 flex-none", className)}>
      {minderheit && (
        <circle cx="7" cy="7" r="6.4" fill="none" strokeWidth="1"
          strokeDasharray="2.2 1.8" style={{ stroke: ton, opacity: 0.75 }} />
      )}
      {form === "eigenbetrieb" && (
        <rect x="2.2" y="2.2" width="9.6" height="9.6" rx="1.5" style={{ fill: ton }} />
      )}
      {form === "aoer" && (
        <path d="M7 1.6 L12.4 7 L7 12.4 L1.6 7 Z" fill="none" strokeWidth="2"
          strokeLinejoin="round" style={{ stroke: ton }} />
      )}
      {form === "gesellschaft" && (
        <circle cx="7" cy="7" r="4.8" fill="none" strokeWidth="2" style={{ stroke: ton }} />
      )}
    </svg>
  );
}

/** Reihenfolge der Gruppen = Reihenfolge des Berichts. */
const GRUPPEN: Rechtsform[] = ["eigenbetrieb", "aoer", "gesellschaft"];

export function Konzernkarte({ gesellschaften, aufGesellschaft, anteil, className }: {
  gesellschaften: Gesellschaft[];
  aufGesellschaft: (key: string) => void;
  /** Anteil der Stadt je Gesellschaft in Prozent, `null` wo der Bericht
   *  keinen nennt. Optional, damit die Karte auch ohne Eigentümerdaten
   *  rendert (alte API, Gesellschaft ohne bestandene Probe). */
  anteil?: (gesellschaft: string) => number | null;
  className?: string;
}) {
  const je = new Map<Rechtsform, Gesellschaft[]>();
  for (const g of gesellschaften) {
    const form = rechtsform(g);
    if (!form) continue; // unbekannte Gruppe: kein Chip statt einer geratenen Form
    const liste = je.get(form) ?? [];
    liste.push(g);
    je.set(form, liste);
  }
  if (!je.size) return null;

  return (
    <div className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Konzernkarte · wer gehört zu wem
      </p>

      {/* Der Stamm: die Stadt. Von ihr hängen alle Gruppen ab — eine Ebene,
          kein Baum-Gestrüpp. */}
      <div className="mt-3 flex flex-col">
        <div className="self-start rounded-xl border-2 border-foreground/70 bg-card px-4 py-2">
          <span className="font-display text-[15px] font-bold tracking-tight">Stadt Oldenburg</span>
        </div>

        <div className="ml-5 flex flex-col gap-3 border-l-2 border-border pl-4 pt-3">
          {GRUPPEN.map((form) => {
            const liste = je.get(form);
            if (!liste?.length) return null;
            return (
              <div key={form}>
                <p className="flex items-center gap-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                  <FormZeichen form={form} className="h-3 w-3" />
                  {RECHTSFORM_TITEL[form]} · {liste.length}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {liste.map((g) => {
                    const quote = anteil?.(g.gesellschaft) ?? null;
                    return (
                      <button key={g.gesellschaft} type="button"
                        onClick={() => aufGesellschaft(g.gesellschaft)}
                        className="inline-flex min-h-[36px] max-w-full items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-left text-[12px] leading-snug transition-colors hover:border-primary/40 mobil:w-full">
                        <FormZeichen form={form} minderheit={istMinderheit(quote)} />
                        <span className="min-w-0">{g.name}</span>
                        {quote !== null && (
                          <span className="flex-none font-mono text-[10.5px] tabular-nums text-muted-foreground">
                            {deProzent(quote)}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="mt-3 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
        Die Gruppen sind die des Beteiligungsberichts. Wer hier eine eigene Form hat,
        taucht auf der Schulden-Seite als eigener Rechtsträger auf. Die Prozentzahl ist
        der Anteil der Stadt aus der Gesellschaftertabelle des Berichts; ein offener Ring
        um das Zeichen heißt, dass die Stadt weniger als die Hälfte hält. Wo keine Zahl
        steht, nennt der Bericht für diese Einheit keine Anteilseigner.
      </p>
    </div>
  );
}
