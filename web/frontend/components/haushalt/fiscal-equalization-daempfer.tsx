"use client";

// Der Finanzausgleichs-Dämpfer — und warum hier keine Zahl steht.
//
// Die Sache, die der Block erklärt: Nimmt Oldenburg mehr eigene Steuern ein,
// rechnet das Land das in den Schlüsselzuweisungen gegen. Das ist der Grund,
// warum selbst die Einnahmen mit dem größten Spielraum weniger Spielraum
// haben, als sie versprechen.
//
// GEGENCHECK (16.08.2026) — der Entwurf H2-07 bezifferte den Dämpfer mit
// „von jedem zusätzlichen Euro blieben rund 34 Cent". Diese Zahl ist aus
// einem einzigen Jahrespaar gegriffen und hält keiner Prüfung stand:
//
//  1. **Sie ist nicht stabil.** Über alle 33 Jahrespaare des Datensatzes
//     streut derselbe Quotient zwischen −868 und +1818 Cent. Die 34 Cent sind
//     das Paar mit der zweitgrößten Steuerkraft-Zunahme, sonst nichts.
//  2. **Sie ist nicht einmal in der Richtung verlässlich.** In 26 Paaren
//     stieg die Steuerkraft; die Zuweisung sank dabei nur in 11, in 15 stieg
//     sie mit. Der Jahresvergleich kann den Dämpfer gar nicht freilegen, weil
//     zugleich der Landestopf und die Steuerkraft aller anderen Kommunen
//     wandern — wir sehen die Summe zweier Bewegungen, nicht den Effekt.
//  3. **Sie misst das Falsche.** Der Quotient stammt aus wachsender
//     Bemessungsgrundlage. Die Debatte, in der er zitiert würde, dreht sich um
//     den Hebesatz — und die Steuerkraftmesszahl wird nach NFAG mit
//     Nivellierungshebesätzen gebildet, also mit fiktiven statt den
//     tatsächlichen Sätzen.
//
//     NICHT „landeseinheitlich": § 11 NFAG staffelt sie nach Größenklasse —
//     Gemeinden unter 100.000 Einwohner*innen rechnen mit anderen Sätzen als
//     die darüber. Das stand hier bis zum 17.08. falsch und widersprach dem
//     eigenen Hinweis auf `/haushalt/vergleich`, der die Schwelle benennt.
//
// Deshalb: Der Mechanismus wird benannt, seine Wirkung nicht beziffert. Diese
// Komponente rechnet bewusst KEINEN Faktor aus — sie zeigt die beiden Reihen
// nebeneinander und zählt aus, wie oft sie überhaupt gegenläufig sind.
//
// JAHRESZUORDNUNG: Datensatz 1106 zählt nach *Ausgleichsjahr*; die Beträge
// decken sich mit dem Landesamt für Statistik, die Jahresangabe steht dort
// aber um ein Jahr versetzt (Klärung läuft). Nichts hier hängt an der exakten
// Zuordnung: Verglichen werden ausschließlich die beiden Spalten DESSELBEN
// Datensatzes, und ein einheitlicher Versatz verschiebt beide gleich. Deshalb
// steht an der Achse „Ausgleichsjahr" und nicht „Haushaltsjahr", und keine
// Zahl von hier wird mit einem Jahr aus `council_steuern` gepaart.

import { useId } from "react";
import { useBreite } from "@/lib/use-breite";
import { deMio } from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/source";
import {
  AbleseBeschreibung, AbleseFlaeche, AbleseStelle, Ableseleiste, useAblesen,
} from "@/components/grafik/ablesen";

type Kraft = {
  year: number;
  tax_index: number | null;
  allocations: number | null;
};

const H = 190, Y0 = 150, YTOP = 20;

/** Kontur-Halo wie in `ist-kurve.tsx`: Sonst schneiden die Linien durch die
 *  Ziffern der Direktbeschriftung. */
const halo = { paintOrder: "stroke", strokeWidth: 3, strokeLinejoin: "round" } as const;

