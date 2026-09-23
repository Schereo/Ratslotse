"use client";

import { useEffect, useState } from "react";
import { Activity, BookOpen, LayoutDashboard, Server, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const GROUPS = [
  { label: "Überblick", icon: LayoutDashboard, views: [["stats", "Überblick"]] },
  { label: "Nutzung", icon: Activity, views: [["aktivitaet", "Aktivität"], ["konten", "Neue Konten"], ["reichweite", "Reichweite"], ["antworten", "Antwortqualität"], ["lotti", "Lotti"]] },
  { label: "Menschen", icon: Users, views: [["users", "Nutzer*innen"], ["emails", "E-Mails"], ["feedback", "Feedback"], ["news", "Neuigkeiten"]] },
  { label: "Betrieb", icon: Server, views: [["jobs", "Import & Cron-Jobs"], ["fehler", "Fehler"], ["llm", "LLM-Kosten"], ["live", "Live-Probe"]] },
  { label: "Inhalte", icon: BookOpen, views: [["quiz", "Quiz"], ["orte", "Ortskandidaten"], ["themen", "Themen-Dubletten"]] },
] as const;

export type AdminView = typeof GROUPS[number]["views"][number][0];

/** Hash links work in the static app export, on reload and with browser Back. */
export function useAdminView() {
  const [view, setView] = useState<AdminView>("stats");
  const [route, setRoute] = useState("");
  useEffect(() => {
    const read = () => {
      const [hash, query = ""] = window.location.hash.slice(1).split("?");
      setRoute(query);
      const found = GROUPS.flatMap((g) => [...g.views]).find(([key]) => key === hash);
      setView(found?.[0] ?? "stats");
    };
    read();
    const navigate = () => { read(); window.scrollTo({ top: 0, behavior: "instant" }); };
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);
  return [view, route] as const;
}

export function AdminNavigation({ view }: { view: AdminView }) {
  const current = GROUPS.find((g) => g.views.some(([key]) => key === view)) ?? GROUPS[0];
  return (
    <div className="mt-6">
      <nav aria-label="Admin-Bereiche" className="grid grid-cols-3 gap-1 rounded-2xl border border-border bg-card p-1.5 sm:grid-cols-5">
        {GROUPS.map(({ label, icon: Icon, views }) => {
          const active = label === current.label;
          return (
            <a key={label} href={`#${active ? view : views[0][0]}`} aria-current={active ? "true" : undefined}
              className={cn("flex min-h-12 items-center justify-center gap-2 rounded-xl px-2 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
              <Icon className="hidden h-4 w-4 shrink-0 sm:block" aria-hidden />{label}
            </a>
          );
        })}
      </nav>
      {current.views.length > 1 && (
        <nav aria-label={`${current.label} im Detail`} className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-b border-border px-1">
          {current.views.map(([key, label]) => (
            <a key={key} href={`#${key}`} aria-current={view === key ? "page" : undefined}
              className={cn("flex min-h-11 items-center border-b-2 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                view === key ? "border-primary font-semibold text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>
              {label}
            </a>
          ))}
        </nav>
      )}
    </div>
  );
}
