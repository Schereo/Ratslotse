"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Clock } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DesktopSidebar, MobileTopbar, MobileBottomNav } from "@/components/nav";
import { Card, Spinner } from "@/components/ui";
import type { User } from "@/lib/types";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();

  const pending = !!user && user.status === "pending" && user.role !== "admin";

  // Poll /me every 30 s while the account is pending so it auto-unlocks
  // as soon as an admin approves it — without requiring a page reload.
  useQuery({
    queryKey: ["me-poll"],
    queryFn: () => api.get<User>("/auth/me").then((u) => { refresh(); return u; }),
    refetchInterval: pending ? 30_000 : false,
    enabled: pending,
  });

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) return <Spinner />;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <DesktopSidebar />
      <MobileTopbar />
      <main className="flex flex-1 flex-col overflow-y-auto pb-[calc(env(safe-area-inset-bottom)+5rem)] md:pb-0">
        <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          {pending ? <PendingNotice email={user.email} /> : children}
        </div>
        <footer className="border-t border-border bg-background/85 py-3 text-center text-xs text-muted-foreground backdrop-blur md:sticky md:bottom-0">
          <a href="/impressum" className="hover:text-foreground">Impressum</a>
          {" · "}
          <a href="/datenschutz" className="hover:text-foreground">Datenschutz</a>
          {" · "}
          <a href="/changelog" className="hover:text-foreground">Changelog</a>
        </footer>
      </main>
      <MobileBottomNav />
    </div>
  );
}

function PendingNotice({ email }: { email: string }) {
  return (
    <Card className="mx-auto mt-10 max-w-md p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
        <Clock className="h-6 w-6 text-amber-600" />
      </div>
      <h1 className="mt-4 text-xl font-bold text-foreground">Konto wartet auf Freischaltung</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Dein Konto <span className="font-medium">{email}</span> wurde erstellt und muss noch von einem
        Administrator freigeschaltet werden. Du wirst informiert, sobald es so weit ist.
      </p>
    </Card>
  );
}
