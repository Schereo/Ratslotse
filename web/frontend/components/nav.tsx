"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Home, Tags, Search, Settings, LogOut, UserCircle, ChevronRight,
  CalendarDays, BarChart3, Trophy, Sparkles, Map as MapIcon, Command,
  MoreHorizontal, MessageCircle, Bookmark, Euro, Bell,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { vertrag } from "@/lib/vertrag";
import { useAuth } from "@/lib/auth";
import { LANDING_HREF } from "@/components/native-redirect";
import { isNativeApp } from "@/lib/platform";
import { darfAdmin, darfHaushalt } from "@/lib/rechte";
import { Brand, BrandMark } from "@/components/brand";
import { FeedbackButton, openFeedback } from "@/components/feedback";
import { WebThemeSwitch } from "@/components/web-theme-switch";
import { cn, pfad } from "@/lib/utils";
import { openCommandPalette } from "@/components/command-palette";
import { useGleitMarker, GleitMarker } from "@/components/gleit-marker";

// `tour` markiert Elemente als Anker für die Lotti-Tour (components/tour.tsx);
// Sidebar und Bottom-Nav tragen denselben Wert — die Tour nimmt das sichtbare.
type Item = { href: string; label: string; icon: typeof Home; tour?: string };

/** Höhe der Tab-Leiste (inkl. Sicherheitszone) — die EINE Quelle dafür.
 *
 *  Bis 16.08. war die Leiste inhaltsgetrieben hoch, und alles, was auf ihr
 *  aufsitzt, riet ihre Höhe mit einer eigenen Zahl: der fixierte Composer im
 *  Ratsgespräch mit `4rem`, das „Mehr"-Sheet und der Platzhalter in `main` mit
 *  `4.75rem`. Nachgemessen war sie aber je Breakpoint verschieden hoch — 63 px
 *  auf dem Telefon, 61 px ab `md` (dort `py-1` statt `py-2`, dafür größere
 *  Symbole). Zwischen Composer-Unterkante und Leisten-Oberkante blieb dadurch
 *  ein Streifen offen, durch den der Antworttext scrollte (Tims iPad-Befund
 *  16.08.). Zwei Zahlen an zwei Orten laufen immer wieder auseinander; deshalb
 *  ERZWINGT die Leiste diese Höhe, und wer an ihr andockt, importiert
 *  denselben Ausdruck, statt ihn nachzubauen.
 *
 *  Wer hier etwas ändert, ändert damit auch die Andockkante des Composers —
 *  das ist der Sinn. Nur `main` in app/(app)/layout.tsx rechnet noch mit einer
 *  eigenen Zahl (4.75rem = diese Höhe + Luft); das ist ein Platzhalter im
 *  Fluss, der ein paar Pixel Toleranz verträgt. */
const TABLEISTE_INHALT = "4rem"; // die Leiste selbst, ohne Sicherheitszone
export const TABLEISTE_HOEHE = `calc(env(safe-area-inset-bottom) + ${TABLEISTE_INHALT})`;

/** Höhe der mobilen Kopfleiste (inkl. Sicherheitszone) — dieselbe Rolle für
 *  oben: `pt-0.75rem` + Inhalt `h-9` + `pb-3` + 1 px Rahmen = 3.8125rem. Wer
 *  etwas unter dem Kopf festpinnt (die Belege-Spalte auf dem iPad), nimmt das
 *  hier statt einer geschätzten Zahl. */
export const KOPFLEISTE_HOEHE = "calc(env(safe-area-inset-top) + 3.8125rem)";

/** RL-903: Zahl ungesehener Themen-Treffer — der Orange-Zähler an
 *  „Meine Themen". Ruhig gepollt (60 s), 0 blendet aus. */
