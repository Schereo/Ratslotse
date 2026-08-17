// <Wasserfall> — Brutto, Abzüge, Ergebnis als eine Rechnung (GB-14).
//
// Der Vertrag: `schritte: {label, wert, art: "start" | "abzug" | "ergebnis"}[]`
// auf einer gemeinsamen Achse. Die Abzüge hängen an der LAUFSUMME — gerechnet
// mit `cumsum` aus d3-array, nicht als „schwebender Balken" von Hand: Wer
// einen zweiten Abzug einfügt, bekommt seine Position geschenkt statt sie
// auszurechnen.
//
// Warum diese Form und keine drei Balken nebeneinander: Drei gleich lange
// Balken (Ausgaben, Einnahmen, Differenz) zwingen die Leserin, selbst zu
// subtrahieren. Hier steht jeder Abzug rechtsbündig unter dem Betrag, von dem
// er abgeht — der Abzug ist eine Bewegung, keine Aufzählung.
//
// Kein SVG, sondern Kästen mit Prozentbreiten (übernommen aus der Haushalts-
// Fassung, die diese Komponente ablöst): Eine feste viewBox skaliert ihre
// Schrift mit — auf 375 px unlesbar genau dort, wo die meisten lesen. Die
// Beträge stehen als echte Schrift in der Zeile ÜBER ihrem Balken und wachsen
// nie aus einem Kasten heraus. Die Balken selbst sind dekorativ
// (`aria-hidden`) — was sie zeigen, sagen die Zeilen, und nur die werden
// vorgelesen.
//
// Die Breiten sind exakt, ohne Mindestbreite: Ein Abzug von 2 % ist ein
// 2-%-Streifen. Eine Mindestbreite machte aus „fast nichts" ein sichtbares
// Stück und wäre eine Behauptung.
//
// KEIN ROT AM ERGEBNIS (GB-14 wörtlich): Ein Zuschussbedarf ist
// Daseinsvorsorge, keine Schwäche. Das Ergebnis trägt die Differenz-
// Konvention des Bereichs — Schraffur mit gestrichelter Signal-Kante — weil
// es eine gerechnete Größe ist, keine Zeile des Dokuments; bewertet wird
// nichts.
//
// SUMMENPROBE STATT VERTRAUEN: Weicht der übergebene Ergebnis-Wert von der
// Laufsumme ab (Rundungs- oder Rechenfehler der Seite), sagt die Grafik das
// unter dem Bild, statt still den falschen Balken zu zeichnen. Deshalb nimmt
// sie das Ergebnis als eigenen Schritt entgegen: Beide Beträge sind meist
// schon gerundet, und wer die Differenz aus den Rohwerten kennt, gibt sie mit
// (bei den nicht rechtsfähigen Stiftungen kippte durch Doppelrundung sogar
// einmal die Richtung).

import type { ReactNode } from "react";
import { cumsum } from "d3-array";
import { deZahl } from "@/components/grafik/format";
import { cn } from "@/lib/utils";

export type WasserfallSchritt = {
  label: string;
  /** Immer positiv — die Richtung sagt `art`. */
  wert: number;
  art: "start" | "abzug" | "ergebnis";
  /** Der Halbsatz hinter dem Label („Gebühren, Entgelte, Erstattungen …"). */
  hinweis?: string;
  /** Rampen-Token (`var(--hh-…)`). Ohne Angabe: start `--hh-aus-0`,
   *  abzug `--hh-ein-0`; das Ergebnis ist immer die Schraffur. */
  farbe?: string;
};

/** Über dieser Abweichung (in Einheiten der Achse) meldet die Summenprobe.
 *  Bemessen an Beträgen, die auf EINE Nachkommastelle gerundet ankommen:
 *  Start und Abzug dürfen je ±0,05 danebenliegen, das aus Rohwerten
 *  gerundete Ergebnis noch einmal — zusammen 0,15. Alles darüber ist kein
 *  Rundungsrauschen mehr, sondern ein Rechenfehler der Seite. */
const TOLERANZ = 0.16;

const VORGABE: Record<"start" | "abzug", string> = {
  start: "var(--hh-aus-0)",
  abzug: "var(--hh-ein-0)",
};

