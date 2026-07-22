"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  BarChart3, CalendarDays, CornerDownLeft, Gavel, History, Home, Landmark,
  Play, Scale, Search, Settings, Sparkles, SunMoon, Tag, Tags, UserCircle, type LucideIcon,
} from "lucide-react";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/use-debounce";
import { decisionHref } from "@/lib/routes";
import { getRecentDecisions } from "@/lib/recent";
import { cycleTheme } from "@/lib/theme";
import { formatDate, toast } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { startGuidedTour } from "@/components/tour";
import type { CouncilDecision } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * ⌘K-Palette: Schnellnavigation, Aktionen und Live-Beschluss-Suche in einem
 * Overlay. Öffnet per ⌘K/Strg+K, über den Such-Button in der Sidebar oder das
 * Lupen-Icon der mobilen Topbar (`openCommandPalette()`).
 */
const OPEN_EVENT = "ratslotse:open-palette";

export function openCommandPalette() {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

type Item = {
  key: string;
  section: string;
  label: string;
  sub?: string;
  icon: LucideIcon;
  run: () => void;
};

const THEME_LABEL: Record<string, string> = { light: "Hell", dark: "Dunkel", system: "System" };

export function CommandPalette() {
  const router = useRouter();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [decisions, setDecisions] = useState<CouncilDecision[]>([]);
  const [searching, setSearching] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const debounced = useDebounce(query.trim(), 250);

  // Öffnen/Schließen: Event + globales ⌘K/Strg+K.
  useEffect(() => {
    const onOpen = () => setOpen(true);
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener(OPEN_EVENT, onOpen);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener(OPEN_EVENT, onOpen);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  // Zustand beim Öffnen zurücksetzen.
  useEffect(() => {
    if (open) {
      setQuery("");
      setDecisions([]);
      setActive(0);
    }
  }, [open]);

  // Live-Suche über die Beschlüsse (ab 3 Zeichen).
  useEffect(() => {
    if (!open || debounced.length < 3) {
      setDecisions([]);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    api
      .get<{ total: number; decisions: CouncilDecision[] }>(
        `/council/decisions${qs({ q: debounced, limit: 5, offset: 0 })}`,
      )
      .then((d) => {
        if (!cancelled) setDecisions(d.decisions.filter((x) => x.kind !== "subvote"));
      })
      .catch(() => {
        if (!cancelled) setDecisions([]);
      })
      .finally(() => {
        if (!cancelled) setSearching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, debounced]);

  const close = useCallback(() => setOpen(false), []);
  const go = useCallback(
    (href: string) => {
      close();
      router.push(href);
    },
    [close, router],
  );

  // Flache Item-Liste (für Tastatur-Navigation), gruppiert per section-Label.
  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase();
    const match = (label: string) => !q || label.toLowerCase().includes(q);

    const nav: Item[] = [
      { key: "nav-dash", section: "Navigation", label: "Übersicht", icon: Home, run: () => go("/dashboard") },
      { key: "nav-besch", section: "Navigation", label: "Beschlüsse", icon: Gavel, run: () => go("/council?tab=decisions") },
      { key: "nav-sitz", section: "Navigation", label: "Sitzungen", icon: CalendarDays, run: () => go("/council?tab=sessions") },
      { key: "nav-themen", section: "Navigation", label: "Themen & Karte", icon: Tag, run: () => go("/council?tab=themen") },
      { key: "nav-analyse", section: "Navigation", label: "Analyse", icon: BarChart3, run: () => go("/council?tab=analysis") },
      { key: "nav-meine", section: "Navigation", label: "Meine Themen", icon: Tags, run: () => go("/topics") },
      { key: "nav-konto", section: "Navigation", label: "Mein Konto", icon: UserCircle, run: () => go("/account") },
      ...(user?.role === "admin"
        ? [{ key: "nav-admin", section: "Navigation", label: "Admin", icon: Settings, run: () => go("/admin") } as Item]
        : []),
    ].filter((i) => match(i.label));

    const actions: Item[] = [
      {
        key: "act-frage", section: "Aktionen", label: "KI-Frage stellen", sub: "Frag den Stadtrat in normaler Sprache",
        icon: Sparkles, run: () => go("/council?tab=decisions&mode=fragen"),
      },
      {
        key: "act-theme", section: "Aktionen", label: "Design wechseln", sub: "Hell → Dunkel → System",
        icon: SunMoon, run: () => { const t = cycleTheme(); toast.success(`Design: ${THEME_LABEL[t] ?? t}`); },
      },
      {
        key: "act-tour", section: "Aktionen", label: "Lotti-Tour starten", sub: "Einmal durch alles, was Ratslotse kann",
        icon: Play, run: () => { close(); startGuidedTour(); },
      },
    ].filter((i) => match(i.label));

    const recent: Item[] = q
      ? []
      : getRecentDecisions().slice(0, 4).map((r) => ({
          key: `rec-${r.id}`, section: "Zuletzt angesehen", label: r.title,
          sub: `${r.committee} · ${formatDate(r.session_date)}`, icon: History,
          run: () => go(decisionHref(r.id)),
        }));

    const found: Item[] = decisions.map((d) => ({
      key: `dec-${d.id}`, section: "Beschlüsse", label: d.title ?? "Beschluss",
      sub: `${d.committee} · ${formatDate(d.session_date)}`, icon: Scale,
      run: () => go(decisionHref(d.id)),
    }));
    if (debounced.length >= 3) {
      found.push({
        key: "dec-all", section: "Beschlüsse", label: `Alle Ergebnisse für „${debounced}“`,
        icon: Search, run: () => go(`/council?tab=decisions&q=${encodeURIComponent(debounced)}`),
      });
    }

    return [...recent, ...found, ...nav, ...actions];
  }, [query, debounced, decisions, user, go, close]);

  // Aktiven Eintrag im gültigen Bereich halten + sichtbar scrollen.
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, items.length - 1)));
  }, [items.length]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); items[active]?.run(); }
  };

  // Gruppiert rendern, Index läuft flach über alle Sektionen.
  let index = -1;
  const sections = Array.from(new Set(items.map((i) => i.section)));

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        {/* Bewusst KEINE Öffnungs-Animation: ⌘K ist eine Tastatur-Aktion, die
            dutzende Male am Tag feuert — jede Animation macht sie gefühlt
            langsamer (Raycast-Prinzip). */}
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          onOpenAutoFocus={(e) => {
            // Fokus direkt ins Suchfeld statt auf den Dialog-Container.
            e.preventDefault();
            (document.getElementById("cmdk-input") as HTMLInputElement | null)?.focus();
          }}
          className="fixed left-1/2 top-[12vh] z-50 w-[min(94vw,560px)] -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-card shadow-lifted"
        >
          <DialogPrimitive.Title className="sr-only">Suche und Befehle</DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              id="cmdk-input"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActive(0); }}
              onKeyDown={onKeyDown}
              placeholder="Suchen oder Befehl eingeben…"
              className="h-12 w-full bg-transparent text-base sm:text-sm text-foreground outline-none placeholder:text-muted-foreground"
              role="combobox"
              aria-expanded="true"
              aria-controls="cmdk-list"
              aria-activedescendant={items[active] ? `cmdk-item-${items[active].key}` : undefined}
            />
            <kbd className="hidden shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:block">
              ESC
            </kbd>
          </div>

          <div ref={listRef} id="cmdk-list" role="listbox" className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
            {searching && decisions.length === 0 && (
              <p className="px-3 py-2 text-xs text-muted-foreground">Suche in Beschlüssen…</p>
            )}
            {items.length === 0 && !searching && (
              <div className="flex flex-col items-center py-8 text-center">
                <Mascot pose="search" className="h-20 w-20" />
                <p className="mt-2 text-sm font-medium text-foreground">Nichts gefunden</p>
                <p className="mt-0.5 text-xs text-muted-foreground">Versuch einen anderen Begriff — oder frag die KI direkt.</p>
              </div>
            )}
            {sections.map((section) => (
              <div key={section}>
                <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  {section}
                </p>
                {items.filter((i) => i.section === section).map((item) => {
                  index += 1;
                  const i = index;
                  const Icon = item.icon;
                  const isActive = i === active;
                  return (
                    <button
                      key={item.key}
                      id={`cmdk-item-${item.key}`}
                      data-index={i}
                      role="option"
                      aria-selected={isActive}
                      type="button"
                      onClick={() => item.run()}
                      onMouseMove={() => setActive(i)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        isActive ? "bg-primary/10 text-foreground" : "text-foreground/90",
                      )}
                    >
                      <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground")} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{item.label}</span>
                        {item.sub && <span className="block truncate text-xs text-muted-foreground">{item.sub}</span>}
                      </span>
                      {isActive && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
