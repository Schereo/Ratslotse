"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/dashboard", label: "Übersicht", icon: "🏠" },
  { href: "/nwz", label: "NWZ-Suche", icon: "📰" },
  { href: "/council", label: "Ratsinfo", icon: "🏛️" },
  { href: "/topics", label: "Meine Themen", icon: "📌" },
  { href: "/link", label: "Telegram", icon: "🔗" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const navItems = [...links];
  if (user?.role === "admin") navItems.push({ href: "/admin", label: "Admin", icon: "⚙️" });

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="px-5 py-5">
        <span className="text-lg font-bold text-slate-900">NWZ-Bot</span>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((l) => {
          const active = pathname === l.href || pathname.startsWith(l.href + "/");
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span>{l.icon}</span>
              {l.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-slate-200 p-3">
        <div className="px-2 pb-2 text-xs text-slate-400">{user?.email}</div>
        <button
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          <span>↩</span> Abmelden
        </button>
      </div>
    </aside>
  );
}
