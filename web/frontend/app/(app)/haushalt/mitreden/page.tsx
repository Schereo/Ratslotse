"use client";

// /haushalt/mitreden — die Etappe „Mitreden" als EINE Seite.
//
// WARUM ZUSAMMENGELEGT (Tim, 21.08.2026): „Ganz generell bin ich auch gar kein
// Fan davon, dass wir jetzt irgendwie 19 Unterseiten haben. […] Man weiß gar
// nicht, wo man anfangen soll. […] Man wird erschlagen vor Inhalten."
//
// Gemessen war der Befund schärfer als „neunzehn sind viele": Mehrere Seiten
// waren entlang unserer EINLESE-Geschichte geschnitten, nicht entlang der
// Frage, die jemand hat. Diese Abschnitte beantworten zusammen eine einzige —
// „Wie rede ich mit?" —, und `/haushalt/jahr` war im ganzen Frontend über
// nichts als den Wegweiser erreichbar. Eine Seite, die sonst niemand
// verlinkt, trägt nicht als eigenes Ziel.
//
// DAS LABOR IST SEIT 24.08.2026 WIEDER EIGENE SEITE (/haushalt/labor). Es
// stand hier drei Tage als dritter Abschnitt; Tims Entscheidung: Es soll
// deutlich mehr Stellschrauben bekommen, und ein wachsendes Werkzeug braucht
// eine eigene Adresse. Der Befund von damals — nichts verlinkte hin — ist
// damit nicht zurück: Diese Seite, der Steuer-Steckbrief und die
// Weiter-Navigation am Fuß führen hin.
//
// Die Reihenfolge ist die des Mitredens: erst WANN (sonst kommt man zu spät),
// dann WORÜBER gestritten wurde — ausprobieren geht danach im Labor.
//
// DER RAHMEN LIEGT HIER, der Inhalt in den `abschnitt-*.tsx`: Quellenkontext
// und Verzeichnis führen die VEREINIGUNG aller Quellen, und der Beleg-Chip
// nummeriert seitenweise. Verschachtelte Quellenkontexte hätten
// konkurrierende Nummerierungen ergeben.

import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight, ChevronRight } from "lucide-react";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittZeichen } from "@/components/haushalt/schritt-zeichen";
import { TermineAbschnitt } from "@/components/haushalt/abschnitt-termine";
import { StreitAbschnitt } from "@/components/haushalt/abschnitt-streit";

/** Beide Abschnitte belegen sich ausschließlich mit dem
 *  Ratsinformationssystem — Termine wie Streit sind Ratsdaten, keine
 *  Finanzdokumente. (`tests/test_quellen_dokumente.py` liest die Literale
 *  dieser Liste, um stumme Beleg-Chips zu finden.) */
const QUELLEN: QuellenSchluessel[] = ["ratsbeschluss"];

const MARKEN = [
  { id: "termine", titel: "Wann entschieden wird" },
  { id: "streit", titel: "Der Streit ums Geld" },
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

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/mitreden" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Mitreden
            </h1>
            <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
              Ein Haushalt ist kein Rechenergebnis, sondern ein Kompromiss — und er
              entsteht in öffentlichen Sitzungen. Hier steht, wann darüber entschieden
              wird und worüber die Fraktionen gestritten haben. Selbst an den
              Stellschrauben drehen kannst du danach im{" "}
              <Link href="/haushalt/labor" className="font-semibold text-primary">
                Haushalts-Labor
              </Link>.
            </p>
          </div>
          <SchrittZeichen href="/haushalt/mitreden" />
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

        {/* Die Anschlussstelle zum Labor — bewusst eine Karte statt nur des
            Satzes im Kopf: Wer bis hierher gelesen hat, weiß, worum gestritten
            wurde, und ist genau die Person, die jetzt selbst drehen will. */}
        <Link
          href="/haushalt/labor"
          className="group flex items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40"
        >
          <span>
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Selbst ausprobieren
            </span>
            <span className="mt-1 block text-[13.5px] font-semibold">
              Haushalts-Labor: an den Stellschrauben drehen und sehen, was das ausmacht
            </span>
          </span>
          <ArrowRight size={16} strokeWidth={2}
            className="shrink-0 text-primary transition-transform group-hover:translate-x-0.5" />
        </Link>

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
