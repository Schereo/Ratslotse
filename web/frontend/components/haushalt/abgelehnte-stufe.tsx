"use client";

// „Die Stufe, die nicht kam" — das Bild zum abgelehnten Hebesatz-Vorschlag
// (Steuer-Steckbrief, H-11).
//
// WARUM EIN BALKEN AB NULL UND KEINE TREPPE IM KLEINEN. Die beiden Zahlen
// liegen nah beieinander (2026: der geltende Satz gegen den vorgeschlagenen).
// Zwei Stufen nebeneinander, deren Höhe die Aussage tragen soll, müsste man
// dafür an einer beschnittenen Achse zeichnen — dann sähe ein Unterschied von
// wenigen Punkten aus wie eine Verdopplung. Der Balken läuft deshalb von 0 bis
// zum geltenden Satz, und der Vorschlag hängt als schraffiertes Stück hinten
// dran: Er zeigt ehrlich, dass es um wenige Punkte ging — und genau das ist
// die Aussage.
//
// SCHRAFFUR HEISST „WÄRE GEWESEN". Dieselbe Auszeichnung wie der
// Rücklagen-Kasten im Gegenbalken (`.hh-schraffur`, app/globals.css): ein
// Stück, das die Stadt nicht hat. Kein Signal-Rot als Fläche — abgelehnt ist
// keine schlechte Nachricht, sondern eine Entscheidung.
//
// OHNE ZAHL LIEBER OHNE BALKEN. Der vorgeschlagene Satz steht in der
// Haushaltssatzung des Jahrgangs (§ 5). Führt der Bestand ihn nicht — oder
// liegt er nicht über dem geltenden Satz, dann war es kein Erhöhungs-
// vorschlag, den wir hier zeigen dürften —, zeichnet die Komponente das Stück
// gar nicht erst, sondern sagt in einer Zeile, dass die Höhe nicht vorliegt.
// Geraten wird sie nicht.

import type { ReactNode } from "react";
import { deMio } from "@/lib/haushalt";
import { deZahl } from "@/components/grafik/format";

export function AbgelehnteStufe({
  jahr, geltend, geltendSeit, vorgeschlagen, proPunkt, beleg, satzungBeleg,
}: {
  /** Das Haushaltsjahr, für das der Vorschlag galt. */
  jahr: number;
  /** Der Hebesatz, der gilt — in Prozentpunkten. */
  geltend: number;
  /** Seit wann er gilt (Änderungsjahr der Reihe). */
  geltendSeit: number;
  /** Der vorgeschlagene Satz aus der Haushaltssatzung, oder `null`. */
  vorgeschlagen: number | null;
  /** Was ein Hebesatzpunkt überschlagen bringt, in Euro — oder `null`. */
  proPunkt: number | null;
  beleg?: ReactNode;
  satzungBeleg?: ReactNode;
}) {
  const mehr = vorgeschlagen != null && vorgeschlagen > geltend
    ? vorgeschlagen - geltend : null;
  const skala = geltend + (mehr ?? 0);
  const anteilGeltend = (geltend / skala) * 100;
  // Ein Stück von zwei Punkten auf 539 ist 0,37 % der Breite — unsichtbar.
  // Der Balken bleibt maßstäblich, das Stück bekommt aber eine Mindestbreite,
  // damit man es überhaupt findet; die Zahl daneben sagt, wie groß es ist.
  const anteilMehr = mehr != null ? Math.max(100 - anteilGeltend, 2.5) : 0;

  return (
    // `flex-1` + `justify-center`: Die Karte steht in einer Grid-Zeile neben
    // dem Überschlag-Kasten und wird auf dessen Höhe gezogen. Ohne das säße
    // das Bild oben und darunter stünde die Leere, die es füllen soll.
    <div className="mt-3.5 flex flex-1 flex-col justify-center">
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex h-9 w-full items-stretch overflow-hidden rounded-md">
            <div
              className="flex items-center justify-end rounded-l-md bg-[color:var(--hh-ein-1)] px-2"
              style={{ width: `${mehr != null ? 100 - anteilMehr : 100}%` }}
            >
              <span className="font-display text-[13.5px] font-bold tabular-nums text-white">
                {deZahl(geltend)}&nbsp;%
              </span>
            </div>
            {mehr != null && (
              <div
                className="hh-schraffur rounded-r-md border border-l-0 border-dashed border-signal/70"
                style={{ width: `${anteilMehr}%` }}
              />
            )}
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            gilt seit {geltendSeit}{beleg}
          </p>
        </div>

        {mehr != null && (
          <div className="flex-none text-right">
            <p className="font-display text-[15px] font-bold leading-none tabular-nums text-signal">
              +{deZahl(mehr)}
              <span className="ml-0.5 text-[11px] font-semibold">Punkte</span>
            </p>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              auf {deZahl(vorgeschlagen as number)}&nbsp;% vorgeschlagen{satzungBeleg}
            </p>
          </div>
        )}
      </div>

      {/* Was das Stück wert gewesen wäre — als Überschlag benannt, weil es
          einer ist: ein Punkt, hochgerechnet aus dem letzten Ist-Aufkommen. */}
      {mehr != null && proPunkt != null && (
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-foreground/80">
          Das schraffierte Stück wäre überschlagen{" "}
          <strong className="font-semibold">
            {deMio((proPunkt * mehr) / 1e6)}&#8239;Mio.&nbsp;€
          </strong>{" "}
          im Jahr gewesen — gerechnet mit dem Aufkommen des letzten Ist-Jahres,
          bei unverändertem Messbetrag.
        </p>
      )}
      {mehr == null && (
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
          Um wie viele Punkte der Satz hätte steigen sollen, können wir für{" "}
          {jahr} nicht belegen — deshalb steht hier keine Höhe, nur der
          geltende Satz.
        </p>
      )}
    </div>
  );
}
