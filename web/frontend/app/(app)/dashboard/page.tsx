"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Newspaper, Landmark, Tags, Link2, Check, ArrowRight, Sparkles, BarChart3, Map, type LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Topic } from "@/lib/types";
import { Badge, Card, PageHeader } from "@/components/ui";

const tiles = [
  { href: "/council", title: "Ratsinformationssystem", desc: "Beschlüsse, KI-Fragen, Sitzungen, Themen und Analysen.", icon: Landmark },
  { href: "/topics", title: "Meine Themen", desc: "Themen verwalten und Treffer ansehen.", icon: Tags },
  { href: "/nwz", title: "Artikelsuche", desc: "Schlagzeilen aus der NWZ zu Ratsthemen.", icon: Newspaper },
  { href: "/link", title: "Telegram verbinden", desc: "Konto mit dem Bot verknüpfen.", icon: Link2 },
];

export default function DashboardPage() {
  const { user } = useAuth();

  // Topic count marks the "first topic" step done; only queryable once linked.
  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
    enabled: !!user?.linked,
  });
  const topicCount = topicsQuery.data?.length ?? 0;
  // NWZ is a manually-unlocked feature — hide its quick-access tile from normal users
  // (mirrors the nav gating); the press links on decisions handle the rest.
  const showNwz = !!user?.nwz_fulltext_allowed || user?.role === "admin";
  const visibleTiles = tiles.filter((t) => t.href !== "/nwz" || showNwz);

  return (
    <div>
      <PageHeader
        title="Willkommen zurück"
        description={user?.email}
        action={user?.linked ? <Badge color="green">Telegram verbunden</Badge> : <Badge color="amber">Telegram offen</Badge>}
      />

      <FirstSteps linked={!!user?.linked} hasTopic={topicCount > 0} />

      <h2 className="mt-8 text-sm font-semibold text-muted-foreground">Schnellzugriff</h2>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {visibleTiles.map((t) => {
          const Icon = t.icon;
          return (
            <Link key={t.href} href={t.href}>
              <Card className="card-interactive p-5">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <h3 className="font-semibold text-foreground">{t.title}</h3>
                    <p className="mt-0.5 text-sm text-muted-foreground">{t.desc}</p>
                  </div>
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

const ONBOARDING_KEY = "ratslotse:onboarding-visited";

type Step = { id: string; icon: LucideIcon; title: string; desc: string; href: string; done?: boolean };

function FirstSteps({ linked, hasTopic }: { linked: boolean; hasTopic: boolean }) {
  // Onboarding is a nudge, not critical state — track opened steps client-side so a step
  // ticks off as soon as it's clicked (the action steps have no other completion signal).
  // Read in an effect (not during render) to avoid an SSR hydration mismatch.
  const [visited, setVisited] = useState<string[]>([]);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(ONBOARDING_KEY);
      if (raw) setVisited(JSON.parse(raw));
    } catch { /* ignore unreadable storage */ }
  }, []);
  const markVisited = (id: string) =>
    setVisited((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      try { localStorage.setItem(ONBOARDING_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });

  const steps: Step[] = [
    { id: "frag", icon: Sparkles, title: "Stell dem Rat eine Frage",
      desc: "Beispiel-Frage: Was wurde zum Fliegerhorst beschlossen? Die KI findet die passenden Beschlüsse und antwortet mit Quellen.",
      href: "/council?tab=decisions&mode=fragen" },
    { id: "beschluesse", icon: Landmark, title: "Beschlüsse durchstöbern",
      desc: "Volltextsuche mit Filtern nach Fraktion, Themenfeld und Geldbeträgen.",
      href: "/council" },
    { id: "analyse", icon: BarChart3, title: "Die Analyse erkunden",
      desc: "Wer ist im Rat aktiv, wo fließt das Geld, welche Themen bewegen — Parteien, Personen, Finanzen, Trends.",
      href: "/council?tab=analysis" },
    { id: "karten", icon: Map, title: "Themen-Seiten mit Karten",
      desc: "Gebiete und Straßen mit KI-Beschreibung und eingezeichneter Karte.",
      href: "/council?tab=themen" },
    { id: "thema", icon: Tags, title: "Erstes Thema anlegen",
      desc: "Lege ein Thema an und werde über neue Beschlüsse dazu benachrichtigt.",
      href: "/topics", done: hasTopic },
    { id: "telegram", icon: Link2, title: "Telegram verbinden",
      desc: "Optional: Benachrichtigungen direkt per Telegram statt per E-Mail.",
      href: "/link", done: linked },
  ];

  return (
    <Card className="mt-6 p-5">
      <h2 className="font-semibold text-foreground">Erste Schritte</h2>
      <p className="text-sm text-muted-foreground">Entdecke, was Ratslotse kann.</p>
      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {steps.map((step) => {
          const Icon = step.icon;
          const done = step.done || visited.includes(step.id);
          return (
            <Link
              key={step.id}
              href={step.href}
              onClick={() => markVisited(step.id)}
              className="group flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:border-primary/40 hover:bg-primary/5"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                {done ? <Check className="h-4 w-4 text-green-600" /> : <Icon className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  {done && <Badge color="green">Erledigt</Badge>}
                </div>
                <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.desc}</p>
              </div>
              <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </Link>
          );
        })}
      </div>
    </Card>
  );
}
