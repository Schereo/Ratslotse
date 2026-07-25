import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { id?: string } };

/** Design 29a, P1 — schlanke Server-Hülle: schreibt Titel, Ergebnis, Gremium
 *  und Datum in die Link-Vorschau. Die Ansicht selbst bleibt unverändert.
 *
 *  Die Export-Abfrage steht bewusst VOR jedem Zugriff auf `searchParams`:
 *  Schon das Lesen macht die Seite dynamisch, und `output: export` bricht dann
 *  mit „couldn't be rendered statically" ab. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const id = searchParams?.id;
  return vorschauMetadata("decision", id, `/council/decision?id=${id ?? ""}`);
}

export default function Page() {
  return <View />;
}
