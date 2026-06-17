"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Home, Newspaper, Landmark, Tags, Link2, Settings, LogOut, Menu, Moon, Sun, UserCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, Button } from "@/components/ui";
import { Brand, BrandMark } from "@/components/brand";
import { cn } from "@/lib/utils";
import { toggleTheme } from "@/lib/theme";

const LINKS = [
  { href: "/dashboard", label: "Übersicht", icon: Home },
  { href: "/nwz", label: "Artikelsuche", icon: Newspaper },
  { href: "/council", label: "Ratsinfo", icon: Landmark },
  { href: "/topics", label: "Meine Themen", icon: Tags },
  { href: "/link", label: "Telegram", icon: Link2 },
  { href: "/account", label: "Mein Konto", icon: UserCircle },
];

// Primary destinations shown in the mobile bottom tab bar (thumb-friendly).
const PRIMARY = [
  { href: "/dashboard", label: "Start", icon: Home },
  { href: "/nwz", label: "Suche", icon: Newspaper },
  { href: "/council", label: "Ratsinfo", icon: Landmark },
  { href: "/topics", label: "Themen", icon: Tags },
];

function useDarkMode() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  const toggle = () => {
    toggleTheme();
    setDark(document.documentElement.classList.contains("dark"));
  };
  return { dark, toggle };
}

function ThemeToggle({ className }: { className?: string }) {
  const { dark, toggle } = useDarkMode();
  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Helles Design aktivieren" : "Dunkles Design aktivieren"}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className,
      )}
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = [...LINKS];
  if (user?.role === "admin") items.push({ href: "/admin", label: "Admin", icon: Settings });

  return (
    <nav className="flex-1 space-y-1 px-3">
      {items.map((l) => {
        const Icon = l.icon;
        const active = pathname === l.href || pathname.startsWith(l.href + "/");
        return (
          <Link
            key={l.href}
            href={l.href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserFooter() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center justify-between px-2 pb-2">
        <span className="truncate text-xs text-muted-foreground">{user?.email}</span>
        <ThemeToggle />
      </div>
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
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card md:flex">
      <div className="px-5 py-5">
        <Brand />
      </div>
      <NavLinks />
      <UserFooter />
    </aside>
  );
}

export function MobileTopbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-card/95 px-4 py-3 backdrop-blur md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Menü öffnen">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent>
          <SheetTitle>Navigation</SheetTitle>
          <div className="px-5 py-5">
            <Brand />
          </div>
          <NavLinks onNavigate={() => setOpen(false)} />
          <UserFooter />
        </SheetContent>
      </Sheet>
      <div className="flex flex-1 items-center gap-2">
        <BrandMark className="h-7 w-7" />
        <span className="text-base font-bold tracking-tight text-foreground">Stadtpuls</span>
      </div>
      <ThemeToggle />
    </header>
  );
}

export function MobileBottomNav() {
  const pathname = usePathname();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
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
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-colors",
              active ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className={cn("h-5 w-5 transition-transform", active && "scale-110")} />
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
