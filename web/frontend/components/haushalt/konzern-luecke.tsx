"use client";

// Die Lücke: Was der Haushalts-Bereich zeigt, gegen das, was die Stadt
// insgesamt bewegt — als geschachtelter Balken je Jahrgang.
//
// WARUM GESCHACHTELT UND NICHT GESTAPELT. Ein Stapel aus acht Trägern ergäbe
// nicht die Konzernsumme: Dazwischen steht die Konsolidierung, die 2024 rund
// 99 Mio. € wieder abzieht. Ein Stapel, dessen Teile nicht die Summe ergeben,
// ist eine Lüge mit Achse. Hier liegt deshalb EIN Balken je Jahr — die
// Konzernsumme —, und darin sitzt der Teil, den der Kernhaushalt abbildet.
// Der Rest ist dann per Definition „alles Übrige, schon verrechnet".
//
// KEINE BEWERTUNGSFARBEN, wie überall im Haushalts-Bereich (siehe
// components/grafik/hantel.tsx). Ein großer Konzernanteil ist weder gut
// noch schlecht — er heißt nur, dass die Stadt viel über eigene Betriebe
// erledigt statt über die Verwaltung. Die beiden Töne sind deshalb zwei
// Stufen derselben blauen Rampe, nicht Grün gegen Rot.
//
// FEHLENDE JAHRE BLEIBEN LEER. Bis 2016 führen die Berichte die
// Trägeraufstellung noch nicht; für diese Jahrgänge kennen wir die
// Konzernsumme, aber nicht ihren Kernanteil. Der Balken steht dann ganz da
// und trägt die Schraffur der Lücken-Konvention statt einer geschätzten
// Trennlinie.

import { deMio } from "@/lib/haushalt";
import { KonzernDaten, kernAnteil } from "@/lib/haushalt-konzern";

export type LueckeArt = "ertraege" | "aufwendungen";

export function KonzernLuecke({ daten, art }: { daten: KonzernDaten; art: LueckeArt }) {
  const zeilen = daten.konzern
    .map((k) => {
      const konzern = art === "ertraege" ? k.ertraege_summe : k.aufwendungen_summe;
      if (konzern == null) return null;
      const anteil = kernAnteil(daten, k.jahr, art);
      return { jahr: k.jahr, konzern, kern: anteil?.kern ?? null };
    })
    .filter((z): z is { jahr: number; konzern: number; kern: number | null } => z !== null);
  if (zeilen.length < 2) return null;

  const max = Math.max(...zeilen.map((z) => z.konzern));

  return (
    <div>
      <div className="flex flex-col gap-1.5">
        {zeilen.map((z) => {
          const breite = (z.konzern / max) * 100;
          const kernAnteilProzent = z.kern != null ? (z.kern / z.konzern) * 100 : null;
          return (
            <div key={z.jahr} className="flex items-center gap-2.5">
              <span className="w-9 flex-none font-mono text-[10.5px] tabular-nums text-muted-foreground">
                {z.jahr}
              </span>
              <div className="min-w-0 flex-1">
                <div className="h-5 w-full">
                  <div className="relative h-full rounded-[3px]"
                    style={{ width: `${breite}%`, background: "var(--hh-ein-4)" }}>
                    {kernAnteilProzent != null ? (
                      <div className="absolute inset-y-0 left-0 rounded-l-[3px]"
                        style={{
                          width: `${kernAnteilProzent}%`,
                          background: "var(--hh-ein-0)",
                        }} />
                    ) : (
                      <div className="hh-schraffur absolute inset-0 rounded-[3px] opacity-70" />
                    )}
                  </div>
                </div>
              </div>
              {/* Feste Breite und `whitespace-nowrap`: Ohne beides bricht
                  „632,2 von 1.129,8" ab 2020 auf zwei Zeilen um, und die
                  Zeilen der Reihe werden verschieden hoch — die Balken
                  stünden dann nicht mehr auf gleichem Raster.
                  Die längste Angabe ist „799,1 / 1.241,5": 15 Zeichen, in
                  Mono also gut 0,6 em je Zeichen. Auf 375 px trägt der
                  Schrägstrich das „von", und 10 px Schrift halten die Spalte
                  bei 102 px — mit 10,5 px und 92 px schnitt sie ab 2020
                  die letzte Ziffer ab. */}
              <span className="w-[102px] flex-none whitespace-nowrap text-right font-mono text-[10px] tabular-nums text-muted-foreground sm:w-[120px] sm:text-[10.5px]">
                {z.kern != null ? (
                  <>
                    <span className="font-semibold text-foreground">{deMio(z.kern / 1e6)}</span>
                    <span className="hidden sm:inline"> von </span>
                    <span className="sm:hidden"> / </span>
                    {deMio(z.konzern / 1e6)}
                  </>
                ) : (
                  <>{deMio(z.konzern / 1e6)}</>
                )}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11.5px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-[2px]" style={{ background: "var(--hh-ein-0)" }} />
          Kernverwaltung — das, was der Haushalt zeigt
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-[2px]" style={{ background: "var(--hh-ein-4)" }} />
          Betriebe und Beteiligungen, Verrechnung schon abgezogen
        </span>
        <span className="flex items-center gap-1.5">
          <span className="hh-schraffur h-2.5 w-4 rounded-[2px] border border-dashed border-border" />
          Aufteilung für dieses Jahr nicht ausgewiesen
        </span>
      </div>
      <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
        Alle Beträge in Mio.&nbsp;€, {art === "ertraege" ? "ordentliche Erträge" : "ordentliche Aufwendungen"}.
        Die Balkenlänge steht für die Konzernsumme des Jahres — der dunkle Teil ist
        die Kernverwaltung darin.
      </p>
    </div>
  );
}
