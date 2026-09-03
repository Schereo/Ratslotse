"use client";

import Link from "next/link";
import { PublicProblemDetail } from "@/components/public-problem-detail";
import { ApiError } from "@/lib/api";
import { usePublicProblem } from "@/lib/use-public-problem";
import { Button, EmptyState, ErrorState, Spinner } from "@/components/ui";

export default function DetailView({ problemId }: { problemId: number | null }) {
  const query = usePublicProblem(problemId);
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
