import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { ksinr?: string } };

/** Die geteilte Sitzung: Gremium und Datum in die Link-Vorschau (die Vorschau
 *  gab es für Sitzungen schon, sie hing nur an der Listen-Adresse). */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const ksinr = searchParams?.ksinr;
  return vorschauMetadata("sitzung", ksinr, `/council/sitzung?ksinr=${ksinr ?? ""}`);
}

export default function Page() {
  return <View />;
}
