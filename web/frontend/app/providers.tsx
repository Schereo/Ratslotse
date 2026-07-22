"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { AuthProvider } from "@/lib/auth";
import { AppIntro } from "@/components/app-intro";
import { OfflinePill } from "@/components/offline-pill";
import { PullToRefresh } from "@/components/pull-to-refresh";
import { Toaster } from "@/components/ui";
import { initTheme } from "@/lib/theme";
import { initAppUrlOpen } from "@/lib/app-links";
import { isNativeApp } from "@/lib/platform";

// In der App überlebt der Query-Cache den Neustart (RL-1103): beim Start im
// Zug/Funkloch zeigt Ratslotse die zuletzt geladenen Daten statt Skeletons.
// gcTime muss die maxAge überdauern, sonst räumt der GC vor dem Persist auf.
const PERSIST_MAX_AGE = 24 * 60 * 60 * 1000;

export function Providers({ children }: { children: React.ReactNode }) {
  const [native] = useState(() => isNativeApp());
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            ...(native ? { gcTime: PERSIST_MAX_AGE } : {}),
          },
        },
      }),
  );

  const router = useRouter();

  useEffect(() => {
    initTheme();
  }, []);

  // In der nativen App ist Pinch-/Auto-Zoom aus — App-UIs zoomen nicht, und
  // ein versehentlicher Zoom blieb sonst dauerhaft hängen. Nur die WKWebView
  // respektiert maximum-scale; der iOS-System-Zoom (Bedienungshilfen)
  // funktioniert weiterhin. Im Web bleibt Pinch-Zoom unangetastet.
  useEffect(() => {
    if (!native) return;
    document
      .querySelector('meta[name="viewport"]')
      ?.setAttribute(
        "content",
        "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover",
      );
  }, [native]);

  // Route incoming Universal/App Links (email verify/reset) into the app.
  useEffect(() => {
    void initAppUrlOpen((path) => router.push(path));
  }, [router]);

  const inner = (
    <>
      <AuthProvider>{children}</AuthProvider>
      {/* RL-1103/1104: Offline-Hinweis (web + app), First-Run-Intro und
          Pull-to-Refresh (beide nur App). */}
      <OfflinePill />
      <AppIntro />
      <PullToRefresh />
      <Toaster />
    </>
  );

  if (native) {
    const persister = createSyncStoragePersister({
      storage: window.localStorage,
      key: "ratslotse.query-cache",
    });
    return (
      <PersistQueryClientProvider
        client={queryClient}
        // buster v2: verwirft bestehende Caches, in denen ["subscriptions"]
        // fälschlich als rohes Objekt statt als Array lag (Crash auf /topics).
        persistOptions={{ persister, maxAge: PERSIST_MAX_AGE, buster: "v2" }}
      >
        {inner}
      </PersistQueryClientProvider>
    );
  }

  return <QueryClientProvider client={queryClient}>{inner}</QueryClientProvider>;
}
