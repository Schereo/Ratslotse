import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import View from "./view";
import { PROBLEM_ANGEBOT } from "@/lib/probleme";
import { PROBLEME_FREI } from "@/lib/probleme-frei";
import { Spinner } from "@/components/ui";

const metadataFrei: Metadata = {
  title: PROBLEM_ANGEBOT.name,
  description: "Kommunale Probleme in Oldenburg auf einer unabhängigen Ratslotse-Karte.",
};

export function generateMetadata(): Metadata {
  return PROBLEME_FREI ? metadataFrei : {};
}

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return (
    <Suspense fallback={<Spinner label="Übersicht wird geladen…" className="min-h-[420px] rounded-xl border border-border bg-card" />}>
      <View />
    </Suspense>
  );
}
