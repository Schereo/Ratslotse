"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Home, Landmark, Tags, Search, Settings, LogOut, Menu, Monitor, Moon, Sun, UserCircle,
  CalendarDays, BarChart3, Trophy, Sparkles, Map as MapIcon,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, Button } from "@/components/ui";
import { Brand, BrandMark } from "@/components/brand";
import { FeedbackButton } from "@/components/feedback";
import { cn } from "@/lib/utils";
import { cycleTheme, getTheme, type Theme } from "@/lib/theme";
import { openCommandPalette } from "@/components/command-palette";

// `tour` markiert Elemente als Anker für die Lotti-Tour (components/tour.tsx);
// Sidebar und Bottom-Nav tragen denselben Wert — die Tour nimmt das sichtbare.
type Item = { href: string; label: string; icon: typeof Home; tour?: string };

/** RL-903: Zahl ungesehener Themen-Treffer — der Orange-Zähler an
 *  „Meine Themen". Ruhig gepollt (60 s), 0 blendet aus. */
function useUnreadTopicHits(): number {
  const { data } = useQuery({
    queryKey: ["topics-unread"],
    queryFn: () => api.get<{ total: number }>("/topics/unread-count"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  return data?.total ?? 0;
}

function UnreadBadge({ n }: { n: number }) {
  if (n <= 0) return null;
  return (
    <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-signal px-1.5 text-[11px] font-bold tabular-nums text-signal-foreground">
      {n > 99 ? "99+" : n}
    </span>
  );
}

// Sidebar 2a (RL-201): fünf Hauptziele flach, danach Abschnitt PERSÖNLICH.
// „Stadtkarte" = der bisherige Themen-Tab (Unterscheidung von „Meine Themen").
const MAIN_ITEMS: (Item & { tab?: string })[] = [
  { href: "/dashboard", label: "Heute", icon: Home },
  { href: "/council", label: "Suchen & Fragen", icon: Search, tab: "decisions", tour: "nav-ratsinfo" },
  { href: "/council?tab=sessions", label: "Sitzungen", icon: CalendarDays, tab: "sessions" },
  { href: "/council?tab=themen", label: "Stadtkarte", icon: MapIcon, tab: "themen" },
  { href: "/council?tab=analysis", label: "Analyse", icon: BarChart3, tab: "analysis" },
];
const PERSONAL: Item = { href: "/topics", label: "Meine Themen", icon: Tags, tour: "nav-themen" };
const QUIZ: Item = { href: "/quiz", label: "Quiz", icon: Trophy };

// Mobile Bottom-Nav (RL-201): 4 Ziele + zentrale „Fragen"-Taste in Signal-
// Orange (angehoben, 54 px) — Route direkt in den KI-Frage-Modus.
const PRIMARY_LEFT: Item[] = [
  { href: "/dashboard", label: "Heute", icon: Home },
  { href: "/council", label: "Ratsinfo", icon: Landmark, tour: "nav-ratsinfo" },
];
const PRIMARY_RIGHT: Item[] = [
  { href: "/topics", label: "Themen", icon: Tags, tour: "nav-themen" },
  { href: "/account", label: "Konto", icon: UserCircle },
];
const FRAGEN_HREF = "/council?tab=decisions&mode=fragen";

const THEME_META: Record<Theme, { icon: typeof Sun; label: string }> = {
  light: { icon: Sun, label: "Hell" },
  dark: { icon: Moon, label: "Dunkel" },
  system: { icon: Monitor, label: "System" },
};

/** Dreistufig hell → dunkel → System (folgt dem OS), statt der alten Zweier-Sackgasse. */
function ThemeToggle({ className }: { className?: string }) {
  // Erst nach dem Mount aus localStorage lesen (SSR-Hydration).
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    setTheme(getTheme());
  }, []);
  const { icon: Icon, label } = THEME_META[theme];
  return (
    <button
      onClick={() => setTheme(cycleTheme())}
      title={`Design: ${label} — klicken zum Wechseln`}
      aria-label={`Design wechseln (aktuell: ${label})`}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className,
      )}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return <p className="px-3 pb-1 pt-5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">{children}</p>;
}

