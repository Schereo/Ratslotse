import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { ksinr?: string; q?: string } };

/** Design 29a, P1 — die Sitzungs-Ansicht lebt als `?ksinr=` auf dieser Seite
 *  (lib/routes.ts sessionHref). Mit Sitzung im Link zeigt die Vorschau Gremium
 *  und Datum, sonst bleibt es beim sprechenden Seitentitel. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const ksinr = searchParams?.ksinr;
  if (ksinr) {
    return vorschauMetadata("sitzung", ksinr, `/council?tab=sessions&ksinr=${ksinr}`);
  }
  const q = searchParams?.q?.trim();
  return {
    title: q ? `„${q}“ — Suchen & Fragen` : "Suchen & Fragen",
    description:
      "Beschlüsse des Oldenburger Stadtrats durchsuchen oder dem Rat eine Frage stellen — "
      + "mit Ergebnis, Gremium, Datum und Quellenangabe.",
  };
}

export default function Page() {
  return <View />;
}
