"use client";

import { Suspense, useEffect, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { Clock, MailWarning } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { initPush } from "@/lib/push";
import { DesktopSidebar, MobileTopbar, MobileBottomNav, TABLEISTE_HOEHE } from "@/components/nav";
import { SlashSearchShortcut } from "@/components/keyboard-shortcuts";
import { GuidedTour } from "@/components/tour";
import { CommandPalette } from "@/components/command-palette";
import { FeedbackDialog } from "@/components/feedback";
import { OnboardingTracker } from "@/components/onboarding";
import { BadgeCelebrator } from "@/components/badges";
import { BackToTop } from "@/components/back-to-top";
import { ScrollMemory } from "@/components/scroll-memory";
import { PeekingChick } from "@/components/peeking-chick";
import { PublicShell } from "@/components/public-shell";
import { Button, Card, CardListSkeleton, Skeleton, toast } from "@/components/ui";
import { istOeffentlich, mitRuecksprung } from "@/lib/public-routes";
import type { User } from "@/lib/types";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  // Geteilte Detailseiten lassen sich ohne Konto lesen (s. lib/public-routes.ts).
  const oeffentlich = istOeffentlich(pathname);

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
    if (loading || user || oeffentlich) return;
    // Das Ziel mitnehmen, statt es zu verlieren: Wer aus einem Lesezeichen oder
    // einer angetippten Mitteilung auf „Meine Themen" kommt und sich anmelden
    // muss, landete danach stumpf auf dem Dashboard.
    const ziel = window.location.pathname + window.location.search;
    router.replace(ziel === "/dashboard" ? "/login" : mitRuecksprung("/login", ziel));
  }, [user, loading, router, oeffentlich]);

  // Wire native push once a user is present: device token → backend, tap → route.
  // No-op on the web and when notifications aren't permitted.
  useEffect(() => {
    if (user) void initPush((path) => router.push(path));
  }, [user, router]);

  // Ganzseitig laden: mittig statt oben. Ohne das klebte der Spinner am
  // oberen Rand — in der App halb hinter der Dynamic Island.
  // Solange das Konto gesperrt ist, gibt es die App-Hülle noch nicht: Topbar,
  // Suche und Bottom-Nav führen alle ins Leere, wenn man nichts darf. Der
  // Hinweis steht deshalb für sich, wie die Auth-Seiten davor.
  if (gated) {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-waves px-4 py-10">
        <div className="w-full max-w-sm">
          {needsVerify ? <VerifyNotice email={user!.email} /> : <PendingNotice email={user!.email} />}
        </div>
      </div>
    );
  }

  // Ohne Konto auf einer geteilten Detailseite: lesen lassen, statt zur
  // Anmeldung zu schicken. Die App-Hülle passt hier nicht — ihre Navigation
  // führt ausschließlich zu Seiten, die ein Konto verlangen.
  if (!loading && !user && oeffentlich) return <PublicShell>{children}</PublicShell>;

  // Design 29a (P3): Der erste Eindruck war ein Spinner auf weißem Grund — die
  // Marke verschwand ausgerechnet in der Sekunde, die zählt, und jeder App-Start
  // begann mit etwas, das aussah wie eine hängende Seite. Jetzt steht die Hülle
  // sofort (Logo, Navigations-Silhouette), nur der Inhalt füllt sich nach.
  if (loading || !user) return <ShellSkeleton />;

  return (
    <div className="flex min-h-screen flex-col desk:flex-row">
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
      {/* useSearchParams braucht eine Suspense-Grenze (CSR-Bailout beim Prerender). */}
      <Suspense fallback={null}>
        <OnboardingTracker />
      </Suspense>
      {/* RL-U12: feiert neu verdiente Lotsen-Abzeichen — auf jeder Seite. */}
      <BadgeCelebrator />
      {/* BackToTop liest useSearchParams (im Ratsgespräch ausgeblendet). */}
      <Suspense fallback={null}>
        <BackToTop />
      </Suspense>
      {/* Scroll-Position je Seite behalten (Tims iOS-Befund 12.08.). */}
      <Suspense fallback={null}>
        <ScrollMemory />
      </Suspense>
      <PeekingChick />
      <DesktopSidebar />
      <MobileTopbar />
      {/* Design 9a: Freiraum = Tab-Bar-Höhe + Luft (der angehobene FAB ist
          weg, 5,5rem hinterließen nur totes Ende unter jeder Seite).
          KEIN overflow-y-auto: Der Root ist min-h-screen, gescrollt wird immer
          am Window — ein overflow-Container, der nie selbst scrollt, macht
          nur jede sticky-Leiste in main wirkungslos (Composer 2①, RG-10-
          Sprungmarken, Analyse-/Quiz-Leisten klebten deshalb nie). */}
      {/* min-w-0: `main` liegt als Flex-Kind NEBEN der Seitenleiste. Ohne das
          gilt `min-width:auto`, und die Mindestbreite des längsten
          unumbrechbaren Inhalts (ein Beschluss-Titel in „Zuletzt angesehen")
          schiebt die ganze Seite auf. Auf dem iPad hochkant lief das Layout
          dadurch 1228 px breit bei 834 px Fenster — die Karten rechts waren
          abgeschnitten, die Seite ließ sich seitlich wegschieben. */}
      {/* Der Platzhalter unter dem Inhalt rechnet mit derselben Leistenhöhe wie
          die Leiste selbst (TABLEISTE_HOEHE aus components/nav.tsx) plus etwas
          Luft — vorher stand hier eine eigene Zahl, und genau solche zweiten
          Zahlen sind am 16.08. auseinandergelaufen. Als Variable, nicht als
          Inline-Höhe: `desk:pb-0` muss weiter gewinnen, wo es keine Leiste gibt. */}
      <main id="main" tabIndex={-1} style={{ "--rl-unten": TABLEISTE_HOEHE } as React.CSSProperties}
        className="flex min-w-0 flex-1 flex-col outline-none pb-[calc(var(--rl-unten)+0.75rem)] desk:pb-0">
        {/* Design 11a: Inhalt läuft breiter (~1280 px statt 1024) — die Karten
            atmen wie im Mock; Text-Detailseiten begrenzen sich weiter selbst. */}
        <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          {children}
        </div>
        {/* Design 6a③: Der sticky Seiten-Footer entfällt — die Pflicht-Links
            sitzen jetzt im Sidebar-Fuß (Desktop) bzw. Burger-Menü (mobil),
            beides über den UserFooter in components/nav.tsx. */}
      </main>
      <MobileBottomNav />
    </div>
  );
}

