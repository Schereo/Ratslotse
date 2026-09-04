import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/ui";
import { ReportModeration } from "@/components/report-moderation";
import { PROBLEME_FREI } from "@/lib/probleme-frei";

const metadataFrei: Metadata = {
  title: "Meldungen prüfen",
  description: "Private Bürgerportal-Meldungen menschlich prüfen.",
};

export function generateMetadata(): Metadata {
  return PROBLEME_FREI ? metadataFrei : {};
}

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return (
    <div className="mx-auto w-full max-w-3xl space-y-5">
      <PageHeader
        title="Meldungen prüfen"
        description="Private Meldungen in Eingangsreihenfolge prüfen. Keine Entscheidung veröffentlicht automatisch etwas."
      />
      <ReportModeration />
    </div>
  );
}
