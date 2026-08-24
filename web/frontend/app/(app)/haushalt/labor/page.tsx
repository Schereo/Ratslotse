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
// Diese Datei holt nur die Daten: den Haushalt für die Rechnung und die
// Produktebene des jüngsten vorliegenden Jahres, aus der die Regler ihre
// Vergleichsgrößen ziehen („so viel wie …"). Die Regeln, nach denen das Labor
// rechnet und was es bewusst NICHT rechnet, stehen bei der Komponente:
// components/haushalt/labor.tsx.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, ProdukteAntwort, jahreSortiert } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Labor } from "@/components/haushalt/labor";

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
// `hebesaetze` seit 21.08.2026: Der geltende Gewerbesteuer-Satz stand im
// Labor als Konstante (439) und wurde trotzdem als Quelle zitiert — er
// kommt jetzt aus der Reihe (s. `hebesatzHeute` in labor.tsx).
const FELDER = ["jahre", "produkt_jahre", "steuern", "steuerkraft", "einwohner",
                "ergebnisrechnung", "hebesaetze"] as const;

/** Reihenfolge = Nummerierung der Beleg-Chips, deshalb nach Leserichtung:
 *  Plan (die Zahl, gegen die gerechnet wird), Steuern am Regler, Rücklage im
 *  Ergebnis, dann die beiden Dokumentquellen, zuletzt der Gegen-Block. */
const QUELLEN: QuellenSchluessel[] = [
  "plan", "steuern", "ruecklage", "jahresabschluss", "teilhaushalt",
  "steuerkraft", "hebesaetze",
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

      <div>
        <SchrittKicker href="/haushalt/labor" />
        <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">Haushalts-Labor</h1>
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

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}
