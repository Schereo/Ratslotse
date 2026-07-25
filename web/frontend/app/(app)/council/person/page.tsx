import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { slug?: string } };

/** Design 29a, P1 — Name und Fraktion in die Link-Vorschau.
 *  Export-Abfrage zuerst, siehe decision/page.tsx. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const slug = searchParams?.slug;
  return vorschauMetadata("person", slug, `/council/person?slug=${encodeURIComponent(slug ?? "")}`);
}

export default function Page() {
  return <View />;
}
