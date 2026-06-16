"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Clock } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { DesktopSidebar, MobileTopbar } from "@/components/nav";
import { Card, Spinner } from "@/components/ui";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) return <Spinner />;

  const pending = user.status === "pending" && user.role !== "admin";

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <DesktopSidebar />
      <MobileTopbar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
          {pending ? <PendingNotice email={user.email} /> : children}
        </div>
      </main>
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
