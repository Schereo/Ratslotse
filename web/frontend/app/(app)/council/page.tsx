import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { ksinr?: string; q?: string; tab?: string } };

/** Design 29a, P1 — die Sitzungs-Ansicht lebt als `?ksinr=` auf dieser Seite
 *  (lib/routes.ts sessionHref). Mit Sitzung im Link zeigt die Vorschau Gremium
 *  und Datum, sonst bleibt es beim sprechenden Seitentitel. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const ksinr = searchParams?.ksinr;
  if (ksinr) {
    return vorschauMetadata("sitzung", ksinr, `/council?tab=sessions&ksinr=${ksinr}`);
  }
  // Seit dem Split heißt die Seite „Suche" — außer der Link zeigt auf einen
  // der Geschwister-Tabs, die weiter hier wohnen.
  const TAB_TITEL: Record<string, string> = {
    sessions: "Sitzungen", themen: "Stadtkarte", analysis: "Analyse" };
  const tabTitel = TAB_TITEL[searchParams?.tab ?? ""];
  if (tabTitel) return { title: tabTitel };
  const q = searchParams?.q?.trim();
  const titel = q ? `„${q}“ — Suche` : "Suche";
  const text =
    "Beschlüsse des Oldenburger Stadtrats durchsuchen — "
    + "mit Ergebnis, Gremium, Datum und Quellenangabe.";
  // openGraph mitgeben, nicht nur title/description: Messenger lesen die
  // og:-Felder zuerst — ohne sie zeigte eine geteilte Suche wieder die
  // allgemeine Kachel, genau das, was 29a abstellen sollte.
  return { title: titel, description: text, openGraph: { title: titel, description: text } };
}

export default function Page() {
  return <View />;
}
