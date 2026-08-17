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
