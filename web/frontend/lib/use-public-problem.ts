"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";

/** Gemeinsame Client-Abfrage für Web-Route und statischen Query-Adapter. */
export function usePublicProblem(problemId: number | null) {
  return useQuery({
    queryKey: ["public-problem", problemId],
    queryFn: () => api.get<ApiAntwort<"/probleme/{problem_id}">>(`/probleme/${problemId}`),
    enabled: problemId !== null,
    staleTime: 60_000,
    retry: false,
  });
}