function Zeile({ s, von, bis, skala, nachkomma }: {
  s: WasserfallSchritt;
  /** Linke und rechte Kante des Balkens auf der Achse. */
  von: number;
  bis: number;
  skala: number;
  nachkomma: number;
}) {
  const links = (Math.max(von, 0) / skala) * 100;
  const breite = (Math.max(bis - von, 0) / skala) * 100;
  const ergebnis = s.art === "ergebnis";
  return (
    <div>
      <div className="flex items-baseline gap-2.5">
        <p className="min-w-0 flex-1 text-[12.5px] leading-relaxed text-foreground/85">
          {s.art === "abzug" && <span aria-hidden="true">−&#8239;</span>}
          {s.label}
          {s.hinweis && <span className="text-muted-foreground"> — {s.hinweis}</span>}
        </p>
        <span className={cn(
          "flex-none font-display text-[15px] font-bold tabular-nums",
          ergebnis && "text-signal",
        )}>
          {deZahl(s.wert, nachkomma)}
        </span>
      </div>
      <div aria-hidden="true" className="mt-1 h-6">
        <div
          className={cn(
            "h-full rounded",
            ergebnis && "hh-schraffur border border-dashed border-signal",
          )}
          style={{
            marginLeft: `${links}%`,
            width: `${breite}%`,
            background: ergebnis ? undefined : s.farbe ?? VORGABE[s.art as "start" | "abzug"],
          }}
        />
      </div>
    </div>
  );
}

export function Wasserfall({ schritte, einheit, kicker, beleg, nachkomma = 1, className }: {
  /** Die Rechnung von oben nach unten: erst `start`, dann Abzüge, zuletzt
   *  das Ergebnis („aus Steuermitteln", „trägt die Stadt"). */
  schritte: WasserfallSchritt[];
  /** Achsen-Einheit, steht rechts oben: „Mio. € 2026". */
  einheit: string;
  /** Mono-Kicker links oben; ohne ihn beginnt die Karte mit der Rechnung. */
  kicker?: string;
  /** Beleg-Chip-Slot (GB-00) — die Seite kennt ihren Quellenkontext. */
  beleg?: ReactNode;
  /** Nachkommastellen der Beträge (fest, damit die Spalte nicht springt). */
  nachkomma?: number;
  className?: string;
}) {
  const werte = schritte.filter((s) => s.wert > 0 || s.art === "ergebnis");
  if (!werte.some((s) => s.art === "start")) return null;

  // Die Laufsumme: Start zählt hinzu, Abzüge ziehen ab, das Ergebnis ist
  // eine Probe und bewegt sie nicht. `cumsum` liefert die Summe NACH jedem
  // Schritt — die rechte Kante eines Abzugs ist also die Laufsumme davor.
  const lauf = Array.from(cumsum(werte.map((s) =>
    s.art === "start" ? s.wert : s.art === "abzug" ? -s.wert : 0)));
  const skala = Math.max(...lauf, ...werte.map((s) => s.wert), 1);

  const letzterStand = lauf[lauf.length - 1] ?? 0;
  const ergebnis = werte.find((s) => s.art === "ergebnis");
  const probeDaneben = ergebnis != null
    && Math.abs(ergebnis.wert - Math.max(letzterStand, 0)) > TOLERANZ;

  return (
    <div className={className}>
      {(kicker || einheit) && (
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {kicker}{beleg}
          </p>
          <span className="flex-none font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
            {einheit}
          </span>
        </div>
      )}

      <div className="flex flex-col gap-2.5">
        {werte.map((s, i) => {
          const vorher = i > 0 ? lauf[i - 1] : 0;
          const [von, bis] = s.art === "start"
            ? [0, s.wert]
            : s.art === "abzug"
              ? [lauf[i], vorher]
              : [0, s.wert];
          return <Zeile key={`${s.art}-${s.label}`} s={s} von={von} bis={bis}
            skala={skala} nachkomma={nachkomma} />;
        })}
      </div>

      {probeDaneben && ergebnis && (
        <p className="mt-2.5 text-[11px] leading-relaxed text-signal">
          Summenprobe: Die Schritte ergeben {deZahl(Math.max(letzterStand, 0), nachkomma)},
          als Ergebnis übergeben sind {deZahl(ergebnis.wert, nachkomma)} — die Grafik zeigt
          das, statt zu strecken.
        </p>
      )}
    </div>
  );
}
