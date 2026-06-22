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
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-4 py-6 pb-[calc(env(safe-area-inset-bottom)+6rem)] sm:px-6 sm:py-8 md:pb-8">
          {pending ? <PendingNotice email={user.email} /> : children}
        </div>
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
