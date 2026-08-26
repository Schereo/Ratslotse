"use client";

// /haushalt/produkte — vom Teilhaushalt zur einzelnen Aufgabe.
//
// Vierte von fünf Zusammenlegungen (Tims Weg A, 21.08.2026). „Was steckt
// hinter den Namen?" und „Was kostet eigentlich …?" waren zwei Schritte, gehen
// aber denselben Baum hinunter: erst die zehn Teilhaushalte im Klartext, dann
// die einzelnen Produkte darin. Wer den zweiten Schritt ohne den ersten liest,
// sucht Aufgaben in Bereichen, deren Namen ihm nichts sagen.
//
// DIE DRITTE EBENE BLEIBT EINE EIGENE SEITE: `/haushalt/bereich?thh=…` ist der
// Steckbrief eines einzelnen Teilhaushalts. Er hat bewusst keinen Schritt im
// Wegweiser — man kommt dorthin aus der Liste, nicht der Reihe nach.

import { Suspense } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittZeichen } from "@/components/haushalt/schritt-zeichen";
import { BereicheAbschnitt } from "@/components/haushalt/abschnitt-bereiche";
import { ProdukteAbschnitt } from "@/components/haushalt/abschnitt-produkte";

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste. Vereinigung beider Abschnitte, in
 *  Leserichtung — die Bereichs-Übersicht belegt sich mit `plan`, die
 *  Produktebene mit `teilhaushalt`. */
const QUELLEN: QuellenSchluessel[] = [
  "plan", "steuern", "steuerkraft", "teilhaushalt",
];

const MARKEN = [
  { id: "bereiche", titel: "Was die Namen heißen" },
  { id: "produkte", titel: "Was einzelne Aufgaben kosten" },
];

function ProdukteSeiteInner() {
  return (
    // KEIN gemeinsames `jahr`: Die Bereichs-Übersicht zeigt den jüngsten
    // Ansatz, die Produktebene den jüngsten Jahrgang MIT Produktdaten — und
    // die liegen auseinander, weil die Produktebene erst mit dem Abschluss
    // vorliegt. Ohne den Wert nimmt jeder Beleg das jüngste Dokument seiner
    // Quelle und schreibt den Jahrgang an.
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Was kostet eigentlich …?</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/produkte" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Was kostet eigentlich …?
            </h1>
            <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
              Der Haushalt ist in zehn Teilhaushalte geteilt, und deren Namen stammen aus
              der Verwaltungsgliederung: Sie sagen, wer zuständig ist, nicht, worum es
              geht. Zuerst steht deshalb zu jedem eine Zeile, die man ohne Vorwissen lesen
              kann — und darunter die einzelnen Aufgaben mit ihren Kosten.
            </p>
          </div>
          <SchrittZeichen href="/haushalt/produkte" />
        </div>

        <Abschnitte marken={MARKEN} />

        <section id="bereiche" className="scroll-mt-20">
          <BereicheAbschnitt />
        </section>

        <section id="produkte" className="scroll-mt-20 border-t border-border pt-4">
          <ProdukteAbschnitt />
        </section>

        <SchrittWeiter href="/haushalt/produkte" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function ProdukteSeite() {
  // `useSearchParams` im Produkte-Abschnitt braucht eine Suspense-Grenze.
  return (
    <Suspense
      fallback={
        <div className="py-16 text-center text-sm text-muted-foreground">
          Produkte werden geladen …
        </div>
      }
    >
      <ProdukteSeiteInner />
    </Suspense>
  );
}
