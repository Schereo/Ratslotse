"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Newspaper, Landmark, Tags, Link2, Check, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Topic } from "@/lib/types";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { cn } from "@/lib/utils";

const tiles = [
  { href: "/nwz", title: "Artikelsuche", desc: "Das Artikel-Archiv per Volltext durchsuchen.", icon: Newspaper },
  { href: "/council", title: "Ratsinformationssystem", desc: "Sitzungen und Tagesordnungen durchsuchen.", icon: Landmark },
  { href: "/topics", title: "Meine Themen", desc: "Themen verwalten und Treffer ansehen.", icon: Tags },
  { href: "/link", title: "Telegram verbinden", desc: "Konto mit dem Bot verknüpfen.", icon: Link2 },
];

export default function DashboardPage() {
  const { user } = useAuth();

  // Topic count drives the third onboarding step; only queryable once linked.
  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<Topic[]>("/topics"),
    enabled: !!user?.linked,
  });
  const topicCount = topicsQuery.data?.length ?? 0;

  return (
    <div>
      <PageHeader
        title="Willkommen zurück"
        description={user?.email}
        action={
          <div className="flex flex-wrap gap-2">
            {user?.linked ? <Badge color="green">Telegram verbunden</Badge> : <Badge color="amber">Telegram offen</Badge>}
            {user?.nwz_verified ? <Badge color="green">NWZ verifiziert</Badge> : <Badge color="amber">NWZ offen</Badge>}
          </div>
        }
      />

      <OnboardingChecklist
        nwzVerified={!!user?.nwz_verified}
        linked={!!user?.linked}
        hasTopic={topicCount > 0}
      />

      <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Schnellzugriff</h2>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {tiles.map((t) => {
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

function OnboardingChecklist({
  nwzVerified,
  linked,
  hasTopic,
}: {
  nwzVerified: boolean;
  linked: boolean;
  hasTopic: boolean;
}) {
  const steps = [
    {
      done: nwzVerified,
      title: "NWZ-Zugang verifizieren",
      desc: "Hinterlege einmalig deine NWZ-Login-Daten, um Artikel zu durchsuchen.",
      href: "/nwz",
      cta: "Verifizieren",
    },
    {
      done: linked,
      title: "Telegram verbinden",
      desc: "Verknüpfe dein Konto mit dem Bot für Benachrichtigungen.",
      href: "/link",
      cta: "Verbinden",
    },
    {
      done: hasTopic,
      title: "Erstes Thema anlegen",
      desc: linked ? "Lege ein Thema an, nach dem der Bot täglich sucht." : "Zuerst Telegram verbinden.",
      href: "/topics",
      cta: "Thema anlegen",
      locked: !linked,
    },
  ];

  const doneCount = steps.filter((s) => s.done).length;
  const pct = Math.round((doneCount / steps.length) * 100);

  // Once everything's set up, the checklist disappears to reduce clutter.
  if (doneCount === steps.length) return null;

  // Index of the next actionable (not done, not locked) step — only it gets the CTA.
  const nextIdx = steps.findIndex((s) => !s.done && !s.locked);

  return (
    <Card className="mt-6 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold text-foreground">Erste Schritte</h2>
          <p className="text-sm text-muted-foreground">Schließe die Einrichtung ab, um alle Funktionen zu nutzen.</p>
        </div>
        <span className="shrink-0 text-sm font-medium text-muted-foreground">{doneCount}/{steps.length}</span>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>

      <ol className="mt-4 space-y-2">
        {steps.map((step, i) => (
          <li
            key={step.title}
            className={cn(
              "flex items-center gap-3 rounded-lg border p-3 transition-colors",
              step.done ? "border-border bg-muted/40" : i === nextIdx ? "border-primary/40 bg-primary/5" : "border-border",
            )}
          >
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                step.done ? "bg-green-100 text-green-700" : "border border-border bg-card text-muted-foreground",
              )}
            >
              {step.done ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className={cn("text-sm font-medium", step.done ? "text-muted-foreground line-through" : "text-foreground")}>
                {step.title}
              </p>
              <p className="text-xs text-muted-foreground">{step.desc}</p>
            </div>
            {step.done ? (
              <Badge color="green">Erledigt</Badge>
            ) : i === nextIdx ? (
              <Button asChild size="sm">
                <Link href={step.href}>
                  {step.cta} <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            ) : null}
          </li>
        ))}
      </ol>
    </Card>
  );
}
