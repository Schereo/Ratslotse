import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: Promise<{ ksinr?: string; top?: string }> };

/** Ein Tagesordnungspunkt auf seiner eigenen Seite (Plan Sitzungsseite,
 *  Schritt 4): Nummer und Titel in die Link-Vorschau. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { ksinr, top } = await searchParams;
  const key = ksinr && top ? `${ksinr}|${top}` : undefined;
  return vorschauMetadata("punkt", key,
    `/council/punkt?ksinr=${ksinr ?? ""}&top=${encodeURIComponent(top ?? "")}`);
}

export default function Page() {
  return <View />;
}
