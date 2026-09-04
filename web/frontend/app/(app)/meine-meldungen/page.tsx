import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { MyReports } from "@/components/my-reports";
import { PageHeader } from "@/components/ui";
import { PROBLEME_FREI } from "@/lib/probleme-frei";

const enabledMetadata: Metadata = {
  title: "Meine Meldungen",
  description: "Eigene private Meldungen und Entwürfe ansehen.",
};

export function generateMetadata(): Metadata {
  return PROBLEME_FREI ? enabledMetadata : {};
}

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return (
    <div className="mx-auto w-full max-w-3xl space-y-5">
      <PageHeader
        title="Meine Meldungen"
        description="Deine Entwürfe und privat eingegangenen Meldungen."
      />
      <MyReports />
    </div>
  );
}
