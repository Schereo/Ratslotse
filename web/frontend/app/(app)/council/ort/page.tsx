import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: Promise<{ id?: string }> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { id } = await searchParams;
  return vorschauMetadata("ort", id, `/council/ort?id=${encodeURIComponent(id ?? "")}`);
}

export default function Page() {
  return <View />;
}
