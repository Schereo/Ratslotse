"use client";

// Weiter-Navigation am Fuß jeder Schritt-Seite (Tims Befund 17.08.: „Wäre
// cool, wenn man direkt aus den detailseiten auch auf die nächste kommen
// könnte") — vorher führte der einzige Weg zum nächsten Schritt zurück über
// die Übersicht.
//
// Die Reihenfolge kommt aus `wegweiser.tsx` (SCHRITTE) — der einzigen Quelle,
// die auch der Schritt-Nummern-Wächter liest. Hier wird nichts gezählt und
// nichts behauptet: Kennt die Liste den Pfad nicht (Steckbriefe wie
// /haushalt/bereich haben bewusst keinen Schritt), rendert die Komponente
// nichts, statt eine falsche Nummer zu erfinden.
//
// Der letzte Schritt bekommt keinen erfundenen „Weiter"-Kandidaten, sondern
// den ehrlichen Abschluss: zurück zur Übersicht.

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { SCHRITTE } from "@/components/haushalt/wegweiser";

export function SchrittWeiter({ href }: { href: string }) {
  const i = SCHRITTE.findIndex((s) => s.href === href);
  if (i < 0) return null;
  const naechster = SCHRITTE[i + 1];

  return (
    <nav
      aria-label="Weiter im Haushalts-Weg"
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border border-border bg-card p-4"
    >
      <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Schritt {SCHRITTE[i].nr} von {SCHRITTE.length}
      </span>
      {naechster ? (
        <Link
          href={naechster.href}
          className="group inline-flex items-center gap-2 text-[13.5px] font-semibold text-primary"
        >
          Weiter: {naechster.nr} · {naechster.titel}
          <ArrowRight
            size={15}
            strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5"
          />
        </Link>
      ) : (
        <Link
          href="/haushalt"
          className="group inline-flex items-center gap-2 text-[13.5px] font-semibold text-primary"
        >
          Geschafft — zurück zur Übersicht
          <ArrowRight
            size={15}
            strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5"
          />
        </Link>
      )}
    </nav>
  );
}

/** Der Kicker über der Überschrift: „Stadtfinanzen Oldenburg · Schritt N".
 *
 *  DIE NUMMER WIRD GERECHNET, NICHT GESCHRIEBEN. Acht Seiten trugen sie bis
 *  zum 21.08.2026 als Text im Kicker, und damit gab es zwei Wahrheiten für
 *  dieselbe Zahl: den Wegweiser, der sie durchzählt, und den Satz auf der
 *  Seite. Sobald eine Seite dazukam, gingen sie auseinander — laut
 *  `tests/test_haushalt_schritte.py` am 16.08. viermal an einem Tag, und beim
 *  Zusammenlegen der Etappen (21.08.) wäre es viermal mehr geworden: Jede
 *  Zusammenlegung verschiebt alles danach um eins.
 *
 *  Auffallen kann so ein Widerspruch niemandem — der Wegweiser zeigt die
 *  richtige Nummer, die Seite die falsche, und beide sehen für sich stimmig
 *  aus. Deshalb schreibt sie jetzt keine Seite mehr selbst.
 *
 *  Kennt die Liste den Pfad nicht (Steckbriefe wie `/haushalt/bereich` haben
 *  bewusst keinen Schritt), steht nur „Stadtfinanzen Oldenburg" da — eine
 *  erfundene Nummer wäre schlimmer als keine. */
export function SchrittKicker({ href, className }: {
  href: string;
  className?: string;
}) {
  const schritt = SCHRITTE.find((s) => s.href === href);
  return (
    <p className={className ?? "font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground"}>
      Stadtfinanzen Oldenburg{schritt ? ` · Schritt ${schritt.nr}` : ""}
    </p>
  );
}

/** Die Nummer eines Schritts — für Verweis-Karten, die sie im Text mitführen
 *  („Schritt 11 · Und ist das die ganze Stadt?").
 *
 *  Dieselbe Regel wie beim Kicker: nachgeschlagen statt geschrieben. Diese
 *  beiden Stellen waren die letzten, die eine Nummer als Text trugen — und
 *  standen nach der ersten Zusammenlegung prompt um eins daneben. */
export function schrittNummer(href: string): number | null {
  return SCHRITTE.find((s) => s.href === href)?.nr ?? null;
}
