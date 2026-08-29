import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DetailView from "./view";
import { PROBLEM_ANGEBOT } from "@/lib/probleme";

export const metadata: Metadata = {
  title: `Problem in Oldenburg — ${PROBLEM_ANGEBOT.name}`,
  description: "Moderierte Informationen und die öffentliche Zeitleiste eines kommunalen Problems in Oldenburg.",
};

// Ein Parameter erzeugt im statischen App-Export die dynamische Routen-Shell;
// konkrete IDs kommen erst zur Laufzeit aus Karte oder Deep Link. Der Web-Build
// rendert alle weiteren IDs bei Bedarf, ohne Problemdaten einzubetten.
export function generateStaticParams() {
  return [{ id: "1" }];
}

export default function Page({ params }: { params: { id: string } }) {
  const problemId = Number(params.id);
  if (!Number.isSafeInteger(problemId) || problemId < 1) notFound();

  const vorschau = process.env.VERCEL_ENV === "preview"
    || (process.env.NODE_ENV !== "production"
      && process.env.NEXT_PUBLIC_BUERGERPORTAL_VORSCHAU === "1");
  return <DetailView problemId={problemId} vorschau={vorschau} />;
}
