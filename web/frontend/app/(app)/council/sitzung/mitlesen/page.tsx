import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { ksinr?: string } };

/** Mitlesen einer Sitzung (Plan Sitzungsseite, Schritt 5): Gremium und Datum
 *  wie bei der Sitzung in die Link-Vorschau. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const ksinr = searchParams?.ksinr;
  return vorschauMetadata("sitzung", ksinr, `/council/sitzung/mitlesen?ksinr=${ksinr ?? ""}`);
}

export default function Page() {
  return <View />;
}
