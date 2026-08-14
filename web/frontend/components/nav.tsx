"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Home, Tags, Search, Settings, LogOut, UserCircle, ChevronRight,
  CalendarDays, BarChart3, Trophy, Sparkles, Map as MapIcon, Command,
  MoreHorizontal, MessageCircle,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LANDING_HREF } from "@/components/native-redirect";
import { isNativeApp } from "@/lib/platform";
import { Brand, BrandMark } from "@/components/brand";
import { FeedbackButton, openFeedback } from "@/components/feedback";
import { LottiThemeSwitch } from "@/components/theme-switch";
import { cn, pfad } from "@/lib/utils";
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

/** Zahl offener Feedback-Einträge — dasselbe Zeichen wie bei „Meine Themen",
 *  nur an „Admin". Läuft ausschließlich für Admins: Der Endpunkt verlangt die
 *  Rolle, für alle anderen wäre die Abfrage ein garantierter 403. */
function useUnreadFeedback(enabled: boolean): number {
  const { data } = useQuery({
    queryKey: ["admin-feedback-unread"],
    queryFn: () => api.get<{ total: number }>("/admin/feedback/unread-count"),
    enabled,
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
  // Split 12.08.: Fragen ist das Headliner-Feature und steht als eigene
  // Seite VOR der Suche; „Suchen & Fragen" gibt es nicht mehr.
  // Anker hieß bis 12.08. „nav-ratsinfo" — aus der Zeit, als hier „Suchen &
  // Fragen" stand und die Tour das Ratsinfo als Ganzes erklärte. Nach dem
  // Split zeigte die Station „Das Ratsinfo" auf „Fragen"; der Anker heißt
  // jetzt, worauf er zeigt.
  { href: "/fragen", label: "Fragen", icon: Sparkles, tour: "nav-fragen" },
  { href: "/council", label: "Suche", icon: Search, tab: "decisions" },
  { href: "/council?tab=sessions", label: "Sitzungen", icon: CalendarDays, tab: "sessions" },
  { href: "/council?tab=themen", label: "Stadtkarte", icon: MapIcon, tab: "themen" },
  { href: "/council?tab=analysis", label: "Analyse", icon: BarChart3, tab: "analysis" },
];
const PERSONAL: Item = { href: "/topics", label: "Meine Themen", icon: Tags, tour: "nav-themen" };
const QUIZ: Item = { href: "/quiz", label: "Quiz", icon: Trophy };

// Mobile Tab-Bar (Design 9a③): fünf gleichwertige Ziele, kein FAB mehr —
// „Fragen" führt direkt in den KI-Frage-Modus, alles Übrige wohnt in „Mehr".
const FRAGEN_HREF = "/fragen";
const TABS: (Item & { aktiv: (pathname: string, tab: string | null) => boolean })[] = [
  { href: "/dashboard", label: "Start", icon: Home,
    aktiv: (p) => p === "/dashboard" || p.startsWith("/dashboard/") },
  { href: FRAGEN_HREF, label: "Fragen", icon: Sparkles, tour: "nav-fragen",
    aktiv: (p) => p === "/fragen" || p.startsWith("/fragen/") },
  { href: "/council?tab=sessions", label: "Sitzungen", icon: CalendarDays,
    aktiv: (p, t) => p === "/council" && t === "sessions" },
  { href: "/topics", label: "Themen", icon: Tags, tour: "nav-themen",
    aktiv: (p) => p === "/topics" || p.startsWith("/topics/") },
];
// Ziele hinter „Mehr" (9a④) — der Tab gilt als aktiv, wenn eine davon offen ist.
const MEHR_AKTIV = (pathname: string, tab: string | null) =>
  // Die Suche wohnt seit dem Split (#455) hier drin — samt ihrer Detailseiten
  // (Beschluss, Person, Thema), die ihr Inneres sind.
  (pathname === "/council" && tab !== "sessions")
  || pathname.startsWith("/council/")
  || ["/quiz", "/account", "/admin"].some((p) => pathname === p || pathname.startsWith(p + "/"));

/** RL-U09: Der Lotti-Himmel-Schalter ersetzt den Dreistufen-Icon-Toggle — im
 *  Web binär (Erststart folgt dem OS, danach entscheidet der Schalter).
 *  Nur Desktop-Sidebar: Auf Mobilgeräten (Web wie App) läuft die Wahl über
 *  Konto → „Erscheinungsbild" — die Topbar bleibt schlank (Tim, 22.07.).
 *  Mount-Gate: SSR kennt die Plattform nicht. */
function WebThemeSwitch({ className }: { className?: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => setShow(!isNativeApp()), []);
  if (!show) return null;
  return <LottiThemeSwitch className={className} />;
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
  const pathname = pfad(usePathname());
  const { user } = useAuth();
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const onCouncil = pathname === "/council" || pathname.startsWith("/council/");
  const unread = useUnreadTopicHits();
  const openFeedback = useUnreadFeedback(user?.role === "admin");

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
        <NavItem
          item={{ href: "/admin", label: "Admin", icon: Settings }}
          active={isActive("/admin")}
          badge={openFeedback}
          onNavigate={onNavigate}
        />
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

function UserFooter({ onNavigate, showTheme = false }: { onNavigate?: () => void; showTheme?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };
  const accountActive = pfad(pathname) === "/account";
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
        {showTheme && <WebThemeSwitch />}
      </div>
      <FeedbackButton onNavigate={onNavigate} />
      <button
        onClick={onLogout}
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <LogOut className="h-4 w-4" /> Abmelden
      </button>
      <RechtsLinks />
    </div>
  );
}

/** Design 6a③: Die Pflicht-Links wohnen im Sidebar-Fuß (Desktop) bzw. im
 *  „Mehr"-Sheet (mobil, 9a④) — der sticky Seiten-Footer, der auf jeder Seite
 *  mitscrollte, entfällt dafür. */
function RechtsLinks({ zentriert = false }: { zentriert?: boolean }) {
  // Die Technik-Doku (/docs) liegt nur auf dem Server, nicht im App-Bundle —
  // in der nativen App wäre der Link tot (Review-Befund P4). Erst nach dem
  // Mount entscheiden, gleiches Hydration-Muster wie beim Druck-Knopf.
  const [mitDocs, setMitDocs] = useState(false);
  useEffect(() => { setMitDocs(!isNativeApp()); }, []);
  return (
    <p className={cn(
      "text-[11px] leading-relaxed text-muted-foreground/80",
      zentriert ? "border-t border-border/60 pt-2.5 text-center" : "px-3 pb-1 pt-2",
    )}>
      <a href="/hilfe" className="hover:text-foreground">Hilfe</a>
      {" · "}
      <a href="/impressum" className="hover:text-foreground">Impressum</a>
      {" · "}
      <a href="/datenschutz" className="hover:text-foreground">Datenschutz</a>
      {" · "}
      <a href="/changelog" className="hover:text-foreground">Changelog</a>
      {mitDocs && (
        <>
          {" · "}
          {/* Angemeldete werden von „/" aufs Dashboard geschickt — dieser
              Link ist die Fluchttür zur Startseite (Tims Wunsch 12.08.). */}
          <a href={LANDING_HREF} className="hover:text-foreground">Startseite</a>
        </>
      )}
      {mitDocs && (
        <>
          {" · "}
          <a href="/docs" className="hover:text-foreground">Technik-Doku</a>
        </>
      )}
    </p>
  );
}

export function DesktopSidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card desk:flex desk:sticky desk:top-0 desk:h-screen desk:self-start desk:overflow-y-auto">
      {/* Design 28a/R5: Hier standen zwei „Suchen" mit derselben Lupe 40 px
          übereinander — die Ghost-Zeile (Befehlspalette) und der Navigations-
          punkt „Suchen & Fragen". Wer die Lupe nahm, landete oft im falschen
          der beiden. Die Palette ist keine Rubrik, sondern ein Werkzeug: sie
          sitzt jetzt als ⌘-Knopf neben dem Logo, die Lupe gehört allein der
          Suche. */}
      <div className="flex items-center gap-2 px-5 pb-2 pt-5">
        <Brand />
        <button
          type="button"
          onClick={openCommandPalette}
          aria-label="Befehle und Sprünge öffnen (Tastenkürzel ⌘K)"
          title="Befehle & Sprünge — ⌘K"
          className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/70 bg-muted/50 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Command className="h-4 w-4" />
        </button>
      </div>
      <NavLinks />
      <UserFooter showTheme />
    </aside>
  );
}

