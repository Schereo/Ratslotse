import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DetailView from "./view";
import { PROBLEME_FREI } from "@/lib/probleme-frei";
import { parseProblemId } from "@/lib/probleme";
import { problemVorschauMetadata } from "@/lib/share-metadata";

export function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> | Metadata {
  if (!PROBLEME_FREI) return {};
  return problemVorschauMetadata(parseProblemId(params.id), `/probleme/${params.id}`);
}

export default function Page({ params }: { params: { id: string } }) {
  if (!PROBLEME_FREI) notFound();
  return <DetailView problemId={parseProblemId(params.id)} />;
}
