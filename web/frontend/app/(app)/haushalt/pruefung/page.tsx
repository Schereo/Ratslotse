"use client";

// /haushalt/pruefung — „Die Gegenprobe" in ihrer zweiten Hälfte: geprüft und
// zusammengefasst.
//
// Zweite von fünf Zusammenlegungen (Tims Weg A, 21.08.2026). Bis dahin waren
// das zwei Schritte: „Die Prüfung" (was das Rechnungsprüfungsamt fand) und
// „Die dreizehn Zahlen" (womit die Stadt ihren eigenen Abschluss zusammenfasst).
// Sie beantworten dieselbe Frage aus zwei Richtungen — von außen geprüft, von
// innen zusammengefasst —, und nebeneinander sind sie mehr wert als
// hintereinander: Die Kennzahlen sagen, wie die Stadt dasteht, die
// Feststellungen, wie verlässlich diese Auskunft ist.
//
// Der Rahmen liegt hier, der Inhalt in den beiden `abschnitt-*.tsx` (die
// Begründung steht im Kopf von `abschnitt-termine.tsx`).

import { Suspense } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { PruefungAbschnitt } from "@/components/haushalt/abschnitt-pruefung";
import { KennzahlenAbschnitt } from "@/components/haushalt/abschnitt-kennzahlen";

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste, um stumme Beleg-Chips zu finden. */
const QUELLEN: QuellenSchluessel[] = ["pruefbericht", "kennzahlen", "bilanz"];

const MARKEN = [
  { id: "feststellungen", titel: "Was geprüft wurde" },
  { id: "kennzahlen", titel: "Die dreizehn Zahlen" },
];

function PruefungInner() {
  return (
    // KEIN `jahr` am Kontext. Die beiden Abschnitte führen verschiedene
    // Jahrgänge — der Prüfbericht den gewählten (`?jahr=`), die Kennzahlen den
    // jüngsten Rechenschaftsbericht. Ein gemeinsamer Wert wäre für einen von
    // beiden der falsche; ohne ihn nimmt jeder Beleg das jüngste Dokument
    // seiner Quelle und schreibt den Jahrgang an.
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Geprüft und zusammengefasst</span>
        </div>

        <div>
          <SchrittKicker href="/haushalt/pruefung" />
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
            Geprüft und zusammengefasst
          </h1>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            Jeder Jahresabschluss wird von einer eigenen Stelle geprüft, die dem Rat
            berichtet und nicht der Verwaltungsspitze untersteht. Und am Ende jedes
            Rechenschaftsberichts fasst die Stadt denselben Abschluss selbst in
            dreizehn Kennzahlen zusammen. Beides gehört nebeneinander: Die Kennzahlen
            sagen, wie die Stadt dasteht — die Feststellungen, wie verlässlich diese
            Auskunft ist.
          </p>
        </div>

        <Abschnitte marken={MARKEN} />

        <section id="feststellungen" className="scroll-mt-20">
          <PruefungAbschnitt />
        </section>

        <section id="kennzahlen" className="scroll-mt-20 border-t border-border pt-4">
          <KennzahlenAbschnitt />
        </section>

        <SchrittWeiter href="/haushalt/pruefung" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function PruefungPage() {
  // `useSearchParams` im Prüfungs-Abschnitt (`?jahr=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Prüfungs-Seite und bleibt hier.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <PruefungInner />
    </Suspense>
  );
}
