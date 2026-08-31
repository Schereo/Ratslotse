"use client";

// <Hantel> — „geplant und tatsächlich" (GB-05, Design H-16; verallgemeinert
// aus der früheren Haushalts-Fassung `components/haushalt/hantel.tsx`).
//
// Zwei Punkte auf einer gemeinsamen Achse, dazwischen eine Linie: Die Linie
// IST die Abweichung — Länge und Richtung liest man, ohne die Zahl zu suchen.
//
// WARUM DIE ACHSE DIE ABWEICHUNG ZEIGT UND NICHT DEN BETRAG.
// Die erste Fassung setzte beide Punkte auf eine Skala von 0 bis zum größten
// Wert. Bei echten Haushaltszahlen fallen sie damit aufeinander: Ein Bereich
// mit 6,2 geplant und 6,3 tatsächlich hat auf einer Skala bis 251 Mio. eine
// Differenz von 0,04 % der Breite — unsichtbar. Genau die Differenz ist aber
// die Aussage. Deshalb liegt der Nullpunkt bei „wie geplant", und die Strecke
// misst, wie weit es davon abwich. Die Beträge stehen als Zahl daneben; sie
// brauchen keine Pixel, um lesbar zu sein.
//
// UND WARUM IN PROZENT, NICHT IN EURO (Voreinstellung).
// Auch die Abweichung selbst spreizt in Euro zu weit: Bei den Ausgaben 2024
// reicht sie von −0,7 bis +20,5 Mio., fünf der zwölf Zeilen wären kürzer als
// zwei Prozent der Breite. Gemessen am jeweiligen Plan liegt dieselbe Spanne
// bei −10 bis +14 %, die mittlere Strecke wird fünfmal so lang, und die
// Reihenfolge ändert sich — vorn steht dann nicht der größte Bereich, sondern
// der, dessen Plan am weitesten danebenlag. Beides sind richtige Antworten auf
// verschiedene Fragen, deshalb der Umschalter.
//
// KEINE LOG-SKALA. Sie würde die kleinen Zeilen ebenfalls sichtbar machen,
// aber die Grundannahme brechen, dass die doppelte Länge den doppelten Wert
// meint — und bei Vorzeichenwechsel und Werten nahe null bräuchte es einen
// willkürlich gesetzten linearen Kern. Für ein Publikum, das keinen Haushalt
// gewohnt ist, ist das eine Falle.
//
// KEINE BEWERTUNGSFARBEN. Mehrausgaben sind nicht automatisch schlecht
// (Tarifabschluss, mehr Kita-Plätze), Minderausgaben nicht automatisch gut
// (nicht gebaut, Stellen unbesetzt). Deshalb steht Signal-Orange hier nur für
// „hier ist die Differenz", nicht für „das ist schlimm" — und Grün kommt gar
// nicht vor.
//
// WAS GEGENÜBER DER HAUSHALTS-FASSUNG DAZUKAM (GB-05):
//  * `einordnung` ist Pflicht-FELD jeder Zeile — eine Hantel ohne Erklärsatz
//    kompiliert nicht. `null` heißt ausdrücklich „die Quelle erläutert diese
//    Zeile nicht" und muss hingeschrieben werden; vergessen geht nicht.
//    Gerendert wird der Satz über <Einordnung> (GB-00), nie abgeschnitten.
//  * `sortierung`: |Abweichung| absteigend ist die Voreinstellung (H4-07),
//    `alpha` sortiert nach Label — für Jahres-Zeilen die Chronologie.
//  * `schwelle`: alles hinter Rang N steht hinter „alle N zeigen" — Zeilen
//    verschwinden nie ersatzlos (H4-A).
//  * Die Achse trägt ihre Einheit selbst („Mio. €" an den Skalenenden) —
//    Review-Befund H4-07.
//  * Mobil (H4-A, unter 520 px Containerbreite): Name über der Achse, Achse
//    volle Breite, Plan/Ist-Werte unter den Punkten — nie zweispaltig.

