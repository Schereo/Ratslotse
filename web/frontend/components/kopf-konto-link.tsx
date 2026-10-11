"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

/** Rechts im Kopf der Textseiten (Hilfe, Impressum, Datenschutz, …).
 *
 *  Dort stand bis 10/2026 fest „Anmelden →" — auch für alle, die aus der App
 *  über den Fuß der Seitenleiste kamen und längst angemeldet waren. Der Weg
 *  zurück in die App fehlte damit ausgerechnet dort, wo man nur kurz
 *  nachschlagen wollte. Bis `/auth/me` antwortet, steht nichts (statt
 *  kurz das Falsche). */
export function KopfKontoLink() {
  const { user, loading } = useAuth();
  if (loading) return <span aria-hidden className="text-sm">&nbsp;</span>;
  return user ? (
    <Link href="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">Zurück zur App →</Link>
  ) : (
    <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
  );
}
