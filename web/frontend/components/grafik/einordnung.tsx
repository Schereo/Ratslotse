// <Einordnung> — der Satz unter der Zahl (GB-00).
//
// Der Pflicht-Baustein überall dort, wo eine Zahl allein missverstanden
// würde: „Ein Verkehrsbetrieb mit Verlust erfüllt seinen Auftrag." Die
// Grafiken, deren Vertrag `einordnung`, `nichtAussagen` oder `gemessen` als
// Pflicht-Prop führt (Hantel, Kassenzettel, Zeitstrahl, Beteiligungen,
// Pro-Kopf), rendern sie hierüber — einheitlich, damit derselbe Gedanke auf
// jeder Seite gleich aussieht und niemand ihn „kompakt" wegoptimiert.
//
// DREI FORMEN, EIN BAUSTEIN:
//  * `satz` — die Einordnung selbst. Berichtet, bewertet nicht (keine
//    Bewertungsfarben, DESIGNSPRACHE § 7); sie gehört zur Zahl und wird nie
//    abgeschnitten (H4-07: „der Einordnungssatz gehört zur Hantel").
//  * `gemessen` — die ehrliche Zählangabe („7 von 8 Jahren"): woraus die
//    Aussage gezählt ist. Der Zeitstrahl behauptet nichts, was nicht aus den
//    Jahrgängen gezählt ist (GB-11) — die Angabe steht deshalb sichtbar
//    daneben, Mono-Kicker wie alle Zähl-/Zeitraum-Angaben des Bereichs.
//  * `nichtAussagen` — der „Was diese Zahl nicht sagt"-Kasten. Pflicht am
//    Kassenzettel (GB-13): Die Pro-Kopf-Zahl ist die missbrauchbarste des
//    Bereichs und reist nie ohne ihn. Gestrichelter Rand wie alle
//    Reichweiten-Hinweise, NIE einklappbar (H4-A).
//
// Kein <details>, kein „mehr anzeigen": Was hier steht, ist der Teil der
// Wahrheit, der beim Einklappen zuerst verloren ginge.

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Einordnung({ satz, gemessen, nichtAussagen, className }: {
  /** Der Satz, der die Zahl einordnet — ganze Sätze, keine Stichworte. */
  satz?: ReactNode;
  /** Woraus gezählt wurde: „7 von 8 Jahren", „26 von 33 Jahrespaaren". */
  gemessen?: string;
  /** Die Grenzen der Zahl, je Punkt ein Satz. */
  nichtAussagen?: string[];
  className?: string;
}) {
  const hatKasten = !!nichtAussagen?.length;
  if (!satz && !gemessen && !hatKasten) return null;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {(satz || gemessen) && (
        <div className="border-l-2 border-border pl-2.5">
          {satz && (
            <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
              {satz}
            </p>
          )}
          {gemessen && (
            <p className={cn(
              "font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground",
              satz && "mt-1",
            )}>
              Gemessen: {gemessen}
            </p>
          )}
        </div>
      )}
      {hatKasten && (
        <div className="rounded-xl border border-dashed border-border p-3">
          <p className="text-[12px] font-semibold leading-snug">
            Was diese Zahl nicht sagt
          </p>
          <ul className="mt-1 max-w-[74ch] list-disc space-y-1 pl-4 text-[12px] leading-relaxed text-muted-foreground">
            {nichtAussagen!.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
