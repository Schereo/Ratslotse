"use client";

// /haushalt/labor — das Haushalts-Labor (Design H-19). Zum Ausprobieren,
// nicht zum Beschließen.
//
// Vom 21. bis 24.08.2026 war das Labor der dritte Abschnitt von
// /haushalt/mitreden (#698). Es ist wieder eine eigene Seite — Tims
// Entscheidung vom 24.08.: Das Labor soll deutlich mehr Stellschrauben
// bekommen, und ein wachsendes Werkzeug braucht eine eigene Adresse statt
// eines Abschnitts am Fuß einer langen Seite. Der Befund hinter #698 —
// niemand außer dem Wegweiser verlinkte hierher — ist dabei nicht zurück:
// Die Mitreden-Seite, der Steuer-Steckbrief und die Weiter-Navigation
// führen jetzt alle hierher.
//
// Diese Datei holt nur die Daten; die Regeln, nach denen das Labor rechnet
// und was es bewusst NICHT rechnet, stehen bei der Komponente
// (components/haushalt/labor.tsx). Vier Aufrufe, drei davon unkritisch:
// Der Haushalt trägt die Rechnung — Städtevergleich (Städte-Leiter und die
// belegte Grundsteuer-Aufteilung), Investitionsprogramm und Schuldenreihe
// sind Zugaben, ohne die das Labor mit weniger Bausteinen weiterläuft.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, ProdukteAntwort, jahreSortiert } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import type { VergleichDaten } from "@/lib/haushalt-vergleich";
import type { ProgrammDaten } from "@/lib/haushalt-investitionsprogramm";
import type { SchuldenDaten } from "@/lib/haushalt-schulden";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Labor } from "@/components/haushalt/labor";

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
// `hebesaetze` seit 21.08.2026 (der geltende Satz kommt aus der Reihe statt
// aus einer Konstante); `ergebnishaushalt`, `gebuehren` und
// `haushaltssatzung` seit dem Werkbank-Umbau (Labor 2.0): Rücklagen-Pfad,
// gesperrte Gebühren-Schraube und der Kredit-Kasten der dritten Werkbank.
const FELDER = ["jahre", "produkt_jahre", "steuern", "steuerkraft", "einwohner",
                "ergebnisrechnung", "hebesaetze", "ergebnishaushalt",
                "gebuehren", "haushaltssatzung"] as const;

/** Reihenfolge = Nummerierung der Beleg-Chips, deshalb nach Leserichtung:
 *  Plan (die Zahl, gegen die gerechnet wird), die Regler der ersten Werkbank
 *  (Steuern, Hebesätze, LSN-Aufteilung, Gebühren), die Ausgaben-Werkbank
 *  (Teilhaushalt), die dritte Werkbank (Programm, Satzung, Schulden), dann
 *  die Ergebnis-Spalte (Steuerkraft-Spanne, Rücklage, Planjahre) und der
 *  Anker unten (Jahresabschluss). */
const QUELLEN: QuellenSchluessel[] = [
  "plan", "steuern", "hebesaetze", "lsn_realsteuern", "gebuehren",
  "teilhaushalt", "investitionsprogramm", "haushaltssatzung", "schulden",
  "steuerkraft", "ruecklage", "ergebnishaushalt", "jahresabschluss",
];

export default function LaborPage() {
  // Das Labor rechnet ausschließlich mit der Kernverwaltung; die
  // Teilhaushalts-Ebene der Ergebnisrechnung braucht es nicht.
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER, "keine"));
  // Die Produktebene liegt nur für abgeschlossene Jahre vor — wir nehmen das
  // jüngste. Fehlt sie ganz, läuft das Labor ohne Vergleichsgrößen weiter.
  const produktJahr = data?.produkt_jahre?.at(-1) ?? null;
  const { data: produkte } = useFetch<ProdukteAntwort>(
    produktJahr ? `/council/haushalt/produkte?jahr=${produktJahr}` : null);
  // Die drei Zugaben — jede Komponente kommt mit `null` zurecht und lässt
  // ihren Baustein dann weg, statt mit halben Daten zu rechnen.
  const { data: vergleich } = useFetch<VergleichDaten>("/council/haushalt/vergleich");
  const { data: programm } = useFetch<ProgrammDaten>("/council/haushalt/investitionsprogramm");
  const { data: schulden } = useFetch<SchuldenDaten>("/council/haushalt/schulden");

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Labor wird geladen …</div>;
  }

  return (
    <Quellenkontext schluessel={QUELLEN} jahr={jahreSortiert(data).at(-1) ?? null}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Haushalts-Labor</span>
      </div>

      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <SchrittKicker href="/haushalt/labor" />
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">Haushalts-Labor</h1>
          <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
            Was passiert, wenn der Rat an den Stellschrauben dreht? Drei Werkbänke, jede mit
            ihrer eigenen Zielgröße — zum Ausprobieren. Das ist eine Rechnung zum Verstehen,
            kein Vorschlag und schon gar kein Beschluss.
          </p>
        </div>
        {/* Bewusst OHNE Bühne (H5-09): Das Labor ist Werkzeug, keine
              Lektüre — sein Kopf ist der eigene Regler-Stand. Eine
              Lese-Kennzahl würde hier etwas behaupten, das man gleich selbst
              verändert. Der Schritt-Pfad bleibt: Das Labor ist der letzte
              Schritt des Wegs. */}
          <SchrittPfad href="/haushalt/labor" />
      </div>

      <Labor
        daten={data}
        produkte={produkte?.produkte ?? []} produktJahr={produktJahr}
        vergleich={vergleich ?? null}
        programm={programm ?? null}
        schulden={schulden ?? null}
      />

      <LottiErklaert
        titel="Warum das kein Sparvorschlag ist"
        text="Dieses Labor rechnet mit ganzen Bereichen und festen Annahmen. Ein echter Haushalt entsteht anders: Die Verwaltung rechnet jede Position durch, Ausschüsse beraten monatelang, und am Ende stimmt der Rat ab. Was du hier siehst, ist ein Gefühl für Größenordnungen — mehr nicht, aber auch nicht weniger."
      />

      <SchrittWeiter href="/haushalt/labor" />

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}
