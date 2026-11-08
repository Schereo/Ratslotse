import type { Metadata } from "next";
import { vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { id?: string } };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const id = searchParams?.id;
  return vorschauMetadata("ort", id, `/council/ort?id=${encodeURIComponent(id ?? "")}`);
}

export default function Page() {
  return <View />;
}
