import type { Metadata } from "next";
import { Suspense } from "react";
import { DetailSkeleton } from "@/components/ui";
import { Mehrheitsrechner } from "@/components/werkzeuge/mehrheitsrechner";

export const metadata: Metadata = {
  title: "Mehrheitsrechner",
  description: "Welche Fraktionen zusammen eine Mehrheit haben — im Rat und in jedem Ausschuss.",
};

export default function MehrheitenPage() {
  // Die Auswahl steht in der Adresse (useSearchParams) — ohne Suspense-Grenze
  // bricht `next build` beim Vorrendern ab.
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <Mehrheitsrechner />
    </Suspense>
  );
}
