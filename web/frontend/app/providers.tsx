"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth";
import { Toaster } from "@/components/ui";
import { initTheme } from "@/lib/theme";
import { initAppUrlOpen } from "@/lib/app-links";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  const router = useRouter();

  useEffect(() => {
    initTheme();
  }, []);

  // Route incoming Universal/App Links (email verify/reset) into the app.
  useEffect(() => {
    void initAppUrlOpen((path) => router.push(path));
  }, [router]);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      <Toaster />
    </QueryClientProvider>
  );
}
