import type { Metadata } from "next";
import { istExport } from "@/lib/share-metadata";
import View from "./view";

/** Die KI-Frage als eigene Seite (Tims Go 12.08.): Suchen und Fragen sind
 *  zwei große Features — und Fragen ist das Headliner-Feature, das nicht
 *  hinter einem Modus-Umschalter der Suche wohnen soll. Alte Links auf
 *  `/council?mode=fragen` leitet die Council-Seite hierher weiter. */
export async function generateMetadata(): Promise<Metadata> {
  if (istExport()) return {};
  const title = "Fragen";
  const text =
    "Stell dem Oldenburger Stadtrat eine Frage in normaler Sprache — "
    + "Ratslotse antwortet mit Beschlüssen, Wortbeiträgen und Quellenangabe.";
  return { title: title, description: text, openGraph: { title: title, description: text } };
}

export default function Page() {
  return <View />;
}