export function MobileTopbar() {
  // Design 9a③: kein Burger mehr — die Hauptziele stehen in der Tab-Bar,
  // Sekundäres im „Mehr"-Sheet. Der Kopf behält nur Logo + Suche.
  return (
    <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-card/95 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] backdrop-blur desk:hidden">
      <div className="flex flex-1 items-center gap-2">
        <BrandMark className="h-7 w-7" />
        <span className="font-display text-base font-bold tracking-tight text-foreground">Ratslotse</span>
      </div>
      <button
        type="button"
        onClick={openCommandPalette}
        aria-label="Suchen und Befehle öffnen"
        className="flex h-9 w-9 items-center justify-center rounded-md text-foreground transition-colors hover:bg-accent"
      >
        <Search className="h-[19px] w-[19px]" />
      </button>
    </header>
  );
}

export function MobileBottomNav() {
  // useSearchParams (für den ?tab=-Abgleich) verlangt eine Suspense-Grenze;
  // der Fallback rendert dieselbe Leiste ohne Tab-Wissen — kein Leer-Blitz.
  return (
    <Suspense fallback={<BottomNavInner tab={null} />}>
      <BottomNavMitParams />
    </Suspense>
  );
}

function BottomNavMitParams() {
  return <BottomNavInner tab={useSearchParams().get("tab")} />;
}

