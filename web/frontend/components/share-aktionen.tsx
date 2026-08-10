"use client";

/**
 * Aktionsleiste unter einer geteilten Antwort (Task 31c): Eingeloggte springen
 * mit einem Klick ins Ratsgespräch und fragen zur geteilten Antwort weiter
 * (?share=<token> lädt sie dort als ersten Turn); wer kein Konto hat, bekommt
 * Registrieren/Anmelden — mit `?weiter=` direkt aufs Weiterfragen, damit das
 * Ziel den Login-Umweg überlebt. Client-Insel in der Server-Seite /g.
 */
import Link from "next/link";
import { MessageSquarePlus, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { mitRuecksprung } from "@/lib/public-routes";

export function ShareAktionen({ token }: { token: string }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  const ziel = `/council?tab=decisions&mode=fragen&share=${encodeURIComponent(token)}`;
  if (user) {
    return (
      <div className="mt-6">
        <Link href={ziel}
          className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <MessageSquarePlus className="h-4 w-4" aria-hidden />
          Im Ratsgespräch weiterfragen
        </Link>
      </div>
    );
  }
  return (
    <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-4">
      <p className="text-sm font-semibold">Selbst weiterfragen?</p>
      <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">
        Mit einem kostenlosen Konto kannst du an diese Antwort anknüpfen und dem
        Rat eigene Fragen stellen — mit Quellen zu jedem zitierten Beschluss.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={mitRuecksprung("/register", ziel)}
          className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> Kostenlos registrieren
        </Link>
        <Link href={mitRuecksprung("/login", ziel)}
          className="inline-flex items-center rounded-full border border-border bg-card px-4 py-1.5 text-sm font-medium transition-colors hover:bg-muted">
          Anmelden
        </Link>
      </div>
    </div>
  );
}
