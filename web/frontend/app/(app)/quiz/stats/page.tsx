"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { QuizStats, QuizAreas } from "@/lib/types";
import { PageHeader, Spinner, EmptyState } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { QuizProgress } from "@/components/quiz-progress";

function StatsInner() {
  const router = useRouter();
  const { data: stats, loading } = useFetch<QuizStats>("/quiz/stats");
  const { data: areas } = useFetch<QuizAreas>("/quiz/areas");
  const themeLabels = useMemo(
    () => Object.fromEntries((areas?.themen ?? []).map((t) => [t.key, t.label ?? t.key])),
    [areas],
  );

  return (
    <div>
      <Link href="/quiz" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-4 w-4" /> Zurück zum Quiz
      </Link>
      <PageHeader title="Meine Quiz-Statistik" description="Dein Fortschritt je Gebiet — schwächste zuerst — plus Serie und Abzeichen." />

      {loading ? (
        <div className="py-10"><Spinner /></div>
      ) : stats && stats.total.answered > 0 ? (
        <div className="mt-2">
          {/* Von hier aus startet Üben/Fehler auf der Quiz-Seite (per Query). */}
          <QuizProgress
            stats={stats}
            themeLabels={themeLabels}
            onPractice={(area) => router.push(`/quiz?play=${encodeURIComponent(area)}`)}
            onReview={() => router.push("/quiz?review=1")}
          />
        </div>
      ) : (
        <EmptyState mascot="sleep" title="Noch keine gespielten Fragen"
          hint="Spiel eine Runde im Quiz — danach siehst du hier deinen Fortschritt je Gebiet." />
      )}
    </div>
  );
}

export default function QuizStatsPage() {
  return (
    <Suspense fallback={<div className="py-10"><Spinner /></div>}>
      <StatsInner />
    </Suspense>
  );
}