export function FinanzausgleichDaempfer({ tax_capacity }: { tax_capacity: Kraft[] }) {
  // 260 statt der üblichen 280: Dieses Diagramm trägt keine Jahreszahlen an
  // der Achse und bleibt deshalb zwanzig Pixel schmaler noch lesbar.
  const { box, breite } = useBreite(640, 260);

  const series = tax_capacity
    .filter((k): k is Kraft & { tax_index: number; allocations: number } =>
      k.tax_index != null && k.allocations != null)
    .sort((a, b) => a.year - b.year);

  // Vor dem Ausstieg: Ein Hook hinter einem `return` ist kein Hook mehr.
  const ablesen = useAblesen(series.length, Math.max(series.length - 1, 0));
  const beschreibungId = useId();
  if (series.length < 3) return null;

  // Wie oft ist die Zuweisung überhaupt gegenläufig? Das ist die einzige
  // Kennzahl, die dieser Block nennt — eine Auszählung, kein Umrechnungskurs.
  // Sie ist gegen einen einheitlichen Jahresversatz immun, weil sie nur
  // aufeinanderfolgende Zeilen derselben Tabelle vergleicht.
  const steigend = series.slice(1)
    .map((k, i) => ({ dKraft: k.tax_index - series[i].tax_index, dZuw: k.allocations - series[i].allocations }))
    .filter((p) => p.dKraft > 0);
  const gegenlaeufig = steigend.filter((p) => p.dZuw < 0).length;

  const schmal = breite < 520;
  const fs = schmal ? { achse: 12, year: 12, value: 12.5 } : { achse: 10.5, year: 10.5, value: 12 };
  const W = breite, X0 = schmal ? 34 : 40, X1 = W - (schmal ? 8 : 12);

  // EINE gemeinsame Achse in Mio. € für beide Reihen. Zwei Achsen mit eigener
  // Skala ließen sich hübscher zeichnen, würden aber genau die Aussage
  // erzeugen, die hier widerlegt werden soll: Man kann zwei beliebig
  // gestreckte Kurven immer zur Deckung bringen.
  const hoechst = Math.max(...series.map((k) => Math.max(k.tax_index, k.allocations))) / 1e6;
  const hi = Math.ceil(hoechst / 100) * 100;
  const x = (i: number) => X0 + (i / (series.length - 1)) * (X1 - X0);
  const y = (v: number) => Y0 - (v / hi) * (Y0 - YTOP);
  const pfad = (field: "tax_index" | "allocations") =>
    series.map((k, i) => `${i ? "L" : "M"}${x(i)} ${y(k[field] / 1e6)}`).join(" ");

  const gitter = [0.5, 1].map((f) => Math.round(hi * f));
  const schritt = Math.ceil(series.length / (schmal ? 4 : 7));
  const letzte = series[series.length - 1];

  // Angeschrieben sind dauerhaft die beiden Endwerte — mehr passt zwischen 33
  // Jahrgänge nicht, ohne dass sich die Ziffern überlagern. Jedes einzelne
  // Ausgleichsjahr trägt die Leiste unter dem Bild, die immer eines zeigt und
  // beim Überfahren, Antippen oder mit den Pfeiltasten wechselt. Eine Tabelle
  // hatte dieser Block nie; die vollständige Reihe steht als sr-only-Absatz
  // daneben und wird von der Grafik referenziert.
  const stellen: AbleseStelle[] = series.map((k) => ({
    titel: String(k.year),
    werte: [
      { label: "Steuerkraft", value: deMio(k.tax_index / 1e6), farbe: "var(--hh-ein-0)" },
      { label: "Zuweisungen", value: deMio(k.allocations / 1e6), farbe: "var(--hh-aus-2)" },
    ],
    vorlesen: `Ausgleichsjahr ${k.year}: Steuerkraftmesszahl ${deMio(k.tax_index / 1e6)} Millionen Euro, `
      + `Schlüsselzuweisungen ${deMio(k.allocations / 1e6)} Millionen Euro.`,
  }));

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was das Land gegenrechnet
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          Ausgleichsjahre {series[0].year}–{letzte.year}
        </span>
      </div>

      <p className="mt-2 max-w-[74ch] text-[13px] leading-relaxed text-foreground/90">
        <strong>Auch bei den Landeszuweisungen wirkt sich die eigene Steuerkraft aus.</strong>{" "}
        Das Land berücksichtigt in seiner Formel, wie viele Steuereinnahmen Oldenburg
        rechnerisch erzielen kann. Mit höherer eigener Steuerkraft sinkt grundsätzlich der
        errechnete Finanzbedarf.
      </p>

      <div ref={box} className="mt-3">
        <AbleseBeschreibung id={beschreibungId}>
          {`Zwei Reihen über die Ausgleichsjahre ${series[0].year} bis ${letzte.year}, in Millionen Euro. `
            + `Steuerkraftmesszahl: ${series.map((k) => `${k.year} ${deMio(k.tax_index / 1e6)}`).join(", ")}. `
            + `Schlüsselzuweisungen: ${series.map((k) => `${k.year} ${deMio(k.allocations / 1e6)}`).join(", ")}.`}
        </AbleseBeschreibung>
        <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
          aria-describedby={beschreibungId}
          aria-label={`Steuerkraft und Zuweisungen, Ausgleichsjahre ${series[0].year} bis ${letzte.year}`}>
          {gitter.map((v) => (
            <g key={v}>
              <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
              <text x={X0 - 5} y={y(v) + 4} textAnchor="end" fontSize={fs.achse}
                className="fill-muted-foreground font-mono">{v}</text>
            </g>
          ))}
          <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

          <path d={pfad("tax_index")} fill="none" strokeWidth={2.2} strokeLinejoin="round"
            strokeLinecap="round" style={{ stroke: "var(--hh-ein-0)" }} />
          <path d={pfad("allocations")} fill="none" strokeWidth={2.2} strokeLinejoin="round"
            strokeLinecap="round" style={{ stroke: "var(--hh-aus-2)" }} strokeDasharray="5 3" />

          <text x={x(series.length - 1)} y={y(letzte.tax_index / 1e6) - 8} textAnchor="end"
            fontSize={fs.value} fontWeight={700} className="stroke-card" {...halo}
            style={{ fill: "var(--hh-ein-0)" }}>{deMio(letzte.tax_index / 1e6)}</text>
          <text x={x(series.length - 1)} y={y(letzte.allocations / 1e6) - 8} textAnchor="end"
            fontSize={fs.value} fontWeight={700} className="stroke-card" {...halo}
            style={{ fill: "var(--hh-aus-2)" }}>{deMio(letzte.allocations / 1e6)}</text>

          {/* Die Randbeschriftungen ankern nach innen. Mittig zentriert stand
              die letzte Jahreszahl bei 375 px vier Pixel über der rechten
              SVG-Kante und wurde abgeschnitten (Befund 16.08.2026). */}
          {series.map((k, i) => {
            const letzterTick = i === series.length - 1;
            if (!(i % schritt === 0 || letzterTick)) return null;
            return (
              <text key={k.year} x={x(i)} y={172} fontSize={fs.year}
                textAnchor={letzterTick ? "end" : i === 0 ? "start" : "middle"}
                className={letzterTick
                  ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
                {k.year}
              </text>
            );
          })}

          {/* Zuletzt: die Ablese-Fläche liegt über beiden Kurven. Das
              Fingerziel reicht bis unter die Jahreszeile. */}
          <AbleseFlaeche
            stellen={stellen} steuerung={ablesen} gruppe="Ausgleichsjahre der Reihe"
            x={(i) => x(i)} xVon={X0} xBis={X1}
            yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={176 - YTOP}
            marken={(i) => [
              { y: y(series[i].tax_index / 1e6), farbe: "var(--hh-ein-0)" },
              { y: y(series[i].allocations / 1e6), farbe: "var(--hh-aus-2)" },
            ]}
          />
        </svg>
        <Ableseleiste className="mt-2" stelle={stellen[ablesen.aktiv]} steuerung={ablesen}
          note="Mio. € · Ausgleichsjahr überfahren, antippen oder mit den Pfeiltasten wechseln." />
      </div>

      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{ background: "var(--hh-ein-0)" }} />
          Steuerkraftmesszahl
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{
            backgroundImage: "repeating-linear-gradient(90deg, var(--hh-aus-2) 0 5px, transparent 5px 8px)",
          }} />
          Schlüsselzuweisungen
        </span>
        <span>Mio.&nbsp;€ je Ausgleichsjahr<Beleg q="tax_capacity" /></span>
      </div>

      {/* Der Kern: Warum hier keine Zahl steht. Die Auszählung ist die
          Begründung, nicht der Ersatzfaktor. */}
      {/* Zwei Gedanken, zwei Spalten: „was die Zahlen nicht sagen" und „warum
          wir keinen Kurs nennen" sind getrennt, standen aber untereinander —
          und ließen auf breiten Schirmen die halbe Karte leer. Die Zeilenlänge
          bleibt bei 74 Zeichen; breiter zu setzen wäre schlechter zu lesen,
          nicht besser (Designsprache §4). */}
      <div className="mt-3 grid gap-x-8 gap-y-2 border-t border-dashed border-border pt-3 lg:grid-cols-2">
        <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
          <strong>Wie stark dieser Ausgleich wirkt, lässt sich aus diesen Zahlen allein nicht ableiten.</strong>{" "}In{" "}
          {steigend.length} Ausgleichsjahren stieg Oldenburgs Steuerkraft gegenüber dem Vorjahr —
          die Zuweisung sank dabei nur {gegenlaeufig}-mal, in den übrigen{" "}
          {steigend.length - gegenlaeufig} stieg sie mit. Denn es bewegt sich beides zugleich:
          Oldenburg und der Landestopf, aus dem alle Kommunen bedient werden.
        </p>
        <p className="mt-2 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground lg:mt-0">
          Deshalb lässt sich kein fester Betrag nach dem Muster „Von jedem zusätzlichen Euro
          bleiben X Cent“ angeben. Die Berechnung hängt auch von der Entwicklung der anderen
          Kommunen und der verfügbaren Ausgleichsmasse ab. Außerdem arbeitet das Land mit
          einheitlichen fiktiven Hebesätzen. Eine Oldenburger Hebesatzänderung geht daher nicht
          eins zu eins in die Steuerkraftmesszahl ein.
        </p>
      </div>
    </div>
  );
}
