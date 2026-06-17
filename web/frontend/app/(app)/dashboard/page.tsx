"use client";

import Link from "next/link";
import { Newspaper, Landmark, Tags, Link2, ShieldCheck, ShieldAlert } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Badge, Card } from "@/components/ui";

const tiles = [
  { href: "/nwz", title: "Artikelsuche", desc: "Das Artikel-Archiv per Volltext durchsuchen.", icon: Newspaper },
  { href: "/council", title: "Ratsinformationssystem", desc: "Sitzungen und Tagesordnungen durchsuchen.", icon: Landmark },
  { href: "/topics", title: "Meine Themen", desc: "Themen verwalten und Treffer ansehen.", icon: Tags },
  { href: "/link", title: "Telegram verbinden", desc: "Konto mit dem Bot verknüpfen.", icon: Link2 },
];

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Willkommen zurück</h1>
          <p className="mt-1 text-sm text-muted-foreground">{user?.email}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {user?.linked ? <Badge color="green">Telegram verbunden</Badge> : <Badge color="amber">Telegram nicht verbunden</Badge>}
          {user?.nwz_verified ? <Badge color="green">NWZ verifiziert</Badge> : <Badge color="amber">NWZ nicht verifiziert</Badge>}
        </div>
      </div>

      {!user?.nwz_verified && (
        <Card className="mt-6 flex items-start gap-3 border-amber-200 bg-amber-50 p-4">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800">
            Für die NWZ-Suche musst du einmalig deine eigenen NWZ-Zugangsdaten hinterlegen.{" "}
            <Link href="/nwz" className="font-semibold underline">Jetzt verifizieren →</Link>
          </p>
        </Card>
      )}

      {!user?.linked && (
        <Card className="mt-4 flex items-start gap-3 border-amber-200 bg-amber-50 p-4">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800">
            Verknüpfe dein Konto mit Telegram, um Themen anzulegen und Benachrichtigungen zu erhalten.{" "}
            <Link href="/link" className="font-semibold underline">Jetzt verbinden →</Link>
          </p>
        </Card>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {tiles.map((t) => {
          const Icon = t.icon;
          return (
            <Link key={t.href} href={t.href}>
              <Card className="p-5 transition-shadow hover:shadow-md">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <h2 className="font-semibold text-foreground">{t.title}</h2>
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
