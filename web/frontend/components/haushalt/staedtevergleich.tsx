"use client";

// Der Städtevergleich als Rangliste — acht Balken, einer davon unserer.
//
// WARUM RANGLISTE UND NICHT DIE BALKENFORM AUS DEM ENTWURF.
// Der erste Entwurf stellte je Stadt zwei Balken übereinander (Oldenburg
// gegen die andere Stadt, Kennzahl für Kennzahl). Das trägt bei zwei Städten
// und bricht bei acht: Man liest Paare statt einer Ordnung und sieht gerade
// das nicht, worum es geht — wo Oldenburg im Feld steht. Eine sortierte Liste
// beantwortet „der wievielte sind wir?" ohne Zählen, und die Balkenlänge
// beantwortet „mit welchem Abstand?".
//
// DIE SKALA BEGINNT BEI NULL. Bei Pro-Kopf-Beträgen ist das keine
// Geschmacksfrage: Ein abgeschnittener Nullpunkt macht aus 1.974 gegen 1.651
// Euro optisch einen Faktor drei. Wer die Unterschiede größer zeigen will,
// als sie sind, hat den Zweck dieser Seite verfehlt.
//
// KEINE BEWERTUNGSFARBEN — die Regel des ganzen Bereichs
// (components/grafik/hantel.tsx), und hier besonders wichtig: Eine hohe
// Steuerkraft ist gut, ein hoher Hebesatz ist es nicht unbedingt, und ob eine
// hohe Gewerbesteuer Stärke oder Abhängigkeit bedeutet, ist genau die Frage,
// die diese Seite offenlässt. Grün und Rot würden sie beantworten, ohne sie
// gestellt zu haben. Oldenburg ist deshalb nicht „gut" eingefärbt, sondern
// nur HERVORGEHOBEN — damit man die eigene Stadt findet, nicht damit man sie
// bewertet.

import { Balken, euroJeEw } from "@/lib/haushalt-vergleich";
import { cn } from "@/lib/utils";

export function Staedtevergleich({
  zeilen, unit = "eur_je_ew", hinweisUnter100k = false,
}: {
  zeilen: Balken[];
  /** `eur_je_ew` schreibt „€", `percent` schreibt „%" — die Hebesätze sind
   *  keine Beträge, und ein Euro-Zeichen daran wäre schlicht falsch. */
  unit?: "eur_je_ew" | "percent";
  /** Die Fußnote zur 100.000-Einwohner-Schwelle im Finanzausgleich. Nur bei
   *  der Steuerkraft — die Steuereinnahmekraft kennt die Schwelle nicht. */
  hinweisUnter100k?: boolean;
}) {
  if (!zeilen.length) return null;
  const groesster = Math.max(...zeilen.map((z) => z.wert));
  const betroffen = hinweisUnter100k && zeilen.some((z) => z.unter_100k);

  return (
    <div>
      <ol className="flex flex-col gap-1.5">
        {zeilen.map((z) => {
          const anteil = groesster > 0 ? (z.wert / groesster) * 100 : 0;
          return (
            <li key={z.schluessel} className="grid grid-cols-[7.5rem_1fr_auto] items-center gap-2 sm:grid-cols-[9rem_1fr_auto] sm:gap-3">
              <span className={cn(
                "truncate text-[12.5px] leading-tight",
                z.ist_oldenburg ? "font-bold text-foreground" : "text-muted-foreground",
              )}>
                {z.name}
                {/* Kreuz statt Sternchen: Die Fußnote unten endet auf
                    „Einwohner*innen" — zwei Sternchen mit verschiedener
                    Bedeutung nebeneinander liest niemand auseinander. */}
                {hinweisUnter100k && z.unter_100k && (
                  <span className="align-super text-[9px] text-muted-foreground"> †</span>
                )}
              </span>
              {/* Die Schiene macht sichtbar, dass die Skala bei null anfängt
                  und wo das Maximum liegt — ohne sie schwebten die Balken. */}
              <span className="h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: "var(--hh-ein-6)" }}>
                <span className="block h-full rounded-full"
                  style={{
                    width: `${Math.max(anteil, 1.5)}%`,
                    background: z.ist_oldenburg ? "var(--hh-ein-0)" : "var(--hh-ein-3)",
                  }} />
              </span>
              <span className={cn(
                "text-right font-mono text-[12px] tabular-nums",
                z.ist_oldenburg ? "font-bold text-foreground" : "text-muted-foreground",
              )}>
                {unit === "percent"
                  ? `${Math.round(z.wert)} %`
                  : `${euroJeEw(z.wert)} €`}
              </span>
            </li>
          );
        })}
      </ol>
      {betroffen && (
        <p className="mt-2.5 max-w-[86ch] text-[11px] leading-relaxed text-muted-foreground">
          <span className="align-super text-[9px]">†</span> Unter 100.000 Einwohner*innen
          rechnet das Land die Steuerkraft mit anderen fiktiven Hebesätzen. Diese
          Städte stehen deshalb nicht auf derselben Rechenvorschrift wie die übrigen.
        </p>
      )}
    </div>
  );
}

/** Eine Zeitreihe als Ministrecke — für den einen Fall, in dem die
 *  Veränderung die Aussage ist (Wolfsburgs Absturz gegen Oldenburgs Anstieg).
 *
 *  Bewusst kein Diagramm: Drei Punkte tragen keine Achsen. Die Zahlen
 *  nebeneinander mit dem Prozentsatz dahinter sagen dasselbe auf einer Zeile. */
export function Zeitreihe({
  titel, punkte, change: delta,
}: {
  titel: string;
  punkte: { year: number; wert: number }[];
  change: number | null;
}) {
  if (!punkte.length) return null;
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className="text-[12.5px] font-semibold">{titel}</span>
      {/* Selbst umbruchfähig, nicht nur die Zeile darüber: Auf 375 px passen
          drei Wertepaare nicht nebeneinander, und als EIN Flex-Element ließe
          sich die Kette nicht unter ihre Inhaltsbreite drücken — sie stand
          14 px über den Kartenrand hinaus. */}
      <span className="inline-flex flex-wrap items-baseline gap-x-0.5 font-mono text-[12px] tabular-nums text-muted-foreground">
        {punkte.map((p, i) => (
          <span key={p.year} className="whitespace-nowrap">
            {i > 0 && <span className="px-1 text-muted-foreground/60">→</span>}
            {euroJeEw(p.wert)}&nbsp;€
            <span className="ml-0.5 text-[10px]">({p.year})</span>
          </span>
        ))}
      </span>
      {delta != null && (
        // Signal-Orange steht hier für „das ist die Differenz", nicht für
        // „das ist schlimm" — dieselbe Lesart wie in der Hantel.
        <span className="font-mono text-[12px] font-semibold tabular-nums text-signal">
          {delta > 0 ? "+" : ""}{delta}&nbsp;%
        </span>
      )}
    </div>
  );
}
