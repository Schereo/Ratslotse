import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProblemReportDisclosures, ProblemReportFlow } from "@/components/problem-report-flow";
import { PageHeader } from "@/components/ui";
import { PROBLEME_FREI } from "@/lib/probleme-frei";

export const metadata: Metadata = {
  title: "Problem melden",
  description: "Eine eigene Beobachtung privat an Ratslotse melden.",
};

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return (
    <div className="mx-auto w-full max-w-3xl space-y-5">
      <PageHeader title="Problem melden" description="Schritt für Schritt zu einer privaten Meldung." />
      <ProblemReportDisclosures />
      <ProblemReportFlow />
    </div>
  );
}
