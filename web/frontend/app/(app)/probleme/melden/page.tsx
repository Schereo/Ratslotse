import type { Metadata } from "next";
import { ProblemReportFlow } from "@/components/problem-report-flow";

export const metadata: Metadata = {
  title: "Problem melden",
  description: "Eine kommunale Beobachtung privat an Ratslotse melden.",
};

export default function ReportProblemPage() {
  return <ProblemReportFlow />;
}
