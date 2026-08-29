import type { Metadata } from "next";
import DetailView from "./view";
import { buergerportalVorschauAktiv } from "@/lib/probleme-server";
import { problemVorschauMetadata } from "@/lib/share-metadata";

function parseProblemId(raw: string): number | null {
  const value = Number(raw);
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  return problemVorschauMetadata(parseProblemId(params.id), `/probleme/${params.id}`);
}

export default function Page({ params }: { params: { id: string } }) {
  return (
    <DetailView
      problemId={parseProblemId(params.id)}
      vorschau={buergerportalVorschauAktiv()}
    />
  );
}