import { useState, type ReactNode } from "react";
import { deMio } from "@/components/grafik/format";
import { Einordnung } from "@/components/grafik/einordnung";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type HantelZeile = {
  label: string;
  plan: number | null;
  ist: number | null;
  /** Der Satz, der die Abweichung dieser Zeile einordnet (GB-05, Pflicht):
   *  „Tarifabschluss — Mehrausgabe ist keine Wertung." `null` sagt bewusst,
   *  dass die Quelle diese Zeile nicht erläutert — das Feld wegzulassen ist
   *  kein gültiger Zustand. */
  einordnung: ReactNode | null;
};

export type HantelMassstab = "prozent" | "amount";
export type HantelSortierung = "deviation" | "alpha";

/** Der Satz, der die Nicht-Wertung ausschreibt, wenn die Zeilen AUSGABEN sind.
 *
 *  Voreinstellung, weil die Hantel dafür gebaut wurde (Plan-Ist, Bereichs-
 *  Steckbrief). Auf einer Einnahmen-Seite ist er falsch — dort ist nichts
 *  „ausgegeben" —, deshalb ist er austauschbar und nicht fest verdrahtet. Bis
 *  18.08.2026 war er es, und auf dem Steuer-Steckbrief stand dann unter drei
 *  Steuerzeilen etwas von Kita-Plätzen und unbesetzten Stellen. */
const AUSGABEN_KEINE_WERTUNG =
  "Die Farbe bewertet nicht: Mehr ausgegeben kann ein Tarifabschluss sein oder "
  + "mehr Kita-Plätze; weniger ausgegeben heißt oft, dass etwas nicht gebaut "
  + "oder eine Stelle nicht besetzt wurde.";

