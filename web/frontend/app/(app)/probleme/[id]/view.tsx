"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import type { PublicProblem } from "@/lib/types";
import { VORSCHAU_PROBLEME } from "@/lib/probleme";
import { PublicProblemDetail } from "@/components/public-problem-detail";
import { Button, EmptyState, ErrorState, Spinner } from "@/components/ui";

export default function DetailView({ problemId, vorschau }: { problemId: number | null; vorschau: boolean }) {
  const query = useQuery({
    queryKey: ["public-problem", problemId],
    queryFn: () => api.get<PublicProblem>(`/probleme/${problemId}`),
    enabled: !vorschau && problemId !== null,
    staleTime: 60_000,
  });
  const problem = vorschau
    ? VORSCHAU_PROBLEME.find((entry) => entry.id === problemId) ?? null
    : query.data ?? null;
  const notFound = problemId === null || (vorschau
    ? problem === null
    : query.error instanceof ApiError && query.error.status === 404);

  if (notFound) {
    return (
      <EmptyState
        title="Problem nicht gefunden"
        headingLevel={1}
        hint="Es wurde nicht veröffentlicht, archiviert oder der Link ist nicht mehr gültig."
        mascot="search"
        action={<Button asChild variant="secondary"><Link href="/probleme">Zur Problemkarte</Link></Button>}
      />
    );
  }
  if (!vorschau && query.isLoading) return <Spinner label="Problem wird geladen…" className="min-h-[24rem]" />;
  if (!problem) {
    return (
      <ErrorState
        title="Problem konnte nicht geladen werden"
        hint="Die öffentliche Detailseite ist gerade nicht erreichbar."
        onRetry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  }

  return <PublicProblemDetail problem={problem} vorschau={vorschau} backHref="/probleme" />;
}
