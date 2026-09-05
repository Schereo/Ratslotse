import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/ui";
import { ReportProjections } from "@/components/report-projections";
import { PROBLEME_FREI } from "@/lib/probleme-frei";

const metadataFrei: Metadata = {
  title: "Öffentlich zuordnen",
  description: "Freigegebene private Meldungen bewusst öffentlich zuordnen.",
};

export function generateMetadata(): Metadata {
  return PROBLEME_FREI ? metadataFrei : {};
}

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return (
    <div className="mx-auto w-full max-w-3xl space-y-5">
      <PageHeader
        title="Öffentlich zuordnen"
        description="Erst diese getrennte menschliche Bestätigung verändert die öffentliche Problemübersicht."
      />
      <ReportProjections />
    </div>
  );
}
