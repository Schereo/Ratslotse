"use client";

// /haushalt/mitreden — die Etappe „Mitreden" als EINE Seite.
//
// WARUM ZUSAMMENGELEGT (Tim, 21.08.2026): „Ganz generell bin ich auch gar kein
// Fan davon, dass wir jetzt irgendwie 19 Unterseiten haben. […] Man weiß gar
// nicht, wo man anfangen soll. […] Man wird erschlagen vor Inhalten."
//
// Gemessen war der Befund schärfer als „neunzehn sind viele": Mehrere Seiten
// waren entlang unserer EINLESE-Geschichte geschnitten, nicht entlang der
// Frage, die jemand hat. Diese drei beantworten zusammen eine einzige — „Wie
// rede ich mit?" —, und zwei von ihnen (`/haushalt/jahr`, `/haushalt/labor`)
// waren im ganzen Frontend über nichts als den Wegweiser erreichbar. Eine
// Seite, die sonst niemand verlinkt, trägt nicht als eigenes Ziel.
//
// Die Reihenfolge ist die des Mitredens: erst WANN (sonst kommt man zu spät),
// dann WORÜBER gestritten wurde, dann selbst ausprobieren.
//
// DER RAHMEN LIEGT HIER, der Inhalt in den drei `abschnitt-*.tsx`. Das ist
// keine Kosmetik: Quellenkontext und Verzeichnis müssen die VEREINIGUNG aller
// Quellen führen (`ratsbeschluss` plus die sieben des Labors), und der
// Beleg-Chip nummeriert seitenweise. Drei verschachtelte Quellenkontexte
// hätten drei konkurrierende Nummerierungen ergeben.

import { Suspense } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { TermineAbschnitt } from "@/components/haushalt/abschnitt-termine";
import { StreitAbschnitt } from "@/components/haushalt/abschnitt-streit";
import { LaborAbschnitt } from "@/components/haushalt/abschnitt-labor";

/** Die Vereinigung der Quellen aller drei Abschnitte, AUSGESCHRIEBEN.
 *
 *  Ein erster Versuch setzte sie aus einem Spread zusammen
 *  (`["ratsbeschluss", ...LABOR_QUELLEN]`). Das las sich kürzer, aber zwei
 *  Dinge sprechen dagegen: Wer die Seite liest, sieht ihre Beleglage nicht
 *  mehr an einer Stelle — und `tests/test_quellen_dokumente.py` liest die
 *  Literale dieser Liste, um stumme Beleg-Chips zu finden. Durch einen Spread
 *  sieht der Wächter nicht hindurch und meldete fünf Chips als stumm, die es
 *  nicht waren.
 *
 *  `ratsbeschluss` zuerst: Die Reihenfolge ist die Nummerierung der Chips, und
 *  die beiden ersten Abschnitte belegen sich ausschließlich damit. */
const QUELLEN: QuellenSchluessel[] = [
  "ratsbeschluss",
  // ab hier: das Haushalts-Labor
  "plan", "steuern", "ruecklage", "jahresabschluss", "teilhaushalt",
  "steuerkraft", "hebesaetze",
];

const MARKEN = [
  { id: "termine", titel: "Wann entschieden wird" },
  { id: "streit", titel: "Der Streit ums Geld" },
  { id: "labor", titel: "Selbst ausprobieren" },
];

function MitredenInner() {
  return (
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Mitreden</span>
        </div>

        <div>
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stadtfinanzen Oldenburg · Schritt 17
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
            Mitreden
          </h1>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            Ein Haushalt ist kein Rechenergebnis, sondern ein Kompromiss — und er
            entsteht in öffentlichen Sitzungen. Hier steht, wann darüber entschieden
            wird, worüber die Fraktionen gestritten haben, und was passierte, wenn man
            selbst an den Stellschrauben drehte.
          </p>
        </div>

        <Abschnitte marken={MARKEN} />

        {/* `scroll-mt` an jedem Abschnitt: Der klebende Streifen deckt die
            Überschrift sonst zu, wenn jemand mit einem `#anker` von außen
            kommt — dann läuft unser eigener Sprung-Rechner gar nicht. */}
        <section id="termine" className="scroll-mt-20">
          <TermineAbschnitt />
        </section>

        <section id="streit" className="scroll-mt-20 border-t border-border pt-4">
          <StreitAbschnitt />
        </section>

        <section id="labor" className="scroll-mt-20 border-t border-border pt-4">
          <LaborAbschnitt />
        </section>

        <SchrittWeiter href="/haushalt/mitreden" />

        <Quellenverzeichnis schluessel={QUELLEN} />

        <Link
          href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary"
        >
          Zurück zur Übersicht über den Haushalt
          <ChevronRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </Quellenkontext>
  );
}

export default function MitredenPage() {
  // `useSearchParams` im Streit-Abschnitt (`?jahr=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Streit-Seite und zieht mit um.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <MitredenInner />
    </Suspense>
  );
}
