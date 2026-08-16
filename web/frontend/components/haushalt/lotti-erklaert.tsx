"use client";

// „Lotti erklärt's einfach" für den Haushalts-Bereich.
//
// Der Haushalt ist der sperrigste Stoff, den Ratslotse zeigt: Doppik-Vokabular,
// Millionen ohne Bezugsgröße, Zuständigkeiten quer über drei Ebenen. Lotti
// steht hier in ihrer angestammten Rolle (Beobachterin, die einordnet — nie
// Autorin einer Antwort) und übersetzt genau eine Sache pro Karte in
// Alltagssprache. Regeln aus der Designsprache: max. drei Sätze, keine
// Fachwörter ohne Erklärung, keine Bewertung („zu viel“, „zu wenig“).
//
// Zwei Formen, mehr braucht es nicht:
// - `LottiErklaert`: die Karte an einer schweren Stelle im Fluss.
// - `LottiVergleich`: eine große Zahl in eine Alltagsgröße übersetzt
//   (pro Kopf, pro Tag) — der Rechenweg steht dabei, weil er unsere
//   Rechnung ist und keine amtliche Kennzahl.

import { Mascot } from "@/components/mascot";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

export function LottiErklaert({
  titel, text, pose = "point", className,
}: {
  titel: string;
  text: string;
  pose?: "point" | "search" | "wave" | "confused";
  className?: string;
}) {
  return (
    <aside className={cn(
      "flex gap-3.5 rounded-2xl border border-primary/20 bg-primary/[0.04] p-3.5",
      className,
    )}>
      <Mascot pose={pose} decorative className="h-11 w-11 flex-none sm:h-12 sm:w-12" />
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
          {titel}
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">
          <GlossaryText text={text} />
        </p>
      </div>
    </aside>
  );
}

/** Große Zahl → Alltagsgröße. `pro_kopf` rechnet mit der Einwohnerzahl, die
 *  als Quelle mitgegeben wird; ohne sie erscheint der Baustein nicht. */
export function LottiVergleich({
  betragMio, einwohner, was, className,
}: {
  betragMio: number;
  einwohner: number;
  /** Wofür das Geld ist — steht im Satz („für Kitas und Jugendhilfe"). */
  was: string;
  className?: string;
}) {
  if (!einwohner) return null;
  const proKopf = Math.round((betragMio * 1_000_000) / einwohner);
  const proKopfMonat = Math.round(proKopf / 12);
  return (
    <aside className={cn(
      "flex gap-3.5 rounded-2xl border border-primary/20 bg-primary/[0.04] p-3.5",
      className,
    )}>
      <Mascot pose="point" decorative className="h-11 w-11 flex-none sm:h-12 sm:w-12" />
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
          Was heißt das pro Kopf?
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">
          {betragMio.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&#8239;Mio.&nbsp;€ {was} sind{" "}
          <strong>{proKopf.toLocaleString("de-DE")}&nbsp;€ pro Einwohner*in im Jahr</strong>
          {proKopfMonat >= 1 && <> — rund {proKopfMonat.toLocaleString("de-DE")}&nbsp;€ im Monat</>}.
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          Unsere Rechnung: Betrag geteilt durch {einwohner.toLocaleString("de-DE")} Einwohner*innen.
          Keine amtliche Kennzahl — die Stadt weist sie so nicht aus.
        </p>
      </div>
    </aside>
  );
}
