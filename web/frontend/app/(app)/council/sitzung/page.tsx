import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { ksinr?: string } };

/** Die geteilte Sitzung: Gremium und Datum in die Link-Vorschau (die Vorschau
 *  gab es für Sitzungen schon, sie hing nur an der Listen-Adresse).
 *
 *  Die Export-Abfrage steht vor jedem Zugriff auf `searchParams` — schon das
 *  Lesen macht die Seite dynamisch, und `output: export` bricht dann ab
 *  (s. decision/page.tsx). */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const ksinr = searchParams?.ksinr;
  return vorschauMetadata("sitzung", ksinr, `/council/sitzung?ksinr=${ksinr ?? ""}`);
}

export default function Page() {
  return <View />;
}