export function Hantel({
  zeilen, einheit = "Mio. €", massstab = "prozent",
  sortierung = "deviation", schwelle, beleg,
  wovon = "der Bereich", keineWertung = AUSGABEN_KEINE_WERTUNG,
}: {
  zeilen: HantelZeile[];
  /** Einheit der Beträge — steht an den Skalenenden und in der Legende. */
  einheit?: string;
  /** Woran die Streckenlänge hängt — siehe Kommentar oben. */
  massstab?: HantelMassstab;
  /** |Abweichung| absteigend (Default, H4-07) oder nach Label. */
  sortierung?: HantelSortierung;
  /** Ab diesem Rang stehen Zeilen hinter „alle N zeigen" — nie ersatzlos. */
  schwelle?: number;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: ReactNode;
  /** Was eine Zeile IST, in der Legende: „der Bereich", „diese Steuer".
   *
   *  Ein Nominativ mit Artikel — er wird in einen Satz eingesetzt, der selbst
   *  kein Genus kennt. („von seinem Plan" stand hier bis 18.08.2026 und
   *  ergab „die Steuer von seinem Plan".) */
  wovon?: string;
  /** Der ausgeschriebene Verzicht auf eine Wertung. Er bleibt Pflicht — nur
   *  sein Wortlaut hängt daran, worüber die Hantel spricht. */
  keineWertung?: ReactNode;
}) {
  const [alle, setAlle] = useState(false);
  const { box, breite } = useBreite();
  const schmal = breite < 520;

  const gueltig = zeilen.filter((z) => z.plan != null && z.ist != null);
  // Zeilen ohne beide Werte fallen nicht still weg — sie stehen unter der
  // Liste als Satz (Lücken-Regel des Baukastens).
  const ohneWerte = zeilen.filter((z) => z.plan == null || z.ist == null);
  if (!gueltig.length) return null;

  const diff = (z: HantelZeile) => Math.round(((z.ist as number) - (z.plan as number)) * 10) / 10;
  const anteil = (z: HantelZeile) =>
    z.plan ? (((z.ist as number) - (z.plan as number)) / Math.abs(z.plan as number)) * 100 : null;
  // Was die Strecke misst: den Betrag oder den Anteil am Plan. In Prozent
  // spreizen sich die Zeilen deutlich besser — bei den Ausgaben 2024 ist die
  // mittlere Strecke fünfmal so lang, und statt fünf sind nur zwei von zwölf
  // Zeilen kürzer als zwei Prozent der Breite.
  const skala = (z: HantelZeile) => (massstab === "prozent" ? anteil(z) ?? 0 : diff(z));

  const sortiert = [...gueltig].sort((a, b) =>
    sortierung === "alpha"
      ? a.label.localeCompare(b.label, "de")
      : Math.abs(skala(b)) - Math.abs(skala(a)));
  const gezeigt = schwelle != null && !alle ? sortiert.slice(0, schwelle) : sortiert;
  const versteckt = sortiert.length - gezeigt.length;

  // Gemeinsame Skala über ALLE Zeilen (auch die hinter der Schwelle) — sonst
  // spränge der Maßstab beim Aufklappen, und die Längen wären nicht
  // vergleichbar. Die Null ist immer dabei, auch wenn alle Abweichungen in
  // dieselbe Richtung gehen: Sonst verschöbe sich der Bezugspunkt.
  const werte = sortiert.map(skala);
  const min = Math.min(0, ...werte);
  const max = Math.max(0, ...werte);
  const spanne = max - min || 1;
  const pos = (v: number) => ((v - min) / spanne) * 100;
  const nullPos = pos(0);
  // Die Achse trägt ihre Einheit selbst — „−6,2 Mio. €" statt einer nackten
  // Zahl, deren Einheit man in der Legende suchen muss (Review H4-07).
  const skalenEnde = (v: number) =>
    massstab === "prozent"
      ? `${v > 0 ? "+" : ""}${Math.round(v)} %`
      : `${v > 0 ? "+" : ""}${deMio(v)} ${einheit}`;

  const gitter = "grid-cols-[minmax(96px,150px)_1fr_auto]";

  /** Die Achse einer Zeile — Strecke, Null-Marke, beide Punkte. */
  const achse = (z: HantelZeile) => {
    const s = skala(z);
    return (
      <div aria-hidden="true" className="relative h-5">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border/60" />
        <div className="absolute inset-y-0 w-px bg-border" style={{ left: `${nullPos}%` }} />
        {/* Die Abweichung als Strecke, ab der Null — immer Signal-Orange,
            die Punkte nie farbcodiert (GB-05). */}
        <div
          className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-signal/70"
          style={{
            left: `${Math.min(nullPos, pos(s))}%`,
            width: `${Math.max(Math.abs(pos(s) - nullPos), 0.5)}%`,
          }}
        />
        {/* Geplant: offener Punkt auf der Null. Tatsächlich: gefüllter
            Punkt am Ende. Beide ohne `title`: Ein Browser-Tooltip
            wiederholte nur, was daneben ohnehin als Text steht — und zwar
            ausschließlich für die Maus. Auf dem Telefon und für die
            Tastatur gab es ihn nie, für die Vorlesehilfe war er eine
            zweite Stimme über derselben Zahl. Die Punkte sind Bild zur
            Zeile, also `aria-hidden`. */}
        <span
          aria-hidden="true"
          className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
          style={{ left: `${nullPos}%`, borderColor: "var(--hh-ein-0)" }}
        />
        <span
          aria-hidden="true"
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: `${pos(s)}%`, background: "var(--hh-aus-0)" }}
        />
      </div>
    );
  };

  /* Die drei Zahlen stehen dauerhaft da — hier braucht es keine
     Ablese-Leiste, die Zeile IST die Beschriftung. Die sr-only-Wörter sagen
     nur, was der Pfeil sichtbar sagt: „6,2 → 6,3 +0,1" ist vorgelesen ohne
     sie nicht zuzuordnen. */
  const zahlen = (z: HantelZeile, mitQuote: boolean) => {
    const d = diff(z);
    const quote = anteil(z);
    return (
      <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
        <span className="sr-only">geplant </span>
        <span className="text-muted-foreground">{deMio(z.plan as number)}</span>
        <span aria-hidden="true" className="mx-1 text-muted-foreground">→</span>
        <span className="sr-only">, tatsächlich </span>
        <span className="font-semibold">{deMio(z.ist as number)}</span>
        <span className="sr-only">, Abweichung </span>
        <span className={cn("ml-1.5", d !== 0 && "text-signal")}>
          {d > 0 ? "+" : ""}{deMio(d)}
        </span>
        {mitQuote && quote != null && (
          <span className="ml-1 text-[11px] text-muted-foreground">
            ({quote > 0 ? "+" : "−"}{Math.abs(quote).toLocaleString("de-DE", {
              minimumFractionDigits: 1, maximumFractionDigits: 1 })}&nbsp;%)
          </span>
        )}
      </span>
    );
  };

  return (
    <div ref={box} className="flex flex-col gap-2.5">
      {gezeigt.map((z) => (
        <div key={z.label} className="flex flex-col gap-1">
          {schmal ? (
            // H4-A: Name über der Achse, Achse volle Breite, Werte unter den
            // Punkten — nie zweispaltig.
            <>
              <span className="text-[12.5px] font-medium">{z.label}</span>
              {achse(z)}
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[11px] text-muted-foreground">
                  ○ Plan <span className="tabular-nums">{deMio(z.plan as number)}</span>
                </span>
                {(() => { const d = diff(z); return (
                  <span className={cn("text-[11.5px] font-semibold tabular-nums",
                    d !== 0 && "text-signal")}>
                    {d > 0 ? "+" : ""}{deMio(d)}
                  </span>
                ); })()}
                <span className="text-[11px] text-muted-foreground">
                  ● Ist <span className="font-semibold tabular-nums text-foreground">
                    {deMio(z.ist as number)}</span>
                </span>
              </div>
            </>
          ) : (
            <div className={cn("grid items-center gap-x-3", gitter)}>
              <span className="truncate text-[12.5px]">{z.label}</span>
              {achse(z)}
              {zahlen(z, true)}
            </div>
          )}
          {/* Der Erklärsatz gehört zur Hantel und wird nie abgeschnitten
              (H4-07) — deshalb <Einordnung>, kein <details>. */}
          {z.einordnung != null && (
            <Einordnung satz={z.einordnung} className={cn(!schmal && "sm:ml-[calc(96px+0.75rem)]")} />
          )}
        </div>
      ))}

      {versteckt > 0 && (
        <button
          type="button" aria-expanded={false} onClick={() => setAlle(true)}
          className="self-start text-[12.5px] font-semibold text-primary"
        >
          alle {sortiert.length} zeigen
        </button>
      )}

      {/* Skalenenden — ohne sie wüsste niemand, wofür die Länge steht. */}
      <div className={cn("grid gap-x-3", schmal ? "grid-cols-1" : gitter)}>
        {!schmal && <span />}
        <div className="relative h-4 text-[10px] tabular-nums text-muted-foreground">
          {min < 0 && <span className="absolute left-0 top-0 whitespace-nowrap">{skalenEnde(min)}</span>}
          <span className="absolute top-0 -translate-x-1/2 whitespace-nowrap" style={{ left: `${nullPos}%` }}>
            wie geplant
          </span>
          {max > 0 && <span className="absolute right-0 top-0 whitespace-nowrap">{skalenEnde(max)}</span>}
        </div>
        {!schmal && <span />}
      </div>

      {/* Zeilen ohne beide Werte: benannt statt still verschluckt. */}
      {ohneWerte.length > 0 && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Ohne Vergleich, weil Plan oder Ist fehlt:{" "}
          {ohneWerte.map((z) => z.label).join(", ")}.
        </p>
      )}

      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5 text-[11.5px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border-2 bg-card" style={{ borderColor: "var(--hh-ein-0)" }} />
          geplant
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full" style={{ background: "var(--hh-aus-0)" }} />
          tatsächlich
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-[3px] w-4 rounded-full bg-signal/70" />
          {massstab === "prozent" ? "Abweichung in Prozent des Plans" : `Abweichung in ${einheit}`}
        </span>
        {beleg && <span>{beleg}</span>}
        <span className="basis-full text-[11px] leading-relaxed">
          {massstab === "prozent"
            ? `Die Strecke misst, um wie viel Prozent ${wovon} vom Plan abwich — so ist eine Zeile von 231 Mio. € mit einer von 6 Mio. € vergleichbar. Der Betrag steht rechts daneben.`
            : `Die Strecke misst den Betrag der Abweichung. Große Zeilen dominieren dabei; wie exact ${wovon} beim Plan lag, zeigt die Prozent-Ansicht besser.`}{" "}
          {keineWertung}
        </span>
      </div>
    </div>
  );
}
