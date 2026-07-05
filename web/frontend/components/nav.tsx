"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Home, Landmark, Tags, Search, Settings, LogOut, Menu, Monitor, Moon, Sun, UserCircle,
  Gavel, CalendarDays, Tag, BarChart3, Trophy,
} from "lucide-react";
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

const OVERVIEW: Item = { href: "/dashboard", label: "Übersicht", icon: Home };
const PERSONAL: Item = { href: "/topics", label: "Meine Themen", icon: Tags, tour: "nav-themen" };
const QUIZ: Item = { href: "/quiz", label: "Quiz", icon: Trophy };

// Ratsinfo sub-pages (the council page's tabs), surfaced directly in the nav.
const COUNCIL_ITEMS: (Item & { tab: string })[] = [
  { href: "/council", label: "Beschlüsse", icon: Gavel, tab: "decisions", tour: "nav-ratsinfo" },
  { href: "/council?tab=sessions", label: "Sitzungen", icon: CalendarDays, tab: "sessions" },
  { href: "/council?tab=themen", label: "Themen", icon: Tag, tab: "themen" },
  { href: "/council?tab=analysis", label: "Analyse", icon: BarChart3, tab: "analysis" },
];

// Mobile bottom tab bar (thumb-friendly) — the four most-used destinations.
const PRIMARY: Item[] = [
  { href: "/dashboard", label: "Start", icon: Home },
  { href: "/council", label: "Ratsinfo", icon: Landmark, tour: "nav-ratsinfo" },
  { href: "/topics", label: "Themen", icon: Tags, tour: "nav-themen" },
  { href: "/account", label: "Konto", icon: UserCircle },
];

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

function NavItem({ item, active, onNavigate }: { item: Item; active: boolean; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      data-tour={item.tour}
      className={cn(
        "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {active && <span className="absolute inset-y-1.5 left-0 w-1 rounded-full bg-primary" aria-hidden />}
      <Icon className="h-4 w-4" />
      {item.label}
    </Link>
  );
}

function NavLinksInner({ activeTab, onNavigate }: { activeTab: string; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const onCouncil = pathname === "/council" || pathname.startsWith("/council/");

  return (
    <nav className="flex-1 space-y-1 px-3">
      <NavItem item={OVERVIEW} active={isActive("/dashboard")} onNavigate={onNavigate} />

      <SectionHeader>Ratsinfo</SectionHeader>
      {COUNCIL_ITEMS.map((l) => (
        <NavItem key={l.href} item={l} active={onCouncil && activeTab === l.tab} onNavigate={onNavigate} />
      ))}

      <div className="pt-3" />
      <NavItem item={PERSONAL} active={isActive("/topics")} onNavigate={onNavigate} />
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
      {PRIMARY.map((l) => {
        const Icon = l.icon;
        const active = pathname === l.href || pathname.startsWith(l.href + "/");
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            data-tour={l.tour}
            className={cn(
              // active:scale-95 = spürbares Touch-Feedback beim Antippen.
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95",
              active ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <span className={cn("rounded-full px-3.5 py-1 transition-colors", active && "bg-primary/10")}>
              <Icon className={cn("h-5 w-5 transition-transform", active && "scale-110")} />
            </span>
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