/** Die App-Hülle, solange die Anmeldung geprüft wird (Design 29a, P3).
 *
 *  Bewusst kein Nachbau der echten Navigation: Die Ziele stehen erst fest, wenn
 *  klar ist, wer da ist (Admin-Punkt, Zähler). Was hier steht, ist die *Form* —
 *  Logo, Seitenspalte, Kopf- und Fußleiste in ihren Maßen — damit nichts
 *  springt, wenn der Inhalt eintrifft, und die Marke im ersten Moment da ist.
 */
function ShellSkeleton() {
  return (
    <div className="flex min-h-screen flex-col desk:flex-row" aria-busy="true" aria-live="polite">
      <span className="sr-only">Ratslotse wird geladen …</span>

      {/* Seitenspalte (Desktop) */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card desk:flex desk:sticky desk:top-0 desk:h-screen">
        <div className="flex items-center gap-2.5 px-4 py-4">
          <Image src="/icon-192.png" alt="" width={32} height={32} className="h-8 w-8 rounded-lg" priority />
          <span className="font-display text-lg font-bold text-foreground">Ratslotse</span>
        </div>
        <div className="space-y-1.5 px-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full rounded-md" />
          ))}
          <Skeleton className="!mt-6 h-2.5 w-20" />
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full rounded-md" />
          ))}
        </div>
      </aside>

      {/* Kopfleiste (Mobil) — dieselben Maße wie die echte, damit nichts springt. */}
      <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-card/95 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur desk:hidden">
        <Image src="/icon-192.png" alt="" width={28} height={28} className="h-7 w-7 rounded-lg" priority />
        <span className="flex-1 font-display text-base font-bold text-foreground">Ratslotse</span>
        <Skeleton className="h-9 w-9 rounded-md" />
      </header>

      <main style={{ "--rl-unten": TABLEISTE_HOEHE } as React.CSSProperties}
        className="flex min-w-0 flex-1 flex-col pb-[calc(var(--rl-unten)+0.75rem)] desk:pb-0">
        <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <Skeleton className="h-7 w-52" />
          <Skeleton className="mt-2 h-3.5 w-72" />
          <div className="mt-6">
            <CardListSkeleton rows={3} />
          </div>
        </div>
      </main>

      {/* Fußleiste (Mobil) */}
      {/* Gleiche Aufteilung der Safe Area wie in der echten Tab-Leiste —
          sonst springt der Inhalt beim Übergang vom Skelett zur Navigation. */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/90 pb-[calc(env(safe-area-inset-bottom)/2)] pt-[calc(env(safe-area-inset-bottom)/2)] backdrop-blur desk:hidden">
        <div className="flex h-[4.25rem] items-center justify-around px-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-12 rounded-lg" />
          ))}
        </div>
      </div>
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
