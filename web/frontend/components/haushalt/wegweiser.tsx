// Wegweiser zu den Vertiefungsseiten (Einnahmen, Produkte, Pflicht/Kür,
// Labor, Plan gegen Ist).
//
// Die drei Karten standen als reine Textkacheln zwischen zwei großen
// Diagramm-Panels und gingen dort unter (Tim, 16.08.). Sie sind aber der
// einzige Weg in die Tiefe — deshalb tragen sie jetzt ein Piktogramm im
// Primär-Tint, den Titel in der Display-Schrift und einen Pfeil, der beim
// Überfahren mitgeht. Farbe bleibt Hafenblau: Signal-Orange ist im Haushalt
// dem Minus vorbehalten.

import Link from "next/link";
import { ArrowRight, Coins, GitCompareArrows, Receipt, Scale, SlidersHorizontal } from "lucide-react";

const ZIELE = [
  {
    href: "/haushalt/einnahmen",
    Icon: Coins,
    titel: "Woher kommt das Geld?",
    text: "Alle Einnahmequellen — und bei welchen der Rat überhaupt etwas zu entscheiden hat.",
  },
  {
    href: "/haushalt/produkte",
    Icon: Receipt,
    titel: "Was kostet eigentlich …?",
    text: "Archiv, Feuerwehr, Schwimmbad: einzelne Aufgaben mit Kosten, Auftrag und Spielraum.",
  },
  {
    href: "/haushalt/pflicht",
    Icon: Scale,
    titel: "Muss oder kann?",
    text: "Wie viel vom Haushalt gesetzlich vorgeschrieben ist — und wie wenig frei verfügbar.",
  },
  {
    href: "/haushalt/labor",
    Icon: SlidersHorizontal,
    titel: "Haushalts-Labor",
    text: "Selbst an den Stellschrauben drehen und sehen, was das ausmacht.",
  },
  {
    href: "/haushalt/plan-ist",
    Icon: GitCompareArrows,
    titel: "Geplant und geworden",
    text: "Was am Jahresende wirklich zusammenkam — aus den Jahresabschlüssen.",
  },
];

export function Wegweiser() {
  return (
    <div>
      <p className="mb-2.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Tiefer einsteigen
      </p>
      {/* Fünf Karten: auf breiten Schirmen drei/zwei statt vier/eins — bei
          `lg:grid-cols-4` stünde die fünfte allein in einer eigenen Zeile. */}
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {ZIELE.map(({ href, Icon, titel, text }) => (
          <Link key={href} href={href}
            className="group flex items-start gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40 sm:flex-col sm:gap-0">
            <span aria-hidden className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary/[0.16] sm:mb-3">
              <Icon size={22} strokeWidth={2} />
            </span>
            {/* Der Spalte gibt flex-1 + mt-auto eine gemeinsame Grundlinie:
                Sonst rutscht „Ansehen" mit der Textlänge auf und ab. */}
            <span className="flex min-w-0 flex-col sm:flex-1">
              <span className="block font-display text-[15px] font-bold leading-snug tracking-tight">{titel}</span>
              <span className="mt-1 block text-[12.5px] leading-relaxed text-muted-foreground">{text}</span>
              <span className="mt-2.5 flex items-center gap-1 text-[12.5px] font-semibold text-primary sm:mt-auto sm:pt-2.5">
                Ansehen
                <ArrowRight size={14} strokeWidth={2}
                  className="transition-transform group-hover:translate-x-0.5" />
              </span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
