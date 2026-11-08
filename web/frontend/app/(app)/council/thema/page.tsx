import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { slug?: string } };

/** Design 29a, P1 — Thema und Anzahl der Beschlüsse in die Link-Vorschau. */
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const slug = searchParams?.slug;
  return vorschauMetadata("thema", slug, `/council/thema?slug=${encodeURIComponent(slug ?? "")}`);
}

export default function Page() {
  return <View />;
}