function BottomNavInner({ tab }: { tab: string | null }) {
  const pathname = pfad(usePathname());
  const [mehrOffen, setMehrOffen] = useState(false);
  // Seitenwechsel (auch via Tab-Bar unterm Sheet) schließt das Sheet.
  useEffect(() => { setMehrOffen(false); }, [pathname, tab]);
  const mehrAktiv = mehrOffen || MEHR_AKTIV(pathname, tab);
  return (
    <>
      {mehrOffen && <MehrSheet onClose={() => setMehrOffen(false)} />}
      <nav
        // Echtes Glas statt nur Blur (iOS-Look): halbtransparente Fläche +
        // backdrop-saturate, eine 1-px-Lichtkante innen (simuliert die
        // Kanten-Brechung) und ein weicher Schatten nach oben für Tiefe.
        // Beim offenen „Mehr"-Sheet wird die Fläche deckend (9a④): das Sheet
        // dockt DARUNTER an, Glas würde seine Kante durchscheinen lassen.
        className={cn(
          // Die Safe Area wird GETEILT statt komplett unten angehängt: Sonst
          // sitzt der Inhalt 8 px unter der Oberkante, aber 8 + 20 px über der
          // Unterkante — die Icons wirken nach oben gedrückt (Tims Befund
          // 14.08.). Halb/halb ist optisch mittig, die Leiste bleibt gleich
          // hoch (der Platzhalter in `main` rechnet mit derselben Summe), und
          // der Abstand zum Home-Indikator reicht weiterhin.
          "fixed inset-x-0 bottom-0 flex border-t border-border/50 pb-[calc(env(safe-area-inset-bottom)/2)] pt-[calc(env(safe-area-inset-bottom)/2)] desk:hidden",
          mehrOffen
            ? "z-50 bg-card shadow-[0_-10px_28px_-14px_rgba(2,32,71,0.22)]"
            : "z-40 bg-card/70 backdrop-blur-xl backdrop-saturate-150 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.45),0_-10px_28px_-14px_rgba(2,32,71,0.22)] dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08),0_-10px_28px_-14px_rgba(0,0,0,0.5)]",
        )}
        aria-label="Hauptnavigation"
      >
        {/* Auf dem Handy verteilen sich die fünf Ziele über die Gerätebreite —
            78 pt pro Ziel, dicht genug. Auf dem iPad wären es 206 pt: fünf
            kleine Symbole, verloren in einer breiten Leiste (Tims Befund
            14.08.). Ab md rücken sie deshalb zu einer mittigen Gruppe
            zusammen — dieselbe Dichte wie auf dem Handy, und nah an der
            schwebenden Tab-Leiste, die iPadOS selbst zeigt. `md:` heißt hier
            immer „breites Touch-Gerät", weil die ganze Leiste ab `desk`
            ohnehin der Seitenleiste weicht. */}
        <div className="flex w-full md:mx-auto md:max-w-2xl">
          {TABS.map((l) => (
            <BottomNavItem key={l.label} item={l} active={!mehrOffen && l.aktiv(pathname, tab)} />
          ))}
          {/* „Mehr" ist ein Schalter, kein Link: öffnet/schließt das Sheet. */}
          <button
            type="button"
            onClick={() => setMehrOffen((v) => !v)}
            aria-expanded={mehrOffen}
            aria-current={mehrAktiv && !mehrOffen ? "page" : undefined}
            className={cn(
              // Größere Symbole/Schrift auf dem iPad, dafür weniger Polsterung:
              // Die Leiste bleibt gleich hoch, das Ziel darin wird größer.
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95 md:py-1 md:text-[12.5px]",
              mehrAktiv ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <span className={cn("relative rounded-full px-3.5 py-1 transition-colors", mehrAktiv && "bg-primary/10")}>
              <MoreHorizontal className={cn("h-5 w-5 transition-transform md:h-6 md:w-6", mehrAktiv && "scale-110")} />
            </span>
            Mehr
          </button>
        </div>
      </nav>
    </>
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
        "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95 md:py-1 md:text-[12.5px]",
        active ? "text-primary" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span className={cn("relative rounded-full px-3.5 py-1 transition-colors", active && "bg-primary/10")}>
        <Icon className={cn("h-5 w-5 transition-transform md:h-6 md:w-6", active && "scale-110")} />
        {showDot && <span className="absolute right-1.5 top-0 h-2 w-2 rounded-full bg-signal ring-2 ring-card" aria-hidden />}
      </span>
      {item.label}
    </Link>
  );
}

/* --------------------- „Mehr"-Sheet (Design 9a④, mobil) --------------------- */

function MehrZeile({ href, icon: Icon, label, badge = 0, primaerFarbe = true, onClose }: {
  href: string; icon: typeof Home; label: string; badge?: number;
  primaerFarbe?: boolean; onClose: () => void;
}) {
  return (
    <Link href={href} onClick={onClose}
      className="flex min-h-11 items-center gap-3 border-b border-border/60 px-1 py-2.5 text-sm font-medium text-foreground transition-colors active:bg-muted">
      <Icon className={cn("h-[17px] w-[17px] shrink-0", primaerFarbe ? "text-primary" : "text-muted-foreground")} aria-hidden />
      <span className="min-w-0 flex-1">{label}</span>
      <UnreadBadge n={badge} />
      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" aria-hidden />
    </Link>
  );
}

/** Bottom Sheet über der Tab-Bar: Konto-Zeile, Ziele ohne Tab-Platz, dann
 *  Einstellungen/Feedback/Abmelden und die Pflicht-Links als Fußzeile — es
 *  ersetzt Burger-Menü UND Seiten-Footer auf Mobil (9a④, 6a③). */
function MehrSheet({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const openFeedbackUnread = useUnreadFeedback(user?.role === "admin");
  // Hintergrund einfrieren, solange das Sheet offen ist.
  useEffect(() => {
    const alt = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = alt; };
  }, []);
  // Wisch nach unten schließt (9a④) — simple Geste, kein Mitzieh-Effekt.
  const startY = useRef<number | null>(null);
  const onLogout = async () => {
    onClose();
    await logout();
    router.replace("/login");
  };
  const initialen = (user?.email ?? "?").slice(0, 2).toUpperCase();
  return (
    <div className="fixed inset-0 z-40 desk:hidden" role="dialog" aria-modal="true" aria-label="Mehr">
      <button type="button" aria-label="Menü schließen" onClick={onClose}
        className="absolute inset-0 bg-[hsl(212_50%_12%/0.4)]" />
      <div
        className="absolute inset-x-0 bottom-0 rounded-t-[20px] bg-card px-4 pb-[calc(env(safe-area-inset-bottom)+4.75rem)] pt-2 shadow-[0_-18px_50px_-12px_rgba(2,32,71,0.45)]"
        onTouchStart={(e) => { startY.current = e.touches[0]?.clientY ?? null; }}
        onTouchMove={(e) => {
          const y = e.touches[0]?.clientY;
          if (startY.current != null && y != null && y - startY.current > 60) onClose();
        }}
      >
        <span aria-hidden className="mx-auto block h-1 w-[38px] rounded-full bg-border" />
        <Link href="/account" onClick={onClose}
          className="mt-3 flex items-center gap-2.5 border-b border-border/60 px-0.5 pb-2.5 transition-colors active:bg-muted">
          <span aria-hidden className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            {initialen}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13.5px] font-semibold text-foreground">{user?.display_name || "Mein Konto"}</span>
            <span className="block truncate text-[11px] text-muted-foreground">{user?.email}</span>
          </span>
          <span className="shrink-0 rounded-full border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground">
            Konto
          </span>
        </Link>
        <div className="flex flex-col pt-1">
          {/* Tims Befund 12.08.: Seit „Fragen" den Tab-Platz hat (Split #455),
              führte mobil KEIN Weg mehr zur Beschluss-Suche — die Lupe oben
              öffnet die Befehlspalette, nicht die Seite. Sie steht deshalb
              zuoberst im Sheet, vor Stadtkarte und Analyse. */}
          <MehrZeile href="/council" icon={Search} label="Suche" onClose={onClose} />
          <MehrZeile href="/council?tab=themen" icon={MapIcon} label="Stadtkarte" onClose={onClose} />
          <MehrZeile href="/council?tab=analysis" icon={BarChart3} label="Analyse" onClose={onClose} />
          <MehrZeile href="/quiz" icon={Trophy} label="Quiz" onClose={onClose} />
          {user?.role === "admin" && (
            <MehrZeile href="/admin" icon={Settings} label="Admin" badge={openFeedbackUnread} primaerFarbe={false} onClose={onClose} />
          )}
          <button type="button" onClick={() => { onClose(); openFeedback(); }}
            className="flex min-h-11 items-center gap-3 border-b border-border/60 px-1 py-2.5 text-left text-sm font-medium text-foreground transition-colors active:bg-muted">
            <MessageCircle className="h-[17px] w-[17px] shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1">Feedback geben</span>
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" aria-hidden />
          </button>
          <button type="button" onClick={() => void onLogout()}
            className="flex min-h-11 items-center gap-3 px-1 py-2.5 text-left text-sm font-medium text-foreground transition-colors active:bg-muted">
            <LogOut className="h-[17px] w-[17px] shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1">Abmelden</span>
          </button>
        </div>
        {/* 6a③/9a④: ersetzt mobil den Seiten-Footer — Pflicht-Links bleiben
            damit von jeder Seite aus zwei Tipper entfernt. */}
        <RechtsLinks zentriert />
      </div>
    </div>
  );
}
