"use client";

// /haushalt/konzern — die ganze Stadt: Summe, Gesellschaften, Pläne, Gebühren.
//
// Fünfte und letzte Zusammenlegung (Tims Weg A, 21.08.2026; 19 → 11). VIER
// Seiten beantworteten dieselbe Frage — „Ist der Haushalt die ganze Stadt?" —
// und zwar in einer Kette, die man nur ganz versteht:
//
//   1. die SUMME       (Gesamtabschluss: Kernverwaltung plus alle Betriebe)
//   2. die BETEILIGTEN (jede Gesellschaft mit Auftrag und Aufsicht)
//   3. ihre PLÄNE      (was die Eigenbetriebe sich fürs Jahr vornehmen)
//   4. die FOLGE       (was davon als Gebühr bei den Leuten ankommt)
//
// Wer bei 4 anfängt, liest eine Zahl ohne Herkunft; wer bei 1 aufhört, weiß
// nicht, wer dahintersteckt. Als vier Schritte im Wegweiser standen sie
// nebeneinander wie vier Angebote.
//
// EIN DATENAUFRUF FÜR ZWEI ABSCHNITTE. Betriebe und Gebühren brauchen beide
// `herkunft`, und `useFetch` hat keinen Zwischenspeicher — zwei Abschnitte mit
// eigenem Aufruf wären zwei Requests auf fast dieselbe Adresse. Die Seite holt
// deshalb `wirtschaftsplaene`, `gebuehren` und `herkunft` zusammen und reicht
// sie durch. Sie braucht die Wirtschaftsplan-Zeilen ohnehin selbst: Aus ihnen
// entsteht `jeDokument`, die Nummerierung der einzelnen Pläne.

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, herkunftVon } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Abschnitte } from "@/components/haushalt/abschnitte";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittZeichen } from "@/components/haushalt/schritt-zeichen";
import { KonzernAbschnitt } from "@/components/haushalt/abschnitt-konzern";
import { GesellschaftenAbschnitt } from "@/components/haushalt/abschnitt-gesellschaften";
import { BetriebeAbschnitt } from "@/components/haushalt/abschnitt-betriebe";
import { GebuehrenAbschnitt } from "@/components/haushalt/abschnitt-gebuehren";

const FELDER = ["wirtschaftsplaene", "gebuehren", "herkunft"] as const;

/** Ausgeschrieben, nicht zusammengesetzt: `tests/test_quellen_dokumente.py`
 *  liest die Literale dieser Liste. Reihenfolge = Nummerierung der Chips, also
 *  die Reihenfolge der Abschnitte. */
const QUELLEN: QuellenSchluessel[] = [
  "gesamtabschluss", "beteiligungsbericht", "wirtschaftsplan", "gebuehren",
];

const MARKEN = [
  { id: "summe", titel: "Die ganze Stadt" },
  { id: "gesellschaften", titel: "Wer dahintersteckt" },
  { id: "betriebe", titel: "Was sie planen" },
  { id: "gebuehren", titel: "Was Sie zahlen" },
];

function KonzernSeiteInner() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(
    haushaltUrl(FELDER));

  // Die Adressen der Pläne, die die Betriebs-Karten zeigen — aus den KARTEN,
  // nicht aus dem Jahrgang: Den Stadthafen gibt es seit 2020 nicht mehr, die
  // Stadion-Planung endete 2024. Ihre Papiere stehen in keiner Jahrgangsliste
  // von 2026, ihre Karten aber sehr wohl auf der Seite.
  const jeDokument = useMemo(() => {
    const zeilen = data?.wirtschaftsplaene ?? [];
    const jeBetrieb = new Map<string, typeof zeilen>();
    for (const z of zeilen) jeBetrieb.set(z.betrieb, [...(jeBetrieb.get(z.betrieb) ?? []), z]);
    const gruppen = [...jeBetrieb.values()]
      .sort((a, b) => Math.abs(b.at(-1)?.ergebnis ?? 0) - Math.abs(a.at(-1)?.ergebnis ?? 0));
    const urls = gruppen
      .map((g) => [...g].sort((a, b) => a.jahr - b.jahr).at(-1))
      .map((z) => (z ? herkunftVon(data, z.herkunft_id)?.url : undefined))
      .filter((u): u is string => !!u);
    return urls.length ? { wirtschaftsplan: urls } : {};
  }, [data]);

  return (
    <Quellenkontext schluessel={QUELLEN} jeDokument={jeDokument}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Die ganze Stadt</span>
        </div>

        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/konzern" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Und ist das die ganze Stadt?
            </h1>
            <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
              Nein. Der Haushalt zeigt die Verwaltung. Klinikum, Busse, Bäder und die
              städtischen Gebäude führen eigene Bücher. Hier stehen sie: erst in einer
              gemeinsamen Rechnung, dann einzeln mit ihrem Auftrag, dann mit dem, was sie
              sich fürs Jahr vornehmen — und zuletzt das, was davon als Gebühr bei Ihnen
              ankommt.
            </p>
          </div>
          <SchrittZeichen href="/haushalt/konzern" />
        </div>

        <Abschnitte marken={MARKEN} />

        <section id="summe" className="scroll-mt-20">
          <KonzernAbschnitt />
        </section>

        <section id="gesellschaften" className="scroll-mt-20 border-t border-border pt-4">
          <GesellschaftenAbschnitt />
        </section>

        <section id="betriebe" className="scroll-mt-20 border-t border-border pt-4">
          <BetriebeAbschnitt data={data} loading={loading} />
        </section>

        <section id="gebuehren" className="scroll-mt-20 border-t border-border pt-4">
          <GebuehrenAbschnitt data={data} loading={loading} />
        </section>

        <SchrittWeiter href="/haushalt/konzern" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function KonzernSeite() {
  // `useSearchParams` im Gesellschaften-Abschnitt (`?g=`) braucht eine
  // Suspense-Grenze — sie lag vorher an der Beteiligungen-Seite.
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}
    >
      <KonzernSeiteInner />
    </Suspense>
  );
}