function useUnreadTopicHits(): number {
  const { data } = useQuery({
    queryKey: ["topics-unread"],
    queryFn: () => vertrag.get("/topics/unread-count"),
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
    queryFn: () => vertrag.get("/admin/feedback/unread-count"),
    enabled,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  return data?.total ?? 0;
}

function UnreadBadge({ n }: { n: number }) {
  if (n <= 0) return null;
  return (
    // `key` auf der Zahl: Der Zähler wird alle 60 s neu geholt: Springt er von
    // 2 auf 3, montiert React denselben Knoten neu und die Pop-Animation läuft
    // wieder — ohne den Schlüssel liefe sie nur beim allerersten Erscheinen,
    // und genau der Sprung ist die Nachricht.
    <span
      key={n}
      className="animate-pop-in ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-signal px-1.5 text-[11px] font-bold tabular-nums text-signal-foreground"
    >
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

// Design-Serie „Haushalt" (H-01): eigener Bereich in der Sidebar; mobil hängt
// er im „Mehr"-Sheet — die Tab-Bar bleibt fünfteilig (H-05).
//
// Steht seit dem Rollen-Umbau NEBEN der Liste statt darin: Wer ihn sehen darf,
// hängt am Konto (Recht `budget`), und eine Modul-Konstante kennt kein Konto.
// Ein Anker auf eine Seite, die für diese Person ein 404 ist, wäre schlechter
// als kein Anker — genau diese Falle steht in web/frontend/CLAUDE.md.
const HAUSHALT: Item = { href: "/haushalt", label: "Haushalt", icon: Euro };
const PERSONAL: Item = { href: "/topics", label: "Meine Themen", icon: Tags, tour: "nav-themen" };
// Split 28.08.2026: Ausschuss-Abos hingen als Block unter „Meine Themen" und
// bekamen dadurch weder Platz noch einen eigenen Weg dorthin — man musste an
// den Themen vorbeiscrollen. Zwei Arten, dem Rat zu folgen (ein Anliegen vs.
// ein ganzes Gremium), sind jetzt zwei Ziele.
const ABOS: Item = { href: "/abos", label: "Abos", icon: Bell };
const BOOKMARKS: Item = { href: "/bookmarks", label: "Merkliste", icon: Bookmark };
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
  || ["/abos", "/bookmarks", "/quiz", "/account", "/admin"].some((p) => pathname === p || pathname.startsWith(p + "/"));

// RL-U09: In der App-Hülle sitzt der Lotti-Himmel-Schalter (WebThemeSwitch)
// nur in der Desktop-Sidebar — mobil läuft die Wahl über Konto →
// „Erscheinungsbild", die Topbar bleibt schlank (Tim, 22.07.).

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
      data-aktiv={active ? "true" : undefined}
      aria-current={active ? "page" : undefined}
      className={cn(
        // Aktiv = Pill (RL-102): Fläche + Farbe, kein Akzent-Balken mehr. Die
        // Fläche zeichnet seit 09/2026 die gleitende Markierung (s. o.); die
        // Klasse hier bleibt als Stand ohne JS stehen und wird vom Marker
        // übernommen, sobald er misst.
        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-fluss",
        active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {/* Das Zeichen rückt beim Überfahren einen halben Schritt vor und steht
          am aktiven Punkt etwas größer — die zwei Pixel sagen „hier geht es
          weiter", ohne dass die Zeile ihren Platz ändert. */}
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 transition-transform duration-fluss ease-out-strong",
          active ? "scale-110" : "group-hover:translate-x-0.5",
        )}
      />
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
  const openFeedback = useUnreadFeedback(darfAdmin(user));

  // Der Marker muss neu messen, sobald sich das aktive Ziel ändern KANN — das
  // ist der Pfad plus der ?tab=-Wert (fünf der Punkte zeigen auf /council und
  // unterscheiden sich nur darin) plus alles, was die Liste VERLÄNGERT.
  //
  // Das war bis 09/2026 `user?.role`, weil die Admin-Zeile die einzige
  // rollenabhängige war. Inzwischen kommt die Haushalts-Zeile dazu, und beide
  // hängen an einem RECHT statt an der Rolle (lib/rechte.ts). Die Rolle allein
  // reicht als Schlüssel deshalb nicht mehr: Ein Konto kann mehrere tragen,
  // und `role` nennt nur die stärkste — zwei verschiedene Listenlängen sähen
  // für den Marker gleich aus. Die Rechte nennen genau das, was die Zeilen
  // bestimmt.
  const { gruppeRef, markerRef } = useGleitMarker(
    `${pathname}|${activeTab}|${user?.permissions?.join(",") ?? ""}`, "seitenleiste");

  return (
    <div ref={gruppeRef} className="gleit-gruppe relative flex-1">
      <GleitMarker markerRef={markerRef} radius="var(--radius)" />
      <nav className="space-y-1 px-3">
        {MAIN_ITEMS.map((l) => (
          <NavItem
            key={l.href}
            item={l}
            active={l.tab ? onCouncil && activeTab === l.tab : isActive(l.href)}
            onNavigate={onNavigate}
          />
        ))}
        {darfHaushalt(user) && (
          <NavItem item={HAUSHALT} active={isActive("/haushalt")} onNavigate={onNavigate} />
        )}

        <SectionHeader>Persönlich</SectionHeader>
        <NavItem item={PERSONAL} active={isActive("/topics")} badge={unread} onNavigate={onNavigate} />
        <NavItem item={ABOS} active={isActive("/abos")} onNavigate={onNavigate} />
        <NavItem item={BOOKMARKS} active={isActive("/bookmarks")} onNavigate={onNavigate} />
        <NavItem item={QUIZ} active={isActive("/quiz")} onNavigate={onNavigate} />
        {darfAdmin(user) && (
          <NavItem
            item={{ href: "/admin", label: "Admin", icon: Settings }}
            active={isActive("/admin")}
            badge={openFeedback}
            onNavigate={onNavigate}
          />
        )}
      </nav>
    </div>
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
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors duration-fluss hover:bg-accent hover:text-foreground"
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
          className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/70 bg-muted/50 text-muted-foreground transition-[color,background-color,transform] duration-fluss ease-out-strong hover:bg-accent hover:text-foreground active:scale-95"
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
        className="flex h-9 w-9 items-center justify-center rounded-md text-foreground transition-[color,background-color,transform] duration-fluss ease-out-strong hover:bg-accent active:scale-90"
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
  /** Drei Stände statt eines Schalters: Das Blatt braucht Zeit zum Hinausfahren,
   *  und solange es fährt, muss es noch im Baum stehen. `abgang` ist genau
   *  dieses Fenster — es endet, wenn die Animation meldet, dass sie durch ist. */
  const [mehr, setMehr] = useState<"zu" | "auf" | "abgang">("zu");
  const mehrOffen = mehr !== "zu";
  const schliessen = () => setMehr((v) => (v === "auf" ? "abgang" : v));
  // Seitenwechsel (auch via Tab-Bar unterm Sheet) räumt das Blatt SOFORT weg:
  // Wer navigiert, wartet nicht auf eine Schublade, die er hinter sich lässt.
  useEffect(() => { setMehr("zu"); }, [pathname, tab]);
  // Optik hängt am „auf", nicht am „offen": Sobald geschlossen wird, fährt die
  // Markierung zum echten Tab zurück, während das Blatt hinausgleitet — beides
  // gehört zur selben Handlung und soll gemeinsam laufen.
  const mehrAktiv = mehr === "auf" || MEHR_AKTIV(pathname, tab);
  const { gruppeRef, markerRef } = useGleitMarker(`${pathname}|${tab ?? ""}|${mehr}`, "tableiste");
  return (
    <>
      {mehrOffen && (
        <MehrSheet abgang={mehr === "abgang"} onClose={schliessen} onFertig={() => setMehr("zu")} />
      )}
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
          // Die Sicherheitszone gehört UNTEN hin. Sie hälftig auf oben und
          // unten zu verteilen (so kam sie mit der iPad-Runde #475 herein)
          // macht die Leiste auf dem iPhone rund 17 pt höher und schiebt die
          // Symbole in Richtung Home-Indikator — auf dem iPhone ist die Zone
          // 34 pt hoch, auf dem iPad rund 20 (Tims Befund 15.08.). Der
          // hälftige Ausgleich bleibt deshalb den breiten Touch-Geräten.
          // Die Höhe steht fest (TABLEISTE_HOEHE, s. o.) statt sich aus dem
          // Inhalt zu ergeben: Nur so ist die Oberkante der Leiste dieselbe
          // Kante, an der der Composer andockt. Die Ziele darin zentrieren
          // sich in der verbleibenden Fläche (`justify-center`).
          "fixed inset-x-0 bottom-0 flex border-t border-border/50 pb-[env(safe-area-inset-bottom)] desk:hidden",
          "md:pb-[calc(env(safe-area-inset-bottom)/2)] md:pt-[calc(env(safe-area-inset-bottom)/2)]",
          mehrOffen
            ? "z-50 bg-card shadow-[0_-10px_28px_-14px_rgba(2,32,71,0.22)]"
            : "z-40 bg-card/70 backdrop-blur-xl backdrop-saturate-150 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.45),0_-10px_28px_-14px_rgba(2,32,71,0.22)] dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08),0_-10px_28px_-14px_rgba(0,0,0,0.5)]",
        )}
        style={{ height: TABLEISTE_HOEHE }}
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
        <div ref={gruppeRef} className="gleit-gruppe relative flex w-full md:mx-auto md:max-w-2xl">
          {/* Die Markierung fährt quer durch die Leiste mit — auf dem Telefon
              ist das die sichtbarste Bewegung der ganzen App, weil hier jeder
              Wechsel stattfindet. Rund wie die Pillen, hinter denen sie liegt. */}
          <GleitMarker markerRef={markerRef} radius="9999px" />
          {TABS.map((l) => (
            <BottomNavItem key={l.label} item={l} active={mehr !== "auf" && l.aktiv(pathname, tab)} />
          ))}
          {/* „Mehr" ist ein Schalter, kein Link: öffnet/schließt das Sheet. */}
          <button
            type="button"
            onClick={() => (mehr === "auf" ? schliessen() : setMehr("auf"))}
            aria-expanded={mehr === "auf"}
            aria-current={mehrAktiv && mehr !== "auf" ? "page" : undefined}
            className={cn(
              // Größere Symbole/Schrift auf dem iPad, dafür weniger Polsterung:
              // Die Leiste bleibt gleich hoch, das Ziel darin wird größer.
              "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95 md:py-1 md:text-[12.5px]",
              mehrAktiv ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <span
              data-aktiv={mehrAktiv ? "true" : undefined}
              className={cn("relative rounded-full px-3.5 py-1 transition-colors", mehrAktiv && "bg-primary/10")}
            >
              {/* Die drei Punkte drehen sich beim Öffnen eine Vierteldrehung —
                  aus „hier ist mehr" wird sichtbar „das Blatt ist offen". */}
              <MoreHorizontal
                className={cn(
                  "h-5 w-5 transition-transform duration-weg ease-out-strong md:h-6 md:w-6",
                  mehrAktiv && "scale-110",
                  mehr === "auf" && "rotate-90",
                )}
              />
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
        "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-[color,transform] duration-150 active:scale-95 md:py-1 md:text-[12.5px]",
        active ? "text-primary" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span
        data-aktiv={active ? "true" : undefined}
        className={cn("relative rounded-full px-3.5 py-1 transition-colors", active && "bg-primary/10")}
      >
        <Icon className={cn("h-5 w-5 transition-transform duration-weg ease-out-strong md:h-6 md:w-6", active && "scale-110")} />
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
      className="group flex min-h-11 items-center gap-3 border-b border-border/60 px-1 py-2.5 text-sm font-medium text-foreground transition-colors active:bg-muted">
      <Icon className={cn("h-[17px] w-[17px] shrink-0", primaerFarbe ? "text-primary" : "text-muted-foreground")} aria-hidden />
      <span className="min-w-0 flex-1">{label}</span>
      <UnreadBadge n={badge} />
      {/* Der Pfeil rückt unter dem Finger einen Schritt vor — die Zeile
          bestätigt damit die Richtung, in die sie führt. */}
      <ChevronRight
        className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-transform duration-tipp ease-out-strong group-active:translate-x-0.5"
        aria-hidden
      />
    </Link>
  );
}

/** Bottom Sheet über der Tab-Bar: Konto-Zeile, Ziele ohne Tab-Platz, dann
 *  Einstellungen/Feedback/Abmelden und die Pflicht-Links als Fußzeile — es
 *  ersetzt Burger-Menü UND Seiten-Footer auf Mobil (9a④, 6a③). */
function MehrSheet({ abgang, onClose, onFertig }: { abgang: boolean; onClose: () => void; onFertig: () => void }) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const openFeedbackUnread = useUnreadFeedback(darfAdmin(user));
  // Hintergrund einfrieren, solange das Sheet offen ist.
  useEffect(() => {
    const alt = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = alt; };
  }, []);
  // Wisch nach unten schließt (9a④) — simple Geste, kein Mitzieh-Effekt.
  const startY = useRef<number | null>(null);
  /** Auffangnetz für den Abgang: Normalerweise räumt `onAnimationEnd` das
   *  Blatt weg. Feuert das Ereignis nicht — der Tab wechselt mitten in der
   *  Animation in den Hintergrund, ein Zoom unterbricht sie —, bliebe sonst
   *  ein unsichtbares Blatt über der Seite liegen und finge jeden Tipper ab.
   *  Der Wecker läuft etwas länger als der Abgang selbst (`--takt-abgang`). */
  useEffect(() => {
    if (!abgang) return;
    const t = setTimeout(onFertig, 400);
    return () => clearTimeout(t);
  }, [abgang, onFertig]);
  const onLogout = async () => {
    onClose();
    await logout();
    router.replace("/login");
  };
  const initialen = (user?.email ?? "?").slice(0, 2).toUpperCase();
  return (
    <div className="fixed inset-0 z-40 desk:hidden" role="dialog" aria-modal="true" aria-label="Mehr">
      <button type="button" aria-label="Menü schließen" onClick={onClose}
        className={cn("scrim absolute inset-0", abgang ? "animate-scrim-zu" : "animate-scrim-auf")} />
      <div
        className={cn(
          "absolute inset-x-0 bottom-0 rounded-t-[20px] bg-card px-4 pt-2 shadow-[0_-18px_50px_-12px_rgba(2,32,71,0.45)]",
          abgang ? "animate-sheet-zu" : "animate-sheet-auf",
        )}
        onAnimationEnd={(e) => {
          // Nur auf das eigene Hinausfahren hören: Im Blatt laufen weitere
          // Animationen (die Pop-Marke an „Admin"), deren Ende hier ebenfalls
          // ankommt und das Blatt sonst mitten im Auftritt wegräumte.
          if (e.animationName === "sheet-zu" && e.target === e.currentTarget) onFertig();
        }}
        /* Das Sheet dockt UNTER der Leiste an — sein Fuß hält deren Höhe frei,
           plus 0,75 rem Luft. Aus derselben Quelle wie die Leiste selbst. */
        style={{ paddingBottom: `calc(${TABLEISTE_HOEHE} + 0.75rem)` }}
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
          {darfHaushalt(user) && <MehrZeile href="/haushalt" icon={Euro} label="Haushalt" onClose={onClose} />}
          {/* Direkt hinter „Themen" in der Tab-Leiste gedacht: Die Abos sind
              die zweite Art, dem Rat zu folgen, und hatten seit dem Split vom
              28.08.2026 keinen eigenen Weg mehr auf dem Telefon. */}
          <MehrZeile href="/abos" icon={Bell} label="Ausschuss-Abos" onClose={onClose} />
          <MehrZeile href="/bookmarks" icon={Bookmark} label="Merkliste" onClose={onClose} />
          <MehrZeile href="/quiz" icon={Trophy} label="Quiz" onClose={onClose} />
          {darfAdmin(user) && (
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
