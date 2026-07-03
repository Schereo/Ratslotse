"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, MailWarning } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { initPush } from "@/lib/push";
import { DesktopSidebar, MobileTopbar, MobileBottomNav } from "@/components/nav";
import { SlashSearchShortcut } from "@/components/keyboard-shortcuts";
import { GuidedTour } from "@/components/tour";
import { CommandPalette } from "@/components/command-palette";
import { FeedbackDialog } from "@/components/feedback";
import { BackToTop } from "@/components/back-to-top";
import { PeekingChick } from "@/components/peeking-chick";
import { Button, Card, Spinner, toast } from "@/components/ui";
import type { User } from "@/lib/types";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();

  const needsVerify = !!user && !user.email_verified && user.role !== "admin";
  const pending = !!user && user.status === "pending" && user.role !== "admin";
  const gated = needsVerify || pending;

  // Poll /me every 30 s while the account is gated (email unverified or awaiting
  // approval) so it auto-unlocks without a page reload.
  useQuery({
    queryKey: ["me-poll"],
    queryFn: () => api.get<User>("/auth/me").then((u) => { refresh(); return u; }),
    refetchInterval: gated ? 30_000 : false,
    enabled: gated,
  });

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  // Wire native push once a user is present: device token → backend, tap → route.
  // No-op on the web and when notifications aren't permitted.
  useEffect(() => {
    if (user) void initPush((path) => router.push(path));
  }, [user, router]);

  if (loading || !user) return <Spinner />;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Screenreader/Tastatur: direkt zum Inhalt, an Sidebar und Topbar vorbei. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Zum Inhalt springen
      </a>
      <SlashSearchShortcut />
      <GuidedTour />
      <CommandPalette />
      <FeedbackDialog />
      <BackToTop />
      <PeekingChick />
      <DesktopSidebar />
      <MobileTopbar />
      <main id="main" tabIndex={-1} className="flex flex-1 flex-col overflow-y-auto outline-none pb-[calc(env(safe-area-inset-bottom)+5rem)] md:pb-0">
        <div className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          {needsVerify ? <VerifyNotice email={user.email} /> : pending ? <PendingNotice email={user.email} /> : children}
        </div>
        <footer className="border-t border-border bg-background/85 py-3 text-center text-xs text-muted-foreground backdrop-blur md:sticky md:bottom-0">
          <a href="/impressum" className="hover:text-foreground">Impressum</a>
          {" · "}
          <a href="/datenschutz" className="hover:text-foreground">Datenschutz</a>
          {" · "}
          <a href="/changelog" className="hover:text-foreground">Changelog</a>
          {" · "}
          <a href="/docs" className="hover:text-foreground">Technik-Doku</a>
        </footer>
      </main>
      <MobileBottomNav />
    </div>
  );
}

function VerifyNotice({ email }: { email: string }) {
  const [busy, setBusy] = useState(false);

  const resend = async () => {
    setBusy(true);
    try {
      await api.post("/auth/resend-verification");
      toast.success("Bestätigungs-E-Mail wurde erneut gesendet.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="mx-auto mt-10 max-w-md p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
        <MailWarning className="h-6 w-6 text-blue-600" />
      </div>
      <h1 className="mt-4 text-xl font-bold text-foreground">Bitte bestätige deine E-Mail</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Wir haben einen Bestätigungslink an <span className="font-medium">{email}</span> geschickt.
        Klick den Link, um fortzufahren. Schau auch im Spam-Ordner nach.
      </p>
      <Button onClick={resend} disabled={busy} variant="secondary" className="mt-5">
        {busy ? "Senden…" : "E-Mail erneut senden"}
      </Button>
    </Card>
  );
}

/** Nach der Auto-Aktivierung bedeutet `pending` bei verifizierter Adresse:
    von einem Admin deaktiviert (Moderation). */
function PendingNotice({ email }: { email: string }) {
  return (
    <Card className="mx-auto mt-10 max-w-md p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
        <Clock className="h-6 w-6 text-amber-600" />
      </div>
      <h1 className="mt-4 text-xl font-bold text-foreground">Konto ist deaktiviert</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Dein Konto <span className="font-medium">{email}</span> ist derzeit deaktiviert.
        Wenn du meinst, dass das ein Irrtum ist, melde dich gern per E-Mail — die
        Kontaktadresse steht im Impressum.
      </p>
    </Card>
  );
}
