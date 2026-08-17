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
// TODO (Datenpfad): Beteiligungsquoten („VWG 74 %") und die Beteiligungen
// UNTER einer Gesellschaft (Klinikum → KMO/KSO/…) stehen im Bericht nur als
// Fließtext bzw. Grafik in Abschnitt 2.1 — `council/beteiligungsbericht.py`
// liest beides bewusst nicht strukturiert aus. Bis der Parser Quoten mit
// Probe liefert, zeigt die Karte Formen ohne Prozentzahl; die
// Unterbeteiligungen stehen im Steckbrief als Abschnitt „Woran sie selbst
// beteiligt ist" im Wortlaut.

import { cn } from "@/lib/utils";
import {
  Gesellschaft, RECHTSFORM_TITEL, Rechtsform, rechtsform,
} from "@/lib/haushalt-beteiligungen";

/** Das Formen-Zeichen — auch die Karten-Liste und die Filter-Chips nutzen es,
 *  damit „Raute = AöR" überall dieselbe Aussage ist. */
export function FormZeichen({ form, ton: tonProp, className }: {
  form: Rechtsform;
  /** Eigene Farbe (z. B. `currentColor` auf einem gefüllten Chip) —
   *  Vorgabe ist der Rampenton. */
  ton?: string;
  className?: string;
}) {
  const ton = tonProp ?? "var(--hh-ein-0)";
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true"
      className={cn("h-3.5 w-3.5 flex-none", className)}>
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

export function Konzernkarte({ gesellschaften, aufGesellschaft, className }: {
  gesellschaften: Gesellschaft[];
  aufGesellschaft: (key: string) => void;
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
                  {liste.map((g) => (
                    <button key={g.gesellschaft} type="button"
                      onClick={() => aufGesellschaft(g.gesellschaft)}
                      className="inline-flex min-h-[36px] max-w-full items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-left text-[12px] leading-snug transition-colors hover:border-primary/40 mobil:w-full">
                      <FormZeichen form={form} />
                      <span className="min-w-0">{g.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="mt-3 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
        Die Gruppen sind die des Beteiligungsberichts. Wer hier eine eigene Form hat,
        taucht auf der Schulden-Seite als eigener Rechtsträger auf — Beteiligungsquoten
        nennt der Bericht nur im Fließtext, deshalb stehen hier keine Prozentzahlen.
      </p>
    </div>
  );
}
