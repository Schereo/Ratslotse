"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Onboarding-Fortschritt („Erste Schritte mit Lotti") — serverseitig am Konto,
 *  damit der Kurs auf jedem Gerät denselben Stand hat und nach Abschluss
 *  überall verschwindet. Schritte gelten als erledigt, sobald die jeweilige
 *  Seite besucht wird (OnboardingTracker), nicht nur per Klick auf die Kachel. */

export type OnboardingState = { steps: string[]; celebrated: boolean };

export type StepId = "frag" | "beschluesse" | "analyse" | "karten" | "thema";

// Vor der Server-Persistenz lebte der Fortschritt im localStorage — einmalig
// hochsyncen, dann aufräumen (sonst fängt ein Zweitgerät wieder bei 0/5 an,
// obwohl dieses Gerät schon alles gesehen hat).
const LEGACY_VISITED_KEY = "ratslotse:onboarding-visited";
const LEGACY_CELEBRATED_KEY = "ratslotse:onboarding-celebrated";
let legacySynced = false;

export function useOnboarding() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["onboarding"],
    queryFn: () => api.get<OnboardingState>("/onboarding"),
    enabled: !!user,
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: (patch: { steps?: string[]; celebrated?: boolean }) =>
      api.post<OnboardingState>("/onboarding", patch),
    // Optimistisch mergen, damit der Haken sofort erscheint.
    onMutate: (patch) => {
      qc.setQueryData<OnboardingState>(["onboarding"], (cur) => ({
        steps: Array.from(new Set([...(cur?.steps ?? []), ...(patch.steps ?? [])])),
        celebrated: patch.celebrated ?? cur?.celebrated ?? false,
      }));
    },
    onSuccess: (data) => qc.setQueryData(["onboarding"], data),
  });

  // Einmalige Migration des localStorage-Bestands auf den Server.
  const { isSuccess, data } = query;
  const { mutate } = mutation;
  useEffect(() => {
    if (!isSuccess || legacySynced) return;
    legacySynced = true;
    try {
      const raw = localStorage.getItem(LEGACY_VISITED_KEY);
      const celebrated = !!localStorage.getItem(LEGACY_CELEBRATED_KEY);
      const legacy: string[] = raw ? JSON.parse(raw) : [];
      const missing = legacy.filter((s) => typeof s === "string" && !data.steps.includes(s));
      if (missing.length || (celebrated && !data.celebrated)) {
        mutate({ steps: missing, ...(celebrated ? { celebrated: true } : {}) });
      }
      localStorage.removeItem(LEGACY_VISITED_KEY);
      localStorage.removeItem(LEGACY_CELEBRATED_KEY);
    } catch { /* unlesbarer Storage — egal */ }
  }, [isSuccess, data, mutate]);

  return {
    ready: query.isSuccess,
    state: query.data ?? { steps: [], celebrated: false },
    markSteps: (steps: StepId[]) => mutation.mutate({ steps }),
    setCelebrated: () => mutation.mutate({ celebrated: true }),
  };
}

/** Seitenbesuch → Kurs-Schritt. „thema" fehlt bewusst: das erste Thema gilt
 *  erst als erledigt, wenn wirklich eins angelegt wurde (topics > 0). */
function stepForLocation(pathname: string, sp: URLSearchParams): StepId | null {
  if (pathname !== "/council") return null;
  const tab = sp.get("tab") ?? "decisions";
  if (tab === "analysis") return "analyse";
  if (tab === "themen") return "karten";
  if (tab === "decisions" || tab === "ask") return sp.get("mode") === "fragen" ? "frag" : "beschluesse";
  return null;
}

/** Global im App-Layout gemountet: meldet besuchte Kurs-Seiten als erledigt. */
export function OnboardingTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { ready, state, markSteps } = useOnboarding();

  useEffect(() => {
    if (!ready || state.celebrated) return;
    const id = stepForLocation(pathname, searchParams);
    if (id && !state.steps.includes(id)) markSteps([id]);
    // markSteps ist stabil genug (react-query mutate); state.steps als Guard reicht.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, pathname, searchParams, state.steps, state.celebrated]);

  return null;
}
