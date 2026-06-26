"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

// Auth-aware call-to-action for the public landing page: "Zum Dashboard" once
// signed in, otherwise "Anmelden". A small client island so the landing page
// itself can stay a server component (good for SEO).
export function HeaderCTA() {
  const { user, loading } = useAuth();
  if (loading) return <span className="inline-block h-9 w-32 rounded-lg bg-muted/50" aria-hidden />;
  return (
    <Link
      href={user ? "/dashboard" : "/login"}
      className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
    >
      {user ? "Zum Dashboard" : "Anmelden"} <span aria-hidden>→</span>
    </Link>
  );
}
