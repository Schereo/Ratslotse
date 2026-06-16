"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { Badge, Card } from "@/components/ui";

const tiles = [
  { href: "/nwz", title: "NWZ-Suche", desc: "Das Artikel-Archiv per Volltext durchsuchen.", icon: "📰" },
  { href: "/council", title: "Ratsinformationssystem", desc: "Sitzungen und Tagesordnungen durchsuchen.", icon: "🏛️" },
  { href: "/topics", title: "Meine Themen", desc: "Themen verwalten und Treffer ansehen.", icon: "📌" },
  { href: "/link", title: "Telegram verbinden", desc: "Konto mit dem Bot verknüpfen.", icon: "🔗" },
];

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Willkommen zurück</h1>
          <p className="mt-1 text-sm text-slate-500">{user?.email}</p>
        </div>
        {user?.linked ? (
          <Badge color="green">Mit Telegram verbunden</Badge>
        ) : (
          <Badge color="amber">Nicht mit Telegram verbunden</Badge>
        )}
      </div>

      {!user?.linked && (
        <Card className="mt-6 border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-800">
            Verknüpfe dein Konto mit Telegram, um Themen anzulegen und Benachrichtigungen zu erhalten.{" "}
            <Link href="/link" className="font-semibold underline">
              Jetzt verbinden →
            </Link>
          </p>
        </Card>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {tiles.map((t) => (
          <Link key={t.href} href={t.href}>
            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{t.icon}</span>
                <div>
                  <h2 className="font-semibold text-slate-900">{t.title}</h2>
                  <p className="mt-0.5 text-sm text-slate-500">{t.desc}</p>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