function NavItem({ item, active, badge = 0, onNavigate }: { item: Item; active: boolean; badge?: number; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      data-tour={item.tour}
      aria-current={active ? "page" : undefined}
      className={cn(
        // Aktiv = Pill (RL-102): Fläche + Farbe, kein Akzent-Balken mehr.
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4" />
      {item.label}
      <UnreadBadge n={badge} />
    </Link>
  );
}

function NavLinksInner({ activeTab, onNavigate }: { activeTab: string; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const onCouncil = pathname === "/council" || pathname.startsWith("/council/");
  const unread = useUnreadTopicHits();

  return (
    <nav className="flex-1 space-y-1 px-3">
      {MAIN_ITEMS.map((l) => (
        <NavItem
          key={l.href}
          item={l}
          active={l.tab ? onCouncil && activeTab === l.tab : isActive(l.href)}
          onNavigate={onNavigate}
        />
      ))}

      <SectionHeader>Persönlich</SectionHeader>
      <NavItem item={PERSONAL} active={isActive("/topics")} badge={unread} onNavigate={onNavigate} />
      <NavItem item={QUIZ} active={isActive("/quiz")} onNavigate={onNavigate} />
      {user?.role === "admin" && (
        <NavItem item={{ href: "/admin", label: "Admin", icon: Settings }} active={isActive("/admin")} onNavigate={onNavigate} />
      )}
    </nav>
  );
}

function NavLinksWithParams({ onNavigate }: { onNavigate?: () => void }) {
  const tab = useSearchParams().get("tab") || "decisions";
  return <NavLinksInner activeTab={tab} onNavigate={onNavigate} />;
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  // useSearchParams must sit under a Suspense boundary; the fallback renders the
  // same nav with the default (decisions) tab so there is no empty flash.
  return (
    <Suspense fallback={<NavLinksInner activeTab="decisions" onNavigate={onNavigate} />}>
      <NavLinksWithParams onNavigate={onNavigate} />
    </Suspense>
  );
}

function UserFooter({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };
  const accountActive = pathname === "/account";
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center justify-between gap-2 pb-2">
        <Link
          href="/account"
          onClick={onNavigate}
          title="Mein Konto"
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors",
            accountActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          <UserCircle className="h-4 w-4 shrink-0" />
          <span className="truncate">{user?.email}</span>
        </Link>
        <ThemeToggle />
      </div>
      <FeedbackButton onNavigate={onNavigate} />
      <button
        onClick={onLogout}
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <LogOut className="h-4 w-4" /> Abmelden
      </button>
    </div>
  );
}

export function DesktopSidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card md:flex md:sticky md:top-0 md:h-screen md:self-start md:overflow-y-auto">
      <div className="px-5 pb-2 pt-5">
        <Brand />
      </div>
      {/* Suche als Ghost-Zeile im Nav-Stil statt Input-Kasten — wirkt sonst
          gedrungen zwischen Logo und Navigation. */}
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={openCommandPalette}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">Suchen</span>
          <kbd className="rounded border border-border/70 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground/80">⌘K</kbd>
        </button>
      </div>
      <NavLinks />
      <UserFooter />
    </aside>
  );
}

export function MobileTopbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-card/95 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Menü öffnen" className="h-11 w-11">
            <Menu className="h-6 w-6" />
          </Button>
        </SheetTrigger>
        <SheetContent>
          <SheetTitle>Navigation</SheetTitle>
          <div className="px-5 py-5">
            <Brand />
          </div>
          <NavLinks onNavigate={() => setOpen(false)} />
          <UserFooter onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="flex flex-1 items-center gap-2">
        <BrandMark className="h-7 w-7" />
        <span className="font-display text-base font-bold tracking-tight text-foreground">Ratslotse</span>
      </div>
      <button
        type="button"
        onClick={openCommandPalette}
        aria-label="Suchen und Befehle öffnen"
        className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Search className="h-4 w-4" />
      </button>
      <ThemeToggle />
    </header>
  );
}

export function MobileBottomNav() {
  const pathname = usePathname();
  return (
    <nav
      // Echtes Glas statt nur Blur (iOS-Look): halbtransparente Fläche +
      // backdrop-saturate, eine 1-px-Lichtkante innen (simuliert die
      // Kanten-Brechung) und ein weicher Schatten nach oben für Tiefe.
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border/50 bg-card/70 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl backdrop-saturate-150 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.45),0_-10px_28px_-14px_rgba(2,32,71,0.22)] dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08),0_-10px_28px_-14px_rgba(0,0,0,0.5)] md:hidden"
      aria-label="Hauptnavigation"
    >
      {PRIMARY_LEFT.map((l) => (
        <BottomNavItem key={l.href} item={l} active={pathname === l.href || pathname.startsWith(l.href + "/")} />
      ))}
      {/* Zentrale „Fragen"-Taste (RL-201): DIE Signal-Handlung der Bottom-Nav —
          angehoben über der Leiste, führt direkt in den KI-Frage-Modus. */}
      <Link
        href={FRAGEN_HREF}
        aria-label="Frag den Rat — KI-Frage stellen"
        className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium text-muted-foreground transition-[color,transform] duration-150 active:scale-95"
      >
        <span className="-mt-[22px] flex h-[54px] w-[54px] items-center justify-center rounded-full bg-signal text-signal-foreground shadow-[0_8px_22px_-10px_hsl(19_92%_45%/0.6)] ring-4 ring-background">
          <Sparkles className="h-6 w-6" />
        </span>
        Fragen
      </Link>
      {PRIMARY_RIGHT.map((l) => (
        <BottomNavItem key={l.href} item={l} active={pathname === l.href || pathname.startsWith(l.href + "/")} />
      ))}
    </nav>
  );
}

function BottomNavItem({ item, active }: { item: Item; active: boolean }) {
  const Icon = item.icon;
  // Oranger Punkt am Themen-Tab bei ungesehenen Treffern (RL-903).
  const unread = useUnreadTopicHits();
  const showDot = item.href === "/topics" && unread > 0;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      data-tour={item.tour}
      className={cn(
        // active:scale-95 = spürbares Touch-Feedback beim Antippen.
        "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95",
        active ? "text-primary" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span className={cn("relative rounded-full px-3.5 py-1 transition-colors", active && "bg-primary/10")}>
        <Icon className={cn("h-5 w-5 transition-transform", active && "scale-110")} />
        {showDot && <span className="absolute right-1.5 top-0 h-2 w-2 rounded-full bg-signal ring-2 ring-card" aria-hidden />}
      </span>
      {item.label}
    </Link>
  );
}
