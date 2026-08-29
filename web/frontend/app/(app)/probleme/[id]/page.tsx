import type { Metadata } from "next";
import DetailView from "./view";
import { VORSCHAU_PROBLEME } from "@/lib/probleme";
import { buergerportalVorschauAktiv } from "@/lib/probleme-server";
import { problemVorschauMetadata } from "@/lib/share-metadata";

function parseProblemId(raw: string): number | null {
  if (!/^[1-9]\d*$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : null;
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const problemId = parseProblemId(params.id);
  const preview = buergerportalVorschauAktiv()
    ? VORSCHAU_PROBLEME.find((problem) => problem.id === problemId) ?? null
    : null;
  return problemVorschauMetadata(problemId, `/probleme/${params.id}`, preview);
}

export default function Page({ params }: { params: { id: string } }) {
  return (
    <DetailView
      problemId={parseProblemId(params.id)}
      vorschau={buergerportalVorschauAktiv()}
    />
  );
}
