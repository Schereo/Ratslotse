import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { id?: string } };

/** Design 29a, P1 — schlanke Server-Hülle: schreibt Titel, Ergebnis, Gremium
 *  und Datum in die Link-Vorschau. Die Ansicht selbst bleibt unverändert. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const id = searchParams?.id;
  return vorschauMetadata("decision", id, `/council/decision?id=${id ?? ""}`);
}

export default function Page() {
  return <View />;
}
