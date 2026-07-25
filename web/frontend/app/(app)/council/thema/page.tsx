import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { slug?: string } };

/** Design 29a, P1 — Thema und Anzahl der Beschlüsse in die Link-Vorschau.
 *  Export-Abfrage zuerst, siehe decision/page.tsx. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const slug = searchParams?.slug;
  return vorschauMetadata("thema", slug, `/council/thema?slug=${encodeURIComponent(slug ?? "")}`);
}

export default function Page() {
  return <View />;
}
