"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PublicProblemDetail } from "@/components/public-problem-detail";
import { ApiError, api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { Button, EmptyState, ErrorState, Spinner } from "@/components/ui";

export default function DetailView({ problemId }: { problemId: number | null }) {
  const query = useQuery({
    queryKey: ["public-problem", problemId],
    queryFn: () => api.get<ApiAntwort<"/probleme/{problem_id}">>(`/probleme/${problemId}`),
    enabled: problemId !== null,
    staleTime: 60_000,
    retry: false,
  });
  const notFound = problemId === null || query.error instanceof ApiError && query.error.status === 404;

  if (notFound) {
    return (
      <EmptyState
        mascot="search"
        title="Problem nicht gefunden"
        headingLevel={1}
        hint="Es ist nicht öffentlich oder der Link ist nicht mehr gültig."
        action={<Button asChild variant="secondary"><Link href="/probleme">Zur Übersicht</Link></Button>}
      />
    );
  }
  if (query.isLoading) return <Spinner label="Problem wird geladen…" className="min-h-[24rem]" />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="Problem konnte nicht geladen werden"
        hint="Die öffentliche Detailseite ist gerade nicht erreichbar."
        onRetry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  }

  return <PublicProblemDetail problem={query.data} />;
}
