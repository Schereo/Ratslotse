"use client";

// /haushalt/labor — das Haushalts-Labor (Design H-19). Zum Ausprobieren,
// nicht zum Beschließen.
//
// Diese Datei holt nur die Daten: den Haushalt für die Rechnung und die
// Produktebene des jüngsten vorliegenden Jahres, aus der die Regler ihre
// Vergleichsgrößen ziehen („so viel wie …"). Die Regeln, nach denen das Labor
// rechnet und was es bewusst NICHT rechnet, stehen bei der Komponente:
// components/haushalt/labor.tsx.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, ProdukteAntwort, jahreSortiert } from "@/lib/haushalt";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Labor } from "@/components/haushalt/labor";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

export default function LaborPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  // Die Produktebene liegt nur für abgeschlossene Jahre vor — wir nehmen das
  // jüngste. Fehlt sie ganz, läuft das Labor ohne Vergleichsgrößen weiter.
  const produktJahr = data?.produkt_jahre?.at(-1) ?? null;
  const { data: produkte } = useFetch<ProdukteAntwort>(
    produktJahr ? `/council/haushalt/produkte?jahr=${produktJahr}` : null);

  // Reihenfolge = Nummerierung der Beleg-Chips, deshalb nach Leserichtung:
  // Plan (die Zahl, gegen die gerechnet wird), Steuern am Regler, Rücklage im
  // Ergebnis, dann die beiden neuen Dokumentquellen, zuletzt der Gegen-Block.
  const quellen: QuellenSchluessel[] = [
    "plan", "steuern", "ruecklage", "jahresabschluss", "teilhaushalt", "steuerkraft", "hebesaetze",
  ];

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Labor wird geladen …</div>;
  }

  return (
    <Quellenkontext schluessel={quellen} jahr={jahreSortiert(data).at(-1) ?? null}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Haushalts-Labor</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">Haushalts-Labor</h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Was passiert, wenn der Rat an den Stellschrauben dreht? Hier kannst du es ausprobieren.
          Das ist eine Rechnung zum Verstehen — kein Vorschlag und schon gar kein Beschluss.
        </p>
      </div>

      <Labor daten={data} produkte={produkte?.produkte ?? []} produktJahr={produktJahr} />

      <LottiErklaert
        titel="Warum das kein Sparvorschlag ist"
        text="Dieses Labor rechnet mit ganzen Bereichen und festen Annahmen. Ein echter Haushalt entsteht anders: Die Verwaltung rechnet jede Position durch, Ausschüsse beraten monatelang, und am Ende stimmt der Rat ab. Was du hier siehst, ist ein Gefühl für Größenordnungen — mehr nicht, aber auch nicht weniger."
      />

      <SchrittWeiter href="/haushalt/labor" />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
