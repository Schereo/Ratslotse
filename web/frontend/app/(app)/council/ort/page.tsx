import type { Metadata } from "next";
import { istExport, vorschauMetadata } from "@/lib/share-metadata";
import View from "./view";

type Props = { searchParams: { id?: string } };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (istExport()) return {};
  const id = searchParams?.id;
  return vorschauMetadata("ort", id, `/council/ort?id=${encodeURIComponent(id ?? "")}`);
}

export default function Page() {
  return <View />;
}
